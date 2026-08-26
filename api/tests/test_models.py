"""Pruebas del esquema.

No prueban SQLAlchemy —eso ya está probado por sus autores— sino nuestras
decisiones de modelado: las restricciones, el borrado en cascada, el orden
del historial. Son las reglas que decidimos nosotros.
"""

from datetime import datetime, timedelta, timezone

import pytest
from sqlalchemy import func, select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import selectinload

from app.models import Check, Domain

NOW = datetime.now(timezone.utc)


def make_check(domain_id: int, grade: str = "A", score: int = 100, **extra) -> Check:
    return Check(domain_id=domain_id, grade=grade, score=score, reachable=True, **extra)


async def test_se_guarda_y_se_lee_un_dominio(session):
    session.add(Domain(hostname="github.com", port=443, label="GitHub"))
    await session.commit()

    found = (await session.execute(select(Domain))).scalar_one()
    assert found.hostname == "github.com"
    assert found.created_at is not None


async def test_no_se_puede_repetir_host_y_puerto(session):
    """La restricción vive en la base: ninguna ruta de escritura la evade."""
    session.add(Domain(hostname="github.com", port=443))
    await session.commit()

    session.add(Domain(hostname="github.com", port=443))
    with pytest.raises(IntegrityError):
        await session.commit()


async def test_el_mismo_host_en_otro_puerto_si_se_permite(session):
    session.add_all([
        Domain(hostname="github.com", port=443),
        Domain(hostname="github.com", port=8443),
    ])
    await session.commit()

    total = (await session.execute(select(func.count(Domain.id)))).scalar_one()
    assert total == 2


async def test_los_chequeos_se_acumulan_no_se_reemplazan(session):
    """El corazón del diseño: la tabla es de solo anexado."""
    domain = Domain(hostname="github.com")
    session.add(domain)
    await session.commit()

    session.add_all([
        make_check(domain.id, "A", 100, observed_at=NOW - timedelta(days=2)),
        make_check(domain.id, "B", 88, observed_at=NOW - timedelta(days=1)),
        make_check(domain.id, "F", 0, observed_at=NOW),
    ])
    await session.commit()

    total = (await session.execute(select(func.count(Check.id)))).scalar_one()
    assert total == 3


async def test_el_historial_llega_del_mas_reciente_al_mas_viejo(session):
    domain = Domain(hostname="github.com")
    session.add(domain)
    await session.commit()

    session.add_all([
        make_check(domain.id, "A", 100, observed_at=NOW - timedelta(days=2)),
        make_check(domain.id, "F", 0, observed_at=NOW),
        make_check(domain.id, "B", 88, observed_at=NOW - timedelta(days=1)),
    ])
    await session.commit()

    # selectinload trae la relación en la misma operación. Sin él, tocar
    # domain.checks dispara una carga perezosa que en async revienta con
    # MissingGreenlet: no se puede hacer E/S implícita fuera del await.
    # También es lo que evita el N+1 cuando listemos muchos dominios.
    loaded = (
        await session.execute(
            select(Domain).options(selectinload(Domain.checks)).where(Domain.id == domain.id)
        )
    ).scalar_one()

    assert [c.grade for c in loaded.checks] == ["F", "B", "A"]


async def test_borrar_un_dominio_borra_su_historial(session):
    """Sin la cascada quedarían chequeos huérfanos apuntando a la nada."""
    domain = Domain(hostname="github.com")
    session.add(domain)
    await session.commit()

    session.add(make_check(domain.id))
    await session.commit()

    await session.delete(domain)
    await session.commit()

    assert (await session.execute(select(func.count(Check.id)))).scalar_one() == 0


async def test_los_hallazgos_sobreviven_el_viaje_a_json(session):
    """JSON es cómodo, pero hay que comprobar que vuelve como se guardó."""
    domain = Domain(hostname="github.com")
    session.add(domain)
    await session.commit()

    hallazgos = [
        {"code": "cert_expired", "severity": "critical", "title": "Vencido", "detail": "x"},
        {"code": "protocol_dated", "severity": "low", "title": "Sin TLS 1.3", "detail": "y"},
    ]
    session.add(make_check(domain.id, "F", 0, findings=hallazgos))
    await session.commit()

    check = (await session.execute(select(Check))).scalar_one()
    assert len(check.findings) == 2
    assert check.findings[0]["code"] == "cert_expired"


async def test_el_instante_de_vencimiento_se_conserva(session):
    """El instante sobrevive el viaje de ida y vuelta.

    Ojo con el alcance: SQLite no tiene tipo con zona horaria y devuelve
    datetimes ingenuos. Que la zona se conserve depende de Postgres, y se
    verificó a mano contra la base real. Comparamos aquí solo lo que SQLite
    sí puede garantizar; una prueba que finge verificar más de lo que
    verifica es peor que no tenerla.
    """
    domain = Domain(hostname="github.com")
    session.add(domain)
    await session.commit()

    vence = datetime(2026, 9, 30, 23, 59, 59, tzinfo=timezone.utc)
    session.add(make_check(domain.id, not_after=vence))
    await session.commit()

    check = (await session.execute(select(Check))).scalar_one()
    guardado = check.not_after
    if guardado.tzinfo is None:
        guardado = guardado.replace(tzinfo=timezone.utc)

    assert guardado == vence
