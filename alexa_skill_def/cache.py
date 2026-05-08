"""
cache.py

Caché simple de dos niveles:
1) memoria de la Lambda mientras el contenedor esté caliente;
2) DynamoDB opcional si USE_DYNAMO=true.

Para la práctica basta con la caché en memoria.
"""

import json
import logging
import os
import re
import time
import unicodedata
from typing import Dict, Optional

logger = logging.getLogger(__name__)

USE_DYNAMO = os.environ.get("USE_DYNAMO", "false").lower() == "true"
DYNAMO_TABLE = os.environ.get("DYNAMO_TABLE", "IMDBMovieCache")
TTL_SECONDS = int(os.environ.get("CACHE_TTL_DAYS", "7")) * 86400

_memory_cache = {}  # type: Dict[str, dict]
_dynamo_client = None


def _get_dynamo():
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
    nfkd = unicodedata.normalize("NFKD", title or "")
    text = "".join(c for c in nfkd if not unicodedata.combining(c))
    text = text.lower()
    text = re.sub(r"^(el|la|los|las|the|a|an|un|una)\s+", "", text)
    text = re.sub(r"[^\w\s]", " ", text)
    text = re.sub(r"\s+", " ", text).strip()
    return text


def get_cached(title):
    # type: (str) -> Optional[dict]
    key = normalise_key(title)
    now = time.time()

    entry = _memory_cache.get(key)
    if entry:
        if now - entry["ts"] < TTL_SECONDS:
            return entry["data"]
        del _memory_cache[key]

    table = _get_dynamo()
    if table:
        try:
            resp = table.get_item(Key={"movie_key": key})
            item = resp.get("Item")
            if item:
                ts = float(item.get("ts", 0))
                if now - ts < TTL_SECONDS:
                    data = json.loads(item["data"])
                    _memory_cache[key] = {"data": data, "ts": ts}
                    return data
        except Exception as exc:
            logger.warning("Error leyendo DynamoDB: %s", exc)

    return None


def set_cached(title, data):
    # type: (str, dict) -> None
    key = normalise_key(title)
    now = time.time()
    _memory_cache[key] = {"data": data, "ts": now}

    table = _get_dynamo()
    if table:
        try:
            table.put_item(Item={
                "movie_key": key,
                "data": json.dumps(data, ensure_ascii=False),
                "ts": int(now),
                "ttl": int(now + TTL_SECONDS),
            })
        except Exception as exc:
            logger.warning("Error escribiendo DynamoDB: %s", exc)


def clear_cache(title=None):
    # type: (Optional[str]) -> None
    if title:
        _memory_cache.pop(normalise_key(title), None)
    else:
        _memory_cache.clear()
