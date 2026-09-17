"""header.py (PySide6)
======================
Header superior consistente para todas las pantallas del ERP
(sección 8 del rediseño UI/UX):

    [Nombre de pantalla / breadcrumb]   [🔎 Buscar]   [🔔] [👤 Usuario]

La búsqueda global consulta app.logica_busqueda.buscar_global y
muestra resultados agrupados por categoría en un popup; al elegir
uno, emite `resultadoSeleccionado` con el dict del resultado para
que la ventana principal navegue al módulo correspondiente.
"""

from __future__ import annotations

from PySide6.QtCore import Qt, Signal, QPoint
from PySide6.QtGui import QColor
from PySide6.QtWidgets import (
    QFrame, QHBoxLayout, QVBoxLayout, QLabel, QLineEdit, QPushButton,
    QListWidget, QListWidgetItem,
)

from app.ui.estilos import (
    COLOR_TARJETA, COLOR_TEXTO, COLOR_TEXTO_SECUNDARIO,
    _COLOR_SEPARADOR, fuente, fondo, poner_clase,
)
from app.ui.widgets import Migaja
from app.logica_busqueda import buscar_global


class HeaderSuperior(QFrame):
    resultadoSeleccionado = Signal(dict)
    notificacionesClic = Signal()

    def __init__(self, parent=None):
        super().__init__(parent)
        fondo(self, COLOR_TARJETA, f"border-bottom: 1px solid {_COLOR_SEPARADOR};")
        self.setFixedHeight(58)

        layout = QHBoxLayout(self)
        layout.setContentsMargins(22, 8, 22, 8)
        layout.setSpacing(16)

        # ── Título / breadcrumb de la pantalla actual ───────────────
        col_titulo = QVBoxLayout()
        col_titulo.setSpacing(1)
        self._lbl_titulo = QLabel("Inicio")
        self._lbl_titulo.setFont(fuente(12, negrita=True))
        self._lbl_titulo.setStyleSheet(f"background: transparent; color: {COLOR_TEXTO};")
        col_titulo.addWidget(self._lbl_titulo)
        self._migaja = Migaja([])
        col_titulo.addWidget(self._migaja)
        layout.addLayout(col_titulo)

        layout.addStretch()

        # ── Búsqueda global ──────────────────────────────────────────
        self.campo_busqueda = QLineEdit()
        self.campo_busqueda.setPlaceholderText("🔎  Buscar en el ERP...   (Ctrl+K)")
        self.campo_busqueda.setFixedWidth(320)
        self.campo_busqueda.textChanged.connect(self._al_escribir)
        layout.addWidget(self.campo_busqueda)

        self._popup = QListWidget()
        self._popup.setWindowFlags(Qt.Popup)
        self._popup.setFocusProxy(self.campo_busqueda)
        self._popup.setStyleSheet(
            f"QListWidget {{ background-color: {COLOR_TARJETA}; "
            f"border: 1px solid {_COLOR_SEPARADOR}; font-size: 9pt; }}"
        )
        self._popup.itemClicked.connect(self._al_click_resultado)

        # ── Notificaciones ───────────────────────────────────────────
        self.btn_notificaciones = QPushButton("🔔")
        poner_clase(self.btn_notificaciones, "secundario")
        self.btn_notificaciones.setFixedWidth(44)
        self.btn_notificaciones.setToolTip("Alertas pendientes")
        self.btn_notificaciones.clicked.connect(self.notificacionesClic.emit)
        layout.addWidget(self.btn_notificaciones)

        # ── Usuario actual ───────────────────────────────────────────
        col_usuario = QVBoxLayout()
        col_usuario.setSpacing(0)
        self._lbl_usuario = QLabel("")
        self._lbl_usuario.setFont(fuente(9, negrita=True))
        self._lbl_usuario.setStyleSheet(f"background: transparent; color: {COLOR_TEXTO};")
        col_usuario.addWidget(self._lbl_usuario)
        self._lbl_rol = QLabel("")
        self._lbl_rol.setFont(fuente(8))
        self._lbl_rol.setStyleSheet(f"background: transparent; color: {COLOR_TEXTO_SECUNDARIO};")
        col_usuario.addWidget(self._lbl_rol)
        layout.addLayout(col_usuario)

        lbl_avatar = QLabel("👤")
        lbl_avatar.setFont(fuente(17))
        lbl_avatar.setStyleSheet("background: transparent;")
        layout.addWidget(lbl_avatar)

    # ── API pública ──────────────────────────────────────────────────
    def establecer_titulo(self, titulo: str, migas: list = None):
        self._lbl_titulo.setText(titulo)
        self._migaja.establecer(migas if migas else [titulo])

    def establecer_usuario(self, nombre: str, rol: str):
        self._lbl_usuario.setText(nombre)
        self._lbl_rol.setText(rol)

    def establecer_notificaciones(self, cantidad: int):
        self.btn_notificaciones.setText(f"🔔 {cantidad}" if cantidad else "🔔")

    def enfocar_busqueda(self):
        self.campo_busqueda.setFocus()
        self.campo_busqueda.selectAll()

    # ── Búsqueda global ──────────────────────────────────────────────
    def _al_escribir(self, texto: str):
        texto = texto.strip()
        if len(texto) < 2:
            self._popup.hide()
            return

        resultados = buscar_global(texto)
        self._popup.clear()

        if not resultados:
            item = QListWidgetItem(f"Sin resultados para «{texto}»")
            item.setFlags(Qt.NoItemFlags)
            item.setForeground(QColor(COLOR_TEXTO_SECUNDARIO))
            self._popup.addItem(item)
        else:
            categoria_actual = None
            for r in resultados:
                if r["categoria"] != categoria_actual:
                    categoria_actual = r["categoria"]
                    encabezado = QListWidgetItem(categoria_actual.upper())
                    encabezado.setFlags(Qt.NoItemFlags)
                    encabezado.setFont(fuente(8, negrita=True))
                    encabezado.setForeground(QColor(COLOR_TEXTO_SECUNDARIO))
                    self._popup.addItem(encabezado)
                item = QListWidgetItem(f"{r['titulo']}   —   {r['subtitulo']}")
                item.setData(Qt.UserRole, r)
                item.setFont(fuente(9))
                self._popup.addItem(item)

        self._posicionar_popup()
        self._popup.show()

    def _posicionar_popup(self):
        self._popup.setFixedWidth(self.campo_busqueda.width())
        punto = self.campo_busqueda.mapToGlobal(QPoint(0, self.campo_busqueda.height() + 2))
        self._popup.move(punto)

    def _al_click_resultado(self, item: QListWidgetItem):
        datos = item.data(Qt.UserRole)
        if not datos:
            return
        self._popup.hide()
        self.campo_busqueda.clear()
        self.resultadoSeleccionado.emit(datos)
