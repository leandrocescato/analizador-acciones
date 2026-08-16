"""
Catalogo de conceptos contables y sus etiquetas XBRL candidatas.

REGLA CRITICA DE DISEÑO
------------------------
Las empresas cambian de etiqueta XBRL a lo largo del tiempo. CoStar (CSGP), por
ejemplo, dejo de usar `CostOfRevenue` en 2017 y paso a otra. Un extractor que
elige "la primera etiqueta que tenga datos" y despues lee toda esa serie devuelve
numeros de 2013 presentados como si fueran actuales: plausibles y falsos.

Por eso la resolucion se hace AÑO POR AÑO. Para cada ejercicio se recorren las
etiquetas candidatas en orden de preferencia y se toma la primera que tenga dato
para ESE año. Ver `proveedores/edgar.py::serie_por_concepto`.

Este es el unico archivo que hay que tocar para ensenarle al sistema un concepto
contable nuevo. Todo lo demas se propaga solo.

DOS TAXONOMIAS: US-GAAP E IFRS
------------------------------
Los emisores extranjeros presentan 20-F y etiquetan en `ifrs-full`, no en
`us-gaap`. Los nombres de las etiquetas son distintos: donde una empresa de
EE.UU. dice `NetCashProvidedByUsedInOperatingActivities`, una IFRS dice
`CashFlowsFromUsedInOperatingActivities`. Sin ese vocabulario, un 20-F devuelve
una ficha vacia aunque EDGAR tenga todos los datos (le pasaba a NU: 151
etiquetas IFRS disponibles y 0 años extraidos).

Las candidatas IFRS van SIEMPRE despues de las us-gaap en cada lista. Como la
resolucion es año por año y solo rellena huecos, una empresa de EE.UU. nunca
llega a mirarlas, y una IFRS las encuentra al no tener las primeras. Unas pocas
etiquetas (`Assets`, `Liabilities`, `GrossProfit`, `Goodwill`, `InterestExpense`)
se llaman igual en las dos y sirven a ambas sin duplicarse.
"""

from __future__ import annotations

from dataclasses import dataclass, field


@dataclass(frozen=True)
class Concepto:
    """Un concepto contable y las etiquetas XBRL con las que puede aparecer."""

    clave: str
    etiquetas: tuple[str, ...]
    unidad: str = "USD"
    # 'duracion' = suma del ejercicio (ventas). 'instante' = foto de cierre (caja).
    tipo: str = "duracion"
    signo: int = 1  # -1 para invertir salidas de caja y dejarlas positivas
    descripcion: str = ""
    esencial: bool = False  # si falta, la empresa no se puede analizar


def _c(clave, etiquetas, **kw) -> Concepto:
    return Concepto(clave=clave, etiquetas=tuple(etiquetas), **kw)


# ------------------------------------------------------------------ resultados

RESULTADOS = [
    _c("ingresos", [
        "RevenueFromContractWithCustomerExcludingAssessedTax",
        "Revenues",
        "RevenueFromContractWithCustomerIncludingAssessedTax",
        "SalesRevenueNet",
        "SalesRevenueGoodsNet",
        "SalesRevenueServicesNet",
        "RevenuesNetOfInterestExpense",
        # IFRS
        "Revenue",
        "RevenueFromContractsWithCustomers",
    ], descripcion="Ingresos totales", esencial=True),

    _c("costo_ventas", [
        "CostOfRevenue",
        "CostOfGoodsAndServicesSold",
        "CostOfServices",
        "CostOfGoodsSold",
        "CostOfSales",
    ], descripcion="Costo de ventas"),

    _c("ganancia_bruta", ["GrossProfit"], descripcion="Ganancia bruta reportada"),

    _c("gastos_sga", [
        "SellingGeneralAndAdministrativeExpense",
        "GeneralAndAdministrativeExpense",
        # IFRS
        "AdministrativeExpense",
    ], descripcion="Gastos de administracion y comercializacion"),

    _c("gastos_id", [
        "ResearchAndDevelopmentExpense",
    ], descripcion="Investigacion y desarrollo"),

    _c("ebit", [
        "OperatingIncomeLoss",
        # IFRS
        "ProfitLossFromOperatingActivities",
    ], descripcion="Resultado operativo (EBIT)"),

    _c("antes_impuesto", [
        "IncomeLossFromContinuingOperationsBeforeIncomeTaxesExtraordinaryItemsNoncontrollingInterest",
        "IncomeLossFromContinuingOperationsBeforeIncomeTaxesMinorityInterestAndIncomeLossFromEquityMethodInvestments",
        "IncomeLossFromContinuingOperationsBeforeIncomeTaxesDomestic",
        # IFRS
        "ProfitLossBeforeTax",
    ], descripcion="Resultado antes de impuestos"),

    _c("impuesto", [
        "IncomeTaxExpenseBenefit",
        "CurrentIncomeTaxExpenseBenefit",
        # IFRS
        "IncomeTaxExpenseContinuingOperations",
    ], descripcion="Impuesto a las ganancias"),

    _c("intereses", [
        "InterestExpense",
        "InterestExpenseDebt",
        "InterestExpenseNonoperating",
        "InterestIncomeExpenseNet",
    ], descripcion="Gasto por intereses"),

    _c("ganancia_neta", [
        "NetIncomeLoss",
        "ProfitLoss",
        "NetIncomeLossAvailableToCommonStockholdersBasic",
        # IFRS
        "ProfitLossAttributableToOwnersOfParent",
    ], descripcion="Ganancia neta", esencial=True),

    _c("eps_diluido", [
        "EarningsPerShareDiluted",
        "IncomeLossFromContinuingOperationsPerDilutedShare",
        # IFRS
        "DilutedEarningsLossPerShare",
    ], unidad="USD/shares", descripcion="Ganancia por accion diluida"),

    _c("eps_basico", [
        "EarningsPerShareBasic",
        # IFRS
        "BasicEarningsLossPerShare",
    ], unidad="USD/shares", descripcion="Ganancia por accion basica"),
]

# ------------------------------------------------------------------ balance

BALANCE = [
    _c("activo_total", ["Assets"], tipo="instante",
       descripcion="Activo total", esencial=True),

    _c("activo_corriente", [
        "AssetsCurrent",
        # IFRS
        "CurrentAssets",
    ], tipo="instante", descripcion="Activo corriente"),

    _c("pasivo_total", ["Liabilities"], tipo="instante",
       descripcion="Pasivo total"),

    _c("pasivo_corriente", [
        "LiabilitiesCurrent",
        # IFRS
        "CurrentLiabilities",
    ], tipo="instante", descripcion="Pasivo corriente"),

    _c("efectivo", [
        "CashAndCashEquivalentsAtCarryingValue",
        "CashCashEquivalentsRestrictedCashAndRestrictedCashEquivalents",
        "CashAndDueFromBanks",
        # IFRS
        "CashAndCashEquivalents",
    ], tipo="instante", descripcion="Efectivo y equivalentes"),

    _c("inversiones_cp", [
        "ShortTermInvestments",
        "MarketableSecuritiesCurrent",
        "AvailableForSaleSecuritiesDebtSecuritiesCurrent",
        "OtherShortTermInvestments",
    ], tipo="instante", descripcion="Inversiones de corto plazo"),

    _c("deuda_lp", [
        "LongTermDebtNoncurrent",
        "LongTermDebt",
        "LongTermDebtAndCapitalLeaseObligations",
        # GM y varias industriales solo publican el total con vencimientos
        # corrientes incluidos. Es preferible a no tener deuda.
        "LongTermDebtAndCapitalLeaseObligationsIncludingCurrentMaturities",
        # Varios REITs no usan ninguna etiqueta con "Debt": Realty Income
        # publica sus 25.032 M bajo `NotesPayable` y dejo de usar `LongTermDebt`
        # en 2016. Va despues de las anteriores porque en otras empresas puede
        # ser solo una parte de la deuda.
        "NotesPayable",
        # IFRS. Ojo: `Borrowings` a secas NO va aca, es el total de la deuda y
        # varias empresas etiquetan el mismo importe tambien como corriente.
        # Va en `deuda_reportada`, que se usa solo si no hay tramos separados.
        "NoncurrentPortionOfNoncurrentBorrowings",
    ], tipo="instante", descripcion="Deuda de largo plazo"),

    _c("deuda_cp", [
        "LongTermDebtCurrent",
        "DebtCurrent",
        "ShortTermBorrowings",
        "OtherShortTermBorrowings",
        # IFRS
        "ShorttermBorrowings",
        "CurrentPortionOfNoncurrentBorrowings",
    ], tipo="instante", descripcion="Deuda de corto plazo"),

    # Deuda total en una sola etiqueta, para las empresas que no separan tramos.
    # NUNCA se suma a las dos anteriores: es un respaldo que se usa solo en los
    # años donde no hay ni deuda_lp ni deuda_cp. Ver modelo._derivar.
    _c("deuda_reportada", [
        "DebtLongtermAndShorttermCombinedAmount",
        # IFRS
        "Borrowings",
    ], tipo="instante", descripcion="Deuda financiera total reportada"),

    # Los leases operativos son deuda economica real desde ASC 842 (2019).
    # Ignorarlos subestima el apalancamiento de retailers y aerolineas.
    _c("leases_lp", [
        "OperatingLeaseLiabilityNoncurrent",
        # IFRS: la NIIF 16 no separa operativos de financieros, hay un solo pasivo.
        "NoncurrentLeaseLiabilities",
    ], tipo="instante", descripcion="Pasivo por leases operativos (no corriente)"),

    _c("leases_cp", [
        "OperatingLeaseLiabilityCurrent",
        # IFRS
        "CurrentLeaseLiabilities",
    ], tipo="instante", descripcion="Pasivo por leases operativos (corriente)"),

    _c("patrimonio", [
        "StockholdersEquity",
        "StockholdersEquityIncludingPortionAttributableToNoncontrollingInterest",
        # IFRS
        "EquityAttributableToOwnersOfParent",
        "Equity",
    ], tipo="instante", descripcion="Patrimonio neto", esencial=True),

    _c("minoritario", [
        "MinorityInterest",
        # IFRS
        "NoncontrollingInterests",
    ], tipo="instante", descripcion="Participacion minoritaria"),

    _c("preferidas", [
        "PreferredStockValue",
        "PreferredStockLiquidationPreferenceValue",
    ], tipo="instante", descripcion="Acciones preferidas"),

    # Necesario para el Altman Z-Score: mide cuanta ganancia acumulo la empresa
    # historicamente contra cuanto capital le tuvieron que poner.
    _c("resultados_acumulados", [
        "RetainedEarningsAccumulatedDeficit",
        # IFRS
        "RetainedEarnings",
    ], tipo="instante", descripcion="Resultados acumulados"),

    _c("goodwill", ["Goodwill"], tipo="instante", descripcion="Llave de negocio"),

    _c("intangibles", [
        "FiniteLivedIntangibleAssetsNet",
        "IntangibleAssetsNetExcludingGoodwill",
        # IFRS
        "IntangibleAssetsOtherThanGoodwill",
    ], tipo="instante", descripcion="Intangibles excluyendo goodwill"),

    _c("inventario", [
        "InventoryNet",
        # IFRS
        "Inventories",
    ], tipo="instante", descripcion="Inventario"),

    _c("por_cobrar", [
        "AccountsReceivableNetCurrent",
        "ReceivablesNetCurrent",
        # IFRS
        "TradeAndOtherCurrentReceivables",
        "TradeAndOtherReceivables",
    ], tipo="instante", descripcion="Cuentas por cobrar"),

    _c("por_pagar", [
        "AccountsPayableCurrent",
        "AccountsPayableAndAccruedLiabilitiesCurrent",
        # IFRS
        "TradeAndOtherCurrentPayables",
    ], tipo="instante", descripcion="Cuentas por pagar"),

    _c("ppe_neto", [
        "PropertyPlantAndEquipmentNet",
        # IFRS
        "PropertyPlantAndEquipment",
    ], tipo="instante", descripcion="Propiedad, planta y equipo neto"),
]

# ------------------------------------------------------------------ flujo de caja

FLUJO = [
    _c("flujo_operativo", [
        "NetCashProvidedByUsedInOperatingActivities",
        "NetCashProvidedByUsedInOperatingActivitiesContinuingOperations",
        # IFRS
        "CashFlowsFromUsedInOperatingActivities",
    ], descripcion="Flujo de caja operativo", esencial=True),

    _c("capex", [
        "PaymentsToAcquirePropertyPlantAndEquipment",
        "PaymentsToAcquireProductiveAssets",
        "PaymentsForCapitalImprovements",
        # IFRS
        "PurchaseOfPropertyPlantAndEquipmentClassifiedAsInvestingActivities",
    ], descripcion="Inversion en bienes de capital"),

    _c("recompras", [
        "PaymentsForRepurchaseOfCommonStock",
        "PaymentsForRepurchaseOfEquity",
        # IFRS
        "PaymentsToAcquireOrRedeemEntitysShares",
    ], descripcion="Recompra de acciones propias"),

    _c("dividendos", [
        "PaymentsOfDividendsCommonStock",
        "PaymentsOfDividends",
        # Varios REITs (AvalonBay) usan esta desde 2018 y ninguna de las de
        # arriba. Es igualmente efectivo pagado, no dividendo declarado.
        "PaymentsOfOrdinaryDividends",
        "PaymentsOfDistributionsToAffiliates",
        # IFRS
        "DividendsPaidClassifiedAsFinancingActivities",
        "DividendsPaid",
    ], descripcion="Dividendos pagados"),

    _c("emision_acciones", [
        "ProceedsFromIssuanceOfCommonStock",
        "ProceedsFromStockOptionsExercised",
        # IFRS
        "ProceedsFromIssuingShares",
        "ProceedsFromExerciseOfOptions",
    ], descripcion="Efectivo recibido por emision de acciones"),

    _c("dya", [
        "DepreciationDepletionAndAmortization",
        "DepreciationAmortizationAndAccretionNet",
        "DepreciationAndAmortization",
        "Depreciation",
        # IFRS: el ajuste del estado de flujo es el equivalente directo.
        "AdjustmentsForDepreciationAndAmortisationExpense",
        "DepreciationAndAmortisationExpense",
        "DepreciationExpense",
    ], descripcion="Depreciacion y amortizacion"),

    # SBC: gasto que no sale de la caja pero diluye igual. Sin esto el FCF
    # de cualquier empresa de software esta inflado.
    _c("sbc", [
        "ShareBasedCompensation",
        "AllocatedShareBasedCompensationExpense",
        # IFRS
        "AdjustmentsForSharebasedPayments",
        "ExpenseFromSharebasedPaymentTransactionsWithEmployees",
    ], descripcion="Compensacion en acciones"),

    _c("adquisiciones", [
        "PaymentsToAcquireBusinessesNetOfCashAcquired",
        # IFRS
        "CashFlowsUsedInObtainingControlOfSubsidiariesOrOtherBusinessesClassifiedAsInvestingActivities",
    ], descripcion="Efectivo usado en adquisiciones"),
]

# ------------------------------------------------------------------ acciones

ACCIONES = [
    _c("acciones_dil", [
        "WeightedAverageNumberOfDilutedSharesOutstanding",
        # IFRS
        "AdjustedWeightedAverageShares",
    ], unidad="shares", descripcion="Acciones diluidas promedio"),

    _c("acciones_bas", [
        "WeightedAverageNumberOfSharesOutstandingBasic",
        "WeightedAverageNumberOfSharesOutstanding",
        # IFRS
        "WeightedAverageShares",
    ], unidad="shares", descripcion="Acciones basicas promedio"),

    # Las empresas con dos clases de accion (Hershey, Ford, Berkshire) etiquetan
    # el promedio ponderado separado por clase, y la API companyfacts solo
    # devuelve los hechos sin dimension: la serie sale vacia o cortada. Este
    # conteo de cierre es el respaldo para poder seguir midiendo la dilucion.
    _c("acciones_circulacion", [
        "CommonStockSharesOutstanding",
        "EntityCommonStockSharesOutstanding",
        # IFRS
        "NumberOfSharesOutstanding",
    ], unidad="shares", tipo="instante", descripcion="Acciones en circulacion (cierre)"),
]


# ------------------------------------------------------------------ sectoriales
#
# Conceptos que solo existen en un tipo de negocio. Cada lista de candidatas se
# armo relevando que etiqueta usa efectivamente cada empresa en EDGAR: varias
# aparentemente obvias (`ProvisionForCreditLosses`) no las usa nadie, y en
# cambio los bancos se reparten entre dos o tres nombres segun el año.

BANCA = [
    _c("interes_ingresos", [
        "InterestAndDividendIncomeOperating",
    ], descripcion="Ingresos por intereses"),

    # El margen financiero: lo que gana prestando menos lo que paga por fondearse.
    # Es la linea de arriba de un banco, el equivalente a las ventas.
    _c("interes_neto", [
        "InterestIncomeExpenseNet",
        # IFRS
        "InterestRevenueExpense",
    ], descripcion="Margen de intereses (ingresos menos costo de fondeo)"),

    _c("no_interes_ingresos", [
        "NoninterestIncome",
        # IFRS
        "FeeAndCommissionIncome",
    ], descripcion="Ingresos por comisiones y servicios"),

    _c("no_interes_gastos", [
        "NoninterestExpense",
        # IFRS
        "OperatingExpense",
    ], descripcion="Gastos operativos del banco"),

    # Con la entrada de CECL en 2020 los bancos cambiaron de etiqueta: BAC usa
    # `ProvisionForLoanLeaseAndOtherLosses` hasta 2019 y la nueva desde 2020.
    # Es exactamente el caso para el que existe la resolucion año por año.
    _c("provision_creditos", [
        "FinancingReceivableExcludingAccruedInterestCreditLossExpenseReversal",
        "ProvisionForLoanLeaseAndOtherLosses",
        "ProvisionForLoanAndLeaseLosses",
        "ProvisionForLoanLossesExpensed",
        # IFRS
        "IncreaseDecreaseInAllowanceAccountForCreditLossesOfFinancialAssets",
    ], descripcion="Cargo del ejercicio por creditos incobrables"),

    _c("prestamos", [
        "LoansAndLeasesReceivableNetReportedAmount",
        "FinancingReceivableExcludingAccruedInterestBeforeAllowanceForCreditLoss",
        "NotesReceivableNet",
        # IFRS
        "LoansAndAdvancesToCustomers",
    ], tipo="instante", descripcion="Cartera de prestamos"),

    _c("depositos", [
        "Deposits",
        # IFRS
        "DepositsFromCustomers",
    ], tipo="instante", descripcion="Depositos de clientes"),

    _c("reserva_creditos", [
        "LoansAndLeasesReceivableAllowance",
        "FinancingReceivableAllowanceForCreditLosses",
        "FinancingReceivableAllowanceForCreditLossExcludingAccruedInterest",
        # IFRS
        "AllowanceAccountForCreditLossesOfFinancialAssets",
    ], tipo="instante", descripcion="Reserva acumulada para incobrables"),
]

SEGUROS = [
    _c("primas_devengadas", [
        "PremiumsEarnedNet",
        "PremiumsEarnedNetPropertyAndCasualty",
    ], descripcion="Primas devengadas netas"),

    _c("siniestros", [
        "PolicyholderBenefitsAndClaimsIncurredNet",
        "IncurredClaimsPropertyCasualtyAndLiability",
    ], descripcion="Siniestros incurridos"),

    # Total de siniestros mas gastos. Es la unica linea que publican todas las
    # aseguradoras, y con ella sale el ratio combinado sin tener que sumar
    # gastos de suscripcion que cada una etiqueta distinto.
    _c("gastos_seguro_total", [
        "BenefitsLossesAndExpenses",
    ], descripcion="Siniestros y gastos totales"),

    _c("reservas_siniestros", [
        "LiabilityForClaimsAndClaimsAdjustmentExpense",
    ], tipo="instante", descripcion="Reservas por siniestros pendientes"),

    _c("primas_no_devengadas", [
        "UnearnedPremiums",
    ], tipo="instante", descripcion="Primas cobradas todavia no devengadas"),

    _c("ingresos_inversiones", [
        "NetInvestmentIncome",
    ], descripcion="Resultado de la cartera de inversiones"),
]

REITS = [
    # Se restan del FFO porque son ganancias de una sola vez, no del negocio de
    # alquilar. Simon Property no las etiqueta de forma utilizable: ver la nota
    # del indicador FFO.
    _c("ganancia_venta_inmuebles", [
        "GainLossOnSaleOfProperties",
        "GainsLossesOnSalesOfInvestmentRealEstate",
    ], descripcion="Ganancia por venta de inmuebles"),

    _c("deterioro_inmuebles", [
        "ImpairmentOfRealEstate",
    ], descripcion="Deterioro de inmuebles"),

    _c("inmuebles_bruto", [
        "RealEstateGrossAtCarryingValue",
        "RealEstateInvestmentPropertyAtCost",
    ], tipo="instante", descripcion="Inmuebles a costo, antes de amortizacion"),

    _c("inmuebles_neto", [
        "RealEstateInvestmentPropertyNet",
    ], tipo="instante", descripcion="Inmuebles netos de amortizacion"),
]


from . import perfiles

# Conceptos que se le piden a cualquier empresa...
NUCLEO: list[Concepto] = RESULTADOS + BALANCE + FLUJO + ACCIONES

# ...y los que solo tienen sentido pedirle a un tipo de negocio. La distincion
# importa para medir la cobertura: si a una industrial se le contaran como
# faltantes los depositos y las primas de seguro, su cobertura caeria sin que
# nada este mal.
SECTORIALES: dict[str, list[Concepto]] = {
    perfiles.BANCO: BANCA,
    perfiles.SEGUROS: SEGUROS,
    perfiles.REIT: REITS,
}

TODOS: list[Concepto] = NUCLEO + BANCA + SEGUROS + REITS


def esperables(perfil: str) -> list[Concepto]:
    """Conceptos que corresponde encontrar en una empresa de ese tipo."""
    return NUCLEO + SECTORIALES.get(perfil, [])

POR_CLAVE: dict[str, Concepto] = {c.clave: c for c in TODOS}

ESENCIALES: list[str] = [c.clave for c in TODOS if c.esencial]

GRUPOS: dict[str, list[Concepto]] = {
    "Estado de resultados": RESULTADOS,
    "Balance": BALANCE,
    "Flujo de caja": FLUJO,
    "Acciones": ACCIONES,
    "Banca": BANCA,
    "Seguros": SEGUROS,
    "Inmuebles": REITS,
}

