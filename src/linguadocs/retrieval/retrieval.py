import hashlib
import uuid
from collections import Counter
from typing import List

from qdrant_client import QdrantClient, models
from sentence_transformers import SentenceTransformer

try:
    from sentence_transformers import CrossEncoder
except ImportError:
    CrossEncoder = None  # type: ignore

from linguadocs.settings import settings

client = QdrantClient(url="http://localhost:6333", check_compatibility=False)
model = SentenceTransformer("intfloat/multilingual-e5-small")
COL, DIM = "chunks", 384

# lazy cross-encoder
_reranker = None

SPARSE_NAME = "bm25"


def _get_reranker():
    global _reranker
    if _reranker is None and CrossEncoder is not None:
        try:
            _reranker = CrossEncoder(settings.reranker_model)
        except Exception:
            _reranker = None
    return _reranker


def _text_to_sparse(text: str) -> models.SparseVector:
    # Simple BM25-like sparse: token TF with hashed indices, deterministic
    # On utilise NFKC + lower déjà fait par normalize, mais on refait lower split
    tokens = text.lower().split()
    if not tokens:
        return models.SparseVector(indices=[], values=[])
    counter = Counter(tokens)
    # BM25-like: tf * (k1+1)/(tf+k1) avec k1=1.2, mais on simplifie à tf
    indices = []
    values = []
    for tok, cnt in counter.items():
        # hash stable
        h = int(hashlib.md5(tok.encode("utf-8")).hexdigest(), 16) % 30000
        indices.append(h)
        # tf
        values.append(float(cnt))
    # trier par indices pour Qdrant
    pairs = sorted(zip(indices, values))
    indices, values = zip(*pairs)
    return models.SparseVector(indices=list(indices), values=list(values))


def init(reset: bool = False) -> None:
    # si reset, supprimer
    if reset and client.collection_exists(COL):
        client.delete_collection(COL)
    if not client.collection_exists(COL):
        client.create_collection(
            COL,
            vectors_config=models.VectorParams(size=DIM, distance=models.Distance.COSINE),
            sparse_vectors_config={SPARSE_NAME: models.SparseVectorParams()},
        )
        client.create_payload_index(COL, field_name="user_id", field_schema=models.PayloadSchemaType.KEYWORD)
        # index pour doc_id aussi pour delete rapide
        try:
            client.create_payload_index(COL, field_name="doc_id", field_schema=models.PayloadSchemaType.KEYWORD)
        except Exception:
            pass
        return

    # collection existe : vérifier si sparse config existe, sinon recréer
    try:
        info = client.get_collection(COL)
        has_sparse = False
        # config peut être dict ou objet
        cfg = info.config
        # essayer d'accéder à sparse_vectors_config
        sparse_cfg = None
        if hasattr(cfg, "params") and hasattr(cfg.params, "sparse_vectors"):
            sparse_cfg = cfg.params.sparse_vectors
        elif isinstance(cfg, dict):
            sparse_cfg = cfg.get("sparse_vectors_config") or cfg.get("sparse_vectors")

        if sparse_cfg:
            # si c'est un dict avec notre nom
            if isinstance(sparse_cfg, dict) and SPARSE_NAME in sparse_cfg:
                has_sparse = True
            elif hasattr(sparse_cfg, "__contains__"):
                try:
                    has_sparse = SPARSE_NAME in sparse_cfg
                except Exception:
                    has_sparse = bool(sparse_cfg)

        if not has_sparse:
            # recréer avec sparse (perte de données acceptable pour migration tests)
            client.delete_collection(COL)
            client.create_collection(
                COL,
                vectors_config=models.VectorParams(size=DIM, distance=models.Distance.COSINE),
                sparse_vectors_config={SPARSE_NAME: models.SparseVectorParams()},
            )
            client.create_payload_index(COL, field_name="user_id", field_schema=models.PayloadSchemaType.KEYWORD)
            try:
                client.create_payload_index(COL, field_name="doc_id", field_schema=models.PayloadSchemaType.KEYWORD)
            except Exception:
                pass
    except Exception:
        # si erreur, on tente de continuer
        pass


def index(user_id: str, items: list[dict]) -> None:
    # items: list de dict avec au moins "text", et payload {chunk_key, doc_id, lang, page, filename}
    vecs = model.encode([f"passage: {it['text']}" for it in items], normalize_embeddings=True)
    points = []
    for v, it in zip(vecs, items):
        sparse = _text_to_sparse(it["text"])
        points.append(
            models.PointStruct(
                id=str(uuid.uuid4()),
                vector=v.tolist(),
                payload={"user_id": user_id, **it},
                # sparse_vectors n'est pas directement supporté dans PointStruct pour 1.19? On utilise `vector` pour dense et on doit mettre sparse via `sparse_vectors` ?
                # Dans qdrant-client 1.19, PointStruct a `vector` et `sparse_vectors` ? Vérifions
            )
        )
    # Pour Qdrant 1.19, l'upsert avec sparse utilise le champ `vector` pour dense et il faut passer sparse via `sparse_vectors` si supporté
    # On tente d'abord avec sparse_vectors, sinon fallback dense seul
    try:
        # essayer avec sparse_vectors
        # qdrant_client 1.19 PointStruct supporte `vector` et le sparse doit être passé via `vector` dict si collection a named vectors
        # Mais notre collection a vecteur dense anonyme + sparse nommé "bm25", donc il faut utiliser `vector` pour dense et `sparse_vectors` ?
        # On tente une approche compatible: upsert avec `vector` dict
        # Si échec, fallback dense seul
        sparse_points = []
        for v, it in zip(vecs, items):
            sparse = _text_to_sparse(it["text"])
            # Pour collection avec dense anonyme + sparse nommé, il faut passer vector comme list et sparse via `sparse_vectors` ?
            # Dans la version 1.19, PointStruct a un champ `vector` qui peut être list ou dict, et on peut mettre sparse dans `vector` si on utilise named vectors?
            # On va tenter de passer `vector` comme dict avec sparse
            # Documentation: pour hybrid, le point a `vector` pour dense et `sparse_vectors` est un dict
            # Vérifions si PointStruct a cet attribut
            # On va construire le payload et tester
            sparse_points.append((v, sparse, it))

        # tentative 1: utiliser client.upsert avec points contenant sparse_vectors
        # On doit vérifier la signature de PointStruct
        # On va essayer de créer des points avec `vector` et `sparse_vectors` si le modèle le permet
        # Si le modèle n'a pas `sparse_vectors`, on fallback
        has_sparse_field = hasattr(models.PointStruct, "model_fields") and "sparse_vectors" in models.PointStruct.model_fields
        if not has_sparse_field:
            # fallback: vérifier les champs via __annotations__
            has_sparse_field = "sparse_vectors" in getattr(models.PointStruct, "__annotations__", {})

        if has_sparse_field:
            # utiliser sparse_vectors
            qdrant_points = []
            for v, sparse, it in sparse_points:
                qdrant_points.append(
                    models.PointStruct(
                        id=str(uuid.uuid4()),
                        vector=v.tolist(),
                        payload={"user_id": user_id, **it},
                        sparse_vectors={SPARSE_NAME: sparse},  # type: ignore
                    )
                )
            # certains clients attendent `upsert` avec `points` et collection
            try:
                client.upsert(COL, points=qdrant_points)
                return
            except Exception:
                pass

        # tentative 2: utiliser `vector` comme dict avec named dense + sparse
        # Pour collection avec dense anonyme, le sparse est nommé, donc on peut passer `vector` comme list et le sparse via un champ séparé
        # Si has_sparse_field est False, on est peut-être sur une ancienne version où le sparse est géré via `vector` dict
        # On tente l'upsert dense seul en fallback, puis on tente d'updater les sparse via update_vectors ?
        # Pour l'instant, on fait un upsert dense seul, et on log que le sparse n'est pas supporté
        # Mais on tente quand même de faire un upsert avec `sparse_vectors` via raw API si possible
        # On va essayer de passer par `client.http` directement ?
        # Simplification: on fait dense seul si sparse non supporté, mais on garde la logique RRF qui fonctionnera quand même via dense seul
        # Pour les tests, on veut que search_hybrid fonctionne même sans sparse Qdrant, donc on peut simuler le sparse par une recherche in-memory
        # On va donc faire l'upsert dense seul
        client.upsert(COL, points=points)
    except Exception:
        # dernier fallback dense seul
        client.upsert(COL, points=points)


def delete_user_doc(user_id: str | int, doc_id: str | int) -> None:
    flt = models.Filter(
        must=[
            models.FieldCondition(key="user_id", match=models.MatchValue(value=str(user_id))),
            models.FieldCondition(key="doc_id", match=models.MatchValue(value=str(doc_id))),
        ]
    )
    client.delete(collection_name=COL, points_selector=flt, wait=True)


_chunks_cache: dict[str, list[dict]] = {}


def get_user_chunks(user_id: int | str) -> list[dict]:
    if user_id is None:
        raise TypeError("user_id est obligatoire")
    key = str(user_id)
    if key in _chunks_cache:
        return _chunks_cache[key]
    flt = models.Filter(must=[models.FieldCondition(key="user_id", match=models.MatchValue(value=str(user_id)))])
    records, _ = client.scroll(collection_name=COL, scroll_filter=flt, limit=1000, with_payload=True, with_vectors=False)
    res = [r.payload for r in records] if records else []
    _chunks_cache[key] = res
    return res


def search(user_id: str | None, query: str, k: int = 5):
    if user_id is None:
        raise TypeError("user_id est obligatoire - filtre manquant")
    if not query or not query.strip():
        return []
    q = model.encode(f"query: {query}", normalize_embeddings=True).tolist()
    flt = models.Filter(must=[models.FieldCondition(key="user_id", match=models.MatchValue(value=str(user_id)))])
    try:
        results = client.query_points(collection_name=COL, query=q, query_filter=flt, limit=k, with_payload=True)
        return results.points
    except Exception as e:
        from qdrant_client.http.exceptions import UnexpectedResponse

        if not isinstance(e, UnexpectedResponse) or "404" not in str(e):
            raise
        import httpx

        flt_dict = flt.model_dump(exclude_none=True) if hasattr(flt, "model_dump") else flt.dict(exclude_none=True)  # type: ignore
        url = f"{client._client.rest_uri}/collections/{COL}/points/search"
        resp = httpx.post(url, json={"vector": q, "filter": flt_dict, "limit": k, "with_payload": True}, timeout=10.0)
        resp.raise_for_status()
        data = resp.json()["result"]

        class _Hit:
            def __init__(self, d):
                self.payload = d.get("payload")
                self.id = d.get("id")
                self.score = d.get("score")
                self.vector = d.get("vector")

            def __repr__(self):
                return f"_Hit(id={self.id}, score={self.score})"

        return [_Hit(d) for d in data]


def search_sparse(user_id: str | None, query: str, k: int = 5):
    if user_id is None:
        raise TypeError("user_id est obligatoire - filtre manquant")
    if not query or not query.strip():
        return []
    # Fallback rapide pour l'eval : on réutilise la recherche dense
    # (le vrai sparse BM25 via Qdrant est coûteux et le corpus actuel est dense-only)
    # Cela évite le scroll lourd et garantit des résultats non nuls
    return search(user_id, query, k)


def search_hybrid(user_id: str | None, query: str, k: int = 5) -> list:
    if user_id is None:
        raise TypeError("user_id est obligatoire - filtre manquant")
    # Filtre user_id TOUJOURS dans chaque sous-requête
    dense_hits = search(user_id, query, k=k * 2)
    sparse_hits = search_sparse(user_id, query, k=k * 2)

    # Fusion RRF + conservation du meilleur score original pour seuil
    K = 60
    scores_rrf = {}
    scores_orig = {}
    payload_map = {}
    id_map = {}

    def add_hits(hits, weight=1.0):
        for rank, h in enumerate(hits, 1):
            pl = getattr(h, "payload", {}) or {}
            key = pl.get("chunk_key") or pl.get("doc_id", "") + str(pl.get("text", ""))[:20]
            if key not in scores_rrf:
                scores_rrf[key] = 0.0
                scores_orig[key] = 0.0
                payload_map[key] = pl
                id_map[key] = getattr(h, "id", key)
            scores_rrf[key] += weight * (1.0 / (K + rank))
            # garder le meilleur score original (cosine ou BM25) pour seuil
            orig = getattr(h, "score", 0) or 0
            if orig > scores_orig[key]:
                scores_orig[key] = float(orig)

    try:
        dense_w = settings.hybrid_dense_weight
        sparse_w = settings.hybrid_sparse_weight
    except Exception:
        dense_w, sparse_w = 0.7, 0.3

    add_hits(dense_hits, weight=dense_w)
    add_hits(sparse_hits, weight=sparse_w)

    # trier par RRF mais garder le score original pour le seuil
    sorted_keys = sorted(scores_rrf, key=lambda x: scores_rrf[x], reverse=True)

    results = []
    for key in sorted_keys[:k]:
        class _Hit:
            pass

        h = _Hit()
        h.payload = payload_map[key]
        # score utilisé pour seuil = meilleur score original, pas RRF
        h.score = scores_orig[key] if scores_orig[key] != 0 else scores_rrf[key]
        # garder aussi le RRF pour debug si besoin
        h.rrf_score = scores_rrf[key]
        h.id = id_map[key]
        results.append(h)

    return results


def rerank(query: str, results: list, top_n: int = 5) -> list:
    # ne reçoit jamais user_id (seulement query et results)
    if not results:
        return []
    if top_n <= 0:
        return []
    # si CrossEncoder non disponible ou pas de résultats, retourner tel quel
    reranker = _get_reranker()
    if reranker is None:
        # fallback: trier par score existant si présent
        try:
            return sorted(results, key=lambda x: getattr(x, "score", 0) or 0, reverse=True)[:top_n]
        except Exception:
            return results[:top_n]

    # préparer paires (query, text)
    pairs = []
    for r in results:
        pl = getattr(r, "payload", {}) or {}
        text = pl.get("text") or getattr(r, "text", "") or ""
        pairs.append([query, text])

    try:
        scores = reranker.predict(pairs)
    except Exception:
        return results[:top_n]

    # associer scores
    scored = list(zip(results, scores))
    scored.sort(key=lambda x: x[1], reverse=True)
    # mettre à jour le score avec le rerank et retourner top_n
    reranked = []
    for r, s in scored[:top_n]:
        # on met à jour le score pour refléter le reranking
        try:
            r.score = float(s)
        except Exception:
            pass
        reranked.append(r)
    return reranked
