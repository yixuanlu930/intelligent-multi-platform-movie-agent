"""
cache.py
========
Sistema de caché de dos niveles para datos de películas.

El enunciado de la práctica especifica que los datos de IMDb/OMDb deben
cachearse para no volver a consultar la API si se pregunta por la misma
película. Este módulo implementa esa funcionalidad.

Nivel 1 - Memoria en proceso (siempre activo):
    Diccionario Python que persiste mientras el contenedor de AWS Lambda
    esté "caliente" (en ejecución). Es la caché principal para la práctica.

Nivel 2 - DynamoDB (opcional, activar con USE_DYNAMO=true):
    Base de datos NoSQL de AWS que persiste entre ejecuciones independientes.
    Útil en producción, no necesario para la práctica básica.

Variables de entorno configurables en AWS Lambda:
    USE_DYNAMO      → "true" / "false" (default: false)
    DYNAMO_TABLE    → nombre de la tabla DynamoDB (default: IMDBMovieCache)
    CACHE_TTL_DAYS  → días de validez de la caché (default: 7)

Autores: Grupo XX - Práctica IA Agéntica
Asignatura: Agentes Inteligentes
"""

import json
import logging
import os
import re
import time
import unicodedata
from typing import Dict, Optional

logger = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# Configuración desde variables de entorno
# ---------------------------------------------------------------------------

# ¿Usar DynamoDB como segundo nivel de caché?
USE_DYNAMO = os.environ.get("USE_DYNAMO", "false").lower() == "true"

# Nombre de la tabla DynamoDB (solo relevante si USE_DYNAMO=true)
DYNAMO_TABLE = os.environ.get("DYNAMO_TABLE", "IMDBMovieCache")

# Tiempo de vida de las entradas en caché (convertido de días a segundos)
TTL_SECONDS = int(os.environ.get("CACHE_TTL_DAYS", "7")) * 86400

# ---------------------------------------------------------------------------
# Estado interno del módulo
# ---------------------------------------------------------------------------

# Caché en memoria: diccionario { clave_normalizada → { "data": dict, "ts": timestamp } }
_memory_cache = {}  # type: Dict[str, dict]

# Referencia al cliente de DynamoDB (se inicializa de forma lazy si se necesita)
_dynamo_client = None


def _get_dynamo():
    """
    Devuelve el cliente de DynamoDB, inicializándolo si todavía no existe.
    Usa el patrón Singleton (lazy initialization) para no conectar a AWS
    si DynamoDB no está habilitado o si ya existe una conexión.
    Devuelve None si DynamoDB no está disponible.
    """
    global _dynamo_client
    if _dynamo_client is None and USE_DYNAMO:
        try:
            import boto3
            _dynamo_client = boto3.resource("dynamodb").Table(DYNAMO_TABLE)
        except Exception as exc:
            logger.warning("DynamoDB no disponible: %s", exc)
    return _dynamo_client


def normalise_key(title):
    # type: (str) -> str
    """
    Genera una clave normalizada a partir del título de una película.

    Aplica las siguientes transformaciones para que variantes del mismo
    título apunten a la misma entrada de caché:
    - Elimina acentos (Sinopsis → sinopsis)
    - Convierte a minúsculas
    - Elimina artículos iniciales (el, la, the, a, an, un, una...)
    - Elimina puntuación
    - Colapsa espacios múltiples

    Ejemplo: "El Padrino" y "el padrino" → misma clave "padrino"
    """
    # Paso 1: descomponer caracteres acentuados
    nfkd = unicodedata.normalize("NFKD", title or "")
    text = "".join(c for c in nfkd if not unicodedata.combining(c))
    # Paso 2: convertir a minúsculas
    text = text.lower()
    # Paso 3: eliminar artículos al inicio (en español e inglés)
    text = re.sub(r"^(el|la|los|las|the|a|an|un|una)\s+", "", text)
    # Paso 4: reemplazar puntuación por espacios
    text = re.sub(r"[^\w\s]", " ", text)
    # Paso 5: colapsar espacios y eliminar bordes
    text = re.sub(r"\s+", " ", text).strip()
    return text


def get_cached(title):
    # type: (str) -> Optional[dict]
    """
    Busca una película en la caché.
    Comprueba primero la memoria (más rápida), luego DynamoDB (si está activo).

    Devuelve el diccionario de datos si existe y no ha expirado, o None en caso contrario.
    Si encuentra el dato en DynamoDB, lo carga también en memoria para futuras consultas.
    """
    key = normalise_key(title)
    now = time.time()

    # --- Nivel 1: búsqueda en memoria ---
    entry = _memory_cache.get(key)
    if entry:
        if now - entry["ts"] < TTL_SECONDS:
            # Dato válido → devolver directamente sin llamar a OMDb
            return entry["data"]
        # Dato expirado → eliminar de memoria
        del _memory_cache[key]

    # --- Nivel 2: búsqueda en DynamoDB (si está habilitado) ---
    table = _get_dynamo()
    if table:
        try:
            resp = table.get_item(Key={"movie_key": key})
            item = resp.get("Item")
            if item:
                ts = float(item.get("ts", 0))
                if now - ts < TTL_SECONDS:
                    # Dato válido en DynamoDB → deserializar y cargar en memoria
                    data = json.loads(item["data"])
                    _memory_cache[key] = {"data": data, "ts": ts}
                    return data
        except Exception as exc:
            logger.warning("Error leyendo DynamoDB: %s", exc)

    # No se encontró en ningún nivel → habrá que consultar la API
    return None


def set_cached(title, data):
    # type: (str, dict) -> None
    """
    Guarda los datos de una película en la caché.
    Escribe siempre en memoria y, si DynamoDB está activo, también ahí.

    El campo 'ttl' en DynamoDB es una marca de tiempo UNIX que DynamoDB
    usa internamente para borrar automáticamente las entradas expiradas.
    """
    key = normalise_key(title)
    now = time.time()

    # Guardar en memoria
    _memory_cache[key] = {"data": data, "ts": now}

    # Guardar en DynamoDB (si está habilitado)
    table = _get_dynamo()
    if table:
        try:
            table.put_item(Item={
                "movie_key": key,
                "data": json.dumps(data, ensure_ascii=False),  # Serializar el dict
                "ts": int(now),
                "ttl": int(now + TTL_SECONDS),  # DynamoDB TTL para borrado automático
            })
        except Exception as exc:
            logger.warning("Error escribiendo DynamoDB: %s", exc)


def clear_cache(title=None):
    # type: (Optional[str]) -> None
    """
    Limpia la caché en memoria.
    - Si se pasa un título, borra solo esa entrada.
    - Si no se pasa nada, borra toda la caché.
    Nota: no borra DynamoDB (eso se gestiona por TTL automáticamente).
    """
    if title:
        _memory_cache.pop(normalise_key(title), None)
    else:
        _memory_cache.clear()
