from collections.abc import AsyncGenerator

from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine
from sqlalchemy.orm import DeclarativeBase

from app.core.config import settings

engine = create_async_engine(settings.database_url, echo=settings.debug)
async_session = async_sessionmaker(engine, class_=AsyncSession, expire_on_commit=False)


class Base(DeclarativeBase):
    pass


async def get_db() -> AsyncGenerator[AsyncSession, None]:
    async with async_session() as session:
        yield session


def _sync_schema(sync_conn) -> None:
    from sqlalchemy import inspect, text

    inspector = inspect(sync_conn)
    if inspector.has_table("jobs"):
        existing = {col["name"] for col in inspector.get_columns("jobs")}
        if "document_id" not in existing:
            sync_conn.execute(
                text("ALTER TABLE jobs ADD COLUMN document_id UUID")
            )
            sync_conn.execute(
                text("CREATE INDEX IF NOT EXISTS ix_jobs_document_id ON jobs (document_id)")
            )


async def init_db() -> None:
    from app.models import (  # noqa: F401
        candidate,
        document_artifact,
        evidence,
        graph,
        job,
        ledger,
        ranking,
        reasoning,
        scoring,
    )

    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)
        await conn.run_sync(_sync_schema)
