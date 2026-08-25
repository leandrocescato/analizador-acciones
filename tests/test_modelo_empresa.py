"""Accessors de `Empresa` (app/modelo.py).

Cada uno de estos metodos existe para evitar un bug concreto ya documentado
en el codigo fuente: mezclar años entre series (NU, Allstate) o tomar una
serie discontinuada como si fuera actual (Ford).
"""

from __future__ import annotations

from app.modelo import Empresa


def test_f_devuelve_el_valor_mas_reciente_si_no_esta_vencido():
    emp = Empresa(ticker="X", anios=[2024], series={"roic": {2020: 10.0, 2024: 15.0}})
    assert emp.f("roic") == 15.0


def test_f_devuelve_none_si_la_serie_dejo_de_actualizarse():
    # Regresion Ford: una serie que dejo de reportarse hace años no debe
    # presentarse como si fuera el dato actual.
    emp = Empresa(ticker="X", anios=[2024], series={"deuda_vieja": {2018: 5.0}})
    assert emp.f("deuda_vieja") is None


def test_f_con_anio_explicito_ignora_el_vencimiento():
    emp = Empresa(ticker="X", anios=[2024], series={"deuda_vieja": {2018: 5.0}})
    assert emp.f("deuda_vieja", 2018) == 5.0


def test_par_alinea_los_dos_terminos_al_mismo_anio():
    # Regresion NU: tomar cada serie por separado cruzaba la provision de un
    # año con los prestamos de otro y disparaba el costo del riesgo a 42.9%.
    emp = Empresa(
        ticker="NU", anios=[2024],
        series={"provision": {2023: 10.0, 2024: 20.0}, "prestamos": {2024: 1000.0}},
    )
    assert emp.par("provision", "prestamos") == (20.0, 1000.0)


def test_par_sin_anio_en_comun_devuelve_none():
    emp = Empresa(
        ticker="X", anios=[2021],
        series={"a": {2020: 1.0}, "b": {2021: 2.0}},
    )
    assert emp.par("a", "b") == (None, None)


def test_juntos_alinea_tres_series_al_ultimo_anio_en_comun():
    # Regresion Allstate: cada ratio con su propio año mas reciente daba
    # siniestralidad + gastos que no cerraban contra el combinado.
    emp = Empresa(
        ticker="ALL", anios=[2023],
        series={
            "siniestros": {2022: 0.65, 2023: 0.78},
            "gastos": {2022: 0.26, 2023: 0.27},
            "combinado": {2023: 0.91},
        },
    )
    assert emp.juntos("siniestros", "gastos", "combinado") == (0.78, 0.27, 0.91)


def test_ventana_usa_el_ultimo_anio_de_la_empresa_no_de_la_serie():
    emp = Empresa(ticker="X", anios=[2020, 2021, 2022, 2023, 2024])
    assert emp.ventana(3) == {2022, 2023, 2024}


def test_ultimos_no_toma_una_serie_discontinuada_como_si_fuera_reciente():
    # Regresion Ford: si "ultimos" tomara los ultimos N valores que EXISTAN
    # en la serie, devolveria 2010-2014 y los presentaria como los 5 años
    # mas recientes de la empresa.
    emp = Empresa(
        ticker="F", anios=[2020, 2021, 2022, 2023, 2024],
        series={"deuda_lp": {2010: 1.0, 2011: 2.0, 2012: 3.0, 2013: 4.0, 2014: 5.0}},
    )
    assert emp.ultimos("deuda_lp", 5) == []


def test_ultimos_devuelve_los_valores_dentro_de_la_ventana():
    emp = Empresa(
        ticker="X", anios=[2012, 2013, 2014],
        series={"deuda": {2012: 100.0, 2013: 110.0, 2014: 120.0}},
    )
    assert emp.ultimos("deuda", 3) == [100.0, 110.0, 120.0]
