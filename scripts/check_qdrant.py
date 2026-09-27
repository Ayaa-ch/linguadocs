from qdrant_client import QdrantClient
client = QdrantClient(url="http://localhost:6333", check_compatibility=False)
try:
    info = client.get_collection("chunks")
    # vectors_count est déprécié, utiliser points_count
    count = getattr(info, "points_count", None)
    if count is None:
        count = info.vectors_count if hasattr(info, "vectors_count") else "unknown"
    print(f"Nombre de vecteurs : {count}")
    print(f"Status: {info.status}")
    print(f"Vectors config: {info.config.params.vectors}")
    # essai avec l'API moderne
    try:
        print(f"Points count (via info): {info.points_count}")
    except Exception:
        pass
    # via count API
    try:
        cnt = client.count("chunks")
        print(f"Count API: {cnt}")
    except Exception as e:
        print(f"Count API error: {e}")
except Exception as e:
    print(f"Erreur: {e}")
    print("Collection vide ou inexistante")
