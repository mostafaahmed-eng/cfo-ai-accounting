import os
import socket
import pytest
from httpx import AsyncClient, ASGITransport
from sqlalchemy.ext.asyncio import AsyncSession, create_async_engine
from sqlalchemy import pool
from app.database import Base, get_db
from app.main import app

TEST_DATABASE_URL = os.environ.get(
    "TEST_DATABASE_URL",
    "postgresql+asyncpg://postgres:postgres@localhost:5432/cfo_manager_test",
)

_pg_available = False
try:
    import urllib.parse

    parsed = urllib.parse.urlparse(TEST_DATABASE_URL)
    _pg_host = parsed.hostname or "localhost"
    _pg_port = parsed.port or 5432
    _s = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
    _s.settimeout(2)
    _pg_available = _s.connect_ex((_pg_host, _pg_port)) == 0
    _s.close()
except Exception:
    pass

requires_pg = pytest.mark.skipif(
    not _pg_available,
    reason="PostgreSQL not available — skipping DB-dependent tests",
)


@pytest.fixture(scope="session")
async def _engine():
    if not _pg_available:
        pytest.skip("PostgreSQL not available")

    root_url = TEST_DATABASE_URL.rsplit("/", 1)[0]
    test_db_name = TEST_DATABASE_URL.rsplit("/", 1)[1]

    try:
        import asyncpg

        root_pg_url = root_url.replace("+asyncpg", "")
        conn = await asyncpg.connect(root_pg_url)
        row = await conn.fetchrow(
            "SELECT 1 FROM pg_database WHERE datname = $1", test_db_name
        )
        if not row:
            await conn.execute(f'CREATE DATABASE "{test_db_name}"')
        await conn.close()
    except Exception:
        pytest.skip("Cannot create test database")

    engine = create_async_engine(TEST_DATABASE_URL, echo=False, poolclass=pool.NullPool)
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)
    yield engine
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.drop_all)
    await engine.dispose()


@pytest.fixture(scope="function")
async def db_session(_engine):
    async with _engine.connect() as conn:
        txn = await conn.begin()
        session = AsyncSession(bind=conn, expire_on_commit=False)
        try:
            yield session
        finally:
            await txn.rollback()
            await session.close()


@pytest.fixture
async def client(db_session):
    async def override_get_db():
        yield db_session

    app.dependency_overrides[get_db] = override_get_db
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as ac:
        yield ac
    app.dependency_overrides.clear()
