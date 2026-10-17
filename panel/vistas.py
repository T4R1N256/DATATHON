"""HTML de cada zona del panel.

Solo arman texto HTML a partir del evento: no tocan widgets ni escriben archivos.
Las clases CSS están en estilos.css. Todo texto que viene del evento pasa por
html.escape.
"""
import base64
import html

from . import config
from . import eventos as ev

_BADGES = {
    ev.ALERTA: ("pv-badge-alerta", "Coincide con la lista"),
    ev.REVISION: ("pv-badge-revision", "Lectura dudosa"),
    ev.NO_LEGIBLE: ("pv-badge-nolegible", "No legible: el sistema no adivina"),
}


def _img(ruta, alt):
    if ruta is None:
        return f'<div class="pv-img pv-img-vacia">{html.escape(alt)}: sin recorte</div>'
    b64 = base64.b64encode(ruta.read_bytes()).decode()
    return f'<img class="pv-img" src="data:image/png;base64,{b64}" alt="{html.escape(alt)}">'


def _figura(ruta, alt, pie):
    return (
        '<figure class="pv-figura">'
        f"{_img(ruta, alt)}"
        f'<figcaption class="pv-pie">{html.escape(pie)}</figcaption>'
        "</figure>"
    )


def _clase_conf(c):
    if c is None:
        return "pv-conf-nd"
    if c >= config.CONF_ALTA:
        return "pv-conf-alta"
    if c >= config.CONF_MEDIA:
        return "pv-conf-media"
    return "pv-conf-baja"


def _hora(ts):
    """'2026-10-17T14:05:12.400Z' -> '14:05:12 UTC'; si no se puede leer, lo deja igual."""
    if not ts or "T" not in ts:
        return ts
    hora = ts.split("T", 1)[1][:8]
    return f"{hora} UTC" if ts.endswith("Z") else hora


def _marca_falso(evento):
    if evento.get("falso"):
        return '<span class="pv-badge pv-badge-falso">Dato de prueba</span>'
    return ""


def recortes(evento, directorio=None):
    """Original y SR al mismo ancho; en 'no legible' solo el original."""
    alto = evento.get("placa_px_alto")
    lat_sr = (evento.get("latencia_ms") or {}).get("sr")
    pie_orig = "Original · píxeles reales" + (f" · {alto} px de alto" if alto is not None else "")
    pie_sr = "Mejorada (SR)" + (f" · {lat_sr} ms" if lat_sr is not None else "")

    original = _figura(ev.ruta_recorte(evento, "original", directorio), "Recorte original", pie_orig)
    if ev.estado(evento) == ev.NO_LEGIBLE:
        cuerpo = f'<div class="pv-recortes pv-recortes-uno">{original}</div>'
    else:
        sr = _figura(ev.ruta_recorte(evento, "sr", directorio), "Recorte con SR", pie_sr)
        cuerpo = f'<div class="pv-recortes">{original}{sr}</div>'
    return (
        '<div class="pv-card">'
        f'<div class="pv-cabecera"><h3 class="pv-titulo">Comparativa del recorte</h3>{_marca_falso(evento)}</div>'
        f"{cuerpo}</div>"
    )


def lectura(evento):
    """Badge del estado, placa votada con color por carácter y datos de contexto."""
    est = ev.estado(evento)
    clase, texto_badge = _BADGES.get(est, ("pv-badge-nolegible", ""))
    badge = f'<span class="pv-badge {clase}">{html.escape(texto_badge)}</span>'

    if est == ev.NO_LEGIBLE:
        alto = evento.get("placa_px_alto")
        detalle = f"La placa mide {alto} px de alto." if alto is not None else ""
        placa = f'<p class="pv-nolegible">{html.escape(detalle)} Va a revisión humana sin lectura.</p>'
    else:
        texto, conf = ev.lectura(evento)
        celdas = "".join(
            f'<span class="pv-char {_clase_conf(c)}">{html.escape(ch)}</span>'
            for ch, c in zip(texto, conf)
        )
        placa = f'<div class="pv-placa">{celdas or "—"}</div>'

    cuadros = (evento.get("votacion") or {}).get("cuadros")
    meta = " · ".join(
        p for p in (
            evento.get("camara_id"),
            _hora(evento.get("ts")),
            f"votación entre {cuadros} cuadros" if cuadros else None,
        ) if p
    )
    return (
        '<div class="pv-card">'
        f'<div class="pv-cabecera"><h3 class="pv-titulo">Lectura votada</h3>{badge}</div>'
        f'{placa}<p class="pv-meta">{html.escape(meta)}</p></div>'
    )


def reporte(evento):
    """Reporte de Granite según su estado; nunca bloquea la pantalla."""
    rep = evento.get("reporte") or {}
    estado_rep = rep.get("estado")
    if estado_rep == "listo" and rep.get("texto"):
        cuerpo = f'<p>{html.escape(rep["texto"])}</p>'
    elif estado_rep == "pendiente":
        cuerpo = '<p class="pv-meta">Generando reporte…</p>'
    else:
        cuerpo = '<p class="pv-meta">Sin reporte para este evento.</p>'
    return f'<div class="pv-card"><h3 class="pv-titulo">Reporte del incidente (Granite)</h3>{cuerpo}</div>'


def vacio():
    return (
        '<div class="pv-card pv-vacio">'
        '<h3 class="pv-titulo">Sin eventos pendientes</h3>'
        '<p class="pv-meta">Cuando el pipeline escriba eventos nuevos, búscalos con el botón.</p>'
        "</div>"
    )


def aviso(mensaje):
    return f'<p class="pv-aviso">{html.escape(mensaje)}</p>' if mensaje else ""
