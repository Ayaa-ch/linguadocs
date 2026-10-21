# LinguaDocs — Local Multilingual RAG Assistant

![Login](docs/screenshots/01-login.png)
![Workspace](docs/screenshots/02-welcome.png)
![Arabic answer (RTL)](docs/screenshots/03-answer-ar-rtl.png)

---

## Interface

| | |
|---|---|
| ![](docs/screenshots/01-login.png) | **Sign in** — email + password, interface in EN / FR / ES / AR, light & dark themes. |
| ![](docs/screenshots/02-welcome.png) | **Workspace** — your documents on the left, the conversation on the right, document viewer (chunks + pages) in a side panel. |
| ![](docs/screenshots/03-answer-ar-rtl.png) | **Cited answer** — answered in the language of the question, clickable `[file, page]` sources, right-to-left layout for Arabic. |

---

## Project

**LinguaDocs** is a multilingual RAG assistant that runs **entirely on your machine** (CPU only, nothing leaves the box).

- Drop your documents (PDF, TXT, MD, DOCX — 50 MB max), ask a question, get an **cited** answer (file + page) in the language of your question.
- Isolation is strict: every user only ever sees their own documents, at every layer of the retrieval stack.
- Four languages end to end: **EN · FR · ES · AR** (with RTL support).

| | |
|---|---|
| Backend | FastAPI · SQLModel · PostgreSQL 16 (SQLite in tests) |
| Vectors | Qdrant — dense + BM25 sparse, RRF fusion, cross-encoder reranker |
| Embeddings | `BAAI/bge-m3` (1024 dims) |
| Reranker | `BAAI/bge-reranker-v2-m3`, top 3 chunks |
| LLM | Ollama `qwen2.5:3b-instruct` (local, SSE streaming) |
| UI | Plain HTML / CSS / JS, no Node, no React |

---

## How to clone

**Requirements**: Python ≥ 3.11, [uv](https://docs.astral.sh/uv/), Docker, [Ollama](https://ollama.com/).

```bash
git clone https://github.com/Ayaa-ch/linguadocs.git
cd linguadocs

uv sync                        # install dependencies (pyproject.toml + uv.lock)

docker compose up -d           # Qdrant (:6333) + PostgreSQL (:5432)
ollama pull qwen2.5:3b-instruct

uv run uvicorn linguadocs.main:app --port 8000
```

| | |
|---|---|
| UI | http://localhost:8000 |
| API (Swagger) | http://127.0.0.1:8000/docs |
| Health check | http://127.0.0.1:8000/health |

Settings (database, Qdrant, Ollama, refusal threshold…) live in `src/linguadocs/settings.py` and can be overridden by a `.env` file at the repository root.

---

## How to test

```bash
uv run pytest -q                 # 52 tests (in-memory SQLite, mocked LLM) — ~2 min
```

Measurement harnesses:

```bash
uv run python scripts/bench_latency.py     # breakdown: ingest → retrieval → rerank → LLM
uv run python scripts/bench_ttft.py         # time to first token per top_n
uv run python scripts/bench_num_predict.py  # throughput vs num_predict
```

---

## What it is / How it works

An uploaded document goes through:

```
PDF / TXT / MD / DOCX
   → parse (pdfplumber / python-docx)      src/linguadocs/ingest/parsers.py
   → Unicode + Arabic normalization         src/linguadocs/ingest/language.py
   → chunking, 200 words (+40 overlap)     src/linguadocs/ingest/chunker.py
   → dense embeddings + BM25 sparse → Qdrant
```

A question goes through:

```
Question
   → normalization                          src/linguadocs/ingest/language.py
   → hybrid retrieval (dense + BM25, RRF fusion), mandatory user_id filter
   → cross-encoder reranker → 3 chunks      src/linguadocs/retrieval/retrieval.py
   → refusal if the dense score is too low  src/linguadocs/api/routes_ask.py
   → prompt + local LLM (Ollama, SSE)       src/linguadocs/llm/
   → answer + clickable sources
```

The sharp edges, briefly:

- **Isolation** — the `user_id` from the JWT is added to **every** Qdrant query; without it, no search can run.
- **Reranker unavailable** — no silent fallback to score sorting: `/ask` answers **503** with an explicit message.
- **Refusal** — the `REFUSAL_THRESHOLD` applies to the dense score (k=3), not to the RRF score, which cannot tell out-of-domain queries apart.
- **Tools** — summary / quiz / flashcards / translation are wired to `mocks.py` until the LLM is connected.

---

## Coming soon

Four features are **mocked** (`mocks.py`): they simulate a delay so the interface loading states can be exercised. Every route answers `501` until the LLM is wired in.

- Document summary
- Quiz
- Flashcards
- Translation

---

## Evaluation

The evaluation harness (aligned with the real app pipeline: same chunking, same parameters, separate collections) is being finalized and is not published yet.
