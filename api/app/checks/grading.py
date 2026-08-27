"""Calificacion de postura TLS.

Funcion pura: recibe una Observation, devuelve un veredicto. No toca la red
y da siempre el mismo resultado para la misma entrada.

Por eso se puede probar entera sin conexion.
"""

from __future__ import annotations

from dataclasses import dataclass

from app.checks.models import Observation

OBSOLETE_PROTOCOLS = {"SSLv2", "SSLv3", "TLSv1", "TLSv1.1"}

PENALTIES = {
    "unreachable": 100,
    "cert_expired": 100,
    "hostname_mismatch": 100,
    "verify_failed": 70,
    "expires_critical": 55,
    "expires_soon": 30,
    "expires_warning": 12,
    "protocol_obsolete": 60,
    "protocol_untested": 0,
    "protocol_skipped": 0,
    "protocol_dated": 10,
    "weak_cipher": 25,
    "long_lifetime": 8,
}


@dataclass
class Finding:
    code: str
    severity: str  # critical | high | medium | low
    title: str
    detail: str


@dataclass
class Verdict:
    score: int
    grade: str
    findings: list[Finding]


def score_to_grade(score: int) -> str:
    if score >= 90:
        return "A"
    if score >= 80:
        return "B"
    if score >= 70:
        return "C"
    if score >= 60:
        return "D"
    if score >= 40:
        return "E"
    return "F"


def grade(obs: Observation) -> Verdict:
    findings: list[Finding] = []
    score = 100

    def penalise(code: str, severity: str, title: str, detail: str) -> None:
        nonlocal score
        score -= PENALTIES[code]
        findings.append(Finding(code, severity, title, detail))

    # Si no hubo conexion, nada mas tiene sentido reportar.
    if not obs.reachable:
        penalise(
            "unreachable",
            "critical",
            "No responde en el puerto TLS",
            obs.error or "No se pudo establecer conexion.",
        )
        return Verdict(score=0, grade="F", findings=findings)

    days = obs.days_remaining

    if days is not None:
        if days < 0:
            penalise(
                "cert_expired",
                "critical",
                "Certificado vencido",
                f"Vencio hace {abs(days)} dias. Los navegadores bloquean el acceso.",
            )
        elif days < 7:
            penalise(
                "expires_critical",
                "critical",
                "Vence esta semana",
                f"Quedan {days} dias. Renueva ahora.",
            )
        elif days < 15:
            penalise(
                "expires_soon",
                "high",
                "Vence en menos de dos semanas",
                f"Quedan {days} dias.",
            )
        elif days < 30:
            penalise(
                "expires_warning",
                "medium",
                "Vence este mes",
                f"Quedan {days} dias.",
            )

    if obs.verify_error:
        lowered = obs.verify_error.lower()
        if "hostname mismatch" in lowered or "doesn't match" in lowered:
            penalise(
                "hostname_mismatch",
                "critical",
                "El certificado no corresponde al dominio",
                obs.verify_error,
            )
        elif days is None or days >= 0:
            # Un certificado vencido ya fallo la verificacion: no castigar
            # dos veces el mismo problema.
            penalise(
                "verify_failed",
                "critical",
                "La cadena de confianza no valida",
                obs.verify_error,
            )

    # Tres estados distintos, tres mensajes distintos. Confundirlos daria
    # falsa tranquilidad o culparia al servidor de una limitacion nuestra.
    if obs.legacy_accepted:
        penalise(
            "protocol_obsolete",
            "critical",
            f"Acepta protocolos obsoletos: {', '.join(obs.legacy_accepted)}",
            "El RFC 8996 los declara fuera de uso. Un navegador antiguo los "
            "negociaria aunque tu conexion haya usado TLS 1.3.",
        )
    elif obs.legacy_skipped:
        penalise(
            "protocol_skipped",
            "low",
            "Sin comprobar: el sondeo tardo demasiado",
            "Este servidor respondio muy lento, asi que omitimos la prueba de "
            "TLS 1.0 y 1.1 en lugar de hacerte esperar mas.",
        )
    elif obs.legacy_untestable:
        penalise(
            "protocol_untested",
            "low",
            f"Sin comprobar: {', '.join(obs.legacy_untestable)}",
            "Este build de OpenSSL no puede negociar esos protocolos, "
            "asi que no podemos confirmar que el servidor los rechace.",
        )

    if obs.protocol in OBSOLETE_PROTOCOLS:
        penalise(
            "protocol_obsolete",
            "critical",
            f"Protocolo obsoleto: {obs.protocol}",
            "El RFC 8996 declara TLS 1.0 y 1.1 fuera de uso.",
        )
    elif obs.protocol == "TLSv1.2":
        penalise(
            "protocol_dated",
            "low",
            "Sin TLS 1.3",
            "La conexion negocio TLS 1.2. TLS 1.3 es mas rapido y mas seguro.",
        )

    if obs.cipher_bits is not None and obs.cipher_bits < 128:
        penalise(
            "weak_cipher",
            "high",
            f"Cifrador debil: {obs.cipher}",
            f"Negocio {obs.cipher_bits} bits. El minimo aceptable es 128.",
        )

    if obs.lifetime_days is not None and obs.lifetime_days > 398:
        penalise(
            "long_lifetime",
            "low",
            "Vigencia superior a 398 dias",
            "Las CA publicas ya no emiten certificados tan largos.",
        )

    score = max(0, min(100, score))
    return Verdict(score=score, grade=score_to_grade(score), findings=findings)
