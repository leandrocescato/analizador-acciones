# Poner el Analizador en internet

Para entrar desde el teléfono sin depender de que la laptop esté prendida.
Todo lo que sigue es gratis.

Son cuatro pasos y unos 20 minutos. El orden importa: el paso 1 es el que
protege tus datos, y conviene hacerlo antes de subir nada.

---

## 1. El Gist privado, donde van a vivir tus datos

Streamlit Community Cloud **borra el disco cada vez que reinicia**, y reinicia
solo cuando la app queda un rato sin uso. Si los tickers y tus tesis vivieran en
un archivo, se perderían. Por eso van a un Gist privado de GitHub.

1. Andá a **https://gist.github.com**
2. Nombre de archivo: `universo.json`
3. Contenido: `[]`
4. Botón **Create secret gist** — *secret*, no público
5. De la URL que queda, copiá el último tramo. Ese es tu `gist_id`:
   `https://gist.github.com/leandro/`**`a1b2c3d4e5f6...`**

Ahora el token para que la app pueda escribir ahí:

1. **https://github.com/settings/tokens** → *Fine-grained tokens* → *Generate*
2. **Token name**: `analizador-acciones`. Expiración: la que quieras — si vence,
   la app avisa en la barra lateral y lo regenerás
3. **Repository access** → **Public repositories**. Este token es solo para el
   Gist; el código lo vas a subir con tus credenciales normales de git
4. **Permissions** → *Add permissions* → pestaña **Account** → **Gists** →
   *Read and write*

   > Ojo acá: **Gists no está entre los permisos de "Repositories"**, está en
   > "Account". Es donde todo el mundo se traba.

5. Que quede con **0 permisos de repositorio y 1 de cuenta**. Así el token no
   puede tocar tu código ni aunque se filtre
6. Copiá el token: se muestra **una sola vez**. Empieza con `github_pat_`

> Es privado a propósito. El repositorio del código va a ser público —es la
> condición del plan gratuito—, pero tus tesis y tu lista de empresas no tienen
> por qué serlo.

---

## 2. Subir el código a GitHub

Desde una terminal en la carpeta del proyecto:

```bash
git init && git add . && git commit -m "Analizador de acciones"
```

Antes de seguir, **verificá que tus datos no entraron**:

```bash
git ls-files | findstr datos
```

Eso no tiene que devolver nada. `datos/` está en `.gitignore`: ahí viven tu
`cache.db` con las tesis y el historial, y tu `universo.txt`. Si aparece algo,
pará y avisame.

Después creá un repositorio en GitHub y subilo. **Cambiá `TU-USUARIO` por el
tuyo** antes de pegar:

```bash
git branch -M main
```

```bash
git remote add origin https://github.com/TU-USUARIO/analizador-acciones.git
```

```bash
git push -u origin main
```

Si `git remote add` responde *"remote origin already exists"*, es que ya había
uno configurado. No lo agregues de nuevo: corregí el que está.

```bash
git remote set-url origin https://github.com/TU-USUARIO/analizador-acciones.git
```

---

## 3. Desplegar

1. **https://share.streamlit.io** → entrá con GitHub → **New app**
2. Elegí el repositorio, rama `main`, archivo principal `Analizador.py`
3. Antes de darle *Deploy*, entrá a **Advanced settings → Secrets** y pegá:

```toml
clave_acceso = "una-clave-larga-que-te-acuerdes"
email_sec = "leandro.cescato@gmail.com"
github_token = "github_pat_..."
gist_id = "a1b2c3d4e5f6..."
```

4. **Deploy**

La URL queda tipo `https://analizador-acciones.streamlit.app`. Abrila en el
teléfono y agregala a la pantalla de inicio: se comporta como una app.

---

## 4. Cargar tus tickers una vez

La primera vez el Gist está vacío y la app arranca con seis tickers de ejemplo.
Cargá los tuyos desde la barra lateral y **guardá**: quedan en el Gist y ya no
se pierden nunca más, ni cuando la app reinicie ni cuando cambies de teléfono.

---

## Lo que tenés que saber de esta modalidad

**El primer arranque después de un rato es lento.** Cuando la app estuvo
inactiva, Streamlit la apaga; al volver, el caché está vacío y hay que bajar de
nuevo los estados contables de cada empresa desde EDGAR. Con 30 tickers son
varios minutos. Mientras la usás seguido, es instantánea.

**Cuantos más tickers, peor ese primer arranque.** Con 200 empresas el arranque
en frío se vuelve impracticable. Si querés un universo grande, conviene la otra
modalidad: el túnel privado contra tu laptop, donde el caché de 11 MB y los
2.850 snapshots que ya tenés siguen ahí.

**El historial de mediciones no se guarda afuera.** Los snapshots quedan en el
disco efímero y se pierden en cada reinicio; se reconstruyen solos a medida que
abrís empresas. Es información derivada. Tus tesis, que no se pueden
reconstruir, sí van al Gist.

**La SEC limita por dirección IP.** En la nube esa IP es compartida con otras
aplicaciones, así que a veces frena los pedidos aunque vos no hayas hecho nada.
La app reintenta con espera creciente y, si no cede, lo dice con todas las
letras en vez de mostrar una ficha vacía.

**La app queda en internet con una clave compartida.** No es un sistema de
usuarios: es un portón para que no entre cualquiera que pase con la URL. Poné
una clave larga y no la reutilices de otro lado.

---

## Si preferís la otra opción más adelante

Con **Tailscale** (gratis) instalás la app en la laptop y en el teléfono, y
entrás desde cualquier lado como si estuvieras en tu red. La laptop tiene que
estar prendida, pero a cambio: nada sale de tu máquina, no hay arranque en frío,
no hay límite de la SEC compartido, y el universo puede ser tan grande como
quieras. El código ya está preparado para las dos: `.streamlit/config.toml`
escucha en todas las interfaces, y sin secretos configurados la app usa los
archivos locales sin pedir clave.
