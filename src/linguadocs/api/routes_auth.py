import shutil
from pathlib import Path

from fastapi import APIRouter, Depends, HTTPException, status
from pydantic import BaseModel, EmailStr
from sqlmodel import select
from sqlmodel.ext.asyncio.session import AsyncSession

from linguadocs.api.auth import create_token, current_user, hash_password, verify_password
from linguadocs.api.database import get_session
from linguadocs.api.models import Document, User
from linguadocs.settings import settings

router = APIRouter(prefix="/auth", tags=["auth"])
# route alias sans prefix pour DELETE /me (spec demande /me, router a prefix /auth)
me_router = APIRouter(tags=["auth"])


class RegisterRequest(BaseModel):
    email: EmailStr
    password: str


class LoginRequest(BaseModel):
    email: EmailStr
    password: str


class TokenResponse(BaseModel):
    access_token: str
    token_type: str = "bearer"


@router.post("/register", response_model=TokenResponse, status_code=status.HTTP_201_CREATED)
async def register(payload: RegisterRequest, session: AsyncSession = Depends(get_session)):
    # check existing
    result = await session.exec(select(User).where(User.email == payload.email.lower().strip()))
    existing = result.first()
    if existing:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Email déjà utilisé")

    if len(payload.password) < 8:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Mot de passe trop court (min 8)")

    user = User(email=payload.email.lower().strip(), password_hash=hash_password(payload.password))
    session.add(user)
    await session.commit()
    await session.refresh(user)

    token = create_token(user.id)
    return TokenResponse(access_token=token)


@router.post("/login", response_model=TokenResponse)
async def login(payload: LoginRequest, session: AsyncSession = Depends(get_session)):
    result = await session.exec(select(User).where(User.email == payload.email.lower().strip()))
    user = result.first()
    if not user or not verify_password(payload.password, user.password_hash):
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Email ou mot de passe incorrect")

    token = create_token(user.id)
    return TokenResponse(access_token=token)


async def _delete_account(user: User, session: AsyncSession):
    # user_id vient du token JWT uniquement
    # 1. supprimer tous les documents (fichiers + vecteurs Qdrant + lignes SQL)
    result = await session.exec(select(Document).where(Document.user_id == user.id))
    docs = result.all()

    # vecteurs Qdrant : bulk delete par user_id
    try:
        from linguadocs.retrieval.retrieval import client, COL
        from qdrant_client import models

        flt_user = models.Filter(
            must=[models.FieldCondition(key="user_id", match=models.MatchValue(value=str(user.id)))]
        )
        client.delete(collection_name=COL, points_selector=flt_user, wait=True)
    except Exception:
        pass

    # fichiers sur disque
    user_dir = Path(settings.data_dir) / str(user.id)
    if user_dir.exists():
        shutil.rmtree(user_dir, ignore_errors=True)

    # lignes Document
    for d in docs:
        await session.delete(d)

    # 2. supprimer l'utilisateur
    await session.delete(user)
    await session.commit()
    return {"detail": "Compte supprimé"}


@router.delete("/me", status_code=status.HTTP_200_OK)
async def delete_me(
    user: User = Depends(current_user),
    session: AsyncSession = Depends(get_session),
):
    return await _delete_account(user, session)


@me_router.delete("/me", status_code=status.HTTP_200_OK)
async def delete_me_alias(
    user: User = Depends(current_user),
    session: AsyncSession = Depends(get_session),
):
    return await _delete_account(user, session)
