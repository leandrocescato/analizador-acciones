"""
Adaptador de datos de mercado: precio, beta, capitalizacion, volumen, 52 semanas.

Fuente primaria: Yahoo Finance via yfinance. Fallback de precios: Stooq (CSV).

REGLA DE SEPARACION DE FUENTES
------------------------------
De aca salen SOLO datos de mercado. Los fundamentals salen exclusivamente de
EDGAR (`edgar.py`). Yahoo tambien publica estados contables, pero mezclarlos
con los de EDGAR produce ratios donde el numerador y el denominador vienen de
criterios distintos. Es la clase de error que no se nota hasta que decidis
sobre un numero que nunca existio.

La unica excepcion deliberada es `acciones_en_circulacion`, que se usa para la
capitalizacion: ahi el dato de mercado es mas actual que el ultimo 10-K.
"""

from __future__ import annotations

import datetime as dt
import io

import pandas as pd
import requests
import yfinance as yf

from .. import cache, config

_URL_STOOQ = "https://stooq.com/q/d/l/?s={ticker}.us&i=d"


def _sin_nan(valor):
    """Normaliza los NaN y los 0 espurios de Yahoo a None."""
    if valor is None:
        return None
    try:
        f = float(valor)
    except (TypeError, ValueError):
        return None
    return None if f != f else f


# ------------------------------------------------------------------ precios

def _precios_stooq(ticker: str) -> list[dict]:
    url = _URL_STOOQ.format(ticker=ticker.lower().replace(".", "-"))
    resp = requests.get(url, timeout=30)
    resp.raise_for_status()
    df = pd.read_csv(io.StringIO(resp.text))
    if "Close" not in df.columns:
        return []
    return [
        {"fecha": str(f), "cierre": float(c)}
        for f, c in zip(df["Date"], df["Close"])
        if c == c
    ]


def _precios_yahoo(ticker: str, anios: int) -> list[dict]:
    hist = yf.Ticker(ticker).history(period=f"{anios}y", auto_adjust=True)
    if hist is None or hist.empty:
        return []
    return [
        {"fecha": idx.strftime("%Y-%m-%d"), "cierre": float(c)}
        for idx, c in zip(hist.index, hist["Close"])
        if c == c
    ]


def precios(ticker: str, anios: int = 15) -> list[dict]:
    """Serie de cierres ajustados. Yahoo primero, Stooq si Yahoo falla."""
    clave = f"px:{ticker.upper()}:{anios}"
    datos = cache.obtener(clave, config.TTL_PRECIOS_H)
    if datos is not None:
        return datos

    datos = []
    try:
        datos = _precios_yahoo(ticker, anios)
    except Exception:
        datos = []

    if not datos:
        try:
            datos = _precios_stooq(ticker)
        except Exception:
            datos = []

    if datos:
        cache.guardar(clave, "mercado", datos)
    return datos


# ------------------------------------------------------------------ instantanea

def _de_fast_info(t: yf.Ticker) -> dict:
    """fast_info es mucho mas confiable que .info, pero trae menos campos."""
    try:
        fi = t.fast_info
    except Exception:
        return {}
    lectura = {}
    for destino, origen in [
        ("precio", "last_price"),
        ("cierre_previo", "previous_close"),
        ("max52", "year_high"),
        ("min52", "year_low"),
        ("market_cap", "market_cap"),
        ("acciones", "shares"),
        ("volumen", "last_volume"),
        ("volumen_prom_10d", "ten_day_average_volume"),
        ("moneda", "currency"),
    ]:
        try:
            lectura[destino] = fi[origen]
        except Exception:
            lectura[destino] = None
    return lectura


def _de_info(t: yf.Ticker) -> dict:
    """`.info` trae beta y sector, pero se rompe seguido. Nunca es bloqueante."""
    try:
        info = t.info or {}
    except Exception:
        return {}
    return {
        "nombre": info.get("longName") or info.get("shortName"),
        "sector": info.get("sector"),
        "industria": info.get("industry"),
        "beta": _sin_nan(info.get("beta")),
        "div_yield": _sin_nan(info.get("dividendYield")),
        # Monto anual en dolares por accion. A diferencia del yield, no tiene
        # ambiguedad de escala: es la unica forma confiable de calcularlo.
        "dividendo_anual": _sin_nan(info.get("dividendRate")),
        "volumen_prom_3m": _sin_nan(info.get("averageVolume")),
        "acciones_info": _sin_nan(info.get("sharesOutstanding")),
        "market_cap_info": _sin_nan(info.get("marketCap")),
        "pais": info.get("country"),
        "empleados": info.get("fullTimeEmployees"),
        # --- CONSENSO DE ANALISTAS, no dato reportado.
        # Es una tercera categoria de dato: no es un hecho auditado de EDGAR ni
        # una cotizacion. Es lo que un grupo de analistas espera que pase, y en
        # promedio se revisa a la baja a medida que se acerca la fecha. Va
        # etiquetado como estimacion en toda la interfaz.
        "per_forward": _sin_nan(info.get("forwardPE")),
        "eps_forward": _sin_nan(info.get("forwardEps")),
    }


def _de_estimaciones(t: yf.Ticker) -> dict:
    """Crecimiento esperado de ingresos y ganancias para el proximo ejercicio.

    Se toma la fila `+1y`: el ejercicio completo siguiente contra el actual. Es
    la misma base sobre la que Yahoo calcula su PER forward, asi que los tres
    numeros hablan del mismo periodo y se pueden leer juntos.
    """
    salida = {"crec_ingresos_ntm": None, "crec_eps_ntm": None, "analistas_ntm": None}

    def _crecimiento(tabla, campo="growth"):
        try:
            if tabla is None or tabla.empty or "+1y" not in tabla.index:
                return None
            valor = tabla.loc["+1y", campo]
        except Exception:
            return None
        valor = _sin_nan(valor)
        return None if valor is None else float(valor) * 100

    try:
        salida["crec_ingresos_ntm"] = _crecimiento(t.revenue_estimate)
    except Exception:
        pass
    try:
        ganancias = t.earnings_estimate
        salida["crec_eps_ntm"] = _crecimiento(ganancias)
        if ganancias is not None and not ganancias.empty and "+1y" in ganancias.index:
            salida["analistas_ntm"] = _sin_nan(
                ganancias.loc["+1y", "numberOfAnalysts"])
    except Exception:
        pass

    return salida


def instantanea(ticker: str) -> dict:
    """Foto de mercado del ticker. Nunca lanza: si falla, devuelve campos en None."""
    ticker = ticker.upper()
    clave = f"mkt:{ticker}"
    datos = cache.obtener(clave, config.TTL_MERCADO_H)
    if datos is not None:
        return datos

    try:
        t = yf.Ticker(ticker)
        rapido, lento = _de_fast_info(t), _de_info(t)
        estimaciones = _de_estimaciones(t)
    except Exception:
        rapido, lento, estimaciones = {}, {}, {}

    serie = precios(ticker, anios=config.ANIOS_HISTORIA)

    precio = _sin_nan(rapido.get("precio"))
    if precio is None and serie:
        precio = serie[-1]["cierre"]

    previo = _sin_nan(rapido.get("cierre_previo"))
    if previo is None and len(serie) >= 2:
        previo = serie[-2]["cierre"]

    # Si Yahoo no dio 52 semanas, se calcula de la serie de precios.
    max52, min52 = _sin_nan(rapido.get("max52")), _sin_nan(rapido.get("min52"))
    if (max52 is None or min52 is None) and serie:
        corte = (dt.date.today() - dt.timedelta(days=365)).isoformat()
        ultimo_anio = [p["cierre"] for p in serie if p["fecha"] >= corte]
        if ultimo_anio:
            max52 = max52 or max(ultimo_anio)
            min52 = min52 or min(ultimo_anio)

    acciones = _sin_nan(rapido.get("acciones")) or lento.get("acciones_info")
    market_cap = _sin_nan(rapido.get("market_cap")) or lento.get("market_cap_info")
    if market_cap is None and precio and acciones:
        market_cap = precio * acciones

    volumen = (
        lento.get("volumen_prom_3m")
        or _sin_nan(rapido.get("volumen_prom_10d"))
        or _sin_nan(rapido.get("volumen"))
    )

    resultado = {
        "ticker": ticker,
        "nombre": lento.get("nombre"),
        "sector": lento.get("sector"),
        "industria": lento.get("industria"),
        "pais": lento.get("pais"),
        "empleados": lento.get("empleados"),
        "moneda": rapido.get("moneda") or "USD",
        "precio": precio,
        "cierre_previo": previo,
        "var_pct": ((precio / previo - 1) * 100) if precio and previo else None,
        "max52": max52,
        "min52": min52,
        "beta": lento.get("beta"),
        "div_yield": lento.get("div_yield"),
        "dividendo_anual": lento.get("dividendo_anual"),
        # Consenso de analistas: estimaciones, no hechos. Ver _de_estimaciones.
        "per_forward": lento.get("per_forward"),
        "eps_forward": lento.get("eps_forward"),
        **estimaciones,
        "acciones": acciones,
        "market_cap": market_cap,
        "volumen_acciones": volumen,
        "volumen_usd": (volumen * precio) if volumen and precio else None,
        "actualizado": dt.datetime.now().isoformat(timespec="seconds"),
    }

    if precio is not None:
        cache.guardar(clave, "mercado", resultado)
    return resultado


# ------------------------------------------------------------------ derivados

def serie_anual_precios(ticker: str) -> dict[int, float]:
    """Precio de cierre del ultimo dia habil de cada año.

    Se usa para reconstruir multiplos historicos (que PER tenia esta empresa
    en 2016) sin depender de ninguna fuente paga.
    """
    por_anio: dict[int, float] = {}
    for punto in precios(ticker, anios=config.ANIOS_HISTORIA):
        por_anio[int(punto["fecha"][:4])] = punto["cierre"]
    return por_anio


def retornos(ticker: str) -> dict[str, float | None]:
    """Retorno acumulado a 1, 3 y 5 años, y drawdown desde el maximo historico."""
    serie = precios(ticker, anios=config.ANIOS_HISTORIA)
    if not serie:
        return {"ret_1a": None, "ret_3a": None, "ret_5a": None,
                "drawdown_max": None, "maximo_historico": None}

    ultimo = serie[-1]["cierre"]
    hoy = dt.date.today()

    def _retorno(anios: int) -> float | None:
        corte = (hoy - dt.timedelta(days=365 * anios)).isoformat()
        previos = [p for p in serie if p["fecha"] <= corte]
        if not previos or previos[-1]["cierre"] <= 0:
            return None
        return (ultimo / previos[-1]["cierre"] - 1) * 100

    maximo = max(p["cierre"] for p in serie)
    return {
        "ret_1a": _retorno(1),
        "ret_3a": _retorno(3),
        "ret_5a": _retorno(5),
        "drawdown_max": (ultimo / maximo - 1) * 100 if maximo else None,
        "maximo_historico": maximo,
    }

