"""
lambda_function.py - Skill de Alexa "Cine Inteligente"

Recibe intents de Alexa, extrae el slot "pelicula" y consulta OMDb
mediante imdb_scraper.py. El endpoint se despliega en AWS Lambda.

Handler en AWS Lambda:
    lambda_function.handler
"""

import logging
from typing import Optional, Tuple

from ask_sdk_core.dispatch_components import AbstractExceptionHandler, AbstractRequestHandler
from ask_sdk_core.handler_input import HandlerInput
from ask_sdk_core.skill_builder import SkillBuilder
from ask_sdk_core.utils import is_intent_name, is_request_type
from ask_sdk_model.ui import SimpleCard

from imdb_scraper import get_movie_info
from cache import get_cached, set_cached

logger = logging.getLogger(__name__)
logger.setLevel(logging.INFO)

sb = SkillBuilder()

SKILL_NAME = "Cine Inteligente"
SESSION_KEY = "last_movie"


def _clean_for_speech(text):
    """Pequeña limpieza para que Alexa lea mejor algunos textos."""
    if text is None:
        return ""
    return str(text).replace("&", "y")


def _get_movie_slot(handler_input):
    # type: (HandlerInput) -> Optional[str]
    """
    Extrae el título de la película del slot 'pelicula'.
    Si Alexa ha resuelto el slot contra el tipo TITULO_PELICULA,
    preferimos el nombre canónico resuelto, por ejemplo 'Inception'.
    """
    try:
        intent = handler_input.request_envelope.request.intent
        slots = intent.slots or {}
        slot = slots.get("pelicula")
        if not slot:
            return None

        # 1) Intentar usar el valor canónico resuelto por Alexa.
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
            pass

        # 2) Fallback: valor escrito/dicho por el usuario.
        if slot.value:
            return slot.value.strip()
    except Exception as exc:
        logger.warning("No se pudo extraer el slot pelicula: %s", exc)
    return None


def _resolve_movie(handler_input):
    # type: (HandlerInput) -> Tuple[Optional[dict], Optional[str]]
    """Obtiene la película actual desde el slot o desde la sesión."""
    title = _get_movie_slot(handler_input)

    if not title:
        session = handler_input.attributes_manager.session_attributes
        title = session.get(SESSION_KEY)

    if not title:
        return None, None

    handler_input.attributes_manager.session_attributes[SESSION_KEY] = title

    info = get_cached(title)
    if info is None:
        logger.info("Consultando OMDb: %s", title)
        info = get_movie_info(title)
        if info:
            set_cached(title, info)

    return info, title


def _respond(handler_input, speech, reprompt=None, card_title=None, card_text=None, end_session=False):
    rb = handler_input.response_builder.speak(speech)
    if reprompt:
        rb = rb.ask(reprompt)
    if card_title and card_text:
        # ask-sdk-core 1.19 no tiene set_simple_card; hay que crear SimpleCard y usar set_card.
        rb = rb.set_card(SimpleCard(card_title, card_text))
    rb = rb.set_should_end_session(end_session)
    return rb.response

def _not_found_response(handler_input, title):
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


class LaunchRequestHandler(AbstractRequestHandler):
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


class GetRatingIntentHandler(AbstractRequestHandler):
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
    def can_handle(self, handler_input):
        return is_intent_name("GetSynopsisIntent")(handler_input)

    def handle(self, handler_input):
        info, title = _resolve_movie(handler_input)
        if not title:
            return _no_movie_response(handler_input)
        if not info:
            return _not_found_response(handler_input, title)

        synopsis = info.get("sinopsis", "Sin sinopsis disponible")
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
            card_text=info.get("sinopsis", ""),
        )


class GetDirectorIntentHandler(AbstractRequestHandler):
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
    def can_handle(self, handler_input):
        return is_intent_name("GetAllInfoIntent")(handler_input)

    def handle(self, handler_input):
        info, title = _resolve_movie(handler_input)
        if not title:
            return _no_movie_response(handler_input)
        if not info:
            return _not_found_response(handler_input, title)

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
    def can_handle(self, handler_input):
        return is_intent_name("SetMovieIntent")(handler_input)

    def handle(self, handler_input):
        title = _get_movie_slot(handler_input)
        if not title:
            return _no_movie_response(handler_input)

        handler_input.attributes_manager.session_attributes[SESSION_KEY] = title
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


class HelpIntentHandler(AbstractRequestHandler):
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
    def can_handle(self, handler_input):
        return is_intent_name("AMAZON.CancelIntent")(handler_input) or is_intent_name("AMAZON.StopIntent")(handler_input)

    def handle(self, handler_input):
        return _respond(handler_input, "Hasta luego. Espero haberte ayudado.", end_session=True)


class SessionEndedRequestHandler(AbstractRequestHandler):
    def can_handle(self, handler_input):
        return is_request_type("SessionEndedRequest")(handler_input)

    def handle(self, handler_input):
        return handler_input.response_builder.response


class FallbackIntentHandler(AbstractRequestHandler):
    def can_handle(self, handler_input):
        return is_intent_name("AMAZON.FallbackIntent")(handler_input)

    def handle(self, handler_input):
        speech = (
            "No he entendido eso. Puedes preguntar por la nota, el director, "
            "la sinopsis, los votos, el género o la duración de cualquier película."
        )
        return _respond(handler_input, speech, reprompt="¿Sobre qué película quieres preguntar?")


class CatchAllExceptionHandler(AbstractExceptionHandler):
    def can_handle(self, handler_input, exception):
        return True

    def handle(self, handler_input, exception):
        logger.error("Excepción en Lambda: %s", exception, exc_info=True)
        speech = "Ha ocurrido un error al buscar la información. Por favor, inténtalo de nuevo."
        return _respond(handler_input, speech, reprompt="¿Qué película quieres consultar?")


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

handler = sb.lambda_handler()
