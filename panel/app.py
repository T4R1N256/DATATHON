"""Panel del operador: arma los widgets y conecta los botones.

Uso en un notebook:
    from panel.app import mostrar
    panel = mostrar()                      # eventos reales (config.EVENTOS_DIR)
    panel = mostrar(config.EVENTOS_FALSOS_DIR)   # eventos falsos, solo desarrollo
"""
from pathlib import Path

import ipywidgets as widgets
from IPython.display import display

from . import bitacora, config, vistas
from . import eventos as ev

_CSS = Path(__file__).with_name("estilos.css")


def _boton(texto, clase):
    b = widgets.Button(description=texto, layout=widgets.Layout(width="auto"))
    b.add_class("pv-btn")
    b.add_class(clase)
    return b


def _mostrar_si(widget, visible):
    widget.layout.display = None if visible else "none"


class Panel:
    """Un evento a la vez: recortes, lectura, reporte y botones."""

    def __init__(self, directorio=None):
        self.directorio = Path(directorio or config.EVENTOS_DIR)
        self.ruta_bitacora = self.directorio / config.BITACORA_ARCHIVO
        self.cola = []
        self.i = 0

        self.estilo = widgets.HTML(f"<style>{_CSS.read_text(encoding='utf-8')}</style>")
        self.zona_recortes = widgets.HTML()
        self.zona_lectura = widgets.HTML()
        self.zona_reporte = widgets.HTML()
        self.zona_aviso = widgets.HTML()

        self.operador = widgets.Text(placeholder="Operador", layout=widgets.Layout(width="220px"))
        self.operador.add_class("pv-operador")
        self.b_confirmar = _boton("Confirmar alerta", "pv-btn-primario")
        self.b_descartar = _boton("Descartar", "pv-btn-secundario")
        self.b_siguiente = _boton("Siguiente", "pv-btn-secundario")
        self.b_buscar = _boton("Buscar eventos nuevos", "pv-btn-secundario")

        self.b_confirmar.on_click(lambda _: self.decidir("confirmar"))
        self.b_descartar.on_click(lambda _: self.decidir("descartar"))
        self.b_siguiente.on_click(lambda _: self.avanzar())
        self.b_buscar.on_click(lambda _: self.recargar())

        self.botones = widgets.HBox(
            [self.b_confirmar, self.b_descartar, self.b_siguiente, self.b_buscar, self.operador]
        )
        self.botones.add_class("pv-botones")

        self.raiz = widgets.VBox(
            [self.estilo, self.zona_recortes, self.zona_lectura, self.zona_reporte,
             self.botones, self.zona_aviso]
        )
        self.raiz.add_class("pv-panel")
        self.recargar()

    # Estado ---------------------------------------------------------------

    def actual(self):
        return self.cola[self.i] if self.i < len(self.cola) else None

    def recargar(self):
        eventos = ev.cargar(self.directorio)
        self.cola = ev.cola(eventos, bitacora.decididos(self.ruta_bitacora))
        self.i = 0
        self.pintar()

    def avanzar(self, mensaje=""):
        self.i += 1
        self.pintar(mensaje)

    def decidir(self, accion):
        evento = self.actual()
        if evento is None:
            return
        try:
            bitacora.registrar(self.ruta_bitacora, evento, accion, self.operador.value)
        except ValueError as error:
            self.zona_aviso.value = vistas.aviso(str(error))
            return
        self.avanzar()

    # Dibujo ---------------------------------------------------------------

    def pintar(self, mensaje=""):
        evento = self.actual()
        self.zona_aviso.value = vistas.aviso(mensaje)

        if evento is None:
            self.zona_recortes.value = vistas.vacio()
            self.zona_lectura.value = ""
            self.zona_reporte.value = ""
            for b in (self.b_confirmar, self.b_descartar, self.b_siguiente):
                _mostrar_si(b, False)
            _mostrar_si(self.b_buscar, True)
            return

        est = ev.estado(evento)
        self.zona_recortes.value = vistas.recortes(evento, self.directorio)
        self.zona_lectura.value = vistas.lectura(evento)
        self.zona_reporte.value = vistas.reporte(evento) if est != ev.NO_LEGIBLE else ""

        self.b_confirmar.description = "Confirmar alerta" if est == ev.ALERTA else "Confirmar"
        _mostrar_si(self.b_confirmar, est in (ev.ALERTA, ev.REVISION))
        _mostrar_si(self.b_descartar, est in (ev.ALERTA, ev.REVISION))
        _mostrar_si(self.b_siguiente, est == ev.NO_LEGIBLE)
        _mostrar_si(self.b_buscar, False)


def mostrar(directorio=None):
    """Crea el panel, lo muestra en la celda y lo devuelve (útil para depurar)."""
    panel = Panel(directorio)
    display(panel.raiz)
    return panel
