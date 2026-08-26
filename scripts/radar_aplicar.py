"""
Mezcla al radar los diagnosticos que escribio la Claude Code GitHub Action.

    python scripts/radar_aplicar.py datos/diagnosticos

Es el tercer paso del workflow, y es a proposito un script tonto: el agente
busca y escribe archivos, pero el unico que toca el almacen es esto, que valida
antes de guardar. Un JSON mal formado se ignora con un aviso; no hay manera de
que una corrida rara del agente rompa el radar entero.
"""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from app import almacen, diagnostico  # noqa: E402


def main() -> int:
    ap = argparse.ArgumentParser(description="Aplica los diagnosticos al radar.")
    ap.add_argument("carpeta", nargs="?", default="datos/diagnosticos",
                    help="Donde estan los <TICKER>.json que escribio el agente.")
    args = ap.parse_args()

    carpeta = Path(args.carpeta)
    archivos = sorted(carpeta.glob("*.json")) if carpeta.is_dir() else []
    if not archivos:
        print(f"No hay diagnosticos en {carpeta}. Nada que aplicar.")
        return 0

    estado = almacen.leer_radar()
    por_ticker = {c.get("ticker"): c for c in (estado.get("candidatas") or [])}

    aplicados, ignorados = 0, 0
    for archivo in archivos:
        ticker = archivo.stem.strip().upper()
        candidata = por_ticker.get(ticker)
        if candidata is None:
            # Paso entre el barrido y ahora: la aprobaste o la descartaste
            # desde el telefono mientras el agente trabajaba.
            print(f"  {ticker}: ya no esta en el radar, se ignora.")
            ignorados += 1
            continue

        leido = _leer(archivo)
        if leido is None:
            print(f"  {ticker}: archivo ilegible o sin texto, se ignora.")
            ignorados += 1
            continue

        candidata["diagnostico"] = leido
        aplicados += 1
        print(f"  {ticker}: {leido.get('causa') or 'sin etiqueta'}")

    if aplicados:
        almacen.guardar_radar(estado)
        destino = "gist privado" if almacen.hay_remoto() else "archivo local"
        print(f"Guardado en {destino}: {aplicados} diagnosticos aplicados"
              + (f", {ignorados} ignorados." if ignorados else "."))
    else:
        print(f"Ningun diagnostico aplicable ({ignorados} ignorados).")
    return 0


def _leer(archivo: Path) -> dict | None:
    """Valida el JSON del agente y lo normaliza a la forma que guarda la app."""
    try:
        crudo = json.loads(archivo.read_text(encoding="utf-8"))
    except (json.JSONDecodeError, OSError):
        return None
    if not isinstance(crudo, dict):
        return None

    texto = str(crudo.get("texto") or "").strip()
    if not texto:
        return None
    # Por si el agente dejo el bloque de fuentes pegado al parrafo, ademas de
    # ponerlas en su campo.
    texto, del_texto = diagnostico.separar_fuentes(texto)

    # La causa se acepta solo si es una de las cinco. Si el agente invento una
    # etiqueta, el parrafo vale igual y la columna Causa queda vacia: es
    # preferible a una etiqueta que la app no sabe leer.
    propuesta = str(crudo.get("causa") or "").strip()
    causa = next((c for c in diagnostico.CAUSAS
                  if propuesta.lower().startswith(c.lower()[:12])), "")

    fuentes = []
    for f in (crudo.get("fuentes") or [])[:5]:
        if isinstance(f, dict) and f.get("url"):
            fuentes.append({"titulo": str(f.get("titulo") or "")[:120],
                            "url": str(f["url"])})
    fuentes = fuentes or del_texto

    return {
        "texto": texto,
        "causa": causa,
        "fuentes": fuentes,
        "fecha": _fecha_de(archivo),
        "modelo": diagnostico.MODELO,
        "motor": "claude-code-action",
    }


def _fecha_de(archivo: Path) -> str:
    import datetime as dt
    return dt.date.fromtimestamp(archivo.stat().st_mtime).isoformat()


if __name__ == "__main__":
    raise SystemExit(main())
