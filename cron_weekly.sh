#!/bin/bash
# Automatización semanal: cartelera + conciertos → Telegram
# Configurar con `crontab -e`:
#   0 9 * * 1 /ruta/completa/al/proyecto/cron_weekly.sh

set -e
cd "$(dirname "$0")"

echo "[$(date)] Iniciando cron semanal..."

# 1. Cartelera de Madrid filtrada por perfil → Telegram
python3 cartelera_scraper.py --filtrar --telegram
echo "[$(date)] Cartelera enviada"

# 2. Conciertos de la semana filtrados por artistas favoritos → Telegram
python3 concerts_cron.py
echo "[$(date)] Conciertos enviados"
