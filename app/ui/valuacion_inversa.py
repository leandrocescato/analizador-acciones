"""
DCF inverso — la herramienta central de valuacion de la app.

Un DCF normal te pide proyectar el futuro y escupe un valor. El problema es que
la proyeccion la elegis vos, asi que el resultado termina confirmando lo que ya
pensabas.

El DCF inverso da vuelta la pregunta: en lugar de estimar cuanto vale, calcula
QUE CRECIMIENTO TIENE QUE CUMPLIR LA EMPRESA para justificar el precio al que
cotiza hoy. Despues vos decidis una sola cosa, que es la unica que importa:
ese crecimiento, es plausible o no?

Es mucho mas honesto, porque convierte una estimacion imposible (el valor) en
un juicio acotado (si un 4% anual durante diez años es razonable para este
negocio).
"""

from __future__ import annotations

from ..metricas.base import promedio, resta, suma
from ..metricas.capital import _wacc

ANIOS_PROYECCION = 10
CRECIMIENTO_TERMINAL = 0.025


def valor_presente(fcf0: float, g: float, wacc: float,
                   anios: int = ANIOS_PROYECCION,
                   g_terminal: float = CRECIMIENTO_TERMINAL) -> float:
    """Valor presente del negocio: `años` de crecimiento g y despues perpetuidad."""
    wacc = max(wacc, g_terminal + 0.01)  # sin esto la perpetuidad se va a infinito

    valor, fcf = 0.0, fcf0
    for t in range(1, anios + 1):
        fcf *= (1 + g)
        valor += fcf / (1 + wacc) ** t

    terminal = fcf * (1 + g_terminal) / (wacc - g_terminal)
    return valor + terminal / (1 + wacc) ** anios


def crecimiento_implicito(e, fcf0: float | None = None,
                          wacc: float | None = None) -> dict | None:
    """Busca el crecimiento que iguala el valor calculado a la capitalizacion actual."""
    if fcf0 is None:
        # Se normaliza con 3 años para que un ejercicio raro no distorsione.
        fcf0 = promedio(e.ultimos("fcf", 3))
    if fcf0 is None or fcf0 <= 0:
        return None

    if wacc is None:
        wacc = _wacc(e) or 0.09

    objetivo = e.market_cap
    if not objetivo or objetivo <= 0:
        return None

    caja = e.f("caja_total") or 0.0
    deuda = e.f("deuda_total") or 0.0

    def equity(g: float) -> float:
        return valor_presente(fcf0, g, wacc) + caja - deuda

    lo, hi = -0.30, 0.60
    if equity(hi) < objetivo:
        return {"fcf0": fcf0, "wacc": wacc, "g_implicito": None,
                "mensaje": "Ni con 60% anual durante 10 años se justifica el precio actual."}
    if equity(lo) > objetivo:
        return {"fcf0": fcf0, "wacc": wacc, "g_implicito": None,
                "mensaje": "El precio actual esta por debajo del valor con FCF en caida del 30% anual."}

    for _ in range(80):
        medio = (lo + hi) / 2
        if equity(medio) < objetivo:
            lo = medio
        else:
            hi = medio

    return {"fcf0": fcf0, "wacc": wacc, "g_implicito": (lo + hi) / 2, "mensaje": None}


def escenarios(e, fcf0: float, wacc: float, tasas: list[float]) -> list[dict]:
    """Valor por accion bajo distintos supuestos de crecimiento."""
    acciones = e.f("acciones_dil")
    if not acciones:
        return []

    caja = e.f("caja_total") or 0.0
    deuda = e.f("deuda_total") or 0.0
    precio = e.mercado.get("precio")

    salida = []
    for g in tasas:
        equity = valor_presente(fcf0, g, wacc) + caja - deuda
        por_accion = equity / acciones
        salida.append({
            "crecimiento": g * 100,
            "valor_por_accion": por_accion,
            "margen": ((por_accion / precio - 1) * 100) if precio else None,
        })
    return salida

