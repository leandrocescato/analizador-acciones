"""
Catalogo de metricas.

Importar este paquete puebla `base.REGISTRO` con todos los indicadores.
El orden de import define el orden en que aparecen dentro de cada grupo.

PARA AGREGAR UN INDICADOR NUEVO:
  1. Elegi el modulo del grupo que corresponda (o crea uno nuevo y sumalo aca).
  2. Escribi una funcion con el decorador @metrica.
  3. Listo. Aparece en el Panel, en el Detalle, en los filtros y en el historial.

No hay que registrar nada en ningun otro lado.
"""

from . import base  # noqa: F401  (define el registro)
from . import mercado_met  # noqa: F401
from . import valuacion  # noqa: F401
from . import rentabilidad  # noqa: F401
from . import caja  # noqa: F401
from . import solidez  # noqa: F401
from . import capital  # noqa: F401
from . import crecimiento  # noqa: F401
from . import senales  # noqa: F401
from . import sectoriales  # noqa: F401  (banca, seguros y REITs)

from .base import (  # noqa: F401
    REGISTRO,
    Metrica,
    calcular_todas,
    del_panel,
    evaluar,
    formatear,
    por_grupo,
)

__all__ = [
    "REGISTRO", "Metrica", "calcular_todas", "del_panel",
    "evaluar", "formatear", "por_grupo", "base",
]

