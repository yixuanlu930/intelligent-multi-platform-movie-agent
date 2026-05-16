# Workflow ComfyUI — Ace Step (generación de canciones con voces)

Dos workflows en formato API para [ComfyUI](https://github.com/comfyanonymous/ComfyUI)
que usan **Ace Step** (modelo de difusión para audio musical) para generar:

1. **Canción cantada** con letra y voz (`acestep_workflow.json`).
2. **Instrumental** sin voces (`acestep_workflow_instrumental.json`).

Más un **cliente Python** que envía los workflows a la API de ComfyUI,
permite sobrescribir tags/letra/semilla por línea de comandos, espera a
que termine la generación y descarga el `.flac` resultante.

Cumple la opcional del **Bloque II**:
> ✓ Workflow con Ace Step para generación de canciones

> Construido a partir del **workflow oficial de Comfy-Org**
> ([ace_step_1_t2m.json](https://github.com/Comfy-Org/example_workflows/blob/main/audio/ace-step/ace_step_1_t2m.json)),
> convertido a formato API y adaptado para parametrización desde Python.

## Estructura del workflow (importante para que las voces salgan)

El workflow oficial tiene **10 tipos de nodo**. Los 4 críticos para que Ace Step
genere voces correctamente:

| Nodo | Para qué |
|---|---|
| `ModelSamplingSD3` (shift=5) | Configura el flow del sampler para Ace Step. Sin él, el modelo se desorienta. |
| `LatentOperationTonemapReinhard` (multiplier=1.0) | Controla el volumen/prominencia de las voces. |
| `LatentApplyOperationCFG` | Aplica el tonemap durante el sampling. |
| `ConditioningZeroOut` | El "negativo" no es un prompt aparte: es el positivo zeroreado. |

Faltar cualquiera de estos provoca síntomas tipo "solo sale instrumental" o
"sale ruido / voces ininteligibles". Los tests (`test_workflow.py`) comprueban
que estén todos.

## Contenido del ZIP

```
opt2_comfyui_acestep/
├── acestep_workflow.json                 # Canción cantada (120s)
├── acestep_workflow_instrumental.json    # Instrumental rock (60s)
├── generar_cancion.py                    # Cliente Python (API de ComfyUI)
├── letra_ejemplo.txt                     # Letra en español de ejemplo
├── test_workflow.py                      # 10 tests (no necesitan ComfyUI)
├── requirements.txt
└── README.md
```

## Prerrequisitos

> **Importante**: Ace Step está integrado **nativamente** en ComfyUI desde mayo de 2025.
> **No** hace falta instalar ningún custom node. Solo asegúrate de tener ComfyUI
> actualizado (versión >= 0.3.34).

1. **ComfyUI actualizado** y corriendo:
   ```bash
   cd ComfyUI
   git pull
   pip install -r requirements.txt --upgrade
   python main.py
   ```

2. **Modelo Ace Step 3.5B** descargado en `ComfyUI/models/checkpoints/`:
   ```bash
   cd ComfyUI/models/checkpoints
   curl -L -o ace_step_v1_3.5b.safetensors \
     https://huggingface.co/Comfy-Org/ACE-Step_ComfyUI_repackaged/resolve/main/all_in_one/ace_step_v1_3.5b.safetensors
   ```
   (~3.5 GB). Página HuggingFace: https://huggingface.co/Comfy-Org/ACE-Step_ComfyUI_repackaged/tree/main/all_in_one

## Uso

### Método A — desde la UI de ComfyUI (lo más visual)

1. Abre la UI (`http://localhost:8188`).
2. Botón **Load** → seleccionas `acestep_workflow.json`.
3. Verás el grafo con 10 nodos conectados.
4. Botón **Queue Prompt** → espera 1–3 minutos.
5. Reproductor con el `.flac` generado al final del grafo (nodo *Save Audio*).

### Método B — desde Python (reproducible)

```bash
pip install -r requirements.txt

# Encolar el workflow tal cual y salir:
python generar_cancion.py

# Encolar y esperar a que termine, descargando el audio:
python generar_cancion.py --wait

# Generar con tu propia letra:
python generar_cancion.py --wait \
    --tags "synthwave, retro, 120 bpm, neon, dreamy, female vocal" \
    --lyrics-file letra_ejemplo.txt

# Instrumental:
python generar_cancion.py --wait \
    --workflow acestep_workflow_instrumental.json \
    --output mi_instrumental.flac
```

## Tests

```bash
python -m pytest test_workflow.py -v
```

10 tests que verifican estructura del workflow, presencia de los nodos
críticos para voces, valores correctos (`shift=5`, `lyrics_strength > 0.5`)
y comportamiento de los overrides del cliente. No requieren ComfyUI corriendo.

## Cómo conseguir que cante la letra que tú quieres

Este es el punto donde fallan la mayoría de intentos. La regla de oro:

> **El modelo necesita tres cosas: tags pidiendo voces, letra estructurada y `lyrics_strength` alto.**

### 1. En los tags incluye "vocal" / "voice"
| Bien | Mal |
|---|---|
| `"indie pop, female vocal, clear vocals, ..."` | `"indie pop, dreamy, lo-fi, ..."` (no menciona voces) |
| `"rock, male vocalist, powerful voice, ..."` | `"rock, energetic, 130 bpm"` |
| `"latin pop, female singer, spanish vocals, ..."` | `"latin pop, reggaeton, tropical"` |

### 2. Estructura la letra con marcadores
Ace Step entiende `[verse]`, `[chorus]`, `[bridge]`, `[outro]`, `[inst]`.
Estructurar la letra mejora muchísimo el resultado.

```
[verse]
Primera línea de la estrofa
Segunda línea de la estrofa
...

[chorus]
Letra del estribillo
...

[bridge]
Letra del puente
```

### 3. `lyrics_strength` entre 0.8 y 1.0
- `1.0` (workflow oficial: `0.99`): el modelo intenta cantar la letra exacta.
- `0.5`: el modelo se inspira en la letra pero canta libremente.
- `0.0`: ignora la letra (úsalo solo para instrumental).

### 4. Para canciones en **español**
El soporte multi-idioma de Ace Step pasa por transcribir cualquier idioma
a caracteres latinos y prefijarlo con el código de idioma. Para español:

```
[verse]
[es]bajo la luz de la luna camino sin pensar
[es]cada calle me regala una historia que contar
```

En la práctica, **el español puro (sin prefijo `[es]`) suele funcionar bien
también** porque ya está en caracteres latinos. La letra de
`letra_ejemplo.txt` está en español sin prefijos y se canta correctamente.

### 5. Si las voces salen muy bajas
Edita en el workflow el nodo **LatentOperationTonemapReinhard** y sube el
`multiplier` de 1.0 a 1.5 o 2.0. Cuanto más alto, más prominentes son las voces.

### 6. Si quieres voz masculina o femenina concreta
En los tags: `"male vocal"`, `"male vocalist"`, `"male singer"` /
`"female vocal"`, `"female vocalist"`, `"clear female voice"`.

### 7. Genera varias y quédate con la mejor
El consejo más importante de la comunidad: **no esperes acertar a la primera**.
La misma combinación de tags+letra con semillas distintas da resultados
muy diferentes. Para producción:
- En la UI: pon `batch_size` a 4 u 8 en `EmptyAceStepLatentAudio`.
- En Python: lanza varias veces variando `--seed`.

## Anatomía del workflow (canción)

```
CheckpointLoaderSimple ──┬──► CLIP ──► TextEncodeAceStepAudio ──┬──► (positivo)
   (modelo + CLIP + VAE) │                  (tags + letra)      │
                         │                                      ▼
                         │                              ConditioningZeroOut
                         │                                      │
                         │                                      ▼
                         │                                  (negativo)
                         │                                      │
                         ▼                                      │
                  ModelSamplingSD3 (shift=5)                    │
                         │                                      │
                         ▼                                      │
                  LatentApplyOperationCFG ◄──── LatentOperationTonemapReinhard
                         │                              (multiplier=1.0)
                         ▼                                      │
                     KSampler ◄──────────────────────────────────┘
            (50 steps, CFG 5, euler/simple)
                         │
                         │  EmptyAceStepLatentAudio (seconds=120) ──► latent_image
                         │
                         ▼
                  VAEDecodeAudio
                         │
                         ▼
                    SaveAudio  →  output/audio/ace_step_song.flac
```

## Problemas habituales

| Síntoma | Causa | Solución |
|---|---|---|
| Solo sale instrumental | Faltaba `LatentOperationTonemapReinhard` o `ModelSamplingSD3` | Usar este workflow (ya están) |
| Voces apagadas | `multiplier` del Tonemap bajo | Subir de 1.0 a 1.5–2.0 |
| Letra ininteligible | `lyrics_strength` bajo o tags sin "vocal" | Subir a 0.99, añadir "clear vocals" a tags |
| `Connection refused` | ComfyUI no corre o no está en 127.0.0.1:8188 | Usa `--server tu_host:puerto` |
| `Checkpoint not found` | Modelo mal puesto | `ace_step_v1_3.5b.safetensors` debe estar en `ComfyUI/models/checkpoints/` |
| Nodos en rojo | ComfyUI desactualizado | `git pull` en ComfyUI |

## Créditos

- Modelo: [ACE-Step v1 3.5B](https://huggingface.co/Comfy-Org/ACE-Step_ComfyUI_repackaged) (ACE Studio + StepFun, licencia Apache-2.0).
- Workflow oficial de referencia: [Comfy-Org/example_workflows/audio/ace-step/ace_step_1_t2m.json](https://github.com/Comfy-Org/example_workflows/blob/main/audio/ace-step/ace_step_1_t2m.json).
- Documentación: https://docs.comfy.org/tutorials/audio/ace-step/ace-step-v1
