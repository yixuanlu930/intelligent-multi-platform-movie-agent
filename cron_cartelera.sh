#!/bin/bash
# cron_cartelera.sh
# =================
# Script para ejecutar el scraper de cartelera via cron.
#
# Configura en crontab con:
#   crontab -e
#   0 9 * * 1 /ruta/completa/cron_cartelera.sh
#
# Esto ejecuta el script todos los lunes a las 9:00.

# Calculamos la ruta absoluta del directorio donde esta este script,
# independientemente del CWD desde el que lo lance cron.
SCRIPT_DIR="$(cd "$(dirname "$0")" && pwd)"
cd "$SCRIPT_DIR"

# Activar entorno virtual si existe (necesario para que Python encuentre las dependencias)
if [ -f "venv/bin/activate" ]; then
    source venv/bin/activate
fi

# Ejecutar scraper con filtro de perfil y envio por Telegram.
# >> añade al log sin borrar entradas anteriores.
# 2>&1 redirige stderr al mismo fichero que stdout (captura errores tambien).
python3 cartelera_scraper.py --filtrar --telegram >> cartelera_cron.log 2>&1

# Timestamp al final del log para verificar que el cron se ejecuto correctamente
echo "[$(date)] Cartelera ejecutada" >> cartelera_cron.log
