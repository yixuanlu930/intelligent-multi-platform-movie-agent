#!/usr/bin/env python3
"""
Lambda de Alexa Skill para consultar informacion de peliculas.
Usa el scraper de IMDB para obtener datos y responder al usuario.

Intents:
  - GetRatingIntent: nota de la pelicula
  - GetDirectorIntent: director de la pelicula
  - GetDurationIntent: duracion de la pelicula
  - GetSynopsisIntent: sinopsis de la pelicula
  - GetVotesIntent: numero de votos
  - GetAllInfoIntent: toda la informacion
  - GetGenreIntent: genero de la pelicula

Despliegue:
  1. Subir este fichero + movie_scraper.py + config.py a AWS Lambda
  2. O usar en Alexa Developer Console como Alexa-hosted skill
"""

import json
import os
import sys

# En AWS Lambda, las dependencias estan en /opt o junto al handler
# Para desarrollo local, importamos normalmente
try:
    from ask_sdk_core.skill_builder import SkillBuilder
    from ask_sdk_core.dispatch_components import (
        AbstractRequestHandler,
        AbstractExceptionHandler,
    )
    from ask_sdk_core.utils import is_request_type, is_intent_name
    from ask_sdk_model.ui import SimpleCard
except ImportError:
    print("AVISO: ask-sdk-core no instalado. Instalar con: pip install ask-sdk-core",
          file=sys.stderr)
    sys.exit(1)

from movie_scraper import get_movie_info

# ============================================================
# Cache en memoria para la sesion Lambda
# ============================================================

movie_cache = {}

def get_cached_movie(title):
    """Obtiene info de pelicula con cache en memoria + disco."""
    key = title.lower().strip()
    if key in movie_cache:
        return movie_cache[key]
    info = get_movie_info(title)
    if info:
        movie_cache[key] = info
    return info

# ============================================================
# Handlers de Alexa
# ============================================================

class LaunchRequestHandler(AbstractRequestHandler):
    """Handler para cuando el usuario abre el skill."""
    def can_handle(self, handler_input):
        return is_request_type("LaunchRequest")(handler_input)

    def handle(self, handler_input):
        speech = ("Bienvenido al agente de peliculas. "
                  "Puedes preguntarme sobre cualquier pelicula. "
                  "Por ejemplo, di: cual es la nota de Inception.")
        return (
            handler_input.response_builder
            .speak(speech)
            .ask("¿Sobre que pelicula quieres saber?")
            .set_card(SimpleCard("Agente de Peliculas", speech))
            .response
        )


class GetRatingIntentHandler(AbstractRequestHandler):
    """Handler para preguntar la nota de una pelicula."""
    def can_handle(self, handler_input):
        return is_intent_name("GetRatingIntent")(handler_input)

    def handle(self, handler_input):
        movie_name = handler_input.request_envelope.request.intent.slots["movie"].value
        info = get_cached_movie(movie_name)

        if info:
            nota = info.get("nota", "N/A")
            speech = f"La nota de {info['titulo']} en IMDB es {nota} sobre 10."
        else:
            speech = f"Lo siento, no he encontrado la pelicula {movie_name}."

        return (
            handler_input.response_builder
            .speak(speech)
            .set_card(SimpleCard("Nota", speech))
            .response
        )


class GetDirectorIntentHandler(AbstractRequestHandler):
    """Handler para preguntar el director de una pelicula."""
    def can_handle(self, handler_input):
        return is_intent_name("GetDirectorIntent")(handler_input)

    def handle(self, handler_input):
        movie_name = handler_input.request_envelope.request.intent.slots["movie"].value
        info = get_cached_movie(movie_name)

        if info:
            director = info.get("director", "desconocido")
            speech = f"{info['titulo']} fue dirigida por {director}."
        else:
            speech = f"Lo siento, no he encontrado la pelicula {movie_name}."

        return (
            handler_input.response_builder
            .speak(speech)
            .set_card(SimpleCard("Director", speech))
            .response
        )


class GetDurationIntentHandler(AbstractRequestHandler):
    """Handler para preguntar la duracion de una pelicula."""
    def can_handle(self, handler_input):
        return is_intent_name("GetDurationIntent")(handler_input)

    def handle(self, handler_input):
        movie_name = handler_input.request_envelope.request.intent.slots["movie"].value
        info = get_cached_movie(movie_name)

        if info:
            duracion = info.get("duracion", "desconocida")
            speech = f"{info['titulo']} dura {duracion}."
        else:
            speech = f"Lo siento, no he encontrado la pelicula {movie_name}."

        return (
            handler_input.response_builder
            .speak(speech)
            .set_card(SimpleCard("Duracion", speech))
            .response
        )


class GetSynopsisIntentHandler(AbstractRequestHandler):
    """Handler para preguntar la sinopsis de una pelicula."""
    def can_handle(self, handler_input):
        return is_intent_name("GetSynopsisIntent")(handler_input)

    def handle(self, handler_input):
        movie_name = handler_input.request_envelope.request.intent.slots["movie"].value
        info = get_cached_movie(movie_name)

        if info:
            sinopsis = info.get("sinopsis", "No disponible")
            speech = f"La sinopsis de {info['titulo']} es: {sinopsis}"
        else:
            speech = f"Lo siento, no he encontrado la pelicula {movie_name}."

        return (
            handler_input.response_builder
            .speak(speech)
            .set_card(SimpleCard("Sinopsis", speech))
            .response
        )


class GetVotesIntentHandler(AbstractRequestHandler):
    """Handler para preguntar el numero de votos."""
    def can_handle(self, handler_input):
        return is_intent_name("GetVotesIntent")(handler_input)

    def handle(self, handler_input):
        movie_name = handler_input.request_envelope.request.intent.slots["movie"].value
        info = get_cached_movie(movie_name)

        if info:
            votos = info.get("votos", 0)
            speech = f"{info['titulo']} tiene {votos:,} votos en IMDB."
        else:
            speech = f"Lo siento, no he encontrado la pelicula {movie_name}."

        return (
            handler_input.response_builder
            .speak(speech)
            .set_card(SimpleCard("Votos", speech))
            .response
        )


class GetGenreIntentHandler(AbstractRequestHandler):
    """Handler para preguntar el genero de una pelicula."""
    def can_handle(self, handler_input):
        return is_intent_name("GetGenreIntent")(handler_input)

    def handle(self, handler_input):
        movie_name = handler_input.request_envelope.request.intent.slots["movie"].value
        info = get_cached_movie(movie_name)

        if info:
            genero = info.get("genero", "desconocido")
            speech = f"El genero de {info['titulo']} es {genero}."
        else:
            speech = f"Lo siento, no he encontrado la pelicula {movie_name}."

        return (
            handler_input.response_builder
            .speak(speech)
            .set_card(SimpleCard("Genero", speech))
            .response
        )


class GetAllInfoIntentHandler(AbstractRequestHandler):
    """Handler para obtener toda la informacion de una pelicula."""
    def can_handle(self, handler_input):
        return is_intent_name("GetAllInfoIntent")(handler_input)

    def handle(self, handler_input):
        movie_name = handler_input.request_envelope.request.intent.slots["movie"].value
        info = get_cached_movie(movie_name)

        if info:
            speech = (
                f"{info['titulo']}, del año {info.get('año', 'desconocido')}. "
                f"Dirigida por {info.get('director', 'desconocido')}. "
                f"Genero: {info.get('genero', 'desconocido')}. "
                f"Duracion: {info.get('duracion', 'desconocida')}. "
                f"Nota en IMDB: {info.get('nota', 'N/A')} sobre 10 "
                f"con {info.get('votos', 0):,} votos. "
                f"Sinopsis: {info.get('sinopsis', 'no disponible')}"
            )
        else:
            speech = f"Lo siento, no he encontrado la pelicula {movie_name}."

        return (
            handler_input.response_builder
            .speak(speech)
            .set_card(SimpleCard("Info Completa", speech))
            .response
        )


class HelpIntentHandler(AbstractRequestHandler):
    def can_handle(self, handler_input):
        return is_intent_name("AMAZON.HelpIntent")(handler_input)

    def handle(self, handler_input):
        speech = ("Puedes preguntarme sobre cualquier pelicula. "
                  "Prueba con: cual es la nota de Inception, "
                  "quien dirigio The Matrix, "
                  "cuanto dura Interstellar, "
                  "o dime todo sobre Pulp Fiction.")
        return (
            handler_input.response_builder
            .speak(speech)
            .ask(speech)
            .response
        )


class CancelAndStopIntentHandler(AbstractRequestHandler):
    def can_handle(self, handler_input):
        return (is_intent_name("AMAZON.CancelIntent")(handler_input) or
                is_intent_name("AMAZON.StopIntent")(handler_input))

    def handle(self, handler_input):
        return (
            handler_input.response_builder
            .speak("Hasta luego. Disfruta del cine.")
            .response
        )


class SessionEndedRequestHandler(AbstractRequestHandler):
    def can_handle(self, handler_input):
        return is_request_type("SessionEndedRequest")(handler_input)

    def handle(self, handler_input):
        return handler_input.response_builder.response


class CatchAllExceptionHandler(AbstractExceptionHandler):
    def can_handle(self, handler_input, exception):
        return True

    def handle(self, handler_input, exception):
        print(f"Error: {exception}", file=sys.stderr)
        speech = "Lo siento, ha ocurrido un error. Intentalo de nuevo."
        return (
            handler_input.response_builder
            .speak(speech)
            .ask(speech)
            .response
        )


# ============================================================
# Skill Builder
# ============================================================

sb = SkillBuilder()

sb.add_request_handler(LaunchRequestHandler())
sb.add_request_handler(GetRatingIntentHandler())
sb.add_request_handler(GetDirectorIntentHandler())
sb.add_request_handler(GetDurationIntentHandler())
sb.add_request_handler(GetSynopsisIntentHandler())
sb.add_request_handler(GetVotesIntentHandler())
sb.add_request_handler(GetGenreIntentHandler())
sb.add_request_handler(GetAllInfoIntentHandler())
sb.add_request_handler(HelpIntentHandler())
sb.add_request_handler(CancelAndStopIntentHandler())
sb.add_request_handler(SessionEndedRequestHandler())

sb.add_exception_handler(CatchAllExceptionHandler())

# Entry point para AWS Lambda
handler = sb.lambda_handler()
