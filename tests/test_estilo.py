"""Clasificacion VALUE/GROWTH/HIBRIDA/TURNAROUND (app/estilo.py).

Los tests de `clasificar` fijan `_crecimiento` con `monkeypatch` para poder
probar cada rama de la regla con numeros exactos, sin depender de que la
aritmetica de CAGR compuesto de por casualidad el mismo resultado. El
calculo real de `_crecimiento` se prueba aparte, con numeros limpios.
"""

from __future__ import annotations

import pytest

from app import estilo, perfiles
from app.modelo import Empresa


def _empresa(ingresos=None, ganancia_neta=None, fcf=None, anios=None,
             sector="", perfil=perfiles.GENERAL) -> Empresa:
    series = {}
    if ingresos:
        series["ingresos"] = ingresos
    if ganancia_neta is not None:
        series["ganancia_neta"] = {max(anios or [2024]): ganancia_neta}
    if fcf is not None:
        series["fcf"] = {max(anios or [2024]): fcf}
    return Empresa(ticker="X", anios=anios or [2024], series=series,
                    sector=sector, perfil=perfil)


# ------------------------------------------------------------------ _crecimiento

def test_crecimiento_calcula_yoy_y_cagr3_con_crecimiento_constante():
    # 20% anual constante: yoy y cagr3 de 3 años deben coincidir.
    emp = _empresa(
        ingresos={2021: 1000.0, 2022: 1200.0, 2023: 1440.0, 2024: 1728.0},
        anios=[2021, 2022, 2023, 2024],
    )
    yoy, cagr3 = estilo._crecimiento(emp)
    assert yoy == pytest.approx(20.0)
    assert cagr3 == pytest.approx(20.0)


def test_crecimiento_sin_serie_de_ingresos():
    emp = _empresa(anios=[2024])
    assert estilo._crecimiento(emp) == (None, None)


def test_crecimiento_con_un_solo_anio_no_alcanza():
    emp = _empresa(ingresos={2024: 1000.0}, anios=[2024])
    assert estilo._crecimiento(emp) == (None, None)


# ------------------------------------------------------------------ es_ciclica

def test_es_ciclica_por_perfil_contable():
    emp = _empresa(anios=[2024], perfil=perfiles.BANCO)
    assert estilo.es_ciclica(emp) is True


def test_es_ciclica_por_sector():
    emp = _empresa(anios=[2024], sector="Energy")
    assert estilo.es_ciclica(emp) is True


def test_es_ciclica_false_para_sector_no_ciclico():
    emp = _empresa(anios=[2024], sector="Technology")
    assert estilo.es_ciclica(emp) is False


# ------------------------------------------------------------------ clasificar

def test_clasificar_turnaround_pierde_plata_y_no_crece(monkeypatch):
    monkeypatch.setattr(estilo, "_crecimiento", lambda emp: (2.0, 3.0))
    emp = _empresa(ganancia_neta=-50.0, anios=[2024])
    resultado = estilo.clasificar(emp)
    assert resultado["estilo"] == estilo.TURNAROUND


def test_clasificar_growth_si_crece_15_por_ciento_o_mas(monkeypatch):
    monkeypatch.setattr(estilo, "_crecimiento", lambda emp: (20.0, 20.0))
    emp = _empresa(ganancia_neta=100.0, fcf=50.0, anios=[2024])
    resultado = estilo.clasificar(emp)
    assert resultado["estilo"] == estilo.GROWTH
    assert any("caja libre" in r for r in resultado["razones"])


def test_clasificar_growth_con_fcf_negativo_avisa_que_quema_caja(monkeypatch):
    monkeypatch.setattr(estilo, "_crecimiento", lambda emp: (20.0, 20.0))
    emp = _empresa(ganancia_neta=100.0, fcf=-30.0, anios=[2024])
    resultado = estilo.clasificar(emp)
    assert resultado["estilo"] == estilo.GROWTH
    assert any("negativa" in r for r in resultado["razones"])


def test_clasificar_value_si_crece_menos_de_10_por_ciento(monkeypatch):
    monkeypatch.setattr(estilo, "_crecimiento", lambda emp: (5.0, 4.0))
    emp = _empresa(ganancia_neta=100.0, anios=[2024])
    resultado = estilo.clasificar(emp)
    assert resultado["estilo"] == estilo.VALUE


def test_clasificar_hibrida_entre_10_y_15_por_ciento(monkeypatch):
    monkeypatch.setattr(estilo, "_crecimiento", lambda emp: (12.0, 12.0))
    emp = _empresa(ganancia_neta=100.0, anios=[2024])
    resultado = estilo.clasificar(emp)
    assert resultado["estilo"] == estilo.HIBRIDA


def test_clasificar_sin_ingresos_cae_en_value(monkeypatch):
    monkeypatch.setattr(estilo, "_crecimiento", lambda emp: (None, None))
    emp = _empresa(ganancia_neta=100.0, anios=[2024])
    resultado = estilo.clasificar(emp)
    assert resultado["estilo"] == estilo.VALUE
    assert any("Sin serie de ingresos" in r for r in resultado["razones"])


def test_clasificar_avisa_divergencia_entre_yoy_y_cagr3(monkeypatch):
    # Diferencia de 22 puntos entre el ultimo ejercicio y el CAGR de 3 años:
    # amerita aviso, mas alla de en que estilo termine clasificada.
    monkeypatch.setattr(estilo, "_crecimiento", lambda emp: (30.0, 8.0))
    emp = _empresa(ganancia_neta=100.0, anios=[2024])
    resultado = estilo.clasificar(emp)
    assert resultado["avisos"]  # no vacio
    assert resultado["yoy"] == 30.0 and resultado["cagr3"] == 8.0


def test_clasificar_avisa_riesgo_ciclico_en_value(monkeypatch):
    monkeypatch.setattr(estilo, "_crecimiento", lambda emp: (5.0, 4.0))
    emp = _empresa(ganancia_neta=100.0, anios=[2024], sector="Energy")
    resultado = estilo.clasificar(emp)
    assert resultado["estilo"] == estilo.VALUE
    assert resultado["ciclica"] is True
    assert any("ciclico" in a for a in resultado["avisos"])
