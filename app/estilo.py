"""
Clasificacion de una empresa en VALUE, GROWTH, HIBRIDA o TURNAROUND.

POR QUE IMPORTA
---------------
Los mismos numeros significan cosas distintas segun el tipo de empresa. Un PER
de 40x es una alarma en una empresa que crece al 4% y es normal en una que
crece al 30%. Un FCF Yield del 1% descalifica a una madura y no dice nada de
una que esta reinvirtiendo todo. Sin saber de que tipo es, el semaforo miente
en las dos direcciones: pinta de rojo un crecimiento sano y de verde una
trampa barata.

Esta clasificacion decide que cuadro de ratios se muestra en el Detalle, con
que se compara cada numero, y cual es la pregunta que hay que contestar.

LA REGLA
--------
Se mira el crecimiento de ingresos por dos caminos —el ultimo ejercicio y el
CAGR de 3 años— porque un año suelto se distorsiona por efecto base, divisa,
adquisiciones o un calendario de 52/53 semanas. Manda el mas conservador de
los dos, salvo que difieran mucho, y en ese caso se avisa.

Dos casos que no son ninguno de los tres perfiles y hay que decirlo:

  - TURNAROUND: pierde plata y ademas crece poco. No es growth aunque no gane:
    es una reestructuracion, y lo que importa ahi es cuanta caja le queda.
  - CICLICA: bancos, energia, materiales, autos. Se analizan como value, pero
    su PER es contraciclico —barato en el pico, caro en el suelo— asi que hay
    que mirar valor libro y ganancias normalizadas del ciclo, no el PER.
"""

from __future__ import annotations

from . import perfiles

VALUE = "value"
GROWTH = "growth"
HIBRIDA = "hibrida"
TURNAROUND = "turnaround"

NOMBRES = {
    VALUE: "Value",
    GROWTH: "Growth",
    HIBRIDA: "Hibrida",
    TURNAROUND: "Turnaround",
}

COLORES = {
    VALUE: "#2f6f4e",
    GROWTH: "#8a4bbd",
    HIBRIDA: "#1f6fb2",
    TURNAROUND: "#a8562a",
}

# La pregunta que define la tesis en cada caso. Va en el encabezado del Detalle.
PREGUNTA = {
    VALUE: "Esta barata porque el mercado se equivoca, o porque el negocio se "
           "esta deteriorando de verdad?",
    GROWTH: "El crecimiento justifica el multiplo, y va a sostenerse el tiempo "
            "suficiente para que el multiplo no importe?",
    HIBRIDA: "Cuanto de la valuacion es calidad ya probada y cuanto es "
             "crecimiento que todavia hay que ver?",
    TURNAROUND: "Le alcanza la caja para llegar a ser rentable, y hay alguna "
                "prueba de que el deterioro se este frenando?",
}

# Umbrales de la regla. Estan en un solo lugar para poder discutirlos.
CRECIMIENTO_GROWTH = 15.0   # % anual: arriba de esto es growth
CRECIMIENTO_VALUE = 10.0    # % anual: abajo de esto es value
DIVERGENCIA_AVISO = 12.0    # puntos entre el año y el CAGR que ameritan aviso

# Rubros donde el ciclo domina el resultado y el PER se lee al reves.
_SECTORES_CICLICOS = (
    "energy", "basic materials", "materials", "industrials",
    "consumer cyclical", "financial services", "financial", "real estate",
)


def _crecimiento(emp) -> tuple[float | None, float | None]:
    """Crecimiento de ingresos del ultimo ejercicio y CAGR de 3 años."""
    serie = emp.serie("ingresos")
    if not serie:
        return (None, None)
    anios = sorted(emp.ventana(4) & set(serie))
    if len(anios) < 2:
        return (None, None)

    ultimo, previo = anios[-1], anios[-2]
    yoy = None
    if serie[previo] > 0:
        yoy = (serie[ultimo] / serie[previo] - 1) * 100

    cagr3 = None
    if len(anios) >= 3 and serie[anios[0]] > 0:
        periodos = ultimo - anios[0]
        if periodos > 0:
            cagr3 = ((serie[ultimo] / serie[anios[0]]) ** (1 / periodos) - 1) * 100

    return (yoy, cagr3)


def es_ciclica(emp) -> bool:
    """Cierto para los negocios donde el resultado lo manda el ciclo."""
    if emp.perfil in (perfiles.BANCO, perfiles.SEGUROS, perfiles.REIT):
        return True
    sector = (emp.sector or "").strip().lower()
    return any(c in sector for c in _SECTORES_CICLICOS)


def clasificar(emp, metricas: dict | None = None) -> dict:
    """Perfil de inversion de la empresa, con los numeros que lo sostienen.

    Devuelve:
        {"estilo": "value", "nombre": "Value", "razones": [...],
         "yoy": 4.2, "cagr3": 3.8, "ciclica": False, "avisos": [...]}
    """
    metricas = metricas or {}
    yoy, cagr3 = _crecimiento(emp)
    razones: list[str] = []
    avisos: list[str] = []

    # El crecimiento de referencia es el mas conservador de los dos caminos.
    candidatos = [v for v in (yoy, cagr3) if v is not None]
    crecimiento = min(candidatos) if candidatos else None

    if yoy is not None and cagr3 is not None and abs(yoy - cagr3) >= DIVERGENCIA_AVISO:
        avisos.append(
            f"El ultimo ejercicio crecio {yoy:+.1f}% y el promedio de 3 años "
            f"{cagr3:+.1f}%. Esa diferencia suele venir de una adquisicion, de "
            "un efecto base o de un cambio de calendario: conviene mirar de "
            "donde sale antes de proyectarla."
        )

    ganancia = emp.f("ganancia_neta")
    fcf = emp.f("fcf")
    pierde = ganancia is not None and ganancia < 0
    quema = fcf is not None and fcf < 0

    # --- turnaround: pierde plata y ademas no crece
    if pierde and (crecimiento is None or crecimiento < CRECIMIENTO_GROWTH):
        razones.append(
            f"Cerro el ultimo ejercicio en perdida y crece {crecimiento:.1f}%"
            if crecimiento is not None else
            "Cerro el ultimo ejercicio en perdida y no hay serie de ingresos"
        )
        razones.append("Perder plata sin crecer no es growth: es una reestructuracion")
        return _armar(TURNAROUND, razones, yoy, cagr3, emp, avisos)

    if crecimiento is None:
        razones.append("Sin serie de ingresos suficiente para clasificar")
        return _armar(VALUE, razones, yoy, cagr3, emp, avisos)

    # --- growth
    if crecimiento >= CRECIMIENTO_GROWTH:
        razones.append(f"Los ingresos crecen {crecimiento:.1f}% anual")
        if quema:
            razones.append("Reinvierte mas de lo que genera: la caja es negativa")
        elif fcf is not None:
            razones.append("Crece y ademas genera caja libre")
        return _armar(GROWTH, razones, yoy, cagr3, emp, avisos)

    # --- value
    if crecimiento < CRECIMIENTO_VALUE:
        razones.append(f"Los ingresos crecen {crecimiento:.1f}% anual")
        retorno = metricas.get("shareholder_yield")
        if retorno is not None and retorno > 0:
            razones.append(f"Devuelve {retorno:.1f}% al accionista entre dividendos y recompras")
        rendimiento = metricas.get("fcf_yield")
        if rendimiento is not None and rendimiento >= 5:
            razones.append(f"Genera un FCF Yield de {rendimiento:.1f}%")
        return _armar(VALUE, razones, yoy, cagr3, emp, avisos)

    # --- hibrida: crece entre 10 y 15 con rentabilidad alta
    razones.append(f"Crecimiento intermedio: {crecimiento:.1f}% anual")
    roic = metricas.get("roic_prom_5a") or metricas.get("roic")
    if roic is not None:
        razones.append(f"Con un ROIC de {roic:.1f}%, la calidad ya esta probada")
    razones.append("Se mira con los dos cuadros: el de value y el de growth")
    return _armar(HIBRIDA, razones, yoy, cagr3, emp, avisos)


def _armar(estilo, razones, yoy, cagr3, emp, avisos) -> dict:
    ciclica = es_ciclica(emp)
    if ciclica and estilo in (VALUE, HIBRIDA):
        avisos.append(
            "Es un negocio ciclico: su PER es contraciclico, parece barato en el "
            "pico del ciclo y caro en el suelo. Miralo contra el valor libro y "
            "contra la ganancia normalizada de un ciclo entero, no contra el PER."
        )
    return {
        "estilo": estilo,
        "nombre": NOMBRES[estilo],
        "color": COLORES[estilo],
        "pregunta": PREGUNTA[estilo],
        "razones": razones,
        "avisos": avisos,
        "yoy": yoy,
        "cagr3": cagr3,
        "ciclica": ciclica,
    }


# ------------------------------------------------------------------ cuadros

# Que ratios se muestran en el Detalle segun el estilo, con el nombre del
# bloque. Sale directo del marco: value se juzga por lo que ya genera, growth
# por la calidad y la durabilidad de lo que esta creciendo.

CUADRO_VALUE = [
    ("Valuacion", ["per", "per_normalizado", "p_vl", "ev_ebitda", "fcf_yield"]),
    ("Solvencia", ["deuda_neta_ebitda", "liquidez_corriente", "deuda_patrimonio",
                   "cobertura_intereses"]),
    ("Rentabilidad", ["roic", "roic_prom_5a", "roe", "margen_operativo"]),
    ("Retorno al accionista", ["div_yield", "payout_real", "var_acciones_5a",
                               "shareholder_yield"]),
]

CUADRO_GROWTH = [
    ("Crecimiento", ["cagr_ingresos_5a", "cagr_ingresos_10a", "cagr_fcf_5a",
                     "aceleracion_ingresos"]),
    ("Eficiencia", ["margen_bruto", "fcf_margen", "regla_40", "sbc_ingresos"]),
    ("Valuacion de crecimiento", ["ev_ventas", "ev_fcf", "peg", "fcf_yield"]),
    ("Riesgo de dilucion y caja", ["var_acciones_5a", "meses_de_caja",
                                   "sbc_fcf"]),
]

CUADRO_TURNAROUND = [
    ("Supervivencia", ["meses_de_caja", "deuda_neta_ebitda", "liquidez_corriente",
                       "cobertura_intereses", "altman_z"]),
    ("Se esta frenando la caida?", ["margen_op_vs_prom", "cagr_ingresos_5a",
                                    "piotroski", "anios_con_perdida"]),
    ("Que pagas por el intento", ["p_vl", "p_vl_tangible", "precio_vs_ncav",
                                  "ev_ventas"]),
    ("Dilucion", ["var_acciones_5a", "var_acciones_10a", "sbc_ingresos"]),
]


def cuadro(estilo: str) -> list[tuple[str, list[str]]]:
    """Los bloques de ratios que corresponden a ese estilo."""
    if estilo == GROWTH:
        return CUADRO_GROWTH
    if estilo == TURNAROUND:
        return CUADRO_TURNAROUND
    if estilo == HIBRIDA:
        # Los dos cuadros, sin repetir bloques.
        return CUADRO_VALUE + [CUADRO_GROWTH[0], CUADRO_GROWTH[1]]
    return CUADRO_VALUE
