from contextlib import asynccontextmanager
from pathlib import Path
import asyncio

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles

from linguadocs.api.database import init_db
from linguadocs.api.routes_auth import me_router as me_router
from linguadocs.api.routes_auth import router as auth_router
from linguadocs.api.routes_ask import router as ask_router
from linguadocs.api.routes_documents import router as docs_router
from linguadocs.api.routes_history import router as history_router
from linguadocs.api.routes_tools import router as tools_router


@asynccontextmanager
async def lifespan(app: FastAPI):
    await init_db()
    try:
        from linguadocs.retrieval.dense import init as qdrant_init

        qdrant_init(reset=False)
    except Exception:
        pass
    # warm-up Ollama en tâche de fond : l'API démarre aussitôt,
    # le modèle charge en parallèle (robuste si Ollama est down)
    try:
        from linguadocs.llm.client import warmup_ollama

        asyncio.create_task(warmup_ollama())
    except Exception:
        pass
    yield


app = FastAPI(title="LinguaDocs", version="0.1.0", lifespan=lifespan)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(auth_router)
app.include_router(me_router)
app.include_router(docs_router)
app.include_router(ask_router)
app.include_router(history_router)
app.include_router(tools_router)


@app.get("/health", tags=["health"])
async def health():
    return {"status": "ok"}


# UI statique principale (HTML/CSS/JS maison) — montée APRÈS les routes :
# /auth, /documents, /ask, /history, /summary... gardent la priorité.
UI_DIR = Path(__file__).resolve().parents[2] / "ui"
if UI_DIR.is_dir():
    app.mount("/", StaticFiles(directory=str(UI_DIR), html=True), name="ui")
