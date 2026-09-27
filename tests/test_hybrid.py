import uuid
import time
import pytest
from linguadocs.retrieval.retrieval import init as qdrant_init, index as qdrant_index


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
    from linguadocs.retrieval.retrieval import rerank

    # créer des résultats factices
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
