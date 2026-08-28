"""
Radar: el barrido que sale a buscar candidatas al mercado entero, a pedido.

POR QUE NO SE USA EDGAR ACA
---------------------------
El resto de la app tiene una regla firme: los fundamentals salen de EDGAR y de
ningun otro lado. Aca se rompe a proposito, y conviene entender por que no es
una contradiccion.

EDGAR es el archivo de la SEC, no un buscador. Para preguntarle "traeme las
empresas con PER menor a 14" habria que bajar el companyfacts de cada una de
las 5000 que cotizan —entre 5 y 30 MB por empresa— y calcular el ratio uno por
uno. Son varias horas de descarga por corrida para contestar una pregunta que
el screener de Yahoo contesta en dos segundos.

Entonces el barrido usa Yahoo COMO EMBUDO, no como fuente de verdad: su unico
trabajo es bajar de 5000 a 40 nombres. Los numeros que trae quedan marcados
como lo que son —una foto de Yahoo, con su criterio y sus errores— y sirven
para decidir a cual le dedicas una tarde. En el momento en que una candidata te
interesa de verdad y la abris en el Detalle, la app la vuelve a calcular con
EDGAR desde cero, y esos son los numeros que valen.

La linea es esa: Yahoo elige a quien mirar, EDGAR dice cuanto vale.
"""

from __future__ import annotations

import datetime as dt
from concurrent.futures import ThreadPoolExecutor, as_completed
from dataclasses import dataclass

import yfinance as yf

from .proveedores import mercado

# ------------------------------------------------------------------ universo del barrido
#
# Fijo, no configurable. `region us` deja afuera las bolsas del resto del
# mundo, que no reportan a la SEC y por lo tanto la app no puede analizar
# despues. Los dos codigos de mercado son Nasdaq (NMS) y NYSE (NYQ): sin eso
# entra el mercado OTC, donde los ratios de Yahoo salen de estados contables
# que muchas veces nadie audito.

_REGION = "us"
_MERCADOS = ["NMS", "NYQ"]

# Cuantos dias sobrevive una candidata que dejo de pasar el filtro sin que vos
# la hayas resuelto. Si el precio se recupero y ya no esta barata, en algun
# momento tiene que dejar de ocupar lugar en la pantalla.
DIAS_RETENCION = 30

# Cuantas fichas seguidas pueden fallar antes de dar por perdido el intento de
# completar sectores. Ver `completar_perfil`.
FALLOS_PARA_CORTAR = 5

# Tope de candidatas por corrida. No es un filtro de Yahoo: es cuantas se traen
# de las que pasaron, empezando por las mas baratas por PER.
MAX_CANDIDATAS = 40


@dataclass(frozen=True)
class Filtro:
    """Un filtro del barrido: como se ve en la app y como viaja a Yahoo."""
    clave: str
    rotulo: str
    campo: str          # nombre del campo en el screener de Yahoo
    op: str             # "gt" (mayor que) o "lt" (menor que)
    unidad: str         # para formatear el control en la interfaz
    defecto: float | None
    ayuda: str


# El preset arranca en deep value castigado: barata, ganando plata, con
# rentabilidad decente, sin deuda asfixiante, y abajo en el año. Los que
# arrancan en None estan apagados y se prenden desde la app.
FILTROS: list[Filtro] = [
    Filtro("cap_min", "Capitalizacion minima", "intradaymarketcap", "gt", "usd",
           300_000_000,
           "Debajo de unos 300 millones el spread de compraventa y la falta de "
           "cobertura hacen que el precio no sea una referencia confiable."),
    Filtro("volumen_min", "Volumen diario minimo", "avgdailyvol3m", "gt", "acciones",
           200_000,
           "Promedio de 3 meses. Filtra lo que no se puede comprar ni vender sin "
           "mover el precio vos mismo."),
    Filtro("per_min", "PER minimo", "peratio.lasttwelvemonths", "gt", "x", 1.0,
           "Un PER de 0,3 casi nunca es una ganga: suele ser una ganancia "
           "extraordinaria de un solo año que no se repite."),
    Filtro("per_max", "PER maximo", "peratio.lasttwelvemonths", "lt", "x", 14.0,
           "El corte de barata. Es el filtro que mas mueve la cantidad de "
           "candidatas por dia."),
    Filtro("eps_min", "EPS minimo", "netepsdiluted.lasttwelvemonths", "gt", "usd_ps",
           0.0,
           "Diluido, ultimos doce meses. En cero deja afuera a las que pierden "
           "plata, donde el PER no significa nada."),
    Filtro("roe_min", "ROE minimo", "returnonequity.lasttwelvemonths", "gt", "pct", 8.0,
           "Separa la barata de la que rinde poco por naturaleza. Ojo que el ROE "
           "se infla con deuda: por eso va junto al filtro de deuda."),
    Filtro("deuda_ebitda_max", "Deuda / EBITDA maxima",
           "totaldebtebitda.lasttwelvemonths", "lt", "x", 3.5,
           "Deuda total sobre EBITDA. Arriba de 3,5x la que decide el futuro de "
           "la empresa es la tasa de refinanciacion, no el negocio."),
    Filtro("var_52s_max", "Variacion 52 semanas maxima", "fiftytwowkpercentchange",
           "lt", "pct", 0.0,
           "El disparador contrarian. En 0 pide que este mas abajo que hace un "
           "año; en -25 pide una caida de verdad."),
    # --- apagados por defecto: son para apretar el filtro cuando entran demasiadas
    Filtro("pvl_max", "Precio / Valor libro maximo", "pricebookratio.quarterly",
           "lt", "x", None,
           "Menos de 1 significa que el mercado paga menos que el patrimonio "
           "contable. Cuidado en tecnologicas, donde el activo real no esta en "
           "el balance."),
    Filtro("roic_min", "ROIC minimo", "returnontotalcapital.lasttwelvemonths",
           "gt", "pct", None,
           "Rentabilidad sobre el capital total. A diferencia del ROE, no se "
           "puede maquillar con deuda."),
    Filtro("altman_min", "Altman Z minimo",
           "altmanzscoreusingtheaveragestockinformationforaperiod.lasttwelvemonths",
           "gt", "num", None,
           "Debajo de 1,8 el modelo la clasifica en riesgo de default; arriba de "
           "3 la considera segura."),
    Filtro("liquidez_min", "Liquidez corriente minima",
           "currentratio.lasttwelvemonths", "gt", "x", None,
           "Activo corriente sobre pasivo corriente. Debajo de 1 depende de "
           "refinanciar para pagar lo que vence este año."),
    Filtro("ev_ebit_max", "EV / EBIT maximo", "lastclosetevebit.lasttwelvemonths",
           "lt", "x", None,
           "El PER de la empresa entera, deuda incluida. No se deja enganar por "
           "una caja grande ni por una deuda escondida."),
    Filtro("div_min", "Dividendo minimo", "dividendyield", "gt", "pct", None,
           "Rendimiento del dividendo. Un dividendo alto en una accion castigada "
           "muchas veces es un recorte que todavia no se anuncio."),
]

FILTROS_POR_CLAVE = {f.clave: f for f in FILTROS}


def filtros_por_defecto() -> dict:
    valores = {f.clave: f.defecto for f in FILTROS}
    valores["max_candidatas"] = MAX_CANDIDATAS
    return valores


def normalizar(filtros: dict | None) -> dict:
    """Completa con los valores por defecto lo que falte y descarta lo que sobre.

    Los filtros vienen del gist, que lo escribio una version anterior de la app.
    Si mañana se agrega un filtro nuevo, el archivo guardado no lo tiene: sin
    esto, el barrido saldria sin ese corte y en silencio.
    """
    base = filtros_por_defecto()
    for clave, valor in (filtros or {}).items():
        if clave in base:
            base[clave] = valor
    return base


# ------------------------------------------------------------------ el barrido


def _consulta(filtros: dict):
    """Arma la consulta del screener a partir del diccionario de filtros."""
    EQ = yf.EquityQuery
    condiciones = [
        EQ("eq", ["region", _REGION]),
        EQ("is-in", ["exchange"] + _MERCADOS),
    ]
    for f in FILTROS:
        valor = filtros.get(f.clave)
        if valor is None or valor == "":
            continue
        condiciones.append(EQ(f.op, [f.campo, float(valor)]))
    return EQ("and", condiciones)


def _dist_max52(precio, maximo) -> float | None:
    """Cuanto esta abajo del maximo del año, en porciento.

    Se calcula, no se lee. Yahoo publica `fiftyTwoWeekHighChangePercent` pero
    lo devuelve en FRACCION (-0,647), en el mismo objeto donde
    `fiftyTwoWeekChangePercent` viene en PORCIENTO (-63,0). Tomar los dos como
    vienen daba fichas que decian que una accion que cayo 63% en el año estaba
    a 0,6% de su maximo: absurdo, pero absurdo silencioso, del tipo que se lee
    como un dato bueno. El cociente contra el maximo no tiene esa ambiguedad.
    """
    if not precio or not maximo:
        return None
    return (precio / maximo - 1) * 100


def _fila(q: dict) -> dict:
    """Una candidata, con los numeros que el screener devuelve en la respuesta.

    OJO: no son todos los que se filtraron. Yahoo acepta filtrar por ROE o por
    deuda/EBITDA, pero no los devuelve en la respuesta del screener: de esos dos
    sabemos que pasaron el corte y nada mas. Los numeros completos llegan cuando
    abris la empresa en el Detalle y se calculan con EDGAR.
    """
    precio = q.get("regularMarketPrice")
    vl = q.get("bookValue")
    return {
        "ticker": q.get("symbol"),
        "nombre": (q.get("longName") or q.get("shortName") or "")[:60],
        "precio": precio,
        "market_cap": q.get("marketCap"),
        "per": q.get("trailingPE"),
        "eps": q.get("epsTrailingTwelveMonths"),
        "pvl": (precio / vl) if precio and vl and vl > 0 else None,
        "var_52s": q.get("fiftyTwoWeekChangePercent"),
        "dist_max52": _dist_max52(precio, q.get("fiftyTwoWeekHigh")),
        "volumen": q.get("averageDailyVolume3Month"),
        "mercado": q.get("fullExchangeName"),
        # El screener no los devuelve; los completa `completar_perfil`.
        "sector": None,
        "industria": None,
    }


def barrer(filtros: dict | None = None) -> tuple[list[dict], int]:
    """Corre el screener y devuelve (candidatas, cuantas pasaron el filtro).

    El total casi siempre es mayor que la lista: se traen las `max_candidatas`
    mas baratas por PER, no todas.
    """
    filtros = normalizar(filtros)
    tope = int(filtros.get("max_candidatas") or MAX_CANDIDATAS)
    consulta = _consulta(filtros)

    filas, total, offset = [], 0, 0
    while len(filas) < tope:
        lote = yf.screen(
            consulta, offset=offset, size=min(100, tope - len(filas)),
            sortField="peratio.lasttwelvemonths", sortAsc=True)
        total = lote.get("total") or 0
        cotizaciones = lote.get("quotes") or []
        if not cotizaciones:
            break
        filas.extend(_fila(q) for q in cotizaciones if q.get("symbol"))
        offset += len(cotizaciones)
        if offset >= total:
            break

    # Los duplicados existen: la misma empresa aparece dos veces si tiene dos
    # clases de accion cotizando.
    vistos, limpias = set(), []
    for f in filas:
        if f["ticker"] and f["ticker"] not in vistos:
            vistos.add(f["ticker"])
            limpias.append(f)
    return limpias[:tope], total


# ------------------------------------------------------------------ sector e industria


def completar_perfil(candidatas: list[dict], barra=None) -> int:
    """Rellena sector e industria de las que no los tengan. Devuelve cuantas.

    El screener de Yahoo NO los devuelve: filtra por sector pero no lo publica
    en la respuesta. Hay que pedir la ficha de cada empresa aparte, que es un
    pedido por ticker y tarda casi dos segundos.

    Por eso se hace una sola vez por candidata y queda guardado con ella. En la
    primera corrida son cuarenta pedidos; despues, los dos o tres que entraron
    ese dia.

    Que una ficha falle no es motivo para nada: la candidata se queda sin
    sector y el resto de sus numeros —que son los que la trajeron al radar—
    siguen estando.
    """
    faltan = [c for c in candidatas if not c.get("sector")]
    if not faltan:
        return 0

    def _perfil(candidata):
        try:
            foto = mercado.instantanea(candidata["ticker"])
            return foto.get("sector"), foto.get("industria")
        except Exception:
            return None, None

    completadas, fallos = 0, 0
    # Tres hilos: suficiente para que no tarde una eternidad, poco para que
    # Yahoo no lo tome por una rafaga y empiece a rechazar.
    with ThreadPoolExecutor(max_workers=3) as pool:
        futuros = {pool.submit(_perfil, c): c for c in faltan}
        for i, fut in enumerate(as_completed(futuros), 1):
            candidata = futuros[fut]
            sector, industria = fut.result()
            if sector:
                candidata["sector"] = sector
                candidata["industria"] = industria
                completadas += 1
            else:
                fallos += 1
            if barra is not None:
                barra.progress(i / len(faltan),
                               text=f"Sector de {candidata['ticker']} ({i}/{len(faltan)})")
            # CORTE: si nada entra al principio, Yahoo esta rechazando esta IP
            # —lo normal cuando la app corre en la nube— y seguir es esperar
            # ochenta veces por la misma negativa. Las candidatas quedan sin
            # sector, que se muestra como un guion, y la corrida en GitHub (que
            # sale de otra IP) los completa.
            if fallos >= FALLOS_PARA_CORTAR and completadas == 0:
                for pendiente in futuros:
                    pendiente.cancel()
                break
    return completadas


# ------------------------------------------------------------------ estado guardado


def fusionar(previo: dict, encontradas: list[dict], universo: list[str],
             filtros: dict, total: int = 0) -> dict:
    """Mezcla el barrido de hoy con lo que ya habia.

    Tres cosas tienen que sobrevivir a cada barrido:

    1. La fecha en que una candidata aparecio por primera vez. Sin eso no se
       distingue la que entro hoy de la que llevas dos semanas sin mirar.
    2. El diagnostico ya escrito. Volver a pedirlo en cada barrido seria pagarle
       a Claude de nuevo por la misma respuesta.
    3. Las que descartaste. Una accion barata sigue estando barata mañana: sin
       memoria, el barrido te ofreceria lo que ya rechazaste, cada vez,
       para siempre.
    """
    hoy = dt.date.today().isoformat()
    descartadas = dict(previo.get("descartadas") or {})
    en_universo = {t.strip().upper() for t in universo}
    previas = {c["ticker"]: c for c in (previo.get("candidatas") or [])
               if c.get("ticker")}

    salida, vistas = [], set()
    for enc in encontradas:
        t = enc["ticker"]
        if t in descartadas or t in en_universo:
            continue
        anterior = previas.get(t) or {}
        salida.append({
            **enc,
            # El sector se averigua una vez y se hereda: volver a pedirlo cada
            # dia serian cuarenta pedidos a Yahoo para un dato que no cambia.
            "sector": anterior.get("sector") or enc.get("sector"),
            "industria": anterior.get("industria") or enc.get("industria"),
            "fecha_alta": anterior.get("fecha_alta", hoy),
            "diagnostico": anterior.get("diagnostico"),
            "vigente": True,
            "visto": hoy,
        })
        vistas.add(t)

    # Las que hoy no pasaron el filtro pero seguis sin resolver: se quedan un
    # tiempo marcadas, porque el motivo por el que salieron —el precio subio—
    # es informacion, no un error.
    for t, ant in previas.items():
        if t in vistas or t in descartadas or t in en_universo:
            continue
        if _dias_desde(ant.get("visto")) > DIAS_RETENCION:
            continue
        salida.append({**ant, "vigente": False})

    return {
        "corrida": dt.datetime.now(dt.timezone.utc).isoformat(timespec="seconds"),
        "filtros": filtros,
        "total_mercado": total,
        "candidatas": salida,
        "descartadas": descartadas,
    }


def _dias_desde(fecha: str | None) -> int:
    if not fecha:
        return 10_000
    try:
        return (dt.date.today() - dt.date.fromisoformat(fecha)).days
    except ValueError:
        return 10_000


def dias_en_radar(candidata: dict) -> int:
    return _dias_desde(candidata.get("fecha_alta"))


def descartar(estado: dict, ticker: str, motivo: str = "") -> dict:
    """Saca una candidata y la anota para que el barrido no la vuelva a traer."""
    ticker = ticker.strip().upper()
    estado = dict(estado)
    descartadas = dict(estado.get("descartadas") or {})
    descartadas[ticker] = {"fecha": dt.date.today().isoformat(), "motivo": motivo}
    estado["descartadas"] = descartadas
    estado["candidatas"] = [c for c in (estado.get("candidatas") or [])
                            if c.get("ticker") != ticker]
    return estado


def rehabilitar(estado: dict, ticker: str) -> dict:
    """Deshace un descarte: vuelve a ser elegible en el proximo barrido."""
    ticker = ticker.strip().upper()
    estado = dict(estado)
    descartadas = dict(estado.get("descartadas") or {})
    descartadas.pop(ticker, None)
    estado["descartadas"] = descartadas
    return estado


def quitar(estado: dict, ticker: str) -> dict:
    """Saca una candidata sin marcarla como descartada (se la llevo el universo)."""
    ticker = ticker.strip().upper()
    estado = dict(estado)
    estado["candidatas"] = [c for c in (estado.get("candidatas") or [])
                            if c.get("ticker") != ticker]
    return estado


def sin_diagnostico(estado: dict) -> list[dict]:
    """Las vigentes a las que todavia nadie les escribio el por que.

    Una que fallo vuelve a estar pendiente: lo que la saca de la cola es tener
    texto, no haberlo intentado. Un timeout de la corrida anterior no puede
    dejar a la candidata sin explicacion para siempre.
    """
    return [c for c in (estado.get("candidatas") or [])
            if c.get("vigente") and not (c.get("diagnostico") or {}).get("texto")]


def nunca_diagnosticado(estado: dict) -> bool:
    """Si el diagnostico no corrio NUNCA sobre este radar.

    No es lo mismo que una candidata sin diagnostico. Una celda vacia en la
    columna Causa es normal —esa todavia no le toco—; la columna entera vacia
    quiere decir que el paso que la llena no existe todavia, y eso no se
    adivina mirando una tabla llena de guiones. Un intento fallido cuenta como
    corrida: significa que el mecanismo esta enchufado y lo que fallo fue esa
    llamada.
    """
    for c in estado.get("candidatas") or []:
        diag = c.get("diagnostico") or {}
        if diag.get("texto") or diag.get("error"):
            return False
    return True
