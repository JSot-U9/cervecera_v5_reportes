"""widgets.py (PySide6)
=======================
Design system: componentes reutilizables para el ERP Cervecería.

Componentes:
  - centrar_ventana, ajustar_ventana_a_contenido
  - EncabezadoModulo     : franja superior con título y subtítulo
  - TarjetaKPI           : tarjeta con valor numérico y etiqueta
  - BarraBusqueda        : campo de filtro + botones de acción
  - TablaDatos           : QTableWidget con filas alternas, tags de color y filtro
  - formatear_estado     : "EN_PROCESO" -> "🟠 En proceso"
  - SeccionFormulario    : QGroupBox estilizado para agrupar campos
  - CampoFormulario      : label + entry/combobox con validación inline
  - DialogoConfirmacion / confirmar : diálogo modal sí/no
  - MensajeEstado        : banda de mensaje éxito/error/advertencia
  - BarraEstado          : barra inferior con usuario/rol
"""

from PySide6.QtCore import Qt, QTimer, QThread, Signal
from PySide6.QtGui import QScreen
from PySide6.QtWidgets import (
    QWidget, QLabel, QFrame, QVBoxLayout, QHBoxLayout, QPushButton,
    QLineEdit, QComboBox, QTableWidget, QTableWidgetItem, QHeaderView,
    QAbstractItemView, QGroupBox, QDialog, QApplication, QGraphicsDropShadowEffect,
    QProgressBar,
)
from PySide6.QtGui import QColor

from app.ui.estilos import (
    COLOR_TEXTO, COLOR_TEXTO_SECUNDARIO, COLOR_PRIMARIO,
    COLOR_ALERTA, COLOR_EXITO, COLOR_ADVERTENCIA,
    COLOR_FONDO, COLOR_TARJETA, COLOR_SIDEBAR, COLOR_SIDEBAR_TEXTO,
    _COLOR_SEPARADOR, poner_clase, fuente, fondo, estilo_escopado,
)


# ══════════════════════════════════════════════════════════════════
#  UTILIDADES DE VENTANA
# ══════════════════════════════════════════════════════════════════

def centrar_ventana(ventana: QWidget, ancho: int, alto: int):
    ventana.resize(ancho, alto)
    pantalla = ventana.screen() or QApplication.primaryScreen()
    geo = pantalla.availableGeometry()
    x = geo.x() + (geo.width() - ancho) // 2
    y = geo.y() + (geo.height() - alto) // 2
    ventana.move(x, y)


def ajustar_ventana_a_contenido(ventana: QWidget, ancho: int = None):
    ventana.adjustSize()
    if ancho:
        ventana.resize(ancho, ventana.height())


# ══════════════════════════════════════════════════════════════════
#  ENCABEZADO DE MÓDULO
# ══════════════════════════════════════════════════════════════════

class EncabezadoModulo(QFrame):
    """Franja superior de color con el título del módulo y descripción."""

    def __init__(self, titulo: str, subtitulo: str = "", icono: str = "", parent=None):
        super().__init__(parent)
        fondo(self, COLOR_PRIMARIO)
        layout = QHBoxLayout(self)
        layout.setContentsMargins(24, 16, 24, 16)
        layout.setSpacing(12)

        if icono:
            lbl_icono = QLabel(icono)
            lbl_icono.setStyleSheet("background: transparent; color: white;")
            lbl_icono.setFont(fuente(20))
            layout.addWidget(lbl_icono)

        col = QVBoxLayout()
        col.setSpacing(2)
        lbl_titulo = QLabel(titulo)
        lbl_titulo.setStyleSheet("background: transparent; color: white;")
        lbl_titulo.setFont(fuente(15, negrita=True))
        col.addWidget(lbl_titulo)
        if subtitulo:
            lbl_sub = QLabel(subtitulo)
            lbl_sub.setStyleSheet("background: transparent; color: #F2D9B8;")
            lbl_sub.setFont(fuente(9))
            col.addWidget(lbl_sub)
        layout.addLayout(col)
        layout.addStretch()


# ══════════════════════════════════════════════════════════════════
#  TARJETA KPI
# ══════════════════════════════════════════════════════════════════

class TarjetaKPI(QFrame):
    """Tarjeta blanca con número grande y etiqueta.
    variante: "normal" | "alerta" | "exito" | "advertencia" """

    _COLOR_VALOR = {
        "normal": COLOR_PRIMARIO, "alerta": COLOR_ALERTA,
        "exito": COLOR_EXITO, "advertencia": COLOR_ADVERTENCIA,
    }

    def __init__(self, etiqueta: str, valor_inicial: str = "—",
                 variante: str = "normal", icono: str = "", parent=None):
        super().__init__(parent)
        color_valor = self._COLOR_VALOR.get(variante, COLOR_PRIMARIO)
        fondo(self, COLOR_TARJETA,
              f"border: 1px solid {_COLOR_SEPARADOR}; border-bottom: 3px solid {color_valor}; "
              f"border-radius: 6px;")
        layout = QVBoxLayout(self)
        layout.setContentsMargins(16, 14, 16, 12)

        fila_superior = QHBoxLayout()
        self._lbl_valor = QLabel(valor_inicial)
        self._lbl_valor.setStyleSheet(f"background: transparent; color: {color_valor};")
        self._lbl_valor.setFont(fuente(22, negrita=True))
        fila_superior.addWidget(self._lbl_valor)
        fila_superior.addStretch()
        if icono:
            lbl_icono = QLabel(icono)
            lbl_icono.setStyleSheet(f"background: transparent; color: {COLOR_TEXTO_SECUNDARIO};")
            lbl_icono.setFont(fuente(13))
            fila_superior.addWidget(lbl_icono)
        layout.addLayout(fila_superior)

        lbl_etiqueta = QLabel(etiqueta)
        lbl_etiqueta.setStyleSheet(f"background: transparent; color: {COLOR_TEXTO_SECUNDARIO};")
        lbl_etiqueta.setFont(fuente(9))
        lbl_etiqueta.setWordWrap(True)
        layout.addWidget(lbl_etiqueta)

    def actualizar(self, nuevo_valor: str):
        self._lbl_valor.setText(nuevo_valor)


# ══════════════════════════════════════════════════════════════════
#  BARRA DE BÚSQUEDA
# ══════════════════════════════════════════════════════════════════

class BarraBusqueda(QWidget):
    """Campo de búsqueda (con placeholder nativo de Qt) + botones."""

    textoCambiado = Signal(str)

    def __init__(self, al_escribir=None, placeholder="🔎  Buscar...", parent=None):
        super().__init__(parent)
        self._al_escribir = al_escribir
        layout = QHBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(8)

        self.entrada = QLineEdit()
        self.entrada.setPlaceholderText(placeholder)
        self.entrada.setFixedWidth(300)
        self.entrada.textChanged.connect(self._al_cambiar)
        layout.addWidget(self.entrada)

        self._botones_layout = QHBoxLayout()
        self._botones_layout.setSpacing(6)
        layout.addLayout(self._botones_layout)
        layout.addStretch()

    def _al_cambiar(self, texto):
        self.textoCambiado.emit(texto)
        if self._al_escribir:
            self._al_escribir(texto)

    def agregar_boton(self, texto: str, comando, estilo: str = "accion") -> QPushButton:
        boton = QPushButton(texto)
        poner_clase(boton, estilo)
        boton.clicked.connect(comando)
        self._botones_layout.addWidget(boton)
        return boton

    def limpiar(self):
        self.entrada.clear()


# ══════════════════════════════════════════════════════════════════
#  TABLA DE DATOS
# ══════════════════════════════════════════════════════════════════

_TAG_COLORES = {
    "exito":       ("#E8F5E2", "#2D6A22"),
    "alerta":      ("#FDECEA", "#8E2A1C"),
    "advertencia": ("#FFF8E1", "#7A5A00"),
    "normal":      (None, None),
    "par":         (None, None),
}


class TablaDatos(QTableWidget):
    """
    QTableWidget con filas alternas, tags de color por fila y filtro
    de texto. Misma API que la versión Tkinter para que sea sencillo
    trasladar la lógica de cada vista:
        tabla = TablaDatos(columnas, anchos={...})
        tabla.cargar_filas(filas, tags_por_fila=[...])
        tabla.filtrar(texto)
        tabla.id_seleccionado()
    """

    dobleClicFila = Signal(object)

    def __init__(self, columnas: list, con_id: bool = True,
                 al_doble_clic=None, anchos: dict = None, parent=None):
        super().__init__(parent)
        self._con_id = con_id
        self._al_doble_clic = al_doble_clic
        self._filas_actuales: list = []
        self._tags_actuales: list = []

        self.setColumnCount(len(columnas))
        self.setHorizontalHeaderLabels(columnas)
        self.setAlternatingRowColors(True)
        self.setSelectionBehavior(QAbstractItemView.SelectRows)
        self.setSelectionMode(QAbstractItemView.SingleSelection)
        self.setEditTriggers(QAbstractItemView.NoEditTriggers)
        self.verticalHeader().setVisible(False)
        self.setShowGrid(True)
        self.horizontalHeader().setStretchLastSection(True)

        for i, col in enumerate(columnas):
            ancho = (anchos or {}).get(col, 130)
            self.setColumnWidth(i, ancho)

        if al_doble_clic:
            self.cellDoubleClicked.connect(lambda r, c: al_doble_clic(self.id_seleccionado()))

    def empaquetar(self, **kwargs):
        """Compatibilidad con el nombre usado en la versión Tkinter:
        aquí no hace falta (el layout del padre ya agrega la tabla),
        pero se deja como no-operación para no romper el estilo de
        las vistas al portarlas."""
        return self

    def cargar_filas(self, filas: list, tags_por_fila: list = None):
        self._filas_actuales = filas
        self._tags_actuales = tags_por_fila or []
        self._repintar(filas, self._tags_actuales)

    # ── Resaltado de una fila concreta ────────────────────────────
    # A diferencia de filtrar(), esto NO esconde el resto de la tabla:
    # deja ver el contexto completo y solo lleva al usuario hasta la
    # fila exacta que estaba buscando (es lo que usan el buscador
    # global y las tarjetas "Requiere tu atención" del Dashboard).
    COLOR_RESALTADO = "#FFE8A3"
    COLOR_RESALTADO_TEXTO = "#5C4200"

    def resaltar(self, texto: str) -> bool:
        """Selecciona y hace scroll hasta la primera fila que contenga
        `texto`, dejando el resto de la tabla visible. Devuelve True si
        encontró la fila."""
        self.limpiar_resaltado()
        texto = (texto or "").lower().strip()
        if not texto:
            return False

        for fila in range(self.rowCount()):
            for col in range(self.columnCount()):
                item = self.item(fila, col)
                if item is not None and texto in item.text().lower():
                    self._pintar_resaltado(fila)
                    self.selectRow(fila)
                    self.setCurrentCell(fila, 0)
                    self.scrollToItem(self.item(fila, 0),
                                      QAbstractItemView.PositionAtCenter)
                    self.setFocus()
                    return True
        return False

    def _pintar_resaltado(self, fila: int):
        colores_originales = []
        for col in range(self.columnCount()):
            item = self.item(fila, col)
            if item is None:
                colores_originales.append(None)
                continue
            colores_originales.append((item.background(), item.foreground()))
            item.setBackground(QColor(self.COLOR_RESALTADO))
            item.setForeground(QColor(self.COLOR_RESALTADO_TEXTO))
        self._fila_resaltada = (fila, colores_originales)

    def limpiar_resaltado(self):
        datos = getattr(self, "_fila_resaltada", None)
        if not datos:
            return
        fila, colores_originales = datos
        if fila < self.rowCount():
            for col, original in enumerate(colores_originales):
                item = self.item(fila, col)
                if item is None or original is None:
                    continue
                item.setBackground(original[0])
                item.setForeground(original[1])
        self._fila_resaltada = None

    def _repintar(self, filas, tags_por_fila):
        # Repintar reconstruye los QTableWidgetItem, así que cualquier
        # resaltado anterior deja de existir: se olvida la referencia
        # para no intentar restaurar colores de items ya destruidos.
        self._fila_resaltada = None
        self.setRowCount(0)
        self.setRowCount(len(filas))
        for i, fila in enumerate(filas):
            valores = fila[1:] if self._con_id else fila
            tag = (tags_por_fila[i] if tags_por_fila and i < len(tags_por_fila)
                   else ("par" if i % 2 == 1 else "normal"))
            bg, fg = _TAG_COLORES.get(tag, (None, None))
            for c, valor in enumerate(valores):
                item = QTableWidgetItem(str(valor))
                if c == 0 and self._con_id:
                    item.setData(Qt.UserRole, fila[0])
                if bg:
                    item.setBackground(QColor(bg))
                    item.setForeground(QColor(fg))
                self.setItem(i, c, item)

    def filtrar(self, texto: str):
        texto = (texto or "").lower().strip()
        if not texto:
            self._repintar(self._filas_actuales, self._tags_actuales)
            return
        filtradas, tags_filtradas = [], []
        for i, fila in enumerate(self._filas_actuales):
            valores_visibles = fila[1:] if self._con_id else fila
            if any(texto in str(c).lower() for c in valores_visibles):
                filtradas.append(fila)
                tags_filtradas.append(
                    self._tags_actuales[i] if i < len(self._tags_actuales) else "normal")
        self._repintar(filtradas, tags_filtradas)

    def id_seleccionado(self):
        fila = self.currentRow()
        if fila < 0:
            return None
        item = self.item(fila, 0)
        if item is None:
            return None
        if self._con_id:
            valor = item.data(Qt.UserRole)
            try:
                return int(valor)
            except (TypeError, ValueError):
                return None
        try:
            return int(item.text())
        except ValueError:
            return None


# ══════════════════════════════════════════════════════════════════
#  ESTADO BADGE
# ══════════════════════════════════════════════════════════════════

_ESTADO_MAP = {
    "INICIADA":    ("🟡", "Iniciada",   "advertencia"),
    "EN_PROCESO":  ("🟠", "En proceso", "advertencia"),
    "COMPLETADA":  ("🟢", "Completada", "exito"),
    "CANCELADA":   ("🔴", "Cancelada",  "alerta"),
    "DISPONIBLE":  ("🟢", "Disponible", "exito"),
    "AGOTADO":     ("🔴", "Agotado",    "alerta"),
    "VENCIDO":     ("⚫", "Vencido",    "alerta"),
    "BAJO":        ("🟡", "Stock bajo", "advertencia"),
    "ACTIVO":      ("🟢", "Activo",     "exito"),
    "INACTIVO":    ("⚪", "Inactivo",   "normal"),
    "PENDIENTE":   ("🟡", "Pendiente",  "advertencia"),
    "REGISTRADA":  ("🟢", "Registrada", "exito"),
}


def formatear_estado(estado_interno: str) -> str:
    info = _ESTADO_MAP.get(str(estado_interno).upper())
    if info:
        return f"{info[0]} {info[1]}"
    return estado_interno


# ══════════════════════════════════════════════════════════════════
#  BOTÓN DE AYUDA CONTEXTUAL
# ══════════════════════════════════════════════════════════════════

class BotonAyuda(QPushButton):
    """Botón circular de ayuda contextual.

    Usa el carácter ASCII "?" y NO el emoji "❓" a propósito: cuando el
    sistema no tiene instalada una fuente con emojis en color (algo
    habitual en Windows con fuentes recortadas y en muchos Linux), Qt
    dibuja el glifo faltante como un recuadro vacío — que sobre el
    fondo crema de los botones secundarios se veía como "una cuadrícula
    amarilla sin ícono". Un "?" normal se ve siempre igual en todos
    lados.
    """

    def __init__(self, titulo: str, texto: str, parent=None, tooltip: str = ""):
        super().__init__("?", parent)
        self._titulo = titulo
        self._texto = texto
        self.setFixedSize(26, 26)
        self.setCursor(Qt.PointingHandCursor)
        self.setToolTip(tooltip or f"¿Qué es esto? — {titulo}")
        self.setFont(fuente(10, negrita=True))
        # Estilo propio (no depende de la clase "secundario") para
        # garantizar contraste entre el "?" y el fondo del botón.
        self.setStyleSheet(
            f"QPushButton {{ background-color: {COLOR_PRIMARIO}; color: white; "
            f"border: none; border-radius: 13px; padding: 0px; font-weight: bold; }}"
            f"QPushButton:hover {{ background-color: {COLOR_TEXTO}; color: white; }}"
        )
        self.clicked.connect(self._mostrar)

    def _mostrar(self):
        from PySide6.QtWidgets import QMessageBox
        QMessageBox.information(self.window(), self._titulo, self._texto)


# ══════════════════════════════════════════════════════════════════
#  CAMPO DE FORMULARIO CON VALIDACIÓN INLINE
# ══════════════════════════════════════════════════════════════════

class CampoFormulario(QWidget):
    """Label + Entry/Combobox con mensaje de error inline."""

    def __init__(self, etiqueta: str, obligatorio: bool = False,
                 tipo: str = "entry", opciones: list = None,
                 readonly: bool = False, parent=None):
        super().__init__(parent)
        self._obligatorio = obligatorio
        self._tipo = tipo

        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(2)

        texto_label = f"{etiqueta} *" if obligatorio else etiqueta
        lbl = QLabel(texto_label)
        lbl.setFont(fuente(9, negrita=True))
        layout.addWidget(lbl)

        if tipo == "combobox":
            self.widget = QComboBox()
            self.widget.addItems(opciones or [])
            self.widget.setEditable(not readonly)
        else:
            self.widget = QLineEdit()
            self.widget.setReadOnly(readonly)
        layout.addWidget(self.widget)

        self._lbl_error = QLabel("")
        self._lbl_error.setStyleSheet(f"color: {COLOR_ALERTA};")
        self._lbl_error.setFont(fuente(8))
        layout.addWidget(self._lbl_error)

        if readonly:
            lbl_auto = QLabel("Autocompletado automáticamente")
            lbl_auto.setStyleSheet(f"color: {COLOR_TEXTO_SECUNDARIO};")
            lbl_auto.setFont(fuente(8, cursiva=True))
            layout.addWidget(lbl_auto)

    def get(self) -> str:
        if self._tipo == "combobox":
            return self.widget.currentText().strip()
        return self.widget.text().strip()

    def set(self, valor: str):
        if self._tipo == "combobox":
            self.widget.setCurrentText(str(valor))
        else:
            self.widget.setText(str(valor))

    def mostrar_error(self, mensaje: str):
        self._lbl_error.setText(f"❌ {mensaje}")

    def limpiar_error(self):
        self._lbl_error.setText("")

    def validar(self) -> bool:
        if self._obligatorio and not self.get():
            self.mostrar_error("Este campo es obligatorio")
            return False
        self.limpiar_error()
        return True


# ══════════════════════════════════════════════════════════════════
#  SECCIÓN DE FORMULARIO
# ══════════════════════════════════════════════════════════════════

class SeccionFormulario(QGroupBox):
    """QGroupBox con estilo mejorado para agrupar campos del formulario."""

    def __init__(self, titulo: str, parent=None):
        super().__init__(titulo, parent)


# ══════════════════════════════════════════════════════════════════
#  PANEL TITULADO (alternativa a QGroupBox para contenedores dentro
#  de QScrollArea: en ciertos anidamientos, el título/borde nativo de
#  QGroupBox no se pinta bien ahí — este panel usa un QLabel propio
#  arriba y un QFrame con borde escopado, sin depender de esas
#  métricas internas)
# ══════════════════════════════════════════════════════════════════

class PanelTitulado(QFrame):
    def __init__(self, titulo: str, parent=None):
        super().__init__(parent)
        outer = QVBoxLayout(self)
        outer.setContentsMargins(0, 0, 0, 0)
        outer.setSpacing(4)

        lbl = QLabel(titulo)
        lbl.setFont(fuente(10, negrita=True))
        lbl.setStyleSheet(f"color: {COLOR_PRIMARIO}; background: transparent;")
        outer.addWidget(lbl)

        caja = QFrame()
        estilo_escopado(caja, f"border: 1px solid {_COLOR_SEPARADOR}; border-radius: 6px; "
                               f"background-color: {COLOR_TARJETA};")
        self.layout_interior = QVBoxLayout(caja)
        self.layout_interior.setContentsMargins(14, 12, 14, 12)
        outer.addWidget(caja)


# ══════════════════════════════════════════════════════════════════
#  MENSAJE DE ESTADO (BANDA)
# ══════════════════════════════════════════════════════════════════

class MensajeEstado(QWidget):
    """Banda de mensaje temporal. tipo: "exito" | "error" | "advertencia" """

    def __init__(self, parent=None):
        super().__init__(parent)
        self._layout = QVBoxLayout(self)
        self._layout.setContentsMargins(0, 0, 0, 0)
        self._frame = None
        self._timer = None

    def mostrar(self, texto: str, tipo: str = "exito", duracion_ms: int = 4000):
        if self._frame:
            self._frame.deleteLater()
            self._frame = None
        if self._timer:
            self._timer.stop()

        cfg = {
            "exito": ("#D4EDDA", "#155724", "✓"),
            "error": ("#FDECEA", "#7B1111", "✗"),
            "advertencia": ("#FFF3CD", "#856404", "⚠"),
            "info": ("#D1ECF1", "#0C5460", "ℹ"),
        }.get(tipo, ("#D4EDDA", "#155724", "✓"))

        frame = QFrame()
        fondo(frame, cfg[0], "border-radius: 4px;")
        flayout = QHBoxLayout(frame)
        flayout.setContentsMargins(12, 8, 12, 8)
        lbl = QLabel(f"{cfg[2]}  {texto}")
        lbl.setStyleSheet(f"background: transparent; color: {cfg[1]};")
        lbl.setFont(fuente(9))
        flayout.addWidget(lbl)
        flayout.addStretch()
        self._layout.addWidget(frame)
        self._frame = frame

        if duracion_ms > 0:
            self._timer = QTimer(self)
            self._timer.setSingleShot(True)
            self._timer.timeout.connect(self._ocultar)
            self._timer.start(duracion_ms)

    def _ocultar(self):
        if self._frame:
            self._frame.deleteLater()
            self._frame = None


# ══════════════════════════════════════════════════════════════════
#  DIÁLOGO DE CONFIRMACIÓN
# ══════════════════════════════════════════════════════════════════

class DialogoConfirmacion(QDialog):
    """Diálogo modal de confirmación. `.resultado` es True/False."""

    def __init__(self, parent, titulo: str, mensaje: str,
                 texto_confirmar: str = "Confirmar",
                 texto_cancelar: str = "Cancelar",
                 peligro: bool = False):
        super().__init__(parent)
        self.setWindowTitle(titulo)
        self.setFixedSize(400, 200)
        self.resultado = False

        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(0)

        color_franja = COLOR_ALERTA if peligro else COLOR_PRIMARIO
        franja = QFrame()
        fondo(franja, color_franja)
        flayout = QHBoxLayout(franja)
        flayout.setContentsMargins(20, 12, 20, 12)
        icono = "⚠" if peligro else "?"
        lbl_titulo = QLabel(f"{icono}  {titulo}")
        lbl_titulo.setStyleSheet("background: transparent; color: white;")
        lbl_titulo.setFont(fuente(13, negrita=True))
        flayout.addWidget(lbl_titulo)
        layout.addWidget(franja)

        cuerpo = QWidget()
        clayout = QVBoxLayout(cuerpo)
        clayout.setContentsMargins(20, 16, 20, 16)
        lbl_msg = QLabel(mensaje)
        lbl_msg.setWordWrap(True)
        lbl_msg.setFont(fuente(10))
        clayout.addWidget(lbl_msg)
        clayout.addStretch()

        fila_botones = QHBoxLayout()
        fila_botones.addStretch()
        btn_cancelar = QPushButton(texto_cancelar)
        poner_clase(btn_cancelar, "secundario")
        btn_cancelar.clicked.connect(self._cancelar)
        fila_botones.addWidget(btn_cancelar)
        btn_confirmar = QPushButton(texto_confirmar)
        if peligro:
            poner_clase(btn_confirmar, "peligro")
        btn_confirmar.clicked.connect(self._confirmar)
        fila_botones.addWidget(btn_confirmar)
        clayout.addLayout(fila_botones)
        layout.addWidget(cuerpo)

        centrar_ventana(self, 400, 200)

    def keyPressEvent(self, evento):
        if evento.key() == Qt.Key_Escape:
            self._cancelar()
        else:
            super().keyPressEvent(evento)

    def _confirmar(self):
        self.resultado = True
        self.accept()

    def _cancelar(self):
        self.resultado = False
        self.reject()


def confirmar(parent, titulo: str, mensaje: str,
              texto_confirmar: str = "Confirmar",
              texto_cancelar: str = "Cancelar",
              peligro: bool = False) -> bool:
    dlg = DialogoConfirmacion(parent, titulo, mensaje, texto_confirmar, texto_cancelar, peligro)
    dlg.exec()
    return dlg.resultado


# ══════════════════════════════════════════════════════════════════
#  BARRA DE ESTADO INFERIOR
# ══════════════════════════════════════════════════════════════════

class Migaja(QWidget):
    """Breadcrumb: 'Inventario › Productos › Anka Chida'. El último
    elemento se muestra resaltado para indicar la ubicación actual."""

    def __init__(self, partes: list = None, parent=None):
        super().__init__(parent)
        self._layout = QHBoxLayout(self)
        self._layout.setContentsMargins(0, 0, 0, 0)
        self._layout.setSpacing(4)
        self.establecer(partes or [])

    def establecer(self, partes: list):
        while self._layout.count():
            item = self._layout.takeAt(0)
            w = item.widget()
            if w is not None:
                w.deleteLater()
        for i, parte in enumerate(partes):
            es_ultimo = (i == len(partes) - 1)
            if i > 0:
                sep = QLabel("›")
                sep.setStyleSheet(f"background: transparent; color: {COLOR_TEXTO_SECUNDARIO};")
                sep.setFont(fuente(9))
                self._layout.addWidget(sep)
            lbl = QLabel(str(parte))
            color = COLOR_TEXTO if es_ultimo else COLOR_TEXTO_SECUNDARIO
            lbl.setFont(fuente(9, negrita=es_ultimo))
            lbl.setStyleSheet(f"background: transparent; color: {color};")
            self._layout.addWidget(lbl)
        self._layout.addStretch()


# ══════════════════════════════════════════════════════════════════
#  ESTADO VACÍO
# ══════════════════════════════════════════════════════════════════

class EstadoVacio(QWidget):
    """Mensaje para listas/tablas sin datos: siempre indica qué puede
    hacer el usuario a continuación, nunca solo 'No hay datos.'"""

    def __init__(self, icono: str, titulo: str, descripcion: str = "",
                 texto_accion: str = "", accion=None, parent=None):
        super().__init__(parent)
        layout = QVBoxLayout(self)
        layout.setAlignment(Qt.AlignCenter)
        layout.setSpacing(6)
        layout.setContentsMargins(20, 30, 20, 30)

        lbl_icono = QLabel(icono)
        lbl_icono.setFont(fuente(30))
        lbl_icono.setAlignment(Qt.AlignCenter)
        lbl_icono.setStyleSheet("background: transparent;")
        layout.addWidget(lbl_icono)

        lbl_titulo = QLabel(titulo)
        lbl_titulo.setFont(fuente(11, negrita=True))
        lbl_titulo.setAlignment(Qt.AlignCenter)
        lbl_titulo.setStyleSheet(f"background: transparent; color: {COLOR_TEXTO};")
        layout.addWidget(lbl_titulo)

        if descripcion:
            lbl_desc = QLabel(descripcion)
            lbl_desc.setFont(fuente(9))
            lbl_desc.setAlignment(Qt.AlignCenter)
            lbl_desc.setWordWrap(True)
            lbl_desc.setMaximumWidth(360)
            lbl_desc.setStyleSheet(f"background: transparent; color: {COLOR_TEXTO_SECUNDARIO};")
            layout.addWidget(lbl_desc, alignment=Qt.AlignCenter)

        if texto_accion and accion:
            fila = QHBoxLayout()
            fila.addStretch()
            btn = QPushButton(texto_accion)
            btn.clicked.connect(accion)
            fila.addWidget(btn)
            fila.addStretch()
            layout.addLayout(fila)


# ══════════════════════════════════════════════════════════════════
#  TARJETA DE ACCIÓN (alertas accionables del Dashboard)
# ══════════════════════════════════════════════════════════════════

class TarjetaAccion(QFrame):
    """Tarjeta clickeable para la sección 'Requiere tu atención' del
    Dashboard: ícono + color según severidad, texto y un botón que
    lleva directo al módulo donde se resuelve el problema.
    severidad: "critico" | "riesgo" | "atencion" | "info" """

    clicked = Signal()

    _COLOR = {"critico": COLOR_ALERTA, "riesgo": "#E07B00",
              "atencion": COLOR_ADVERTENCIA, "info": "#2B6CB0"}
    _ICONO = {"critico": "🔴", "riesgo": "🟠", "atencion": "🟡", "info": "🔵"}

    def __init__(self, titulo: str, descripcion: str, severidad: str = "atencion",
                 texto_boton: str = "Revisar", al_clic=None, parent=None):
        super().__init__(parent)
        color = self._COLOR.get(severidad, COLOR_ADVERTENCIA)
        icono = self._ICONO.get(severidad, "🟡")
        fondo(self, COLOR_TARJETA,
              f"border: 1px solid {_COLOR_SEPARADOR}; border-left: 4px solid {color}; "
              f"border-radius: 6px;")
        self.setCursor(Qt.PointingHandCursor)

        layout = QHBoxLayout(self)
        layout.setContentsMargins(14, 10, 14, 10)
        layout.setSpacing(10)

        lbl_icono = QLabel(icono)
        lbl_icono.setFont(fuente(14))
        lbl_icono.setStyleSheet("background: transparent;")
        layout.addWidget(lbl_icono, alignment=Qt.AlignTop)

        col = QVBoxLayout()
        col.setSpacing(1)
        lbl_t = QLabel(titulo)
        lbl_t.setFont(fuente(10, negrita=True))
        lbl_t.setWordWrap(True)
        lbl_t.setStyleSheet(f"background: transparent; color: {COLOR_TEXTO};")
        col.addWidget(lbl_t)
        lbl_d = QLabel(descripcion)
        lbl_d.setFont(fuente(9))
        lbl_d.setWordWrap(True)
        lbl_d.setStyleSheet(f"background: transparent; color: {COLOR_TEXTO_SECUNDARIO};")
        col.addWidget(lbl_d)
        layout.addLayout(col, stretch=1)

        btn = QPushButton(texto_boton)
        poner_clase(btn, "accionSecundaria")
        btn.clicked.connect(self._disparar)
        layout.addWidget(btn, alignment=Qt.AlignVCenter)

        self._al_clic = al_clic

    def mousePressEvent(self, evento):
        if evento.button() == Qt.LeftButton:
            self._disparar()
        super().mousePressEvent(evento)

    def _disparar(self):
        self.clicked.emit()
        if self._al_clic:
            self._al_clic()


# ══════════════════════════════════════════════════════════════════
#  INDICADOR DE CARGA (feedback durante operaciones que demoran)
# ══════════════════════════════════════════════════════════════════

class IndicadorCarga(QWidget):
    """Overlay de carga (sección 20): cubre a su widget padre mientras
    dura una operación que puede demorar — cambio de pantalla/pestaña,
    cálculo de IA, generación de reportes — para que la ventana nunca
    se vea congelada. Normalmente no se usa directamente: ver
    ejecutar_con_carga() más abajo."""

    def __init__(self, parent: QWidget):
        super().__init__(parent)
        self.setAttribute(Qt.WA_StyledBackground, True)
        self.setStyleSheet("background-color: rgba(250, 248, 240, 0.94);")

        layout = QVBoxLayout(self)
        layout.setAlignment(Qt.AlignCenter)
        layout.setSpacing(10)

        self._lbl_icono = QLabel("⏳")
        self._lbl_icono.setFont(fuente(24))
        self._lbl_icono.setAlignment(Qt.AlignCenter)
        self._lbl_icono.setStyleSheet("background: transparent;")
        layout.addWidget(self._lbl_icono)

        self._lbl_mensaje = QLabel("Cargando...")
        self._lbl_mensaje.setFont(fuente(10, negrita=True))
        self._lbl_mensaje.setAlignment(Qt.AlignCenter)
        self._lbl_mensaje.setStyleSheet(f"background: transparent; color: {COLOR_TEXTO};")
        layout.addWidget(self._lbl_mensaje)

        self._lbl_submensaje = QLabel("")
        self._lbl_submensaje.setFont(fuente(9))
        self._lbl_submensaje.setAlignment(Qt.AlignCenter)
        self._lbl_submensaje.setWordWrap(True)
        self._lbl_submensaje.setMaximumWidth(320)
        self._lbl_submensaje.setStyleSheet(f"background: transparent; color: {COLOR_TEXTO_SECUNDARIO};")
        layout.addWidget(self._lbl_submensaje, alignment=Qt.AlignCenter)

        self._barra = QProgressBar()
        self._barra.setRange(0, 0)  # indeterminado: no conocemos el avance real
        self._barra.setFixedWidth(220)
        self._barra.setTextVisible(False)
        layout.addWidget(self._barra, alignment=Qt.AlignCenter)

        self.hide()

    def establecer_texto(self, mensaje: str, submensaje: str = "", icono: str = "⏳"):
        self._lbl_icono.setText(icono)
        self._lbl_mensaje.setText(mensaje)
        self._lbl_submensaje.setText(submensaje)
        self._lbl_submensaje.setVisible(bool(submensaje))

    def mostrar(self):
        padre = self.parentWidget()
        if padre is not None:
            self.setGeometry(padre.rect())
        self.raise_()
        self.show()
        # Fuerza el repintado inmediato: sin esto, el overlay no se
        # vería hasta que Qt procese eventos por su cuenta, es decir,
        # después de que termine la operación que estamos anunciando.
        QApplication.processEvents()

    def ocultar(self):
        self.hide()

    def showEvent(self, evento):
        padre = self.parentWidget()
        if padre is not None:
            self.setGeometry(padre.rect())
        super().showEvent(evento)


def ejecutar_con_carga(contenedor: QWidget, funcion, mensaje: str = "Cargando...",
                        submensaje: str = "", icono: str = "⏳"):
    """Ejecuta `funcion` (sin argumentos) mostrando un overlay de carga
    sobre `contenedor` mientras dura, para que ningún cambio de
    pantalla/pestaña ni cálculo de IA deje la ventana con aspecto de
    congelada (sección 20). Reutiliza un único overlay por contenedor.
    Devuelve lo que retorne `funcion`; si lanza una excepción, el
    overlay igual se oculta antes de relanzarla, para que el llamador
    la maneje como siempre."""
    overlay = getattr(contenedor, "_indicador_carga", None)
    if overlay is None or overlay.parentWidget() is not contenedor:
        overlay = IndicadorCarga(contenedor)
        contenedor._indicador_carga = overlay
    overlay.establecer_texto(mensaje, submensaje, icono)
    overlay.mostrar()
    try:
        return funcion()
    finally:
        overlay.ocultar()


class _TareaEnHilo(QThread):
    """Ejecuta una función pesada fuera del hilo de la interfaz."""

    finalizado = Signal(object, object)   # (resultado, excepción)

    def __init__(self, funcion, parent=None):
        super().__init__(parent)
        self._funcion = funcion

    def run(self):
        try:
            self.finalizado.emit(self._funcion(), None)
        except Exception as error:      # noqa: BLE001 — se reenvía al llamador
            self.finalizado.emit(None, error)


def ejecutar_en_hilo(contenedor: QWidget, funcion, al_terminar,
                     mensaje: str = "Cargando...", submensaje: str = "",
                     icono: str = "⏳"):
    """Igual que `ejecutar_con_carga`, pero SIN congelar la ventana.

    `funcion` corre en un hilo aparte mientras el overlay se anima de
    verdad; cuando termina se llama a `al_terminar(resultado, error)`
    ya de vuelta en el hilo de la interfaz (Qt entrega la señal ahí),
    así que ese callback puede tocar widgets con total seguridad.

    Es lo que usan los cálculos de IA del Centro de Inteligencia: antes
    se ejecutaban de forma síncrona y la ventana quedaba bloqueada unos
    5 segundos cada vez que se entraba al módulo.

    Importante: `funcion` NO debe tocar widgets — solo calcular y
    devolver datos. Las consultas a SQLite son seguras porque el engine
    se crea con `check_same_thread=False` (ver app/basedatos.py) y cada
    llamada abre su propia sesión.
    """
    overlay = getattr(contenedor, "_indicador_carga", None)
    if overlay is None or overlay.parentWidget() is not contenedor:
        overlay = IndicadorCarga(contenedor)
        contenedor._indicador_carga = overlay
    overlay.establecer_texto(mensaje, submensaje, icono)
    overlay.mostrar()

    tarea = _TareaEnHilo(funcion, contenedor)

    def _al_finalizar(resultado, error):
        overlay.ocultar()
        # Se suelta la referencia para que el QThread pueda recolectarse.
        if getattr(contenedor, "_tarea_en_curso", None) is tarea:
            contenedor._tarea_en_curso = None
        al_terminar(resultado, error)

    tarea.finalizado.connect(_al_finalizar)
    # Sin guardar la referencia, Python podría recolectar el QThread
    # mientras sigue corriendo y la app se caería.
    contenedor._tarea_en_curso = tarea
    tarea.start()
    return tarea


class BarraEstado(QFrame):
    """Barra inferior con información del sistema."""

    def __init__(self, usuario: str = "", rol: str = "", parent=None):
        super().__init__(parent)
        fondo(self, COLOR_SIDEBAR)
        self.setFixedHeight(28)
        layout = QHBoxLayout(self)
        layout.setContentsMargins(12, 3, 12, 3)

        lbl_usuario = QLabel(f"Usuario: {usuario}  |  Rol: {rol}")
        lbl_usuario.setStyleSheet("background: transparent; color: #B9C7A9;")
        lbl_usuario.setFont(fuente(8))
        layout.addWidget(lbl_usuario)
        layout.addStretch()

        lbl_db = QLabel("✓ Base de datos conectada")
        lbl_db.setStyleSheet("background: transparent; color: #5FDD73;")
        lbl_db.setFont(fuente(8))
        layout.addWidget(lbl_db)
