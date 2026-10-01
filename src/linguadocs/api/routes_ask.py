import time
import json
from typing import Literal

from fastapi import APIRouter, Depends
from fastapi.responses import StreamingResponse
from pydantic import BaseModel

from linguadocs.api.auth import current_user
from linguadocs.api.models import User
from linguadocs.ingest.language import detect_lang, normalize
from linguadocs.llm.client import generate_chat as _generate_chat
from linguadocs.llm.client import generate_chat_stream as _generate_chat_stream
from linguadocs.llm.client import strip_thinking
from linguadocs.llm.prompts import build_messages
from linguadocs.retrieval.retrieval import rerank, search, search_hybrid
from linguadocs.retrieval.retrieval import search_sparse as search_sparse_fn
from linguadocs.settings import settings

router = APIRouter(prefix="/ask", tags=["ask"])

NOT_FOUND = "Je ne trouve pas de réponse dans vos documents."

# Alias public (utilisé par le code ci-dessous) :
# - generate / generate_stream = noms patchés par les tests existants
# - generate_chat / generate_chat_stream = noms réels
generate = _generate_chat
generate_chat = _generate_chat
generate_stream = _generate_chat_stream
generate_chat_stream = _generate_chat_stream


class AskRequest(BaseModel):
    question: str
    stream: bool = False
    search_mode: Literal["dense", "sparse", "hybrid"] = "hybrid"


@router.post("")
async def ask(payload: AskRequest, user: User = Depends(current_user)):
    t0 = time.perf_counter()
    question_raw = payload.question.strip()
    if not question_raw:
        return {
            "answer": NOT_FOUND,
            "sources": [],
            "question_lang": "fr",
            "refused": True,
            "latency_ms": {"retrieve": 0, "rerank": 0, "generate": 0, "total": 0},
        }

    # a. detect_lang
    question_lang = detect_lang(question_raw)
    # b. normalize
    norm_q = normalize(question_raw, question_lang)

    # c. search avec filtre user_id obligatoire (JWT uniquement, jamais au LLM)
    # selon search_mode
    t_retrieve_start = time.perf_counter()
    mode = payload.search_mode or settings.search_mode
    if mode == "dense":
        hits = search(str(user.id), norm_q, k=10)
    elif mode == "sparse":
        hits = search_sparse_fn(str(user.id), norm_q, k=10)
    else:  # hybrid
        hits = search_hybrid(str(user.id), norm_q, k=10)
    t_retrieve = int((time.perf_counter() - t_retrieve_start) * 1000)

    if not hits:
        total = int((time.perf_counter() - t0) * 1000)
        return {
            "answer": NOT_FOUND,
            "sources": [],
            "question_lang": question_lang,
            "refused": True,
            "latency_ms": {"retrieve": t_retrieve, "rerank": 0, "generate": 0, "total": total},
        }

    # d. refus si score < seuil (réglable settings.refusal_threshold)
    # Échelles incompatibles : dense=cosinus ~0-1, RRF natif Qdrant ~0.016-0.033.
    # Le chunking reste générique 400 mots (aucune règle par titre de doc).
    # Pour hybrid/sparse on juge le refus sur le score dense (cosinus),
    # pas sur le score RRF qui ne discrimine pas le hors-domaine.
    if mode == "dense":
        best = max((getattr(h, "score", 0) or 0) for h in hits) if hits else 0
    elif mode == "hybrid":
        try:
            _dense_check = search(str(user.id), norm_q, k=3)
            best = max((getattr(h, "score", 0) or 0) for h in _dense_check) if _dense_check else 0
        except Exception:
            best = 1.0  # si le check échoue, ne pas bloquer hybrid
    else:  # sparse : pas de seuil pré-rerank fiable
        best = 1.0
    if best < settings.refusal_threshold:
        total = int((time.perf_counter() - t0) * 1000)
        return {
            "answer": NOT_FOUND,
            "sources": [],
            "question_lang": question_lang,
            "refused": True,
            "latency_ms": {"retrieve": t_retrieve, "rerank": 0, "generate": 0, "total": total},
        }

    # rerank sur les résultats (ne reçoit jamais user_id)
    t_rerank_start = time.perf_counter()
    reranked = rerank(norm_q, hits, top_n=settings.reranker_top_n)
    t_rerank = int((time.perf_counter() - t_rerank_start) * 1000)

    # construire sources : on garde tous les reranked (le seuil a déjà été vérifié avant rerank)
    # on ne refiltre pas sur le score du reranker (échelle différente)
    sources = []
    chunks_for_prompt = []
    for h in reranked:
        pl = getattr(h, "payload", {}) or {}
        score = getattr(h, "score", None)
        src = {
            "doc_id": pl.get("doc_id"),
            "filename": pl.get("filename"),
            "page": pl.get("page"),
            "text": pl.get("text"),
            "score": score,
        }
        sources.append(src)
        chunks_for_prompt.append(src)

    if not sources:
        total = int((time.perf_counter() - t0) * 1000)
        return {
            "answer": NOT_FOUND,
            "sources": [],
            "question_lang": question_lang,
            "refused": True,
            "latency_ms": {"retrieve": t_retrieve, "rerank": t_rerank, "generate": 0, "total": total},
        }

    # e. build messages (rôles system/user séparés pour /api/chat ;
    #    LLM ne reçoit jamais user_id)
    system, user = build_messages(question_raw, chunks_for_prompt, question_lang)

    # f. generate / stream
    if payload.stream:
        async def event_gen():
            # en-tête SSE avec sources d'abord + temps déjà mesurés
            # (le front affichait retrieve 0ms / generate 0ms car il les fabriquait)
            yield f"data: {json.dumps({'sources': sources, 'question_lang': question_lang, 'refused': False, 'latency_ms': {'retrieve': t_retrieve, 'rerank': t_rerank, 'generate': 0, 'total': 0}}, ensure_ascii=False)}\n\n"
            t_gen_start = time.perf_counter()
            async for token in generate_stream(system, user):
                yield f"data: {json.dumps({'token': token}, ensure_ascii=False)}\n\n"
            t_gen = int((time.perf_counter() - t_gen_start) * 1000)
            total = int((time.perf_counter() - t0) * 1000)
            yield f"data: {json.dumps({'latency_ms': {'retrieve': t_retrieve, 'rerank': t_rerank, 'generate': t_gen, 'total': total}}, ensure_ascii=False)}\n\n"
            # on pourrait envoyer latency à la fin
            yield "data: [DONE]\n\n"

        return StreamingResponse(event_gen(), media_type="text/event-stream")

    # non-stream
    t_gen_start = time.perf_counter()
    answer = await generate(system, user)
    answer = strip_thinking(answer)
    t_gen = int((time.perf_counter() - t_gen_start) * 1000)
    total = int((time.perf_counter() - t0) * 1000)
    return {
        "answer": answer,
        "sources": sources,
        "question_lang": question_lang,
        "refused": False,
        "latency_ms": {"retrieve": t_retrieve, "rerank": t_rerank, "generate": t_gen, "total": total},
    }
