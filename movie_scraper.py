#!/usr/bin/env python3
"""
Scraper de peliculas de IMDB.
Extrae: titulo, nota, votos, sinopsis, director, duracion, genero, año, poster.
Uso:
    python movie_scraper.py "The Matrix"
    python movie_scraper.py "Inception" --campo nota
    python movie_scraper.py "2001" --campo director --formato json
"""

import argparse
import json
import os
import sys
import re
import requests

import config

# ============================================================
# Cache
# ============================================================

def load_cache():
    """Carga la cache de peliculas desde disco."""
    if os.path.exists(config.CACHE_FILE):
        with open(config.CACHE_FILE, "r", encoding="utf-8") as f:
            return json.load(f)
    return {}


def save_cache(cache):
    """Guarda la cache de peliculas en disco."""
    with open(config.CACHE_FILE, "w", encoding="utf-8") as f:
        json.dump(cache, f, ensure_ascii=False, indent=2)

# ============================================================
# IMDB: Busqueda por nombre (Suggestion API)
# ============================================================

def search_movie(title):
    """
    Busca una pelicula en IMDB usando la Suggestion API.
    Devuelve el primer resultado (dict) o None.
    """
    # La API espera el titulo en minusculas con espacios reemplazados por _
    query = title.lower().replace(" ", "_")
    # El primer caracter se usa como subcarpeta en la URL
    first_char = re.sub(r'[^a-z0-9]', '', query)[:1] or 'a'
    url = f"https://v2.sg.media-imdb.com/suggestion/{first_char}/{query}.json"

    r = requests.get(url, headers=config.REQUEST_HEADERS, timeout=15)
    r.raise_for_status()
    data = r.json()

    results = data.get("d", [])
    # Filtrar solo peliculas (feature films)
    movies = [m for m in results if m.get("qid") in ("movie", "tvMovie")]
    if not movies:
        return None
    return movies[0]

# ============================================================
# IMDB: Detalle por ID (GraphQL API)
# ============================================================

GRAPHQL_QUERY = """
query GetMovieInfo($id: ID!) {
  title(id: $id) {
    titleText { text }
    originalTitleText { text }
    releaseYear { year }
    ratingsSummary { aggregateRating voteCount }
    plot { plotText { plainText } }
    runtime { seconds displayableProperty { value { plainText } } }
    directors: credits(first: 10, filter: {categories: ["director"]}) {
      edges { node { name { nameText { text } } } }
    }
    genres { genres { text } }
    primaryImage { url }
  }
}
"""


def fetch_movie_details(imdb_id):
    """
    Obtiene la informacion detallada de una pelicula desde la GraphQL API de IMDB.
    Devuelve un diccionario con los campos normalizados.
    """
    headers = {
        **config.REQUEST_HEADERS,
        "Content-Type": "application/json",
    }

    payload = {
        "query": GRAPHQL_QUERY,
        "variables": {"id": imdb_id},
    }

    r = requests.post(
        "https://graphql.imdb.com/",
        headers=headers,
        json=payload,
        timeout=15,
    )
    r.raise_for_status()
    data = r.json()

    title_data = data.get("data", {}).get("title")
    if not title_data:
        return None

    # Extraer directores
    directors = []
    for edge in (title_data.get("directors") or {}).get("edges", []):
        name = edge.get("node", {}).get("name", {}).get("nameText", {}).get("text")
        if name:
            directors.append(name)

    # Extraer generos
    genres = []
    for g in (title_data.get("genres") or {}).get("genres", []):
        if g.get("text"):
            genres.append(g["text"])

    # Extraer duracion
    runtime_data = title_data.get("runtime") or {}
    duration_str = (
        runtime_data.get("displayableProperty", {})
        .get("value", {})
        .get("plainText", "")
    )
    duration_seconds = runtime_data.get("seconds", 0)

    # Extraer sinopsis
    plot = (title_data.get("plot") or {}).get("plotText", {}).get("plainText", "")

    # Extraer rating
    rating_data = title_data.get("ratingsSummary") or {}

    # Construir resultado
    movie_info = {
        "titulo": (title_data.get("titleText") or {}).get("text", ""),
        "titulo_original": (title_data.get("originalTitleText") or {}).get("text", ""),
        "año": (title_data.get("releaseYear") or {}).get("year", ""),
        "nota": rating_data.get("aggregateRating", "N/A"),
        "votos": rating_data.get("voteCount", 0),
        "sinopsis": plot,
        "director": ", ".join(directors) if directors else "N/A",
        "duracion": duration_str or f"{duration_seconds // 60} min",
        "genero": ", ".join(genres) if genres else "N/A",
        "poster": (title_data.get("primaryImage") or {}).get("url", ""),
        "imdb_id": imdb_id,
        "imdb_url": f"https://www.imdb.com/title/{imdb_id}/",
    }

    return movie_info

# ============================================================
# Funcion principal reutilizable
# ============================================================

def get_movie_info(title, use_cache=True):
    """
    Obtiene informacion de una pelicula dado su titulo.
    Usa cache para evitar consultas repetidas.
    Devuelve un diccionario con la info o None si no se encuentra.
    """
    cache = load_cache() if use_cache else {}
    cache_key = title.lower().strip()

    if cache_key in cache:
        return cache[cache_key]

    # Paso 1: buscar la pelicula por nombre
    search_result = search_movie(title)
    if not search_result:
        return None

    imdb_id = search_result.get("id")
    if not imdb_id:
        return None

    # Paso 2: obtener detalles completos
    movie_info = fetch_movie_details(imdb_id)
    if not movie_info:
        return None

    # Guardar en cache
    if use_cache:
        cache[cache_key] = movie_info
        save_cache(cache)

    return movie_info

# ============================================================
# CLI
# ============================================================

CAMPOS_VALIDOS = ["titulo", "titulo_original", "año", "nota", "votos",
                  "sinopsis", "director", "duracion", "genero", "poster",
                  "imdb_id", "imdb_url"]


def format_movie_text(movie, campos=None):
    """Formatea la info de una pelicula como texto legible."""
    if campos:
        lines = []
        for c in campos:
            if c in movie:
                lines.append(f"  {c.capitalize()}: {movie[c]}")
        return "\n".join(lines)

    lines = [
        f"  Titulo: {movie['titulo']}",
        f"  Titulo Original: {movie['titulo_original']}",
        f"  Año: {movie['año']}",
        f"  Nota IMDB: {movie['nota']}/10",
        f"  Votos: {movie['votos']:,}",
        f"  Director: {movie['director']}",
        f"  Duracion: {movie['duracion']}",
        f"  Genero: {movie['genero']}",
        f"  Sinopsis: {movie['sinopsis']}",
        f"  IMDB: {movie['imdb_url']}",
    ]
    return "\n".join(lines)


def main():
    parser = argparse.ArgumentParser(
        description="Scraper de peliculas de IMDB",
        epilog="Ejemplo: python movie_scraper.py \"Inception\" --campo nota",
    )
    parser.add_argument(
        "pelicula",
        help="Nombre de la pelicula a buscar",
    )
    parser.add_argument(
        "--campo", "-c",
        action="append",
        choices=CAMPOS_VALIDOS,
        help="Campo especifico a mostrar (se puede repetir). "
             f"Opciones: {', '.join(CAMPOS_VALIDOS)}",
    )
    parser.add_argument(
        "--formato", "-f",
        choices=["texto", "json"],
        default="texto",
        help="Formato de salida (por defecto: texto)",
    )
    parser.add_argument(
        "--no-cache",
        action="store_true",
        help="No usar cache (forzar consulta a IMDB)",
    )

    args = parser.parse_args()

    movie = get_movie_info(args.pelicula, use_cache=not args.no_cache)

    if not movie:
        print(f"No se encontro la pelicula: {args.pelicula}", file=sys.stderr)
        sys.exit(1)

    if args.formato == "json":
        if args.campo:
            output = {c: movie.get(c) for c in args.campo}
        else:
            output = movie
        print(json.dumps(output, ensure_ascii=False, indent=2))
    else:
        print(f"\n{'='*50}")
        print(f"  {movie['titulo']} ({movie['año']})")
        print(f"{'='*50}")
        print(format_movie_text(movie, args.campo))
        print()


if __name__ == "__main__":
    main()
