"""
logo.py (PySide6)
==================
Carga el logo de la empresa como QPixmap. A diferencia de Tkinter,
Qt no "olvida" las imágenes por falta de referencias activas, así
que no hace falta ningún cache manual — simplemente se carga el
archivo cada vez (QPixmap internamente cachea el decodificado).
"""

from pathlib import Path
from PySide6.QtGui import QPixmap

_CARPETA_ASSETS = Path(__file__).resolve().parent / "assets"
RUTA_LOGO_GRANDE = _CARPETA_ASSETS / "logo_grande.png"
RUTA_LOGO_CHICO = _CARPETA_ASSETS / "logo_chico.png"


def cargar_logo(tamano: str = "grande") -> QPixmap:
    """tamano: "grande" (login) o "chico" (menú lateral)."""
    ruta = RUTA_LOGO_GRANDE if tamano == "grande" else RUTA_LOGO_CHICO
    return QPixmap(str(ruta))
