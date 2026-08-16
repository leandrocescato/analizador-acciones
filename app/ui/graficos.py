"""Graficos de evolucion historica (Plotly).

Cada funcion recibe una Empresa y devuelve una figura, o None si no hay datos
suficientes. La pagina de Detalle decide cuales dibujar.
"""

from __future__ import annotations

import plotly.graph_objects as go

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

    fig = _base("Ingresos y margenes", "Ingresos (M USD)")
    anios, valores = _xy(ing, 1e6)
    fig.add_bar(x=anios, y=valores, name="Ingresos", marker_color=AZUL, opacity=0.55)

    for clave, nombre, color in [
        ("ganancia_bruta", "Margen bruto", VERDE),
        ("ebit", "Margen operativo", NARANJA),
        ("ganancia_neta", "Margen neto", VIOLETA),
    ]:
        serie = e.serie(clave)
        comunes = sorted(set(serie) & set(ing))
        if len(comunes) < 3:
            continue
        fig.add_scatter(
            x=comunes, y=[serie[a] / ing[a] * 100 for a in comunes],
            name=nombre, yaxis="y2", mode="lines+markers", line=dict(color=color, width=2),
        )

    fig.update_layout(yaxis2=_eje_secundario("Margen (%)"))
    return fig


def roic_vs_wacc(e):
    """ROIC contra costo de capital: la linea que separa crear de destruir valor."""
    from ..metricas.capital import _wacc

    nopat, capital = e.serie("nopat"), e.serie("capital_invertido")
    anios = sorted(set(nopat) & set(capital))
    if len(anios) < 3:
        return None

    fig = _base("ROIC contra costo de capital", "%")
    fig.add_scatter(
        x=anios, y=[nopat[a] / capital[a] * 100 for a in anios],
        name="ROIC", mode="lines+markers", line=dict(color=VERDE, width=3),
    )

    w = _wacc(e)
    if w:
        fig.add_scatter(
            x=anios, y=[w * 100] * len(anios), name="WACC estimado",
            mode="lines", line=dict(color=ROJO, width=2, dash="dash"),
        )
    return fig


def ganancia_vs_caja(e):
    """Ganancia contable contra caja libre. La brecha sostenida es la señal."""
    gn, fcf = e.serie("ganancia_neta"), e.serie("fcf")
    anios = sorted(set(gn) | set(fcf))
    if len(anios) < 3:
        return None

    fig = _base("Ganancia neta contra caja libre", "M USD")
    fig.add_bar(x=anios, y=[gn.get(a, 0) / 1e6 for a in anios],
                name="Ganancia neta", marker_color=GRIS)
    fig.add_bar(x=anios, y=[fcf.get(a, 0) / 1e6 for a in anios],
                name="Caja libre (FCF)", marker_color=VERDE)

    sbc = e.serie("sbc")
    if sbc:
        fig.add_scatter(
            x=anios, y=[(fcf.get(a, 0) - sbc.get(a, 0)) / 1e6 for a in anios],
            name="FCF neto de SBC", mode="lines+markers",
            line=dict(color=NARANJA, width=2, dash="dot"),
        )
    fig.update_layout(barmode="group")
    return fig


def deuda(e):
    """Deuda neta en barras y su multiplo de EBITDA en linea."""
    dn = e.serie("deuda_neta")
    if len(dn) < 3:
        return None

    fig = _base("Deuda neta y apalancamiento", "M USD")
    anios, valores = _xy(dn, 1e6)
    fig.add_bar(x=anios, y=valores, name="Deuda neta",
                marker_color=[ROJO if v > 0 else VERDE for v in valores])

    ebitda = e.serie("ebitda")
    comunes = [a for a in anios if ebitda.get(a, 0) > 0]
    if len(comunes) >= 3:
        fig.add_scatter(
            x=comunes, y=[dn[a] / ebitda[a] for a in comunes],
            name="Deuda neta / EBITDA", yaxis="y2", mode="lines+markers",
            line=dict(color=NARANJA, width=2),
        )
        fig.update_layout(yaxis2=_eje_secundario("veces EBITDA"))
    return fig


def acciones(e):
    """Acciones en circulacion. Sube = te diluyen. Baja = tu porcion crece."""
    serie = e.serie("acciones_dil")
    if len(serie) < 3:
        return None

    anios, valores = _xy(serie, 1e6)
    color = VERDE if valores[-1] <= valores[0] else ROJO
    fig = _base("Acciones en circulacion (diluidas)", "Millones de acciones")
    fig.add_scatter(x=anios, y=valores, mode="lines+markers", name="Acciones",
                    line=dict(color=color, width=3), fill="tozeroy",
                    fillcolor="rgba(120,120,120,0.10)")
    return fig


def asignacion_capital(e):
    """A donde va la caja que genera el negocio, año por año."""
    componentes = [
        ("capex", "Capex", AZUL),
        ("adquisiciones", "Adquisiciones", VIOLETA),
        ("dividendos", "Dividendos", VERDE),
        ("recompras", "Recompras", NARANJA),
    ]
    presentes = [(k, n, c) for k, n, c in componentes if e.serie(k)]
    if not presentes:
        return None

    anios = sorted({a for k, _, _ in presentes for a in e.serie(k)})
    if len(anios) < 3:
        return None

    fig = _base("Asignacion del capital", "M USD")
    for clave, nombre, color in presentes:
        serie = e.serie(clave)
        fig.add_bar(x=anios, y=[serie.get(a, 0) / 1e6 for a in anios],
                    name=nombre, marker_color=color)

    flujo = e.serie("flujo_operativo")
    if flujo:
        fig.add_scatter(
            x=anios, y=[flujo.get(a, 0) / 1e6 for a in anios],
            name="Flujo operativo", mode="lines+markers",
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

    fig = _base("Recompras contra cotizacion", "Recompras (M USD)")
    fig.add_bar(x=anios, y=[recompras[a] / 1e6 for a in anios],
                name="Recompras", marker_color=NARANJA, opacity=0.65)
    fig.add_scatter(x=anios, y=[precios_anuales[a] for a in anios],
                    name="Precio de cierre", yaxis="y2", mode="lines+markers",
                    line=dict(color=AZUL, width=3))
    fig.update_layout(yaxis2=_eje_secundario("USD por accion"))
    return fig


def multiplo_historico(e, precios_anuales: dict[int, float]):
    """PER y EV/EBIT año por año, para ver si el precio de hoy es caro
    contra su propia historia y no solo contra el sector."""
    acciones_serie, ganancia = e.serie("acciones_dil"), e.serie("ganancia_neta")
    anios = sorted(set(precios_anuales) & set(acciones_serie) & set(ganancia))
    anios = [a for a in anios if ganancia[a] > 0]
    if len(anios) < 4:
        return None

    fig = _base("PER historico (a cierre de cada año)", "veces")
    valores = [precios_anuales[a] / (ganancia[a] / acciones_serie[a]) for a in anios]
    fig.add_scatter(x=anios, y=valores, name="PER", mode="lines+markers",
                    line=dict(color=AZUL, width=3))

    promedio = sum(valores) / len(valores)
    fig.add_scatter(x=anios, y=[promedio] * len(anios), name=f"Promedio {promedio:.1f}x",
                    mode="lines", line=dict(color=GRIS, width=2, dash="dash"))
    return fig


def precio_historico(e, serie_precios: list[dict]):
    """Cotizacion de largo plazo, para ubicar el punto de entrada."""
    if not serie_precios:
        return None
    fig = _base("Cotizacion (15 años)", "USD")
    fig.add_scatter(
        x=[p["fecha"] for p in serie_precios], y=[p["cierre"] for p in serie_precios],
        name="Cierre", mode="lines", line=dict(color=AZUL, width=1.6),
    )
    fig.update_layout(hovermode="x")
    return fig

