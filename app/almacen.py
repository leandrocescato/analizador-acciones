"""
Donde viven las dos cosas que vos escribis: el universo de tickers y tus tesis.

EL PROBLEMA
-----------
Streamlit Community Cloud borra el disco en cada reinicio, y reinicia cuando la
app queda un rato sin uso. Todo lo que se guarde en un archivo desaparece: si
agregas un ticker desde el movil, al dia siguiente no esta.

Los datos de EDGAR no importan, se vuelven a bajar. Lo que no se puede perder es
lo que escribiste vos, que no esta en ningun lado mas.

LA SOLUCION
-----------
Un Gist privado de GitHub como almacen. Es gratis, no necesita otra cuenta —el
repositorio ya va a estar en GitHub— y siendo privado tus notas no quedan
publicas aunque el codigo si lo este.

Cuando corre en tu laptop y no hay credenciales configuradas, usa los archivos
locales de siempre. El mismo codigo sirve en los dos lados y no hace falta
recordar en cual estas.

QUE NO SE GUARDA AFUERA
-----------------------
El historial de mediciones (los snapshots) se queda en el SQLite local. En la
nube se pierde en cada reinicio y se vuelve a construir solo a medida que abris
empresas. Es un historial de datos derivados: se puede reconstruir. Tus notas,
no.
"""

from __future__ import annotations

import json

import requests
import streamlit as st

from . import cache, config

_API_GIST = "https://api.github.com/gists/{gist}"
_ARCHIVO_UNIVERSO = "universo.json"
_ARCHIVO_NOTAS = "notas.json"
_TIMEOUT = 20

UNIVERSO_INICIAL = ["META", "NVDA", "TSLA", "AAPL", "GOOGL", "NU"]


# ------------------------------------------------------------------ credenciales


def _secreto(nombre: str) -> str | None:
    """Lee un secreto sin explotar cuando no hay archivo de secretos."""
    try:
        valor = st.secrets.get(nombre)
    except Exception:
        return None
    return str(valor).strip() or None if valor else None


def hay_remoto() -> bool:
    """True si esta configurado el almacen externo."""
    return bool(_secreto("github_token") and _secreto("gist_id"))


def _encabezados() -> dict:
    return {
        "Authorization": f"Bearer {_secreto('github_token')}",
        "Accept": "application/vnd.github+json",
        "X-GitHub-Api-Version": "2022-11-28",
    }


# ------------------------------------------------------------------ gist


@st.cache_data(show_spinner=False, ttl=60)
def _bajar_gist(_version: int = 0) -> dict:
    """Contenido del gist, como {archivo: objeto}. Cacheado un minuto.

    El TTL corto es a proposito: cada rerun de Streamlit volveria a pedirlo, y
    la API de GitHub tiene limite de 5000 pedidos por hora. Un minuto alcanza
    para que la app se sienta instantanea sin gastar la cuota.
    """
    url = _API_GIST.format(gist=_secreto("gist_id"))
    resp = requests.get(url, headers=_encabezados(), timeout=_TIMEOUT)
    resp.raise_for_status()

    salida = {}
    for nombre, datos in resp.json().get("files", {}).items():
        contenido = datos.get("content")
        if datos.get("truncated") and datos.get("raw_url"):
            contenido = requests.get(datos["raw_url"], timeout=_TIMEOUT).text
        try:
            salida[nombre] = json.loads(contenido) if contenido else None
        except json.JSONDecodeError:
            salida[nombre] = None
    return salida


def _subir_gist(archivo: str, contenido) -> None:
    url = _API_GIST.format(gist=_secreto("gist_id"))
    cuerpo = {"files": {archivo: {"content": json.dumps(contenido, ensure_ascii=False,
                                                        indent=1)}}}
    resp = requests.patch(url, headers=_encabezados(), json=cuerpo, timeout=_TIMEOUT)
    resp.raise_for_status()
    # Lo que acabamos de escribir tiene que verse en la proxima lectura.
    _bajar_gist.clear()


# ------------------------------------------------------------------ universo


def _universo_local() -> list[str]:
    if not config.RUTA_UNIVERSO.exists():
        _escribir_universo_local(UNIVERSO_INICIAL)
    crudo = config.RUTA_UNIVERSO.read_text(encoding="utf-8")
    return _limpiar(crudo.replace(",", "\n").split("\n"))


def _escribir_universo_local(tickers: list[str]) -> None:
    cabecera = "# Un ticker por linea. Solo emisores que reportan a la SEC.\n"
    config.RUTA_UNIVERSO.write_text(
        cabecera + "\n".join(_limpiar(tickers)), encoding="utf-8")


def _limpiar(tickers) -> list[str]:
    vistos, salida = set(), []
    for t in tickers:
        t = str(t).strip().upper()
        if t and not t.startswith("#") and t not in vistos:
            vistos.add(t)
            salida.append(t)
    return salida


def leer_universo() -> list[str]:
    if not hay_remoto():
        return _universo_local()
    try:
        guardado = _bajar_gist().get(_ARCHIVO_UNIVERSO)
    except Exception:
        # Si GitHub no contesta, mejor seguir con lo ultimo que haya en disco
        # que dejar la app sin universo.
        return _universo_local()
    if not guardado:
        escribir_universo(UNIVERSO_INICIAL)
        return list(UNIVERSO_INICIAL)
    return _limpiar(guardado)


def escribir_universo(tickers: list[str]) -> None:
    limpios = _limpiar(tickers)
    # Siempre se escribe el archivo local: sirve de respaldo y de cache.
    _escribir_universo_local(limpios)
    if hay_remoto():
        _subir_gist(_ARCHIVO_UNIVERSO, limpios)


# ------------------------------------------------------------------ notas


def leer_nota(ticker: str) -> str:
    ticker = ticker.strip().upper()
    if not hay_remoto():
        return cache.leer_nota(ticker)
    try:
        notas = _bajar_gist().get(_ARCHIVO_NOTAS) or {}
    except Exception:
        return cache.leer_nota(ticker)
    return str(notas.get(ticker, "") or "")


def guardar_nota(ticker: str, texto: str) -> None:
    ticker = ticker.strip().upper()
    cache.guardar_nota(ticker, texto)
    if not hay_remoto():
        return
    try:
        notas = dict(_bajar_gist().get(_ARCHIVO_NOTAS) or {})
    except Exception:
        notas = {}
    if texto.strip():
        notas[ticker] = texto
    else:
        notas.pop(ticker, None)
    _subir_gist(_ARCHIVO_NOTAS, notas)


# ------------------------------------------------------------------ diagnostico


def estado() -> dict:
    """Para mostrar en la interfaz donde se estan guardando las cosas."""
    if not hay_remoto():
        return {"remoto": False, "detalle": "Archivos locales en `datos/`."}
    try:
        contenido = _bajar_gist()
        return {
            "remoto": True,
            "detalle": "Gist privado de GitHub.",
            "tickers": len(contenido.get(_ARCHIVO_UNIVERSO) or []),
            "notas": len(contenido.get(_ARCHIVO_NOTAS) or {}),
        }
    except Exception as exc:
        return {"remoto": True, "error": str(exc)[:120],
                "detalle": "Gist configurado pero no responde."}
