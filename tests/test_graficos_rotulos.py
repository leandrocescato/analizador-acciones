"""Los rotulos de los graficos van en ingles y salen del glosario
(app/ui/graficos.py)."""

from __future__ import annotations

import pytest

from app import glosario, modelo
from app.ui import graficos


def _empresa() -> modelo.Empresa:
    anios = list(range(2016, 2026))
    def serie(base, paso=1.1):
        return {a: base * (paso ** (a - 2016)) for a in anios}
    return modelo.Empresa(
        ticker="TEST", nombre="Test Corp.", anios=anios,
        series={
            "ingresos": serie(1_000e6), "ganancia_bruta": serie(400e6),
            "ebit": serie(200e6), "ganancia_neta": serie(150e6),
            "fcf": serie(120e6), "sbc": serie(20e6),
            "deuda_neta": serie(300e6), "ebitda": serie(250e6),
            "acciones_dil": serie(100e6, 0.98),
            "capex": serie(80e6), "dividendos": serie(30e6),
            "recompras": serie(50e6), "flujo_operativo": serie(200e6),
            "nopat": serie(160e6), "capital_invertido": serie(900e6),
        },
    )


def _figuras():
    e = _empresa()
    precios = {a: 50.0 + a - 2016 for a in e.anios}
    return [f for f in (
        graficos.ingresos_y_margenes(e),
        graficos.roic_vs_wacc(e),
        graficos.ganancia_vs_caja(e),
        graficos.deuda(e),
        graficos.acciones(e),
        graficos.asignacion_capital(e),
        graficos.recompras_contra_precio(e, precios),
        graficos.multiplo_historico(e, precios),
    ) if f is not None]


def _rotulos(fig) -> list[str]:
    ejes = [fig.layout.title.text, fig.layout.yaxis.title.text]
    eje2 = getattr(fig.layout, "yaxis2", None)
    if eje2 is not None and eje2.title is not None:
        ejes.append(eje2.title.text)
    return [t for t in ejes + [tr.name for tr in fig.data] if t]


# Palabras que delatan que un rotulo volvio al castellano. No se buscan acentos
# porque el resto del codigo escribe sin ellos: "Margen" y "Ganancia" van a
# aparecer igual.
_CASTELLANO = ("Ingres", "Margen", "Ganancia", "Caja", "Deuda", "Acciones",
               "Recompra", "Precio", "Promedio", "Asignacion", "Cotizacion",
               "veces", "estimado")


def test_ningun_rotulo_de_grafico_quedo_en_castellano():
    figuras = _figuras()
    assert len(figuras) >= 7, "la empresa de prueba tiene que dibujar casi todo"
    for fig in figuras:
        for rotulo in _rotulos(fig):
            for palabra in _CASTELLANO:
                assert palabra not in rotulo, f"{rotulo!r} tiene {palabra!r}"


def test_los_rotulos_salen_del_glosario_y_no_de_una_copia():
    # Si alguien reescribe un rotulo a mano en `graficos.py`, un dia va a decir
    # una cosa distinta de la que dice la tabla de estados contables.
    rotulos = {r for fig in _figuras() for r in _rotulos(fig)}
    assert glosario.ingles("ingresos") in rotulos
    assert glosario.ingles("ganancia_neta") in rotulos
    assert glosario.metrica_en("margen_bruto") in rotulos
    assert glosario.metrica_en("roic") in rotulos


@pytest.mark.parametrize("clave, esperado", [
    ("ingresos", "Total Revenue"),        # concepto contable
    ("margen_bruto", "Gross Margin"),     # indicador calculado
])
def test_en_busca_en_los_dos_diccionarios(clave, esperado):
    assert graficos._en(clave) == esperado


def test_en_cae_al_respaldo_cuando_la_clave_no_esta():
    assert graficos._en("no_existe_esta_clave", "Fallback") == "Fallback"
