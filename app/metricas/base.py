"""
Infraestructura del catalogo de metricas.

ESTE ES EL PUNTO DE EXTENSION DEL SISTEMA
-----------------------------------------
Agregar un indicador nuevo es escribir una funcion con un decorador:

    @metrica("mi_ratio", "Mi Ratio", "Valuacion", formato="x", mejor="bajo",
             umbrales=(10, 25), panel=True)
    def mi_ratio(e):
        return div(e.f("ebit"), e.mercado["market_cap"])

Con eso solo, el indicador aparece en el Panel, en el Detalle, en el semaforo,
en el ordenamiento y en los snapshots historicos. No hay que tocar nada mas.

Si la funcion falla o le faltan datos, devuelve None y el sistema sigue: una
empresa sin inventario no debe romper el analisis de las otras 200.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Callable

from .. import glosario, perfiles

# ------------------------------------------------------------------ helpers


def div(a, b):
    """Division que no explota: None si falta un dato o el divisor es cero."""
    if a is None or b is None:
        return None
    try:
        a, b = float(a), float(b)
    except (TypeError, ValueError):
        return None
    if b == 0 or a != a or b != b:
        return None
    return a / b


def pct(a, b):
    """Cociente expresado en porcentaje."""
    r = div(a, b)
    return None if r is None else r * 100


def suma(*valores):
    """Suma tratando None como cero, pero devuelve None si TODOS son None."""
    presentes = [float(v) for v in valores if v is not None and v == v]
    return sum(presentes) if presentes else None


def resta(a, b):
    if a is None:
        return None
    return float(a) - (float(b) if b is not None else 0.0)


def cagr(inicial, final, anios):
    """Tasa compuesta anual. None si hay signos que la vuelven ininterpretable."""
    if inicial is None or final is None or anios <= 0:
        return None
    if inicial <= 0 or final <= 0:
        return None
    return ((final / inicial) ** (1 / anios) - 1) * 100


def promedio(valores):
    limpios = [float(v) for v in valores if v is not None and v == v]
    return sum(limpios) / len(limpios) if limpios else None


def mediana(valores):
    limpios = sorted(float(v) for v in valores if v is not None and v == v)
    if not limpios:
        return None
    n = len(limpios)
    return limpios[n // 2] if n % 2 else (limpios[n // 2 - 1] + limpios[n // 2]) / 2


def desvio(valores):
    limpios = [float(v) for v in valores if v is not None and v == v]
    if len(limpios) < 2:
        return None
    m = sum(limpios) / len(limpios)
    return (sum((x - m) ** 2 for x in limpios) / (len(limpios) - 1)) ** 0.5


# ------------------------------------------------------------------ registro


@dataclass
class Metrica:
    clave: str
    nombre: str
    grupo: str
    fn: Callable
    formato: str = "num"        # pct | x | usd | num | años | score
    mejor: str = "neutro"       # alto | bajo | neutro
    umbrales: tuple | None = None   # (bueno, malo); admite bueno > malo o al reves
    panel: bool = False         # si aparece por defecto en la hoja 1
    descripcion: str = ""
    ayuda: str = ""             # que mide y como leerlo
    formula: str = ""           # como se calcula, en lenguaje contable


REGISTRO: dict[str, Metrica] = {}
ORDEN_GRUPOS: list[str] = [
    "Mercado",
    "Valuacion",
    "Rentabilidad",
    "Caja",
    "Solidez",
    "Capital",
    "Crecimiento",
    "Senales",
    # Sectoriales: solo aparecen en las empresas de ese tipo.
    "Banca",
    "Seguros",
    "REIT",
]


def _origen(fn) -> tuple[str, str]:
    """De donde viene una funcion. Sobrevive a que el modulo se vuelva a importar."""
    return (getattr(fn, "__module__", ""), getattr(fn, "__qualname__", ""))


def metrica(clave, nombre, grupo, **kw):
    def decorador(fn):
        # Registrar dos veces LA MISMA funcion no es un error: es que el modulo
        # se volvio a importar. Pasa cuando un import se corta por la mitad
        # —Streamlit interrumpe el script si refrescas la pagina mientras
        # arranca— y Python descarta ese modulo pero conserva los que si
        # terminaron. En el siguiente intento el modulo caido se ejecuta de
        # nuevo contra un REGISTRO ya poblado.
        #
        # Antes eso rompia la app para siempre con "Metrica duplicada", que
        # ademas tapaba el error original. Lo que si sigue siendo un error es
        # que DOS funciones distintas peleen por la misma clave.
        previa = REGISTRO.get(clave)
        if previa is not None and _origen(previa.fn) != _origen(fn):
            raise ValueError(
                f"Metrica duplicada: '{clave}' la definen "
                f"{'.'.join(_origen(previa.fn))} y {'.'.join(_origen(fn))}. "
                "Cada indicador necesita su propia clave.")
        REGISTRO[clave] = Metrica(
            clave=clave, nombre=nombre, grupo=grupo, fn=fn,
            descripcion=kw.pop("descripcion", "") or (fn.__doc__ or "").strip(),
            **kw,
        )
        return fn
    return decorador


def calcular_todas(empresa) -> dict[str, float | None]:
    """Corre el catalogo entero sobre una empresa. Ninguna metrica puede romper el resto.

    Las metricas que no aplican al tipo de empresa se devuelven vacias SIN
    calcularlas. En un banco, el ROIC y el EV/EBIT dan numeros perfectamente
    formateados y economicamente falsos; publicarlos es peor que no tenerlos.
    Ver `perfiles.py`.
    """
    perfil = getattr(empresa, "perfil", perfiles.GENERAL)
    no_aplican = perfiles.no_aplican(perfil)

    salida: dict[str, float | None] = {}
    for clave, m in REGISTRO.items():
        if clave in no_aplican:
            salida[clave] = None
            continue
        try:
            valor = m.fn(empresa)
        except Exception:
            valor = None
        if isinstance(valor, (int, float)) and valor != valor:  # NaN
            valor = None
        salida[clave] = valor
    return salida


def rotulo(clave: str) -> str:
    """Nombre visible de un indicador: en ingles, como en cualquier informe.

    El castellano no desaparece: sigue siendo `Metrica.nombre` y sale en el
    tooltip. Se resuelve aca y no en cada pantalla para que el Panel, el
    Detalle, los filtros y el Excel no puedan llamar distinto a lo mismo.
    """
    en_ingles = glosario.metrica_en(clave)
    if en_ingles:
        return en_ingles
    m = REGISTRO.get(clave)
    return m.nombre if m else clave


def rotulo_grupo(grupo: str) -> str:
    """Nombre visible de un grupo. La clave interna no cambia."""
    return glosario.grupo_en(grupo)


def por_grupo() -> dict[str, list[Metrica]]:
    grupos: dict[str, list[Metrica]] = {}
    for m in REGISTRO.values():
        grupos.setdefault(m.grupo, []).append(m)
    ordenados = {g: grupos[g] for g in ORDEN_GRUPOS if g in grupos}
    for g in sorted(grupos):
        ordenados.setdefault(g, grupos[g])
    return ordenados


def del_panel() -> list[Metrica]:
    return [m for m in REGISTRO.values() if m.panel]


# ------------------------------------------------------------------ semaforo


def evaluar(clave: str, valor) -> str:
    """Clasifica un valor en 'bueno' / 'medio' / 'malo' / 'sin_dato'.

    Los umbrales son heuristicas de valor, no verdades: sirven para que el ojo
    encuentre rapido lo que merece atencion, no para decidir por vos.
    """
    m = REGISTRO.get(clave)
    if m is None or valor is None or m.umbrales is None:
        return "sin_dato"
    try:
        v = float(valor)
    except (TypeError, ValueError):
        return "sin_dato"

    bueno, malo = m.umbrales
    if m.mejor == "alto":
        if v >= bueno:
            return "bueno"
        return "malo" if v <= malo else "medio"
    if m.mejor == "bajo":
        if v <= bueno:
            return "bueno"
        return "malo" if v >= malo else "medio"
    return "sin_dato"


def referencia(clave: str) -> str:
    """Los valores esperados de un indicador, EN TEXTO, sacados de sus umbrales.

    Se genera en vez de escribirse a mano a proposito: el tooltip y el color de
    la celda salen de la misma fuente, asi que no pueden contradecirse. Un
    umbral que se ajusta cambia los dos al mismo tiempo.
    """
    m = REGISTRO.get(clave)
    if m is None:
        return ""
    if not m.umbrales:
        return ("Sin umbral fijo: se lee contra su propia historia y contra "
                "empresas comparables del mismo sector.")

    bueno, malo = (formatear(clave, v) for v in m.umbrales)
    if m.mejor == "alto":
        return f"Bueno: {bueno} o mas · Medio: entre {malo} y {bueno} · Malo: {malo} o menos"
    if m.mejor == "bajo":
        return f"Bueno: {bueno} o menos · Medio: entre {bueno} y {malo} · Malo: {malo} o mas"
    return ("Sin umbral fijo: se lee contra su propia historia y contra "
            "empresas comparables del mismo sector.")


def formatear(clave: str, valor) -> str:
    """Representacion en texto de un valor segun el formato declarado."""
    m = REGISTRO.get(clave)
    if valor is None or (isinstance(valor, float) and valor != valor):
        return "—"
    f = m.formato if m else "num"
    try:
        v = float(valor)
    except (TypeError, ValueError):
        return str(valor)

    if f == "pct":
        return f"{v:,.1f}%"
    if f == "x":
        return f"{v:,.1f}x"
    if f == "usd":
        return _usd(v)
    if f == "precio":
        return f"${v:,.2f}"
    if f == "dias":
        return f"{v:,.0f} d"
    if f == "anios":
        return f"{v:,.1f} a"
    if f == "score":
        return f"{v:,.0f}"
    return f"{v:,.2f}"


def _usd(v: float) -> str:
    """Importes grandes siempre en millones de USD, como pediste en las columnas."""
    if abs(v) >= 1e6:
        return f"{v / 1e6:,.0f} M"
    return f"{v:,.0f}"

