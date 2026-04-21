#!/usr/bin/env python3
"""
Interfaz web Flask para consultar peliculas y cartelera de Madrid.

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
# Rutas
# ============================================================

@app.route("/")
def index():
    return render_template("index.html")


@app.route("/buscar", methods=["POST"])
def buscar():
    movie_name = request.form.get("pelicula", "").strip()
    campo = request.form.get("campo", "")

    if not movie_name:
        return render_template("index.html", error="Introduce el nombre de una pelicula.")

    info = get_movie_info(movie_name)
    if not info:
        return render_template("index.html", error=f"No se encontro: {movie_name}")

    return render_template("index.html", movie=info, campo=campo, query=movie_name)


@app.route("/api/pelicula/<nombre>")
def api_pelicula(nombre):
    """API REST para obtener info de una pelicula."""
    info = get_movie_info(nombre)
    if not info:
        return jsonify({"error": f"No se encontro: {nombre}"}), 404
    return jsonify(info)


@app.route("/cartelera")
def cartelera():
    filtrar = request.args.get("filtrar", "false") == "true"
    movies = get_cartelera_madrid()
    movies = enrich_with_sensacine(movies)

    if filtrar:
        profile = load_user_profile()
        movies = filter_by_profile(movies, profile)

    def sort_key(m):
        nota = m.get("nota_sensacine", "N/A")
        return float(nota) if nota != "N/A" else 0
    movies.sort(key=sort_key, reverse=True)

    # Convertir cines dict para serialization
    for m in movies:
        if "cines" in m and isinstance(m["cines"], dict):
            m["cines"] = {k: list(v) for k, v in m["cines"].items()}

    return render_template("index.html", cartelera=movies, filtrar=filtrar)


@app.route("/api/cartelera")
def api_cartelera():
    """API REST para obtener la cartelera."""
    movies = get_cartelera_madrid()
    movies = enrich_with_sensacine(movies)

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
