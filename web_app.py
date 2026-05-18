#!/usr/bin/env python3
"""
Interfaz web Flask para consultar peliculas y cartelera de Madrid.

Rutas disponibles:
    GET  /                    → Pagina principal con buscador de peliculas
    POST /buscar              → Busca una pelicula y devuelve su ficha completa
    GET  /api/pelicula/<n>    → API REST: devuelve JSON con la info de la pelicula
    GET  /cartelera           → Cartelera de Madrid filtrada por perfil (opcional)
    GET  /api/cartelera       → API REST: devuelve JSON con la cartelera completa

Uso:
    python web_app.py
    Abrir http://localhost:5000 en el navegador
"""

import json
import sys

try:
    from flask import Flask, render_template, request, jsonify
except ImportError:
    print("Error: Flask no instalado. Instalar con: pip install flask", file=sys.stderr)
    sys.exit(1)

import config
from movie_scraper import get_movie_info
from cartelera_scraper import (
    get_cartelera_madrid,
    enrich_with_sensacine,
    filter_by_profile,
    load_user_profile,
)

app = Flask(__name__)

# ============================================================
# Rutas HTML (devuelven paginas renderizadas)
# ============================================================

@app.route("/")
def index():
    """Pagina principal: muestra el buscador de peliculas vacio."""
    return render_template("index.html")


@app.route("/buscar", methods=["POST"])
def buscar():
    """
    Procesa el formulario de busqueda de peliculas.

    Recibe el nombre de la pelicula via POST (campo 'pelicula') y
    opcionalmente un campo especifico a mostrar (campo 'campo').
    Devuelve la misma pagina con los datos de la pelicula o un mensaje de error.
    """
    movie_name = request.form.get("pelicula", "").strip()
    campo = request.form.get("campo", "")

    if not movie_name:
        return render_template("index.html", error="Introduce el nombre de una pelicula.")

    info = get_movie_info(movie_name)
    if not info:
        return render_template("index.html", error=f"No se encontro: {movie_name}")

    return render_template("index.html", movie=info, campo=campo, query=movie_name)


@app.route("/cartelera")
def cartelera():
    """
    Muestra la cartelera de cine de Madrid enriquecida con datos de SensaCine.

    Parametro de query:
        filtrar=true → aplica el filtro de perfil del usuario (user_profile.json)

    Las peliculas se ordenan por nota SensaCine descendente.
    Los cines se convierten de dict a lista para que el template los itere correctamente.
    """
    filtrar = request.args.get("filtrar", "false") == "true"
    movies = get_cartelera_madrid()
    movies = enrich_with_sensacine(movies)

    if filtrar:
        profile = load_user_profile()
        movies = filter_by_profile(movies, profile)

    # Ordenar por nota SensaCine descendente (mejor nota primero)
    def sort_key(m):
        nota = m.get("nota_sensacine", "N/A")
        return float(nota) if nota != "N/A" else 0
    movies.sort(key=sort_key, reverse=True)

    # Convertir cines dict a lista para serialization correcta en el template
    for m in movies:
        if "cines" in m and isinstance(m["cines"], dict):
            m["cines"] = {k: list(v) for k, v in m["cines"].items()}

    return render_template("index.html", cartelera=movies, filtrar=filtrar)


# ============================================================
# Rutas API REST (devuelven JSON)
# ============================================================

@app.route("/api/pelicula/<nombre>")
def api_pelicula(nombre):
    """
    API REST: devuelve la informacion de una pelicula en formato JSON.

    Parametro de ruta:
        nombre → titulo de la pelicula a buscar

    Respuestas:
        200 + JSON con la info si se encuentra la pelicula
        404 + JSON con mensaje de error si no se encuentra
    """
    info = get_movie_info(nombre)
    if not info:
        return jsonify({"error": f"No se encontro: {nombre}"}), 404
    return jsonify(info)


@app.route("/api/cartelera")
def api_cartelera():
    """
    API REST: devuelve la cartelera de Madrid en formato JSON.

    Devuelve la lista completa sin filtrar por perfil, ordenada por nota SensaCine.
    Los cines se convierten de dict a lista para que el JSON sea serializable.
    Este endpoint puede ser consumido por otros servicios (ej: el agente LangChain).
    """
    movies = get_cartelera_madrid()
    movies = enrich_with_sensacine(movies)

    # Convertir cines dict a lista serializable para JSON
    for m in movies:
        if "cines" in m and isinstance(m["cines"], dict):
            m["cines"] = {k: list(v) for k, v in m["cines"].items()}

    def sort_key(m):
        nota = m.get("nota_sensacine", "N/A")
        return float(nota) if nota != "N/A" else 0
    movies.sort(key=sort_key, reverse=True)

    return jsonify(movies)


if __name__ == "__main__":
    app.run(
        host=config.FLASK_HOST,
        port=config.FLASK_PORT,
        debug=config.FLASK_DEBUG,
    )
