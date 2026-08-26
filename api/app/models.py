"""Esquema de la base de datos.

Dos tablas, una relación:

  domains  — qué vigilamos
  checks   — qué vimos, una fila por sondeo, para siempre

`checks` es de solo anexado: nada actualiza un chequeo después de escribirlo.
Se paga en espacio y se cobra en poder responder "¿desde cuándo está así?",
que es la pregunta que de verdad importa cuando algo se rompe.
"""

from __future__ import annotations

from datetime import datetime

from sqlalchemy import (
    JSON,
    DateTime,
    ForeignKey,
    Index,
    Integer,
    String,
    UniqueConstraint,
    func,
)
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column, relationship


class Base(DeclarativeBase):
    pass


class Domain(Base):
    __tablename__ = "domains"
    # Un mismo host puede vigilarse en dos puertos distintos, pero no dos
    # veces en el mismo. La restricción vive en la base, no solo en el código:
    # así ninguna ruta de escritura puede saltársela.
    __table_args__ = (UniqueConstraint("hostname", "port", name="uq_domain_host_port"),)

    id: Mapped[int] = mapped_column(primary_key=True)
    hostname: Mapped[str] = mapped_column(String(253), index=True)
    port: Mapped[int] = mapped_column(Integer, default=443)
    label: Mapped[str | None] = mapped_column(String(120), nullable=True)

    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now()
    )

    checks: Mapped[list["Check"]] = relationship(
        back_populates="domain",
        cascade="all, delete-orphan",
        order_by="Check.observed_at.desc()",
    )


class Check(Base):
    __tablename__ = "checks"
    # El índice compuesto sostiene la consulta que más vamos a hacer:
    # "los chequeos de este dominio, más recientes primero".
    __table_args__ = (Index("ix_checks_domain_observed", "domain_id", "observed_at"),)

    id: Mapped[int] = mapped_column(primary_key=True)
    domain_id: Mapped[int] = mapped_column(
        ForeignKey("domains.id", ondelete="CASCADE"), index=True
    )
    observed_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), index=True
    )

    score: Mapped[int] = mapped_column(Integer)
    grade: Mapped[str] = mapped_column(String(1))

    reachable: Mapped[bool] = mapped_column(default=False)
    resolved_ip: Mapped[str | None] = mapped_column(String(45), nullable=True)
    handshake_ms: Mapped[int | None] = mapped_column(Integer, nullable=True)

    protocol: Mapped[str | None] = mapped_column(String(16), nullable=True)
    cipher: Mapped[str | None] = mapped_column(String(120), nullable=True)
    cipher_bits: Mapped[int | None] = mapped_column(Integer, nullable=True)

    issuer: Mapped[str | None] = mapped_column(String(400), nullable=True)
    subject: Mapped[str | None] = mapped_column(String(400), nullable=True)
    not_before: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    not_after: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)

    # Los hallazgos se leen siempre completos junto con su chequeo y nunca se
    # consultan por separado. Normalizarlos sería un JOIN extra en cada lectura
    # para resolver un problema que no tenemos.
    findings: Mapped[list] = mapped_column(JSON, default=list)
    legacy_accepted: Mapped[list] = mapped_column(JSON, default=list)
    legacy_untestable: Mapped[list] = mapped_column(JSON, default=list)

    error: Mapped[str | None] = mapped_column(String(400), nullable=True)

    domain: Mapped[Domain] = relationship(back_populates="checks")
