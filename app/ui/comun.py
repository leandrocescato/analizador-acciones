"""Utilidades compartidas por el Panel y el Detalle."""

from __future__ import annotations

from concurrent.futures import ThreadPoolExecutor, as_completed

import streamlit as st

from .. import almacen, config, modelo, perfiles
from ..metricas import base
from ..proveedores import mercado

# Paleta del semaforo. Sobria a proposito: el color senala donde mirar,
# no reemplaza el criterio.
COLORES = {
    "bueno": "background-color: rgba(34, 160, 90, 0.18)",
    "medio": "background-color: rgba(215, 160, 40, 0.14)",
    "malo": "background-color: rgba(210, 60, 60, 0.18)",
    "sin_dato": "",
}

# ------------------------------------------------------------------ universo
#
# El universo y las notas viven en `almacen.py`, que decide solo si guardarlos
# en disco o en el Gist privado. Aca quedan los atajos para no tener que
# importar dos modulos en cada pantalla.

leer_universo = almacen.leer_universo
escribir_universo = almacen.escribir_universo


# ------------------------------------------------------------------ carga

@st.cache_data(show_spinner=False, ttl=3600)
def cargar_empresa(ticker: str, _version: int = 0):
    """Carga cacheada a nivel de sesion. `_version` fuerza el refresco."""
    emp = modelo.cargar(ticker)
    return emp, modelo.metricas_de(emp)


def cargar_varias(tickers: list[str], version: int = 0, barra=None):
    """Carga en paralelo. El limite de velocidad de la SEC se respeta igual:
    esta impuesto con un lock global dentro del proveedor, asi que los hilos
    solo aprovechan el tiempo de descarga, no atropellan a la API."""
    resultados: dict[str, tuple] = {}
    total = len(tickers)

    with ThreadPoolExecutor(max_workers=4) as pool:
        futuros = {pool.submit(cargar_empresa, t, version): t for t in tickers}
        for i, fut in enumerate(as_completed(futuros), 1):
            ticker = futuros[fut]
            try:
                resultados[ticker] = fut.result()
            except Exception as exc:
                resultados[ticker] = (modelo.Empresa(ticker=ticker, error=str(exc)), {})
            if barra is not None:
                barra.progress(i / total, text=f"Analizando {ticker} ({i}/{total})")

    return [resultados[t] for t in tickers if t in resultados]


# ------------------------------------------------------------------ helpers

@st.cache_data(show_spinner=False, ttl=3600)
def chispa(ticker: str, puntos: int = 52) -> list[float]:
    """Serie corta de precios para la columna GRAFICO del panel (1 año)."""
    serie = mercado.precios(ticker, anios=config.ANIOS_HISTORIA)
    if not serie:
        return []
    ultimo_anio = serie[-252:]
    paso = max(1, len(ultimo_anio) // puntos)
    return [p["cierre"] for p in ultimo_anio[::paso]]


def estilo_semaforo(df, columnas_metrica: dict[str, str]):
    """Devuelve un Styler que colorea segun los umbrales de cada metrica.

    `columnas_metrica` mapea nombre de columna -> clave de metrica.
    """
    def pintar(col):
        clave = columnas_metrica.get(col.name)
        if clave is None:
            return [""] * len(col)
        return [COLORES[base.evaluar(clave, v)] for v in col]

    return df.style.apply(pintar, axis=0, subset=list(columnas_metrica))


def pintar_negativos(valor):
    """Resalta los valores negativos.

    Reemplaza al degradado de pandas, que exige matplotlib. En un estado
    contable ademas dice mas: lo que importa no es si un numero es mayor que
    el de al lado, sino si esta en rojo.
    """
    try:
        v = float(valor)
    except (TypeError, ValueError):
        return ""
    if v != v:
        return ""
    return "color: #d64545; font-weight: 600" if v < 0 else ""


def pintar_signo(valor):
    """Verde para positivo, rojo para negativo. Para margenes de seguridad."""
    try:
        v = float(valor)
    except (TypeError, ValueError):
        return ""
    if v != v:
        return ""
    return COLORES["bueno"] if v > 0 else COLORES["malo"]


def texto_ayuda(clave: str, con_perfiles: bool = True) -> str:
    """El tooltip completo de un indicador: que mide, como se calcula y que esperar.

    Se arma en un solo lugar para que el Panel, el Detalle y el Excel digan
    exactamente lo mismo. Los valores de referencia salen de los umbrales del
    catalogo, no de un texto escrito aparte: asi el tooltip no puede
    contradecir al color de la celda.
    """
    m = base.REGISTRO.get(clave)
    if m is None:
        return ""

    partes = [f"**{m.nombre}**", "", m.ayuda or m.descripcion]

    if m.formula:
        partes += ["", f"**Como se calcula:** {m.formula}"]

    partes += ["", f"**Valores de referencia:** {base.referencia(clave)}"]

    if con_perfiles:
        ajenos = [perfiles.NOMBRES[p]
                  for p in (perfiles.BANCO, perfiles.SEGUROS, perfiles.REIT)
                  if not perfiles.aplica(clave, p)]
        propio = perfiles.EXCLUSIVAS.get(clave)
        if propio:
            partes += ["", f"**Solo aplica a:** {perfiles.NOMBRES[propio]}."]
        elif ajenos:
            partes += ["", f"**No aplica a:** {', '.join(ajenos)}. "
                           "Ahi queda vacio porque no significa nada, no porque "
                           "falte el dato."]

    return "\n".join(partes)

