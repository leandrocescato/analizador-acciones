"""
Senales compuestas: Piotroski F-Score y Beneish M-Score.

Son dos modelos academicos que resumen en un solo numero preguntas que de otra
forma exigen leer varios estados contables completos.

  - PIOTROSKI (1999) fue diseñado exactamente para el problema de Leandro:
    dentro del universo de acciones baratas, separar las que estan mejorando
    fundamentalmente de las que se estan deteriorando. Es el filtro anti-value-trap.

  - BENEISH (1999) estima la probabilidad de que los estados contables esten
    manipulados. Detecto a Enron antes del escandalo.

Ninguno de los dos decide nada por vos. Un F-Score de 8 no hace buena a una
empresa mala, y un M-Score alto no prueba fraude. Son alertas para ir a leer.
"""

from __future__ import annotations

from .base import div, metrica, pct, resta


def _anio_par(e) -> tuple[int, int] | None:
    """Ultimo ejercicio completo y el anterior, alineados sobre datos que existen."""
    base_series = set(e.serie("ganancia_neta")) & set(e.serie("activo_total"))
    if len(base_series) < 2:
        return None
    ordenados = sorted(base_series)
    t = ordenados[-1]
    return (t, t - 1) if (t - 1) in base_series else None


@metrica("piotroski", "Piotroski F-Score", "Senales", formato="score", panel=True,
         mejor="alto", umbrales=(7, 3),
         ayuda="Nueve chequeos binarios sobre rentabilidad, solvencia y "
               "eficiencia, comparando el ultimo ejercicio contra el anterior. "
               "De 8 a 9: la empresa esta mejorando en todos los frentes. "
               "De 0 a 3: se esta deteriorando, y una accion barata que ademas "
               "empeora suele ser una trampa, no una oportunidad.",
         formula="Nueve chequeos binarios que suman un punto cada uno: "
                 "ROA positivo, flujo operativo positivo, ROA "
                 "mejorando, caja mayor que la ganancia, menos deuda, "
                 "mejor liquidez, sin emitir acciones, mejor margen "
                 "bruto y mejor rotacion de activos.")
def piotroski(e):
    par = _anio_par(e)
    if par is None:
        return None
    t, p = par
    v = lambda k, a: e.f(k, a)

    puntos = 0

    # --- Rentabilidad (4 puntos)
    roa_t = div(v("ganancia_neta", t), v("activo_total", t))
    roa_p = div(v("ganancia_neta", p), v("activo_total", p))
    cfo_t = v("flujo_operativo", t)

    if roa_t is not None and roa_t > 0:
        puntos += 1
    if cfo_t is not None and cfo_t > 0:
        puntos += 1
    if roa_t is not None and roa_p is not None and roa_t > roa_p:
        puntos += 1
    # Calidad de la ganancia: la caja operativa supera a la ganancia contable.
    if cfo_t is not None and v("ganancia_neta", t) is not None and cfo_t > v("ganancia_neta", t):
        puntos += 1

    # --- Solvencia y liquidez (3 puntos)
    apal_t = div(v("deuda_lp", t), v("activo_total", t))
    apal_p = div(v("deuda_lp", p), v("activo_total", p))
    if apal_t is not None and apal_p is not None and apal_t < apal_p:
        puntos += 1

    liq_t = div(v("activo_corriente", t), v("pasivo_corriente", t))
    liq_p = div(v("activo_corriente", p), v("pasivo_corriente", p))
    if liq_t is not None and liq_p is not None and liq_t > liq_p:
        puntos += 1

    acc_t, acc_p = v("acciones_dil", t), v("acciones_dil", p)
    if acc_t is not None and acc_p is not None and acc_t <= acc_p * 1.005:
        puntos += 1

    # --- Eficiencia operativa (2 puntos)
    mb_t = div(v("ganancia_bruta", t), v("ingresos", t))
    mb_p = div(v("ganancia_bruta", p), v("ingresos", p))
    if mb_t is not None and mb_p is not None and mb_t > mb_p:
        puntos += 1

    rot_t = div(v("ingresos", t), v("activo_total", t))
    rot_p = div(v("ingresos", p), v("activo_total", p))
    if rot_t is not None and rot_p is not None and rot_t > rot_p:
        puntos += 1

    return float(puntos)


@metrica("beneish_m", "Beneish M-Score", "Senales", formato="num",
         mejor="bajo", umbrales=(-2.5, -1.78),
         ayuda="Estima la probabilidad de manipulacion contable a partir de ocho "
               "indices. Por encima de -1.78 el modelo clasifica a la empresa "
               "como probable manipuladora. No es una acusacion: es un motivo "
               "para leer las notas a los estados contables antes de comprar.",
         formula="Ocho indices ponderados sobre cobranzas, margen "
                 "bruto, calidad del activo, ventas, depreciacion, "
                 "gastos, apalancamiento y accruals.")
def beneish_m(e):
    par = _anio_par(e)
    if par is None:
        return None
    t, p = par
    v = lambda k, a: e.f(k, a)

    ventas_t, ventas_p = v("ingresos", t), v("ingresos", p)
    activo_t, activo_p = v("activo_total", t), v("activo_total", p)
    if not all([ventas_t, ventas_p, activo_t, activo_p]):
        return None

    # DSRI: dias de venta en cuentas por cobrar
    dsri = div(div(v("por_cobrar", t), ventas_t), div(v("por_cobrar", p), ventas_p)) or 1.0

    # GMI: deterioro del margen bruto (>1 = empeoro)
    mb_t = div(resta(ventas_t, v("costo_ventas", t)), ventas_t)
    mb_p = div(resta(ventas_p, v("costo_ventas", p)), ventas_p)
    gmi = div(mb_p, mb_t) or 1.0

    # AQI: calidad del activo (proporcion de activos no corrientes ni fisicos)
    def _no_calidad(anio, activo):
        ac, ppe = v("activo_corriente", anio), v("ppe_neto", anio)
        if ac is None or ppe is None:
            return None
        return 1 - (ac + ppe) / activo
    aqi = div(_no_calidad(t, activo_t), _no_calidad(p, activo_p)) or 1.0

    # SGI: crecimiento de ventas
    sgi = div(ventas_t, ventas_p) or 1.0

    # DEPI: caida en la tasa de depreciacion
    def _tasa_dep(anio):
        dya, ppe = v("dya", anio), v("ppe_neto", anio)
        if dya is None or ppe is None or (dya + ppe) == 0:
            return None
        return dya / (dya + ppe)
    depi = div(_tasa_dep(p), _tasa_dep(t)) or 1.0

    # SGAI: gastos de administracion sobre ventas
    sgai = div(div(v("gastos_sga", t), ventas_t), div(v("gastos_sga", p), ventas_p)) or 1.0

    # LVGI: aumento del apalancamiento
    def _apal(anio, activo):
        return div((v("deuda_lp", anio) or 0) + (v("pasivo_corriente", anio) or 0), activo)
    lvgi = div(_apal(t, activo_t), _apal(p, activo_p)) or 1.0

    # TATA: accruals totales sobre activos, el componente de mas peso del modelo
    tata = div(resta(v("ganancia_neta", t), v("flujo_operativo", t)), activo_t) or 0.0

    return (-4.84 + 0.920 * dsri + 0.528 * gmi + 0.404 * aqi + 0.892 * sgi
            + 0.115 * depi - 0.172 * sgai + 4.679 * tata - 0.327 * lvgi)


@metrica("anios_con_perdida", "Años con perdida (15a)", "Senales", formato="score",
         mejor="bajo", umbrales=(0, 3),
         ayuda="Cuantos ejercicios cerro en rojo en la historia disponible. "
               "Una empresa que nunca perdio plata en 15 años, incluyendo 2008 "
               "y 2020, tiene un modelo probado contra el ciclo.",
         formula="Cuenta de ejercicios con ganancia neta negativa en la "
                 "historia disponible.")
def anios_con_perdida(e):
    serie = e.serie("ganancia_neta")
    return float(sum(1 for v in serie.values() if v < 0)) if serie else None


@metrica("anios_fcf_negativo", "Años con FCF negativo (15a)", "Senales", formato="score",
         mejor="bajo", umbrales=(0, 3),
         ayuda="Ejercicios en los que la empresa quemo caja. Mas revelador que "
               "los años con perdida contable.",
         formula="Cuenta de ejercicios con caja libre negativa en la "
                 "historia disponible.")
def anios_fcf_negativo(e):
    serie = e.serie("fcf")
    return float(sum(1 for v in serie.values() if v < 0)) if serie else None


@metrica("cobertura_datos", "Cobertura de datos", "Senales", formato="pct",
         mejor="alto", umbrales=(80, 50),
         ayuda="Porcentaje de conceptos del catalogo que se pudieron extraer de "
               "EDGAR para esta empresa. Bajo no significa que la empresa sea "
               "mala: significa que etiqueta distinto y que hay que mirar los "
               "numeros con mas cuidado. Bancos y aseguradoras siempre dan bajo.",
         formula="Conceptos contables extraidos / conceptos que "
                 "corresponde pedirle a este tipo de empresa × 100.")
def cobertura_datos(e):
    from .. import conceptos
    # Se mide contra lo que corresponde pedirle a ESTA empresa: a una
    # industrial no se le reprocha no tener depositos ni primas de seguro.
    esperables = {c.clave for c in conceptos.esperables(e.perfil)}
    faltan = len(esperables & set(e.faltantes))
    return pct(len(esperables) - faltan, len(esperables))

