#!/usr/bin/env python3
"""
Scraper de cartelera de cine de Madrid desde ecartelera.com.
Integra los datos con el scraper de SensaCine y aplica filtro por perfil de usuario.

Uso:
    python cartelera_scraper.py                   # Muestra cartelera completa
    python cartelera_scraper.py --filtrar          # Aplica filtro por perfil de usuario
    python cartelera_scraper.py --telegram         # Envia por Telegram
    python cartelera_scraper.py --formato json     # Salida JSON
"""

import argparse
import json
import os
import sys
import re
import time
import requests
from bs4 import BeautifulSoup

import config
from movie_scraper import get_movie_info

# ============================================================
# Cines principales de Madrid en ecartelera.com
# ============================================================

CINES_MADRID = [
    ("Yelmo Cines Ideal", "https://www.ecartelera.com/cines/54,0,1.html"),
    ("Callao", "https://www.ecartelera.com/cines/8,0,1.html"),
    ("Cinesa Proyecciones", "https://www.ecartelera.com/cines/17,0,1.html"),
    ("Cines Princesa", "https://www.ecartelera.com/cines/20,0,1.html"),
    ("Palacio de la Prensa", "https://www.ecartelera.com/cines/38,0,1.html"),
    ("Renoir Plaza de España", "https://www.ecartelera.com/cines/44,0,1.html"),
    ("Cinesa Príncipe Pío", "https://www.ecartelera.com/cines/53,0,1.html"),
]

# ============================================================
# Scraper de ecartelera.com
# ============================================================

def scrape_cinema(cinema_name, cinema_url):
    """
    Scrapea las peliculas en cartelera de un cine concreto.
    Devuelve una lista de dicts con info basica de ecartelera.
    """
    try:
        r = requests.get(cinema_url, headers=config.REQUEST_HEADERS, timeout=15)
        r.raise_for_status()
    except requests.RequestException as e:
        print(f"  Error al acceder a {cinema_name}: {e}", file=sys.stderr)
        return []

    soup = BeautifulSoup(r.text, "lxml")
    items = soup.find_all("div", class_="titem")
    movies = []

    for item in items:
        title_el = item.find("p", class_="tit")
        if not title_el:
            continue

        link_el = title_el.find("a")
        title = link_el.get_text(strip=True) if link_el else title_el.get_text(strip=True)
        ecartelera_url = link_el.get("href", "") if link_el else ""

        # Metadata: duracion, pais, genero, clasificacion
        data_el = item.find("p", class_="data")
        data_spans = data_el.find_all("span") if data_el else []
        duracion = data_spans[0].get_text(strip=True) if len(data_spans) > 0 else ""
        pais = data_spans[1].get_text(strip=True) if len(data_spans) > 1 else ""
        genero = data_spans[2].get_text(strip=True) if len(data_spans) > 2 else ""
        clasificacion = data_spans[3].get_text(strip=True) if len(data_spans) > 3 else ""

        # Director
        dir_el = item.find("p", class_="dir")
        director = ""
        if dir_el:
            dir_links = dir_el.find_all("a")
            director = ", ".join(a.get_text(strip=True) for a in dir_links)

        # Nota de ecartelera
        score_el = item.find("span", class_="nota")
        nota_ecartelera = score_el.get_text(strip=True) if score_el else ""

        # Horarios
        sessions_el = item.find("div", class_="sessions")
        horarios = []
        if sessions_el:
            for li in sessions_el.find_all("li"):
                session = li.find(["a", "span"], attrs={"data-session-time": True})
                if session:
                    horarios.append(session.get("data-session-time", ""))

        movies.append({
            "titulo": title,
            "duracion": duracion,
            "pais": pais,
            "genero": genero,
            "clasificacion": clasificacion,
            "director": director,
            "nota_ecartelera": nota_ecartelera,
            "horarios": horarios,
            "ecartelera_url": ecartelera_url,
            "cine": cinema_name,
        })

    return movies


def get_cartelera_madrid():
    """
    Obtiene la cartelera completa de Madrid scrapeando varios cines.
    Deduplica peliculas (agrupa cines y horarios por titulo).
    """
    all_movies = {}

    for cinema_name, cinema_url in CINES_MADRID:
        print(f"  Scrapeando {cinema_name}...", file=sys.stderr)
        movies = scrape_cinema(cinema_name, cinema_url)

        for m in movies:
            key = m["titulo"].lower().strip()
            if key not in all_movies:
                all_movies[key] = {
                    "titulo": m["titulo"],
                    "duracion": m["duracion"],
                    "pais": m["pais"],
                    "genero": m["genero"],
                    "director": m["director"],
                    "nota_ecartelera": m["nota_ecartelera"],
                    "ecartelera_url": m["ecartelera_url"],
                    "cines": {},
                }

            # Agregar cine y horarios
            cine_name = m["cine"]
            if cine_name not in all_movies[key]["cines"]:
                all_movies[key]["cines"][cine_name] = m["horarios"]
            else:
                all_movies[key]["cines"][cine_name].extend(m["horarios"])

            # Actualizar nota si no la teniamos
            if not all_movies[key]["nota_ecartelera"] and m["nota_ecartelera"]:
                all_movies[key]["nota_ecartelera"] = m["nota_ecartelera"]

        time.sleep(0.5)  # Ser amable con el servidor

    return list(all_movies.values())


# ============================================================
# Integracion con SensaCine
# ============================================================

def enrich_with_sensacine(movies):
    """
    Enriquece las peliculas de cartelera con datos de SensaCine.
    """
    enriched = []
    for m in movies:
        print(f"  Buscando en SensaCine: {m['titulo']}...", file=sys.stderr)
        sc_info = get_movie_info(m["titulo"])

        if sc_info:
            m["nota_sensacine"] = sc_info.get("nota", "N/A")
            m["nota_escala"] = sc_info.get("nota_escala", "/5")
            m["votos_sensacine"] = sc_info.get("votos", 0)
            m["sinopsis"] = sc_info.get("sinopsis", "")
            m["genero_sensacine"] = sc_info.get("genero", "")
            m["sensacine_url"] = sc_info.get("url", "")
            m["poster"] = sc_info.get("poster", "")
        else:
            m["nota_sensacine"] = "N/A"
            m["nota_escala"] = "/5"
            m["votos_sensacine"] = 0
            m["sinopsis"] = ""
            m["genero_sensacine"] = m.get("genero", "")
            m["sensacine_url"] = ""
            m["poster"] = ""

        enriched.append(m)
        time.sleep(0.3)

    return enriched


# ============================================================
# Filtro por perfil de usuario
# ============================================================

def load_user_profile():
    """Carga el perfil de usuario desde disco."""
    path = config.USER_PROFILE_FILE
    if os.path.exists(path):
        with open(path, "r", encoding="utf-8") as f:
            return json.load(f)
    return {"genres": {}, "favorite_directors": []}


def filter_by_profile(movies, profile=None):
    """
    Filtra peliculas segun el perfil del usuario.
    - Generos: la nota SensaCine debe superar el minimo configurado para ese genero.
    - Directores favoritos: siempre pasan el filtro.

    Nota: el perfil (user_profile.json) define notas minimas en escala SensaCine (/5).
    """
    if profile is None:
        profile = load_user_profile()

    genre_filters = profile.get("genres", {})
    fav_directors = [d.lower() for d in profile.get("favorite_directors", [])]

    if not genre_filters and not fav_directors:
        return movies

    filtered = []
    for m in movies:
        # Director favorito -> siempre pasa
        director = m.get("director", "").lower()
        if any(fav in director for fav in fav_directors):
            filtered.append(m)
            continue

        # Filtro por genero + nota
        nota = m.get("nota_sensacine", "N/A")
        if nota == "N/A":
            continue

        nota = float(nota)
        genres_movie = m.get("genero_sensacine", "") or m.get("genero", "")

        passed = False
        for genre, min_nota in genre_filters.items():
            if genre.lower() in genres_movie.lower():
                if nota >= min_nota:
                    passed = True
                    break

        # Si no tiene genero configurado, dejamos pasar si supera la nota minima por defecto
        if not passed and not any(g.lower() in genres_movie.lower() for g in genre_filters):
            if nota >= 3.5:
                passed = True

        if passed:
            filtered.append(m)

    return filtered


# ============================================================
# Envio por Telegram
# ============================================================

def send_telegram(message, chat_id=None):
    """Envia un mensaje por Telegram."""
    token = config.TELEGRAM_BOT_TOKEN
    chat_id = chat_id or config.TELEGRAM_CHAT_ID

    if not token or token == "TU_TOKEN_AQUI" or not chat_id:
        print("Error: Configura TELEGRAM_BOT_TOKEN y TELEGRAM_CHAT_ID en config.py",
              file=sys.stderr)
        return False

    url = f"https://api.telegram.org/bot{token}/sendMessage"
    # Telegram tiene un limite de 4096 caracteres por mensaje
    chunks = [message[i:i+4000] for i in range(0, len(message), 4000)]

    for chunk in chunks:
        payload = {
            "chat_id": chat_id,
            "text": chunk,
            "parse_mode": "HTML",
            "disable_web_page_preview": True,
        }
        try:
            r = requests.post(url, json=payload, timeout=15)
            r.raise_for_status()
        except requests.RequestException as e:
            print(f"Error enviando por Telegram: {e}", file=sys.stderr)
            return False

    return True


# ============================================================
# Formateo
# ============================================================

def format_cartelera_text(movies):
    """Formatea la cartelera como texto legible."""
    lines = ["=" * 55]
    lines.append("  CARTELERA DE CINE - MADRID")
    lines.append("=" * 55)

    for m in movies:
        nota_sc = m.get("nota_sensacine", "N/A")
        escala = m.get("nota_escala", "/5")
        nota_str = f"{nota_sc}{escala}" if nota_sc != "N/A" else "Sin nota"
        lines.append(f"\n  {m['titulo']}")
        lines.append(f"  {'─' * 40}")
        if nota_sc != "N/A":
            lines.append(f"  Nota SensaCine: {nota_str}")
        if m.get("nota_ecartelera"):
            lines.append(f"  Nota eCartelera: {m['nota_ecartelera']}")
        if m.get("genero_sensacine"):
            lines.append(f"  Genero: {m['genero_sensacine']}")
        elif m.get("genero"):
            lines.append(f"  Genero: {m['genero']}")
        if m.get("director"):
            lines.append(f"  Director: {m['director']}")
        if m.get("duracion"):
            lines.append(f"  Duracion: {m['duracion']}")
        if m.get("sinopsis"):
            lines.append(f"  Sinopsis: {m['sinopsis'][:150]}...")

        cines = m.get("cines", {})
        if cines:
            lines.append(f"  Cines ({len(cines)}):")
            for cine, horarios in cines.items():
                horarios_str = ", ".join(horarios) if horarios else "consultar"
                lines.append(f"    - {cine}: {horarios_str}")

        if m.get("ecartelera_url"):
            lines.append(f"  eCartelera: {m['ecartelera_url']}")
        if m.get("sensacine_url"):
            lines.append(f"  SensaCine: {m['sensacine_url']}")

    lines.append(f"\n{'=' * 55}")
    lines.append(f"  Total: {len(movies)} peliculas")
    lines.append("=" * 55)
    return "\n".join(lines)


def format_cartelera_telegram(movies):
    """Formatea la cartelera para Telegram (HTML)."""
    lines = ["<b>🎬 CARTELERA DE CINE - MADRID</b>\n"]

    for m in movies:
        nota_sc = m.get("nota_sensacine", "N/A")
        escala = m.get("nota_escala", "/5")
        nota_str = f"{nota_sc}{escala}" if nota_sc != "N/A" else "Sin nota"
        title = m["titulo"]

        lines.append(f"<b>{title}</b>")
        lines.append(f"⭐ Nota SensaCine: {nota_str}")
        if m.get("genero_sensacine"):
            lines.append(f"🎭 {m['genero_sensacine']}")
        if m.get("director"):
            lines.append(f"🎬 Dir: {m['director']}")

        links = []
        if m.get("ecartelera_url"):
            links.append(f'<a href="{m["ecartelera_url"]}">Ficha eCartelera</a>')
        if m.get("sensacine_url"):
            links.append(f'<a href="{m["sensacine_url"]}">Ficha SensaCine</a>')
        if links:
            lines.append("🔗 " + " | ".join(links))

        lines.append("─" * 30)

    lines.append(f"\n<b>Total: {len(movies)} peliculas</b>")
    return "\n".join(lines)


# ============================================================
# CLI
# ============================================================

def main():
    parser = argparse.ArgumentParser(
        description="Scraper de cartelera de cine de Madrid",
    )
    parser.add_argument(
        "--filtrar", action="store_true",
        help="Filtrar peliculas por perfil de usuario",
    )
    parser.add_argument(
        "--telegram", action="store_true",
        help="Enviar resultado por Telegram",
    )
    parser.add_argument(
        "--chat-id",
        help="Chat ID de Telegram (sobreescribe config.py)",
    )
    parser.add_argument(
        "--formato", "-f",
        choices=["texto", "json", "telegram"],
        default="texto",
        help="Formato de salida",
    )
    parser.add_argument(
        "--no-sensacine", "--no-imdb", dest="no_sensacine", action="store_true",
        help="No enriquecer con datos de SensaCine (mas rapido)",
    )

    args = parser.parse_args()

    print("Obteniendo cartelera de Madrid...", file=sys.stderr)
    movies = get_cartelera_madrid()
    print(f"  {len(movies)} peliculas encontradas", file=sys.stderr)

    if not args.no_sensacine:
        print("Enriqueciendo con datos de SensaCine...", file=sys.stderr)
        movies = enrich_with_sensacine(movies)

    if args.filtrar:
        profile = load_user_profile()
        print(f"Aplicando filtro de perfil...", file=sys.stderr)
        movies = filter_by_profile(movies, profile)
        print(f"  {len(movies)} peliculas tras filtro", file=sys.stderr)

    # Ordenar por nota SensaCine descendente
    def sort_key(m):
        nota = m.get("nota_sensacine", "N/A")
        return float(nota) if nota != "N/A" else 0
    movies.sort(key=sort_key, reverse=True)

    # Salida
    if args.formato == "json":
        # Convertir sets/etc a serializable
        for m in movies:
            if "cines" in m:
                m["cines"] = {k: list(v) for k, v in m["cines"].items()}
        print(json.dumps(movies, ensure_ascii=False, indent=2))
    elif args.formato == "telegram":
        print(format_cartelera_telegram(movies))
    else:
        print(format_cartelera_text(movies))

    # Envio por Telegram
    if args.telegram:
        msg = format_cartelera_telegram(movies)
        if send_telegram(msg, chat_id=args.chat_id):
            print("Enviado por Telegram correctamente.", file=sys.stderr)
        else:
            print("Error al enviar por Telegram.", file=sys.stderr)
            sys.exit(1)


if __name__ == "__main__":
    main()
