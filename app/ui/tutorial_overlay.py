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

from app.ui.estilos import COLOR_PRIMARIO, COLOR_PRIMARIO_OSCURO, COLOR_PRIMARIO_CLARO, poner_clase, fuente

_COLOR_VELO = QColor(22, 36, 13, 150)           # verde oscuro translúcido (~59% opaco)
_COLOR_TARJETA_RGBA = "rgba(34, 51, 28, 235)"    # tarjeta oscura, ligeramente translúcida
_GROSOR_MARCO = 6                                 # la mitad queda visible fuera del hueco
_PADDING_HUECO = 6
_ANCHO_TARJETA = 420

# Estilos de botón EXPLÍCITOS para la tarjeta del tutorial, en vez de
# depender de la clase global "secundario" (sección I.1 del reporte de
# bugs). Se definen aquí, completos, para que ninguna regla sin
# selector de un widget ancestro (ver _Tarjeta más abajo) los pueda
# volver a sobrescribir sin que se note: "Saltar tutorial" y
# "Anterior" quedan claramente legibles sobre el fondo verde oscuro.
_ESTILO_BOTON_FANTASMA = (
    "QPushButton { background-color: rgba(255,255,255,28); color: #F5F1E3; "
    "border: 1px solid rgba(255,255,255,90); border-radius: 5px; "
    "padding: 7px 14px; font-weight: normal; }"
    "QPushButton:hover { background-color: rgba(255,255,255,55); }"
)
_ESTILO_BOTON_PRIMARIO = (
    f"QPushButton {{ background-color: {COLOR_PRIMARIO}; color: white; "
    f"border: none; border-radius: 5px; padding: 7px 16px; font-weight: bold; }}"
    f"QPushButton:hover {{ background-color: {COLOR_PRIMARIO_OSCURO}; }}"
)


class _Velo(QWidget):
    """El widget que oscurece la ventana, con un hueco real (no
    pintado, no clicable) alrededor del control resaltado."""

    def __init__(self, parent):
        super().__init__(parent)
        self.setAttribute(Qt.WA_TranslucentBackground)
        self._hueco = None

    def set_hueco(self, rect: QRect | None):
        # Early-exit: si el hueco no cambió no hace falta recalcular la
        # máscara ni forzar un repaint — ahorra un QPainter pass completo
        # por cada evento de geometría redundante que llega en ráfaga.
        if rect == self._hueco:
            return
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
        franja.setObjectName("franjaTutorial")
        # OJO con setStyleSheet() sin selector: Qt lo trata como
        # "* { ... }", que SE FILTRA a todos los widgets hijos —
        # incluyendo los botones de más abajo, aunque estén en otro
        # sub-widget (`barra`). Eso es justo lo que pasaba antes: la
        # regla `background-color` de `barra` (sección I.1 del reporte
        # de bugs) terminaba pintando también el fondo de "Saltar
        # tutorial" y "Anterior" con el mismo verde oscuro de la
        # tarjeta, dejando el texto casi ilegible. Usar un selector por
        # `#objectName` en vez de una regla sin selector evita que se
        # filtre a los hijos.
        franja.setStyleSheet(
            f"#franjaTutorial {{ background-color: {COLOR_PRIMARIO}; border-radius: 6px; }}")
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
        cuerpo.setObjectName("cuerpoTutorial")
        cuerpo.setStyleSheet(f"#cuerpoTutorial {{ background-color: {_COLOR_TARJETA_RGBA}; }}")
        cl = QVBoxLayout(cuerpo)
        cl.setContentsMargins(16, 12, 16, 12)
        lbl_texto = QLabel(texto)
        lbl_texto.setStyleSheet("background: transparent; color: #EDE7D3;")
        lbl_texto.setFont(fuente(10))
        lbl_texto.setWordWrap(True)
        cl.addWidget(lbl_texto)
        layout.addWidget(cuerpo)

        barra = QWidget()
        barra.setObjectName("barraTutorial")
        barra.setStyleSheet(f"#barraTutorial {{ background-color: {_COLOR_TARJETA_RGBA}; }}")
        bl = QHBoxLayout(barra)
        bl.setContentsMargins(16, 0, 16, 14)
        btn_saltar = QPushButton(texto_saltar)
        btn_saltar.setStyleSheet(_ESTILO_BOTON_FANTASMA)
        btn_saltar.clicked.connect(on_saltar)
        bl.addWidget(btn_saltar)
        bl.addStretch()
        if mostrar_anterior:
            btn_anterior = QPushButton("◀  Anterior")
            btn_anterior.setStyleSheet(_ESTILO_BOTON_FANTASMA)
            btn_anterior.clicked.connect(on_anterior)
            bl.addWidget(btn_anterior)
        if mostrar_siguiente:
            btn_siguiente = QPushButton(texto_siguiente or ("Finalizar  ✓" if es_ultimo else "Siguiente  ▶"))
            btn_siguiente.setStyleSheet(_ESTILO_BOTON_PRIMARIO)
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
        # OJO: self._tarjeta.sizeHint().height() NO sirve aquí. La
        # tarjeta tiene setFixedWidth(360), pero QWidget.sizeHint()
        # sigue devolviendo el tamaño "ideal" del layout SIN respetar
        # ese ancho fijo (p. ej. 406×194 en vez de 360×algo) — con un
        # texto largo, a 406 px de ancho entra en menos líneas que a
        # 360, así que la altura reportada quedaba corta y el texto
        # se veía cortado por abajo. layout().totalHeightForWidth(...)
        # sí calcula la altura real que hace falta para ESE ancho.
        alto = max(self._tarjeta.layout().totalHeightForWidth(ancho), 90)
        rw, rh = self._host.width(), self._host.height()
        margen = 14

        def _recortar(cx, cy):
            cx = max(4, min(cx, rw - ancho - 4))
            cy = max(4, min(cy, rh - alto - 4))
            return cx, cy

        def _area_solapada(cx, cy):
            if hueco is None:
                return 0
            interseccion = QRect(int(cx), int(cy), ancho, alto).intersected(hueco)
            return interseccion.width() * interseccion.height()

        if hueco is not None:
            candidatos = [
                (hueco.left(), hueco.bottom() + margen),
                (hueco.left(), hueco.top() - alto - margen),
                (hueco.right() + margen, hueco.top()),
                (hueco.left() - ancho - margen, hueco.top()),
            ]
            # Antes se probaba cada candidato SIN recortar contra los
            # bordes de la ventana, y si ninguno entraba perfecto se
            # usaba el primero ("debajo") ya recortado — lo que podía
            # terminar tapando justo el control que se quería señalar
            # cuando ese control estaba pegado a una esquina (p. ej. el
            # botón "Guardar" al fondo de un diálogo). Ahora se recorta
            # cada candidato PRIMERO y luego se elige el que menos (o
            # nada) se solape con el hueco — nunca el que tape más el
            # control resaltado.
            x, y = _recortar(*candidatos[0])
            mejor_solape = _area_solapada(x, y)
            for cx, cy in candidatos[1:]:
                ccx, ccy = _recortar(cx, cy)
                solape = _area_solapada(ccx, ccy)
                if solape < mejor_solape:
                    x, y, mejor_solape = ccx, ccy, solape
                    if solape == 0:
                        break
        else:
            x, y = _recortar((rw - ancho) // 2, (rh - alto) // 2)

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
        # loop, y el control resaltado puede además seguir moviéndose
        # un poco después de mostrarse el paso — por ejemplo, al
        # cambiar de pestaña dentro de Centro de Inteligencia, o
        # cuando una tabla se termina de poblar en segundo plano — sin
        # que eso dispare un evento de resize/move de la VENTANA que
        # el overlay ya escucha. Por eso se vuelve a comprobar la
        # posición un par de veces más, recalculando el hueco de cero
        # cada vez (no el valor ya capturado), en vez de una sola
        # corrección con datos que pueden haber quedado desactualizados.
        self._id_paso = getattr(self, "_id_paso", 0) + 1
        id_paso = self._id_paso
        for demora_ms in (0, 60, 200):
            QTimer.singleShot(demora_ms, lambda i=id_paso: self._reverificar_posicion(i))

    def _reverificar_posicion(self, id_paso: int):
        if self._cerrado or id_paso != getattr(self, "_id_paso", None):
            return
        hueco = self._hueco_de(self._widget_actual, self._host)
        if self._velo is not None:
            self._velo.set_hueco(hueco)
        self._posicionar_tarjeta(hueco)

    def eventFilter(self, obj, evento):
        if obj is self._host and evento.type() in (QEvent.Resize, QEvent.Move):
            # Debounce: en el tutorial, navegar a un módulo dispara
            # decenas de eventos Resize/Move seguidos (stack cambia,
            # layouts se ajustan, pestaña se selecciona…). Sin este
            # guard se llama _reposicionar_todo una vez por cada uno,
            # recalculando geometrías y redibujando el velo en cada
            # frame aunque el resultado final sea idéntico. Con el timer
            # pendiente se colapsa toda esa ráfaga en un único repaint
            # al final del ciclo.
            if not getattr(self, "_reposicion_pendiente", False):
                self._reposicion_pendiente = True
                QTimer.singleShot(0, self._reposicionar_todo)
        elif obj is self._host and evento.type() == QEvent.KeyPress:
            if evento.key() == Qt.Key_Escape and self._on_saltar_actual and not self._cerrado:
                self._on_saltar_actual()
                return True
        return False

    def _reposicionar_todo(self):
        self._reposicion_pendiente = False
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
