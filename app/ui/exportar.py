"""
Exportacion a Excel.

El CSV perdia todo: los porcentajes quedaban como 33.79999999, los importes en
dolares crudos sin separador, y no habia forma de distinguir un multiplo de un
plazo en dias. Aca cada columna se escribe como NUMERO con el formato de Excel
que le corresponde, asi que sigue siendo ordenable y calculable, pero se lee.

Los formatos salen del campo `formato` del catalogo de metricas, que es el mismo
que usa la pantalla. Si mañana agregas un indicador con `formato="pct"`, se
exporta bien sin tocar este archivo.
"""

from __future__ import annotations

import io

import pandas as pd

from ..metricas import base

# Formato de Excel por tipo de metrica. La coma final en '#,##0,,' es la forma
# que tiene Excel de dividir por mil: dos comas = millones.
FORMATOS_EXCEL = {
    "pct": '#,##0.0"%"',
    "x": '#,##0.0"x"',
    "precio": '$#,##0.00',
    "usd": '#,##0,,"  M"',
    "dias": '#,##0" d"',
    "anios": '#,##0.0" a"',
    "score": "#,##0",
    "num": "#,##0.00",
}

RELLENOS = {
    "bueno": "#dcf0e4",
    "medio": "#fbf0d6",
    "malo": "#f8dcdc",
}


def _ancho(nombre: str, formato: str) -> int:
    base_ancho = max(len(nombre) + 3, 11)
    return min(base_ancho, 22 if formato != "usd" else 16)


def panel_a_excel(vista: pd.DataFrame, columnas_metrica: list[str]) -> bytes:
    """Convierte la tabla del Panel en un .xlsx formateado.

    Incluye el semaforo como color de fondo, autofiltro y paneles congelados,
    para que la planilla sirva sola sin tener que volver a la app.
    """
    df = vista.drop(columns=[c for c in ("GRAFICO",) if c in vista.columns])

    buffer = io.BytesIO()
    with pd.ExcelWriter(buffer, engine="xlsxwriter") as writer:
        df.to_excel(writer, sheet_name="Panel", index=False, startrow=1, header=False)
        libro = writer.book
        hoja = writer.sheets["Panel"]

        f_encabezado = libro.add_format({
            "bold": True, "bg_color": "#33415c", "font_color": "white",
            "border": 1, "border_color": "#26334d",
            "align": "center", "valign": "vcenter", "text_wrap": True,
        })
        f_texto = libro.add_format({"valign": "vcenter"})
        f_ticker = libro.add_format({"bold": True, "valign": "vcenter"})

        # Un formato numerico por tipo, y una variante por color de semaforo.
        cache_formatos: dict[tuple[str, str], object] = {}

        def formato_de(tipo: str, estado: str = ""):
            clave = (tipo, estado)
            if clave not in cache_formatos:
                spec = {"num_format": FORMATOS_EXCEL.get(tipo, "#,##0.00"),
                        "valign": "vcenter"}
                if estado in RELLENOS:
                    spec["bg_color"] = RELLENOS[estado]
                cache_formatos[clave] = libro.add_format(spec)
            return cache_formatos[clave]

        # --- encabezados
        for col, nombre in enumerate(df.columns):
            metrica = base.REGISTRO.get(nombre)
            etiqueta = metrica.nombre if metrica else nombre
            hoja.write(0, col, etiqueta, f_encabezado)
            if metrica:
                # El mismo texto que el tooltip de la pantalla, sin el markdown:
                # que mide, como se calcula y que valores esperar.
                nota = "\n\n".join(x for x in [
                    metrica.ayuda or metrica.descripcion,
                    f"Como se calcula: {metrica.formula}" if metrica.formula else "",
                    f"Valores de referencia: {base.referencia(nombre)}",
                ] if x)
                hoja.write_comment(0, col, nota, {"width": 380, "height": 210})
            tipo = metrica.formato if metrica else "texto"
            hoja.set_column(col, col, _ancho(etiqueta, tipo),
                            None if metrica else f_texto)

        # --- celdas
        for fila_idx, (_, fila) in enumerate(df.iterrows(), start=1):
            for col, nombre in enumerate(df.columns):
                valor = fila[nombre]
                metrica = base.REGISTRO.get(nombre)

                if metrica is None:
                    hoja.write(fila_idx, col, "" if pd.isna(valor) else str(valor),
                               f_ticker if nombre == "Ticker" else f_texto)
                    continue

                if valor is None or pd.isna(valor):
                    hoja.write_blank(fila_idx, col, None)
                    continue

                estado = base.evaluar(nombre, valor) if nombre in columnas_metrica else ""
                hoja.write_number(fila_idx, col, float(valor),
                                  formato_de(metrica.formato, estado))

        hoja.freeze_panes(1, 1)
        hoja.autofilter(0, 0, len(df), len(df.columns) - 1)
        hoja.set_row(0, 34)

    return buffer.getvalue()


def estados_a_excel(emp, tablas: dict[str, pd.DataFrame]) -> bytes:
    """Estados contables en una hoja por estado, con los años como columnas."""
    buffer = io.BytesIO()
    with pd.ExcelWriter(buffer, engine="xlsxwriter") as writer:
        libro = writer.book
        f_encabezado = libro.add_format({
            "bold": True, "bg_color": "#33415c", "font_color": "white",
            "align": "center", "valign": "vcenter", "border": 1,
        })
        f_concepto = libro.add_format({"bold": False, "valign": "vcenter"})
        f_millones = libro.add_format({"num_format": '#,##0;[Red]-#,##0'})
        f_unitario = libro.add_format({"num_format": '#,##0.00;[Red]-#,##0.00'})

        for nombre_hoja, df in tablas.items():
            if df is None or df.empty:
                continue
            hoja_nombre = nombre_hoja[:31]
            df.to_excel(writer, sheet_name=hoja_nombre, startrow=1, header=False)
            hoja = writer.sheets[hoja_nombre]

            hoja.write(0, 0, f"{emp.ticker} — en millones de USD", f_encabezado)
            for col, anio in enumerate(df.columns, start=1):
                hoja.write(0, col, str(anio), f_encabezado)

            for fila_idx, concepto in enumerate(df.index, start=1):
                hoja.write(fila_idx, 0, str(concepto), f_concepto)
                # La ganancia por accion es el unico renglon que no va en millones.
                formato = f_unitario if "accion" in str(concepto).lower() else f_millones
                for col, anio in enumerate(df.columns, start=1):
                    valor = df.loc[concepto, anio]
                    if valor is None or pd.isna(valor):
                        hoja.write_blank(fila_idx, col, None)
                    else:
                        hoja.write_number(fila_idx, col, float(valor), formato)

            hoja.set_column(0, 0, 34)
            hoja.set_column(1, len(df.columns), 13)
            hoja.freeze_panes(1, 1)

    return buffer.getvalue()
