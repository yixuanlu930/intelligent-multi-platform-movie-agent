#!/usr/bin/env python3
"""
Generador de calendarios en formato iCalendar (RFC 5545).

Extraido de la celda 26 de Practica_Agentes.ipynb para que pueda importarse
desde scripts externos. Los .ics generados se pueden importar directamente
en Google Calendar, Outlook o Apple Calendar.

Uso programatico:
    from calendar_agent import concerts_to_ics, cartelera_to_ics
    concerts_to_ics([...], "agenda_conciertos.ics")
"""

import hashlib
import os
from datetime import datetime, timedelta, time, timezone

ICS_HEADER = "BEGIN:VCALENDAR\r\nVERSION:2.0\r\nPRODID:-//Agente Peliculas//ES\r\nCALSCALE:GREGORIAN\r\n"
ICS_FOOTER = "END:VCALENDAR\r\n"


def _esc(t):
    """Escapa caracteres especiales segun la especificacion iCalendar."""
    if not t:
        return ""
    return t.replace("\\", "\\\\").replace(",", "\\,").replace(";", "\\;").replace("\n", "\\n")


def _event(uid, dtstart, dtend, summary, description, location, url=None):
    """Genera el bloque VEVENT de un evento iCalendar."""
    fmt = "%Y%m%dT%H%M%S"
    fields = [
        "BEGIN:VEVENT",
        f"UID:{uid}@agente-peliculas",
        f"DTSTAMP:{datetime.now(timezone.utc).strftime(fmt)}Z",
        f"DTSTART:{dtstart.strftime(fmt)}",
        f"DTEND:{dtend.strftime(fmt)}",
        f"SUMMARY:{_esc(summary)}",
        f"DESCRIPTION:{_esc(description)}",
        f"LOCATION:{_esc(location)}",
    ]
    if url:
        fields.append(f"URL:{_esc(url)}")
    fields.append("END:VEVENT")
    return "\r\n".join(fields) + "\r\n"


def concerts_to_ics(concerts, output_path="agenda_conciertos.ics"):
    """Exporta una lista de conciertos a fichero .ics."""
    body = ICS_HEADER
    for c in concerts:
        try:
            ymd = c["fecha"]
            hh, mm = (c.get("hora") or "21:00").split(":")[:2]
            dt = datetime.strptime(f"{ymd} {hh}:{mm}", "%Y-%m-%d %H:%M")
        except Exception:
            dt = datetime.combine(datetime.strptime(c["fecha"], "%Y-%m-%d").date(), time(21, 0))

        end = dt + timedelta(hours=2)
        artists = ", ".join(c.get("artistas", []))
        # UID determinista basado en id+titulo, para que reimportar no duplique eventos
        uid = hashlib.md5(f"{c.get('id', '')}-{c.get('titulo', '')}".encode()).hexdigest()
        body += _event(uid, dt, end, c.get("titulo", "Concierto"),
                       f"Artistas: {artists}", c.get("recinto", ""), c.get("url"))
    body += ICS_FOOTER

    with open(output_path, "w", encoding="utf-8") as f:
        f.write(body)
    return os.path.abspath(output_path)


def cartelera_to_ics(movies, output_path="agenda_cartelera.ics"):
    """Exporta una lista de peliculas de cartelera a fichero .ics."""
    body = ICS_HEADER
    for m in movies:
        title = m.get("titulo", "Película")
        dt = datetime.combine(datetime.now().date(), time(21, 0))
        uid = hashlib.md5(f"{title}-{m.get('cine', '')}".encode()).hexdigest()
        desc = f"Director: {m.get('director', '')}\nNota: {m.get('nota_sensacine', '')}\n{m.get('sinopsis', '')[:200]}"
        body += _event(uid, dt, dt + timedelta(hours=2), f"Cine: {title}",
                       desc, m.get("cine", ""), m.get("url_sensacine"))
    body += ICS_FOOTER

    with open(output_path, "w", encoding="utf-8") as f:
        f.write(body)
    return os.path.abspath(output_path)


if __name__ == "__main__":
    # Smoke test minimo: genera un .ics con un concierto y otro con una pelicula
    sample_concerts = [{
        "id": "demo1", "titulo": "Concierto demo",
        "fecha": datetime.now().date().isoformat(), "hora": "21:00",
        "artistas": ["Artista demo"], "recinto": "Sala demo",
        "url": "https://example.com",
    }]
    sample_movies = [{
        "titulo": "Pelicula demo", "director": "Director demo",
        "nota_sensacine": "4.0", "sinopsis": "Sinopsis demo.",
        "cine": "Cine demo",
    }]
    print(concerts_to_ics(sample_concerts, "_smoke_conciertos.ics"))
    print(cartelera_to_ics(sample_movies, "_smoke_cartelera.ics"))
