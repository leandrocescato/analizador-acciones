"""
Metricas de rentabilidad y calidad del negocio.

El ROIC es el numero mas importante de todos: mide cuanto gana la empresa por
cada dolar de capital que le pusieron. Un negocio que sostiene ROIC alto durante
una decada tiene una ventaja competitiva real; uno que lo tuvo y lo perdio esta
avisando que la ventaja se erosiono, y ahi es donde vive la value trap.
"""

from __future__ import annotations

from .base import desvio, div, metrica, pct, promedio, resta


@metrica("roic", "ROIC", "Rentabilidad", formato="pct", panel=True,
         mejor="alto", umbrales=(15, 7),
         ayuda="NOPAT sobre capital invertido (patrimonio + deuda - caja). "
               "Por encima de 15% sostenido hay ventaja competitiva. Por debajo "
               "del costo de capital, la empresa destruye valor cuando crece.",
         formula="NOPAT / capital invertido × 100. NOPAT = EBIT × (1 − "
                 "tasa efectiva). Capital invertido = patrimonio + "
                 "deuda total − caja.")
def roic(e):
    return pct(e.f("nopat"), e.f("capital_invertido"))


@metrica("roic_prom_5a", "ROIC promedio 5a", "Rentabilidad", formato="pct", panel=True,
         mejor="alto", umbrales=(15, 7),
         ayuda="El ROIC de un solo año puede ser un accidente. Este es el que "
               "importa para juzgar la calidad estructural del negocio.",
         formula="Promedio simple del ROIC de los ultimos 5 ejercicios "
                 "de la empresa.")
def roic_prom_5a(e):
    nopat, capital = e.serie("nopat"), e.serie("capital_invertido")
    anios = sorted(set(nopat) & set(capital) & e.ventana(5))
    return promedio([pct(nopat[a], capital[a]) for a in anios])


@metrica("roic_ex_gw", "ROIC ex-goodwill", "Rentabilidad", formato="pct",
         mejor="alto", umbrales=(20, 10),
         ayuda="ROIC sacando goodwill e intangibles del capital invertido. "
               "Mide la calidad del negocio operativo sin el precio que la "
               "empresa pago por sus adquisiciones. Si este numero es mucho mas "
               "alto que el ROIC normal, el negocio es bueno pero la empresa "
               "pago de mas comprando.",
         formula="Igual al ROIC pero restandole al capital el goodwill "
                 "y los intangibles. Solo se publica si lo que queda "
                 "supera el 15% del capital.")
def roic_ex_gw(e):
    return pct(e.f("nopat"), e.f("capital_invertido_ex_gw"))


@metrica("roic_incremental", "ROIC incremental 5a", "Rentabilidad", formato="pct",
         panel=True, mejor="alto", umbrales=(15, 5),
         ayuda="Variacion del NOPAT dividida la variacion del capital invertido "
               "en 5 años. Responde la pregunta que casi nadie hace: el capital "
               "NUEVO que la empresa esta poniendo, a cuanto rinde? Un ROIC "
               "historico alto con incremental bajo significa que el negocio "
               "bueno ya esta maduro y lo nuevo no rinde.",
         formula="(NOPAT de hoy − NOPAT de hace 5 años) / (capital "
                 "invertido de hoy − capital invertido de hace 5 años) "
                 "× 100.")
def roic_incremental(e):
    nopat, capital = e.serie("nopat"), e.serie("capital_invertido")
    comunes = sorted(set(nopat) & set(capital) & e.ventana(6))
    if len(comunes) < 5:
        return None
    ini, fin = comunes[0], comunes[-1]
    d_nopat = resta(nopat[fin], nopat[ini])
    d_capital = resta(capital[fin], capital[ini])
    if d_capital is None or d_capital <= 0:
        return None
    return pct(d_nopat, d_capital)


@metrica("roce", "ROCE", "Rentabilidad", formato="pct",
         mejor="alto", umbrales=(18, 8),
         ayuda="EBIT sobre capital empleado (activo total - pasivo corriente). "
               "Variante del ROIC antes de impuestos.",
         formula="EBIT / (activo total − pasivo corriente) × 100.")
def roce(e):
    empleado = resta(e.f("activo_total"), e.f("pasivo_corriente"))
    return pct(e.f("ebit"), empleado)


@metrica("roe", "ROE", "Rentabilidad", formato="pct",
         mejor="alto", umbrales=(18, 8),
         ayuda="Retorno sobre patrimonio. Se puede inflar con deuda: un ROE alto "
               "con ROIC bajo es apalancamiento, no calidad.",
         formula="Ganancia neta / patrimonio neto × 100.")
def roe(e):
    return pct(e.f("ganancia_neta"), e.f("patrimonio"))


@metrica("roa", "ROA", "Rentabilidad", formato="pct",
         mejor="alto", umbrales=(10, 3),
         ayuda="Ganancia neta sobre el activo total. Cuanto rinde cada dolar "
               "del balance, sin importar como se financio. Es la vara "
               "natural para bancos y para cualquier negocio intensivo en "
               "activos.",
         formula="Ganancia neta / activo total × 100.")
def roa(e):
    return pct(e.f("ganancia_neta"), e.f("activo_total"))


@metrica("margen_bruto", "Margen bruto", "Rentabilidad", formato="pct", panel=True,
         mejor="alto", umbrales=(40, 20),
         ayuda="Poder de fijacion de precios. Su tendencia a lo largo de los años "
               "dice mas que su nivel absoluto.",
         formula="Ganancia bruta / ingresos × 100.")
def margen_bruto(e):
    return pct(e.f("ganancia_bruta"), e.f("ingresos"))


@metrica("margen_operativo", "Margen operativo", "Rentabilidad", formato="pct", panel=True,
         mejor="alto", umbrales=(18, 6),
         ayuda="Lo que queda de cada dolar de venta despues de todos los "
               "costos del negocio, antes de intereses e impuestos. Es la "
               "medida mas limpia de la eficiencia operativa porque no la "
               "afecta como este financiada.",
         formula="EBIT / ingresos × 100.")
def margen_operativo(e):
    return pct(e.f("ebit"), e.f("ingresos"))


@metrica("margen_neto", "Margen neto", "Rentabilidad", formato="pct",
         mejor="alto", umbrales=(12, 4),
         formula="Ganancia neta / ingresos × 100.",
         ayuda="Lo que queda de cada dolar de venta al final de todo. Menos "
               "util que el operativo para comparar entre empresas, porque lo "
               "mueven la deuda, los impuestos y los extraordinarios, pero es "
               "el que termina en tu bolsillo.")
def margen_neto(e):
    return pct(e.f("ganancia_neta"), e.f("ingresos"))


@metrica("margen_op_prom10", "Margen operativo prom 10a", "Rentabilidad", formato="pct",
         mejor="alto", umbrales=(18, 6),
         ayuda="El margen operativo promedio de una decada, que incluye al "
               "menos una recesion. Es la referencia contra la cual juzgar si "
               "el margen de hoy esta inflado o deprimido.",
         formula="Promedio del margen operativo de los ultimos 10 ejercicios.")
def margen_op_prom10(e):
    ebit, ing = e.serie("ebit"), e.serie("ingresos")
    anios = sorted(set(ebit) & set(ing) & e.ventana(10))
    return promedio([pct(ebit[a], ing[a]) for a in anios])


@metrica("margen_op_vs_prom", "Margen op. vs promedio 10a", "Rentabilidad", formato="pct",
         panel=True, mejor="neutro",
         ayuda="Diferencia en puntos entre el margen operativo actual y su "
               "promedio de 10 años. LA pregunta del deep value: un valor muy "
               "negativo significa que el margen esta deprimido. Si el motivo es "
               "ciclico, es oportunidad; si es estructural, es una trampa. "
               "Este numero te dice donde mirar, no cual de las dos es.",
         formula="Margen operativo actual − promedio de 10 años, en "
                 "puntos porcentuales.")
def margen_op_vs_prom(e):
    actual = margen_operativo(e)
    historico = margen_op_prom10(e)
    return None if actual is None or historico is None else actual - historico


@metrica("estabilidad_margen", "Desvio del margen op. 10a", "Rentabilidad", formato="pct",
         mejor="bajo", umbrales=(3, 10),
         ayuda="Desvio estandar del margen operativo en 10 años. Bajo = negocio "
               "predecible. Alto = ciclico o fragil, y exige mas margen de seguridad.",
         formula="Desvio estandar del margen operativo de 10 años, en "
                 "puntos.")
def estabilidad_margen(e):
    ebit, ing = e.serie("ebit"), e.serie("ingresos")
    anios = sorted(set(ebit) & set(ing) & e.ventana(10))
    return desvio([pct(ebit[a], ing[a]) for a in anios])


@metrica("rotacion_activos", "Rotacion de activos", "Rentabilidad", formato="x",
         mejor="alto", umbrales=(1.0, 0.4),
         ayuda="Cuantos dolares de venta genera cada dolar de activo. Junto "
               "con el margen explica el ROIC: se puede ganar plata vendiendo "
               "caro y poco, o barato y mucho.",
         formula="Ingresos / activo total.")
def rotacion_activos(e):
    return div(e.f("ingresos"), e.f("activo_total"))

