import uuid
from qdrant_client import QdrantClient, models
from sentence_transformers import SentenceTransformer

client = QdrantClient(url="http://localhost:6333", check_compatibility=False)
model = SentenceTransformer("intfloat/multilingual-e5-small")
COL, DIM = "chunks", 384


def init(reset: bool = False) -> None:
    if reset and client.collection_exists(COL):
        client.delete_collection(COL)
    if not client.collection_exists(COL):
        client.create_collection(
            COL, vectors_config=models.VectorParams(
                size=DIM, distance=models.Distance.COSINE))
        client.create_payload_index(
            COL, field_name="user_id",
            field_schema=models.PayloadSchemaType.KEYWORD)


def index(user_id: str, items: list[dict]) -> None:
    vecs = model.encode(
        [f"passage: {it['text']}" for it in items],
        normalize_embeddings=True)
    client.upsert(COL, points=[
        models.PointStruct(
            id=str(uuid.uuid4()),
            vector=v.tolist(),
            payload={"user_id": user_id, **it})
        for v, it in zip(vecs, items)])


def delete_user_doc(user_id: str | int, doc_id: str | int) -> None:
    """Supprime les vecteurs Qdrant d'un document spécifique (filtre user_id ET doc_id)."""
    flt = models.Filter(must=[
        models.FieldCondition(key="user_id", match=models.MatchValue(value=str(user_id))),
        models.FieldCondition(key="doc_id", match=models.MatchValue(value=str(doc_id))),
    ])
    client.delete(collection_name=COL, points_selector=flt, wait=True)


def get_user_chunks(user_id: int | str) -> list[dict]:
    """Retourne tous les chunks d'un utilisateur (pour vérifier l'isolation)."""
    if user_id is None:
        raise TypeError("user_id est obligatoire")
    flt = models.Filter(must=[models.FieldCondition(
        key="user_id", match=models.MatchValue(value=str(user_id)))])
    # scroll avec filtre
    records, _ = client.scroll(
        collection_name=COL,
        scroll_filter=flt,
        limit=1000,
        with_payload=True,
        with_vectors=False,
    )
    return [r.payload for r in records] if records else []


def search(user_id: str | None, query: str, k: int = 5):
    if user_id is None:
        raise TypeError("user_id est obligatoire - filtre manquant")
    q = model.encode(
        f"query: {query}",
        normalize_embeddings=True).tolist()
    flt = models.Filter(must=[models.FieldCondition(
        key="user_id",
        match=models.MatchValue(value=str(user_id)))])
    try:
        results = client.query_points(
            collection_name=COL,
            query=q,
            query_filter=flt,
            limit=k,
            with_payload=True)
        return results.points
    except Exception as e:
        # Fallback for Qdrant server <1.10 (docker image v1.9.0) where
        # POST /collections/{col}/points/query does not exist (404).
        # Use legacy POST /collections/{col}/points/search via raw HTTP.
        from qdrant_client.http.exceptions import UnexpectedResponse
        if not isinstance(e, UnexpectedResponse) or "404" not in str(e):
            raise
        import httpx
        flt_dict = flt.model_dump(exclude_none=True) if hasattr(flt, "model_dump") else flt.dict(exclude_none=True)  # type: ignore
        url = f"{client._client.rest_uri}/collections/{COL}/points/search"
        resp = httpx.post(url, json={
            "vector": q,
            "filter": flt_dict,
            "limit": k,
            "with_payload": True,
        }, timeout=10.0)
        resp.raise_for_status()
        data = resp.json()["result"]
        # Normalize to same shape as query_points().points (ScoredPoint)
        class _Hit:
            def __init__(self, d): self.payload=d.get("payload"); self.id=d.get("id"); self.score=d.get("score"); self.vector=d.get("vector")
            def __repr__(self): return f"_Hit(id={self.id}, score={self.score})"
        return [_Hit(d) for d in data]