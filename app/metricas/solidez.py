"""
Metricas de solvencia y riesgo de quiebra.

Para un inversor que aguanta caidas del 50% sin vender, este es el grupo
eliminatorio. Una tesis equivocada sobre el crecimiento cuesta tiempo; una
tesis equivocada sobre la solvencia cuesta el capital entero. La empresa tiene
que poder sobrevivir el tiempo que la tesis tarde en materializarse.
"""

from __future__ import annotations

from .base import div, metrica, pct, resta, suma


@metrica("caja_neta", "Situacion de caja", "Solidez", formato="usd", panel=True,
         ayuda="Caja e inversiones menos deuda total (incluyendo leases). "
               "Positivo = caja neta, la empresa le debe a nadie. Negativo = "
               "deuda neta.",
         formula="Caja e inversiones de corto plazo − deuda total. "
                 "Positivo es caja neta.")
def caja_neta(e):
    dn = e.f("deuda_neta")
    return None if dn is None else -dn


@metrica("deuda_neta_ebitda", "Deuda neta / EBITDA", "Solidez", formato="x", panel=True,
         mejor="bajo", umbrales=(1.5, 4.0),
         ayuda="Cuantos años de EBITDA hacen falta para cancelar la deuda neta. "
               "Arriba de 4x la empresa deja de decidir su destino: lo deciden "
               "los acreedores. Debajo de 0 hay caja neta.",
         formula="(Deuda total con leases − caja) / EBITDA.")
def deuda_neta_ebitda(e):
    dn, ebitda = e.f("deuda_neta"), e.f("ebitda")
    if dn is None or ebitda is None or ebitda <= 0:
        return None
    return dn / ebitda


@metrica("cobertura_intereses", "Cobertura de intereses", "Solidez", formato="x", panel=True,
         mejor="alto", umbrales=(8, 2.5),
         ayuda="EBIT sobre gasto de intereses. Cuantas veces la operacion cubre "
               "el costo de la deuda. Debajo de 2x, cualquier tropiezo operativo "
               "se convierte en un problema de solvencia.",
         formula="EBIT / gasto por intereses.")
def cobertura_intereses(e):
    intereses = e.f("intereses")
    if intereses is None or abs(intereses) < 1:
        return None
    return div(e.f("ebit"), abs(intereses))


@metrica("deuda_patrimonio", "Deuda / Patrimonio", "Solidez", formato="x",
         mejor="bajo", umbrales=(0.5, 2.0),
         formula="Deuda total / patrimonio neto.",
         ayuda="Cuanta deuda hay por cada dolar de patrimonio. Es la medida "
               "clasica de apalancamiento; a diferencia de deuda/EBITDA, no "
               "depende de las ganancias, asi que sigue siendo legible cuando "
               "la empresa pierde plata.")
def deuda_patrimonio(e):
    p = e.f("patrimonio")
    return None if p is None or p <= 0 else div(e.f("deuda_total"), p)


@metrica("liquidez_corriente", "Liquidez corriente", "Solidez", formato="x", panel=True,
         mejor="alto", umbrales=(1.8, 1.0),
         ayuda="Activo corriente sobre pasivo corriente. Debajo de 1x la empresa "
               "no cubre con sus activos liquidos lo que vence en 12 meses.",
         formula="Activo corriente / pasivo corriente.")
def liquidez_corriente(e):
    return div(e.f("activo_corriente"), e.f("pasivo_corriente"))


@metrica("liquidez_acida", "Liquidez acida", "Solidez", formato="x",
         mejor="alto", umbrales=(1.2, 0.6),
         ayuda="Igual que la anterior pero sin contar el inventario, que es lo "
               "mas dificil de convertir en caja rapido.",
         formula="(Activo corriente − inventario) / pasivo corriente.")
def liquidez_acida(e):
    ac = resta(e.f("activo_corriente"), e.f("inventario"))
    return div(ac, e.f("pasivo_corriente"))


@metrica("anios_deuda_fcf", "Años de FCF para pagar deuda", "Solidez", formato="anios",
         mejor="bajo", umbrales=(3, 10),
         ayuda="Deuda neta dividida caja libre anual. Mas intuitivo que el "
               "multiplo de EBITDA: cuantos años de generacion real de caja "
               "necesita para desendeudarse.",
         formula="Deuda neta / caja libre anual.")
def anios_deuda_fcf(e):
    dn, fcf = e.f("deuda_neta"), e.f("fcf")
    if dn is None or fcf is None or fcf <= 0:
        return None
    return max(dn, 0) / fcf


@metrica("altman_z", "Altman Z-Score", "Solidez", formato="score", panel=True,
         mejor="alto", umbrales=(3.0, 1.8),
         ayuda="Modelo clasico de riesgo de quiebra. Arriba de 3 zona segura; "
               "entre 1.8 y 3 zona gris; debajo de 1.8 riesgo alto de default a "
               "dos años. Fue calibrado para industriales: en bancos, "
               "aseguradoras y software leelo con pinzas.",
         formula="1,2×capital de trabajo/activo + 1,4×resultados "
                 "acumulados/activo + 3,3×EBIT/activo + "
                 "0,6×capitalizacion/pasivo + 1,0×ventas/activo.")
def altman_z(e):
    activo = e.f("activo_total")
    if not activo or activo <= 0:
        return None

    x1 = div(e.f("capital_trabajo"), activo)
    x2 = div(e.f("resultados_acumulados"), activo)
    x3 = div(e.f("ebit"), activo)
    x4 = div(e.market_cap, e.f("pasivo_total"))
    x5 = div(e.f("ingresos"), activo)

    if x3 is None or x5 is None or x4 is None:
        return None

    return (1.2 * (x1 or 0) + 1.4 * (x2 or 0) + 3.3 * x3 + 0.6 * x4 + 1.0 * x5)


@metrica("deuda_sobre_ev", "Deuda total / EV", "Solidez", formato="pct",
         mejor="bajo", umbrales=(20, 60),
         ayuda="Que parte del valor de la empresa esta financiado con deuda. "
               "Alto significa que el equity es una opcion apalancada: si la "
               "tesis sale bien ganas mucho mas, si sale mal perdes todo.",
         formula="Deuda total / enterprise value × 100. Que parte de la "
                 "empresa financian los acreedores y no vos.")
def deuda_sobre_ev(e):
    return pct(e.f("deuda_total"), e.ev)



@metrica("meses_de_caja", "Meses de caja", "Solidez", formato="num",
         mejor="alto", umbrales=(24, 12), panel=True,
         ayuda="Cuantos meses de operacion cubre la caja al ritmo actual de "
               "quema. Solo se calcula si la empresa esta quemando caja: en una "
               "que genera, no significa nada y queda vacio. Debajo de 12 meses "
               "la empresa va a tener que emitir acciones o tomar deuda, y va a "
               "hacerlo en las condiciones que le toquen, no en las que elija.",
         formula="Caja e inversiones / (quema mensual de caja libre). "
                 "Solo se calcula si el FCF es negativo.")
def meses_de_caja(e):
    fcf = e.f("fcf")
    if fcf is None or fcf >= 0:
        return None  # no quema caja: la pregunta no aplica
    caja = e.f("caja_total")
    if caja is None or caja <= 0:
        return 0.0
    return caja / (abs(fcf) / 12)
