"""Superficie HTTP.

Las funciones aquí son delgadas a propósito: leen la petición, llaman a
service.py y serializan la respuesta. Toda la lógica vive en la capa de
servicio, que no sabe que HTTP existe.
"""

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.ext.asyncio import AsyncSession

from app import service
from app.db import get_session
from app.schemas import CheckOut, DomainCreate, DomainOut

router = APIRouter(prefix="/api/domains", tags=["dominios"])


def _to_out(domain) -> DomainOut:
    """Adjunta el chequeo más reciente. La relación viene ordenada
    descendente desde el modelo, así que el primero es el último."""
    out = DomainOut.model_validate(domain)
    if domain.checks:
        out.latest = CheckOut.model_validate(domain.checks[0])
    return out


@router.get("", response_model=list[DomainOut])
async def list_domains(session: AsyncSession = Depends(get_session)):
    return [_to_out(d) for d in await service.list_domains(session)]


@router.post("", response_model=DomainOut, status_code=status.HTTP_201_CREATED)
async def add_domain(payload: DomainCreate, session: AsyncSession = Depends(get_session)):
    if await service.find_domain(session, payload.hostname, payload.port) is not None:
        raise HTTPException(
            status.HTTP_409_CONFLICT, f"{payload.hostname} ya está en la lista."
        )

    domain = await service.create_domain(
        session, payload.hostname, payload.port, payload.label
    )

    # Se revisa de inmediato: una tarjeta recién creada nunca aparece vacía.
    await service.run_check(session, domain)

    return _to_out(await service.get_domain(session, domain.id))


@router.post("/{domain_id}/check", response_model=CheckOut)
async def check_now(domain_id: int, session: AsyncSession = Depends(get_session)):
    domain = await service.get_domain(session, domain_id)
    if domain is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Dominio no encontrado.")
    return CheckOut.model_validate(await service.run_check(session, domain))


@router.get("/{domain_id}/checks", response_model=list[CheckOut])
async def history(
    domain_id: int, limit: int = 50, session: AsyncSession = Depends(get_session)
):
    domain = await service.get_domain(session, domain_id)
    if domain is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Dominio no encontrado.")
    return [CheckOut.model_validate(c) for c in domain.checks[:limit]]


@router.delete("/{domain_id}", status_code=status.HTTP_204_NO_CONTENT)
async def remove(domain_id: int, session: AsyncSession = Depends(get_session)):
    domain = await service.get_domain(session, domain_id)
    if domain is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Dominio no encontrado.")
    await session.delete(domain)
    await session.commit()
