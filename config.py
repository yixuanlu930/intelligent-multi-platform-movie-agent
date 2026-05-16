"""
Configuracion centralizada del proyecto Agente Inteligente de Peliculas.
Editar las variables segun tu entorno.
"""

# --- Telegram ---
TELEGRAM_BOT_TOKEN = "TU_TOKEN_AQUI"  # Obtener de @BotFather en Telegram
TELEGRAM_CHAT_ID = "TU_CHAT_ID_AQUI"  # Chat ID para envio automatico de cartelera

# --- LLM Open Source (Ollama) ---
OLLAMA_URL = "http://172.17.240.1:11434" # http://localhost:11434 si Ollama se ejecuta en la misma máquina
OLLAMA_MODEL = "qwen2.5:1.5b"  # Modelo a usar: qwen2.5:1.5b (2GB RAM, buena calidad)

# --- Alternativa: Groq API (LLM en la nube, gratis) ---
GROQ_API_KEY = ""  # Obtener en console.groq.com (gratis)
GROQ_MODEL = "llama-3.3-70b-versatile"

# --- Scraping ---
IMDB_BASE_URL = "https://www.imdb.com"
ECARTELERA_URL = "https://www.ecartelera.com"
REQUEST_HEADERS = {
    "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
                  "(KHTML, like Gecko) Chrome/131.0.0.0 Safari/537.36",
    "Accept-Language": "es-ES,es;q=0.9,en;q=0.8",
    "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
}

# --- Cache ---
CACHE_FILE = "movie_cache.json"

# --- Perfil de usuario ---
USER_PROFILE_FILE = "user_profile.json"

# --- Web App ---
FLASK_HOST = "0.0.0.0" 
FLASK_PORT = 5000
FLASK_DEBUG = True
