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
    QPushButton, QStackedWidget, QScrollArea,
)

from app.sesion import sesion_actual
from app.seguridad import modulos_visibles
from app.logica_autenticacion import cerrar_sesion
from app.logica_configuracion import obtener_parametro
from app.ui.estilos import fuente, poner_clase
from app.ui.logo import cargar_logo, EtiquetaLogoResponsiva
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
    ("ventas",              "💰", "Realizar ventas",         VistaVentas,                "OPERACIÓN"),
    ("costos",              "📊", "Reportes de ventas",      VistaCostos,                "ANÁLISIS"),
    # "prediccion" ya NO es un módulo aparte del sidebar (sección G del
    # reporte de bugs): su vista completa ahora vive como una pestaña
    # dentro de Centro de Inteligencia (ver vista_centro_inteligencia.py).
    ("centro_inteligencia", "🧠", "Centro de Inteligencia",   VistaCentroInteligencia,    "INTELIGENCIA"),
    ("admin",               "⚙️", "Administración",           VistaAdmin,                 "ADMINISTRACIÓN"),
]

# Título y breadcrumb mostrados en el header superior por cada módulo.
_TITULOS_MODULO = {
    # El segundo elemento de cada tupla es la migaja de pan (breadcrumb)
    # bajo el título. Antes repetía literalmente el nombre del módulo
    # ("Inicio" bajo "Inicio", "Compras" bajo "Compras"), lo cual un
    # tester marcó como redundante y poco informativo sobre qué se
    # hace en cada módulo. Ahora el último segmento nombra la operación
    # principal de ese módulo en vez de repetir su nombre.
    "dashboard":            ("Inicio", ["Centro de operaciones"]),
    "compras":              ("Compras", ["Operación", "Órdenes de compra"]),
    "inventario":           ("Inventario", ["Operación", "Stock y lotes"]),
    "produccion":           ("Producción", ["Operación", "Órdenes de producción"]),
    "ventas":               ("Realizar ventas", ["Operación", "Órdenes de venta"]),
    "costos":               ("Reportes de ventas", ["Análisis", "Costos y márgenes"]),
    "centro_inteligencia":  ("Centro de Inteligencia", ["Inteligencia", "Recomendaciones y predicciones"]),
    "admin":                ("Administración", ["Administración", "Datos de la empresa y usuarios"]),
}

# A qué módulo/tabla/tabla-interna navegar cuando se elige un resultado
# de la búsqueda global (ver app/logica_busqueda.py):
#   tipo -> (modulo, índice de pestaña o None, atributo de TablaDatos)
_MAPA_RESULTADOS_BUSQUEDA = {
    "producto":   ("inventario", 3, "tabla_catalogo"),
    # "stock": alertas de stock bajo del Dashboard. Van a la pestaña
    # "Stock Actual" (índice 0) y no al catálogo, porque lo que el
    # usuario quiere comprobar ahí es justamente la cantidad disponible.
    "stock":      ("inventario", 0, "tabla_stock"),
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

        # El sidebar tiene MUCHOS elementos de alto fijo apilados (la
        # tarjeta del logo, cada botón de menú, la info del usuario,
        # los botones de abajo). Si la ventana se hace más baja de lo
        # que todo eso necesita, Qt no puede simplemente "inventar"
        # espacio — y en vez de recortar limpio, el motor de layout
        # termina comprimiendo el conjunto de forma despareja, lo que
        # hacía que el nombre de la empresa se dibujara ENCIMA de la
        # tarjeta del logo (el bug reportado: se veía bien con la
        # ventana grande, pero se corrompía al achicarla). La solución
        # correcta no es adivinar un tamaño más chico para el logo —
        # es dejar que el sidebar tenga scroll cuando de verdad no
        # entra todo, igual que cualquier menú de navegación real.
        scroll = QScrollArea()
        scroll.setWidgetResizable(True)
        scroll.setFrameShape(QFrame.NoFrame)
        scroll.setHorizontalScrollBarPolicy(Qt.ScrollBarAlwaysOff)
        scroll.setVerticalScrollBarPolicy(Qt.ScrollBarAsNeeded)
        scroll.setStyleSheet(
            f"QScrollArea {{ background-color: {COLOR_SIDEBAR}; border: none; }}"
            f"QScrollArea > QWidget > QWidget {{ background-color: {COLOR_SIDEBAR}; }}"
            f"QScrollBar:vertical {{ background-color: {COLOR_SIDEBAR}; width: 8px; margin: 0; }}"
            f"QScrollBar::handle:vertical {{ background-color: #3D4F28; border-radius: 4px; min-height: 24px; }}"
            f"QScrollBar::add-line:vertical, QScrollBar::sub-line:vertical {{ height: 0px; }}"
        )
        layout_sidebar_externo = QVBoxLayout(sidebar)
        layout_sidebar_externo.setContentsMargins(0, 0, 0, 0)
        layout_sidebar_externo.addWidget(scroll)
        self._scroll_sidebar = scroll

        contenido = QWidget()
        scroll.setWidget(contenido)

        sl = QVBoxLayout(contenido)
        sl.setContentsMargins(12, 12, 12, 10)
        sl.setSpacing(2)

        tarjeta_logo = QFrame()
        fondo(tarjeta_logo, COLOR_TARJETA, "border-radius: 6px;")
        tl = QVBoxLayout(tarjeta_logo)
        tl.setContentsMargins(10, 10, 10, 10)
        # Espacio real disponible: 230 (sidebar) − 24 (márgenes del
        # sidebar) − 20 (márgenes de la tarjeta) = 186 px.
        #
        # EtiquetaLogoResponsiva (y no un QPixmap escalado una sola
        # vez): reescala el logo cada vez que SU espacio cambia, en
        # vez de fijar una escala calculada aquí una única vez. Así,
        # si el sidebar alguna vez cambia de ancho (otro DPI, un
        # sidebar colapsable a futuro), el logo se sigue ajustando
        # solo y nunca vuelve a quedar recortado contra el nombre de
        # la empresa que tiene debajo.
        ANCHO_UTIL_LOGO = 186
        lbl_logo = EtiquetaLogoResponsiva("chico")
        # El ANCHO lo decide el layout (política Expanding, por
        # defecto en QLabel); solo se fija el ALTO del contenedor,
        # calculado a partir del ancho útil actual para reservarle un
        # espacio consistente sin necesidad de adivinar un tamaño
        # exacto de pixmap.
        alto_logo = lbl_logo.alto_para_ancho(ANCHO_UTIL_LOGO)
        tarjeta_logo.setFixedHeight(alto_logo + 20)
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
        # Lazy: se guarda solo la fábrica; cada vista se instancia la
        # primera vez que se navega a ella, no todas al arrancar.
        # Esto elimina el coste de construir (y ejecutar refrescar() en)
        # módulos que el usuario puede que nunca abra en esa sesión.
        self._fabricas: dict = {}
        for clave, _icono, _texto, fabrica, _seccion in DEFINICION_MODULOS:
            if clave not in self._modulos_permitidos:
                continue
            self._fabricas[clave] = fabrica

    def _obtener_o_crear_vista(self, clave: str):
        """Devuelve la vista ya construida, o la construye ahora si es la
        primera vez que se navega a ese módulo."""
        if clave not in self._vistas:
            fabrica = self._fabricas.get(clave)
            if fabrica is None:
                return None
            vista = fabrica()
            self._stack.addWidget(vista)
            self._vistas[clave] = vista
        return self._vistas[clave]

    def _navegar(self, clave: str):
        if clave not in self._fabricas:
            return
        if self._clave_activa and self._clave_activa in self._botones_menu:
            poner_clase(self._botones_menu[self._clave_activa], "sidebar")
        if clave in self._botones_menu:
            poner_clase(self._botones_menu[clave], "sidebarActivo")

        ya_activa = (clave == self._clave_activa)
        self._clave_activa = clave

        vista = self._obtener_o_crear_vista(clave)
        if vista is None:
            return

        self._stack.setCurrentWidget(vista)
        titulo, migas = _TITULOS_MODULO.get(clave, (clave.title(), [clave.title()]))
        self._header.establecer_titulo(titulo, migas)

        # No re-ejecutar refrescar() si el usuario ya estaba aquí: evita
        # disparar consultas a BD y reconstruir tablas sin motivo cada vez
        # que el tutorial navega al módulo activo (el caso más común de
        # "miles de iteraciones" que mencionaste).
        if not ya_activa and hasattr(vista, "refrescar"):
            ejecutar_con_carga(self._stack, vista.refrescar, mensaje=f"Cargando {titulo}...")
        self._actualizar_notificaciones()

    # ── Búsqueda global (header) ─────────────────────────────────────
    def ir_a_resultado(self, resultado: dict):
        """API pública: navega al módulo correspondiente y deja su tabla
        filtrada por el recurso indicado (dict con 'tipo' y 'texto_filtro').
        La usa tanto el buscador global del header como las tarjetas de
        "Requiere tu atención" del Dashboard, para no duplicar el mapeo
        tipo -> (módulo, pestaña, tabla)."""
        self._ir_a_resultado_busqueda(resultado)

    def _ir_a_resultado_busqueda(self, resultado: dict):
        """Lleva al usuario hasta el recurso exacto SIN esconder el resto.

        Antes esto llamaba a `tabla.filtrar(texto)`, lo que dejaba la
        tabla reducida a una sola fila: no se veía en qué posición
        estaba el lote respecto a los demás y no había forma evidente de
        volver a la tabla completa. Ahora se resalta y se hace scroll
        hasta la fila, dejando todo el contexto a la vista. Solo si el
        recurso no aparece entre las filas cargadas se recurre al filtro
        (y se avisa en la barra de estado cómo deshacerlo).
        """
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
        texto = resultado.get("texto_filtro", "")
        if tabla is None or not texto:
            return

        if hasattr(tabla, "resaltar") and tabla.resaltar(texto):
            return

        # Plan B: no está entre las filas visibles (p. ej. la pestaña
        # muestra solo lotes disponibles). Se filtra, pero avisando.
        if hasattr(tabla, "filtrar"):
            tabla.filtrar(texto)
            self._avisar_filtro_aplicado(vista, texto, tabla)

    def _avisar_filtro_aplicado(self, vista, texto: str, tabla):
        """Cuando hay que filtrar de verdad, el usuario tiene que poder
        volver a la tabla completa de un clic."""
        from PySide6.QtWidgets import QMessageBox
        caja = QMessageBox(self)
        caja.setWindowTitle("Vista filtrada")
        caja.setIcon(QMessageBox.Information)
        caja.setText(
            f"La tabla se filtró por «{texto}» porque ese registro no aparecía "
            f"en la lista completa que estaba cargada."
        )
        boton_ver_todo = caja.addButton("Ver tabla completa", QMessageBox.AcceptRole)
        caja.addButton("Mantener el filtro", QMessageBox.RejectRole)
        caja.exec()
        if caja.clickedButton() is boton_ver_todo:
            tabla.filtrar("")

    # ── Notificaciones (header) ──────────────────────────────────────
    def _actualizar_notificaciones(self):
        """Cuenta rápida y barata (sin IA) de asuntos que requieren
        atención, para el badge de la campana del header. Debe reflejar
        exactamente lo mismo que ve el usuario en la sección "Requiere tu
        atención" del Dashboard (misma fuente de datos)."""
        try:
            from app.basedatos import nueva_sesion
            with nueva_sesion() as db:
                cantidad = len(productos_bajo_minimo(db)) + len(lotes_proximos_a_vencer(db, dias=30))
            self._header.establecer_notificaciones(cantidad)
        except Exception:
            # Antes este error se silenciaba por completo (`except: pass`),
            # lo que podía dejar el número de la campana "congelado" en un
            # valor viejo e incorrecto para siempre si la consulta empezaba
            # a fallar (p. ej. con datasets grandes), sin ninguna pista de
            # que algo estaba mal. Se deja constancia en el log y se limpia
            # el badge en vez de mostrar una cifra que ya no es real.
            import logging
            logging.getLogger(__name__).exception(
                "No se pudo calcular el número de notificaciones pendientes."
            )
            self._header.establecer_notificaciones(0)

    # ── API pública ───────────────────────────────────────────────
    def navegar(self, clave: str):
        self._navegar(clave)

    def obtener_vista(self, clave: str):
        return self._vistas.get(clave)

    def actualizar_pestana_interna(self, nombre_pestana: str):
        """Refleja en el header la pestaña interna activa dentro del
        módulo actual (ej. "Inventario · Lotes FIFO"), sin volver a
        navegar ni reconstruir la vista. Antes el header solo se
        actualizaba al cambiar de MÓDULO (sidebar): cambiar de pestaña
        interna dentro de un mismo módulo (de "Stock Actual" a
        "Lotes" en Inventario, por ejemplo) no se reflejaba en ningún
        lado fuera de la pestaña misma.

        Cada vista con pestañas internas (self.notebook) llama a esto
        desde su propio manejador de currentChanged.
        """
        titulo_base, migas_base = _TITULOS_MODULO.get(
            self._clave_activa, (self._clave_activa or "", [self._clave_activa or ""])
        )
        if not nombre_pestana:
            self._header.establecer_titulo(titulo_base, migas_base)
            return
        self._header.establecer_titulo(
            f"{titulo_base} · {nombre_pestana}", migas_base + [nombre_pestana]
        )

    def vista_activa(self):
        return self._vistas.get(self._clave_activa)

    def boton_menu(self, clave: str):
        boton = self._botones_menu.get(clave)
        # Si el sidebar tiene scroll activo (ventana baja, ver
        # _crear_sidebar) y el tutorial va a resaltar un botón que
        # está fuera del área visible, hay que desplazarlo a la vista
        # primero — si no, el overlay terminaría señalando un botón
        # que el usuario no puede ver.
        if boton is not None and hasattr(self, "_scroll_sidebar"):
            self._scroll_sidebar.ensureWidgetVisible(boton, 0, 40)
        return boton

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
