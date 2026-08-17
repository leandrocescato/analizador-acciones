"""
Metricas de crecimiento.

Se miden a 5 y 10 años porque el crecimiento de un solo ejercicio no distingue
una tendencia de un rebote. Y siempre en tasa compuesta anual, no acumulada:
un 100% en 10 años suena bien hasta que ves que son 7,2% por año.

Ojo con leerlas aisladas: crecer no es bueno per se. Crecer con ROIC incremental
por debajo del WACC destruye valor. Este grupo se lee junto con `Rentabilidad`.
"""

from __future__ import annotations

from .base import cagr, div, metrica, pct, promedio


def _cagr_serie(e, clave: str, anios: int) -> float | None:
    """CAGR anclado al ultimo ejercicio de la EMPRESA.

    Si la serie dejo de reportarse hace años, devuelve None en lugar de medir
    un crecimiento entre dos fechas viejas y presentarlo como actual.
    """
    serie = e.serie(clave)
    if not serie or e.ultimo is None:
        return None

    fin = max(serie)
    if e.ultimo - fin > 2:
        return None

    candidatos = [a for a in serie if a <= fin - anios]
    ini = max(candidatos) if candidatos else min(serie)
    if ini == fin or fin - ini < 3:
        return None
    return cagr(serie[ini], serie[fin], fin - ini)


@metrica("cagr_ingresos_5a", "Crecimiento ingresos 5a", "Crecimiento", formato="pct",
         panel=True, mejor="alto", umbrales=(8, 0),
         ayuda="A que ritmo crece el negocio, medido en 5 años para que no lo "
               "distorsione un ejercicio suelto. En una empresa castigada, un "
               "crecimiento que sigue positivo es la mejor prueba de que la "
               "caida es de multiplo y no de negocio.",
         formula="Tasa compuesta anual de los ingresos en 5 ejercicios.")
def cagr_ingresos_5a(e):
    return _cagr_serie(e, "ingresos", 5)


@metrica("cagr_ingresos_10a", "Crecimiento ingresos 10a", "Crecimiento", formato="pct",
         mejor="alto", umbrales=(7, 0),
         ayuda="La misma medida en 10 años. Comparala con la de 5: si la de 5 "
               "es mucho menor, el negocio se esta desacelerando.",
         formula="Tasa compuesta anual de los ingresos en 10 "
                 "ejercicios.")
def cagr_ingresos_10a(e):
    return _cagr_serie(e, "ingresos", 10)


@metrica("cagr_ebit_5a", "Crecimiento EBIT 5a", "Crecimiento", formato="pct",
         mejor="alto", umbrales=(10, 0),
         ayuda="Si el EBIT crece mas rapido que los ingresos, hay apalancamiento "
               "operativo: los margenes se estan expandiendo.",
         formula="Tasa compuesta anual del resultado operativo en 5 "
                 "ejercicios.")
def cagr_ebit_5a(e):
    return _cagr_serie(e, "ebit", 5)


@metrica("cagr_fcf_5a", "Crecimiento FCF 5a", "Crecimiento", formato="pct", panel=True,
         mejor="alto", umbrales=(10, 0),
         ayuda="Crecimiento de la caja libre. Es el que mas importa: es la plata "
               "que efectivamente le pertenece al accionista.",
         formula="Tasa compuesta anual de la caja libre en 5 "
                 "ejercicios.")
def cagr_fcf_5a(e):
    return _cagr_serie(e, "fcf", 5)


@metrica("cagr_eps_5a", "Crecimiento EPS 5a", "Crecimiento", formato="pct",
         mejor="alto", umbrales=(10, 0),
         ayuda="Crecimiento de la ganancia POR ACCION. Si supera al del EBIT, "
               "las recompras estan sumando; si queda por debajo, la dilucion "
               "se esta comiendo el crecimiento del negocio.",
         formula="Tasa compuesta anual de la ganancia por accion en 5 "
                 "ejercicios.")
def cagr_eps_5a(e):
    return _cagr_serie(e, "eps_diluido", 5)


@metrica("cagr_patrimonio_5a", "Crecimiento patrimonio 5a", "Crecimiento", formato="pct",
         ayuda="Crecimiento del valor libro. En negocios con muchas recompras "
               "puede ser negativo sin que eso sea malo.",
         formula="Tasa compuesta anual del patrimonio neto en 5 "
                 "ejercicios.")
def cagr_patrimonio_5a(e):
    return _cagr_serie(e, "patrimonio", 5)


@metrica("aceleracion_ingresos", "Aceleracion de ingresos", "Crecimiento", formato="pct",
         mejor="alto", umbrales=(2, -5),
         ayuda="Crecimiento de 5 años menos el de 10 años, en puntos. Positivo "
               "significa que el negocio se esta acelerando; negativo, que la "
               "tendencia larga se esta apagando. Para una empresa castigada, "
               "esta es una de las pistas mas utiles sobre si la caida es "
               "temporal o estructural.",
         formula="CAGR de ingresos a 5 años − CAGR a 10 años, en "
                 "puntos.")
def aceleracion_ingresos(e):
    c5, c10 = _cagr_serie(e, "ingresos", 5), _cagr_serie(e, "ingresos", 10)
    return None if c5 is None or c10 is None else c5 - c10



@metrica("regla_40", "Regla del 40", "Crecimiento", formato="num",
         mejor="alto", umbrales=(40, 20), panel=True,
         ayuda="Crecimiento de ingresos mas margen de caja libre, sumados. La "
               "regla dice que una empresa sana esta arriba de 40: puede crecer "
               "poco si genera mucha caja, o quemar caja si crece rapido, pero "
               "no las dos cosas mal a la vez. Sirve para juzgar a una empresa "
               "en crecimiento sin castigarla por reinvertir.",
         formula="Crecimiento de ingresos (%) + margen de caja libre "
                 "(%), sumados.")
def regla_40(e):
    crecimiento = _cagr_serie(e, "ingresos", 3) or _cagr_serie(e, "ingresos", 5)
    margen = pct(e.f("fcf"), e.f("ingresos"))
    if crecimiento is None or margen is None:
        return None
    return crecimiento + margen


@metrica("peg", "PEG", "Crecimiento", formato="x",
         mejor="bajo", umbrales=(1.0, 2.0),
         ayuda="PER dividido el crecimiento anual de la ganancia por accion. "
               "Debajo de 1 el crecimiento no esta pagado; arriba de 2, el "
               "precio ya descuenta que siga creciendo asi. Solo tiene sentido "
               "con crecimiento positivo: con ganancias que caen, el cociente "
               "no significa nada y queda vacio.",
         formula="PER / crecimiento anual de la ganancia por accion. "
                 "Solo con crecimiento positivo.")
def peg(e):
    from .base import REGISTRO
    per = REGISTRO["per"].fn(e)
    crecimiento = _cagr_serie(e, "eps_diluido", 5)
    if per is None or crecimiento is None or crecimiento <= 0:
        return None
    return per / crecimiento


@metrica("crec_ingresos_ntm", "Ingresos NTM (est.)", "Crecimiento", formato="pct",
         mejor="alto", umbrales=(10, 0), panel=True,
         formula="Crecimiento estimado de los ingresos del proximo ejercicio "
                 "completo contra el actual, segun el consenso de analistas "
                 "que publica Yahoo Finance.",
         ayuda="OJO: es una estimacion, no un dato reportado. Vale sobre todo "
               "comparada con el crecimiento historico de la fila de al lado: "
               "si la empresa viene creciendo al 3% y el consenso proyecta 15%, "
               "alguien tiene que explicar de donde sale esa aceleracion, y esa "
               "explicacion es tu tesis o es el motivo para no comprar. El "
               "consenso se revisa a la baja mas seguido que al alza.")
def crec_ingresos_ntm(e):
    return e.mercado.get("crec_ingresos_ntm")


@metrica("crec_eps_ntm", "EPS NTM (est.)", "Crecimiento", formato="pct",
         mejor="alto", umbrales=(12, 0), panel=True,
         formula="Crecimiento estimado de la ganancia por accion del proximo "
                 "ejercicio completo contra el actual, segun el consenso de "
                 "analistas que publica Yahoo Finance.",
         ayuda="OJO: es una estimacion, no un dato reportado. Comparalo con el "
               "crecimiento esperado de ingresos: si se espera que la ganancia "
               "crezca mucho mas rapido que las ventas, el consenso esta "
               "asumiendo expansion de margenes, que es el supuesto que mas "
               "seguido falla. Si crece menos, hay dilucion o presion de costos.")
def crec_eps_ntm(e):
    return e.mercado.get("crec_eps_ntm")
