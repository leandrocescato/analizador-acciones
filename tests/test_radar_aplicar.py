"""La validacion de lo que escribe el agente en la nube
(scripts/radar_aplicar.py).

Es el unico punto donde una corrida rara del agente puede tocar el radar. El
agente busca en la web y escribe archivos; este script decide que entra. Por eso
los casos que importan no son los felices: son los archivos rotos.
"""

from __future__ import annotations

import importlib.util
import json
from pathlib import Path

import pytest

RAIZ = Path(__file__).resolve().parent.parent
_spec = importlib.util.spec_from_file_location(
    "radar_aplicar", RAIZ / "scripts" / "radar_aplicar.py")
radar_aplicar = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(radar_aplicar)


def _archivo(tmp_path: Path, contenido, nombre="AAA.json") -> Path:
    ruta = tmp_path / nombre
    if isinstance(contenido, str):
        ruta.write_text(contenido, encoding="utf-8")
    else:
        ruta.write_text(json.dumps(contenido, ensure_ascii=False), encoding="utf-8")
    return ruta


def test_un_diagnostico_bien_formado_entra_completo(tmp_path):
    ruta = _archivo(tmp_path, {
        "causa": "Hecho puntual",
        "texto": "Le cayo un juicio. Para descartar trampa: mirar las provisiones.",
        "fuentes": [{"titulo": "Reuters", "url": "https://reuters.com/x"}],
    })
    leido = radar_aplicar._leer(ruta)
    assert leido["causa"] == "Hecho puntual"
    assert leido["texto"].startswith("Le cayo un juicio")
    assert leido["fuentes"] == [{"titulo": "Reuters", "url": "https://reuters.com/x"}]
    assert leido["motor"] == "claude-code-action"


@pytest.mark.parametrize("contenido", [
    "{ esto no es json",
    '["una lista", "no un objeto"]',
    '{"causa": "Hecho puntual"}',          # sin texto
    '{"texto": "   ", "causa": "Ciclo del sector"}',   # texto en blanco
])
def test_un_archivo_roto_se_ignora_en_vez_de_romper_el_radar(tmp_path, contenido):
    assert radar_aplicar._leer(_archivo(tmp_path, contenido)) is None


def test_una_causa_inventada_pierde_la_etiqueta_y_no_el_texto(tmp_path):
    # El texto es el trabajo caro: si el agente etiqueto mal, se pierde la
    # etiqueta, no el analisis.
    ruta = _archivo(tmp_path, {
        "causa": "Pesimismo generalizado del mercado emergente",
        "texto": "Algo paso. Para descartar trampa: mirar el margen.",
    })
    leido = radar_aplicar._leer(ruta)
    assert leido["causa"] == ""
    assert leido["texto"].startswith("Algo paso")


def test_la_causa_se_reconoce_aunque_venga_con_cola(tmp_path):
    ruta = _archivo(tmp_path, {
        "causa": "Deterioro estructural (regulatorio)",
        "texto": "Algo paso. Para descartar trampa: mirar el margen.",
    })
    assert radar_aplicar._leer(ruta)["causa"] == "Deterioro estructural"


def test_las_fuentes_pegadas_al_parrafo_se_separan(tmp_path):
    # Claude Code cierra con una lista de enlaces aunque le pidas que no ponga
    # encabezados. Adentro del parrafo ensucian la ficha.
    ruta = _archivo(tmp_path, {
        "causa": "Ciclo del sector",
        "texto": ("Cayo el precio del gas. Para descartar trampa: mirar las "
                  "coberturas.\n\nSources:\n- [Reuters](https://reuters.com/g)"),
    })
    leido = radar_aplicar._leer(ruta)
    assert "Sources:" not in leido["texto"]
    assert leido["fuentes"][0]["url"] == "https://reuters.com/g"


def test_una_fuente_sin_url_no_entra(tmp_path):
    ruta = _archivo(tmp_path, {
        "causa": "Ciclo del sector", "texto": "Algo. Para descartar trampa: algo.",
        "fuentes": [{"titulo": "sin enlace"}, "no soy un dict",
                    {"titulo": "buena", "url": "https://x.com/1"}],
    })
    assert radar_aplicar._leer(ruta)["fuentes"] == [
        {"titulo": "buena", "url": "https://x.com/1"}]


def test_no_se_guardan_mas_de_cinco_fuentes(tmp_path):
    ruta = _archivo(tmp_path, {
        "causa": "Ciclo del sector", "texto": "Algo. Para descartar trampa: algo.",
        "fuentes": [{"titulo": f"n{i}", "url": f"https://x.com/{i}"} for i in range(9)],
    })
    assert len(radar_aplicar._leer(ruta)["fuentes"]) == 5
