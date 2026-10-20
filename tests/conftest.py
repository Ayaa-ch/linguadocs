import asyncio
import uuid

import pytest
from fastapi.testclient import TestClient
from sqlalchemy.ext.asyncio import create_async_engine
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool
from sqlmodel import SQLModel
from sqlmodel.ext.asyncio.session import AsyncSession

from linguadocs.main import app
from linguadocs.api.database import get_session

# Les tests ne doivent JAMAIS écrire dans la collection Qdrant de l'app
# ("chunks") : ils utilisent une collection dédiée, supprimable sans risque.
import linguadocs.retrieval.retrieval as _retrieval

_retrieval.COL = "chunks_test"

# SQLite en mémoire partagée pour les tests (pas PostgreSQL)
TEST_DB_URL = "sqlite+aiosqlite:///:memory:"

test_engine = create_async_engine(
    TEST_DB_URL,
    echo=False,
    future=True,
    poolclass=StaticPool,
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


asyncio.run(_create_tables())


async def get_test_session():
    async with TestSessionLocal() as session:
        yield session


app.dependency_overrides[get_session] = get_test_session


@pytest.fixture(scope="function")
def client():
    # nettoyer et recréer les tables avant chaque test (même engine, StaticPool)
    asyncio.run(_drop_tables())
    asyncio.run(_create_tables())
    with TestClient(app) as c:
        yield c


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
