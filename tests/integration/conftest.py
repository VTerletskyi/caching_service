import pytest

from sqlalchemy import text

from caching_svc.database import engine, session_factory
from caching_svc.shared.application.services import PayloadService
from caching_svc.shared.models import BaseModel


@pytest.fixture(scope="session", autouse=True)
async def setup_database():
    async with engine.begin() as conn:
        await conn.run_sync(BaseModel.metadata.drop_all)
        await conn.run_sync(BaseModel.metadata.create_all)
    yield
    await engine.dispose()


@pytest.fixture(autouse=True)
async def clean_tables(setup_database):
    """Every test starts with an empty cache, so call counts are not affected by test order."""
    yield
    tables = ", ".join(table.name for table in BaseModel.metadata.sorted_tables)
    async with engine.begin() as conn:
        await conn.execute(text(f"TRUNCATE {tables}"))


@pytest.fixture
def payload_service(transformer) -> PayloadService:
    return PayloadService(
        session_factory=session_factory, transformer=transformer, max_concurrency=10
    )
