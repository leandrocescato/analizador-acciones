"""Memoria del radar entre corridas (app/radar.py).

Lo que se prueba aca no es el barrido —eso es una llamada a Yahoo y no tiene
sentido probarlo sin red— sino `fusionar`, que es donde el radar puede
arruinarse en silencio. Si pierde la memoria, el barrido diario te ofrece todos
los dias las mismas empresas que ya rechazaste, o vuelve a pagarle a Claude por
un diagnostico que ya estaba escrito. Ninguna de las dos cosas rompe nada: solo
hacen que la herramienta deje de servir.
"""

from __future__ import annotations

import datetime as dt

from app import radar

HOY = dt.date.today().isoformat()


def _candidata(ticker="AAA", **extra) -> dict:
    return {"ticker": ticker, "nombre": "Empresa " + ticker, "per": 8.0,
            "eps": 2.0, "var_52s": -30.0, **extra}


def _estado(candidatas=None, descartadas=None) -> dict:
    return {"corrida": None, "filtros": radar.filtros_por_defecto(),
            "candidatas": candidatas or [], "descartadas": descartadas or {}}


# ------------------------------------------------------------------ altas


def test_una_candidata_nueva_entra_con_la_fecha_de_hoy():
    nuevo = radar.fusionar(_estado(), [_candidata()], [], {})
    assert [c["ticker"] for c in nuevo["candidatas"]] == ["AAA"]
    assert nuevo["candidatas"][0]["fecha_alta"] == HOY
    assert nuevo["candidatas"][0]["vigente"] is True


def test_la_que_ya_tenes_en_el_universo_no_es_candidata():
    nuevo = radar.fusionar(_estado(), [_candidata("AAPL")], ["aapl"], {})
    assert nuevo["candidatas"] == []


def test_la_descartada_no_vuelve_aunque_siga_pasando_el_filtro():
    previo = radar.descartar(_estado([_candidata()]), "AAA", "no me gusta")
    nuevo = radar.fusionar(previo, [_candidata()], [], {})
    assert nuevo["candidatas"] == []
    assert "AAA" in nuevo["descartadas"]


def test_rehabilitar_la_vuelve_a_hacer_elegible():
    previo = radar.rehabilitar(radar.descartar(_estado(), "AAA"), "AAA")
    nuevo = radar.fusionar(previo, [_candidata()], [], {})
    assert [c["ticker"] for c in nuevo["candidatas"]] == ["AAA"]


# ------------------------------------------------------------------ memoria


def test_el_diagnostico_y_la_fecha_de_alta_sobreviven_a_la_corrida_siguiente():
    ayer = (dt.date.today() - dt.timedelta(days=1)).isoformat()
    diag = {"texto": "Cayo por un juicio", "causa": "Hecho puntual"}
    previo = _estado([_candidata(fecha_alta=ayer, diagnostico=diag, vigente=True,
                                visto=ayer)])

    nuevo = radar.fusionar(previo, [_candidata()], [], {})

    guardada = nuevo["candidatas"][0]
    assert guardada["fecha_alta"] == ayer, "la antiguedad en el radar se perdio"
    assert guardada["diagnostico"] == diag, "habria que pagar el diagnostico de nuevo"


def test_los_numeros_si_se_actualizan_todos_los_dias():
    previo = _estado([_candidata(per=8.0, fecha_alta=HOY, visto=HOY)])
    nuevo = radar.fusionar(previo, [_candidata(per=6.0)], [], {})
    assert nuevo["candidatas"][0]["per"] == 6.0


# ------------------------------------------------------------------ bajas


def test_la_que_dejo_de_pasar_el_filtro_queda_marcada_pero_no_desaparece():
    previo = _estado([_candidata(fecha_alta=HOY, visto=HOY, vigente=True)])
    nuevo = radar.fusionar(previo, [], [], {})
    assert len(nuevo["candidatas"]) == 1
    assert nuevo["candidatas"][0]["vigente"] is False


def test_la_que_no_pasa_el_filtro_hace_meses_se_va_sola():
    viejo = (dt.date.today() - dt.timedelta(days=radar.DIAS_RETENCION + 1)).isoformat()
    previo = _estado([_candidata(fecha_alta=viejo, visto=viejo, vigente=False)])
    nuevo = radar.fusionar(previo, [], [], {})
    assert nuevo["candidatas"] == []


def test_quitar_saca_del_radar_sin_dejarla_descartada():
    """Es lo que pasa cuando la aprobas: se va al universo, no al descarte.

    La diferencia importa: una descartada nunca vuelve, y si aprobar la marcara
    como descartada, sacarla del universo mas adelante la volveria invisible
    para el barrido para siempre.
    """
    nuevo = radar.quitar(_estado([_candidata()]), "AAA")
    assert nuevo["candidatas"] == []
    assert nuevo["descartadas"] == {}


# ------------------------------------------------------------------ filtros


def test_normalizar_completa_los_filtros_que_falten():
    """El gist lo escribio una version anterior de la app, sin los filtros nuevos."""
    completos = radar.normalizar({"per_max": 9.0})
    assert completos["per_max"] == 9.0
    assert completos["roe_min"] == radar.FILTROS_POR_CLAVE["roe_min"].defecto
    assert "max_candidatas" in completos


def test_un_filtro_en_blanco_no_viaja_a_la_consulta():
    filtros = radar.normalizar({"per_max": None})
    consulta = str(radar._consulta(filtros))
    assert "peratio" in consulta, "el PER minimo si tiene valor y deberia estar"
    assert consulta.count("peratio") == 1, "el PER maximo estaba apagado"


def test_sin_diagnostico_solo_mira_las_vigentes():
    estado = _estado([
        _candidata("AAA", vigente=True, diagnostico=None),
        _candidata("BBB", vigente=True, diagnostico={"texto": "ya esta"}),
        _candidata("CCC", vigente=False, diagnostico=None),
    ])
    assert [c["ticker"] for c in radar.sin_diagnostico(estado)] == ["AAA"]


# ------------------------------------------------------------------ escalas


def test_la_distancia_al_maximo_se_calcula_y_no_se_lee_de_yahoo():
    """Yahoo mezcla dos escalas en el mismo objeto y una de las dos miente.

    `fiftyTwoWeekChangePercent` viene en porciento (-63,0) y
    `fiftyTwoWeekHighChangePercent` en fraccion (-0,647). Leer los dos como
    vienen daba candidatas que habian caido 63% en el año y figuraban a 0,6%
    de su maximo. No rompe nada: solo miente, que es peor.
    """
    fila = radar._fila({
        "symbol": "QFIN",
        "regularMarketPrice": 11.53,
        "fiftyTwoWeekHigh": 32.69,
        "fiftyTwoWeekHighChangePercent": -0.6472928,   # la fraccion, ignorada
        "fiftyTwoWeekChangePercent": -63.00909,        # el porciento, usado
    })
    assert fila["var_52s"] == -63.00909
    assert -65.0 < fila["dist_max52"] < -64.0, "quedo en escala de fraccion"


def test_sin_maximo_de_52_semanas_la_distancia_queda_vacia():
    fila = radar._fila({"symbol": "AAA", "regularMarketPrice": 10, "fiftyTwoWeekHigh": None})
    assert fila["dist_max52"] is None


def test_el_precio_sobre_valor_libro_no_se_calcula_con_patrimonio_negativo():
    """Un P/VL de -3x no significa 'barata': significa que no aplica."""
    assert radar._fila({"symbol": "A", "regularMarketPrice": 10, "bookValue": -5})["pvl"] is None
    assert radar._fila({"symbol": "A", "regularMarketPrice": 10, "bookValue": 5})["pvl"] == 2.0


# ------------------------------------------------------------------ el candado del gasto


def test_la_api_no_se_prende_sola_por_tener_la_clave_en_el_entorno(monkeypatch):
    """La regla es que el diagnostico no cuesta un peso arriba de la suscripcion.

    Una ANTHROPIC_API_KEY suelta en el entorno —muchas herramientas la dejan
    puesta— alcanzaba para que la app empezara a facturar aparte sin decir nada.
    Ahora hace falta pedirlo a mano.
    """
    from app import diagnostico

    monkeypatch.setattr(diagnostico, "_cli", lambda: None)  # sin Claude Code
    monkeypatch.setenv("ANTHROPIC_API_KEY", "sk-ant-loquesea")
    monkeypatch.delenv(diagnostico.PERMISO_API, raising=False)

    motor, motivo = diagnostico.backend()
    assert motor is None, "se prendio la API sin que nadie la habilitara"
    assert diagnostico.PERMISO_API in motivo


def test_con_claude_code_nunca_se_mira_la_api(monkeypatch):
    from app import diagnostico

    monkeypatch.setattr(diagnostico, "_cli", lambda: "/usr/bin/claude")
    monkeypatch.setenv("ANTHROPIC_API_KEY", "sk-ant-loquesea")
    monkeypatch.setenv(diagnostico.PERMISO_API, "1")

    assert diagnostico.backend() == ("claude-code", "")
