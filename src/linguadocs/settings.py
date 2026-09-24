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


settings = Settings()
