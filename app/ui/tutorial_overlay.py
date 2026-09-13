"""tutorial_overlay.py (PySide6)
=================================
Motor visual del tutorial interactivo — con transparencia REAL, algo
que no era posible de forma confiable en la versión Tkinter.

Cómo funciona (y por qué aquí sí es seguro, a diferencia de Tkinter):
  El velo oscuro y la tarjeta son widgets HIJOS de la propia ventana
  principal (no ventanas nuevas), con un fondo `rgba(...)` semi-
  transparente. Qt compone sus propios widgets con su motor de
  render (QPainter) al dibujar la ventana — la mezcla de colores no
  depende de que el sistema operativo tenga un "compositor" activo,
  como sí pasaba con `-alpha` en Tkinter. Por eso nunca se pinta
  negro sólido por accidente.

  El "hueco" que deja ver el control resaltado se logra con
  `QWidget.setMask()`: se le quita al velo la región exacta del
  hueco, así que ahí simplemente no pinta nada — se ve el control
  real de la ventana, tal cual es.

  La tarjeta explicativa se RECREA por completo en cada paso (en vez
  de limpiar y rellenar la misma) — igual que hacía la versión
  Tkinter con su ventana Toplevel. Reciclar el mismo widget
  translúcido cambiando su contenido podía dejar restos de texto del
  paso anterior en pantalla; crear uno nuevo cada vez lo evita del
  todo y es más simple.
"""

from PySide6.QtCore import Qt, QObject, QEvent, QRect, QTimer
from PySide6.QtGui import QPainter, QColor, QPen, QRegion
from PySide6.QtWidgets import QWidget, QLabel, QPushButton, QVBoxLayout, QHBoxLayout

from app.ui.estilos import COLOR_PRIMARIO, COLOR_PRIMARIO_CLARO, poner_clase, fuente

_COLOR_VELO = QColor(22, 36, 13, 150)           # verde oscuro translúcido (~59% opaco)
_COLOR_TARJETA_RGBA = "rgba(34, 51, 28, 235)"    # tarjeta oscura, ligeramente translúcida
_GROSOR_MARCO = 6                                 # la mitad queda visible fuera del hueco
_PADDING_HUECO = 6
_ANCHO_TARJETA = 360


class _Velo(QWidget):
    """El widget que oscurece la ventana, con un hueco real (no
    pintado, no clicable) alrededor del control resaltado."""

    def __init__(self, parent):
        super().__init__(parent)
        self.setAttribute(Qt.WA_TranslucentBackground)
        self._hueco = None

    def set_hueco(self, rect: QRect | None):
        self._hueco = rect
        if rect is not None and not rect.isEmpty():
            region = QRegion(self.rect()).subtracted(QRegion(rect))
            self.setMask(region)
        else:
            self.clearMask()
        self.update()

    def paintEvent(self, _evento):
        pintor = QPainter(self)
        pintor.setRenderHint(QPainter.Antialiasing)
        pintor.fillRect(self.rect(), _COLOR_VELO)
        if self._hueco is not None and not self._hueco.isEmpty():
            pluma = QPen(QColor(COLOR_PRIMARIO))
            pluma.setWidth(_GROSOR_MARCO)
            pintor.setPen(pluma)
            pintor.setBrush(Qt.NoBrush)
            pintor.drawRect(self._hueco)


class _Tarjeta(QWidget):
    """Tarjeta explicativa: fondo oscuro semi-transparente, texto
    claro, botones de navegación. Se construye completa en el
    constructor — para un paso nuevo se crea una tarjeta nueva."""

    def __init__(self, parent, *, icono, titulo, texto, indice, total,
                 on_anterior, on_siguiente, on_saltar,
                 mostrar_anterior, es_ultimo, texto_siguiente=None,
                 mostrar_siguiente=True, texto_saltar="Saltar tutorial ✕"):
        super().__init__(parent)
        self.setAttribute(Qt.WA_TranslucentBackground)
        self.setFixedWidth(_ANCHO_TARJETA)
        self.setStyleSheet(
            f"_Tarjeta {{ background-color: {_COLOR_TARJETA_RGBA}; "
            f"border: 2px solid {COLOR_PRIMARIO}; border-radius: 8px; }}"
        )
        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(0)

        franja = QWidget()
        franja.setStyleSheet(f"background-color: {COLOR_PRIMARIO}; border-radius: 6px;")
        fl = QVBoxLayout(franja)
        fl.setContentsMargins(16, 10, 16, 10)
        fila = QHBoxLayout()
        if icono:
            lbl_icono = QLabel(icono)
            lbl_icono.setStyleSheet("background: transparent; color: white;")
            lbl_icono.setFont(fuente(16))
            fila.addWidget(lbl_icono)
        col = QVBoxLayout()
        lbl_titulo = QLabel(titulo)
        lbl_titulo.setStyleSheet("background: transparent; color: white;")
        lbl_titulo.setFont(fuente(12, negrita=True))
        lbl_titulo.setWordWrap(True)
        col.addWidget(lbl_titulo)
        if total:
            lbl_paso = QLabel(f"Paso {indice + 1} de {total}")
            lbl_paso.setStyleSheet(f"background: transparent; color: {COLOR_PRIMARIO_CLARO};")
            lbl_paso.setFont(fuente(8))
            col.addWidget(lbl_paso)
        fila.addLayout(col)
        fila.addStretch()
        fl.addLayout(fila)
        layout.addWidget(franja)

        cuerpo = QWidget()
        cuerpo.setStyleSheet(f"background-color: {_COLOR_TARJETA_RGBA};")
        cl = QVBoxLayout(cuerpo)
        cl.setContentsMargins(16, 12, 16, 12)
        lbl_texto = QLabel(texto)
        lbl_texto.setStyleSheet("background: transparent; color: #EDE7D3;")
        lbl_texto.setFont(fuente(10))
        lbl_texto.setWordWrap(True)
        cl.addWidget(lbl_texto)
        layout.addWidget(cuerpo)

        barra = QWidget()
        barra.setStyleSheet(f"background-color: {_COLOR_TARJETA_RGBA};")
        bl = QHBoxLayout(barra)
        bl.setContentsMargins(16, 0, 16, 14)
        btn_saltar = QPushButton(texto_saltar)
        poner_clase(btn_saltar, "secundario")
        btn_saltar.clicked.connect(on_saltar)
        bl.addWidget(btn_saltar)
        bl.addStretch()
        if mostrar_anterior:
            btn_anterior = QPushButton("◀  Anterior")
            poner_clase(btn_anterior, "secundario")
            btn_anterior.clicked.connect(on_anterior)
            bl.addWidget(btn_anterior)
        if mostrar_siguiente:
            btn_siguiente = QPushButton(texto_siguiente or ("Finalizar  ✓" if es_ultimo else "Siguiente  ▶"))
            btn_siguiente.clicked.connect(on_siguiente)
            bl.addWidget(btn_siguiente)
        layout.addWidget(barra)

        layout.activate()
        self.adjustSize()


class OverlayTutorial(QObject):
    """
    Coordina el velo + la tarjeta sobre `root` (la ventana principal).
    """

    def __init__(self, root: QWidget):
        super().__init__(root)
        self.root = root
        self._host: QWidget = root
        self._velo: _Velo | None = None
        self._tarjeta: _Tarjeta | None = None
        self._widget_actual = None
        self._on_saltar_actual = None
        self._cerrado = False
        root.installEventFilter(self)

    # ── Geometría ────────────────────────────────────────────────
    def _ventana_de(self, widget: QWidget) -> QWidget:
        """Ventana de nivel superior que realmente contiene `widget`
        (la principal, o un diálogo real abierto por este paso)."""
        if widget is None:
            return self.root
        try:
            return widget.window()
        except RuntimeError:
            return self.root

    def _hueco_de(self, widget: QWidget, host: QWidget) -> QRect | None:
        if widget is None:
            return None
        try:
            if not widget.isVisible():
                return None
            top_izq = widget.mapTo(host, widget.rect().topLeft())
            rect = QRect(top_izq, widget.size())
            return rect.adjusted(-_PADDING_HUECO, -_PADDING_HUECO, _PADDING_HUECO, _PADDING_HUECO)
        except RuntimeError:
            return None

    def _posicionar_tarjeta(self, hueco: QRect | None):
        if self._tarjeta is None:
            return
        ancho = _ANCHO_TARJETA
        alto = max(self._tarjeta.sizeHint().height(), 90)
        rw, rh = self._host.width(), self._host.height()
        margen = 14

        if hueco is not None:
            candidatos = [
                (hueco.left(), hueco.bottom() + margen),
                (hueco.left(), hueco.top() - alto - margen),
                (hueco.right() + margen, hueco.top()),
                (hueco.left() - ancho - margen, hueco.top()),
            ]
            x, y = candidatos[0]
            for cx, cy in candidatos:
                if 0 <= cx and cx + ancho <= rw and 0 <= cy and cy + alto <= rh:
                    x, y = cx, cy
                    break
            x = max(4, min(x, rw - ancho - 4))
            y = max(4, min(y, rh - alto - 4))
        else:
            x = (rw - ancho) // 2
            y = (rh - alto) // 2

        self._tarjeta.setGeometry(int(x), int(y), ancho, alto)
        self._tarjeta.raise_()

    # ── API pública ──────────────────────────────────────────────
    def mostrar_paso(self, widget, *, icono="💡", titulo="", texto="",
                      indice=0, total=0, on_anterior=None, on_siguiente=None,
                      on_saltar=None, mostrar_anterior=True, es_ultimo=False,
                      texto_siguiente=None, mostrar_siguiente=True,
                      texto_saltar="Saltar tutorial ✕"):
        if self._cerrado:
            return
        self._widget_actual = widget

        nuevo_host = self._ventana_de(widget)
        if nuevo_host is not self._host:
            try:
                self._host.removeEventFilter(self)
            except RuntimeError:
                pass
            self._host = nuevo_host
            self._host.installEventFilter(self)
        self._on_saltar_actual = on_saltar

        velo_anterior = self._velo
        self._velo = _Velo(self._host)
        self._velo.setGeometry(0, 0, self._host.width(), self._host.height())
        hueco = self._hueco_de(widget, self._host)
        self._velo.set_hueco(hueco)
        self._velo.show()
        self._velo.raise_()
        if velo_anterior is not None:
            velo_anterior.hide()
            velo_anterior.deleteLater()

        tarjeta_anterior = self._tarjeta
        self._tarjeta = _Tarjeta(
            self._host, icono=icono, titulo=titulo, texto=texto, indice=indice, total=total,
            on_anterior=on_anterior or (lambda: None),
            on_siguiente=on_siguiente or (lambda: None),
            on_saltar=on_saltar or (lambda: None),
            mostrar_anterior=mostrar_anterior, es_ultimo=es_ultimo,
            texto_siguiente=texto_siguiente, mostrar_siguiente=mostrar_siguiente,
            texto_saltar=texto_saltar,
        )
        self._posicionar_tarjeta(hueco)
        self._tarjeta.show()
        self._tarjeta.raise_()

        if tarjeta_anterior is not None:
            tarjeta_anterior.hide()
            tarjeta_anterior.deleteLater()

        # El tamaño exacto (con el texto ya ajustado a este ancho) a
        # veces solo se conoce con certeza tras un ciclo del event
        # loop — se corrige la posición una vez más por seguridad.
        QTimer.singleShot(0, lambda: self._posicionar_tarjeta(hueco) if not self._cerrado else None)

    def eventFilter(self, obj, evento):
        if obj is self._host and evento.type() in (QEvent.Resize, QEvent.Move):
            QTimer.singleShot(0, self._reposicionar_todo)
        elif obj is self._host and evento.type() == QEvent.KeyPress:
            if evento.key() == Qt.Key_Escape and self._on_saltar_actual and not self._cerrado:
                self._on_saltar_actual()
                return True
        return False

    def _reposicionar_todo(self):
        if self._cerrado or self._velo is None or not self._velo.isVisible():
            return
        self._velo.setGeometry(0, 0, self._host.width(), self._host.height())
        hueco = self._hueco_de(self._widget_actual, self._host)
        self._velo.set_hueco(hueco)
        self._posicionar_tarjeta(hueco)

    def cerrar(self):
        if self._cerrado:
            return
        self._cerrado = True
        try:
            self._host.removeEventFilter(self)
        except RuntimeError:
            pass
        if self._velo is not None:
            try:
                self._velo.hide()
                self._velo.deleteLater()
            except RuntimeError:
                pass
            self._velo = None
        if self._tarjeta is not None:
            try:
                self._tarjeta.hide()
                self._tarjeta.deleteLater()
            except RuntimeError:
                pass
            self._tarjeta = None
