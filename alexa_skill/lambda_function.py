"""
lambda_function.py
==================
Skill de Alexa "Cine Inteligente" — función Lambda de AWS.

Este archivo es el punto de entrada que AWS Lambda ejecuta cuando
Alexa recibe un comando del usuario. Implementa todos los intents
definidos en interactionModel.json.

Flujo general de una petición:
    1. El usuario habla a Alexa ("cuál es la nota de Inception")
    2. Alexa analiza la frase con el modelo de interacción y genera un intent
    3. AWS Lambda ejecuta este archivo (función handler)
    4. El handler extrae el slot "pelicula" y consulta OMDb via imdb_scraper.py
    5. Se usa cache.py para evitar llamadas repetidas a la API
    6. Se construye una respuesta de voz y se devuelve a Alexa

Handler en AWS Lambda:
    lambda_function.handler

Intents implementados:
    GetRatingIntent     → nota de la película
    GetVotesIntent      → número de votos
    GetSynopsisIntent   → sinopsis
    GetDirectorIntent   → director
    GetDurationIntent   → duración
    GetGenreIntent      → género
    GetAllInfoIntent    → ficha completa
    SetMovieIntent      → precargar película en sesión

Autores: Grupo XX - Práctica IA Agéntica
Asignatura: Agentes Inteligentes
"""

import logging
from typing import Optional, Tuple

# SDK oficial de Alexa para Python
from ask_sdk_core.dispatch_components import AbstractExceptionHandler, AbstractRequestHandler
from ask_sdk_core.handler_input import HandlerInput
from ask_sdk_core.skill_builder import SkillBuilder
from ask_sdk_core.utils import is_intent_name, is_request_type
from ask_sdk_model.ui import SimpleCard

# Módulos propios del proyecto
from imdb_scraper import get_movie_info
from cache import get_cached, set_cached

logger = logging.getLogger(__name__)
logger.setLevel(logging.INFO)

# El SkillBuilder es el contenedor principal del skill.
# Se le añaden todos los handlers y al final genera el handler de Lambda.
sb = SkillBuilder()

# Nombre del skill (aparece en las cards de la app de Alexa)
SKILL_NAME = "Cine Inteligente"

# Clave bajo la que guardamos la película activa en los atributos de sesión.
# Permite que el usuario diga "cuánto dura" sin repetir el nombre de la película.
SESSION_KEY = "last_movie"


# ---------------------------------------------------------------------------
# Funciones auxiliares
# ---------------------------------------------------------------------------

def _clean_for_speech(text):
    """
    Pequeña limpieza de texto antes de enviarlo a Alexa como voz.
    Reemplaza '&' por 'y' porque el sintetizador de voz no lee bien el símbolo.
    """
    if text is None:
        return ""
    return str(text).replace("&", "y")


def _get_movie_slot(handler_input):
    # type: (HandlerInput) -> Optional[str]
    """
    Extrae el nombre de la película del slot 'pelicula' del intent.

    Alexa puede resolver slots contra un tipo personalizado (TITULO_PELICULA),
    lo que permite mapear "El Caballero Oscuro" al valor canónico "The Dark Knight".
    Este método intenta usar ese valor canónico primero, y si no existe,
    usa directamente el texto que dijo el usuario.

    Devuelve None si no hay ningún slot disponible.
    """
    try:
        intent = handler_input.request_envelope.request.intent
        slots = intent.slots or {}
        slot = slots.get("pelicula")
        if not slot:
            return None

        # Intento 1: valor canónico resuelto por Alexa contra TITULO_PELICULA
        # El código "ER_SUCCESS_MATCH" indica que Alexa encontró una coincidencia
        try:
            resolutions = slot.resolutions.resolutions_per_authority
            if resolutions:
                for resolution in resolutions:
                    if resolution.status and str(resolution.status.code) == "ER_SUCCESS_MATCH":
                        values = resolution.values or []
                        if values:
                            canonical = values[0].value.name
                            if canonical:
                                return canonical.strip()
        except Exception:
            pass  # Si falla la resolución, usamos el valor literal

        # Intento 2: valor literal que dijo el usuario
        if slot.value:
            return slot.value.strip()

    except Exception as exc:
        logger.warning("No se pudo extraer el slot pelicula: %s", exc)
    return None


def _resolve_movie(handler_input):
    # type: (HandlerInput) -> Tuple[Optional[dict], Optional[str]]
    """
    Función central: obtiene los datos de la película que el usuario está consultando.

    Lógica de resolución:
    1. ¿Hay un slot 'pelicula' en este turno? → usar ese título.
    2. Si no, ¿hay una película guardada en la sesión? → usar esa (conversación multi-turno).
    3. Si tampoco → no hay película, devolver (None, None).

    Una vez resuelto el título:
    - Guarda en sesión para el siguiente turno.
    - Busca en caché; si no está, llama a OMDb y cachea el resultado.

    Devuelve una tupla (info_dict, titulo_str).
    """
    # Paso 1: intentar obtener título del slot del intent actual
    title = _get_movie_slot(handler_input)

    # Paso 2: si no hay slot, recuperar de la sesión (pregunta anterior)
    if not title:
        session = handler_input.attributes_manager.session_attributes
        title = session.get(SESSION_KEY)

    if not title:
        return None, None

    # Guardar el título en sesión para siguientes preguntas
    handler_input.attributes_manager.session_attributes[SESSION_KEY] = title

    # Paso 3: buscar datos (caché primero, luego OMDb)
    info = get_cached(title)
    if info is None:
        logger.info("Consultando OMDb: %s", title)
        info = get_movie_info(title)
        if info:
            set_cached(title, info)  # Guardar en caché para futuras preguntas

    return info, title


def _respond(handler_input, speech, reprompt=None, card_title=None, card_text=None, end_session=False):
    """
    Construye y devuelve una respuesta de Alexa.

    Parámetros:
        speech      → texto que Alexa leerá en voz alta (obligatorio)
        reprompt    → texto que Alexa dice si el usuario no responde en ~8s
        card_title  → título de la card visible en la app de Alexa (opcional)
        card_text   → contenido de la card (opcional)
        end_session → True para cerrar la sesión, False para seguir escuchando
    """
    rb = handler_input.response_builder.speak(speech)
    if reprompt:
        rb = rb.ask(reprompt)
    if card_title and card_text:
        # SimpleCard muestra texto en la pantalla de la app de Alexa
        rb = rb.set_card(SimpleCard(card_title, card_text))
    rb = rb.set_should_end_session(end_session)
    return rb.response


def _not_found_response(handler_input, title):
    """Respuesta estándar cuando no se encuentra la película en OMDb."""
    speech = (
        "Lo siento, no he encontrado información sobre la película {}. "
        "Intenta con otro título o comprueba si está escrito correctamente."
    ).format(_clean_for_speech(title))
    return _respond(
        handler_input,
        speech,
        reprompt="¿Sobre qué película quieres preguntar?",
        card_title="Película no encontrada",
        card_text=speech,
    )


def _no_movie_response(handler_input):
    """Respuesta cuando el usuario no especificó ninguna película."""
    speech = (
        "¿Sobre qué película quieres saber? "
        "Por ejemplo, puedes decir: dime la nota de El Padrino."
    )
    return _respond(
        handler_input,
        speech,
        reprompt="¿Cuál es el nombre de la película?",
        card_title=SKILL_NAME,
        card_text=speech,
    )


# ---------------------------------------------------------------------------
# Handlers de peticiones del sistema
# ---------------------------------------------------------------------------

class LaunchRequestHandler(AbstractRequestHandler):
    """
    Se ejecuta cuando el usuario abre el skill sin decir nada más.
    Ejemplo: "Alexa, abre Cine Inteligente"
    """
    def can_handle(self, handler_input):
        return is_request_type("LaunchRequest")(handler_input)

    def handle(self, handler_input):
        speech = (
            "Bienvenido a {}. Puedo darte información sobre películas: "
            "nota, número de votos, director, sinopsis, duración y género. "
            "Por ejemplo, dime: cuál es la nota de Inception."
        ).format(SKILL_NAME)
        return _respond(
            handler_input,
            speech,
            reprompt="¿Sobre qué película quieres preguntar?",
            card_title=SKILL_NAME,
            card_text="Pregunta por nota, votos, director, sinopsis, duración o género.",
        )


# ---------------------------------------------------------------------------
# Handlers de intents de película
# (cada uno corresponde a un intent en interactionModel.json)
# ---------------------------------------------------------------------------

class GetRatingIntentHandler(AbstractRequestHandler):
    """Responde a preguntas sobre la nota de una película en IMDb."""
    def can_handle(self, handler_input):
        return is_intent_name("GetRatingIntent")(handler_input)

    def handle(self, handler_input):
        info, title = _resolve_movie(handler_input)
        if not title:
            return _no_movie_response(handler_input)
        if not info:
            return _not_found_response(handler_input, title)

        speech = (
            "La película {} del año {} tiene una nota de {} sobre diez en IMDB, "
            "con {} votos."
        ).format(
            _clean_for_speech(info.get("titulo", title)),
            info.get("anio", ""),
            info.get("nota", "N/D"),
            info.get("votos", "N/D"),
        )
        card_text = "{}/10 - {} votos".format(info.get("nota", "N/D"), info.get("votos", "N/D"))
        return _respond(
            handler_input,
            speech,
            reprompt="¿Quieres saber algo más sobre esta película?",
            card_title="Nota: {}".format(info.get("titulo", title)),
            card_text=card_text,
        )


class GetVotesIntentHandler(AbstractRequestHandler):
    """Responde a preguntas sobre el número de votos de una película."""
    def can_handle(self, handler_input):
        return is_intent_name("GetVotesIntent")(handler_input)

    def handle(self, handler_input):
        info, title = _resolve_movie(handler_input)
        if not title:
            return _no_movie_response(handler_input)
        if not info:
            return _not_found_response(handler_input, title)

        speech = "{} tiene {} votos en IMDB, con una nota media de {}.".format(
            _clean_for_speech(info.get("titulo", title)),
            info.get("votos", "N/D"),
            info.get("nota", "N/D"),
        )
        return _respond(handler_input, speech, reprompt="¿Quieres saber algo más sobre esta película?")


class GetSynopsisIntentHandler(AbstractRequestHandler):
    """Responde a preguntas sobre el argumento o sinopsis de una película."""
    def can_handle(self, handler_input):
        return is_intent_name("GetSynopsisIntent")(handler_input)

    def handle(self, handler_input):
        info, title = _resolve_movie(handler_input)
        if not title:
            return _no_movie_response(handler_input)
        if not info:
            return _not_found_response(handler_input, title)

        synopsis = info.get("sinopsis", "Sin sinopsis disponible")
        # Limitamos a 550 caracteres para que la respuesta de voz no sea demasiado larga.
        # rsplit(" ", 1) corta por la última palabra completa para no partir palabras.
        if len(synopsis) > 550:
            synopsis = synopsis[:550].rsplit(" ", 1)[0] + "..."

        speech = "La sinopsis de {} es: {}".format(
            _clean_for_speech(info.get("titulo", title)),
            _clean_for_speech(synopsis),
        )
        return _respond(
            handler_input,
            speech,
            reprompt="¿Quieres saber algo más sobre esta película?",
            card_title="Sinopsis: {}".format(info.get("titulo", title)),
            card_text=info.get("sinopsis", ""),  # La card muestra la sinopsis completa
        )


class GetDirectorIntentHandler(AbstractRequestHandler):
    """Responde a preguntas sobre el director de una película."""
    def can_handle(self, handler_input):
        return is_intent_name("GetDirectorIntent")(handler_input)

    def handle(self, handler_input):
        info, title = _resolve_movie(handler_input)
        if not title:
            return _no_movie_response(handler_input)
        if not info:
            return _not_found_response(handler_input, title)

        speech = "{} fue dirigida por {}.".format(
            _clean_for_speech(info.get("titulo", title)),
            _clean_for_speech(info.get("director", "desconocido")),
        )
        return _respond(
            handler_input,
            speech,
            reprompt="¿Quieres saber algo más sobre esta película?",
            card_title="Director: {}".format(info.get("titulo", title)),
            card_text=info.get("director", ""),
        )


class GetDurationIntentHandler(AbstractRequestHandler):
    """Responde a preguntas sobre la duración de una película."""
    def can_handle(self, handler_input):
        return is_intent_name("GetDurationIntent")(handler_input)

    def handle(self, handler_input):
        info, title = _resolve_movie(handler_input)
        if not title:
            return _no_movie_response(handler_input)
        if not info:
            return _not_found_response(handler_input, title)

        speech = "{} tiene una duración de {}.".format(
            _clean_for_speech(info.get("titulo", title)),
            info.get("duracion", "desconocida"),
        )
        return _respond(handler_input, speech, reprompt="¿Quieres saber algo más sobre esta película?")


class GetGenreIntentHandler(AbstractRequestHandler):
    """Responde a preguntas sobre el género de una película."""
    def can_handle(self, handler_input):
        return is_intent_name("GetGenreIntent")(handler_input)

    def handle(self, handler_input):
        info, title = _resolve_movie(handler_input)
        if not title:
            return _no_movie_response(handler_input)
        if not info:
            return _not_found_response(handler_input, title)

        speech = "{} es una película de {}.".format(
            _clean_for_speech(info.get("titulo", title)),
            _clean_for_speech(info.get("generos", "género desconocido")),
        )
        return _respond(handler_input, speech, reprompt="¿Quieres saber algo más sobre esta película?")


class GetAllInfoIntentHandler(AbstractRequestHandler):
    """
    Responde con la ficha completa de una película:
    título, año, director, género, duración, nota, votos y sinopsis resumida.
    """
    def can_handle(self, handler_input):
        return is_intent_name("GetAllInfoIntent")(handler_input)

    def handle(self, handler_input):
        info, title = _resolve_movie(handler_input)
        if not title:
            return _no_movie_response(handler_input)
        if not info:
            return _not_found_response(handler_input, title)

        # La sinopsis se acorta a 300 chars en la ficha completa
        # para dejar espacio al resto de datos
        synopsis_short = info.get("sinopsis", "")
        if len(synopsis_short) > 300:
            synopsis_short = synopsis_short[:300].rsplit(" ", 1)[0] + "..."

        speech = (
            "{}, del año {}, dirigida por {}. Género: {}. Duración: {}. "
            "Nota en IMDB: {} sobre diez, con {} votos. Argumento: {}"
        ).format(
            _clean_for_speech(info.get("titulo", title)),
            info.get("anio", ""),
            _clean_for_speech(info.get("director", "desconocido")),
            _clean_for_speech(info.get("generos", "desconocido")),
            info.get("duracion", "desconocida"),
            info.get("nota", "N/D"),
            info.get("votos", "N/D"),
            _clean_for_speech(synopsis_short),
        )
        return _respond(
            handler_input,
            speech,
            reprompt="¿Quieres saber algo más sobre esta película?",
            card_title=info.get("titulo", title),
            card_text=speech,
        )


class SetMovieIntentHandler(AbstractRequestHandler):
    """
    Permite precargar una película en la sesión sin hacer una pregunta concreta.
    Ejemplo: "quiero preguntar por Inception"
    Así el usuario puede decir a continuación solo "cuánto dura" sin repetir el título.
    """
    def can_handle(self, handler_input):
        return is_intent_name("SetMovieIntent")(handler_input)

    def handle(self, handler_input):
        title = _get_movie_slot(handler_input)
        if not title:
            return _no_movie_response(handler_input)

        # Guardar en sesión
        handler_input.attributes_manager.session_attributes[SESSION_KEY] = title

        # Pre-cargar los datos en caché para agilizar las siguientes preguntas
        info = get_cached(title)
        if info is None:
            info = get_movie_info(title)
            if info:
                set_cached(title, info)

        if info:
            speech = (
                "De acuerdo, tengo {} del año {}. Puedes preguntarme por la nota, "
                "los votos, el director, la duración, la sinopsis o el género."
            ).format(_clean_for_speech(info.get("titulo", title)), info.get("anio", ""))
        else:
            speech = "He guardado {}, pero no encontré información en OMDb.".format(
                _clean_for_speech(title)
            )
        return _respond(handler_input, speech, reprompt="¿Qué quieres saber de esta película?")


# ---------------------------------------------------------------------------
# Handlers de intents de Amazon (obligatorios en todo skill)
# ---------------------------------------------------------------------------

class HelpIntentHandler(AbstractRequestHandler):
    """Se activa cuando el usuario dice 'ayuda'."""
    def can_handle(self, handler_input):
        return is_intent_name("AMAZON.HelpIntent")(handler_input)

    def handle(self, handler_input):
        speech = (
            "Con {} puedes preguntar cosas como: cuál es la nota de Inception, "
            "quién dirigió El Padrino, de qué trata Matrix, o dime todo sobre Oppenheimer. "
            "¿Sobre qué película quieres preguntar?"
        ).format(SKILL_NAME)
        return _respond(handler_input, speech, reprompt="¿Sobre qué película quieres preguntar?")


class CancelAndStopIntentHandler(AbstractRequestHandler):
    """Se activa cuando el usuario dice 'cancela' o 'para'. Cierra el skill."""
    def can_handle(self, handler_input):
        return (
            is_intent_name("AMAZON.CancelIntent")(handler_input)
            or is_intent_name("AMAZON.StopIntent")(handler_input)
        )

    def handle(self, handler_input):
        # end_session=True cierra la sesión completamente
        return _respond(handler_input, "Hasta luego. Espero haberte ayudado.", end_session=True)


class SessionEndedRequestHandler(AbstractRequestHandler):
    """
    Se ejecuta cuando la sesión termina (por timeout, error o el usuario dice 'para').
    No devuelve respuesta de voz; solo permite hacer limpieza si fuera necesario.
    """
    def can_handle(self, handler_input):
        return is_request_type("SessionEndedRequest")(handler_input)

    def handle(self, handler_input):
        return handler_input.response_builder.response


class FallbackIntentHandler(AbstractRequestHandler):
    """
    Captura frases que Alexa no sabe asignar a ningún intent.
    Siempre hay que registrarlo para evitar errores en producción.
    """
    def can_handle(self, handler_input):
        return is_intent_name("AMAZON.FallbackIntent")(handler_input)

    def handle(self, handler_input):
        speech = (
            "No he entendido eso. Puedes preguntar por la nota, el director, "
            "la sinopsis, los votos, el género o la duración de cualquier película."
        )
        return _respond(handler_input, speech, reprompt="¿Sobre qué película quieres preguntar?")


# ---------------------------------------------------------------------------
# Handler de excepciones
# ---------------------------------------------------------------------------

class CatchAllExceptionHandler(AbstractExceptionHandler):
    """
    Captura cualquier excepción no controlada en los handlers.
    Sin esto, un error en producción causaría una respuesta vacía o timeout.
    Lo registramos en CloudWatch Logs para poder depurar.
    """
    def can_handle(self, handler_input, exception):
        return True  # Captura absolutamente cualquier excepción

    def handle(self, handler_input, exception):
        logger.error("Excepción en Lambda: %s", exception, exc_info=True)
        speech = "Ha ocurrido un error al buscar la información. Por favor, inténtalo de nuevo."
        return _respond(handler_input, speech, reprompt="¿Qué película quieres consultar?")


# ---------------------------------------------------------------------------
# Registro de handlers en el SkillBuilder
# El orden importa: se evalúan en orden hasta que can_handle() devuelve True.
# Los handlers de Amazon deben ir después de los propios del skill.
# ---------------------------------------------------------------------------

sb.add_request_handler(LaunchRequestHandler())
sb.add_request_handler(GetRatingIntentHandler())
sb.add_request_handler(GetVotesIntentHandler())
sb.add_request_handler(GetSynopsisIntentHandler())
sb.add_request_handler(GetDirectorIntentHandler())
sb.add_request_handler(GetDurationIntentHandler())
sb.add_request_handler(GetGenreIntentHandler())
sb.add_request_handler(GetAllInfoIntentHandler())
sb.add_request_handler(SetMovieIntentHandler())
sb.add_request_handler(HelpIntentHandler())
sb.add_request_handler(CancelAndStopIntentHandler())
sb.add_request_handler(SessionEndedRequestHandler())
sb.add_request_handler(FallbackIntentHandler())
sb.add_exception_handler(CatchAllExceptionHandler())

# Punto de entrada que AWS Lambda invoca al recibir una petición de Alexa.
# AWS busca esta variable con el nombre configurado en el handler: "lambda_function.handler"
handler = sb.lambda_handler()
