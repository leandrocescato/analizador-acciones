"""
Porton de entrada, para cuando la app corre en internet.

Las apps de Streamlit Community Cloud son PUBLICAS: cualquiera con la URL entra.
Y aunque los datos de EDGAR sean publicos, tus tesis no lo son, ni la lista de
empresas que estas mirando.

Si hay una clave configurada en los secretos, se pide antes de mostrar nada. Si
no la hay —que es el caso cuando corre en tu laptop— no molesta con nada.

No es un sistema de usuarios ni pretende serlo: es una clave compartida para que
la app no quede abierta al que pase. Alcanza para esto y no para mas.
"""

from __future__ import annotations

import hmac

import streamlit as st

_CLAVE_ESTADO = "acceso_concedido"


def _clave_configurada() -> str | None:
    try:
        valor = st.secrets.get("clave_acceso")
    except Exception:
        return None
    return str(valor) if valor else None


def exigir_clave() -> bool:
    """True si se puede seguir. Dibuja el formulario y corta cuando no."""
    esperada = _clave_configurada()
    if not esperada:
        return True  # sin clave configurada: uso local, sin friccion
    if st.session_state.get(_CLAVE_ESTADO):
        return True

    st.title("Analizador de Acciones")
    st.caption("Esta instancia esta en internet y pide clave para entrar.")

    with st.form("acceso"):
        ingresada = st.text_input("Clave", type="password")
        enviar = st.form_submit_button("Entrar")

    if enviar:
        # compare_digest en vez de == : compara en tiempo constante y no filtra
        # cuantos caracteres acertaste por lo que tarda en responder.
        if hmac.compare_digest(ingresada, esperada):
            st.session_state[_CLAVE_ESTADO] = True
            st.rerun()
        else:
            st.error("Clave incorrecta.")

    return False
