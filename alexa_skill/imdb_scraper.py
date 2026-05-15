"""
imdb_scraper.py
===============
Scraper de información de películas usando la API de OMDb (Open Movie Database).

Aunque el nombre del archivo hace referencia a IMDb, usamos OMDb como fuente
de datos porque ofrece una API REST estable, sin necesidad de hacer scraping
directo de HTML (lo que evita problemas de bloqueos y cambios de estructura).

Uso por línea de comandos (requisito de la práctica):
    python imdb_scraper.py "Inception"
    python imdb_scraper.py "El Padrino"

Requisito previo:
    Variable de entorno OMDB_API_KEY con una clave válida de https://www.omdbapi.com/apikey.aspx

Autores: Grupo XX - Práctica IA Agéntica
Asignatura: Agentes Inteligentes
"""

import logging
import os
import re
import unicodedata

import requests

# Configuramos el logger del módulo para depuración
logger = logging.getLogger(__name__)

# URL base de la API de OMDb
OMDB_URL = "https://www.omdbapi.com/"

# ---------------------------------------------------------------------------
# Tabla de alias: mapea títulos en español a sus equivalentes en inglés.
# OMDb indexa principalmente en inglés, por lo que sin estos alias muchas
# búsquedas de títulos españoles fallarían.
# ---------------------------------------------------------------------------
TITLE_ALIASES = {
    "origen": "Inception",
    "matrix": "The Matrix",
    "el padrino": "The Godfather",
    "el padrino 2": "The Godfather Part II",
    "el club de la lucha": "Fight Club",
    "2001 odisea en el espacio": "2001: A Space Odyssey",
    "el senor de los anillos": "The Lord of the Rings: The Fellowship of the Ring",
    "el señor de los anillos": "The Lord of the Rings: The Fellowship of the Ring",
    "el senor de los anillos la comunidad del anillo": "The Lord of the Rings: The Fellowship of the Ring",
    "el señor de los anillos la comunidad del anillo": "The Lord of the Rings: The Fellowship of the Ring",
    "el caballero oscuro": "The Dark Knight",
    "batman el caballero oscuro": "The Dark Knight",
    "parásitos": "Parasite",
    "parasitos": "Parasite",
    "la lista de schindler": "Schindler's List",
    "el rey leon": "The Lion King",
    "el rey león": "The Lion King",
    "dune parte dos": "Dune: Part Two",
}


def _normalize(text):
    """
    Normaliza un texto para comparaciones: convierte a minúsculas,
    elimina acentos y caracteres especiales.
    Se usa principalmente para buscar en la tabla de alias.
    """
    if not text:
        return ""
    # Descompone caracteres Unicode (ej: 'é' → 'e' + acento)
    text = unicodedata.normalize("NFKD", str(text).strip().lower())
    # Elimina los caracteres de combinación (los acentos)
    text = "".join(c for c in text if not unicodedata.combining(c))
    # Deja solo letras, números, ñ y espacios
    text = re.sub(r"[^a-z0-9ñ\s]", " ", text)
    # Colapsa espacios múltiples
    text = re.sub(r"\s+", " ", text).strip()
    return text


def _clean(value, default="N/D"):
    """
    Limpia un valor de la respuesta de OMDb:
    - Devuelve el valor por defecto si es None, vacío o "N/A" (el placeholder de OMDb).
    """
    if value is None:
        return default
    value = str(value).strip()
    if not value or value == "N/A":
        return default
    return value


def _format_votes(votes_str):
    """
    Convierte el string de votos de OMDb (ej: "1,234,567") a formato
    legible en español para que Alexa lo lea de forma natural:
    - 1.234.567 → "1.2 millones"
    - 234.567   → "235 mil"
    """
    raw = _clean(votes_str, default="")
    try:
        # OMDb usa comas como separador de miles (formato anglosajón)
        v = int(raw.replace(",", "").replace(".", ""))
        if v >= 1_000_000:
            return "{:.1f} millones".format(v / 1_000_000)
        if v >= 1_000:
            return "{:.0f} mil".format(v / 1_000)
        return str(v)
    except Exception:
        return raw or "N/D"


def _to_movie_dict(data, fallback_title):
    """
    Convierte la respuesta JSON cruda de OMDb a un diccionario normalizado
    con las claves que usa el resto del proyecto.

    Esto desacopla el código de los nombres de campo de OMDb: si OMDb cambiara
    sus nombres, solo habría que modificar esta función.
    """
    imdb_id = _clean(data.get("imdbID"), default="")
    # Construimos la URL de IMDb a partir del ID si está disponible
    imdb_url = "https://www.imdb.com/title/{}/".format(imdb_id) if imdb_id else ""

    # El poster puede venir como "N/A" si no hay imagen disponible
    poster = data.get("Poster", "")
    if poster == "N/A":
        poster = ""

    return {
        "titulo":   _clean(data.get("Title"), default=fallback_title),
        "anio":     _clean(data.get("Year"), default=""),
        "nota":     _clean(data.get("imdbRating")),
        "votos":    _format_votes(data.get("imdbVotes", "")),
        "sinopsis": _clean(data.get("Plot"), default="Sin sinopsis disponible"),
        "director": _clean(data.get("Director"), default="Desconocido"),
        "duracion": _clean(data.get("Runtime")),
        "generos":  _clean(data.get("Genre")),
        "poster":   poster,
        "imdb_id":  imdb_id,
        "imdb_url": imdb_url,
    }


def _request_omdb(params):
    """
    Realiza una petición GET a la API de OMDb con los parámetros dados.
    Añade automáticamente la API key y el formato JSON.
    Devuelve el JSON de la respuesta, o None si hay un error.
    """
    api_key = os.environ.get("OMDB_API_KEY", "").strip()
    if not api_key:
        logger.error("Falta la variable de entorno OMDB_API_KEY")
        return None

    # Parámetros base: autenticación y formato
    query = {"apikey": api_key, "r": "json"}
    query.update(params)

    try:
        resp = requests.get(OMDB_URL, params=query, timeout=10)
        resp.raise_for_status()  # Lanza excepción si el servidor devuelve 4xx/5xx
        return resp.json()
    except Exception as exc:
        logger.exception("Error llamando a OMDb: %s", exc)
        return None


def _get_by_title(title):
    """Búsqueda exacta por título ('t' = title exact match en OMDb)."""
    return _request_omdb({
        "t": title,
        "type": "movie",
        "plot": "full",  # Pedimos la sinopsis completa
    })


def _get_by_imdb_id(imdb_id):
    """Obtiene los detalles completos de una película a partir de su ID de IMDb."""
    return _request_omdb({
        "i": imdb_id,
        "plot": "full",
    })


def _search_first(title):
    """
    Búsqueda aproximada ('s' = search en OMDb): devuelve una lista de resultados.
    Tomamos el primero y obtenemos sus detalles completos por ID.
    Se usa como fallback cuando la búsqueda exacta por título no da resultado.
    """
    data = _request_omdb({
        "s": title,
        "type": "movie",
    })
    if not data or data.get("Response") != "True":
        return None
    results = data.get("Search") or []
    if not results:
        return None
    imdb_id = results[0].get("imdbID")
    if not imdb_id:
        return None
    return _get_by_imdb_id(imdb_id)


def get_movie_info(title):
    """
    Función principal del scraper. Busca una película por título y devuelve
    un diccionario con su información, o None si no se encuentra.

    Estrategia de búsqueda en cascada:
    1. Intentar con el título original tal como lo escribió el usuario.
    2. Intentar con el alias en inglés (si existe en TITLE_ALIASES).
    3. Intentar con el título capitalizado (ej: "the matrix" → "The Matrix").
    Para cada candidato, primero búsqueda exacta y luego búsqueda aproximada.
    """
    if not title:
        return None

    original_title = str(title).strip()
    normalized = _normalize(original_title)
    candidates = []

    # Candidato 1: título tal cual lo dijo el usuario
    candidates.append(original_title)

    # Candidato 2: alias en inglés (si está registrado)
    alias = TITLE_ALIASES.get(normalized)
    if alias and alias not in candidates:
        candidates.append(alias)

    # Candidato 3: título con capitalización estándar
    titled = original_title.title()
    if titled not in candidates:
        candidates.append(titled)

    # --- Búsqueda exacta por título para cada candidato ---
    for candidate in candidates:
        data = _get_by_title(candidate)
        if data and data.get("Response") == "True":
            return _to_movie_dict(data, fallback_title=original_title)
        if data:
            logger.warning("OMDb no encontró por título '%s': %s", candidate, data.get("Error"))

    # --- Fallback: búsqueda aproximada y primer resultado ---
    for candidate in candidates:
        data = _search_first(candidate)
        if data and data.get("Response") == "True":
            return _to_movie_dict(data, fallback_title=original_title)

    logger.warning("No se encontró información para '%s'", original_title)
    return None


# ---------------------------------------------------------------------------
# Bloque de ejecución por línea de comandos
# Requisito del enunciado: el fichero .py debe recibir el nombre de la película
# por línea de comandos y devolver el valor de los campos.
#
# Uso:
#   python imdb_scraper.py "Inception"
#   python imdb_scraper.py "El Padrino"
#   python imdb_scraper.py  (sin argumentos, usa "Inception" como ejemplo)
# ---------------------------------------------------------------------------
if __name__ == "__main__":
    import json
    import sys

    # Tomamos todos los argumentos como el título de la película
    movie_title = " ".join(sys.argv[1:]) if len(sys.argv) > 1 else "Inception"

    print(f"Buscando información de: '{movie_title}'")
    result = get_movie_info(movie_title)

    if result:
        # Imprimimos el diccionario completo en formato JSON legible
        print(json.dumps(result, ensure_ascii=False, indent=2))
    else:
        print(f"No se encontró información para '{movie_title}'.")
        sys.exit(1)
