# Alexa Skill: Cine Inteligente

Carpeta corregida para el skill de Alexa de la práctica de agentes.

Esta versión usa **OMDb API** para consultar datos de películas, en vez de scraping directo de IMDb. Es más estable para AWS Lambda.

## Archivos

```text
alexa_skill_def/
├── lambda_function.py       # Código principal de la Lambda de Alexa
├── imdb_scraper.py          # Consulta OMDb API y devuelve datos normalizados
├── cache.py                 # Caché en memoria + DynamoDB opcional
├── requirements.txt         # Dependencias fijadas
├── interactionModel.json    # Modelo de Alexa en español, sin dialog/prompts
├── deploy_lambda.sh         # Genera lambda_package.zip
└── README_ALEXA.md
```

## 1. Requisitos

Necesitas una API key de OMDb:

```text
https://www.omdbapi.com/apikey.aspx
```

No la subas a GitHub ni la pegues en el código. Debe ir en AWS Lambda como variable de entorno.

## 2. Crear el ZIP de Lambda

Desde esta carpeta:

```bash
python3 -m venv venv
source venv/bin/activate
pip install -r requirements.txt

python -m py_compile lambda_function.py imdb_scraper.py cache.py
bash deploy_lambda.sh
```

Esto genera:

```text
lambda_package.zip
```

Ese es el archivo que se sube a AWS Lambda.

## 3. Configurar AWS Lambda

En AWS Lambda, función `CineInteligente`:

```text
Runtime: Python 3.11
Handler: lambda_function.handler
Memory: 512 MB
Timeout: 20 seconds
Trigger: Alexa / Kit de habilidades de Alexa
```

Sube `lambda_package.zip` en:

```text
Code → Upload from → .zip file
```

Configura variables de entorno:

```text
OMDB_API_KEY = tu_api_key_real
USE_DYNAMO = false
CACHE_TTL_DAYS = 7
```

## 4. Configurar Alexa Developer Console

En tu skill `Cine Inteligente`, locale **Spanish (ES)**:

1. `Build → Interaction Model → JSON Editor`
2. Borra el JSON actual.
3. Pega el contenido de `interactionModel.json`.
4. Pulsa `Save Model`.
5. Pulsa `Build skill`.

Luego en:

```text
Build → Endpoint
```

selecciona:

```text
AWS Lambda ARN
```

y pega el ARN de tu Lambda en:

```text
Default Region
Europe and India
```

Deja `North America` y `Far East` vacíos.

## 5. Probar

En `Test`, activa `Development` y prueba:

```text
abre cine inteligente
cuál es la nota de Inception
quién dirigió Inception
cuánto dura Inception
dime todo sobre Inception
cuál es la nota de Origen
cuál es la nota de El Padrino
```

## 6. Si falla

Revisa CloudWatch Logs en AWS Lambda:

```text
AWS Lambda → CineInteligente → Monitor → View CloudWatch logs
```

Errores típicos:

- `Falta OMDB_API_KEY`: no configuraste la variable de entorno.
- `Unable to import module`: handler mal puesto o ZIP mal empaquetado.
- `No module named ask_sdk_core`: subiste solo los `.py`, no el `lambda_package.zip` generado.
