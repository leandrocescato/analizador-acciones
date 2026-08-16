"""
Cache local en SQLite.

Dos responsabilidades distintas:

1. `obtener` / `guardar`: cache con TTL de cualquier respuesta de un proveedor.
   Los payloads se guardan como JSON comprimido con gzip, porque un companyfacts
   de la SEC pesa entre 5 y 30 MB en crudo.

2. `registrar_snapshot` / `historial_snapshots`: guarda las metricas calculadas
   cada vez que se mira una empresa. Esto es lo que una planilla no puede dar:
   dentro de seis meses vas a poder ver que PER y que ROIC tenia una accion el
   dia que la miraste, y si la tesis se movio a favor o en contra.
"""

from __future__ import annotations

import gzip
import json
import sqlite3
import threading
import time
from contextlib import contextmanager
from typing import Any

from . import config

_lock = threading.Lock()

_ESQUEMA = """
CREATE TABLE IF NOT EXISTS cache (
    clave      TEXT PRIMARY KEY,
    fuente     TEXT NOT NULL,
    payload    BLOB NOT NULL,
    ts         REAL NOT NULL
);
CREATE INDEX IF NOT EXISTS idx_cache_fuente ON cache(fuente);

CREATE TABLE IF NOT EXISTS snapshots (
    id         INTEGER PRIMARY KEY AUTOINCREMENT,
    ticker     TEXT NOT NULL,
    fecha      TEXT NOT NULL,
    metrica    TEXT NOT NULL,
    valor      REAL,
    UNIQUE(ticker, fecha, metrica)
);
CREATE INDEX IF NOT EXISTS idx_snap_ticker ON snapshots(ticker);

CREATE TABLE IF NOT EXISTS notas (
    ticker     TEXT PRIMARY KEY,
    texto      TEXT NOT NULL,
    ts         REAL NOT NULL
);
"""


@contextmanager
def conexion():
    con = sqlite3.connect(config.RUTA_CACHE, timeout=30)
    con.row_factory = sqlite3.Row
    try:
        yield con
        con.commit()
    finally:
        con.close()


def inicializar() -> None:
    with _lock, conexion() as con:
        con.executescript(_ESQUEMA)
        con.execute("PRAGMA journal_mode=WAL")


# ------------------------------------------------------------------ cache TTL

def obtener(clave: str, ttl_horas: float) -> Any | None:
    """Devuelve el payload si existe y no expiro. Si no, None."""
    with conexion() as con:
        fila = con.execute(
            "SELECT payload, ts FROM cache WHERE clave = ?", (clave,)
        ).fetchone()

    if fila is None:
        return None
    if (time.time() - fila["ts"]) > ttl_horas * 3600:
        return None

    try:
        return json.loads(gzip.decompress(fila["payload"]).decode("utf-8"))
    except (OSError, json.JSONDecodeError, UnicodeDecodeError):
        # Entrada corrupta: se trata como si no existiera y se vuelve a bajar.
        return None


def guardar(clave: str, fuente: str, payload: Any) -> None:
    blob = gzip.compress(json.dumps(payload, default=str).encode("utf-8"), compresslevel=6)
    with _lock, conexion() as con:
        con.execute(
            "INSERT OR REPLACE INTO cache (clave, fuente, payload, ts) VALUES (?,?,?,?)",
            (clave, fuente, blob, time.time()),
        )


def edad_horas(clave: str) -> float | None:
    """Antiguedad de una entrada, para poder mostrarla en la interfaz."""
    with conexion() as con:
        fila = con.execute("SELECT ts FROM cache WHERE clave = ?", (clave,)).fetchone()
    return None if fila is None else (time.time() - fila["ts"]) / 3600


def invalidar(patron: str) -> int:
    """Borra entradas cuya clave contenga `patron`. Devuelve cuantas borro."""
    with _lock, conexion() as con:
        cur = con.execute("DELETE FROM cache WHERE clave LIKE ?", (f"%{patron}%",))
        return cur.rowcount


def estadisticas() -> dict[str, Any]:
    with conexion() as con:
        filas = con.execute(
            "SELECT fuente, COUNT(*) n, SUM(LENGTH(payload)) bytes FROM cache GROUP BY fuente"
        ).fetchall()
        snaps = con.execute("SELECT COUNT(*) n FROM snapshots").fetchone()["n"]
    return {
        "por_fuente": {f["fuente"]: {"entradas": f["n"], "bytes": f["bytes"] or 0} for f in filas},
        "snapshots": snaps,
        "archivo_mb": config.RUTA_CACHE.stat().st_size / 1e6 if config.RUTA_CACHE.exists() else 0,
    }


# ------------------------------------------------------------------ snapshots

def registrar_snapshot(ticker: str, metricas: dict[str, float | None]) -> None:
    """Guarda las metricas de hoy. Reescribe si ya se corrio hoy."""
    hoy = time.strftime("%Y-%m-%d")
    filas = [
        (ticker, hoy, k, float(v))
        for k, v in metricas.items()
        if isinstance(v, (int, float)) and v == v  # descarta None y NaN
    ]
    if not filas:
        return
    with _lock, conexion() as con:
        con.executemany(
            "INSERT OR REPLACE INTO snapshots (ticker, fecha, metrica, valor) VALUES (?,?,?,?)",
            filas,
        )


def historial_snapshots(ticker: str, metrica: str | None = None) -> list[dict]:
    sql = "SELECT fecha, metrica, valor FROM snapshots WHERE ticker = ?"
    args: list[Any] = [ticker]
    if metrica:
        sql += " AND metrica = ?"
        args.append(metrica)
    sql += " ORDER BY fecha"
    with conexion() as con:
        return [dict(f) for f in con.execute(sql, args).fetchall()]


# ------------------------------------------------------------------ notas

def guardar_nota(ticker: str, texto: str) -> None:
    with _lock, conexion() as con:
        con.execute(
            "INSERT OR REPLACE INTO notas (ticker, texto, ts) VALUES (?,?,?)",
            (ticker, texto, time.time()),
        )


def leer_nota(ticker: str) -> str:
    with conexion() as con:
        fila = con.execute("SELECT texto FROM notas WHERE ticker = ?", (ticker,)).fetchone()
    return fila["texto"] if fila else ""


inicializar()

