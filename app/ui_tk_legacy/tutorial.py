"""
tutorial.py
===========
Orquesta el tutorial interactivo de Cervecera: recorre los pasos
declarados en `tutorial_data.py`, usando `tutorial_overlay.py` para
resaltar los controles reales de la interfaz mientras el usuario
navega con ella.

Piezas públicas principales:
  - tal_vez_iniciar_tutorial_general(ventana) : se llama una vez, al
    abrir la ventana principal; si el usuario nunca vio el tour
    general, lo arranca automáticamente.
  - iniciar_tutorial_general(ventana)
  - iniciar_tutorial_modulo(ventana, clave, reiniciar=False)
  - iniciar_practica_compras(ventana)
  - abrir_centro_ayuda(ventana)   : panel "❓ Ayuda y tutorial"

El controlador de pasos (`TutorialController`) es genérico: sirve
para el tour general y para cualquier tutorial de módulo, porque
ambos son simplemente listas de `PasoTutorial`. Agregar un tutorial
nuevo no requiere tocar este archivo — solo `tutorial_data.py`.
"""

from __future__ import annotations

import tkinter as tk
from tkinter import ttk

from app.sesion import sesion_actual
from app.ui.estilos import (
    COLOR_PRIMARIO, COLOR_TEXTO, COLOR_TEXTO_SECUNDARIO,
    COLOR_FONDO, COLOR_TARJETA, COLOR_EXITO, COLOR_ADVERTENCIA,
)
from app.ui.widgets import centrar_ventana
from app.ui.tutorial_overlay import OverlayTutorial, boton_ayuda_contextual  # noqa: F401 (re-exportado)
from app.ui.tutorial_data import (
    Tutorial, PasoTutorial,
    construir_tutorial_general, TUTORIALES_MODULO, ORDEN_CENTRO_AYUDA,
    tutoriales_disponibles_para_rol,
    obtener_progreso, guardar_progreso, marcar_completado, reiniciar_progreso,
    estado_tutorial, tutorial_general_pendiente, marcar_tutorial_general_visto,
    AYUDA_CONTEXTUAL,
)


def _seleccionar_tab(vista, texto_tab: str) -> bool:
    """Selecciona, en el Notebook de la vista (si tiene), la pestaña
    cuyo texto contiene `texto_tab`. Devuelve True si la encontró."""
    notebook = getattr(vista, "notebook", None)
    if notebook is None or not texto_tab:
        return False
    for tab_id in notebook.tabs():
        if texto_tab in notebook.tab(tab_id, "text"):
            notebook.select(tab_id)
            return True
    return False


class TutorialController:
    """
    Ejecuta un `Tutorial` (lista de `PasoTutorial`) paso a paso sobre
    una `VentanaPrincipal` real, usando un `OverlayTutorial` para
    resaltar los controles.
    """

    def __init__(self, ventana_principal, tutorial: Tutorial, on_terminar=None):
        self.ventana = ventana_principal
        self.tutorial = tutorial
        self.on_terminar = on_terminar
        self.overlay = OverlayTutorial(ventana_principal)
        self._indice = 0
        self._dialogo_actual = None
        self._cerrar_dialogo_al_avanzar = False
        self._activo = False

    # ── Ciclo de vida ────────────────────────────────────────────
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
        guardar_progreso(
            sesion_actual.usuario_id, self.tutorial.clave,
            self._indice, len(self.tutorial.pasos), completado=completado,
        )

    def _cerrar_dialogo_si_corresponde(self):
        if self._dialogo_actual is not None:
            try:
                if self._dialogo_actual.winfo_exists():
                    self._dialogo_actual.destroy()
            except tk.TclError:
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
                self.ventana.update_idletasks()
                if paso.tab and vista is not None:
                    _seleccionar_tab(vista, paso.tab)
                    self.ventana.update_idletasks()
            else:
                vista = self.ventana.vista_activa()
        except (tk.TclError, AttributeError):
            vista = None

        if paso.abrir is not None and vista is not None:
            try:
                nuevo_dialogo = paso.abrir(vista)
                if nuevo_dialogo is not None:
                    self._dialogo_actual = nuevo_dialogo
                    self.ventana.update_idletasks()
            except (tk.TclError, AttributeError):
                pass

        self._cerrar_dialogo_al_avanzar = bool(paso.cerrar_dialogo)

        contexto = {"ventana": self.ventana, "vista": vista, "dialogo": self._dialogo_actual}
        widget_objetivo = None
        if paso.target is not None:
            try:
                widget_objetivo = paso.target(contexto)
            except (tk.TclError, AttributeError, KeyError):
                widget_objetivo = None

        self._guardar_progreso_actual(completado=False)

        self.overlay.mostrar_paso(
            widget_objetivo,
            icono=paso.icono, titulo=paso.titulo, texto=paso.texto,
            indice=self._indice, total=len(pasos),
            on_anterior=self._anterior, on_siguiente=self._siguiente,
            on_saltar=self._saltar,
            mostrar_anterior=(self._indice > 0),
            es_ultimo=(self._indice == len(pasos) - 1),
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
                marcar_completado(sesion_actual.usuario_id, self.tutorial.clave,
                                   len(self.tutorial.pasos))
                if self.tutorial.clave == "general":
                    marcar_tutorial_general_visto(sesion_actual.usuario_id)
            else:
                self._guardar_progreso_actual(completado=False)
                if self.tutorial.clave == "general":
                    # Saltar el tour general tampoco debe insistir en el
                    # próximo inicio de sesión.
                    marcar_tutorial_general_visto(sesion_actual.usuario_id)
        self._cerrar_dialogo_si_corresponde()
        self.overlay.cerrar()
        if self.on_terminar:
            self.on_terminar()


# ══════════════════════════════════════════════════════════════════
#  API PÚBLICA
# ══════════════════════════════════════════════════════════════════

def tal_vez_iniciar_tutorial_general(ventana_principal):
    """Llamar una vez al abrir la ventana principal. Si el usuario
    nunca vio (ni saltó) el tour general, lo arranca automáticamente."""
    if sesion_actual.usuario_id is None:
        return
    if tutorial_general_pendiente(sesion_actual.usuario_id):
        iniciar_tutorial_general(ventana_principal)


def iniciar_tutorial_general(ventana_principal, reiniciar: bool = False):
    tutorial = construir_tutorial_general(ventana_principal.nombre_empresa(),
                                           sesion_actual.rol)
    paso_inicial = 0
    if not reiniciar and sesion_actual.usuario_id is not None:
        progreso = obtener_progreso(sesion_actual.usuario_id, "general")
        if not progreso["completado"]:
            paso_inicial = progreso["paso_actual"]
    controlador = TutorialController(ventana_principal, tutorial)
    controlador.iniciar(paso_inicial)
    return controlador


def iniciar_tutorial_modulo(ventana_principal, clave: str, reiniciar: bool = False,
                             on_terminar=None):
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


def iniciar_practica_compras(ventana_principal, on_terminar=None):
    from app.ui.tutorial_practice import PracticaCompras
    return PracticaCompras(ventana_principal, on_terminar=on_terminar).iniciar()


# ══════════════════════════════════════════════════════════════════
#  CENTRO DE AYUDA
# ══════════════════════════════════════════════════════════════════

_ICONO_ESTADO = {"completado": "✓", "en_progreso": "◐", "no_iniciado": "○"}
_COLOR_ESTADO = {"completado": COLOR_EXITO, "en_progreso": COLOR_ADVERTENCIA,
                 "no_iniciado": COLOR_TEXTO_SECUNDARIO}
_TEXTO_ESTADO = {"completado": "Completado", "en_progreso": "En progreso",
                  "no_iniciado": "No iniciado"}


class CentroAyuda(tk.Toplevel):
    """Panel «❓ Ayuda y tutorial»: lista todos los tutoriales
    disponibles para el rol del usuario con su estado, y permite
    iniciarlos, continuarlos o repetirlos."""

    ANCHO, ALTO = 480, 560

    def __init__(self, ventana_principal):
        super().__init__(ventana_principal)
        self.ventana_principal = ventana_principal
        self.title("Ayuda y tutorial")
        self.configure(bg=COLOR_FONDO)
        self.resizable(False, False)
        self.transient(ventana_principal)

        franja = tk.Frame(self, bg=COLOR_PRIMARIO, padx=20, pady=16)
        franja.pack(fill="x")
        tk.Label(franja, text="❓  Centro de ayuda", bg=COLOR_PRIMARIO, fg="white",
                  font=("Segoe UI", 15, "bold")).pack(anchor="w")
        tk.Label(franja, text="Aprende a usar cada módulo con un recorrido guiado.",
                  bg=COLOR_PRIMARIO, fg="#F2E6C9", font=("Segoe UI", 9)).pack(anchor="w")

        # Área con scroll (por si el rol tiene muchos tutoriales disponibles)
        contenedor = tk.Frame(self, bg=COLOR_FONDO)
        contenedor.pack(fill="both", expand=True)
        canvas = tk.Canvas(contenedor, bg=COLOR_FONDO, highlightthickness=0)
        scrollbar = ttk.Scrollbar(contenedor, orient="vertical", command=canvas.yview)
        canvas.configure(yscrollcommand=scrollbar.set)
        scrollbar.pack(side="right", fill="y")
        canvas.pack(side="left", fill="both", expand=True)

        cuerpo = tk.Frame(canvas, bg=COLOR_FONDO, padx=16, pady=12)
        cuerpo_id = canvas.create_window((0, 0), window=cuerpo, anchor="nw")
        cuerpo.bind("<Configure>", lambda e: canvas.configure(scrollregion=canvas.bbox("all")))
        canvas.bind("<Configure>", lambda e: canvas.itemconfig(cuerpo_id, width=e.width))

        self._construir_lista(cuerpo)

        barra = tk.Frame(self, bg=COLOR_FONDO, padx=16, pady=12)
        barra.pack(fill="x")
        ttk.Button(barra, text="Cerrar", command=self.destroy).pack(side="right")

        centrar_ventana(self, self.ANCHO, self.ALTO)
        self.bind("<Escape>", lambda e: self.destroy())
        self.grab_set()
        self.focus_set()

    def _construir_lista(self, cuerpo):
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
            self._fila_tutorial(cuerpo, clave, icono, titulo, descripcion, estado)

        # Práctica guiada (ejemplo completo de aprender haciendo)
        if "compras" in disponibles:
            self._fila_practica(cuerpo)

    def _fila_tutorial(self, parent, clave, icono, titulo, descripcion, estado):
        fila = tk.Frame(parent, bg=COLOR_TARJETA, padx=14, pady=10,
                          highlightbackground="#E5D6B3", highlightthickness=1)
        fila.pack(fill="x", pady=5)

        superior = tk.Frame(fila, bg=COLOR_TARJETA)
        superior.pack(fill="x")
        tk.Label(superior, text=f"{icono}  {titulo}", bg=COLOR_TARJETA, fg=COLOR_TEXTO,
                  font=("Segoe UI", 11, "bold"), anchor="w").pack(side="left")
        tk.Label(superior, text=f"{_ICONO_ESTADO[estado]}  {_TEXTO_ESTADO[estado]}",
                  bg=COLOR_TARJETA, fg=_COLOR_ESTADO[estado],
                  font=("Segoe UI", 9, "bold")).pack(side="right")

        tk.Label(fila, text=descripcion, bg=COLOR_TARJETA, fg=COLOR_TEXTO_SECUNDARIO,
                  font=("Segoe UI", 9), wraplength=340, justify="left",
                  anchor="w").pack(fill="x", pady=(2, 8))

        botonera = tk.Frame(fila, bg=COLOR_TARJETA)
        botonera.pack(fill="x")
        texto_principal = {
            "completado": "Repetir tutorial",
            "en_progreso": "Continuar",
            "no_iniciado": "Empezar",
        }[estado]
        ttk.Button(botonera, text=texto_principal,
                   command=lambda: self._iniciar(clave, reiniciar=(estado == "completado"))
                   ).pack(side="left")
        if estado == "en_progreso":
            ttk.Button(botonera, text="Reiniciar", style="Secundario.TButton",
                       command=lambda: self._iniciar(clave, reiniciar=True)
                       ).pack(side="left", padx=(8, 0))

    def _fila_practica(self, parent):
        fila = tk.Frame(parent, bg=COLOR_TARJETA, padx=14, pady=10,
                          highlightbackground=COLOR_PRIMARIO, highlightthickness=1)
        fila.pack(fill="x", pady=5)
        tk.Label(fila, text="🧑‍🏫  Practicar: Compras", bg=COLOR_TARJETA, fg=COLOR_TEXTO,
                  font=("Segoe UI", 11, "bold"), anchor="w").pack(fill="x")
        tk.Label(fila,
                  text="Registra una compra de prueba de verdad, con ayuda "
                       "del sistema en cada paso.",
                  bg=COLOR_TARJETA, fg=COLOR_TEXTO_SECUNDARIO, font=("Segoe UI", 9),
                  wraplength=340, justify="left", anchor="w").pack(fill="x", pady=(2, 8))
        ttk.Button(fila, text="Empezar práctica", command=self._iniciar_practica).pack(anchor="w")

    def _iniciar(self, clave, reiniciar):
        self.destroy()
        if clave == "general":
            iniciar_tutorial_general(self.ventana_principal, reiniciar=reiniciar)
        else:
            iniciar_tutorial_modulo(self.ventana_principal, clave, reiniciar=reiniciar)

    def _iniciar_practica(self):
        self.destroy()
        iniciar_practica_compras(self.ventana_principal)


def abrir_centro_ayuda(ventana_principal):
    CentroAyuda(ventana_principal)
