"""login.py (PySide6)
=====================
Ventana de inicio de sesión. Se usa como QDialog modal desde main.py:

    login = VentanaLogin()
    login.exec()
    if login.acepto:
        ...continuar...
"""

from PySide6.QtCore import Qt
from PySide6.QtWidgets import (
    QDialog, QVBoxLayout, QHBoxLayout, QLabel, QLineEdit, QPushButton, QFrame,
)

from app.logica_autenticacion import iniciar_sesion, ErrorAutenticacion
from app.ui.estilos import COLOR_PRIMARIO, COLOR_ALERTA, COLOR_TEXTO_SECUNDARIO, fuente, poner_clase, fondo
from app.ui.widgets import ajustar_ventana_a_contenido, centrar_ventana
from app.ui.logo import cargar_logo, EtiquetaLogoResponsiva
from app.ui.dialogo_creditos import mostrar_creditos


class VentanaLogin(QDialog):
    def __init__(self):
        super().__init__()
        self.setWindowTitle("Iniciar sesión")
        self.setFixedSize(380, 650)
        self.acepto = False

        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(0)

        # Franja superior con el logo
        franja = QFrame()
        fondo(franja, COLOR_PRIMARIO)
        flayout = QVBoxLayout(franja)
        flayout.setContentsMargins(30, 24, 30, 20)
        flayout.setSpacing(6)
        flayout.setAlignment(Qt.AlignCenter)

        # El ancho útil de la franja es 380 − 30 − 30 = 320 px.
        #
        # EtiquetaLogoResponsiva: reescala el logo cada vez que su
        # espacio cambia, en vez de fijar una escala una sola vez al
        # construir la ventana — así nunca vuelve a quedar recortado
        # ni superpuesto con el subtítulo de abajo.
        ANCHO_UTIL_LOGO = 320
        lbl_logo = EtiquetaLogoResponsiva("grande")
        alto_logo = min(lbl_logo.alto_para_ancho(ANCHO_UTIL_LOGO), 190)
        lbl_logo.setFixedHeight(alto_logo)
        flayout.addWidget(lbl_logo)

        lbl_sub = QLabel("Sistema de gestión integrada")
        lbl_sub.setStyleSheet("background: transparent; color: #F2D9B8;")
        lbl_sub.setFont(fuente(9))
        lbl_sub.setAlignment(Qt.AlignCenter)
        flayout.addWidget(lbl_sub)
        layout.addWidget(franja)

        # Formulario
        contenedor = QVBoxLayout()
        contenedor.setContentsMargins(30, 24, 30, 24)
        contenedor.setSpacing(4)

        contenedor.addWidget(QLabel("Usuario:"))
        self.entrada_usuario = QLineEdit()
        contenedor.addWidget(self.entrada_usuario)
        contenedor.addSpacing(10)

        contenedor.addWidget(QLabel("Contraseña:"))
        self.entrada_contrasena = QLineEdit()
        self.entrada_contrasena.setEchoMode(QLineEdit.Password)
        self.entrada_contrasena.returnPressed.connect(self._intentar_login)
        contenedor.addWidget(self.entrada_contrasena)
        contenedor.addSpacing(6)

        self.etiqueta_error = QLabel("")
        self.etiqueta_error.setStyleSheet(f"color: {COLOR_ALERTA};")
        self.etiqueta_error.setWordWrap(True)
        contenedor.addWidget(self.etiqueta_error)
        contenedor.addSpacing(4)

        btn_login = QPushButton("Iniciar sesión")
        btn_login.clicked.connect(self._intentar_login)
        contenedor.addWidget(btn_login)

        btn_salir = QPushButton("Salir")
        poner_clase(btn_salir, "secundario")
        btn_salir.clicked.connect(self._salir)
        contenedor.addWidget(btn_salir)

        contenedor.addSpacing(6)
        btn_creditos = QPushButton("ℹ️  Créditos")
        poner_clase(btn_creditos, "secundario")
        btn_creditos.clicked.connect(lambda: mostrar_creditos(self))
        contenedor.addWidget(btn_creditos)

        contenedor.addStretch()
        layout.addLayout(contenedor)

        self.entrada_usuario.setFocus()
        centrar_ventana(self, 380, 650)

    def _intentar_login(self):
        self.etiqueta_error.setText("")
        try:
            iniciar_sesion(self.entrada_usuario.text().strip(), self.entrada_contrasena.text())
            self.acepto = True
            self.accept()
        except ErrorAutenticacion as error:
            self.etiqueta_error.setText(str(error))
            self.entrada_contrasena.clear()

    def _salir(self):
        self.acepto = False
        self.reject()

    def keyPressEvent(self, evento):
        if evento.key() == Qt.Key_Escape:
            self._salir()
        else:
            super().keyPressEvent(evento)
