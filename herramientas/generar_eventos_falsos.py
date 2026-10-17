"""Genera eventos falsos del contrato para desarrollar el panel sin el pipeline.

SOLO PARA DESARROLLO. Cada evento lleva "falso": true y su id empieza con
"falso-", y el panel les pone la etiqueta "Dato de prueba". Nunca van en el video.

Escribe en su propia carpeta (por defecto ~/shared/eventos_falsos/) para no
mezclarse nunca con los eventos reales del pipeline.

Uso, dentro del contenedor de Jupyter (ya trae Pillow):
    python herramientas/generar_eventos_falsos.py
    python herramientas/generar_eventos_falsos.py --dir /otra/carpeta --semilla 3
"""
import argparse
import hashlib
import hmac
import json
import random
import sys
from datetime import datetime, timedelta, timezone
from pathlib import Path

from PIL import Image, ImageDraw, ImageFilter, ImageFont

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
from panel import config  # noqa: E402

# Solo para eventos falsos. La llave real va en una variable de entorno (bloque de privacidad).
CLAVE_DEV = b"clave-solo-desarrollo"
LETRAS = "ABCDEFGHJKLMNPRSTUVWXYZ"
DIGITOS = "0123456789"
CAMARAS = ("cam01", "cam02", "cam03")


def _placa(rng):
    return "".join(rng.choice(LETRAS) for _ in range(3)) + "".join(rng.choice(DIGITOS) for _ in range(4))


def _hmac(texto):
    return hmac.new(CLAVE_DEV, texto.encode(), hashlib.sha256).hexdigest()[:16]


def _dibujar(texto):
    """Placa sintética nítida de 320 × 100 px, en escala de grises."""
    img = Image.new("L", (320, 100), 235)
    d = ImageDraw.Draw(img)
    d.rectangle((3, 3, 316, 96), outline=40, width=4)
    fuente = ImageFont.load_default(size=56)
    x0, y0, x1, y1 = d.textbbox((0, 0), texto, font=fuente)
    d.text(((320 - (x1 - x0)) / 2 - x0, (100 - (y1 - y0)) / 2 - y0), texto, fill=20, font=fuente)
    return img


def _degradar(img, alto):
    """La placa como la vería una cámara lejana: desenfocada y de `alto` px."""
    ancho = round(alto * img.width / img.height)
    return img.filter(ImageFilter.GaussianBlur(1.5)).resize((ancho, alto), Image.BILINEAR)


def _guardar(img, carpeta, nombre):
    img.save(carpeta / nombre)
    return f"crops/{nombre}"


def generar(directorio=None, semilla=7):
    """Borra lo anterior de la carpeta de falsos y escribe 12 eventos, 3 por estado."""
    directorio = Path(directorio or config.EVENTOS_FALSOS_DIR)
    if directorio.resolve() == Path(config.EVENTOS_DIR).resolve():
        raise SystemExit("No escribo eventos falsos en la carpeta de eventos reales.")
    crops = directorio / "crops"
    crops.mkdir(parents=True, exist_ok=True)
    for viejo in crops.glob("falso-*.png"):
        viejo.unlink()
    (directorio / config.BITACORA_ARCHIVO).unlink(missing_ok=True)

    rng = random.Random(semilla)
    inicio = datetime(2026, 10, 17, 14, 0, tzinfo=timezone.utc)
    eventos = []

    for n in range(12):
        tipo = ("alerta", "revision", "no_legible", "sin_coincidencia")[n % 4]
        eid = f"falso-{n:03d}"
        texto = _placa(rng)
        cuadros = rng.randint(4, 8)
        evento = {
            "falso": True,
            "evento_id": eid,
            "camara_id": rng.choice(CAMARAS),
            "ts": (inicio + timedelta(seconds=37 * n)).strftime("%Y-%m-%dT%H:%M:%SZ"),
            "latencia_ms": {"deteccion": rng.randint(30, 60), "sr": rng.randint(10, 25), "ocr": rng.randint(20, 40)},
        }

        if tipo == "alerta":
            alto = rng.randint(18, 26)
            chica = _degradar(_dibujar(texto), alto)
            evento.update(
                placa_px_alto=alto,
                votacion={"texto": texto, "cuadros": cuadros,
                          "conf": [round(rng.uniform(0.85, 0.98), 2) for _ in texto]},
                placa_hmac=_hmac(texto), en_lista=True, decision="alerta", motivo="en_lista",
                recortes={
                    "original": _guardar(chica, crops, f"{eid}_lr.png"),
                    # Sustituto bicúbico de la SR: la real la entrega el modelo de Ana.
                    "sr": _guardar(chica.resize((chica.width * 4, alto * 4), Image.BICUBIC), crops, f"{eid}_sr.png"),
                },
                reporte={"estado": "listo", "texto": "[Dato de prueba] Texto de relleno: aquí va el reporte "
                         "de Granite con la lectura, su confianza y lo que no se pudo confirmar."},
            )
        elif tipo == "revision":
            alto = rng.randint(12, 15)
            chica = _degradar(_dibujar(texto), alto)
            dudoso = rng.randrange(len(texto))
            leido = texto[:dudoso] + "?" + texto[dudoso + 1:]
            conf = [round(rng.uniform(0.6, 0.95), 2) for _ in texto]
            conf[dudoso] = round(rng.uniform(0.2, 0.45), 2)
            evento.update(
                placa_px_alto=alto,
                votacion={"texto": leido, "cuadros": cuadros, "conf": conf},
                placa_hmac=None, en_lista=False, decision="revision", motivo="confianza_baja",
                recortes={
                    "original": _guardar(chica, crops, f"{eid}_lr.png"),
                    "sr": _guardar(chica.resize((chica.width * 4, alto * 4), Image.BICUBIC), crops, f"{eid}_sr.png"),
                },
                reporte=({"estado": "pendiente"} if n == 1 else
                         {"estado": "listo", "texto": "[Dato de prueba] Lectura dudosa en un carácter; "
                          "se pide revisión humana antes de cualquier alerta."}),
            )
        elif tipo == "no_legible":
            alto = rng.randint(6, 9)
            chica = _degradar(_dibujar(texto), alto)
            evento.update(
                placa_px_alto=alto, votacion={"cuadros": cuadros},
                placa_hmac=None, en_lista=False, decision="descartar", motivo=config.MOTIVO_PLACA_PEQUENA,
                recortes={"original": _guardar(chica, crops, f"{eid}_lr.png"), "sr": None},
            )
        else:  # sin coincidencia: legible y fuera de la lista; sin texto ni recortes
            evento.update(
                placa_px_alto=rng.randint(18, 26), votacion={"cuadros": cuadros},
                placa_hmac=_hmac(texto), en_lista=False, decision="descartar", motivo="no_en_lista",
                recortes=None,
            )
        eventos.append(evento)

    with (directorio / config.EVENTOS_ARCHIVO).open("w", encoding="utf-8") as f:
        for e in eventos:
            f.write(json.dumps(e, ensure_ascii=False) + "\n")
    print(f"{len(eventos)} eventos falsos en {directorio}")
    return eventos


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("--dir", default=None, help="carpeta de salida (por defecto EVENTOS_FALSOS_DIR)")
    parser.add_argument("--semilla", type=int, default=7)
    args = parser.parse_args()
    generar(args.dir, args.semilla)
