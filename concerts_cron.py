#!/usr/bin/env python3
"""
Tarea cron: cada lunes 9:00 consulta los conciertos de la semana en Madrid
filtrados por artistas favoritos del perfil y los envia por Telegram.

Se invoca desde `cron_weekly.sh`. Tambien puede ejecutarse manualmente:

    python concerts_cron.py

Reusa la logica de `concerts_scraper.py` para no duplicar el scraping.
Usa requests.post directamente a la API de Telegram (sin SDK) para no
añadir dependencias extra al entorno del cron.
"""

import json
import os
import sys

import requests

# Hacemos que el import funcione aunque cron lo lance desde otro CWD
# (cron no garantiza que el directorio de trabajo sea el del proyecto)
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

import config
from concerts_scraper import fetch_concerts, filter_by_favorite_artists


def build_telegram_message(concerts):
    """
    Compone el mensaje HTML que enviaremos por Telegram.

    Usa etiquetas <b> y <a href> que Telegram renderiza con parse_mode='HTML'.
    Cada concierto ocupa un bloque con fecha, titulo, sala, artista favorito y link.
    """
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
        parts.append("")  # Linea en blanco entre conciertos
    return "\n".join(parts)


def main():
    """
    Punto de entrada del cron.

    Flujo:
    1. Obtiene los conciertos de la proxima semana desde la API de Wegow.
    2. Filtra por artistas favoritos del perfil del usuario.
    3. Si no hay matches, sale en silencio (es un caso normal, no un error).
    4. Verifica que las credenciales de Telegram esten configuradas.
    5. Envia el mensaje por Telegram via POST directo a la API.
    """
    # Paso 1: conciertos de la proxima semana, filtrados por perfil
    concerts = fetch_concerts(limit_days=7)
    favorites = filter_by_favorite_artists(concerts)

    if not favorites:
        # Caso normal: hay semanas sin matches. No es error, salimos en silencio.
        print("Sin conciertos favoritos esta semana.")
        return 0

    # Paso 2: comprobamos credenciales antes de intentar el envio
    token = getattr(config, "TELEGRAM_BOT_TOKEN", "")
    chat_id = getattr(config, "TELEGRAM_CHAT_ID", "")
    if not token or token == "TU_TOKEN_AQUI" or not chat_id:
        print("Falta TELEGRAM_BOT_TOKEN o TELEGRAM_CHAT_ID en config.py", file=sys.stderr)
        return 1

    # Paso 3: envio a la API de Telegram directamente con requests.post
    # (sin SDK para no añadir dependencias al entorno del cron)
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
