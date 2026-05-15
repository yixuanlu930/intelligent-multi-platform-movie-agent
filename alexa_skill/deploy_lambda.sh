#!/bin/bash
# deploy_lambda.sh
# ================
# Script de despliegue: genera lambda_package.zip listo para subir a AWS Lambda.
#
# AWS Lambda requiere que todas las dependencias vayan DENTRO del ZIP,
# ya que el entorno de ejecución de Lambda no tiene librerías instaladas.
# Por eso instalamos todo en una carpeta local (lambda_build/) y la comprimimos.
#
# Uso:
#   cd alexa_skill_def
#   bash deploy_lambda.sh
#
# Tras ejecutarlo, sube lambda_package.zip a:
#   AWS Lambda → CineInteligente → Code → Upload from → .zip file
#
# Autores: Grupo XX - Práctica IA Agéntica

set -e  # Detener el script si cualquier comando falla

# --- Paso 1: Limpiar builds anteriores ---
# Eliminamos la carpeta de build y el ZIP previo para evitar archivos obsoletos
rm -rf lambda_build lambda_package.zip
mkdir -p lambda_build

# --- Paso 2: Instalar dependencias en la carpeta de build ---
# El flag -t (target) instala las librerías directamente en lambda_build/
# en lugar de en el entorno global de Python
python3 -m pip install --upgrade pip
python3 -m pip install -r requirements.txt -t lambda_build

# --- Paso 3: Copiar el código fuente del proyecto ---
# Los tres archivos .py del skill van también dentro del ZIP
cp lambda_function.py imdb_scraper.py cache.py lambda_build/

# --- Paso 4: Generar el ZIP ---
# Lambda espera un ZIP con todo en el directorio raíz (sin subcarpetas de proyecto)
cd lambda_build
zip -r ../lambda_package.zip . >/dev/null
cd ..

# --- Resumen de pasos siguientes ---
echo "OK: creado lambda_package.zip"
echo "Sube este ZIP a AWS Lambda → CineInteligente → Code → Upload from → .zip file"
echo "Handler: lambda_function.handler"
echo "Memoria recomendada: 512 MB"
echo "Timeout recomendado: 20 segundos"
echo "Variables de entorno necesarias en AWS Lambda:"
echo "  OMDB_API_KEY=tu_api_key_de_omdb"
echo "  USE_DYNAMO=false"
echo "  CACHE_TTL_DAYS=7"
