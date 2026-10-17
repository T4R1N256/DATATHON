"""Pruebas rápidas del panel, sin abrir Jupyter.

Uso, desde la raíz del repo (dentro del contenedor):
    python tests/test_panel.py
"""
import json
import sys
import tempfile
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from herramientas.generar_eventos_falsos import generar  # noqa: E402
from panel import bitacora, config, vistas  # noqa: E402
from panel import eventos as ev  # noqa: E402


def probar_cola_y_estados(d):
    eventos = ev.cargar(d)
    assert len(eventos) == 12
    cola = ev.cola(eventos)
    estados = [ev.estado(e) for e in cola]
    assert ev.SIN_COINCIDENCIA not in estados, "los sin coincidencia no se muestran"
    assert estados == sorted(estados, key=[ev.ALERTA, ev.REVISION, ev.NO_LEGIBLE].index), "alertas primero"
    assert len(cola) == 9


def probar_privacidad(d):
    for e in ev.cargar(d):
        if ev.estado(e) == ev.SIN_COINCIDENCIA:
            assert e.get("recortes") is None, "sin recortes fuera de la lista"
            assert "texto" not in (e.get("votacion") or {}), "sin texto fuera de la lista"


def probar_bitacora(d):
    ruta = Path(d) / config.BITACORA_ARCHIVO
    evento = ev.cola(ev.cargar(d))[0]
    texto, _ = ev.lectura(evento)
    try:
        bitacora.registrar(ruta, evento, "confirmar", "  ")
        raise AssertionError("debió exigir operador")
    except ValueError:
        pass
    bitacora.registrar(ruta, evento, "confirmar", "op1")
    contenido = ruta.read_text(encoding="utf-8")
    assert texto not in contenido, "la bitácora nunca guarda el texto de la placa"
    assert json.loads(contenido)["evento_id"] == evento["evento_id"]
    assert evento["evento_id"] not in {e["evento_id"] for e in ev.cola(ev.cargar(d), bitacora.decididos(ruta))}


def probar_vistas(d):
    for e in ev.cola(ev.cargar(d)):
        html = vistas.recortes(e, d) + vistas.lectura(e) + vistas.reporte(e)
        assert "Dato de prueba" in html, "los eventos falsos siempre llevan la etiqueta"
        if ev.estado(e) == ev.NO_LEGIBLE:
            assert "Recorte con SR" not in html


def probar_app(d):
    try:
        from panel.app import Panel
    except ImportError:
        print("  (sin ipywidgets: se omite la prueba de la app)")
        return
    p = Panel(d)
    vistos = 0
    while p.actual() is not None:
        est = ev.estado(p.actual())
        if est == ev.NO_LEGIBLE:
            assert p.b_siguiente.layout.display is None and p.b_confirmar.layout.display == "none"
            p.b_siguiente.click()
        else:
            if not p.operador.value:
                actual = p.actual()
                p.decidir("confirmar")  # sin operador: avisa y no avanza
                assert "operador" in p.zona_aviso.value and p.actual() is actual
                p.operador.value = "op1"
            p.b_descartar.click()
        vistos += 1
    assert vistos == 9 and "Sin eventos pendientes" in p.zona_recortes.value


if __name__ == "__main__":
    with tempfile.TemporaryDirectory() as tmp:
        generar(tmp)
        for prueba in (probar_cola_y_estados, probar_privacidad, probar_vistas, probar_bitacora):
            prueba(tmp)
            print(f"ok  {prueba.__name__}")
    with tempfile.TemporaryDirectory() as tmp:
        generar(tmp)
        probar_app(tmp)
        print("ok  probar_app")
