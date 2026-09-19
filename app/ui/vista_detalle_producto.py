"""vista_detalle_producto.py (PySide6)
=================================================
Vista de detalle de un producto (sección 13 del prompt maestro de
rediseño UI/UX — Parte 3):

    Inventario › Productos › Anka Chida

    ANKA CHIDA
    Stock actual   32      Stock mínimo   20      Estado   🟢 NORMAL

    [Información] [Lotes] [Movimientos] [Ventas] [🧠 Inteligencia]

Se abre con doble clic en una fila de la pestaña "Stock Actual" de
Inventario, como una página más dentro del mismo QStackedWidget del
módulo (no un diálogo aparte) — así el botón "‹ Volver" regresa
instantáneamente a la tabla, con el filtro y la pestaña donde el
usuario los dejó, sin reconstruir nada.

Esta vista NO se reconstruye cada vez que se abre: VistaInventario
crea una sola instancia y llama a cargar(producto_id) cada vez que el
usuario hace doble clic en un producto distinto.
"""

from __future__ import annotations

from PySide6.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QGridLayout, QLabel, QLineEdit,
    QPushButton, QTabWidget, QComboBox,
)

from app.basedatos import nueva_sesion
from app.modelos import Producto, LoteInventario, MovimientoInventario, DetalleVenta, OrdenVenta
from app.sesion import sesion_actual
from app.seguridad import puede, modulos_visibles
from app.logica_inventario import stock_total, actualizar_producto
from app.ui.widgets import (
    TarjetaKPI, Migaja, TablaDatos, SeccionFormulario, MensajeEstado,
    formatear_estado, tag_para_estado, EstadoVacio, ejecutar_con_carga,
)
from app.ui.estilos import COLOR_TEXTO_SECUNDARIO, COLOR_PRIMARIO, fuente, poner_clase


class VistaDetalleProducto(QWidget):
    """volver: callback sin argumentos que VistaInventario pasa para
    saber cuándo el usuario quiere regresar a la tabla."""

    def __init__(self, volver, al_guardar=None, parent=None):
        super().__init__(parent)
        self._volver_cb = volver
        self._al_guardar_cb = al_guardar
        self.producto_id: int | None = None
        self.tutorial_targets = {}

        layout = QVBoxLayout(self)
        layout.setContentsMargins(16, 12, 16, 16)
        layout.setSpacing(10)

        # ── Fila superior: breadcrumb secundario + volver ───────────
        fila_top = QHBoxLayout()
        self._migaja = Migaja([])
        fila_top.addWidget(self._migaja)
        fila_top.addStretch()
        self.btn_volver = QPushButton("‹  Volver")
        poner_clase(self.btn_volver, "secundario")
        self.btn_volver.clicked.connect(self._al_volver)
        fila_top.addWidget(self.btn_volver)
        layout.addLayout(fila_top)

        # ── Encabezado: nombre + código/tipo ─────────────────────────
        self._lbl_nombre = QLabel("—")
        self._lbl_nombre.setFont(fuente(18, negrita=True))
        self._lbl_nombre.setStyleSheet(f"color: {COLOR_PRIMARIO};")
        layout.addWidget(self._lbl_nombre)
        self._lbl_subtitulo = QLabel("—")
        self._lbl_subtitulo.setStyleSheet(f"color: {COLOR_TEXTO_SECUNDARIO};")
        self._lbl_subtitulo.setFont(fuente(9))
        layout.addWidget(self._lbl_subtitulo)

        # ── KPIs ──────────────────────────────────────────────────
        fila_kpi = QHBoxLayout()
        fila_kpi.setSpacing(10)
        self.kpi_stock = TarjetaKPI("Stock actual", icono="📊")
        self.kpi_stock_minimo = TarjetaKPI("Stock mínimo", icono="🔻")
        self.kpi_estado = TarjetaKPI("Estado", icono="🏷")
        for k in (self.kpi_stock, self.kpi_stock_minimo, self.kpi_estado):
            fila_kpi.addWidget(k)
        fila_kpi.addStretch(1)
        layout.addLayout(fila_kpi)

        # ── Pestañas ──────────────────────────────────────────────
        self.notebook = QTabWidget()
        layout.addWidget(self.notebook, stretch=1)

        self._pestana_informacion()
        self._pestana_lotes()
        self._pestana_movimientos()
        self._pestana_ventas()
        self._indice_tab_inteligencia = None  # se agrega recién en cargar(), según el rol

    # ══════════════════════════════════════════════════════════
    #  Construcción de pestañas (una sola vez)
    # ══════════════════════════════════════════════════════════
    def _pestana_informacion(self):
        pestana = QWidget()
        pl = QVBoxLayout(pestana)
        pl.setContentsMargins(10, 10, 10, 10)
        self.notebook.addTab(pestana, "ℹ️  Información")

        self._msg_info = MensajeEstado()
        pl.addWidget(self._msg_info)

        sec = SeccionFormulario("Datos del producto")
        secl = QGridLayout(sec)
        secl.setColumnStretch(1, 1)
        pl.addWidget(sec)

        self.entrada_codigo = QLineEdit()
        self.entrada_codigo.setReadOnly(True)
        self.entrada_codigo.setStyleSheet(f"color: {COLOR_TEXTO_SECUNDARIO};")
        self.entrada_tipo = QLineEdit()
        self.entrada_tipo.setReadOnly(True)
        self.entrada_tipo.setStyleSheet(f"color: {COLOR_TEXTO_SECUNDARIO};")
        self.entrada_nombre = QLineEdit()
        self.entrada_unidad = QLineEdit()
        self.entrada_precio = QLineEdit()
        self.entrada_stock_minimo = QLineEdit()
        self.entrada_descripcion = QLineEdit()

        filas = [
            ("Código (no editable)", self.entrada_codigo),
            ("Tipo (no editable)", self.entrada_tipo),
            ("Nombre *", self.entrada_nombre),
            ("Unidad de medida", self.entrada_unidad),
            ("Precio de venta (S/)", self.entrada_precio),
            ("Stock mínimo", self.entrada_stock_minimo),
            ("Descripción", self.entrada_descripcion),
        ]
        for i, (etiqueta, widget) in enumerate(filas):
            lbl = QLabel(etiqueta)
            lbl.setFont(fuente(9, negrita=True))
            secl.addWidget(lbl, i, 0)
            secl.addWidget(widget, i, 1)

        lbl_nota = QLabel(
            "El código y el tipo se fijan al crear el producto y no se pueden "
            "cambiar después (para no desalinear la numeración del catálogo)."
        )
        lbl_nota.setWordWrap(True)
        lbl_nota.setStyleSheet(f"color: {COLOR_TEXTO_SECUNDARIO};")
        lbl_nota.setFont(fuente(8, cursiva=True))
        pl.addWidget(lbl_nota)
        pl.addStretch()

        self._puede_editar_info = False
        fila_btn = QHBoxLayout()
        fila_btn.addStretch()
        self.btn_guardar_info = QPushButton("💾  Guardar cambios")
        self.btn_guardar_info.clicked.connect(self._guardar_informacion)
        fila_btn.addWidget(self.btn_guardar_info)
        pl.addLayout(fila_btn)

    def _pestana_lotes(self):
        pestana = QWidget()
        pl = QVBoxLayout(pestana)
        pl.setContentsMargins(10, 10, 10, 10)
        self.notebook.addTab(pestana, "🗂  Lotes")

        self.tabla_lotes_detalle = TablaDatos(
            ["N° Lote", "Ingresado", "Vencimiento", "Cantidad", "Estado"],
            anchos={"N° Lote": 140, "Ingresado": 110, "Vencimiento": 110,
                    "Cantidad": 100, "Estado": 120},
            con_id=False,
            estado_vacio=EstadoVacio(
                "🗂", "Sin lotes para este producto",
                "Todavía no se registró ningún lote de este producto (se crean "
                "al registrar una compra o cerrar una producción).",
            ),
        )
        pl.addWidget(self.tabla_lotes_detalle, stretch=1)

    def _pestana_movimientos(self):
        pestana = QWidget()
        pl = QVBoxLayout(pestana)
        pl.setContentsMargins(10, 10, 10, 10)
        self.notebook.addTab(pestana, "📋  Movimientos")

        self.tabla_movimientos_detalle = TablaDatos(
            ["Lote", "Tipo", "Cantidad", "Referencia", "Fecha"],
            anchos={"Lote": 140, "Tipo": 100, "Cantidad": 90,
                    "Referencia": 180, "Fecha": 140},
            con_id=False,
            estado_vacio=EstadoVacio(
                "📋", "Sin movimientos para este producto",
                "Todavía no hay movimientos de inventario registrados para "
                "este producto.",
            ),
        )
        pl.addWidget(self.tabla_movimientos_detalle, stretch=1)

    def _pestana_ventas(self):
        pestana = QWidget()
        pl = QVBoxLayout(pestana)
        pl.setContentsMargins(10, 10, 10, 10)
        self.notebook.addTab(pestana, "💰  Ventas")

        self.tabla_ventas_detalle = TablaDatos(
            ["N° Orden", "Cliente", "Fecha", "Cantidad", "Subtotal (S/)"],
            anchos={"N° Orden": 110, "Cliente": 200, "Fecha": 110,
                    "Cantidad": 90, "Subtotal (S/)": 110},
            con_id=False,
            estado_vacio=EstadoVacio(
                "💰", "Sin ventas para este producto",
                "Este producto todavía no aparece en ninguna orden de venta.",
            ),
        )
        pl.addWidget(self.tabla_ventas_detalle, stretch=1)

    def _construir_tab_inteligencia(self):
        """Se construye una sola vez, la primera vez que un usuario con
        acceso a Centro de Inteligencia abre el detalle de un producto
        — así los usuarios sin ese acceso ni siquiera cargan estos
        imports pesados (motor de reposición / predicción de demanda)."""
        pestana = QWidget()
        v = QVBoxLayout(pestana)
        v.setContentsMargins(10, 10, 10, 10)
        v.setSpacing(10)

        self._msg_inteligencia = MensajeEstado()
        v.addWidget(self._msg_inteligencia)

        self._lbl_intro_inteligencia = QLabel("")
        self._lbl_intro_inteligencia.setWordWrap(True)
        self._lbl_intro_inteligencia.setStyleSheet(f"color: {COLOR_TEXTO_SECUNDARIO};")
        self._lbl_intro_inteligencia.setFont(fuente(9, cursiva=True))
        v.addWidget(self._lbl_intro_inteligencia)

        fila_ctrl = QHBoxLayout()
        self.combo_horizonte_detalle = QComboBox()
        self.combo_horizonte_detalle.addItem("7 días", 7)
        self.combo_horizonte_detalle.addItem("14 días", 14)
        self.combo_horizonte_detalle.addItem("30 días", 30)
        self.combo_horizonte_detalle.setCurrentIndex(1)
        fila_ctrl.addWidget(QLabel("Horizonte:"))
        fila_ctrl.addWidget(self.combo_horizonte_detalle)
        fila_ctrl.addSpacing(16)
        self.btn_recalcular_inteligencia = QPushButton("🔄  Recalcular solo este producto")
        self.btn_recalcular_inteligencia.clicked.connect(self._recalcular_inteligencia)
        fila_ctrl.addWidget(self.btn_recalcular_inteligencia)
        fila_ctrl.addStretch()
        v.addLayout(fila_ctrl)

        fila_kpi = QHBoxLayout()
        fila_kpi.setSpacing(10)
        self.kpi_int_1 = TarjetaKPI("—", icono="📦")
        self.kpi_int_2 = TarjetaKPI("—", icono="📈")
        self.kpi_int_3 = TarjetaKPI("—", icono="🎯")
        for k in (self.kpi_int_1, self.kpi_int_2, self.kpi_int_3):
            fila_kpi.addWidget(k)
        fila_kpi.addStretch(1)
        v.addLayout(fila_kpi)

        self._lbl_detalle_inteligencia = QLabel(
            "Presiona \"🔄 Recalcular solo este producto\" para ver el resultado "
            "más reciente del motor — abrir esta pestaña no dispara ningún "
            "cálculo por sí sola."
        )
        self._lbl_detalle_inteligencia.setWordWrap(True)
        self._lbl_detalle_inteligencia.setStyleSheet(f"color: {COLOR_TEXTO_SECUNDARIO};")
        v.addWidget(self._lbl_detalle_inteligencia)
        v.addStretch()

        self._indice_tab_inteligencia = self.notebook.addTab(pestana, "🧠  Inteligencia")

    # ══════════════════════════════════════════════════════════
    #  Carga de un producto (se llama cada vez que se abre)
    # ══════════════════════════════════════════════════════════
    def cargar(self, producto_id: int):
        self.producto_id = producto_id
        with nueva_sesion() as db:
            p = db.get(Producto, producto_id)
            if p is None:
                return
            stock = stock_total(db, producto_id)
            if stock <= 0:
                estado_interno = "AGOTADO"
            elif stock < p.stock_minimo:
                estado_interno = "BAJO"
            else:
                estado_interno = "NORMAL"

            nombre, codigo, tipo = p.nombre, p.codigo, p.tipo
            unidad, precio, stock_minimo = p.unidad_medida or "", p.precio_venta, p.stock_minimo
            descripcion = p.descripcion or ""

            filas_lotes, tags_lotes = [], []
            for lote in (db.query(LoteInventario)
                         .filter_by(producto_id=producto_id)
                         .order_by(LoteInventario.fecha_ingreso.asc(), LoteInventario.id.asc())
                         .all()):
                filas_lotes.append([
                    lote.numero_lote, str(lote.fecha_ingreso),
                    str(lote.fecha_vencimiento) if lote.fecha_vencimiento else "—",
                    f"{lote.cantidad_disponible:.2f}", formatear_estado(lote.estado),
                ])
                tags_lotes.append(tag_para_estado(lote.estado))

            filas_mov = []
            lotes_ids = [lote.id for lote in db.query(LoteInventario.id)
                         .filter_by(producto_id=producto_id).all()]
            if lotes_ids:
                movs = (db.query(MovimientoInventario)
                        .filter(MovimientoInventario.lote_id.in_(lotes_ids))
                        .order_by(MovimientoInventario.fecha.desc()).limit(200).all())
                for m in movs:
                    filas_mov.append([
                        m.lote.numero_lote if m.lote else "—", m.tipo,
                        f"{m.cantidad:.2f}", m.referencia or "—", str(m.fecha)[:16],
                    ])

            filas_ventas = []
            detalles = (db.query(DetalleVenta)
                        .filter_by(producto_id=producto_id)
                        .join(OrdenVenta, DetalleVenta.orden_id == OrdenVenta.id)
                        .order_by(OrdenVenta.fecha.desc()).all())
            for d in detalles:
                filas_ventas.append([
                    d.orden.numero, d.orden.cliente.nombre if d.orden.cliente else "—",
                    str(d.orden.fecha), f"{d.cantidad:.2f}", f"S/ {d.subtotal:.2f}",
                ])

        # ── Breadcrumb secundario + header ──────────────────────
        self._migaja.establecer(["Inventario", "Productos", nombre])
        ventana = self.window()
        if hasattr(ventana, "actualizar_pestana_interna"):
            ventana.actualizar_pestana_interna(nombre, migas_extra=["Productos", nombre])

        # ── Encabezado + KPIs ────────────────────────────────────
        self._lbl_nombre.setText(nombre)
        self._lbl_subtitulo.setText(f"{codigo}  ·  {tipo}")
        self.kpi_stock.actualizar(f"{stock:.2f} {unidad}".strip())
        self.kpi_stock_minimo.actualizar(f"{stock_minimo:.2f} {unidad}".strip())
        self.kpi_estado.actualizar(formatear_estado(estado_interno))

        # ── Pestaña Información ─────────────────────────────────
        self._puede_editar_info = puede(sesion_actual.rol, "inventario", "entrada")
        self.entrada_codigo.setText(codigo)
        self.entrada_tipo.setText(tipo)
        self.entrada_nombre.setText(nombre)
        self.entrada_unidad.setText(unidad)
        self.entrada_precio.setText(f"{precio:.2f}")
        self.entrada_stock_minimo.setText(f"{stock_minimo:.2f}")
        self.entrada_descripcion.setText(descripcion)
        for campo in (self.entrada_nombre, self.entrada_unidad, self.entrada_precio,
                      self.entrada_stock_minimo, self.entrada_descripcion):
            campo.setReadOnly(not self._puede_editar_info)
        self.btn_guardar_info.setVisible(self._puede_editar_info)
        self._msg_info._ocultar()

        # ── Pestañas Lotes / Movimientos / Ventas ───────────────
        self.tabla_lotes_detalle.cargar_filas(filas_lotes, tags_por_fila=tags_lotes)
        self.tabla_movimientos_detalle.cargar_filas(filas_mov)
        self.tabla_ventas_detalle.cargar_filas(filas_ventas)

        # ── Pestaña Inteligencia (según rol Y tipo de producto) ──
        self._tipo_producto_actual = tipo
        tiene_acceso_ia = "centro_inteligencia" in modulos_visibles(sesion_actual.rol)
        if tiene_acceso_ia and self._indice_tab_inteligencia is None:
            self._construir_tab_inteligencia()
        if self._indice_tab_inteligencia is not None:
            self.notebook.setTabVisible(self._indice_tab_inteligencia, tiene_acceso_ia)
        if tiene_acceso_ia:
            if tipo == "Insumo":
                self._lbl_intro_inteligencia.setText(
                    "Recalcula la recomendación de reposición de este insumo puntual "
                    "(cantidad a reponer, prioridad) sin correr el motor completo "
                    "sobre todo el catálogo."
                )
            else:
                self._lbl_intro_inteligencia.setText(
                    "Recalcula la demanda prevista de este producto para el horizonte "
                    "elegido, igual que en el resumen de Centro de Inteligencia."
                )
            self.kpi_int_1.actualizar("—")
            self.kpi_int_2.actualizar("—")
            self.kpi_int_3.actualizar("—")
            self._lbl_detalle_inteligencia.setText(
                "Presiona \"🔄 Recalcular solo este producto\" para ver el resultado "
                "más reciente — abrir esta pestaña no dispara ningún cálculo por "
                "sí sola."
            )

        self.notebook.setCurrentIndex(0)

    # ══════════════════════════════════════════════════════════
    #  Guardar Información
    # ══════════════════════════════════════════════════════════
    def _guardar_informacion(self):
        if not self._puede_editar_info or self.producto_id is None:
            return
        try:
            precio = float(self.entrada_precio.text() or 0)
            stock_minimo = float(self.entrada_stock_minimo.text() or 0)
        except ValueError:
            self._msg_info.mostrar("El precio y el stock mínimo deben ser números válidos.", "error")
            return
        with nueva_sesion() as db:
            try:
                actualizar_producto(
                    db, self.producto_id,
                    nombre=self.entrada_nombre.text(),
                    unidad_medida=self.entrada_unidad.text(),
                    precio_venta=precio,
                    stock_minimo=stock_minimo,
                    descripcion=self.entrada_descripcion.text(),
                )
                db.commit()
            except ValueError as error:
                self._msg_info.mostrar(str(error), "error")
                return
        self._msg_info.mostrar("Cambios guardados.", "exito")
        # Refresca KPIs/encabezado (el nombre pudo cambiar) sin perder
        # la pestaña activa, y avisa a VistaInventario para que la
        # tabla de Stock/Catálogo detrás también quede al día.
        indice_actual = self.notebook.currentIndex()
        self.cargar(self.producto_id)
        self.notebook.setCurrentIndex(indice_actual)
        if self._al_guardar_cb is not None:
            self._al_guardar_cb()

    # ══════════════════════════════════════════════════════════
    #  Recalcular Inteligencia (puntual, un solo producto)
    # ══════════════════════════════════════════════════════════
    def _recalcular_inteligencia(self):
        if self.producto_id is None:
            return
        horizonte = self.combo_horizonte_detalle.currentData()

        def _calcular():
            if self._tipo_producto_actual == "Insumo":
                from app.ia.reposicion import calcular_recomendacion_individual
                return ("reposicion", calcular_recomendacion_individual(
                    self.producto_id, horizonte_dias=horizonte))
            from app.ia.demanda_prediction import predecir_demanda
            return ("demanda", predecir_demanda(self.producto_id, horizonte))

        tipo_resultado, resultado = ejecutar_con_carga(
            self, _calcular, mensaje="🧠  Calculando...",
            submensaje="Analizando solo este producto...",
        )

        if tipo_resultado == "reposicion":
            if resultado is None:
                self.kpi_int_1.actualizar("0.00")
                self.kpi_int_2.actualizar("—")
                self.kpi_int_3.actualizar(formatear_estado("BAJA"))
                self._lbl_detalle_inteligencia.setText(
                    "Este insumo no necesita reposición ahora mismo (stock por "
                    "encima del mínimo y sin demanda proyectada pendiente)."
                )
                return
            self.kpi_int_1.actualizar(f"{resultado['cantidad_recomendada']:.2f} {resultado['unidad']}")
            self.kpi_int_2.actualizar(f"{resultado['stock_disponible']:.2f} {resultado['unidad']}")
            self.kpi_int_3.actualizar(formatear_estado(resultado["prioridad"]))
            self._lbl_detalle_inteligencia.setText(resultado["motivo"])
        else:
            if not resultado.get("exito"):
                self._lbl_detalle_inteligencia.setText(
                    resultado.get("mensaje") or
                    "No hay suficiente historial de ventas para pronosticar este producto."
                )
                return
            self.kpi_int_1.actualizar(f"{resultado['demanda_total']:.1f}")
            self.kpi_int_2.actualizar(f"{resultado['promedio_diario']:.1f} /día")
            self.kpi_int_3.actualizar("🟢 Modelo IA" if resultado.get("usando_ml") else "⚠️ Estimación básica")
            self._lbl_detalle_inteligencia.setText(
                f"Demanda prevista para los próximos {horizonte} días, según el "
                "historial de ventas de este producto."
            )

    # ══════════════════════════════════════════════════════════
    def _al_volver(self):
        if self._volver_cb is not None:
            self._volver_cb()
