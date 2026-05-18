"""
Plantilla de configuracion. Copiala como config.py y rellena los campos.

  cp config.example.py config.py

config.py esta en .gitignore: NUNCA debe subirse al repositorio porque
contiene tokens y claves privadas.
"""

# --- Telegram ---
# Obtener token de @BotFather en Telegram (/newbot).
TELEGRAM_BOT_TOKEN = "TU_TOKEN_AQUI"
# Chat ID del usuario o grupo al que el bot enviara mensajes automaticos
# (cartelera semanal, conciertos favoritos, etc.).
# Para obtenerlo: hablar al bot y mirar el JSON de
# https://api.telegram.org/bot<TOKEN>/getUpdates → result[0].message.chat.id
TELEGRAM_CHAT_ID = ""

# --- LLM Open Source (Ollama) ---
# Instalar Ollama: https://ollama.com/download
# Levantar modelo: ollama pull qwen2.5:1.5b
OLLAMA_URL = "http://localhost:11434"
OLLAMA_MODEL = "qwen2.5:1.5b"

# --- Alternativa: Groq API (LLM en la nube, gratis) ---
# Obtener clave en console.groq.com
GROQ_API_KEY = ""
GROQ_MODEL = "llama-3.3-70b-versatile"

# --- Scraping ---
IMDB_BASE_URL = "https://www.imdb.com"
ECARTELERA_URL = "https://www.ecartelera.com"
WEGOW_API = "https://www.wegow.com/api/events?cities=3117735"  # 3117735 = ID de Madrid en Wegow

# Headers HTTP que simulan un navegador real para evitar bloqueos de los scrapers.
# Sin User-Agent algunos sitios devuelven 403 o contenido diferente.
# Accept-Language: es-ES garantiza que las paginas respondan en español.
REQUEST_HEADERS = {
    "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
                  "(KHTML, like Gecko) Chrome/131.0.0.0 Safari/537.36",
    "Accept-Language": "es-ES,es;q=0.9,en;q=0.8",
    "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
}

# --- Cache ---
# Fichero JSON donde se guardan las peliculas ya consultadas.
# Evita peticiones repetidas a SensaCine para la misma pelicula.
CACHE_FILE = "movie_cache.json"

# --- Perfil de usuario ---
# Fichero JSON con las preferencias del usuario: generos con nota minima,
# directores favoritos y artistas de musica favoritos.
USER_PROFILE_FILE = "user_profile.json"

# --- Web App ---
FLASK_HOST = "0.0.0.0"
FLASK_PORT = 5000
FLASK_DEBUG = True
