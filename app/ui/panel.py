"""
Hoja 1 — Panel.

Una fila por accion, una columna por indicador. Sirve para una sola cosa:
mirar 200 empresas y decidir cuales tres merecen que les dediques una tarde.

Las columnas son configurables desde la barra lateral y salen del catalogo de
metricas, asi que cualquier indicador nuevo que agregues aparece aca sin tocar
este archivo.
"""

from __future__ import annotations

import datetime as dt

import pandas as pd
import streamlit as st

from .. import alertas, cache, estilo, perfiles
from ..metricas import base
from . import comun, exportar

# ---------------------------------------------------------------- vistas
#
# Una tabla de 40 columnas no se lee: se recorre con el scroll horizontal y se
# terminan mirando las tres primeras. Por eso el panel trabaja con VISTAS, cada
# una con las columnas que contestan UNA pregunta. Se cambia de vista en la
# barra lateral, y desde ahi se puede seguir agregando o sacando a mano.
#
# La vista Esencial responde las cuatro preguntas del screening en 12 columnas:
# donde esta parada, que tan buena es, cuanto cuesta, y si aguanta.

ESENCIAL = [
    # Donde esta parada: el disparador contrarian.
    "precio", "market_cap", "dist_max52", "drawdown_max",
    # Cuanto cuesta y con que rentabilidad. El PER va entre el EPS que lo
    # explica y el forward que dice cuanto del precio depende de que el
    # consenso acierte. ROIC actual contra su promedio de 5 años se leen
    # enfrentados: si el actual esta muy por debajo, el deterioro ya empezo.
    # EV/EBITDA contra EV/EBIT, igual: la diferencia entre los dos es cuanto
    # pesa la amortizacion en el negocio.
    "eps", "per", "per_forward",
    "roic", "roic_prom_5a", "roe", "ev_ebitda", "ev_ebit",
    # Si aguanta, y si el castigo ya aparece en los numeros. Las dos
    # estimaciones NTM van pegadas al crecimiento historico a proposito: solas
    # no dicen nada, y enfrentadas muestran cuanta aceleracion esta dando por
    # descontada el consenso.
    "deuda_neta_ebitda", "margen_op_vs_prom",
    "cagr_ingresos_5a", "crec_ingresos_ntm", "crec_eps_ntm",
    "fcf_yield", "piotroski",
]

VISTAS: dict[str, list[str]] = {
    "Esencial": ESENCIAL,
    "Valuacion": [
        "precio", "market_cap", "per", "per_normalizado", "ev_ebit", "ev_ebitda",
        "ev_fcf", "fcf_yield", "fcf_yield_post_sbc", "earnings_yield",
        "p_vl_tangible", "div_yield", "shareholder_yield", "precio_vs_ncav", "epv",
    ],
    "Calidad y caja": [
        "roic", "roic_prom_5a", "roic_incremental", "roce", "margen_bruto",
        "margen_operativo", "margen_op_vs_prom", "estabilidad_margen",
        "fcf_margen", "fcf_conversion_prom5", "accruals_sloan", "sbc_fcf",
    ],
    "Solidez y riesgo": [
        "caja_neta", "deuda_neta_ebitda", "cobertura_intereses", "liquidez_corriente",
        "anios_deuda_fcf", "altman_z", "piotroski", "beneish_m",
        "anios_con_perdida", "anios_fcf_negativo", "cobertura_datos",
    ],
    "Crecimiento y capital": [
        "cagr_ingresos_5a", "cagr_ingresos_10a", "cagr_ebit_5a", "cagr_fcf_5a",
        "cagr_eps_5a", "aceleracion_ingresos", "spread_roic_wacc",
        "var_acciones_5a", "reinversion", "payout_fcf", "recompras_sobre_fcf",
    ],
    "Mercado": [
        "precio", "var_pct", "max52", "min52", "pos_rango52", "dist_max52",
        "drawdown_max", "ret_1a", "ret_3a", "ret_5a", "beta",
        "market_cap", "ev", "volumen_usd", "eps",
    ],
    # Vistas por sector. Cada una mezcla lo general que sigue valiendo con los
    # indicadores propios del negocio. Las columnas sectoriales aparecen vacias
    # en las empresas de otro tipo, asi que estas vistas se usan filtrando por
    # la columna PERFIL.
    "Banca": [
        "precio", "market_cap", "dist_max52", "drawdown_max",
        "margen_intereses", "ratio_eficiencia", "coste_riesgo",
        "prestamos_depositos", "apalancamiento", "cagr_depositos_5a",
        "roe", "roa", "p_vl_tangible", "per", "div_yield", "anios_con_perdida",
    ],
    "Seguros": [
        "precio", "market_cap", "dist_max52", "drawdown_max",
        "ratio_combinado", "ratio_siniestralidad", "ratio_gastos",
        "float_sobre_cap", "rendimiento_float", "cagr_primas_5a",
        "roe", "p_vl_tangible", "per", "div_yield", "anios_con_perdida",
    ],
    "REITs": [
        "precio", "market_cap", "dist_max52", "drawdown_max",
        "p_ffo", "ffo_yield", "payout_ffo", "cagr_ffo_5a",
        "deuda_sobre_inmuebles", "deuda_neta_ebitda", "cobertura_intereses",
        "div_yield", "var_acciones_5a", "cagr_ingresos_5a",
    ],
    "Movil": [],      # se resuelve con la lista MOVIL, definida abajo
    "Completa": [],   # se resuelve con el flag panel=True del catalogo
}

VISTA_INICIAL = "Esencial"

# En un telefono no entran diecinueve columnas: entran cuatro. Esta vista deja
# lo minimo para decidir si una empresa merece que la abras, y el resto se mira
# en el Detalle, que si se lee bien en vertical.
MOVIL = ["precio", "dist_max52", "per", "roic_prom_5a"]


def _columnas_de_vista(nombre: str) -> list[str]:
    """Claves de metrica de una vista, filtrando las que ya no existan."""
    if nombre == "Completa":
        return [m.clave for m in base.del_panel()]
    if nombre == "Movil":
        return list(MOVIL)
    return [c for c in VISTAS.get(nombre, ESENCIAL) if c in base.REGISTRO]


def _cambio_de_vista() -> None:
    """Elegir otra vista reemplaza la seleccion de columnas."""
    nueva = st.session_state["vista_panel"]
    st.session_state["_vista"] = nueva
    st.session_state["_columnas"] = _columnas_de_vista(nueva)


def _cambio_de_columnas() -> None:
    """Agregar o sacar indicadores a mano no cambia la vista elegida."""
    st.session_state["_columnas"] = list(st.session_state["cols_visibles"])


def _fila(emp, metricas: dict) -> dict:
    fila = {
        "Ticker": emp.ticker,
        "Empresa": (emp.nombre or "")[:38],
        "Sector": emp.sector or "—",
        "GRAFICO": comun.chispa(emp.ticker),
    }
    fila.update({m.clave: metricas.get(m.clave) for m in base.REGISTRO.values()})
    return fila


def _config_columnas(visibles: list[str]) -> dict:
    cfg = {
        "GRAFICO": st.column_config.LineChartColumn(
            "GRAFICO", help="Cotizacion de las ultimas 52 semanas", width="small"),
        "Ticker": st.column_config.TextColumn("Ticker", pinned=True, width="small"),
        "Empresa": st.column_config.TextColumn("Empresa", width="medium"),
    }
    for clave in visibles:
        m = base.REGISTRO[clave]
        formato = {
            "pct": "%.1f%%", "x": "%.1fx", "precio": "$%.2f",
            "dias": "%.0f d", "anios": "%.1f a", "score": "%.0f",
        }.get(m.formato)
        if m.formato == "usd":
            # Formato compacto: 3,9T y 108,2B en vez de 15 y 12 digitos. Los
            # importes de mercado abarcan seis ordenes de magnitud y en formato
            # largo la columna se come el ancho de tres.
            cfg[clave] = st.column_config.NumberColumn(
                m.nombre, help=comun.texto_ayuda(clave), format="compact")
        else:
            cfg[clave] = st.column_config.NumberColumn(
                m.nombre, help=comun.texto_ayuda(clave), format=formato or "%.2f")
    return cfg


def _filtros(df: pd.DataFrame, visibles: list[str]) -> pd.DataFrame:
    with st.sidebar.expander("Filtros", expanded=False):
        st.caption(
            "Los filtros descartan filas donde la metrica tiene dato y no cumple. "
            "Las empresas sin ese dato se conservan, para que un hueco de EDGAR "
            "no te esconda una candidata."
        )
        for clave in visibles:
            m = base.REGISTRO[clave]
            serie = pd.to_numeric(df[clave], errors="coerce").dropna()
            if serie.empty or m.formato in ("usd",):
                continue
            usar = st.checkbox(f"Filtrar {m.nombre}", key=f"chk_{clave}")
            if not usar:
                continue
            lo, hi = float(serie.min()), float(serie.max())
            if lo >= hi:
                continue
            rango = st.slider(m.nombre, lo, hi, (lo, hi), key=f"sld_{clave}")
            valores = pd.to_numeric(df[clave], errors="coerce")
            df = df[valores.isna() | valores.between(*rango)]
    return df


def _alta_rapida(universo: list[str]) -> None:
    """Alta de tickers desde el panel mismo.

    La tabla de arriba no es editable a proposito: cada celda es un calculo
    derivado de EDGAR, no un dato que tenga sentido escribir a mano. Lo unico
    editable de verdad es QUE empresas mirar, y para eso alcanza este campo.
    Acepta varios separados por espacio o coma.
    """
    with st.form("alta_ticker", clear_on_submit=True, border=False):
        fila = st.container(horizontal=True, vertical_alignment="bottom")
        with fila:
            entrada = st.text_input(
                "Agregar ticker", placeholder="Ej: META, o varios: META NVDA CRM",
                label_visibility="collapsed")
            enviar = st.form_submit_button("Agregar", icon=":material/add:")

    if not enviar or not entrada.strip():
        return

    nuevos = [t.strip().upper() for t in entrada.replace(",", " ").split() if t.strip()]
    ya_estaban = [t for t in nuevos if t in universo]
    agregar = [t for t in nuevos if t not in universo]

    if agregar:
        comun.escribir_universo(universo + agregar)
        st.session_state["recien_agregados"] = agregar
    if ya_estaban:
        st.session_state["ya_estaban"] = ya_estaban
    st.rerun()


def _avisos_alta() -> None:
    for clave, plantilla in [
        ("recien_agregados", "Agregado al universo: {}"),
        ("ya_estaban", "Ya estaba en el universo: {}"),
    ]:
        valores = st.session_state.pop(clave, None)
        if valores:
            st.toast(plantilla.format(", ".join(valores)))


def render():
    st.title("Panel")
    st.caption(
        "Una fila por accion. Fundamentals de SEC EDGAR, datos de mercado de Yahoo Finance."
    )

    universo = comun.leer_universo()
    version = st.session_state.setdefault("version_datos", 0)

    _avisos_alta()
    _alta_rapida(universo)

    # ---------------------------------------------------------- barra lateral
    with st.sidebar:
        st.subheader("Universo")
        texto = st.text_area(
            "Tickers", value="\n".join(universo), height=180,
            help="Un ticker por linea. Solo emisores que reportan a la SEC.")
        col_a, col_b = st.columns(2)
        if col_a.button("Guardar", width="stretch"):
            comun.escribir_universo(texto.split("\n"))
            st.rerun()
        if col_b.button("Actualizar", width="stretch",
                        help="Vuelve a pedirle a Yahoo los datos de mercado de "
                             "todo el universo, sin usar nada guardado. Los "
                             "estados contables no se tocan: EDGAR solo cambia "
                             "cuatro veces al año."):
            # Hay que limpiar las DOS capas. `st.cache_data` guarda las
            # metricas ya calculadas, y abajo el cache en disco guarda la foto
            # de mercado por seis horas. Borrar solo la de arriba hacia que el
            # boton volviera a armar el mismo resultado con los mismos datos
            # viejos, que es exactamente no hacer nada.
            cache.invalidar("mkt:")
            st.session_state["version_datos"] = version + 1
            st.cache_data.clear()
            st.rerun()

        st.subheader("Columnas")

        # LA ELECCION DE COLUMNAS VIVE EN UNA CLAVE QUE NO ES DE WIDGET
        # ------------------------------------------------------------
        # Streamlit descarta el estado de todo widget que no se haya dibujado
        # durante una corrida. Y `st.rerun()` corta el script donde esta: el
        # alta de tickers lo llama ANTES de esta barra lateral, asi que estos
        # dos widgets no llegaban a dibujarse y su estado se perdia. La tabla
        # quedaba con las cuatro columnas fijas y ninguna metrica, y no se
        # recuperaba sola porque la vista seguia siendo la misma.
        #
        # `_vista` y `_columnas` son claves comunes de session_state: nadie las
        # limpia. Los widgets se siembran desde ellas en cada corrida y les
        # devuelven lo que elegiste.
        st.session_state.setdefault("_vista", VISTA_INICIAL)
        st.session_state.setdefault("_columnas", _columnas_de_vista(VISTA_INICIAL))

        # El espejo se actualiza en callbacks, que Streamlit corre ANTES de
        # volver a ejecutar el script. Hacerlo despues del widget no sirve:
        # cuando tocas el selector, la corrida siguiente empieza sembrando el
        # widget con el valor viejo y tu eleccion se pierde antes de leerse.
        # Y se siembran los widgets desde el espejo: si en la corrida anterior
        # no llegaron a dibujarse, su estado no existe y hay que reponerlo.
        st.session_state["vista_panel"] = st.session_state["_vista"]
        st.session_state["cols_visibles"] = list(st.session_state["_columnas"])

        st.selectbox(
            "Vista", list(VISTAS), key="vista_panel", on_change=_cambio_de_vista,
            help="Cada vista trae las columnas que contestan una pregunta. "
                 "Esencial alcanza para barrer el universo; las otras son para "
                 "cuando ya tenes una candidata y queres profundizar un angulo.",
        )
        st.multiselect(
            "Indicadores", list(base.REGISTRO), key="cols_visibles",
            on_change=_cambio_de_columnas,
            format_func=lambda c: f"{base.REGISTRO[c].nombre}  ({base.REGISTRO[c].grupo})",
            help="Sobre la vista elegida podes agregar o sacar lo que quieras.",
        )

    vista = st.session_state["_vista"]
    visibles = list(st.session_state["_columnas"])

    if not universo:
        st.info("Agrega tickers en la barra lateral para empezar.")
        return

    # ---------------------------------------------------------- carga
    barra = st.progress(0.0, text="Analizando...")
    pares = comun.cargar_varias(universo, version, barra)
    barra.empty()

    fallidas = [(e.ticker, e.error) for e, _ in pares if e.error]
    validas = [(e, m) for e, m in pares if e.tiene_datos()]
    # El perfil ya no ocupa una columna, pero sigue haciendo falta saber si hay
    # alguna financiera en la tabla: es lo que explica sus celdas vacias.
    hay_financieras = any(e.perfil != perfiles.GENERAL for e, _ in validas)

    if not validas:
        st.error("No se pudo analizar ningun ticker.")
        for t, err in fallidas:
            st.write(f"- **{t}**: {err}")
        return

    df = pd.DataFrame([_fila(e, m) for e, m in validas])

    # ---------------------------------------------------------- filtros y orden
    df = _filtros(df, visibles)

    # El sparkline va detras de Sector: no lo nombraste en el orden nuevo, pero
    # fue lo primero que pediste cuando armamos esto y ver la forma del precio
    # al lado del nombre es media lectura. Sacarlo es borrar una linea de aca.
    # En la vista Movil tambien sobran las fijas: el nombre largo de la empresa
    # y el sector se comen el ancho de dos indicadores.
    if vista == "Movil":
        fijas = ["Ticker", "GRAFICO"]
    else:
        fijas = ["Ticker", "Empresa", "Sector", "GRAFICO"]
    columnas = fijas + [c for c in visibles if c not in fijas]

    barra_orden = st.container(horizontal=True, vertical_alignment="bottom")
    with barra_orden:
        orden_por = st.selectbox(
            "Ordenar por", ["(sin orden)"] + visibles,
            format_func=lambda c: c if c == "(sin orden)" else base.REGISTRO[c].nombre)
        # Por defecto lo "mejor" queda arriba, pero en las metricas neutras (el
        # margen contra su promedio, sin ir mas lejos) lo interesante esta en el
        # extremo negativo, asi que hay que poder dar vuelta el orden.
        invertir = st.checkbox("Invertir", help="Da vuelta el orden de la columna elegida.")

    if orden_por != "(sin orden)":
        ascendente = base.REGISTRO[orden_por].mejor == "bajo"
        df = df.sort_values(orden_por, ascending=ascendente != invertir,
                            na_position="last")

    # ---------------------------------------------------------- tabla
    vista = df[columnas]
    numericas = {c: c for c in visibles if base.REGISTRO[c].umbrales}
    estilo = comun.estilo_semaforo(vista, numericas) if numericas else vista

    evento = st.dataframe(
        estilo,
        column_config=_config_columnas(visibles),
        hide_index=True,
        width="stretch",
        height=min(120 + 35 * len(vista), 760),
        on_select="rerun",
        selection_mode="single-row",
    )

    # Clic en una fila lleva esa empresa al Detalle, que es lo que uno quiere
    # hacer apenas encuentra algo interesante en el panel.
    filas = evento.selection.rows if evento and evento.selection else []
    if filas:
        elegido = vista.iloc[filas[0]]["Ticker"]
        if st.session_state.get("ticker_detalle") != elegido:
            st.session_state["ticker_detalle"] = elegido
            # Señal de un solo uso que el Detalle consume para mover su
            # selector. Tiene que ser una clave aparte: si el Detalle mirara
            # `ticker_detalle`, no podria distinguir un clic tuyo aca de lo que
            # el mismo escribio en la corrida anterior, y terminaria pisando la
            # empresa que acabas de elegir alla.
            st.session_state["ir_a_detalle"] = elegido
            st.rerun()
        st.info(
            f"**{elegido}** seleccionada. Abri la vista **Detalle** en la barra "
            "lateral para el analisis completo.",
            icon=":material/arrow_forward:",
        )

    nota_perfiles = ""
    if hay_financieras:
        nota_perfiles = (
            " En bancos, seguros y REITs las celdas vacias de ROIC, EV/EBIT, "
            "Altman o caja libre **no son datos faltantes**: son indicadores que "
            "no aplican a un balance financiero. Para esas empresas estan las "
            "vistas **Banca**, **Seguros** y **REITs**, con los indicadores "
            "propios de cada negocio."
        )
    st.caption(
        f"{len(vista)} de {len(universo)} tickers. "
        "Verde / amarillo / rojo son heuristicas de valor, no veredictos: "
        "senialan donde mirar." + nota_perfiles
    )

    if fallidas:
        with st.expander(f"{len(fallidas)} ticker(s) sin datos"):
            for t, err in fallidas:
                st.write(f"- **{t}**: {err}")

    # ---------------------------------------------------------- pie
    pie = st.container(horizontal=True, vertical_alignment="center")
    with pie:
        st.download_button(
            "Descargar Excel",
            data=exportar.panel_a_excel(vista, visibles),
            file_name=f"panel_{dt.date.today():%Y-%m-%d}.xlsx",
            mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
            icon=":material/download:",
            help="Cada columna va con su formato real (%, x, $, millones), el "
                 "semaforo como color de fondo, autofiltro y la explicacion de "
                 "cada indicador como comentario en el encabezado.",
        )
        est = cache.estadisticas()
        st.caption(f"Cache: {est['archivo_mb']:.0f} MB · {est['snapshots']} snapshots")


