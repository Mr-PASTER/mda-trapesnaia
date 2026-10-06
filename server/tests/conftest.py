import os

import pytest
from httpx import ASGITransport, AsyncClient
from sqlalchemy import text
from sqlalchemy.ext.asyncio import async_sessionmaker, create_async_engine
from sqlalchemy.pool import NullPool

from app.db.base import Base
from app.db.session import get_db
from app.main import app

TEST_DATABASE_URL = os.environ.get(
    "TEST_DATABASE_URL",
    # 127.0.0.1, а не localhost: на Windows localhost сначала резолвится в ::1,
    # и каждое подключение теряет ~2 с. Порт БД опубликован только на IPv4-loopback.
    "postgresql+asyncpg://mda:mda@127.0.0.1:5432/mda_test",
)

engine = create_async_engine(TEST_DATABASE_URL, pool_pre_ping=True, poolclass=NullPool)
TestSession = async_sessionmaker(engine, expire_on_commit=False)


@pytest.fixture(scope="session", autouse=True)
async def _create_schema():
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)
    yield
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.drop_all)
    await engine.dispose()


@pytest.fixture(autouse=True)
async def _reset_data():
    # Фикстура operator коммитит строки, поэтому после каждого теста очищаем БД,
    # иначе повторная вставка конфликтует по уникальным ключам.
    yield
    tables = ", ".join(table.name for table in Base.metadata.sorted_tables)
    async with engine.begin() as conn:
        await conn.execute(text(f"TRUNCATE TABLE {tables} RESTART IDENTITY CASCADE"))


@pytest.fixture
async def db_session():
    async with TestSession() as session:
        yield session
        await session.rollback()


@pytest.fixture
async def client():
    # Приложение ходит в БД через get_db (SessionLocal из app.db.session).
    # Переопределяем зависимость на тестовую NullPool-сессию, чтобы HTTP-клиент
    # работал с той же тестовой БД, что и db_session, и не переиспользовал
    # соединения между разными event loop'ами.
    async def _override_get_db():
        async with TestSession() as session:
            yield session

    app.dependency_overrides[get_db] = _override_get_db
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as c:
        yield c
    app.dependency_overrides.pop(get_db, None)
