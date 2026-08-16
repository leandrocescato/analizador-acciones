"""
El objeto `Empresa`: une los fundamentals de EDGAR con los datos de mercado y
expone una interfaz unica sobre la que se escriben todas las metricas.

Ademas calcula las SERIES DERIVADAS (FCF, deuda neta, NOPAT, capital invertido,
EBITDA...). Se calculan una sola vez aca, año por año, para que ninguna
metrica tenga que reconstruirlas y para que todas usen exactamente la misma
definicion. Si mañana cambias como se define el capital invertido, lo cambias
en un solo lugar y se propaga a ROIC, a ROIC incremental y al spread contra WACC.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any

from . import cache, config, perfiles
from .metricas import base
from .metricas.base import div, resta, suma
from .proveedores import edgar, mercado

# Cuantos ejercicios puede atrasarse una serie antes de considerarla vencida.
# Dos permite que un concepto falte en el ultimo 10-K sin perder el dato;
# tres o mas ya es una serie discontinuada.
TOLERANCIA_ANIOS = 2


@dataclass
class Empresa:
    ticker: str
    nombre: str = ""
    cik: str = ""
    sector: str = ""
    industria: str = ""
    # Tipo contable: banco / seguros / reit / general. Decide que metricas se
    # publican, porque varias no significan nada fuera de una industrial.
    perfil: str = perfiles.GENERAL
    sic: str = ""
    sic_desc: str = ""
    anios: list[int] = field(default_factory=list)
    series: dict[str, dict[int, float]] = field(default_factory=dict)
    procedencia: dict[str, dict[int, dict]] = field(default_factory=dict)
    faltantes: list[str] = field(default_factory=list)
    mercado: dict[str, Any] = field(default_factory=dict)
    retornos: dict[str, Any] = field(default_factory=dict)
    error: str | None = None

    # ------------------------------------------------------------ acceso

    @property
    def ultimo(self) -> int | None:
        return self.anios[-1] if self.anios else None

    def serie(self, clave: str) -> dict[int, float]:
        return self.series.get(clave, {})

    def ventana(self, n: int) -> set[int]:
        """Los ultimos n ejercicios de la EMPRESA, no de la serie.

        La diferencia es la que evita el peor error posible. Ford deja de
        etiquetar su deuda con conceptos estandar despues de 2014: si un
        promedio 'de 5 años' toma los ultimos 5 valores que existan, devuelve
        2010-2014 y los presenta como actuales. Mismo problema que el cambio de
        etiquetas XBRL: no rompe nada, solo miente.
        """
        if self.ultimo is None:
            return set()
        return set(range(self.ultimo - n + 1, self.ultimo + 1))

    def f(self, clave: str, anio: int | None = None) -> float | None:
        """Valor de un concepto. Sin año, el mas reciente, si no esta vencido."""
        s = self.series.get(clave)
        if not s:
            return None
        if anio is not None:
            return s.get(anio)
        reciente = max(s)
        if self.ultimo is not None and self.ultimo - reciente > TOLERANCIA_ANIOS:
            return None  # dato viejo: mejor vacio que engañoso
        return s[reciente]

    def anio_de(self, clave: str) -> int | None:
        s = self.series.get(clave)
        return max(s) if s else None

    def esta_vencida(self, clave: str) -> bool:
        """True si la serie existe pero dejo de actualizarse hace años."""
        s = self.series.get(clave)
        if not s or self.ultimo is None:
            return False
        return (self.ultimo - max(s)) > TOLERANCIA_ANIOS

    def prev(self, clave: str, n: int = 1) -> float | None:
        """Valor de n ejercicios antes del mas reciente de esa serie."""
        s = self.series.get(clave)
        if not s:
            return None
        objetivo = max(s) - n
        return s.get(objetivo)

    def ultimos(self, clave: str, n: int) -> list[float]:
        """Valores de los ultimos n ejercicios de la empresa. Puede devolver
        menos de n, o ninguno si la serie dejo de reportarse."""
        s = self.series.get(clave)
        if not s:
            return []
        return [s[a] for a in sorted(self.ventana(n) & set(s))]

    def prom(self, clave: str, n: int) -> float | None:
        return base.promedio(self.ultimos(clave, n))

    def par(self, a: str, b: str) -> tuple[float | None, float | None]:
        """Dos conceptos del ULTIMO ejercicio en que existen los dos.

        `f()` devuelve el valor mas reciente de cada serie por separado, y eso
        en un cociente puede cruzar ejercicios distintos: a NU le tomaba la
        provision de 2023 contra los prestamos de 2024 y devolvia un coste del
        riesgo del 42,9%. Para un ratio, los dos terminos tienen que ser del
        mismo año o no significan nada.
        """
        sa, sb = self.series.get(a), self.series.get(b)
        if not sa or not sb:
            return (None, None)
        comunes = set(sa) & set(sb)
        if not comunes:
            return (None, None)
        anio = max(comunes)
        if self.ultimo is not None and self.ultimo - anio > TOLERANCIA_ANIOS:
            return (None, None)
        return (sa[anio], sb[anio])

    def juntos(self, *claves: str) -> tuple[float | None, ...]:
        """Varios conceptos del ultimo ejercicio en que existen TODOS.

        Para un grupo de ratios que se leen juntos y que tienen que cerrar
        entre si. Allstate cambio de etiqueta de siniestros en 2023: calculando
        cada ratio con su propio año mas reciente, la siniestralidad daba 78%
        y los gastos 27% contra un combinado de 91%, que es aritmeticamente
        imposible. Mejor los tres de 2023 que tres numeros que no cierran.
        """
        series = [self.series.get(c) for c in claves]
        if any(not s for s in series):
            return tuple(None for _ in claves)
        comunes = set(series[0])
        for s in series[1:]:
            comunes &= set(s)
        if not comunes:
            return tuple(None for _ in claves)
        anio = max(comunes)
        if self.ultimo is not None and self.ultimo - anio > TOLERANCIA_ANIOS:
            return tuple(None for _ in claves)
        return tuple(s[anio] for s in series)

    def tabla(self, claves: list[str]) -> dict[str, dict[int, float]]:
        return {k: self.serie(k) for k in claves if self.serie(k)}

    # ------------------------------------------------------------ atajos

    @property
    def precio(self) -> float | None:
        return self.mercado.get("precio")

    @property
    def market_cap(self) -> float | None:
        return self.mercado.get("market_cap")

    @property
    def ev(self) -> float | None:
        """Enterprise value: capitalizacion + deuda neta + minoritarios + preferidas."""
        mc = self.market_cap
        if mc is None:
            return None
        return suma(mc, self.f("deuda_neta"), self.f("minoritario"), self.f("preferidas"))

    def tiene_datos(self) -> bool:
        return bool(self.anios) and self.error is None


# ------------------------------------------------------------------ derivadas


def _serie_binaria(a: dict[int, float], b: dict[int, float], op) -> dict[int, float]:
    """Combina dos series año por año. Solo produce años donde se puede."""
    salida = {}
    for anio in set(a) | set(b):
        valor = op(a.get(anio), b.get(anio))
        if valor is not None:
            salida[anio] = valor
    return salida


def _derivar(series: dict[str, dict[int, float]]) -> None:
    """Agrega las series derivadas. Muta `series` en el lugar."""
    g = lambda k: series.get(k, {})

    # --- rellenos de conceptos que muchas empresas no etiquetan explicitamente
    if not g("ganancia_bruta") and g("ingresos") and g("costo_ventas"):
        series["ganancia_bruta"] = _serie_binaria(
            g("ingresos"), g("costo_ventas"),
            lambda i, c: resta(i, c) if i is not None and c is not None else None)

    if not g("pasivo_total") and g("activo_total") and g("patrimonio"):
        series["pasivo_total"] = _serie_binaria(
            g("activo_total"), g("patrimonio"),
            lambda a, p: resta(a, p) if a is not None and p is not None else None)

    # Varias farmaceuticas (MRK, PFE, ZTS) y algunas industriales no etiquetan
    # OperatingIncomeLoss. Sin EBIT no hay NOPAT, y sin NOPAT se caen el ROIC,
    # el EV/EBIT y el spread contra el WACC. Se reconstruye por la via clasica:
    # resultado antes de impuestos mas el gasto de intereses.
    faltan_ebit = set(g("antes_impuesto")) - set(g("ebit"))
    if faltan_ebit:
        reconstruido = dict(g("ebit"))
        for anio in faltan_ebit:
            antes = g("antes_impuesto").get(anio)
            if antes is None:
                continue
            reconstruido[anio] = antes + abs(g("intereses").get(anio) or 0.0)
        series["ebit"] = reconstruido

    # Relleno de la serie de acciones para las empresas de doble clase, que no
    # publican un promedio ponderado consolidado sin dimension.
    if g("acciones_circulacion"):
        completada = dict(g("acciones_dil"))
        for anio, valor in g("acciones_circulacion").items():
            completada.setdefault(anio, valor)
        if completada:
            series["acciones_dil"] = completada


    # --- caja y deuda
    series["caja_total"] = _serie_binaria(
        g("efectivo"), g("inversiones_cp"), lambda e, i: suma(e, i))

    series["deuda_financiera"] = _serie_binaria(
        g("deuda_lp"), g("deuda_cp"), lambda l, c: suma(l, c))

    # Respaldo para las empresas que publican la deuda en una sola etiqueta sin
    # separar tramos. Solo rellena años vacios: sumarlo seria contar dos veces.
    # Es un riesgo concreto, no teorico: NU etiqueta el mismo importe como
    # `Borrowings` y como `ShorttermBorrowings`, con el mismo valor al centavo.
    for anio, valor in g("deuda_reportada").items():
        series["deuda_financiera"].setdefault(anio, valor)

    leases = _serie_binaria(g("leases_lp"), g("leases_cp"), lambda l, c: suma(l, c))
    series["leases_total"] = leases

    # Los leases operativos son deuda economica real: alquilar 500 locales por
    # 10 años obliga igual que un bono. Se incluyen en la deuda total.
    series["deuda_total"] = _serie_binaria(
        series["deuda_financiera"], leases, lambda d, l: suma(d, l))

    series["deuda_neta"] = _serie_binaria(
        series["deuda_total"], series["caja_total"],
        lambda d, c: resta(d, c) if d is not None or c is not None else None)

    # --- resultado y caja
    series["ebitda"] = _serie_binaria(g("ebit"), g("dya"), lambda e, d: suma(e, d))

    series["fcf"] = _serie_binaria(
        g("flujo_operativo"), g("capex"),
        lambda o, c: resta(o, c) if o is not None else None)

    # FCF neto de compensacion en acciones: el gasto no sale de la caja, pero
    # la dilucion que provoca la paga el accionista igual.
    series["fcf_post_sbc"] = _serie_binaria(
        series["fcf"], g("sbc"), lambda f, s: resta(f, s) if f is not None else None)

    # --- capital y retorno
    series["tasa_impositiva"] = _serie_binaria(
        g("impuesto"), g("antes_impuesto"),
        lambda i, a: min(max(div(i, a), 0.0), 0.5) if div(i, a) is not None else None)

    series["nopat"] = {
        anio: ebit * (1 - series["tasa_impositiva"].get(anio, 0.21))
        for anio, ebit in g("ebit").items()
    }

    # Capital invertido = patrimonio + deuda total - caja excedente.
    # Se resta la caja porque no esta puesta a trabajar en el negocio.
    #
    # Guarda contra un artefacto real: en empresas con financiera cautiva (Ford,
    # GM) o con mucha caja contra poco patrimonio, la resta puede dar un capital
    # invertido minusculo y el ROIC se dispara a cientos por ciento. Un ROIC de
    # 463% no es una empresa extraordinaria, es una division por casi cero. Se
    # exige que el capital invertido sea al menos el 5% del activo para
    # publicarlo; si no llega, el año queda sin dato.
    series["capital_invertido"] = {}
    for anio in g("patrimonio"):
        ci = suma(g("patrimonio").get(anio), series["deuda_total"].get(anio))
        if ci is None:
            continue
        ci = resta(ci, series["caja_total"].get(anio))
        piso = (g("activo_total").get(anio) or 0) * 0.05
        if ci and ci > max(piso, 0):
            series["capital_invertido"][anio] = ci

    # Capital invertido sin goodwill: mide el retorno del negocio operativo,
    # sin el precio que la empresa pago por sus adquisiciones.
    # Cuando el goodwill se come casi todo el capital, el cociente se dispara a
    # cifras sin sentido economico (miles por ciento). En ese caso no se publica
    # el año: un numero absurdo confunde mas que un dato ausente.
    series["capital_invertido_ex_gw"] = {}
    for anio, ci in series["capital_invertido"].items():
        neto = ci - (g("goodwill").get(anio) or 0) - (g("intangibles").get(anio) or 0)
        if neto > ci * 0.15:
            series["capital_invertido_ex_gw"][anio] = neto

    series["capital_trabajo"] = _serie_binaria(
        g("activo_corriente"), g("pasivo_corriente"),
        lambda a, p: resta(a, p) if a is not None and p is not None else None)

    series["patrimonio_tangible"] = {
        anio: p - (g("goodwill").get(anio) or 0) - (g("intangibles").get(anio) or 0)
        for anio, p in g("patrimonio").items()
    }

    # Retorno total al accionista en efectivo (dividendos + recompras).
    series["retorno_accionista"] = _serie_binaria(
        g("dividendos"), g("recompras"), lambda d, r: suma(d, r))

    # --- sectoriales
    #
    # Ingreso total de un banco: margen financiero mas comisiones. Es el
    # denominador del ratio de eficiencia y el equivalente a las ventas.
    series["ingresos_bancarios"] = _serie_binaria(
        g("interes_neto"), g("no_interes_ingresos"), lambda i, c: suma(i, c))

    # FFO (Funds From Operations), el estandar de NAREIT para REITs: la
    # ganancia neta devolviendole la amortizacion, que en un inmueble no
    # representa un desgaste real, y sacandole los resultados de una sola vez
    # por venta de propiedades. Es la razon por la que el PER de un REIT no
    # significa nada y este numero si.
    #
    # SOLO se calcula si la empresa etiqueta en algun año la ganancia por
    # venta de inmuebles. La que no lo hace deja esos resultados extraordinarios
    # mezclados en la ganancia neta, y el FFO sale inflado justo en los años
    # que mas importan. Simon Property es el caso: en 2025 su ganancia neta
    # salta a 5.364 M por una operacion que no desglosa, y el FFO daria 20,81
    # dolares por accion contra los 11-12 reales de los tres años anteriores.
    # Un REIT sin ventas en un ejercicio puntual no se ve afectado: alcanza con
    # que etiquete la ganancia alguna vez para saber que la etiqueta cuando la hay.
    series["ffo"] = {}
    if g("ganancia_venta_inmuebles"):
        for anio, neta in g("ganancia_neta").items():
            dya = g("dya").get(anio)
            if dya is None:
                continue  # sin amortizacion no hay FFO que valga
            valor = neta + dya
            valor -= g("ganancia_venta_inmuebles").get(anio) or 0.0
            valor += g("deterioro_inmuebles").get(anio) or 0.0
            series["ffo"][anio] = valor

    # Limpieza: series vacias no aportan y ensucian la interfaz.
    for clave in [k for k, v in series.items() if not v]:
        series.pop(clave)


# ------------------------------------------------------------------ carga


def cargar(ticker: str, con_mercado: bool = True) -> Empresa:
    """Construye una Empresa completa. Nunca lanza: los errores viajan en `.error`."""
    ticker = ticker.strip().upper()
    try:
        fund = edgar.fundamentals(ticker)
    except edgar.ErrorEdgar as exc:
        return Empresa(ticker=ticker, error=str(exc))
    except Exception as exc:
        return Empresa(ticker=ticker, error=f"Error al leer EDGAR: {exc}")

    series = fund["series"]
    _derivar(series)

    emp = Empresa(
        ticker=ticker,
        nombre=fund["nombre"],
        cik=fund["cik"],
        anios=fund["anios"],
        series=series,
        procedencia=fund["procedencia"],
        faltantes=fund["faltantes"],
        perfil=fund.get("perfil", perfiles.GENERAL),
        sic=fund.get("sic", ""),
        sic_desc=fund.get("sic_desc", ""),
    )

    if con_mercado:
        try:
            emp.mercado = mercado.instantanea(ticker)
            emp.retornos = mercado.retornos(ticker)
            emp.sector = emp.mercado.get("sector") or ""
            emp.industria = emp.mercado.get("industria") or ""
            if emp.mercado.get("nombre"):
                emp.nombre = emp.mercado["nombre"]
        except Exception:
            emp.mercado, emp.retornos = {}, {}

    return emp


def metricas_de(emp: Empresa) -> dict[str, float | None]:
    """Calcula el catalogo completo y deja constancia del dia en el historial."""
    valores = base.calcular_todas(emp)
    if emp.tiene_datos():
        try:
            cache.registrar_snapshot(emp.ticker, valores)
        except Exception:
            pass  # el historial es un extra, nunca puede frenar el analisis
    return valores

