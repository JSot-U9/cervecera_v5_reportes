"""ventana_principal.py (PySide6)
==================================
Ventana principal del ERP: sidebar de navegación a la izquierda +
área de contenido (QStackedWidget) a la derecha, más la barra de
estado inferior.

Todos los módulos están migrados a PySide6, incluido el sistema de
tutorial interactivo (con transparencia real en el overlay).
"""

from PySide6.QtCore import Qt, QTimer
from PySide6.QtGui import QKeySequence, QShortcut
from PySide6.QtWidgets import (
    QMainWindow, QWidget, QFrame, QVBoxLayout, QHBoxLayout, QLabel,
    QPushButton, QStackedWidget,
)

from app.sesion import sesion_actual
from app.seguridad import modulos_visibles
from app.logica_autenticacion import cerrar_sesion
from app.logica_configuracion import obtener_parametro
from app.ui.estilos import fuente, poner_clase
from app.ui.logo import cargar_logo
from app.ui.widgets import BarraEstado, ejecutar_con_carga
from app.ui.header import HeaderSuperior
from app.ui.tutorial import abrir_centro_ayuda, tal_vez_iniciar_tutorial_general
from app.ui.dialogo_creditos import mostrar_creditos
from app.logica_inventario import productos_bajo_minimo, lotes_proximos_a_vencer

from app.ui.vista_dashboard import VistaDashboard
from app.ui.vista_compras import VistaCompras
from app.ui.vista_inventario import VistaInventario
from app.ui.vista_produccion import VistaProduccion
from app.ui.vista_ventas import VistaVentas
from app.ui.vista_costos import VistaCostos
from app.ui.vista_admin import VistaAdmin
from app.ui.vista_prediccion import VistaPrediccion
from app.ui.vista_centro_inteligencia import VistaCentroInteligencia

# (clave, icono, etiqueta, clase_de_vista, sección_de_sidebar)
# La sección agrupa el menú lateral tal como pide el rediseño UI/UX
# (OPERACIÓN / ANÁLISIS / INTELIGENCIA / ADMINISTRACIÓN); "" = sin
# grupo (Inicio va suelto, arriba de todo).
DEFINICION_MODULOS = [
    ("dashboard",           "🏠", "Inicio",                  VistaDashboard,             ""),
    ("compras",             "🛒", "Compras",                  VistaCompras,               "OPERACIÓN"),
    ("inventario",          "📦", "Inventario",               VistaInventario,            "OPERACIÓN"),
    ("produccion",          "🍺", "Producción",               VistaProduccion,            "OPERACIÓN"),
    ("ventas",              "💰", "Ventas",                   VistaVentas,                "OPERACIÓN"),
    ("costos",              "📊", "Costos",                   VistaCostos,                "ANÁLISIS"),
    ("prediccion",          "🔮", "Predicción Demanda",       VistaPrediccion,            "ANÁLISIS"),
    ("centro_inteligencia", "🧠", "Centro de Inteligencia",   VistaCentroInteligencia,    "INTELIGENCIA"),
    ("admin",               "⚙️", "Administración",           VistaAdmin,                 "ADMINISTRACIÓN"),
]

# Título y breadcrumb mostrados en el header superior por cada módulo.
_TITULOS_MODULO = {
    "dashboard":            ("Inicio", ["Inicio"]),
    "compras":              ("Compras", ["Operación", "Compras"]),
    "inventario":           ("Inventario", ["Operación", "Inventario"]),
    "produccion":           ("Producción", ["Operación", "Producción"]),
    "ventas":               ("Ventas", ["Operación", "Ventas"]),
    "costos":               ("Costos", ["Análisis", "Costos"]),
    "prediccion":           ("Predicción de Demanda", ["Análisis", "Predicción Demanda"]),
    "centro_inteligencia":  ("Centro de Inteligencia", ["Inteligencia", "Centro de Inteligencia"]),
    "admin":                ("Administración", ["Administración"]),
}

# A qué módulo/tabla/tabla-interna navegar cuando se elige un resultado
# de la búsqueda global (ver app/logica_busqueda.py):
#   tipo -> (modulo, índice de pestaña o None, atributo de TablaDatos)
_MAPA_RESULTADOS_BUSQUEDA = {
    "producto":   ("inventario", 3, "tabla_catalogo"),
    "lote":       ("inventario", 1, "tabla_lotes"),
    "produccion": ("produccion", None, "tabla"),
    "compra":     ("compras", 0, "tabla_ordenes"),
    "proveedor":  ("compras", 1, "tabla_proveedores"),
    "venta":      ("ventas", 0, "tabla_ventas"),
    "cliente":    ("ventas", 1, "tabla_clientes"),
}


class VentanaPrincipal(QMainWindow):
    def __init__(self):
        super().__init__()

        self._nombre_empresa = obtener_parametro("empresa_nombre", "Sistema de Gestión")
        self.setWindowTitle(
            f"{self._nombre_empresa}  —  {sesion_actual.nombre_completo} [{sesion_actual.rol}]"
        )
        self.resize(1280, 760)
        self.setMinimumSize(1000, 640)

        self.quiere_reiniciar_login = False
        self._modulos_permitidos = modulos_visibles(sesion_actual.rol)
        self._botones_menu: dict = {}
        self._vistas: dict = {}
        self._clave_activa: str = ""

        QShortcut(QKeySequence("F5"), self).activated.connect(self._refrescar_activo)
        QShortcut(QKeySequence("Ctrl+K"), self).activated.connect(
            lambda: self._header.enfocar_busqueda())

        central = QWidget()
        self.setCentralWidget(central)
        layout_central = QVBoxLayout(central)
        layout_central.setContentsMargins(0, 0, 0, 0)
        layout_central.setSpacing(0)

        fila = QHBoxLayout()
        fila.setContentsMargins(0, 0, 0, 0)
        fila.setSpacing(0)
        layout_central.addLayout(fila, stretch=1)

        self._crear_sidebar(fila)

        # ── Columna derecha: header superior + contenido de módulo ──
        columna_derecha = QVBoxLayout()
        columna_derecha.setContentsMargins(0, 0, 0, 0)
        columna_derecha.setSpacing(0)
        fila.addLayout(columna_derecha, stretch=1)

        self._header = HeaderSuperior()
        self._header.establecer_usuario(sesion_actual.nombre_completo, sesion_actual.rol)
        self._header.resultadoSeleccionado.connect(self._ir_a_resultado_busqueda)
        self._header.notificacionesClic.connect(lambda: self._navegar("dashboard"))
        columna_derecha.addWidget(self._header)

        self._stack = QStackedWidget()
        columna_derecha.addWidget(self._stack, stretch=1)

        barra_estado = BarraEstado(usuario=sesion_actual.nombre_completo, rol=sesion_actual.rol)
        layout_central.addWidget(barra_estado)

        self._crear_vistas()
        self._navegar("dashboard")
        self._actualizar_notificaciones()

        # Al terminar de construir la ventana, revisa si corresponde
        # mostrar el tour general (primer ingreso de este usuario).
        QTimer.singleShot(600, lambda: tal_vez_iniciar_tutorial_general(self))

    # ── Sidebar ───────────────────────────────────────────────────
    def _crear_sidebar(self, layout_padre):
        from app.ui.estilos import COLOR_SIDEBAR, COLOR_TARJETA, fondo

        sidebar = QFrame()
        sidebar.setFixedWidth(230)
        fondo(sidebar, COLOR_SIDEBAR)
        self._sidebar = sidebar
        layout_padre.addWidget(sidebar)

        sl = QVBoxLayout(sidebar)
        sl.setContentsMargins(12, 12, 12, 10)
        sl.setSpacing(2)

        tarjeta_logo = QFrame()
        fondo(tarjeta_logo, COLOR_TARJETA, "border-radius: 6px;")
        tl = QVBoxLayout(tarjeta_logo)
        tl.setContentsMargins(10, 10, 10, 10)
        lbl_logo = QLabel()
        lbl_logo.setPixmap(cargar_logo("chico"))
        lbl_logo.setAlignment(Qt.AlignCenter)
        tl.addWidget(lbl_logo)
        sl.addWidget(tarjeta_logo)
        sl.addSpacing(4)

        lbl_empresa = QLabel(self._nombre_empresa)
        lbl_empresa.setStyleSheet("background: transparent; color: white;")
        lbl_empresa.setFont(fuente(11, negrita=True))
        lbl_empresa.setAlignment(Qt.AlignCenter)
        lbl_empresa.setWordWrap(True)
        sl.addWidget(lbl_empresa)
        sl.addSpacing(8)

        sl.addWidget(self._separador())

        seccion_actual = None
        for clave, icono, etiqueta, _fabrica, seccion in DEFINICION_MODULOS:
            if clave not in self._modulos_permitidos:
                continue
            if seccion and seccion != seccion_actual:
                sl.addWidget(self._encabezado_seccion(seccion))
            seccion_actual = seccion
            boton = QPushButton(f"{icono}   {etiqueta}")
            poner_clase(boton, "sidebar")
            boton.clicked.connect(lambda checked=False, c=clave: self._navegar(c))
            sl.addWidget(boton)
            self._botones_menu[clave] = boton

        sl.addStretch()

        sl.addWidget(self._separador())

        lbl_usuario = QLabel("👤  " + sesion_actual.nombre_completo)
        lbl_usuario.setStyleSheet("background: transparent; color: white;")
        lbl_usuario.setFont(fuente(9, negrita=True))
        lbl_usuario.setWordWrap(True)
        sl.addWidget(lbl_usuario)
        lbl_rol = QLabel(sesion_actual.rol)
        from app.ui.estilos import COLOR_PRIMARIO_CLARO
        lbl_rol.setStyleSheet(f"background: transparent; color: {COLOR_PRIMARIO_CLARO};")
        lbl_rol.setFont(fuente(8, negrita=True))
        sl.addWidget(lbl_rol)
        sl.addSpacing(6)

        self._btn_ayuda = QPushButton("❓  Ayuda y tutorial")
        poner_clase(self._btn_ayuda, "secundario")
        self._btn_ayuda.clicked.connect(self._abrir_ayuda)
        sl.addWidget(self._btn_ayuda)

        btn_creditos = QPushButton("ℹ️  Créditos")
        poner_clase(btn_creditos, "secundario")
        btn_creditos.clicked.connect(lambda: mostrar_creditos(self))
        sl.addWidget(btn_creditos)

        btn_salir = QPushButton("🚪  Cerrar sesión")
        poner_clase(btn_salir, "peligro")
        btn_salir.clicked.connect(self._cerrar_sesion)
        sl.addWidget(btn_salir)

    def _separador(self) -> QFrame:
        from app.ui.estilos import fondo
        sep = QFrame()
        sep.setFixedHeight(1)
        fondo(sep, "#3D4F28")
        return sep

    def _encabezado_seccion(self, texto: str) -> QLabel:
        """Etiqueta de agrupación del menú lateral (OPERACIÓN, ANÁLISIS,
        INTELIGENCIA, ADMINISTRACIÓN) — separa lo operativo de lo
        administrativo y ayuda al usuario a ubicarse (sección 7)."""
        lbl = QLabel(texto)
        lbl.setStyleSheet("background: transparent; color: #8FA07A;")
        lbl.setFont(fuente(7, negrita=True))
        lbl.setContentsMargins(8, 10, 0, 2)
        return lbl

    def _abrir_ayuda(self):
        abrir_centro_ayuda(self)

    # ── Vistas ────────────────────────────────────────────────────
    def _crear_vistas(self):
        for clave, _icono, _texto, fabrica, _seccion in DEFINICION_MODULOS:
            if clave not in self._modulos_permitidos:
                continue
            vista = fabrica()
            self._stack.addWidget(vista)
            self._vistas[clave] = vista

    def _navegar(self, clave: str):
        if clave not in self._vistas:
            return
        if self._clave_activa and self._clave_activa in self._botones_menu:
            poner_clase(self._botones_menu[self._clave_activa], "sidebar")
        if clave in self._botones_menu:
            poner_clase(self._botones_menu[clave], "sidebarActivo")
        self._clave_activa = clave
        self._stack.setCurrentWidget(self._vistas[clave])
        titulo, migas = _TITULOS_MODULO.get(clave, (clave.title(), [clave.title()]))
        self._header.establecer_titulo(titulo, migas)
        vista = self._vistas[clave]
        if hasattr(vista, "refrescar"):
            ejecutar_con_carga(self._stack, vista.refrescar, mensaje=f"Cargando {titulo}...")
        self._actualizar_notificaciones()

    # ── Búsqueda global (header) ─────────────────────────────────────
    def _ir_a_resultado_busqueda(self, resultado: dict):
        tipo = resultado.get("tipo")
        destino = _MAPA_RESULTADOS_BUSQUEDA.get(tipo)
        if not destino:
            return
        modulo, indice_pestana, atributo_tabla = destino
        if modulo not in self._vistas:
            return
        self._navegar(modulo)
        vista = self._vistas[modulo]
        if indice_pestana is not None and hasattr(vista, "notebook"):
            vista.notebook.setCurrentIndex(indice_pestana)
        tabla = getattr(vista, atributo_tabla, None)
        if tabla is not None and hasattr(tabla, "filtrar"):
            tabla.filtrar(resultado.get("texto_filtro", ""))

    # ── Notificaciones (header) ──────────────────────────────────────
    def _actualizar_notificaciones(self):
        """Cuenta rápida y barata (sin IA) de asuntos que requieren
        atención, para el badge de la campana del header."""
        try:
            from app.basedatos import nueva_sesion
            with nueva_sesion() as db:
                cantidad = len(productos_bajo_minimo(db)) + len(lotes_proximos_a_vencer(db, dias=30))
            self._header.establecer_notificaciones(cantidad)
        except Exception:
            pass

    # ── API pública ───────────────────────────────────────────────
    def navegar(self, clave: str):
        self._navegar(clave)

    def obtener_vista(self, clave: str):
        return self._vistas.get(clave)

    def vista_activa(self):
        return self._vistas.get(self._clave_activa)

    def boton_menu(self, clave: str):
        return self._botones_menu.get(clave)

    def widget_sidebar(self):
        return self._sidebar

    def boton_ayuda(self):
        return self._btn_ayuda

    def nombre_empresa(self) -> str:
        return self._nombre_empresa

    def modulos_permitidos(self) -> set:
        return set(self._modulos_permitidos)

    def _refrescar_activo(self):
        vista = self._vistas.get(self._clave_activa)
        if vista is not None and hasattr(vista, "refrescar"):
            vista.refrescar()

    def _cerrar_sesion(self):
        cerrar_sesion()
        self.quiere_reiniciar_login = True
        self.close()
