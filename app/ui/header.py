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

from PySide6.QtCore import Qt, Signal, QPoint, QTimer, QEvent
from PySide6.QtGui import QColor
from PySide6.QtWidgets import (
    QFrame, QHBoxLayout, QVBoxLayout, QLabel, QLineEdit, QPushButton,
    QListWidget, QListWidgetItem, QSizePolicy,
)

from app.ui.estilos import (
    COLOR_TARJETA, COLOR_TEXTO, COLOR_TEXTO_SECUNDARIO, COLOR_PRIMARIO_CLARO,
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
        self.campo_busqueda.textChanged.connect(self._programar_busqueda)
        self.campo_busqueda.installEventFilter(self)
        layout.addWidget(self.campo_busqueda)

        self._popup = QListWidget()
        # Qt.ToolTip (y NO Qt.Popup): una ventana con la bandera
        # Qt.Popup toma un "grab" de teclado y de ratón a nivel de
        # aplicación en cuanto se muestra. Como el popup aparecía justo
        # al llegar al mínimo de 2 caracteres, a partir de ese momento
        # las teclas dejaban de llegar al campo de búsqueda y el texto
        # se quedaba congelado en esos 2 primeros caracteres. Ninguna
        # llamada posterior a setFocus() lo arregla, porque el problema
        # es el grab, no el foco. Qt.ToolTip + WA_ShowWithoutActivating
        # muestra la lista sin robar nada: el usuario sigue escribiendo
        # con normalidad.
        self._popup.setWindowFlags(Qt.ToolTip | Qt.FramelessWindowHint)
        self._popup.setAttribute(Qt.WA_ShowWithoutActivating)
        self._popup.setFocusPolicy(Qt.NoFocus)
        self._popup.setStyleSheet(
            f"QListWidget {{ background-color: {COLOR_TARJETA}; "
            f"border: 1px solid {_COLOR_SEPARADOR}; font-size: 9pt; }}"
            f"QListWidget::item:selected {{ background-color: {COLOR_PRIMARIO_CLARO}; "
            f"color: {COLOR_TEXTO}; }}"
        )
        self._popup.itemClicked.connect(self._al_click_resultado)

        # La búsqueda consulta 7 tablas; lanzarla en cada pulsación
        # hacía que escribir rápido se sintiera pesado. Se espera a que
        # el usuario deje de teclear un momento.
        self._temporizador_busqueda = QTimer(self)
        self._temporizador_busqueda.setSingleShot(True)
        self._temporizador_busqueda.setInterval(220)
        self._temporizador_busqueda.timeout.connect(self._ejecutar_busqueda)

        # ── Notificaciones ───────────────────────────────────────────
        self.btn_notificaciones = QPushButton("🔔")
        poner_clase(self.btn_notificaciones, "secundario")
        # Antes: setFixedWidth(44). Con el padding del QSS, "🔔 137"
        # necesita ~74 px, así que Qt recortaba el texto y el usuario
        # leía "13" donde el sistema quería decir 137. Ahora el botón
        # crece con su contenido y el número nunca queda cortado.
        self.btn_notificaciones.setMinimumWidth(44)
        self.btn_notificaciones.setSizePolicy(QSizePolicy.Minimum, QSizePolicy.Fixed)
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
        cantidad = max(0, int(cantidad or 0))
        if not cantidad:
            self.btn_notificaciones.setText("🔔")
            self.btn_notificaciones.setToolTip("No hay asuntos pendientes")
        else:
            # Por encima de 99 se muestra "99+" para que el botón no
            # empuje al resto del header, pero el número exacto queda
            # siempre disponible en el tooltip.
            etiqueta = str(cantidad) if cantidad <= 99 else "99+"
            self.btn_notificaciones.setText(f"🔔 {etiqueta}")
            self.btn_notificaciones.setToolTip(
                f"{cantidad} asunto(s) requieren tu atención — clic para verlos en Inicio"
            )
        self.btn_notificaciones.adjustSize()
        self.btn_notificaciones.updateGeometry()

    def enfocar_busqueda(self):
        self.campo_busqueda.setFocus()
        self.campo_busqueda.selectAll()

    # ── Búsqueda global ──────────────────────────────────────────────
    def _programar_busqueda(self, _texto: str = ""):
        if len(self.campo_busqueda.text().strip()) < 2:
            self._temporizador_busqueda.stop()
            self._popup.hide()
            return
        self._temporizador_busqueda.start()

    def eventFilter(self, obj, evento):
        """Permite manejar el popup con el teclado sin que este tenga
        el foco: las flechas mueven la selección, Enter abre el
        resultado y Escape cierra la lista."""
        if obj is self.campo_busqueda and evento.type() == QEvent.KeyPress:
            tecla = evento.key()
            if tecla == Qt.Key_Escape and self._popup.isVisible():
                self._popup.hide()
                return True
            if self._popup.isVisible() and tecla in (Qt.Key_Down, Qt.Key_Up):
                self._mover_seleccion(1 if tecla == Qt.Key_Down else -1)
                return True
            if tecla in (Qt.Key_Return, Qt.Key_Enter):
                if self._popup.isVisible():
                    item = self._popup.currentItem()
                    if item is not None and item.data(Qt.UserRole):
                        self._al_click_resultado(item)
                        return True
                # Sin selección todavía: forzar la búsqueda inmediata
                # en vez de esperar al temporizador.
                self._temporizador_busqueda.stop()
                self._ejecutar_busqueda()
                return True
        elif obj is self.campo_busqueda and evento.type() == QEvent.FocusOut:
            self._popup.hide()
        return super().eventFilter(obj, evento)

    def _mover_seleccion(self, paso: int):
        """Avanza a la siguiente fila seleccionable, saltándose los
        encabezados de categoría (que están deshabilitados)."""
        total = self._popup.count()
        if not total:
            return
        fila = self._popup.currentRow()
        for _ in range(total):
            fila += paso
            if fila < 0:
                fila = total - 1
            elif fila >= total:
                fila = 0
            item = self._popup.item(fila)
            if item is not None and item.data(Qt.UserRole):
                self._popup.setCurrentRow(fila)
                return

    def _ejecutar_busqueda(self):
        texto = self.campo_busqueda.text().strip()
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
        # Preseleccionar el primer resultado real para que Enter
        # funcione de inmediato.
        self._popup.setCurrentRow(-1)
        self._mover_seleccion(1)

    def _posicionar_popup(self):
        self._popup.setFixedWidth(self.campo_busqueda.width())
        alto_fila = 24
        filas_visibles = min(self._popup.count(), 12)
        self._popup.setFixedHeight(max(alto_fila, filas_visibles * alto_fila + 8))
        punto = self.campo_busqueda.mapToGlobal(QPoint(0, self.campo_busqueda.height() + 2))
        self._popup.move(punto)

    def hideEvent(self, evento):
        # Si la ventana principal se oculta o cambia de pantalla, el
        # popup (que es una ventana aparte) no debe quedar flotando.
        # Al cerrar la aplicación, Qt puede destruir el popup antes que
        # este header durante la limpieza final — se ignora ese caso.
        try:
            self._popup.hide()
        except RuntimeError:
            pass
        super().hideEvent(evento)

    def _al_click_resultado(self, item: QListWidgetItem):
        datos = item.data(Qt.UserRole)
        if not datos:
            return
        self._popup.hide()
        self.campo_busqueda.clear()
        self.resultadoSeleccionado.emit(datos)
