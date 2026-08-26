"""Motor y sesiones de base de datos.

El engine se construye de forma perezosa, no al importar el módulo. Esa
decisión de tres líneas significa que importar este archivo no exige una
base de datos alcanzable ni siquiera el driver instalado — y es lo que va
a permitir que las pruebas corran contra SQLite en memoria más adelante.
"""

import os
from collections.abc import AsyncGenerator
from functools import lru_cache

from sqlalchemy.ext.asyncio import (
    AsyncEngine,
    AsyncSession,
    async_sessionmaker,
    create_async_engine,
)

DEFAULT_URL = "postgresql+asyncpg://atalaya:atalaya@localhost:5432/atalaya"


def database_url() -> str:
    return os.getenv("DATABASE_URL", DEFAULT_URL)


@lru_cache
def get_engine() -> AsyncEngine:
    return create_async_engine(
        database_url(),
        # Reconecta si Postgres se reinició o la conexión quedó ociosa.
        pool_pre_ping=True,
    )


@lru_cache
def get_sessionmaker() -> async_sessionmaker[AsyncSession]:
    return async_sessionmaker(get_engine(), expire_on_commit=False)


async def get_session() -> AsyncGenerator[AsyncSession, None]:
    async with get_sessionmaker()() as session:
        yield session
