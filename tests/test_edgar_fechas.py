"""Año fiscal y filtros de duracion (app/proveedores/edgar.py)."""

from __future__ import annotations

from app.proveedores import edgar
from conftest import hecho


# ------------------------------------------------------------------ _anio_fiscal

def test_anio_fiscal_fecha_normal():
    assert edgar._anio_fiscal("2024-06-30") == 2024


def test_anio_fiscal_cierre_52_53_semanas_en_enero_va_al_anio_anterior():
    # Un ejercicio 52/53 semanas que cierra los primeros dias de enero
    # pertenece, en los hechos, al año anterior (docstring del modulo).
    assert edgar._anio_fiscal("2024-01-03") == 2023


def test_anio_fiscal_15_de_enero_ya_no_entra_en_la_excepcion():
    assert edgar._anio_fiscal("2024-01-15") == 2024


def test_anio_fiscal_fecha_invalida_devuelve_none():
    assert edgar._anio_fiscal("no-es-una-fecha") is None
    assert edgar._anio_fiscal(None) is None


# ------------------------------------------------------------------ _duracion_valida

def test_duracion_valida_ejercicio_completo():
    h = hecho(100, start="2023-01-01", end="2023-12-31")
    assert edgar._duracion_valida(h) is True


def test_duracion_valida_rechaza_trimestre():
    h = hecho(100, start="2023-10-01", end="2023-12-31")
    assert edgar._duracion_valida(h) is False


def test_duracion_valida_sin_start_o_end():
    assert edgar._duracion_valida({"val": 1, "end": "2023-12-31"}) is False
    assert edgar._duracion_valida({"val": 1, "start": "2023-01-01"}) is False


# ------------------------------------------------------------------ _duracion_trimestral

def test_duracion_trimestral_acepta_trimestre_tipico():
    h = hecho(100, start="2023-07-01", end="2023-09-30")
    assert edgar._duracion_trimestral(h) is True


def test_duracion_trimestral_rechaza_ejercicio_completo():
    h = hecho(100, start="2023-01-01", end="2023-12-31")
    assert edgar._duracion_trimestral(h) is False


# ------------------------------------------------------------------ _etiqueta_trimestre

def test_etiqueta_trimestre_calendario_completo_mes_cierre_12():
    # Empresa de año calendario: cada fin de trimestre calza con su propio numero.
    assert edgar._etiqueta_trimestre("2024-03-31", 12) == (2024, 1)
    assert edgar._etiqueta_trimestre("2024-06-30", 12) == (2024, 2)
    assert edgar._etiqueta_trimestre("2024-09-30", 12) == (2024, 3)
    assert edgar._etiqueta_trimestre("2024-12-31", 12) == (2024, 4)


def test_etiqueta_trimestre_apple_cierra_en_diciembre_es_su_primer_trimestre():
    # Apple cierra ejercicio en septiembre: su trimestre de diciembre es el
    # primero de su año fiscal (ejemplo del propio docstring de edgar.py).
    assert edgar._etiqueta_trimestre("2023-12-30", 9) == (2024, 1)


def test_etiqueta_trimestre_dia_temprano_de_enero_se_cuenta_como_diciembre():
    # El ajuste de 52/53 semanas: un cierre el 10 de enero se lee como si
    # hubiera cerrado en diciembre.
    assert edgar._etiqueta_trimestre("2024-01-10", 12) == (2024, 4)


def test_etiqueta_trimestre_fecha_invalida_devuelve_none():
    assert edgar._etiqueta_trimestre("no-es-una-fecha", 12) is None
