"""dialogo_creditos.py (PySide6)
==================================
Ventana emergente "Acerca de / Créditos" del sistema.

Muestra los datos de autoría del proyecto (autor, institución, lugar y año).
Se puede abrir tanto desde la pantalla de inicio de sesión como desde el 
menú lateral de la ventana principal.
"""

from pathlib import Path

from PySide6.QtCore import Qt
from PySide6.QtGui import QPixmap
from PySide6.QtWidgets import (
    QDialog, QVBoxLayout, QHBoxLayout, QLabel, QPushButton, QFrame,
)

from app.ui.estilos import (
    COLOR_PRIMARIO, COLOR_TEXTO, COLOR_TEXTO_SECUNDARIO, fuente, fondo,
)
from app.ui.widgets import centrar_ventana
from app.ui.logo import cargar_logo

# ══════════════════════════════════════════════════════════════════
#  DATOS DE CRÉDITOS DEL PROYECTO
# ══════════════════════════════════════════════════════════════════
AUTOR = "Kevin Daniel Zuñiga Chacon"
INSTITUCION = "Universidad Andina del Cusco"
LUGAR = "Cusco - Perú"
ANIO = "2026"


class DialogoCreditos(QDialog):
    """Diálogo modal de "Acerca de" con los créditos del sistema."""

    def __init__(self, parent):
        super().__init__(parent)
        self.setWindowTitle("Créditos")
        self.setModal(True)
        self.setStyleSheet("background: white;")

        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(0)

        # Franja superior con logo
        franja = QFrame()
        fondo(franja, COLOR_PRIMARIO)
        flayout = QVBoxLayout(franja)
        flayout.setContentsMargins(24, 18, 24, 18)
        flayout.setSpacing(0)
        
        lbl_logo = QLabel()
        # Usar el logo de la universidad en lugar del logo de la empresa
        ruta_uac = Path(__file__).resolve().parent / "assets" / "UAC_logo.png"
        pix = QPixmap(str(ruta_uac))
        if not pix.isNull():
            pix = pix.scaled(160, 120, Qt.KeepAspectRatio, Qt.SmoothTransformation)
            lbl_logo.setPixmap(pix)
        lbl_logo.setAlignment(Qt.AlignCenter)
        flayout.addWidget(lbl_logo)
        layout.addWidget(franja)

        # Cuerpo con datos de créditos
        cuerpo = QVBoxLayout()
        cuerpo.setContentsMargins(28, 20, 28, 20)
        cuerpo.setSpacing(0)

        lbl_titulo = QLabel("Créditos")
        lbl_titulo.setFont(fuente(14, negrita=True))
        lbl_titulo.setStyleSheet(f"color: {COLOR_TEXTO};")
        lbl_titulo.setAlignment(Qt.AlignCenter)
        cuerpo.addWidget(lbl_titulo)
        cuerpo.addSpacing(14)

        self._agregar_fila(cuerpo, "Autor", AUTOR)
        self._agregar_fila(cuerpo, "Institución", INSTITUCION)
        self._agregar_fila(cuerpo, "Lugar", LUGAR)
        self._agregar_fila(cuerpo, "Año", ANIO)

        cuerpo.addSpacing(18)

        btn_cerrar = QPushButton("Cerrar")
        btn_cerrar.setFont(fuente(10))
        btn_cerrar.clicked.connect(self.accept)
        cuerpo.addWidget(btn_cerrar)

        layout.addLayout(cuerpo)
        centrar_ventana(self, 380, 340)

    def _agregar_fila(self, layout_padre, etiqueta: str, valor: str):
        """Agrega una fila con etiqueta y valor."""
        lbl_etiqueta = QLabel(f"{etiqueta}:")
        lbl_etiqueta.setFont(fuente(10, negrita=True))
        lbl_etiqueta.setStyleSheet(f"color: {COLOR_TEXTO_SECUNDARIO};")
        layout_padre.addWidget(lbl_etiqueta)

        lbl_valor = QLabel(valor)
        lbl_valor.setFont(fuente(11))
        lbl_valor.setStyleSheet(f"color: {COLOR_TEXTO};")
        lbl_valor.setWordWrap(True)
        layout_padre.addWidget(lbl_valor)
        layout_padre.addSpacing(8)

    def keyPressEvent(self, evento):
        if evento.key() == Qt.Key_Escape:
            self.accept()
        else:
            super().keyPressEvent(evento)


def mostrar_creditos(parent):
    """Abre el diálogo de créditos como ventana modal."""
    DialogoCreditos(parent).exec()
