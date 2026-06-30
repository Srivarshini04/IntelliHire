from functools import lru_cache

from pydantic_settings import BaseSettings


class Settings(BaseSettings):
    app_name: str = "DELULU API"
    # Safe-by-default for production: drives SQLAlchemy SQL echo (app/core/database.py).
    # Enable in development via DEBUG=true in .env / .env.local.
    debug: bool = False
    database_url: str = "postgresql+asyncpg://delulu:delulu@localhost:5432/delulu"
    database_url_sync: str = "postgresql://delulu:delulu@localhost:5432/delulu"
    redis_url: str = "redis://localhost:6379/0"
    qdrant_url: str = "http://localhost:6333"
    gemini_api_key: str = ""
    gemini_model: str = "gemini-2.0-flash"
    llm_provider: str = "gemini"
    openai_api_key: str = ""
    openai_model: str = "gpt-4o-mini"
    upload_dir: str = "./uploads"
    cors_origins: list[str] = ["http://localhost:3000"]

    # GitHub intelligence (delulu pipeline)
    github_token: str = ""
    github_intel_db_url: str = "sqlite:///./github_intel.db"
    top_n_repos: int = 3
    max_fetch_files: int = 40
    fetch_git_history_for_all: bool = False
    use_tree_api: bool = True
    clone_repos: bool = False
    semantic_matching: bool = False
    github_api_base: str = "https://api.github.com"

    # LLM / LinkedIn (optional)
    llm_api_base: str = "https://api.openai.com/v1"
    llm_model: str = "gpt-4o-mini"
    use_llm_linkedin: bool = True
    linkdapi_api_key: str = ""
    linkdapi_api_base: str = "https://linkdapi.com/api/v1"
    linkedin_data_provider: str = "auto"
    linkedin_session_cookie: str = ""

    # Apify (LinkedIn evidence) — mirrors GitHub token/base settings
    apify_token: str = ""
    apify_api_base: str = "https://api.apify.com/v2"
    apify_linkedin_actor: str = "harvestapi/linkedin-profile-scraper"
    apify_linkedin_input_field: str = "queries"

    # Document intelligence
    pii_policy: str = "mask_external"  # detect_only | mask_external | mask_always
    object_storage_backend: str = "local"  # local | s3 | minio
    object_storage_bucket: str = "delulu-documents"
    object_storage_endpoint: str = ""
    object_storage_access_key: str = ""
    object_storage_secret_key: str = ""

    # .env.local is loaded last so it overrides .env (local secrets / API tokens).
    model_config = {"env_file": (".env", ".env.local"), "extra": "ignore"}


@lru_cache
def get_settings() -> Settings:
    return Settings()


settings = get_settings()
