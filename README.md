# Agente Inteligente para Peliculas — Multi-Frontend

**Asignatura:** Sistemas Inteligentes II  
**Profesor:** Francisco Serradilla  

---

## 1. Descripcion del proyecto

Este proyecto implementa un **Agente Inteligente** capaz de extraer, procesar y servir informacion de peliculas mediante **web scraping** (BeautifulSoup + requests) e integra un **LLM open source** (Qwen 2.5, ejecutado localmente con Ollama) para generar respuestas en lenguaje natural.

El agente ofrece **cuatro interfaces de usuario** (frontends):

1. **CLI** (linea de comandos) — consulta directa desde terminal
2. **Alexa Skill** — asistente de voz via Amazon Alexa
3. **Interfaz Web** — aplicacion Flask con buscador y cartelera
4. **Bot de Telegram** — bot conversacional con comandos y texto libre

Ademas incluye un **scraper de la cartelera de cine de Madrid** que se ejecuta automaticamente cada lunes a las 9:00 via cron, filtra las peliculas segun un perfil de preferencias del usuario, y envia el resultado por Telegram.

---

## 2. Arquitectura del sistema

```
                         ┌──────────────────┐
                         │   Usuario final   │
                         └────────┬─────────┘
                  ┌───────────────┼───────────────┐
                  │               │               │
           ┌──────▼──────┐ ┌─────▼──────┐ ┌──────▼──────┐
           │  Alexa Skill │ │  Telegram  │ │  Web Flask  │
           │  (Lambda)    │ │  Bot       │ │  (HTML/CSS) │
           └──────┬──────┘ └─────┬──────┘ └──────┬──────┘
                  │               │               │
                  └───────────────┼───────────────┘
                                  │
                    ┌─────────────▼─────────────┐
                    │       movie_scraper.py     │
                    │  (modulo central reusable) │
                    └─────────────┬─────────────┘
                                  │
                   ┌──────────────┼──────────────┐
                   │                             │
          ┌────────▼────────┐          ┌─────────▼─────────┐
          │  SensaCine.com  │          │   eCartelera.com   │
          │  (scraping HTML │          │   (scraping HTML   │
          │  de peliculas)  │          │   cartelera Madrid)│
          └─────────────────┘          └───────────────────┘

                    ┌─────────────────────────┐
                    │  Ollama + Qwen 2.5 3B   │
                    │  (LLM local open source)│
                    └─────────────────────────┘
```

Todos los frontends reutilizan el mismo modulo `movie_scraper.py`, que es el nucleo del agente. La cache local (`movie_cache.json`) evita repetir consultas web.

---

## 3. Estructura de ficheros

```
.
├── movie_scraper.py              # Scraper principal (SensaCine) + CLI
├── cartelera_scraper.py          # Scraper de cartelera de Madrid (eCartelera)
├── alexa_lambda.py               # Funcion Lambda para Alexa Skill
├── alexa_interaction_model.json  # Modelo de interaccion JSON para Alexa
├── telegram_bot.py               # Bot de Telegram
├── web_app.py                    # Aplicacion web Flask
├── templates/
│   └── index.html                # Plantilla HTML (frontend web)
├── config.py                     # Configuracion centralizada
├── user_profile.json             # Perfil del usuario (filtrado por genero/director)
├── cron_cartelera.sh             # Script bash para ejecucion automatica con cron
├── requirements.txt              # Dependencias Python
├── movie_cache.json              # Cache local de peliculas (generado automaticamente)
└── README.md
```

---

## 4. Tecnologias utilizadas

| Tecnologia | Uso | Justificacion |
|---|---|---|
| **Python 3.12** | Lenguaje principal | Ecosistema rico para scraping, bots y web |
| **BeautifulSoup 4** + **lxml** | Parseado de HTML | Scraping robusto de paginas web |
| **requests** | Peticiones HTTP | Descargar paginas para scraping |
| **Flask** | Interfaz web | Framework ligero, ideal para prototipos rapidos |
| **python-telegram-bot** | Bot de Telegram | Libreria oficial, asincrona, bien documentada |
| **ask-sdk-core** | Alexa Skill | SDK oficial de Amazon para skills en Python |
| **Ollama** + **Qwen 2.5 3B** | LLM open source local | Ejecucion sin cloud, privacidad, sin coste |
| **cron** (Linux) | Automatizacion semanal | Estandar Unix para tareas programadas |

---

## 5. Funcionamiento detallado de cada componente

### 5.1. Scraper de peliculas (`movie_scraper.py`)

**Fuente de datos:** SensaCine.com (web scraping con BeautifulSoup, sin APIs)

**Campos extraidos:** titulo, titulo original, ano, nota, numero de votos, sinopsis, director, duracion, genero, poster, URL.

#### Como funciona el scraping paso a paso

El proceso de obtener la informacion de una pelicula tiene **dos fases de scraping**:

**Fase 1 — Busqueda (scraping de la pagina de resultados):**

1. Se hace una peticion `GET` a `https://www.sensacine.com/buscar/?q=<titulo>`
2. Se parsea el HTML descargado (~75 KB) con `BeautifulSoup`
3. Se localizan los `<div class="entity-card">` que representan cada resultado
4. Dentro de cada tarjeta, se lee el atributo `data-entity-id` de un `<div>` interno
5. Este atributo contiene el ID codificado en base64 (ej: `TW92aWU6MTk3NzY=`)
6. Se decodifica: `"Movie:19776"` → ID numerico `19776`
7. Se construye la URL de la ficha: `/peliculas/pelicula-19776/`

**Fase 2 — Ficha de la pelicula (scraping de la pagina de detalle):**

1. Se hace `GET` a `https://www.sensacine.com/peliculas/pelicula-19776/`
2. Se parsea el HTML completo (~300 KB) con `BeautifulSoup`
3. Se extrae el bloque `<script type="application/ld+json">` embebido en la pagina, que contiene datos estructurados (Schema.org): titulo, sinopsis, directores, generos, duracion, poster, nota agregada y votos
4. Se scrapean campos adicionales directamente de elementos HTML:
   - `<div class="rating-item-content">` para la nota y estrellas
   - `<div class="meta-body-item">` para el ano, titulo original, reparto
5. Se construye el diccionario final con todos los campos

**Cache:** los resultados se guardan en `movie_cache.json`. Si se consulta la misma pelicula otra vez, se devuelve directamente del fichero sin hacer peticiones web.

#### Ejemplo de ejecucion

```
$ python movie_scraper.py "The Matrix" --no-cache

  [SCRAPING] GET https://www.sensacine.com/buscar/?q=The%20Matrix
  [SCRAPING] Parseando HTML... 7 resultados encontrados
  [SCRAPING] Resultado: 'Matrix' -> ID 19776
  [SCRAPING] GET https://www.sensacine.com/peliculas/pelicula-19776/
  [SCRAPING] Parseando HTML de la ficha (297,916 bytes)...
  [SCRAPING] JSON-LD extraido del HTML
  [SCRAPING] Datos extraidos: Matrix (1999) - Nota: 4.3/5

==================================================
  Matrix (1999)
==================================================
  Titulo: Matrix
  Titulo Original: The Matrix
  Ano: 1999
  Nota SensaCine: 4.3/5
  Votos: 6,455
  Director: Lana Wachowski, Lilly Wachowski
  Duracion: 2h 15min
  Genero: Accion, Ciencia ficcion
  Sinopsis: Neo (Keanu Reeves) es un joven pirata informatico...
  URL: https://www.sensacine.com/peliculas/pelicula-19776/
```

#### Opciones de la CLI

```bash
python movie_scraper.py "Inception"                          # Info completa
python movie_scraper.py "Inception" --campo nota             # Solo la nota
python movie_scraper.py "Inception" --campo nota --campo director  # Nota y director
python movie_scraper.py "El Padrino" --formato json          # Salida JSON
python movie_scraper.py "Interstellar" --no-cache            # Sin cache
```

**Campos disponibles:** `titulo`, `titulo_original`, `año`, `nota`, `votos`, `sinopsis`, `director`, `duracion`, `genero`, `poster`, `url`

---

### 5.2. Scraper de cartelera de Madrid (`cartelera_scraper.py`)

**Fuente de datos:** eCartelera.com (web scraping con BeautifulSoup)

#### Como funciona el scraping paso a paso

1. Se recorren **7 cines grandes de Madrid** (Yelmo Ideal, Callao, Cinesa Proyecciones, Cines Princesa, Palacio de la Prensa, Renoir Plaza de Espana, Cinesa Principe Pio)
2. Para cada cine, se hace `GET` a su pagina en eCartelera (ej: `https://www.ecartelera.com/cines/54,0,1.html`)
3. Se parsea el HTML y se localizan los `<div class="titem">` (cada pelicula en cartelera)
4. De cada bloque se extrae scrapeando el HTML:
   - `<p class="tit">` → titulo y enlace
   - `<p class="data">` → duracion, pais, genero, clasificacion
   - `<p class="dir">` → director
   - `<span class="nota">` → nota de eCartelera
   - `<div class="sessions">` → horarios de las sesiones
5. Se **deduplican** peliculas (si una pelicula esta en varios cines, se agrupan sus horarios)
6. Se **enriquece** cada pelicula con datos de SensaCine (nota, sinopsis, generos) usando `movie_scraper.get_movie_info()`
7. Se aplica el **filtro por perfil de usuario** (opcional)
8. Se ordena por nota descendente

#### Filtrado por perfil de usuario

El fichero `user_profile.json` define las preferencias:

```json
{
  "genres": {
    "Sci-Fi": 6.0,
    "Drama": 7.0,
    "Comedy": 6.0,
    "Horror": 5.5
  },
  "favorite_directors": [
    "Christopher Nolan",
    "Quentin Tarantino",
    "Pedro Almodovar"
  ]
}
```

**Logica del filtro:**
- Si la pelicula es de un **director favorito** → pasa siempre
- Si el **genero** esta en el perfil → la nota debe superar el minimo configurado (ej: una Sci-Fi necesita > 6.0)
- Si el genero **no esta** en el perfil → necesita nota >= 7.0 para pasar
- Si la pelicula **no tiene nota** → no pasa

#### Ejecucion automatica con cron

El script `cron_cartelera.sh` se programa en crontab para ejecutarse cada lunes a las 9:00:

```bash
# Editar crontab
crontab -e

# Anadir esta linea:
0 9 * * 1 /ruta/completa/al/proyecto/cron_cartelera.sh
```

El script ejecuta el scraper con filtro y envio por Telegram automaticamente.

#### Opciones de la CLI

```bash
python cartelera_scraper.py                    # Cartelera completa con datos SensaCine
python cartelera_scraper.py --no-imdb          # Solo datos de eCartelera (rapido)
python cartelera_scraper.py --filtrar           # Aplicar filtro por perfil
python cartelera_scraper.py --formato json      # Salida JSON
python cartelera_scraper.py --filtrar --telegram  # Filtrar y enviar por Telegram
```

---

### 5.3. Alexa Skill (`alexa_lambda.py`)

Funcion Lambda de AWS que procesa las peticiones del Alexa Skill. Usa la libreria `ask-sdk-core`.

#### Intents implementados

Cada intent responde a una pregunta concreta sobre una pelicula. El slot `{movie}` es de tipo `AMAZON.Movie`:

| Intent | Ejemplos de frases (utterances) |
|---|---|
| **GetRatingIntent** | "Cual es la nota de {movie}", "Que nota tiene {movie}", "Puntuacion de {movie}" |
| **GetDirectorIntent** | "Quien dirigio {movie}", "Director de {movie}", "Quien hizo {movie}" |
| **GetDurationIntent** | "Cuanto dura {movie}", "Duracion de {movie}" |
| **GetSynopsisIntent** | "De que va {movie}", "De que trata {movie}", "Sinopsis de {movie}" |
| **GetVotesIntent** | "Cuantos votos tiene {movie}", "Numero de votos de {movie}" |
| **GetGenreIntent** | "Que genero es {movie}", "De que genero es {movie}" |
| **GetAllInfoIntent** | "Dime todo sobre {movie}", "Informacion de {movie}" |

#### Como funciona

1. El usuario activa el skill: *"Alexa, abre agente de peliculas"*
2. Alexa procesa el lenguaje natural y detecta el intent y el slot (nombre de la pelicula)
3. La Lambda recibe el intent, llama a `get_movie_info()` para scrapear SensaCine
4. Los datos se cachean en memoria para no repetir consultas en la misma sesion
5. Se construye la respuesta de voz y la tarjeta visual
6. Alexa lee la respuesta al usuario

#### Despliegue

1. Ir a [Alexa Developer Console](https://developer.amazon.com/alexa/console/ask)
2. Crear un Skill nuevo (Custom, Python, Alexa-hosted)
3. En **Build > Interaction Model > JSON Editor**, importar `alexa_interaction_model.json`
4. En **Code**, subir `alexa_lambda.py`, `movie_scraper.py` y `config.py`
5. Build Model y Deploy
6. Probar en la pestana Test

---

### 5.4. Bot de Telegram (`telegram_bot.py`)

Bot conversacional que responde consultas sobre peliculas y muestra la cartelera. Integra el LLM Qwen 2.5 para generar comentarios en lenguaje natural.

#### Comandos

| Comando | Que hace |
|---|---|
| `/start` | Muestra bienvenida y lista de comandos |
| `/pelicula <nombre>` | Informacion completa de la pelicula (titulo, nota, director, sinopsis...) |
| `/nota <nombre>` | Solo la nota |
| `/director <nombre>` | Solo el director |
| `/duracion <nombre>` | Solo la duracion |
| `/sinopsis <nombre>` | Solo la sinopsis |
| `/cartelera` | Cartelera de Madrid con notas y enlaces |
| `/perfil` | Muestra el perfil de filtrado actual |

Si el usuario escribe **texto libre** (sin comando), el bot lo interpreta como nombre de pelicula y busca la informacion.

#### Integracion con el LLM

Cuando el bot devuelve la ficha de una pelicula, llama a Ollama (Qwen 2.5 3B) para generar un **comentario o recomendacion** en lenguaje natural. Ejemplo:

> *"Interstellar es una pelicula epica de ciencia ficcion con efectos visuales impresionantes y una trama innovadora que vale la pena ver."*

Si Ollama no esta disponible, el bot funciona igualmente, solo sin el comentario generado.

#### Configuracion

1. Hablar con [@BotFather](https://t.me/BotFather) en Telegram y crear un bot
2. Copiar el token en `config.py`:
   ```python
   TELEGRAM_BOT_TOKEN = "1234567890:ABCdefGHIjklMNOpqrsTUVwxyz"
   ```
3. Ejecutar: `python telegram_bot.py`

---

### 5.5. Interfaz Web (`web_app.py`)

Aplicacion web Flask con tema oscuro (estilo cine).

#### Funcionalidades

- **Buscador de peliculas:** formulario donde escribes el nombre, muestra la ficha con poster, nota, director, sinopsis, etc.
- **Filtro por campo:** dropdown para seleccionar solo el dato que quieres (nota, director, duracion, sinopsis, genero, votos)
- **Cartelera de Madrid:** listado de todas las peliculas en cartelera con notas y enlaces a eCartelera y SensaCine
- **Cartelera filtrada:** aplica el perfil de usuario para mostrar solo las peliculas que cumplen los criterios
- **API REST:** endpoints JSON para integracion con otros sistemas

#### Ejecucion

```bash
python web_app.py
# Abrir http://localhost:5000
```

#### Endpoints API REST

| Endpoint | Metodo | Descripcion |
|---|---|---|
| `/` | GET | Pagina principal con buscador |
| `/buscar` | POST | Buscar pelicula (form: `pelicula`, `campo`) |
| `/cartelera` | GET | Cartelera de Madrid |
| `/cartelera?filtrar=true` | GET | Cartelera filtrada por perfil |
| `/api/pelicula/<nombre>` | GET | Info de pelicula en JSON |
| `/api/cartelera` | GET | Cartelera completa en JSON |

---

## 6. LLM Open Source: Qwen 2.5 3B con Ollama

El proyecto integra un modelo de lenguaje open source ejecutado **localmente** (sin depender de servicios en la nube).

### Modelo elegido

**Qwen 2.5 3B** (Alibaba, open source):
- 3 mil millones de parametros
- 1.9 GB en disco (cuantizado Q4)
- ~2 GB de RAM en ejecucion
- Soporta espanol e ingles
- Tiempo de respuesta: ~5 segundos en CPU ARM64

### Justificacion de la eleccion

El entorno de desarrollo es un portatil con CPU ARM (Snapdragon X), 7.5 GB de RAM y sin GPU dedicada. Se evaluo:

| Modelo | RAM necesaria | Viable | Calidad |
|---|---|---|---|
| Qwen 2.5 0.5B | ~400 MB | Si | Baja |
| Qwen 2.5 1.5B | ~1.2 GB | Si | Media |
| **Qwen 2.5 3B** | **~2 GB** | **Si** | **Buena** |
| Qwen 2.5 7B | ~4.7 GB | Justo | Alta |

El modelo de 3B ofrece el mejor equilibrio calidad/rendimiento para el hardware disponible.

### Uso en el proyecto

- **Telegram bot:** genera comentarios y recomendaciones sobre peliculas
- **Futuro:** puede extenderse a procesamiento de consultas en lenguaje natural ("que peliculas de terror buenas hay en cartelera?")

### Instalacion

```bash
curl -fsSL https://ollama.ai/install.sh | sh   # Instalar Ollama
ollama pull qwen2.5:1.5b                          # Descargar modelo
```

---

## 7. Configuracion (`config.py`)

Toda la configuracion esta centralizada en un unico fichero:

| Variable | Descripcion | Valor por defecto |
|---|---|---|
| `TELEGRAM_BOT_TOKEN` | Token del bot (de @BotFather) | `"TU_TOKEN_AQUI"` |
| `TELEGRAM_CHAT_ID` | Chat ID para envio automatico | `""` |
| `OLLAMA_URL` | URL del servidor Ollama | `"http://localhost:11434"` |
| `OLLAMA_MODEL` | Modelo LLM | `"qwen2.5:1.5b"` |
| `CACHE_FILE` | Fichero de cache de peliculas | `"movie_cache.json"` |
| `USER_PROFILE_FILE` | Fichero de perfil de usuario | `"user_profile.json"` |
| `FLASK_HOST` | Host de la app web | `"0.0.0.0"` |
| `FLASK_PORT` | Puerto de la app web | `5000` |
| `REQUEST_HEADERS` | Headers HTTP para scraping | User-Agent Chrome |

---

## 8. Instalacion y puesta en marcha

### Paso 1: Clonar el repositorio

```bash
git clone git@github.com:yixuanlu930/Intelligent-Movie-Agent-IMDB-Multi-Frontend-.git
cd Intelligent-Movie-Agent-IMDB-Multi-Frontend-
```

### Paso 2: Instalar dependencias Python

```bash
pip install -r requirements.txt
```

### Paso 3: Instalar Ollama y descargar el modelo

```bash
curl -fsSL https://ollama.ai/install.sh | sh
ollama pull qwen2.5:1.5b
```

### Paso 4: Probar el scraper

```bash
python movie_scraper.py "The Matrix"
python movie_scraper.py "El Padrino" --formato json
python cartelera_scraper.py --no-imdb
```

### Paso 5: (Opcional) Configurar Telegram

1. Crear bot con @BotFather en Telegram
2. Editar `config.py` con el token
3. Ejecutar: `python telegram_bot.py`

### Paso 6: (Opcional) Lanzar la web

```bash
python web_app.py
# Abrir http://localhost:5000
```

### Paso 7: (Opcional) Configurar cron

```bash
chmod +x cron_cartelera.sh
crontab -e
# Anadir: 0 9 * * 1 /ruta/completa/cron_cartelera.sh
```

---

## 9. Dependencias (`requirements.txt`)

```
requests>=2.31.0          # Peticiones HTTP para scraping
beautifulsoup4>=4.12.0    # Parseado de HTML
lxml>=5.0.0               # Parser rapido para BeautifulSoup
flask>=3.0.0              # Interfaz web
python-telegram-bot>=21.0 # Bot de Telegram
ask-sdk-core>=1.19.0      # Alexa Skill SDK
ollama>=0.4.0             # Cliente Python para Ollama (LLM)
```
