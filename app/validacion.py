"""
Control cruzado de los estados contables extraidos de EDGAR.

POR QUE EXISTE
--------------
El extractor elige, para cada concepto y cada año, la primera etiqueta XBRL que
tenga dato. Cuando la etiqueta elegida no es la que la empresa imprimio en la
cara del estado, el numero que sale no es un error visible: es un numero
plausible, del orden de magnitud correcto, y mal.

Paso de verdad. Hasta el 2026-08-26 los ingresos se leian de
`RevenueFromContractWithCustomerExcludingAssessedTax`, que es solo la venta bajo
contrato con clientes. Bloom Energy publicaba 2.024 M y la app mostraba 2.002 M.
La diferencia era el leasing de equipos. Nadie la iba a notar mirando la tabla.
CNA, una aseguradora, se veia diez veces mas chica.

Lo que si se nota es que las cuentas no cierren. La empresa publica los tres
numeros por separado —ingresos, costo y ganancia bruta— y tienen que sumar. Si
no suman, alguno de los tres salio de la etiqueta equivocada. Eso es lo que
revisa este modulo: identidades contables que se cumplen por definicion, no
rangos razonables ni heuristicas.

QUE NO HACE
-----------
No corrige nada ni descarta datos. Marca. Una identidad rota puede ser un
problema del extractor o una particularidad real de como esa empresa presenta
—un banco no tiene "costo de ventas", una minera reexpresa un ejercicio— y
decidir cual de las dos cosas es requiere abrir el 10-K. El modulo dice donde
mirar.

TOLERANCIAS
-----------
Cada identidad se compara contra una fraccion de la magnitud que la ancla, no
contra un absoluto: medio punto de los ingresos de Apple son 2.000 millones y
medio punto de los de Bloom son 10. Las tolerancias son anchas a proposito. Un
redondeo de presentacion o un renglon "otros" chico no tiene que llenar la
pantalla de avisos; lo que se busca son las etiquetas cruzadas, que se van por
porcentajes de dos digitos.
"""

from __future__ import annotations

from dataclasses import dataclass

# Cuanto puede desviarse cada identidad antes de marcarse, como fraccion de su
# magnitud de referencia.
_TOL_RESULTADOS = 0.005   # ingresos = costo + bruta: es aritmetica de la cara
_TOL_BALANCE = 0.005      # activo = pasivo + patrimonio: idem
_TOL_IMPUESTO = 0.05      # antes de impuesto - impuesto = neta: hay renglones en el medio
_TOL_EPS = 0.05           # neta / acciones = EPS: las acciones son un promedio ponderado

# Debajo de este monto no se marca nada. Una identidad que falla por 40.000
# dolares en una empresa que factura millones es redondeo de presentacion.
_PISO_ABSOLUTO = 500_000.0


@dataclass(frozen=True)
class Hallazgo:
    """Una identidad que no cierra, en un año concreto."""

    anio: int
    identidad: str
    severidad: str      # "grave" | "aviso"
    esperado: float
    obtenido: float
    detalle: str

    @property
    def desvio(self) -> float:
        """Diferencia en porciento sobre el valor esperado."""
        if not self.esperado:
            return 0.0
        return (self.obtenido - self.esperado) / abs(self.esperado) * 100


def _v(series: dict, clave: str, anio: int) -> float | None:
    valor = (series.get(clave) or {}).get(anio)
    return None if valor is None else float(valor)


def _etiqueta(procedencia: dict, clave: str, anio: int) -> str:
    return ((procedencia.get(clave) or {}).get(anio) or {}).get("etiqueta", "?")


def _rompe(esperado: float, obtenido: float, tolerancia: float) -> bool:
    diferencia = abs(obtenido - esperado)
    if diferencia < _PISO_ABSOLUTO:
        return False
    return diferencia > abs(esperado) * tolerancia


def _resultados(series, procedencia, anio) -> Hallazgo | None:
    """ingresos = costo de ventas + ganancia bruta.

    Es la identidad mas util de todas porque las tres lineas salen de etiquetas
    distintas y las tres estan impresas una debajo de la otra. Si el extractor
    se equivoco en cualquiera, esto lo delata.
    """
    ingresos = _v(series, "ingresos", anio)
    costo = _v(series, "costo_ventas", anio)
    bruta = _v(series, "ganancia_bruta", anio)
    if ingresos is None or costo is None or bruta is None:
        return None

    esperado = costo + bruta
    if not _rompe(esperado, ingresos, _TOL_RESULTADOS):
        return None

    return Hallazgo(
        anio=anio,
        identidad="Ingresos = costo de ventas + ganancia bruta",
        severidad="grave",
        esperado=esperado,
        obtenido=ingresos,
        detalle=(
            f"La empresa publica una ganancia bruta de {bruta / 1e6:,.0f} M sobre "
            f"un costo de {costo / 1e6:,.0f} M, o sea ingresos por "
            f"{esperado / 1e6:,.0f} M. El extractor leyo {ingresos / 1e6:,.0f} M "
            f"de `{_etiqueta(procedencia, 'ingresos', anio)}`."
        ),
    )


def _balance(series, procedencia, anio) -> Hallazgo | None:
    """activo = pasivo + patrimonio, con los renglones de al lado que correspondan.

    La ecuacion fundamental. Si no cierra de ninguna forma razonable, alguna de
    las patas vino de una etiqueta que mide otra cosa.

    "De ninguna forma razonable" hay que tomarlo en serio, porque entre el pasivo
    y el patrimonio viven renglones cuya inclusion depende de como etiqueto la
    empresa, y no siempre se puede saber por el nombre de la etiqueta:

      - La participacion minoritaria esta adentro de `StockholdersEquity...
        IncludingPortion...` y afuera de `StockholdersEquity`.
      - El patrimonio temporal aparece a veces con una etiqueta, a veces con
        otra, y a veces con las dos: Yalla informa los mismos 25,9 M como
        `TemporaryEquityCarryingAmountAttributableToParent` y como
        `RedeemableNoncontrollingInterestEquityPreferredCarryingAmount`. Sumar
        las dos cuenta el renglon dos veces y rompe un balance que cierra.

    Asi que en vez de decidir de antemano cual va, se prueban las lecturas
    posibles y basta con que UNA cierre. Es un control, no un calculo: la
    pregunta que responde es si el balance se puede explicar, y si se puede, no
    hay nada que avisar. Que varias combinaciones cierren por casualidad, con la
    tolerancia de medio punto, no pasa.
    """
    activo = _v(series, "activo_total", anio)
    pasivo = _v(series, "pasivo_total", anio)
    patrimonio = _v(series, "patrimonio", anio)
    if activo is None or pasivo is None or patrimonio is None:
        return None

    etiqueta = _etiqueta(procedencia, "patrimonio", anio)
    minoritario = _v(series, "minoritario", anio) or 0.0
    temporal = _v(series, "patrimonio_temporal", anio) or 0.0
    rescatable = _v(series, "minoritario_rescatable", anio) or 0.0

    # Cada lectura posible del tramo que va entre el pasivo y el patrimonio.
    extras = {0.0, temporal, rescatable, temporal + rescatable}
    if "IncludingPortion" not in etiqueta and etiqueta != "Equity":
        extras |= {m + minoritario for m in set(extras)}

    mejor = min((pasivo + patrimonio + extra for extra in extras),
                key=lambda e: abs(activo - e))
    if not _rompe(mejor, activo, _TOL_BALANCE):
        return None

    return Hallazgo(
        anio=anio,
        identidad="Activo = pasivo + patrimonio",
        severidad="grave",
        esperado=mejor,
        obtenido=activo,
        detalle=(
            f"Pasivo {pasivo / 1e6:,.0f} M mas patrimonio "
            f"{patrimonio / 1e6:,.0f} M dan {mejor / 1e6:,.0f} M en la lectura "
            f"que mas se acerca, pero el activo total leido es "
            f"{activo / 1e6:,.0f} M. El patrimonio salio de `{etiqueta}`."
        ),
    )


def _impuesto(series, procedencia, anio) -> Hallazgo | None:
    """resultado antes de impuesto - impuesto = ganancia neta.

    Aviso y no grave: entre esas dos lineas puede haber resultado de operaciones
    discontinuadas, resultado por participacion en asociadas o el minoritario, y
    ninguno de los tres es un error. Un desvio chico es esperable; uno grande
    suele significar que `antes_impuesto` salio de una etiqueta que no es la de
    esta empresa.
    """
    antes = _v(series, "antes_impuesto", anio)
    impuesto = _v(series, "impuesto", anio)
    neta = _v(series, "ganancia_neta", anio)
    if antes is None or impuesto is None or neta is None:
        return None

    esperado = antes - impuesto
    if not _rompe(esperado, neta, _TOL_IMPUESTO):
        return None

    return Hallazgo(
        anio=anio,
        identidad="Antes de impuesto - impuesto = ganancia neta",
        severidad="aviso",
        esperado=esperado,
        obtenido=neta,
        detalle=(
            f"{antes / 1e6:,.0f} M menos {impuesto / 1e6:,.0f} M de impuesto dan "
            f"{esperado / 1e6:,.0f} M, y la ganancia neta leida es "
            f"{neta / 1e6:,.0f} M. Puede ser real (discontinuadas, asociadas, "
            f"minoritario) o que `{_etiqueta(procedencia, 'antes_impuesto', anio)}` "
            f"no sea la linea que usa esta empresa."
        ),
    )


def _eps(series, procedencia, anio) -> Hallazgo | None:
    """ganancia neta / acciones diluidas = EPS diluido.

    Es el control que detecta un split mal aplicado: si las acciones quedaron en
    una escala y la ganancia en otra, el EPS reportado deja de coincidir con la
    division. Tolerancia ancha porque el denominador del EPS es un promedio
    ponderado del ejercicio y las acciones que guardamos no siempre lo son.
    """
    neta = _v(series, "ganancia_neta", anio)
    acciones = _v(series, "acciones_dil", anio)
    eps = _v(series, "eps_diluido", anio)
    if neta is None or eps is None or not acciones:
        return None
    # Con ganancias cerca de cero el porcentaje se dispara sin que pase nada.
    if abs(eps) < 0.10:
        return None

    esperado = eps
    obtenido = neta / acciones
    if abs(obtenido - esperado) <= abs(esperado) * _TOL_EPS:
        return None

    return Hallazgo(
        anio=anio,
        identidad="Ganancia neta / acciones diluidas = EPS diluido",
        severidad="aviso",
        esperado=esperado,
        obtenido=obtenido,
        detalle=(
            f"La empresa reporta un EPS diluido de {eps:,.2f} y la division da "
            f"{obtenido:,.2f} ({neta / 1e6:,.0f} M sobre "
            f"{acciones / 1e6:,.1f} M de acciones). Suele ser un split aplicado a "
            f"una de las dos series y no a la otra."
        ),
    )


_CONTROLES = (_resultados, _balance, _impuesto, _eps)


def revisar(datos: dict) -> list[Hallazgo]:
    """Corre todas las identidades sobre la salida de `edgar.fundamentals`.

    Devuelve los hallazgos del mas grave y mas reciente al mas viejo, que es el
    orden en el que sirven: un problema en el ultimo ejercicio afecta a todos
    los multiplos de hoy, uno de hace ocho años solo mueve un CAGR.
    """
    series = datos.get("series") or {}
    procedencia = datos.get("procedencia") or {}
    anios = sorted(datos.get("anios") or [], reverse=True)

    hallazgos = []
    for anio in anios:
        for control in _CONTROLES:
            hallazgo = control(series, procedencia, anio)
            if hallazgo is not None:
                hallazgos.append(hallazgo)

    orden = {"grave": 0, "aviso": 1}
    return sorted(hallazgos, key=lambda h: (orden[h.severidad], -h.anio))


def resumen(hallazgos: list[Hallazgo]) -> dict[str, int]:
    return {
        "grave": sum(1 for h in hallazgos if h.severidad == "grave"),
        "aviso": sum(1 for h in hallazgos if h.severidad == "aviso"),
    }
