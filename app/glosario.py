"""
Glosario de los estados contables: nombre en ingles, traduccion y que mide.

POR QUE EN INGLES
-----------------
Los estados salen de la SEC, y en la SEC estan en ingles. Si la app te los
muestra traducidos, cada vez que abris el 10-K original tenes que hacer la
traduccion inversa de cabeza, y ahi es donde se cuelan los errores: "Gross
Profit" no siempre es la ganancia bruta que uno espera, y "Cost of Revenue"
no es lo mismo que "Cost of Goods Sold" en todas las empresas. Se muestra el
termino que vas a leer en la presentacion, y la traduccion viaja en el tooltip.

FORMATO DE CADA ENTRADA
-----------------------
    clave: (ingles, castellano, que mide o como se calcula)

El ingles es el rotulo tipico de un 10-K, no la etiqueta XBRL (esa vive en
`conceptos.py` y puede ser cualquiera de varias). El tercer campo es lo que
sale en el tooltip debajo de la traduccion: dice para que sirve la linea o
como se arma, no la repite con otras palabras.
"""

from __future__ import annotations

# ------------------------------------------------------------------ resultados

RESULTADOS: dict[str, tuple[str, str, str]] = {
    "ingresos": (
        "Total Revenue", "Ingresos totales",
        "Lo facturado por vender bienes y servicios en el ejercicio, neto de "
        "devoluciones y descuentos. Es la primera linea: todo lo demas se resta "
        "de aca.",
    ),
    "costo_ventas": (
        "Cost of Revenue", "Costo de ventas",
        "Lo que costo producir o comprar lo que se vendio: materiales, mano de "
        "obra directa, fletes. No incluye la estructura.",
    ),
    "ganancia_bruta": (
        "Gross Profit", "Ganancia bruta reportada",
        "Ingresos menos costo de ventas. Mide poder de fijacion de precios: "
        "cuanto queda antes de pagar la estructura.",
    ),
    "gastos_sga": (
        "Selling, General & Administrative (SG&A)",
        "Gastos de administracion y comercializacion",
        "Sueldos de estructura, marketing, alquileres, legales. Es el costo de "
        "operar la empresa, no el de producir.",
    ),
    "gastos_id": (
        "Research & Development (R&D)", "Investigacion y desarrollo",
        "Lo gastado en desarrollar productos nuevos. En EE.UU. va entero al "
        "resultado del ejercicio, no se activa: deprime la ganancia contable de "
        "una empresa que invierte.",
    ),
    "ebit": (
        "Operating Income (EBIT)", "Resultado operativo",
        "Ganancia bruta menos SG&A menos I+D. Lo que gana el negocio antes de "
        "intereses e impuestos, o sea antes de como esta financiado.",
    ),
    "intereses": (
        "Interest Expense", "Gasto por intereses",
        "Lo que cuesta la deuda en el ejercicio. Contra el EBIT da la cobertura "
        "de intereses: cuantas veces la ganancia operativa paga el costo "
        "financiero.",
    ),
    "antes_impuesto": (
        "Pre-Tax Income (EBT)", "Resultado antes de impuestos",
        "EBIT menos intereses, mas o menos los resultados no operativos.",
    ),
    "impuesto": (
        "Income Tax Expense", "Impuesto a las ganancias",
        "El cargo devengado del ejercicio, que no es lo efectivamente pagado. "
        "Dividido por el resultado antes de impuestos da la tasa efectiva.",
    ),
    "ganancia_neta": (
        "Net Income", "Ganancia neta",
        "La ultima linea, despues de todo. Es la que alimenta el EPS y el PER, "
        "y la mas facil de maquillar: leela siempre contra el flujo operativo.",
    ),
    "ebitda": (
        "EBITDA", "Resultado antes de intereses, impuestos y amortizaciones",
        "EBIT mas depreciacion y amortizacion. Aproxima la caja operativa, pero "
        "ignora que los activos se gastan y hay que reponerlos.",
    ),
    "eps_diluido": (
        "Diluted EPS", "Ganancia por accion diluida",
        "Ganancia neta sobre acciones diluidas promedio. Diluida = contando "
        "opciones y convertibles como si ya se hubieran ejercido. Es la version "
        "conservadora y la que corresponde usar.",
    ),
    "acciones_dil": (
        "Diluted Weighted-Average Shares", "Acciones diluidas promedio",
        "Promedio ponderado del ejercicio, con el efecto de opciones y "
        "convertibles. Si sube año a año, te estan diluyendo.",
    ),
}

# ------------------------------------------------------------------ balance

BALANCE: dict[str, tuple[str, str, str]] = {
    "efectivo": (
        "Cash & Cash Equivalents", "Efectivo y equivalentes",
        "Caja y colocaciones a menos de 90 dias.",
    ),
    "inversiones_cp": (
        "Short-Term Investments", "Inversiones de corto plazo",
        "Titulos negociables a mas de 90 dias y menos de un año. Es caja a un "
        "paso de distancia.",
    ),
    "por_cobrar": (
        "Accounts Receivable", "Cuentas por cobrar",
        "Lo facturado y todavia no cobrado. Si crece bastante mas rapido que "
        "las ventas, la empresa le esta vendiendo a quien no le paga.",
    ),
    "inventario": (
        "Inventory", "Inventario",
        "Mercaderia y materias primas sin vender. Creciendo mas rapido que las "
        "ventas suele anticipar rebajas de precio.",
    ),
    "activo_corriente": (
        "Total Current Assets", "Activo corriente",
        "Lo que se convierte en caja dentro de los proximos 12 meses.",
    ),
    "ppe_neto": (
        "Property, Plant & Equipment, net (PP&E)",
        "Propiedad, planta y equipo neto",
        "Activos fijos a costo menos la depreciacion acumulada.",
    ),
    "goodwill": (
        "Goodwill", "Llave de negocio",
        "Lo pagado por encima del valor de los activos al comprar otra empresa. "
        "No genera caja por si mismo y se borra de golpe cuando la adquisicion "
        "sale mal.",
    ),
    "intangibles": (
        "Intangible Assets, excl. Goodwill", "Intangibles sin llave de negocio",
        "Patentes, marcas, cartera de clientes. Se amortizan contra resultados.",
    ),
    "activo_total": (
        "Total Assets", "Activo total",
        "Todo lo que la empresa controla. Es el denominador del ROA y del "
        "apalancamiento.",
    ),
    "por_pagar": (
        "Accounts Payable", "Cuentas por pagar",
        "Lo comprado y todavia no pagado a proveedores. Es financiamiento "
        "gratis: estirarlo mejora la caja.",
    ),
    "pasivo_corriente": (
        "Total Current Liabilities", "Pasivo corriente",
        "Lo que hay que pagar dentro de los proximos 12 meses.",
    ),
    "deuda_cp": (
        "Short-Term Debt", "Deuda de corto plazo",
        "Deuda financiera que vence dentro del año, mas la porcion corriente de "
        "la de largo plazo. Es la que puede voltear a una empresa solvente pero "
        "sin liquidez.",
    ),
    "deuda_lp": (
        "Long-Term Debt", "Deuda de largo plazo",
        "Deuda financiera que vence a mas de un año.",
    ),
    "leases_total": (
        "Operating Lease Liabilities", "Pasivo por leases operativos",
        "Alquileres ya comprometidos a futuro. Desde 2019 van al balance: "
        "obligan igual que la deuda, y por eso aca se suman a ella.",
    ),
    "pasivo_total": (
        "Total Liabilities", "Pasivo total",
        "Todo lo que la empresa debe.",
    ),
    "resultados_acumulados": (
        "Retained Earnings", "Resultados acumulados",
        "La suma historica de ganancias no distribuidas. Negativo quiere decir "
        "que la empresa perdio mas de lo que gano en toda su vida.",
    ),
    "patrimonio": (
        "Total Shareholders' Equity", "Patrimonio neto",
        "Activo menos pasivo. Lo que quedaria para los accionistas si se "
        "liquidara todo a valor libros.",
    ),
    "patrimonio_tangible": (
        "Tangible Book Value", "Patrimonio tangible",
        "Patrimonio menos llave de negocio menos intangibles. Lo que hay de "
        "verdad detras de la accion.",
    ),
    "deuda_total": (
        "Total Debt, incl. Leases", "Deuda total con leases",
        "Deuda de corto plazo mas la de largo plazo mas los leases operativos.",
    ),
    "caja_total": (
        "Cash & Investments", "Caja e inversiones",
        "Efectivo mas inversiones de corto plazo.",
    ),
    "deuda_neta": (
        "Net Debt", "Deuda neta",
        "Deuda total menos caja e inversiones. Negativa significa caja neta: "
        "podria cancelar todo lo que debe y le sobraria.",
    ),
    "capital_trabajo": (
        "Working Capital", "Capital de trabajo",
        "Activo corriente menos pasivo corriente. Lo que la operacion necesita "
        "tener financiado para funcionar.",
    ),
}

# ------------------------------------------------------------------ flujo

FLUJO: dict[str, tuple[str, str, str]] = {
    "flujo_operativo": (
        "Cash Flow from Operations (CFO)", "Flujo de caja operativo",
        "La caja que genero el negocio. Es la linea mas dificil de maquillar: "
        "comparala siempre contra la ganancia neta.",
    ),
    "capex": (
        "Capital Expenditures (CapEx)", "Inversion en bienes de capital",
        "Plata puesta en activos fijos. Una parte es mantenimiento y otra "
        "crecimiento; el estado no las separa.",
    ),
    "fcf": (
        "Free Cash Flow (FCF)", "Caja libre",
        "Flujo operativo menos CapEx. La plata que de verdad queda disponible "
        "para deuda, dividendos y recompras.",
    ),
    "sbc": (
        "Stock-Based Compensation (SBC)", "Compensacion en acciones",
        "Sueldos pagados con acciones. No sale caja, por eso se suma al flujo "
        "operativo, pero te diluye igual: es un costo real para el accionista.",
    ),
    "fcf_post_sbc": (
        "Free Cash Flow after SBC", "Caja libre neta de compensacion en acciones",
        "FCF menos la compensacion en acciones. La version honesta del FCF en "
        "empresas que pagan buena parte del sueldo con papel.",
    ),
    "adquisiciones": (
        "Acquisitions, net of cash acquired", "Efectivo usado en adquisiciones",
        "Plata gastada en comprar otras empresas.",
    ),
    "dividendos": (
        "Dividends Paid", "Dividendos pagados",
        "Caja distribuida a los accionistas.",
    ),
    "recompras": (
        "Share Repurchases", "Recompra de acciones propias",
        "Caja usada en comprar acciones propias. Crea valor solo si se compra "
        "barato; si no, es un traspaso del accionista que se queda al que sale.",
    ),
    "emision_acciones": (
        "Proceeds from Issuance of Stock",
        "Efectivo recibido por emision de acciones",
        "Plata que entro por emitir acciones nuevas. Contra las recompras dice "
        "si la empresa recompra neto o solo tapa la dilucion.",
    ),
    "dya": (
        "Depreciation & Amortization (D&A)", "Depreciacion y amortizacion",
        "El desgaste contable de los activos. No sale caja, por eso se suma al "
        "flujo operativo. Contra el CapEx dice si la empresa invierte mas o "
        "menos de lo que se le gasta.",
    ),
}

TODOS: dict[str, tuple[str, str, str]] = {**RESULTADOS, **BALANCE, **FLUJO}


def ingles(clave: str) -> str | None:
    """Rotulo en ingles, o None si el concepto no esta en el glosario."""
    entrada = TODOS.get(clave)
    return entrada[0] if entrada else None


def castellano(clave: str) -> str | None:
    entrada = TODOS.get(clave)
    return entrada[1] if entrada else None


def tooltip(clave: str) -> str:
    """Traduccion y significado, en el orden en que se leen."""
    entrada = TODOS.get(clave)
    if not entrada:
        return ""
    _, es, que_mide = entrada
    return f"{es} — {que_mide}"
