"""Sondeo TLS: la unica parte que toca la red.

Estrategia de doble intento. Primero se conecta verificando, como lo haria
un navegador. Si la verificacion falla, reconecta con verificacion apagada
unicamente para leer el certificado, y guarda aparte la razon del fallo.

Nunca se confia en ese certificado. Solo se lee. Sin este segundo intento,
el caso mas importante de reportar -un certificado vencido- produciria el
reporte mas vacio.
"""

from __future__ import annotations

import socket
import ssl
from datetime import UTC, datetime

from cryptography import x509
from cryptography.x509.oid import ExtensionOID

from app.checks.models import Observation

# Python en macOS no usa el llavero del sistema, sino el paquete de raices
# de OpenSSL. Eso hace que sitios perfectamente validos -gob.mx, unam.mx-
# aparezcan con la cadena rota. truststore delega la verificacion al almacen
# nativo del sistema operativo, que es lo que hace un navegador.
try:
    import truststore

    truststore.inject_into_ssl()
except ImportError:  # pragma: no cover
    pass


DEFAULT_TIMEOUT = 8.0

# Protocolos que probamos por separado. OpenSSL moderno los rechaza en el
# contexto por defecto, asi que negociar TLS 1.3 no prueba que el servidor
# haya dejado de ofrecer TLS 1.0. Un navegador viejo si los aceptaria, y
# eso es justo lo que un monitor de postura debe reportar.
LEGACY_PROTOCOLS = {
    "TLSv1": ssl.TLSVersion.TLSv1,
    "TLSv1.1": ssl.TLSVersion.TLSv1_1,
}

# Segundos del sondeo principal a partir de los cuales ya no vale la pena
# gastar dos handshakes mas en la deteccion de protocolos obsoletos.
LEGACY_BUDGET = 6.0


def probe(  # pragma: no cover - E/S de red, se ejercita a mano no en CI
    hostname: str, port: int = 443, timeout: float = DEFAULT_TIMEOUT
) -> Observation:
    obs = Observation(hostname=hostname, port=port)
    started = datetime.now(UTC)

    try:
        _handshake(obs, ssl.create_default_context(), timeout)
    except ssl.SSLError as exc:
        # Fallo la verificacion, pero el servidor esta vivo. Segundo intento.
        obs.verify_error = _readable(exc)
        try:
            _handshake(obs, _lax_context(), timeout)
        except OSError as inner:
            obs.error = f"{type(inner).__name__}: {inner}"
    except OSError as exc:
        # Ni siquiera hubo conexion: DNS, timeout, puerto cerrado.
        obs.error = f"{type(exc).__name__}: {exc}"

    # Solo tiene sentido si el servidor responde. Anade dos handshakes mas,
    # asi que se omite cuando el sondeo principal ya consumio demasiado
    # tiempo: un servidor lento no merece 5 segundos extra de espera del
    # usuario, y "no comprobado" es una respuesta honesta.
        elapsed = (datetime.now(UTC) - started).total_seconds()
    if obs.reachable and elapsed < LEGACY_BUDGET:
        obs.legacy_accepted, obs.legacy_untestable = detect_legacy(hostname, port, 2.5)
    elif obs.reachable:
        # No es que OpenSSL no pueda: es que nos rendimos por tiempo.
        obs.legacy_skipped = True


def _lax_context() -> ssl.SSLContext:
    context = ssl.create_default_context()
    context.check_hostname = False
    context.verify_mode = ssl.CERT_NONE
    return context


def _handshake(  # pragma: no cover - E/S de red
    obs: Observation, context: ssl.SSLContext, timeout: float
) -> None:
    """Un handshake. Llena obs con lo que se vea. Deja escapar las excepciones."""
    with socket.create_connection((obs.hostname, obs.port), timeout=timeout) as raw:
        obs.reachable = True
        obs.resolved_ip = raw.getpeername()[0]
        # create_connection solo limita el establecimiento TCP. Sin esto un
        # servidor que acepta y luego calla deja el handshake colgado sin
        # limite: unam.mx tardo 64 segundos antes de este ajuste.
        raw.settimeout(timeout / 3)

        with context.wrap_socket(raw, server_hostname=obs.hostname) as tls:
            obs.protocol = tls.version()
            cipher = tls.cipher()
            if cipher:
                obs.cipher, _, obs.cipher_bits = cipher

            # binary_form funciona en ambos contextos; getpeercert() sin
            # argumentos devuelve {} cuando no hubo verificacion.
            der = tls.getpeercert(binary_form=True)
            if der:
                _read_certificate(obs, der)


def _read_certificate(obs: Observation, der: bytes) -> None:  # pragma: no cover
    """De bytes DER a campos. Una sola ruta de extraccion para ambos intentos."""
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
    """El mensaje util, sin el ruido de '(_ssl.c:1010)'."""
    message = getattr(exc, "verify_message", None)
    return message or str(getattr(exc, "reason", None) or exc)


def detect_legacy(  # pragma: no cover - E/S de red
    hostname: str, port: int = 443, timeout: float = 2.5
) -> tuple[list[str], list[str]]:
    """Protocolos obsoletos que el servidor acepta.

    Devuelve (aceptados, no_comprobables). El segundo importa: si este build
    de OpenSSL no soporta TLS 1.0, no podemos afirmar que el servidor lo
    rechace. "No lo comprobamos" y "esta limpio" son cosas distintas, y
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
            # El servidor lo rechazo. Es el resultado que queremos.
            continue
        except OSError:
            # Red caida a media prueba: no es evidencia de nada.
            untestable.append(name)

    return accepted, untestable