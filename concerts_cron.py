#!/usr/bin/env python3
"""
Tarea cron: cada lunes 9:00 consulta los conciertos de la semana en Madrid
filtrados por artistas favoritos del perfil y los envia por Telegram.

Se invoca desde `cron_weekly.sh`. Tambien puede ejecutarse manualmente:

    python concerts_cron.py

Reusa la logica de `concerts_scraper.py` para no duplicar el scraping.
"""

import json
import os
import sys

import requests

# Hacemos que el import funcione aunque cron lo lance desde otro CWD
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

import config
from concerts_scraper import fetch_concerts, filter_by_favorite_artists


def build_telegram_message(concerts):
    """Compone el mensaje HTML que enviaremos por Telegram."""
    parts = ["<b>Conciertos favoritos esta semana</b>", ""]
    for c in concerts:
        parts.append(f"{c['fecha']} {c['hora']}")
        parts.append(c["titulo"])
        if c.get("recinto"):
            parts.append("Sala: " + c["recinto"])
        if c.get("_match"):
            parts.append("Artista favorito: " + c["_match"])
        if c.get("url"):
            parts.append(f'<a href="{c["url"]}">Mas info</a>')
        parts.append("")
    return "\n".join(parts)


def main():
    # 1) Conciertos de la proxima semana, filtrados por perfil
    concerts = fetch_concerts(limit_days=7)
    favorites = filter_by_favorite_artists(concerts)

    if not favorites:
        # Caso normal: hay semanas sin matches. No es error, salimos en silencio.
        print("Sin conciertos favoritos esta semana.")
        return 0

    # 2) Comprobamos credenciales antes de intentar el envio
    token = getattr(config, "TELEGRAM_BOT_TOKEN", "")
    chat_id = getattr(config, "TELEGRAM_CHAT_ID", "")
    if not token or token == "TU_TOKEN_AQUI" or not chat_id:
        print("Falta TELEGRAM_BOT_TOKEN o TELEGRAM_CHAT_ID en config.py", file=sys.stderr)
        return 1

    # 3) Envio a la API de Telegram
    msg = build_telegram_message(favorites)
    resp = requests.post(
        f"https://api.telegram.org/bot{token}/sendMessage",
        data={
            "chat_id": chat_id,
            "text": msg,
            "parse_mode": "HTML",
            "disable_web_page_preview": "true",
        },
        timeout=15,
    )
    print(f"Conciertos enviados: status={resp.status_code}, {len(favorites)} eventos.")
    return 0 if resp.ok else 1


if __name__ == "__main__":
    sys.exit(main())
