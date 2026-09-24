import asyncio
import os
import uuid
from pathlib import Path

import pytest
from fastapi.testclient import TestClient
from sqlalchemy.ext.asyncio import create_async_engine
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import NullPool
from sqlmodel import SQLModel
from sqlmodel.ext.asyncio.session import AsyncSession

from linguadocs.main import app
from linguadocs.api.database import get_session

# SQLite fichier pour les tests (partagé entre event loops, pas PostgreSQL)
TEST_DB_PATH = Path("./test.db")
TEST_DB_URL = f"sqlite+aiosqlite:///{TEST_DB_PATH}"

test_engine = create_async_engine(
    TEST_DB_URL,
    echo=False,
    future=True,
    poolclass=NullPool,
    connect_args={"check_same_thread": False},
)
TestSessionLocal = sessionmaker(test_engine, class_=AsyncSession, expire_on_commit=False)

# patch database module pour que lifespan utilise SQLite en test
import linguadocs.api.database as db_module

db_module.engine = test_engine
db_module.AsyncSessionLocal = TestSessionLocal


async def _create_tables():
    async with test_engine.begin() as conn:
        await conn.run_sync(SQLModel.metadata.create_all)


async def _drop_tables():
    async with test_engine.begin() as conn:
        await conn.run_sync(SQLModel.metadata.drop_all)


async def get_test_session():
    async with TestSessionLocal() as session:
        yield session


# override FastAPI dependency
app.dependency_overrides[get_session] = get_test_session


@pytest.fixture(scope="function")
def client():
    # nettoyer et recréer les tables avant chaque test (même fichier, même engine)
    # on utilise asyncio.run car on est hors event loop (sync fixture)
    asyncio.run(_drop_tables())
    asyncio.run(_create_tables())
    with TestClient(app) as c:
        yield c
    # optionnel: nettoyer après
    # asyncio.run(_drop_tables())
    # ne pas supprimer le fichier, il sera réutilisé


@pytest.fixture
def token_alice(client):
    email = f"alice_{uuid.uuid4().hex[:8]}@test.com"
    r = client.post("/auth/register", json={"email": email, "password": "AlicePass123"})
    assert r.status_code == 201, r.text
    return r.json()["access_token"]


@pytest.fixture
def token_bob(client):
    email = f"bob_{uuid.uuid4().hex[:8]}@test.com"
    r = client.post("/auth/register", json={"email": email, "password": "BobPass123"})
    assert r.status_code == 201, r.text
    return r.json()["access_token"]
