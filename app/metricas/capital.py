"""
Metricas de asignacion de capital.

Es el capitulo mas revelador y el que casi nadie mira. Una empresa puede tener
un negocio excelente y aun asi destruir valor si el management usa mal la caja:
recomprando acciones caras, comprando empresas a multiplos absurdos, o diluyendo
al accionista para pagar sueldos.

La pregunta que responde este grupo es: la plata que genera el negocio, a donde
va, y el accionista termina con mas o con menos?
"""

from __future__ import annotations

from .. import config
from .base import cagr, div, metrica, pct, promedio, resta, suma


def _wacc(e) -> float | None:
    """Costo promedio ponderado del capital, con CAPM del lado del equity.

    Es una estimacion, no una medicion. Sirve para contrastarla contra el ROIC,
    que es donde importa: si el ROIC no supera al WACC, crecer destruye valor.
    """
    beta = e.mercado.get("beta") or 1.0
    ke = config.TASA_LIBRE_RIESGO + beta * config.PRIMA_RIESGO_MERCADO

    equity = e.market_cap
    deuda = e.f("deuda_total") or 0.0
    if not equity or equity <= 0:
        return None

    intereses = abs(e.f("intereses") or 0.0)
    kd = div(intereses, deuda) if deuda > 0 else 0.0
    kd = min(max(kd or 0.05, 0.02), 0.20)
    tasa = e.f("tasa_impositiva")
    tasa = 0.21 if tasa is None else tasa

    total = equity + deuda
    return (equity * ke + deuda * kd * (1 - tasa)) / total


@metrica("wacc", "WACC estimado", "Capital", formato="pct",
         ayuda="Costo del capital estimado por CAPM. Es la valla que el ROIC "
               "tiene que superar para que el crecimiento sume valor.",
         formula="Costo del capital por CAPM: tasa libre de riesgo + "
                 "beta × prima de riesgo, ponderado con el costo de la "
                 "deuda despues de impuestos.")
def wacc(e):
    w = _wacc(e)
    return None if w is None else w * 100


@metrica("spread_roic_wacc", "ROIC - WACC", "Capital", formato="pct", panel=True,
         mejor="alto", umbrales=(6, 0),
         ayuda="La diferencia entre lo que la empresa gana con su capital y lo "
               "que ese capital le cuesta. Positivo: cada dolar reinvertido crea "
               "valor. Negativo: la empresa crece y destruye valor al mismo "
               "tiempo, y lo mejor que podria hacer es repartir la caja.",
         formula="ROIC − WACC, en puntos porcentuales.")
def spread_roic_wacc(e):
    from .rentabilidad import roic_prom_5a
    r = roic_prom_5a(e)
    w = _wacc(e)
    return None if r is None or w is None else r - w * 100


@metrica("var_acciones_5a", "Variacion acciones 5a", "Capital", formato="pct", panel=True,
         mejor="bajo", umbrales=(-2, 5),
         ayuda="Cambio porcentual anual compuesto en la cantidad de acciones "
               "diluidas. Negativo = recompras netas, tu porcion de la empresa "
               "crece sin que hagas nada. Positivo = dilucion, cada año tenes "
               "menos empresa por la misma plata.",
         formula="Variacion anual del conteo de acciones diluidas en 5 "
                 "años. La serie se corrige por splits antes de "
                 "comparar.")
def var_acciones_5a(e):
    serie = e.serie("acciones_dil")
    anios = sorted(set(serie) & e.ventana(6))
    if len(anios) < 5:
        return None
    ini, fin = anios[0], anios[-1]
    return cagr(serie[ini], serie[fin], fin - ini)


@metrica("var_acciones_10a", "Variacion acciones 10a", "Capital", formato="pct",
         mejor="bajo", umbrales=(-2, 5),
         ayuda="La historia larga de dilucion, que es dificil de disimular. "
               "Diez años de emision constante dicen mas sobre como piensa la "
               "direccion que cualquier presentacion a inversores.",
         formula="Variacion anual del conteo de acciones diluidas en 10 "
                 "años, corregida por splits.")
def var_acciones_10a(e):
    serie = e.serie("acciones_dil")
    anios = sorted(serie)
    if len(anios) < 8:
        return None
    ini, fin = anios[0], anios[-1]
    return cagr(serie[ini], serie[fin], fin - ini)


@metrica("payout", "Payout de dividendos", "Capital", formato="pct",
         mejor="bajo", umbrales=(50, 90),
         ayuda="Dividendos sobre ganancia neta. Arriba de 90% el dividendo no "
               "esta cubierto por las ganancias y es candidato a recorte.",
         formula="Dividendos pagados / ganancia neta × 100.")
def payout(e):
    return pct(e.f("dividendos"), e.f("ganancia_neta"))


@metrica("payout_fcf", "Payout sobre FCF", "Capital", formato="pct",
         mejor="bajo", umbrales=(50, 90),
         ayuda="La version honesta del payout: dividendos sobre caja libre, no "
               "sobre ganancia contable. Un dividendo que se paga con deuda "
               "aparece aca y no en el payout tradicional.",
         formula="Dividendos pagados / caja libre × 100.")
def payout_fcf(e):
    return pct(e.f("dividendos"), e.f("fcf"))


@metrica("recompras_sobre_fcf", "Recompras / FCF", "Capital", formato="pct",
         ayuda="Cuanta caja libre se destina a recomprar acciones. Es bueno o "
               "malo segun el precio al que se recompro: mirá el grafico de "
               "recompras contra cotizacion en la pestaña de Detalle.",
         formula="Recompras de acciones / caja libre × 100.")
def recompras_sobre_fcf(e):
    return pct(e.f("recompras"), e.f("fcf"))


@metrica("reinversion", "Tasa de reinversion", "Capital", formato="pct",
         ayuda="Capex + adquisiciones sobre flujo operativo. Cuanto de lo que "
               "genera vuelve al negocio en lugar de ir al accionista.",
         formula="(Capex + adquisiciones) / flujo operativo × 100.")
def reinversion(e):
    invertido = suma(e.f("capex"), e.f("adquisiciones"))
    return pct(invertido, e.f("flujo_operativo"))


@metrica("caja_devuelta_5a", "Caja devuelta al accionista 5a", "Capital", formato="usd",
         ayuda="Suma de dividendos y recompras de los ultimos 5 ejercicios, en "
               "dolares. Contrastalo con la capitalizacion actual.",
         formula="Suma de dividendos y recompras de los ultimos 5 "
                 "ejercicios.")
def caja_devuelta_5a(e):
    valores = e.ultimos("retorno_accionista", 5)
    return sum(valores) if valores else None


@metrica("goodwill_sobre_activo", "Goodwill / Activo", "Capital", formato="pct",
         mejor="bajo", umbrales=(15, 40),
         ayuda="Que parte del activo es el sobreprecio pagado en adquisiciones. "
               "Muy alto significa que la empresa crecio comprando, y que hay "
               "riesgo de cargos por deterioro si esas compras no rinden.",
         formula="Goodwill / activo total × 100.")
def goodwill_sobre_activo(e):
    return pct(e.f("goodwill"), e.f("activo_total"))



@metrica("payout_real", "Payout real (div + recompras)", "Capital", formato="pct",
         mejor="bajo", umbrales=(70, 100), panel=True,
         ayuda="Dividendos MAS recompras netas de emision, sobre la caja libre. "
               "Es el payout que importa: el tradicional mira solo el dividendo "
               "contra la ganancia contable y deja afuera las dos cosas que mas "
               "plata mueven. Por encima de 100% la empresa esta devolviendo mas "
               "de lo que genera, y eso sale de deuda o de vender activos.",
         formula="(Dividendos + recompras − emision de acciones) / caja "
                 "libre × 100.")
def payout_real(e):
    devuelto = suma(e.f("dividendos"), e.f("recompras"))
    neto = resta(devuelto, e.f("emision_acciones"))
    return pct(neto, e.f("fcf"))
