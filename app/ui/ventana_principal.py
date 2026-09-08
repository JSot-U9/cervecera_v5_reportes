"""
ventana_principal.py
=====================
Ventana principal del ERP con sidebar mejorado:
- Estado activo persistente (no solo hover)
- Información de usuario/rol en la parte inferior
- Barra de estado inferior
- Etiquetas simplificadas de módulos
"""

import tkinter as tk
from tkinter import ttk

from app.sesion import sesion_actual
from app.seguridad import modulos_visibles
from app.logica_autenticacion import cerrar_sesion
from app.logica_configuracion import obtener_parametro
from app.ui.estilos import aplicar_estilos, COLOR_SIDEBAR, COLOR_PRIMARIO, COLOR_SIDEBAR_SELECCIONADO
from app.ui.logo import cargar_logo
from app.ui.widgets import BarraEstado
from app.ui.dialogo_creditos import mostrar_creditos

from app.ui.vista_dashboard import VistaDashboard
from app.ui.vista_compras import VistaCompras
from app.ui.vista_inventario import VistaInventario
from app.ui.vista_produccion import VistaProduccion
from app.ui.vista_ventas import VistaVentas
from app.ui.vista_costos import VistaCostos
from app.ui.vista_admin import VistaAdmin

# Módulos: (clave, ícono, etiqueta, clase)
DEFINICION_MODULOS = [
    ("dashboard",  "🏠", "Inicio",         VistaDashboard),
    ("compras",    "🛒", "Compras",         VistaCompras),
    ("inventario", "📦", "Inventario",      VistaInventario),
    ("produccion", "🍺", "Producción",      VistaProduccion),
    ("ventas",     "💰", "Ventas",          VistaVentas),
    ("costos",     "📊", "Costos",          VistaCostos),
    ("admin",      "⚙️", "Administración",  VistaAdmin),
]


class VentanaPrincipal(tk.Tk):
    def __init__(self):
        super().__init__()

        self._nombre_empresa = obtener_parametro("empresa_nombre", "Sistema de Gestión")
        self.title(
            f"{self._nombre_empresa}  —  "
            f"{sesion_actual.nombre_completo} [{sesion_actual.rol}]"
        )
        self.geometry("1280x760")
        self.minsize(1000, 640)
        aplicar_estilos(self)

        self.quiere_reiniciar_login = False
        self._modulos_permitidos = modulos_visibles(sesion_actual.rol)
        self._botones_menu: dict[str, ttk.Button] = {}
        self._vistas: dict = {}
        self._clave_activa: str = ""

        # Atajos de teclado globales
        self.bind("<F5>", lambda e: self._refrescar_activo())

        # Layout principal: sidebar | contenido
        contenedor_principal = ttk.Frame(self)
        contenedor_principal.pack(fill="both", expand=True)

        self._crear_sidebar(contenedor_principal)
        self._area_contenido = ttk.Frame(contenedor_principal)
        self._area_contenido.pack(side="left", fill="both", expand=True)

        # Barra de estado inferior
        barra_estado = BarraEstado(
            self,
            usuario=sesion_actual.nombre_completo,
            rol=sesion_actual.rol
        )
        barra_estado.pack(side="bottom", fill="x")

        self._crear_vistas()
        self._navegar("dashboard")

    # ── Sidebar ───────────────────────────────────────────────────
    def _crear_sidebar(self, parent):
        sidebar = ttk.Frame(parent, width=230, style="Sidebar.TFrame")
        sidebar.pack(side="left", fill="y")
        sidebar.pack_propagate(False)

        # Logo y nombre de empresa
        tarjeta_logo = ttk.Frame(sidebar, style="Tarjeta.TFrame", padding=(10, 10))
        tarjeta_logo.pack(padx=12, pady=(12, 4), fill="x")
        self._imagen_logo_sidebar = cargar_logo(self, tamano="chico")
        ttk.Label(tarjeta_logo, image=self._imagen_logo_sidebar,
                  style="Tarjeta.TLabel").pack()

        ttk.Label(
            sidebar,
            text=self._nombre_empresa,
            style="SidebarTitulo.TLabel",
            wraplength=200,
            justify="center",
            anchor="center",
        ).pack(pady=(4, 8), padx=8)

        # Separador
        sep1 = tk.Frame(sidebar, bg="#3D4F28", height=1)
        sep1.pack(fill="x", padx=12, pady=(0, 6))

        # Botones de navegación
        for clave, icono, etiqueta, _clase in DEFINICION_MODULOS:
            if clave not in self._modulos_permitidos:
                continue
            texto = f"{icono}   {etiqueta}"
            boton = ttk.Button(
                sidebar,
                text=texto,
                style="Sidebar.TButton",
                command=lambda c=clave: self._navegar(c)
            )
            boton.pack(fill="x", padx=8, pady=2)
            self._botones_menu[clave] = boton

        # Relleno flexible
        ttk.Frame(sidebar, style="Sidebar.TFrame").pack(fill="both", expand=True)

        # Separador antes de usuario
        sep2 = tk.Frame(sidebar, bg="#3D4F28", height=1)
        sep2.pack(fill="x", padx=12, pady=8)

        # Sección usuario
        frame_usuario = ttk.Frame(sidebar, style="Sidebar.TFrame", padding=(12, 6))
        frame_usuario.pack(fill="x")

        ttk.Label(frame_usuario, text="👤  " + sesion_actual.nombre_completo,
                  style="SidebarTitulo.TLabel",
                  font=("Segoe UI", 9, "bold"),
                  wraplength=190).pack(anchor="w")
        ttk.Label(frame_usuario, text=sesion_actual.rol,
                  style="SidebarRol.TLabel").pack(anchor="w", pady=(0, 6))

        ttk.Button(
            sidebar,
            text="ℹ️  Créditos",
            style="Secundario.TButton",
            command=lambda: mostrar_creditos(self)
        ).pack(fill="x", padx=8, pady=(0, 4))

        ttk.Button(
            sidebar,
            text="🚪  Cerrar sesión",
            style="Peligro.TButton",
            command=self._cerrar_sesion
        ).pack(fill="x", padx=8, pady=(0, 10))

    # ── Vistas ────────────────────────────────────────────────────
    def _crear_vistas(self):
        for clave, _icono, _texto, clase_vista in DEFINICION_MODULOS:
            if clave not in self._modulos_permitidos:
                continue
            vista = clase_vista(self._area_contenido)
            vista.place(relx=0, rely=0, relwidth=1, relheight=1)
            self._vistas[clave] = vista

    def _navegar(self, clave: str):
        if clave not in self._vistas:
            return
        # Restaurar estilo del botón anterior
        if self._clave_activa and self._clave_activa in self._botones_menu:
            self._botones_menu[self._clave_activa].configure(style="Sidebar.TButton")
        # Marcar botón activo
        if clave in self._botones_menu:
            self._botones_menu[clave].configure(style="SidebarActivo.TButton")
        self._clave_activa = clave
        self._vistas[clave].tkraise()
        if hasattr(self._vistas[clave], "refrescar"):
            self._vistas[clave].refrescar()

    def _refrescar_activo(self):
        if self._clave_activa and self._clave_activa in self._vistas:
            vista = self._vistas[self._clave_activa]
            if hasattr(vista, "refrescar"):
                vista.refrescar()

    def _cerrar_sesion(self):
        cerrar_sesion()
        self.quiere_reiniciar_login = True
        self.destroy()
