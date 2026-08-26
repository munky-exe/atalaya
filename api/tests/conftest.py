"""Configuración compartida de pruebas.

Una base SQLite en memoria por prueba. Es SQL real, no un simulacro, pero
arranca vacía y desaparece al terminar. Cada prueba queda aislada sin que
nadie tenga que limpiar nada.
"""

import pytest_asyncio
from sqlalchemy.ext.asyncio import async_sessionmaker, create_async_engine

from app.models import Base


@pytest_asyncio.fixture
async def session():
    engine = create_async_engine("sqlite+aiosqlite:///:memory:")

    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)

    maker = async_sessionmaker(engine, expire_on_commit=False)
    async with maker() as s:
        yield s

    await engine.dispose()
