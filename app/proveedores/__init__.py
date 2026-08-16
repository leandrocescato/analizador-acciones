"""Adaptadores de fuentes de datos.

Cada modulo de este paquete encapsula UNA fuente y expone funciones que
devuelven estructuras limpias. Ningun modulo de metricas ni de interfaz
debe saber de donde vino el dato ni como esta paginado.

Para agregar una fuente nueva (por ejemplo Finnhub para insider trading),
se crea un modulo aca y se lo consume desde `modelo.py`. Nada mas cambia.
"""

