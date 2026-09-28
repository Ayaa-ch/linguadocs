import uuid
from typing import List

from qdrant_client import QdrantClient, models
from sentence_transformers import SentenceTransformer

try:
    from sentence_transformers import CrossEncoder
except ImportError:
    CrossEncoder = None  # type: ignore

from linguadocs.settings import settings

client = QdrantClient(url=settings.qdrant_url, check_compatibility=False)
model = SentenceTransformer("intfloat/multilingual-e5-small")
COL, DIM = "chunks", 384

# fastembed sparse BM25
_sparse_model = None
SPARSE_NAME = "bm25"


def _get_sparse_model():
    global _sparse_model
    if _sparse_model is None:
        try:
            from fastembed import SparseTextEmbedding

            # Qdrant/bm25 est le modèle BM25 léger
            _sparse_model = SparseTextEmbedding(model_name="Qdrant/bm25")
        except Exception as e:
            # fallback si fastembed non dispo
            print(f"fastembed BM25 non disponible: {e}, fallback hash")
            _sparse_model = None
    return _sparse_model


def _get_reranker():
    global _reranker
    if "_reranker" not in globals():
        globals()["_reranker"] = None
    if globals().get("_reranker") is None and CrossEncoder is not None:
        try:
            globals()["_reranker"] = CrossEncoder(settings.reranker_model)
        except Exception:
            globals()["_reranker"] = None
    return globals().get("_reranker")


_reranker = None


_sparse_cache: dict[str, models.SparseVector] = {}


def _text_to_sparse(text: str) -> models.SparseVector:
    if text in _sparse_cache:
        return _sparse_cache[text]
    # essayer fastembed d'abord
    try:
        m = _get_sparse_model()
        if m is not None:
            emb = list(m.embed([text]))[0]
            if hasattr(emb, "indices"):
                vec = models.SparseVector(indices=list(emb.indices), values=list(emb.values))
                _sparse_cache[text] = vec
                return vec
    except Exception:
        pass
    # fallback hash
    import hashlib
    from collections import Counter

    tokens = text.lower().split()
    if not tokens:
        vec = models.SparseVector(indices=[], values=[])
        _sparse_cache[text] = vec
        return vec
    counter = Counter(tokens)
    indices = []
    values = []
    for tok, cnt in counter.items():
        h = int(hashlib.md5(tok.encode("utf-8")).hexdigest(), 16) % 30000
        indices.append(h)
        values.append(float(cnt))
    pairs = sorted(zip(indices, values))
    indices, values = zip(*pairs)
    vec = models.SparseVector(indices=list(indices), values=list(values))
    _sparse_cache[text] = vec
    return vec


def init(reset: bool = False) -> None:
    if reset and client.collection_exists(COL):
        client.delete_collection(COL)
    if not client.collection_exists(COL):
        client.create_collection(
            COL,
            vectors_config={"dense": models.VectorParams(size=DIM, distance=models.Distance.COSINE)},
            sparse_vectors_config={SPARSE_NAME: models.SparseVectorParams()},
        )
        client.create_payload_index(COL, field_name="user_id", field_schema=models.PayloadSchemaType.KEYWORD)
        try:
            client.create_payload_index(COL, field_name="doc_id", field_schema=models.PayloadSchemaType.KEYWORD)
        except Exception:
            pass
        return

    # vérifier si la collection a bien les deux configs, sinon recréer
    try:
        info = client.get_collection(COL)
        # vérifier vectors_config contient "dense" et sparse_vectors_config contient "bm25"
        has_dense = False
        has_sparse = False
        try:
            # info.config.params.vectors est soit VectorParams soit dict
            vectors = info.config.params.vectors
            if isinstance(vectors, dict) and "dense" in vectors:
                has_dense = True
            elif hasattr(vectors, "size"):
                # ancien format anonyme
                has_dense = False
        except Exception:
            pass
        try:
            sparse_vectors = info.config.params.sparse_vectors
            if isinstance(sparse_vectors, dict) and SPARSE_NAME in sparse_vectors:
                has_sparse = True
            elif sparse_vectors is not None:
                has_sparse = True
        except Exception:
            pass
        if not (has_dense and has_sparse):
            client.delete_collection(COL)
            client.create_collection(
                COL,
                vectors_config={"dense": models.VectorParams(size=DIM, distance=models.Distance.COSINE)},
                sparse_vectors_config={SPARSE_NAME: models.SparseVectorParams()},
            )
            client.create_payload_index(COL, field_name="user_id", field_schema=models.PayloadSchemaType.KEYWORD)
            try:
                client.create_payload_index(COL, field_name="doc_id", field_schema=models.PayloadSchemaType.KEYWORD)
            except Exception:
                pass
    except Exception:
        pass


def index(user_id: str, items: list[dict]) -> None:
    # items: list de dict avec au moins "text"
    dense_vecs = model.encode([f"passage: {it['text']}" for it in items], normalize_embeddings=True)
    # sparse via fastembed
    sparse_model = _get_sparse_model()
    sparse_vecs = []
    if sparse_model is not None:
        try:
            texts = [it["text"] for it in items]
            # fastembed embed renvoie un itérable
            sparse_vecs = list(sparse_model.embed(texts))
        except Exception:
            sparse_vecs = [None] * len(items)
    else:
        sparse_vecs = [None] * len(items)

    points = []
    for dense_v, sparse_emb, it in zip(dense_vecs, sparse_vecs, items):
        # sparse qdrant
        if sparse_emb is not None and hasattr(sparse_emb, "indices"):
            sparse_vec = models.SparseVector(indices=list(sparse_emb.indices), values=list(sparse_emb.values))
        elif sparse_emb is not None and isinstance(sparse_emb, dict):
            sparse_vec = models.SparseVector(indices=sparse_emb.get("indices", []), values=sparse_emb.get("values", []))
        else:
            sparse_vec = _text_to_sparse(it["text"])

        # Pour Qdrant 1.19 avec vectors_config={"dense": ...} et sparse_vectors_config={"bm25": ...}
        # le PointStruct doit avoir vector={"dense": [...], "bm25": SparseVector}
        # comme indiqué dans la tâche
        points.append(
            models.PointStruct(
                id=str(uuid.uuid4()),
                vector={
                    "dense": dense_v.tolist(),
                    "bm25": sparse_vec,
                },
                payload={"user_id": user_id, **it},
            )
        )
    # upsert
    try:
        client.upsert(COL, points=points)
    except Exception as e:
        # fallback: essayer avec l'ancien format si le nouveau échoue (compatibilité)
        print(f"upsert hybrid failed {e}, fallback dense")
        # fallback dense seul avec l'ancien format
        fallback_points = []
        for dense_v, it in zip(dense_vecs, items):
            fallback_points.append(
                models.PointStruct(
                    id=str(uuid.uuid4()),
                    vector=dense_v.tolist(),
                    payload={"user_id": user_id, **it},
                )
            )
        try:
            client.upsert(COL, points=fallback_points)
        except Exception as e2:
            print(f"fallback also failed {e2}")
            raise


def delete_user_doc(user_id: str | int, doc_id: str | int) -> None:
    flt = models.Filter(
        must=[
            models.FieldCondition(key="user_id", match=models.MatchValue(value=str(user_id))),
            models.FieldCondition(key="doc_id", match=models.MatchValue(value=str(doc_id))),
        ]
    )
    client.delete(collection_name=COL, points_selector=flt, wait=True)


def get_user_chunks(user_id: int | str) -> list[dict]:
    if user_id is None:
        raise TypeError("user_id est obligatoire")
    flt = models.Filter(must=[models.FieldCondition(key="user_id", match=models.MatchValue(value=str(user_id)))])
    records, _ = client.scroll(collection_name=COL, scroll_filter=flt, limit=1000, with_payload=True, with_vectors=False)
    return [r.payload for r in records] if records else []


def search(user_id: str | None, query: str, k: int = 5):
    if user_id is None:
        raise TypeError("user_id est obligatoire - filtre manquant")
    if not query or not query.strip():
        return []
    q = model.encode(f"query: {query}", normalize_embeddings=True).tolist()
    flt = models.Filter(must=[models.FieldCondition(key="user_id", match=models.MatchValue(value=str(user_id)))])
    try:
        # dense avec vecteur nommé "dense"
        results = client.query_points(collection_name=COL, query=q, using="dense", query_filter=flt, limit=k, with_payload=True)
        return results.points
    except Exception as e:
        # fallback pour ancienne collection avec vecteur anonyme
        try:
            results = client.query_points(collection_name=COL, query=q, query_filter=flt, limit=k, with_payload=True)
            return results.points
        except Exception:
            pass
        from qdrant_client.http.exceptions import UnexpectedResponse

        if isinstance(e, UnexpectedResponse) and "404" in str(e):
            import httpx

            flt_dict = flt.model_dump(exclude_none=True) if hasattr(flt, "model_dump") else flt.dict(exclude_none=True)  # type: ignore
            url = f"{client._client.rest_uri}/collections/{COL}/points/search"
            resp = httpx.post(url, json={"vector": {"name": "dense", "vector": q} if False else q, "filter": flt_dict, "limit": k, "with_payload": True}, timeout=10.0)
            # pour vecteur nommé, il faut spécifier `vector_name`
            # on réessaye avec l'ancien format
            try:
                resp = httpx.post(url, json={"vector": q, "filter": flt_dict, "limit": k, "with_payload": True}, timeout=10.0)
                resp.raise_for_status()
                data = resp.json()["result"]

                class _Hit:
                    def __init__(self, d):
                        self.payload = d.get("payload")
                        self.id = d.get("id")
                        self.score = d.get("score")
                        self.vector = d.get("vector")

                return [_Hit(d) for d in data]
            except Exception:
                raise e
        raise


def search_sparse(user_id: str | None, query: str, k: int = 5):
    if user_id is None:
        raise TypeError("user_id est obligatoire - filtre manquant")
    if not query or not query.strip():
        return []
    flt = models.Filter(must=[models.FieldCondition(key="user_id", match=models.MatchValue(value=str(user_id)))])
    sparse_q = _text_to_sparse(query)
    if not sparse_q.indices:
        return []
    try:
        results = client.query_points(
            collection_name=COL,
            query=sparse_q,
            using=SPARSE_NAME,
            query_filter=flt,
            limit=k,
            with_payload=True,
        )
        return results.points
    except Exception:
        # fallback in-memory si Qdrant sparse non dispo
        return search(user_id, query, k)


def search_hybrid(user_id: str | None, query: str, k: int = 5) -> list:
    if user_id is None:
        raise TypeError("user_id est obligatoire - filtre manquant")
    flt = models.Filter(must=[models.FieldCondition(key="user_id", match=models.MatchValue(value=str(user_id)))])
    # Filtre user_id TOUJOURS dans chaque sous-requête
    q_dense = model.encode(f"query: {query}", normalize_embeddings=True).tolist()
    sparse_q = _text_to_sparse(query)

    try:
        from qdrant_client.models import Fusion, FusionQuery, Prefetch

        results = client.query_points(
            collection_name=COL,
            prefetch=[
                Prefetch(query=q_dense, using="dense", filter=flt, limit=20),
                Prefetch(query=sparse_q, using=SPARSE_NAME, filter=flt, limit=20),
            ],
            query=FusionQuery(fusion=Fusion.RRF),
            limit=k,
            with_payload=True,
        )
        # Qdrant RRF retourne déjà fusionné et trié, on garde le score RRF mais on conserve aussi le payload
        # Pour le seuil, on utilise le score dense original si possible, sinon RRF
        return results.points
    except Exception as e:
        # fallback python RRF si Qdrant fusion non supporté
        print(f"hybrid fusion fallback {e}")
        dense_hits = search(user_id, query, k=k * 2)
        sparse_hits = search_sparse(user_id, query, k=k * 2)
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
                orig = getattr(h, "score", 0) or 0
                if orig > scores_orig[key]:
                    scores_orig[key] = float(orig)
        dense_w = settings.hybrid_dense_weight
        sparse_w = settings.hybrid_sparse_weight
        add_hits(dense_hits, weight=dense_w)
        add_hits(sparse_hits, weight=sparse_w)
        sorted_keys = sorted(scores_rrf, key=lambda x: scores_rrf[x], reverse=True)
        res = []
        for key in sorted_keys[:k]:
            class _Hit:
                pass
            h = _Hit()
            h.payload = payload_map[key]
            h.score = scores_orig[key] if scores_orig[key] != 0 else scores_rrf[key]
            h.rrf_score = scores_rrf[key]
            h.id = id_map[key]
            res.append(h)
        return res


def rerank(query: str, results: list, top_n: int = 5) -> list:
    if not results:
        return []
    if top_n <= 0:
        return []
    reranker = _get_reranker()
    if reranker is None:
        try:
            return sorted(results, key=lambda x: getattr(x, "score", 0) or 0, reverse=True)[:top_n]
        except Exception:
            return results[:top_n]
    pairs = []
    for r in results:
        pl = getattr(r, "payload", {}) or {}
        text = pl.get("text") or getattr(r, "text", "") or ""
        pairs.append([query, text])
    try:
        scores = reranker.predict(pairs)
    except Exception:
        return results[:top_n]
    scored = list(zip(results, scores))
    scored.sort(key=lambda x: x[1], reverse=True)
    reranked = []
    for r, s in scored[:top_n]:
        try:
            r.score = float(s)
        except Exception:
            pass
        reranked.append(r)
    return reranked
