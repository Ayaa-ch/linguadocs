from __future__ import annotations

from pathlib import Path
import uuid

from sqlmodel import select
from sqlmodel.ext.asyncio.session import AsyncSession

from linguadocs.api.database import AsyncSessionLocal
from linguadocs.api.models import Document
from linguadocs.ingest.parsers import parse
from linguadocs.ingest.language import detect_lang, normalize
from linguadocs.ingest.chunker import chunk_pages


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
    # récupérer document et vérifier ownership
    result = await session.exec(select(Document).where(Document.id == doc_id, Document.user_id == user_id))
    doc = result.first()
    if not doc:
        # fallback sans filtre user (si déjà supprimé)
        result = await session.exec(select(Document).where(Document.id == doc_id))
        doc = result.first()
        if not doc:
            return

    try:
        doc.status = "processing"
        doc.error = None
        await session.commit()

        # b. parse
        pages = parse(file_path)  # lève ValueError si PDF scanné

        # c. detect_lang sur texte complet
        full_text = "\n".join([p.text for p in pages])
        lang = detect_lang(full_text)

        # d. normalize chaque page
        for p in pages:
            p.text = normalize(p.text, lang)

        # e. chunk_pages
        chunks = chunk_pages(pages, chunk_size=400, overlap=50, doc_title=str(doc.filename))

        if not chunks:
            raise ValueError("Aucun chunk généré")

        # f. embedding + g. upsert Qdrant
        # on prépare payloads: {user_id, doc_id, chunk_key, lang, page, text}
        from linguadocs.retrieval.dense import init, index as dense_index

        init(reset=False)

        # chunker génère déjà chunk_key = "title#idx", on veut "doc_id#idx" pour stabilité
        items = []
        for idx, ch in enumerate(chunks):
            items.append(
                {
                    "text": ch["text"],
                    "chunk_key": f"{doc.id}#{idx}",
                    "doc_id": str(doc.id),
                    "lang": lang,
                    "page": ch.get("page"),
                    "filename": doc.filename,
                }
            )

        # e5-small attend préfixe "passage: " déjà géré dans dense.index
        dense_index(str(user_id), items)

        # h. indexed
        doc.status = "indexed"
        doc.lang = lang
        doc.n_pages = len(pages)
        doc.error = None
        await session.commit()

    except Exception as e:
        # i. error
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
