import uuid
import shutil
from pathlib import Path
import mimetypes

from fastapi import APIRouter, Depends, UploadFile, File, HTTPException, status, BackgroundTasks
from sqlmodel import select
from sqlmodel.ext.asyncio.session import AsyncSession

from linguadocs.api.auth import current_user
from linguadocs.api.database import AsyncSessionLocal
from linguadocs.api.models import Document, User
from linguadocs.api.database import get_session
from linguadocs.settings import settings

router = APIRouter(prefix="/documents", tags=["documents"])

# mime réels autorisés
ALLOWED = {
    "application/pdf": "pdf",
    "text/plain": "txt",
    "text/markdown": "md",
    # pdfplumber/python-magic peut retourner text/plain pour .md, on gère aussi par extension
    "application/vnd.openxmlformats-officedocument.wordprocessingml.document": "docx",
}
EXT_TO_MIME = {
    ".pdf": "application/pdf",
    ".txt": "text/plain",
    ".md": "text/markdown",
    ".docx": "application/vnd.openxmlformats-officedocument.wordprocessingml.document",
}
MAX_SIZE = settings.max_upload_mb * 1024 * 1024  # 50 MB


def _detect_mime(content: bytes, filename: str) -> str:
    # python-magic-bin
    try:
        import magic as magic_lib  # type: ignore
        mime = magic_lib.from_buffer(content, mime=True)
        # magic can return text/plain for md, normalize via extension
        ext = Path(filename).suffix.lower()
        if ext == ".md" and mime == "text/plain":
            return "text/markdown"
        # some systems return application/octet-stream for txt
        if mime == "application/octet-stream" and ext in EXT_TO_MIME:
            return EXT_TO_MIME[ext]
        return mime
    except Exception:
        # fallback by extension
        ext = Path(filename).suffix.lower()
        return EXT_TO_MIME.get(ext, "application/octet-stream")


def _chunk_text(text: str, chunk_size: int = 1000, overlap: int = 200) -> list[str]:
    chunks = []
    start = 0
    n = len(text)
    while start < n:
        end = min(start + chunk_size, n)
        chunk = text[start:end]
        if chunk.strip():
            chunks.append(chunk)
        if end == n:
            break
        start = end - overlap
    return chunks


async def _process_document(doc_id: uuid.UUID):
    """Background task: extract, detect lang, chunk, index in Qdrant."""
    async with AsyncSessionLocal() as session:
        result = await session.exec(select(Document).where(Document.id == doc_id))
        doc = result.first()
        if not doc:
            return
        # status -> processing
        doc.status = "processing"
        await session.commit()

        file_dir = Path(settings.data_dir) / str(doc.user_id) / str(doc.id)
        # find original file (only one)
        files = list(file_dir.glob("*")) if file_dir.exists() else []
        if not files:
            doc.status = "error"
            doc.error = "Fichier introuvable sur disque"
            await session.commit()
            return

        file_path = files[0]  # original saved file
        try:
            text = ""
            n_pages: int | None = None

            if doc.doc_type == "pdf":
                # try pdfplumber then pypdf
                import pdfplumber
                from pypdf import PdfReader

                # count pages via pypdf quickly
                try:
                    reader = PdfReader(str(file_path))
                    n_pages = len(reader.pages)
                except Exception:
                    n_pages = None

                # extract with pdfplumber (better for multilingual)
                try:
                    with pdfplumber.open(str(file_path)) as pdf:
                        if n_pages is None:
                            n_pages = len(pdf.pages)
                        texts = []
                        for page in pdf.pages:
                            t = page.extract_text() or ""
                            texts.append(t)
                        text = "\n".join(texts)
                except Exception as e:
                    # fallback pypdf
                    try:
                        reader = PdfReader(str(file_path))
                        text = "\n".join([p.extract_text() or "" for p in reader.pages])
                    except Exception:
                        raise RuntimeError(f"Impossible de lire le PDF: {e}")

                if not text.strip():
                    raise RuntimeError(
                        "PDF scanné ou vide — aucun texte extractible. "
                        "Veuillez fournir un PDF avec du texte sélectionnable ou OCRiser le document au préalable."
                    )

            elif doc.doc_type == "docx":
                import docx  # python-docx

                document = docx.Document(str(file_path))
                text = "\n".join([p.text for p in document.paragraphs])
                n_pages = None

            else:  # txt, md
                text = file_path.read_text(encoding="utf-8", errors="ignore")
                n_pages = 1

            if not text.strip():
                raise RuntimeError("Document vide — aucun texte à indexer")

            # language detection
            lang = None
            try:
                from lingua import Language, LanguageDetectorBuilder

                # keep AR/FR/EN/ES mandatory - build once?
                detector = LanguageDetectorBuilder.from_languages(
                    Language.ARABIC, Language.FRENCH, Language.ENGLISH, Language.SPANISH
                ).build()
                # detect on first 2k chars
                sample = text[:2000]
                conf_values = detector.compute_language_confidence_values(sample)
                if conf_values:
                    best = conf_values[0]
                    mapping = {
                        "ARABIC": "ar",
                        "FRENCH": "fr",
                        "ENGLISH": "en",
                        "SPANISH": "es",
                    }
                    lang = mapping.get(str(best.language).split(".")[-1], None)
                    # fallback to iso_code
                    if not lang:
                        try:
                            lang = best.language.iso_code_639_1().name.lower()  # type: ignore
                        except Exception:
                            pass
            except Exception:
                lang = None

            # chunk & index
            chunks = _chunk_text(text)
            if not chunks:
                raise RuntimeError("Impossible de découper le document en chunks")

            # prepare items for dense.index
            items = []
            for i, ch in enumerate(chunks):
                items.append(
                    {
                        "text": ch,
                        "chunk_key": f"{doc.id}#{i}",
                        "doc_id": str(doc.id),
                        "filename": doc.filename,
                        "lang": lang,
                        "page": None,  # could add per-chunk page if needed
                    }
                )

            # init collection if needed then upsert
            from linguadocs.retrieval.dense import init, index as dense_index

            # ensure collection exists (dense.init is idempotent)
            init(reset=False)
            dense_index(str(doc.user_id), items)

            doc.lang = lang
            doc.n_pages = n_pages
            doc.status = "indexed"
            doc.error = None
            await session.commit()

        except Exception as e:
            doc.status = "error"
            doc.error = str(e)[:1024]
            await session.commit()


@router.post("", status_code=status.HTTP_201_CREATED)
async def upload_document(
    background_tasks: BackgroundTasks,
    file: UploadFile = File(...),
    user: User = Depends(current_user),
    session: AsyncSession = Depends(get_session),
):
    if not file.filename:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Nom de fichier manquant")

    # read content (limit 50MB)
    content = await file.read()
    if len(content) > MAX_SIZE:
        raise HTTPException(
            status_code=status.HTTP_413_REQUEST_ENTITY_TOO_LARGE,
            detail=f"Fichier trop volumineux ({len(content) / 1024 / 1024:.1f} MB) — limite {settings.max_upload_mb} MB",
        )
    if len(content) == 0:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Fichier vide")

    # vérification extension d'abord (sécurité)
    ext = Path(file.filename).suffix.lower()
    ALLOWED_EXTS = {".pdf", ".txt", ".md", ".docx"}
    if ext not in ALLOWED_EXTS:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Extension non supportée: {ext} (autorisé: .pdf, .txt, .md, .docx)",
        )

    # detect real mime via python-magic
    mime = _detect_mime(content, file.filename)
    # si magic dit octet-stream mais extension est valide -> on fait confiance à l'extension
    if mime not in ALLOWED:
        if mime == "application/octet-stream" and ext in EXT_TO_MIME:
            mime = EXT_TO_MIME[ext]
        else:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail=f"Type MIME réel non supporté: {mime} (fichier: {ext})",
            )
    # cohérence extension vs mime (évite .exe renommé .txt avec contenu binaire)
    expected_mime = EXT_TO_MIME.get(ext)
    # autorise txt/md interchangeables (magic retourne text/plain pour .md)
    if mime != expected_mime and not (ext == ".md" and mime == "text/plain") and mime != "application/octet-stream":
        # si mismatch sévère (ex: .txt mais mime = application/pdf -> suspect)
        # on reste tolérant pour pdf/docx car magic est fiable, mais on log via mime réel
        pass

    doc_type = ALLOWED.get(mime)
    if not doc_type:
        # dernière chance via extension
        doc_type = ALLOWED.get(expected_mime or "")
    if doc_type not in ("pdf", "txt", "md", "docx"):
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=f"Type non supporté: {doc_type}")

    # create doc row
    doc = Document(
        user_id=user.id,
        filename=file.filename,
        mime=mime,
        doc_type=doc_type,
        status="queued",
    )
    session.add(doc)
    await session.commit()
    await session.refresh(doc)

    # save to data/users/<user_id>/<doc_id>/
    save_dir = Path(settings.data_dir) / str(user.id) / str(doc.id)
    save_dir.mkdir(parents=True, exist_ok=True)
    # sanitize filename
    safe_name = Path(file.filename).name
    save_path = save_dir / safe_name
    save_path.write_bytes(content)

    # background indexing
    background_tasks.add_task(_process_document, doc.id)

    return {
        "id": str(doc.id),
        "filename": doc.filename,
        "mime": doc.mime,
        "doc_type": doc.doc_type,
        "status": doc.status,
        "lang": doc.lang,
        "n_pages": doc.n_pages,
        "error": doc.error,
        "created_at": doc.created_at.isoformat(),
    }


@router.get("")
async def list_documents(
    user: User = Depends(current_user), session: AsyncSession = Depends(get_session)
):
    result = await session.exec(select(Document).where(Document.user_id == user.id).order_by(Document.created_at.desc()))  # type: ignore
    docs = result.all()
    return [
        {
            "id": str(d.id),
            "filename": d.filename,
            "mime": d.mime,
            "doc_type": d.doc_type,
            "status": d.status,
            "lang": d.lang,
            "n_pages": d.n_pages,
            "error": d.error,
            "created_at": d.created_at.isoformat(),
        }
        for d in docs
    ]


@router.get("/{doc_id}")
async def get_document(
    doc_id: uuid.UUID,
    user: User = Depends(current_user),
    session: AsyncSession = Depends(get_session),
):
    result = await session.exec(select(Document).where(Document.id == doc_id, Document.user_id == user.id))
    doc = result.first()
    if not doc:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Document introuvable")
    return {
        "id": str(doc.id),
        "filename": doc.filename,
        "mime": doc.mime,
        "doc_type": doc.doc_type,
        "status": doc.status,
        "lang": doc.lang,
        "n_pages": doc.n_pages,
        "error": doc.error,
        "created_at": doc.created_at.isoformat(),
    }


@router.delete("/{doc_id}")
async def delete_document(
    doc_id: uuid.UUID,
    user: User = Depends(current_user),
    session: AsyncSession = Depends(get_session),
):
    result = await session.exec(select(Document).where(Document.id == doc_id, Document.user_id == user.id))
    doc = result.first()
    if not doc:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Document introuvable")

    # delete vectors Qdrant
    try:
        from linguadocs.retrieval.dense import client, COL
        from qdrant_client import models

        flt = models.Filter(
            must=[
                models.FieldCondition(key="user_id", match=models.MatchValue(value=str(user.id))),
                models.FieldCondition(key="doc_id", match=models.MatchValue(value=str(doc.id))),
            ]
        )
        # delete requires points_selector
        client.delete(collection_name=COL, points_selector=flt, wait=True)
    except Exception:
        # do not fail deletion if Qdrant not reachable
        pass

    # delete file on disk
    save_dir = Path(settings.data_dir) / str(user.id) / str(doc.id)
    if save_dir.exists():
        shutil.rmtree(save_dir, ignore_errors=True)

    await session.delete(doc)
    await session.commit()

    return {"detail": "Document supprimé"}
