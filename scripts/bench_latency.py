"""Benchmark latence du pipeline RAG LinguaDocs.

Mesure chaque etape : parsing PDF, chunking, langue, embedding,
indexation Qdrant, recherche dense/hybrid, prompt, LLM (TTFT + total)
et pipeline end-to-end.

Lancer : uv run python scripts/bench_latency.py

ATTENTION : init(reset=True) recree la collection Qdrant 'chunks',
les vecteurs existants sont supprimes.
"""

import json
import sys
import time
from pathlib import Path

import httpx

sys.path.insert(0, "src")

from linguadocs.ingest.chunker import chunk_pages
from linguadocs.ingest.language import detect_lang, normalize
from linguadocs.ingest.parsers import parse
from linguadocs.llm.prompts import build_prompt
from linguadocs.retrieval.retrieval import index, init, search, search_hybrid
from linguadocs.retrieval.retrieval import rerank
from linguadocs.settings import settings
from sentence_transformers import SentenceTransformer

# Config
PDF_PATH = Path("scripts/test_bench.pdf")
USER_ID = "bench_user"
QUESTION_FR = "Quels sont les droits de l'enfant ?"
QUESTION_EN = "What are the rights of the child?"
QUESTION_AR = "ما هي حقوق الطفل؟"
OLLAMA_URL = "http://localhost:11434"
MODEL = settings.llm_model
TOP_N = settings.reranker_top_n  # aligne sur /ask (top_n=3)

results = {}


def measure(name, fn):
    t0 = time.perf_counter()
    result = fn()
    dt = (time.perf_counter() - t0) * 1000
    results[name] = round(dt, 1)
    print(f"  OK {name:<35} {dt:>8.1f} ms")
    return result


print("\n" + "=" * 55)
print("  LinguaDocs - Benchmark latence pipeline")
print("=" * 55)

# Creer PDF test si inexistant (FR + EN ; pas d'arabe : police
# Helvetica de fpdf2 limitée à latin-1)
if not PDF_PATH.exists():
    from fpdf import FPDF

    pdf = FPDF()
    for i in range(5):
        pdf.add_page()
        pdf.set_font("Helvetica", size=12)
        en = (
            f"Page {i + 1}. The Security Council adopted a resolution on "
            "the protection of children rights in armed conflict. "
        ) * 20
        fr = (
            "Le Conseil de sécurité a adopté une résolution sur la "
            "protection des droits de l'enfant dans les conflits armés. "
            "Les États membres doivent garantir l'accès à l'éducation. "
        ) * 10
        pdf.multi_cell(0, 10, en + "\n\n" + fr)
    pdf.output(str(PDF_PATH))
    print(f"  PDF test créé : {PDF_PATH}")

print("\n--- INGESTION ---")

# 1. PDF Parsing
pages = measure("1. PDF parsing (pdfplumber)", lambda: parse(PDF_PATH))
print(f"     -> {len(pages)} pages extraites")

# 2. Chunking
chunks = measure(
    "2. Chunking (400 tokens, overlap 50)",
    lambda: chunk_pages(pages, chunk_size=400, overlap=50, doc_title="test"),
)
print(f"     -> {len(chunks)} chunks créés")

# 3. Détection de langue
lang = measure("3. Detection de langue (lingua)", lambda: detect_lang(pages[0].text[:500]))
print(f"     -> langue détectée : {lang}")

# 4. Normalisation
measure("4. Normalisation texte", lambda: normalize(pages[0].text[:500], lang))

# 5. Embedding (modèle chargé une fois)
print("\n--- EMBEDDINGS ---")
model = SentenceTransformer("intfloat/multilingual-e5-small")

embed_texts = [f"passage: {c['text']}" for c in chunks]


def embed_all():
    return model.encode(embed_texts, normalize_embeddings=True, batch_size=16)


vecs = measure("5. Embedding dense (e5-small, tous chunks)", embed_all)
print(f"     -> {len(vecs)} vecteurs, dim={vecs.shape[1]}")

per_chunk = results["5. Embedding dense (e5-small, tous chunks)"] / len(chunks)
print(f"     -> {per_chunk:.1f} ms par chunk")

# 6. Indexation Qdrant
print("\n--- QDRANT ---")
init(reset=True)

items = [
    {
        "chunk_key": f"bench#{i}",
        "text": c["text"],
        "lang": lang,
        "page": c.get("page", 0),
    }
    for i, c in enumerate(chunks)
]

measure("6. Indexation Qdrant (tous chunks)", lambda: index(USER_ID, items))
print(f"     -> {len(items)} chunks indexés")

# 7. Vector search dense
print("\n--- RETRIEVAL ---")

results_dense = measure("7. Vector search dense (k=5)", lambda: search(USER_ID, QUESTION_FR, k=5))
print(f"     -> {len(results_dense)} résultats")

# 8. Vector search hybrid
try:
    results_hybrid = measure(
        "8. Vector search hybrid RRF (k=5)", lambda: search_hybrid(USER_ID, QUESTION_FR, k=5)
    )
    print(f"     -> {len(results_hybrid)} résultats")
except Exception as e:
    print(f"  !! Hybrid non disponible : {e}")
    results["8. Vector search hybrid RRF (k=5)"] = -1

# 8b. Rerank (comme /ask : top_n=settings)
try:
    results_reranked = measure(
        f"8b. Rerank cross-encoder (top_n={TOP_N})",
        lambda: rerank(QUESTION_FR, results_dense, top_n=TOP_N),
    )
    print(f"     -> {len(results_reranked)} chunks gardés pour le prompt")
except Exception as e:
    print(f"  !! Rerank impossible : {e}")
    results[f"8b. Rerank cross-encoder (top_n={TOP_N})"] = -1
    results_reranked = list(results_dense)[:TOP_N]

# 9. Prompt construction
print("\n--- LLM ---")

chunks_for_prompt = [
    {
        "text": r.payload["text"],
        "filename": "test.pdf",
        "page": r.payload.get("page", 0),
        "score": r.score,
    }
    for r in results_reranked
]

prompt = measure("9. Construction du prompt", lambda: build_prompt(QUESTION_FR, chunks_for_prompt, "fr"))
print(f"     -> prompt de {len(prompt)} caractères")


# 10. LLM Time to First Token
def llm_first_token():
    with httpx.stream(
        "POST",
        f"{OLLAMA_URL}/api/generate",
        json={"model": MODEL, "prompt": prompt, "stream": True, "options": {"num_predict": 50}},
        timeout=180,
    ) as r:
        for chunk in r.iter_lines():
            if chunk:
                return chunk  # premier token reçu


try:
    measure("10. LLM time to first token (qwen3:4b)", llm_first_token)
except Exception as e:
    print(f"  !! TTFT impossible (>180s) : {e}")
    results["10. LLM time to first token (qwen3:4b)"] = -1


# 11. LLM génération complète (50 tokens)
def llm_full():
    resp = httpx.post(
        f"{OLLAMA_URL}/api/generate",
        json={
            "model": MODEL,
            "prompt": prompt,
            "stream": False,
            "options": {"num_predict": 50, "temperature": 0},
        },
        timeout=180,
    ).json()
    return resp.get("response", "")


try:
    full = measure("11. LLM generation complete (50 tokens)", llm_full)
    print(f"     -> réponse : {full[:80]}...")
except Exception as e:
    print(f"  !! Generation complete impossible : {e}")
    results["11. LLM generation complete (50 tokens)"] = -1


# 12. Pipeline end-to-end simulé
print("\n--- PIPELINE COMPLET ---")


def pipeline_complet():
    q = QUESTION_FR
    lang_q = detect_lang(q)
    n = normalize(q, lang_q)
    hits = search(USER_ID, n, k=10)
    ranked = rerank(n, hits, top_n=TOP_N)
    chunks_p = [
        {
            "text": h.payload["text"],
            "filename": "test.pdf",
            "page": h.payload.get("page", 0),
            "score": h.score,
        }
        for h in ranked
    ]
    p = build_prompt(n, chunks_p, lang_q)
    resp = httpx.post(
        f"{OLLAMA_URL}/api/generate",
        json={"model": MODEL, "prompt": p, "stream": False, "options": {"num_predict": 100}},
        timeout=180,
    ).json()
    return resp.get("response", "")


try:
    measure("12. Pipeline end-to-end (detect->search->rerank->generate)", pipeline_complet)
except Exception as e:
    print(f"  !! Pipeline end-to-end impossible : {e}")
    results["12. Pipeline end-to-end (detect->search->rerank->generate)"] = -1

# Résumé final
print("\n" + "=" * 55)
print("  RESUME")
print("=" * 55)
fast = [(k, v) for k, v in results.items() if v > 0]
fast.sort(key=lambda x: x[1])

for name, ms in fast:
    bar = "#" * min(int(ms / 100), 40)
    print(f"  {name[:35]:<35} {ms:>8.1f}ms {bar}")

print("\n  Goulots d'etranglement :")
slow = [(k, v) for k, v in results.items() if v > 1000 and v > 0]
slow.sort(key=lambda x: -x[1])
for name, ms in slow:
    print(f"  !! {name}: {ms:.0f}ms ({ms / 1000:.1f}s)")

# Sauvegarder
out = Path("docs/results/bench_latency.json")
out.parent.mkdir(parents=True, exist_ok=True)
out.write_text(json.dumps(results, indent=2, ensure_ascii=False))
print(f"\n  Résultats sauvegardés : {out}")
