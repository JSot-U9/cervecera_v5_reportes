"""tutorial_practice.py (PySide6)
==================================
Modo de tutorial PRÁCTICO: el usuario realiza de verdad las acciones,
sobre el formulario REAL de Compras (`VentanaNuevaOrden`), detectando
sus acciones reales sin duplicar ninguna lógica de negocio ni crear
datos de demostración.
"""

from __future__ import annotations

from PySide6.QtCore import Qt, QTimer
from PySide6.QtWidgets import QDialog, QWidget, QVBoxLayout, QHBoxLayout, QLabel, QPushButton

from app.sesion import sesion_actual
from app.ui.estilos import (
    COLOR_PRIMARIO, COLOR_TEXTO_SECUNDARIO, COLOR_TARJETA, COLOR_EXITO,
    COLOR_ADVERTENCIA, fuente, fondo,
)
from app.ui.widgets import centrar_ventana
from app.ui.tutorial_overlay import OverlayTutorial
from app.ui.tutorial_data import marcar_completado, guardar_progreso

_ITEMS = [
    "Abrir el módulo de Compras",
    "Abrir el formulario “Nueva orden”",
    "Seleccionar un proveedor",
    "Agregar un producto a la orden (cantidad y precio)",
    "Guardar la orden cuando estés listo(a)",
]
_INTERVALO_MS = 300
_CLAVE_PROGRESO = "compras_practica"


class PanelChecklist(QDialog):
    """Ventana flotante, no modal, con la lista de acciones de la
    práctica y su estado (pendiente / hecho)."""

    def __init__(self, parent, items: list[str], on_salir):
        super().__init__(parent)
        self.setWindowTitle("Práctica: registrar una compra")
        self.setModal(False)
        self._on_salir = on_salir

        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(0)

        franja = QWidget()
        fondo(franja, COLOR_PRIMARIO)
        fl = QVBoxLayout(franja)
        fl.setContentsMargins(16, 12, 16, 12)
        lbl = QLabel("🧑‍🏫  PRACTICA")
        lbl.setStyleSheet("background: transparent; color: white;")
        lbl.setFont(fuente(12, negrita=True))
        fl.addWidget(lbl)
        lbl2 = QLabel("Registra una compra de prueba.")
        lbl2.setStyleSheet("background: transparent; color: #F2E6C9;")
        lbl2.setFont(fuente(9))
        fl.addWidget(lbl2)
        layout.addWidget(franja)

        cuerpo = QWidget()
        fondo(cuerpo, COLOR_TARJETA)
        cl = QVBoxLayout(cuerpo)
        cl.setContentsMargins(16, 12, 16, 12)

        self._filas = []
        for texto in items:
            fila = QHBoxLayout()
            lbl_check = QLabel("☐")
            lbl_check.setStyleSheet(f"color: {COLOR_TEXTO_SECUNDARIO}; background: transparent;")
            lbl_check.setFont(fuente(11))
            fila.addWidget(lbl_check)
            lbl_texto = QLabel(texto)
            lbl_texto.setStyleSheet("background: transparent;")
            lbl_texto.setFont(fuente(9))
            lbl_texto.setWordWrap(True)
            fila.addWidget(lbl_texto, stretch=1)
            cl.addLayout(fila)
            self._filas.append((lbl_check, lbl_texto))

        self._lbl_estado = QLabel("")
        self._lbl_estado.setFont(fuente(9, negrita=True))
        self._lbl_estado.setWordWrap(True)
        self._lbl_estado.setStyleSheet("background: transparent;")
        cl.addWidget(self._lbl_estado)
        layout.addWidget(cuerpo)

        barra = QHBoxLayout()
        barra.setContentsMargins(16, 10, 16, 10)
        barra.addStretch()
        btn_salir = QPushButton("Salir del tutorial")
        from app.ui.estilos import poner_clase
        poner_clase(btn_salir, "secundario")
        btn_salir.clicked.connect(on_salir)
        barra.addWidget(btn_salir)
        layout.addLayout(barra)

        centrar_ventana(self, 330, 130 + 30 * len(items))

    def marcar_hecho(self, indice: int):
        lbl_check, lbl_texto = self._filas[indice]
        lbl_check.setText("✅")
        lbl_check.setStyleSheet(f"color: {COLOR_EXITO}; background: transparent;")

    def resaltar_pendiente(self, indice: int):
        for i, (_lbl_check, lbl_texto) in enumerate(self._filas):
            lbl_texto.setFont(fuente(9, negrita=(i == indice)))

    def mostrar_mensaje(self, texto: str, tipo: str = "info"):
        color = {"exito": COLOR_EXITO, "advertencia": COLOR_ADVERTENCIA,
                 "info": COLOR_TEXTO_SECUNDARIO}.get(tipo, COLOR_TEXTO_SECUNDARIO)
        self._lbl_estado.setStyleSheet(f"color: {color}; background: transparent;")
        self._lbl_estado.setText(texto)

    def keyPressEvent(self, evento):
        if evento.key() == Qt.Key_Escape:
            self._on_salir()
        else:
            super().keyPressEvent(evento)


class PracticaCompras:
    def __init__(self, ventana_principal, on_terminar=None):
        self.ventana = ventana_principal
        self.on_terminar = on_terminar
        self.overlay = OverlayTutorial(ventana_principal)
        self.panel: PanelChecklist | None = None
        self._vista = None
        self._dialogo = None
        self._al_guardar_original = None
        self._guardado_detectado = False
        self._estado = 0
        self._timer: QTimer | None = None
        self._activo = False

    def iniciar(self):
        self._vista = self.ventana.obtener_vista("compras")
        if self._vista is None:
            return self
        self.ventana.navegar("compras")

        self._activo = True
        self.panel = PanelChecklist(self.ventana, _ITEMS, on_salir=self.detener)
        self.panel.show()
        self.panel.marcar_hecho(0)
        self._estado = 1
        self._actualizar_paso()

        self._timer = QTimer(self.ventana)
        self._timer.timeout.connect(self._verificar_seguro)
        self._timer.start(_INTERVALO_MS)
        return self

    def _verificar_seguro(self):
        if not self._activo:
            return
        try:
            self._verificar()
        except RuntimeError:
            pass

    def _dialogo_activo(self):
        dialogo = getattr(self._vista, "ultimo_dialogo_nueva_orden", None)
        if dialogo is None:
            return None
        try:
            if not dialogo.isVisible():
                return None
        except RuntimeError:
            return None
        return dialogo

    def _verificar(self):
        dialogo = self._dialogo_activo()

        if self._estado == 1:
            if dialogo is not None:
                self._dialogo = dialogo
                self._envolver_guardado()
                self.panel.marcar_hecho(1)
                self.panel.mostrar_mensaje("✓ ¡Correcto! Ahora elige un proveedor.", "exito")
                self._estado = 2
                self._actualizar_paso()
            return

        if dialogo is None and not self._guardado_detectado:
            self.panel.mostrar_mensaje(
                "Cerraste el formulario antes de terminar. Puedes reiniciar "
                "la práctica cuando quieras desde «❓ Ayuda y tutorial».", "advertencia")
            self.detener(marcar_progreso=True)
            return

        if self._estado == 2:
            if dialogo is not None and dialogo.combo_proveedor.currentIndex() >= 0:
                self.panel.marcar_hecho(2)
                self.panel.mostrar_mensaje(
                    "✓ ¡Correcto! Ahora agrega un producto (cantidad y precio).", "exito")
                self._estado = 3
                self._actualizar_paso()
            return

        if self._estado == 3:
            if dialogo is not None and getattr(dialogo, "items_agregados", []):
                self.panel.marcar_hecho(3)
                self.panel.mostrar_mensaje(
                    "✓ ¡Correcto! Cuando quieras, guarda la orden para terminar.", "exito")
                self._estado = 4
                self._actualizar_paso()
            return

        if self._estado == 4 and self._guardado_detectado:
            self.panel.marcar_hecho(4)
            self._finalizar()

    def _actualizar_paso(self):
        if not self.panel:
            return
        self.panel.resaltar_pendiente(self._estado)
        widget = None
        if self._estado == 1:
            widget = getattr(self._vista, "tutorial_targets", {}).get("btn_nueva_orden")
        elif self._estado in (2, 3, 4) and self._dialogo is not None:
            claves = {2: "combo_proveedor", 3: "btn_agregar_item", 4: "btn_guardar"}
            widget = getattr(self._dialogo, claves[self._estado], None)

        textos = {
            1: ("＋", "Abre el formulario",
                "Pulsa «＋ Nueva orden» para empezar a registrar una compra de prueba."),
            2: ("🏭", "Selecciona un proveedor", "Elige cualquier proveedor real de la lista."),
            3: ("📦", "Agrega un producto",
                "Elige un producto, indica cantidad y precio, y pulsa «＋ Agregar a la orden»."),
            4: ("💾", "Guarda cuando quieras",
                "Puedes guardar la orden de verdad para completar la práctica, o «Cancelar» "
                "si solo querías practicar. Ninguna de las dos opciones te bloquea."),
        }
        icono, titulo, texto = textos.get(self._estado, ("💡", "", ""))
        self.overlay.mostrar_paso(
            widget, icono=icono, titulo=titulo, texto=texto,
            mostrar_siguiente=False, mostrar_anterior=False,
            texto_saltar="Salir del tutorial ✕", on_saltar=self.detener,
        )

    def _envolver_guardado(self):
        if self._dialogo is None or self._al_guardar_original is not None:
            return
        self._al_guardar_original = self._dialogo.al_guardar

        def _envoltura():
            self._guardado_detectado = True
            self._al_guardar_original()

        self._dialogo.al_guardar = _envoltura

    def _detener_timer(self):
        if self._timer is not None:
            try:
                self._timer.stop()
            except RuntimeError:
                pass
            self._timer = None

    def _finalizar(self):
        if not self._activo:
            return
        self._activo = False
        self._detener_timer()
        if sesion_actual.usuario_id is not None:
            marcar_completado(sesion_actual.usuario_id, _CLAVE_PROGRESO, len(_ITEMS))
        self.overlay.cerrar()
        if self.panel is not None:
            self.panel.close()
        if self.on_terminar:
            self.on_terminar()

    def detener(self, marcar_progreso: bool = False):
        if not self._activo:
            return
        self._activo = False
        self._detener_timer()
        if marcar_progreso and sesion_actual.usuario_id is not None:
            guardar_progreso(sesion_actual.usuario_id, _CLAVE_PROGRESO,
                              self._estado, len(_ITEMS), completado=False)
        self.overlay.cerrar()
        if self.panel is not None:
            self.panel.close()
        if self.on_terminar:
            self.on_terminar()
