"""Pruebas de la API.

Sin servidor y sin puerto: httpx habla con la aplicación en memoria. Y sin
Postgres: la dependencia get_session se sustituye por una que apunta a
SQLite, que es exactamente para lo que existe la inyección de dependencias.

Lo único falseado es el sondeo de red. Las pruebas no deben depender de
internet: fallarían por razones ajenas al código, y las pruebas que fallan
sin culpa son las que la gente deja de correr.
"""

from datetime import UTC, datetime, timedelta

import pytest
import pytest_asyncio
from httpx import ASGITransport, AsyncClient
from sqlalchemy.ext.asyncio import async_sessionmaker, create_async_engine

from app.checks.models import Observation
from app.db import get_session
from app.models import Base

NOW = datetime.now(UTC)


def fake_probe(hostname: str, port: int = 443, timeout: float = 8.0) -> Observation:
    """Sondeo determinista. Cada hostname representa un escenario."""
    if hostname == "caido.example":
        return Observation(hostname=hostname, reachable=False, error="DNS falló")

    if hostname == "vencido.example":
        return Observation(
            hostname=hostname,
            reachable=True,
            protocol="TLSv1.3",
            cipher_bits=256,
            not_before=NOW - timedelta(days=400),
            not_after=NOW - timedelta(days=10),
            verify_error="certificate has expired",
        )

    return Observation(
        hostname=hostname,
        reachable=True,
        resolved_ip="10.0.0.1",
        protocol="TLSv1.3",
        cipher="TLS_AES_256_GCM_SHA384",
        cipher_bits=256,
        not_before=NOW - timedelta(days=10),
        not_after=NOW + timedelta(days=80),
    )


@pytest_asyncio.fixture
async def client(monkeypatch):
    # Se parchea donde se usa, no donde se define: service.py hizo
    # "from app.checks.probe import probe", así que su referencia local
    # es la que hay que sustituir.
    monkeypatch.setattr("app.service.probe", fake_probe)

    engine = create_async_engine("sqlite+aiosqlite:///:memory:")
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)
    maker = async_sessionmaker(engine, expire_on_commit=False)

    from app.main import app

    async def override():
        async with maker() as s:
            yield s

    app.dependency_overrides[get_session] = override

    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://t") as ac:
        yield ac

    app.dependency_overrides.clear()
    await engine.dispose()


async def test_la_lista_empieza_vacia(client):
    response = await client.get("/api/domains")
    assert response.status_code == 200
    assert response.json() == []


async def test_agregar_un_dominio_lo_revisa_de_inmediato(client):
    """Una tarjeta recién creada nunca debe aparecer en blanco."""
    response = await client.post("/api/domains", json={"hostname": "github.com"})
    assert response.status_code == 201
    assert response.json()["latest"]["grade"] == "A"


async def test_una_url_completa_se_acepta_y_se_limpia(client):
    response = await client.post(
        "/api/domains", json={"hostname": "https://github.com/munky-exe/atalaya"}
    )
    assert response.status_code == 201
    assert response.json()["hostname"] == "github.com"


async def test_un_dominio_invalido_se_rechaza(client):
    response = await client.post("/api/domains", json={"hostname": "asdf"})
    assert response.status_code == 422


async def test_no_se_puede_agregar_dos_veces(client):
    await client.post("/api/domains", json={"hostname": "github.com"})
    otra = await client.post("/api/domains", json={"hostname": "github.com"})
    assert otra.status_code == 409


async def test_un_dominio_caido_se_guarda_no_se_descarta(client):
    """El fallo es información. Un host que no responde debe quedar
    registrado con su nota, no desaparecer."""
    response = await client.post("/api/domains", json={"hostname": "caido.example"})
    assert response.status_code == 201
    latest = response.json()["latest"]
    assert latest["grade"] == "F"
    assert latest["reachable"] is False


async def test_un_certificado_vencido_reporta_el_detalle(client):
    response = await client.post("/api/domains", json={"hostname": "vencido.example"})
    codes = [f["code"] for f in response.json()["latest"]["findings"]]
    assert "cert_expired" in codes


async def test_revisar_de_nuevo_agrega_al_historial(client):
    """Congela la decisión del esquema: los chequeos se anexan, no se pisan."""
    creado = await client.post("/api/domains", json={"hostname": "github.com"})
    domain_id = creado.json()["id"]

    await client.post(f"/api/domains/{domain_id}/check")
    historial = await client.get(f"/api/domains/{domain_id}/checks")

    assert len(historial.json()) == 2


async def test_borrar_quita_el_dominio(client):
    creado = await client.post("/api/domains", json={"hostname": "github.com"})
    domain_id = creado.json()["id"]

    assert (await client.delete(f"/api/domains/{domain_id}")).status_code == 204
    assert (await client.get("/api/domains")).json() == []


@pytest.mark.parametrize(
    "metodo,ruta",
    [
        ("post", "/api/domains/999/check"),
        ("get", "/api/domains/999/checks"),
        ("delete", "/api/domains/999"),
    ],
)
async def test_un_dominio_inexistente_da_404(client, metodo, ruta):
    response = await getattr(client, metodo)(ruta)
    assert response.status_code == 404
