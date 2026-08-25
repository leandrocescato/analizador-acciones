"""Deteccion de splits por reexpresion del mismo ejercicio
(app/proveedores/edgar.py)."""

from __future__ import annotations

from app.conceptos import Concepto
from app.proveedores import edgar
from conftest import bloque, facts_de, hecho

_CONCEPTO_ACCIONES = Concepto(
    clave="acciones_circulacion", etiquetas=("SharesOutstanding",),
    unidad="shares", tipo="instante",
)


def test_eventos_split_detecta_salto_por_reexpresion_del_mismo_ejercicio():
    # El mismo ejercicio 2018 aparece con 100M de acciones en el informe
    # original y con 500M en uno posterior: la proporcion (5x) esta en los
    # datos porque el ejercicio no cambia, sin mezclarse con emision o
    # recompra real del periodo (ver docstring de `_eventos_split`).
    facts = facts_de(us_gaap={"SharesOutstanding": bloque(
        hecho(100_000_000, end="2018-12-31", filed="2019-02-01"),
        hecho(500_000_000, end="2018-12-31", filed="2021-02-01"),
        unidad="shares",
    )})
    eventos = edgar._eventos_split(facts, _CONCEPTO_ACCIONES)
    assert eventos == [("2021-02-01", 5.0)]


def test_eventos_split_ignora_reexpresion_chica_no_es_split():
    # Una diferencia del 10% entre presentaciones es una correccion normal,
    # no un split: no debe superar el umbral de 1.4x.
    facts = facts_de(us_gaap={"SharesOutstanding": bloque(
        hecho(100_000_000, end="2018-12-31", filed="2019-02-01"),
        hecho(110_000_000, end="2018-12-31", filed="2021-02-01"),
        unidad="shares",
    )})
    assert edgar._eventos_split(facts, _CONCEPTO_ACCIONES) == []


def test_eventos_split_detecta_split_inverso():
    # Un split inverso 1-por-2 tambien es una escala del 0.5x, no una
    # variacion normal de acciones en circulacion.
    facts = facts_de(us_gaap={"SharesOutstanding": bloque(
        hecho(100_000_000, end="2018-12-31", filed="2019-02-01"),
        hecho(50_000_000, end="2018-12-31", filed="2021-02-01"),
        unidad="shares",
    )})
    eventos = edgar._eventos_split(facts, _CONCEPTO_ACCIONES)
    assert eventos == [("2021-02-01", 0.5)]


def test_eventos_split_consolida_varios_anios_con_la_mediana():
    # Un mismo split queda reexpresado en varios ejercicios a la vez: se
    # consolida con la mediana para absorber el redondeo entre ellos.
    facts = facts_de(us_gaap={"SharesOutstanding": bloque(
        hecho(100_000_000, end="2018-12-31", filed="2019-02-01"),
        hecho(500_000_000, end="2018-12-31", filed="2021-02-01"),
        hecho(120_000_000, end="2019-12-31", filed="2020-02-01"),
        hecho(600_000_000, end="2019-12-31", filed="2021-02-01"),
        unidad="shares",
    )})
    eventos = edgar._eventos_split(facts, _CONCEPTO_ACCIONES)
    assert eventos == [("2021-02-01", 5.0)]


# ------------------------------------------------------------------ _mediana

def test_mediana_cantidad_impar():
    assert edgar._mediana([3.0, 1.0, 2.0]) == 2.0


def test_mediana_cantidad_par_promedia_el_medio():
    assert edgar._mediana([1.0, 2.0, 3.0, 4.0]) == 2.5


# ------------------------------------------------------------------ _factor_split

def test_factor_split_reescala_lo_presentado_antes_del_split():
    eventos = [("2021-02-01", 5.0)]
    assert edgar._factor_split(eventos, "2019-02-01") == 5.0


def test_factor_split_no_reescala_lo_presentado_despues():
    eventos = [("2021-02-01", 5.0)]
    assert edgar._factor_split(eventos, "2022-06-01") == 1.0


def test_factor_split_compone_varios_splits_posteriores():
    eventos = [("2020-01-01", 2.0), ("2022-01-01", 3.0)]
    assert edgar._factor_split(eventos, "2019-01-01") == 6.0
    assert edgar._factor_split(eventos, "2021-01-01") == 3.0


def test_factor_split_sin_fecha_presentada_no_reescala():
    assert edgar._factor_split([("2021-02-01", 5.0)], None) == 1.0
