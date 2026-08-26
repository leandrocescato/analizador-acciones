"""Identidades contables y los cuatro errores que las rompian
(app/validacion.py, app/proveedores/edgar.py, app/conceptos.py)."""

from __future__ import annotations

from app import validacion
from app.conceptos import Concepto, POR_CLAVE
from app.proveedores import edgar
from conftest import bloque, facts_de, hecho


def _datos(series: dict, procedencia: dict | None = None, anios=(2025,)) -> dict:
    return {"series": series, "procedencia": procedencia or {}, "anios": list(anios)}


# ------------------------------------------------- ingresos = costo + bruta

def test_ingresos_que_no_cierran_contra_costo_y_bruta_se_marcan():
    # El caso Bloom Energy: 2.002 M leidos de la etiqueta de contratos contra
    # 2.024 M publicados. La ganancia bruta reportada delata la diferencia.
    hallazgos = validacion.revisar(_datos({
        "ingresos": {2025: 2_001_614_000.0},
        "costo_ventas": {2025: 1_436_594_000.0},
        "ganancia_bruta": {2025: 587_400_000.0},
    }))
    assert len(hallazgos) == 1
    assert hallazgos[0].severidad == "grave"
    assert hallazgos[0].anio == 2025


def test_ingresos_que_cierran_no_dicen_nada():
    assert validacion.revisar(_datos({
        "ingresos": {2025: 2_023_994_000.0},
        "costo_ventas": {2025: 1_436_594_000.0},
        "ganancia_bruta": {2025: 587_400_000.0},
    })) == []


def test_un_redondeo_de_presentacion_no_llena_la_pantalla_de_avisos():
    assert validacion.revisar(_datos({
        "ingresos": {2025: 2_024_000_000.0},
        "costo_ventas": {2025: 1_436_594_000.0},
        "ganancia_bruta": {2025: 587_400_000.0},
    })) == []


# ------------------------------------------------------- activo = pasivo + patrimonio

def test_balance_suma_el_minoritario_cuando_el_patrimonio_no_lo_incluye():
    datos = _datos(
        {"activo_total": {2025: 1000.0}, "pasivo_total": {2025: 700.0},
         "patrimonio": {2025: 250.0}, "minoritario": {2025: 50.0}},
        {"patrimonio": {2025: {"etiqueta": "StockholdersEquity"}}},
    )
    assert validacion.revisar(datos) == []


def test_balance_no_cuenta_el_minoritario_dos_veces():
    # Con la etiqueta que ya lo incluye, sumarlo aparte romperia una identidad
    # que en realidad cierra.
    datos = _datos(
        {"activo_total": {2025: 1000.0}, "pasivo_total": {2025: 700.0},
         "patrimonio": {2025: 300.0}, "minoritario": {2025: 50.0}},
        {"patrimonio": {2025: {
            "etiqueta": "StockholdersEquityIncludingPortionAttributableToNoncontrollingInterest"}}},
    )
    assert validacion.revisar(datos) == []


def test_balance_contempla_el_patrimonio_temporal():
    # Tesla 2019: 643 M de participaciones rescatables que no son ni pasivo ni
    # patrimonio. Sin este termino la ecuacion fallaba por 1,9%.
    datos = _datos(
        {"activo_total": {2019: 34_309e6}, "pasivo_total": {2019: 26_199e6},
         "patrimonio": {2019: 6_618e6}, "minoritario": {2019: 849e6},
         "minoritario_rescatable": {2019: 643e6}},
        {"patrimonio": {2019: {"etiqueta": "StockholdersEquity"}}},
        anios=(2019,),
    )
    assert validacion.revisar(datos) == []


def test_balance_que_de_verdad_no_cierra_se_marca_como_grave():
    datos = _datos(
        {"activo_total": {2025: 1000.0e6}, "pasivo_total": {2025: 700.0e6},
         "patrimonio": {2025: 100.0e6}},
        {"patrimonio": {2025: {"etiqueta": "StockholdersEquity"}}},
    )
    hallazgos = validacion.revisar(datos)
    assert [h.severidad for h in hallazgos] == ["grave"]


# --------------------------------------------------------------- EPS y splits

def test_eps_que_no_coincide_con_la_division_es_aviso_no_grave():
    datos = _datos({
        "ganancia_neta": {2025: 100e6}, "acciones_dil": {2025: 50e6},
        "eps_diluido": {2025: 8.00},   # deberia ser 2,00
    })
    hallazgos = validacion.revisar(datos)
    assert [h.severidad for h in hallazgos] == ["aviso"]


def test_eps_cerca_de_cero_no_se_evalua():
    # Con la ganancia al borde de cero, el porcentaje se dispara sin que pase
    # nada: un centavo de diferencia da cientos por ciento.
    datos = _datos({
        "ganancia_neta": {2025: 1e6}, "acciones_dil": {2025: 50e6},
        "eps_diluido": {2025: 0.02},
    })
    assert validacion.revisar(datos) == []


def test_hallazgos_ordenados_por_gravedad_y_despues_por_año():
    datos = _datos(
        {"ingresos": {2020: 1000e6, 2025: 1000e6},
         "costo_ventas": {2020: 900e6, 2025: 900e6},
         "ganancia_bruta": {2020: 500e6, 2025: 500e6},
         "ganancia_neta": {2025: 100e6}, "acciones_dil": {2025: 50e6},
         "eps_diluido": {2025: 8.00}},
        anios=(2020, 2025),
    )
    hallazgos = validacion.revisar(datos)
    assert [(h.severidad, h.anio) for h in hallazgos] == [
        ("grave", 2025), ("grave", 2020), ("aviso", 2025)]


# --------------------------------------- el orden de las etiquetas de ingresos

def test_revenues_gana_a_la_etiqueta_de_contratos():
    # Sin nada con que desempatar, `Revenues` es el total de la cara del estado
    # y la de contratos solo la parte bajo ASC 606. Si el orden se invierte,
    # vuelve el error de BE.
    etiquetas = POR_CLAVE["ingresos"].etiquetas
    assert etiquetas.index("Revenues") < etiquetas.index(
        "RevenueFromContractWithCustomerExcludingAssessedTax")


def _facts_ingresos(**por_etiqueta: float) -> dict:
    return facts_de(us_gaap={
        etiqueta: bloque(hecho(valor, start="2015-01-01", end="2015-12-31"))
        for etiqueta, valor in por_etiqueta.items()
    })


def _crudo(valor: float, etiqueta: str) -> dict:
    return {2015: {"valor": valor, "etiqueta": etiqueta}}


def test_la_identidad_corrige_una_etiqueta_de_ingresos_que_no_es_el_total():
    # Apogee: `Revenues` trae 72,7 M sobre un ejercicio de 934 M. El costo y la
    # ganancia bruta que publica la empresa apuntan a `SalesRevenueNet`.
    facts = _facts_ingresos(Revenues=72.7e6, SalesRevenueNet=933.9e6)
    crudo = _crudo(72.7e6, "Revenues")
    edgar._arbitrar_ingresos(
        facts, crudo, _crudo(725.4e6, "CostOfGoodsSold"),
        _crudo(208.5e6, "GrossProfit"), mes_cierre=12)
    assert crudo[2015]["etiqueta"] == "SalesRevenueNet"
    assert crudo[2015]["valor"] == 933.9e6
    assert crudo[2015]["por_identidad"] is True


def test_la_identidad_no_toca_lo_que_ya_cierra():
    facts = _facts_ingresos(Revenues=934e6, SalesRevenueNet=900e6)
    crudo = _crudo(934e6, "Revenues")
    edgar._arbitrar_ingresos(
        facts, crudo, _crudo(725.5e6, "CostOfGoodsSold"),
        _crudo(208.5e6, "GrossProfit"), mes_cierre=12)
    assert crudo[2015]["etiqueta"] == "Revenues"
    assert "por_identidad" not in crudo[2015]


def test_si_ningun_candidato_cierra_se_deja_el_que_estaba():
    # LendingTree: la ganancia bruta que publica no forma la identidad con
    # ninguna linea de ingresos. Inventar un reemplazo seria peor; queda el
    # elegido y `validacion.py` lo marca.
    facts = _facts_ingresos(Revenues=1_117e6)
    crudo = _crudo(1_117e6, "Revenues")
    edgar._arbitrar_ingresos(
        facts, crudo, _crudo(42.5e6, "CostOfRevenue"),
        _crudo(352e6, "GrossProfit"), mes_cierre=12)
    assert crudo[2015]["valor"] == 1_117e6
    assert "por_identidad" not in crudo[2015]


def test_sin_ganancia_bruta_no_hay_arbitraje():
    # Bancos y aseguradoras no publican ganancia bruta: ahi manda el orden de
    # preferencia, que para ese caso es el correcto.
    facts = _facts_ingresos(Revenues=14_989e6,
                            RevenueFromContractWithCustomerExcludingAssessedTax=1_577e6)
    crudo = _crudo(14_989e6, "Revenues")
    edgar._arbitrar_ingresos(facts, crudo, {}, {}, mes_cierre=12)
    assert crudo[2015]["valor"] == 14_989e6


# ------------------------------------------------- instantes fuera del cierre

def _concepto_instante(clave="activo_total", etiqueta="Assets") -> Concepto:
    return Concepto(clave=clave, etiquetas=(etiqueta,), tipo="instante")


def test_un_instante_de_marzo_no_es_el_balance_de_un_ejercicio_que_cierra_en_diciembre():
    # El balance de BE de 2018 salia del 31 de marzo: activo 1.214 M en lugar de
    # 1.522 M, patrimonio -2.213 M en lugar de -143 M. Numeros reales de la
    # empresa, del trimestre equivocado, dentro de un 10-K.
    trimestre = hecho(1_214e6, end="2018-03-31", filed="2020-03-31")
    cierre = hecho(1_522e6, end="2018-12-31", filed="2019-03-22")
    facts = facts_de(us_gaap={"Assets": bloque(trimestre, cierre)})
    salida = edgar._hechos_anuales(facts, "Assets", _concepto_instante(), mes_cierre=12)
    assert salida[2018]["val"] == 1_522e6


def test_sin_mes_de_cierre_conocido_no_se_filtra_nada():
    trimestre = hecho(1_214e6, end="2018-03-31", filed="2020-03-31")
    facts = facts_de(us_gaap={"Assets": bloque(trimestre)})
    assert edgar._hechos_anuales(facts, "Assets", _concepto_instante()) != {}


def test_el_cierre_de_52_semanas_de_principios_de_mes_sigue_valiendo():
    # Sandisk cierra el 3 de julio: es el cierre del ejercicio, no un trimestre.
    facts = facts_de(us_gaap={"Assets": bloque(hecho(500e6, end="2026-07-03"))})
    salida = edgar._hechos_anuales(facts, "Assets", _concepto_instante(), mes_cierre=7)
    assert salida[2026]["val"] == 500e6


def test_el_cierre_que_se_corre_al_mes_siguiente_sigue_valiendo():
    # Ejercicio de 52/53 semanas que cierra el 2 de enero: es el ejercicio
    # anterior, y el mes de cierre habitual es diciembre.
    facts = facts_de(us_gaap={"Assets": bloque(hecho(500e6, end="2019-01-02"))})
    salida = edgar._hechos_anuales(facts, "Assets", _concepto_instante(), mes_cierre=12)
    assert salida[2018]["val"] == 500e6


# ---------------------------------------------------- splits sobre el EPS

def _facts_split_eps(proporcion: float, neta_reexpresada: float | None = None) -> dict:
    """Un ejercicio 2019 presentado dos veces, la segunda despues de un split."""
    neta_2 = 1_000e6 if neta_reexpresada is None else neta_reexpresada
    return facts_de(us_gaap={
        "EarningsPerShareDiluted": bloque(
            hecho(10.0, start="2019-01-01", end="2019-12-31", filed="2020-02-01"),
            hecho(10.0 * proporcion, start="2019-01-01", end="2019-12-31",
                  filed="2023-02-01"),
            unidad="USD/shares",
        ),
        "NetIncomeLoss": bloque(
            hecho(1_000e6, start="2019-01-01", end="2019-12-31", filed="2020-02-01"),
            hecho(neta_2, start="2019-01-01", end="2019-12-31", filed="2023-02-01"),
        ),
    })


def test_el_split_se_deduce_del_eps_cuando_la_ganancia_neta_no_cambio():
    # Alphabet: hasta 2021 informo las acciones por clase, asi que no hay serie
    # de acciones donde ver el split de 20 a 1. El EPS cae a 1/20 y la ganancia
    # neta queda igual: eso solo puede ser un split.
    eventos = edgar._eventos_split_por_eps(
        _facts_split_eps(1 / 20), POR_CLAVE["eps_diluido"])
    assert len(eventos) == 1
    fecha, proporcion = eventos[0]
    assert fecha == "2023-02-01"
    assert round(proporcion) == 20  # en la escala de las acciones, no del EPS


def test_un_eps_reexpresado_con_otra_ganancia_no_es_un_split():
    # Si la ganancia neta tambien cambio, lo que hubo fue una reexpresion
    # contable (una operacion discontinuada, por ejemplo), no un split.
    eventos = edgar._eventos_split_por_eps(
        _facts_split_eps(1 / 20, neta_reexpresada=50e6), POR_CLAVE["eps_diluido"])
    assert eventos == []


def test_un_cambio_de_signo_en_el_eps_no_es_un_split():
    facts = _facts_split_eps(-3.0)
    assert edgar._eventos_split_por_eps(facts, POR_CLAVE["eps_diluido"]) == []


def test_una_proporcion_absurda_no_es_un_split():
    # Nu Holdings informa un ejercicio en miles y el mismo en unidades: el
    # cociente da 15.079. Ninguna empresa hace un split de quince mil a uno.
    assert not edgar._split_plausible(15_079.0)
    assert edgar._split_plausible(20.0)
    assert edgar._split_plausible(1 / 20)


# --------------------------------------------- datos descartados por escala

def test_un_año_de_acciones_en_otra_escala_se_descarta():
    serie = {
        2019: {"valor": 306_210.0}, 2020: {"valor": 405_394.0},
        2021: {"valor": 1_602_126_000.0}, 2022: {"valor": 4_676_977_000.0},
        2023: {"valor": 4_857_600_000.0},
    }
    assert sorted(edgar._quiebres_de_escala(serie)) == [2019, 2020]


def test_una_serie_de_acciones_normal_no_pierde_ningun_año():
    serie = {a: {"valor": v} for a, v in
             {2021: 16_865e6, 2022: 16_326e6, 2023: 15_813e6, 2024: 15_408e6}.items()}
    assert edgar._quiebres_de_escala(serie) == []


def test_con_menos_de_tres_años_no_se_descarta_nada():
    # Sin serie no hay contra que comparar, y descartar a ciegas es peor.
    assert edgar._quiebres_de_escala({2024: {"valor": 1.0}, 2025: {"valor": 5000.0}}) == []
