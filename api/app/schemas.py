"""Formato de entrada y salida de la API.

Separado de models.py a propósito: lo que se guarda y lo que se expone son
contratos distintos, y deben poder cambiar por separado.
"""

from __future__ import annotations

import re
from datetime import datetime

from pydantic import BaseModel, ConfigDict, Field, field_validator

# Un hostname válido: etiquetas alfanuméricas separadas por puntos, sin
# empezar ni terminar en guion, máximo 253 caracteres en total.
HOSTNAME_RE = re.compile(
    r"^(?=.{1,253}$)(?!-)[A-Za-z0-9-]{1,63}(?<!-)(\.(?!-)[A-Za-z0-9-]{1,63}(?<!-))+$"
)


class DomainCreate(BaseModel):
    hostname: str = Field(..., examples=["github.com"])
    port: int = Field(443, ge=1, le=65535)
    label: str | None = Field(None, max_length=120)

    @field_validator("hostname", mode="before")
    @classmethod
    def clean(cls, value: str) -> str:
        """Rescata lo rescatable antes de rechazar.

        La gente pega URLs completas, y tiene razón sobre lo que quiere:
        solo se equivocó de formato. Extraer el host es trabajo que la
        máquina puede hacer en su lugar. Lo que no se puede rescatar sí
        se rechaza, con un mensaje que diga qué se esperaba.
        """
        if not isinstance(value, str):
            raise ValueError("El dominio debe ser texto.")

        cleaned = value.strip().lower()
        cleaned = re.sub(r"^[a-z]+://", "", cleaned)  # esquema
        cleaned = cleaned.split("/")[0]  # ruta
        cleaned = cleaned.split("?")[0]  # query
        cleaned = cleaned.split("@")[-1]  # credenciales
        cleaned = cleaned.split(":")[0]  # puerto

        if not HOSTNAME_RE.match(cleaned):
            raise ValueError(f"'{value}' no es un dominio válido. Ejemplo: github.com")

        return cleaned


class FindingOut(BaseModel):
    code: str
    severity: str
    title: str
    detail: str


class CheckOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    observed_at: datetime
    score: int
    grade: str
    reachable: bool
    resolved_ip: str | None
    handshake_ms: int | None
    protocol: str | None
    cipher: str | None
    cipher_bits: int | None
    issuer: str | None
    subject: str | None
    not_before: datetime | None
    not_after: datetime | None
    findings: list[FindingOut]
    legacy_accepted: list[str]
    legacy_untestable: list[str]
    error: str | None


class DomainOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    hostname: str
    port: int
    label: str | None
    created_at: datetime
    # El más reciente. El historial completo se pide aparte.
    latest: CheckOut | None = None
