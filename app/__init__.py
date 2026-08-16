"""Analizador de Acciones — nucleo de la aplicacion.

Capas, de abajo hacia arriba:
    config      parametros y rutas
    cache       persistencia local en SQLite
    conceptos   catalogo de conceptos contables XBRL
    proveedores adaptadores de fuentes externas (EDGAR, mercado)
    metricas    catalogo extensible de indicadores calculados
    modelo      union de fundamentals + mercado en un objeto Empresa
    ui          Panel (hoja 1) y Detalle (hoja 2) en Streamlit

Cada capa solo conoce a las de abajo.
"""

__version__ = "1.0.0"

