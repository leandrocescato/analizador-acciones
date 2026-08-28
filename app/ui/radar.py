"""
Hoja 3 — Radar.

Las otras dos hojas contestan preguntas sobre empresas que vos elegiste mirar.
Esta trae empresas que no elegiste: es la unica parte de la app que sale a
buscar al mercado entero y deja una lista corta esperandote.

Se corre a pedido, no en automatico. Un barrido agendado acumula candidatas mas
rapido de lo que uno las mira, y el diagnostico de cada una consume cuota del
plan aunque esa semana no estes buscando nada.

La bandeja de entrada de la cartera. Cada candidata tiene tres salidas y
ninguna es quedarse: al universo, al descarte, o la dejas y la resolves mañana.
Lo que se descarta no vuelve, que es lo que evita que el radar se convierta en
la misma lista de siempre.
"""

from __future__ import annotations

import datetime as dt

import pandas as pd
import streamlit as st

from .. import almacen, diagnostico, radar
from . import comun

# Los numeros de la tabla, y como se formatean. Todos vienen del screener de
# Yahoo: por eso el encabezado de la pagina lo aclara y por eso ninguno usa el
# semaforo del Panel, que esta calibrado sobre datos de EDGAR.
COLUMNAS = {
    "Ticker": st.column_config.TextColumn("Ticker", pinned=True, width="small"),
    "Empresa": st.column_config.TextColumn("Empresa", width="medium"),
    "Sector": st.column_config.TextColumn("Sector", width="small"),
    "Industria": st.column_config.TextColumn("Industria", width="medium"),
    "Causa": st.column_config.TextColumn(
        "Causa", width="medium",
        help="Como clasifico Claude el motivo de la caida. Un guion es que "
             "todavia nadie la diagnostico: se pide desde el panel Diagnostico "
             "de la barra lateral, o desde la ficha de cada candidata."),
    "PER": st.column_config.NumberColumn("PER", format="%.1fx"),
    "EPS": st.column_config.NumberColumn("EPS", format="$%.2f"),
    "P/VL": st.column_config.NumberColumn("P/VL", format="%.2fx"),
    "Precio": st.column_config.NumberColumn("Precio", format="$%.2f"),
    "Cap": st.column_config.NumberColumn("Cap", format="compact"),
    "52 sem": st.column_config.NumberColumn(
        "52 sem", format="%.1f%%", help="Variacion del precio en un año."),
    "vs max": st.column_config.NumberColumn(
        "vs max", format="%.1f%%", help="Distancia al maximo de las 52 semanas."),
    "Dias": st.column_config.NumberColumn(
        "Dias", format="%.0f", help="Dias que lleva en el radar sin que la resuelvas."),
    "Estado": st.column_config.TextColumn("Estado", width="small"),
}


# ------------------------------------------------------------------ estado


def _estado() -> dict:
    """El radar guardado. Vive en session_state entre reruns de un mismo clic."""
    if "radar_estado" not in st.session_state:
        st.session_state["radar_estado"] = almacen.leer_radar()
    return st.session_state["radar_estado"]


def _guardar(estado: dict) -> None:
    almacen.guardar_radar(estado)
    st.session_state["radar_estado"] = estado


def _barrer_ahora(estado: dict) -> None:
    filtros = radar.normalizar(estado.get("filtros"))
    with st.spinner("Barriendo el mercado..."):
        try:
            encontradas, total = radar.barrer(filtros)
        except Exception as exc:
            st.error(f"El screener de Yahoo no contesto: {exc}")
            return
    nuevo = radar.fusionar(estado, encontradas, comun.leer_universo(), filtros, total)

    # El sector no viene en el screener y hay que pedirlo empresa por empresa.
    # Con barra, porque en la primera corrida son cuarenta pedidos.
    barra = st.progress(0.0, text="Buscando el sector de cada una...")
    radar.completar_perfil(nuevo["candidatas"], barra)
    barra.empty()

    _guardar(nuevo)
    st.toast(f"{len(nuevo['candidatas'])} candidatas ({total} pasaron el filtro).")


def _diagnosticar_tanda(estado: dict, cuantas: int) -> None:
    """Diagnostica las primeras `cuantas` pendientes, de a una y guardando.

    Se guarda despues de CADA una y no al final. Un diagnostico tarda un par de
    minutos; si a la quinta se corta la conexion o cerras la pestaña, las cuatro
    anteriores ya estan en el Gist. Perder cuatro llamadas ya pagadas por no
    haber guardado seria la peor forma de gastar la cuota.
    """
    pendientes = radar.sin_diagnostico(estado)[:cuantas]
    if not pendientes:
        st.toast("No hay ninguna pendiente.")
        return

    barra = st.progress(0.0, text="Preparando...")
    hechas = fallidas = 0
    for i, candidata in enumerate(pendientes):
        ticker = candidata["ticker"]
        barra.progress(i / len(pendientes),
                       text=f"Buscando que le paso a {ticker} ({i + 1} de {len(pendientes)})...")
        resultado = diagnostico.diagnosticar(candidata)
        candidata["diagnostico"] = resultado
        _guardar(estado)
        if resultado.get("texto"):
            hechas += 1
        else:
            fallidas += 1
    barra.empty()

    aviso = f"{hechas} diagnosticada(s)."
    if fallidas:
        aviso += f" {fallidas} fallaron: abrilas para ver que dijo."
    st.session_state["radar_aviso"] = aviso


def _panel_diagnostico(estado: dict) -> None:
    """El control que llena la columna Causa."""
    pendientes = radar.sin_diagnostico(estado)
    st.subheader("Diagnostico")

    ok, motivo = diagnostico.disponible()
    if not ok:
        st.caption(motivo)
        return

    if not pendientes:
        st.caption("Todas las candidatas vigentes ya tienen el suyo.")
        return

    st.caption(
        f"{len(pendientes)} sin diagnosticar. Cada una es una llamada a Claude "
        "con buscador web: tarda un par de minutos y sale de tu cuota del plan, "
        "no de una factura aparte. Por eso el tope de a poco.")
    cuantas = st.number_input(
        "Cuantas ahora", min_value=1, max_value=min(len(pendientes), 20),
        value=min(3, len(pendientes)), step=1, key="radar_cuantas_diag",
        help="Van en orden de la lista. Las que no entren quedan pendientes "
             "para la proxima tanda.")
    if st.button(f"Diagnosticar {int(cuantas)}", width="stretch",
                 icon=":material/psychology:"):
        _diagnosticar_tanda(estado, int(cuantas))
        st.rerun()


# ------------------------------------------------------------------ barra lateral


def _panel_filtros(estado: dict) -> None:
    st.subheader("Filtros del barrido")
    st.caption(
        "Es el corte que aplica cada barrido. Los que estan en blanco estan "
        "apagados. Se guardan donde se guarda todo lo tuyo, asi que la corrida "
        "en GitHub usa exactamente esto.")

    guardados = radar.normalizar(estado.get("filtros"))
    nuevos = {}
    for f in radar.FILTROS:
        valor = guardados.get(f.clave)
        formato = {"usd": "%.0f", "acciones": "%.0f", "pct": "%.1f",
                   "x": "%.2f", "usd_ps": "%.2f", "num": "%.2f"}[f.unidad]
        nuevos[f.clave] = st.number_input(
            f.rotulo, value=None if valor is None else float(valor),
            format=formato, help=f.ayuda, placeholder="apagado",
            key=f"radar_f_{f.clave}")

    nuevos["max_candidatas"] = st.number_input(
        "Maximo de candidatas", min_value=5, max_value=200,
        value=int(guardados.get("max_candidatas") or radar.MAX_CANDIDATAS), step=5,
        help="De las que pasan el filtro se traen las mas baratas por PER. "
             "Este numero es cuantas.")

    if st.button("Guardar filtros", width="stretch", icon=":material/save:"):
        estado = dict(estado)
        estado["filtros"] = nuevos
        _guardar(estado)
        st.toast("Filtros guardados. El proximo barrido los usa.")
        st.rerun()


def _panel_descartadas(estado: dict) -> None:
    descartadas = estado.get("descartadas") or {}
    with st.expander(f"Descartadas ({len(descartadas)})", expanded=False):
        if not descartadas:
            st.caption("Todavia no descartaste ninguna.")
            return
        st.caption("Estas no vuelven a aparecer. Si cambiaste de idea, "
                   "rehabilitala y el proximo barrido la considera de nuevo.")
        for ticker, datos in sorted(descartadas.items()):
            fila = st.container(horizontal=True, vertical_alignment="center")
            with fila:
                st.write(f"**{ticker}** · {datos.get('fecha', '')}")
                if st.button("Rehabilitar", key=f"rehab_{ticker}"):
                    _guardar(radar.rehabilitar(estado, ticker))
                    st.rerun()
            if datos.get("motivo"):
                st.caption(datos["motivo"])


# ------------------------------------------------------------------ ficha


def _ficha(estado: dict, candidata: dict) -> None:
    ticker = candidata["ticker"]
    universo = comun.leer_universo()

    st.subheader(f"{ticker} · {candidata.get('nombre') or ''}")

    diag = candidata.get("diagnostico") or {}
    if diag.get("texto"):
        if diag.get("causa"):
            st.markdown(f"**{diag['causa']}**")
        st.write(diag["texto"])
        pie = [f"Claude, {diag.get('fecha', '')}"]
        st.caption(" · ".join(pie))
        if diag.get("fuentes"):
            with st.expander("De donde lo saco"):
                for f in diag["fuentes"]:
                    st.markdown(f"- [{f['titulo']}]({f['url']})")
    elif diag.get("error"):
        st.warning(f"El diagnostico fallo: {diag['error']}", icon=":material/error:")
    else:
        st.caption("Todavia sin diagnostico. Pedilo con el boton de abajo, o "
                   "de a varias desde el panel Diagnostico de la barra lateral.")

    # ------------------------------------------------------------ acciones
    acciones = st.container(horizontal=True, vertical_alignment="center")
    with acciones:
        if st.button("Al universo", icon=":material/add:", type="primary",
                     help="La suma a tu lista y la saca del radar. A partir de "
                          "ahi aparece en el Panel, calculada con EDGAR."):
            if ticker not in universo:
                comun.escribir_universo(universo + [ticker])
            _guardar(radar.quitar(estado, ticker))
            st.session_state["radar_aviso"] = f"{ticker} entro al universo."
            st.rerun()

        if st.button("Ver en el Detalle", icon=":material/search:",
                     help="La analiza con EDGAR sin sumarla al universo."):
            # El Detalle acepta tickers de afuera del universo por su campo
            # libre: se lo manda ahi, no al selector.
            st.session_state["ticker_detalle"] = ticker
            st.session_state["ir_a_detalle"] = "(escribir otro)"
            st.session_state["ir_a_pagina"] = "Detalle"
            st.rerun()

        ok, motivo = diagnostico.disponible()
        if not diag.get("texto") and ok:
            if st.button("Diagnosticar ahora", icon=":material/psychology:"):
                with st.spinner(f"Buscando que le paso a {ticker}..."):
                    resultado = diagnostico.diagnosticar(candidata)
                candidata["diagnostico"] = resultado
                _guardar(estado)
                st.rerun()
        elif not diag.get("texto") and not ok:
            st.caption(f"Diagnostico manual no disponible: {motivo}")

    with st.form(f"descartar_{ticker}", border=False, clear_on_submit=True):
        fila = st.container(horizontal=True, vertical_alignment="bottom")
        with fila:
            motivo = st.text_input(
                "Motivo del descarte", label_visibility="collapsed",
                placeholder="Por que la descartas (opcional, pero dentro de un "
                            "año te va a servir)")
            if st.form_submit_button("Descartar", icon=":material/block:"):
                _guardar(radar.descartar(estado, ticker, motivo.strip()))
                st.session_state["radar_aviso"] = f"{ticker} descartada."
                st.rerun()


# ------------------------------------------------------------------ pagina


def _tabla(candidatas: list[dict]) -> pd.DataFrame:
    hoy = dt.date.today().isoformat()
    filas = []
    for c in candidatas:
        diag = c.get("diagnostico") or {}
        if not c.get("vigente"):
            marca = "Ya no pasa"
        elif c.get("fecha_alta") == hoy:
            marca = "Nueva"
        else:
            marca = ""
        filas.append({
            "Ticker": c.get("ticker"),
            "Empresa": (c.get("nombre") or "")[:38],
            "Sector": c.get("sector") or "—",
            "Industria": c.get("industria") or "—",
            # El guion es informacion: dice "nadie la miro todavia". Una celda
            # vacia se lee como un error de la app.
            "Causa": diag.get("causa") or ("fallo" if diag.get("error") else "—"),
            "PER": c.get("per"),
            "EPS": c.get("eps"),
            "P/VL": c.get("pvl"),
            "Precio": c.get("precio"),
            "Cap": c.get("market_cap"),
            "52 sem": c.get("var_52s"),
            "vs max": c.get("dist_max52"),
            "Dias": radar.dias_en_radar(c),
            "Estado": marca,
        })
    return pd.DataFrame(filas)


def render():
    st.title("Radar")
    st.caption(
        "Candidatas que el ultimo barrido encontro en el mercado de EE.UU. "
        "**Los numeros de esta tabla son del screener de Yahoo**, que sirve "
        "para elegir a cual mirar. Los de verdad, calculados con EDGAR, "
        "aparecen cuando la abris en el Detalle."
    )

    estado = _estado()
    candidatas = estado.get("candidatas") or []

    aviso = st.session_state.pop("radar_aviso", None)
    if aviso:
        st.toast(aviso)

    with st.sidebar:
        if st.button("Barrer ahora", width="stretch", icon=":material/radar:",
                     help="Sale a buscar candidatas nuevas al mercado entero "
                          "con los filtros de abajo. Tarda un minuto."):
            _barrer_ahora(estado)
            st.rerun()
        st.divider()
        _panel_diagnostico(estado)
        st.divider()
        _panel_filtros(estado)
        st.divider()
        _panel_descartadas(estado)

    # ---------------------------------------------------------- encabezado
    if estado.get("corrida"):
        try:
            corrida = dt.datetime.fromisoformat(estado["corrida"])
            cuando = corrida.astimezone().strftime("%d/%m %H:%M")
        except ValueError:
            cuando = estado["corrida"]
        total = estado.get("total_mercado") or 0
        nuevas = sum(1 for c in candidatas
                     if c.get("fecha_alta") == dt.date.today().isoformat())
        pendientes = len(radar.sin_diagnostico(estado))
        resumen = [f"Ultimo barrido: **{cuando}**",
                   f"{total} empresas pasaron el filtro",
                   f"**{len(candidatas)}** en el radar"]
        if nuevas:
            resumen.append(f"**{nuevas} nuevas hoy**")
        if pendientes:
            resumen.append(f"{pendientes} sin diagnostico")
        st.markdown(" · ".join(resumen))

    # La columna Causa vacia en TODA la tabla no es lo mismo que una celda
    # vacia: quiere decir que el diagnostico no corrio nunca, y eso no se
    # adivina mirando una columna de guiones.
    if candidatas and radar.nunca_diagnosticado(estado):
        ok, motivo = diagnostico.disponible()
        st.info(
            "**La columna Causa esta vacia porque el diagnostico todavia no "
            "corrio ninguna vez.** El barrido encuentra las candidatas; el "
            "parrafo que explica por que cayo cada una lo escribe Claude "
            "aparte, y eso todavia no paso.\n\n"
            + ("Podes lanzarlo ahora desde **Diagnostico**, en la barra "
               "lateral. Sale de tu cuota del plan.\n\n"
               if ok else f"Desde esta maquina no se puede: {motivo}\n\n")
            + "La otra forma es correr el workflow **Radar a pedido** en "
              "GitHub: hace lo mismo en sus servidores, con la laptop apagada. "
              "Ninguna de las dos corre sola: el radar no tiene nada agendado.",
            icon=":material/psychology_alt:")

    if not candidatas:
        st.info(
            "El radar esta vacio. Si todavia no configuraste la corrida "
            "automatica, mira `RADAR.md`; para probarlo ahora mismo, toca "
            "**Barrer ahora** en la barra lateral.",
            icon=":material/radar:")
        return

    df = _tabla(candidatas)
    # Lo mas castigado arriba: es el orden en el que uno quiere leer esta lista.
    df = df.sort_values("52 sem", ascending=True, na_position="last")

    evento = st.dataframe(
        df, column_config=COLUMNAS, hide_index=True, width="stretch",
        height=min(120 + 35 * len(df), 600),
        on_select="rerun", selection_mode="single-row")

    filas = evento.selection.rows if evento and evento.selection else []
    if not filas:
        st.caption("Toca una fila para ver el diagnostico y decidir que hacer con ella.")
        return

    elegido = df.iloc[filas[0]]["Ticker"]
    candidata = next((c for c in candidatas if c.get("ticker") == elegido), None)
    if candidata:
        st.divider()
        _ficha(estado, candidata)
