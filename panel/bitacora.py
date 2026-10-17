"""Bitácora de decisiones del operador.

Una línea JSON por decisión. Nunca guarda el texto de la placa: solo el HMAC
que ya trae el evento.
"""
import json
from datetime import datetime, timezone
from pathlib import Path

ACCIONES = ("confirmar", "descartar")


def registrar(ruta, evento, accion, operador):
    """Agrega una decisión a la bitácora y devuelve la línea escrita.

    Lanza ValueError si la acción no existe o falta el operador, para que el
    panel lo avise en vez de registrar una decisión sin dueño.
    """
    if accion not in ACCIONES:
        raise ValueError(f"Acción desconocida: {accion}")
    operador = (operador or "").strip()
    if not operador:
        raise ValueError("Escribe tu nombre de operador antes de decidir.")
    linea = {
        "ts": datetime.now(timezone.utc).isoformat(timespec="seconds"),
        "operador": operador,
        "evento_id": evento.get("evento_id"),
        "placa_hmac": evento.get("placa_hmac"),
        "accion": accion,
    }
    ruta = Path(ruta)
    ruta.parent.mkdir(parents=True, exist_ok=True)
    with ruta.open("a", encoding="utf-8") as f:
        f.write(json.dumps(linea, ensure_ascii=False) + "\n")
    return linea


def decididos(ruta):
    """Ids de los eventos que ya tienen una decisión, para no volver a mostrarlos."""
    ruta = Path(ruta)
    if not ruta.exists():
        return set()
    ids = set()
    with ruta.open(encoding="utf-8") as f:
        for linea in f:
            try:
                ids.add(json.loads(linea)["evento_id"])
            except (json.JSONDecodeError, KeyError):
                continue
    return ids
