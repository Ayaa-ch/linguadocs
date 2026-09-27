from __future__ import annotations

import json
from typing import AsyncGenerator

import httpx

OLLAMA_URL = "http://localhost:11434/api/generate"
TIMEOUT = 120.0


async def generate(prompt: str, model: str = "qwen3:4b") -> str:
    async with httpx.AsyncClient(timeout=TIMEOUT) as client:
        resp = await client.post(
            OLLAMA_URL,
            json={"model": model, "prompt": prompt, "stream": False, "think": False},
        )
        resp.raise_for_status()
        data = resp.json()
        return data.get("response", "")


async def generate_stream(prompt: str, model: str = "qwen3:4b") -> AsyncGenerator[str, None]:
    async with httpx.AsyncClient(timeout=TIMEOUT) as client:
        async with client.stream(
            "POST",
            OLLAMA_URL,
            json={"model": model, "prompt": prompt, "stream": True, "think": False},
        ) as resp:
            resp.raise_for_status()
            async for line in resp.aiter_lines():
                if not line:
                    continue
                try:
                    obj = json.loads(line)
                except json.JSONDecodeError:
                    continue
                token = obj.get("response", "")
                if token:
                    yield token
                if obj.get("done"):
                    break
