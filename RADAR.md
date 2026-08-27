# El Radar

La tercera hoja de la app. Las otras dos analizan empresas que vos elegiste; el
Radar sale a buscarlas solo, una vez por día, y te deja una lista corta
esperando.

Son dos piezas que no se conocen entre sí:

- **El barrido**, que corre en GitHub Actions todas las mañanas y escribe el
  resultado en tu Gist privado.
- **La hoja Radar** de la app, que lee ese Gist y te deja aprobar o descartar.

---

## Qué hace cada mañana

La corrida son **tres pasos**, y el reparto entre ellos es la decisión de diseño
que sostiene todo lo demás:

| Paso | Quién | Qué hace |
|---|---|---|
| 1. Barrer | Python (`scripts/radar_diario.py`) | Determinista: filtra el mercado, cruza contra tu universo y tus descartes, **guarda** |
| 2. Diagnosticar | Claude Code (la Action) | Agente con buscador: escribe un JSON por empresa |
| 3. Aplicar | Python (`scripts/radar_aplicar.py`) | Determinista: valida esos JSON y los mezcla al radar |

**El agente nunca toca el almacén ni ve el token del Gist.** Escribe archivos en
el runner y listo. Por eso una corrida rara del paso 2 no puede romper nada: lo
peor que pasa es que el paso 3 ignore un archivo mal escrito y esa empresa quede
pendiente para mañana. Está probado con JSON roto, con etiquetas inventadas y
con tickers que ya no están en el radar.

El paso 1 guarda **antes** de que el paso 2 empiece. Si el agente se queda sin
cuota a mitad de camino, las candidatas del día ya están a salvo, y el paso 3
corre igual (`if: always()`) para no perder lo que sí alcanzó a escribir.

### El diagnóstico

A las candidatas que aparecen **por primera vez**, Claude les busca en la web
qué les pasó en los últimos doce meses y escribe dos a cuatro oraciones con
fechas y cifras, más una que arranca con *"Para descartar trampa:"* y dice qué
verificar en los estados contables. Lo clasifica en una de cinco causas:
deterioro estructural, ciclo del sector, hecho puntual, contabilidad o gobierno,
arrastre de mercado.

Se pide **una sola vez por empresa** y queda guardado. Es lo que evita pagar dos
veces por la misma respuesta. Si una falla, vuelve a la cola: lo que la saca es
tener párrafo, no haberlo intentado.

**Sin esperar a mañana.** En la barra lateral del Radar hay un panel
*Diagnóstico* que dice cuántas están pendientes y las corre ahí mismo, de a
tandas. Guarda después de **cada una**, no al final: si a la quinta cerrás la
pestaña, las cuatro anteriores ya están en el Gist. Perder llamadas que ya
consumieron cuota por no haber guardado sería la peor forma de gastarla.

---

## Por qué Yahoo y no EDGAR

Toda la app tiene una regla: los estados contables salen de EDGAR y de ningún
otro lado. El Radar es la excepción, y es deliberada.

EDGAR es un archivo, no un buscador: no se le puede preguntar "cuáles tienen PER
menor a 14" sin bajarse antes los 5 a 30 MB de cada una de las 5000 empresas.
Serían horas por corrida.

Entonces Yahoo hace de **embudo**: baja de 5000 a 40. Sus números sirven para
decidir a cuál mirar, no para decidir si comprar — por eso la tabla del Radar lo
dice en el encabezado. **En el momento en que una candidata te interesa y la
abrís en el Detalle, la app la recalcula con EDGAR desde cero.** Esos son los
números que valen.

Yahoo elige a quién mirar. EDGAR dice cuánto vale.

> **Y no confíes en sus escalas.** `fiftyTwoWeekChangePercent` viene en
> porciento (-63,0) y `fiftyTwoWeekHighChangePercent` en fracción (-0,647), en
> el mismo objeto. Leerlos como vienen daba candidatas que habían caído 63% en
> el año y figuraban a 0,6% de su máximo. La distancia al máximo se **calcula**
> contra el precio, no se lee. Es la misma trampa del dividend yield, que ya
> estaba documentada en el README.

---

## Puesta en marcha

### 0. El Gist (obligatorio)

El barrido corre en los servidores de GitHub y la app corre en tu laptop: el
Gist privado es el único lugar donde las dos se encuentran. **Sin Gist, la
Action escribe en un disco que se borra y tu app nunca ve nada.**

Si todavía no lo creaste, son los pasos 1 de [DESPLIEGUE.md](DESPLIEGUE.md):
crear el Gist secreto y el token *fine-grained* con permiso **Account → Gists →
Read and write**.

> **Sembralo con tu lista actual, no con `[]`.** En cuanto la app ve un Gist
> configurado deja de leer `datos/universo.txt`, y si el Gist está vacío lo
> toma como primera vez: escribe la lista por defecto **encima de la tuya**.
> Poné en `universo.json` los tickers que ya tenés y el problema no existe.

Después, para que **tu laptop lea el mismo Gist**, poné `gist_id` y
`github_token` en `.streamlit/secrets.toml`. Ese archivo está en `.gitignore`:
no se sube. Para comprobar que quedó bien:

```bash
python -c "from app import almacen; print(almacen.estado())"
```

Tiene que decir `remoto: True` y la cantidad de tickers que ves en el Panel. Si
dice `False`, alguno de los dos valores está vacío o mal pegado.

### 1. El token de tu suscripción

El diagnóstico corre como **Claude Code**, no contra la API, así que sale de tu
plan Pro y no de una factura aparte. Desde una terminal:

```bash
claude setup-token
```

Genera un token de larga duración atado a tu suscripción. Copialo: es el valor
del secreto `CLAUDE_CODE_OAUTH_TOKEN`.

> No hace falta instalar la GitHub App de Claude. El workflow le pasa el
> `GITHUB_TOKEN` propio de la Action, porque este paso no comenta ni commitea
> nada: solo lee un archivo, busca en la web y escribe JSON en el runner.

### 2. Los tres secretos en GitHub

En **https://github.com/leandrocescato/analizador-acciones** → *Settings* →
*Secrets and variables* → *Actions* → **New repository secret**:

| Nombre | Qué va | Falta si... |
|---|---|---|
| `GIST_TOKEN` | El token fine-grained con permiso de Gists | La Action no tiene dónde escribir |
| `GIST_ID` | El tramo final de la URL del Gist | Lo mismo |
| `CLAUDE_CODE_OAUTH_TOKEN` | Lo que devolvió `claude setup-token` | Las candidatas llegan sin el párrafo |

Los nombres tienen que ser **exactamente** esos: son los que lee
`.github/workflows/radar.yml`.

> `GIST_TOKEN` no es el `GITHUB_TOKEN` que la Action tiene sola. Ese sirve para
> el repositorio y **no puede escribir gists**: es el error que hace que todo
> parezca andar y el Gist nunca cambie.

### 3. La primera corrida, a mano

*Actions* → **Radar diario** → *Run workflow*. Marcá **sin_diagnostico** la
primera vez: confirma que el Gist se escribe sin gastar nada de cuota. Si el log
termina en `Guardado en gist privado`, ya está. Sacale la marca y corré de nuevo
para ver los diagnósticos.

De ahí en más sale solo a las **7 de la mañana**, de martes a sábado (cada
corrida mira el cierre del día hábil anterior).

> GitHub apaga los `cron` de un repositorio público que pase 60 días sin
> actividad. Si un día el radar deja de actualizarse solo, es lo primero a
> revisar.

---

## Los filtros

Se editan en la barra lateral de la hoja Radar y se guardan en el mismo Gist,
así que **la corrida de esa noche usa lo que dejaste puesto**. No hay que tocar
código ni volver a desplegar nada.

El preset de fábrica es deep value castigado:

| Filtro | Valor | Por qué |
|---|---|---|
| PER | entre 1 y 14 | El corte de "barata". Debajo de 1 casi siempre es una ganancia extraordinaria |
| EPS diluido | > 0 | Sin ganancia el PER no significa nada |
| ROE | > 8% | Separa la barata de la que rinde poco por naturaleza |
| Deuda / EBITDA | < 3,5x | Arriba de eso decide la tasa, no el negocio |
| Variación 52 semanas | < 0% | El disparador contrarian |
| Capitalización | > USD 300M | Debajo el precio no es referencia |
| Volumen 3 meses | > 200.000 | Que se pueda comprar y vender |

Hay seis filtros más apagados (P/VL, ROIC, Altman Z, liquidez corriente,
EV/EBIT, dividendo) para apretar cuando entren demasiadas. Con el preset actual
pasan unas 70 por día; agregando `Altman Z > 3` y `Variación 52s < -25%` bajan a
diez o quince.

**Un filtro en blanco está apagado.** Vaciar la casilla es como sacarlo.

---

## Qué cuesta

**Nada por encima de la suscripción.** Es una regla de la herramienta, no una
intención: está sostenida en el código y en el workflow.

| Dónde | Con qué se autentica | Puede facturar aparte |
|---|---|---|
| La Action diaria | `CLAUDE_CODE_OAUTH_TOKEN` | **No.** El workflow no recibe ninguna `ANTHROPIC_API_KEY` ni instala el paquete `anthropic`: no tiene con qué |
| El botón de la app | El comando `claude`, con tu sesión | **No.** No existe otro camino en el código |

**No hay ningún camino por la API de Anthropic.** Hubo uno, apagado con llave:
no se encendía solo por tener una `ANTHROPIC_API_KEY` en el entorno, había que
pedirlo a mano. Funcionaba, y aun así se sacó. Un seguro que hay que revisar es
peor que no tener nada que asegurar: mientras el código exista, alguna
combinación de variables de entorno puede llegar a él. Si no está el comando
`claude`, no hay diagnóstico — el barrido guarda las candidatas sin párrafo y lo
dice. Hay un test que falla si alguien vuelve a agregarlo.

Lo que sí consumís es **cuota de uso del Pro**, la misma de tus sesiones de
Claude Code. Cuando se agota, esperás al reset; no se convierte en un cargo.

Claude Code informa cada corrida con un número en dólares (`total_cost_usd`) y
la app lo guarda en el campo `costo`. **Ese número no es una factura**: es lo que
esa misma llamada habría costado por API, y sirve para una cosa sola, que es
tener una vara de cuánta cuota consume cada candidata. Medido sobre tres
corridas reales con Opus 5 y búsqueda web: QFIN 0,52 · DEC 0,92 · TREE 1,04, dos
a tres minutos cada una. Léelo como "TREE consume el doble que QFIN", nunca como
un peso a pagar.

Por eso el tope por corrida arranca en **8**, no en quince. Si querés medir el
impacto sobre tu propio uso antes de soltarlo, arrancá en **3** las primeras
corridas y subilo cuando veas que no te aprieta.

La cuenta que importa es esta:

- **La primera semana es la cara.** Hoy hay ~70 candidatas sin diagnosticar; a 8
  por día, nueve días para ponerse al día.
- **Después es barato.** En régimen entran dos a cinco nuevas por día, porque
  las que ya estaban conservan su párrafo.

Tres frenos, por si algún día el filtro se afloja de más:

- `--max-diagnosticos` (8 por corrida) es un tope duro.
- El diagnóstico se pide una vez por empresa y no se repite.
- Correr con `sin_diagnostico` marcado no gasta nada.

Para gastar bastante menos por llamada, cambiá `MODELO` en `app/diagnostico.py`
a `claude-sonnet-5`.

### Dos cosas que el código no controla

1. **Que no tengas activado el uso extra / pago por uso** en tu cuenta de
   Anthropic. Con eso apagado, cuando se agota la cuota del Pro la corrida
   simplemente falla y las candidatas quedan sin párrafo hasta el reset. Con eso
   prendido, podría seguir andando y facturarte. Revisalo una vez.
2. **Los minutos de GitHub Actions**, que son de GitHub, no de Anthropic. En un
   repositorio público son gratis; en uno privado tenés 2000 minutos por mes en
   el plan gratis y esta corrida usa del orden de 5 a 15 por día — unos 110 a
   330 al mes, bien adentro del tope.

---

## Las tres salidas de una candidata

Tocando una fila se abre su ficha, con el diagnóstico y tres botones. La cuarta
opción es no hacer nada, y esa también está prevista: la candidata se queda con
su contador de días en el radar.

- **Al universo** — la suma a tu lista y la saca del radar. Desde ahí es una
  empresa más del Panel, con sus números de EDGAR.
- **Ver en el Detalle** — la analiza a fondo sin sumarla. Es el paso natural
  cuando el diagnóstico dice "hecho puntual" y querés ver si el balance aguanta.
- **Descartar** — no vuelve a aparecer nunca. El campo del motivo es opcional,
  pero dentro de un año, cuando la veas cotizando al triple, vas a querer saber
  qué pensabas hoy.

Lo descartado se rehabilita desde la barra lateral.

---

## Si algo no anda

| Síntoma | Causa y solución |
|---|---|
| El Radar aparece vacío en la app | La app no está leyendo el Gist. Te falta `.streamlit/secrets.toml` con `github_token` y `gist_id`. Mientras tanto, **Barrer ahora** trabaja contra el archivo local |
| La Action dice OK pero el Gist no cambia | El `GIST_TOKEN` no tiene el permiso **Account → Gists → Read and write**, o venció |
| Las candidatas llegan sin párrafo | Falta `CLAUDE_CODE_OAUTH_TOKEN`, o el token venció, o se te acabó la cuota del plan. El log del paso 2 lo dice. Es el modo de falla buscado: antes que gastar de más, no escribe |
| **La columna Causa está vacía en TODAS** | El diagnóstico no corrió nunca. La página te lo dice con todas las letras cuando pasa. O te faltan los tres secretos del paso 2, o corriste el workflow con `sin_diagnostico` tildado. Para llenarla ahora: panel *Diagnóstico* de la barra lateral |
| Una sola fila sin Causa | Normal: a esa todavía no le tocó. El tope por corrida es 8 |
| El paso 2 falla por autenticación | Probá el token localmente con `claude` antes de debuggear el workflow. Si igual falla, instalá la [GitHub App de Claude](https://github.com/apps/claude) y sacá la línea `github_token` |
| Se diagnostican menos de las que esperabas | Es el tope de 8 por corrida. Subilo en *Run workflow* o en el `default` del workflow |
| Entran demasiadas candidatas | Apretá el filtro: Altman Z > 3, o variación 52 semanas < -25% |
| No entra ninguna | Lo contrario, y suele ser el PER: un mercado caro deja pocas debajo de 14. Probalo en 18 |
| El screener de Yahoo no contesta | Pasa: rechaza cuando le entran muchos pedidos juntos. La corrida siguiente se cura sola |

---

## Correrlo a mano desde la laptop

```bash
python scripts/radar_diario.py --sin-diagnostico
```

Sin nada configurado escribe `datos/radar.json` y la app lo lee de ahí. Es la
forma de probar un filtro nuevo sin esperar a mañana — aunque para eso alcanza
el botón **Barrer ahora** de la barra lateral.

Con diagnóstico, y usando tu suscripción igual que en la nube:

```bash
python scripts/radar_diario.py --max-diagnosticos 3
```

Busca el comando `claude` en el PATH y lo corre en modo no interactivo, en un
directorio temporal para no arrastrarle el `CLAUDE.md` de este proyecto. Si no
lo encuentra, guarda las candidatas sin párrafo y lo dice: no hay un segundo
motor al que caer.
