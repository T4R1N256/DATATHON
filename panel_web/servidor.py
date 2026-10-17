"""Backend del panel del operador: la página, el CSS y tres rutas JSON.

Solo usa la biblioteca estándar de Python. Corre detrás de nginx, que pide el
login y pasa el usuario en el encabezado X-Remote-User. En Compose no publica
ningún puerto: solo nginx lo alcanza, por la red interna.

Uso:
    python -u panel_web/servidor.py

Variables de entorno:
    EVENTOS_DIR  carpeta con eventos.jsonl, crops/ y bitacora.jsonl
    PANEL_HOST   dirección donde escucha (por defecto 127.0.0.1; en Compose, 0.0.0.0)
    PANEL_PORT   puerto (por defecto 8080)
"""
import json
import os
import platform
import sys
from http import HTTPStatus
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from urllib.parse import parse_qs, urlparse

RAIZ = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(RAIZ))

from panel import bitacora, config, vistas  # noqa: E402
from panel import eventos as ev  # noqa: E402

PAGINA = Path(__file__).with_name("index.html")
CSS = RAIZ / "panel" / "estilos.css"
MAX_CUERPO = 4096
MAX_OMITIDOS = 500


def _directorio():
    return Path(config.EVENTOS_DIR)


def _ruta_bitacora():
    return _directorio() / config.BITACORA_ARCHIVO


def _pendientes(omitir=()):
    eventos = ev.cargar(_directorio())
    return ev.cola(eventos, bitacora.decididos(_ruta_bitacora()) | set(omitir))


def _acciones(estado):
    if estado in (ev.ALERTA, ev.REVISION):
        return ["confirmar", "descartar"]
    return ["siguiente"]


def siguiente(omitir, operador):
    """Primer evento pendiente, ya convertido en HTML por las mismas vistas del notebook."""
    cola = _pendientes(omitir)
    if not cola:
        return {"evento": None, "pendientes": 0, "operador": operador}
    evento = cola[0]
    est = ev.estado(evento)
    return {
        "evento": {
            "evento_id": evento.get("evento_id"),
            "estado": est,
            "acciones": _acciones(est),
            "etiqueta_confirmar": "Confirmar alerta" if est == ev.ALERTA else "Confirmar",
            "html": {
                "recortes": vistas.recortes(evento, _directorio()),
                "lectura": vistas.lectura(evento),
                "reporte": vistas.reporte(evento) if est != ev.NO_LEGIBLE else "",
            },
        },
        "pendientes": len(cola),
        "operador": operador,
    }


def decidir(evento_id, accion, operador):
    """Registra la decisión en la bitácora. Devuelve (estado HTTP, cuerpo)."""
    if not operador:
        return HTTPStatus.UNAUTHORIZED, {"error": "Falta el usuario del login: entra por nginx."}
    evento = next((e for e in _pendientes() if e.get("evento_id") == evento_id), None)
    if evento is None:
        return HTTPStatus.CONFLICT, {"error": "Ese evento ya no está pendiente."}
    if ev.estado(evento) not in (ev.ALERTA, ev.REVISION):
        return HTTPStatus.BAD_REQUEST, {"error": "Este evento no admite decisión."}
    try:
        bitacora.registrar(_ruta_bitacora(), evento, accion, operador)
    except ValueError as error:
        return HTTPStatus.BAD_REQUEST, {"error": str(error)}
    return HTTPStatus.OK, {"ok": True}


class Manejador(BaseHTTPRequestHandler):
    server_version = "PanelOperador"
    sys_version = ""

    def _operador(self):
        return (self.headers.get("X-Remote-User") or "").strip()

    def _enviar(self, estado, cuerpo, tipo="application/json; charset=utf-8"):
        datos = cuerpo if isinstance(cuerpo, bytes) else json.dumps(cuerpo, ensure_ascii=False).encode()
        self.send_response(estado)
        self.send_header("Content-Type", tipo)
        self.send_header("Content-Length", str(len(datos)))
        self.send_header("Cache-Control", "no-store")
        self.send_header("X-Content-Type-Options", "nosniff")
        self.end_headers()
        self.wfile.write(datos)

    def do_GET(self):
        url = urlparse(self.path)
        if url.path in ("/", "/index.html"):
            self._enviar(HTTPStatus.OK, PAGINA.read_bytes(), "text/html; charset=utf-8")
        elif url.path == "/estilos.css":
            self._enviar(HTTPStatus.OK, CSS.read_bytes(), "text/css; charset=utf-8")
        elif url.path == "/api/salud":
            self._enviar(HTTPStatus.OK, {"ok": True, "maquina": platform.machine()})
        elif url.path == "/api/siguiente":
            crudo = parse_qs(url.query).get("omitir", [""])[0]
            omitir = [i for i in crudo.split(",") if i][:MAX_OMITIDOS]
            self._enviar(HTTPStatus.OK, siguiente(omitir, self._operador()))
        else:
            self._enviar(HTTPStatus.NOT_FOUND, {"error": "No existe."})

    def do_POST(self):
        if urlparse(self.path).path != "/api/decision":
            self._enviar(HTTPStatus.NOT_FOUND, {"error": "No existe."})
            return
        try:
            largo = int(self.headers.get("Content-Length") or 0)
        except ValueError:
            largo = 0
        if largo <= 0 or largo > MAX_CUERPO:
            self._enviar(HTTPStatus.BAD_REQUEST, {"error": "Cuerpo vacío o demasiado grande."})
            return
        try:
            datos = json.loads(self.rfile.read(largo))
        except (json.JSONDecodeError, UnicodeDecodeError):
            datos = None
        if not isinstance(datos, dict):
            self._enviar(HTTPStatus.BAD_REQUEST, {"error": "Se esperaba un objeto JSON."})
            return
        estado, cuerpo = decidir(str(datos.get("evento_id", "")), str(datos.get("accion", "")), self._operador())
        self._enviar(estado, cuerpo)

    def log_message(self, formato, *args):
        # Una línea por petición en la consola del contenedor; nunca cuerpos ni placas.
        sys.stderr.write("%s %s\n" % (self.log_date_time_string(), formato % args))


def main():
    host = os.environ.get("PANEL_HOST", "127.0.0.1")
    puerto = int(os.environ.get("PANEL_PORT", "8080"))
    servidor = ThreadingHTTPServer((host, puerto), Manejador)
    print(f"Panel en http://{host}:{puerto} · eventos en {config.EVENTOS_DIR}", flush=True)
    servidor.serve_forever()


if __name__ == "__main__":
    main()
