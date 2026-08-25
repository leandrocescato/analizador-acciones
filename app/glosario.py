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


# ------------------------------------------------------------------ indicadores
#
# El nombre en ingles de cada indicador del catalogo. Aca va SOLO el rotulo: la
# version en castellano ya vive en `metricas/base.REGISTRO[clave].nombre`, y
# duplicarla seria pedir que un dia digan cosas distintas. El tooltip toma el
# ingles de aca y el castellano de alla.
#
# Se usa la terminologia de un informe en ingles, no una traduccion literal:
# "Cobertura de intereses" es Interest Coverage, no "Interest Cover"; el ratio
# de siniestralidad de una aseguradora es el Loss Ratio.

METRICAS: dict[str, str] = {
    # --- Mercado
    "precio": "Price",
    "var_pct": "Daily Change %",
    "max52": "52-Week High",
    "min52": "52-Week Low",
    "dist_max52": "% Below 52-Week High",
    "pos_rango52": "52-Week Range Position",
    "drawdown_max": "Drawdown from All-Time High",
    "ret_1a": "1-Year Return",
    "ret_3a": "3-Year Return",
    "ret_5a": "5-Year Return",
    "beta": "Beta",
    "market_cap": "Market Cap",
    "ev": "Enterprise Value",
    "volumen_usd": "Daily Dollar Volume",
    "eps": "EPS",
    # --- Valuacion
    "per": "P/E",
    "per_normalizado": "Normalized P/E (10Y)",
    "ev_ebit": "EV / EBIT",
    "ev_ebitda": "EV / EBITDA",
    "ev_fcf": "EV / FCF",
    "ev_ventas": "EV / Sales",
    "fcf_yield": "FCF Yield",
    "fcf_yield_post_sbc": "FCF Yield after SBC",
    "earnings_yield": "Earnings Yield (Greenblatt)",
    "p_vl": "Price / Book",
    "p_vl_tangible": "Price / Tangible Book",
    "div_yield": "Dividend Yield",
    "shareholder_yield": "Shareholder Yield",
    "precio_vs_ncav": "Price / NCAV",
    "epv": "EPV / Market Cap",
    "per_forward": "Forward P/E (est.)",
    # --- Rentabilidad
    "roic": "ROIC",
    "roic_prom_5a": "5-Year Average ROIC",
    "roic_ex_gw": "ROIC ex-Goodwill",
    "roic_incremental": "Incremental ROIC (5Y)",
    "roce": "ROCE",
    "roe": "ROE",
    "roa": "ROA",
    "margen_bruto": "Gross Margin",
    "margen_operativo": "Operating Margin",
    "margen_neto": "Net Margin",
    "margen_op_prom10": "10-Year Average Operating Margin",
    "margen_op_vs_prom": "Operating Margin vs 10Y Average",
    "estabilidad_margen": "Operating Margin Volatility (10Y)",
    "rotacion_activos": "Asset Turnover",
    # --- Caja
    "fcf_margen": "FCF Margin",
    "fcf_conversion": "FCF / Net Income",
    "fcf_conversion_prom5": "5-Year Average FCF Conversion",
    "accruals_sloan": "Accruals Ratio (Sloan)",
    "capex_ventas": "CapEx / Sales",
    "capex_dya": "CapEx / D&A",
    "dso": "Days Sales Outstanding (DSO)",
    "dio": "Days Inventory Outstanding (DIO)",
    "dpo": "Days Payable Outstanding (DPO)",
    "ciclo_caja": "Cash Conversion Cycle",
    "sbc_ingresos": "SBC / Revenue",
    "sbc_fcf": "SBC / FCF",
    # --- Solidez
    "caja_neta": "Net Cash Position",
    "deuda_neta_ebitda": "Net Debt / EBITDA",
    "cobertura_intereses": "Interest Coverage",
    "deuda_patrimonio": "Debt / Equity",
    "liquidez_corriente": "Current Ratio",
    "liquidez_acida": "Quick Ratio",
    "anios_deuda_fcf": "Years of FCF to Repay Debt",
    "altman_z": "Altman Z-Score",
    "deuda_sobre_ev": "Total Debt / EV",
    "meses_de_caja": "Months of Cash",
    # --- Capital
    "wacc": "Estimated WACC",
    "spread_roic_wacc": "ROIC − WACC Spread",
    "var_acciones_5a": "5-Year Change in Share Count",
    "var_acciones_10a": "10-Year Change in Share Count",
    "payout": "Dividend Payout Ratio",
    "payout_fcf": "Dividend Payout / FCF",
    "recompras_sobre_fcf": "Buybacks / FCF",
    "reinversion": "Reinvestment Rate",
    "caja_devuelta_5a": "Cash Returned to Shareholders (5Y)",
    "goodwill_sobre_activo": "Goodwill / Total Assets",
    "payout_real": "Total Payout (Dividends + Buybacks)",
    # --- Crecimiento
    "cagr_ingresos_5a": "Revenue CAGR (5Y)",
    "cagr_ingresos_10a": "Revenue CAGR (10Y)",
    "cagr_ebit_5a": "EBIT CAGR (5Y)",
    "cagr_fcf_5a": "FCF CAGR (5Y)",
    "cagr_eps_5a": "EPS CAGR (5Y)",
    "cagr_patrimonio_5a": "Book Value CAGR (5Y)",
    "aceleracion_ingresos": "Revenue Growth Acceleration",
    "regla_40": "Rule of 40",
    "peg": "PEG",
    "crec_ingresos_ntm": "Revenue Growth NTM (est.)",
    "crec_eps_ntm": "EPS Growth NTM (est.)",
    # --- Señales
    "piotroski": "Piotroski F-Score",
    "beneish_m": "Beneish M-Score",
    "anios_con_perdida": "Years with a Loss (15Y)",
    "anios_fcf_negativo": "Years with Negative FCF (15Y)",
    "cobertura_datos": "Data Coverage",
    # --- Banca
    "margen_intereses": "Net Interest Margin (NIM)",
    "ratio_eficiencia": "Efficiency Ratio",
    "coste_riesgo": "Cost of Risk",
    "cobertura_reservas": "Allowance / Gross Loans",
    "prestamos_depositos": "Loans / Deposits",
    "apalancamiento": "Leverage (Assets / Equity)",
    "peso_comisiones": "Fee Income / Revenue",
    "cagr_depositos_5a": "Deposit CAGR (5Y)",
    # --- Seguros
    "ratio_combinado": "Combined Ratio",
    "ratio_siniestralidad": "Loss Ratio",
    "ratio_gastos": "Expense Ratio",
    "float_sobre_cap": "Float / Market Cap",
    "rendimiento_float": "Return on Float",
    "cagr_primas_5a": "Premium CAGR (5Y)",
    # --- REIT
    "ffo": "FFO",
    "ffo_por_accion": "FFO per Share",
    "p_ffo": "Price / FFO",
    "ffo_yield": "FFO Yield",
    "payout_ffo": "Payout / FFO",
    "deuda_sobre_inmuebles": "Debt / Real Estate at Cost",
    "cagr_ffo_5a": "FFO CAGR (5Y)",
}

# Los grupos tambien, porque son los titulos que quedan arriba de indicadores
# en ingles. La clave interna no cambia: esto es solo el rotulo.
GRUPOS_EN: dict[str, str] = {
    "Mercado": "Market",
    "Valuacion": "Valuation",
    "Rentabilidad": "Profitability",
    "Caja": "Cash",
    "Solidez": "Financial Strength",
    "Capital": "Capital Allocation",
    "Crecimiento": "Growth",
    "Senales": "Signals",
    "Banca": "Banking",
    "Seguros": "Insurance",
    "REIT": "REIT",
}


def metrica_en(clave: str) -> str | None:
    """Rotulo en ingles de un indicador, o None si no esta traducido."""
    return METRICAS.get(clave)


def grupo_en(grupo: str) -> str:
    """Rotulo en ingles de un grupo. Si falta, se devuelve tal cual."""
    return GRUPOS_EN.get(grupo, grupo)


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
