"""
Perfil contable de la empresa, y que indicadores dejan de tener sentido en cada uno.

POR QUE EXISTE ESTE MODULO
--------------------------
Un banco no es una empresa industrial con otro producto: tiene otra estructura
economica. Sus depositos son materia prima, no financiamiento; su deuda es
insumo, no carga; y no tiene margen bruto ni inventario porque esos conceptos no
existen en su contabilidad.

El problema no es que falten datos. Es que el catalogo los calcula igual y
devuelve numeros plausibles y falsos. Medido sobre datos reales:

    JPMorgan          Accenture
    EV/EBIT   6,8x    10,4x      <- JPM parece 35% mas barata
    ROIC 5a   32,5%   33,8%      <- y con la misma rentabilidad
    DN/EBITDA 0,9x    -0,3x      <- con 400 mil millones de deuda
    Altman Z  0       4          <- modelo calibrado para industriales
    FCF Yield -15,3%  10,0%      <- el flujo sigue la cartera de prestamos

Ninguno de esos cinco numeros significa lo que aparenta, y los cinco se ven
normales. Cambiar de fuente de datos no lo arregla: Yahoo Finance deja los
mismos campos vacios para JPM, porque tampoco existen ahi.

La respuesta correcta es no publicarlos. Un guion es informacion honesta; un
6,8x es una mentira con formato de dato.

COMO SE DETECTA
---------------
Por codigo SIC de EDGAR, que es la clasificacion oficial del emisor. Si por
alguna razon no esta disponible, se cae a la evidencia de las propias etiquetas
XBRL: una empresa que reporta depositos de clientes y prestamos es un banco,
tenga el SIC que tenga.
"""

from __future__ import annotations

# ------------------------------------------------------------------ perfiles

BANCO = "banco"
SEGUROS = "seguros"
REIT = "reit"
GENERAL = "general"

NOMBRES = {
    BANCO: "Banco",
    SEGUROS: "Seguros",
    REIT: "REIT",
    GENERAL: "General",
}

# Como leer una ficha de cada tipo, para el aviso del Detalle.
EXPLICACION = {
    BANCO: (
        "Los depositos y la deuda son la materia prima de un banco, no su "
        "financiamiento. Por eso el capital invertido, el enterprise value y "
        "las metricas de caja libre no significan nada aca, y quedan vacias. "
        "En su lugar tenes el grupo **Banca**: margen de intereses, ratio de "
        "eficiencia, coste del riesgo, prestamos sobre depositos y "
        "apalancamiento."
    ),
    SEGUROS: (
        "Una aseguradora invierte el float —la plata de las primas todavia no "
        "reclamada— asi que su balance no se lee como el de una industrial. "
        "Las metricas basadas en capital invertido y enterprise value quedan "
        "vacias. En su lugar tenes el grupo **Seguros**, con el ratio "
        "combinado a la cabeza: por debajo de 100 gana plata asegurando."
    ),
    REIT: (
        "La amortizacion contable de un REIT no refleja el desgaste real del "
        "inmueble, asi que la ganancia neta, el PER y el valor libro "
        "subestiman lo que el negocio genera de verdad. En su lugar tenes el "
        "grupo **REIT**, construido sobre el FFO, que es el estandar del "
        "sector."
    ),
    GENERAL: "",
}

# ------------------------------------------------------------------ deteccion

# Rangos SIC. Los limites son inclusivos.
#   6020-6199  bancos, cajas y credito no bancario (JPM 6021, NU 6199)
#   6200-6299  brokers y bolsas: tienen EBIT real, van como general
#   6300-6499  seguros (PGR 6331)
#   6726       fondos cerrados y BDCs
#   6798       REITs (O y SPG 6798)
_RANGOS_SIC = [
    (6020, 6199, BANCO),
    (6300, 6499, SEGUROS),
    (6726, 6726, BANCO),
    (6798, 6798, REIT),
]

# Etiquetas XBRL que delatan el tipo de negocio, en us-gaap y en ifrs-full.
_EVIDENCIA = [
    (BANCO, {
        "Deposits", "DepositsFromCustomers", "InterestAndDividendIncomeOperating",
        "LoansAndLeasesReceivableNetReportedAmount", "LoansAndAdvancesToCustomers",
        "InterestIncomeExpenseNet", "InterestRevenueExpense",
    }),
    (SEGUROS, {
        "PremiumsEarnedNet", "PolicyholderBenefitsAndClaimsIncurredNet",
        "LiabilityForFuturePolicyBenefits", "InsuranceContractsThatAreLiabilities",
    }),
    (REIT, {
        "RealEstateInvestmentPropertyNet", "RealEstateInvestmentPropertyAtCost",
        "InvestmentProperty",
    }),
]


def por_sic(sic) -> str | None:
    """Perfil segun el codigo SIC del emisor. None si no se puede decidir."""
    try:
        codigo = int(str(sic).strip())
    except (TypeError, ValueError):
        return None
    for desde, hasta, perfil in _RANGOS_SIC:
        if desde <= codigo <= hasta:
            return perfil
    return GENERAL


def por_evidencia(etiquetas) -> str:
    """Perfil deducido de las etiquetas XBRL que la empresa efectivamente usa."""
    presentes = set(etiquetas or ())
    for perfil, marcadores in _EVIDENCIA:
        if presentes & marcadores:
            return perfil
    return GENERAL


def detectar(sic=None, etiquetas=None) -> str:
    """SIC como fuente principal; las etiquetas solo si no hay SIC.

    La evidencia NO puede pisar al SIC, ni siquiera cuando este dice `general`:
    un SIC presente es un veredicto, no una ausencia de dato. Visa reporta
    etiquetas de intereses y depositos por su negocio de pagos y quedaba
    clasificada como banco, perdiendo ROIC y EV/EBIT que en su caso son
    perfectamente validos. Su SIC 7389 (servicios) siempre lo supo.
    """
    perfil = por_sic(sic)
    if perfil is not None:
        return perfil
    return por_evidencia(etiquetas)


# ------------------------------------------------------------------ supresion

# Metricas que NO se publican en cada perfil, con el motivo agrupado.
#
# Esta tabla es deliberadamente central en vez de un campo por metrica: es una
# politica transversal, y conviene poder auditarla y ajustarla de un vistazo.

_CAPITAL_INVERTIDO = {
    # El capital invertido de una financiera no mide nada: los depositos y la
    # deuda son insumo del negocio, no capital puesto a trabajar.
    "roic", "roic_prom_5a", "roic_ex_gw", "roic_incremental", "roce",
    "spread_roic_wacc",
}

_ENTERPRISE_VALUE = {
    # El EV suma la deuda neta al precio. En una financiera eso es sumarle la
    # materia prima, y da multiplos absurdamente bajos.
    "ev", "ev_ebit", "ev_ebitda", "ev_fcf", "ev_ventas",
    "earnings_yield", "epv", "precio_vs_ncav", "deuda_sobre_ev",
}

_CAJA_LIBRE = {
    # El flujo operativo de un banco se mueve con la cartera de prestamos, no
    # con la caja que genera el negocio: un FCF Yield de -15% no es una alarma.
    "fcf_yield", "fcf_yield_post_sbc", "fcf_margen", "fcf_conversion",
    "fcf_conversion_prom5", "accruals_sloan", "cagr_fcf_5a",
    "anios_fcf_negativo", "sbc_fcf", "payout_fcf", "recompras_sobre_fcf",
    "anios_deuda_fcf", "payout_real", "regla_40", "meses_de_caja",
}

_CICLO_OPERATIVO = {
    # Sin inventario ni ciclo comercial, estas metricas no tienen referente.
    "dso", "dio", "dpo", "ciclo_caja", "capex_ventas", "capex_dya",
    "rotacion_activos",
}

_MARGENES_OPERATIVOS = {
    # Un banco no publica resultado operativo: el EBIT reconstruido le devuelve
    # el costo de fondeo, que es su principal costo real.
    "margen_bruto", "margen_operativo", "margen_op_prom10", "margen_op_vs_prom",
    "estabilidad_margen", "cagr_ebit_5a",
}

_APALANCAMIENTO_INDUSTRIAL = {
    # Un banco apalancado 10 a 1 es normal; una industrial asi esta quebrada.
    # Estos ratios comparan contra la vara equivocada.
    "deuda_neta_ebitda", "cobertura_intereses", "deuda_patrimonio",
    "liquidez_corriente", "liquidez_acida", "caja_neta", "reinversion",
}

_MODELOS_INDUSTRIALES = {
    # Altman se calibro sobre industriales. Piotroski y Beneish incluyen margen
    # bruto, liquidez corriente y rotacion: en una financiera esos chequeos no
    # se pueden evaluar y suman cero en silencio, lo que subestima el score sin
    # avisar. Un F-Score de 5 que en realidad es de 5 sobre 6 no es comparable.
    "altman_z", "piotroski", "beneish_m",
}

SUPRIMIDAS: dict[str, frozenset[str]] = {
    BANCO: frozenset(
        _CAPITAL_INVERTIDO | _ENTERPRISE_VALUE | _CAJA_LIBRE | _CICLO_OPERATIVO
        | _MARGENES_OPERATIVOS | _APALANCAMIENTO_INDUSTRIAL | _MODELOS_INDUSTRIALES
    ),
    SEGUROS: frozenset(
        _CAPITAL_INVERTIDO | _ENTERPRISE_VALUE | _CICLO_OPERATIVO
        | _MODELOS_INDUSTRIALES
        # La regla del 40 se invento para software: suma crecimiento y margen
        # de caja, y en una aseguradora o un REIT el margen de caja no mide lo
        # mismo. Realty Income daba 87, que parece un puntaje extraordinario.
        | {"margen_bruto", "accruals_sloan", "deuda_neta_ebitda",
           "liquidez_corriente", "liquidez_acida", "anios_deuda_fcf",
           "regla_40"}
    ),
    REIT: frozenset(
        _CAPITAL_INVERTIDO | _MODELOS_INDUSTRIALES
        # La amortizacion contable deprime la ganancia neta de un REIT muy por
        # debajo de su caja real: el PER y todo lo derivado de EBIT engañan.
        | {"per", "per_normalizado", "per_forward", "peg", "earnings_yield",
           "epv", "ev_ebit",
           "precio_vs_ncav", "margen_bruto", "rotacion_activos",
           "dio", "ciclo_caja", "capex_dya",
           "fcf_conversion", "fcf_conversion_prom5", "accruals_sloan",
           "liquidez_corriente", "liquidez_acida", "regla_40"}
        # Y el mismo defecto vacia el patrimonio contable: decadas de
        # amortizacion sobre inmuebles que en realidad se revalorizaron. Simon
        # Property daba ROE 103% y Realty Income 2,7%; ninguno de los dos mide
        # calidad, solo cuanto hace que compraron los edificios.
        | {"roe", "roa", "p_vl", "p_vl_tangible"}
    ),
    GENERAL: frozenset(),
}


# ------------------------------------------------------------------ exclusivas

# Metricas que SOLO existen en un tipo de negocio. Es la contracara de la tabla
# de arriba: aquella tapa lo que no aplica, esta habilita lo propio del sector.
#
# La diferencia importa para la interfaz. Un indicador tapado se muestra como
# "no aplica", porque saber que el ROIC de un banco no significa nada es
# informacion util. Uno ajeno, en cambio, se oculta entero: a nadie le sirve
# leer "Ratio combinado — no aplica" en la ficha de una empresa de software.

EXCLUSIVAS: dict[str, str] = {
    clave: BANCO for clave in (
        "margen_intereses", "ratio_eficiencia", "coste_riesgo",
        "cobertura_reservas", "prestamos_depositos", "apalancamiento",
        "peso_comisiones", "cagr_depositos_5a",
    )
}
EXCLUSIVAS.update({
    clave: SEGUROS for clave in (
        "ratio_combinado", "ratio_siniestralidad", "ratio_gastos",
        "float_sobre_cap", "rendimiento_float", "cagr_primas_5a",
    )
})
EXCLUSIVAS.update({
    clave: REIT for clave in (
        "ffo", "ffo_por_accion", "p_ffo", "ffo_yield", "payout_ffo",
        "deuda_sobre_inmuebles", "cagr_ffo_5a",
    )
})


def suprimidas(perfil: str) -> frozenset[str]:
    """Metricas del catalogo general que no significan nada en este perfil.

    Se muestran, pero vacias y marcadas como "no aplica".
    """
    return SUPRIMIDAS.get(perfil or GENERAL, frozenset())


def ajenas(perfil: str) -> frozenset[str]:
    """Metricas de OTROS sectores. No se muestran en absoluto."""
    perfil = perfil or GENERAL
    return frozenset(c for c, p in EXCLUSIVAS.items() if p != perfil)


def no_aplican(perfil: str) -> frozenset[str]:
    """Todo lo que no hay que calcular para este perfil."""
    return suprimidas(perfil) | ajenas(perfil)


def aplica(clave: str, perfil: str) -> bool:
    """False si esa metrica no tiene sentido economico para ese tipo de empresa."""
    return clave not in no_aplican(perfil)


def metricas_del_sector(perfil: str) -> list[str]:
    """Las metricas propias de este perfil, en el orden en que se declararon."""
    return [c for c, p in EXCLUSIVAS.items() if p == (perfil or GENERAL)]
