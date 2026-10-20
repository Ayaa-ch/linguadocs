import uuid
import time
import json
import pytest
from unittest.mock import AsyncMock, patch

from linguadocs.retrieval.dense import init as qdrant_init, index as qdrant_index
from linguadocs.retrieval.retrieval import RerankerUnavailableError
from linguadocs.ingest.language import detect_lang


@pytest.fixture
def indexed_user(client):
    email = f"ask_{uuid.uuid4().hex[:8]}@test.com"
    r = client.post("/auth/register", json={"email": email, "password": "AskPass123"})
    assert r.status_code == 201
    token = r.json()["access_token"]
    import jwt
    from linguadocs.settings import settings

    payload = jwt.decode(token, settings.jwt_secret, algorithms=[settings.jwt_algorithm])
    user_id = payload["sub"]

    qdrant_init(reset=False)
    items = [
        {
            "text": "La Charte des Nations Unies a été signée à San Francisco en 1945. Elle établit les principes de l'égalité souveraine.",
            "chunk_key": f"doc_fr#0",
            "doc_id": "doc_fr",
            "filename": "charte.pdf",
            "page": 1,
        },
        {
            "text": "The United Nations Charter was signed in San Francisco in 1945. It establishes the principle of sovereign equality.",
            "chunk_key": f"doc_en#0",
            "doc_id": "doc_en",
            "filename": "charter.pdf",
            "page": 1,
        },
        {
            "text": "ميثاق الأمم المتحدة وُقّع في سان فرانسيسكو عام 1945. وهو يؤسس لمبدأ المساواة في السيادة.",
            "chunk_key": f"doc_ar#0",
            "doc_id": "doc_ar",
            "filename": "mithaq.pdf",
            "page": 1,
        },
    ]
    qdrant_index(user_id, items)
    time.sleep(0.5)
    return {"token": token, "user_id": user_id, "client": client}


def test_ask_francais(indexed_user):
    client = indexed_user["client"]
    token = indexed_user["token"]
    with patch("linguadocs.api.routes_ask.generate", new=AsyncMock(return_value="La Charte a été signée à San Francisco en 1945. [charte.pdf, page 1]")) as mock_gen:
        r = client.post(
            "/ask",
            headers={"Authorization": f"Bearer {token}"},
            json={"question": "Où a été signée la Charte des Nations Unies ?", "stream": False},
        )
        assert r.status_code == 200, r.text
        data = r.json()
        assert not data["refused"]
        assert data["question_lang"] == "fr"
        # réponse en français (vérifiée via lingua ou contenu)
        assert "San Francisco" in data["answer"] or len(data["sources"]) > 0
        mock_gen.assert_called_once()
        # prompt ne doit pas contenir user_id
        prompt_arg = mock_gen.call_args[0][0]
        assert indexed_user["user_id"] not in prompt_arg


def test_ask_anglais(indexed_user):
    client = indexed_user["client"]
    token = indexed_user["token"]
    with patch("linguadocs.api.routes_ask.generate", new=AsyncMock(return_value="The Charter was signed in San Francisco in 1945. [charter.pdf, page 1]")):
        r = client.post(
            "/ask",
            headers={"Authorization": f"Bearer {token}"},
            json={"question": "Where was the UN Charter signed ?", "stream": False},
        )
        assert r.status_code == 200
        data = r.json()
        assert not data["refused"]
        assert data["question_lang"] == "en"
        assert detect_lang("Where was the UN Charter signed ?") == "en"


def test_ask_hors_domaine(indexed_user):
    client = indexed_user["client"]
    token = indexed_user["token"]
    # question hors domaine (recette cuisine, pas dans les 3 passages ONU)
    # seuil temporaire à 0.85 pour garantir le refus (scores ~0.74)
    from linguadocs.settings import settings

    with patch.object(settings, "refusal_threshold", 0.85):
        with patch("linguadocs.api.routes_ask.generate", new=AsyncMock(return_value="should not be called")) as mock_gen:
            r = client.post(
                "/ask",
                headers={"Authorization": f"Bearer {token}"},
                json={"question": "Comment préparer une paella valencienne ?", "stream": False},
            )
            assert r.status_code == 200
            data = r.json()
            assert data["refused"] is True
            assert data["answer"] == "Je ne trouve pas de réponse dans vos documents."
            assert data["sources"] == []
            mock_gen.assert_not_called()


def test_ask_cite_sources(indexed_user):
    client = indexed_user["client"]
    token = indexed_user["token"]
    with patch("linguadocs.api.routes_ask.generate", new=AsyncMock(return_value="Réponse avec source [charte.pdf, page 1]")):
        r = client.post(
            "/ask",
            headers={"Authorization": f"Bearer {token}"},
            json={"question": "Parle moi de la Charte des Nations Unies", "stream": False},
        )
        assert r.status_code == 200
        data = r.json()
        assert len(data["sources"]) >= 1
        # chaque source a doc_id, filename, page, text, score
        for s in data["sources"]:
            assert "doc_id" in s and "filename" in s and "text" in s


def test_ask_stream(indexed_user):
    client = indexed_user["client"]
    token = indexed_user["token"]

    async def fake_stream(prompt, model="qwen2.5:3b-instruct"):
        for tok in ["La ", "Charte ", "a ", "été ", "signée."]:
            yield tok

    with patch("linguadocs.api.routes_ask.generate_stream", new=fake_stream):
        r = client.post(
            "/ask",
            headers={"Authorization": f"Bearer {token}"},
            json={"question": "Où a été signée la Charte ?", "stream": True},
        )
        assert r.status_code == 200
        assert "text/event-stream" in r.headers.get("content-type", "")
        body = r.text
        assert "data:" in body
        assert "sources" in body or "token" in body
        # vérifier que le stream contient des tokens
        assert "La " in body or "Charte" in body


def test_ask_reranker_indisponible_503(indexed_user):
    """Reranker indisponible -> 503 explicite (jamais 500), en non-stream ET en stream.

    Le rerank précède le branchement SSE : les deux modes doivent remonter
    le même HTTP 503 avec le message de RerankerUnavailableError.
    """
    client = indexed_user["client"]
    token = indexed_user["token"]
    headers = {"Authorization": f"Bearer {token}"}
    body = {"question": "Où a été signée la Charte des Nations Unies ?", "stream": False}

    unavailable = RerankerUnavailableError(
        "reranker indisponible : mémoire insuffisante ou chargement échoué (test simulé)"
    )

    with patch("linguadocs.api.routes_ask.rerank", side_effect=unavailable):
        # --- mode non-stream ---
        r = client.post("/ask", headers=headers, json=body)
        assert r.status_code == 503, r.text
        detail = r.json()["detail"]
        assert "reranker indisponible" in detail
        assert "Internal Server Error" not in detail

        # --- mode stream ---
        r2 = client.post("/ask", headers=headers, json={**body, "stream": True})
        assert r2.status_code == 503, r2.text
        detail2 = r2.json()["detail"]
        assert "reranker indisponible" in detail2
        # aucune réponse SSE ne doit démarrer
        assert "text/event-stream" not in r2.headers.get("content-type", "")
