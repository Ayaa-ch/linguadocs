from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", env_file_encoding="utf-8", extra="ignore")

    database_url: str = "postgresql+asyncpg://linguadocs:secret@localhost:5432/linguadocs"
    jwt_secret: str = "change-me-super-secret-dev-key-please-override"
    jwt_algorithm: str = "HS256"
    jwt_expire_hours: int = 24
    qdrant_url: str = "http://localhost:6333"
    data_dir: str = "data/users"
    max_upload_mb: int = 50
    chunk_size: int = 200
    chunk_overlap: int = 40
    refusal_threshold: float = 0.30
    ollama_url: str = "http://localhost:11434/api/generate"
    llm_model: str = "qwen2.5:3b-instruct"
    llm_num_predict: int = 350
    # -1 = Ollama garde le modèle chargé en RAM (jamais déchargé)
    ollama_keep_alive: int = -1
    reranker_model: str = "BAAI/bge-reranker-v2-m3"
    # Nombre de chunks envoyés au LLM après rerank (routes_ask.py).
    reranker_top_n: int = 3
    embedding_model: str = "BAAI/bge-m3"
    embedding_dim: int = 1024
    hybrid_dense_weight: float = 0.7
    hybrid_sparse_weight: float = 0.3
    # Routes tools (résumé/quiz/flashcards/traduction) : mocks.py tant que le LLM n'est pas branché.
    # false => la route répond 501 (place aux futures routes Ollama).
    use_mock_summary: bool = True
    use_mock_quiz: bool = True
    use_mock_flashcards: bool = True
    use_mock_translate: bool = True


settings = Settings()
