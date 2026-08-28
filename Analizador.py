"""
Analizador de Acciones — punto de entrada.

Ejecutar con:
    streamlit run Analizador.py
"""

import streamlit as st

st.set_page_config(
    page_title="Analizador de Acciones",
    page_icon="📊",
    layout="wide",
    initial_sidebar_state="expanded",
)

from app import acceso, almacen  # noqa: E402  (despues de set_page_config)
from app.ui import detalle, panel, radar  # noqa: E402


def main():
    # Cuando corre en internet hay clave; en la laptop, no hay ninguna friccion.
    if not acceso.exigir_clave():
        return

    with st.sidebar:
        st.markdown("### 📊 Analizador de Acciones")
        # El Radar manda al Detalle cuando tocas "Ver en el Detalle" en una
        # candidata, y para eso tiene que mover este radio. No puede escribir
        # `pagina` directamente: Streamlit prohibe tocar la clave de un widget
        # despues de dibujarlo, y el Radar se dibuja despues de esta linea. Por
        # eso deja una señal de un solo uso que se consume aca, antes.
        destino = st.session_state.pop("ir_a_pagina", None)
        if destino:
            st.session_state["pagina"] = destino

        pagina = st.radio(
            "Vista", ["Panel", "Detalle", "Radar"], key="pagina",
            label_visibility="collapsed",
            captions=["Una fila por accion", "Analisis profundo de una empresa",
                      "Candidatas que trajo el ultimo barrido"],
        )
        st.divider()

    if pagina == "Panel":
        panel.render()
    elif pagina == "Radar":
        radar.render()
    else:
        detalle.render()

    with st.sidebar:
        st.divider()
        guardado = almacen.estado()
        if guardado.get("error"):
            st.warning(
                "Tus tickers y notas se estan guardando **solo en este servidor**, "
                "que se reinicia solo y borra el disco. El almacen externo esta "
                f"configurado pero no responde: {guardado['error']}",
                icon=":material/cloud_off:")
        elif guardado["remoto"]:
            st.caption(
                f"Guardado en Gist privado · {guardado.get('tickers', 0)} tickers "
                f"· {guardado.get('notas', 0)} tesis")
        st.caption(
            "Fundamentals: SEC EDGAR (XBRL, auditado).  \n"
            "Mercado: Yahoo Finance, con Stooq de respaldo.  \n"
            "Los indicadores son insumos para tu criterio, no recomendaciones."
        )


if __name__ == "__main__":
    main()
