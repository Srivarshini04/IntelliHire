from collections.abc import Generator

from sqlalchemy import create_engine, inspect, text
from sqlalchemy.orm import DeclarativeBase, Session, sessionmaker

from app.core.config import settings

GITHUB_INTEL_DB = settings.github_intel_db_url


class Base(DeclarativeBase):
    pass


connect_args = {"check_same_thread": False} if GITHUB_INTEL_DB.startswith("sqlite") else {}
engine = create_engine(GITHUB_INTEL_DB, connect_args=connect_args)
SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)


def _sync_columns() -> None:
    from app.github_intel import models  # noqa: F401

    inspector = inspect(engine)
    if not inspector.has_table("gh_repository_analyses"):
        return

    existing = {col["name"] for col in inspector.get_columns("gh_repository_analyses")}
    with engine.begin() as conn:
        if "features_json" not in existing:
            conn.execute(
                text("ALTER TABLE gh_repository_analyses ADD COLUMN features_json TEXT DEFAULT '{}'")
            )


def init_github_intel_db() -> None:
    from app.github_intel import models  # noqa: F401

    Base.metadata.create_all(bind=engine)
    if GITHUB_INTEL_DB.startswith("sqlite"):
        _sync_columns()

    db = SessionLocal()
    try:
        from app.github_intel.seed import seed_capability_graph

        seed_capability_graph(db)
    finally:
        db.close()


def get_github_intel_db() -> Generator[Session, None, None]:
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()
