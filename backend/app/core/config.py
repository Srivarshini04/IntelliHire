from functools import lru_cache

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
    openai_api_key: str = ""
    llm_api_base: str = "https://api.openai.com/v1"
    llm_model: str = "gpt-4o-mini"
    use_llm_linkedin: bool = True
    linkdapi_api_key: str = ""
    linkdapi_api_base: str = "https://linkdapi.com/api/v1"
    linkedin_data_provider: str = "auto"
    linkedin_session_cookie: str = ""

    model_config = {"env_file": ".env", "extra": "ignore"}


@lru_cache
def get_settings() -> Settings:
    return Settings()


settings = get_settings()
