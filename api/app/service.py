"""Lo que hace la aplicación, sin saber que existe HTTP.

Este módulo no importa FastAPI. Esa restricción es deliberada: el worker en
segundo plano de la Fase 2 va a llamar run_check() tal cual, sin arrastrar
un framework web para hacerlo.
"""

from __future__ import annotations

import asyncio
from dataclasses import asdict

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from app.checks.grading import grade
from app.checks.probe import probe
from app.models import Check, Domain


async def run_check(session: AsyncSession, domain: Domain) -> Check:
    """Sondea un dominio y añade el resultado a su historial.

    El sondeo bloquea en un socket, así que corre en un hilo. Sin esto un
    handshake lento congelaría el event loop y con él todas las demás
    peticiones: el timeout es de 8 segundos.
    """
    obs = await asyncio.to_thread(probe, domain.hostname, domain.port)
    verdict = grade(obs)

    check = Check(
        domain_id=domain.id,
        score=verdict.score,
        grade=verdict.grade,
        reachable=obs.reachable,
        resolved_ip=obs.resolved_ip,
        handshake_ms=obs.handshake_ms,
        protocol=obs.protocol,
        cipher=obs.cipher,
        cipher_bits=obs.cipher_bits,
        issuer=obs.issuer,
        subject=obs.subject,
        not_before=obs.not_before,
        not_after=obs.not_after,
        findings=[asdict(f) for f in verdict.findings],
        legacy_accepted=obs.legacy_accepted,
        legacy_untestable=obs.legacy_untestable,
        error=obs.error or obs.verify_error,
    )
    session.add(check)
    await session.commit()
    await session.refresh(check)
    return check


async def list_domains(session: AsyncSession) -> list[Domain]:
    """Dominios con su historial cargado.

    selectinload lanza una consulta extra para todos los chequeos, en vez de
    una por dominio. Es la diferencia entre 2 consultas y 21 con 20 dominios,
    y no se nota hasta que ya duele.
    """
    result = await session.execute(
        select(Domain).options(selectinload(Domain.checks)).order_by(Domain.hostname)
    )
    return list(result.scalars().unique())


async def get_domain(session: AsyncSession, domain_id: int) -> Domain | None:
    result = await session.execute(
        select(Domain).options(selectinload(Domain.checks)).where(Domain.id == domain_id)
    )
    return result.scalars().unique().one_or_none()


async def find_domain(session: AsyncSession, hostname: str, port: int) -> Domain | None:
    result = await session.execute(
        select(Domain).where(Domain.hostname == hostname, Domain.port == port)
    )
    return result.scalars().one_or_none()


async def create_domain(
    session: AsyncSession, hostname: str, port: int, label: str | None
) -> Domain:
    domain = Domain(hostname=hostname, port=port, label=label)
    session.add(domain)
    await session.commit()
    await session.refresh(domain)
    return domain
