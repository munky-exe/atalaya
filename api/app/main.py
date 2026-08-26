"""Punto de entrada de la aplicación."""

import logging
import os
from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from sqlalchemy import text

from app.db import get_engine, get_sessionmaker
from app.models import Base
from app.routers import domains

logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(message)s")

CORS_ORIGINS = os.getenv("CORS_ORIGINS", "http://localhost:5173").split(",")


@asynccontextmanager
async def lifespan(app: FastAPI):
    """Se ejecuta una vez al arrancar y una vez al apagar."""
    # Provisional: en la Fase 2 esto lo hace Alembic.
    async with get_engine().begin() as conn:
        await conn.run_sync(Base.metadata.create_all)
    logging.info("Esquema listo")

    yield

    await get_engine().dispose()


app = FastAPI(
    title="Atalaya",
    description="Vigilancia de la postura TLS de tus dominios.",
    version="0.1.0",
    lifespan=lifespan,
)

# Sin esto el navegador bloquea las peticiones del frontend, que corre en
# otro puerto y por tanto cuenta como otro origen.
app.add_middleware(
    CORSMiddleware,
    allow_origins=[o.strip() for o in CORS_ORIGINS],
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(domains.router)


@app.get("/health", tags=["ops"])
async def health():
    """Toca la base a propósito: un health que solo responde 'ok' sin
    verificar nada miente cuando Postgres está caído."""
    async with get_sessionmaker()() as session:
        await session.execute(text("SELECT 1"))
    return {"status": "ok", "version": app.version}
