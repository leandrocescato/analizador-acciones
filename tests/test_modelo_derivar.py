"""Series derivadas de `app/modelo.py::_derivar`.

Los casos con "regresion" en el nombre reproducen bugs reales que el
docstring de `_derivar` documenta explicitamente (ROIC de 463% en empresas
con financiera cautiva, FFO inflado de Simon Property por una venta no
desglosada, doble conteo de deuda de NU).
"""

from __future__ import annotations

from app.modelo import _derivar


def test_caja_deuda_y_deuda_neta():
    series = {
        "efectivo": {2023: 100.0},
        "inversiones_cp": {2023: 50.0},
        "deuda_lp": {2023: 200.0},
        "deuda_cp": {2023: 20.0},
        # 2023 ya esta cubierto por deuda_lp/deuda_cp: no debe sumarse aparte.
        # 2024 no tiene deuda_lp/deuda_cp: se rellena con deuda_reportada.
        "deuda_reportada": {2023: 999.0, 2024: 500.0},
    }
    _derivar(series)

    assert series["caja_total"][2023] == 150.0
    assert series["deuda_financiera"][2023] == 220.0  # no se duplica con deuda_reportada
    assert series["deuda_financiera"][2024] == 500.0  # relleno del año sin desglose
    assert series["deuda_neta"][2023] == 70.0  # 220 - 150


def test_capital_invertido_excluye_anio_bajo_el_piso_del_5pc_del_activo():
    # Regresion: mucha caja contra poco patrimonio puede dejar un capital
    # invertido casi nulo y disparar el ROIC a cientos por ciento.
    series = {
        "patrimonio": {2023: 1000.0},
        "deuda_reportada": {2023: 0.0},
        "efectivo": {2023: 950.0},
        "activo_total": {2023: 2000.0},
    }
    _derivar(series)
    assert 2023 not in series.get("capital_invertido", {})


def test_capital_invertido_incluye_anio_que_supera_el_piso():
    series = {
        "patrimonio": {2023: 1000.0},
        "deuda_reportada": {2023: 0.0},
        "efectivo": {2023: 500.0},
        "activo_total": {2023: 2000.0},
    }
    _derivar(series)
    assert series["capital_invertido"][2023] == 500.0


def test_capital_invertido_ex_gw_excluye_cuando_el_goodwill_se_come_el_capital():
    series = {
        "patrimonio": {2023: 1000.0},
        "deuda_reportada": {2023: 0.0},
        "efectivo": {2023: 500.0},
        "activo_total": {2023: 2000.0},
        "goodwill": {2023: 400.0},
        "intangibles": {2023: 50.0},
    }
    _derivar(series)
    assert 2023 not in series.get("capital_invertido_ex_gw", {})


def test_capital_invertido_ex_gw_incluye_cuando_queda_capital_operativo_sano():
    series = {
        "patrimonio": {2023: 1000.0},
        "deuda_reportada": {2023: 0.0},
        "efectivo": {2023: 500.0},
        "activo_total": {2023: 2000.0},
        "goodwill": {2023: 100.0},
        "intangibles": {2023: 50.0},
    }
    _derivar(series)
    assert series["capital_invertido_ex_gw"][2023] == 350.0


def test_fcf_fcf_post_sbc_y_ebitda():
    series = {
        "flujo_operativo": {2023: 500.0},
        "capex": {2023: 100.0},
        "sbc": {2023: 50.0},
        "ebit": {2023: 300.0},
        "dya": {2023: 80.0},
    }
    _derivar(series)
    assert series["fcf"][2023] == 400.0
    assert series["fcf_post_sbc"][2023] == 350.0
    assert series["ebitda"][2023] == 380.0


def test_tasa_impositiva_se_acota_entre_0_y_50pc_y_alimenta_el_nopat():
    series = {
        "impuesto": {2021: 90.0, 2022: 200.0, 2023: -10.0},
        "antes_impuesto": {2021: 300.0, 2022: 100.0, 2023: 100.0},
        "ebit": {2021: 300.0, 2022: 100.0, 2023: 100.0},
    }
    _derivar(series)
    assert series["tasa_impositiva"][2021] == 0.3
    assert series["tasa_impositiva"][2022] == 0.5   # clamp superior: 200/100 = 2.0
    assert series["tasa_impositiva"][2023] == 0.0    # clamp inferior: -10/100 = -0.1
    assert series["nopat"][2021] == 210.0  # 300 * (1 - 0.3)


def test_ebit_se_reconstruye_solo_para_los_anios_que_faltan():
    # Farmaceuticas e industriales que no etiquetan OperatingIncomeLoss: se
    # reconstruye con antes_impuesto + intereses, pero sin pisar los años que
    # ya tienen EBIT reportado.
    series = {
        "antes_impuesto": {2022: 100.0, 2023: 150.0},
        "ebit": {2022: 120.0},
        "intereses": {2023: 20.0},
    }
    _derivar(series)
    assert series["ebit"][2022] == 120.0  # intacto
    assert series["ebit"][2023] == 170.0  # 150 + |20|


def test_ffo_no_se_calcula_si_nunca_se_etiqueto_ganancia_por_venta_de_inmuebles():
    series = {
        "ganancia_neta": {2023: 1000.0},
        "dya": {2023: 200.0},
    }
    _derivar(series)
    assert "ffo" not in series


def test_ffo_neto_de_ventas_puntuales_y_con_deterioro_sumado():
    # Caso Simon Property: sin esta resta, una venta grande de un solo año
    # infla el FFO muy por encima de los años normales.
    series = {
        "ganancia_neta": {2022: 500.0, 2023: 1000.0},
        "dya": {2022: 100.0, 2023: 200.0},
        "ganancia_venta_inmuebles": {2023: 300.0},
        "deterioro_inmuebles": {2022: 50.0},
    }
    _derivar(series)
    assert series["ffo"][2022] == 650.0  # 500 + 100 - 0 + 50
    assert series["ffo"][2023] == 900.0  # 1000 + 200 - 300 + 0


def test_ganancia_bruta_se_completa_pero_no_pisa_un_valor_ya_reportado():
    series = {
        "ingresos": {2023: 1000.0},
        "costo_ventas": {2023: 600.0},
    }
    _derivar(series)
    assert series["ganancia_bruta"][2023] == 400.0

    series_con_dato_propio = {
        "ingresos": {2023: 1000.0},
        "costo_ventas": {2023: 600.0},
        "ganancia_bruta": {2023: 999.0},
    }
    _derivar(series_con_dato_propio)
    assert series_con_dato_propio["ganancia_bruta"][2023] == 999.0
