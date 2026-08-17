"""
Metricas de valuacion.

Criterio de fondo: el PER es el multiplo mas popular y el menos confiable.
Ignora la deuda, ignora la caja, y usa una ganancia contable que puede estar
inflada o deprimida por un solo año. Por eso aca conviven varios multiplos
que se corrigen entre si:

  - EV/EBIT y EV/FCF neutralizan la estructura de capital.
  - El PER normalizado usa la ganancia promedio de 10 años: si la empresa esta
    en el piso del ciclo, el PER corriente la hace ver cara justo cuando esta barata.
  - El NCAV de Graham y el EPV de Greenwald son pisos de valor, no multiplos.
"""

from __future__ import annotations

from .base import div, metrica, pct, promedio, resta, suma


@metrica("per", "PER", "Valuacion", formato="x", panel=True,
         mejor="bajo", umbrales=(12, 30),
         ayuda="Precio sobre ganancia por accion. Util como referencia rapida, "
               "peligroso como unico criterio.",
         formula="Capitalizacion / ganancia neta. No usa el conteo de "
                 "acciones, que en empresas de doble clase viene "
                 "incompleto en EDGAR.")
def per(e):
    # Se calcula como capitalizacion sobre ganancia neta, que es identico a
    # precio sobre EPS pero no depende del conteo de acciones. Las empresas de
    # doble clase no publican un EPS consolidado en XBRL, y usar un conteo
    # viejo daba multiplos equivocados con toda la apariencia de correctos.
    r = div(e.market_cap, e.f("ganancia_neta"))
    if r is None:
        r = div(e.mercado.get("precio"), e.f("eps_diluido"))
    return None if r is None or r < 0 else r


@metrica("per_normalizado", "PER normalizado 10a", "Valuacion", formato="x", panel=True,
         mejor="bajo", umbrales=(15, 35),
         ayuda="Precio sobre la ganancia por accion PROMEDIO de los ultimos 10 "
               "ejercicios. Es la defensa contra comprar una ciclica en el pico "
               "de sus ganancias, o descartarla en el piso.",
         formula="Capitalizacion / promedio de la ganancia neta de 10 "
                 "años. Necesita al menos 5 ejercicios.")
def per_normalizado(e):
    ganancias = e.ultimos("ganancia_neta", 10)
    if len(ganancias) < 5:
        return None
    r = div(e.market_cap, promedio(ganancias))
    return None if r is None or r < 0 else r


@metrica("ev_ebit", "EV / EBIT", "Valuacion", formato="x", panel=True,
         mejor="bajo", umbrales=(10, 25),
         ayuda="El multiplo que mira un comprador de la empresa entera. "
               "Comparable entre empresas con distinto nivel de deuda.",
         formula="Enterprise value / resultado operativo.")
def ev_ebit(e):
    r = div(e.ev, e.f("ebit"))
    return None if r is None or r < 0 else r


@metrica("ev_ebitda", "EV / EBITDA", "Valuacion", formato="x",
         mejor="bajo", umbrales=(8, 18),
         ayuda="Popular en M&A. Ojo: ignora que la depreciacion tarde o temprano "
               "hay que reponerla con capex real.",
         formula="Enterprise value / (EBIT + depreciacion y "
                 "amortizacion).")
def ev_ebitda(e):
    r = div(e.ev, e.f("ebitda"))
    return None if r is None or r < 0 else r


@metrica("ev_fcf", "EV / FCF", "Valuacion", formato="x", panel=True,
         mejor="bajo", umbrales=(15, 35),
         ayuda="Mi multiplo preferido: caja libre real contra el valor total de "
               "la empresa. Lo mas dificil de maquillar contablemente.",
         formula="Enterprise value / caja libre.")
def ev_fcf(e):
    r = div(e.ev, e.f("fcf"))
    return None if r is None or r < 0 else r


@metrica("ev_ventas", "EV / Ventas", "Valuacion", formato="x",
         mejor="bajo", umbrales=(1.5, 6),
         ayuda="Ultimo recurso cuando la empresa no tiene ganancias. "
               "Solo comparable dentro de la misma industria.",
         formula="Enterprise value / ingresos.")
def ev_ventas(e):
    return div(e.ev, e.f("ingresos"))


@metrica("fcf_yield", "FCF Yield", "Valuacion", formato="pct", panel=True,
         mejor="alto", umbrales=(8, 3),
         ayuda="Caja libre anual dividida la capitalizacion. Es el rendimiento "
               "que te daria la empresa si te repartiera toda su caja libre. "
               "Compara este numero contra el bono a 10 años.",
         formula="Caja libre / capitalizacion × 100. FCF = flujo "
                 "operativo − capex.")
def fcf_yield(e):
    return pct(e.f("fcf"), e.market_cap)


@metrica("fcf_yield_post_sbc", "FCF Yield neto de SBC", "Valuacion", formato="pct",
         mejor="alto", umbrales=(7, 2),
         ayuda="Igual que el anterior pero descontando la compensacion en acciones. "
               "En software la diferencia entre los dos numeros suele ser brutal.",
         formula="(Caja libre − compensacion en acciones) / "
                 "capitalizacion × 100.")
def fcf_yield_post_sbc(e):
    return pct(e.f("fcf_post_sbc"), e.market_cap)


@metrica("earnings_yield", "Earnings Yield (Greenblatt)", "Valuacion", formato="pct",
         panel=True, mejor="alto", umbrales=(10, 4),
         ayuda="EBIT sobre Enterprise Value. La mitad de la 'formula magica' de "
               "Joel Greenblatt: mide cuanto rinde el negocio contra lo que "
               "cuesta comprarlo entero.",
         formula="EBIT / enterprise value × 100. Es la formula de "
                 "Greenblatt.")
def earnings_yield(e):
    return pct(e.f("ebit"), e.ev)


@metrica("p_vl", "Precio / Valor Libro", "Valuacion", formato="x",
         mejor="bajo", umbrales=(1.5, 5),
         ayuda="Contra el patrimonio contable. Relevante en bancos y en empresas "
               "con muchos activos fisicos; casi inutil en las de servicios.",
         formula="Capitalizacion / patrimonio neto.")
def p_vl(e):
    return div(e.market_cap, e.f("patrimonio"))


@metrica("p_vl_tangible", "Precio / Valor Libro tangible", "Valuacion", formato="x",
         mejor="bajo", umbrales=(2, 6),
         ayuda="Igual que el anterior pero sacando goodwill e intangibles: solo "
               "lo que existe de verdad si hay que liquidar.",
         formula="Capitalizacion / (patrimonio − goodwill − "
                 "intangibles).")
def p_vl_tangible(e):
    pt = e.f("patrimonio_tangible")
    return None if pt is None or pt <= 0 else div(e.market_cap, pt)


@metrica("div_yield", "Dividend Yield", "Valuacion", formato="pct",
         ayuda="Dividendo anual sobre precio. Se calcula con el monto en "
               "dolares por accion, no con el yield que publica Yahoo, porque "
               "ese viene sin escala declarada. El respaldo son los dividendos "
               "efectivamente pagados segun el ultimo estado de flujo de EDGAR, "
               "que incluye los extraordinarios.",
         formula="Dividendo anual por accion / precio × 100. Si Yahoo "
                 "no lo da, dividendos pagados del ultimo ejercicio / "
                 "capitalizacion.")
def div_yield(e):
    # El yield de Yahoo NO se puede usar: llega como 2.3 para un 2,3% y como
    # 0.19 para un 0,19%, sin nada que distinga una escala de la otra. La
    # heuristica "si es menor que 1 es fraccion" convertia el 0,19% de
    # Progressive en 19%: cien veces mas, y con formato impecable.
    monto = e.mercado.get("dividendo_anual")
    directo = pct(monto, e.mercado.get("precio"))
    if directo is not None:
        return directo
    # Respaldo auditado: lo que la empresa realmente giro en el ultimo ejercicio.
    return pct(e.f("dividendos"), e.market_cap)


@metrica("shareholder_yield", "Shareholder Yield", "Valuacion", formato="pct", panel=True,
         mejor="alto", umbrales=(6, 0),
         ayuda="Dividendos + recompras - emision de acciones, sobre la "
               "capitalizacion. Es el dividend yield honesto: una empresa que "
               "reparte 3% pero se diluye 4% te esta sacando plata, no dandotela.",
         formula="(Dividendos + recompras − emision de acciones) / "
                 "capitalizacion × 100.")
def shareholder_yield(e):
    devuelto = suma(e.f("dividendos"), e.f("recompras"))
    neto = resta(devuelto, e.f("emision_acciones"))
    return pct(neto, e.market_cap)


@metrica("precio_vs_ncav", "Precio / NCAV", "Valuacion", formato="x",
         mejor="bajo", umbrales=(1.0, 3.0),
         ayuda="NCAV de Graham = activo corriente menos TODO el pasivo. Por "
               "debajo de 1x estas comprando la empresa por menos que su capital "
               "de trabajo neto, con la operacion de regalo. Es rarisimo y suele "
               "indicar o una ganga historica o un negocio que quema caja.",
         formula="Capitalizacion / (activo corriente − pasivo total). "
                 "El NCAV de Graham; solo tiene sentido si es positivo.")
def precio_vs_ncav(e):
    ncav = resta(e.f("activo_corriente"), e.f("pasivo_total"))
    return None if ncav is None or ncav <= 0 else div(e.market_cap, ncav)


@metrica("epv", "EPV / Capitalizacion", "Valuacion", formato="x",
         mejor="alto", umbrales=(1.3, 0.8),
         ayuda="Earnings Power Value de Greenwald: NOPAT promedio de 8 años "
               "capitalizado al costo de capital, sin suponer NADA de crecimiento. "
               "Por encima de 1x, el precio actual no te esta cobrando el "
               "crecimiento futuro: te lo regalan.",
         formula="Valor de las ganancias sostenibles (EBIT promedio de "
                 "8 años, despues de impuestos, dividido el WACC) sobre "
                 "la capitalizacion.")
def epv(e):
    nopat_prom = promedio(e.ultimos("nopat", 8))
    if nopat_prom is None or nopat_prom <= 0:
        return None
    from .capital import _wacc
    wacc = _wacc(e) or 0.09
    valor_operativo = nopat_prom / max(wacc, 0.04)
    # Al valor del negocio se le suma la caja y se le resta la deuda.
    valor_equity = resta(suma(valor_operativo, e.f("caja_total")), e.f("deuda_total"))
    return div(valor_equity, e.market_cap)



@metrica("per_forward", "PER Forward (est.)", "Valuacion", formato="x", panel=True,
         mejor="bajo", umbrales=(12, 30),
         formula="Precio / ganancia por accion estimada para el proximo "
                 "ejercicio, segun el consenso que publica Yahoo Finance.",
         ayuda="OJO: NO es un dato reportado, es lo que un grupo de analistas "
               "espera. Es la unica familia de numeros de esta app que no sale "
               "de un balance auditado. Sirve para ver cuanto del precio actual "
               "depende de que esas expectativas se cumplan: si el PER es 30x y "
               "el forward 15x, el mercado esta pagando por una duplicacion de "
               "ganancias que todavia no ocurrio. El consenso tiende a ser "
               "optimista y se revisa a la baja al acercarse la fecha, asi que "
               "leelo como el mejor escenario, no como el probable.")
def per_forward(e):
    valor = e.mercado.get("per_forward")
    if valor is None:
        # Respaldo: el EPS estimado contra el precio de hoy.
        valor = div(e.mercado.get("precio"), e.mercado.get("eps_forward"))
    return None if valor is None or valor < 0 else valor
