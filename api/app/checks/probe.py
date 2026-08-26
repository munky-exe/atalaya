"""Sondeo TLS: la única parte que toca la red.

Estrategia de doble intento. Primero se conecta verificando, como lo haría
un navegador. Si la verificación falla, reconecta con verificación apagada
únicamente para leer el certificado, y guarda aparte la razón del fallo.

Nunca se confía en ese certificado. Solo se lee. Sin este segundo intento,
el caso más importante de reportar —un certificado vencido— produciría el
reporte más vacío.
"""

from __future__ import annotations

import socket
import ssl
from datetime import UTC, datetime

from cryptography import x509
from cryptography.x509.oid import ExtensionOID

from app.checks.models import Observation

DEFAULT_TIMEOUT = 8.0


def probe(hostname: str, port: int = 443, timeout: float = DEFAULT_TIMEOUT) -> Observation:
    obs = Observation(hostname=hostname, port=port)
    started = datetime.now(UTC)

    try:
        _handshake(obs, ssl.create_default_context(), timeout)
    except ssl.SSLError as exc:
        # Falló la verificación, pero el servidor está vivo. Segundo intento.
        obs.verify_error = _readable(exc)
        try:
            _handshake(obs, _lax_context(), timeout)
        except OSError as inner:
            obs.error = f"{type(inner).__name__}: {inner}"
    except OSError as exc:
        # Ni siquiera hubo conexión: DNS, timeout, puerto cerrado.
        obs.error = f"{type(exc).__name__}: {exc}"

    obs.handshake_ms = int((datetime.now(UTC) - started).total_seconds() * 1000)

    # Solo tiene sentido si el servidor responde. Añade dos handshakes más.
    if obs.reachable:
        obs.legacy_accepted, obs.legacy_untestable = detect_legacy(hostname, port, timeout / 2)

    return obs


def _lax_context() -> ssl.SSLContext:
    context = ssl.create_default_context()
    context.check_hostname = False
    context.verify_mode = ssl.CERT_NONE
    return context


def _handshake(obs: Observation, context: ssl.SSLContext, timeout: float) -> None:
    """Un handshake. Llena obs con lo que se vea. Deja escapar las excepciones."""
    with socket.create_connection((obs.hostname, obs.port), timeout=timeout) as raw:
        obs.reachable = True
        obs.resolved_ip = raw.getpeername()[0]

        with context.wrap_socket(raw, server_hostname=obs.hostname) as tls:
            obs.protocol = tls.version()
            cipher = tls.cipher()
            if cipher:
                obs.cipher, _, obs.cipher_bits = cipher

            # binary_form funciona en ambos contextos; getpeercert() sin
            # argumentos devuelve {} cuando no hubo verificación.
            der = tls.getpeercert(binary_form=True)
            if der:
                _read_certificate(obs, der)


def _read_certificate(obs: Observation, der: bytes) -> None:
    """De bytes DER a campos. Una sola ruta de extracción para ambos intentos."""
    cert = x509.load_der_x509_certificate(der)

    obs.issuer = cert.issuer.rfc4514_string()
    obs.subject = cert.subject.rfc4514_string()
    obs.not_before = cert.not_valid_before_utc
    obs.not_after = cert.not_valid_after_utc

    try:
        san = cert.extensions.get_extension_for_oid(ExtensionOID.SUBJECT_ALTERNATIVE_NAME)
        obs.san = san.value.get_values_for_type(x509.DNSName)
    except x509.ExtensionNotFound:
        obs.san = []


def _readable(exc: ssl.SSLError) -> str:
    """El mensaje útil, sin el ruido de '(_ssl.c:1010)'."""
    message = getattr(exc, "verify_message", None)
    return message or str(getattr(exc, "reason", None) or exc)


# Protocolos que probamos por separado. OpenSSL moderno los rechaza en el
# contexto por defecto, así que negociar TLS 1.3 no prueba que el servidor
# haya dejado de ofrecer TLS 1.0. Un navegador viejo sí los aceptaría, y
# eso es justo lo que un monitor de postura debe reportar.
LEGACY_PROTOCOLS = {
    "TLSv1": ssl.TLSVersion.TLSv1,
    "TLSv1.1": ssl.TLSVersion.TLSv1_1,
}


def detect_legacy(
    hostname: str, port: int = 443, timeout: float = 4.0
) -> tuple[list[str], list[str]]:
    """Protocolos obsoletos que el servidor acepta.

    Devuelve (aceptados, no_comprobables). El segundo importa: si este build
    de OpenSSL no soporta TLS 1.0, no podemos afirmar que el servidor lo
    rechace. "No lo comprobamos" y "está limpio" son cosas distintas, y
    confundirlas da falsa tranquilidad.
    """
    accepted: list[str] = []
    untestable: list[str] = []

    for name, version in LEGACY_PROTOCOLS.items():
        context = ssl.create_default_context()
        context.check_hostname = False
        context.verify_mode = ssl.CERT_NONE

        try:
            # SECLEVEL=0 baja el filtro que impide siquiera intentarlo.
            context.set_ciphers("ALL:@SECLEVEL=0")
            context.minimum_version = version
            context.maximum_version = version
        except (ValueError, ssl.SSLError):
            # Este OpenSSL no compila ese protocolo. No podemos opinar.
            untestable.append(name)
            continue

        try:
            with (
                socket.create_connection((hostname, port), timeout=timeout) as raw,
                context.wrap_socket(raw, server_hostname=hostname),
            ):
                accepted.append(name)
        except ssl.SSLError:
            # El servidor lo rechazó. Es el resultado que queremos.
            continue
        except OSError:
            # Red caída a media prueba: no es evidencia de nada.
            untestable.append(name)

    return accepted, untestable
