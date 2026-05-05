#!/bin/bash
# Lunes 9:00: enviar cartelera filtrada + conciertos favoritos por Telegram.
# Configurar con `crontab -e`:
#   0 9 * * 1 /home/anaya/Desktop-Ub/SSII/cron_weekly.sh
set -e
cd "$(dirname "$0")"

# Cartelera de Madrid filtrada por perfil -> Telegram
python3 cartelera_scraper.py --telegram

# Conciertos de la semana filtrados por artistas favoritos -> Telegram
python3 concerts_cron.py
