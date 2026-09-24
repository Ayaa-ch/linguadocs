import uuid
import time


def test_isolation_alice_bob(client):
    # créer alice et bob
    email_alice = f"alice_{uuid.uuid4().hex[:8]}@test.com"
    r = client.post("/auth/register", json={"email": email_alice, "password": "AlicePass123"})
    assert r.status_code == 201
    token_alice = r.json()["access_token"]

    email_bob = f"bob_{uuid.uuid4().hex[:8]}@test.com"
    r = client.post("/auth/register", json={"email": email_bob, "password": "BobPass123"})
    assert r.status_code == 201
    token_bob = r.json()["access_token"]

    # phrase unique secrète
    secret = f"PHRASE_SECRETE_{uuid.uuid4().hex}_ALICE"
    alice_content = f"Ceci est le document d'Alice. {secret} Ne pas divulguer.".encode("utf-8")

    # alice uploade TXT
    r = client.post(
        "/documents",
        headers={"Authorization": f"Bearer {token_alice}"},
        files={"file": ("alice_secret.txt", alice_content, "text/plain")},
    )
    assert r.status_code == 201, r.text
    doc_id = r.json()["id"]

    # attendre indexed (polling)
    for _ in range(20):
        r = client.get(f"/documents/{doc_id}", headers={"Authorization": f"Bearer {token_alice}"})
        assert r.status_code == 200
        if r.json()["status"] == "indexed":
            break
        if r.json()["status"] == "error":
            assert False, f"indexation error: {r.json()['error']}"
        time.sleep(0.5)
    else:
        assert False, "timeout attente indexed"

    # bob pose question qui cible exactement la phrase secrète
    r = client.post(
        "/ask",
        headers={"Authorization": f"Bearer {token_bob}"},
        json={"question": secret, "stream": False},
    )
    assert r.status_code == 200, r.text
    data = r.json()
    assert "sources" in data
    sources = data["sources"]

    # vérifier que toutes les sources appartiennent à bob (doc_id de bob uniquement)
    # bob n'a aucun doc => sources doit être vide ou ne contenir que ses docs (aucun)
    # donc la phrase secrète ne doit pas apparaître
    for s in sources:
        # doc_id de bob ne peut pas être celui d'alice
        assert s.get("doc_id") != doc_id, "fuite isolation: bob a reçu doc_id d'alice"
        text = (s.get("text") or "")
        assert secret not in text, "phrase secrète d'alice fuite dans sources de bob"

    # alternative: réponse not found attendue
    if sources:
        # si sources non vides, s'assurer qu'elles ne contiennent pas secret
        assert all(secret not in (s.get("text") or "") for s in sources)
    else:
        # cas nominal: bob n'a pas de doc, donc pas de source
        assert data["answer"] == "Je ne trouve pas de réponse dans vos documents." or len(sources) == 0

    # vérifier côté alice qu'elle retrouve bien sa phrase
    r = client.post(
        "/ask",
        headers={"Authorization": f"Bearer {token_alice}"},
        json={"question": secret},
    )
    assert r.status_code == 200
    data_alice = r.json()
    assert len(data_alice["sources"]) > 0
    assert any(secret in (s.get("text") or "") or doc_id == s.get("doc_id") for s in data_alice["sources"])


def test_search_sans_user_id_leve_typeerror():
    from linguadocs.retrieval.dense import search

    try:
        search(None, "hello", k=5)
        assert False, "search(None) devrait lever TypeError"
    except TypeError as e:
        assert "user_id" in str(e).lower()

    try:
        # appel sans user_id du tout
        search(query="hello", k=5)  # type: ignore
        assert False, "search sans user_id devrait lever TypeError"
    except TypeError:
        pass
