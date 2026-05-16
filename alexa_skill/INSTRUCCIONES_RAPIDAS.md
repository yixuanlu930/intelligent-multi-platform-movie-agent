# Instrucciones rápidas

## En terminal

```bash
cd alexa_skill
python3 -m venv venv
source venv/bin/activate
pip install -r requirements.txt
python -m py_compile lambda_function.py imdb_scraper.py cache.py
bash deploy_lambda.sh
```

Sube `lambda_package.zip` a AWS Lambda.

## En AWS Lambda

- Runtime: Python 3.11
- Handler: `lambda_function.handler`
- Memory: 512 MB
- Timeout: 20 s
- Environment variables:
  - `OMDB_API_KEY=tu_api_key_real`
  - `USE_DYNAMO=false`
  - `CACHE_TTL_DAYS=7`

## En Alexa Developer Console

- Locale: Spanish (ES)
- JSON Editor: pega `interactionModel.json`
- Save Model
- Build skill
- Endpoint: AWS Lambda ARN

## Prueba

```text
abre cine inteligente
cuál es la nota de Inception
quién dirigió Inception
cuánto dura Inception
```
