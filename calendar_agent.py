#!/usr/bin/env python3
"""
Generador de calendarios en formato iCalendar (RFC 5545).

Extraido de la celda 26 de Practica_Agentes.ipynb para que pueda importarse
desde scripts externos. Los .ics generados se pueden importar directamente
en Google Calendar, Outlook o Apple Calendar.

Formato de entrada esperado:
  - concerts: lista de dicts con claves id, titulo, fecha (YYYY-MM-DD),
              hora (HH:MM), artistas (lista), recinto, url.
  - movies:   lista de dicts con claves titulo, director, nota_sensacine,
              sinopsis, cine, url_sensacine.

Uso programatico:
    from calendar_agent import concerts_to_ics, cartelera_to_ics
    concerts_to_ics([...], "agenda_conciertos.ics")
"""

import hashlib
import os
from datetime import datetime, timedelta, time, timezone

# Cabecera y pie obligatorios del formato iCalendar (RFC 5545).
# PRODID identifica la aplicacion que genero el fichero.
# CALSCALE:GREGORIAN indica que usamos el calendario gregoriano estandar.
ICS_HEADER = "BEGIN:VCALENDAR\r\nVERSION:2.0\r\nPRODID:-//Agente Peliculas//ES\r\nCALSCALE:GREGORIAN\r\n"
ICS_FOOTER = "END:VCALENDAR\r\n"


def _esc(t):
    """
    Escapa caracteres especiales segun la especificacion iCalendar (RFC 5545).

    Los caracteres \\ , ; y saltos de linea tienen significado especial en el
    formato .ics y deben ir precedidos de una barra invertida para ser literales.
    """
    if not t:
        return ""
    return t.replace("\\", "\\\\").replace(",", "\\,").replace(";", "\\;").replace("\n", "\\n")


def _event(uid, dtstart, dtend, summary, description, location, url=None):
    """
    Genera el bloque VEVENT completo de un evento iCalendar.

    Parametros:
        uid         → identificador unico del evento (debe ser persistente para
                      evitar duplicados al reimportar el mismo .ics)
        dtstart     → datetime de inicio del evento
        dtend       → datetime de fin del evento
        summary     → titulo del evento (visible en el calendario)
        description → descripcion larga del evento
        location    → lugar donde se celebra
        url         → enlace opcional con mas informacion

    Devuelve el bloque VEVENT como string con terminadores CRLF (obligatorio en RFC 5545).
    """
    fmt = "%Y%m%dT%H%M%S"
    fields = [
        "BEGIN:VEVENT",
        f"UID:{uid}@agente-peliculas",
        # DTSTAMP es la fecha en que se genero el evento (ahora, en UTC)
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
    # RFC 5545 exige CRLF (\r\n) como terminador de linea
    return "\r\n".join(fields) + "\r\n"


def concerts_to_ics(concerts, output_path="agenda_conciertos.ics"):
    """
    Exporta una lista de conciertos a un fichero .ics importable en Google Calendar.

    Para cada concierto crea un VEVENT con:
    - Titulo del concierto como SUMMARY
    - Lista de artistas en la DESCRIPTION
    - Recinto como LOCATION
    - Duracion estimada de 2 horas (no todos los eventos publican hora de fin)
    - UID generado con MD5(id+titulo) para que reimportar no duplique eventos

    Devuelve la ruta absoluta del fichero generado.
    """
    body = ICS_HEADER
    for c in concerts:
        try:
            ymd = c["fecha"]
            hh, mm = (c.get("hora") or "21:00").split(":")[:2]
            dt = datetime.strptime(f"{ymd} {hh}:{mm}", "%Y-%m-%d %H:%M")
        except Exception:
            # Si la hora no tiene formato esperado, usamos las 21:00 como hora por defecto
            dt = datetime.combine(datetime.strptime(c["fecha"], "%Y-%m-%d").date(), time(21, 0))

        end = dt + timedelta(hours=2)
        artists = ", ".join(c.get("artistas", []))
        # UID determinista basado en id+titulo: si el usuario reimporta el mismo .ics
        # el calendario no duplicara el evento (lo reconoce por el UID)
        uid = hashlib.md5(f"{c.get('id', '')}-{c.get('titulo', '')}".encode()).hexdigest()
        body += _event(uid, dt, end, c.get("titulo", "Concierto"),
                       f"Artistas: {artists}", c.get("recinto", ""), c.get("url"))
    body += ICS_FOOTER

    with open(output_path, "w", encoding="utf-8") as f:
        f.write(body)
    return os.path.abspath(output_path)


def cartelera_to_ics(movies, output_path="agenda_cartelera.ics"):
    """
    Exporta una lista de peliculas de cartelera a un fichero .ics.

    Para cada pelicula crea un VEVENT con:
    - Titulo como SUMMARY (prefijado con "Cine: " para distinguirlos en el calendario)
    - Director, nota y primeros 200 chars de sinopsis en la DESCRIPTION
    - Cine como LOCATION
    - Hora de inicio a las 21:00 (hora estimada; no disponible en ecartelera)
    - Duracion estimada de 2 horas

    Devuelve la ruta absoluta del fichero generado.
    """
    body = ICS_HEADER
    for m in movies:
        title = m.get("titulo", "Película")
        # Usamos la fecha actual a las 21:00 como referencia (peliculas en cartelera hoy)
        dt = datetime.combine(datetime.now().date(), time(21, 0))
        # UID determinista basado en titulo+cine para evitar duplicados al reimportar
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
    # para verificar que el formato es valido sin necesitar datos reales
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
