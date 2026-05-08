"""
imdb_scraper.py

Obtiene información de películas usando OMDb API.
Aunque el nombre del archivo sea imdb_scraper.py para encajar con la práctica,
esta versión usa una API estable en vez de scrapear HTML.

Requiere variable de entorno en AWS Lambda:
    OMDB_API_KEY
"""

import logging
import os
import re
import unicodedata

import requests

logger = logging.getLogger(__name__)

OMDB_URL = "https://www.omdbapi.com/"

# Alias para títulos españoles o variantes frecuentes. Ayuda a que OMDb encuentre mejor.
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
    if not text:
        return ""
    text = unicodedata.normalize("NFKD", str(text).strip().lower())
    text = "".join(c for c in text if not unicodedata.combining(c))
    text = re.sub(r"[^a-z0-9ñ\s]", " ", text)
    text = re.sub(r"\s+", " ", text).strip()
    return text


def _clean(value, default="N/D"):
    if value is None:
        return default
    value = str(value).strip()
    if not value or value == "N/A":
        return default
    return value


def _format_votes(votes_str):
    raw = _clean(votes_str, default="")
    try:
        v = int(raw.replace(",", "").replace(".", ""))
        if v >= 1_000_000:
            return "{:.1f} millones".format(v / 1_000_000)
        if v >= 1_000:
            return "{:.0f} mil".format(v / 1_000)
        return str(v)
    except Exception:
        return raw or "N/D"


def _to_movie_dict(data, fallback_title):
    imdb_id = _clean(data.get("imdbID"), default="")
    imdb_url = "https://www.imdb.com/title/{}/".format(imdb_id) if imdb_id else ""
    poster = data.get("Poster", "")
    if poster == "N/A":
        poster = ""

    return {
        "titulo": _clean(data.get("Title"), default=fallback_title),
        "anio": _clean(data.get("Year"), default=""),
        "nota": _clean(data.get("imdbRating")),
        "votos": _format_votes(data.get("imdbVotes", "")),
        "sinopsis": _clean(data.get("Plot"), default="Sin sinopsis disponible"),
        "director": _clean(data.get("Director"), default="Desconocido"),
        "duracion": _clean(data.get("Runtime")),
        "generos": _clean(data.get("Genre")),
        "poster": poster,
        "imdb_id": imdb_id,
        "imdb_url": imdb_url,
    }


def _request_omdb(params):
    api_key = os.environ.get("OMDB_API_KEY", "").strip()
    if not api_key:
        logger.error("Falta la variable de entorno OMDB_API_KEY")
        return None

    query = {"apikey": api_key, "r": "json"}
    query.update(params)

    try:
        resp = requests.get(OMDB_URL, params=query, timeout=10)
        resp.raise_for_status()
        return resp.json()
    except Exception as exc:
        logger.exception("Error llamando a OMDb: %s", exc)
        return None


def _get_by_title(title):
    return _request_omdb({
        "t": title,
        "type": "movie",
        "plot": "full",
    })


def _get_by_imdb_id(imdb_id):
    return _request_omdb({
        "i": imdb_id,
        "plot": "full",
    })


def _search_first(title):
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
    Busca una película por título usando OMDb API.
    Devuelve dict o None si no encuentra resultados.
    """
    if not title:
        return None

    original_title = str(title).strip()
    normalized = _normalize(original_title)
    candidates = []

    # 1) Título dicho por el usuario.
    candidates.append(original_title)

    # 2) Alias si existe.
    alias = TITLE_ALIASES.get(normalized)
    if alias and alias not in candidates:
        candidates.append(alias)

    # 3) Variante capitalizada simple.
    titled = original_title.title()
    if titled not in candidates:
        candidates.append(titled)

    # Intentar búsqueda exacta por título.
    for candidate in candidates:
        data = _get_by_title(candidate)
        if data and data.get("Response") == "True":
            return _to_movie_dict(data, fallback_title=original_title)
        if data:
            logger.warning("OMDb no encontró por título '%s': %s", candidate, data.get("Error"))

    # Fallback: búsqueda por lista y escoger el primer resultado.
    for candidate in candidates:
        data = _search_first(candidate)
        if data and data.get("Response") == "True":
            return _to_movie_dict(data, fallback_title=original_title)

    logger.warning("No se encontró información para '%s'", original_title)
    return None


if __name__ == "__main__":
    import json
    import sys

    movie_title = " ".join(sys.argv[1:]) if len(sys.argv) > 1 else "Inception"
    result = get_movie_info(movie_title)
    print(json.dumps(result, ensure_ascii=False, indent=2))
