"""
Metricas de caja y calidad de las ganancias.

La ganancia contable es una opinion; la caja es un hecho. Este grupo existe para
detectar la distancia entre las dos. Cuando una empresa reporta ganancias
crecientes y su flujo de caja no las acompaña, casi siempre hay una explicacion
incomoda: cobranzas que no entran, inventario que no se vende, o criterios
contables que se fueron estirando.
"""

from __future__ import annotations

from .base import div, metrica, pct, promedio, resta, suma


@metrica("fcf_margen", "Margen de FCF", "Caja", formato="pct", panel=True,
         mejor="alto", umbrales=(15, 5),
         ayuda="Cuanta caja libre deja cada dolar vendido. Es el margen que "
               "no se puede maquillar: la ganancia contable admite criterios, "
               "la caja no.",
         formula="Caja libre / ingresos × 100.")
def fcf_margen(e):
    return pct(e.f("fcf"), e.f("ingresos"))


@metrica("fcf_conversion", "Conversion FCF / Ganancia", "Caja", formato="pct", panel=True,
         mejor="alto", umbrales=(90, 50),
         ayuda="Caja libre dividida ganancia neta. Por encima de 100% la empresa "
               "genera mas caja de la que reporta como ganancia: excelente señal. "
               "Por debajo de 50% sostenido, las ganancias son de papel.",
         formula="Caja libre / ganancia neta × 100.")
def fcf_conversion(e):
    return pct(e.f("fcf"), e.f("ganancia_neta"))


@metrica("fcf_conversion_prom5", "Conversion FCF prom 5a", "Caja", formato="pct",
         mejor="alto", umbrales=(90, 50),
         ayuda="La conversion de ganancia a caja promediada a 5 años, para "
               "que un ejercicio con capital de trabajo raro no distorsione "
               "la lectura. Debajo de 70% sostenido hay que entender por que "
               "la ganancia no llega a caja.",
         formula="Promedio de la conversion a caja de los ultimos 5 "
                 "ejercicios.")
def fcf_conversion_prom5(e):
    fcf, gn = e.serie("fcf"), e.serie("ganancia_neta")
    anios = sorted(set(fcf) & set(gn) & e.ventana(5))
    return promedio([pct(fcf[a], gn[a]) for a in anios])


@metrica("accruals_sloan", "Accruals ratio (Sloan)", "Caja", formato="pct", panel=True,
         mejor="bajo", umbrales=(0, 10),
         ayuda="(Ganancia neta - flujo operativo) sobre activo total. Richard "
               "Sloan mostro que las empresas con accruals altos rinden "
               "sistematicamente peor: la ganancia que no viene acompañada de "
               "caja tiende a revertirse. Arriba de 10% es una alerta seria.",
         formula="(Ganancia neta − flujo operativo) / activo total × "
                 "100.")
def accruals_sloan(e):
    brecha = resta(e.f("ganancia_neta"), e.f("flujo_operativo"))
    return pct(brecha, e.f("activo_total"))


@metrica("capex_ventas", "Capex / Ventas", "Caja", formato="pct",
         mejor="bajo", umbrales=(5, 15),
         ayuda="Cuanta inversion exige el negocio para sostenerse. Bajo es mejor: "
               "significa que el crecimiento no se come la caja.",
         formula="Capex / ingresos × 100.")
def capex_ventas(e):
    return pct(e.f("capex"), e.f("ingresos"))


@metrica("capex_dya", "Capex / Depreciacion", "Caja", formato="x",
         ayuda="Cerca de 1x la empresa apenas repone lo que se le gasta (capex "
               "de mantenimiento). Muy por encima, esta invirtiendo para crecer, "
               "y ahi hay que preguntarse a cuanto rinde ese capital nuevo. Muy "
               "por debajo sostenido, se esta descapitalizando.",
         formula="Capex / depreciacion y amortizacion. Arriba de 1 la "
                 "empresa invierte mas de lo que se le gasta.")
def capex_dya(e):
    return div(e.f("capex"), e.f("dya"))


@metrica("dso", "Dias de cobranza (DSO)", "Caja", formato="dias",
         mejor="bajo", umbrales=(45, 90),
         ayuda="Dias que tarda en cobrar. Si sube año a año mientras las ventas "
               "crecen, puede estar vendiendo con condiciones cada vez peores "
               "para sostener el crecimiento.",
         formula="Cuentas por cobrar / ingresos × 365.")
def dso(e):
    return div(e.f("por_cobrar"), div(e.f("ingresos"), 365))


@metrica("dio", "Dias de inventario (DIO)", "Caja", formato="dias",
         mejor="bajo", umbrales=(60, 150),
         ayuda="Cuantos dias tarda el inventario en venderse. Subiendo sin "
               "que suban las ventas suele anticipar una rebaja de precios o "
               "un castigo contable.",
         formula="Inventario / costo de ventas × 365.")
def dio(e):
    return div(e.f("inventario"), div(e.f("costo_ventas"), 365))


@metrica("dpo", "Dias de pago (DPO)", "Caja", formato="dias",
         mejor="alto", umbrales=(60, 20),
         ayuda="Cuantos dias tarda en pagarle a sus proveedores. Alto es "
               "bueno: se financia con ellos gratis. Pero un salto brusco "
               "puede ser señal de que esta estirando pagos porque no le "
               "alcanza la caja.",
         formula="Cuentas por pagar / costo de ventas × 365.")
def dpo(e):
    return div(e.f("por_pagar"), div(e.f("costo_ventas"), 365))


@metrica("ciclo_caja", "Ciclo de conversion de caja", "Caja", formato="dias",
         mejor="bajo", umbrales=(30, 100),
         ayuda="DSO + DIO - DPO. Dias que la plata queda inmovilizada en el "
               "circuito operativo. Negativo es excelente: los clientes financian "
               "el negocio (el modelo de Amazon o Mercado Libre).",
         formula="DSO + DIO − DPO.")
def ciclo_caja(e):
    partes = [dso(e), dio(e), dpo(e)]
    if partes[0] is None and partes[1] is None:
        return None
    return (partes[0] or 0) + (partes[1] or 0) - (partes[2] or 0)


@metrica("sbc_ingresos", "SBC / Ingresos", "Caja", formato="pct",
         mejor="bajo", umbrales=(3, 12),
         ayuda="Compensacion en acciones sobre ingresos. No sale de la caja, "
               "pero diluye. Arriba de 10% el accionista esta financiando la "
               "nomina con su propia participacion.",
         formula="Compensacion en acciones / ingresos × 100.")
def sbc_ingresos(e):
    return pct(e.f("sbc"), e.f("ingresos"))


@metrica("sbc_fcf", "SBC / FCF", "Caja", formato="pct", panel=True,
         mejor="bajo", umbrales=(10, 40),
         ayuda="Que porcion de la caja libre se va en compensacion en acciones. "
               "Es la forma mas directa de ver cuanto del FCF reportado es real "
               "para vos como accionista.",
         formula="Compensacion en acciones / caja libre × 100.")
def sbc_fcf(e):
    return pct(e.f("sbc"), e.f("fcf"))


