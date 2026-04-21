#!/usr/bin/env python3
"""
Bot de Telegram para consultar informacion de peliculas y cartelera de Madrid.

Comandos:
    /start              - Bienvenida y ayuda
    /pelicula <nombre>  - Info completa de una pelicula
    /nota <nombre>      - Nota SensaCine
    /director <nombre>  - Director
    /duracion <nombre>  - Duracion
    /sinopsis <nombre>  - Sinopsis
    /cartelera          - Cartelera de Madrid
    /perfil             - Ver perfil de usuario
    /ayuda              - Ayuda

Configuracion:
    Editar TELEGRAM_BOT_TOKEN en config.py con el token de @BotFather
"""

import json
import logging
import sys

try:
    from telegram import Update
    from telegram.ext import (
        Application,
        CommandHandler,
        MessageHandler,
        ContextTypes,
        filters,
    )
except ImportError:
    print("Error: python-telegram-bot no instalado. Instalar con: pip install python-telegram-bot",
          file=sys.stderr)
    sys.exit(1)

import config
from movie_scraper import get_movie_info
from cartelera_scraper import get_cartelera_madrid, enrich_with_sensacine, filter_by_profile, load_user_profile

logging.basicConfig(
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
    level=logging.INFO,
)
logger = logging.getLogger(__name__)

# ============================================================
# Integracion con LLM Open Source (Ollama)
# ============================================================

def query_llm(prompt):
    """
    Consulta al LLM open source (Ollama) para generar respuestas naturales.
    Si Ollama no esta disponible, devuelve None.
    """
    try:
        import ollama
        response = ollama.chat(
            model=config.OLLAMA_MODEL,
            messages=[
                {"role": "system", "content": "Eres un asistente experto en cine. Responde de forma concisa y amigable en español."},
                {"role": "user", "content": prompt},
            ],
        )
        return response["message"]["content"]
    except Exception:
        return None


def format_movie_response(info, field=None):
    """Formatea la respuesta de una pelicula para Telegram."""
    escala = info.get("nota_escala", "/5")
    if field == "nota":
        text = f"⭐ <b>{info['titulo']}</b> ({info['año']})\nNota SensaCine: {info['nota']}{escala} ({info['votos']:,} votos)"
    elif field == "director":
        text = f"🎬 <b>{info['titulo']}</b> ({info['año']})\nDirector: {info['director']}"
    elif field == "duracion":
        text = f"⏱ <b>{info['titulo']}</b> ({info['año']})\nDuración: {info['duracion']}"
    elif field == "sinopsis":
        text = f"📖 <b>{info['titulo']}</b> ({info['año']})\n\n{info['sinopsis']}"
    else:
        text = (
            f"🎬 <b>{info['titulo']}</b> ({info['año']})\n"
            f"{'─' * 25}\n"
            f"⭐ Nota: {info['nota']}{escala} ({info['votos']:,} votos)\n"
            f"🎭 Género: {info['genero']}\n"
            f"👤 Director: {info['director']}\n"
            f"⏱ Duración: {info['duracion']}\n"
            f"📖 Sinopsis: {info['sinopsis']}\n"
            f"\n🔗 <a href=\"{info['url']}\">Ver en SensaCine</a>"
        )
    return text

# ============================================================
# Handlers de comandos
# ============================================================

async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text(
        "🎬 <b>Agente de Peliculas</b>\n\n"
        "Puedo darte informacion sobre cualquier pelicula.\n\n"
        "<b>Comandos:</b>\n"
        "/pelicula &lt;nombre&gt; - Info completa\n"
        "/nota &lt;nombre&gt; - Nota SensaCine\n"
        "/director &lt;nombre&gt; - Director\n"
        "/duracion &lt;nombre&gt; - Duracion\n"
        "/sinopsis &lt;nombre&gt; - Sinopsis\n"
        "/cartelera - Cartelera de Madrid\n"
        "/perfil - Ver perfil de filtrado\n"
        "/ayuda - Ayuda\n\n"
        "O simplemente escribe el nombre de una pelicula.",
        parse_mode="HTML",
    )


async def ayuda(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await start(update, context)


async def pelicula_cmd(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not context.args:
        await update.message.reply_text("Uso: /pelicula <nombre de la pelicula>")
        return

    movie_name = " ".join(context.args)
    await update.message.reply_text(f"🔍 Buscando '{movie_name}'...")

    info = get_movie_info(movie_name)
    if info:
        response = format_movie_response(info)
        escala = info.get("nota_escala", "/5")
        # Intentar enriquecer con LLM
        llm_response = query_llm(
            f"En una frase breve, recomienda o comenta sobre la pelicula '{info['titulo']}' "
            f"({info['año']}) dirigida por {info['director']}. Nota SensaCine: {info['nota']}{escala}."
        )
        if llm_response:
            response += f"\n\n🤖 <i>{llm_response}</i>"
        await update.message.reply_text(response, parse_mode="HTML", disable_web_page_preview=True)
    else:
        await update.message.reply_text(f"❌ No encontré la pelicula '{movie_name}'.")


async def nota_cmd(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not context.args:
        await update.message.reply_text("Uso: /nota <nombre de la pelicula>")
        return
    movie_name = " ".join(context.args)
    info = get_movie_info(movie_name)
    if info:
        await update.message.reply_text(format_movie_response(info, "nota"), parse_mode="HTML")
    else:
        await update.message.reply_text(f"❌ No encontré '{movie_name}'.")


async def director_cmd(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not context.args:
        await update.message.reply_text("Uso: /director <nombre de la pelicula>")
        return
    movie_name = " ".join(context.args)
    info = get_movie_info(movie_name)
    if info:
        await update.message.reply_text(format_movie_response(info, "director"), parse_mode="HTML")
    else:
        await update.message.reply_text(f"❌ No encontré '{movie_name}'.")


async def duracion_cmd(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not context.args:
        await update.message.reply_text("Uso: /duracion <nombre de la pelicula>")
        return
    movie_name = " ".join(context.args)
    info = get_movie_info(movie_name)
    if info:
        await update.message.reply_text(format_movie_response(info, "duracion"), parse_mode="HTML")
    else:
        await update.message.reply_text(f"❌ No encontré '{movie_name}'.")


async def sinopsis_cmd(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not context.args:
        await update.message.reply_text("Uso: /sinopsis <nombre de la pelicula>")
        return
    movie_name = " ".join(context.args)
    info = get_movie_info(movie_name)
    if info:
        await update.message.reply_text(format_movie_response(info, "sinopsis"), parse_mode="HTML")
    else:
        await update.message.reply_text(f"❌ No encontré '{movie_name}'.")


async def cartelera_cmd(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text("🎬 Obteniendo cartelera de Madrid... (puede tardar unos segundos)")

    movies = get_cartelera_madrid()
    movies = enrich_with_sensacine(movies)

    # Aplicar filtro si el usuario lo pide con --filtrar
    if context.args and "filtrar" in context.args:
        profile = load_user_profile()
        movies = filter_by_profile(movies, profile)

    # Ordenar por nota
    def sort_key(m):
        nota = m.get("nota_sensacine", "N/A")
        return float(nota) if nota != "N/A" else 0
    movies.sort(key=sort_key, reverse=True)

    if not movies:
        await update.message.reply_text("No se encontraron peliculas en cartelera.")
        return

    # Formatear respuesta
    lines = ["🎬 <b>CARTELERA DE CINE - MADRID</b>\n"]
    for m in movies[:15]:  # Limitar a 15 para no exceder Telegram
        nota_sc = m.get("nota_sensacine", "N/A")
        escala = m.get("nota_escala", "/5")
        nota_str = f"{nota_sc}{escala}" if nota_sc != "N/A" else "Sin nota"
        title = m["titulo"]

        lines.append(f"<b>{title}</b>")
        lines.append(f"⭐ {nota_str}")
        if m.get("genero_sensacine"):
            lines.append(f"🎭 {m['genero_sensacine']}")

        links = []
        if m.get("ecartelera_url"):
            links.append(f'<a href="{m["ecartelera_url"]}">eCartelera</a>')
        if m.get("sensacine_url"):
            links.append(f'<a href="{m["sensacine_url"]}">SensaCine</a>')
        if links:
            lines.append("🔗 " + " | ".join(links))
        lines.append("")

    lines.append(f"<b>Total: {len(movies)} peliculas</b>")
    msg = "\n".join(lines)

    await update.message.reply_text(msg, parse_mode="HTML", disable_web_page_preview=True)


async def perfil_cmd(update: Update, context: ContextTypes.DEFAULT_TYPE):
    profile = load_user_profile()
    genres = profile.get("genres", {})
    directors = profile.get("favorite_directors", [])

    text = "👤 <b>Perfil de Usuario</b>\n\n"
    text += "<b>Géneros (nota mínima):</b>\n"
    for genre, min_nota in genres.items():
        text += f"  • {genre}: {min_nota}\n"
    text += f"\n<b>Directores favoritos:</b>\n"
    for d in directors:
        text += f"  • {d}\n"
    text += "\n<i>Edita user_profile.json para cambiar preferencias.</i>"

    await update.message.reply_text(text, parse_mode="HTML")


async def text_message(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Maneja mensajes de texto libre - busca la pelicula directamente."""
    movie_name = update.message.text.strip()
    if not movie_name:
        return

    info = get_movie_info(movie_name)
    if info:
        response = format_movie_response(info)
        escala = info.get("nota_escala", "/5")
        llm_response = query_llm(
            f"En una frase breve, recomienda o comenta sobre la pelicula '{info['titulo']}' "
            f"({info['año']}) dirigida por {info['director']}. Nota SensaCine: {info['nota']}{escala}."
        )
        if llm_response:
            response += f"\n\n🤖 <i>{llm_response}</i>"
        await update.message.reply_text(response, parse_mode="HTML", disable_web_page_preview=True)
    else:
        await update.message.reply_text(
            f"❌ No encontré '{movie_name}'.\n"
            "Prueba con /ayuda para ver los comandos disponibles."
        )

# ============================================================
# Main
# ============================================================

def main():
    token = config.TELEGRAM_BOT_TOKEN
    if not token or token == "TU_TOKEN_AQUI":
        print("Error: Configura TELEGRAM_BOT_TOKEN en config.py", file=sys.stderr)
        print("  1. Habla con @BotFather en Telegram", file=sys.stderr)
        print("  2. Crea un bot con /newbot", file=sys.stderr)
        print("  3. Copia el token en config.py", file=sys.stderr)
        sys.exit(1)

    app = Application.builder().token(token).build()

    app.add_handler(CommandHandler("start", start))
    app.add_handler(CommandHandler("ayuda", ayuda))
    app.add_handler(CommandHandler("help", ayuda))
    app.add_handler(CommandHandler("pelicula", pelicula_cmd))
    app.add_handler(CommandHandler("nota", nota_cmd))
    app.add_handler(CommandHandler("director", director_cmd))
    app.add_handler(CommandHandler("duracion", duracion_cmd))
    app.add_handler(CommandHandler("sinopsis", sinopsis_cmd))
    app.add_handler(CommandHandler("cartelera", cartelera_cmd))
    app.add_handler(CommandHandler("perfil", perfil_cmd))
    app.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, text_message))

    print("Bot de Telegram iniciado. Presiona Ctrl+C para detener.")
    app.run_polling()


if __name__ == "__main__":
    main()
