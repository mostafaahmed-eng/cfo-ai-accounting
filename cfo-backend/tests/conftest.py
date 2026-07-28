import os
import socket
from datetime import UTC, datetime
from uuid import uuid4

import pytest
from httpx import ASGITransport, AsyncClient
from sqlalchemy import pool
from sqlalchemy.ext.asyncio import AsyncSession, create_async_engine

from app.core.security import hash_password
from app.database import Base, get_db
from app.main import app
from app.models.company import Company, CompanyMember
from app.models.user import User
from app.services.auth import create_access_token

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


@pytest.fixture
async def _setup_company_and_user(db_session):
    user_id = uuid4()
    company_id = uuid4()

    user = User(
        id=user_id,
        email=f"test_{user_id.hex[:8]}@example.com",
        name="Test User",
        password_hash=hash_password("testpass123"),
        language="en",
        timezone="UTC",
        status="active",
    )
    company = Company(
        id=company_id,
        name="Test Company",
        country_code="US",
        base_currency="USD",
        fiscal_year_start=1,
        timezone="UTC",
    )
    member = CompanyMember(
        id=uuid4(),
        company_id=str(company_id),
        user_id=str(user_id),
        role="OWNER",
        status="active",
        joined_at=datetime.now(UTC).strftime("%Y-%m-%dT%H:%M:%SZ"),
    )
    db_session.add_all([user, company, member])
    await db_session.flush()

    token = create_access_token(str(user_id))
    headers = {"Authorization": f"Bearer {token}"}

    return company_id, user_id, headers
