@echo off
REM Lanzador del Analizador de Acciones.
REM Doble clic para abrirlo. Deja esta ventana negra abierta mientras lo uses:
REM es el servidor. Al cerrarla, la app se apaga.

title Analizador de Acciones - NO CERRAR mientras lo uses
cd /d "%~dp0"

echo.
echo   Iniciando el Analizador de Acciones...
echo   Se va a abrir solo en el navegador, en http://localhost:8501
echo.
echo   IMPORTANTE: no cierres esta ventana mientras uses la app.
echo   Para apagarla, cerra esta ventana o apreta Ctrl+C.
echo.

streamlit run Analizador.py --server.port 8501 --browser.gatherUsageStats false

REM Si streamlit no esta en el PATH, se intenta por modulo de Python.
if errorlevel 1 (
    echo.
    echo   No se encontro el comando streamlit. Reintentando via Python...
    echo.
    python -m streamlit run Analizador.py --server.port 8501 --browser.gatherUsageStats false
)

echo.
echo   La aplicacion se detuvo.
pause
