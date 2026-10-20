from __future__ import annotations

from pathlib import Path
import uuid

from starlette.concurrency import run_in_threadpool
from sqlmodel import select
from sqlmodel.ext.asyncio.session import AsyncSession

from linguadocs.api.database import AsyncSessionLocal
from linguadocs.api.models import Document
from linguadocs.ingest.parsers import parse
from linguadocs.ingest.language import detect_lang, normalize
from linguadocs.ingest.chunker import chunk_pages


def _process_document(
    file_path: Path,
    doc_id: int | uuid.UUID,
    user_id: int | uuid.UUID,
    filename: str,
) -> tuple[str, int]:
    """
    Traitement lourd SYNCHRONE : parse -> detect_lang -> normalize -> chunk
    -> init Qdrant -> embedding -> upsert.

    Aucune opération DB ici. Cette fonction est CPU/IO-bound (pdfplumber,
    sentence-transformers, réseau Qdrant) et doit être exécutée DANS UN THREAD
    (via run_in_threadpool) pour ne jamais bloquer la boucle d'événements
    asyncio. Sinon tout le serveur (upload, polling de statut, health) fige
    le temps de l'indexation d'un gros fichier.

    Retourne (lang, n_pages).
    """
    # b. parse (lève ValueError si PDF scanné)
    pages = parse(file_path)

    # c. detect_lang sur texte complet (métadonnée doc.lang uniquement,
    # jamais pour router/filtrer la recherche : embeddings multilingues)
    full_text = "\n".join([p.text for p in pages])
    lang = detect_lang(full_text)

    # d. normalize unique chaque page (sans routage par langue)
    for p in pages:
        p.text = normalize(p.text)

    # e. chunk_pages (settings: chunk_size / chunk_overlap)
    from linguadocs.settings import settings as _settings

    chunks = chunk_pages(
        pages,
        chunk_size=_settings.chunk_size,
        overlap=_settings.chunk_overlap,
        doc_title=str(filename),
    )

    if not chunks:
        raise ValueError("Aucun chunk généré")

    from linguadocs.retrieval.retrieval import init, index as dense_index

    init(reset=False)

    # chunker génère déjà chunk_key = "title#idx", on veut "doc_id#idx" pour stabilité
    items = []
    for idx, ch in enumerate(chunks):
        items.append(
            {
                "text": ch["text"],
                "chunk_key": f"{doc_id}#{idx}",
                "doc_id": str(doc_id),
                "lang": lang,
                "page": ch.get("page"),
                "filename": filename,
            }
        )

    dense_index(str(user_id), items)

    return lang, len(pages)


async def index_document(
    doc_id: int | uuid.UUID,
    user_id: int | uuid.UUID,
    file_path: Path,
    session: AsyncSession | None = None,
):
    """
    Indexation complète d'un document.
    Peut être appelée avec ou sans session existante.
    Si session est None, on crée une session interne.
    Étapes: processing -> parse -> detect_lang -> normalize -> chunk -> embed -> Qdrant -> indexed/error
    """
    # si appelée en BackgroundTasks depuis FastAPI, session est None -> on ouvre AsyncSessionLocal
    # sinon on réutilise la session passée
    owns_session = session is None
    if owns_session:
        async with AsyncSessionLocal() as sess:
            return await _run_index(doc_id, user_id, file_path, sess)
    else:
        return await _run_index(doc_id, user_id, file_path, session)  # type: ignore


async def _run_index(
    doc_id: int | uuid.UUID,
    user_id: int | uuid.UUID,
    file_path: Path,
    session: AsyncSession,
):
    result = await session.exec(select(Document).where(Document.id == doc_id, Document.user_id == user_id))
    doc = result.first()
    if not doc:
        # fallback sans filtre user (si déjà supprimé)
        result = await session.exec(select(Document).where(Document.id == doc_id))
        doc = result.first()
        if not doc:
            return

    try:
        # DB only — rapide, reste sur la boucle d'événements
        doc.status = "processing"
        doc.error = None
        await session.commit()

        # b->g. parse + lang + normalize + chunk + embed + upsert Qdrant.
        # EXÉCUTÉ DANS UN THREAD (CPU/IO-bound) : ne bloque pas asyncio,
        # donc le serveur continue de répondre (polling statut, autres uploads).
        lang, n_pages = await run_in_threadpool(
            _process_document, file_path, doc_id, user_id, str(doc.filename)
        )

        doc.status = "indexed"
        doc.lang = lang
        doc.n_pages = n_pages
        doc.error = None
        await session.commit()

    except Exception as e:
        try:
            doc.status = "error"
            # message clair pour PDF scanné
            msg = str(e)
            if "PDF scanné" in msg:
                doc.error = "PDF scanné non supporté"
            else:
                doc.error = msg[:1024]
            await session.commit()
        except Exception:
            pass
        # ne pas relancer pour BackgroundTasks
