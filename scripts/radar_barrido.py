"""
El barrido del radar. Se corre a pedido: no hay nada agendado que lo dispare.

Lo corre GitHub Actions cuando apretas *Run workflow*, o vos desde la laptop.
Antes tenia un cron todas las mañanas y se saco: un barrido automatico acumula
candidatas mas rapido de lo que uno las mira, y el diagnostico de cada una
consume cuota del plan aunque esa semana no estes buscando nada.

    python scripts/radar_barrido.py                    # barrido y diagnostico
    python scripts/radar_barrido.py --sin-diagnostico  # solo los numeros
    python scripts/radar_barrido.py --sin-diagnostico --exportar-pendientes datos/pendientes.md

Que hace, en orden:

  1. Lee del gist los filtros que dejaste puestos en la app y las candidatas de
     la corrida anterior, con sus descartes.
  2. Le pide al screener de Yahoo las que pasan el filtro hoy.
  3. Mezcla: las nuevas entran, las que ya estaban conservan su fecha y su
     diagnostico, las que descartaste no vuelven.
  4. Guarda todo de vuelta en el gist, que es lo que lee la app.
  5. El por que de cada candidata nueva, por uno de dos caminos:

     - En tu laptop, con `--max-diagnosticos`: los pide aca mismo, uno por uno,
       via Claude Code, con tu suscripcion (ver `app/diagnostico.py`).
     - En la nube, con `--exportar-pendientes`: NO los pide. Deja escrito el
       encargo en un archivo y termina. El que los escribe es el paso siguiente
       del workflow, que es la Claude Code GitHub Action corriendo con tu
       suscripcion, y `scripts/radar_aplicar.py` los mezcla despues.

Termina con codigo 0 aunque el diagnostico falle. Un radar con numeros y sin
parrafos sirve; una corrida abortada no deja nada.
"""

from __future__ import annotations

import argparse
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from app import almacen, diagnostico, radar  # noqa: E402

CARPETA_DIAGNOSTICOS = "datos/diagnosticos"


def main() -> int:
    ap = argparse.ArgumentParser(description="Barrido del radar, a pedido.")
    ap.add_argument("--sin-diagnostico", action="store_true",
                    help="No pide el por que. Solo trae las candidatas.")
    ap.add_argument("--max-diagnosticos", type=int, default=8,
                    help="Tope de diagnosticos en esta corrida (default 8). Es el "
                         "freno de mano del gasto: medido, cada diagnostico con "
                         "busqueda web sale del orden de USD 0,60 de cuota, asi "
                         "que un dia en que el filtro se afloje y entren ochenta "
                         "candidatas no puede convertirse en ochenta llamadas.")
    ap.add_argument("--exportar-pendientes", metavar="ARCHIVO",
                    help="Escribe el encargo para la Claude Code GitHub Action "
                         "en vez de diagnosticar aca. Implica --sin-diagnostico.")
    ap.add_argument("--carpeta-diagnosticos", default=CARPETA_DIAGNOSTICOS,
                    help="Donde el agente deja sus JSON. Solo se nombra en el "
                         "encargo; quien los lee es radar_aplicar.py.")
    args = ap.parse_args()

    estado = almacen.leer_radar()
    universo = almacen.leer_universo()
    filtros = radar.normalizar(estado.get("filtros"))

    print(f"Universo actual: {len(universo)} tickers")
    print(f"Radar de ayer:   {len(estado.get('candidatas') or [])} candidatas, "
          f"{len(estado.get('descartadas') or {})} descartadas")

    encontradas, total = radar.barrer(filtros)
    print(f"Barrido: {total} empresas pasaron el filtro; "
          f"se traen las {len(encontradas)} mas baratas por PER.")

    previas = {c.get("ticker") for c in (estado.get("candidatas") or [])}
    nuevo = radar.fusionar(estado, encontradas, universo, filtros, total)
    nuevas = [c for c in nuevo["candidatas"]
              if c.get("vigente") and c["ticker"] not in previas]
    print(f"Nuevas hoy: {len(nuevas)}"
          + (f" -> {', '.join(c['ticker'] for c in nuevas)}" if nuevas else ""))

    completadas = radar.completar_perfil(nuevo["candidatas"])
    if completadas:
        print(f"Sector e industria: completados en {completadas}.")

    # El radar se guarda ANTES de diagnosticar. Si el paso del por que falla o
    # se queda sin cuota, las candidatas del dia ya estan a salvo.
    almacen.guardar_radar(nuevo)
    destino = "gist privado" if almacen.hay_remoto() else "archivo local"
    print(f"Guardado en {destino}: {len(nuevo['candidatas'])} candidatas.")

    # -------------------------------------------------------------- el por que
    if args.exportar_pendientes:
        _exportar(nuevo, args.exportar_pendientes, args.carpeta_diagnosticos,
                  args.max_diagnosticos)
    elif args.sin_diagnostico:
        print("Diagnostico: salteado por --sin-diagnostico.")
    elif _diagnosticar(nuevo, args.max_diagnosticos):
        almacen.guardar_radar(nuevo)
        print("Radar actualizado con los diagnosticos.")
    return 0


# ------------------------------------------------------------------ en la nube


def _exportar(estado: dict, archivo: str, carpeta: str, tope: int) -> None:
    """Deja el encargo escrito y no llama a nadie."""
    pendientes = _por_prioridad(radar.sin_diagnostico(estado))[:tope]
    ruta = Path(archivo)
    ruta.parent.mkdir(parents=True, exist_ok=True)
    Path(carpeta).mkdir(parents=True, exist_ok=True)

    if not pendientes:
        # El archivo se escribe igual, vacio de trabajo: el paso siguiente del
        # workflow lo lee sin condicionales y no tiene nada que hacer.
        ruta.write_text("# Diagnostico de candidatas del radar\n\n"
                        "No hay ninguna pendiente. No hagas nada.\n",
                        encoding="utf-8")
        print("Pendientes: ninguna. No hay nada que diagnosticar hoy.")
        return

    ruta.write_text(diagnostico.briefing(pendientes, carpeta), encoding="utf-8")
    print(f"Pendientes: {len(pendientes)} -> "
          f"{', '.join(c['ticker'] for c in pendientes)}")
    print(f"Encargo escrito en {ruta}. Lo resuelve el paso siguiente del workflow.")


# ------------------------------------------------------------------ en la laptop


def _diagnosticar(estado: dict, tope: int) -> bool:
    """Pide los diagnosticos aca mismo. True si escribio alguno."""
    pendientes = radar.sin_diagnostico(estado)
    if not pendientes:
        print("Diagnostico: nada pendiente.")
        return False

    motor, motivo = diagnostico.backend()
    if motor is None:
        print(f"Diagnostico: no se puede ({motivo}). Las candidatas quedan "
              f"guardadas igual, sin el parrafo.")
        return False
    print(f"Diagnostico: usando {motor}.")

    recortadas = _por_prioridad(pendientes)[:tope]
    if len(pendientes) > tope:
        print(f"  ({len(pendientes)} pendientes, se hacen {tope} por el tope "
              f"de la corrida. El resto queda para la proxima.)")

    costo, escritos = 0.0, 0
    for i, candidata in enumerate(recortadas, 1):
        ticker = candidata["ticker"]
        resultado = diagnostico.diagnosticar(candidata)
        if resultado.get("error"):
            print(f"  [{i}/{len(recortadas)}] {ticker}: ERROR {resultado['error']}")
            continue
        costo += resultado.get("costo") or 0.0
        # `candidata` es el mismo objeto que esta en estado["candidatas"], asi
        # que escribirle el diagnostico aca ya lo deja listo para guardar.
        candidata["diagnostico"] = resultado
        escritos += 1
        print(f"  [{i}/{len(recortadas)}] {ticker}: "
              f"{resultado.get('causa') or 'sin etiqueta'}")

    if costo:
        etiqueta = ("equivalente, sale de tu suscripcion" if motor == "claude-code"
                    else "facturado a la API")
        print(f"Costo de la corrida: USD {costo:.2f} ({etiqueta}).")
    return escritos > 0


def _por_prioridad(pendientes: list[dict]) -> list[dict]:
    """Las mas castigadas primero.

    Si el tope corta la lista, que corte por las que menos probable es que te
    interesen, no por orden alfabetico.
    """
    return sorted(pendientes,
                  key=lambda c: c.get("var_52s") if c.get("var_52s") is not None else 0)


if __name__ == "__main__":
    raise SystemExit(main())
