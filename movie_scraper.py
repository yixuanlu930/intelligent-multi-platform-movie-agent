#!/usr/bin/env python3
"""
Scraper de peliculas mediante web scraping de SensaCine.com (BeautifulSoup + requests).
NO usa APIs — todo el proceso es scraping de paginas HTML reales.

Extrae: titulo, nota, votos, sinopsis, director, duracion, genero, año, poster.

Uso:
    python movie_scraper.py "The Matrix"
    python movie_scraper.py "Inception" --campo nota
    python movie_scraper.py "2001" --campo director --formato json

Fuente: https://www.sensacine.com
"""

import argparse
import base64
import json
import os
import re
import sys

import requests
from bs4 import BeautifulSoup

import config

SENSACINE_BASE = "https://www.sensacine.com"

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
# PASO 1 — Buscar pelicula scrapeando la pagina de busqueda
# ============================================================

def search_movie(title):
    """
    Busca una pelicula en SensaCine scrapeando la pagina de resultados HTML.

    Proceso de scraping:
      1. Hacemos GET a https://www.sensacine.com/buscar/?q=<titulo>
      2. Parseamos el HTML con BeautifulSoup
      3. Buscamos los <div class="entity-card"> (tarjetas de resultados)
      4. Dentro de cada tarjeta, encontramos el atributo data-entity-id
         que contiene el ID de la pelicula codificado en base64 ("Movie:19776")
      5. Decodificamos el base64 para obtener el ID numerico
      6. Construimos la URL: /peliculas/pelicula-{id}/

    Devuelve (titulo, url_path) o (None, None).
    """
    search_url = f"{SENSACINE_BASE}/buscar/?q={requests.utils.quote(title)}"
    print(f"  [SCRAPING] GET {search_url}", file=sys.stderr)

    r = requests.get(search_url, headers=config.REQUEST_HEADERS, timeout=15)
    r.raise_for_status()

    soup = BeautifulSoup(r.text, "lxml")

    # Buscar tarjetas de resultados en el HTML
    cards = soup.find_all("div", class_="entity-card")
    print(f"  [SCRAPING] Parseando HTML... {len(cards)} resultados encontrados", file=sys.stderr)

    if not cards:
        return None, None

    # Recorrer las tarjetas buscando el data-entity-id
    for card in cards:
        # Extraer titulo del resultado
        title_el = card.find("h2", class_="meta-title")
        card_title = title_el.get_text(strip=True) if title_el else ""

        # Buscar el div con data-entity-id (contiene el ID en base64)
        entity_div = card.find(attrs={"data-entity-id": True})
        if not entity_div:
            continue

        encoded_id = entity_div.get("data-entity-id", "")
        if not encoded_id:
            continue

        # Decodificar base64: "TW92aWU6MTk3NzY=" -> "Movie:19776"
        try:
            decoded = base64.b64decode(encoded_id).decode("utf-8")
        except Exception:
            continue

        # Verificar que es una pelicula (formato "Movie:XXXXX")
        if not decoded.startswith("Movie:"):
            continue

        movie_id = decoded.split(":")[1]
        movie_path = f"/peliculas/pelicula-{movie_id}/"

        print(f"  [SCRAPING] Resultado: '{card_title}' -> ID {movie_id}", file=sys.stderr)
        return card_title, movie_path

    return None, None


# ============================================================
# PASO 2 — Scrapear la pagina de detalle de la pelicula
# ============================================================

def scrape_movie_page(movie_path):
    """
    Scrapea la pagina de detalle de una pelicula en SensaCine.

    Proceso de scraping:
      1. GET https://www.sensacine.com/peliculas/pelicula-XXXXX/
      2. Parseamos el HTML completo con BeautifulSoup
      3. Extraemos el bloque <script type="application/ld+json"> del HTML
         (datos estructurados embebidos en la pagina, NO es una API)
      4. Parseamos campos adicionales directamente del HTML:
         - Nota: <div class="stareval"> dentro de <div class="rating-item-content">
         - Votos: texto junto a las estrellas
         - Info: <div class="meta-body-item"> para fecha, director, reparto
      5. Construimos el diccionario final con todos los campos

    Devuelve un diccionario con la informacion de la pelicula.
    """
    url = SENSACINE_BASE + movie_path
    print(f"  [SCRAPING] GET {url}", file=sys.stderr)

    r = requests.get(url, headers=config.REQUEST_HEADERS, timeout=15)
    r.raise_for_status()

    soup = BeautifulSoup(r.text, "lxml")
    print(f"  [SCRAPING] Parseando HTML de la ficha ({len(r.text):,} bytes)...", file=sys.stderr)

    # ---- Extraer JSON-LD embebido en el HTML ----
    # (Es un <script> dentro de la pagina, no una llamada API)
    jsonld_tag = soup.find("script", type="application/ld+json")
    ld_data = {}
    if jsonld_tag and jsonld_tag.string:
        try:
            ld_data = json.loads(jsonld_tag.string)
            print(f"  [SCRAPING] JSON-LD extraido del HTML", file=sys.stderr)
        except json.JSONDecodeError:
            pass

    # ---- Titulo (del JSON-LD embebido en HTML) ----
    titulo = ld_data.get("name", "")

    # ---- Titulo original (del HTML, en <div class="meta-body-item">) ----
    titulo_original = ld_data.get("alternateName", titulo)
    if not titulo_original or titulo_original == titulo:
        for item in soup.find_all("div", class_="meta-body-item"):
            text = item.get_text(" ", strip=True)
            if "original" in text.lower():
                # Extraer el texto despues de "Título original"
                parts = re.split(r"original\s*", text, flags=re.I)
                if len(parts) > 1:
                    titulo_original = parts[1].strip()
                break

    # ---- Sinopsis (del JSON-LD) ----
    sinopsis = ld_data.get("description", "")
    # Alternativa: buscar directamente en el HTML
    if not sinopsis:
        synopsis_div = soup.find("div", class_="content-txt")
        if synopsis_div:
            sinopsis = synopsis_div.get_text(strip=True)

    # ---- Directores (del JSON-LD) ----
    directors_data = ld_data.get("director", [])
    if isinstance(directors_data, dict):
        directors_data = [directors_data]
    directores = [d.get("name", "") for d in directors_data if d.get("name")]
    # Alternativa: del HTML
    if not directores:
        for item in soup.find_all("div", class_="meta-body-item"):
            text = item.get_text(" ", strip=True)
            if "dirigida por" in text.lower():
                links = item.find_all("a")
                directores = [a.get_text(strip=True) for a in links]
                break

    # ---- Generos (del JSON-LD) ----
    generos = ld_data.get("genre", [])
    if isinstance(generos, str):
        generos = [generos]

    # ---- Duracion (del JSON-LD, formato ISO 8601) ----
    duracion_iso = ld_data.get("duration", "")
    duracion = _parse_iso_duration(duracion_iso)
    # Alternativa: del HTML
    if duracion == "N/A":
        for item in soup.find_all("div", class_="meta-body-item"):
            match = re.search(r"(\d+)\s*h\s*(\d+)\s*min", item.get_text())
            if match:
                duracion = f"{match.group(1)}h {match.group(2)}min"
                break

    # ---- Poster (del JSON-LD) ----
    poster_data = ld_data.get("image", {})
    poster = poster_data.get("url", "") if isinstance(poster_data, dict) else ""

    # ---- Año (scrapeando del HTML) ----
    año = ""
    for item in soup.find_all("div", class_="meta-body-item"):
        text = item.get_text(strip=True)
        year_match = re.search(r"de\s+(\d{4})", text)
        if year_match:
            año = int(year_match.group(1))
            break

    # ---- Nota (scrapeando del HTML: div.rating-item-content > div.stareval) ----
    nota = "N/A"
    votos = 0
    best_rating = "5"

    # Intentar desde JSON-LD embebido en la pagina
    agg_rating = ld_data.get("aggregateRating", {})
    if agg_rating:
        nota_raw = str(agg_rating.get("ratingValue", "")).replace(",", ".")
        try:
            nota = round(float(nota_raw), 1)
        except ValueError:
            pass
        votos_raw = str(agg_rating.get("ratingCount", "0"))
        try:
            votos = int(votos_raw.replace(",", "").replace(".", ""))
        except ValueError:
            votos = 0
        best_rating = str(agg_rating.get("bestRating", "5"))

    # Alternativa: scrapear nota directamente de los elementos HTML
    if nota == "N/A":
        rating_items = soup.find_all("div", class_="rating-item-content")
        for ri in rating_items:
            note_el = ri.find("span", class_=re.compile(r"note"))
            if note_el:
                note_text = note_el.get_text(strip=True).replace(",", ".")
                try:
                    nota = round(float(note_text), 1)
                    break
                except ValueError:
                    continue

    print(f"  [SCRAPING] Datos extraidos: {titulo} ({año}) - Nota: {nota}/{best_rating}", file=sys.stderr)

    return {
        "titulo": titulo,
        "titulo_original": titulo_original,
        "año": año,
        "nota": nota,
        "nota_escala": f"/{best_rating}",
        "votos": votos,
        "sinopsis": sinopsis,
        "director": ", ".join(directores) if directores else "N/A",
        "duracion": duracion,
        "genero": ", ".join(generos) if generos else "N/A",
        "poster": poster,
        "url": url,
    }


def _parse_iso_duration(iso_str):
    """Convierte duracion ISO 8601 (PT02H15M00S) a formato legible (2h 15min)."""
    if not iso_str:
        return "N/A"
    match = re.match(r"PT(?:(\d+)H)?(?:(\d+)M)?(?:(\d+)S)?", iso_str)
    if not match:
        return iso_str
    hours = int(match.group(1) or 0)
    minutes = int(match.group(2) or 0)
    parts = []
    if hours:
        parts.append(f"{hours}h")
    if minutes:
        parts.append(f"{minutes}min")
    return " ".join(parts) if parts else "N/A"


# ============================================================
# Funcion principal reutilizable
# ============================================================

def get_movie_info(title, use_cache=True):
    """
    Obtiene informacion de una pelicula dado su titulo.
    Usa cache para evitar consultas repetidas a la web.
    Devuelve un diccionario con la info o None si no se encuentra.
    """
    cache = load_cache() if use_cache else {}
    cache_key = title.lower().strip()

    if cache_key in cache:
        print(f"  [CACHE] '{title}' obtenido de cache local", file=sys.stderr)
        return cache[cache_key]

    # Paso 1: scrapear pagina de busqueda
    card_title, movie_path = search_movie(title)
    if not movie_path:
        return None

    # Paso 2: scrapear pagina de la pelicula
    movie_info = scrape_movie_page(movie_path)
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
                  "sinopsis", "director", "duracion", "genero", "poster", "url"]


def format_movie_text(movie, campos=None):
    """Formatea la info de una pelicula como texto legible."""
    escala = movie.get("nota_escala", "/5")

    if campos:
        lines = []
        for c in campos:
            if c in movie:
                val = movie[c]
                if c == "nota":
                    val = f"{val}{escala}"
                lines.append(f"  {c.capitalize()}: {val}")
        return "\n".join(lines)

    lines = [
        f"  Titulo: {movie['titulo']}",
        f"  Titulo Original: {movie['titulo_original']}",
        f"  Año: {movie['año']}",
        f"  Nota SensaCine: {movie['nota']}{escala}",
        f"  Votos: {movie['votos']:,}",
        f"  Director: {movie['director']}",
        f"  Duracion: {movie['duracion']}",
        f"  Genero: {movie['genero']}",
        f"  Sinopsis: {movie['sinopsis']}",
        f"  URL: {movie['url']}",
    ]
    return "\n".join(lines)


def main():
    parser = argparse.ArgumentParser(
        description="Scraper de peliculas (web scraping de SensaCine.com con BeautifulSoup)",
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
        help="No usar cache (forzar nueva consulta web)",
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
