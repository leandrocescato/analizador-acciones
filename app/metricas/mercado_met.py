"""Metricas de mercado: precio, rango, castigo acumulado, liquidez, tamaño."""

from __future__ import annotations

from .base import div, metrica, pct


@metrica("precio", "Cotizacion", "Mercado", formato="precio", panel=True,
         ayuda="Ultimo cierre. Por si solo no dice nada sobre si algo esta "
               "caro o barato: una accion de 5 dolares puede estar carisima y "
               "una de 800 puede ser una ganga. Sirve como referencia y para "
               "calcular el resto.",
         formula="Ultimo cierre segun Yahoo Finance, con Stooq de respaldo.")
def precio(e):
    return e.mercado.get("precio")


@metrica("var_pct", "Var % dia", "Mercado", formato="pct", panel=True,
         ayuda="Movimiento del dia contra el cierre anterior. Es ruido para "
               "quien compra para tener años: sirve para ubicarse, no para "
               "decidir.",
         formula="(Precio de hoy / cierre anterior − 1) × 100.")
def var_pct(e):
    return e.mercado.get("var_pct")


@metrica("max52", "Max 52s", "Mercado", formato="precio",
         ayuda="El techo del ultimo año. Junto con el minimo define el rango "
               "en el que el mercado viene tasando a la empresa; la distancia "
               "hasta aca es el castigo que todavia no revirtio.",
         formula="Maximo de los cierres de las ultimas 52 semanas.")
def max52(e):
    return e.mercado.get("max52")


@metrica("min52", "Min 52s", "Mercado", formato="precio",
         ayuda="El piso del ultimo año. Cotizar cerca del minimo no es en si "
               "una oportunidad: hay que entender por que llego ahi.",
         formula="Minimo de los cierres de las ultimas 52 semanas.")
def min52(e):
    return e.mercado.get("min52")


@metrica("dist_max52", "% desde max 52s", "Mercado", formato="pct", panel=True,
         mejor="bajo", umbrales=(-40, -10),
         ayuda="Cuanto cayo desde el maximo del año. Es tu punto de entrada "
               "contrarian: mientras mas negativo, mas castigada esta.",
         formula="(Precio / maximo de 52 semanas − 1) × 100. Siempre "
                 "negativo o cero.")
def dist_max52(e):
    p, mx = e.mercado.get("precio"), e.mercado.get("max52")
    return None if not (p and mx) else (p / mx - 1) * 100


@metrica("pos_rango52", "Posicion rango 52s", "Mercado", formato="pct",
         ayuda="Donde esta el precio dentro del rango del año: 0% pegado al "
               "minimo, 100% pegado al maximo. Debajo de 20% la accion esta "
               "en la parte castigada de su propio rango, que es donde "
               "conviene empezar a buscar.",
         formula="(Precio − minimo 52s) / (maximo 52s − minimo 52s) × 100.")
def pos_rango52(e):
    p, mx, mn = e.mercado.get("precio"), e.mercado.get("max52"), e.mercado.get("min52")
    if not (p and mx and mn) or mx <= mn:
        return None
    return (p - mn) / (mx - mn) * 100


@metrica("drawdown_max", "Caida desde max historico", "Mercado", formato="pct", panel=True,
         mejor="bajo", umbrales=(-50, -15),
         ayuda="Distancia al maximo historico de los ultimos 15 años. "
               "Una empresa a -60% es candidata; el trabajo es decidir si esta "
               "barata o rota.",
         formula="(Precio / maximo historico de cierre − 1) × 100.")
def drawdown_max(e):
    return e.retornos.get("drawdown_max")


@metrica("ret_1a", "Retorno 1 año", "Mercado", formato="pct",
         formula="(Precio de hoy / precio de hace 1 año − 1) × 100. Sin "
                 "dividendos.",
         ayuda="Cuanto rindio la accion en el ultimo año, solo por precio, "
               "sin contar dividendos. Un retorno muy negativo es el punto de "
               "partida de una tesis contrarian, no su conclusion.")
def ret_1a(e):
    return e.retornos.get("ret_1a")


@metrica("ret_3a", "Retorno 3 años", "Mercado", formato="pct",
         formula="Retorno acumulado a 3 años, sin dividendos.",
         ayuda="Retorno acumulado de 3 años, sin dividendos. Suaviza el ruido "
               "de un año suelto y suele coincidir mejor con lo que le paso "
               "al negocio.")
def ret_3a(e):
    return e.retornos.get("ret_3a")


@metrica("ret_5a", "Retorno 5 años", "Mercado", formato="pct",
         formula="Retorno acumulado a 5 años, sin dividendos.",
         ayuda="Retorno acumulado de 5 años, sin dividendos. En este plazo el "
               "precio ya sigue a los fundamentos: si el negocio mejoro y la "
               "accion no, ahi hay algo para mirar.")
def ret_5a(e):
    return e.retornos.get("ret_5a")


@metrica("beta", "Beta", "Mercado", formato="num", panel=True,
         ayuda="Cuanto se mueve la accion cuando se mueve el mercado. Ojo con "
               "leerlo como riesgo: mide volatilidad, no probabilidad de "
               "perder el capital. Una accion que ya cayo 60% tiene beta alta "
               "y puede ser MENOS riesgosa que antes de caer.",
         formula="Dato de Yahoo: regresion del retorno de la accion "
                 "contra el S&P 500 a 5 años.")
def beta(e):
    return e.mercado.get("beta")


@metrica("market_cap", "Market Cap", "Mercado", formato="usd", panel=True,
         ayuda="Lo que cuesta comprar todo el patrimonio a precio de mercado. "
               "Define en que liga juga la empresa: por debajo de 2.000 "
               "millones hay menos analistas mirando y mas probabilidad de "
               "que el precio se despegue del valor.",
         formula="Precio × acciones en circulacion.")
def market_cap(e):
    return e.mercado.get("market_cap")


@metrica("ev", "Enterprise Value", "Mercado", formato="usd", panel=True,
         ayuda="Capitalizacion + deuda neta + minoritarios. Lo que costaria "
               "comprar la empresa entera y quedarse con sus deudas.",
         formula="Capitalizacion + deuda neta + minoritarios + "
                 "preferidas.")
def ev(e):
    return e.ev


@metrica("volumen_usd", "Volumen diario USD", "Mercado", formato="usd", panel=True,
         mejor="alto", umbrales=(2e7, 2e6),
         ayuda="Volumen promedio en dolares. Por debajo de 5 M diarios, entrar "
               "o salir de una posicion mueve el precio en tu contra.",
         formula="Volumen promedio de acciones × precio.")
def volumen_usd(e):
    return e.mercado.get("volumen_usd")


@metrica("eps", "EPS / BPA", "Mercado", formato="num", panel=True,
         ayuda="Ganancia por accion diluida del ultimo ejercicio. Es el "
               "denominador del PER. Comparalo con el de años anteriores, no "
               "con el de otra empresa: depende de cuantas acciones haya.",
         formula="Ganancia por accion diluida del ultimo ejercicio, segun "
                 "EDGAR.")
def eps(e):
    reportado = e.f("eps_diluido")
    if reportado is not None:
        return reportado
    # Respaldo para empresas de doble clase: el conteo de acciones de Yahoo
    # incluye todas las clases, que es justo lo que XBRL no consolida.
    return (div(e.f("ganancia_neta"), e.f("acciones_dil"))
            or div(e.f("ganancia_neta"), e.mercado.get("acciones")))

