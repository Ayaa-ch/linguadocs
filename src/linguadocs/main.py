from contextlib import asynccontextmanager

from fastapi import FastAPI

from linguadocs.api.database import init_db
from linguadocs.api.routes_auth import router as auth_router
from linguadocs.api.routes_documents import router as docs_router


@asynccontextmanager
async def lifespan(app: FastAPI):
    await init_db()
    # ensure Qdrant collection exists
    try:
        from linguadocs.retrieval.dense import init as qdrant_init

        qdrant_init(reset=False)
    except Exception:
        pass
    yield


app = FastAPI(title="LinguaDocs", version="0.1.0", lifespan=lifespan)

app.include_router(auth_router)
app.include_router(docs_router)


@app.get("/health", tags=["health"])
async def health():
    return {"status": "ok"}


@app.get("/", tags=["health"])
async def root():
    return {"status": "ok", "docs": "/docs"}
