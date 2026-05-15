"""
Tests del workflow Ace Step y del cliente Python.

No requieren tener ComfyUI corriendo. Solo validan:
  - que los JSON tienen la estructura esperada
  - que `aplicar_overrides` modifica los nodos correctos

    python -m pytest test_workflow.py -v

Resultado esperado al ejecutar: 8 tests pasados.
"""

import json
from pathlib import Path

import pytest

# Importa las dos funciones publicas del cliente que se van a probar.
from generar_cancion import cargar_workflow, aplicar_overrides

# Directorio raiz de la practica (donde viven los JSON).
AQUI = Path(__file__).parent


# ---------------------------------------------------------------------------
# Validación estructural del workflow
# ---------------------------------------------------------------------------

@pytest.mark.parametrize("nombre", [
    "acestep_workflow.json",
    "acestep_workflow_instrumental.json",
])
def test_workflow_tiene_nodos_minimos(nombre):
    """Comprueba que cada workflow contiene todos los tipos de nodo obligatorios.

    ComfyUI necesita exactamente estos nodos para generar audio con Ace Step:
    - CheckpointLoaderSimple: carga el modelo ace_step_v1_3.5b.safetensors.
    - EmptyAceStepLatentAudio: crea el espacio latente de audio vacio.
    - TextEncodeAceStepAudio: codifica el prompt textual (x2: positivo y negativo).
    - KSampler: aplica el proceso de difusion para generar el latente.
    - VAEDecodeAudio: decodifica el latente a audio en formato de onda.
    - SaveAudio: guarda el resultado como .flac en la carpeta output de ComfyUI.
    """
    wf = cargar_workflow(AQUI / nombre)
    tipos = {node["class_type"] for node in wf.values()}
    obligatorios = {
        "CheckpointLoaderSimple",
        "EmptyAceStepLatentAudio",
        "TextEncodeAceStepAudio",
        "KSampler",
        "VAEDecodeAudio",
        "SaveAudio",
    }
    faltan = obligatorios - tipos
    assert not faltan, f"Faltan nodos en {nombre}: {faltan}"


@pytest.mark.parametrize("nombre", [
    "acestep_workflow.json",
    "acestep_workflow_instrumental.json",
])
def test_workflow_tiene_dos_text_encoders(nombre):
    """Necesitamos uno positivo y uno negativo.

    Ace Step requiere dos TextEncodeAceStepAudio:
    - Positivo: describe el estilo musical y la letra que se quiere generar.
    - Negativo: describe lo que se quiere evitar (p.ej. voces en el instrumental).
    """
    wf = cargar_workflow(AQUI / nombre)
    encoders = [n for n in wf.values() if n["class_type"] == "TextEncodeAceStepAudio"]
    assert len(encoders) == 2


# ---------------------------------------------------------------------------
# Tests de aplicar_overrides
# ---------------------------------------------------------------------------

def test_override_tags_y_seed():
    """Verifica que aplicar_overrides modifica tags en el encoder positivo y seed en KSampler.

    El encoder positivo es el que esta conectado a la entrada 'positive' del KSampler.
    El encoder negativo no debe modificarse aunque cambiemos los tags.
    """
    wf = cargar_workflow(AQUI / "acestep_workflow.json")
    aplicar_overrides(
        wf, tags="jazz, slow, sax", lyrics=None,
        seed=777, seconds=None, steps=None,
    )

    # El sampler recibió la nueva semilla.
    sampler = next(n for n in wf.values() if n["class_type"] == "KSampler")
    assert sampler["inputs"]["seed"] == 777

    # El text encoder positivo (lyrics_strength > 0) recibió los nuevos tags.
    # El instrumental tiene lyrics_strength=0, por lo que aqui se comprueba el de cancion.
    positivos = [
        n for n in wf.values()
        if n["class_type"] == "TextEncodeAceStepAudio"
        and n["inputs"]["lyrics_strength"] > 0
    ]
    assert any(n["inputs"]["tags"] == "jazz, slow, sax" for n in positivos)


def test_override_lyrics_no_modifica_negative():
    """Verifica que el encoder negativo no se toca cuando se cambian las lyrics.

    El nodo negativo describe lo que el modelo debe evitar generar.
    Cambiar la letra no debe afectarle en absoluto.
    """
    wf = cargar_workflow(AQUI / "acestep_workflow.json")
    # Guarda el estado inicial de los encoders negativos (lyrics_strength == 0).
    negatives_antes = [
        dict(n["inputs"]) for n in wf.values()
        if n["class_type"] == "TextEncodeAceStepAudio"
        and n["inputs"]["lyrics_strength"] == 0
    ]
    aplicar_overrides(
        wf, tags=None, lyrics="nueva letra",
        seed=None, seconds=None, steps=None,
    )
    # Comprueba que los negativos no cambiaron nada.
    negatives_despues = [
        dict(n["inputs"]) for n in wf.values()
        if n["class_type"] == "TextEncodeAceStepAudio"
        and n["inputs"]["lyrics_strength"] == 0
    ]
    assert negatives_antes == negatives_despues


def test_override_seconds():
    """Verifica que la duracion se modifica correctamente en EmptyAceStepLatentAudio.

    'seconds' controla cuantos segundos de audio va a generar el modelo.
    """
    wf = cargar_workflow(AQUI / "acestep_workflow.json")
    aplicar_overrides(
        wf, tags=None, lyrics=None,
        seed=None, seconds=45, steps=None,
    )
    latente = next(n for n in wf.values()
                   if n["class_type"] == "EmptyAceStepLatentAudio")
    assert latente["inputs"]["seconds"] == 45


def test_workflow_es_json_valido():
    """Garantía mínima: el workflow modificado sigue siendo JSON serializable.

    Despues de aplicar todos los overrides, el diccionario debe poder
    convertirse a JSON sin errores para poder enviarse a la API de ComfyUI.
    """
    wf = cargar_workflow(AQUI / "acestep_workflow.json")
    aplicar_overrides(
        wf, tags="x", lyrics="y", seed=1, seconds=10, steps=10,
    )
    json.dumps(wf)  # no debe lanzar excepcion
