"""Pruebas del backend web, sin nginx: levanta el servidor en un puerto libre.

Uso, desde la raíz del proyecto:
    python tests/test_servidor.py
"""
import json
import os
import sys
import tempfile
import threading
import urllib.error
import urllib.request
from pathlib import Path

RAIZ = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(RAIZ))

_tmp = tempfile.TemporaryDirectory()
os.environ["EVENTOS_DIR"] = _tmp.name  # antes de importar panel.config

from http.server import ThreadingHTTPServer  # noqa: E402

from herramientas.generar_eventos_falsos import generar  # noqa: E402
from panel_web.servidor import Manejador  # noqa: E402


def pedir(base, ruta, cuerpo=None, usuario="op1"):
    datos = json.dumps(cuerpo).encode() if cuerpo is not None else None
    req = urllib.request.Request(base + ruta, data=datos, method="POST" if datos else "GET")
    req.add_header("Content-Type", "application/json")
    if usuario:
        req.add_header("X-Remote-User", usuario)
    try:
        with urllib.request.urlopen(req) as r:
            return r.status, json.loads(r.read())
    except urllib.error.HTTPError as e:
        return e.code, json.loads(e.read())


if __name__ == "__main__":
    # El generador se niega a escribir en EVENTOS_DIR; para la prueba se aparta un momento.
    from panel import config
    real = config.EVENTOS_DIR
    config.EVENTOS_DIR = Path(_tmp.name) / "no-es-esta"
    generar(_tmp.name)
    config.EVENTOS_DIR = real
    servidor = ThreadingHTTPServer(("127.0.0.1", 0), Manejador)
    threading.Thread(target=servidor.serve_forever, daemon=True).start()
    base = f"http://127.0.0.1:{servidor.server_address[1]}"

    estado, d = pedir(base, "/api/siguiente")
    assert estado == 200 and d["evento"]["estado"] == "alerta" and d["pendientes"] == 9
    eid = d["evento"]["evento_id"]

    assert pedir(base, "/api/decision", {"evento_id": eid, "accion": "confirmar"}, usuario="")[0] == 401
    assert pedir(base, "/api/decision", {"evento_id": eid, "accion": "borrar"})[0] == 400
    assert pedir(base, "/api/decision", {"evento_id": eid, "accion": "confirmar"})[0] == 200
    assert pedir(base, "/api/decision", {"evento_id": eid, "accion": "confirmar"})[0] == 409

    linea = json.loads((Path(_tmp.name) / "bitacora.jsonl").read_text(encoding="utf-8"))
    assert linea["operador"] == "op1" and "texto" not in linea

    _, d = pedir(base, "/api/siguiente")
    assert d["pendientes"] == 8 and d["evento"]["evento_id"] != eid
    print("ok  backend: rutas, login, decisiones y bitácora")
    servidor.shutdown()
