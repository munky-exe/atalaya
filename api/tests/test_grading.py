"""Pruebas del motor de calificación.

Ninguna toca la red. Construimos Observations a mano, que es exactamente
para lo que separamos los datos de la conexión.

Cada prueba nombra la situación real que describe, no la función que llama.
Si una falla, el nombre debe decirte qué caso del mundo se rompió.
"""

from datetime import UTC, datetime, timedelta

from app.checks.grading import grade, score_to_grade
from app.checks.models import Observation

NOW = datetime.now(UTC)


def healthy(**overrides) -> Observation:
    """Un sitio sin nada malo. Cada prueba cambia una sola cosa.

    Este ayudante es lo que mantiene las pruebas legibles: sin él, cada una
    tendría diez líneas de preparación y el detalle importante se perdería.
    """
    defaults = dict(
        hostname="example.com",
        reachable=True,
        protocol="TLSv1.3",
        cipher="TLS_AES_256_GCM_SHA384",
        cipher_bits=256,
        not_before=NOW - timedelta(days=30),
        not_after=NOW + timedelta(days=60),
    )
    defaults.update(overrides)
    return Observation(**defaults)


def test_sitio_sano_saca_cien():
    verdict = grade(healthy())
    assert verdict.score == 100
    assert verdict.grade == "A"
    assert verdict.findings == []


def test_host_inalcanzable_reprueba():
    verdict = grade(Observation(hostname="nope.invalid", reachable=False, error="DNS falló"))
    assert verdict.grade == "F"
    assert verdict.score == 0


def test_inalcanzable_no_reporta_nada_mas():
    """No tiene sentido hablar del cifrador de un host que nunca contestó."""
    verdict = grade(Observation(hostname="nope.invalid", reachable=False, protocol="TLSv1"))
    assert len(verdict.findings) == 1


def test_certificado_vencido_reprueba():
    verdict = grade(healthy(not_after=NOW - timedelta(days=3)))
    assert verdict.grade == "F"
    assert "cert_expired" in [f.code for f in verdict.findings]


def test_vencido_no_se_castiga_dos_veces():
    """Un certificado vencido también falla la verificación. Cuenta una vez."""
    verdict = grade(
        healthy(
            not_after=NOW - timedelta(days=3),
            verify_error="certificate has expired",
        )
    )
    codes = [f.code for f in verdict.findings]
    assert codes.count("cert_expired") == 1
    assert "verify_failed" not in codes


def test_nombre_que_no_corresponde_se_reporta_aparte():
    verdict = grade(healthy(verify_error="Hostname mismatch, certificate is not valid"))
    assert "hostname_mismatch" in [f.code for f in verdict.findings]


def test_tls_11_es_critico():
    verdict = grade(healthy(protocol="TLSv1.1"))
    finding = next(f for f in verdict.findings if f.code == "protocol_obsolete")
    assert finding.severity == "critical"


def test_tls_12_solo_es_un_empujon():
    """Funciona bien; solo queremos que migren. No debe tumbar la nota."""
    verdict = grade(healthy(protocol="TLSv1.2"))
    assert verdict.grade == "A"


def test_cifrador_debil_se_marca():
    verdict = grade(healthy(cipher="RC4-MD5", cipher_bits=64))
    assert "weak_cipher" in [f.code for f in verdict.findings]


def test_la_nota_nunca_es_negativa():
    verdict = grade(
        Observation(
            hostname="terrible.example",
            reachable=True,
            protocol="TLSv1",
            cipher_bits=40,
            not_before=NOW - timedelta(days=800),
            not_after=NOW - timedelta(days=10),
            verify_error="Hostname mismatch",
        )
    )
    assert verdict.score == 0


def test_fronteras_de_las_bandas():
    assert score_to_grade(90) == "A"
    assert score_to_grade(89) == "B"
    assert score_to_grade(39) == "F"


# --- Detección de protocolos obsoletos -------------------------------------
#
# La distinción entre "acepta TLS 1.0" y "no pudimos comprobarlo" es una
# decisión de producto, no un detalle técnico. Estas pruebas la congelan.


def test_aceptar_protocolo_obsoleto_es_critico():
    verdict = grade(healthy(legacy_accepted=["TLSv1", "TLSv1.1"]))
    finding = next(f for f in verdict.findings if f.code == "protocol_obsolete")
    assert finding.severity == "critical"
    # Deliberadamente no fijamos la letra: acoplar la prueba a la tabla de
    # castigos la rompe cada vez que se ajusta un número. Lo que importa es
    # que la nota caiga por debajo de aprobatoria.
    assert verdict.score < 60


def test_el_hallazgo_nombra_los_protocolos():
    """El usuario tiene que saber cuál desactivar, no solo que hay un problema."""
    verdict = grade(healthy(legacy_accepted=["TLSv1"]))
    finding = next(f for f in verdict.findings if f.code == "protocol_obsolete")
    assert "TLSv1" in finding.title


def test_no_comprobable_informa_pero_no_castiga():
    verdict = grade(healthy(legacy_untestable=["TLSv1", "TLSv1.1"]))
    assert verdict.score == 100
    assert verdict.grade == "A"
    assert "protocol_untested" in [f.code for f in verdict.findings]


def test_no_comprobable_no_se_confunde_con_limpio():
    """Un servidor sin revisar no debe verse igual que uno bien configurado."""
    limpio = grade(healthy())
    sin_revisar = grade(healthy(legacy_untestable=["TLSv1"]))

    assert limpio.score == sin_revisar.score  # misma nota
    assert limpio.findings == []  # pero el limpio no dice nada
    assert len(sin_revisar.findings) == 1  # y el otro sí avisa


def test_aceptado_tiene_prioridad_sobre_no_comprobable():
    """Si uno se aceptó y otro no se pudo probar, manda la evidencia dura."""
    verdict = grade(healthy(legacy_accepted=["TLSv1.1"], legacy_untestable=["TLSv1"]))
    codes = [f.code for f in verdict.findings]
    assert "protocol_obsolete" in codes
    assert "protocol_untested" not in codes
