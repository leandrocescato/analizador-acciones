"""
Senales de alerta, clasificadas por gravedad y por estilo de inversion.

Una empresa value y una growth se rompen por motivos distintos, y la misma
cifra significa lo contrario en cada una. Un FCF negativo en una madura es una
alarma; en una que crece al 40% puede ser reinversion sana. Una dilucion del 4%
anual es normal en una growth joven y es un robo silencioso en una madura que
dice estar recomprando.

Por eso las alertas se evaluan contra el cuadro que corresponde:

  - VALUE: se buscan TRAMPAS DE VALOR. Barata porque el negocio se deteriora,
    deuda que hay que refinanciar mas cara, dividendo que no cubre la caja,
    ganancia contable que no se convierte en efectivo.
  - GROWTH: se busca DETERIORO DE LA CALIDAD DEL CRECIMIENTO. Desaceleracion,
    dilucion por compensacion en acciones, quema de caja con poco tiempo por
    delante, crecimiento que ya no viene acompañado de margen.
  - TURNAROUND: se busca si LLEGA. Meses de caja, solvencia, y si hay alguna
    prueba de que la caida se este frenando.

Cada alerta sale con una severidad —critica, vigilar o menor— y con el numero
que la dispara. Sin el numero seria una opinion.
"""

from __future__ import annotations

from . import estilo as est

CRITICA = "critica"
VIGILAR = "vigilar"
MENOR = "menor"

ORDEN = {CRITICA: 0, VIGILAR: 1, MENOR: 2}
ICONO = {CRITICA: "🔴", VIGILAR: "🟠", MENOR: "🟡"}
ETIQUETA = {CRITICA: "Critica", VIGILAR: "Vigilar", MENOR: "Menor"}


def _a(severidad, titulo, detalle, valor=None):
    return {"severidad": severidad, "titulo": titulo, "detalle": detalle,
            "valor": valor}


# ------------------------------------------------------------------ comunes


def _comunes(emp, m) -> list[dict]:
    alertas = []

    z = m.get("altman_z")
    if z is not None and z < 1.8:
        alertas.append(_a(
            CRITICA, "Riesgo de quiebra",
            f"Altman Z de {z:.1f}. Debajo de 1,8 el modelo clasifica a la "
            "empresa en zona de riesgo de default a dos años.", z))

    beneish = m.get("beneish_m")
    if beneish is not None and beneish > -1.78:
        alertas.append(_a(
            VIGILAR, "Contabilidad a revisar",
            f"Beneish M de {beneish:.2f}, por encima del corte de -1,78. No "
            "prueba nada, pero obliga a leer las notas antes de comprar.", beneish))

    accruals = m.get("accruals_sloan")
    if accruals is not None and accruals > 10:
        alertas.append(_a(
            VIGILAR, "La ganancia no viene con caja",
            f"Accruals del {accruals:.1f}% del activo. Sloan mostro que la "
            "ganancia que no viene acompañada de efectivo tiende a revertir.",
            accruals))

    perdidas = m.get("anios_con_perdida")
    if perdidas is not None and perdidas >= 3:
        alertas.append(_a(
            VIGILAR, "Historial de perdidas",
            f"Cerro en rojo {perdidas:.0f} ejercicios de los ultimos 15.", perdidas))

    cobertura = m.get("cobertura_datos")
    if cobertura is not None and cobertura < 60:
        alertas.append(_a(
            MENOR, "Datos incompletos",
            f"Solo se pudo extraer el {cobertura:.0f}% de los conceptos "
            "contables. Revisa la auditoria de etiquetas antes de confiar en "
            "los ratios.", cobertura))

    return alertas


# ------------------------------------------------------------------ value


def _value(emp, m) -> list[dict]:
    alertas = []

    deuda = m.get("deuda_neta_ebitda")
    if deuda is not None and deuda > 4:
        alertas.append(_a(
            CRITICA, "Deuda que decide por vos",
            f"Deuda neta de {deuda:.1f}x EBITDA. Por encima de 4x el destino de "
            "la empresa lo deciden los acreedores, no la direccion.", deuda))
    elif deuda is not None and deuda > 3:
        alertas.append(_a(
            VIGILAR, "Apalancamiento alto",
            f"Deuda neta de {deuda:.1f}x EBITDA. Todavia manejable, pero deja "
            "poco margen si el negocio se enfria.", deuda))

    cobertura = m.get("cobertura_intereses")
    if cobertura is not None and cobertura < 3:
        alertas.append(_a(
            CRITICA, "Intereses mal cubiertos",
            f"El resultado operativo cubre {cobertura:.1f}x los intereses. "
            "Debajo de 3x, un ejercicio malo compromete el pago.", cobertura))

    payout = m.get("payout_real")
    if payout is not None and payout > 100:
        alertas.append(_a(
            CRITICA, "Devuelve mas de lo que genera",
            f"Payout real del {payout:.0f}% de la caja libre entre dividendos y "
            "recompras. La diferencia sale de deuda o de vender activos, y eso "
            "no se sostiene.", payout))

    margen = m.get("margen_op_vs_prom")
    if margen is not None and margen < -5:
        alertas.append(_a(
            VIGILAR, "Margen deprimido",
            f"El margen operativo esta {abs(margen):.1f} puntos por debajo de su "
            "promedio de 10 años. Ahi esta la tesis entera: si es ciclico es "
            "la oportunidad, si es estructural es la trampa.", margen))

    aceleracion = m.get("aceleracion_ingresos")
    if aceleracion is not None and aceleracion < -5:
        alertas.append(_a(
            CRITICA, "El negocio se apaga",
            f"Crece {abs(aceleracion):.1f} puntos menos que en la decada previa. "
            "Un deterioro sostenido del top-line es la señal mas confiable de "
            "declive estructural, y la fabrica numero uno de trampas de valor.",
            aceleracion))

    conversion = m.get("fcf_conversion_prom5")
    if conversion is not None and conversion < 60:
        alertas.append(_a(
            VIGILAR, "Poca conversion a caja",
            f"Solo el {conversion:.0f}% de la ganancia contable llega a caja "
            "libre, promediado a 5 años.", conversion))

    dilucion = m.get("var_acciones_5a")
    if dilucion is not None and dilucion > 2:
        alertas.append(_a(
            VIGILAR, "Dilucion en una empresa madura",
            f"Las acciones crecieron {dilucion:.1f}% en 5 años. En una empresa "
            "que ya no necesita capital para crecer, cada emision te saca "
            "porcion sin darte nada a cambio.", dilucion))

    return alertas


# ------------------------------------------------------------------ growth


def _growth(emp, m) -> list[dict]:
    alertas = []

    meses = m.get("meses_de_caja")
    if meses is not None and meses < 12:
        alertas.append(_a(
            CRITICA, "Se queda sin caja",
            f"Le quedan {meses:.0f} meses al ritmo actual de quema. Va a tener "
            "que emitir o endeudarse en las condiciones que le toquen, no en "
            "las que elija.", meses))
    elif meses is not None and meses < 24:
        alertas.append(_a(
            VIGILAR, "Pista de caja corta",
            f"{meses:.0f} meses de caja al ritmo actual.", meses))

    r40 = m.get("regla_40")
    if r40 is not None and r40 < 20:
        alertas.append(_a(
            CRITICA, "Ni crece ni genera",
            f"Regla del 40 en {r40:.0f}. Una empresa en crecimiento puede crecer "
            "poco si genera caja, o quemar caja si crece rapido; con las dos "
            "cosas flojas a la vez no hay tesis.", r40))
    elif r40 is not None and r40 < 40:
        alertas.append(_a(
            VIGILAR, "Debajo del umbral de la regla del 40",
            f"Regla del 40 en {r40:.0f}, contra los 40 que se consideran sanos.",
            r40))

    dilucion = m.get("var_acciones_5a")
    if dilucion is not None and dilucion > 15:
        alertas.append(_a(
            CRITICA, "Dilucion fuerte",
            f"Las acciones crecieron {dilucion:.1f}% en 5 años. El negocio puede "
            "estar creciendo y tu porcion achicandose igual: mira el crecimiento "
            "POR ACCION, no el total.", dilucion))
    elif dilucion is not None and dilucion > 8:
        alertas.append(_a(
            VIGILAR, "Dilucion a vigilar",
            f"Las acciones crecieron {dilucion:.1f}% en 5 años.", dilucion))

    sbc = m.get("sbc_ingresos")
    if sbc is not None and sbc > 15:
        alertas.append(_a(
            VIGILAR, "Compensacion en acciones alta",
            f"La SBC equivale al {sbc:.1f}% de los ingresos. Es un gasto real "
            "aunque no salga de la caja, y cualquier 'beneficio ajustado' que "
            "la excluya esta inflado.", sbc))

    aceleracion = m.get("aceleracion_ingresos")
    if aceleracion is not None and aceleracion < -8:
        alertas.append(_a(
            CRITICA, "El crecimiento se desacelera",
            f"Crece {abs(aceleracion):.1f} puntos menos que en la decada previa. "
            "En una empresa cara, la desaceleracion no baja el precio de a poco: "
            "lo baja de golpe, porque se comprime el multiplo.", aceleracion))

    peg = m.get("peg")
    if peg is not None and peg > 2:
        alertas.append(_a(
            VIGILAR, "El precio ya descuenta el crecimiento",
            f"PEG de {peg:.1f}x. Por encima de 2 estas pagando por adelantado un "
            "crecimiento que todavia tiene que ocurrir.", peg))

    margen = m.get("margen_bruto")
    if margen is not None and margen < 30:
        alertas.append(_a(
            MENOR, "Margen bruto bajo para una growth",
            f"Margen bruto del {margen:.1f}%. Deja poco lugar para que el "
            "crecimiento se convierta en ganancia al final.", margen))

    return alertas


# ------------------------------------------------------------------ turnaround


def _turnaround(emp, m) -> list[dict]:
    alertas = []

    meses = m.get("meses_de_caja")
    if meses is not None and meses < 18:
        alertas.append(_a(
            CRITICA, "El reloj corre",
            f"{meses:.0f} meses de caja al ritmo actual de quema. En una "
            "reestructuracion, el tiempo es la restriccion que manda.", meses))

    piotroski = m.get("piotroski")
    if piotroski is not None and piotroski <= 3:
        alertas.append(_a(
            CRITICA, "Sigue deteriorandose",
            f"Piotroski de {piotroski:.0f} sobre 9. No hay señal de que el "
            "cambio haya empezado: una accion barata que ademas empeora es una "
            "trampa, no una oportunidad.", piotroski))
    elif piotroski is not None and piotroski >= 7:
        alertas.append(_a(
            MENOR, "Hay señal de mejora",
            f"Piotroski de {piotroski:.0f} sobre 9: la empresa esta mejorando en "
            "la mayoria de los frentes que mide el modelo.", piotroski))

    deuda = m.get("deuda_neta_ebitda")
    if deuda is not None and deuda > 3:
        alertas.append(_a(
            CRITICA, "Deuda en plena reestructuracion",
            f"Deuda neta de {deuda:.1f}x EBITDA mientras el negocio se acomoda. "
            "Es la combinacion que decide quien se queda con la empresa.", deuda))

    return alertas


# ------------------------------------------------------------------ API


def evaluar(emp, metricas: dict, clasificacion: dict) -> list[dict]:
    """Alertas de esta empresa, de la mas grave a la mas leve."""
    por_estilo = {
        est.VALUE: _value,
        est.GROWTH: _growth,
        est.TURNAROUND: _turnaround,
        # Una hibrida se rompe por los dos lados.
        est.HIBRIDA: lambda e, m: _value(e, m) + _growth(e, m),
    }
    fn = por_estilo.get(clasificacion["estilo"], _value)

    alertas = _comunes(emp, metricas) + fn(emp, metricas)

    # Sin duplicados: una hibrida puede disparar la misma alerta dos veces.
    vistas, unicas = set(), []
    for a in alertas:
        if a["titulo"] in vistas:
            continue
        vistas.add(a["titulo"])
        unicas.append(a)

    return sorted(unicas, key=lambda a: ORDEN[a["severidad"]])


def resumen(alertas: list[dict]) -> dict[str, int]:
    conteo = {CRITICA: 0, VIGILAR: 0, MENOR: 0}
    for a in alertas:
        conteo[a["severidad"]] += 1
    return conteo
