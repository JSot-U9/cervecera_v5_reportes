"""dialogo_creditos.py (PySide6)"""

from PySide6.QtCore import Qt
from PySide6.QtWidgets import QDialog, QVBoxLayout, QHBoxLayout, QLabel, QPushButton, QFrame

from app.ui.estilos import COLOR_PRIMARIO, COLOR_TEXTO, COLOR_TEXTO_SECUNDARIO, fuente, fondo
from app.ui.widgets import centrar_ventana


class DialogoCreditos(QDialog):
    def __init__(self, parent):
        super().__init__(parent)
        self.setWindowTitle("Créditos")

        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(0)

        franja = QFrame()
        fondo(franja, COLOR_PRIMARIO)
        flayout = QVBoxLayout(franja)
        flayout.setContentsMargins(24, 20, 24, 20)
        lbl = QLabel("🍺  Cervecera v5")
        lbl.setStyleSheet("background: transparent; color: white;")
        lbl.setFont(fuente(16, negrita=True))
        flayout.addWidget(lbl)
        layout.addWidget(franja)

        cuerpo = QVBoxLayout()
        cuerpo.setContentsMargins(24, 18, 24, 18)
        cuerpo.setSpacing(6)
        for texto in (
            "Sistema de gestión para cervecerías artesanales",
            "Compras · Inventario (FIFO) · Producción · Ventas · Costos",
            "",
            "Desarrollado con Python, SQLAlchemy y PySide6.",
        ):
            lbl2 = QLabel(texto)
            lbl2.setFont(fuente(9))
            lbl2.setStyleSheet(f"color: {COLOR_TEXTO_SECUNDARIO};")
            lbl2.setWordWrap(True)
            cuerpo.addWidget(lbl2)
        layout.addLayout(cuerpo)

        barra = QHBoxLayout()
        barra.setContentsMargins(24, 0, 24, 18)
        barra.addStretch()
        btn = QPushButton("Cerrar")
        btn.clicked.connect(self.accept)
        barra.addWidget(btn)
        layout.addLayout(barra)

        centrar_ventana(self, 420, 260)

    def keyPressEvent(self, evento):
        if evento.key() == Qt.Key_Escape:
            self.accept()
        else:
            super().keyPressEvent(evento)


def mostrar_creditos(parent):
    DialogoCreditos(parent).exec()
