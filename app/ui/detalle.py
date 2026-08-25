"""
Hoja 2 — Detalle.

Analisis profundo de una empresa: estados contables completos, evolucion
historica, y los bloques que responden la pregunta de fondo: esta empresa
merece que le pongas plata?

El orden de la pagina es deliberado: primero que paso (caida y contexto),
despues que tan buena es (calidad y caja), despues si aguanta (solvencia), y
recien al final cuanto vale (valuacion). Valuar antes de entender es la forma
mas rapida de comprar una value trap.
"""

from __future__ import annotations

import html

import pandas as pd
import streamlit as st

from .. import alertas, almacen, cache, estilo, glosario, perfiles
from ..conceptos import GRUPOS, POR_CLAVE
from ..metricas import base
from ..proveedores import edgar, mercado
from . import comun, exportar, graficos, valuacion_inversa

# Conceptos que se muestran en cada estado, en orden de lectura contable.
ESTADO_RESULTADOS = [
    "ingresos", "costo_ventas", "ganancia_bruta", "gastos_sga", "gastos_id",
    "ebit", "intereses", "antes_impuesto", "impuesto", "ganancia_neta",
    "ebitda", "eps_diluido", "acciones_dil",
]
ESTADO_BALANCE = [
    "efectivo", "inversiones_cp", "por_cobrar", "inventario", "activo_corriente",
    "ppe_neto", "goodwill", "intangibles", "activo_total",
    "por_pagar", "pasivo_corriente", "deuda_cp", "deuda_lp", "leases_total",
    "pasivo_total", "resultados_acumulados", "patrimonio", "patrimonio_tangible",
    "deuda_total", "caja_total", "deuda_neta", "capital_trabajo",
]
ESTADO_FLUJO = [
    "flujo_operativo", "capex", "fcf", "sbc", "fcf_post_sbc",
    "adquisiciones", "dividendos", "recompras", "emision_acciones", "dya",
]

# Etiquetas legibles de las series derivadas (las de EDGAR salen de POR_CLAVE).
NOMBRES_DERIVADOS = {
    "ebitda": "EBITDA",
    "fcf": "Caja libre (FCF)",
    "fcf_post_sbc": "FCF neto de SBC",
    "deuda_total": "Deuda total (con leases)",
    "caja_total": "Caja e inversiones",
    "deuda_neta": "Deuda neta",
    "capital_trabajo": "Capital de trabajo",
    "patrimonio_tangible": "Patrimonio tangible",
    "leases_total": "Leases operativos",
    "capital_invertido": "Capital invertido",
    "nopat": "NOPAT",
}


def _nombre(clave: str) -> str:
    """Rotulo de la fila. En los estados va en ingles, como en la presentacion.

    Lo que la SEC publica esta en ingles. Mostrar los estados traducidos obliga
    a hacer la traduccion inversa cada vez que se abre el 10-K original, y ahi
    es donde se cuela el error. La traduccion y el significado viajan en el
    tooltip de cada fila (`glosario.py`).
    """
    en_ingles = glosario.ingles(clave)
    if en_ingles:
        return en_ingles
    if clave in NOMBRES_DERIVADOS:
        return NOMBRES_DERIVADOS[clave]
    c = POR_CLAVE.get(clave)
    return c.descripcion if c else clave


def _tabla_estado(emp, claves: list[str]) -> pd.DataFrame | None:
    """Arma un estado contable con los años como columnas, en millones."""
    filas, indice = [], []
    anios = emp.anios[-12:]

    usados = []
    for clave in claves:
        serie = emp.serie(clave)
        if not serie:
            continue
        es_unitario = clave in ("eps_diluido", "eps_basico")
        escala = 1.0 if es_unitario else 1e6
        filas.append([
            (serie[a] / escala) if a in serie else None
            for a in anios
        ])
        indice.append(_nombre(clave))
        usados.append(clave)

    if not filas:
        return None
    df = pd.DataFrame(filas, index=indice, columns=[str(a) for a in anios])
    # La clave de cada fila viaja con la tabla: es lo que despues permite
    # colgarle el tooltip del glosario al rotulo, que ya esta en ingles.
    df.attrs["claves"] = usados
    return df


def _formato_celda(valor):
    """Millones sin decimales; la ganancia por accion, que es chica, con dos."""
    if valor is None or valor != valor:
        return "—"
    return f"{valor:,.2f}" if abs(valor) < 100 else f"{valor:,.0f}"


# Los estados se dibujan a mano y no con `st.dataframe` por una sola razon:
# hace falta un tooltip POR FILA, y `column_config` solo admite ayuda por
# columna. Transponer la tabla para ganar los tooltips daria vuelta un estado
# contable, que se lee con los conceptos en las filas y los ejercicios en las
# columnas. Asi que el rotulo lleva un `title` nativo y listo.
#
# Los colores salen de `currentColor` y de grises translucidos: la hoja se ve
# igual de bien en tema claro que en oscuro sin preguntar cual esta activo.
_CSS_ESTADOS = """
<style>
.estado-scroll { overflow-x: auto; margin-bottom: .5rem; }
table.estado {
  border-collapse: collapse; width: 100%;
  font-size: .86rem; font-variant-numeric: tabular-nums;
}
table.estado th, table.estado td {
  padding: .34rem .65rem; white-space: nowrap;
  border-bottom: 1px solid rgba(128,128,128,.22);
}
table.estado thead th {
  text-align: right; font-weight: 600;
  border-bottom: 2px solid rgba(128,128,128,.45);
}
table.estado thead th:first-child { text-align: left; }
table.estado td { text-align: right; }
table.estado th.concepto { text-align: left; font-weight: 400; }
table.estado th.concepto span {
  border-bottom: 1px dotted rgba(128,128,128,.7); cursor: help;
}
table.estado td.neg { color: #d64545; font-weight: 600; }
table.estado tbody tr:hover { background: rgba(128,128,128,.09); }
</style>
"""


def _html_estado(df: pd.DataFrame) -> str:
    """El estado como tabla HTML, con la traduccion colgada de cada rotulo."""
    claves = df.attrs.get("claves", [])

    cabecera = "".join(f"<th>{html.escape(str(c))}</th>" for c in df.columns)
    filas = []
    for posicion, (rotulo, valores) in enumerate(zip(df.index, df.values)):
        clave = claves[posicion] if posicion < len(claves) else ""
        ayuda = glosario.tooltip(clave)
        etiqueta = html.escape(str(rotulo))
        concepto = (
            f'<span title="{html.escape(ayuda, quote=True)}">{etiqueta}</span>'
            if ayuda else etiqueta
        )

        celdas = []
        for valor in valores:
            negativo = valor is not None and valor == valor and valor < 0
            celdas.append(
                f'<td class="neg">{_formato_celda(valor)}</td>' if negativo
                else f"<td>{_formato_celda(valor)}</td>")
        filas.append(
            f'<tr><th class="concepto">{concepto}</th>{"".join(celdas)}</tr>')

    return (
        '<div class="estado-scroll"><table class="estado">'
        f"<thead><tr><th></th>{cabecera}</tr></thead>"
        f'<tbody>{"".join(filas)}</tbody></table></div>'
    )


# Los seis numeros del encabezado y los seis controles de la lectura rapida
# cambian segun el tipo de empresa. En un banco, la version general dejaba
# cuatro de seis casilleros vacios: no porque falten datos, sino porque esas
# preguntas no se le hacen a un banco. Ver perfiles.py.

RESUMEN = {
    perfiles.GENERAL: [
        ("dist_max52", "Desde max 52s"), ("drawdown_max", "Desde max historico"),
        ("per", "PER"), ("fcf_yield", "FCF Yield"),
        ("roic_prom_5a", "ROIC 5a"), ("piotroski", "Piotroski"),
    ],
    perfiles.BANCO: [
        ("dist_max52", "Desde max 52s"), ("drawdown_max", "Desde max historico"),
        ("per", "PER"), ("p_vl_tangible", "Precio / VL tangible"),
        ("roe", "ROE"), ("ratio_eficiencia", "Ratio de eficiencia"),
    ],
    perfiles.SEGUROS: [
        ("dist_max52", "Desde max 52s"), ("drawdown_max", "Desde max historico"),
        ("per", "PER"), ("p_vl_tangible", "Precio / VL tangible"),
        ("roe", "ROE"), ("ratio_combinado", "Ratio combinado"),
    ],
    perfiles.REIT: [
        ("dist_max52", "Desde max 52s"), ("drawdown_max", "Desde max historico"),
        ("p_ffo", "Precio / FFO"), ("ffo_yield", "FFO Yield"),
        ("div_yield", "Dividend Yield"), ("deuda_sobre_inmuebles", "Deuda / Inmuebles"),
    ],
}

CONTROLES = {
    perfiles.GENERAL: [
        ("Solvencia", "deuda_neta_ebitda", "Puede sobrevivir el tiempo que tarde la tesis?"),
        ("Calidad del negocio", "roic_prom_5a", "Gana mas de lo que le cuesta el capital?"),
        ("Calidad de las ganancias", "fcf_conversion_prom5", "Las ganancias vienen con caja?"),
        ("Trayectoria fundamental", "piotroski", "Esta mejorando o deteriorandose?"),
        ("Dilucion", "var_acciones_5a", "Tu porcion de la empresa crece o se achica?"),
        ("Contabilidad", "beneish_m", "Hay señales de maquillaje contable?"),
    ],
    perfiles.BANCO: [
        ("Rentabilidad", "roe", "Cuanto gana sobre el capital de los accionistas?"),
        ("Gestion", "ratio_eficiencia", "Cuanto le cuesta generar un dolar de ingreso?"),
        ("Calidad de la cartera", "coste_riesgo", "Cuanto le cuesta prestar mal, cada año?"),
        ("Fondeo", "prestamos_depositos", "Presta con depositos o con fondeo mayorista?"),
        ("Solvencia", "apalancamiento", "Cuanta perdida aguanta antes de comerse el capital?"),
        ("Trayectoria", "anios_con_perdida", "Cuantas veces perdio plata en su historia?"),
    ],
    perfiles.SEGUROS: [
        ("Suscripcion", "ratio_combinado", "Gana plata asegurando, o solo invirtiendo?"),
        ("Siniestralidad", "ratio_siniestralidad", "Elige y tarifa bien los riesgos?"),
        ("Gastos", "ratio_gastos", "Cuanto cuesta vender y administrar las polizas?"),
        ("Float", "float_sobre_cap", "Cuanta plata de terceros invierte por su cuenta?"),
        ("Rentabilidad", "roe", "Cuanto gana sobre el capital de los accionistas?"),
        ("Crecimiento", "cagr_primas_5a", "Crecen las primas? Ojo si es bajando precios."),
    ],
    perfiles.REIT: [
        ("Valuacion", "p_ffo", "Caro o barato contra la caja que genera de verdad?"),
        ("Apalancamiento", "deuda_sobre_inmuebles", "Cuanto de los inmuebles esta financiado?"),
        ("Cobertura", "cobertura_intereses", "Le alcanza el resultado para pagar intereses?"),
        ("Sostenibilidad", "payout_ffo", "El dividendo sale del FFO o de deuda nueva?"),
        ("Crecimiento", "cagr_ffo_5a", "El FFO por accion crece?"),
        ("Dilucion", "var_acciones_5a", "Un REIT que crece emitiendo acciones te diluye."),
    ],
}


def _insignia(texto: str, color: str, tono: str = "#ffffff") -> str:
    return (f"<span style='background:{color};color:{tono};border-radius:6px;"
            f"padding:2px 10px;font-size:0.78em;font-weight:700;"
            f"letter-spacing:.04em;text-transform:uppercase'>{texto}</span>")


def _bloque_encabezado(emp, met: dict, clas: dict):
    izq, der = st.columns([3, 2])
    with izq:
        st.title(f"{emp.ticker} — {emp.nombre}")
        # Lo que no hay no se anuncia: una ficha sembrada de "s/d" se lee como
        # si la empresa fuera el problema, cuando el que falto fue el proveedor.
        ficha = [p for p in (emp.sector, emp.industria) if p]
        ficha.append(f"CIK {emp.cik}")
        ficha.append(f"{len(emp.anios)} ejercicios ({emp.anios[0]}-{emp.anios[-1]})")
        st.caption(" · ".join(ficha))

        # La clasificacion decide con que vara se lee todo lo que sigue.
        etiquetas = [_insignia(clas["nombre"], clas["color"])]
        if clas["ciclica"]:
            etiquetas.append(_insignia("Ciclica", "#6b7280"))
        if emp.perfil != perfiles.GENERAL:
            etiquetas.append(_insignia(perfiles.NOMBRES[emp.perfil], "#374151"))
        st.markdown(
            " ".join(etiquetas)
            + f"<div style='margin-top:8px;color:#6b7280;font-size:0.9em'>"
              f"{' · '.join(clas['razones'])}</div>",
            unsafe_allow_html=True,
        )
        st.markdown(
            f"<div style='margin-top:10px;padding:10px 14px;border-left:3px solid "
            f"{clas['color']};background:rgba(127,127,127,0.07);font-size:0.95em'>"
            f"<b>La pregunta de esta empresa:</b> {clas['pregunta']}</div>",
            unsafe_allow_html=True,
        )

        for aviso in clas["avisos"]:
            st.warning(aviso, icon=":material/warning:")

        if emp.perfil != perfiles.GENERAL:
            st.info(
                f"**{perfiles.NOMBRES[emp.perfil]}** ({emp.sic_desc or 'SIC ' + emp.sic}). "
                + perfiles.EXPLICACION[emp.perfil]
                + f"\n\nQuedan sin calcular {len(perfiles.suprimidas(emp.perfil))} "
                  "indicadores del catalogo: no faltan datos, no aplican a este "
                  "tipo de empresa.",
                icon=":material/account_balance:",
            )
    with der:
        precio = emp.mercado.get("precio")
        var = emp.mercado.get("var_pct")
        if precio:
            st.metric("Cotizacion", f"${precio:,.2f}",
                      f"{var:+.2f}%" if var is not None else None)

    cols = st.columns(6)
    for col, (clave, etiqueta) in zip(cols, RESUMEN.get(emp.perfil, RESUMEN[perfiles.GENERAL])):
        col.metric(etiqueta, base.formatear(clave, met.get(clave)),
                   help=comun.texto_ayuda(clave))


def _bloque_veredicto(emp, met: dict):
    """Lectura rapida de los puntos eliminatorios, en la vara de su perfil."""
    st.subheader("Lectura rapida")

    controles = CONTROLES.get(emp.perfil, CONTROLES[perfiles.GENERAL])

    simbolos = {"bueno": "🟢", "medio": "🟡", "malo": "🔴", "sin_dato": "⚪"}
    cols = st.columns(3)
    for i, (titulo, clave, pregunta) in enumerate(controles):
        valor = met.get(clave)
        estado = base.evaluar(clave, valor)
        with cols[i % 3]:
            st.markdown(
                f"**{simbolos[estado]} {titulo}**  \n"
                f"{base.REGISTRO[clave].nombre}: `{base.formatear(clave, valor)}`  \n"
                f"<span style='color:#8a8f98;font-size:0.85em'>{pregunta}</span>",
                unsafe_allow_html=True,
            )

    # En una financiera la cobertura baja ya esta explicada por el aviso de
    # perfil del encabezado, asi que aca solo se avisa si ademas es anomala.
    faltantes = met.get("cobertura_datos")
    umbral = 70 if emp.perfil == perfiles.GENERAL else 45
    if faltantes is not None and faltantes < umbral:
        st.warning(
            f"Solo se pudo extraer el {faltantes:.0f}% de los conceptos contables de "
            "EDGAR para esta empresa: etiqueta su contabilidad de una forma que el "
            "catalogo no reconoce. Revisa la auditoria de etiquetas XBRL antes de "
            "confiar en cualquier ratio de esta ficha."
        )


def _bloque_cuadro(emp, met: dict, clas: dict):
    """El cuadro de ratios que corresponde al estilo de la empresa.

    Una value se juzga por lo que ya genera y por si el precio la protege; una
    growth, por la calidad y la durabilidad de lo que esta creciendo. Mostrar
    los mismos cuatro bloques a las dos es lo que hace que el ojo busque en el
    lugar equivocado.
    """
    st.subheader(f"Cuadro de ratios — {clas['nombre']}")

    bloques = [(titulo, [c for c in claves
                         if c in base.REGISTRO and perfiles.aplica(c, emp.perfil)])
               for titulo, claves in estilo.cuadro(clas["estilo"])]
    bloques = [(t, cs) for t, cs in bloques if cs]

    simbolos = {"bueno": "🟢", "medio": "🟡", "malo": "🔴", "sin_dato": "⚪"}
    columnas = st.columns(min(len(bloques), 4)) if bloques else []

    for i, (titulo, claves) in enumerate(bloques):
        with columnas[i % len(columnas)]:
            st.markdown(f"**{titulo}**")
            lineas = []
            for clave in claves:
                m = base.REGISTRO[clave]
                valor = met.get(clave)
                estado = base.evaluar(clave, valor)
                lineas.append(
                    f"{simbolos[estado]} {m.nombre}  \n"
                    f"<span style='font-size:1.15em;font-weight:600'>"
                    f"{base.formatear(clave, valor)}</span>"
                )
            st.markdown(
                "<div style='line-height:1.5;font-size:0.88em'>"
                + "<div style='margin-bottom:9px'>"
                + "</div><div style='margin-bottom:9px'>".join(lineas)
                + "</div></div>",
                unsafe_allow_html=True,
            )


def _bloque_alertas(emp, met: dict, clas: dict):
    """Senales de alerta, ordenadas por gravedad y con el numero que las dispara."""
    st.subheader("Seniales de alerta")

    lista = alertas.evaluar(emp, met, clas)
    conteo = alertas.resumen(lista)

    if not lista:
        st.success(
            "Ninguna de las alertas del marco se dispara con los numeros "
            "actuales. Eso no la hace una buena compra: significa que no hay "
            "nada roto a la vista, y que el trabajo que queda es entender por "
            "que esta al precio que esta.",
            icon=":material/check_circle:",
        )
        return

    st.caption(
        "Evaluadas contra el cuadro de una empresa **%s**: %d criticas, "
        "%d para vigilar, %d menores." % (
            clas["nombre"].lower(), conteo[alertas.CRITICA],
            conteo[alertas.VIGILAR], conteo[alertas.MENOR])
    )

    tonos = {alertas.CRITICA: "#c0392b", alertas.VIGILAR: "#d68910",
             alertas.MENOR: "#9a7d0a"}
    cols = st.columns(2)
    for i, a in enumerate(lista):
        with cols[i % 2]:
            st.markdown(
                f"<div style='border-left:3px solid {tonos[a['severidad']]};"
                f"padding:8px 12px;margin-bottom:10px;"
                f"background:rgba(127,127,127,0.06)'>"
                f"<div style='font-size:0.72em;font-weight:700;letter-spacing:.05em;"
                f"text-transform:uppercase;color:{tonos[a['severidad']]}'>"
                f"{alertas.ETIQUETA[a['severidad']]}</div>"
                f"<div style='font-weight:600;margin:2px 0 4px'>{a['titulo']}</div>"
                f"<div style='font-size:0.87em;color:#6b7280'>{a['detalle']}</div>"
                f"</div>",
                unsafe_allow_html=True,
            )


@st.cache_data(show_spinner=False, ttl=3600)
def _trimestrales(ticker: str, claves: tuple[str, ...]) -> dict:
    try:
        return edgar.trimestrales(ticker, list(claves))
    except Exception:
        return {"periodos": [], "series": {}, "derivados": set()}


def _tabla_trimestral(datos: dict, claves: list[str], cuantos: int = 12):
    """Mismo estado, con los trimestres en columnas en vez de los ejercicios."""
    periodos = datos["periodos"][-cuantos:]
    if not periodos:
        return None

    filas, indice, usados = [], [], []
    for clave in claves:
        serie = datos["series"].get(clave)
        if not serie:
            continue
        es_unitario = clave in ("eps_diluido", "eps_basico")
        escala = 1.0 if es_unitario else 1e6
        filas.append([(serie[p] / escala) if p in serie else None for p in periodos])
        indice.append(_nombre(clave))
        usados.append(clave)

    if not filas:
        return None
    columnas = ["%dT%02d" % (t, a % 100) for a, t in periodos]
    df = pd.DataFrame(filas, index=indice, columns=columnas)
    df.attrs["claves"] = usados
    return df


def _bloque_estados(emp):
    st.subheader("Estados contables")

    fila = st.container(horizontal=True, vertical_alignment="center")
    with fila:
        periodicidad = st.segmented_control(
            "Periodicidad", ["Anual", "Trimestral"], default="Anual",
            label_visibility="collapsed", key="periodicidad_estados")
        st.caption("En millones de USD, salvo la ganancia por accion. "
                   "Fuente: SEC EDGAR.")

    st.caption("Los conceptos van en ingles, igual que en la presentacion "
               "original. Pasa el mouse por encima de cualquiera para ver la "
               "traduccion y que mide.")
    st.markdown(_CSS_ESTADOS, unsafe_allow_html=True)

    nombres = ["Income Statement", "Balance Sheet", "Cash Flow"]
    grupos = [ESTADO_RESULTADOS, ESTADO_BALANCE, ESTADO_FLUJO]

    if periodicidad == "Trimestral":
        _estados_trimestrales(emp, nombres, grupos)
        return

    tablas = {n: _tabla_estado(emp, claves) for n, claves in zip(nombres, grupos)}

    for pestania, nombre in zip(st.tabs(nombres), nombres):
        with pestania:
            df = tablas[nombre]
            if df is None:
                st.info("Sin datos suficientes para este estado.")
                continue
            st.markdown(_html_estado(df), unsafe_allow_html=True)

    _descarga_estados(emp, tablas)


def _estados_trimestrales(emp, nombres, grupos):
    """Los mismos estados por trimestre, con lo que EDGAR realmente permite.

    El flujo de caja queda afuera a proposito: en los 10-Q se presenta
    acumulado desde el inicio del ejercicio, no por trimestre. Publicarlo como
    si fuera trimestral mostraria el primer trimestre bien y los otros tres
    inflados, que es peor que no mostrarlo.
    """
    claves = tuple(ESTADO_RESULTADOS + ESTADO_BALANCE)
    datos = _trimestrales(emp.ticker, claves)

    if not datos["periodos"]:
        st.info(
            f"**{emp.ticker} no publica datos trimestrales en XBRL.** Los "
            "emisores extranjeros presentan 20-F una vez al ano y reportan sus "
            "trimestres por formulario 6-K, que es texto libre y no lleva datos "
            "estructurados. Solo hay informacion trimestral de las empresas que "
            "presentan 10-Q.",
            icon=":material/info:",
        )
        return

    tablas = {
        nombres[0]: _tabla_trimestral(datos, ESTADO_RESULTADOS),
        nombres[1]: _tabla_trimestral(datos, ESTADO_BALANCE),
        nombres[2]: None,
    }

    for pestania, nombre in zip(st.tabs(nombres), nombres):
        with pestania:
            if nombre == nombres[2]:
                st.info(
                    "El flujo de caja de un 10-Q viene acumulado desde el "
                    "inicio del ejercicio, no por trimestre, asi que no se "
                    "puede mostrar trimestralizado sin inventar los numeros. "
                    "Esta completo en la vista **Anual**.",
                    icon=":material/info:",
                )
                continue
            df = tablas[nombre]
            if df is None:
                st.info("Sin datos suficientes para este estado.")
                continue
            st.markdown(_html_estado(df), unsafe_allow_html=True)

    cuartos = sorted({p for _, p in datos["derivados"] if p[1] == 4})
    if cuartos:
        st.caption(
            "Los cuartos trimestres marcados —%s— se calculan restandole al "
            "ejercicio los tres trimestres anteriores: ninguna empresa presenta "
            "un informe del cuarto trimestre, va directo al anual."
            % ", ".join("4T%02d" % (a % 100) for a, _ in cuartos[-4:])
        )

    _descarga_estados(emp, tablas, sufijo="trimestral")


def _descarga_estados(emp, tablas, sufijo: str = "anual"):
    con_datos = {n: df for n, df in tablas.items() if df is not None}
    if not con_datos:
        return
    periodo = "años" if sufijo == "anual" else "trimestres"
    st.download_button(
        "Descargar estados en Excel",
        data=exportar.estados_a_excel(emp, con_datos),
        file_name=f"{emp.ticker}_estados_{sufijo}.xlsx",
        mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
        icon=":material/download:",
        key=f"descarga_estados_{sufijo}",
        help=f"Una hoja por estado, los {periodo} en columnas y los negativos "
             "en rojo. Listo para hacerle tus propias cuentas al lado.",
    )


def _bloque_graficos(emp):
    st.subheader("Evolucion historica")

    serie_precios = mercado.precios(emp.ticker)
    precios_anuales = mercado.serie_anual_precios(emp.ticker)

    figuras = [
        graficos.ingresos_y_margenes(emp),
        graficos.roic_vs_wacc(emp),
        graficos.ganancia_vs_caja(emp),
        graficos.deuda(emp),
        graficos.acciones(emp),
        graficos.asignacion_capital(emp),
        graficos.recompras_contra_precio(emp, precios_anuales),
        graficos.multiplo_historico(emp, precios_anuales),
    ]
    figuras = [f for f in figuras if f is not None]

    for i in range(0, len(figuras), 2):
        cols = st.columns(2)
        for col, fig in zip(cols, figuras[i:i + 2]):
            col.plotly_chart(fig, width="stretch")

    fig_precio = graficos.precio_historico(emp, serie_precios)
    if fig_precio:
        st.plotly_chart(fig_precio, width="stretch")


def _bloque_valuacion(emp, met: dict):
    st.subheader("Valuacion")

    izq, der = st.columns([1, 1])

    with izq:
        st.markdown("**DCF inverso**")
        st.caption(
            "No estima cuanto vale la empresa: calcula que crecimiento de la caja "
            "libre esta descontando el precio de hoy. Tu unico trabajo es decidir "
            "si ese numero es plausible."
        )

        wacc_defecto = (met.get("wacc") or 9.0)
        wacc = st.slider("Costo de capital (WACC)", 4.0, 20.0,
                         float(round(wacc_defecto, 1)), 0.5,
                         help="Mas alto = mas exigente. El estimado sale de CAPM "
                              "con la beta de la empresa.") / 100

        fcf_base = base.promedio(emp.ultimos("fcf", 3))
        if fcf_base:
            fcf_base = st.number_input(
                "FCF normalizado (M USD)", value=float(round(fcf_base / 1e6, 1)),
                step=10.0,
                help="Promedio de los ultimos 3 ejercicios. Ajustalo si sabes que "
                     "hubo algo extraordinario.") * 1e6

        resultado = valuacion_inversa.crecimiento_implicito(emp, fcf_base, wacc)
        if resultado is None:
            st.info("No se puede calcular: la empresa no tiene caja libre positiva.")
        elif resultado["g_implicito"] is None:
            st.warning(resultado["mensaje"])
        else:
            g = resultado["g_implicito"] * 100
            st.metric("Crecimiento anual implicito (10 años)", f"{g:,.1f}%")
            historico = met.get("cagr_fcf_5a")
            if historico is not None:
                st.caption(
                    f"Crecimiento real del FCF en los ultimos 5 años: **{historico:,.1f}%**. "
                    + ("El precio pide menos de lo que la empresa viene entregando."
                       if g < historico else
                       "El precio pide mas de lo que la empresa viene entregando.")
                )

    with der:
        st.markdown("**Valor por accion segun crecimiento**")
        st.caption("Que valdria la accion si el FCF creciera a cada tasa durante 10 años.")
        if fcf_base:
            tasas = [-0.05, 0.0, 0.03, 0.05, 0.08, 0.12]
            filas = valuacion_inversa.escenarios(emp, fcf_base, wacc, tasas)
            if filas:
                df = pd.DataFrame(filas)
                df.columns = ["Crecimiento", "Valor por accion", "Margen vs precio"]
                st.dataframe(
                    df.style.format({
                        "Crecimiento": "{:,.0f}%",
                        "Valor por accion": "${:,.2f}",
                        "Margen vs precio": "{:+,.0f}%",
                    }, na_rep="—").map(comun.pintar_signo,
                                       subset=["Margen vs precio"]),
                    hide_index=True, width="stretch",
                )
                st.caption(
                    "Margen positivo = el modelo da un valor mayor al precio de "
                    "mercado bajo ese supuesto."
                )


def _bloque_metricas(emp, met: dict):
    st.subheader("Todos los indicadores")

    no_aplican = perfiles.suprimidas(emp.perfil)
    ajenas = perfiles.ajenas(emp.perfil)
    propio = {perfiles.BANCO: "Banca", perfiles.SEGUROS: "Seguros",
              perfiles.REIT: "REIT"}.get(emp.perfil)

    for grupo, metricas_grupo in base.por_grupo().items():
        # Los grupos sectoriales solo existen para su propio tipo de empresa.
        if grupo in ("Banca", "Seguros", "REIT") and grupo != propio:
            continue
        visibles = [m for m in metricas_grupo if m.clave not in ajenas]
        if not visibles:
            continue
        abierto = grupo in ("Rentabilidad", "Solidez") or grupo == propio
        with st.expander(grupo, expanded=abierto):
            filas = []
            for m in visibles:
                valor = met.get(m.clave)
                estado = base.evaluar(m.clave, valor)
                # Distinguir "no aplica" de "falta el dato" es la mitad del
                # valor de esto: uno es una decision, el otro es un hueco.
                if m.clave in no_aplican:
                    texto = f"no aplica a {perfiles.NOMBRES[emp.perfil].lower()}"
                else:
                    texto = base.formatear(m.clave, valor)
                filas.append({
                    "": {"bueno": "🟢", "medio": "🟡", "malo": "🔴", "sin_dato": ""}[estado],
                    "Indicador": m.nombre,
                    "Valor": texto,
                    "Que mide": m.ayuda or m.descripcion,
                    "Como se calcula": m.formula,
                    "Valores de referencia": base.referencia(m.clave),
                })
            st.dataframe(
                pd.DataFrame(filas), hide_index=True, width="stretch",
                column_config={
                    "": st.column_config.TextColumn(width="small"),
                    "Indicador": st.column_config.TextColumn(width="medium"),
                    "Valor": st.column_config.TextColumn(width="small"),
                    "Que mide": st.column_config.TextColumn(width="large"),
                    "Como se calcula": st.column_config.TextColumn(width="medium"),
                    "Valores de referencia": st.column_config.TextColumn(width="medium"),
                })


def _bloque_diagnostico_mercado(emp):
    """Por que un dato de mercado viene vacio.

    Los fundamentals salen de EDGAR y su ausencia se explica en la auditoria de
    etiquetas. Los datos de mercado salen de Yahoo, que no es una API oficial y
    falla de maneras que desde afuera parecen "la columna esta vacia". Este
    bloque muestra que devolvio realmente y que error hubo.
    """
    with st.expander("Diagnostico de datos de mercado"):
        mk = emp.mercado or {}
        if not mk:
            st.error("No se obtuvo ningun dato de mercado para este ticker.")
            return

        st.caption(
            f"Fuente: Yahoo Finance vía yfinance {mk.get('version_yfinance', '?')} · "
            f"actualizado {mk.get('actualizado', 's/d')}"
        )

        if mk.get("error_info"):
            st.warning(
                f"**`.info` fallo:** {mk['error_info']}\n\nSin eso no hay sector, "
                "beta, dividendo ni PER forward. Suele pasar desde servidores: "
                "Yahoo bloquea direcciones de centros de datos.",
                icon=":material/cloud_off:")
        if mk.get("error_estimaciones"):
            st.warning(
                f"**Las estimaciones de consenso fallaron:** "
                f"{mk['error_estimaciones']}",
                icon=":material/query_stats:")

        filas = [
            ("Precio", mk.get("precio")),
            ("Market cap", mk.get("market_cap")),
            ("Sector", mk.get("sector")),
            ("Beta", mk.get("beta")),
            ("Dividendo anual por accion", mk.get("dividendo_anual")),
            ("PER forward (consenso)", mk.get("per_forward")),
            ("EPS forward (consenso)", mk.get("eps_forward")),
            ("Crecimiento ingresos NTM", mk.get("crec_ingresos_ntm")),
            ("Crecimiento EPS NTM", mk.get("crec_eps_ntm")),
            ("Analistas que cubren", mk.get("analistas_ntm")),
            ("Moneda del consenso", mk.get("moneda_ntm")),
            ("Moneda de la cotizacion", mk.get("moneda")),
        ]
        def _texto(v):
            # Todo a texto a proposito: la columna mezcla nombres de sector con
            # importes, y una columna de tipos mezclados no la puede serializar
            # Arrow. Aca lo que importa es si el campo llego, no operar con el.
            if v is None:
                return "—"
            if isinstance(v, float):
                return f"{v:,.2f}"
            return str(v)

        st.dataframe(
            pd.DataFrame(
                [{"Campo": n, "Valor": _texto(v),
                  "Estado": "vacio" if v is None else "ok"} for n, v in filas],
            ),
            hide_index=True, width="stretch")

        moneda_ntm, moneda = mk.get("moneda_ntm"), mk.get("moneda")
        if moneda_ntm and moneda and moneda_ntm != moneda:
            st.info(
                f"El consenso de analistas viene en **{moneda_ntm}** y la accion "
                f"cotiza en **{moneda}**. El PER forward queda vacio a proposito: "
                "dividir un precio por una ganancia en otra moneda da un multiplo "
                "que parece una ganga. Los crecimientos NTM si sirven, porque son "
                "porcentajes.",
                icon=":material/currency_exchange:")

        vacios = [n for n, v in filas if v is None]
        if vacios and not (mk.get("error_info") or mk.get("error_estimaciones")):
            st.caption(
                "Los campos vacios de arriba no dieron error: Yahoo simplemente "
                "no publica ese dato para este ticker. Es comun en empresas "
                "chicas, ADRs y REITs poco cubiertos por analistas."
            )


def _bloque_auditoria(emp):
    with st.expander("Auditoria de etiquetas XBRL"):
        st.caption(
            "De que etiqueta de EDGAR salio cada concepto. Si un numero te parece "
            "raro, mira aca antes de abrir el 10-K. Las empresas cambian de "
            "etiqueta con el tiempo: la columna 'cambio de etiqueta' marca donde "
            "el extractor tuvo que combinar dos o mas para armar la serie."
        )
        try:
            filas = edgar.diagnostico(emp.ticker)
        except Exception as exc:
            st.error(f"No se pudo generar el diagnostico: {exc}")
            return
        df = pd.DataFrame(filas)
        df.columns = ["Concepto", "Descripcion", "Años", "Etiquetas usadas", "Cambio de etiqueta"]
        st.dataframe(df, hide_index=True, width="stretch", height=400)


def _bloque_notas(emp):
    st.subheader("Tu tesis")
    st.caption(
        "Se guarda en la base local. Es el resumen de una linea que tenes que "
        "poder escribir antes de comprar."
    )
    actual = almacen.leer_nota(emp.ticker)
    texto = st.text_area(
        "Notas", value=actual, height=160, label_visibility="collapsed",
        placeholder="Por que cayo, que tiene que pasar para que se recupere, "
                    "que me haria admitir que me equivoque.")
    if st.button("Guardar nota"):
        almacen.guardar_nota(emp.ticker, texto)
        st.success("Nota guardada.")


def render():
    universo = comun.leer_universo()
    version = st.session_state.get("version_datos", 0)

    # El Panel deja aca la empresa sobre la que hiciste clic.
    preseleccion = st.session_state.get("ticker_detalle")

    with st.sidebar:
        st.subheader("Empresa")
        # El universo va primero y "(escribir otro)" al final: asi la opcion
        # por defecto es la primera accion de tu panel y no un ticker de
        # ejemplo que no seguis.
        opciones = universo + ["(escribir otro)"]

        # El selector va con `key` y no con `index`. Pasarle un index calculado
        # desde el mismo estado que el widget escribe cambia su identidad en
        # cada corrida: Streamlit lo toma por un widget nuevo y descarta lo que
        # elegiste, asi que cambiar de empresa dejaba de responder.
        #
        # La empresa que llega del Panel viaja en una clave de un solo uso, y
        # se consume aca. Solo asi mueve el selector cuando corresponde y no
        # cada vez que se vuelve a dibujar la pagina.
        pendiente = st.session_state.pop("ir_a_detalle", None)
        if pendiente and pendiente in opciones:
            st.session_state["sel_detalle"] = pendiente
        elif st.session_state.get("sel_detalle") not in opciones:
            # Primera visita, o el ticker elegido se fue del universo.
            st.session_state["sel_detalle"] = (
                preseleccion if preseleccion in opciones else opciones[0])
        elegido = st.selectbox("Del universo", opciones, key="sel_detalle")

        if elegido == "(escribir otro)":
            elegido = st.text_input(
                "Ticker", value=preseleccion or "",
                help="Cualquier emisor de EE.UU. que reporte a la SEC, este o no "
                     "en tu universo.").strip().upper()

        if elegido:
            st.session_state["ticker_detalle"] = elegido

        # Si estas mirando algo que no seguis todavia, sumarlo tiene que ser
        # un clic, no una vuelta por la barra lateral del Panel.
        if elegido and elegido not in universo:
            if st.button(f"Agregar {elegido} al universo", width="stretch",
                         icon=":material/add:"):
                comun.escribir_universo(universo + [elegido])
                st.rerun()

        if st.button("Recargar esta empresa", width="stretch",
                     icon=":material/refresh:"):
            st.cache_data.clear()
            st.rerun()

    if not elegido:
        st.info("Elegi un ticker en la barra lateral.")
        return

    with st.spinner(f"Analizando {elegido}..."):
        emp, met = comun.cargar_una(elegido, version)

    if emp.error:
        st.error(emp.error)
        return
    if not emp.tiene_datos():
        st.error(f"EDGAR no devolvio datos anuales utilizables para {elegido}.")
        return

    clas = estilo.clasificar(emp, met)

    _bloque_encabezado(emp, met, clas)
    st.divider()
    _bloque_cuadro(emp, met, clas)
    st.divider()
    _bloque_alertas(emp, met, clas)
    st.divider()
    _bloque_veredicto(emp, met)
    st.divider()
    _bloque_graficos(emp)
    st.divider()
    _bloque_estados(emp)
    st.divider()
    _bloque_valuacion(emp, met)
    st.divider()
    _bloque_metricas(emp, met)
    _bloque_auditoria(emp)
    _bloque_diagnostico_mercado(emp)
    st.divider()
    _bloque_notas(emp)


