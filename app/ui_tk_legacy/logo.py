"""
logo.py
=======
Carga el logo de la empresa (assets/logo_grande.png y logo_chico.png)
como imágenes de Tkinter, para usarlas en el login y en el menú lateral.

¿Por qué una función y no simplemente `tk.PhotoImage(file=...)` en cada
pantalla? Porque Tkinter "olvida" (recolecta como basura) una imagen si
ningún objeto Python la sigue referenciando — un error clásico y
confuso para quien recién empieza es ver la imagen desaparecer sola.
Por eso esta función guarda cada imagen ya cargada en el diccionario
_CACHE, para que exista una referencia viva mientras el programa corre.
"""

import tkinter as tk
from pathlib import Path

_CARPETA_ASSETS = Path(__file__).resolve().parent / "assets"
RUTA_LOGO_GRANDE = _CARPETA_ASSETS / "logo_grande.png"
RUTA_LOGO_CHICO = _CARPETA_ASSETS / "logo_chico.png"

_CACHE = {}


def cargar_logo(ventana, tamano="grande"):
    """
    Devuelve un tk.PhotoImage con el logo de la empresa.
    'tamano' es "grande" (para el login) o "chico" (para el menú lateral).

    IMPORTANTE: cada ventana raíz (Tk) tiene su propio "mundo" de
    imágenes en Tkinter, por eso la imagen se crea pasándole 'ventana'
    y se guarda en el cache junto con el id de esa ventana.
    """
    ruta = RUTA_LOGO_GRANDE if tamano == "grande" else RUTA_LOGO_CHICO
    clave = (id(ventana), tamano)
    if clave not in _CACHE:
        _CACHE[clave] = tk.PhotoImage(master=ventana, file=str(ruta))
    return _CACHE[clave]
