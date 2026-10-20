"""Routes tools : résumé, quiz, flashcards, traduction (contrats mocks.py).

Les lignes Document sont créées directement en base (pas d'indexation/Qdrant) :
les routes tools ne lisent que user_id/filename/n_pages du Document.
"""

import asyncio
import uuid

from sqlmodel import select

from conftest import TestSessionLocal
from linguadocs.api.models import Document, User
from linguadocs.settings import settings


def _auth(token: str) -> dict:
    return {"Authorization": f"Bearer {token}"}


def _register(client, prefix: str = "tools") -> tuple[str, str]:
    email = f"{prefix}_{uuid.uuid4().hex[:8]}@test.com"
    r = client.post("/auth/register", json={"email": email, "password": "Secret1234"})
    assert r.status_code == 201, r.text
    return email, r.json()["access_token"]


def _user_id(email: str) -> uuid.UUID:
    async def _get():
        async with TestSessionLocal() as sess:
            res = await sess.exec(select(User).where(User.email == email))
            return res.first().id

    return asyncio.run(_get())


def _make_doc(user_id: uuid.UUID, filename: str = "rapport.pdf", n_pages: int = 12) -> uuid.UUID:
    async def _create():
        async with TestSessionLocal() as sess:
            doc = Document(
                user_id=user_id,
                filename=filename,
                mime="application/pdf",
                doc_type="pdf",
                status="indexed",
                n_pages=n_pages,
            )
            sess.add(doc)
            await sess.commit()
            await sess.refresh(doc)
            return doc.id

    return asyncio.run(_create())


def test_page_range_clamp(client):
    email, token = _register(client)
    doc_id = _make_doc(_user_id(email), n_pages=5)
    r = client.post(
        "/summary",
        headers=_auth(token),
        json={"doc_id": str(doc_id), "page_from": 50, "page_to": 99, "language": "en"},
    )
    assert r.status_code == 200, r.text
    data = r.json()
    assert data["sources"] == []
    for src in data["sources"]:
        assert src["page"] <= 5


def test_tools_sans_token(client):
    email, token = _register(client)
    doc_id = _make_doc(_user_id(email))
    r = client.post("/summary", json={"doc_id": str(doc_id)})
    assert r.status_code == 403, f"expected 403 got {r.status_code}"


def test_doc_etranger_404(client):
    email_alice, token_alice = _register(client, "alice")
    doc_id = _make_doc(_user_id(email_alice))
    _, token_bob = _register(client, "bob")
    for path in ("/summary", "/quiz", "/flashcards", "/translate"):
        r = client.post(path, headers=_auth(token_bob), json={"doc_id": str(doc_id)})
        assert r.status_code == 404, f"{path}: expected 404 got {r.status_code} — {r.text}"


def test_doc_inconnu_404(client):
    _, token = _register(client)
    r = client.post(
        "/flashcards",
        headers=_auth(token),
        json={"doc_id": str(uuid.uuid4())},
    )
    assert r.status_code == 404


def test_flag_mock_off_501(client, monkeypatch):
    email, token = _register(client)
    doc_id = _make_doc(_user_id(email))
    monkeypatch.setattr(settings, "use_mock_summary", False)
    r = client.post(
        "/summary",
        headers=_auth(token),
        json={"doc_id": str(doc_id)},
    )
    assert r.status_code == 501
    monkeypatch.setattr(settings, "use_mock_summary", True)
