"""
El por que. La unica parte de la app que no sale de un estado contable.

El barrido contesta CUALES estan baratas. Esa pregunta la contesta un filtro y
no necesita a nadie pensando. La que importa no la contesta ningun ratio: por
que esta barata. Una caida del 40% con ROIC alto y balance limpio se ve
exactamente igual sea una oportunidad o una trampa de valor, y la diferencia
esta en las noticias de los ultimos meses, no en el balance.

Por eso este modulo le pasa cada candidata a Claude con buscador web y le pide
UNA cosa: que averigue por que cayo y lo clasifique. No opina sobre si comprar
—esa decision es tuya y la app entera esta construida para no tomarla— y
tampoco valua. Es el paso previo: el que te dice si vale la pena que le dediques
la tarde, y en que enfocar la lectura cuando se la dediques.

DOS MOTORES, Y POR QUE EL ORDEN ES ESE
--------------------------------------
1. `claude` (Claude Code, el CLI que ya tenes instalado). Corre con tu
   suscripcion Pro: no cuesta un peso aparte, sale de la misma cuota de uso que
   tus sesiones de Claude Code. Es el que se usa siempre que este disponible.
2. La API de Anthropic. Se factura APARTE del Pro, asi que esta APAGADA: no
   se enciende sola por tener la clave en el entorno, hay que pedirlo con
   `RADAR_PERMITIR_API=1`. Existe solo para una maquina sin Claude Code.

En la nube pasa lo mismo por otro camino: la Action no usa este modulo, usa la
Claude Code GitHub Action con tu token OAuth, que tambien come de la
suscripcion. Ver RADAR.md.

SIN NINGUNO DE LOS DOS NO PASA NADA
-----------------------------------
El barrido igual corre y guarda las candidatas con todos sus numeros. Lo unico
que falta es el parrafo. La app lo dice y sigue andando.
"""

from __future__ import annotations

import datetime as dt
import json
import os
import re
import shutil
import subprocess
import tempfile

MODELO = "claude-opus-5"

# Cuanto puede tardar una corrida del CLI. Con busqueda web, un minuto es lo
# normal; tres es senal de que algo se colgo.
TIMEOUT_CLI = 240

# Las cinco formas de estar castigada. La clasificacion importa mas que el
# parrafo: es lo que decide si seguis leyendo o pasas a la siguiente.
CAUSAS = [
    "Deterioro estructural",   # el negocio es peor que antes y no vuelve
    "Ciclo del sector",        # la industria entera esta abajo
    "Hecho puntual",           # un juicio, una adquisicion, un guidance fallado
    "Contabilidad o gobierno", # el problema esta en los numeros o en quien manda
    "Arrastre de mercado",     # no hay noticia propia; cayo con todo lo demas
]

# Las reglas del trabajo. Viven en un solo lugar porque las usan los dos
# caminos: este modulo cuando pedis un diagnostico desde la app, y el archivo
# de instrucciones que arma `briefing()` para la corrida diaria en la nube.
INSTRUCCIONES = """Sos un analista de renta variable que trabaja para un
inversor deep value contrarian. El te va a decir si compra o no: vos no
recomendas, no valuas y no ponderas si esta cara o barata. Tu unico trabajo es
averiguar POR QUE el precio de una accion esta donde esta, y decir si el motivo
es reversible.

Busca en la web lo que paso en los ultimos doce meses: resultados trimestrales,
guidance, cambios de management, litigios, cambios regulatorios, movimientos
del sector.

Escribi en español rioplatense, en este formato exacto y nada mas:

CAUSA: <una sola de estas etiquetas, textual: {causas}>
<Dos a cuatro oraciones con lo que paso, con fechas y cifras concretas cuando
las tengas. Despues UNA oracion que empiece con "Para descartar trampa:" y diga
que es lo especifico que hay que verificar en los estados contables para saber
si esto se revierte o es permanente.>

Reglas: si no encontras nada especifico de la empresa, deci "Arrastre de
mercado" y aclara que no hay noticia propia. Nunca inventes cifras ni fechas:
si no la encontraste, deci que no la encontraste. Sin encabezados, sin vinetas,
sin conclusiones sobre si conviene comprar."""


def _instrucciones() -> str:
    return INSTRUCCIONES.format(causas=", ".join(CAUSAS))


# ------------------------------------------------------------------ que motor hay


def _cli() -> str | None:
    return shutil.which("claude")


# EL SEGURO CONTRA UNA FACTURA QUE NO PEDISTE
# -------------------------------------------
# La regla de esta herramienta es que el diagnostico NO cuesta un peso por
# encima de la suscripcion. El camino por la API la rompe: se factura aparte.
#
# Por eso no alcanza con tener una ANTHROPIC_API_KEY en el entorno para que se
# use. Muchas herramientas dejan esa variable puesta, y bastaba con eso para
# que un boton de la app empezara a facturar en silencio. Hay que prenderlo a
# mano, y prenderlo es una decision explicita:
#
#     RADAR_PERMITIR_API=1
#
# Sin eso, si no hay Claude Code, no hay diagnostico. Que falte el parrafo es
# molesto; una factura sorpresa, no.
PERMISO_API = "RADAR_PERMITIR_API"


def _api_habilitada() -> bool:
    return os.environ.get(PERMISO_API, "").strip().lower() in ("1", "true", "si", "yes")


def backend() -> tuple[str | None, str]:
    """(motor a usar, motivo si no hay ninguno)."""
    if _cli():
        return "claude-code", ""

    if not _api_habilitada():
        return None, ("No se encontro el comando `claude`. El diagnostico corre "
                      "con tu suscripcion, y sin Claude Code no hay de donde "
                      "sacarlo. (El camino por la API existe pero se factura "
                      f"aparte: hay que habilitarlo a mano con {PERMISO_API}=1.)")

    if not os.environ.get("ANTHROPIC_API_KEY"):
        return None, (f"{PERMISO_API} esta prendido pero falta ANTHROPIC_API_KEY.")
    try:
        import anthropic  # noqa: F401
    except ImportError:
        return None, ("Hay ANTHROPIC_API_KEY pero falta el paquete: "
                      "`pip install -r requirements-radar.txt`.")
    return "api", ""


def disponible() -> tuple[bool, str]:
    motor, motivo = backend()
    return motor is not None, motivo


# ------------------------------------------------------------------ el pedido


def _pedido(candidata: dict) -> str:
    partes = [f"Empresa: {candidata.get('nombre') or candidata.get('ticker')} "
              f"({candidata.get('ticker')})."]
    var = candidata.get("var_52s")
    if var is not None:
        partes.append(f"En las ultimas 52 semanas el precio hizo {var:+.1f}%.")
    dist = candidata.get("dist_max52")
    if dist is not None:
        partes.append(f"Esta {dist:.1f}% respecto de su maximo de 52 semanas.")
    per = candidata.get("per")
    if per is not None:
        partes.append(f"Cotiza a un PER de {per:.1f} segun Yahoo Finance.")
    partes.append("Por que esta castigada?")
    return " ".join(partes)


def _partir(texto: str) -> tuple[str, str]:
    """Separa la etiqueta de causa del parrafo. Tolera que el formato se corra."""
    causa, cuerpo = "", texto.strip()
    for linea in cuerpo.splitlines():
        limpia = linea.strip()
        if limpia.upper().startswith("CAUSA:"):
            propuesta = limpia.split(":", 1)[1].strip()
            # Se acepta solo si es una de las etiquetas; si el modelo invento
            # una, el parrafo vale igual y la etiqueta queda vacia.
            for c in CAUSAS:
                if propuesta.lower().startswith(c.lower()[:12]):
                    causa = c
                    break
            cuerpo = cuerpo.replace(linea, "", 1).strip()
            break
    return causa, cuerpo


_ENLACE = re.compile(r"\[([^\]]+)\]\((https?://[^)\s]+)\)")
_ENCABEZADO_FUENTES = re.compile(r"(?im)^\s*(sources?|fuentes|referencias)\s*:")


def separar_fuentes(texto: str) -> tuple[str, list[dict]]:
    """Saca del parrafo el bloque de fuentes y lo devuelve aparte.

    Claude Code, cuando busca en la web, cierra la respuesta con una lista de
    enlaces aunque le pidas que no ponga encabezados. Es informacion buena en
    el lugar equivocado: dentro del parrafo ensucia la ficha, y en su propio
    campo se convierte en el "de donde lo saco" que te deja ir a verificar.
    """
    corte = _ENCABEZADO_FUENTES.search(texto)
    if corte:
        cuerpo, cola = texto[:corte.start()], texto[corte.start():]
    else:
        cuerpo, cola = texto, ""

    vistas, fuentes = set(), []
    for titulo, url in _ENLACE.findall(cola) + _ENLACE.findall(cuerpo):
        if url not in vistas:
            vistas.add(url)
            fuentes.append({"titulo": titulo.strip()[:120], "url": url})
    return cuerpo.strip(), fuentes[:5]


def _armar(texto: str, motor: str, costo: float | None = None) -> dict:
    causa, cuerpo = _partir(texto)
    cuerpo, fuentes = separar_fuentes(cuerpo)
    salida = {"texto": cuerpo, "causa": causa, "fuentes": fuentes,
              "fecha": dt.date.today().isoformat(), "modelo": MODELO,
              "motor": motor}
    if costo is not None:
        salida["costo"] = costo
    return salida


# ------------------------------------------------------------------ motor: Claude Code


def _via_cli(candidata: dict) -> dict:
    """Claude Code en modo no interactivo, con tu sesion y tu suscripcion.

    Corre en un directorio temporal a proposito. Lanzado desde la carpeta del
    proyecto levantaria el CLAUDE.md y los settings de la app, que no tienen
    nada que ver con leer noticias de una empresa: son varios miles de tokens
    de contexto por candidata, pagados con tu cuota, para empeorar la respuesta.
    """
    prompt = _instrucciones() + "\n\n" + _pedido(candidata)
    comando = [
        _cli(), "-p", prompt,
        "--output-format", "json",
        "--model", MODELO,
        "--allowedTools", "WebSearch",
    ]
    try:
        with tempfile.TemporaryDirectory() as vacio:
            proc = subprocess.run(comando, capture_output=True, text=True,
                                  encoding="utf-8", errors="replace",
                                  timeout=TIMEOUT_CLI, cwd=vacio)
    except subprocess.TimeoutExpired:
        return {"error": f"Claude Code no contesto en {TIMEOUT_CLI} segundos."}
    except OSError as exc:
        return {"error": f"No se pudo ejecutar `claude`: {exc}"}

    if proc.returncode != 0:
        return {"error": f"`claude` termino con codigo {proc.returncode}: "
                         f"{(proc.stderr or '').strip()[:200]}"}
    try:
        datos = json.loads(proc.stdout)
    except json.JSONDecodeError:
        return {"error": "Claude Code devolvio algo que no es JSON."}

    if datos.get("is_error"):
        return {"error": str(datos.get("result") or "Error de Claude Code")[:200]}
    texto = (datos.get("result") or "").strip()
    if not texto:
        return {"error": "Respuesta vacia de Claude Code."}
    return _armar(texto, "claude-code", datos.get("total_cost_usd"))


# ------------------------------------------------------------------ motor: API


def _via_api(candidata: dict) -> dict:
    import anthropic

    cliente = anthropic.Anthropic()
    try:
        respuesta = cliente.messages.create(
            model=MODELO,
            max_tokens=8000,
            system=_instrucciones(),
            thinking={"type": "adaptive"},
            output_config={"effort": "medium"},
            tools=[{"type": "web_search_20260209", "name": "web_search",
                    "max_uses": 5}],
            messages=[{"role": "user", "content": _pedido(candidata)}],
        )
    except Exception as exc:  # red, tarifa, clave vencida: todo termina igual
        return {"error": f"{type(exc).__name__}: {str(exc)[:200]}"}

    if respuesta.stop_reason == "refusal":
        return {"error": "El modelo declino contestar sobre esta empresa."}

    texto = "\n".join(b.text for b in respuesta.content if b.type == "text").strip()
    if not texto:
        return {"error": "Respuesta vacia del modelo."}

    salida = _armar(texto, "api")
    # Las de la API son mejores: salen de los bloques de resultado, no de
    # como el modelo decidio citarlas en el texto.
    salida["fuentes"] = _fuentes_api(respuesta) or salida["fuentes"]
    salida["costo"] = _costo_api(respuesta.usage)
    return salida


def _fuentes_api(respuesta) -> list[dict]:
    """Los articulos que efectivamente leyo, para poder ir a la fuente.

    Un error de busqueda NO levanta excepcion: llega como un bloque de
    resultado cuyo contenido, en vez de la lista de siempre, es un objeto con
    el codigo de error. Por eso el isinstance antes de recorrerlo.
    """
    salida = []
    for bloque in respuesta.content:
        if bloque.type != "web_search_tool_result":
            continue
        if not isinstance(bloque.content, list):
            continue
        for resultado in bloque.content:
            if getattr(resultado, "type", "") == "web_search_result":
                salida.append({"titulo": (resultado.title or "")[:120],
                               "url": resultado.url})
    vistas, unicas = set(), []
    for f in salida:
        if f["url"] not in vistas:
            vistas.add(f["url"])
            unicas.append(f)
    return unicas[:5]


def _costo_api(usage) -> float:
    """Dolares a precio de lista de Claude Opus 5."""
    return (usage.input_tokens / 1_000_000 * 5.00
            + usage.output_tokens / 1_000_000 * 25.00)


# ------------------------------------------------------------------ entrada


def diagnosticar(candidata: dict) -> dict:
    """Un diagnostico para una candidata. Nunca levanta: los errores se guardan.

    Que devuelva el error en vez de explotar es a proposito. El barrido diario
    corre solo, de noche, sobre quince empresas: que una cuota agotada o una
    busqueda caida corte la corrida entera y te deje sin radar seria el peor
    intercambio posible.
    """
    motor, motivo = backend()
    if motor is None:
        return {"error": motivo}
    return _via_cli(candidata) if motor == "claude-code" else _via_api(candidata)


# ------------------------------------------------------------------ la corrida en la nube


def briefing(pendientes: list[dict], carpeta_salida: str) -> str:
    """El archivo que lee Claude Code dentro de GitHub Actions.

    En la nube no se llama a este modulo empresa por empresa: corre la Claude
    Code GitHub Action, que es un agente con las manos libres. Entonces en vez
    de una llamada por candidata se le deja un encargo escrito con las mismas
    reglas de siempre, la lista del dia, y un contrato de salida —un JSON por
    empresa— que despues `scripts/radar_aplicar.py` mezcla al radar.

    El reparto es a proposito: el agente busca y escribe, pero quien toca el
    almacen es un script deterministico. Un archivo mal escrito se ignora; no
    hay forma de que una corrida rara te rompa el radar entero.
    """
    lineas = [
        "# Diagnostico de candidatas del radar",
        "",
        _instrucciones(),
        "",
        "## Como entregar el resultado",
        "",
        f"Por CADA empresa de la lista, escribi un archivo JSON en `{carpeta_salida}/`",
        "llamado `<TICKER>.json`, con exactamente estas claves:",
        "",
        "```json",
        json.dumps({
            "causa": CAUSAS[2],
            "texto": "Lo que paso, en dos a cuatro oraciones. Para descartar "
                     "trampa: que hay que mirar en los estados contables.",
            "fuentes": [{"titulo": "Titulo de la nota", "url": "https://..."}],
        }, ensure_ascii=False, indent=2),
        "```",
        "",
        "`causa` tiene que ser una de las cinco etiquetas, textual. En `texto` NO",
        "repitas la linea CAUSA. En `fuentes`, hasta cinco de las paginas que",
        "realmente leiste.",
        "",
        "Trabaja empresa por empresa y escribi cada archivo apenas la termines, no",
        "todos al final: si te quedas sin tiempo o sin cuota, lo ya escrito se",
        "guarda igual y el resto queda para mañana.",
        "",
        f"## Las {len(pendientes)} de hoy",
        "",
    ]
    for c in pendientes:
        detalle = [f"**{c.get('ticker')}** — {c.get('nombre') or 'sin nombre'}"]
        if c.get("per") is not None:
            detalle.append(f"PER {c['per']:.1f}")
        if c.get("var_52s") is not None:
            detalle.append(f"{c['var_52s']:+.1f}% en 52 semanas")
        if c.get("dist_max52") is not None:
            detalle.append(f"{c['dist_max52']:.1f}% del maximo")
        lineas.append("- " + " · ".join(detalle))
    return "\n".join(lineas) + "\n"
