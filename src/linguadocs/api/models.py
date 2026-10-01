import uuid
from datetime import datetime, timezone
from typing import Optional

from sqlmodel import SQLModel, Field


class User(SQLModel, table=True):
    __tablename__ = "users"  # type: ignore

    id: uuid.UUID = Field(default_factory=uuid.uuid4, primary_key=True)
    email: str = Field(unique=True, index=True, max_length=255)
    password_hash: str = Field(max_length=512)
    created_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))


class Document(SQLModel, table=True):
    __tablename__ = "documents"  # type: ignore

    id: uuid.UUID = Field(default_factory=uuid.uuid4, primary_key=True)
    user_id: uuid.UUID = Field(foreign_key="users.id", index=True)
    filename: str = Field(max_length=512)
    mime: str = Field(max_length=128)
    doc_type: str = Field(max_length=16)  # pdf, txt, md, docx
    status: str = Field(default="queued", max_length=16)  # queued/processing/indexed/error
    lang: Optional[str] = Field(default=None, max_length=8)
    n_pages: Optional[int] = Field(default=None)
    error: Optional[str] = Field(default=None, max_length=1024)
    created_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))


class ChatMessage(SQLModel, table=True):
    """Historique par utilisateur + par document. Isolation via user_id (JWT)."""

    __tablename__ = "chat_messages"  # type: ignore

    id: uuid.UUID = Field(default_factory=uuid.uuid4, primary_key=True)
    user_id: uuid.UUID = Field(foreign_key="users.id", index=True)
    doc_id: str = Field(index=True, max_length=64)  # str(doc.uuid), pas de FK stricte
    role: str = Field(max_length=8)  # user | bot
    content: str = Field(max_length=8000)  # question ou réponse
    sources_json: Optional[str] = Field(default=None, max_length=16000)
    question_lang: Optional[str] = Field(default=None, max_length=8)
    refused: bool = Field(default=False)
    created_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))
