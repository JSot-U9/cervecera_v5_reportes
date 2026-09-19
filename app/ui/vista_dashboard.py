"""vista_dashboard.py (PySide6)
================================
Centro de operaciones. Responde tres preguntas (sección 9 del
rediseño UI/UX):

    ¿Cómo está la operación?        -> Indicadores generales
    ¿Qué requiere mi atención?      -> Tarjetas accionables (clic -> módulo)
    ¿Qué debería hacer ahora?       -> Acciones rápidas

Las tarjetas de "Requiere tu atención" usan solo consultas baratas de
base de datos (sin modelos de IA) para que el Dashboard cargue rápido
cada vez que se navega a él; el análisis pesado (reposición
inteligente, merma, demanda) vive en el Centro de Inteligencia y se
enlaza desde aquí, no se recalcula en cada visita.
"""

from datetime import date

from PySide6.QtCore import Qt, QTimer
from PySide6.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QGridLayout, QLabel,
    QScrollArea, QPushButton,
)

from app.basedatos import nueva_sesion
from app.modelos import Producto, Proveedor, Cliente, OrdenVenta, OrdenProduccion
from app.logica_inventario import productos_bajo_minimo, lotes_proximos_a_vencer
from app.logica_configuracion import obtener_parametro_numerico
from app.sesion import sesion_actual
from app.seguridad import puede
from app.ui.widgets import EncabezadoModulo, TarjetaKPI, TarjetaAccion, EstadoVacio
from app.ui.estilos import COLOR_TEXTO_SECUNDARIO, fuente, poner_clase


_PRIORIDAD_SEVERIDAD = {"critico": 0, "riesgo": 1, "atencion": 2, "info": 3}


class VistaDashboard(QWidget):
    def __init__(self, parent=None):
        super().__init__(parent)
        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(0)

        layout.addWidget(EncabezadoModulo(
            "Inicio — Centro de Operaciones",
            "Cómo está la operación, qué requiere atención y qué puedes hacer ahora",
            icono="🏠",
        ))

        scroll = QScrollArea()
        scroll.setWidgetResizable(True)
        scroll.setFrameShape(QScrollArea.NoFrame)
        layout.addWidget(scroll, stretch=1)
        # Guardar referencia al scroll para detectar desplazamiento y
        # cargar las tarjetas de "Requiere tu atención" de forma diferida.
        self._scroll = scroll
        self._scroll_conectado = False

        cuerpo = QWidget()
        scroll.setWidget(cuerpo)
        self._cuerpo_layout = QVBoxLayout(cuerpo)
        self._cuerpo_layout.setContentsMargins(20, 16, 20, 20)
        self._cuerpo_layout.setSpacing(6)

        self._construir_ui()
        self.refrescar()

    def _titulo_seccion(self, texto: str) -> QLabel:
        lbl = QLabel(texto)
        lbl.setFont(fuente(9, negrita=True))
        lbl.setStyleSheet(f"color: {COLOR_TEXTO_SECUNDARIO};")
        return lbl

    # ── Construcción de la UI (estática; los datos llegan en refrescar) ──
    def _construir_ui(self):
        cl = self._cuerpo_layout

        cl.addWidget(self._titulo_seccion("INDICADORES GENERALES"))
        fila1 = QGridLayout()
        fila1.setSpacing(8)
        self.kpi_productos = TarjetaKPI("Productos activos", icono="📦")
        self.kpi_proveedores = TarjetaKPI("Proveedores registrados", icono="🏭")
        self.kpi_clientes = TarjetaKPI("Clientes registrados", icono="👥")
        self.kpi_ventas = TarjetaKPI("Órdenes de venta", icono="🧾")
        self.kpi_produccion_activa = TarjetaKPI("Lotes en producción", variante="advertencia", icono="🍺")
        self.kpi_ingresos_mes = TarjetaKPI("Ingresos del mes", variante="exito", icono="💰")
        for i, t in enumerate((self.kpi_productos, self.kpi_proveedores, self.kpi_clientes,
                                self.kpi_ventas, self.kpi_produccion_activa, self.kpi_ingresos_mes)):
            fila1.addWidget(t, i // 3, i % 3)
            fila1.setColumnStretch(i % 3, 1)
        cl.addLayout(fila1)
        cl.addSpacing(14)

        # ── Requiere tu atención ─────────────────────────────────────
        fila_titulo_atencion = QHBoxLayout()
        fila_titulo_atencion.addWidget(self._titulo_seccion("REQUIERE TU ATENCIÓN"))
        fila_titulo_atencion.addStretch()
        btn_ver_inteligencia = QPushButton("🧠  Ver recomendaciones de reposición")
        poner_clase(btn_ver_inteligencia, "accionSecundaria")
        btn_ver_inteligencia.clicked.connect(lambda: self._navegar("centro_inteligencia"))
        fila_titulo_atencion.addWidget(btn_ver_inteligencia)
        cl.addLayout(fila_titulo_atencion)

        self._layout_atencion = QVBoxLayout()
        self._layout_atencion.setSpacing(6)
        cl.addLayout(self._layout_atencion)
        cl.addSpacing(14)

        # ── Acciones rápidas ─────────────────────────────────────────
        cl.addWidget(self._titulo_seccion("ACCIONES RÁPIDAS"))
        self._layout_acciones = QHBoxLayout()
        self._layout_acciones.setSpacing(8)
        self._construir_acciones_rapidas()
        cl.addLayout(self._layout_acciones)
        cl.addSpacing(14)

        # ── Capital de referencia ────────────────────────────────────
        fila3 = QHBoxLayout()
        self.kpi_capital_inicial = TarjetaKPI("Capital inicial asignado (S/)")
        self.kpi_capital_inicial.setFixedWidth(220)
        fila3.addWidget(self.kpi_capital_inicial)
        lbl_capital = QLabel(
            "Monto de referencia con el que arrancó el negocio.\n"
            "No incluye ingresos ni egresos posteriores."
        )
        lbl_capital.setStyleSheet(f"color: {COLOR_TEXTO_SECUNDARIO};")
        lbl_capital.setFont(fuente(9))
        fila3.addWidget(lbl_capital)
        fila3.addStretch()
        cl.addLayout(fila3)

        cl.addStretch()

    def _construir_acciones_rapidas(self):
        rol = sesion_actual.rol
        acciones = []
        if puede(rol, "ventas", "crear"):
            acciones.append(("＋  Nueva venta", "ventas", "_abrir_nueva_venta"))
        if puede(rol, "compras", "crear"):
            acciones.append(("＋  Nueva compra", "compras", "_abrir_nueva_orden"))
        if puede(rol, "produccion", "crear"):
            acciones.append(("＋  Nueva producción", "produccion", "_abrir_nueva_orden"))
        if puede(rol, "inventario", "ajuste") or puede(rol, "inventario", "ver"):
            acciones.append(("📦  Movimiento de inventario", "inventario", None))
        if puede(rol, "costos", "ver"):
            acciones.append(("📊  Nuevo reporte", "costos", "_abrir_dialogo_reporte"))

        if not acciones:
            lbl = QLabel("No tienes acciones rápidas disponibles con tu rol actual.")
            lbl.setStyleSheet(f"color: {COLOR_TEXTO_SECUNDARIO};")
            lbl.setFont(fuente(9))
            self._layout_acciones.addWidget(lbl)
            self._layout_acciones.addStretch()
            return

        for etiqueta, modulo, metodo in acciones:
            btn = QPushButton(etiqueta)
            btn.clicked.connect(
                lambda checked=False, m=modulo, met=metodo: self._ejecutar_accion_rapida(m, met))
            self._layout_acciones.addWidget(btn)
        self._layout_acciones.addStretch()

    def _navegar(self, clave: str):
        ventana = self.window()
        if hasattr(ventana, "navegar"):
            ventana.navegar(clave)

    def _ejecutar_accion_rapida(self, modulo: str, metodo):
        ventana = self.window()
        if not hasattr(ventana, "navegar"):
            return
        ventana.navegar(modulo)
        if metodo:
            vista = ventana.obtener_vista(modulo) if hasattr(ventana, "obtener_vista") else None
            accion = getattr(vista, metodo, None) if vista else None
            if callable(accion):
                accion()

    def _limpiar_layout(self, layout):
        while layout.count():
            item = layout.takeAt(0)
            w = item.widget()
            if w is not None:
                w.deleteLater()
            sub_layout = item.layout()
            if sub_layout is not None:
                self._limpiar_layout(sub_layout)

    # ── Render progresivo de las tarjetas "Requiere tu atención" ──
    #
    # La versión anterior mostraba 4 tarjetas y cargaba más solo cuando
    # el usuario hacía scroll hasta el final del área visible. Como el
    # bloque de 4 casi nunca llegaba a desbordar la pantalla, ese evento
    # no se disparaba nunca y en la práctica el Dashboard mostraba
    # únicamente los 4 elementos más prioritarios, escondiendo el resto
    # de los productos escasos.
    #
    # Ahora se muestran TODOS, pero repartidos en tandas encadenadas con
    # QTimer: cada tanda se crea en un ciclo distinto del bucle de
    # eventos, así que la ventana nunca se congela aunque haya cientos
    # de alertas. Sobre los primeros _VISIBLES_INICIAL se coloca además
    # un botón "Ver los N restantes" para no abrumar de entrada.
    _BLOQUE_CARGA = 25
    _VISIBLES_INICIAL = 8

    def _cancelar_carga_progresiva(self):
        """Invalida cualquier cadena de QTimer pendiente de una llamada
        anterior a _repintar_atencion. Necesario porque F5 (refrescar) o
        una nueva navegación pueden disparar un repintado mientras la
        tanda anterior todavía se estaba completando en segundo plano;
        sin esto, las tarjetas viejas seguirían apareciendo por encima
        del contenido nuevo."""
        self._generacion_atencion = getattr(self, "_generacion_atencion", 0) + 1
        self._pendientes_data = []
        self._pendientes_index = 0

    def _repintar_atencion(self, bajos: list, por_vencer: list):
        self._limpiar_layout(self._layout_atencion)
        self._cancelar_carga_progresiva()
        hoy = date.today()

        pendientes = []  # lista de dicts con la info necesaria para crear la tarjeta

        for b in bajos:
            severidad = "critico" if b["stock"] <= 0 else "riesgo"
            descripcion = (
                f"Stock actual: {b['stock']:.1f} {b['unidad']}  "
                f"(mínimo requerido: {b['minimo']})."
            )
            pendientes.append({
                "titulo": f"{b['nombre']} — stock bajo el mínimo",
                "descripcion": descripcion,
                "severidad": severidad,
                "texto_boton": "Ver en stock",
                # tipo/texto_filtro: para poder llevar al usuario directo a la
                # fila exacta en Inventario, no solo abrir el módulo genérico.
                # "stock" abre la pestaña "Stock Actual", que es donde se
                # comprueba la cantidad disponible frente al mínimo.
                "tipo": "stock",
                "texto_filtro": b["codigo"] or b["nombre"],
            })

        for lote in por_vencer:
            fv = lote["fecha_vencimiento"]
            dias_restantes = (fv - hoy).days if fv else None
            critico = dias_restantes is not None and dias_restantes <= 7
            severidad = "critico" if critico else "atencion"
            if fv:
                descripcion = f"Vence el {fv.strftime('%d/%m/%Y')} ({dias_restantes} días)."
            else:
                descripcion = "Fecha de vencimiento no registrada."
            pendientes.append({
                "titulo": f"{lote['nombre']} — lote {lote['numero']} próximo a vencer",
                "descripcion": descripcion,
                "severidad": severidad,
                "texto_boton": "Ver lote",
                "tipo": "lote",
                "texto_filtro": lote["numero"],
            })

        if not pendientes:
            self._layout_atencion.addWidget(EstadoVacio(
                "✅", "Todo en orden",
                "No hay productos con stock bajo el mínimo ni lotes próximos a vencer "
                "en los próximos 30 días.",
            ))
            return

        # Priorizar
        pendientes.sort(key=lambda d: _PRIORIDAD_SEVERIDAD.get(d.get("severidad"), 9))

        self._pendientes_data = pendientes
        generacion = self._generacion_atencion

        # Primera tanda: se muestra de inmediato para que el Dashboard
        # se sienta instantáneo (antes esto era, sin querer, TODO lo que
        # el usuario llegaba a ver — sección A.7 del reporte de bugs).
        visibles_inicial = min(self._VISIBLES_INICIAL, len(pendientes))
        self._agregar_tarjetas(pendientes[:visibles_inicial])
        self._pendientes_index = visibles_inicial

        restantes = len(pendientes) - visibles_inicial
        if restantes > 0:
            self._mostrar_boton_ver_mas(restantes, generacion)

    def _agregar_tarjetas(self, datos: list):
        for data in datos:
            self._layout_atencion.addWidget(self._crear_tarjeta_desde_data(data))

    def _mostrar_boton_ver_mas(self, restantes: int, generacion: int):
        self._quitar_boton_ver_mas()
        boton = QPushButton(f"Ver los {restantes} restantes")
        poner_clase(boton, "accionSecundaria")
        boton.clicked.connect(lambda: self._iniciar_carga_completa(generacion))
        self._layout_atencion.addWidget(boton)
        self._btn_ver_mas = boton

    def _quitar_boton_ver_mas(self):
        boton = getattr(self, "_btn_ver_mas", None)
        if boton is not None:
            self._layout_atencion.removeWidget(boton)
            boton.deleteLater()
            self._btn_ver_mas = None

    def _iniciar_carga_completa(self, generacion: int):
        """Muestra TODAS las alertas restantes, en tandas encadenadas
        con QTimer.singleShot(0, ...): cada tanda se crea en un ciclo
        distinto del bucle de eventos, así que aunque haya cientos de
        productos escasos la ventana nunca deja de responder mientras
        se construyen los widgets."""
        self._quitar_boton_ver_mas()
        self._cargar_siguiente_bloque(generacion)

    def _cargar_siguiente_bloque(self, generacion: int):
        # Si mientras tanto se disparó otro refrescar() (F5, cambio de
        # rol, nueva navegación), esta cadena quedó obsoleta: se aborta
        # en vez de seguir agregando tarjetas sobre un layout que ya se
        # limpió para otro contenido.
        if generacion != self._generacion_atencion:
            return
        inicio = self._pendientes_index
        fin = min(inicio + self._BLOQUE_CARGA, len(self._pendientes_data))
        self._agregar_tarjetas(self._pendientes_data[inicio:fin])
        self._pendientes_index = fin
        if fin < len(self._pendientes_data):
            QTimer.singleShot(0, lambda: self._cargar_siguiente_bloque(generacion))

    def _crear_tarjeta_desde_data(self, data: dict):
        return TarjetaAccion(
            titulo=data["titulo"],
            descripcion=data["descripcion"],
            severidad=data.get("severidad", "info"),
            texto_boton=data.get("texto_boton", "Ver"),
            al_clic=lambda tipo=data["tipo"], texto=data["texto_filtro"]:
                self._ir_al_recurso(tipo, texto),
        )

    def _ir_al_recurso(self, tipo: str, texto_filtro: str):
        """Navega a Inventario y deja la tabla correspondiente filtrada
        exactamente por el producto/lote de la tarjeta en la que se hizo
        clic, en lugar de solo abrir el módulo en su estado por defecto."""
        ventana = self.window()
        if hasattr(ventana, "ir_a_resultado"):
            ventana.ir_a_resultado({"tipo": tipo, "texto_filtro": texto_filtro})
        else:
            self._navegar("inventario")

    # ── Datos ─────────────────────────────────────────────────────────
    def refrescar(self):
        with nueva_sesion() as db:
            n_productos = db.query(Producto).filter_by(activo=True).count()
            n_proveedores = db.query(Proveedor).filter_by(activo=True).count()
            n_clientes = db.query(Cliente).filter_by(activo=True).count()
            n_ventas = db.query(OrdenVenta).count()
            n_produccion_activa = db.query(OrdenProduccion).filter(
                OrdenProduccion.estado.in_(["INICIADA", "EN_PROCESO"])
            ).count()

            bajos = productos_bajo_minimo(db)
            _lotes_vencer = lotes_proximos_a_vencer(db, dias=30)
            # Extraer todo lo que necesita la UI *dentro* de la sesión para
            # evitar DetachedInstanceError al acceder a relaciones lazy más tarde.
            por_vencer = [
                {
                    "numero": lote.numero_lote,
                    "nombre": (lote.producto.nombre
                               if lote.producto else lote.numero_lote),
                    "fecha_vencimiento": lote.fecha_vencimiento,
                }
                for lote in _lotes_vencer
            ]

            hoy = date.today()
            ventas_del_mes = [
                v for v in db.query(OrdenVenta).all()
                if v.fecha and v.fecha.month == hoy.month and v.fecha.year == hoy.year
            ]
            total_mes = sum(v.total for v in ventas_del_mes)

        capital_inicial = obtener_parametro_numerico("capital_inicial", 0.0)

        self.kpi_productos.actualizar(str(n_productos))
        self.kpi_proveedores.actualizar(str(n_proveedores))
        self.kpi_clientes.actualizar(str(n_clientes))
        self.kpi_ventas.actualizar(str(n_ventas))
        self.kpi_produccion_activa.actualizar(str(n_produccion_activa))
        self.kpi_ingresos_mes.actualizar(f"S/ {total_mes:,.2f}")
        self.kpi_capital_inicial.actualizar(f"S/ {capital_inicial:,.2f}")

        self._repintar_atencion(bajos, por_vencer)
