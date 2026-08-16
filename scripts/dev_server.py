"""
Lanzador de la app para desarrollo, en un puerto libre.

Existe por un desajuste puntual: el entorno de desarrollo asigna el puerto por
la variable de entorno PORT, y Streamlit no la lee (solo acepta --server.port o
STREAMLIT_SERVER_PORT). Este script traduce una en la otra.

Para uso normal NO hace falta: para eso esta `Abrir Analizador.bat`, que corre
siempre en el 8501. Gracias a esta separacion, una sesion de desarrollo puede
levantar la app sin pisar la instancia que ya tengas abierta.
"""

import os
import pathlib
import subprocess
import sys

RAIZ = pathlib.Path(__file__).resolve().parent.parent


def main() -> int:
    puerto = os.environ.get("PORT") or os.environ.get("STREAMLIT_SERVER_PORT") or "8502"
    return subprocess.call(
        [
            sys.executable, "-m", "streamlit", "run", str(RAIZ / "Analizador.py"),
            "--server.port", str(puerto),
            "--server.headless", "true",
            "--browser.gatherUsageStats", "false",
        ],
        cwd=str(RAIZ),
    )


if __name__ == "__main__":
    sys.exit(main())
