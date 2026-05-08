#!/bin/bash
set -e

# Crea lambda_package.zip para subirlo a AWS Lambda.
# Uso:
#   cd alexa_skill_def
#   bash deploy_lambda.sh

rm -rf lambda_build lambda_package.zip
mkdir -p lambda_build

python3 -m pip install --upgrade pip
python3 -m pip install -r requirements.txt -t lambda_build

cp lambda_function.py imdb_scraper.py cache.py lambda_build/

cd lambda_build
zip -r ../lambda_package.zip . >/dev/null
cd ..

echo "OK: creado lambda_package.zip"
echo "Sube este ZIP a AWS Lambda → CineInteligente → Code → Upload from → .zip file"
echo "Handler: lambda_function.handler"
echo "Memoria recomendada: 512 MB"
echo "Timeout recomendado: 20 segundos"
echo "Variables de entorno necesarias en AWS Lambda:"
echo "  OMDB_API_KEY=tu_api_key_de_omdb"
echo "  USE_DYNAMO=false"
echo "  CACHE_TTL_DAYS=7"
