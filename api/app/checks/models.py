"""Estructuras de datos del chequeo TLS.

Aqui no hay logica ni red: solo la forma que tienen los datos. Separarlo
permite que las pruebas construyan una Observation a mano, sin conectarse
a nada.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import UTC, datetime


@dataclass
class Observation:
    """Hechos crudos de un handshake. Sin juicios de valor."""

    hostname: str
    port: int = 443

    reachable: bool = False
    resolved_ip: str | None = None
    handshake_ms: int | None = None

    protocol: str | None = None
    cipher: str | None = None
    cipher_bits: int | None = None

    issuer: str | None = None
    subject: str | None = None
    san: list[str] = field(default_factory=list)
    not_before: datetime | None = None
    not_after: datetime | None = None

    # Se llena cuando la verificacion fallo pero el certificado si se pudo
    # leer con el segundo intento. Es el caso de expired.badssl.com.
    verify_error: str | None = None

    # Protocolos obsoletos que el servidor todavia acepta, y aquellos que
    # este build de OpenSSL no pudo comprobar. La distincion es deliberada.
    legacy_accepted: list[str] = field(default_factory=list)
    legacy_untestable: list[str] = field(default_factory=list)

    # Distinto de legacy_untestable: aqui si podiamos comprobar, pero el
    # sondeo principal ya tardo demasiado y no gastamos dos handshakes mas.
    legacy_skipped: bool = False

    # Se llena cuando ni siquiera hubo conexion.
    error: str | None = None

    @property
    def days_remaining(self) -> int | None:
        if self.not_after is None:
            return None
        return (self.not_after - datetime.now(UTC)).days

    @property
    def lifetime_days(self) -> int | None:
        """Ventana completa de vigencia. Es lo que da contexto a los dias
        restantes: 38 dias sobre 89 es normal; sobre 730 seria alarmante."""
        if self.not_after is None or self.not_before is None:
            return None
        return (self.not_after - self.not_before).days
