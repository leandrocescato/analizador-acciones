"""
Configuracion central del Analizador de Acciones.

Resuelve tres cosas al importarse:
  1. Rutas del proyecto (datos, cache).
  2. El problema de SSL de Avast en esta maquina (ver nota abajo).
  3. Parametros de negocio: años de historia, TTLs de cache, user-agent de la SEC.

Nota sobre SSL: Avast Web Shield intercepta TLS en esta maquina. El certificado
raiz de Avast no esta en el bundle de certifi, asi que `requests` falla con
SSLCertVerificationError aunque el navegador ande bien. La solucion es combinar
ambos bundles en un archivo y apuntar REQUESTS_CA_BUNDLE / SSL_CERT_FILE ahi.
Se hace automaticamente en preparar_ssl(), que es idempotente.
"""

from __future__ import annotations

import os
from pathlib import Path

import certifi

# ---------------------------------------------------------------- rutas

RAIZ = Path(__file__).resolve().parent.parent
DIR_DATOS = RAIZ / "datos"
DIR_DATOS.mkdir(exist_ok=True)

RUTA_CACHE = DIR_DATOS / "cache.db"
RUTA_UNIVERSO = DIR_DATOS / "universo.txt"
RUTA_RADAR = DIR_DATOS / "radar.json"
RUTA_CA_BUNDLE = DIR_DATOS / "ca_bundle.pem"

# ---------------------------------------------------------------- SSL / Avast

CERT_AVAST = Path(r"C:\ProgramData\Avast Software\Avast\wscert.pem")


def preparar_ssl() -> str | None:
    """Combina certifi + el certificado de Avast y lo deja activo en el entorno.

    Devuelve la ruta del bundle usado, o None si no hizo falta intervenir.
    Es seguro llamarla muchas veces: solo reescribe el archivo si falta o si
    el certificado de Avast cambio de fecha.
    """
    if not CERT_AVAST.exists():
        # Maquina sin Avast: certifi alcanza.
        return None

    hay_que_regenerar = (
        not RUTA_CA_BUNDLE.exists()
        or RUTA_CA_BUNDLE.stat().st_mtime < CERT_AVAST.stat().st_mtime
    )

    if hay_que_regenerar:
        partes = [
            Path(certifi.where()).read_text(encoding="utf-8", errors="ignore"),
            CERT_AVAST.read_text(encoding="utf-8", errors="ignore"),
        ]
        RUTA_CA_BUNDLE.write_text("\n".join(partes), encoding="utf-8")

    ruta = str(RUTA_CA_BUNDLE)
    os.environ["REQUESTS_CA_BUNDLE"] = ruta
    os.environ["SSL_CERT_FILE"] = ruta
    os.environ["CURL_CA_BUNDLE"] = ruta
    return ruta


# Se ejecuta al importar: cualquier modulo que use requests ya lo encuentra listo.
BUNDLE_SSL = preparar_ssl()

# ---------------------------------------------------------------- negocio

# Historia de estados contables. 15 años cubre 2008-09 y 2020: sin eso no se
# puede distinguir un margen ciclicamente deprimido de uno estructuralmente roto.
ANIOS_HISTORIA = 15

# La SEC exige un User-Agent con un email real; sin eso devuelve 403.
# En la nube el email viaja por los secretos de Streamlit, para no dejarlo
# escrito en un repositorio publico.


def _email_sec() -> str:
    desde_entorno = os.environ.get("EMAIL_SEC")
    if desde_entorno:
        return desde_entorno
    try:
        import streamlit as st
        valor = st.secrets.get("email_sec")
        if valor:
            return str(valor)
    except Exception:
        pass
    # Respaldo para uso local. En la nube va por secretos: ver DESPLIEGUE.md.
    return "leandro.cescato@gmail.com"


EMAIL_SEC = _email_sec()
USER_AGENT_SEC = f"Analizador de Acciones ({EMAIL_SEC})"

# La SEC pide no superar 10 req/s. Nos quedamos comodos.
PAUSA_SEC_SEG = 0.15

# TTL del cache, en horas. Los estados contables cambian 4 veces al año;
# el precio cambia todo el tiempo. No tiene sentido el mismo TTL para ambos.
TTL_FUNDAMENTALS_H = 24 * 7
TTL_MERCADO_H = 6
TTL_PRECIOS_H = 12
TTL_CIK_H = 24 * 30

# Una foto de mercado a la que le falto algo NO es la respuesta: es un fallo
# pasajero de Yahoo, que rechaza seguido cuando le entran varios pedidos
# juntos. Se guarda igual, para no volver a golpearlo en cada corrida, pero
# vence rapido y se cura sola. Con el TTL normal, un rechazo de un segundo
# dejaba tres columnas vacias durante seis horas.
TTL_MERCADO_PARCIAL_H = 0.25

# Tasa libre de riesgo por defecto para el WACC del DCF inverso.
# Se puede sobreescribir desde la interfaz.
TASA_LIBRE_RIESGO = 0.042
PRIMA_RIESGO_MERCADO = 0.050

