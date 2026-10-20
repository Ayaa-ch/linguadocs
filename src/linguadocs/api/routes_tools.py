"""Routes « tools » document : résumé, quiz, flashcards, traduction.

Contrats JSON strictement identiques à mocks.py à la racine (source unique de
vérité partagée avec l'UI Streamlit archivée). mocks.py est chargé paresseusement
via importlib (il vit à la racine du repo, hors du package).

Flags settings.use_mock_* (env USE_MOCK_SUMMARY/QUIZ/FLASHCARDS/TRANSLATE,
défaut true) : si false, la route répond 501 — place réservée aux futures
vraies routes LLM (Ollama) sans changer le contrat ni le front.

Sécurité : auth JWT obligatoire, ownership du document vérifié en base,
les champs filename/n_pages viennent du Document serveur (jamais du client).
"""

from __future__ import annotations

import asyncio
import importlib.util
import uuid
from pathlib import Path
from typing import Any, Literal

from fastapi import APIRouter, Depends, HTTPException, status
from pydantic import BaseModel, Field
from sqlmodel import select
from sqlmodel.ext.asyncio.session import AsyncSession

from linguadocs.api.auth import current_user
from linguadocs.api.database import get_session
from linguadocs.api.models import Document, User
from linguadocs.settings import settings

router = APIRouter(tags=["tools"])

# src/linguadocs/api/routes_tools.py -> racine du repo = parents[3]
_MOCKS_PATH = Path(__file__).resolve().parents[3] / "mocks.py"
_mocks_module: Any = None


def _load_mocks() -> Any:
    global _mocks_module
    if _mocks_module is not None:
        return _mocks_module
    if not _MOCKS_PATH.exists():
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="mocks.py introuvable à la racine du dépôt",
        )
    spec = importlib.util.spec_from_file_location("linguadocs_root_mocks", _MOCKS_PATH)
    if spec is None or spec.loader is None:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="mocks.py illisible",
        )
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    _mocks_module = module
    return module


def _ensure_mock(flag: bool, route_name: str) -> None:
    if not flag:
        raise HTTPException(
            status_code=status.HTTP_501_NOT_IMPLEMENTED,
            detail=f"{route_name} : route LLM réelle non implémentée (activez USE_MOCK_*=true)",
        )


async def _owned_doc(doc_id: uuid.UUID, user: User, session: AsyncSession) -> Document:
    result = await session.exec(
        select(Document).where(Document.id == doc_id, Document.user_id == user.id)
    )
    doc = result.first()
    if not doc:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Document introuvable")
    return doc


def _clamp(value: int | None, lo: int, hi: int, default: int | None = None) -> int | None:
    if value is None:
        return default
    return max(lo, min(hi, value))


class SummaryRequest(BaseModel):
    doc_id: uuid.UUID
    length: Literal["short", "medium", "long"] = "medium"
    language: str = Field(default="en", max_length=8)
    page_from: int | None = None
    page_to: int | None = None


class QuizRequest(BaseModel):
    doc_id: uuid.UUID
    n_questions: int = Field(default=10, ge=1, le=20)
    difficulty: Literal["easy", "medium", "hard"] = "medium"
    language: str = Field(default="en", max_length=8)


class FlashcardsRequest(BaseModel):
    doc_id: uuid.UUID
    n_cards: int = Field(default=20, ge=1, le=50)
    language: str = Field(default="en", max_length=8)


class TranslateRequest(BaseModel):
    doc_id: uuid.UUID
    source_lang: str = Field(default="en", max_length=8)
    target_lang: str = Field(default="fr", max_length=8)
    page_from: int | None = None
    page_to: int | None = None


@router.post("/summary")
async def summarize_document(
    payload: SummaryRequest,
    user: User = Depends(current_user),
    session: AsyncSession = Depends(get_session),
):
    _ensure_mock(settings.use_mock_summary, "/summary")
    doc = await _owned_doc(payload.doc_id, user, session)
    n_pages = doc.n_pages or 1
    page_from = _clamp(payload.page_from, 1, max(1, n_pages), default=1)
    page_to = _clamp(payload.page_to, page_from or 1, max(1, n_pages), default=n_pages)
    return await asyncio.to_thread(
        _load_mocks().summarize,
        str(doc.id),
        doc.filename,
        n_pages,
        payload.length,
        payload.language,
        page_from,
        page_to,
    )


@router.post("/quiz")
async def generate_quiz(
    payload: QuizRequest,
    user: User = Depends(current_user),
    session: AsyncSession = Depends(get_session),
):
    _ensure_mock(settings.use_mock_quiz, "/quiz")
    doc = await _owned_doc(payload.doc_id, user, session)
    return await asyncio.to_thread(
        _load_mocks().generate_quiz,
        str(doc.id),
        doc.filename,
        payload.n_questions,
        payload.difficulty,
        payload.language,
    )


@router.post("/flashcards")
async def generate_flashcards(
    payload: FlashcardsRequest,
    user: User = Depends(current_user),
    session: AsyncSession = Depends(get_session),
):
    _ensure_mock(settings.use_mock_flashcards, "/flashcards")
    doc = await _owned_doc(payload.doc_id, user, session)
    return await asyncio.to_thread(
        _load_mocks().generate_flashcards,
        str(doc.id),
        doc.filename,
        payload.n_cards,
        payload.language,
    )


@router.post("/translate")
async def translate_document(
    payload: TranslateRequest,
    user: User = Depends(current_user),
    session: AsyncSession = Depends(get_session),
):
    _ensure_mock(settings.use_mock_translate, "/translate")
    doc = await _owned_doc(payload.doc_id, user, session)
    n_pages = doc.n_pages or 1
    page_from = _clamp(payload.page_from, 1, max(1, n_pages), default=1)
    page_to = _clamp(payload.page_to, page_from or 1, max(1, n_pages), default=n_pages)
    return await asyncio.to_thread(
        _load_mocks().translate,
        str(doc.id),
        doc.filename,
        payload.source_lang,
        payload.target_lang,
        page_from,
        page_to,
    )
