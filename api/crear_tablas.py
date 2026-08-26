"""Crea el esquema. Provisional: en la Fase 2 lo reemplaza Alembic."""

import asyncio

from app.db import get_engine
from app.models import Base


async def main():
    engine = get_engine()
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)
    await engine.dispose()
    print("Tablas creadas.")


asyncio.run(main())
