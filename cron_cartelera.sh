#!/bin/bash
# Script para ejecutar el scraper de cartelera via cron.
# Configurar en crontab con:
#   crontab -e
#   0 9 * * 1 /ruta/completa/cron_cartelera.sh
#
# Esto ejecuta el script todos los lunes a las 9:00.

SCRIPT_DIR="$(cd "$(dirname "$0")" && pwd)"
cd "$SCRIPT_DIR"

# Activar entorno virtual si existe
if [ -f "venv/bin/activate" ]; then
    source venv/bin/activate
fi

# Ejecutar scraper con filtro y envio por Telegram
python3 cartelera_scraper.py --filtrar --telegram >> cartelera_cron.log 2>&1

echo "[$(date)] Cartelera ejecutada" >> cartelera_cron.log
