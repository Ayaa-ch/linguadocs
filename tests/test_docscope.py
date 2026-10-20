import time
import uuid


def _upload(client, token, name, text):
    r = client.post(
        "/documents",
        headers={"Authorization": f"Bearer {token}"},
        files={"file": (name, text.encode("utf-8"), "text/plain")},
    )
    assert r.status_code == 201, r.text
    doc_id = r.json()["id"]
    for _ in range(20):
        r = client.get(f"/documents/{doc_id}", headers={"Authorization": f"Bearer {token}"})
        assert r.status_code == 200
        st = r.json()["status"]
        if st == "indexed":
            break
        assert st != "error", r.json().get("error")
        time.sleep(0.5)
    else:
        raise AssertionError("timeout attente indexed")
    return doc_id


def test_ask_doc_scope(client):
    # même utilisateur, deux docs avec secrets distincts
    email = f"scope_{uuid.uuid4().hex[:8]}@test.com"
    r = client.post("/auth/register", json={"email": email, "password": "ScopePass123"})
    assert r.status_code == 201
    token = r.json()["access_token"]

    secret_a = f"SECRET_DOC_A_{uuid.uuid4().hex}"
    secret_b = f"SECRET_DOC_B_{uuid.uuid4().hex}"
    doc_a = _upload(client, token, "doc_a.txt", f"Document A. {secret_a} Fin A.")
    doc_b = _upload(client, token, "doc_b.txt", f"Document B. {secret_b} Fin B.")

    from unittest.mock import AsyncMock, patch

    with patch("linguadocs.api.routes_ask.generate", new=AsyncMock(return_value="ok")):
        # question sur A ciblée sur doc B => le secret A ne doit JAMAIS apparaître
        r = client.post(
            "/ask",
            headers={"Authorization": f"Bearer {token}"},
            json={"question": secret_a, "stream": False, "doc_id": doc_b},
        )
        assert r.status_code == 200, r.text
        data = r.json()
        assert secret_a not in data.get("answer", "")
        for s in data["sources"]:
            assert s.get("doc_id") == doc_b, f"fuite doc: {s.get('doc_id')} != {doc_b}"
            assert secret_a not in (s.get("text") or "")

        # question sur A ciblée sur doc A => sources uniquement de A
        r = client.post(
            "/ask",
            headers={"Authorization": f"Bearer {token}"},
            json={"question": secret_a, "stream": False, "doc_id": doc_a},
        )
        assert r.status_code == 200, r.text
        data = r.json()
        assert len(data["sources"]) > 0
        for s in data["sources"]:
            assert s.get("doc_id") == doc_a, f"fuite doc: {s.get('doc_id')} != {doc_a}"

        # sans doc_id => comportement inchangé (tous les docs)
        r = client.post(
            "/ask",
            headers={"Authorization": f"Bearer {token}"},
            json={"question": secret_a, "stream": False},
        )
        assert r.status_code == 200, r.text

    # doc_id inexistant => 404
    r = client.post(
        "/ask",
        headers={"Authorization": f"Bearer {token}"},
        json={"question": "hello", "stream": False, "doc_id": "00000000-0000-0000-0000-000000000000"},
    )
    assert r.status_code == 404, r.text

    # doc_id d'un autre utilisateur => 404 (indistinguable d'inexistant)
    email2 = f"scope2_{uuid.uuid4().hex[:8]}@test.com"
    r = client.post("/auth/register", json={"email": email2, "password": "ScopePass123"})
    token2 = r.json()["access_token"]
    r = client.post(
        "/ask",
        headers={"Authorization": f"Bearer {token2}"},
        json={"question": "hello", "stream": False, "doc_id": doc_a},
    )
    assert r.status_code == 404, r.text


def test_ask_doc_not_indexed_409(client):
    # doc existant mais pas indexed => 409
    import asyncio

    from sqlmodel import select

    from linguadocs.api.models import Document, User
    from conftest import TestSessionLocal

    email = f"scope409_{uuid.uuid4().hex[:8]}@test.com"
    r = client.post("/auth/register", json={"email": email, "password": "ScopePass123"})
    assert r.status_code == 201
    token = r.json()["access_token"]

    async def _mk_queued():
        async with TestSessionLocal() as s:
            u = (await s.exec(select(User).where(User.email == email))).first()
            d = Document(
                user_id=u.id, filename="pending.txt",
                mime="text/plain", doc_type="txt", status="queued",
            )
            s.add(d)
            await s.commit()
            await s.refresh(d)
            return str(d.id)

    doc_id = asyncio.run(_mk_queued())
    r = client.post(
        "/ask",
        headers={"Authorization": f"Bearer {token}"},
        json={"question": "hello", "stream": False, "doc_id": doc_id},
    )
    assert r.status_code == 409, r.text
