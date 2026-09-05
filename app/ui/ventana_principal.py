"""
ventana_principal.py
=====================
La ventana principal tiene dos partes:

  - Un menú lateral (izquierda) con un botón por cada módulo que el
    usuario actual tiene permiso de ver (según su rol).
  - Un área de contenido (derecha) que muestra la pantalla del
    módulo seleccionado.

Navegación: TODAS las pantallas se crean una sola vez al arrancar y
se "apilan" unas sobre otras con .place(). Al hacer clic en un botón
del menú se trae al frente (tkraise) la pantalla correspondiente y se
llama a su método refrescar() para mostrar datos actualizados.
"""

import tkinter as tk
from tkinter import ttk

from app.sesion import sesion_actual
from app.seguridad import modulos_visibles
from app.logica_autenticacion import cerrar_sesion
from app.ui.estilos import aplicar_estilos
from app.ui.logo import cargar_logo

from app.ui.vista_dashboard import VistaDashboard
from app.ui.vista_compras import VistaCompras
from app.ui.vista_inventario import VistaInventario
from app.ui.vista_produccion import VistaProduccion
from app.ui.vista_ventas import VistaVentas
from app.ui.vista_costos import VistaCostos
from app.ui.vista_admin import VistaAdmin

# Definición de todos los módulos: (clave interna, texto del botón, clase de la vista)
DEFINICION_MODULOS = [
    ("dashboard",  "🏠  Inicio",                 VistaDashboard),
    ("compras",    "🛒  Módulo de Compras",       VistaCompras),
    ("inventario", "📦  Módulo de Inventario",    VistaInventario),
    ("produccion", "🍺  Módulo de Producción",    VistaProduccion),
    ("ventas",     "💰  Módulo de Ventas",        VistaVentas),
    ("costos",     "📊  Módulo de Costos",        VistaCostos),
    ("admin",      "⚙️   Administración",          VistaAdmin),
]


class VentanaPrincipal(tk.Tk):
    def __init__(self):
        super().__init__()
        self.title(
            f"Cervecería del Valle Sagrado  —  {sesion_actual.nombre_completo} [{sesion_actual.rol}]"
        )
        self.geometry("1200x720")
        self.minsize(980, 620)
        aplicar_estilos(self)

        self.quiere_reiniciar_login = False  # True si el usuario cerró sesión (no la app)

        self._modulos_permitidos = modulos_visibles(sesion_actual.rol)
        self._botones_menu = {}
        self._vistas = {}

        contenedor_principal = ttk.Frame(self)
        contenedor_principal.pack(fill="both", expand=True)

        self._crear_menu_lateral(contenedor_principal)
        self._area_contenido = ttk.Frame(contenedor_principal)
        self._area_contenido.pack(side="left", fill="both", expand=True)

        self._crear_vistas()
        self._navegar("dashboard")

    # ── Menú lateral ─────────────────────────────────────────────
    def _crear_menu_lateral(self, parent):
        menu = ttk.Frame(parent, width=220, padding=10, style="Sidebar.TFrame")
        menu.pack(side="left", fill="y")
        menu.pack_propagate(False)

        tarjeta_logo = ttk.Frame(menu, style="Tarjeta.TFrame", padding=8)
        tarjeta_logo.pack(pady=(0, 10))
        self._imagen_logo_sidebar = cargar_logo(self, tamano="chico")
        ttk.Label(tarjeta_logo, image=self._imagen_logo_sidebar,
                  style="Tarjeta.TLabel").pack()

        for clave, texto, _clase in DEFINICION_MODULOS:
            if clave not in self._modulos_permitidos:
                continue
            boton = ttk.Button(menu, text=texto, style="Sidebar.TButton",
                                command=lambda c=clave: self._navegar(c))
            boton.pack(fill="x", pady=2)
            self._botones_menu[clave] = boton

        relleno = ttk.Frame(menu, style="Sidebar.TFrame")
        relleno.pack(fill="both", expand=True)

        ttk.Separator(menu, orient="horizontal", style="Sidebar.TSeparator").pack(
            fill="x", pady=8)
        ttk.Label(menu, text=sesion_actual.nombre_completo,
                  style="SidebarTitulo.TLabel", font=("Segoe UI", 10, "bold")).pack(anchor="w")
        ttk.Label(menu, text=sesion_actual.rol, style="Sidebar.TLabel").pack(
            anchor="w", pady=(0, 8))
        ttk.Button(menu, text="Cerrar sesión", style="Peligro.TButton",
                   command=self._cerrar_sesion).pack(fill="x")

    # ── Crear todas las vistas permitidas, una encima de otra ───
    def _crear_vistas(self):
        for clave, _texto, clase_vista in DEFINICION_MODULOS:
            if clave not in self._modulos_permitidos:
                continue
            vista = clase_vista(self._area_contenido)
            vista.place(relx=0, rely=0, relwidth=1, relheight=1)
            self._vistas[clave] = vista

    def _navegar(self, clave: str):
        if clave not in self._vistas:
            return
        self._vistas[clave].tkraise()
        if hasattr(self._vistas[clave], "refrescar"):
            self._vistas[clave].refrescar()

    def _cerrar_sesion(self):
        cerrar_sesion()
        self.quiere_reiniciar_login = True
        self.destroy()