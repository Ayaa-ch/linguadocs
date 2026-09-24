from fastapi import APIRouter, Depends
from pydantic import BaseModel

from linguadocs.api.auth import current_user
from linguadocs.api.models import User
from linguadocs.ingest.language import detect_lang, normalize
from linguadocs.retrieval.dense import search

router = APIRouter(prefix="/ask", tags=["ask"])

NOT_FOUND = "Je ne trouve pas de réponse dans vos documents."
SCORE_THRESHOLD = 0.30


class AskRequest(BaseModel):
    question: str
    stream: bool = False


@router.post("")
async def ask(payload: AskRequest, user: User = Depends(current_user)):
    question = payload.question.strip()
    if not question:
        return {"answer": NOT_FOUND, "sources": []}

    lang = detect_lang(question)
    norm_q = normalize(question, lang)

    # user_id vient du token JWT uniquement, filtre obligatoire dans dense.search
    hits = search(str(user.id), norm_q, k=5)

    if not hits:
        return {"answer": NOT_FOUND, "sources": []}

    best = max((getattr(h, "score", 0) or 0) for h in hits) if hits else 0
    if best < SCORE_THRESHOLD:
        return {"answer": NOT_FOUND, "sources": []}

    sources = []
    for h in hits:
        pl = getattr(h, "payload", {}) or {}
        score = getattr(h, "score", None)
        if score is not None and score < SCORE_THRESHOLD:
            continue
        sources.append(
            {
                "doc_id": pl.get("doc_id"),
                "filename": pl.get("filename"),
                "page": pl.get("page"),
                "text": pl.get("text"),
                "score": score,
            }
        )

    if not sources:
        return {"answer": NOT_FOUND, "sources": []}

    # Pour l'instant PAS de LLM, juste les sources
    return {"answer": f"{len(sources)} source(s) trouvée(s)", "sources": sources}
