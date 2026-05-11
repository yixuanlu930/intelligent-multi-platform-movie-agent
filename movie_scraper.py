#!/usr/bin/env python3
"""
Scraper de películas mediante web scraping de SensaCine.com (BeautifulSoup + requests).
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


def load_cache():
    """
    Carga la caché de películas desde disco.
    Si el archivo existe, lo lee y devuelve un diccionario con los datos guardados.
    Si no existe, devuelve un diccionario vacío para empezar de cero.
    """
    if os.path.exists(config.CACHE_FILE):
        with open(config.CACHE_FILE, "r", encoding="utf-8") as f:
            return json.load(f)
    return {}


def save_cache(cache):
    """
    Guarda la caché de películas en disco.
    Escribe el diccionario en formato JSON con codificación UTF-8 para preservar
    caracteres especiales como tildes y eñes, con indentación para legibilidad.
    """
    with open(config.CACHE_FILE, "w", encoding="utf-8") as f:
        json.dump(cache, f, ensure_ascii=False, indent=2)


def search_movie(title):
    """
    Busca una película en SensaCine scrapeando la página de resultados HTML.

    El proceso funciona así:
    1. Construimos la URL de búsqueda con el título codificado para URLs
    2. Hacemos una petición GET con headers configurados para parecer un navegador real
    3. Parseamos el HTML recibido con BeautifulSoup para navegar por su estructura
    4. Buscamos los elementos <div class="entity-card"> que representan cada resultado
    5. Dentro de cada tarjeta, extraemos el atributo data-entity-id que contiene
       el ID de la película codificado en base64 (formato "Movie:19776")
    6. Decodificamos ese base64 para obtener el ID numérico real
    7. Construimos la URL definitiva de la ficha de la película

    Devuelve una tupla (titulo_encontrado, ruta_relativa) o (None, None) si no hay resultados.
    """
    search_url = f"{SENSACINE_BASE}/buscar/?q={requests.utils.quote(title)}"
    print(f"  [SCRAPING] GET {search_url}", file=sys.stderr)

    r = requests.get(search_url, headers=config.REQUEST_HEADERS, timeout=15)
    r.raise_for_status()

    soup = BeautifulSoup(r.text, "lxml")

    # Buscamos todas las tarjetas de resultados en el HTML parseado
    cards = soup.find_all("div", class_="entity-card")
    print(f"  [SCRAPING] Parseando HTML... {len(cards)} resultados encontrados", file=sys.stderr)

    if not cards:
        return None, None

    # Recorremos las tarjetas una por una hasta encontrar la primera válida
    for card in cards:
        # Extraemos el título que muestra SensaCine para este resultado
        title_el = card.find("h2", class_="meta-title")
        card_title = title_el.get_text(strip=True) if title_el else ""

        # Buscamos el div que contiene el data-entity-id, nuestra clave para el ID
        entity_div = card.find(attrs={"data-entity-id": True})
        if not entity_div:
            continue

        encoded_id = entity_div.get("data-entity-id", "")
        if not encoded_id:
            continue

        # Decodificamos el base64: "TW92aWU6MTk3NzY=" se convierte en "Movie:19776"
        try:
            decoded = base64.b64decode(encoded_id).decode("utf-8")
        except Exception:
            continue

        # Verificamos que efectivamente sea una película y no otro tipo de contenido
        if not decoded.startswith("Movie:"):
            continue

        # Extraemos solo el número del ID y construimos la ruta relativa
        movie_id = decoded.split(":")[1]
        movie_path = f"/peliculas/pelicula-{movie_id}/"

        print(f"  [SCRAPING] Resultado: '{card_title}' -> ID {movie_id}", file=sys.stderr)
        return card_title, movie_path

    return None, None


def scrape_movie_page(movie_path):
    """
    Scrapea la página de detalle de una película en SensaCine.

    Estrategia de extracción:
    1. Hacemos GET a la URL completa de la ficha de la película
    2. Parseamos todo el HTML con BeautifulSoup
    3. Extraemos primero el bloque <script type="application/ld+json"> que contiene
       datos estructurados en formato JSON-LD embebido en la página (esto no es una API externa,
       es HTML normal con metadatos para buscadores)
    4. Para campos que no están en el JSON-LD o que queremos validar, buscamos
       directamente en el HTML usando selectores CSS y expresiones regulares
    5. Combinamos toda la información en un diccionario limpio y consistente

    Devuelve un diccionario con todos los campos extraídos de la película.
    """
    url = SENSACINE_BASE + movie_path
    print(f"  [SCRAPING] GET {url}", file=sys.stderr)

    r = requests.get(url, headers=config.REQUEST_HEADERS, timeout=15)
    r.raise_for_status()

    soup = BeautifulSoup(r.text, "lxml")
    print(f"  [SCRAPING] Parseando HTML de la ficha ({len(r.text):,} bytes)...", file=sys.stderr)

    # Extraemos el JSON-LD embebido en el HTML: son metadatos estructurados
    # que la página incluye para SEO, muy útiles para nosotros
    jsonld_tag = soup.find("script", type="application/ld+json")
    ld_data = {}
    if jsonld_tag and jsonld_tag.string:
        try:
            ld_data = json.loads(jsonld_tag.string)
            print(f"  [SCRAPING] JSON-LD extraido del HTML", file=sys.stderr)
        except json.JSONDecodeError:
            pass

    # Título principal: lo tomamos del JSON-LD si está disponible
    titulo = ld_data.get("name", "")

    # Título original: intentamos obtenerlo del JSON-LD, y si no coincide
    # o falta, lo buscamos manualmente en el HTML donde suele aparecer
    # etiquetado como "Título original"
    titulo_original = ld_data.get("alternateName", titulo)
    if not titulo_original or titulo_original == titulo:
        for item in soup.find_all("div", class_="meta-body-item"):
            text = item.get_text(" ", strip=True)
            if "original" in text.lower():
                parts = re.split(r"original\s*", text, flags=re.I)
                if len(parts) > 1:
                    titulo_original = parts[1].strip()
                break

    # Sinopsis: prioridad al JSON-LD, con fallback al HTML si hace falta
    sinopsis = ld_data.get("description", "")
    if not sinopsis:
        synopsis_div = soup.find("div", class_="content-txt")
        if synopsis_div:
            sinopsis = synopsis_div.get_text(strip=True)

    # Directores: el JSON-LD puede tener un objeto único o una lista,
    # normalizamos a lista para procesarlo uniformemente
    directors_data = ld_data.get("director", [])
    if isinstance(directors_data, dict):
        directors_data = [directors_data]
    directores = [d.get("name", "") for d in directors_data if d.get("name")]
    # Si no encontramos directores en JSON-LD, buscamos en el HTML
    # donde suele aparecer "Dirigida por" seguido de enlaces a los nombres
    if not directores:
        for item in soup.find_all("div", class_="meta-body-item"):
            text = item.get_text(" ", strip=True)
            if "dirigida por" in text.lower():
                links = item.find_all("a")
                directores = [a.get_text(strip=True) for a in links]
                break

    # Géneros: pueden venir como string único o lista, lo normalizamos
    generos = ld_data.get("genre", [])
    if isinstance(generos, str):
        generos = [generos]

    # Duración: el JSON-LD usa formato ISO 8601 (PT02H15M), lo convertimos
    # a formato legible. Si falla, intentamos extraerlo directamente del HTML
    duracion_iso = ld_data.get("duration", "")
    duracion = _parse_iso_duration(duracion_iso)
    if duracion == "N/A":
        for item in soup.find_all("div", class_="meta-body-item"):
            match = re.search(r"(\d+)\s*h\s*(\d+)\s*min", item.get_text())
            if match:
                duracion = f"{match.group(1)}h {match.group(2)}min"
                break

    # Póster: puede ser un string directo o un objeto con propiedad "url"
    poster_data = ld_data.get("image", {})
    poster = poster_data.get("url", "") if isinstance(poster_data, dict) else ""

    # Año: lo extraemos del HTML buscando patrones como "de 2023" en los metadatos
    año = ""
    for item in soup.find_all("div", class_="meta-body-item"):
        text = item.get_text(strip=True)
        year_match = re.search(r"de\s+(\d{4})", text)
        if year_match:
            año = int(year_match.group(1))
            break

    # Nota y votos: prioridad al JSON-LD si tiene aggregateRating,
    # con fallback al scraping directo del HTML si hace falta
    nota = "N/A"
    votos = 0
    best_rating = "5"

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

    # Si la nota sigue sin estar disponible, la buscamos en el HTML
    # dentro de elementos con clase "stareval" o similares
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
    """
    Convierte una duración en formato ISO 8601 (ej: PT02H15M00S)
    a un formato legible para humanos (ej: "2h 15min").

    Maneja casos parciales: solo horas, solo minutos, o combinaciones.
    Devuelve "N/A" si la cadena no tiene formato reconocido.
    """
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


def get_movie_info(title, use_cache=True):
    """
    Función principal reutilizable para obtener información de una película.

    Dado un título, busca la película en SensaCine y devuelve un diccionario
    con todos los campos extraídos. Usa caché local para evitar consultas
    repetidas a la web, lo que acelera el proceso y reduce carga al servidor.

    Devuelve el diccionario con la info o None si no se encuentra la película.
    """
    cache = load_cache() if use_cache else {}
    cache_key = title.lower().strip()

    if cache_key in cache:
        print(f"  [CACHE] '{title}' obtenido de cache local", file=sys.stderr)
        return cache[cache_key]

    # Paso 1: buscamos la película en la página de resultados
    card_title, movie_path = search_movie(title)
    if not movie_path:
        return None

    # Paso 2: una vez tenemos la ruta, scrapeamos la ficha completa
    movie_info = scrape_movie_page(movie_path)
    if not movie_info:
        return None

    # Guardamos en caché para futuras consultas con el mismo título
    if use_cache:
        cache[cache_key] = movie_info
        save_cache(cache)

    return movie_info


CAMPOS_VALIDOS = ["titulo", "titulo_original", "año", "nota", "votos",
                  "sinopsis", "director", "duracion", "genero", "poster", "url"]


def format_movie_text(movie, campos=None):
    """
    Formatea la información de una película como texto legible para consola.

    Si se especifican campos concretos, muestra solo esos. Si no, muestra
    toda la información disponible con un formato limpio y estructurado.
    """
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
    """
    Punto de entrada del script cuando se ejecuta desde línea de comandos.

    Configura el parser de argumentos para permitir:
    - Buscar por título de película (obligatorio)
    - Filtrar campos específicos a mostrar (--campo)
    - Elegir formato de salida: texto plano o JSON (--formato)
    - Forzar consulta web ignorando caché (--no-cache)

    Luego ejecuta la búsqueda, formatea el resultado según las opciones
    y lo imprime por pantalla.
    """
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