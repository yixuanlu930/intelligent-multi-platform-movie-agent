#!/usr/bin/env python3
"""
Scraper de conciertos en Madrid mediante la API publica de Wegow.

Extraido de la celda 18 de Practica_Agentes.ipynb para que pueda importarse
desde scripts externos (telegram_bot, web_app, agente unificado, etc.).

Uso programatico:
    from concerts_scraper import fetch_concerts, filter_by_favorite_artists, format_concerts_text
"""

import json
import sys
from datetime import datetime, timedelta, timezone

import requests

import config

# URL por defecto si no esta declarada en config.py
DEFAULT_WEGOW_API = "https://www.wegow.com/api/events?cities=3117735"


def fetch_concerts(limit_days=7):
    """
    Consulta la API de Wegow y devuelve los conciertos en Madrid
    de los proximos `limit_days` dias.
    """
    api_url = getattr(config, "WEGOW_API", DEFAULT_WEGOW_API)
    try:
        r = requests.get(api_url, headers=config.REQUEST_HEADERS, timeout=20)
        r.raise_for_status()
    except requests.RequestException as e:
        print(f"Error al contactar Wegow: {e}", file=sys.stderr)
        return []

    data = r.json()
    events = data.get("events", []) if isinstance(data, dict) else []

    today = datetime.now(timezone.utc).date()
    deadline = today + timedelta(days=limit_days)

    out = []
    for e in events:
        # Filtro por ciudad: solo Madrid
        city = e.get("city") or {}
        if city.get("name") != "Madrid":
            continue

        # Filtro temporal: solo la ventana solicitada
        sd = e.get("start_date")
        if not sd:
            continue
        try:
            dt = datetime.strptime(sd[:10], "%Y-%m-%d").date()
        except ValueError:
            continue
        if not (today <= dt <= deadline):
            continue

        venue = e.get("venue") or {}
        out.append({
            "id":       e.get("id"),
            "titulo":   e.get("title"),
            "fecha":    dt.isoformat(),
            "hora":     sd[11:16] if len(sd) >= 16 else "",
            "artistas": [a.get("name") for a in (e.get("artists") or [])],
            "recinto":  venue.get("name") or "",
            "url":      e.get("permalink") or e.get("purchase_url") or "",
        })

    out.sort(key=lambda c: c["fecha"])
    return out


def filter_by_favorite_artists(concerts, profile=None):
    """Devuelve solo los conciertos que incluyen artistas del perfil favorito."""
    if profile is None:
        with open(config.USER_PROFILE_FILE, encoding="utf-8") as f:
            profile = json.load(f)
    favs = [a.lower() for a in profile.get("favorite_artists", [])]
    if not favs:
        return concerts

    out = []
    for c in concerts:
        for a in c["artistas"]:
            if a and a.lower() in favs:
                # Marcamos cual artista fue el match para poder mostrarlo despues
                c["_match"] = a
                out.append(c)
                break
    return out


def format_concerts_text(concerts, only_favorites=False):
    """Formatea la lista de conciertos como texto legible."""
    if not concerts:
        return "Sin conciertos favoritos esta semana." if only_favorites else "Sin conciertos esta semana."

    title = "CONCIERTOS - ARTISTAS FAVORITOS" if only_favorites else "CONCIERTOS EN MADRID (7 DIAS)"
    lines = [title, "=" * len(title), ""]
    for c in concerts:
        lines.append(f"[{c['fecha']} {c['hora']}] {c['titulo']}")
        if c["artistas"]:
            lines.append(f"   Artistas: {', '.join(c['artistas'][:5])}")
        if c["recinto"]:
            lines.append(f"   Sala: {c['recinto']}")
        if c.get("_match"):
            lines.append(f"   * Favorito: {c['_match']}")
        if c["url"]:
            lines.append(f"   {c['url']}")
        lines.append("")
    return "\n".join(lines)


if __name__ == "__main__":
    import argparse

    parser = argparse.ArgumentParser(description="Conciertos de la semana en Madrid (Wegow).")
    parser.add_argument("--dias", type=int, default=7, help="Ventana de dias hacia adelante (defecto: 7)")
    parser.add_argument("--favoritos", action="store_true", help="Filtrar por artistas favoritos del perfil")
    parser.add_argument("--formato", choices=["texto", "json"], default="texto")
    args = parser.parse_args()

    cs = fetch_concerts(limit_days=args.dias)
    if args.favoritos:
        cs = filter_by_favorite_artists(cs)

    if args.formato == "json":
        print(json.dumps(cs, ensure_ascii=False, indent=2))
    else:
        print(format_concerts_text(cs, only_favorites=args.favoritos))
