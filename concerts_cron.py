#!/usr/bin/env python3
import json, os, sys
import requests
from datetime import datetime, timedelta, timezone

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import config

WEGOW = "https://www.wegow.com/api/events?cities=3117735"
r = requests.get(WEGOW, headers=config.REQUEST_HEADERS, timeout=20)
events = r.json().get("events", [])
today = datetime.now(timezone.utc).date()
deadline = today + timedelta(days=7)

with open(os.path.join(os.path.dirname(os.path.abspath(__file__)), "user_profile.json"), encoding="utf-8") as f:
    profile = json.load(f)
favs = [a.lower() for a in profile.get("favorite_artists", [])]

picked = []
for e in events:
    city = e.get("city") or {}
    if city.get("name") != "Madrid":
        continue
    sd = e.get("start_date") or ""
    if not sd:
        continue
    try:
        d = datetime.strptime(sd[:10], "%Y-%m-%d").date()
    except ValueError:
        continue
    if not (today <= d <= deadline):
        continue
    artists = [a.get("name") for a in (e.get("artists") or [])]
    for a in artists:
        if a and a.lower() in favs:
            picked.append({
                "fecha": d.isoformat(),
                "hora":  sd[11:16] if len(sd) >= 16 else "",
                "titulo": e.get("title", ""),
                "recinto": (e.get("venue") or {}).get("name", ""),
                "match":  a,
                "url":    e.get("permalink", ""),
            })
            break

if not picked:
    print("Sin conciertos favoritos esta semana.")
    sys.exit(0)

parts = ["<b>Conciertos favoritos esta semana</b>", ""]
for c in picked:
    parts.append(c['fecha'] + ' ' + c['hora'])
    parts.append(c['titulo'])
    parts.append('Sala: ' + c['recinto'])
    parts.append('Artista favorito: ' + c['match'])
    parts.append('<a href="' + c['url'] + '">Mas info</a>')
    parts.append('')
msg = chr(10).join(parts)

token   = config.TELEGRAM_BOT_TOKEN
chat_id = config.TELEGRAM_CHAT_ID
resp = requests.post(
    "https://api.telegram.org/bot" + token + "/sendMessage",
    data={"chat_id": chat_id, "text": msg, "parse_mode": "HTML", "disable_web_page_preview": "true"},
    timeout=15,
)
print("Conciertos enviados: status=" + str(resp.status_code) + ", " + str(len(picked)) + " eventos.")
