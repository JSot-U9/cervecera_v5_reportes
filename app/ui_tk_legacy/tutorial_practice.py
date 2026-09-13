"""
tutorial_practice.py
=====================
Modo de tutorial PRÁCTICO: el usuario realiza de verdad las acciones
(no solo lee explicaciones). Se implementa aquí el ejemplo mínimo
pedido — registrar una compra de prueba en el módulo de Compras —,
sobre los controles REALES del formulario (`VentanaNuevaOrden`, en
`vista_compras.py`), sin duplicar ninguna lógica de negocio.

Cómo se detectan las acciones, sin modificar `logica_compras.py` ni
inventar un segundo sistema de eventos:
  - "Abrir Compras"        → se detecta navegando nosotros mismos.
  - "Abrir Nueva orden"    → `VistaCompras` guarda una referencia al
    diálogo recién abierto en `self.ultimo_dialogo_nueva_orden`;
    este controlador la vigila con un `after()` periódico.
  - "Seleccionar proveedor"/"Agregar producto" → se observa el propio
    estado del formulario (`combo_proveedor.get()`, `items_agregados`),
    que ya existe para su funcionamiento normal.
  - "Guardar la orden"     → se envuelve (sin romperlo) el callback
    `al_guardar` que el diálogo ya recibe, para enterarnos cuando el
    usuario complete el guardado real.

No se crean datos de demostración: el usuario practica con
proveedores y productos reales, y decide él mismo si guarda la orden
al final (ver punto 13 del pedido: nada se contamina si no se guarda).
Salir de la práctica en cualquier momento («Salir del tutorial») no
bloquea ni cierra el formulario: el usuario conserva el control.
"""

from __future__ import annotations

import tkinter as tk
from tkinter import ttk

from app.sesion import sesion_actual
from app.ui.estilos import (
    COLOR_PRIMARIO, COLOR_TEXTO, COLOR_TEXTO_SECUNDARIO, COLOR_FONDO,
    COLOR_TARJETA, COLOR_EXITO, COLOR_ADVERTENCIA,
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


class PanelChecklist(tk.Toplevel):
    """Ventana flotante, no modal, con la lista de acciones de la
    práctica y su estado (pendiente / hecho)."""

    def __init__(self, parent, items: list[str], on_salir):
        super().__init__(parent)
        self.title("Práctica: registrar una compra")
        self.configure(bg=COLOR_FONDO)
        self.resizable(False, False)
        self.attributes("-topmost", True)
        self.protocol("WM_DELETE_WINDOW", on_salir)

        franja = tk.Frame(self, bg=COLOR_PRIMARIO, padx=16, pady=12)
        franja.pack(fill="x")
        tk.Label(franja, text="🧑‍🏫  PRACTICA", bg=COLOR_PRIMARIO, fg="white",
                  font=("Segoe UI", 12, "bold")).pack(anchor="w")
        tk.Label(franja, text="Registra una compra de prueba.", bg=COLOR_PRIMARIO,
                  fg="#F2E6C9", font=("Segoe UI", 9)).pack(anchor="w")

        cuerpo = tk.Frame(self, bg=COLOR_TARJETA, padx=16, pady=12)
        cuerpo.pack(fill="both", expand=True)

        self._filas = []
        for texto in items:
            fila = tk.Frame(cuerpo, bg=COLOR_TARJETA)
            fila.pack(fill="x", pady=3)
            lbl_check = tk.Label(fila, text="☐", bg=COLOR_TARJETA,
                                   fg=COLOR_TEXTO_SECUNDARIO, font=("Segoe UI", 11))
            lbl_check.pack(side="left", padx=(0, 8))
            lbl_texto = tk.Label(fila, text=texto, bg=COLOR_TARJETA, fg=COLOR_TEXTO,
                                   font=("Segoe UI", 9), anchor="w", justify="left",
                                   wraplength=260)
            lbl_texto.pack(side="left", fill="x", expand=True)
            self._filas.append((lbl_check, lbl_texto))

        self._lbl_estado = tk.Label(cuerpo, text="", bg=COLOR_TARJETA,
                                      font=("Segoe UI", 9, "bold"), wraplength=280,
                                      justify="left", anchor="w")
        self._lbl_estado.pack(fill="x", pady=(8, 0))

        barra = tk.Frame(self, bg=COLOR_FONDO, padx=16, pady=10)
        barra.pack(fill="x")
        ttk.Button(barra, text="Salir del tutorial", style="Secundario.TButton",
                   command=on_salir).pack(side="right")

        centrar_ventana(self, 330, 120 + 26 * len(items))
        self.bind("<Escape>", lambda e: on_salir())

    def marcar_hecho(self, indice: int):
        lbl_check, lbl_texto = self._filas[indice]
        lbl_check.configure(text="✅", fg=COLOR_EXITO)
        lbl_texto.configure(fg=COLOR_TEXTO_SECUNDARIO)

    def resaltar_pendiente(self, indice: int):
        for i, (lbl_check, lbl_texto) in enumerate(self._filas):
            if i == indice:
                lbl_texto.configure(font=("Segoe UI", 9, "bold"))
            else:
                lbl_texto.configure(font=("Segoe UI", 9, "normal"))

    def mostrar_mensaje(self, texto: str, tipo: str = "info"):
        color = {"exito": COLOR_EXITO, "advertencia": COLOR_ADVERTENCIA,
                  "info": COLOR_TEXTO_SECUNDARIO}.get(tipo, COLOR_TEXTO_SECUNDARIO)
        self._lbl_estado.configure(text=texto, fg=color)


class PracticaCompras:
    """Orquesta la práctica guiada de Compras, ver docstring del módulo."""

    def __init__(self, ventana_principal, on_terminar=None):
        self.ventana = ventana_principal
        self.on_terminar = on_terminar
        self.overlay = OverlayTutorial(ventana_principal)
        self.panel: PanelChecklist | None = None
        self._vista = None
        self._dialogo = None
        self._al_guardar_original = None
        self._guardado_detectado = False
        self._estado = 0     # índice del ítem de checklist pendiente
        self._poll_id = None
        self._activo = False

    # ── Ciclo de vida ────────────────────────────────────────────
    def iniciar(self):
        self._vista = self.ventana.obtener_vista("compras")
        if self._vista is None:
            return self  # el rol actual no tiene acceso a Compras
        self.ventana.navegar("compras")
        self.ventana.update_idletasks()

        self._activo = True
        self.panel = PanelChecklist(self.ventana, _ITEMS, on_salir=self.detener)
        self.panel.marcar_hecho(0)  # "Abrir Compras" ya se cumplió al navegar
        self._estado = 1
        self._actualizar_paso()
        self._tick()
        return self

    def _tick(self):
        if not self._activo:
            return
        try:
            self._verificar()
        except tk.TclError:
            pass
        self._poll_id = self.ventana.after(_INTERVALO_MS, self._tick)

    def _dialogo_activo(self):
        dialogo = getattr(self._vista, "ultimo_dialogo_nueva_orden", None)
        if dialogo is None:
            return None
        try:
            if not dialogo.winfo_exists():
                return None
        except tk.TclError:
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

        # A partir de aquí, si el diálogo se cerró antes de guardar,
        # se detiene la práctica sin bloquear al usuario.
        if dialogo is None and not self._guardado_detectado:
            self.panel.mostrar_mensaje(
                "Cerraste el formulario antes de terminar. Puedes reiniciar "
                "la práctica cuando quieras desde «❓ Ayuda y tutorial».",
                "advertencia",
            )
            self.detener(marcar_progreso=True)
            return

        if self._estado == 2:
            if dialogo is not None and dialogo.combo_proveedor.get():
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
            2: ("🏭", "Selecciona un proveedor",
                "Elige cualquier proveedor real de la lista."),
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
        """Envuelve el callback `al_guardar` del diálogo (sin romper su
        comportamiento normal) para saber cuándo el usuario guardó de
        verdad la orden."""
        if self._dialogo is None or self._al_guardar_original is not None:
            return
        self._al_guardar_original = self._dialogo.al_guardar

        def _envoltura():
            self._guardado_detectado = True
            self._al_guardar_original()

        self._dialogo.al_guardar = _envoltura

    def _finalizar(self):
        if not self._activo:
            return
        self._activo = False
        if self._poll_id is not None:
            try:
                self.ventana.after_cancel(self._poll_id)
            except tk.TclError:
                pass
        if sesion_actual.usuario_id is not None:
            marcar_completado(sesion_actual.usuario_id, _CLAVE_PROGRESO, len(_ITEMS))
        self.overlay.cerrar()
        if self.panel is not None:
            try:
                self.panel.destroy()
            except tk.TclError:
                pass
        if self.on_terminar:
            self.on_terminar()

    def detener(self, marcar_progreso: bool = False):
        """Sale de la práctica en cualquier momento SIN cerrar el
        formulario ni bloquear al usuario."""
        if not self._activo:
            return
        self._activo = False
        if self._poll_id is not None:
            try:
                self.ventana.after_cancel(self._poll_id)
            except tk.TclError:
                pass
        if marcar_progreso and sesion_actual.usuario_id is not None:
            guardar_progreso(sesion_actual.usuario_id, _CLAVE_PROGRESO,
                              self._estado, len(_ITEMS), completado=False)
        self.overlay.cerrar()
        if self.panel is not None:
            try:
                self.panel.destroy()
            except tk.TclError:
                pass
        if self.on_terminar:
            self.on_terminar()
