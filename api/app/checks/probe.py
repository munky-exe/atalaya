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
import time
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

    # La deteccion de protocolos obsoletos anade dos handshakes mas, asi que
    # se omite cuando el sondeo principal ya consumio demasiado tiempo: un
    # servidor lento no merece cinco segundos extra de espera del usuario.
    elapsed = (datetime.now(UTC) - started).total_seconds()
    if obs.reachable and elapsed < LEGACY_BUDGET:
        obs.legacy_accepted, obs.legacy_untestable = detect_legacy(hostname, port, 2.5)
    elif obs.reachable:
        # No es que OpenSSL no pueda: es que nos rendimos por tiempo.
        obs.legacy_skipped = True

    obs.handshake_ms = int((datetime.now(UTC) - started).total_seconds() * 1000)
    return obs


def _lax_context() -> ssl.SSLContext:
    context = ssl.create_default_context()
    context.check_hostname = False
    context.verify_mode = ssl.CERT_NONE
    return context


def _handshake(  # pragma: no cover - E/S de red
    obs: Observation, context: ssl.SSLContext, timeout: float
) -> None:
    """Un handshake. Llena obs con lo que se vea. Deja escapar las excepciones."""
    with _connect(obs.hostname, obs.port, timeout) as raw:
        obs.reachable = True
        obs.resolved_ip = raw.getpeername()[0]
        # create_connection solo limita el establecimiento TCP, y settimeout
        # aplica por operacion, no al total: un servidor que responde justo
        # antes de cada limite estira el handshake sin activarlo nunca.
        # unam.mx llegaba a 32 segundos con el timeout completo.
        raw.settimeout(timeout)

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
                _connect(hostname, port, timeout) as raw,
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


def _connect(hostname: str, port: int, budget: float) -> socket.socket:  # pragma: no cover
    """Conecta respetando un presupuesto TOTAL de tiempo.

    socket.create_connection aplica su timeout a CADA direccion resuelta, no
    al conjunto. Un host con cuatro IPs inalcanzables consume timeout x 4:
    unam.mx publica varias IPv6 que esta red no alcanza y tardaba 32 segundos
    con un timeout nominal de 8.
    """
    deadline = time.monotonic() + budget
    infos = _interleave(socket.getaddrinfo(hostname, port, type=socket.SOCK_STREAM))
    last: OSError | None = None

    for family, socktype, proto, _, address in infos:
        remaining = deadline - time.monotonic()
        if remaining <= 0:
            break

        sock = socket.socket(family, socktype, proto)
        # Reparte lo que queda: dos direcciones pendientes no deben poder
        # gastar el presupuesto completo cada una.
        sock.settimeout(min(remaining, budget / 2))
        try:
            sock.connect(address)
            return sock
        except OSError as exc:
            sock.close()
            last = exc

    raise last or TimeoutError(f"Sin conexion a {hostname}:{port} en {budget}s")


def _interleave(infos: list) -> list:  # pragma: no cover
    """Alterna IPv6 e IPv4 en lugar de agotar una familia antes de la otra.

    getaddrinfo suele devolver todas las IPv6 primero. Si esta red no las
    alcanza, se gasta el presupuesto completo antes de tocar una sola IPv4.
    unam.mx publica cuatro de cada una y ese era exactamente el caso.

    Es la idea de Happy Eyeballs (RFC 8305) sin la parte concurrente: los
    navegadores prueban ambas familias casi a la vez, por eso abren el sitio
    al instante donde este codigo tardaba 32 segundos.
    """
    v6 = [i for i in infos if i[0] == socket.AF_INET6]
    v4 = [i for i in infos if i[0] != socket.AF_INET6]

    mixed = []
    for pair in zip(v6, v4, strict=False):
        mixed.extend(pair)
    mixed.extend(v6[len(v4) :])
    mixed.extend(v4[len(v6) :])
    return mixed
