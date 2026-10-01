"""Bench TTFT (time to first token) vs taille du prompt.

Test A : top_n = 5, chunks complets  (~12k caracteres)
Test B : top_n = 3, chunks complets  (~7k caracteres)
Test C : top_n = 3, chunks tronques  (~4k caracteres)

Mesure le temps jusqu'au premier token Ollama (streaming),
comme le fait desormais le dashboard.

Lancer : uv run python scripts/bench_ttft.py

N'utilise PAS init(reset=True) : les vecteurs existants sont preserves
(indexation sous un user dedie, sans reset de la collection).
"""

import json
import sys
import time
from pathlib import Path

import httpx

sys.path.insert(0, "src")

from linguadocs.ingest.chunker import chunk_pages
from linguadocs.ingest.parsers import parse
from linguadocs.llm.prompts import build_prompt
from linguadocs.retrieval.retrieval import index, init, search
from linguadocs.retrieval.retrieval import rerank
from linguadocs.settings import settings

PDF_PATH = Path("scripts/test_bench.pdf")
USER_ID = "ttft_bench"
QUESTION = "Quels sont les droits de l'enfant ?"
OLLAMA_URL = "http://localhost:11434"
MODEL = settings.llm_model
TRUNC_CHARS = 1200  # test C : max caracteres par chunk

results = {}


def ttft(prompt: str) -> float:
    """Temps (ms) jusqu'au premier token non vide. -1 si echec/timeout."""
    t0 = time.perf_counter()
    try:
        with httpx.stream(
            "POST",
            f"{OLLAMA_URL}/api/generate",
            json={"model": MODEL, "prompt": prompt, "stream": True, "think": False},
            timeout=600,
        ) as r:
            for line in r.iter_lines():
                if not line:
                    continue
                try:
                    obj = json.loads(line)
                except json.JSONDecodeError:
                    continue
                if obj.get("response"):
                    return (time.perf_counter() - t0) * 1000
                if obj.get("done"):
                    break
    except Exception as e:
        print(f"  !! erreur Ollama : {e}")
    return -1.0


print("\n" + "=" * 55)
print(f"  Bench TTFT vs taille prompt (modele : {MODEL})")
print("=" * 55)

# --- Donnees : reuse le PDF du bench latence ---
# Qdrant si dispo, sinon chunks directs du PDF (memes tailles de prompt)
pages = parse(PDF_PATH)
chunks = chunk_pages(pages, chunk_size=400, overlap=50, doc_title="ttft")

hits = None
try:
    init(reset=False)
    items = [
        {
            "chunk_key": f"ttft#{i}",
            "text": c["text"],
            "lang": "en",
            "page": c.get("page", 0),
        }
        for i, c in enumerate(chunks)
    ]
    index(USER_ID, items)
    print(f"  {len(items)} chunks indexes sous user '{USER_ID}' (sans reset)")
    hits = search(USER_ID, QUESTION, k=10)
    print("  retrieval Qdrant OK (top_n via rerank comme /ask)")
except Exception as e:
    print(f"  !! Qdrant indisponible ({e}) : fallback chunks directs du PDF")

# --- Warmup : charge le modele en memoire (non mesure) ---
print("\n  Warmup (chargement modele, non mesure)...")
with httpx.stream(
    "POST",
    f"{OLLAMA_URL}/api/generate",
    json={"model": MODEL, "prompt": "Dis bonjour.", "stream": True, "think": False},
    timeout=600,
) as r:
    for line in r.iter_lines():
        if not line:
            continue
        try:
            if json.loads(line).get("done"):
                break
        except json.JSONDecodeError:
            continue
print("  modele chaud.")

# --- Retrieval reel (comme /ask) ou fallback direct ---
if hits is not None:
    hits = search(USER_ID, QUESTION, k=10)


def to_chunks(hits_list):
    return [
        {
            "text": h.payload["text"],
            "filename": "test.pdf",
            "page": h.payload.get("page", 0),
            "score": h.score,
        }
        for h in hits_list
    ]


def direct_chunks(n):
    return [
        {"text": c["text"], "filename": "test.pdf", "page": c.get("page", 0), "score": 1.0}
        for c in chunks[:n]
    ]


def run_test(name, top_n, trunc=None):
    if hits is not None:
        ranked = rerank(QUESTION, hits, top_n=top_n)
        chs = to_chunks(ranked)
    else:
        chs = direct_chunks(top_n)
    if trunc:
        for c in chs:
            if len(c["text"]) > trunc:
                c["text"] = c["text"][:trunc] + " [...]"
    prompt = build_prompt(QUESTION, chs, "fr")
    ms = ttft(prompt)
    results[name] = {"prompt_chars": len(prompt), "top_n": top_n, "ttft_ms": round(ms, 1)}
    status = f"{ms:.0f} ms ({ms / 1000:.1f}s)" if ms > 0 else "ECHEC/TIMEOUT"
    print(f"  {name:<28} prompt={len(prompt):>6} chars  top_n={top_n}  TTFT={status}")
    return prompt


print("\n--- TESTS ---")
run_test("Test A (top_n=5, complet)", top_n=5)
run_test("Test B (top_n=3, complet)", top_n=3)
run_test("Test C (top_n=3, tronque)", top_n=3, trunc=TRUNC_CHARS)

print("\n" + "=" * 55)
print("  RESUME TTFT")
print("=" * 55)
for name, r in results.items():
    ms = r["ttft_ms"]
    bar = "#" * min(int(ms / 1000), 60) if ms > 0 else "ECHEC"
    print(f"  {name:<28} {r['prompt_chars']:>6} chars  {str(ms) + ' ms':>12} {bar}")

out = Path("docs/results/bench_ttft.json")
out.parent.mkdir(parents=True, exist_ok=True)
out.write_text(json.dumps(results, indent=2, ensure_ascii=False))
print(f"\n  Resultats sauvegardes : {out}")
