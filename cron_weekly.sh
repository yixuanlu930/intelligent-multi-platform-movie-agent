#!/bin/bash
# cron_weekly.sh
# ==============
# Automatización semanal: cartelera + conciertos → Telegram.
#
# Configura con `crontab -e`:
#   0 9 * * 1 /ruta/completa/al/proyecto/cron_weekly.sh

# set -e detiene el script inmediatamente si cualquier comando devuelve error.
# Esto evita que un fallo en la cartelera enmascare un error posterior en conciertos.
set -e

# Cambiamos al directorio del script para que los imports de Python funcionen
# correctamente independientemente del CWD desde el que cron lance el script.
cd "$(dirname "$0")"

echo "[$(date)] Iniciando cron semanal..."

# Paso 1: Cartelera de Madrid filtrada por perfil → Telegram
python3 cartelera_scraper.py --filtrar --telegram
echo "[$(date)] Cartelera enviada"

# Paso 2: Conciertos de la semana filtrados por artistas favoritos → Telegram
python3 concerts_cron.py
echo "[$(date)] Conciertos enviados"
