"""
Lector de instancias XBRL crudas, para tapar los agujeros de la API de la SEC.

POR QUE HACE FALTA
------------------
`companyfacts` es una API de conveniencia: la SEC la arma procesando las
presentaciones, y a veces no procesa alguna. Nu Holdings presento su 20-F del
ejercicio 2025 el 8 de abril de 2026, con el XBRL completo adentro, y en agosto
de 2026 `companyfacts` seguia devolviendo datos hasta 2024. La ficha mostraba un
año de atraso sin ningun aviso: exactamente el tipo de error silencioso que
esta app trata de no cometer.

El archivo que la empresa presenta es una instancia XBRL estandar, y tiene los
mismos hechos. Este modulo la lee y devuelve la estructura EXACTA de
`companyfacts`, para que el resto del extractor no se entere de la diferencia.

QUE SE DESCARTA, PARA IGUALAR A companyfacts
--------------------------------------------
Los hechos con dimensiones (un ingreso abierto por segmento o por region) se
ignoran, igual que hace la API. Si se colaran, una empresa podria terminar con
el ingreso de su division mas chica presentado como el ingreso total.
Las etiquetas de extension propias de la empresa (`nu:...`) tambien se
descartan: no tienen significado fuera de su propio informe.
"""

from __future__ import annotations

import xml.etree.ElementTree as ET

# Espacio de nombres de la especificacion XBRL. En las instancias suele estar
# como namespace por defecto, sin prefijo.
_NS_XBRLI = "http://www.xbrl.org/2003/instance"

# Solo se leen las taxonomias estandar. El prefijo que se devuelve es el mismo
# que usa companyfacts, para que las etiquetas del catalogo sigan sirviendo.
_TAXONOMIAS = {
    "us-gaap": "us-gaap",
    "ifrs-full": "ifrs-full",
    "ifrs": "ifrs-full",
    "dei": "dei",
    "srt": "srt",
}


def _prefijo_de(uri: str) -> str | None:
    """Traduce la URI de un namespace al prefijo que usa companyfacts."""
    for clave, prefijo in _TAXONOMIAS.items():
        # Las URIs llevan version: .../us-gaap/2024 , .../ifrs-full/2024-03-27
        if f"/{clave}/" in uri or uri.rstrip("/").endswith("/" + clave):
            return prefijo
    return None


def _unidades(raiz) -> dict[str, str]:
    """id de unidad -> nombre normalizado (USD, shares, pure, USD/shares)."""
    salida: dict[str, str] = {}
    for unidad in raiz.findall(f"{{{_NS_XBRLI}}}unit"):
        ident = unidad.get("id")
        if not ident:
            continue
        medidas = [m.text.strip() for m in unidad.iter(f"{{{_NS_XBRLI}}}measure")
                   if m.text]
        limpias = [m.split(":")[-1] for m in medidas]
        if not limpias:
            continue
        # Un cociente (USD por accion) trae dos medidas, numerador y denominador.
        divide = unidad.find(f"{{{_NS_XBRLI}}}divide")
        if divide is not None and len(limpias) >= 2:
            salida[ident] = f"{limpias[0]}/{limpias[1]}"
        else:
            salida[ident] = limpias[0]
    return salida


def _contextos(raiz) -> dict[str, dict]:
    """id de contexto -> periodo. Los contextos con dimensiones se omiten."""
    salida: dict[str, dict] = {}
    for ctx in raiz.findall(f"{{{_NS_XBRLI}}}context"):
        ident = ctx.get("id")
        if not ident:
            continue
        # Dimensiones: el hecho describe un segmento, no el consolidado.
        if any(True for _ in ctx.iter("{http://xbrl.org/2006/xbrldi}explicitMember")):
            continue
        if any(True for _ in ctx.iter("{http://xbrl.org/2006/xbrldi}typedMember")):
            continue

        periodo = ctx.find(f"{{{_NS_XBRLI}}}period")
        if periodo is None:
            continue
        instante = periodo.find(f"{{{_NS_XBRLI}}}instant")
        if instante is not None and instante.text:
            salida[ident] = {"end": instante.text.strip()}
            continue
        inicio = periodo.find(f"{{{_NS_XBRLI}}}startDate")
        fin = periodo.find(f"{{{_NS_XBRLI}}}endDate")
        if inicio is not None and fin is not None and inicio.text and fin.text:
            salida[ident] = {"start": inicio.text.strip(), "end": fin.text.strip()}
    return salida


def leer(xml: str | bytes, forma: str, presentado: str) -> dict:
    """Convierte una instancia XBRL en la estructura de `companyfacts`.

    `forma` y `presentado` no estan en el archivo: vienen de la ficha de
    presentaciones y hacen falta porque el extractor filtra por tipo de
    formulario y desempata reexpresiones por fecha de presentacion.
    """
    raiz = ET.fromstring(xml)
    unidades = _unidades(raiz)
    contextos = _contextos(raiz)

    facts: dict[str, dict] = {}
    for elemento in raiz:
        ctx = elemento.get("contextRef")
        if not ctx or ctx not in contextos:
            continue
        unidad = unidades.get(elemento.get("unitRef") or "")
        if not unidad:
            continue  # sin unidad no es un hecho numerico
        if elemento.get("{http://www.w3.org/2001/XMLSchema-instance}nil") == "true":
            continue

        etiqueta = elemento.tag
        if not etiqueta.startswith("{"):
            continue
        uri, _, local = etiqueta[1:].partition("}")
        prefijo = _prefijo_de(uri)
        if prefijo is None:
            continue  # extension propia de la empresa

        texto = (elemento.text or "").strip().replace(",", "")
        if not texto:
            continue
        try:
            valor = float(texto)
        except ValueError:
            continue

        # El signo declarado se aplica igual que en la API.
        if elemento.get("sign") == "-":
            valor = -valor

        hecho = dict(contextos[ctx])
        hecho.update({"val": valor, "form": forma, "filed": presentado,
                      "fy": None, "fp": "FY"})

        bloque = facts.setdefault(prefijo, {}).setdefault(local, {"units": {}})
        bloque["units"].setdefault(unidad, []).append(hecho)

    return {"facts": facts}


def combinar(base: dict, extra: dict) -> dict:
    """Suma los hechos de `extra` a `base` sin pisar lo que ya estaba.

    Un hecho de la instancia solo entra si ese periodo no venia de la API. Asi
    la fuente principal sigue siendo `companyfacts`, y esto es un relleno.
    """
    salida = {"facts": {k: v for k, v in base.get("facts", {}).items()}}
    for k, v in base.items():
        if k != "facts":
            salida[k] = v

    agregados = 0
    for prefijo, tags in extra.get("facts", {}).items():
        destino_taxo = salida["facts"].setdefault(prefijo, {})
        for tag, bloque in tags.items():
            destino_tag = destino_taxo.setdefault(tag, {"units": {}})
            destino_unidades = destino_tag.setdefault("units", {})
            for unidad, hechos in bloque.get("units", {}).items():
                existentes = destino_unidades.setdefault(unidad, [])
                periodos = {(h.get("start"), h.get("end")) for h in existentes}
                for h in hechos:
                    clave = (h.get("start"), h.get("end"))
                    if clave in periodos:
                        continue
                    existentes.append(h)
                    periodos.add(clave)
                    agregados += 1

    salida["_hechos_agregados"] = agregados
    return salida
