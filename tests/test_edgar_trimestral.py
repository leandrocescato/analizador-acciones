"""Mes de cierre fiscal, series trimestrales y el 4T derivado por resta
(app/proveedores/edgar.py)."""

from __future__ import annotations

from app.conceptos import Concepto
from app.proveedores import edgar
from conftest import bloque, facts_de, hecho


# ------------------------------------------------------------------ _mes_cierre_fiscal

def test_mes_cierre_fiscal_toma_el_mes_mas_frecuente_en_informes_anuales():
    facts = facts_de(us_gaap={"Revenues": bloque(
        hecho(100, start="2021-10-01", end="2022-09-30", form="10-K"),
        hecho(110, start="2022-10-01", end="2023-09-30", form="10-K"),
        hecho(120, start="2023-10-01", end="2024-09-30", form="10-K"),
        # Un unico informe con otro mes de cierre (p.ej. un stub period) no
        # debe cambiar la moda.
        hecho(50, start="2020-01-01", end="2020-12-31", form="10-K"),
    )})
    assert edgar._mes_cierre_fiscal(facts) == 9


def test_mes_cierre_fiscal_ignora_hechos_trimestrales():
    facts = facts_de(us_gaap={"Revenues": bloque(
        hecho(100, start="2024-01-01", end="2024-03-31", form="10-Q"),
    )})
    assert edgar._mes_cierre_fiscal(facts) is None


# ------------------------------------------------------------------ serie_trimestral

def test_serie_trimestral_resuelve_los_tres_trimestres_presentados():
    concepto = Concepto(clave="ingresos_test", etiquetas=("Revenues",))
    facts = facts_de(us_gaap={"Revenues": bloque(
        hecho(100, start="2024-01-01", end="2024-03-31", form="10-Q", filed="2024-05-01"),
        hecho(110, start="2024-04-01", end="2024-06-30", form="10-Q", filed="2024-08-01"),
        hecho(120, start="2024-07-01", end="2024-09-30", form="10-Q", filed="2024-11-01"),
    )})
    salida = edgar.serie_trimestral(facts, concepto, mes_cierre=12)
    assert salida[(2024, 1)]["valor"] == 100
    assert salida[(2024, 2)]["valor"] == 110
    assert salida[(2024, 3)]["valor"] == 120


def test_serie_trimestral_ignora_hechos_de_duracion_no_trimestral():
    concepto = Concepto(clave="ingresos_test", etiquetas=("Revenues",))
    facts = facts_de(us_gaap={"Revenues": bloque(
        hecho(1000, start="2023-01-01", end="2023-12-31", form="10-K"),
    )})
    assert edgar.serie_trimestral(facts, concepto, mes_cierre=12) == {}


# ------------------------------------------------------------------ trimestrales(): 4T por resta

def test_trimestrales_deriva_el_cuarto_trimestre_por_resta(monkeypatch):
    # Las empresas de EE.UU. presentan tres 10-Q y un 10-K con el ejercicio
    # entero: el 4T no existe como tal y se calcula restandole al total anual
    # los tres trimestres previos (docstring de `trimestrales`).
    facts = facts_de(us_gaap={"Revenues": bloque(
        hecho(100, start="2024-01-01", end="2024-03-31", form="10-Q", filed="2024-05-01"),
        hecho(110, start="2024-04-01", end="2024-06-30", form="10-Q", filed="2024-08-01"),
        hecho(120, start="2024-07-01", end="2024-09-30", form="10-Q", filed="2024-11-01"),
        hecho(1000, start="2023-01-01", end="2023-12-31", form="10-K", filed="2024-02-01"),
        hecho(460, start="2024-01-01", end="2024-12-31", form="10-K", filed="2025-02-01"),
    )})

    monkeypatch.setattr(edgar, "companyfacts", lambda ticker: facts)
    monkeypatch.setattr(edgar, "identidad",
                         lambda ticker: {"sic": "", "sic_desc": "", "ultimo_anual": None})
    monkeypatch.setattr(edgar, "cik_de", lambda ticker: "0000000000")

    resultado = edgar.trimestrales("ACME", concepto_claves=["ingresos"])

    serie = resultado["series"]["ingresos"]
    assert serie[(2024, 1)] == 100
    assert serie[(2024, 2)] == 110
    assert serie[(2024, 3)] == 120
    assert serie[(2024, 4)] == 130  # 460 - 100 - 110 - 120
    assert ("ingresos", (2024, 4)) in resultado["derivados"]
    assert resultado["periodos"] == [(2024, 1), (2024, 2), (2024, 3), (2024, 4)]


def test_trimestrales_vacio_si_la_empresa_no_presenta_trimestrales(monkeypatch):
    # Caso NU: reporta por 6-K sin XBRL, asi que no hay hechos con forma
    # trimestral. Mostrar los saldos de cierre anual como si fueran
    # trimestres armaria un balance con una sola columna por año.
    facts = facts_de(us_gaap={"Revenues": bloque(
        hecho(1000, start="2023-01-01", end="2023-12-31", form="10-K", filed="2024-02-01"),
    )})
    monkeypatch.setattr(edgar, "companyfacts", lambda ticker: facts)
    monkeypatch.setattr(edgar, "identidad",
                         lambda ticker: {"sic": "", "sic_desc": "", "ultimo_anual": None})
    monkeypatch.setattr(edgar, "cik_de", lambda ticker: "0000000000")

    resultado = edgar.trimestrales("NU", concepto_claves=["ingresos"])
    assert resultado == {"periodos": [], "series": {}, "derivados": set()}
