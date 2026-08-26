"""Graficos de evolucion historica (Plotly).

Cada funcion recibe una Empresa y devuelve una figura, o None si no hay datos
suficientes. La pagina de Detalle decide cuales dibujar.

LOS ROTULOS VAN EN INGLES
-------------------------
Por lo mismo que los estados contables (ver `ui/detalle.py::_nombre`): lo que
publica la SEC esta en ingles, y un grafico que dice "Margen bruto" al lado de
una tabla que dice "Gross Profit" obliga a traducir de ida y de vuelta cada vez.

Y no se escriben a mano aca. Salen de `glosario.py`, que es de donde salen los
de la tabla: un rotulo duplicado es un rotulo que un dia va a decir otra cosa.
`_en()` busca primero entre los conceptos contables y despues entre los
indicadores calculados, que son dos diccionarios distintos.
"""

from __future__ import annotations

import plotly.graph_objects as go

from .. import glosario

VERDE = "#2f9e6b"
ROJO = "#cf4b4b"
AZUL = "#3b7dd8"
NARANJA = "#e0912f"
GRIS = "#8a8f98"
VIOLETA = "#8e6fd0"


def _base(titulo: str, y_titulo: str = "") -> go.Figure:
    """Figura con el layout comun a todos los graficos.

    La leyenda va DEBAJO del area de dibujo, no arriba. Arriba compite con el
    titulo por el mismo espacio y, en las columnas angostas del Detalle, se
    parte en dos renglones y lo tapa. Abajo puede crecer todo lo que necesite:
    `margin.autoexpand` le hace lugar sola.

    `automargin` en los ejes evita que se corten los titulos laterales cuando
    el grafico entra en media pantalla.
    """
    fig = go.Figure()
    fig.update_layout(
        title=dict(text=titulo, x=0, xanchor="left", y=0.97, yanchor="top",
                   font=dict(size=15)),
        height=420,
        margin=dict(l=10, r=10, t=54, b=10),
        hovermode="x unified",
        legend=dict(orientation="h", yanchor="top", y=-0.14,
                    xanchor="left", x=0, font=dict(size=11)),
        yaxis=dict(title=y_titulo, automargin=True),
        xaxis=dict(automargin=True),
    )
    return fig


def _eje_secundario(titulo: str) -> dict:
    """Eje derecho, siempre con automargin para que no se corte su titulo."""
    return dict(title=titulo, overlaying="y", side="right",
                showgrid=False, automargin=True)


def _en(clave: str, respaldo: str = "") -> str:
    """Rotulo en ingles de un concepto contable o de un indicador calculado."""
    return glosario.ingles(clave) or glosario.metrica_en(clave) or respaldo or clave


def _xy(serie: dict[int, float], escala: float = 1.0):
    anios = sorted(serie)
    return anios, [serie[a] / escala for a in anios]


def ingresos_y_margenes(e):
    """Ingresos en barras contra los tres margenes en lineas.

    Es el grafico que mas rapido separa una empresa que cayo por precio de una
    que cayo por deterioro: si los ingresos crecen y los margenes se hunden,
    el problema es de costos o de competencia, no del mercado.
    """
    ing = e.serie("ingresos")
    if len(ing) < 3:
        return None

    fig = _base(f'{_en("ingresos")} & Margins', f'{_en("ingresos")} ($M)')
    anios, valores = _xy(ing, 1e6)
    fig.add_bar(x=anios, y=valores, name=_en("ingresos"), marker_color=AZUL, opacity=0.55)

    for clave, nombre, color in [
        ("ganancia_bruta", _en("margen_bruto"), VERDE),
        ("ebit", _en("margen_operativo"), NARANJA),
        ("ganancia_neta", _en("margen_neto"), VIOLETA),
    ]:
        serie = e.serie(clave)
        comunes = sorted(set(serie) & set(ing))
        if len(comunes) < 3:
            continue
        fig.add_scatter(
            x=comunes, y=[serie[a] / ing[a] * 100 for a in comunes],
            name=nombre, yaxis="y2", mode="lines+markers", line=dict(color=color, width=2),
        )

    fig.update_layout(yaxis2=_eje_secundario("Margin (%)"))
    return fig


def roic_vs_wacc(e):
    """ROIC contra costo de capital: la linea que separa crear de destruir valor."""
    from ..metricas.capital import _wacc

    nopat, capital = e.serie("nopat"), e.serie("capital_invertido")
    anios = sorted(set(nopat) & set(capital))
    if len(anios) < 3:
        return None

    fig = _base(f'{_en("roic")} vs. Cost of Capital', "%")
    fig.add_scatter(
        x=anios, y=[nopat[a] / capital[a] * 100 for a in anios],
        name=_en("roic"), mode="lines+markers", line=dict(color=VERDE, width=3),
    )

    w = _wacc(e)
    if w:
        fig.add_scatter(
            x=anios, y=[w * 100] * len(anios), name=_en("wacc"),
            mode="lines", line=dict(color=ROJO, width=2, dash="dash"),
        )
    return fig


def ganancia_vs_caja(e):
    """Ganancia contable contra caja libre. La brecha sostenida es la señal."""
    gn, fcf = e.serie("ganancia_neta"), e.serie("fcf")
    anios = sorted(set(gn) | set(fcf))
    if len(anios) < 3:
        return None

    fig = _base(f'{_en("ganancia_neta")} vs. {_en("fcf")}', "$M")
    fig.add_bar(x=anios, y=[gn.get(a, 0) / 1e6 for a in anios],
                name=_en("ganancia_neta"), marker_color=GRIS)
    fig.add_bar(x=anios, y=[fcf.get(a, 0) / 1e6 for a in anios],
                name=_en("fcf"), marker_color=VERDE)

    sbc = e.serie("sbc")
    if sbc:
        fig.add_scatter(
            x=anios, y=[(fcf.get(a, 0) - sbc.get(a, 0)) / 1e6 for a in anios],
            name="FCF net of SBC", mode="lines+markers",
            line=dict(color=NARANJA, width=2, dash="dot"),
        )
    fig.update_layout(barmode="group")
    return fig


def deuda(e):
    """Deuda neta en barras y su multiplo de EBITDA en linea."""
    dn = e.serie("deuda_neta")
    if len(dn) < 3:
        return None

    fig = _base(f'{_en("deuda_neta")} & Leverage', "$M")
    anios, valores = _xy(dn, 1e6)
    fig.add_bar(x=anios, y=valores, name=_en("deuda_neta"),
                marker_color=[ROJO if v > 0 else VERDE for v in valores])

    ebitda = e.serie("ebitda")
    comunes = [a for a in anios if ebitda.get(a, 0) > 0]
    if len(comunes) >= 3:
        fig.add_scatter(
            x=comunes, y=[dn[a] / ebitda[a] for a in comunes],
            name=_en("deuda_neta_ebitda"), yaxis="y2", mode="lines+markers",
            line=dict(color=NARANJA, width=2),
        )
        fig.update_layout(yaxis2=_eje_secundario("x EBITDA"))
    return fig


def acciones(e):
    """Acciones en circulacion. Sube = te diluyen. Baja = tu porcion crece."""
    serie = e.serie("acciones_dil")
    if len(serie) < 3:
        return None

    anios, valores = _xy(serie, 1e6)
    color = VERDE if valores[-1] <= valores[0] else ROJO
    fig = _base(_en("acciones_dil"), "Millions of shares")
    fig.add_scatter(x=anios, y=valores, mode="lines+markers", name=_en("acciones_dil"),
                    line=dict(color=color, width=3), fill="tozeroy",
                    fillcolor="rgba(120,120,120,0.10)")
    return fig


def asignacion_capital(e):
    """A donde va la caja que genera el negocio, año por año."""
    componentes = [
        ("capex", "CapEx", AZUL),
        ("adquisiciones", "Acquisitions", VIOLETA),
        ("dividendos", _en("dividendos"), VERDE),
        ("recompras", _en("recompras"), NARANJA),
    ]
    presentes = [(k, n, c) for k, n, c in componentes if e.serie(k)]
    if not presentes:
        return None

    anios = sorted({a for k, _, _ in presentes for a in e.serie(k)})
    if len(anios) < 3:
        return None

    fig = _base(glosario.grupo_en("Capital"), "$M")
    for clave, nombre, color in presentes:
        serie = e.serie(clave)
        fig.add_bar(x=anios, y=[serie.get(a, 0) / 1e6 for a in anios],
                    name=nombre, marker_color=color)

    flujo = e.serie("flujo_operativo")
    if flujo:
        fig.add_scatter(
            x=anios, y=[flujo.get(a, 0) / 1e6 for a in anios],
            name="Cash Flow from Operations", mode="lines+markers",
            line=dict(color=GRIS, width=2, dash="dash"),
        )
    fig.update_layout(barmode="stack")
    return fig


def recompras_contra_precio(e, precios_anuales: dict[int, float]):
    """Cuanto recompro cada año contra a que precio cotizaba.

    Un management que recompra fuerte en los maximos y frena en los minimos
    esta destruyendo valor con la mejor de las intenciones. Este grafico lo
    muestra sin discusion posible.
    """
    recompras = e.serie("recompras")
    if len(recompras) < 3 or not precios_anuales:
        return None

    anios = sorted(set(recompras) & set(precios_anuales))
    if len(anios) < 3:
        return None

    fig = _base(f'{_en("recompras")} vs. Share Price', f'{_en("recompras")} ($M)')
    fig.add_bar(x=anios, y=[recompras[a] / 1e6 for a in anios],
                name=_en("recompras"), marker_color=NARANJA, opacity=0.65)
    fig.add_scatter(x=anios, y=[precios_anuales[a] for a in anios],
                    name="Closing Price", yaxis="y2", mode="lines+markers",
                    line=dict(color=AZUL, width=3))
    fig.update_layout(yaxis2=_eje_secundario("$ per share"))
    return fig


def multiplo_historico(e, precios_anuales: dict[int, float]):
    """PER y EV/EBIT año por año, para ver si el precio de hoy es caro
    contra su propia historia y no solo contra el sector."""
    acciones_serie, ganancia = e.serie("acciones_dil"), e.serie("ganancia_neta")
    anios = sorted(set(precios_anuales) & set(acciones_serie) & set(ganancia))
    anios = [a for a in anios if ganancia[a] > 0]
    if len(anios) < 4:
        return None

    fig = _base(f'Historical {_en("per")} (at each year-end)', "x")
    valores = [precios_anuales[a] / (ganancia[a] / acciones_serie[a]) for a in anios]
    fig.add_scatter(x=anios, y=valores, name=_en("per"), mode="lines+markers",
                    line=dict(color=AZUL, width=3))

    promedio = sum(valores) / len(valores)
    fig.add_scatter(x=anios, y=[promedio] * len(anios), name=f"Average {promedio:.1f}x",
                    mode="lines", line=dict(color=GRIS, width=2, dash="dash"))
    return fig


def precio_historico(e, serie_precios: list[dict]):
    """Cotizacion de largo plazo, para ubicar el punto de entrada."""
    if not serie_precios:
        return None
    fig = _base("Share Price (15 years)", "USD")
    fig.add_scatter(
        x=[p["fecha"] for p in serie_precios], y=[p["cierre"] for p in serie_precios],
        name="Close", mode="lines", line=dict(color=AZUL, width=1.6),
    )
    fig.update_layout(hovermode="x")
    return fig

