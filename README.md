# Analizador de Acciones

Aplicación local para análisis fundamental de acciones de EE.UU. con enfoque
*deep value*. Tres vistas: un **Panel** con una fila por acción para barrer el
universo, un **Detalle** con estados contables, evolución histórica y valuación
para las que merecen una tarde entera, y un **Radar** que sale a buscar
candidatas nuevas al mercado entero cuando se lo pedís.

Los estados contables salen de **SEC EDGAR** (XBRL auditado, 15 años). Los datos
de mercado, de **Yahoo Finance**, con Stooq como respaldo. Sin claves de API:
el diagnóstico del Radar corre como Claude Code, con tu suscripción.

---

## Cómo se usa

**Doble clic en `Abrir Analizador.bat`.** Se abre solo en el navegador.

Para entrar **desde el teléfono**, ver [DESPLIEGUE.md](DESPLIEGUE.md): la app
está preparada para correr también en Streamlit Community Cloud, con clave de
acceso y con el universo y las tesis guardados en un Gist privado para que
sobrevivan a los reinicios. Sin secretos configurados —que es el caso en tu
laptop— usa los archivos locales y no pide nada.

Se abre una ventana negra de consola: **es el servidor, dejala abierta** mientras
uses la app. Al cerrarla, la app se apaga. Es así por diseño: esto corre en tu
máquina, no en un sitio web, y por eso tus datos y tus notas no salen de acá.

Desde una terminal es equivalente:

```bash
streamlit run Analizador.py
```

Se abre en `http://localhost:8501`. La primera corrida baja los datos de cada
empresa desde EDGAR y tarda unos minutos; a partir de ahí el caché local hace
que sea instantáneo.

Instalación de dependencias, si hiciera falta:

```bash
pip install -r requirements.txt
```

### Si no abre

| Síntoma | Causa y solución |
|---|---|
| La página no carga o dice que no se puede conectar | El servidor no está corriendo. Abrí `Abrir Analizador.bat` |
| Funcionaba y de golpe dejó de andar | Se cerró la ventana negra de consola. Volvé a abrir el `.bat` |
| El `.bat` se cierra solo al instante | Falta alguna dependencia: abrí una terminal en la carpeta y corré `pip install -r requirements.txt` |
| Dice que el puerto 8501 está en uso | Ya hay una instancia abierta: probá `http://localhost:8501` en el navegador antes de lanzar otra |

> **Nota técnica:** `scripts/dev_server.py` es solo para sesiones de desarrollo —
> levanta la app en un puerto libre para no pisar la instancia que tengas abierta
> en el 8501. Para el uso normal, siempre el `.bat`.

---

## Las tres vistas

### Panel

Una fila por acción, sparkline de 52 semanas, semáforo por umbrales, filtros por
rango y exportación a Excel.

#### Vistas

Una tabla de 40 columnas no se lee: se recorre con el scroll y se terminan
mirando las tres primeras. Por eso las columnas se agrupan en **vistas**, cada
una armada alrededor de una pregunta. Se cambia desde la barra lateral, y sobre
la vista elegida podés seguir agregando o sacando indicadores a mano.

| Vista | Para qué | Cols. |
|---|---|---|
| **Esencial** *(inicial)* | Barrer el universo: dónde está parada, qué tan buena es, cuánto cuesta, si aguanta | 19 |
| **Valuación** | Cuánto cuesta, por todos los ángulos: múltiplos, yields, NCAV, EPV | 15 |
| **Calidad y caja** | ROIC, márgenes, conversión a caja, accruals, dilución por SBC | 12 |
| **Solidez y riesgo** | Deuda, coberturas, Altman, Beneish, años en rojo | 11 |
| **Crecimiento y capital** | CAGR, aceleración, spread ROIC-WACC, qué hace con la caja | 11 |
| **Mercado** | Precio, rango, retornos, beta, volumen | 15 |
| **Banca** | Margen de intereses, eficiencia, coste del riesgo, apalancamiento | 16 |
| **Seguros** | Ratio combinado y su descomposición, float | 15 |
| **REITs** | FFO, P/FFO, payout sobre FFO, deuda sobre inmuebles | 14 |
| **Móvil** | Cuatro columnas: lo mínimo para decidir si vale abrir una empresa | 4 |
| **Completa** | Todo lo marcado con `panel=True` en el catálogo | 53 |

Las 15 de **Esencial** están elegidas para contestar las cuatro preguntas del
screening y nada más:

1. **Dónde está parada** — Cotización, Market Cap, % desde máx 52s, caída desde
   máximo histórico
2. **Qué tan buena es** — ROIC y ROIC promedio 5a, ROE, margen operativo contra
   su propio promedio de 10 años, crecimiento de ingresos 5a
3. **Cuánto cuesta** — EPS, PER, PER Forward, EV/EBITDA, EV/EBIT, FCF Yield
4. **Si aguanta** — Deuda neta/EBITDA, Piotroski

Dos pares se leen juntos y por eso están los dos: **ROIC actual contra su
promedio de 5 años** —si el actual está muy por debajo, el deterioro ya
empezó— y **EV/EBITDA contra EV/EBIT**, cuya diferencia es cuánto pesa la
amortización en ese negocio.

Los importes van en formato compacto (`3,9T`, `108,2B`): abarcan seis órdenes
de magnitud y en formato largo una sola columna se come el ancho de tres.

El **margen operativo contra su promedio de 10 años** es la que más trabaja de
las doce, y a propósito **no tiene semáforo**: un valor muy negativo significa
que el margen está deprimido, y eso es exactamente igual de compatible con una
oportunidad cíclica que con un deterioro permanente. Pintarlo de verde o de rojo
sería inventar un veredicto que el dato no da. Ordená por esa columna con
**Invertir** activado y tenés arriba las más castigadas contra su propia
historia; el resto de la fila te dice si el castigo ya se ve en la caja y en la
deuda.

- **Agregar tickers:** campo arriba de la tabla, acepta varios de una
  (`META NVDA CRM`). También podés editar la lista completa en la barra lateral.
  Se guarda en `datos/universo.txt`.
- **Clic en una fila** manda esa empresa al Detalle.
- **Descarga en Excel** (`.xlsx`), no CSV. Cada columna va como número con su
  formato real — `33,8%`, `14,1x`, `$176,89`, `108.246 M` — así que sigue siendo
  ordenable y calculable pero se lee. Incluye el semáforo como color de fondo,
  autofiltro, panel congelado y la explicación de cada indicador como comentario
  en el encabezado.
- Los filtros **conservan** las empresas que no tienen ese dato: un hueco de
  EDGAR no te tiene que esconder una candidata.

Los formatos de Excel salen del campo `formato` del catálogo de métricas, el
mismo que usa la pantalla: un indicador nuevo con `formato="pct"` se exporta
bien sin tocar el exportador.

La tabla en sí es de solo lectura a propósito: cada celda es un cálculo derivado
de EDGAR, no un dato que tenga sentido escribir a mano. Lo único que realmente
elegís vos es *qué* empresas mirar, y para eso está el campo de alta.

### Detalle

Cada empresa se clasifica primero en **Value, Growth, Híbrida o Turnaround**, y
eso decide con qué vara se lee todo lo demás. No es cosmético: un PER de 40x es
una alarma en una empresa que crece al 4% y es normal en una que crece al 30%;
un FCF Yield del 1% descalifica a una madura y no dice nada de una que
reinvierte todo. Sin saber de qué tipo es, el semáforo miente en las dos
direcciones.

La regla mira el crecimiento de ingresos por dos caminos —último ejercicio y
CAGR de 3 años— y manda el más conservador, porque un año suelto se distorsiona
por efecto base, divisa, adquisiciones o calendario 52/53 semanas. Si los dos
difieren mucho, la ficha lo avisa. Dos casos se nombran aparte: **Turnaround**
(pierde plata y además crece poco: no es growth, es una reestructuración, y lo
que importa son los meses de caja) y **Cíclica** (banca, energía, materiales,
autos: el PER es contracíclico, barato en el pico y caro en el suelo).

De ahí salen tres bloques nuevos:

- **Cuadro de ratios** — cambia según el estilo. Value se juzga por valuación,
  solvencia, rentabilidad y retorno al accionista; Growth por crecimiento,
  eficiencia, valuación de crecimiento y riesgo de dilución.
- **Señales de alerta** — marcadas **Crítica / Vigilar / Menor**, cada una con
  la cifra que la dispara. Una value se rompe por trampas de valor; una growth,
  por compresión de múltiplo y dilución. Se evalúan contra el cuadro que
  corresponde.
- **Lectura rápida** — los seis eliminatorios, en la vara de su perfil contable.

El orden es deliberado — valuar antes de entender es la forma más rápida de
comprar una *value trap*:

1. **Lectura rápida** — seis semáforos sobre los puntos eliminatorios
2. **Evolución histórica** — ingresos y márgenes, ROIC contra WACC, ganancia
   contable contra caja, deuda, dilución, asignación de capital, recompras
   contra cotización, PER histórico
3. **Estados contables** — resultados, balance y flujo, con selector
   **Anual / Trimestral** y descarga en Excel (una hoja por estado, negativos
   en rojo)
4. **Valuación** — DCF inverso y tabla de escenarios
5. **Todos los indicadores** — el catálogo completo, agrupado, con cómo leer cada uno
6. **Auditoría XBRL** — de qué etiqueta salió cada número
7. **Tu tesis** — nota por empresa, guardada en la base local

### Radar

La bandeja de entrada. Las otras dos vistas analizan empresas que elegiste vos;
esta trae empresas que no elegiste.

Cuando lo corrés —desde la barra lateral, o con *Run workflow* en GitHub
Actions— el barrido le pide al **screener de Yahoo** las empresas de NYSE y
Nasdaq que pasan tus filtros —el preset de fábrica es
deep value castigado: PER < 14, EPS > 0, ROE > 8%, deuda/EBITDA < 3,5x y abajo
en el año—, descarta las que ya tenés y las que ya rechazaste, y a las nuevas
les pide a **Claude, con buscador web**, un párrafo que conteste por qué están
castigadas, clasificado en una de cinco causas. Corre como Claude Code con tu
suscripción, no contra la API: no hay factura aparte, sale de tu cuota de uso.

Eso último es el punto. El filtro contesta *cuáles están baratas*, que es la
pregunta fácil; una caída del 40% con ROIC alto y balance limpio se ve idéntica
sea una oportunidad o una trampa de valor, y la diferencia está en las noticias,
no en el balance. El párrafo no recomienda ni valúa: dice qué pasó y qué hay
que verificar en los estados contables para saber si se revierte.

Cada candidata tiene tres salidas —**al universo**, **al Detalle** sin sumarla,
o **descartada**— y lo descartado no vuelve a aparecer, que es lo que evita que
el radar se convierta en la misma lista de siempre.

**Nada corre solo.** Hubo un `cron` que barría todas las mañanas y se sacó: un
barrido automático acumula candidatas más rápido de lo que uno las mira, y el
diagnóstico de cada una consume cuota del plan aunque esa semana no estés
buscando nada. Los filtros se editan desde la barra lateral y la próxima corrida
usa lo que dejaste puesto. Puesta en marcha, costos y diagnóstico de fallas:
**[RADAR.md](RADAR.md)**.

---

## El DCF inverso

Es la herramienta central de valuación de la app y merece una explicación aparte.

Un DCF normal te pide proyectar el futuro y devuelve un valor. El problema es
que la proyección la elegís vos, así que el resultado termina confirmando lo que
ya pensabas.

El DCF inverso da vuelta la pregunta: en vez de estimar cuánto vale, calcula
**qué crecimiento de la caja libre está descontando el precio de hoy**. Después
vos decidís una sola cosa, que es la única que importa: ¿ese número es plausible
para este negocio?

> Ejemplo real de la validación: a $176,89 el precio de Accenture implicaba
> **−2,2% anual** de FCF durante 10 años, contra **+7,4%** de crecimiento real
> en los 5 años previos. Eso no dice "comprá": dice que el mercado está
> descontando un deterioro permanente, y que tu trabajo es decidir si ese
> deterioro es real.

---

## Arquitectura

Cuatro capas, cada una conoce solo a las de abajo:

```
app/
  config.py            parámetros, rutas y el fix de SSL de Avast
  cache.py             SQLite: caché con TTL + historial de tus mediciones
  almacen.py           dónde viven los tickers y tus tesis: disco o Gist privado
  acceso.py            portón de clave, solo cuando corre en internet
  conceptos.py         catálogo de conceptos contables y etiquetas XBRL (us-gaap + IFRS)
  perfiles.py          banco / seguros / REIT / general, y qué no aplica a cada uno
  estilo.py            value / growth / híbrida / turnaround, y su cuadro de ratios
  alertas.py           señales de alerta por gravedad, según el estilo
  radar.py             el barrido: filtros del screener y memoria entre corridas
  diagnostico.py       por qué cayó: Claude con buscador web, una vez por empresa
  proveedores/
    edgar.py           SEC EDGAR — la única fuente auditada
    instancia_xbrl.py  lector de XBRL crudo, para cuando la API se atrasa
    mercado.py         Yahoo Finance + Stooq de respaldo
  metricas/
    base.py            registro, semáforo, formato
    mercado_met.py     precio, rango 52s, drawdown, liquidez
    valuacion.py       PER normalizado, EV/FCF, Greenblatt, NCAV, EPV
    rentabilidad.py    ROIC, ROIC incremental, márgenes, estabilidad
    caja.py            FCF, conversión, accruals de Sloan, ciclo de caja
    solidez.py         deuda neta/EBITDA, coberturas, Altman Z
    capital.py         WACC, spread ROIC-WACC, dilución, payout
    crecimiento.py     CAGR a 5 y 10 años, aceleración
    senales.py         Piotroski F-Score, Beneish M-Score
    sectoriales.py     banca, seguros y REITs — solo en su perfil
  modelo.py            Empresa: une fundamentals + mercado, deriva series
  ui/                  Panel, Detalle, Radar, gráficos, DCF inverso
scripts/
  radar_barrido.py     el barrido, a pedido: local o en GitHub Actions
  radar_aplicar.py     mezcla al radar lo que escribió el agente
```

### Los tooltips se arman solos

Cada indicador declara **qué mide** (`ayuda`) y **cómo se calcula** (`formula`).
Los **valores de referencia** no se escriben: se generan desde los mismos
umbrales que pintan la celda, así que el tooltip no puede contradecir al
semáforo — si un umbral se ajusta, cambian los dos a la vez. Y si el indicador
no aplica a algún perfil, el tooltip lo dice.

El texto se compone una sola vez en `ui/comun.py::texto_ayuda()` y lo usan las
tres salidas: el encabezado de columna del Panel, el Detalle y los comentarios
de celda del Excel. Los tres dicen exactamente lo mismo.

### Cómo agregar un indicador

Es el punto de extensión del sistema. Escribís una función con un decorador en
el módulo del grupo que corresponda:

```python
@metrica("mi_ratio", "Mi Ratio", "Valuacion", formato="x", mejor="bajo",
         umbrales=(10, 25), panel=True,
         ayuda="Qué mide y cómo leerlo.",
         formula="EBIT / capitalización.")
def mi_ratio(e):
    return div(e.f("ebit"), e.market_cap)
```

Con eso solo aparece en el Panel, en el Detalle, en el semáforo, en los filtros,
en el ordenamiento y en el historial de snapshots. No hay que registrarlo en
ningún otro lado.

Para un **concepto contable** nuevo que EDGAR reporte, se agrega al catálogo de
`conceptos.py` con sus etiquetas XBRL candidatas. Para una **fuente de datos**
nueva, un módulo en `proveedores/`.

---

## Dos decisiones de diseño que importan

### Las etiquetas XBRL se resuelven año por año

Las empresas cambian de etiqueta contable con el tiempo. CoStar (CSGP) usó
`CostOfRevenue` hasta 2017 y después pasó a `CostOfGoodsAndServicesSold`. Un
extractor que elige "la primera etiqueta que tenga datos" y lee toda esa serie
devuelve números de 2013 presentados como si fueran actuales: **plausibles y
falsos**.

Por eso, para cada ejercicio, se recorren las etiquetas candidatas en orden y se
toma la primera que cubra *ese año*. La pestaña de auditoría XBRL del Detalle
muestra exactamente qué etiqueta se usó en cada año, y marca dónde hubo que
combinar varias.

### Elegir la etiqueta que no es no se ve como un error

Resolver año por año no alcanza: falta elegir bien *cuál* etiqueta va primero.
Los ingresos salían de `RevenueFromContractWithCustomerExcludingAssessedTax`,
que es solo la venta bajo contrato con clientes (ASC 606). Todo lo que la
empresa cobra por fuera de un contrato queda afuera: alquileres, intereses de
créditos, primas de seguro, coberturas.

El resultado no era un error visible. Era un número del orden correcto, y menor:

| Empresa | Lo que mostraba | Lo que publica | Qué faltaba |
|---|---:|---:|---|
| Bloom Energy (BE) | 2.002 M | **2.024 M** | leasing de equipos |
| MercadoLibre (MELI) | 20.335 M | **28.893 M** | intereses del crédito |
| CNA Financial (CNA) | 1.577 M | **14.989 M** | primas de seguro |

CNA es la medida del agujero: una aseguradora se veía **diez veces más chica**
de lo que es.

Invertir el orden y poner `Revenues` primero no alcanza, porque la equivocación
simétrica existe: hay emisores que etiquetan `Revenues` en una línea menor.
American Superconductor publica cero y Apogee 72,7 M sobre un ejercicio de
934 M. Ninguna preferencia fija acierta en los dos casos.

El desempate lo publica la empresa. `GrossProfit` y el costo de ventas salen de
etiquetas distintas y están impresos en la misma cara del estado: **su suma es
el total**. Cuando los tres están, se recorren todos los candidatos y gana el
que cierra la cuenta, sin importar en qué orden estaba — así Apogee vuelve sola
a `SalesRevenueNet`. Cuando la empresa no publica ganancia bruta (los bancos y
las aseguradoras no la publican) manda el orden de preferencia, con `Revenues`
primero, que para esos casos es el correcto. Y si ningún candidato cierra, se
deja el elegido y el control de coherencia lo marca: inventar un reemplazo sería
peor.

### Las cuentas tienen que cerrar, y ahora se controla que cierren

El error de arriba estuvo meses sin que nadie lo notara, y **la empresa misma
lo delataba**: Bloom publica costo de ventas 1.437 M y ganancia bruta 587 M, que
suman 2.024 M, no 2.002 M. Son tres etiquetas distintas que tienen que sumar por
definición.

`app/validacion.py` corre esas identidades sobre cada ficha y las muestra en el
Detalle, arriba de la auditoría XBRL:

- ingresos = costo de ventas + ganancia bruta
- activo = pasivo + patrimonio (+ minoritario, + patrimonio temporal)
- antes de impuesto − impuesto = ganancia neta *(aviso: hay renglones en el medio)*
- ganancia neta / acciones diluidas = EPS diluido *(aviso: es un promedio ponderado)*

No corrige nada: marca el año y la etiqueta para ir a buscarlo al informe. Una
identidad rota puede ser el extractor o puede ser la empresa, y cuál de las dos
es se decide abriendo el 10-K.

El control encontró otros tres errores apenas se encendió, todos en esta misma
familia de "número plausible y falso":

**El balance salía de un trimestre.** Los conceptos de balance son instantes: no
tienen duración que revisar, así que el filtro que descarta trimestres en el
estado de resultados no los protegía. Y un 10-K trae instantes que no son el
cierre —el estado de evolución del patrimonio arrastra saldos intermedios—. El
balance 2018 de Bloom salía del **31 de marzo**: activo 1.214 M en lugar de
1.522 M y patrimonio −2.213 M en lugar de −143 M. Ahora un instante solo se
acepta si cae en el mes de cierre del ejercicio.

**El EPS histórico no estaba ajustado por split.** Las acciones sí, el EPS no,
así que la serie quedaba partida al medio en la fecha del split: Apple mostraba
9,21 dólares por acción en 2017 y 2,98 en 2018, un derrumbe del 68% que nunca
ocurrió. Alphabet necesitó además otro detector: informó las acciones por clase
A, B y C hasta 2021, y la API de EDGAR solo devuelve hechos sin dimensiones, así
que no hay serie de acciones donde ver el split de 20 a 1. Se deduce del EPS
**con la ganancia neta de testigo**: repartir la misma torta en veinte pedazos
no cambia la torta, así que un EPS que cae a 1/20 con la ganancia neta intacta
solo puede ser un split.

**Un cambio de escala del emisor se leía como un split.** Nu Holdings informa
las acciones del ejercicio 2021 en miles (334.436) en un 20-F y en unidades
(1.602.126.000) en otro. El cociente da 15.079, y el detector lo tomaba por un
split. Ninguna empresa hace un split de quince mil a uno: ahora hay una banda de
lo que puede ser un split de verdad, y un año que quede a dos órdenes de
magnitud del resto de su propia serie se descarta en vez de publicarse. El
Detalle lista qué se descartó y por qué.

### Un banco no se mide con la vara de una industrial

Los depósitos de un banco son su materia prima, no su financiamiento; su deuda
es insumo, no carga. Aplicarle el catálogo completo no deja huecos: **devuelve
números plausibles y falsos**. Medido sobre datos reales:

| | JPMorgan | Accenture |
|---|---|---|
| EV / EBIT | **6,8x** | 10,4x |
| ROIC prom. 5a | **32,5%** | 33,8% |
| Deuda neta / EBITDA | **0,9x** | −0,3x |
| Altman Z | **0** | 4 |
| FCF Yield | **−15,3%** | 10,0% |

JPM aparecía 35% más barata que Accenture con la misma rentabilidad. Los cinco
números están mal y los cinco se ven normales.

Por eso cada empresa se clasifica por su **código SIC** en `banco`, `seguros`,
`reit` o `general`, y las métricas que no aplican **no se calculan**. En el
Detalle se muestran como *"no aplica"*, distinto de un guion por falta de dato:
uno es una decisión, el otro es un hueco. El encabezado y la lectura rápida
también cambian de indicadores según el perfil.

La tabla de supresiones vive entera en `perfiles.py`, agrupada por motivo, para
poder auditarla y ajustarla de un vistazo. Piotroski y Beneish entran ahí por
una razón concreta: incluyen chequeos de margen bruto y liquidez corriente que
en un banco no se pueden evaluar y **suman cero en silencio**, así que el score
sale subestimado sin avisar.

Y donde el catálogo general calla, aparece el propio del sector. Son 21
indicadores nuevos que **solo existen en su perfil**: no hay forma de que un
ratio combinado aparezca en una empresa de software, ni de que un REIT muestre
margen de intereses.

| Banca | Seguros | REIT |
|---|---|---|
| Margen de intereses (NIM) | Ratio combinado | FFO y FFO por acción |
| Ratio de eficiencia | Ratio de siniestralidad | Precio / FFO y FFO Yield |
| Coste del riesgo | Ratio de gastos | Payout sobre FFO |
| Reservas sobre cartera | Float / Capitalización | Deuda / Inmuebles a costo |
| Préstamos / Depósitos | Rendimiento del float | Crecimiento del FFO |
| Apalancamiento | Crecimiento de primas | |
| Comisiones / Ingresos | | |
| Crecimiento de depósitos | | |

El encabezado y la lectura rápida del Detalle también cambian: un banco se abre
con ratio de eficiencia y coste del riesgo, una aseguradora con el ratio
combinado, un REIT con Precio/FFO.

### Los splits parten la serie de acciones en dos escalas

Cada ejercicio se toma de la presentación que lo cubre, y una empresa solo
reexpresa los años anteriores en los informes **posteriores** al split. Alphabet
pasaba de 675 millones de acciones en 2020 a 13.242 millones en 2021: no emitió
veinte veces su capital, hizo un split de 20 a 1 y los dos números están en
escalas distintas. Sin corregirlo, Alphabet aparecía **diluyendo 78% en 5 años
mientras recompraba**, y NVIDIA 57% con dos splits de por medio.

La proporción no se adivina del salto entre un año y el siguiente, porque ahí el
split viene mezclado con la emisión real del período: Tesla saltaba 3,66x, que
es un split de 3 a 1 multiplicado por un 22% de emisión genuina. Se saca del
propio dato: **el mismo ejercicio 2018 aparece con 170,5 millones de acciones en
el informe de 2019 y con 853 millones en el de 2021**. Ese cociente es
exactamente el split, sin nada más adentro, porque el ejercicio es el mismo.

### `companyfacts` no siempre está al día

La API de la SEC es de conveniencia: la arman procesando las presentaciones, y
a veces no procesan alguna. Nu Holdings presentó su 20-F del ejercicio 2025 el
**8 de abril de 2026**, con el XBRL completo adentro, y cuatro meses después
`companyfacts` seguía devolviendo datos hasta 2024. La ficha mostraba un año de
atraso sin ningún aviso.

Por eso el extractor compara siempre la última presentación anual del emisor
contra lo más nuevo que devuelve la API. Si la API se quedó atrás, baja la
instancia XBRL de esa presentación y completa las series. Es un relleno: la
fuente principal sigue siendo `companyfacts`, y un período que ya vino de la
API nunca se pisa. Los hechos con dimensiones y las etiquetas de extensión
propias de la empresa se descartan, igual que hace la API.

### Trimestral

El selector **Trimestral** de los estados contables tiene dos límites que
importan:

- **El cuarto trimestre no existe.** Las empresas presentan tres 10-Q y después
  un 10-K con el ejercicio entero. El 4T se calcula restándole al año los tres
  trimestres previos, y la app avisa cuáles salieron así.
- **El flujo de caja no se trimestraliza.** En un 10-Q viene acumulado desde el
  inicio del ejercicio, no por trimestre. Mostrarlo como trimestral daría el
  primer trimestre bien y los otros tres inflados.

Los emisores extranjeros (20-F) **no tienen vista trimestral**: reportan sus
trimestres por formulario 6-K, que es texto libre sin datos estructurados.

### Hay una tercera categoría de dato: el consenso

Casi todo en esta app es un hecho auditado o una cotización. Tres indicadores no
lo son, y están marcados **(est.)** en el nombre: **PER Forward**, **Ingresos
NTM** y **EPS NTM**. Son lo que un grupo de analistas *espera*, publicado por
Yahoo, referido al próximo ejercicio fiscal completo.

Van los tres sobre la misma base para que se puedan leer juntos, y cada uno
avisa en su tooltip que es una estimación. Importan por dos comparaciones:

- **PER contra PER Forward** — cuánto del precio de hoy depende de que esas
  expectativas se cumplan. Si el PER es 45x y el forward 18x, el mercado ya
  está pagando por una duplicación de ganancias que todavía no ocurrió.
- **Crecimiento histórico contra el estimado** — por eso las dos columnas NTM
  van pegadas al CAGR de 5 años. Accenture creció 9,5% anual y el consenso
  proyecta 4,1%: esa brecha es la tesis. Al revés también: si viene creciendo
  al 3% y proyectan 15%, alguien tiene que explicar de dónde sale la
  aceleración.

El consenso tiende a ser optimista y se revisa a la baja al acercarse la fecha.
Léelo como el mejor escenario, no como el probable.

### EDGAR para fundamentals, Yahoo solo para mercado

Yahoo también publica estados contables, pero mezclarlos con los de EDGAR
produce ratios donde el numerador y el denominador vienen de criterios
distintos. Es la clase de error que no se nota hasta que decidís sobre un número
que nunca existió.

**La única excepción es el Radar**, y está acotada a propósito. EDGAR es un
archivo, no un buscador: preguntarle cuáles cotizan a PER menor a 14 exigiría
bajar entre 5 y 30 MB por cada una de las 5000 empresas. Entonces Yahoo hace de
embudo —baja de 5000 a 40— y sus números quedan marcados como lo que son. En el
momento en que una candidata te interesa y la abrís en el Detalle, se recalcula
todo con EDGAR desde cero. Yahoo elige a quién mirar; EDGAR dice cuánto vale.

---

## Limitaciones conocidas

- **Solo emisores que reportan a la SEC**, en dólares. Eso incluye los
  extranjeros que presentan 20-F con taxonomía IFRS, no solo los 10-K
  estadounidenses. Un emisor que reporta en otra moneda devuelve error
  explícito: mezclar un balance en euros con una capitalización en dólares da
  ratios sin sentido y con apariencia normal.
- **Los emisores 20-F traen menos historia y no tienen trimestres.** NU tiene 7
  ejercicios contra los 15 de una empresa de EE.UU., así que los promedios de 10
  años y el PER normalizado quedan vacíos.
- **El ratio combinado es una aproximación.** Se calcula con el total de
  siniestros y gastos que publican todas las aseguradoras, que incluye algún
  gasto ajeno a la suscripción. Sale un par de puntos por encima del que
  reporta la empresa; sirve para comparar y para seguir la tendencia, no como
  cifra oficial.
- **El FFO no está para todos los REITs.** Se omite en los que nunca etiquetan
  la ganancia por venta de inmuebles, porque sin ese dato queda inflado. Simon
  Property es el caso: en 2025 daría $20,81 por acción contra los $11-12 reales.
- **Faltan la mora y el AFFO.** Los préstamos en mora y el capex recurrente de
  un REIT viven en notas con dimensiones que la API `companyfacts` no devuelve.
  El coste del riesgo y el payout sobre FFO cubren buena parte de lo mismo.
- **Etiquetado de ejercicios fiscales**: el año se deriva de la fecha de cierre.
  Los retailers que cierran a fin de enero pueden quedar etiquetados un año
  adelante respecto de cómo ellos nombran su ejercicio. No afecta los ratios
  porque todos los conceptos de una empresa usan la misma regla.
- **Un balance viejo puede mezclar dos reexpresiones.** Cada concepto toma la
  presentación más reciente que lo cubra, y no siempre es la misma para las tres
  patas del balance: First Solar reexpresó el patrimonio de 2015 en el informe
  de 2018 y nunca volvió a presentar el activo de ese año. La ecuación queda
  descuadrada menos del 1%, siempre en ejercicios viejos, y el control de
  coherencia del Detalle lo marca. Los dos números son los que la empresa
  presentó; lo que cambia es de qué informe salió cada uno.
- **Yahoo Finance no es una API oficial** y se rompe cada tanto. Los precios
  tienen respaldo en Stooq; beta y sector no, y pueden aparecer vacíos.
- **Los umbrales del semáforo son heurísticas de valor**, no verdades. Señalan
  dónde mirar; no deciden.

---

## Nota técnica: SSL y Avast

Avast intercepta TLS en esta máquina y su certificado raíz no está en el bundle
de `certifi`, así que `requests` falla con `SSLCertVerificationError`.
`config.preparar_ssl()` combina los dos bundles al importar y apunta ahí las
variables de entorno. Es automático e idempotente; si algún día desinstalás
Avast, sigue funcionando igual.

---

## Lo que la app no hace

El Panel cubre el descubrimiento y el Detalle la valuación, pero entre los dos
falta la etapa que decide todo: **por qué cayó**. Una acción a −40% con ROIC
alto y balance limpio puede ser una oportunidad excepcional o una empresa cuyo
negocio se está evaporando, y los dos casos se ven idénticos en la tabla.

Esa lectura es tuya. La app te dice dónde mirar y te muestra si el deterioro ya
aparece en los números; no te dice si el mercado tiene razón sobre el futuro.
**El diagnóstico precede a cualquier valuación.**
