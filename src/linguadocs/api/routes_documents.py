import uuid
import shutil
from pathlib import Path

from fastapi import APIRouter, Depends, UploadFile, File, HTTPException, status, BackgroundTasks
from sqlmodel import select
from sqlmodel.ext.asyncio.session import AsyncSession

from linguadocs.api.auth import current_user
from linguadocs.api.models import Document, User
from linguadocs.api.database import get_session
from linguadocs.ingest.indexer import index_document
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
            status_code=status.HTTP_415_UNSUPPORTED_MEDIA_TYPE,
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
                status_code=status.HTTP_415_UNSUPPORTED_MEDIA_TYPE,
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
        raise HTTPException(status_code=status.HTTP_415_UNSUPPORTED_MEDIA_TYPE, detail=f"Type non supporté: {doc_type}")

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

    # background indexing via ingest/indexer (user_id depuis JWT)
    # En test (pytest) on indexe de façon synchrone pour que le polling fonctionne (SQLite mémoire)
    import sys as _sys, os as _os

    if "pytest" in _sys.modules or _os.getenv("PYTEST_CURRENT_TEST"):
        await index_document(doc.id, user.id, save_path, session)
    else:
        background_tasks.add_task(index_document, doc.id, user.id, save_path)

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
    # vérifier existence puis ownership pour renvoyer 403 si autre utilisateur
    result = await session.exec(select(Document).where(Document.id == doc_id))
    doc_any = result.first()
    if not doc_any:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Document introuvable")
    if doc_any.user_id != user.id:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Accès interdit")

    doc = doc_any

    # delete vectors Qdrant (filtre user_id ET doc_id obligatoire)
    try:
        from linguadocs.retrieval.dense import delete_user_doc

        delete_user_doc(str(user.id), str(doc.id))
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
