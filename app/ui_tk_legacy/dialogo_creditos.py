"""
dialogo_creditos.py
====================
Ventana emergente "Acerca de / Créditos" del sistema.

Muestra el logo de la empresa y los datos de autoría del proyecto
(autor, institución, lugar y año). Se puede abrir tanto desde la
pantalla de inicio de sesión como desde el menú lateral de la
ventana principal.
"""

import tkinter as tk
from tkinter import ttk

from app.ui.estilos import (
    COLOR_PRIMARIO, COLOR_TEXTO, COLOR_TEXTO_SECUNDARIO, COLOR_FONDO,
)
from app.ui.widgets import centrar_ventana
from app.ui.logo import cargar_logo

# ══════════════════════════════════════════════════════════════════
#  DATOS DE CRÉDITOS DEL PROYECTO
# ══════════════════════════════════════════════════════════════════
AUTOR = "Kevin Daniel Zuñiga Chacon"
INSTITUCION = "Universidad Andina del Cusco"
LUGAR = "Cusco - Perú"
ANIO = "2026"


class DialogoCreditos(tk.Toplevel):
    """Diálogo modal de "Acerca de" con los créditos del sistema."""

    def __init__(self, parent):
        super().__init__(parent)
        self.title("Créditos")
        self.resizable(False, False)
        self.configure(bg=COLOR_FONDO)
        self.transient(parent)
        self.grab_set()

        # Franja superior de color con el logo
        franja = tk.Frame(self, bg=COLOR_PRIMARIO, pady=18, padx=20)
        franja.pack(fill="x")
        self._imagen_logo = cargar_logo(self, tamano="chico")
        tk.Label(franja, image=self._imagen_logo, bg=COLOR_PRIMARIO).pack()

        # Cuerpo con los datos de créditos
        cuerpo = ttk.Frame(self, padding=(28, 20))
        cuerpo.pack(fill="both", expand=True)

        ttk.Label(
            cuerpo, text="Créditos", font=("Segoe UI", 14, "bold"),
            foreground=COLOR_TEXTO,
        ).pack(anchor="center", pady=(0, 14))

        self._fila(cuerpo, "Autor", AUTOR)
        self._fila(cuerpo, "Institución", INSTITUCION)
        self._fila(cuerpo, "Lugar", LUGAR)
        self._fila(cuerpo, "Año", ANIO)

        ttk.Button(
            cuerpo, text="Cerrar", command=self.destroy,
        ).pack(fill="x", pady=(18, 0))

        centrar_ventana(self, 380, 340)
        self.bind("<Escape>", lambda e: self.destroy())

    def _fila(self, parent, etiqueta: str, valor: str):
        fila = ttk.Frame(parent)
        fila.pack(fill="x", pady=(0, 8))
        ttk.Label(
            fila, text=f"{etiqueta}:", font=("Segoe UI", 10, "bold"),
            foreground=COLOR_TEXTO_SECUNDARIO,
        ).pack(anchor="w")
        ttk.Label(
            fila, text=valor, font=("Segoe UI", 11),
            foreground=COLOR_TEXTO, wraplength=320, justify="left",
        ).pack(anchor="w")


def mostrar_creditos(parent):
    """Abre el diálogo de créditos como ventana modal."""
    DialogoCreditos(parent)
