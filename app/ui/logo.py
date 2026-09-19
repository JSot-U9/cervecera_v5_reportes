"""
logo.py (PySide6)
==================
Carga el logo de la empresa como QPixmap. A diferencia de Tkinter,
Qt no "olvida" las imágenes por falta de referencias activas, así
que no hace falta ningún cache manual — simplemente se carga el
archivo cada vez (QPixmap internamente cachea el decodificado).
"""

from pathlib import Path

from PySide6.QtCore import Qt
from PySide6.QtGui import QPixmap
from PySide6.QtWidgets import QLabel

_CARPETA_ASSETS = Path(__file__).resolve().parent / "assets"
RUTA_LOGO_GRANDE = _CARPETA_ASSETS / "logo_grande.png"
RUTA_LOGO_CHICO = _CARPETA_ASSETS / "logo_chico.png"


def cargar_logo(tamano: str = "grande", ancho_max: int = 0, alto_max: int = 0) -> QPixmap:
    """tamano: "grande" (login) o "chico" (menú lateral).

    `ancho_max` / `alto_max` escalan el logo para que quepa entero en
    el espacio del que dispone, manteniendo la proporción.

    Por qué hace falta: los archivos miden 384×256 (grande) y 192×128
    (chico), pero el espacio útil real es menor — unos 320 px en la
    ventana de login y ~186 px en la tarjeta del menú lateral. Sin
    escalar, Qt no encoge el QPixmap: simplemente lo recorta contra los
    bordes del QLabel, y el logo de la cervecería se veía cortado y
    pisado por el texto que va debajo. Escalando con
    SmoothTransformation se ve completo y nítido.
    """
    ruta = RUTA_LOGO_GRANDE if tamano == "grande" else RUTA_LOGO_CHICO
    pixmap = QPixmap(str(ruta))
    if pixmap.isNull():
        return pixmap

    if ancho_max <= 0 and alto_max <= 0:
        return pixmap

    ancho_destino = ancho_max if ancho_max > 0 else pixmap.width()
    alto_destino = alto_max if alto_max > 0 else pixmap.height()
    # Nunca ampliar: si el logo ya entra, se deja tal cual.
    if pixmap.width() <= ancho_destino and pixmap.height() <= alto_destino:
        return pixmap
    return pixmap.scaled(ancho_destino, alto_destino,
                         Qt.KeepAspectRatio, Qt.SmoothTransformation)


class EtiquetaLogoResponsiva(QLabel):
    """QLabel con el logo de la empresa que se reescala solo cada vez
    que SU PROPIO tamaño cambia — no una sola vez, con un ancho
    "adivinado" al construir la ventana.

    Por qué hace falta: `cargar_logo(ancho_max=...)` (más arriba)
    escala el pixmap UNA vez, asumiendo un ancho fijo del contenedor.
    Eso ya arregla el recorte con el layout actual, pero si el espacio
    disponible cambia por cualquier motivo (una ventana más angosta,
    otro DPI, un sidebar que en el futuro se pueda redimensionar), el
    pixmap ya escalado no vuelve a ajustarse — puede quedar más grande
    que su nuevo espacio y recortarse otra vez contra el texto vecino
    (justo el bug original: el logo se veía "detrás" del texto de la
    empresa). Esta clase resuelve eso de raíz: guarda el pixmap
    ORIGINAL sin escalar y lo reescala cada vez que Qt le asigna un
    tamaño distinto, así que siempre entra completo sin importar qué
    tan grande o chico sea el espacio en ese momento.
    """

    def __init__(self, tamano: str = "chico", parent=None):
        super().__init__(parent)
        ruta = RUTA_LOGO_GRANDE if tamano == "grande" else RUTA_LOGO_CHICO
        self._pixmap_original = QPixmap(str(ruta))
        self.setAlignment(Qt.AlignCenter)
        self.setStyleSheet("background: transparent;")
        # minimumSize en 1x1 (y no en el tamaño real del logo): así el
        # layout SÍ puede encogerlo si hace falta, en vez de forzar un
        # tamaño mínimo que vuelva a producir el recorte que se quiere
        # evitar.
        self.setMinimumSize(1, 1)
        self._actualizar_pixmap()

    def resizeEvent(self, evento):
        super().resizeEvent(evento)
        self._actualizar_pixmap()

    def _actualizar_pixmap(self):
        if self._pixmap_original.isNull() or self.width() <= 0 or self.height() <= 0:
            return
        escalado = self._pixmap_original.scaled(
            self.width(), self.height(), Qt.KeepAspectRatio, Qt.SmoothTransformation)
        self.setPixmap(escalado)

    def alto_para_ancho(self, ancho: int) -> int:
        """Alto que le correspondería al logo si se le da este ancho,
        manteniendo su proporción original — útil para reservarle un
        espacio de tamaño fijo al contenedor que lo aloja."""
        if self._pixmap_original.isNull() or self._pixmap_original.width() <= 0:
            return 0
        proporcion = self._pixmap_original.height() / self._pixmap_original.width()
        return round(ancho * proporcion)
