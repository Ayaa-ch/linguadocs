# LinguaDocs — Local Multilingual RAG Assistant

**LinguaDocs** is a local, multilingual Retrieval-Augmented Generation (RAG) assistant running 100 % on CPU. Users upload documents (PDF, TXT, MD, DOCX), ask questions in English, French, Spanish or Arabic, and receive answers with clickable citations (file, page) in the language of the question.

---

## Project at a glance

| Metric | Value |
|---|---|
| Interface languages | EN · FR · ES · AR (RTL) — `lingua` detector on 4 languages |
| Document formats | PDF · TXT · MD · DOCX (≤ 50 MB) |
| Backend | FastAPI + SQLModel + PostgreSQL (prod) / SQLite (tests) |
| Vector store | Qdrant `v1.15.1` — dense + BM25 sparse, RRF fusion |
| Embeddings | `BAAI/bge-m3` (1024 dims) |
| Reranker | `BAAI/bge-reranker-v2-m3`, top 3 |
| LLM | Ollama `qwen2.5:3b-instruct` (local, streaming SSE) |
| UI | Plain HTML/CSS/JS — no Node, no React |
| Test suite | **52 tests · 10 files · all passing** (~90 s on CPU) |
| User isolation | JWT `user_id` filter mandatory on every retrieval call |
| Mock features | Summary · Quiz · Flashcards · Translation (**Coming Soon**) |

---

## Features

### Core (implemented)
- **Upload & indexing** — status tracking `queued → processing → indexed`
- **Hybrid retrieval** — dense embeddings + BM25 sparse, RRF fusion, cross-encoder reranker
- **Cited answers** — responses include `[file, page]` sources; refusal when the information is absent (threshold `0.30`)
- **Strict user isolation** — each user only sees their own documents, enforced at every retrieval layer
- **Document viewer** — chunk listing and per-page text extraction
- **Conversation history** — persisted per `user_id` + `doc_id` (both required)
- **Authentication** — JWT signup/login, argon2 password hashing, account deletion
- **i18n** — EN / FR / ES / AR with right-to-left support for Arabic, light/dark theme

### Coming Soon (mocked)
- **Summary** · **Quiz** · **Flashcards** · **Translation**

These four features are **placeholders** in `mocks.py`. They return `"status": "coming_soon"` after a simulated `DELAY = 1.2 s` so the frontend loading states can be exercised. When a real route is ready, set the matching `use_mock_*` flag to `false`: the route then answers **501** until the LLM implementation lands.

---

## Test results

**52 tests in 10 files — all passing** (`uv run pytest -q`, ≈ 90 s).

| Test file | Tests | Scope |
|---|---|---|
| `test_auth.py` | 6 | Register, duplicate account, login, bad password, missing/invalid token |
| `test_documents.py` | 6 | Upload (valid / too large / unsupported), list isolation, delete, cross-user 403 |
| `test_ask.py` | 6 | Question → retrieval → LLM in FR/EN, out-of-domain refusal, citations, SSE streaming |
| `test_history.py` | 1 | History isolation between users |
| `test_hybrid.py` | 6 | Dense search, hybrid RRF, reranker ordering, multilingual FR/EN/AR, sparse, isolation |
| `test_isolation.py` | 3 | Alice vs Bob document isolation, missing `user_id` raises, `/ask` isolation |
| `test_docscope.py` | 2 | Document-scoped questions, 409 when the document is not indexed |
| `test_tools.py` | 5 | Page-range clamping, auth required, foreign document 404, unknown document 404, `501` when mock is off |
| `test_viewer.py` | 6 | Chunks (ok / 404 / cross-user forbidden), pages (PDF order, TXT, 404) |
| `test_eval.py` | 11 | Eval dataset = app chunking, gold mapping, dedicated `chunks_eval` collection, no `routed` mode |
| **Total** | **52** | |

> The test suite writes to its own Qdrant collection (`chunks_test`), never to the app's `chunks`.

```bash
uv run pytest -q
```

---

## Architecture

```
┌─────────────────────────────────────┐
│  UI — login + workspace (HTML/JS)   │
│  ui/index.html · ui/app.html        │
└──────────────┬──────────────────────┘
               │ JWT
               ▼
┌─────────────────────────────────────┐
│  FastAPI (auth, documents, ask,     │
│   history, tools)                   │
│  ├── SQLModel → PostgreSQL (prod)   │
│  └── SQLite in-memory (tests)       │
│  ├── Qdrant — dense + BM25,         │
│  │   user_id filter mandatory       │
│  ├── bge-m3 embeddings              │
│  ├── bge-reranker-v2-m3 (top 3)     │
│  └── Ollama — local LLM, SSE        │
└─────────────────────────────────────┘
```

---

## Configuration

Defaults live in `src/linguadocs/settings.py`; a `.env` file (git-ignored) overrides them.

| Variable | Default | Description |
|---|---|---|
| `DATABASE_URL` | `postgresql+asyncpg://linguadocs:secret@localhost:5432/linguadocs` | Database |
| `JWT_SECRET` | `change-me-super-secret-dev-key-please-override` | JWT secret |
| `JWT_ALGORITHM` / `JWT_EXPIRE_HOURS` | `HS256` / `24` | Token options |
| `QDRANT_URL` | `http://localhost:6333` | Vector store |
| `OLLAMA_URL` | `http://localhost:11434/api/generate` | LLM endpoint |
| `LLM_MODEL` | `qwen2.5:3b-instruct` | Local LLM model |
| `LLM_NUM_PREDICT` | `350` | Max generated tokens |
| `OLLAMA_KEEP_ALIVE` | `-1` | Keep the model resident in RAM |
| `EMBEDDING_MODEL` / `EMBEDDING_DIM` | `BAAI/bge-m3` / `1024` | Dense embeddings |
| `RERANKER_MODEL` / `RERANKER_TOP_N` | `BAAI/bge-reranker-v2-m3` / `3` | Cross-encoder reordering · number of chunks sent to the LLM |
| `REFUSAL_THRESHOLD` | `0.30` | Below this dense score the assistant refuses |
| `CHUNK_SIZE` / `CHUNK_OVERLAP` | `200` / `40` | Chunk length in **words** |
| `MAX_UPLOAD_MB` | `50` | Upload limit |
| `USE_MOCK_SUMMARY` / `_QUIZ` / `_FLASHCARDS` / `_TRANSLATE` | `true` | `false` → route answers `501` |

---

## Main endpoints

| Method | Endpoint | Description |
|---|---|---|
| `POST` | `/auth/register` | Signup (201 + JWT) |
| `POST` | `/auth/login` | Login (returns JWT) |
| `DELETE` | `/auth/me` | Delete the account |
| `POST` | `/documents` | Upload a document (201) |
| `GET` | `/documents` | List documents |
| `GET` | `/documents/{id}` | Document detail |
| `GET` | `/documents/{id}/chunks` | Indexed chunks (viewer) |
| `GET` | `/documents/{id}/pages` | Extracted page text (viewer) |
| `DELETE` | `/documents/{id}` | Delete a document |
| `POST` | `/ask` | RAG question — JSON or SSE streaming |
| `POST` | `/history` | Persist a message (`doc_id` required in the body) |
| `GET` | `/history?doc_id=…` | Conversation history for a document |
| `DELETE` | `/history?doc_id=…` | Clear a document's history |
| `POST` | `/summary` `/quiz` `/flashcards` `/translate` | Mocked tools (`coming_soon`, or `501`) |
| `GET` | `/health` | API health |

> **Reranker failure is explicit:** if `bge-reranker-v2-m3` cannot be loaded (it needs ≈ 4.3 GB of RAM together with `bge-m3`), `/ask` returns **503** with a `reranker indisponible …` message. There is no silent fallback to raw score ordering.

---

## Quick start

```bash
# 1. Install (uv resolves pyproject.toml + dev group)
uv sync

# 2. Infrastructure — Qdrant v1.15.1 + PostgreSQL 16
docker compose up -d

# 3. Local LLM
ollama pull qwen2.5:3b-instruct

# 4. Start the API
uv run uvicorn linguadocs.main:app --port 8000

# 5. UI           → http://localhost:8000
# 6. API docs     → http://127.0.0.1:8000/docs
# 7. Health check → http://127.0.0.1:8000/health

# 8. Tests
uv run pytest -q
```

On first index, `BAAI/bge-m3` and the reranker (`BAAI/bge-reranker-v2-m3`) are downloaded once from Hugging Face (~4.3 GB of weights together).

---

## Screenshots

![Login page](docs/screenshots/01-login.png)

![Workspace welcome screen with an indexed document](docs/screenshots/02-welcome.png)

![Arabic answer, right-to-left, with grounded sources](docs/screenshots/03-answer-ar-rtl.png)

---

## Evaluation

**Un seul script : `eval/run_hybrid.py`.** Il reproduit le parcours exact de
`api/routes_ask.py` (`normalize` → `search_hybrid(k=10)` → refus dense k=3 → `rerank(top_n=3)`),
mesure le sweep retrieval (dense / sparse / hybrid), le pipeline complet et le refus
hors-domaine, et écrit `docs/results/E4_hybrid.csv` + `docs/results/E4_hybrid.md`.

```bash
# 1. Construire les jeux de données (une fois, ou après modification du corpus)
uv run python eval/prepare_un.py
#    → un_corpus.jsonl               (317 chunks, découpage de l'app)
#    → un_pairs.jsonl                (4 866 requêtes cross-lingues + gold par chunk)
#    → un_pairs_hors_domaine.jsonl   (20 requêtes hors-domaine)

# 2. L'évaluation (commande exacte du rapport)
uv run python eval/run_hybrid.py --modes dense,sparse,hybrid --pipeline-modes hybrid --limit 200 --rerank reel
```

Options utiles :

| Option | Effet |
|---|---|
| `--limit 200` | échantillon **stratifié** (seed 42, 16 par paire de langues). `--limit 0` = les 4 866 requêtes (~7 h) |
| `--rerank reel` | vrai `bge-reranker-v2-m3` (production). `--rerank none` = retrieval seul (rapide), `--rerank simule` = tri par score |
| `--pipeline-modes hybrid` | modes qui passent par le **reranker réel**. Par défaut `hybrid` seul (= config de l'app) : le cross-encoder est le goulot d'étranglement (~6,7 s pour 10 chunks de 200 mots), les autres modes sont mesurés au sweep `recall@k` seul |
| `--top-ns 3,5` | compare les `top_n` dans le pipeline (un seul rerank des 10 candidats, coupé à 3 puis à 5) |
| `--ks 1,3,5,10` | k évalués dans le sweep brut |

> **À savoir avant de lancer**
>
> - **Le découpage est celui de l'app.** `prepare_un.py` regroupe les phrases ONU de chaque
>   langue **dans leur ordre d'origine** puis appelle la fonction de chunking de l'app
>   (`ingest.chunker.chunk_pages`) avec `settings.chunk_size` (200 mots) et
>   `settings.chunk_overlap` (40). Le gold d'une requête = le(s) chunk(s) qui contiennent la
>   phrase gold (2 chunks quand la phrase est à cheval sur le chevauchement).
> - **La collection Qdrant est dédiée** : `chunks_eval`. L'app indexe les documents des
>   utilisateurs dans `chunks` ; partager la collection ferait disparaître leur index.
> - **Le reranker est optionnel.** `bge-reranker-v2-m3` demande ~2,2 Go en plus de `bge-m3`
>   (~4,3 Go au total). S'il ne tient pas en RAM l'éval **ne s'arrête pas** : il bascule en
>   `unavailable`, garde le sweep et la colonne « avant rerank », et laisse « après rerank »
>   vide. `--strict-rerank` restaure l'arrêt immédiat.
> - **Le corpus et les requêtes sont normalisés** comme dans l'app (`normalize()`), sinon
>   l'éval ne mesurerait pas la production (384 des 412 phrases arabes sont réécrites).
> - **Durée** : ~2 min d'indexation (317 chunks, collection réutilisée ensuite) + ~3 min de
>   sweep (3 modes) + ~6,9 s par rerank réel → **~25 min** pour 200 requêtes avec le rerank
>   réel sur `hybrid` seul. Passer `--pipeline-modes dense,sparse,hybrid` triple ce temps
>   (~70 min) pour un pipeline complet sur chaque mode.

### Résultats (mesurés, 96 requêtes cross-lingues, corpus ONU chunké comme l'app)

**Sweep retrieval** — recall@k, avant rerank :

| mode | @1 | @3 | @5 | @10 |
|---|---:|---:|---:|---:|
| dense | 0.156 | 0.417 | 0.562 | **0.729** |
| sparse (BM25) | 0.000 | 0.021 | 0.042 | 0.094 |
| hybrid (RRF) — *mode de l'app* | 0.000 | 0.271 | 0.385 | **0.573** |

**Pipeline de l'app** (mode hybrid, reranker réel, 10 candidats) :

| top_n | plafond (pre10) | avant rerank | après rerank | Δ | latence rerank |
|---:|---:|---:|---:|---:|---:|
| 3 | 0.573 | 0.271 | **0.417** | **+0.146** | 18 795 ms |
| 5 | 0.573 | 0.385 | **0.521** | +0.136 | 18 795 ms |

**Ce que l'éval révèle sur l'app :**

1. **Le reranker apporte +0.146 de recall@3** (0.271 → 0.417) : il remonte le bon chunk
   parmi les 10 candidats dans 1 cas sur 7 environ. C'est le meilleur gain de la chaîne.
2. **BM25 dégrade le cross-lingue** : dense 0.729 contre hybrid 0.573 au recall@10. Le RRF
   fusionne des résultats BM25 qui ne traversent pas les langues et fait redescendre le
   bon chunk dense. Or l'app fait **toujours** du hybrid (`routes_ask.py:93`).
3. **Le reranker coûte 18,8 s par requête** sur des chunks de 200 mots (CPU, 8 threads) —
   soit la quasi-totalité du temps de `/ask` avant le LLM.
4. **Le seuil de refus `0.30` ne tient plus** : 0/20 requêtes hors-domaine sont refusées.
   Les scores se séparent pourtant bien (hors-domaine max **0.456**, in-domain min **0.470**,
   in-domain moyen 0.618) : un seuil vers **0.46** rejetterait tout le hors-domaine sans
   faux refus. À recalibrer sur les documents réels de l'utilisateur avant de changer
   `REFUSAL_THRESHOLD`.

### top_n : 3 ou 5 ?

La comparaison repose sur **deux outils** :

| Question | Outil | Sortie |
|---|---|---|
| **Qualité** — le bon chunk est-il parmi les N envoyés au LLM ? | `eval/run_hybrid.py` | `docs/results/E4_hybrid.md` § 2-3 (`pre10`, avant/après rerank, Δ) |
| **Latence** — quel est le coût pour l'utilisateur ? | `scripts/bench_ttft.py` | `docs/results/bench_ttft.json` (TTFT selon `top_n`) |

Le reranker note **les 10 candidats dans les deux cas** : sa latence ne change donc pas entre
`top_n=3` et `top_n=5`, seule la troncature change. La différence visible par l'utilisateur
vient de la taille du prompt envoyée au LLM — c'est le job de `bench_ttft.py`.

### Limites de l'évaluation

- Le corpus ONU aligné est une **concaténation de plusieurs documents ONU** sans séparateur :
  des chunks peuvent franchir une frontière de document. L'app ne le fait jamais (chaque
  upload = 1 document).
- Corpus en **texte brut** : ni PDF paginés, ni Markdown, ni DOCX, ni tableaux.
- La requête est une **phrase du corpus** (bitext), pas une question libre reformulée.
- Aucun **bout-en-bout LLM** : ni faithfulness, ni exactitude des citations, ni calibration
  fine du seuil de refus sur les documents réels de l'utilisateur.

### Benchmarks

`scripts/` holds the one-off measurement utilities used during development:

| Script | Purpose |
|---|---|
| `bench_latency.py` | End-to-end latency breakdown (ingest → retrieval → rerank → LLM) |
| `bench_ttft.py` | Time to first token (et latence LLM selon `top_n`) |
| `bench_num_predict.py` | Throughput vs `num_predict` |
| `check_qdrant.py` | Inspection helper |
| `reindex_documents.py` | Re-index the app's documents in Qdrant (after a collection wipe or a model change) |

---

## Project structure

```
README.md            mocks.py            pyproject.toml
docker-compose.yml   uv.lock             .gitignore  .python-version

src/linguadocs/
  main.py            FastAPI app, static UI mount, /health
  settings.py        All configuration defaults
  api/               auth, database, models, routes_{auth,documents,ask,history,tools}
  ingest/            parsers, chunker, indexer, language detection
  llm/               Ollama client + prompts
  retrieval/         dense + sparse search, RRF fusion, reranker

tests/               10 files · 52 tests (SQLite in-memory, mocked LLM)
ui/                  index.html (login), app.html (workspace), style.css, js/, assets/
eval/                prepare_un.py · run_hybrid.py  + datasets/
scripts/             benchmark + inspection utilities
docs/                decisions.md · results/
data/                uploaded documents — git-ignored
.env                 local overrides — git-ignored
```

---


