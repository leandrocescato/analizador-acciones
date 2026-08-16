"""
Adaptador de SEC EDGAR — la unica fuente auditada del sistema.

Endpoints usados:
  - https://www.sec.gov/files/company_tickers.json   (ticker -> CIK)
  - https://data.sec.gov/api/xbrl/companyfacts/CIK##########.json

COMO SE ELIGE EL AÑO FISCAL
----------------------------
El campo `fy` que trae cada hecho NO es el año del dato: es el año fiscal del
*informe* donde aparecio. Un 10-K de 2023 trae comparativos de 2022 y 2021, y
los tres hechos vienen con fy=2023. Usarlo desalinea toda la serie.

Por eso el año se deriva de la fecha de cierre del periodo (`end`), con un
ajuste para las empresas de ejercicio 52/53 semanas que cierran en los primeros
dias de enero. Consecuencia conocida y aceptada: los retailers que cierran a fin
de enero o principios de febrero pueden quedar etiquetados un año adelante
respecto de como ellos mismos nombran su ejercicio. No afecta el analisis porque
todos los conceptos de una misma empresa usan la misma regla y quedan alineados.

RESOLUCION DE ETIQUETAS: ver la nota en `conceptos.py`. Se hace año por año.
"""

from __future__ import annotations

import datetime as dt
import threading
import time

import requests

from .. import cache, config, perfiles
from ..conceptos import Concepto, POR_CLAVE, TODOS
from . import instancia_xbrl

_URL_TICKERS = "https://www.sec.gov/files/company_tickers.json"
_URL_FACTS = "https://data.sec.gov/api/xbrl/companyfacts/CIK{cik}.json"
_URL_SUBMISSIONS = "https://data.sec.gov/submissions/CIK{cik}.json"

_ENCABEZADOS = {
    "User-Agent": config.USER_AGENT_SEC,
    "Accept-Encoding": "gzip, deflate",
    "Accept": "application/json",
}

_FORMAS_ANUALES = ("10-K", "20-F", "40-F")
_ESPACIOS = ("us-gaap", "ifrs-full", "dei")

_lock_ritmo = threading.Lock()
_ultimo_pedido = 0.0


class ErrorEdgar(RuntimeError):
    """Falla recuperable al hablar con EDGAR (ticker inexistente, 403, etc.)."""


def _pedir(url: str, timeout: int = 45, intentos: int = 3) -> dict:
    """GET contra la SEC respetando el limite de velocidad que pide su politica.

    Reintenta cuando la SEC frena por exceso de pedidos. Hace falta sobre todo
    corriendo en la nube: ahi la IP es compartida con otras aplicaciones, y el
    limite de la SEC se cuenta por IP, asi que se puede llegar al tope sin haber
    hecho casi nada. La espera se duplica en cada intento.
    """
    global _ultimo_pedido

    for intento in range(intentos):
        with _lock_ritmo:
            espera = config.PAUSA_SEC_SEG - (time.time() - _ultimo_pedido)
            if espera > 0:
                time.sleep(espera)
            _ultimo_pedido = time.time()

        try:
            resp = requests.get(url, headers=_ENCABEZADOS, timeout=timeout)
        except requests.RequestException as exc:
            if intento == intentos - 1:
                raise ErrorEdgar(f"No se pudo contactar a la SEC: {exc}") from exc
            time.sleep(2 ** intento)
            continue

        if resp.status_code in (429, 503):
            if intento == intentos - 1:
                raise ErrorEdgar(
                    "La SEC esta limitando los pedidos desde esta direccion "
                    f"(HTTP {resp.status_code}). Suele pasar en servidores "
                    "compartidos. Espera unos minutos y volve a intentar."
                )
            time.sleep(2 ** intento)
            continue

        if resp.status_code == 403:
            raise ErrorEdgar(
                "La SEC devolvio 403. Revisa que el email del User-Agent sea "
                "real: se configura en EMAIL_SEC o en los secretos de Streamlit."
            )
        if resp.status_code == 404:
            raise ErrorEdgar("La SEC no tiene datos XBRL para ese CIK (404).")

        resp.raise_for_status()
        return resp.json()

    raise ErrorEdgar("La SEC no respondio despues de varios intentos.")


# ------------------------------------------------------------------ CIK

def mapa_tickers() -> dict[str, str]:
    """Diccionario ticker -> CIK de 10 digitos, cacheado un mes.

    Reemplaza la tabla de CIKs que estaba escrita a mano en el Apps Script:
    ahi hacia falta porque la SEC bloquea a los servidores de Google, pero
    desde tu maquina el archivo oficial se baja sin problema.
    """
    clave = "sec:tickers"
    datos = cache.obtener(clave, config.TTL_CIK_H)
    if datos is None:
        crudo = _pedir(_URL_TICKERS)
        datos = {
            str(fila["ticker"]).upper(): str(fila["cik_str"]).zfill(10)
            for fila in crudo.values()
        }
        cache.guardar(clave, "sec", datos)
    return datos


def cik_de(ticker: str) -> str:
    ticker = ticker.strip().upper()
    mapa = mapa_tickers()
    if ticker in mapa:
        return mapa[ticker]
    # Algunos tickers de clases usan guion en EDGAR y punto en Yahoo (BRK.B / BRK-B).
    alterno = ticker.replace(".", "-")
    if alterno in mapa:
        return mapa[alterno]
    raise ErrorEdgar(
        f"'{ticker}' no figura en el listado oficial de la SEC. "
        "Puede ser un ADR sin XBRL, un ticker extranjero o estar mal escrito."
    )


# ------------------------------------------------------------------ companyfacts

def companyfacts(ticker: str) -> dict:
    cik = cik_de(ticker)
    clave = f"sec:facts:{cik}"
    datos = cache.obtener(clave, config.TTL_FUNDAMENTALS_H)
    if datos is None:
        datos = _pedir(_URL_FACTS.format(cik=cik))
        cache.guardar(clave, "sec", datos)
    return datos


def identidad(ticker: str) -> dict:
    """Ficha del emisor: codigo SIC y su ultima presentacion anual.

    Es un pedido aparte de companyfacts. Solo se guarda lo que se usa, no el
    submissions entero, que trae el historico completo de presentaciones y pesa
    varios megas. Se cachea una semana: el rubro no cambia nunca, pero la
    ultima presentacion si, y es lo que permite detectar que la API se quedo
    atras.
    """
    cik = cik_de(ticker)
    clave = f"sec:ident:{cik}"
    datos = cache.obtener(clave, config.TTL_FUNDAMENTALS_H)
    if datos is None:
        crudo = _pedir(_URL_SUBMISSIONS.format(cik=cik))
        datos = {
            "sic": str(crudo.get("sic") or ""),
            "sic_desc": str(crudo.get("sicDescription") or ""),
            "nombre": str(crudo.get("name") or ""),
            "ultimo_anual": _ultima_anual(crudo),
        }
        cache.guardar(clave, "sec", datos)
    return datos


def _ultima_anual(submissions: dict) -> dict | None:
    """La presentacion anual mas reciente: forma, ejercicio y accession."""
    recientes = submissions.get("filings", {}).get("recent", {})
    campos = ("form", "filingDate", "reportDate", "accessionNumber")
    if not all(c in recientes for c in campos):
        return None

    mejor = None
    for forma, presentado, periodo, accession in zip(*(recientes[c] for c in campos)):
        if not str(forma).startswith(_FORMAS_ANUALES) or not periodo:
            continue
        if mejor is None or periodo > mejor["periodo"]:
            mejor = {"forma": forma, "presentado": presentado,
                     "periodo": periodo, "accession": accession}
    return mejor


def _ultimo_cierre(facts: dict) -> str | None:
    """Fecha de cierre mas reciente que trae la API, mirando solo informes anuales."""
    ultimo = None
    for espacio, tags in facts.get("facts", {}).items():
        if espacio == "dei":
            continue
        for bloque in tags.values():
            for hechos in bloque.get("units", {}).values():
                for h in hechos:
                    if not str(h.get("form", "")).startswith(_FORMAS_ANUALES):
                        continue
                    fin = h.get("end")
                    if fin and (ultimo is None or fin > ultimo):
                        ultimo = fin
    return ultimo


def _instancia_de(cik: str, accession: str) -> bytes | None:
    """Descarga el documento de instancia XBRL de una presentacion."""
    sin_guiones = accession.replace("-", "")
    base = f"https://www.sec.gov/Archives/edgar/data/{int(cik)}/{sin_guiones}"
    try:
        indice = _pedir(f"{base}/index.json")
    except Exception:
        return None

    nombres = [i.get("name", "") for i in indice.get("directory", {}).get("item", [])]
    # El documento de instancia de un XBRL en linea termina en `_htm.xml`. Se
    # descartan las linkbases (_cal, _def, _lab, _pre), que no traen hechos.
    candidatos = [n for n in nombres if n.endswith("_htm.xml")]
    if not candidatos:
        candidatos = [n for n in nombres
                      if n.endswith(".xml")
                      and not n.endswith(("_cal.xml", "_def.xml", "_lab.xml",
                                          "_pre.xml", "FilingSummary.xml"))]
    if not candidatos:
        return None

    resp = requests.get(f"{base}/{candidatos[0]}", headers=_ENCABEZADOS, timeout=120)
    if resp.status_code != 200:
        return None
    return resp.content


def completar_con_instancia(ticker: str, facts: dict, ident: dict) -> dict:
    """Rellena los hechos que la API todavia no publico.

    `companyfacts` es una API de conveniencia y a veces se atrasa: el 20-F de NU
    del ejercicio 2025, presentado el 8 de abril de 2026, seguia sin aparecer
    cuatro meses despues. La presentacion en si tiene el XBRL completo, asi que
    cuando la ultima presentacion anual es mas nueva que lo que devuelve la API,
    se lee esa instancia y se completan las series.
    """
    ultima = (ident or {}).get("ultimo_anual")
    if not ultima or not ultima.get("periodo") or not ultima.get("accession"):
        return facts

    cierre_api = _ultimo_cierre(facts)
    if cierre_api is not None and ultima["periodo"] <= cierre_api:
        return facts  # la API esta al dia

    # El contenido de una presentacion no cambia nunca: se cachea por accession.
    clave = f"sec:instancia:{ultima['accession']}"
    extra = cache.obtener(clave, config.TTL_CIK_H)
    if extra is None:
        crudo = _instancia_de(cik_de(ticker), ultima["accession"])
        if crudo is None:
            return facts
        try:
            extra = instancia_xbrl.leer(crudo, ultima["forma"], ultima["presentado"])
        except Exception:
            return facts  # nunca romper el analisis por un relleno
        cache.guardar(clave, "sec", extra)

    return instancia_xbrl.combinar(facts, extra)


def _etiquetas_usadas(facts: dict) -> set[str]:
    """Todos los nombres de etiqueta que la empresa reporta, en cualquier taxonomia."""
    usadas: set[str] = set()
    for espacio, tags in facts.get("facts", {}).items():
        if espacio != "dei":
            usadas.update(tags)
    return usadas


# ------------------------------------------------------------------ año fiscal

def _anio_fiscal(fin: str) -> int | None:
    try:
        fecha = dt.date.fromisoformat(fin)
    except (ValueError, TypeError):
        return None
    # Ejercicios de 52/53 semanas que cierran en los primeros dias de enero
    # pertenecen, en los hechos, al año anterior.
    if fecha.month == 1 and fecha.day <= 14:
        return fecha.year - 1
    return fecha.year


def _duracion_valida(hecho: dict) -> bool:
    """Un ejercicio anual dura entre ~11 y ~13 meses. Descarta trimestres y semestres."""
    inicio, fin = hecho.get("start"), hecho.get("end")
    if not inicio or not fin:
        return False
    try:
        dias = (dt.date.fromisoformat(fin) - dt.date.fromisoformat(inicio)).days
    except (ValueError, TypeError):
        return False
    return 300 <= dias <= 400


def _unidades_del_concepto(bloque: dict, concepto: Concepto) -> list[dict]:
    """Elige la lista de hechos en la unidad correcta.

    Los importes se aceptan UNICAMENTE en USD. Un emisor extranjero que reporta
    en CNY o EUR devolveria numeros que, combinados con una capitalizacion en
    dolares, producen ratios sin ningun sentido y con apariencia normal
    (Alibaba daba un PER de 155x por esta razon). Ante la duda, mejor sin dato.
    """
    unidades = bloque.get("units", {})
    if concepto.unidad in unidades:
        return unidades[concepto.unidad]
    if concepto.unidad == "USD":
        return []  # nunca caer a otra moneda
    for nombre in ("shares", "pure"):
        if nombre in unidades:
            return unidades[nombre]
    return []


def _moneda_reportada(facts: dict) -> str | None:
    """Moneda en la que la empresa presenta su balance, para poder avisar."""
    for etiqueta in ("Assets", "Revenues", "StockholdersEquity"):
        for espacio in _ESPACIOS:
            bloque = facts.get("facts", {}).get(espacio, {}).get(etiqueta)
            if bloque and bloque.get("units"):
                monetarias = [u for u in bloque["units"] if u not in ("shares", "pure")]
                if monetarias:
                    return monetarias[0]
    return None


def _hechos_anuales(facts: dict, etiqueta: str, concepto: Concepto) -> dict[int, dict]:
    """Devuelve {año: hecho} para una etiqueta XBRL puntual.

    Si hay varias presentaciones del mismo periodo (original y reexpresada),
    gana la de fecha de presentacion mas reciente.
    """
    for espacio in _ESPACIOS:
        bloque = facts.get("facts", {}).get(espacio, {}).get(etiqueta)
        if bloque:
            break
    else:
        return {}

    salida: dict[int, dict] = {}
    for hecho in _unidades_del_concepto(bloque, concepto):
        forma = str(hecho.get("form", ""))
        if not forma.startswith(_FORMAS_ANUALES):
            continue
        if concepto.tipo == "duracion" and not _duracion_valida(hecho):
            continue
        if concepto.tipo == "instante" and hecho.get("start"):
            continue

        anio = _anio_fiscal(hecho.get("end"))
        if anio is None or hecho.get("val") is None:
            continue

        previo = salida.get(anio)
        if previo is None or str(hecho.get("filed", "")) > str(previo.get("filed", "")):
            salida[anio] = hecho
    return salida


def serie_por_concepto(facts: dict, concepto: Concepto, anios: list[int]) -> dict[int, dict]:
    """Resuelve un concepto contra sus etiquetas candidatas, AÑO POR AÑO.

    Este es el corazon del extractor y la razon por la que existe este modulo.
    Recorre las etiquetas en orden de preferencia y, para cada año que todavia
    no tiene dato, toma la primera etiqueta que lo cubra. Una empresa que cambio
    de etiqueta a mitad del periodo termina con una serie continua y correcta,
    en lugar de una serie vieja presentada como actual.
    """
    resultado: dict[int, dict] = {}
    faltantes = set(anios)

    for etiqueta in concepto.etiquetas:
        if not faltantes:
            break
        encontrados = _hechos_anuales(facts, etiqueta, concepto)
        for anio in sorted(faltantes):
            hecho = encontrados.get(anio)
            if hecho is None:
                continue
            resultado[anio] = {
                "valor": float(hecho["val"]) * concepto.signo,
                "etiqueta": etiqueta,
                "fin": hecho.get("end"),
                "forma": hecho.get("form"),
                "presentado": hecho.get("filed"),
            }
            faltantes.discard(anio)

    return resultado


# ------------------------------------------------------------------ splits

# Conceptos medidos en acciones: son los unicos que un split reescala.
_CONCEPTOS_ACCIONES = ("acciones_dil", "acciones_bas", "acciones_circulacion")

# Un cambio de escala de esta magnitud entre dos presentaciones del MISMO
# ejercicio no puede ser otra cosa que un split: los numeros de un ejercicio
# cerrado no se corrigen un 40% por una reexpresion contable.
_SALTO_SPLIT = 1.4


def _eventos_split(facts: dict, concepto: Concepto) -> list[tuple[str, float]]:
    """Splits detectados, como (fecha de la primera presentacion en la escala nueva, proporcion).

    NO se infiere del salto entre un año y el siguiente: ahi el split viene
    mezclado con la emision o recompra real del periodo, y separarlos es
    adivinar. Tesla saltaba 3,66x entre 2019 y 2020, que es un split de 3 a 1
    multiplicado por un 22% de emision genuina.

    La proporcion esta en los datos: el mismo ejercicio 2018 aparece con 170,5
    millones de acciones en el informe de 2019 y con 853 millones en el de
    2021. El cociente entre esas dos cifras es exactamente el split, sin nada
    mas adentro, porque el ejercicio es el mismo.
    """
    por_anio: dict[int, dict[str, float]] = {}
    for etiqueta in concepto.etiquetas:
        for espacio in _ESPACIOS:
            bloque = facts.get("facts", {}).get(espacio, {}).get(etiqueta)
            if bloque:
                break
        else:
            continue
        for hecho in _unidades_del_concepto(bloque, concepto):
            if not str(hecho.get("form", "")).startswith(_FORMAS_ANUALES):
                continue
            if concepto.tipo == "duracion" and not _duracion_valida(hecho):
                continue
            if concepto.tipo == "instante" and hecho.get("start"):
                continue
            anio = _anio_fiscal(hecho.get("end"))
            presentado, valor = hecho.get("filed"), hecho.get("val")
            if anio is None or not presentado or not valor:
                continue
            por_anio.setdefault(anio, {})[presentado] = float(valor)

    crudos: dict[str, list[float]] = {}
    for versiones in por_anio.values():
        ordenadas = sorted(versiones.items())
        for (_, previo), (fecha, actual) in zip(ordenadas, ordenadas[1:]):
            if previo <= 0:
                continue
            proporcion = actual / previo
            if proporcion >= _SALTO_SPLIT or proporcion <= 1 / _SALTO_SPLIT:
                crudos.setdefault(fecha, []).append(proporcion)

    # Un mismo split aparece desde varios ejercicios: se consolida con la
    # mediana, que absorbe el redondeo de las cifras reexpresadas.
    return sorted((fecha, _mediana(valores)) for fecha, valores in crudos.items())


def _mediana(valores: list[float]) -> float:
    ordenados = sorted(valores)
    n = len(ordenados)
    return ordenados[n // 2] if n % 2 else (ordenados[n // 2 - 1] + ordenados[n // 2]) / 2


def _factor_split(eventos: list[tuple[str, float]], presentado: str | None) -> float:
    """Cuanto hay que reescalar un hecho presentado en esa fecha, para llevarlo
    a la escala de hoy: el producto de todos los splits POSTERIORES a el."""
    if not presentado:
        return 1.0
    factor = 1.0
    for fecha, proporcion in eventos:
        if fecha > presentado:
            factor *= proporcion
    return factor


# ------------------------------------------------------------------ API publica

def fundamentals(ticker: str, anios: int | None = None) -> dict:
    """Series anuales de todos los conceptos del catalogo, listas para calcular.

    Estructura devuelta:
        {
          "ticker": "ACN",
          "cik": "0001467373",
          "nombre": "Accenture plc",
          "anios": [2011, ..., 2025],
          "series": {"ingresos": {2024: 64896000000.0, ...}, ...},
          "procedencia": {"ingresos": {2024: {"etiqueta": ..., "presentado": ...}}},
          "faltantes": ["gastos_id", ...]
        }
    """
    anios = anios or config.ANIOS_HISTORIA
    facts = companyfacts(ticker)

    # La ficha del emisor da el rubro y, sobre todo, cual fue la ultima
    # presentacion anual: con eso se detecta si la API se quedo atras.
    try:
        ident = identidad(ticker)
    except Exception:
        ident = {"sic": "", "sic_desc": "", "ultimo_anual": None}
    try:
        facts = completar_con_instancia(ticker, facts, ident)
    except Exception:
        pass  # el relleno es un extra, nunca puede frenar el analisis

    # El rango de años se descubre de los datos, no se asume.
    anio_actual = dt.date.today().year
    rango = list(range(anio_actual - anios, anio_actual + 1))

    series: dict[str, dict[int, float]] = {}
    procedencia: dict[str, dict[int, dict]] = {}
    faltantes: list[str] = []

    for concepto in TODOS:
        crudo = serie_por_concepto(facts, concepto, rango)
        if not crudo:
            faltantes.append(concepto.clave)
            continue

        # Los conteos de acciones se llevan todos a la escala actual. Cada año
        # sale de la presentacion que lo cubre, y una empresa solo reexpresa
        # los ejercicios previos en los informes POSTERIORES al split: sin esto
        # Alphabet aparecia diluyendo 78% en 5 años mientras recompraba.
        if concepto.clave in _CONCEPTOS_ACCIONES:
            eventos = _eventos_split(facts, concepto)
            if eventos:
                for anio, dato in crudo.items():
                    dato["valor"] *= _factor_split(eventos, dato.get("presentado"))
                    dato["split_ajustado"] = True

        series[concepto.clave] = {a: d["valor"] for a, d in crudo.items()}
        procedencia[concepto.clave] = {
            a: {k: v for k, v in d.items() if k != "valor"} for a, d in crudo.items()
        }

    # Años efectivamente cubiertos: los que tienen ingresos o ganancia neta.
    cubiertos = sorted(
        set(series.get("ingresos", {})) | set(series.get("ganancia_neta", {}))
    )

    # Si no quedo nada, puede ser que la empresa reporte en otra moneda.
    # Conviene decirlo con todas las letras en lugar de mostrar una ficha vacia.
    if not cubiertos:
        divisa = _moneda_reportada(facts)
        if divisa and divisa != "USD":
            raise ErrorEdgar(
                f"{facts.get('entityName', ticker.upper())} presenta sus estados "
                f"contables en {divisa}, no en USD. Combinarlos con una "
                "capitalizacion en dolares daria ratios incorrectos, asi que se "
                "descarta. La herramienta cubre emisores de EE.UU."
            )

    # Tipo de empresa: define que indicadores tienen sentido economico y cuales
    # hay que dejar vacios en vez de publicar un numero engañoso.
    # Si la ficha del emisor fallo, la deteccion sigue por las etiquetas XBRL.
    perfil = perfiles.detectar(ident.get("sic"), _etiquetas_usadas(facts))

    return {
        "ticker": ticker.upper(),
        "cik": cik_de(ticker),
        "nombre": facts.get("entityName", ticker.upper()),
        "anios": cubiertos,
        "series": series,
        "procedencia": procedencia,
        "faltantes": faltantes,
        "perfil": perfil,
        "sic": ident.get("sic", ""),
        "sic_desc": ident.get("sic_desc", ""),
    }


# ------------------------------------------------------------------ trimestres

_FORMAS_TRIMESTRALES = ("10-Q", "6-K")


def _duracion_trimestral(hecho: dict) -> bool:
    """Un trimestre dura entre ~80 y ~100 dias. Descarta acumulados y ejercicios."""
    inicio, fin = hecho.get("start"), hecho.get("end")
    if not inicio or not fin:
        return False
    try:
        dias = (dt.date.fromisoformat(fin) - dt.date.fromisoformat(inicio)).days
    except (ValueError, TypeError):
        return False
    return 80 <= dias <= 100


def _mes_cierre_fiscal(facts: dict) -> int | None:
    """Mes en que la empresa cierra su ejercicio, sacado de sus informes anuales."""
    meses: dict[int, int] = {}
    for espacio, tags in facts.get("facts", {}).items():
        if espacio == "dei":
            continue
        for bloque in tags.values():
            for hechos in bloque.get("units", {}).values():
                for h in hechos:
                    if not str(h.get("form", "")).startswith(_FORMAS_ANUALES):
                        continue
                    if not _duracion_valida(h):
                        continue
                    try:
                        mes = dt.date.fromisoformat(h["end"]).month
                    except (ValueError, TypeError, KeyError):
                        continue
                    meses[mes] = meses.get(mes, 0) + 1
    return max(meses, key=meses.get) if meses else None


def _etiqueta_trimestre(fin: str, mes_cierre: int) -> tuple[int, int] | None:
    """(año fiscal, numero de trimestre) de un periodo que termina en `fin`.

    Se calcula contra el mes de cierre de la empresa, no contra el calendario:
    el trimestre de Apple que termina en diciembre es su primero, no el cuarto.
    """
    try:
        fecha = dt.date.fromisoformat(fin)
    except (ValueError, TypeError):
        return None
    # Los cierres 52/53 semanas caen unos dias antes o despues del fin de mes.
    mes = fecha.month if fecha.day > 14 else (fecha.month - 1) or 12
    trimestre = ((mes - mes_cierre - 1) % 12) // 3 + 1
    anio = fecha.year + (1 if mes > mes_cierre else 0)
    return (anio, trimestre)


def _tiene_trimestrales(facts: dict) -> bool:
    """True si la empresa presenta informes trimestrales con datos XBRL."""
    for espacio, tags in facts.get("facts", {}).items():
        if espacio == "dei":
            continue
        for bloque in tags.values():
            for hechos in bloque.get("units", {}).values():
                for h in hechos:
                    if str(h.get("form", "")).startswith(_FORMAS_TRIMESTRALES):
                        return True
    return False


def serie_trimestral(facts: dict, concepto: Concepto, mes_cierre: int) -> dict[tuple, dict]:
    """Serie por trimestre de un concepto, resuelta etiqueta por etiqueta.

    Misma logica que la anual: se recorren las candidatas en orden y cada
    periodo se llena con la primera que lo cubra.
    """
    resultado: dict[tuple, dict] = {}
    for etiqueta in concepto.etiquetas:
        for espacio in _ESPACIOS:
            bloque = facts.get("facts", {}).get(espacio, {}).get(etiqueta)
            if bloque:
                break
        else:
            continue

        for hecho in _unidades_del_concepto(bloque, concepto):
            forma = str(hecho.get("form", ""))
            if not forma.startswith(_FORMAS_TRIMESTRALES + _FORMAS_ANUALES):
                continue
            if concepto.tipo == "duracion":
                if not _duracion_trimestral(hecho):
                    continue
            elif hecho.get("start"):
                continue

            clave = _etiqueta_trimestre(hecho.get("end"), mes_cierre)
            if clave is None or hecho.get("val") is None:
                continue

            previo = resultado.get(clave)
            if previo is not None and previo["etiqueta"] != etiqueta:
                continue  # ya lo cubrio una etiqueta de mayor preferencia
            if previo is None or str(hecho.get("filed", "")) > str(previo["presentado"]):
                resultado[clave] = {
                    "valor": float(hecho["val"]) * concepto.signo,
                    "etiqueta": etiqueta,
                    "fin": hecho.get("end"),
                    "presentado": hecho.get("filed"),
                }
    return resultado


def trimestrales(ticker: str, concepto_claves: list[str] | None = None) -> dict:
    """Series trimestrales de los conceptos pedidos.

    Estructura devuelta:
        {"periodos": [(2025, 1), (2025, 2), ...],
         "series": {"ingresos": {(2025, 1): 1234.0, ...}},
         "derivados": {("ingresos", (2025, 4))}}   <- 4T calculados por resta

    EL CUARTO TRIMESTRE NO SE PRESENTA
    ----------------------------------
    Las empresas de EE.UU. presentan tres 10-Q y despues un 10-K con el
    ejercicio entero: el cuarto trimestre no existe como tal en ningun informe.
    Se calcula restandole al ejercicio los tres trimestres previos, y queda
    marcado en `derivados` para poder avisarlo en pantalla.
    """
    facts = companyfacts(ticker)
    try:
        ident = identidad(ticker)
        facts = completar_con_instancia(ticker, facts, ident)
    except Exception:
        pass

    vacio = {"periodos": [], "series": {}, "derivados": set()}

    mes_cierre = _mes_cierre_fiscal(facts)
    if mes_cierre is None:
        return vacio

    # Si la empresa nunca presento un formulario trimestral, no hay trimestres
    # que mostrar. Hace falta chequearlo antes: los saldos de cierre de un
    # informe anual son fechas de fin de ejercicio y se etiquetarian como
    # cuartos trimestres, armando un balance "trimestral" con una sola columna
    # por año. NU es el caso: reporta sus trimestres por 6-K sin XBRL.
    if not _tiene_trimestrales(facts):
        return vacio

    claves = concepto_claves or [c.clave for c in TODOS]
    series: dict[str, dict[tuple, float]] = {}
    derivados: set[tuple] = set()

    for clave in claves:
        concepto = POR_CLAVE.get(clave)
        if concepto is None:
            continue
        crudo = serie_trimestral(facts, concepto, mes_cierre)
        if not crudo:
            continue
        series[clave] = {k: v["valor"] for k, v in crudo.items()}

    # El 4T por diferencia, solo para conceptos de flujo (los de saldo ya vienen).
    anuales = fundamentals(ticker)["series"]
    for clave, por_trimestre in series.items():
        concepto = POR_CLAVE[clave]
        if concepto.tipo != "duracion":
            continue
        anual = anuales.get(clave, {})
        for anio, total in anual.items():
            if (anio, 4) in por_trimestre:
                continue
            previos = [por_trimestre.get((anio, t)) for t in (1, 2, 3)]
            if any(v is None for v in previos):
                continue
            por_trimestre[(anio, 4)] = total - sum(previos)
            derivados.add((clave, (anio, 4)))

    periodos = sorted({p for s in series.values() for p in s})
    return {"periodos": periodos, "series": series, "derivados": derivados}


def diagnostico(ticker: str) -> list[dict]:
    """Tabla de auditoria: que etiqueta se uso para cada concepto y año.

    Sirve para el problema que ya nos mordio una vez: cuando un numero se ve
    raro, esto muestra de que etiqueta XBRL salio y cuando se presento, sin
    tener que abrir el 10-K.
    """
    datos = fundamentals(ticker)
    filas = []
    for clave, por_anio in datos["procedencia"].items():
        etiquetas = {d["etiqueta"] for d in por_anio.values()}
        filas.append({
            "concepto": clave,
            "descripcion": POR_CLAVE[clave].descripcion,
            "anios_cubiertos": len(por_anio),
            "etiquetas_usadas": ", ".join(sorted(etiquetas)),
            "cambio_de_etiqueta": len(etiquetas) > 1,
        })
    for clave in datos["faltantes"]:
        filas.append({
            "concepto": clave,
            "descripcion": POR_CLAVE[clave].descripcion,
            "anios_cubiertos": 0,
            "etiquetas_usadas": "(ninguna encontrada)",
            "cambio_de_etiqueta": False,
        })
    return sorted(filas, key=lambda f: (-f["anios_cubiertos"], f["concepto"]))

