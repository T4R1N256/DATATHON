"""Lectura y clasificación de eventos del contrato JSON.

El panel nunca modifica eventos: solo los lee. Son funciones puras, sin widgets,
para poder probarlas sin abrir Jupyter.
"""
import json
from pathlib import Path

from . import config

ALERTA = "alerta"
REVISION = "revision"
NO_LEGIBLE = "no_legible"
SIN_COINCIDENCIA = "sin_coincidencia"

_PRIORIDAD = {ALERTA: 0, REVISION: 1, NO_LEGIBLE: 2}


def cargar(directorio=None):
    """Lee eventos.jsonl y devuelve una lista de dicts.

    Ignora líneas vacías o rotas: el pipeline puede estar escribiendo la última
    mientras el panel lee.
    """
    ruta = Path(directorio or config.EVENTOS_DIR) / config.EVENTOS_ARCHIVO
    if not ruta.exists():
        return []
    eventos = []
    with ruta.open(encoding="utf-8") as f:
        for linea in f:
            linea = linea.strip()
            if not linea:
                continue
            try:
                eventos.append(json.loads(linea))
            except json.JSONDecodeError:
                continue
    return eventos


def estado(evento):
    """Uno de los cuatro estados del plan, a partir de decision, en_lista y motivo."""
    decision = evento.get("decision")
    if decision == "alerta":
        return ALERTA
    if decision == "revision":
        return REVISION
    if evento.get("motivo") == config.MOTIVO_PLACA_PEQUENA:
        return NO_LEGIBLE
    return SIN_COINCIDENCIA


def cola(eventos, decididos=()):
    """Eventos que el operador debe ver, uno a la vez.

    Orden: alertas, luego revisión, luego no legibles; dentro de cada grupo, por hora.
    Excluye los sin coincidencia (no se muestran) y los que ya están en la bitácora.
    """
    pendientes = [
        e for e in eventos
        if estado(e) != SIN_COINCIDENCIA and e.get("evento_id") not in decididos
    ]
    return sorted(pendientes, key=lambda e: (_PRIORIDAD[estado(e)], e.get("ts", "")))


def ruta_recorte(evento, cual, directorio=None):
    """Ruta del recorte 'original' o 'sr', o None si el evento no lo trae o no existe."""
    relativa = (evento.get("recortes") or {}).get(cual)
    if not relativa:
        return None
    ruta = Path(directorio or config.EVENTOS_DIR) / relativa
    return ruta if ruta.exists() else None


def lectura(evento):
    """Texto votado y confianza por carácter, como (texto, [conf, ...]).

    Acepta votacion.conf como lista (una por carácter, lo ideal) o como un solo
    número, que se repite para todos. Si no cuadra con el texto, devuelve None
    por carácter y la vista los pinta en gris.
    """
    votacion = evento.get("votacion") or {}
    texto = votacion.get("texto") or ""
    conf = votacion.get("conf")
    if isinstance(conf, (int, float)):
        conf = [float(conf)] * len(texto)
    if not isinstance(conf, list) or len(conf) != len(texto):
        conf = [None] * len(texto)
    return texto, conf
