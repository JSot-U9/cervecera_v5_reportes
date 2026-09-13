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

from PySide6.QtCore import Qt, QTimer, Signal
from PySide6.QtGui import QScreen
from PySide6.QtWidgets import (
    QWidget, QLabel, QFrame, QVBoxLayout, QHBoxLayout, QPushButton,
    QLineEdit, QComboBox, QTableWidget, QTableWidgetItem, QHeaderView,
    QAbstractItemView, QGroupBox, QDialog, QApplication, QGraphicsDropShadowEffect,
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

    def _repintar(self, filas, tags_por_fila):
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
