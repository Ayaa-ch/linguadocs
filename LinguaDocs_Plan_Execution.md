# LinguaDocs — assistant multilingue de textes officiels
## Plan d'exécution complet (étudiant seul, 100 % gratuit, CPU)

> **Idée :** l'utilisateur téléverse ses documents (PDF, TXT, DOCX, MD) et pose des questions en **arabe, français ou anglais**, en texte ou **à la voix**. L'outil répond avec des citations (document, page), retrouve des passages **entre langues** (question en arabe, texte en français) et peut **comparer les versions linguistiques** d'un même passage avec ton traducteur. Tout est évalué avec des chiffres.
> **Corpus de test :** le corpus parallèle des Nations unies (textes officiels traduits à la main en arabe, français, anglais et trois autres langues).

Ce plan **complète** le fichier `DocChat_Multilingue_Projet_Complet.md` (le catalogue des outils T01 à T38). Ici, les choix sont déjà faits, et tu sais quoi taper et dans quel ordre. Si les deux fichiers se contredisent, **celui-ci fait foi**.

---

## 0. Résumé d'une page

| Question | Réponse |
|---|---|
| Durée | 10 semaines + 1 semaine de démarrage, à environ 10 h par semaine |
| Coût | 0 € (tout tourne en local) |
| Matériel | i7 8e génération, CPU seul, 16 Go de RAM (à confirmer) |
| Structure | **3 paliers**, chacun est un projet fini que tu peux montrer |
| Palier A (4 sem.) | Français et anglais, texte, RAG simple, isolation, évaluation |
| Palier B (3 sem.) | Arabe, recherche hybride, reranker, **question à la voix** |
| Palier C (3 sem.) | Ton traducteur, comparaison de versions, agent LangGraph, test de charge |
| Règle d'or | Un seul changement à la fois, mesuré avant et après |
| Règle de survie | Si tu es en retard, tu coupes le palier C, **jamais l'évaluation** |

**Ce que tu peux dire à la fin :** « J'ai construit un assistant RAG multilingue avec isolation testée, recherche hybride, question vocale, traducteur intégré et agent, évalué sur un corpus officiel avec des métriques par langue, entièrement en local. »

---

## 1. Périmètre

### Dans le projet

| Fonction | Palier |
|---|---|
| Comptes, upload TXT / PDF texte / DOCX / MD, statut d'indexation | A |
| Question en texte, réponse avec citations (document, page) | A |
| Isolation stricte entre utilisateurs (test automatique) | A |
| Évaluation du retrieval (recall@k, MRR) par langue | A |
| Arabe : parsing, normalisation, retrieval cross-lingue | B |
| Recherche hybride (dense + BM25) et reranker | B |
| **Question à la voix** (Whisper), avec mesure de son coût | B |
| Traducteur intégré (ton modèle, comparé à d'autres) | C |
| **Comparaison des versions linguistiques** d'un passage | C |
| Agent LangGraph, comparé au pipeline fixe | C |
| Logs par étape, test de charge, CI, README chiffré | C |

### Hors projet (décidé une fois pour toutes)

OCR et PDF scannés (détectés et refusés), images, graphe de connaissances, fine-tuning, cloud, vrais utilisateurs, voix en temps réel, indexation de fichiers audio (extension possible plus tard : voir section 9).

### Note sur l'audio

L'audio sert d'abord à **poser la question** (palier B). Indexer des enregistrements comme contenu est une extension facultative : je n'ai pas trouvé de jeu de données audio public vérifié pour ce domaine, donc tu devrais l'évaluer avec tes propres enregistrements.

---

## 2. Technologies retenues

Chaque choix a une raison et une **alternative de secours** si tu bloques ou si la mesure le contredit. Pour comparer d'autres options, voir le catalogue T01 à T38.

| Tâche | Choix retenu | Pourquoi | Plan B |
|---|---|---|---|
| Environnement | Python 3.11 ou 3.12 + `uv` | Installation rapide et reproductible | pip + venv |
| Runtime LLM | **Ollama** | Le plus simple, API HTTP locale | llama.cpp |
| LLM | Un **Qwen 3 de 4B** (ou moins), quantifié | Bon rapport qualité/taille, multilingue, licence permissive (à vérifier) | Un autre modèle 3 à 4B (Gemma, etc.) après benchmark |
| API | **FastAPI** + Pydantic | Async, SSE, documentation automatique | — |
| Base relationnelle | **SQLite** (SQLModel ou SQLAlchemy) | Zéro service | PostgreSQL si tu en as besoin |
| Tâches de fond | `BackgroundTasks` + table de statut | Suffisant à ton échelle | RQ |
| Auth | JWT (`PyJWT`) + `argon2-cffi` | Simple, pédagogique | fastapi-users |
| Parsing | `pypdf` et `pdfplumber` (à comparer), `python-docx` | Licences permissives | PyMuPDF (⚠️ AGPL, à lire) |
| Détection de langue | `lingua-py` | Précis sur les textes courts | fastText |
| Chunking | Récursif par paragraphes, taille en tokens, chevauchement | Robuste | Par titres |
| Embeddings | **multilingual-e5-small** (dev) puis **bge-m3** (final) | Cross-lingue, arabe inclus | Un autre modèle après E3 |
| Base vectorielle | **Qdrant** (Docker) | Filtre par utilisateur, hybride natif | Chroma ou LanceDB si la RAM manque |
| Lexical | BM25 sparse dans Qdrant | Un seul système | Analyseur arabe à tester |
| Fusion | **RRF** | Robuste sans calibrage | Somme pondérée |
| Reranker | **bge-reranker-v2-m3** sur le top 20 | Multilingue | FlashRank, ou sans reranker si le gain est nul |
| STT | **faster-whisper** `small` int8 | Rapide sur CPU, VAD intégré | `base` si trop lent |
| Traduction | **Ton modèle** derrière `translate(text, src, tgt)` | Objet du projet | M2M100, Opus-MT, NLLB (⚠️ non commercial) |
| Agent | Python simple, puis **LangGraph** (palier C) | Boucles limitées, traçabilité | — |
| Sorties structurées | Pydantic + JSON Schema d'Ollama | Routage fiable | Règles + classifieur |
| UI | **Streamlit** (`st.audio_input` pour la voix) | Rapide | Gradio |
| Logs | `structlog` (JSON) | Zéro infrastructure | — |
| Observabilité | Prometheus + Grafana (palier C, facultatif) | Standard | Simple tableau de latence |
| Éval retrieval | Scripts maison | Transparents | `ranx` |
| Éval STT / traduction | `jiwer` / `sacrebleu` | Standards | COMET (échantillon) |
| Tests | `pytest`, **Locust** | Simples | k6 |
| Conteneurs | **Docker Compose** | Un seul `docker compose up` | Podman |
| CI | GitHub Actions + Ruff | Gratuit pour un dépôt public (vérifie les quotas) | — |

**Modèles à charger à la demande :** ne garde pas LLM, embeddings, reranker et Whisper en mémoire en même temps sans mesurer la RAM.

---

## 3. Architecture

### 3.1 Ingestion

```text
Upload (TXT / PDF texte / DOCX / MD)         [user_id = token, jamais un paramètre client]
   ▼ vérif : taille, type MIME réel, nombre de pages
Stockage : data/users/<user_id>/<doc_id>/
   ▼ tâche de fond (statut : queued → processing → indexed | error)
parse → texte + page       (PDF sans texte extractible → erreur claire « scanné »)
   ▼
détecter la langue → normaliser (unicode ; arabe : diacritiques, alef, tatweel)
   ▼
chunker (tokens + chevauchement, préfixe : titre du document)
   ▼
embeddings (dense ; sparse au palier B)
   ▼
Qdrant : payload = {user_id, doc_id, chunk_key, lang, page, source_name, text}
```

### 3.2 Question

```text
Question texte ou voix                       [user_id = token serveur]
   ▼ (voix) transcribe → langue, confiance ; confirmation possible
detect_lang + normalize
   ▼
retrieve (filtre user_id obligatoire) → rerank → check_context
   ▼ insuffisant : reformulate (max 2) puis refuse
generate (langue de la question, citations obligatoires)
   ▼
réponse + sources (document, page) + latence par étape
```

### 3.3 Règles d'isolation

- **Une seule collection Qdrant** avec `user_id` indexé et un **filtre obligatoire** à chaque recherche (dans chaque sous-requête si tu fais de l'hybride).
- La fonction `search()` **n'a pas de valeur par défaut** pour `user_id`.
- Le LLM ne reçoit jamais `user_id`.
- Les clés de cache contiennent `user_id`.
- `DELETE /documents/{id}` et `DELETE /me` effacent fichiers, vecteurs et métadonnées.
- **L'audio n'est pas conservé** : il est transcrit puis supprimé (la voix est une donnée personnelle).

### 3.4 Structure du dépôt

```text
linguadocs/
├── README.md
├── pyproject.toml
├── docker-compose.yml
├── .env.example
├── docs/
│   ├── benchmarks.md          # tes mesures de la semaine 0
│   ├── decisions.md           # une entrée par choix d'outil
│   └── results/               # CSV de chaque expérience
├── src/linguadocs/
│   ├── api/                   # routes, auth, schémas
│   ├── ingest/                # parsers, langue, chunking, indexation
│   ├── retrieval/             # dense, sparse, fusion, rerank
│   ├── llm/                   # client Ollama, prompts
│   ├── speech/                # transcription (palier B)
│   ├── translate/             # interface + implémentations (palier C)
│   ├── agent/                 # graphe LangGraph (palier C)
│   └── settings.py
├── eval/
│   ├── datasets/              # jeux préparés (voir section 6)
│   ├── prepare_un.py
│   ├── run_retrieval.py
│   ├── run_stt.py
│   └── run_translation.py
├── scripts/                   # benchmarks de la semaine 0
├── tests/                     # dont test_isolation.py
├── loadtests/locustfile.py
└── ui/streamlit_app.py
```

### 3.5 Endpoints par palier

| Palier | Endpoints |
|---|---|
| A | `POST /auth/register`, `POST /auth/login`, `POST /documents`, `GET /documents`, `DELETE /documents/{id}`, `POST /ask`, `GET /health` |
| B | `POST /ask/audio` (ou `POST /transcribe` puis `/ask` pour confirmer la transcription) |
| C | `POST /translate`, `POST /compare` (versions linguistiques), `GET /metrics` |

---

# 4. COMMENCE ICI : la semaine 0 (7 jours, environ 2 h par jour)

**Objectif de la semaine :** à la fin, tu as un dépôt, Qdrant qui tourne, tes chiffres de performance, un mini-corpus, et ton **premier test d'isolation qui passe**. Rien d'autre.

### Jour 1 — Installer les outils

1. **Git** et un compte GitHub.
2. **Docker** (Docker Desktop, ou Docker Engine sous Linux). Sous Windows, active WSL2 et limite sa mémoire (fichier `.wslconfig`, par exemple 8 Go).
3. **uv** (gestionnaire Python) : suis les instructions officielles de son site.
4. **Ollama** : installe-le depuis son site, puis télécharge un petit modèle. Vérifie le nom exact sur la bibliothèque d'Ollama :
   ```bash
   ollama pull qwen3:4b
   ollama run qwen3:4b "Dis bonjour en arabe, français et anglais."
   ```
5. **Un micro** qui marche (pour la semaine 7).

**Terminé quand :** `docker --version`, `uv --version` et la réponse d'Ollama fonctionnent.

### Jour 2 — Créer le dépôt et lancer Qdrant

```bash
mkdir linguadocs && cd linguadocs
git init
uv init --package --name linguadocs --python 3.11
mkdir -p docs/results eval/datasets scripts tests data src/linguadocs/retrieval
touch src/linguadocs/retrieval/__init__.py
```

Crée `docker-compose.yml` (annexe A), puis :

```bash
docker compose up -d
# ouvre http://localhost:6333/dashboard dans ton navigateur
```

Crée `docs/decisions.md` et recopie le tableau de la section 2 avec la mention « provisoire ». Premier commit.

**Terminé quand :** le tableau de bord Qdrant s'affiche.

### Jour 3 — Mesurer ton PC (semaine 0, jour crucial)

```bash
uv add httpx sentence-transformers faster-whisper jiwer qdrant-client
```

Copie les trois scripts de l'annexe B dans `scripts/` et lance-les. Note **tes chiffres** dans `docs/benchmarks.md` : tokens par seconde du LLM, temps avant le premier token, chunks par seconde des embeddings (e5-small et bge-m3), vitesse de faster-whisper (RTF) sur un enregistrement de toi, et la RAM maximale observée.

**Terminé quand :** `docs/benchmarks.md` contient des chiffres réels. Ce sont eux qui décident du LLM et des modèles que tu gardes.

### Jour 4 — Télécharger un petit échantillon du corpus ONU

1. Ouvre la page de téléchargement du corpus parallèle de l'ONU (cherche « United Nations Parallel Corpus » sur le site du département DGACM de l'ONU).
2. Commence par la **section « Test and development sets »** : ce sont des documents de 2015 mis de côté, avec **100 documents** (50 pour le développement, 50 pour le test), dont les phrases existent dans toutes les langues officielles. C'est petit, aligné et parfait pour démarrer.
3. **Ne télécharge pas** tout de suite les archives complètes : elles sont énormes et découpées en morceaux (`.00`, `.01`, …). Si tu en as besoin plus tard, regroupe les morceaux d'une même archive avec `cat` avant l'extraction, et lis le README de l'archive.
4. **Licence et attribution :** la page indique que le corpus est composé de documents publics de l'ONU, et exige de citer l'ONU comme source et de citer l'article de référence (Ziemski, Junczys-Dowmunt et Pouliquen, 2016). Note-le dans ton README dès maintenant.
5. Regarde la structure des fichiers (un fichier par document ou par langue, format texte ou XML ?) avec `ls`, `head`, et le script d'exploration de l'annexe B. **Je n'ai pas vu le contenu exact de ces fichiers : adapte le script de préparation à ce que tu constates.**

**Terminé quand :** tu sais décrire, en 3 lignes dans `docs/decisions.md`, comment sont organisés tes fichiers et comment retrouver la phrase arabe et sa version française.

### Jour 5 — Ton premier retrieval cross-lingue

1. Prends **50 documents** ou passages de l'échantillon, en français et en anglais (l'arabe viendra au palier B).
2. Copie `dense.py` (annexe B5) dans `src/linguadocs/retrieval/`. Écris un petit script qui appelle `dense.init()`, `dense.index("alice", [...])` avec tes passages (chaque passage : `chunk_key`, `text`, `lang`, `page`), puis `dense.search("alice", "ta question")`.
3. Pose 5 questions à la main, en français, puis en anglais sur du texte français.
4. Regarde les résultats et note dans `docs/benchmarks.md` ce qui marche et ce qui ne marche pas.

**Terminé quand :** une question en anglais retrouve un passage en français dans les 3 premiers résultats.

### Jour 6 — Le test d'isolation (avant le reste du code)

Installe pytest (`uv add --dev pytest`), copie `test_isolation.py` (annexe B6) dans `tests/`, lance `uv run pytest`. Il doit **passer**. Casse-le volontairement (retire le filtre `user_id`), vérifie qu'il **échoue**, puis remets le filtre.

**Terminé quand :** le test passe avec le filtre et échoue sans.

### Jour 7 — Premier chiffre et revue

1. Copie `eval/prepare_un.py` (annexe B7), écris la fonction `load_aligned()` d'après ce que tu as compris au jour 4, puis lance `build(...)` et `index_corpus()`. Tu obtiens `eval/datasets/un_pairs.jsonl` (voir section 6.2). Garde seulement `fr` et `en` pour l'instant.
2. Lance `eval/run_retrieval.py` (annexe B8) et note ton **premier recall@5**, quel qu'il soit.
3. Commit, puis relis la liste de vérification :

- [ ] Docker, Qdrant, Ollama fonctionnent
- [ ] `benchmarks.md` avec des chiffres réels
- [ ] Échantillon ONU compris (structure et licence notées)
- [ ] Retrieval FR/EN qui marche
- [ ] Test d'isolation vert
- [ ] Premier recall@5 noté
- [ ] Tout est commité sur GitHub

**Tu as terminé la semaine 0.** Passe au palier A.

---
## 5. Plan semaine par semaine

Pour chaque semaine : tu suis les étapes dans l'ordre, tu notes la décision dans `docs/decisions.md`, tu sauvegardes les mesures dans `docs/results/`, et tu ne passes à la suite que quand le critère « Terminé quand » est atteint.

---

# PALIER A — Le noyau (français et anglais, texte) : semaines 1 à 4

### Semaine 1 — API, comptes, upload, parsing

**Étapes**
1. Installer les dépendances :
   ```bash
   uv add fastapi "uvicorn[standard]" python-multipart pydantic-settings sqlmodel \
          pyjwt argon2-cffi pypdf pdfplumber python-docx lingua-language-detector
   ```
2. `settings.py` (Pydantic Settings) : chemins, URL de Qdrant, URL d'Ollama, clé secrète JWT dans `.env`.
3. Modèles SQLite : `users`, `documents` (id, user_id, filename, lang, n_pages, status, error).
4. **Auth** : `/auth/register` (mot de passe haché avec argon2), `/auth/login` (JWT), et une dépendance `current_user()` qui lit le token. `user_id` ne vient **jamais** du corps de la requête.
5. `POST /documents` : vérifier taille et type MIME réel, enregistrer sous `data/users/<user_id>/<doc_id>/`, créer la ligne `documents` avec le statut `queued`, lancer l'indexation en tâche de fond.
6. Parsers derrière une interface `parse(path) -> list[Page]` : TXT, PDF (pypdf **et** pdfplumber), DOCX (python-docx). Si un PDF renvoie très peu de texte par page : statut `error`, message « PDF scanné non supporté ».
7. Détection de langue avec lingua-py sur chaque document.
8. Pour l'instant, l'indexation s'arrête après le parsing (les vecteurs viennent en semaine 2). Le statut passe à `parsed`.

**Décisions à noter :** T04 (FastAPI), T05 (JWT), T06 (SQLite), T07 (BackgroundTasks), T09 (parseur : provisoire, tranché en E1).

**Terminé quand :** je téléverse un PDF via `http://localhost:8000/docs` et le statut passe à `parsed` avec la langue détectée.

### Semaine 2 — Chunking, embeddings, retrieval, isolation dans l'API

**Étapes**
1. Chunker : paragraphes, taille cible en tokens, chevauchement, préfixe de titre. Paramètres dans `settings.py` pour pouvoir les faire varier.
2. Embeddings avec sentence-transformers (**e5-small** au début, n'oublie pas les préfixes `query:` et `passage:`).
3. Créer la collection Qdrant et l'**index de payload** sur `user_id`.
4. Indexation complète : statut `indexed`. Le payload contient `user_id`, `doc_id`, `chunk_key`, `lang`, `page`, `text`.
5. `POST /ask` **sans LLM** : renvoie les 5 meilleurs passages avec document et page.
6. **Test d'isolation au niveau de l'API** (annexe B) avec deux utilisateurs.
7. `DELETE /documents/{id}` qui supprime fichier, vecteurs et ligne SQL. Ajoute le test associé.

**Décisions :** T11 (lingua), T12 (chunking : provisoire), T13 (e5-small pour développer), T15 (Qdrant).

**Terminé quand :** deux utilisateurs, zéro fuite dans le test automatique, et `/ask` retrouve les bonnes sources sur 5 questions faites à la main.

### Semaine 3 — Jeu d'évaluation, baseline et premières expériences

**Étapes**
1. Construire le jeu d'évaluation (section 6) : requêtes tirées de l'ONU (automatiques) **et** 30 à 50 questions écrites à la main. Sépare `dev` et `test`.
2. `eval/run_retrieval.py` : recall@k et MRR, **par langue**, résultats sauvegardés en CSV.
3. **E2 : taille des chunks.** 200, 400 et 800 tokens, chevauchement 0 % et 15 %. Un paramètre à la fois.
4. **E3 : embeddings.** e5-small contre bge-m3 (recall@k, chunks par seconde, RAM). Si l'indexation de bge-m3 est trop lente, calcule les vecteurs sur Kaggle ou Colab (quotas gratuits) et récupère-les.
5. **E1 (FR/EN) : parseurs.** pypdf contre pdfplumber sur 10 PDF officiels que tu as téléchargés à la main (lis les conditions de réutilisation du site). Compare l'ordre du texte, les en-têtes répétés et les tableaux.

**Décisions :** T09, T12, T13 tranchées avec tes chiffres, en utilisant la matrice de la section 4 du catalogue.

**Terminé quand :** un tableau `docs/results/E1_E2_E3.csv` et un paragraphe par décision dans `decisions.md`.

### Semaine 4 — Génération, citations, refus, Docker, README v1

**Étapes**
1. Client Ollama (`llm/`), prompt avec **règles strictes** : répondre uniquement avec le contexte, citer `[doc, page]`, répondre dans la langue de la question, dire « je ne sais pas » sinon.
2. Refus hors domaine : si le meilleur score de retrieval est sous un seuil réglé sur `dev`, ne pas appeler le LLM.
3. Streaming SSE de la réponse.
4. **E15 : refus.** 30 questions sans réponse dans les documents. Mesure refus corrects et faux refus.
5. Évaluer la génération **sans LLM-juge** : la source attendue est citée, la langue de réponse est correcte (lingua), taux de refus.
6. Dockeriser l'API (Dockerfile) et compléter `docker-compose.yml`. Ollama peut rester sur ta machine hôte (souvent plus rapide).
7. README v1 : démarrage en une commande, architecture, tableaux E1 à E3, E15, limites.

**Terminé quand :** `docker compose up` puis upload, question, réponse avec citations, et un README avec des chiffres. **MVP terminé : tu peux t'arrêter ici avec un projet solide.**

---

# PALIER B — Arabe, hybride et voix : semaines 5 à 7

### Semaine 5 — L'arabe

**Étapes**
1. **Normalisation arabe** avant indexation et avant recherche : suppression des diacritiques et du tatweel, unification des formes d'alef, chiffres arabo-indiques. Ajoute des tests unitaires avec des exemples.
2. **E1 (arabe) : parseurs.** Teste pypdf et pdfplumber sur 10 PDF arabes officiels. Cherche les lettres inversées, l'ordre des mots et les chiffres. Si les deux échouent, essaie un autre extracteur (voir T09 du catalogue).
3. Ajouter des documents arabes au corpus de test (à partir de l'échantillon ONU).
4. **E6 : matrice cross-lingue.** Requêtes en arabe, français, anglais contre des documents en arabe, français, anglais (3 × 3), avec e5 et bge-m3.
5. Réponse dans la langue de la question, vérifiée par lingua. Mesure aussi la qualité du LLM en arabe : il sera probablement le point faible (à confirmer sur ton jeu).

**Décisions :** T11/T12 (normalisation), T13 (modèle final selon E6), T03 (LLM : si le petit modèle est trop faible en arabe, note-le comme limite ou passe à un modèle plus multilingue si ta RAM le permet).

**Terminé quand :** un tableau 3 × 3 (recall@5 par paire de langues) et la liste des problèmes rencontrés en arabe.

### Semaine 6 — Recherche hybride et reranker

**Étapes**
1. Ajouter les vecteurs **sparse BM25** dans Qdrant (fastembed ou calcul maison). Vérifie que la tokenisation et le stemming existent pour ta langue.
2. Recherche hybride par **RRF**, avec le filtre `user_id` **dans chaque sous-requête**.
3. **E4 : dense, sparse ou hybride.** Résultats par langue.
4. Reranker `bge-reranker-v2-m3` sur le top 20. **E5 :** avec ou sans reranker, top 10/20/30, gain contre latence.
5. Si un composant n'apporte rien : garde la version simple et **écris-le**.

**Décisions :** T16, T17, T18.

**Terminé quand :** un tableau (dense, sparse, hybride, hybride + reranker) avec recall@5, MRR et latence, par langue.

### Semaine 7 — Question à la voix

**Étapes**
1. `uv add` : rien de plus, faster-whisper est déjà installé. Charge le modèle `small` en int8 **une seule fois** au démarrage.
2. `POST /transcribe` (audio en entrée, texte + langue + confiance en sortie) et `POST /ask/audio`. L'audio est traité dans un fichier temporaire **supprimé aussitôt**.
3. **Langue :** détecter, forcer la langue si la confiance est élevée, avertir si elle est basse. Deux modes : automatique, ou **confirmation** (l'utilisateur corrige le texte avant que le pipeline ne tourne).
4. Normalisation de la transcription : nombres dictés (« mille deux cent vingt et un »), acronymes, symboles de documents.
5. **E9 : ce que coûte la voix.**
   - Enregistre **60 questions** (20 par langue) lues à voix haute, avec au moins 2 voix ou 2 micros différents.
   - Mesure le WER par langue (jiwer, avec normalisation), le RTF, et surtout la **baisse de recall@5** entre la question tapée et la question transcrite.
   - Compare `tiny`, `base` et `small`.
6. **E16 (optionnelle) : lexique par utilisateur.** Extraire les termes fréquents et les symboles des documents de l'utilisateur, les utiliser comme `initial_prompt` de Whisper (à tester) ou pour corriger la transcription par correspondance floue. Compare avec et sans.
7. Interface Streamlit : bouton d'enregistrement (`st.audio_input`), texte transcrit modifiable, réponse avec sources.

**Décisions :** T20 (taille de Whisper selon E9), T27 (Streamlit).

**Terminé quand :** le tableau « texte contre voix » (WER, RTF, recall@5 par langue), et une démo où tu poses une question en arabe à voix haute.

---

# PALIER C — Traducteur, comparaison et agent : semaines 8 à 10

### Semaine 8 — Ton traducteur

**Étapes**
1. **Interface** `translate(text, src, tgt) -> str` dans `translate/`. Ton modèle est une implémentation. Ajoute au moins **une alternative** (M2M100, Opus-MT ou le LLM local) pour comparer. Vérifie leurs licences (T21).
2. Mesure de ton modèle : qualité (chrF++ avec sacrebleu sur les phrases alignées de l'ONU, sur `test` seulement à la fin), vitesse par phrase sur CPU, RAM.
3. **E7 : où placer le traducteur ?**
   - D : rien de traduit (baseline, retrieval cross-lingue direct).
   - B : question traduite avant la recherche.
   - A : réponse traduite dans la langue de l'utilisateur.
4. `POST /translate` explicite (bouton « Traduire »).

**Terminé quand :** un tableau chrF++ et latence par modèle, et un tableau des positions A, B, D avec recall@5 et latence. **Un résultat négatif est valide.**

### Semaine 9 — Comparaison de versions et agent LangGraph

**Étapes**
1. **Comparaison de versions** (section 8.2) : `POST /compare`. Évaluation par injection d'erreurs (E17).
2. Version « pipeline fixe » figée : c'est ta référence (tout le pipeline du palier B).
3. **Agent LangGraph** (section 8.1) : routage par règles, `check_context`, reformulation limitée à 2, refus, nœuds `translate` et `compare`.
4. **E10 :** routage (toujours `ask`, règles, oracle). **E11 :** agent contre pipeline fixe sur `test`.
5. Si l'agent ne bat pas le pipeline fixe sur un critère mesuré (précision, refus corrects, fonctionnalités couvertes), **garde le pipeline fixe** et documente pourquoi.

**Décisions :** T23 (routeur), T24 (LangGraph).

**Terminé quand :** un tableau agent contre pipeline fixe et le taux de détection de la comparaison de versions.

### Semaine 10 — Ingénierie, charge, CI, README final

**Étapes**
1. Logs JSON avec `request_id` et **durée par étape** (transcription, retrieval, rerank, génération, traduction). Prometheus et Grafana seulement si le temps le permet : un tableau de latence calculé à partir des logs suffit.
2. Cache exact (clé : `user_id` + version d'index + question normalisée).
3. **E13 : test de charge** avec Locust : 1, 2, 5, 10 utilisateurs, endpoint de retrieval seul et endpoint complet. Explique le goulot (CPU).
4. **CI** GitHub Actions : Ruff, tests unitaires, test d'isolation, évaluation de retrieval sur un **mini-jeu** avec un petit modèle, sans LLM.
5. **README final** (section 11) et une vidéo de démonstration de 2 minutes.

**Terminé quand :** dépôt propre, CI verte, README avec tous les tableaux et les limites.

---

## 6. Jeux de données et comment les préparer

### 6.1 Corpus ONU (documents et évaluation automatique)

- **Contenu :** documents officiels de l'ONU (1990 à 2014) traduits à la main en arabe, chinois, anglais, français, russe et espagnol, avec alignement au niveau des phrases.
- **À utiliser en premier :** les **ensembles dev et test de 2015** (100 documents), dont les phrases existent dans toutes les langues. Petits et alignés.
- **Attribution obligatoire :** cite l'ONU comme source et l'article de référence (Ziemski, Junczys-Dowmunt, Pouliquen, LREC 2016) dans le README.
- **Tailles :** les archives complètes sont très grandes. Travaille sur une **tranche** de quelques centaines à quelques milliers de phrases par langue.

### 6.2 Requêtes automatiques (« phrase comme requête »)

Pour chaque phrase alignée `s_ar`, `s_fr`, `s_en` d'un document :
- **Requête** = la phrase dans une langue (par exemple `s_ar`).
- **Cible** = le `chunk_key` du passage qui contient la version d'une **autre** langue (par exemple `s_fr`).

Cela donne des milliers de tests cross-lingues sans annotation. **Limite à noter dans ton README :** une phrase traduite est une requête presque « paraphrase » du texte cible, donc elle **surestime** la qualité par rapport à de vraies questions.

### 6.3 Vraies questions (indispensables)

Écris **30 à 50 questions à la main** (10 à 15 par langue), à partir de passages que tu as lus, avec le passage attendu. Ajoute **30 questions hors domaine** (pour le refus). Sépare 60 % `dev` et 40 % `test`, et ne touche à `test` qu'à la fin de chaque palier.

### 6.4 Documents PDF réels

Télécharge **10 PDF officiels par langue** (arabe, français, anglais) à la main, pour tester le parsing (E1). Vérifie les conditions de réutilisation et ne les republie pas dans ton dépôt sans y avoir droit. La comparaison de retrieval (E3 à E6) utilise des fichiers texte issus du corpus pour **séparer** l'effet du parsing de l'effet du retrieval.

### 6.5 Questions vocales (palier B)

- Lis 60 questions (20 FR, 20 AR, 20 EN) à voix haute, en environnement calme, puis 20 avec un léger bruit de fond.
- Format : WAV mono 16 kHz, un fichier par question, nommé par identifiant, plus un fichier texte avec la transcription de référence.
- Si un proche ou un ami enregistre 10 questions, ta mesure devient bien plus crédible (accent, micro différents).
- **Consentement** : garde ces enregistrements privés, ne les publie pas.

### 6.6 Erreurs injectées (palier C)

À partir de 100 paires alignées, crée des versions altérées : chiffre modifié, date décalée, négation supprimée ou ajoutée, nom propre remplacé. Garde aussi 100 paires **intactes** pour mesurer les faux positifs.

---

## 7. Évaluation

### 7.1 Principes

1. **Dev et test séparés** : les seuils se règlent sur `dev`, les résultats finaux se lisent sur `test`, utilisé une seule fois.
2. **Toujours par langue** (arabe, français, anglais), jamais une moyenne globale seule.
3. **Un changement à la fois**, résultat sauvegardé en CSV avec la date et la version du code.
4. **Intervalle de confiance** (bootstrap) sur les petits échantillons. N'interprète pas une différence de un ou deux points.
5. **Métriques sans LLM d'abord.** Le LLM-juge local est lent et bruité : échantillon de 30 questions, la nuit.
6. **Limites écrites** : requêtes quasi-paraphrases, PDF générés, LLM petit, corpus restreint.

### 7.2 Expériences par palier

| ID | Palier | Question | Configurations | Métriques |
|---|---|---|---|---|
| E1 | A/B | Quel parseur PDF ? | pypdf, pdfplumber (et un autre si l'arabe échoue) | Ordre du texte, lettres correctes, temps |
| E2 | A | Quelle taille de chunk ? | 200 / 400 / 800 tokens, chevauchement 0 / 15 % | recall@5, MRR |
| E3 | A | Quel modèle d'embeddings ? | e5-small, bge-m3 | recall@5, MRR, chunks/s, RAM |
| E15 | A | Le refus fonctionne-t-il ? | Seuil de score réglé sur dev | Refus corrects, faux refus |
| E6 | B | Perte cross-lingue ? | Requête AR/FR/EN × document AR/FR/EN | recall@5 par paire |
| E4 | B | Dense, sparse ou hybride ? | dense, BM25, RRF | recall@5, MRR, latence |
| E5 | B | Le reranker vaut-il son coût ? | sans, top 10/20/30 | Gain de recall, latence ajoutée |
| E9 | B | Que coûte la voix ? | tiny/base/small × FR/AR/EN, texte contre voix | WER, RTF, baisse de recall@5 |
| E16 | B | Le lexique par utilisateur aide-t-il ? | sans, `initial_prompt`, correction floue | WER, exactitude des termes, recall |
| E7 | C | Où placer le traducteur ? | D, B, A × ton modèle et alternatives | recall@5, chrF++, latence |
| E17 | C | La comparaison détecte-t-elle les écarts ? | Règles seules, règles + traducteur | Taux de détection, faux positifs |
| E10 | C | Le routeur apporte-t-il quelque chose ? | Toujours `ask`, règles, oracle | Routing accuracy |
| E11 | C | L'agent bat-il le pipeline fixe ? | Pipeline fixe contre agent | recall@5, réponses correctes, refus corrects, latence |
| E13 | C | Tenue en charge ? | 1, 2, 5, 10 utilisateurs | Latence P50/P95, erreurs |
| E14 | A→C | Fuites entre utilisateurs ? | Test automatique en continu | Nombre de fuites (cible : 0) |

### 7.3 Définitions

| Métrique | Définition |
|---|---|
| recall@k | Part des requêtes dont une source pertinente est dans les k premiers résultats |
| MRR | Moyenne de 1 / rang de la première source pertinente |
| WER | (substitutions + suppressions + insertions) / nombre de mots de la référence |
| RTF | Durée de traitement / durée de l'audio |
| chrF++ | Similarité de n-grammes de caractères et de mots (conseillé pour l'arabe) |
| Taux de détection | Part des paires altérées correctement signalées |
| Faux positif | Paire intacte signalée à tort |

### 7.4 Modèle de tableau pour le README

| Configuration | AR | FR | EN | Latence P50 |
|---|---:|---:|---:|---:|
| Dense (e5-small) | | | | |
| Dense (bge-m3) | | | | |
| Hybride | | | | |
| Hybride + reranker | | | | |

*(Cellules à remplir avec tes mesures : recall@5 par langue de la requête.)*

---
## 8. Palier C en détail : agent et comparaison de versions

### 8.1 Agent LangGraph

**Intentions gérées :** `ask` (question sur les documents), `translate` (traduire un passage ou la dernière réponse), `compare` (comparer les versions linguistiques d'un passage), `refuse`.

```python
from typing import Literal, TypedDict
from pydantic import BaseModel, Field

class RouteDecision(BaseModel):
    intent: Literal["ask", "translate", "compare", "refuse"]
    target_lang: str | None = Field(None, description="Code ISO 639-1, ex. 'ar'")
    text_source: Literal["last_answer", "quoted_passage", "user_message"] | None = None
    confidence: float = Field(ge=0, le=1)

class GraphState(TypedDict, total=False):
    user_id: str                 # fixé par le serveur, jamais par le LLM
    question: str
    question_lang: str | None
    decision: RouteDecision
    docs: list[dict]
    answer: str | None
    citations: list[dict]
    retries: int
    trace: list[dict]            # durée de chaque nœud
```

**Routeur en cascade** (du moins cher au plus cher) : 1) règles multilingues (« traduis », « translate », « ترجم », « compare », « قارن »…) ; 2) si aucune règle ne s'applique, `ask` par défaut ; 3) le LLM en sortie structurée seulement si tu mesures que les règles ne suffisent pas. Sur ton CPU, un appel LLM de routage coûte plusieurs secondes.

**Graphe :**

```text
START → normalize → route
route ─ ask ───────► retrieve → rerank → check_context
                                   ├─ suffisant ─► generate → END
                                   ├─ insuffisant et retries < 2 ─► reformulate → retrieve
                                   └─ sinon ─► refuse → END
      ─ translate ─► translate → END
      ─ compare ───► compare_versions → END
      ─ refuse ────► refuse → END
```

```python
from langgraph.graph import StateGraph, START, END

g = StateGraph(GraphState)
for name, fn in [("normalize", normalize), ("route", route), ("retrieve", retrieve),
                 ("rerank", rerank), ("reformulate", reformulate), ("generate", generate),
                 ("translate", translate_node), ("compare_versions", compare_node),
                 ("refuse", refuse)]:
    g.add_node(name, fn)

g.add_edge(START, "normalize")
g.add_edge("normalize", "route")
g.add_conditional_edges("route", lambda s: s["decision"].intent,
    {"ask": "retrieve", "translate": "translate", "compare": "compare_versions", "refuse": "refuse"})
g.add_edge("retrieve", "rerank")
g.add_conditional_edges("rerank", check_context,      # renvoie "generate" | "reformulate" | "refuse"
    {"generate": "generate", "reformulate": "reformulate", "refuse": "refuse"})
g.add_edge("reformulate", "retrieve")
for n in ("generate", "translate", "compare_versions", "refuse"):
    g.add_edge(n, END)
app = g.compile()   # vérifie la documentation de la version de LangGraph que tu installes
```

**Garde-fous :** `retries <= 2` et limite de récursion, délai maximal par nœud, validation Pydantic de la décision (deux essais, puis repli sur `ask`), `user_id` injecté par le code, jamais par le LLM, texte des documents encadré comme **donnée** (aucune instruction issue d'un document n'est suivie).

**Ce que tu dois prouver (E10 et E11) :** l'agent apporte de nouvelles fonctions (traduire, comparer), mais sur les questions simples est-il aussi bon que le pipeline fixe, et à quel coût en latence ? Un « non » est un résultat.

### 8.2 Comparaison de versions linguistiques

**But :** l'utilisateur sélectionne un passage (ou le retrouve par une question). L'outil trouve la version équivalente dans une autre langue et signale les écarts de sens.

**Étapes :**
1. **Trouver la version équivalente** : retrieval cross-lingue dans les documents de l'utilisateur, premier résultat avec un seuil de similarité (réglé sur `dev`).
2. **Vérifications déterministes** (bon marché, fiables) :
   - les **nombres** sont-ils identiques (après normalisation des chiffres arabo-indiques et des séparateurs) ?
   - les **dates** sont-elles identiques ?
   - une **négation** apparaît-elle d'un côté seulement (listes de mots par langue) ?
3. **Vérification sémantique** : traduire la version A vers la langue B avec ton traducteur, puis mesurer la similarité (cosinus d'embeddings et chrF) avec la version B. Sous un seuil (réglé sur `dev`), signaler un écart possible.
4. **Explication** (facultative, LLM local) : formuler en une phrase où se trouve l'écart. Sinon, afficher simplement les deux textes et les différences repérées.

```python
import re
AR_DIGITS = str.maketrans("٠١٢٣٤٥٦٧٨٩", "0123456789")

def numbers(text: str) -> list[str]:
    text = text.translate(AR_DIGITS).replace("\u202f", "").replace("\u00a0", "")
    return sorted(re.findall(r"\d+(?:[.,]\d+)?", text))

def same_numbers(a: str, b: str) -> bool:
    return numbers(a) == numbers(b)
```

Attention aux séparateurs : « 1 000 », « 1,000 » et « 1.000 » ne veulent pas dire la même chose selon la langue. Teste ces cas avant de faire confiance à la règle.

**Évaluation (E17) :** avec les paires intactes et les paires altérées de la section 6.6, mesure le **taux de détection** par type d'erreur (chiffre, date, négation, nom) et le **taux de faux positifs**. Compare : règles seules, traducteur seul, les deux. Règle les seuils sur `dev`, rapporte `test`.

---

## 9. Extensions possibles (seulement après la semaine 10)

- **Audio comme contenu :** indexer des enregistrements que l'utilisateur téléverse (transcription avec horodatage, citations « 34:12 »). Il te faut alors un jeu d'évaluation audio : tes propres enregistrements, ou un corpus de conférences dont tu as vérifié la licence.
- **Mémoire de conversation** par utilisateur (table `messages`, fenêtre glissante).
- **Routage selon le type de fichier** pour la recherche hybride, comparé à « toujours hybride ».
- **Cache sémantique** (par utilisateur) : à évaluer avec prudence, le risque de mauvaise réponse existe.

---

## 10. Pièges fréquents

| Piège | Symptôme | Parade |
|---|---|---|
| Préfixes e5 oubliés | Résultats étrangement mauvais | `query:` pour les questions, `passage:` pour les textes |
| Changer de modèle d'embeddings | Résultats incohérents | Ré-indexer **toute** la collection, dimension de vecteur mise à jour |
| Filtre `user_id` absent d'une sous-requête hybride | Fuite entre utilisateurs | Test d'isolation exécuté sur l'hybride aussi |
| PDF arabe avec lettres inversées | Texte illisible, retrieval nul | Comparer les extracteurs (E1), normaliser, sinon documenter la limite |
| Phrases trop courtes ou génériques dans le jeu d'évaluation | Cibles ambiguës, recall faux | Filtrer les phrases de moins de 8 mots et dédoublonner |
| Whisper qui hallucine sur le silence | Texte inventé | VAD activé, seuil de confiance, message d'avertissement |
| Langue de Whisper mal détectée | Transcription absurde | Forcer la langue si la confiance est haute, sinon confirmation |
| Ollama trop lent ou qui charge le modèle à chaque appel | Latence énorme | Garder le modèle chargé (paramètre `keep_alive`, à vérifier), contexte court |
| RAM saturée (WSL2, Docker) | Processus tués | Limiter WSL2, charger les modèles à la demande |
| Optimiser sur `test` | Résultats trop beaux | `test` utilisé une seule fois par palier |
| Trop de changements en même temps | Impossible de savoir ce qui a marché | Une expérience = une variable |
| Données personnelles (voix) | Risque de confidentialité | Audio supprimé après transcription, jamais publié |

---

## 11. Travailler seul : règles et livrables

### 11.1 Quand tu es bloqué

1. **Timebox de 2 heures.** Au-delà, simplifie (moins de langues, moins de données, un modèle plus petit) ou passe à la suite en notant le blocage dans `decisions.md`.
2. **Réduis le problème** : un document, une question, un utilisateur.
3. **Sauvegarde le message d'erreur complet** et ce que tu as essayé.
4. **Ne change pas trois choses à la fois.**

### 11.2 Comment me demander de l'aide efficacement

Écris : « Semaine X, étape Y », ce que tu voulais obtenir, la commande lancée, l'erreur complète, et ton code concerné. Je te donne le script ou la correction pour **cette étape seulement**.

### 11.3 Critères de fin par palier

- **Palier A :** upload, question, réponse citée en français et anglais, isolation testée, tableaux E1 à E3 et E15, README v1.
- **Palier B :** arabe géré (ou limites documentées), tableaux E6, E4, E5, E9, démo à la voix.
- **Palier C :** traducteur mesuré (E7), comparaison de versions mesurée (E17), agent comparé au pipeline fixe (E10, E11), test de charge (E13), CI verte, README final.

### 11.4 Plan du README final

1. Le problème et la démo (capture ou courte vidéo).
2. Démarrage : `docker compose up` et les commandes utiles.
3. Architecture (schéma section 3).
4. **Données et attribution** (citer l'ONU, la référence de l'article, les licences).
5. **Résultats** : un tableau par expérience, par langue, avec les intervalles de confiance.
6. **Ce qui n'a pas marché** (par exemple : le reranker n'a pas aidé, l'arabe est faible, l'agent n'améliore pas le retrieval).
7. Limites (requêtes quasi-paraphrases, petit LLM, corpus restreint, dialectes non couverts).
8. Décisions techniques (lien vers `decisions.md`).
9. Confidentialité (audio non conservé, suppression des données).

### 11.5 Phrases de CV possibles (à ajuster à tes vrais résultats)

> Assistant RAG multilingue (AR/FR/EN) sur textes officiels de l'ONU : isolation multi-utilisateur testée, recherche hybride et reranking, question vocale (faster-whisper), traducteur intégré et agent LangGraph évalués contre un pipeline fixe, 100 % local sur CPU.

> Protocole d'évaluation reproductible par langue : recall@k et MRR, WER et baisse de recall due à la voix, chrF++ pour la traduction, taux de détection d'écarts entre versions linguistiques, latence P95 sous charge.

---

# ANNEXE A — docker-compose.yml (départ)

```yaml
services:
  qdrant:
    image: qdrant/qdrant        # fige un tag précis quand tout fonctionne
    ports:
      - "6333:6333"
    volumes:
      - ./data/qdrant:/qdrant/storage
    restart: unless-stopped
```

Ajoute l'API (`api`) en semaine 4, et Prometheus / Grafana en semaine 10 seulement si tu en as le temps. Ollama peut rester sur ta machine hôte.

---

# ANNEXE B — Scripts de démarrage

### B1 — `scripts/bench_ollama.py`

```python
import sys
import httpx

MODEL = sys.argv[1] if len(sys.argv) > 1 else "qwen3:4b"
PROMPTS = {
    "court": "Explique en deux phrases ce qu'est un corpus parallèle.",
    "long": "Voici un contexte. " + "Le Conseil a adopté une résolution. " * 150
            + "\nRésume ce contexte en une phrase.",
}
for name, prompt in PROMPTS.items():
    r = httpx.post("http://localhost:11434/api/generate",
                   json={"model": MODEL, "prompt": prompt, "stream": False},
                   timeout=900).json()
    gen_s = r.get("eval_duration", 1) / 1e9
    prompt_s = r.get("prompt_eval_duration", 0) / 1e9
    print(f"{name}: prompt {r.get('prompt_eval_count')} tokens en {prompt_s:.1f}s ; "
          f"génération {r.get('eval_count', 0) / gen_s:.1f} tokens/s ; "
          f"total {r.get('total_duration', 0) / 1e9:.1f}s")
```

### B2 — `scripts/bench_embeddings.py`

```python
import sys
import time
from sentence_transformers import SentenceTransformer

NAME = sys.argv[1] if len(sys.argv) > 1 else "intfloat/multilingual-e5-small"
texts = ["passage: " + "Le Conseil a adopté la résolution après un long débat. " * 20] * 100

t0 = time.time()
model = SentenceTransformer(NAME)
load = time.time() - t0
t0 = time.time()
model.encode(texts, batch_size=16, normalize_embeddings=True)
dt = time.time() - t0
print(f"{NAME}: chargement {load:.1f}s ; {len(texts) / dt:.1f} chunks/s")
```

Lance-le avec `intfloat/multilingual-e5-small` puis `BAAI/bge-m3`. Pour la RAM, regarde le gestionnaire de tâches pendant l'exécution (ou `/usr/bin/time -v` sous Linux).

### B3 — `scripts/bench_whisper.py`

```python
import sys
import time
from faster_whisper import WhisperModel

path = sys.argv[1]
size = sys.argv[2] if len(sys.argv) > 2 else "small"
model = WhisperModel(size, device="cpu", compute_type="int8")

t0 = time.time()
segments, info = model.transcribe(path, vad_filter=True)
text = " ".join(s.text.strip() for s in segments)   # le générateur est consommé ici
dt = time.time() - t0
print(f"langue={info.language} (p={info.language_probability:.2f}) "
      f"durée={info.duration:.1f}s temps={dt:.1f}s RTF={dt / info.duration:.2f}")
print(text)
```

### B4 — `scripts/explore_un.py` (inspecter les fichiers ONU téléchargés)

```python
import pathlib
import sys

root = pathlib.Path(sys.argv[1])
files = sorted(p for p in root.rglob("*") if p.is_file())
print(len(files), "fichiers")
for p in files[:20]:
    print(p, p.stat().st_size)
for p in files[:3]:
    print("===", p)
    print(p.read_text(encoding="utf-8", errors="replace")[:600])
```

### B5 — `src/linguadocs/retrieval/dense.py`

Crée aussi un fichier vide `src/linguadocs/retrieval/__init__.py`.

```python
import uuid
from qdrant_client import QdrantClient, models
from sentence_transformers import SentenceTransformer

client = QdrantClient(url="http://localhost:6333")
model = SentenceTransformer("intfloat/multilingual-e5-small")
COL, DIM = "chunks", 384          # 1024 pour bge-m3 (dense)


def init(reset: bool = False) -> None:
    if reset and client.collection_exists(COL):
        client.delete_collection(COL)
    if not client.collection_exists(COL):
        client.create_collection(
            COL, vectors_config=models.VectorParams(size=DIM, distance=models.Distance.COSINE))
        client.create_payload_index(
            COL, field_name="user_id", field_schema=models.PayloadSchemaType.KEYWORD)


def index(user_id: str, items: list[dict]) -> None:
    """items : [{"chunk_key": ..., "text": ..., "lang": ..., "page": ...}]"""
    vecs = model.encode([f"passage: {it['text']}" for it in items], normalize_embeddings=True)
    client.upsert(COL, points=[
        models.PointStruct(id=str(uuid.uuid4()), vector=v.tolist(),
                           payload={"user_id": user_id, **it})
        for v, it in zip(vecs, items)])


def search(user_id: str, query: str, k: int = 5):      # pas de valeur par défaut pour user_id
    q = model.encode(f"query: {query}", normalize_embeddings=True).tolist()
    flt = models.Filter(must=[models.FieldCondition(
        key="user_id", match=models.MatchValue(value=user_id))])
    return client.query_points(COL, query=q, query_filter=flt,
                               limit=k, with_payload=True).points
```

Vérifie les signatures dans la documentation de la version de `qdrant-client` que tu installes.

### B6 — `tests/test_isolation.py`

```python
import pytest
from linguadocs.retrieval import dense


@pytest.fixture(autouse=True)
def test_collection(monkeypatch):
    monkeypatch.setattr(dense, "COL", "test_chunks")     # ne touche pas à ta vraie collection
    dense.init(reset=True)


def test_bob_never_sees_alice():
    dense.index("alice", [{"chunk_key": "a1", "lang": "fr", "page": 1,
                           "text": "Le budget de 2012 a été adopté par la Cinquième Commission."}])
    dense.index("bob", [{"chunk_key": "b1", "lang": "fr", "page": 1,
                         "text": "La séance de l'après-midi a été consacrée aux droits de l'enfant."}])
    hits = dense.search("bob", "budget adopté par la Cinquième Commission", k=5)
    assert all(h.payload["user_id"] == "bob" for h in hits)
    assert all("Cinquième" not in h.payload["text"] for h in hits)


def test_search_requires_user_id():
    with pytest.raises(TypeError):
        dense.search(query="budget")
```

Installe `pytest` avec `uv add --dev pytest`, puis `uv run pytest`.

### B7 — `eval/prepare_un.py` (squelette à adapter)

```python
"""Adapte load_aligned() au format réel des fichiers ONU que tu as téléchargés.
Sortie : eval/datasets/un_corpus.jsonl et eval/datasets/un_pairs.jsonl"""
import json
from itertools import permutations


def load_aligned(n: int = 500) -> list[dict]:
    """Doit renvoyer [{"doc": "id_document", "fr": "...", "en": "...", "ar": "..."}, ...]"""
    raise NotImplementedError("À écrire après avoir inspecté tes fichiers (jour 4)")


def build(pairs: list[dict], langs=("fr", "en"), user_id="alice") -> None:
    seen, kept = set(), []
    for i, p in enumerate(pairs):
        texts = [p[lang] for lang in langs]
        if min(len(t.split()) for t in texts) < 8:      # phrases trop courtes ou génériques
            continue
        if texts[0] in seen:                             # dédoublonnage
            continue
        seen.add(texts[0])
        kept.append((i, p))

    with open("eval/datasets/un_corpus.jsonl", "w", encoding="utf-8") as fc, \
         open("eval/datasets/un_pairs.jsonl", "w", encoding="utf-8") as fq:
        for i, p in kept:
            for lang in langs:
                fc.write(json.dumps({"chunk_key": f"{p['doc']}#{i}:{lang}", "text": p[lang],
                                     "lang": lang, "page": 0}, ensure_ascii=False) + "\n")
            for qlang, tlang in permutations(langs, 2):         # requêtes cross-lingues seulement
                fq.write(json.dumps({"user_id": user_id, "lang": qlang, "target_lang": tlang,
                                     "query": p[qlang],
                                     "relevant": [f"{p['doc']}#{i}:{tlang}"]},
                                    ensure_ascii=False) + "\n")


def index_corpus(path="eval/datasets/un_corpus.jsonl", user_id="alice", batch=64) -> None:
    from linguadocs.retrieval import dense
    dense.init(reset=True)
    items = [json.loads(line) for line in open(path, encoding="utf-8")]
    for j in range(0, len(items), batch):
        dense.index(user_id, items[j:j + batch])
```

Au jour 7, garde `langs=("fr", "en")`. Au palier B (semaine 5), ajoute `"ar"`.

### B8 — `eval/run_retrieval.py`

```python
import collections
import json
import random
import sys

from linguadocs.retrieval.dense import search


def bootstrap_ci(values: list[float], n: int = 1000) -> tuple[float, float]:
    means = sorted(sum(random.choices(values, k=len(values))) / len(values) for _ in range(n))
    return means[int(0.025 * n)], means[int(0.975 * n)]


def evaluate(path: str, k: int = 5) -> list[dict]:
    per = collections.defaultdict(lambda: {"hit": [], "rr": []})
    for line in open(path, encoding="utf-8"):
        q = json.loads(line)
        keys = [h.payload["chunk_key"] for h in search(q["user_id"], q["query"], k)]
        rel = set(q["relevant"])
        rank = next((i for i, key in enumerate(keys, 1) if key in rel), None)
        d = per[(q["lang"], q.get("target_lang", ""))]
        d["hit"].append(1.0 if rank else 0.0)
        d["rr"].append(1 / rank if rank else 0.0)
    rows = []
    for (lang, tgt), d in sorted(per.items()):
        n = len(d["hit"])
        lo, hi = bootstrap_ci(d["hit"])
        rows.append({"query_lang": lang, "target_lang": tgt, "n": n,
                     f"recall@{k}": round(sum(d["hit"]) / n, 3),
                     "ci95": (round(lo, 3), round(hi, 3)),
                     "mrr": round(sum(d["rr"]) / n, 3)})
    return rows


if __name__ == "__main__":
    for row in evaluate(sys.argv[1]):
        print(row)
```

Lance-le avec `uv run python eval/run_retrieval.py eval/datasets/un_pairs.jsonl`. Sauvegarde ensuite le résultat dans `docs/results/` avec la date et la configuration testée.

---

## Dernier rappel : tes premiers gestes

1. **Aujourd'hui :** jour 1 (installer Git, Docker, uv, Ollama).
2. **Demain :** jour 2 (dépôt + Qdrant).
3. **Après-demain :** jour 3 (les trois benchmarks). Envoie-moi tes chiffres et on choisit les modèles ensemble.
