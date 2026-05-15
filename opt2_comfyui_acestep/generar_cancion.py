#!/usr/bin/env python3
"""
Cliente Python para lanzar el workflow de Ace Step contra ComfyUI vía su API.

ComfyUI expone un endpoint HTTP `/prompt` que acepta workflows en
"API format" (que es exactamente lo que hay en `acestep_workflow.json`).
También expone un WebSocket por el que avisa cuando la generación termina.

Esta versión corrige dos problemas prácticos:
  1. El WebSocket ya no falla si ComfyUI tarda mucho sin enviar mensajes.
  2. Si el WebSocket se corta, el script consulta `/history/<prompt_id>`
     hasta encontrar la salida generada.

Uso:

    # Genera con los valores por defecto del workflow:
    python generar_cancion.py

    # Genera y espera hasta descargar el audio:
    python generar_cancion.py --wait --output cancion.flac

    # Smoke test rápido instrumental:
    python generar_cancion.py \\
        --workflow acestep_workflow_instrumental.json \\
        --seconds 8 \\
        --steps 8 \\
        --wait \\
        --output smoke_test.flac

Requisitos:
    pip install requests websocket-client
    ComfyUI corriendo en http://127.0.0.1:8188.
"""

from __future__ import annotations

import argparse
import json
import logging
import sys
import time
import urllib.parse
import urllib.request
import uuid
from pathlib import Path
from typing import Any

import requests

# websocket-client es opcional; solo se necesita si el usuario pasa --wait.
# Si no está instalado, el import falla silenciosamente y websocket queda como None.
try:
    import websocket  # websocket-client
except ImportError:
    websocket = None  # solo necesario en modo --wait

# Configuracion del log: muestra timestamp, nivel e info de la accion.
logging.basicConfig(
    format="%(asctime)s [%(levelname)s] %(message)s",
    level=logging.INFO,
)
log = logging.getLogger("acestep")

# Servidor por defecto de ComfyUI en instalacion local.
DEFAULT_SERVER = "127.0.0.1:8188"


def cargar_workflow(ruta: Path) -> dict[str, Any]:
    """Carga un workflow JSON en formato API de ComfyUI.

    Los workflows en "API format" son diccionarios donde cada clave es el
    id del nodo (str) y el valor contiene 'class_type' e 'inputs'.
    """
    return json.loads(ruta.read_text(encoding="utf-8"))


def _ids_text_encoder_positivos(workflow: dict[str, Any]) -> set[str]:
    """Devuelve los ids de los TextEncodeAceStepAudio conectados como positivo.

    Es más fiable mirar la conexión del KSampler que usar lyrics_strength,
    porque en algunos workflows el nodo negativo también puede tener
    lyrics_strength distinto de 0.
    """
    positivos: set[str] = set()

    # Busca el nodo KSampler y extrae el id de su entrada 'positive'.
    # En el workflow, 'positive' es una lista [node_id, output_index].
    for node in workflow.values():
        if node.get("class_type") != "KSampler":
            continue
        entrada = node.get("inputs", {}).get("positive")
        if isinstance(entrada, list) and entrada:
            positivos.add(str(entrada[0]))

    if positivos:
        return positivos

    # Fallback por si un workflow futuro no usa KSampler directamente:
    # busca por el titulo del nodo en _meta.
    for node_id, node in workflow.items():
        if node.get("class_type") != "TextEncodeAceStepAudio":
            continue
        title = node.get("_meta", {}).get("title", "").lower()
        if "positivo" in title or "positive" in title:
            positivos.add(str(node_id))

    return positivos


def aplicar_overrides(
    workflow: dict[str, Any], *,
    tags: str | None,
    lyrics: str | None,
    seed: int | None,
    seconds: int | None,
    steps: int | None,
) -> None:
    """Modifica el workflow in-place con los valores que pasa el usuario.

    Solo toca los nodos que corresponden al parametro dado:
    - tags / lyrics  -> TextEncodeAceStepAudio positivo
    - seed / steps   -> KSampler
    - seconds        -> EmptyAceStepLatentAudio
    El nodo negativo (que describe lo que se quiere evitar) no se modifica.
    """
    # Obtiene el conjunto de ids de los encoders positivos para no modificar el negativo.
    positivos = _ids_text_encoder_positivos(workflow)

    for node_id, node in workflow.items():
        ct = node.get("class_type")
        inputs = node.setdefault("inputs", {})

        if ct == "TextEncodeAceStepAudio" and str(node_id) in positivos:
            # Solo el encoder positivo recibe nuevos tags/letra.
            if tags is not None:
                inputs["tags"] = tags
            if lyrics is not None:
                inputs["lyrics"] = lyrics

        elif ct == "KSampler":
            # Semilla y numero de pasos del sampler de difusion.
            if seed is not None:
                inputs["seed"] = seed
            if steps is not None:
                inputs["steps"] = steps

        elif ct == "EmptyAceStepLatentAudio" and seconds is not None:
            # Duracion del audio en segundos en el espacio latente.
            inputs["seconds"] = seconds


def encolar(workflow: dict[str, Any], server: str, client_id: str) -> str:
    """Envía el workflow a ComfyUI. Devuelve el prompt_id.

    ComfyUI acepta el workflow en su /prompt y lo pone en cola.
    El client_id permite que el WebSocket filtre eventos de este cliente.
    """
    url = f"http://{server}/prompt"
    payload = {"prompt": workflow, "client_id": client_id}
    r = requests.post(url, json=payload, timeout=30)
    r.raise_for_status()
    data = r.json()
    if "error" in data:
        raise RuntimeError(f"ComfyUI rechazó el workflow: {data['error']}")
    return data["prompt_id"]


def obtener_history(server: str, prompt_id: str) -> dict[str, Any]:
    """Lee el history de un prompt. Si todavía no existe, devuelve {}.

    El endpoint /history/<id> de ComfyUI almacena el estado final del prompt
    (outputs, status, mensajes de ejecucion).
    """
    url = f"http://{server}/history/{prompt_id}"
    r = requests.get(url, timeout=30)
    r.raise_for_status()
    return r.json().get(prompt_id, {})


def _history_completado(history: dict[str, Any]) -> bool:
    """True si el history indica ejecución completada con éxito o con outputs."""
    if not history:
        return False
    status = history.get("status", {})
    # ComfyUI marca completed=True cuando la ejecucion termina.
    if status.get("completed") is True:
        return True
    # Segunda comprobacion: si hay outputs, la generacion termino.
    if history.get("outputs"):
        return True
    return False


def esperar_por_polling(server: str, prompt_id: str, timeout: int = 3600,
                        intervalo: int = 5) -> dict[str, Any]:
    """Fallback robusto: consulta `/history/<prompt_id>` hasta terminar.

    Se usa cuando el WebSocket no esta disponible o falla.
    Espera en bucle con pausa de 'intervalo' segundos entre intentos.
    """
    inicio = time.time()
    while True:
        if time.time() - inicio > timeout:
            raise TimeoutError("Timeout esperando a ComfyUI por polling.")

        history = obtener_history(server, prompt_id)
        if _history_completado(history):
            log.info("Generación terminada según history de ComfyUI.")
            return history

        log.info("ComfyUI sigue generando; esperando %ss...", intervalo)
        time.sleep(intervalo)


def esperar_finalizacion(server: str, client_id: str, prompt_id: str,
                         timeout: int = 3600) -> dict[str, Any]:
    """Espera a que ComfyUI termine y devuelve el history.

    Primero usa WebSocket. Si el WebSocket no emite mensajes durante un rato,
    o se desconecta, no aborta: comprueba `/history/<prompt_id>` y continúa.

    El evento WebSocket que indica fin de generacion es:
        {"type": "executing", "data": {"prompt_id": "...", "node": null}}
    (node == null significa que ya no hay nodos ejecutandose).
    """
    if websocket is None:
        raise SystemExit(
            "Instala 'websocket-client' para usar --wait: pip install websocket-client"
        )

    ws_url = f"ws://{server}/ws?clientId={client_id}"
    inicio = time.time()

    # Intenta abrir el WebSocket; si falla, usa polling directamente.
    try:
        ws = websocket.create_connection(ws_url, timeout=30)
    except Exception as exc:  # noqa: BLE001
        log.warning("No se pudo abrir WebSocket (%s). Uso polling por history.", exc)
        return esperar_por_polling(server, prompt_id, timeout=timeout)

    log.info("Conectado al WebSocket de ComfyUI.")

    try:
        while True:
            if time.time() - inicio > timeout:
                raise TimeoutError("Timeout esperando a ComfyUI.")

            try:
                mensaje = ws.recv()
            except websocket.WebSocketTimeoutException:
                # Ace Step puede tardar varios minutos sin enviar mensajes.
                # En lugar de abortar, comprobamos el history directamente.
                history = obtener_history(server, prompt_id)
                if _history_completado(history):
                    log.info("Generación terminada según history de ComfyUI.")
                    return history
                log.info("ComfyUI sigue generando; esperando...")
                continue
            except Exception as exc:  # noqa: BLE001
                # Cualquier otro error de red: cambia a polling.
                log.warning("WebSocket desconectado (%s). Uso polling por history.", exc)
                return esperar_por_polling(
                    server,
                    prompt_id,
                    timeout=max(1, int(timeout - (time.time() - inicio))),
                )

            # Los mensajes binarios (previsualización de audio) se ignoran.
            if not isinstance(mensaje, str):
                continue

            evt = json.loads(mensaje)
            # Cuando node es None en el evento 'executing', la cola esta vacia.
            if evt.get("type") == "executing":
                data = evt.get("data", {})
                if data.get("prompt_id") == prompt_id and data.get("node") is None:
                    log.info("Generación terminada según WebSocket.")
                    break
    finally:
        ws.close()

    # Despues de recibir el evento de fin, consulta el history para obtener outputs.
    return esperar_por_polling(server, prompt_id, timeout=60, intervalo=1)


def descargar_audio(server: str, history: dict[str, Any], destino: Path) -> Path | None:
    """Busca un archivo de salida de tipo audio en el history y lo descarga.

    El history de ComfyUI almacena los outputs de cada nodo.
    El nodo SaveAudio guarda los archivos bajo la clave 'audio' o 'audios'.
    Cada item contiene filename, subfolder y type ('output', 'temp', etc.).
    """
    outputs = history.get("outputs", {})
    for node_outputs in outputs.values():
        for clave, items in node_outputs.items():
            if clave not in ("audio", "audios"):
                continue
            for item in items:
                # Construye la URL del endpoint /view con los parametros del archivo.
                qs = urllib.parse.urlencode({
                    "filename": item["filename"],
                    "subfolder": item.get("subfolder", ""),
                    "type": item.get("type", "output"),
                })
                url = f"http://{server}/view?{qs}"
                destino.parent.mkdir(parents=True, exist_ok=True)
                log.info("Descargando audio desde %s", url)
                # Descarga directa al fichero destino.
                with urllib.request.urlopen(url, timeout=120) as src, open(destino, "wb") as dst:
                    dst.write(src.read())
                return destino
    return None


def main() -> int:
    """Punto de entrada. Parsea argumentos, lanza el workflow y opcionalmente espera."""
    parser = argparse.ArgumentParser(description="Genera una canción con Ace Step vía ComfyUI.")
    parser.add_argument(
        "--server",
        default=DEFAULT_SERVER,
        help="host:puerto donde corre ComfyUI (default: 127.0.0.1:8188).",
    )
    parser.add_argument(
        "--workflow", "-w",
        type=Path,
        default=Path(__file__).with_name("acestep_workflow.json"),
        help="Ruta al workflow JSON.",
    )
    parser.add_argument("--tags", help="Sobrescribe los tags de estilo musical.")
    parser.add_argument("--lyrics", help="Sobrescribe la letra (string).")
    parser.add_argument("--lyrics-file", type=Path, help="Lee la letra desde un fichero.")
    parser.add_argument("--seed", type=int, help="Semilla del sampler.")
    parser.add_argument("--seconds", type=int, help="Duración del audio.")
    parser.add_argument("--steps", type=int, help="Pasos del sampler.")
    parser.add_argument(
        "--wait",
        action="store_true",
        help="Espera a que ComfyUI termine y descarga el audio.",
    )
    parser.add_argument(
        "--output", "-o",
        type=Path,
        default=Path("cancion_generada.flac"),
        help="Ruta donde descargar el audio (solo con --wait).",
    )
    args = parser.parse_args()

    # Carga el workflow y aplica overrides de linea de comandos.
    workflow = cargar_workflow(args.workflow)
    lyrics = args.lyrics
    if args.lyrics_file:
        # Si se paso un fichero de letra, tiene prioridad sobre --lyrics.
        lyrics = args.lyrics_file.read_text(encoding="utf-8")

    aplicar_overrides(
        workflow,
        tags=args.tags,
        lyrics=lyrics,
        seed=args.seed,
        seconds=args.seconds,
        steps=args.steps,
    )

    # Genera un client_id unico para identificar los eventos WebSocket de esta sesion.
    client_id = uuid.uuid4().hex
    log.info("Enviando workflow a %s ...", args.server)
    try:
        prompt_id = encolar(workflow, args.server, client_id)
    except (requests.RequestException, RuntimeError) as e:
        log.error("Error encolando: %s", e)
        return 1
    log.info("Encolado con prompt_id=%s", prompt_id)

    # Sin --wait, solo encola y termina. El audio queda en ComfyUI/output/.
    if not args.wait:
        log.info("Workflow en cola. Lánzalo con --wait para descargar el audio.")
        return 0

    # Con --wait, espera la finalizacion y descarga el audio.
    try:
        history = esperar_finalizacion(args.server, client_id, prompt_id)
    except (TimeoutError, OSError, requests.RequestException) as e:
        log.error("Esperando ComfyUI: %s", e)
        return 1

    ruta = descargar_audio(args.server, history, args.output)
    if ruta:
        log.info("Audio descargado en %s", ruta)
        return 0

    log.error("No se ha encontrado audio en el history del prompt.")
    return 1


if __name__ == "__main__":
    sys.exit(main())
