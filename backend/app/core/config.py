from pydantic_settings import BaseSettings


class Settings(BaseSettings):
    app_name: str = "DELULU API"
    debug: bool = True
    database_url: str = "postgresql+asyncpg://delulu:delulu@localhost:5432/delulu"
    database_url_sync: str = "postgresql://delulu:delulu@localhost:5432/delulu"
    redis_url: str = "redis://localhost:6379/0"
    qdrant_url: str = "http://localhost:6333"
    gemini_api_key: str = ""
    upload_dir: str = "./uploads"
    cors_origins: list[str] = ["http://localhost:3000"]

    model_config = {"env_file": ".env", "extra": "ignore"}


settings = Settings()
