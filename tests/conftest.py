"""Helpers compartidos para armar companyfacts sinteticos sin tocar la red.

Los tests de este proyecto arman a mano la porcion minima de un
`companyfacts` de la SEC que necesita cada caso, en vez de guardar fixtures
grandes. `hecho`/`bloque`/`facts_de` son los tres niveles de esa forma:

    facts_de(us_gaap={"Assets": bloque(hecho(100, end="2023-12-31"))})
"""

from __future__ import annotations


def hecho(
    val: float,
    end: str,
    start: str | None = None,
    form: str = "10-K",
    filed: str = "2024-02-01",
) -> dict:
    """Un hecho XBRL individual, con los campos que usa el extractor."""
    h = {"val": val, "end": end, "form": form, "filed": filed}
    if start is not None:
        h["start"] = start
    return h


def bloque(*hechos: dict, unidad: str = "USD") -> dict:
    """La forma `{"units": {unidad: [...]}}` que trae cada etiqueta XBRL."""
    return {"units": {unidad: list(hechos)}}


def facts_de(us_gaap: dict | None = None, ifrs_full: dict | None = None,
             dei: dict | None = None) -> dict:
    """El dict `companyfacts`-shaped completo, con solo los espacios pedidos."""
    facts: dict = {}
    if us_gaap:
        facts["us-gaap"] = us_gaap
    if ifrs_full:
        facts["ifrs-full"] = ifrs_full
    if dei:
        facts["dei"] = dei
    return {"facts": facts}
