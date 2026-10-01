from __future__ import annotations

import json
import uuid

from fastapi import APIRouter, Depends, Query
from pydantic import BaseModel
from sqlmodel import delete, select
from sqlmodel.ext.asyncio.session import AsyncSession

from linguadocs.api.auth import current_user
from linguadocs.api.database import get_session
from linguadocs.api.models import ChatMessage, User

router = APIRouter(prefix="/history", tags=["history"])


class HistoryIn(BaseModel):
    doc_id: str
    role: str  # user | bot
    content: str
    sources: list[dict] | None = None
    question_lang: str | None = None
    refused: bool = False


def _to_out(m: ChatMessage) -> dict:
    try:
        sources = json.loads(m.sources_json) if m.sources_json else []
    except Exception:
        sources = []
    return {
        "id": str(m.id),
        "doc_id": m.doc_id,
        "role": m.role,
        "content": m.content,
        "sources": sources,
        "question_lang": m.question_lang,
        "refused": m.refused,
        "created_at": m.created_at.isoformat() if m.created_at else None,
    }


@router.post("")
async def save_message(
    payload: HistoryIn,
    user: User = Depends(current_user),
    session: AsyncSession = Depends(get_session),
):
    role = payload.role if payload.role in ("user", "bot") else "user"
    msg = ChatMessage(
        user_id=user.id,
        doc_id=payload.doc_id[:64],
        role=role,
        content=payload.content[:8000],
        sources_json=json.dumps(payload.sources or [], ensure_ascii=False)[:16000],
        question_lang=(payload.question_lang or "")[:8] or None,
        refused=bool(payload.refused),
    )
    session.add(msg)
    await session.commit()
    await session.refresh(msg)
    return _to_out(msg)


@router.get("")
async def get_history(
    doc_id: str = Query(...),
    limit: int = Query(100, ge=1, le=500),
    user: User = Depends(current_user),
    session: AsyncSession = Depends(get_session),
):
    # isolation stricte : filtre user_id obligatoire (JWT, jamais client)
    res = await session.exec(
        select(ChatMessage)
        .where(ChatMessage.user_id == user.id, ChatMessage.doc_id == doc_id[:64])
        .order_by(ChatMessage.created_at.asc())
        .limit(limit)
    )
    msgs = res.all()
    return [_to_out(m) for m in msgs]


@router.delete("")
async def clear_history(
    doc_id: str = Query(...),
    user: User = Depends(current_user),
    session: AsyncSession = Depends(get_session),
):
    await session.exec(
        delete(ChatMessage).where(
            ChatMessage.user_id == user.id, ChatMessage.doc_id == doc_id[:64]
        )
    )
    await session.commit()
    return {"ok": True}


def delete_doc_history_sync(doc_id: str, user_id: uuid.UUID, session) -> None:
    """Appelé lors de DELETE /documents/{id} (même session)."""
    # version sync appelée depuis route async avec await session.exec
    return None
