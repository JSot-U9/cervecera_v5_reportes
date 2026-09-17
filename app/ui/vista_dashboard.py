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

from PySide6.QtCore import Qt
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

    # ── Carga diferida (lazy rendering) de tarjetas "Requiere tu atención" ──
    _BLOQUE_CARGA = 4
    _UMBRAL_PIXELS = 120

    def _repintar_atencion(self, bajos: list, por_vencer: list):
        # Preparar lista ligera de datos en lugar de crear todas las tarjetas
        self._limpiar_layout(self._layout_atencion)
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
                "accion": ("inventario",),
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
                "accion": ("inventario",),
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

        # Estado para la carga incremental
        self._pendientes_data = pendientes
        self._pendientes_index = 0

        # Conectar el scroll una sola vez
        if not getattr(self, "_scroll_conectado", False):
            sb = self._scroll.verticalScrollBar()
            sb.valueChanged.connect(self._on_scroll_val_changed)
            self._scroll_conectado = True

        # Cargar el primer bloque inmediatamente para mostrar algo rápido
        self._cargar_siguiente_bloque()

    def _crear_tarjeta_desde_data(self, data: dict):
        return TarjetaAccion(
            titulo=data["titulo"],
            descripcion=data["descripcion"],
            severidad=data.get("severidad", "info"),
            texto_boton="Ver",
            al_clic=lambda: self._navegar("inventario"),
        )

    def _cargar_siguiente_bloque(self):
        if not getattr(self, "_pendientes_data", None):
            return
        inicio = self._pendientes_index
        fin = min(inicio + self._BLOQUE_CARGA, len(self._pendientes_data))
        for i in range(inicio, fin):
            data = self._pendientes_data[i]
            tarjeta = self._crear_tarjeta_desde_data(data)
            self._layout_atencion.addWidget(tarjeta)
        self._pendientes_index = fin

    def _on_scroll_val_changed(self, value: int):
        # Cargar más tarjetas cuando el usuario se acerca al final del área visible
        sb = self._scroll.verticalScrollBar()
        viewport_h = self._scroll.viewport().height()
        # Si el scroll está cerca del final, cargar otro bloque
        if value + viewport_h + self._UMBRAL_PIXELS >= sb.maximum():
            if getattr(self, "_pendientes_data", None) and self._pendientes_index < len(self._pendientes_data):
                self._cargar_siguiente_bloque()

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

    def _repintar_atencion(self, bajos: list, por_vencer: list):
        self._limpiar_layout(self._layout_atencion)
        hoy = date.today()

        # (severidad, TarjetaAccion) para poder priorizar lo crítico arriba
        pendientes = []

        for b in bajos:
            severidad = "critico" if b["stock"] <= 0 else "riesgo"
            descripcion = (
                f"Stock actual: {b['stock']:.1f} {b['unidad']}  "
                f"(mínimo requerido: {b['minimo']})."
            )
            tarjeta = TarjetaAccion(
                titulo=f"{b['nombre']} — stock bajo el mínimo",
                descripcion=descripcion,
                severidad=severidad,
                texto_boton="Revisar",
                al_clic=lambda: self._navegar("inventario"),
            )
            pendientes.append((severidad, tarjeta))

        for lote in por_vencer:
            fv = lote["fecha_vencimiento"]
            dias_restantes = (fv - hoy).days if fv else None
            critico = dias_restantes is not None and dias_restantes <= 7
            severidad = "critico" if critico else "atencion"
            if fv:
                descripcion = f"Vence el {fv.strftime('%d/%m/%Y')} ({dias_restantes} días)."
            else:
                descripcion = "Fecha de vencimiento no registrada."
            tarjeta = TarjetaAccion(
                titulo=f"{lote['nombre']} — lote {lote['numero']} próximo a vencer",
                descripcion=descripcion,
                severidad=severidad,
                texto_boton="Ver lote",
                al_clic=lambda: self._navegar("inventario"),
            )
            pendientes.append((severidad, tarjeta))

        if not pendientes:
            self._layout_atencion.addWidget(EstadoVacio(
                "✅", "Todo en orden",
                "No hay productos con stock bajo el mínimo ni lotes próximos a vencer "
                "en los próximos 30 días.",
            ))
            return

        pendientes.sort(key=lambda par: _PRIORIDAD_SEVERIDAD.get(par[0], 9))
        for _severidad, tarjeta in pendientes:
            self._layout_atencion.addWidget(tarjeta)
