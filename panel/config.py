"""Configuración del panel.

Todo lo que cambia entre servidores o se calibra después vive aquí, no en las vistas.
"""
import os
from pathlib import Path

# Carpeta donde el pipeline escribe eventos.jsonl y crops/.
# En la VM es ~/shared/eventos/; dentro del contenedor de Jupyter,
# /home/ibm-user/shared/eventos/. Cambiar de servidor = cambiar esta variable.
EVENTOS_DIR = Path(os.environ.get("EVENTOS_DIR", "/home/ibm-user/shared/eventos"))

# Carpeta separada para los eventos falsos, para que nunca se mezclen con los reales.
EVENTOS_FALSOS_DIR = Path(os.environ.get("EVENTOS_FALSOS_DIR", "/home/ibm-user/shared/eventos_falsos"))

EVENTOS_ARCHIVO = "eventos.jsonl"
BITACORA_ARCHIVO = "bitacora.jsonl"  # vive junto a los eventos, fuera del repo

# Umbrales de color por carácter. PROVISIONALES: los reemplaza la calibración
# de Marlene (13:00-16:30). No presentarlos como resultado en el video.
CONF_ALTA = 0.80
CONF_MEDIA = 0.50

# Motivo con el que el pipeline marca una placa demasiado pequeña para leer.
MOTIVO_PLACA_PEQUENA = "placa_pequena"
