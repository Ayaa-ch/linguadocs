"""Bench generation vs num_predict (50 / 100 / 150 / 200), think=false.

Mesure pour chaque budget : TTFT, temps total, tokens evalues,
vitesse (tok/s via eval_duration d'Ollama).

Prompt fixe : top_n=3 chunks complets (~8k caracteres, comme /ask).
Pas de dependance Qdrant (chunks directs du PDF).

Lancer : uv run python scripts/bench_num_predict.py
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
from linguadocs.settings import settings

PDF_PATH = Path("scripts/test_bench.pdf")
QUESTION = "Quels sont les droits de l'enfant ?"
OLLAMA_URL = "http://localhost:11434"
MODEL = settings.llm_model
BUDGETS = [50, 100, 150, 200]

results = {}


def run_budget(prompt: str, num_predict: int) -> dict:
    """Un run streaming : TTFT + total + stats Ollama. -1 si echec."""
    t0 = time.perf_counter()
    ttft_ms = -1.0
    text = ""
    eval_count = None
    eval_ns = None
    try:
        with httpx.stream(
            "POST",
            f"{OLLAMA_URL}/api/generate",
            json={
                "model": MODEL,
                "prompt": prompt,
                "stream": True,
                "think": False,
                "options": {"num_predict": num_predict, "temperature": 0},
            },
            timeout=900,
        ) as r:
            for line in r.iter_lines():
                if not line:
                    continue
                try:
                    obj = json.loads(line)
                except json.JSONDecodeError:
                    continue
                if obj.get("response") and ttft_ms < 0:
                    ttft_ms = (time.perf_counter() - t0) * 1000
                    text += obj["response"]
                elif obj.get("response"):
                    text += obj["response"]
                if obj.get("done"):
                    eval_count = obj.get("eval_count")
                    eval_ns = obj.get("eval_duration")
                    break
    except Exception as e:
        print(f"  !! erreur Ollama (budget {num_predict}) : {e}")
        return {"ttft_ms": -1.0, "total_ms": -1.0, "eval_count": None, "tps": None}
    total_ms = (time.perf_counter() - t0) * 1000
    tps = round(eval_count / (eval_ns / 1e9), 1) if eval_count and eval_ns else None
    return {
        "ttft_ms": round(ttft_ms, 1),
        "total_ms": round(total_ms, 1),
        "eval_count": eval_count,
        "tps": tps,
        "answer_chars": len(text),
    }


print("\n" + "=" * 60)
print(f"  Bench num_predict (modele : {MODEL}, think=false)")
print("=" * 60)

pages = parse(PDF_PATH)
chunks = chunk_pages(pages, chunk_size=400, overlap=50, doc_title="numpred")
chs = [
    {"text": c["text"], "filename": "test.pdf", "page": c.get("page", 0), "score": 1.0}
    for c in chunks[:3]
]
prompt = build_prompt(QUESTION, chs, "fr")
print(f"  prompt fixe : {len(prompt)} caracteres (top_n=3, complet)")

print("\n  Warmup (non mesure)...")
run_budget("Dis bonjour en une phrase.", 10)
print("  modele chaud.\n")

print(f"  {'budget':<8} {'TTFT':>10} {'total':>10} {'tokens':>8} {'vitesse':>10}")
for n in BUDGETS:
    r = run_budget(prompt, n)
    results[str(n)] = {"prompt_chars": len(prompt), **r}
    ttft = f"{r['ttft_ms'] / 1000:.1f}s" if r["ttft_ms"] > 0 else "ECHEC"
    tot = f"{r['total_ms'] / 1000:.1f}s" if r["total_ms"] > 0 else "ECHEC"
    tok = str(r["eval_count"]) if r["eval_count"] is not None else "-"
    tps = f"{r['tps']} tok/s" if r["tps"] else "-"
    print(f"  {n:<8} {ttft:>10} {tot:>10} {tok:>8} {tps:>10}", flush=True)

out = Path("docs/results/bench_num_predict.json")
out.parent.mkdir(parents=True, exist_ok=True)
out.write_text(json.dumps(results, indent=2, ensure_ascii=False))
print(f"\n  Resultats sauvegardes : {out}")
