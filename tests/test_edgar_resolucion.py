"""Seleccion de unidad, resolucion anual por etiqueta y año por año
(app/proveedores/edgar.py)."""

from __future__ import annotations

from app.conceptos import Concepto
from app.proveedores import edgar
from conftest import bloque, facts_de, hecho


def _concepto(unidad="USD", tipo="duracion", signo=1) -> Concepto:
    return Concepto(clave="x", etiquetas=("TagA",), unidad=unidad, tipo=tipo, signo=signo)


# ------------------------------------------------------------------ _unidades_del_concepto

def test_unidades_devuelve_la_lista_en_la_unidad_pedida():
    b = bloque(hecho(100, end="2023-12-31"), unidad="USD")
    assert edgar._unidades_del_concepto(b, _concepto(unidad="USD")) == b["units"]["USD"]


def test_unidades_usd_nunca_cae_a_otra_moneda():
    # Un emisor que solo reporta en CNY no debe devolver esos importes para un
    # concepto en USD: mezclarlos con una capitalizacion en dolares da ratios
    # sin sentido (caso Alibaba, PER 155x).
    b = bloque(hecho(100, end="2023-12-31"), unidad="CNY")
    assert edgar._unidades_del_concepto(b, _concepto(unidad="USD")) == []


def test_unidades_no_usd_cae_a_shares_si_no_hay_coincidencia_exacta():
    b = bloque(hecho(100, end="2023-12-31"), unidad="shares")
    assert edgar._unidades_del_concepto(b, _concepto(unidad="pure")) == b["units"]["shares"]


def test_unidades_no_usd_sin_ninguna_coincidencia_devuelve_vacio():
    b = bloque(hecho(100, end="2023-12-31"), unidad="EUR")
    assert edgar._unidades_del_concepto(b, _concepto(unidad="pure")) == []


# ------------------------------------------------------------------ _hechos_anuales

def test_hechos_anuales_gana_la_presentacion_mas_reciente():
    # Un mismo ejercicio reexpresado: gana la version con fecha de
    # presentacion (`filed`) mas nueva, no la primera que aparece.
    original = hecho(100, start="2023-01-01", end="2023-12-31",
                      form="10-K", filed="2024-02-01")
    reexpresado = hecho(105, start="2023-01-01", end="2023-12-31",
                         form="10-K", filed="2025-02-01")
    facts = facts_de(us_gaap={"Revenues": bloque(original, reexpresado)})
    salida = edgar._hechos_anuales(facts, "Revenues", _concepto())
    assert salida[2023]["val"] == 105


def test_hechos_anuales_descarta_formas_no_anuales():
    trimestral = hecho(100, start="2023-10-01", end="2023-12-31", form="10-Q")
    facts = facts_de(us_gaap={"Revenues": bloque(trimestral)})
    assert edgar._hechos_anuales(facts, "Revenues", _concepto()) == {}


def test_hechos_anuales_descarta_duracion_invalida_para_concepto_duracion():
    corto = hecho(100, start="2023-10-01", end="2023-12-31", form="10-K")
    facts = facts_de(us_gaap={"Revenues": bloque(corto)})
    assert edgar._hechos_anuales(facts, "Revenues", _concepto(tipo="duracion")) == {}


def test_hechos_anuales_concepto_instante_descarta_hechos_con_start():
    con_start = hecho(100, start="2023-01-01", end="2023-12-31", form="10-K")
    sin_start = hecho(200, end="2023-12-31", form="10-K")
    facts = facts_de(us_gaap={"Efectivo": bloque(con_start, sin_start)})
    salida = edgar._hechos_anuales(facts, "Efectivo", _concepto(tipo="instante"))
    assert salida[2023]["val"] == 200


# ------------------------------------------------------------------ serie_por_concepto

def test_serie_por_concepto_resuelve_ano_por_ano_entre_etiquetas():
    # Una empresa que cambio de etiqueta a mitad de la serie (caso CoStar):
    # la etiqueta preferida cubre el año que tiene, y la siguiente candidata
    # rellena los años que a la primera le faltan, sin pisar los que si tiene.
    concepto = Concepto(clave="ingresos", etiquetas=("TagNueva", "TagVieja"))
    facts = facts_de(us_gaap={
        "TagNueva": bloque(hecho(2200, start="2022-01-01", end="2022-12-31")),
        "TagVieja": bloque(
            hecho(2000, start="2021-01-01", end="2021-12-31"),
            hecho(2100, start="2022-01-01", end="2022-12-31"),  # no se usa: TagNueva manda
            hecho(2300, start="2023-01-01", end="2023-12-31"),
        ),
    })
    salida = edgar.serie_por_concepto(facts, concepto, [2021, 2022, 2023])
    assert salida[2021]["valor"] == 2000
    assert salida[2021]["etiqueta"] == "TagVieja"
    assert salida[2022]["valor"] == 2200
    assert salida[2022]["etiqueta"] == "TagNueva"
    assert salida[2023]["valor"] == 2300
    assert salida[2023]["etiqueta"] == "TagVieja"


def test_serie_por_concepto_aplica_el_signo():
    concepto = Concepto(clave="capex", etiquetas=("Capex",), signo=-1)
    facts = facts_de(us_gaap={
        "Capex": bloque(hecho(500, start="2023-01-01", end="2023-12-31")),
    })
    salida = edgar.serie_por_concepto(facts, concepto, [2023])
    assert salida[2023]["valor"] == -500


def test_serie_por_concepto_sin_datos_devuelve_vacio():
    concepto = Concepto(clave="x", etiquetas=("NoExiste",))
    facts = facts_de(us_gaap={})
    assert edgar.serie_por_concepto(facts, concepto, [2023]) == {}
