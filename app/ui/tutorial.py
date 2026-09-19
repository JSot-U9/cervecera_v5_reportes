"""tutorial.py (PySide6)
=========================
Orquesta el tutorial interactivo: recorre los pasos de
`tutorial_data.py` usando `tutorial_overlay.py` para resaltar los
controles reales de la interfaz mientras el usuario navega con ella.
"""

from __future__ import annotations

from PySide6.QtCore import Qt
from PySide6.QtWidgets import (
    QDialog, QWidget, QVBoxLayout, QHBoxLayout, QLabel, QPushButton,
    QScrollArea, QFrame,
)

from app.sesion import sesion_actual
from app.ui.estilos import (
    COLOR_PRIMARIO, COLOR_TEXTO, COLOR_TEXTO_SECUNDARIO, COLOR_FONDO,
    COLOR_TARJETA, COLOR_EXITO, COLOR_ADVERTENCIA, fuente, poner_clase, fondo,
)
from app.ui.widgets import centrar_ventana
from app.ui.tutorial_overlay import OverlayTutorial
from app.ui.tutorial_data import (
    Tutorial, construir_tutorial_general, TUTORIALES_MODULO,
    tutoriales_disponibles_para_rol, obtener_progreso, guardar_progreso,
    marcar_completado, estado_tutorial, tutorial_general_pendiente,
    marcar_tutorial_general_visto,
)


def _seleccionar_tab(vista, texto_tab: str) -> bool:
    notebook = getattr(vista, "notebook", None)
    if notebook is None or not texto_tab:
        return False
    for i in range(notebook.count()):
        if texto_tab in notebook.tabText(i):
            notebook.setCurrentIndex(i)
            return True
    return False


class TutorialController:
    def __init__(self, ventana_principal, tutorial: Tutorial, on_terminar=None):
        self.ventana = ventana_principal
        self.tutorial = tutorial
        self.on_terminar = on_terminar
        self.overlay = OverlayTutorial(ventana_principal)
        self._indice = 0
        self._dialogo_actual = None
        self._cerrar_dialogo_al_avanzar = False
        self._activo = False

    def iniciar(self, paso_inicial: int = 0):
        pasos = self.tutorial.pasos
        if not pasos:
            return
        self._activo = True
        indice = paso_inicial if 0 <= paso_inicial < len(pasos) else 0
        self._mostrar(indice)

    def _guardar_progreso_actual(self, completado: bool = False):
        if sesion_actual.usuario_id is None:
            return
        guardar_progreso(sesion_actual.usuario_id, self.tutorial.clave,
                          self._indice, len(self.tutorial.pasos), completado=completado)

    def _cerrar_dialogo_si_corresponde(self):
        if self._dialogo_actual is not None:
            try:
                self._dialogo_actual.close()
            except RuntimeError:
                pass
            self._dialogo_actual = None
        self._cerrar_dialogo_al_avanzar = False

    def _mostrar(self, indice: int):
        if not self._activo:
            return
        if self._cerrar_dialogo_al_avanzar:
            self._cerrar_dialogo_si_corresponde()

        pasos = self.tutorial.pasos
        self._indice = max(0, min(indice, len(pasos) - 1))
        paso = pasos[self._indice]

        vista = None
        try:
            if paso.modulo:
                self.ventana.navegar(paso.modulo)
                vista = self.ventana.obtener_vista(paso.modulo)
                if paso.tab and vista is not None:
                    _seleccionar_tab(vista, paso.tab)
            else:
                vista = self.ventana.vista_activa()
        except RuntimeError:
            vista = None

        if paso.abrir is not None and vista is not None:
            try:
                nuevo_dialogo = paso.abrir(vista)
                if nuevo_dialogo is not None:
                    self._dialogo_actual = nuevo_dialogo
            except (RuntimeError, AttributeError):
                pass

        self._cerrar_dialogo_al_avanzar = bool(paso.cerrar_dialogo)

        contexto = {"ventana": self.ventana, "vista": vista, "dialogo": self._dialogo_actual}
        widget_objetivo = None
        if paso.target is not None:
            try:
                widget_objetivo = paso.target(contexto)
            except (RuntimeError, AttributeError, KeyError):
                widget_objetivo = None

        self._guardar_progreso_actual(completado=False)

        self.overlay.mostrar_paso(
            widget_objetivo, icono=paso.icono, titulo=paso.titulo, texto=paso.texto,
            indice=self._indice, total=len(pasos),
            on_anterior=self._anterior, on_siguiente=self._siguiente, on_saltar=self._saltar,
            mostrar_anterior=(self._indice > 0), es_ultimo=(self._indice == len(pasos) - 1),
        )

    def _siguiente(self):
        if self._indice < len(self.tutorial.pasos) - 1:
            self._mostrar(self._indice + 1)
        else:
            self._finalizar()

    def _anterior(self):
        if self._indice > 0:
            self._mostrar(self._indice - 1)

    def _saltar(self):
        self._terminar(completado=False)

    def _finalizar(self):
        self._terminar(completado=True)

    def _terminar(self, completado: bool):
        if not self._activo:
            return
        self._activo = False
        if sesion_actual.usuario_id is not None:
            if completado:
                marcar_completado(sesion_actual.usuario_id, self.tutorial.clave, len(self.tutorial.pasos))
                if self.tutorial.clave == "general":
                    marcar_tutorial_general_visto(sesion_actual.usuario_id)
            else:
                self._guardar_progreso_actual(completado=False)
                if self.tutorial.clave == "general":
                    marcar_tutorial_general_visto(sesion_actual.usuario_id)
        self._cerrar_dialogo_si_corresponde()
        self.overlay.cerrar()
        if self.on_terminar:
            self.on_terminar()


# ══════════════════════════════════════════════════════════════════
#  API PÚBLICA
# ══════════════════════════════════════════════════════════════════

def tal_vez_iniciar_tutorial_general(ventana_principal):
    if sesion_actual.usuario_id is None:
        return
    if tutorial_general_pendiente(sesion_actual.usuario_id):
        iniciar_tutorial_general(ventana_principal)


def iniciar_tutorial_general(ventana_principal, reiniciar: bool = False):
    tutorial = construir_tutorial_general(ventana_principal.nombre_empresa(), sesion_actual.rol)
    paso_inicial = 0
    if not reiniciar and sesion_actual.usuario_id is not None:
        progreso = obtener_progreso(sesion_actual.usuario_id, "general")
        if not progreso["completado"]:
            paso_inicial = progreso["paso_actual"]
    controlador = TutorialController(ventana_principal, tutorial)
    controlador.iniciar(paso_inicial)
    return controlador


def iniciar_tutorial_modulo(ventana_principal, clave: str, reiniciar: bool = False, on_terminar=None):
    fabrica = TUTORIALES_MODULO.get(clave)
    if fabrica is None:
        return None
    tutorial = fabrica()
    paso_inicial = 0
    if not reiniciar and sesion_actual.usuario_id is not None:
        progreso = obtener_progreso(sesion_actual.usuario_id, clave)
        if not progreso["completado"]:
            paso_inicial = progreso["paso_actual"]
    controlador = TutorialController(ventana_principal, tutorial, on_terminar=on_terminar)
    controlador.iniciar(paso_inicial)
    return controlador


# ══════════════════════════════════════════════════════════════════
#  CENTRO DE AYUDA
# ══════════════════════════════════════════════════════════════════

_ICONO_ESTADO = {"completado": "✓", "en_progreso": "◐", "no_iniciado": "○"}
_COLOR_ESTADO = {"completado": COLOR_EXITO, "en_progreso": COLOR_ADVERTENCIA,
                 "no_iniciado": COLOR_TEXTO_SECUNDARIO}
_TEXTO_ESTADO = {"completado": "Completado", "en_progreso": "En progreso", "no_iniciado": "No iniciado"}


class CentroAyuda(QDialog):
    def __init__(self, ventana_principal):
        super().__init__(ventana_principal)
        self.ventana_principal = ventana_principal
        self.setWindowTitle("Ayuda y tutorial")

        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(0)

        franja = QWidget()
        fondo(franja, COLOR_PRIMARIO)
        fl = QVBoxLayout(franja)
        fl.setContentsMargins(20, 16, 20, 16)
        lbl = QLabel("❓  Centro de ayuda")
        lbl.setStyleSheet("background: transparent; color: white;")
        lbl.setFont(fuente(15, negrita=True))
        fl.addWidget(lbl)
        lbl2 = QLabel("Aprende a usar cada módulo con un recorrido guiado.")
        lbl2.setStyleSheet("background: transparent; color: #F2E6C9;")
        lbl2.setFont(fuente(9))
        fl.addWidget(lbl2)
        layout.addWidget(franja)

        scroll = QScrollArea()
        scroll.setWidgetResizable(True)
        scroll.setFrameShape(QScrollArea.NoFrame)
        layout.addWidget(scroll, stretch=1)

        cuerpo = QWidget()
        scroll.setWidget(cuerpo)
        self._cuerpo_layout = QVBoxLayout(cuerpo)
        self._cuerpo_layout.setContentsMargins(16, 12, 16, 12)
        self._cuerpo_layout.setSpacing(8)

        self._construir_lista()

        barra = QHBoxLayout()
        barra.setContentsMargins(16, 10, 16, 10)
        barra.addStretch()
        btn_cerrar = QPushButton("Cerrar")
        btn_cerrar.clicked.connect(self.accept)
        barra.addWidget(btn_cerrar)
        layout.addLayout(barra)

        centrar_ventana(self, 480, 560)

    def _construir_lista(self):
        rol = sesion_actual.rol
        usuario_id = sesion_actual.usuario_id
        disponibles = tutoriales_disponibles_para_rol(rol)

        titulos = {"general": ("🎓", "Tutorial general", "Aprende a utilizar Cervecera")}
        for clave in TUTORIALES_MODULO:
            t = TUTORIALES_MODULO[clave]()
            titulos[clave] = (t.icono, t.titulo, t.descripcion)

        for clave in disponibles:
            icono, titulo, descripcion = titulos[clave]
            estado = estado_tutorial(usuario_id, clave) if usuario_id is not None else "no_iniciado"
            self._fila_tutorial(clave, icono, titulo, descripcion, estado)

        self._cuerpo_layout.addStretch()

    def _fila_tutorial(self, clave, icono, titulo, descripcion, estado):
        fila = QFrame()
        fila.setStyleSheet(
            f"QFrame {{ background-color: {COLOR_TARJETA}; border: 1px solid #E5D6B3; "
            f"border-radius: 6px; }}")
        fl = QVBoxLayout(fila)
        fl.setContentsMargins(14, 10, 14, 10)

        superior = QHBoxLayout()
        lbl_titulo = QLabel(f"{icono}  {titulo}")
        lbl_titulo.setFont(fuente(11, negrita=True))
        superior.addWidget(lbl_titulo)
        superior.addStretch()
        lbl_estado = QLabel(f"{_ICONO_ESTADO[estado]}  {_TEXTO_ESTADO[estado]}")
        lbl_estado.setStyleSheet(f"color: {_COLOR_ESTADO[estado]};")
        lbl_estado.setFont(fuente(9, negrita=True))
        superior.addWidget(lbl_estado)
        fl.addLayout(superior)

        lbl_desc = QLabel(descripcion)
        lbl_desc.setStyleSheet(f"color: {COLOR_TEXTO_SECUNDARIO};")
        lbl_desc.setFont(fuente(9))
        lbl_desc.setWordWrap(True)
        fl.addWidget(lbl_desc)

        botonera = QHBoxLayout()
        texto_principal = {"completado": "Repetir tutorial", "en_progreso": "Continuar",
                            "no_iniciado": "Empezar"}[estado]
        btn = QPushButton(texto_principal)
        btn.clicked.connect(lambda: self._iniciar(clave, reiniciar=(estado == "completado")))
        botonera.addWidget(btn)
        if estado == "en_progreso":
            btn2 = QPushButton("Reiniciar")
            poner_clase(btn2, "secundario")
            btn2.clicked.connect(lambda: self._iniciar(clave, reiniciar=True))
            botonera.addWidget(btn2)
        botonera.addStretch()
        fl.addLayout(botonera)

        self._cuerpo_layout.addWidget(fila)

    def _iniciar(self, clave, reiniciar):
        self.accept()
        if clave == "general":
            iniciar_tutorial_general(self.ventana_principal, reiniciar=reiniciar)
        else:
            iniciar_tutorial_modulo(self.ventana_principal, clave, reiniciar=reiniciar)

    def keyPressEvent(self, evento):
        if evento.key() == Qt.Key_Escape:
            self.accept()
        else:
            super().keyPressEvent(evento)


def abrir_centro_ayuda(ventana_principal):
    CentroAyuda(ventana_principal).exec()
