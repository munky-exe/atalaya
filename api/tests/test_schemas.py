"""Pruebas de validación de entrada.

Lo que se prueba aquí no es una expresión regular: es la decisión de rescatar
lo que el usuario quiso decir en lugar de castigarlo por el formato.
"""

import pytest
from pydantic import ValidationError

from app.schemas import DomainCreate


@pytest.mark.parametrize(
    "entrada,esperado",
    [
        ("github.com", "github.com"),
        ("  github.com  ", "github.com"),
        ("GitHub.COM", "github.com"),
        ("https://github.com", "github.com"),
        ("http://github.com/", "github.com"),
        ("https://github.com/munky-exe/atalaya", "github.com"),
        ("https://github.com/search?q=tls", "github.com"),
        ("github.com:443", "github.com"),
        ("https://user:pass@github.com/x", "github.com"),
        ("sub.dominio.ejemplo.mx", "sub.dominio.ejemplo.mx"),
    ],
)
def test_rescata_lo_que_el_usuario_quiso_decir(entrada, esperado):
    assert DomainCreate(hostname=entrada).hostname == esperado


@pytest.mark.parametrize(
    "basura",
    [
        "",
        "   ",
        "no es un dominio",
        "localhost",  # sin punto: no es un FQDN
        "..",
        "-guion.com",
        "guion-.com",
        "a" * 300,
    ],
)
def test_rechaza_lo_que_no_se_puede_rescatar(basura):
    with pytest.raises(ValidationError):
        DomainCreate(hostname=basura)


def test_el_error_dice_que_se_esperaba():
    """Un mensaje que solo dice 'inválido' obliga a adivinar."""
    with pytest.raises(ValidationError) as exc:
        DomainCreate(hostname="asdf")
    assert "github.com" in str(exc.value)


def test_el_puerto_por_defecto_es_443():
    assert DomainCreate(hostname="github.com").port == 443


@pytest.mark.parametrize("puerto", [0, -1, 65536, 99999])
def test_puertos_fuera_de_rango_se_rechazan(puerto):
    with pytest.raises(ValidationError):
        DomainCreate(hostname="github.com", port=puerto)
