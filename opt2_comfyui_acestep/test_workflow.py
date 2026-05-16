"""
Tests del workflow Ace Step y del cliente Python.

No requieren tener ComfyUI corriendo. Validan:
  - que los JSON tienen TODOS los nodos críticos del workflow oficial
    (faltar cualquiera de ellos provoca que el modelo NO genere voces)
  - que `aplicar_overrides` modifica los nodos correctos

    python -m pytest test_workflow.py -v
"""

import json
from pathlib import Path

import pytest

from generar_cancion import cargar_workflow, aplicar_overrides

AQUI = Path(__file__).parent


# ---------------------------------------------------------------------------
# Validación estructural del workflow
# ---------------------------------------------------------------------------

@pytest.mark.parametrize("nombre", [
    "acestep_workflow.json",
    "acestep_workflow_instrumental.json",
])
def test_workflow_tiene_nodos_minimos(nombre):
    """Comprueba que están todos los nodos del workflow oficial."""
    wf = cargar_workflow(AQUI / nombre)
    tipos = {node["class_type"] for node in wf.values()}
    obligatorios = {
        "CheckpointLoaderSimple",
        "ModelSamplingSD3",                # crítico para Ace Step
        "LatentOperationTonemapReinhard",  # control de voces
        "LatentApplyOperationCFG",         # aplica el tonemap
        "EmptyAceStepLatentAudio",
        "TextEncodeAceStepAudio",
        "ConditioningZeroOut",             # genera el negativo
        "KSampler",
        "VAEDecodeAudio",
        "SaveAudio",
    }
    faltan = obligatorios - tipos
    assert not faltan, f"Faltan nodos en {nombre}: {faltan}"


def test_workflow_cancion_tiene_lyrics_y_voces():
    """El workflow de canción debe pedir voces y tener letra."""
    wf = cargar_workflow(AQUI / "acestep_workflow.json")
    encoder = next(n for n in wf.values() if n["class_type"] == "TextEncodeAceStepAudio")
    assert encoder["inputs"]["lyrics"].strip(), "Hay que pasar una letra"
    assert encoder["inputs"]["lyrics_strength"] > 0.5, (
        "lyrics_strength debe ser alto para que el modelo cante la letra"
    )
    tags = encoder["inputs"]["tags"].lower()
    assert "vocal" in tags or "voice" in tags, (
        "Los tags deben pedir explícitamente vocal/voice"
    )


def test_workflow_instrumental_sin_letra():
    wf = cargar_workflow(AQUI / "acestep_workflow_instrumental.json")
    encoder = next(n for n in wf.values() if n["class_type"] == "TextEncodeAceStepAudio")
    assert encoder["inputs"]["lyrics"] == "", "Instrumental: sin letra"
    assert encoder["inputs"]["lyrics_strength"] == 0.0
    tags = encoder["inputs"]["tags"].lower()
    assert "no vocal" in tags or "instrumental" in tags


def test_model_sampling_sd3_shift_correcto():
    """Ace Step necesita shift=5 en ModelSamplingSD3 (valor del workflow oficial)."""
    for nombre in ["acestep_workflow.json", "acestep_workflow_instrumental.json"]:
        wf = cargar_workflow(AQUI / nombre)
        ms = next(n for n in wf.values() if n["class_type"] == "ModelSamplingSD3")
        assert ms["inputs"]["shift"] == 5.0, f"{nombre}: shift debe ser 5.0"


# ---------------------------------------------------------------------------
# Tests de aplicar_overrides
# ---------------------------------------------------------------------------

def test_override_tags_y_seed():
    wf = cargar_workflow(AQUI / "acestep_workflow.json")
    aplicar_overrides(
        wf, tags="jazz, slow, sax, male vocal", lyrics=None,
        seed=777, seconds=None, steps=None,
    )

    sampler = next(n for n in wf.values() if n["class_type"] == "KSampler")
    assert sampler["inputs"]["seed"] == 777

    encoder = next(n for n in wf.values() if n["class_type"] == "TextEncodeAceStepAudio")
    assert encoder["inputs"]["tags"] == "jazz, slow, sax, male vocal"


def test_override_lyrics():
    wf = cargar_workflow(AQUI / "acestep_workflow.json")
    aplicar_overrides(
        wf, tags=None, lyrics="[verse]\nNueva letra que canta el modelo\n",
        seed=None, seconds=None, steps=None,
    )
    encoder = next(n for n in wf.values() if n["class_type"] == "TextEncodeAceStepAudio")
    assert "Nueva letra" in encoder["inputs"]["lyrics"]


def test_override_seconds():
    wf = cargar_workflow(AQUI / "acestep_workflow.json")
    aplicar_overrides(
        wf, tags=None, lyrics=None,
        seed=None, seconds=45, steps=None,
    )
    latente = next(n for n in wf.values()
                   if n["class_type"] == "EmptyAceStepLatentAudio")
    assert latente["inputs"]["seconds"] == 45


def test_override_steps():
    wf = cargar_workflow(AQUI / "acestep_workflow.json")
    aplicar_overrides(
        wf, tags=None, lyrics=None,
        seed=None, seconds=None, steps=80,
    )
    sampler = next(n for n in wf.values() if n["class_type"] == "KSampler")
    assert sampler["inputs"]["steps"] == 80


def test_workflow_es_json_valido_tras_overrides():
    wf = cargar_workflow(AQUI / "acestep_workflow.json")
    aplicar_overrides(
        wf, tags="x", lyrics="y", seed=1, seconds=10, steps=10,
    )
    json.dumps(wf)  # no debe lanzar
