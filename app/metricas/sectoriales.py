"""
Indicadores propios de bancos, aseguradoras y REITs.

Estos negocios no son variantes de una industrial: se miden con otra vara. Un
banco no tiene margen operativo pero tiene margen de intereses; una aseguradora
no tiene ROIC pero tiene ratio combinado, que dice en un solo numero si gana
plata asegurando o solo invirtiendo; un REIT no tiene PER util pero tiene FFO.

Cada indicador de aca se calcula UNICAMENTE en su perfil. La regla vive en
`perfiles.EXCLUSIVAS`, no en este archivo: asi no hay forma de que un ratio
combinado aparezca en una empresa de software.
"""

from __future__ import annotations

from .base import cagr, div, metrica, pct, promedio, resta, suma


def _activo_promedio(e) -> float | None:
    """Activo medio del ejercicio. Un banco crece durante el año y medir el
    margen contra el activo de cierre lo subestima."""
    serie = e.serie("activo_total")
    if not serie:
        return None
    ultimo = max(serie)
    valores = [serie[ultimo]]
    if (ultimo - 1) in serie:
        valores.append(serie[ultimo - 1])
    return promedio(valores)


# ------------------------------------------------------------------ banca


@metrica("margen_intereses", "Margen de intereses (NIM)", "Banca", formato="pct",
         mejor="alto", umbrales=(3.5, 2.0), panel=True,
         ayuda="Margen financiero sobre el activo promedio: cuanto le queda al "
               "banco de cada dolar del balance despues de pagar por los "
               "fondos. Es el equivalente al margen bruto de una industrial. "
               "Un banco de deposito tipico ronda el 3%; muy por encima suele "
               "significar prestamos mas riesgosos, no mejor gestion.",
         formula="Margen financiero / activo total promedio del "
                 "ejercicio × 100.")
def margen_intereses(e):
    return pct(e.f("interes_neto"), _activo_promedio(e))


@metrica("ratio_eficiencia", "Ratio de eficiencia", "Banca", formato="pct",
         mejor="bajo", umbrales=(55, 70), panel=True,
         ayuda="Gastos operativos sobre ingresos totales: cuanto cuesta generar "
               "un dolar de ingreso. Es EL indicador de gestion de un banco. "
               "Por debajo de 55% es eficiente; por encima de 70% hay una "
               "estructura que se come el negocio.",
         formula="Gastos operativos / (margen financiero + comisiones) "
                 "× 100.")
def ratio_eficiencia(e):
    return pct(*e.par("no_interes_gastos", "ingresos_bancarios"))


# Un prestamista en marcha no puede perder un cuarto de su cartera por año ni
# tener reservadas la mitad de sus colocaciones. Si el cociente da eso, lo que
# esta mal es el denominador: la empresa etiqueta como "prestamos" solo una
# parte de su cartera. Le pasa a NU, que deja la mayor parte del credito fuera
# de `LoansAndAdvancesToCustomers` y daria un coste del riesgo del 71%.
# No es un tope al indicador: es un detector de cartera incompleta.
TECHO_COSTE_RIESGO = 25.0
TECHO_RESERVAS = 40.0
# Y por abajo pasa lo mismo: ningun prestamista tiene reservado el 0,02% de su
# cartera. NU publica una unica cifra de 1 M contra 3.200 M de creditos, que es
# la reserva de una sub-cartera, no la del balance.
PISO_RESERVAS = 0.1


@metrica("coste_riesgo", "Coste del riesgo", "Banca", formato="pct",
         mejor="bajo", umbrales=(0.5, 2.0), panel=True,
         ayuda="Cargo del ejercicio por incobrables sobre la cartera de "
               "prestamos. Es lo que le cuesta al banco prestar mal, cada año. "
               "Sube antes que la mora y antes que las perdidas: es el aviso "
               "mas temprano que hay en un balance bancario. Queda vacio si la "
               "empresa no etiqueta su cartera completa en EDGAR.",
         formula="Cargo del ejercicio por incobrables / cartera de "
                 "prestamos × 100. Los dos terminos, del mismo "
                 "ejercicio.")
def coste_riesgo(e):
    provision, prestamos = e.par("provision_creditos", "prestamos")
    r = pct(provision, prestamos)
    return None if r is None or r > TECHO_COSTE_RIESGO else r


@metrica("cobertura_reservas", "Reservas sobre cartera", "Banca", formato="pct",
         ayuda="Reserva acumulada para incobrables sobre el total de prestamos. "
               "No hay un valor bueno universal: alto puede ser prudencia o "
               "puede ser una cartera mala. Se lee contra su propia historia y "
               "contra los bancos comparables.",
         formula="Reserva acumulada para incobrables / cartera de "
                 "prestamos × 100.")
def cobertura_reservas(e):
    reserva, prestamos = e.par("reserva_creditos", "prestamos")
    r = pct(reserva, prestamos)
    if r is None or not (PISO_RESERVAS <= r <= TECHO_RESERVAS):
        return None
    return r


@metrica("prestamos_depositos", "Prestamos / Depositos", "Banca", formato="pct",
         mejor="bajo", umbrales=(85, 100), panel=True,
         ayuda="Cuanto de lo que presta el banco esta fondeado con depositos. "
               "Por encima de 100% depende de fondeo mayorista, que es el que "
               "desaparece justo cuando mas se lo necesita: fue exactamente el "
               "mecanismo de las caidas de 2008 y de 2023.",
         formula="Cartera de prestamos / depositos de clientes × 100.")
def prestamos_depositos(e):
    prestamos, depositos = e.par("prestamos", "depositos")
    return pct(prestamos, depositos)


@metrica("apalancamiento", "Apalancamiento (Activo / Patrimonio)", "Banca",
         formato="x", mejor="bajo", umbrales=(10, 15), panel=True,
         ayuda="Cuantas veces el activo supera al patrimonio. En un banco 10x "
               "es normal y 20x es fragil: con 20x, una perdida del 5% del "
               "activo se lleva todo el capital de los accionistas.",
         formula="Activo total / patrimonio neto.")
def apalancamiento(e):
    return div(*e.par("activo_total", "patrimonio"))


@metrica("peso_comisiones", "Comisiones / Ingresos", "Banca", formato="pct",
         ayuda="Que parte del ingreso no depende del diferencial de tasas. Un "
               "banco muy apoyado en comisiones sufre menos cuando las tasas "
               "bajan, pero compite con mas gente por ese negocio.",
         formula="Comisiones y servicios / (margen financiero + "
                 "comisiones) × 100.")
def peso_comisiones(e):
    return pct(*e.par("no_interes_ingresos", "ingresos_bancarios"))


@metrica("cagr_depositos_5a", "Crecimiento depositos 5a", "Banca", formato="pct",
         mejor="alto", umbrales=(6, 0),
         ayuda="Los depositos son la materia prima barata de un banco. Que "
               "crezcan sostenidamente vale mas que casi cualquier otra cosa; "
               "que se fuguen es la forma en que un banco muere.",
         formula="Tasa compuesta anual de los depositos de clientes.")
def cagr_depositos_5a(e):
    serie = e.serie("depositos")
    ventana = sorted(e.ventana(6) & set(serie))
    if len(ventana) < 4:
        return None
    return cagr(serie[ventana[0]], serie[ventana[-1]], ventana[-1] - ventana[0])


# ------------------------------------------------------------------ seguros


def _trio_seguro(e):
    """Gastos totales, siniestros y primas del mismo ejercicio.

    Los tres ratios de suscripcion se leen juntos y tienen que cerrar:
    siniestralidad mas gastos igual a combinado. Sacados cada uno de su propio
    año mas reciente, no cierran.
    """
    return e.juntos("gastos_seguro_total", "siniestros", "primas_devengadas")


@metrica("ratio_combinado", "Ratio combinado", "Seguros", formato="pct",
         mejor="bajo", umbrales=(95, 100), panel=True,
         ayuda="Siniestros y gastos sobre primas devengadas. Es el numero que "
               "define a una aseguradora: por debajo de 100 gana plata "
               "asegurando y ademas cobra por invertir el float; por encima de "
               "100 pierde asegurando y depende de la cartera para no perder "
               "plata. Una que sostiene menos de 95 durante años tiene una "
               "ventaja real en seleccion de riesgos.",
         formula="(Siniestros + gastos) / primas devengadas × 100. Los "
                 "tres terminos salen del mismo ejercicio para que "
                 "cierren entre si.")
def ratio_combinado(e):
    total, _, primas = _trio_seguro(e)
    return pct(total, primas)


@metrica("ratio_siniestralidad", "Ratio de siniestralidad", "Seguros", formato="pct",
         mejor="bajo", umbrales=(65, 80), panel=True,
         ayuda="Siniestros sobre primas. La mitad del ratio combinado que "
               "depende de que tan bien elige y tarifa los riesgos.",
         formula="Siniestros incurridos / primas devengadas × 100.")
def ratio_siniestralidad(e):
    _, siniestros, primas = _trio_seguro(e)
    return pct(siniestros, primas)


@metrica("ratio_gastos", "Ratio de gastos", "Seguros", formato="pct",
         mejor="bajo", umbrales=(28, 35), panel=True,
         ayuda="La otra mitad del ratio combinado: cuanto cuesta vender y "
               "administrar las polizas. Es la parte que la empresa controla "
               "directamente, y donde se ven las ventajas de escala.",
         formula="(Siniestros y gastos totales − siniestros) / primas "
                 "devengadas × 100.")
def ratio_gastos(e):
    total, siniestros, primas = _trio_seguro(e)
    if total is None or siniestros is None:
        return None
    return pct(resta(total, siniestros), primas)


@metrica("float_sobre_cap", "Float / Capitalizacion", "Seguros", formato="pct",
         panel=True,
         ayuda="Reservas por siniestros mas primas no devengadas, sobre la "
               "capitalizacion. Es la plata de terceros que la aseguradora "
               "invierte por su cuenta hasta que tenga que pagarla. Con ratio "
               "combinado por debajo de 100 ese dinero sale a costo negativo, "
               "y ahi esta el negocio: mucho float con buena suscripcion es la "
               "combinacion que hizo a Berkshire.",
         formula="(Reservas por siniestros + primas no devengadas) / "
                 "capitalizacion × 100.")
def float_sobre_cap(e):
    flotante = suma(e.f("reservas_siniestros"), e.f("primas_no_devengadas"))
    return pct(flotante, e.market_cap)


@metrica("rendimiento_float", "Rendimiento del float", "Seguros", formato="pct",
         mejor="alto", umbrales=(4, 1.5),
         ayuda="Resultado de la cartera de inversiones sobre el float. Cuanto "
               "le saca la aseguradora a la plata que todavia no tuvo que pagar.",
         formula="Resultado de inversiones / float × 100.")
def rendimiento_float(e):
    flotante = suma(e.f("reservas_siniestros"), e.f("primas_no_devengadas"))
    return pct(e.f("ingresos_inversiones"), flotante)


@metrica("cagr_primas_5a", "Crecimiento primas 5a", "Seguros", formato="pct",
         mejor="alto", umbrales=(8, 0),
         ayuda="Crecimiento de las primas devengadas. Ojo: crecer rapido es "
               "facil bajando el precio de las polizas, y eso aparece dos años "
               "despues en el ratio de siniestralidad. Se lee junto con el "
               "ratio combinado, nunca solo.",
         formula="Tasa compuesta anual de las primas devengadas.")
def cagr_primas_5a(e):
    serie = e.serie("primas_devengadas")
    ventana = sorted(e.ventana(6) & set(serie))
    if len(ventana) < 4:
        return None
    return cagr(serie[ventana[0]], serie[ventana[-1]], ventana[-1] - ventana[0])


# ------------------------------------------------------------------ REITs


@metrica("ffo", "FFO", "REIT", formato="usd", panel=True,
         ayuda="Funds From Operations, el estandar de NAREIT: ganancia neta mas "
               "amortizacion, menos las ganancias por venta de inmuebles. La "
               "amortizacion supone que un edificio se gasta como una maquina, "
               "y en general se revaloriza, asi que la ganancia contable de un "
               "REIT subestima su capacidad real de generar caja. Queda vacio "
               "si la empresa nunca etiqueta la ganancia por venta de "
               "inmuebles: sin ese dato no se pueden separar los resultados "
               "extraordinarios y el FFO sale inflado. Le pasa a Simon Property.",
         formula="Ganancia neta + amortizacion − ganancia por venta de "
                 "inmuebles + deterioros. Es la definicion de NAREIT.")
def ffo(e):
    return e.f("ffo")


@metrica("ffo_por_accion", "FFO por accion", "REIT", formato="precio",
         ayuda="FFO dividido las acciones diluidas. Es el numero que los REITs "
               "reportan y guian, el equivalente a la ganancia por accion.",
         formula="FFO / acciones diluidas.")
def ffo_por_accion(e):
    return div(e.f("ffo"), e.f("acciones_dil"))


@metrica("p_ffo", "Precio / FFO", "REIT", formato="x", panel=True,
         mejor="bajo", umbrales=(15, 25),
         ayuda="El PER de un REIT. Es la forma correcta de comparar cuanto "
               "cuesta uno contra otro: el PER contable los hace parecer a "
               "todos carisimos porque la amortizacion les come la ganancia.",
         formula="Capitalizacion / FFO.")
def p_ffo(e):
    r = div(e.market_cap, e.f("ffo"))
    return None if r is None or r < 0 else r


@metrica("ffo_yield", "FFO Yield", "REIT", formato="pct", panel=True,
         mejor="alto", umbrales=(7, 4),
         ayuda="FFO sobre capitalizacion, la inversa del Precio/FFO. Compara "
               "este numero contra el bono a 10 años: un REIT es, en el fondo, "
               "un bono con inquilinos.",
         formula="FFO / capitalizacion × 100.")
def ffo_yield(e):
    return pct(e.f("ffo"), e.market_cap)


@metrica("payout_ffo", "Payout sobre FFO", "REIT", formato="pct", panel=True,
         mejor="bajo", umbrales=(80, 100),
         ayuda="Dividendos sobre FFO. Un REIT esta obligado por ley a repartir "
               "el 90% de su ganancia impositiva, asi que payouts altos son "
               "normales; por encima de 100% del FFO, en cambio, el dividendo "
               "se esta pagando con deuda o con acciones nuevas.",
         formula="Dividendos pagados / FFO × 100.")
def payout_ffo(e):
    return pct(e.f("dividendos"), e.f("ffo"))


@metrica("deuda_sobre_inmuebles", "Deuda / Inmuebles a costo", "REIT", formato="pct",
         mejor="bajo", umbrales=(45, 65), panel=True,
         ayuda="Deuda total sobre el valor de los inmuebles antes de "
               "amortizacion. Es un loan-to-value a costo historico: "
               "conservador, porque el valor de mercado de los inmuebles suele "
               "ser mayor. Por encima de 65% el REIT depende de refinanciar en "
               "buenas condiciones, y eso no siempre esta disponible.",
         formula="Deuda total / inmuebles a costo historico × 100.")
def deuda_sobre_inmuebles(e):
    return pct(e.f("deuda_total"), e.f("inmuebles_bruto"))


@metrica("cagr_ffo_5a", "Crecimiento FFO 5a", "REIT", formato="pct",
         mejor="alto", umbrales=(5, 0),
         ayuda="Crecimiento anual del FFO. En un REIT viene de tres lados: "
               "subir alquileres, comprar mas inmuebles y desarrollar. Solo el "
               "primero crea valor por accion sin diluir.",
         formula="Tasa compuesta anual del FFO en 5 ejercicios.")
def cagr_ffo_5a(e):
    serie = e.serie("ffo")
    ventana = sorted(e.ventana(6) & set(serie))
    if len(ventana) < 4:
        return None
    return cagr(serie[ventana[0]], serie[ventana[-1]], ventana[-1] - ventana[0])
