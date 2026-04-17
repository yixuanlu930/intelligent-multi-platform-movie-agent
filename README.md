# Agente Inteligente de Peliculas - IMDB Multi-Frontend

Agente inteligente que extrae informacion de peliculas desde IMDB y la cartelera de cine de Madrid, con multiples interfaces: linea de comandos (CLI), Alexa Skill, interfaz web y bot de Telegram. Integra un LLM open source (Qwen 2.5 via Ollama) para generar respuestas en lenguaje natural.

**Asignatura:** Sistemas Inteligentes II  
**Profesor:** Francisco Serradilla

---

## Estructura del proyecto

```
.
├── movie_scraper.py              # Scraper de IMDB + CLI principal
├── cartelera_scraper.py          # Scraper de cartelera de Madrid (ecartelera.com)
├── alexa_lambda.py               # Lambda de Alexa Skill
├── alexa_interaction_model.json  # Modelo de interaccion para Alexa Developer Console
├── telegram_bot.py               # Bot de Telegram
├── web_app.py                    # Interfaz web (Flask)
├── templates/
│   └── index.html                # Plantilla HTML de la web
├── config.py                     # Configuracion centralizada (tokens, modelo LLM, etc.)
├── user_profile.json             # Perfil de usuario para filtrado por genero/director
├── cron_cartelera.sh             # Script para ejecucion automatica via cron
├── requirements.txt              # Dependencias Python
└── README.md
```

---

## Requisitos previos

- **Python 3.10+**
- **Ollama** (para el LLM open source)

### Instalacion de dependencias

```bash
pip install -r requirements.txt
```

### Instalacion de Ollama y modelo Qwen

```bash
# Instalar Ollama
curl -fsSL https://ollama.ai/install.sh | sh

# Descargar el modelo (Qwen 2.5 3B, ~1.9 GB)
ollama pull qwen2.5:3b
```

> Si tu maquina tiene poca RAM (<8 GB), puedes usar `qwen2.5:1.5b` en su lugar y cambiar el modelo en `config.py`.

---

## 1. Scraper de peliculas (CLI)

`movie_scraper.py` busca cualquier pelicula en IMDB y devuelve: titulo, nota, votos, sinopsis, director, duracion, genero, ano y poster. Los resultados se cachean en `movie_cache.json` para no repetir consultas.

### Uso basico

```bash
# Informacion completa de una pelicula
python movie_scraper.py "The Matrix"

# Solo un campo especifico
python movie_scraper.py "Inception" --campo nota

# Varios campos
python movie_scraper.py "Pulp Fiction" --campo nota --campo director

# Salida en formato JSON
python movie_scraper.py "2001" --formato json

# Forzar consulta sin cache
python movie_scraper.py "Interstellar" --no-cache
```

### Campos disponibles

`titulo`, `titulo_original`, `año`, `nota`, `votos`, `sinopsis`, `director`, `duracion`, `genero`, `poster`, `imdb_id`, `imdb_url`

### Ejemplo de salida

```
==================================================
  The Matrix (1999)
==================================================
  Titulo: The Matrix
  Titulo Original: The Matrix
  Ano: 1999
  Nota IMDB: 8.7/10
  Votos: 2,241,297
  Director: Lana Wachowski, Lilly Wachowski
  Duracion: 2h 16m
  Genero: Action, Sci-Fi
  Sinopsis: When a beautiful stranger leads computer hacker Neo to...
  IMDB: https://www.imdb.com/title/tt0133093/
```

---

## 2. Scraper de cartelera de Madrid

`cartelera_scraper.py` obtiene las peliculas en cartelera de 7 cines de Madrid desde ecartelera.com, las enriquece con datos de IMDB y opcionalmente filtra por el perfil del usuario.

### Uso

```bash
# Cartelera basica (sin datos IMDB, rapido)
python cartelera_scraper.py --no-imdb

# Cartelera con datos de IMDB
python cartelera_scraper.py

# Cartelera filtrada por perfil de usuario
python cartelera_scraper.py --filtrar

# Salida en JSON
python cartelera_scraper.py --formato json

# Enviar por Telegram
python cartelera_scraper.py --filtrar --telegram
```

### Perfil de usuario (`user_profile.json`)

El filtro usa un perfil donde defines la nota minima por genero y tus directores favoritos (siempre pasan el filtro):

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

Ejemplo: una pelicula de Sci-Fi con nota 8.0 pasa el filtro (8.0 > 6.0). Una comedia con nota 5.0 no pasa (5.0 < 6.0). Cualquier pelicula de Tarantino pasa siempre.

### Ejecucion automatica con cron

Para que se ejecute cada lunes a las 9:00 y envie el resultado por Telegram:

```bash
# Dar permisos al script
chmod +x cron_cartelera.sh

# Editar crontab
crontab -e

# Anadir esta linea (ajustar la ruta):
0 9 * * 1 /ruta/completa/al/proyecto/cron_cartelera.sh
```

---

## 3. Alexa Skill

`alexa_lambda.py` es la funcion Lambda para un Alexa Skill que responde preguntas sobre peliculas.

### Intents disponibles

| Intent | Ejemplo de frase |
|---|---|
| GetRatingIntent | "Cual es la nota de Inception" |
| GetDirectorIntent | "Quien dirigio The Matrix" |
| GetDurationIntent | "Cuanto dura Interstellar" |
| GetSynopsisIntent | "De que va Pulp Fiction" |
| GetVotesIntent | "Cuantos votos tiene El Padrino" |
| GetGenreIntent | "Que genero es Blade Runner" |
| GetAllInfoIntent | "Dime todo sobre 2001" |

### Despliegue

1. Ir a [Alexa Developer Console](https://developer.amazon.com/alexa/console/ask)
2. Crear un nuevo Skill (Custom, Python)
3. En **Interaction Model > JSON Editor**, importar `alexa_interaction_model.json`
4. En **Code**, subir `alexa_lambda.py`, `movie_scraper.py` y `config.py`
5. Instalar dependencias en el entorno Lambda (`requirements.txt`)
6. Build y Test en la consola

---

## 4. Bot de Telegram

`telegram_bot.py` es un bot interactivo que responde consultas sobre peliculas y muestra la cartelera. Integra el LLM Qwen para generar comentarios personalizados.

### Configuracion

1. Hablar con [@BotFather](https://t.me/BotFather) en Telegram
2. Crear un bot con `/newbot` y copiar el token
3. Pegar el token en `config.py`:
   ```python
   TELEGRAM_BOT_TOKEN = "1234567890:ABCdefGHIjklMNOpqrsTUVwxyz"
   ```
4. Para envio automatico de cartelera, anadir tambien `TELEGRAM_CHAT_ID`

### Ejecutar

```bash
python telegram_bot.py
```

### Comandos del bot

| Comando | Descripcion |
|---|---|
| `/start` | Bienvenida y ayuda |
| `/pelicula <nombre>` | Informacion completa de una pelicula |
| `/nota <nombre>` | Nota IMDB |
| `/director <nombre>` | Director |
| `/duracion <nombre>` | Duracion |
| `/sinopsis <nombre>` | Sinopsis |
| `/cartelera` | Cartelera de Madrid con notas IMDB |
| `/perfil` | Ver perfil de filtrado |

Tambien responde a **mensajes de texto libre**: si escribes el nombre de una pelicula directamente, te devuelve su informacion.

---

## 5. Interfaz Web

`web_app.py` es una aplicacion Flask con buscador de peliculas y cartelera de Madrid.

### Ejecutar

```bash
python web_app.py
```

Abrir http://localhost:5000 en el navegador.

### Funcionalidades

- **Buscador**: escribe el nombre de una pelicula y obtiene todos sus datos con poster
- **Filtro por campo**: selecciona solo el dato que te interesa (nota, director, etc.)
- **Cartelera de Madrid**: listado de peliculas en cartelera con notas IMDB
- **Cartelera filtrada**: aplica el perfil de usuario al listado

### API REST

La web tambien expone endpoints JSON:

```bash
# Info de una pelicula
curl http://localhost:5000/api/pelicula/Inception

# Cartelera completa
curl http://localhost:5000/api/cartelera
```

---

## Configuracion (`config.py`)

Toda la configuracion esta centralizada en `config.py`:

| Variable | Descripcion |
|---|---|
| `TELEGRAM_BOT_TOKEN` | Token del bot de Telegram (de @BotFather) |
| `TELEGRAM_CHAT_ID` | Chat ID para envio automatico de cartelera |
| `OLLAMA_MODEL` | Modelo LLM a usar (por defecto `qwen2.5:3b`) |
| `OLLAMA_URL` | URL del servidor Ollama (por defecto `http://localhost:11434`) |
| `CACHE_FILE` | Fichero de cache de peliculas |
| `FLASK_PORT` | Puerto de la app web (por defecto 5000) |

---

## Tecnologias utilizadas

- **Scraping**: requests + BeautifulSoup (ecartelera.com), IMDB Suggestion API + GraphQL API
- **LLM**: Ollama + Qwen 2.5 3B (open source, ejecucion local)
- **Web**: Flask + HTML/CSS
- **Telegram**: python-telegram-bot
- **Alexa**: ASK SDK for Python (ask-sdk-core)
- **Automatizacion**: cron (Linux)
