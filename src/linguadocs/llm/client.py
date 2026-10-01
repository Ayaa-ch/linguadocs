from __future__ import annotations

import json
import logging
import time
from typing import AsyncGenerator

import httpx

import re

from linguadocs.llm.prompts import build_messages
from linguadocs.settings import settings

logger = logging.getLogger("linguadocs.llm")

# /api/chat (rôles system/user) plutôt que /api/generate (blob brut) :
# le template de chat fait respecter les règles système à qwen3,
# qui sinon raisonne à voix haute dans sa réponse malgré think:false.
OLLAMA_URL = "http://localhost:11434/api/chat"
TIMEOUT = 120.0

_THINK_RE = re.compile(r"<think>.*?</think>", re.DOTALL | re.IGNORECASE)
_THINK_OPEN_RE = re.compile(r"<think.*?>", re.IGNORECASE)
_THINK_CLOSE_RE = re.compile(r"</think.*?>", re.IGNORECASE)


def strip_thinking(text: str) -> str:
    """Enlève le raisonnement Qwen3 qui fuit dans `content`.

    Couvre 2 cas Ollama :
    - nouveau : thinking dans champ séparé (filtré ailleurs), reste parfois des balises
    - ancien : thinking inline `<think>...</think>` dans content.
    Idempotent, safe si pas de balises.
    """
    if not text:
        return text
    # 1) paire complète <think>...</think>
    text = _THINK_RE.sub("", text)
    # 2) balise orpheline (stream coupé, tag non fermé) : coupe tout après <think>
    if _THINK_OPEN_RE.search(text):
        # s'il reste un open sans close, on enlève open + tout ce qui suit
        # sauf si le close existe encore (déjà géré) -> ici il n'existe plus
        parts = _THINK_OPEN_RE.split(text)
        # garde ce qui est avant le premier <think>, + recolle les morceaux après chaque </think>
        cleaned = parts[0]
        for part in parts[1:]:
            m = _THINK_CLOSE_RE.search(part)
            if m:
                cleaned += part[m.end():]
            # sinon : partie thinking -> jetée
        text = cleaned
    # 3) close orphelin restant
    text = _THINK_CLOSE_RE.sub("", text)
    # 4) préambule de raisonnement anglais typique Qwen3 sans balises
    # (ex: "Okay, let's tackle..." quand think:false ignoré) : on ne peut pas
    # le détecter de façon fiable, le prompt + think:false reste la 1re barrière.
    return text.strip()


def _payload(prompt: str, model: str, stream: bool) -> dict:
    # `prompt` reste le prompt complet historique (system + user concaténés) ;
    # on le re-découpe via build_messages si possible, sinon fallback
    # en message user unique (même comportement que /api/generate).
    messages = [{"role": "user", "content": prompt}]
    return {
        "model": model,
        "messages": messages,
        "stream": stream,
        "think": False,
        # -1 = garder le modèle chargé en RAM après la requête (pas de déchargement)
        "keep_alive": settings.ollama_keep_alive,
        # temperature 0 = réponse déterministe et concise (pas de divagation)
        "options": {"num_predict": settings.llm_num_predict, "temperature": 0},
    }


def _payload_messages(system: str, user: str, model: str, stream: bool) -> dict:
    p = _payload(user, model, stream)
    p["messages"] = [
        {"role": "system", "content": system},
        {"role": "user", "content": user},
    ]
    return p


async def _post_json(payload: dict) -> dict:
    async with httpx.AsyncClient(timeout=TIMEOUT) as client:
        resp = await client.post(OLLAMA_URL, json=payload)
        resp.raise_for_status()
        return resp.json()


async def generate(prompt: str, model: str | None = None) -> str:
    model = model or settings.llm_model
    data = await _post_json(_payload(prompt, model, stream=False))
    raw = (data.get("message") or {}).get("content", "") or data.get("response", "")
    return strip_thinking(raw)


async def generate_chat(system: str, user: str, model: str | None = None) -> str:
    """Chemin principal de /ask : rôles séparés system/user."""
    model = model or settings.llm_model
    data = await _post_json(_payload_messages(system, user, model, stream=False))
    raw = (data.get("message") or {}).get("content", "")
    return strip_thinking(raw)


async def _iter_stream(payload: dict) -> AsyncGenerator[str, None]:
    async with httpx.AsyncClient(timeout=TIMEOUT) as client:
        async with client.stream("POST", OLLAMA_URL, json=payload) as resp:
            resp.raise_for_status()
            in_think = False
            async for line in resp.aiter_lines():
                if not line:
                    continue
                try:
                    obj = json.loads(line)
                except json.JSONDecodeError:
                    continue
                # format /api/chat : {"message": {"content": ..., "thinking": ...}}
                # (fallback /api/generate : {"response": ...})
                msg = obj.get("message") or {}
                # 1) champ thinking séparé (nouvel Ollama + Qwen3) : jamais affiché
                # on l'ignore purement, on ne yield que content.
                token = msg.get("content", "") or obj.get("response", "")
                if not token:
                    # même sans content, un chunk peut ne contenir que du thinking
                    if obj.get("done"):
                        break
                    continue
                # 2) thinking inline <think>...</think> (vieux Ollama, think:false ignoré)
                # filtre stateful car le tag peut être découpé entre 2 chunks SSE.
                out = token
                # boucle pour gérer <think>...</think> dans le même token
                filtered = ""
                buf = out
                while buf:
                    if in_think:
                        idx = buf.lower().find("</think")
                        if idx == -1:
                            # tout le chunk est du thinking -> jeter
                            buf = ""
                            break
                        end = buf.find(">", idx)
                        if end == -1:
                            buf = ""
                            break
                        buf = buf[end + 1 :]
                        in_think = False
                    else:
                        idx = buf.lower().find("<think")
                        if idx == -1:
                            filtered += buf
                            buf = ""
                            break
                        filtered += buf[:idx]
                        end = buf.find(">", idx)
                        if end == -1:
                            # tag découpé entre chunks -> on entre en thinking, on jette le reste
                            in_think = True
                            buf = ""
                            break
                        buf = buf[end + 1 :]
                        in_think = True
                if filtered:
                    yield filtered
                if obj.get("done"):
                    break


async def generate_stream(prompt: str, model: str | None = None) -> AsyncGenerator[str, None]:
    model = model or settings.llm_model
    async for token in _iter_stream(_payload(prompt, model, stream=True)):
        yield token


async def generate_chat_stream(
    system: str, user: str, model: str | None = None
) -> AsyncGenerator[str, None]:
    """Chemin streaming principal de /ask : rôles séparés system/user."""
    model = model or settings.llm_model
    async for token in _iter_stream(_payload_messages(system, user, model, stream=True)):
        yield token


async def warmup_ollama() -> float | None:
    """Charge qwen3:4b en RAM au démarrage (requête minimale).

    Robuste : si Ollama est indisponible, log un avertissement
    et l'API reste disponible (le modèle chargera à la 1re question).
    Retourne la durée en secondes, ou None si échec.
    """
    logger.info("Ollama warm-up started (model=%s)", settings.llm_model)
    t0 = time.perf_counter()
    try:
        system, user = build_messages("ping", [], "en")
        warm_payload = _payload_messages(system, user, settings.llm_model, stream=False)
        warm_payload["options"] = {"num_predict": 5}  # réponse minimale
        async with httpx.AsyncClient(timeout=TIMEOUT) as client:
            resp = await client.post(OLLAMA_URL, json=warm_payload)
            resp.raise_for_status()
    except Exception as e:
        logger.warning("Ollama warm-up failed, API stays available: %s", e)
        return None
    dt = time.perf_counter() - t0
    logger.info("Ollama warm-up completed in %.1fs", dt)
    return dt
