import uuid
import time
import pytest
from linguadocs.retrieval.retrieval import init as qdrant_init, index as qdrant_index


def _commit_free_bytes() -> int | None:
    """Commit charge libre (Windows) — psutil n'est pas une dépendance du projet.

    Retourne None si la plateforme ne le permet pas (l'appelant décide alors
    de ne pas sauter).
    """
    try:
        import ctypes

        class MEMORYSTATUSEX(ctypes.Structure):
            _fields_ = [
                ("dwLength", ctypes.c_ulong),
                ("dwMemoryLoad", ctypes.c_ulong),
                ("ullTotalPhys", ctypes.c_ulonglong),
                ("ullAvailPhys", ctypes.c_ulonglong),
                ("ullTotalPageFile", ctypes.c_ulonglong),
                ("ullAvailPageFile", ctypes.c_ulonglong),
                ("ullTotalVirtual", ctypes.c_ulonglong),
                ("ullAvailVirtual", ctypes.c_ulonglong),
                ("ullAvailExtendedVirtual", ctypes.c_ulonglong),
            ]

        stat = MEMORYSTATUSEX()
        stat.dwLength = ctypes.sizeof(stat)
        if not ctypes.windll.kernel32.GlobalMemoryStatusEx(ctypes.byref(stat)):
            return None
        return int(stat.ullAvailPageFile)
    except Exception:
        return None


@pytest.fixture
def indexed_user(client):
    import jwt
    from linguadocs.settings import settings

    email = f"ask_{uuid.uuid4().hex[:8]}@test.com"
    r = client.post("/auth/register", json={"email": email, "password": "AskPass123"})
    assert r.status_code == 201
    token = r.json()["access_token"]
    payload = jwt.decode(token, settings.jwt_secret, algorithms=[settings.jwt_algorithm])
    user_id = payload["sub"]
    qdrant_init(reset=False)
    items = [
        {
            "text": "La Charte des Nations Unies a été signée à San Francisco en 1945.",
            "chunk_key": f"doc_fr#0",
            "doc_id": "doc_fr",
            "filename": "charte.pdf",
            "page": 1,
        },
        {
            "text": "The United Nations Charter was signed in San Francisco in 1945.",
            "chunk_key": f"doc_en#0",
            "doc_id": "doc_en",
            "filename": "charter.pdf",
            "page": 1,
        },
        {
            "text": "ميثاق الأمم المتحدة وُقّع في سان فرانسيسكو عام 1945.",
            "chunk_key": f"doc_ar#0",
            "doc_id": "doc_ar",
            "filename": "mithaq.pdf",
            "page": 1,
        },
    ]
    qdrant_index(user_id, items)
    time.sleep(0.5)
    return {"token": token, "user_id": user_id, "client": client}


def test_search_dense(indexed_user):
    from linguadocs.retrieval.retrieval import search

    client = indexed_user["client"]
    token = indexed_user["token"]
    import jwt
    from linguadocs.settings import settings

    payload = jwt.decode(token, settings.jwt_secret, algorithms=[settings.jwt_algorithm])
    user_id = payload["sub"]

    hits = search(user_id, "Charte des Nations Unies", k=5)
    assert len(hits) > 0
    # vérifier que chaque hit a un payload avec user_id filtré
    for h in hits:
        assert h.payload.get("user_id") == user_id


def test_search_hybrid(indexed_user):
    from linguadocs.retrieval.retrieval import search_hybrid

    client = indexed_user["client"]
    token = indexed_user["token"]
    import jwt
    from linguadocs.settings import settings

    payload = jwt.decode(token, settings.jwt_secret, algorithms=[settings.jwt_algorithm])
    user_id = payload["sub"]

    hits = search_hybrid(user_id, "Charte des Nations Unies", k=5)
    assert len(hits) > 0
    for h in hits:
        assert h.payload.get("user_id") == user_id


def test_reranker():
    from linguadocs.retrieval.retrieval import RerankerUnavailableError, _get_reranker, rerank

    # bge-m3 (2,17 Go) + bge-reranker-v2-m3 (2,17 Go) doivent tenir ensemble.
    # Sous 3 Go de commit libre le CrossEncoder ne se charge pas : on saute
    # avec un message explicite plutôt que d'abaisser les assertions.
    MIN_COMMIT = 3 * 1024 ** 3
    commit_free = _commit_free_bytes()
    if commit_free is not None and commit_free < MIN_COMMIT:
        pytest.skip(
            "reranker non testable : commit libre "
            f"{commit_free / 1024 ** 3:.2f} Go < 3 Go "
            "(bge-m3 + bge-reranker-v2-m3 = 4,34 Go de poids)"
        )
    try:
        _get_reranker()
    except RerankerUnavailableError as e:
        pytest.skip(str(e))

    class FakeHit:
        def __init__(self, text, score):
            self.payload = {"text": text, "chunk_key": text[:10]}
            self.score = score

    query = "Charte des Nations Unies signée à San Francisco"
    results = [
        FakeHit("Recette de cuisine paella", 0.9),
        FakeHit("Charte des Nations Unies signée à San Francisco en 1945", 0.5),
        FakeHit("Météo à Paris", 0.8),
    ]
    reranked = rerank(query, results, top_n=3)
    # le reranker doit changer l'ordre : le vrai passage sur la Charte doit remonter
    assert len(reranked) == 3
    # le meilleur après rerank doit être celui qui parle de la Charte
    top_text = reranked[0].payload["text"]
    assert "Charte" in top_text or "San Francisco" in top_text
    # s'assurer que l'ordre a changé (le premier initial était paella avec 0.9, après rerank il ne doit plus être premier)
    assert reranked[0].payload["text"] != "Recette de cuisine paella"


# (question, doc_id attendu même langue) — la phrase Charte existe en FR/EN/AR,
# "1945" est présent dans les 3 versions (marqueur inter-langues).
MULTILINGUAL_QUERIES = [
    ("Charte des Nations Unies signée à San Francisco", "doc_fr"),
    ("United Nations Charter signed in San Francisco", "doc_en"),
    ("ميثاق الأمم المتحدة سان فرانسيسكو", "doc_ar"),
]


def _user_id_of(token):
    import jwt
    from linguadocs.settings import settings

    return jwt.decode(token, settings.jwt_secret, algorithms=[settings.jwt_algorithm])["sub"]


def test_multilingual_dense_hybrid(indexed_user):
    """Chaque langue de question retrouve un chunk pertinent (top-5)."""
    from linguadocs.retrieval.retrieval import search, search_hybrid

    user_id = _user_id_of(indexed_user["token"])
    for question, expected_doc in MULTILINGUAL_QUERIES:
        for fn in (search, search_hybrid):
            hits = fn(user_id, question, k=5)
            assert len(hits) > 0, f"{fn.__name__} vide pour {question!r}"
            texts = [h.payload.get("text", "") for h in hits]
            # pertinent : la phrase Charte (n'importe quelle langue) dans le top-5
            assert any("1945" in t for t in texts), f"{fn.__name__} rate {question!r}"
            # idéal : le chunk de la même langue est présent
            doc_ids = [h.payload.get("doc_id") for h in hits]
            assert expected_doc in doc_ids, f"{fn.__name__} : {expected_doc} absent pour {question!r}"


def test_multilingual_rerank_sparse(indexed_user):
    """Rerank cross-lingue + sparse par langue."""
    from linguadocs.retrieval.retrieval import (
        RerankerUnavailableError,
        _get_reranker,
        rerank,
        search,
        search_sparse,
    )

    # Même garde que test_reranker : sans reranker chargeable, on saute.
    MIN_COMMIT = 3 * 1024 ** 3
    commit_free = _commit_free_bytes()
    if commit_free is not None and commit_free < MIN_COMMIT:
        pytest.skip(
            "reranker non testable : commit libre "
            f"{commit_free / 1024 ** 3:.2f} Go < 3 Go "
            "(bge-m3 + bge-reranker-v2-m3 = 4,34 Go de poids)"
        )
    try:
        _get_reranker()
    except RerankerUnavailableError as e:
        pytest.skip(str(e))

    user_id = _user_id_of(indexed_user["token"])
    for question, expected_doc in MULTILINGUAL_QUERIES:
        hits = search(user_id, question, k=5)
        ranked = rerank(question, hits, top_n=3)
        assert len(ranked) > 0
        assert any("1945" in (r.payload.get("text", "")) for r in ranked), f"rerank rate {question!r}"

        sp = search_sparse(user_id, question, k=5)
        assert len(sp) > 0, f"sparse vide pour {question!r}"
        assert expected_doc in [h.payload.get("doc_id") for h in sp], f"sparse rate {question!r}"


def test_isolation_hybrid(client):
    # deux utilisateurs, chacun a ses docs, hybrid doit filtrer
    import jwt
    from linguadocs.settings import settings
    from linguadocs.retrieval.retrieval import search_hybrid, init, index

    # alice
    email_a = f"alice_hybrid_{uuid.uuid4().hex[:8]}@test.com"
    r = client.post("/auth/register", json={"email": email_a, "password": "AlicePass123"})
    token_a = r.json()["access_token"]
    payload_a = jwt.decode(token_a, settings.jwt_secret, algorithms=[settings.jwt_algorithm])
    uid_a = payload_a["sub"]

    # bob
    email_b = f"bob_hybrid_{uuid.uuid4().hex[:8]}@test.com"
    r = client.post("/auth/register", json={"email": email_b, "password": "BobPass123"})
    token_b = r.json()["access_token"]
    payload_b = jwt.decode(token_b, settings.jwt_secret, algorithms=[settings.jwt_algorithm])
    uid_b = payload_b["sub"]

    # indexer un doc unique pour alice
    secret = f"SECRET_HYBRID_{uuid.uuid4().hex}"
    init(reset=False)
    from linguadocs.retrieval.retrieval import index as qindex

    qindex(uid_a, [{"text": f"Document alice {secret}", "chunk_key": "alice#0", "doc_id": "alice_doc", "filename": "a.txt", "page": 1}])
    time.sleep(0.3)

    # bob cherche le secret d'alice via hybrid -> ne doit rien trouver de Alice
    hits_b = search_hybrid(uid_b, secret, k=5)
    for h in hits_b:
        assert h.payload.get("user_id") == uid_b
        assert secret not in h.payload.get("text", "")

    # alice doit retrouver son secret
    hits_a = search_hybrid(uid_a, secret, k=5)
    assert len(hits_a) > 0
    assert any(secret in h.payload.get("text", "") for h in hits_a)

    # search_hybrid sans user_id doit lever TypeError
    try:
        search_hybrid(None, "test", k=5)
        assert False, "should raise TypeError"
    except TypeError as e:
        assert "user_id" in str(e).lower()
