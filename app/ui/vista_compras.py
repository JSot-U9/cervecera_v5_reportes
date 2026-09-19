"""vista_compras.py (PySide6)
==============================
Órdenes de compra a proveedores + gestión de proveedores.
"""

from datetime import datetime

from PySide6.QtCore import Qt
from PySide6.QtWidgets import (
    QWidget, QDialog, QVBoxLayout, QHBoxLayout, QGridLayout, QLabel,
    QLineEdit, QComboBox, QPushButton, QTabWidget, QMessageBox,
)

from app.basedatos import nueva_sesion
from app.modelos import Producto, LoteInventario, Proveedor
from app.sesion import sesion_actual
from app.seguridad import puede, modulos_visibles
from app.logica_compras import (
    registrar_compra, listar_ordenes_compra, listar_proveedores_activos,
    crear_proveedor, actualizar_proveedor,
    productos_ofrecidos_por_proveedor, ultimos_precios_por_proveedor,
)
from app.ui.widgets import (
    EncabezadoModulo, BarraBusqueda, TablaDatos, SeccionFormulario, MensajeEstado,
    centrar_ventana, confirmar,
)
from app.ui.estilos import COLOR_TEXTO_SECUNDARIO, COLOR_PRIMARIO, fuente, poner_clase


class VistaCompras(QWidget):
    def __init__(self, parent=None):
        super().__init__(parent)
        # Referencias a los últimos diálogos abiertos: las usará el
        # sistema de tutorial (fase posterior de la migración) para
        # resaltar los campos reales sin duplicar este formulario.
        self.ultimo_dialogo_nueva_orden = None
        self.ultimo_dialogo_reporte = None
        self.tutorial_targets = {}

        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(0)

        layout.addWidget(EncabezadoModulo(
            "Compras", "Órdenes de compra a proveedores · El inventario se actualiza automáticamente",
            icono="🛒",
        ))

        self.notebook = QTabWidget()
        layout.addWidget(self.notebook, stretch=1)

        self._pestana_ordenes()
        self._pestana_proveedores()

        self.refrescar()

    def _pestana_ordenes(self):
        pestana = QWidget()
        pl = QVBoxLayout(pestana)
        pl.setContentsMargins(10, 10, 10, 10)
        self.notebook.addTab(pestana, "🧾  Órdenes de Compra")

        puede_crear = puede(sesion_actual.rol, "compras", "crear")
        barra = BarraBusqueda(al_escribir=lambda t: self.tabla_ordenes.filtrar(t),
                               placeholder="🔎  Buscar orden, proveedor...")
        if puede_crear:
            self.tutorial_targets["btn_nueva_orden"] = barra.agregar_boton(
                "＋  Nueva orden", self._abrir_nueva_orden)
        self.tutorial_targets["btn_reporte"] = barra.agregar_boton(
            "📊  Reporte", self._abrir_dialogo_reporte, estilo="accionSecundaria")
        if "centro_inteligencia" in modulos_visibles(sesion_actual.rol):
            barra.agregar_boton(
                "🧠  Reposición recomendada", lambda: self._ir_a_inteligencia(),
                estilo="accionSecundaria")
        pl.addWidget(barra)

        self.tabla_ordenes = TablaDatos(
            ["N° Orden", "Proveedor", "Fecha", "Doc. Referencia", "Total (S/)"],
            anchos={"N° Orden": 100, "Proveedor": 200, "Fecha": 110,
                    "Doc. Referencia": 140, "Total (S/)": 110},
        )
        pl.addWidget(self.tabla_ordenes, stretch=1)
        self.tutorial_targets["tabla_ordenes"] = self.tabla_ordenes

    def _pestana_proveedores(self):
        pestana = QWidget()
        pl = QVBoxLayout(pestana)
        pl.setContentsMargins(10, 10, 10, 10)
        self.notebook.addTab(pestana, "🏭  Proveedores")

        puede_crear = puede(sesion_actual.rol, "compras", "crear")
        barra = BarraBusqueda(al_escribir=lambda t: self.tabla_proveedores.filtrar(t),
                               placeholder="🔎  Buscar proveedor...")
        if puede_crear:
            barra.agregar_boton("＋  Nuevo proveedor", self._abrir_nuevo_proveedor)
            barra.agregar_boton("✏  Editar", self._abrir_editar_proveedor, estilo="accionSecundaria")
        pl.addWidget(barra)

        self.tabla_proveedores = TablaDatos(
            ["Razón Social", "RUC", "Contacto", "Teléfono", "Correo"],
            anchos={"Razón Social": 200, "RUC": 110, "Contacto": 150,
                    "Teléfono": 120, "Correo": 180},
        )
        pl.addWidget(self.tabla_proveedores, stretch=1)

    def _ir_a_inteligencia(self):
        """Enlace de integración IA (sección 28): reposición recomendada
        de insumos, calculada en el Centro de Inteligencia."""
        ventana = self.window()
        if hasattr(ventana, "navegar"):
            ventana.navegar("centro_inteligencia")

    def refrescar(self):
        with nueva_sesion() as db:
            filas_ordenes = [
                [o.id, o.numero, o.proveedor.razon_social, str(o.fecha),
                 o.documento_referencia or "—", f"S/ {o.total:,.2f}"]
                for o in listar_ordenes_compra(db)
            ]
            filas_proveedores = [
                [p.id, p.razon_social, p.ruc or "—", p.contacto or "—",
                 p.telefono or "—", p.email or "—"]
                for p in listar_proveedores_activos(db)
            ]
        self.tabla_ordenes.cargar_filas(filas_ordenes)
        self.tabla_proveedores.cargar_filas(filas_proveedores)

    def _abrir_nueva_orden(self):
        self.ultimo_dialogo_nueva_orden = VentanaNuevaOrden(self.window(), al_guardar=self.refrescar)
        self.ultimo_dialogo_nueva_orden.show()
        return self.ultimo_dialogo_nueva_orden

    def abrir_nueva_orden_para_tutorial(self):
        if not puede(sesion_actual.rol, "compras", "crear"):
            return None
        return self._abrir_nueva_orden()

    def abrir_nueva_orden_prellenada(self, producto_id: int, cantidad_sugerida: float):
        """
        Abre el formulario de nueva orden de compra con un insumo y una
        cantidad ya preseleccionados. Se usa desde el Centro de
        Inteligencia al convertir una recomendación de reposición en
        una orden de compra real (el usuario sigue debiendo elegir
        proveedor y precio, y confirmar el guardado).
        """
        if not puede(sesion_actual.rol, "compras", "crear"):
            return None
        self.ultimo_dialogo_nueva_orden = VentanaNuevaOrden(
            self.window(), al_guardar=self.refrescar,
            producto_preseleccionado=producto_id, cantidad_sugerida=cantidad_sugerida,
        )
        self.ultimo_dialogo_nueva_orden.show()
        return self.ultimo_dialogo_nueva_orden

    def abrir_reporte_para_tutorial(self):
        self._abrir_dialogo_reporte()
        return self.ultimo_dialogo_reporte

    def _abrir_nuevo_proveedor(self):
        dlg = VentanaProveedor(self.window(), al_guardar=self.refrescar)
        dlg.exec()

    def _abrir_editar_proveedor(self):
        proveedor_id = self.tabla_proveedores.id_seleccionado()
        if not proveedor_id:
            QMessageBox.warning(self, "Aviso", "Selecciona un proveedor de la lista primero.")
            return
        with nueva_sesion() as db:
            p = db.get(Proveedor, proveedor_id)
            datos = {"razon_social": p.razon_social, "ruc": p.ruc or "",
                     "contacto": p.contacto or "", "telefono": p.telefono or "",
                     "email": p.email or ""}
        dlg = VentanaProveedor(self.window(), al_guardar=self.refrescar,
                                proveedor_id=proveedor_id, datos=datos)
        dlg.exec()

    def _abrir_dialogo_reporte(self):
        from app.ui.dialogo_reporte import DialogoReporte
        self.ultimo_dialogo_reporte = DialogoReporte(self.window(), modulo="compras")
        self.ultimo_dialogo_reporte.show()
        return self.ultimo_dialogo_reporte


# ══════════════════════════════════════════════════════════════════
#  Formulario Proveedor
# ══════════════════════════════════════════════════════════════════

class VentanaProveedor(QDialog):
    def __init__(self, parent, al_guardar, proveedor_id=None, datos=None):
        super().__init__(parent)
        self.setWindowTitle("Editar proveedor" if proveedor_id else "Nuevo proveedor")
        self.al_guardar = al_guardar
        self.proveedor_id = proveedor_id
        datos = datos or {}

        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(0)

        from app.ui.estilos import fondo
        franja = QWidget()
        fondo(franja, COLOR_PRIMARIO)
        fl = QVBoxLayout(franja)
        fl.setContentsMargins(20, 12, 20, 12)
        icono = "✏" if proveedor_id else "＋"
        lbl = QLabel(f"{icono}  {'Editar proveedor' if proveedor_id else 'Nuevo proveedor'}")
        lbl.setStyleSheet("background: transparent; color: white;")
        lbl.setFont(fuente(13, negrita=True))
        fl.addWidget(lbl)
        layout.addWidget(franja)

        cuerpo = QVBoxLayout()
        cuerpo.setContentsMargins(20, 16, 20, 16)
        layout.addLayout(cuerpo)

        self._msg = MensajeEstado()
        cuerpo.addWidget(self._msg)

        sec = SeccionFormulario("Información del proveedor")
        secl = QGridLayout(sec)
        secl.setColumnStretch(1, 1)
        cuerpo.addWidget(sec)

        campos = [
            ("Razón social *", "razon_social", True),
            ("RUC", "ruc", False),
            ("Persona de contacto", "contacto", False),
            ("Teléfono", "telefono", False),
            ("Correo electrónico", "email", False),
        ]
        self._entradas = {}
        for i, (etiqueta, clave, obligatorio) in enumerate(campos):
            lbl_campo = QLabel(etiqueta)
            lbl_campo.setFont(fuente(9, negrita=obligatorio))
            secl.addWidget(lbl_campo, i, 0)
            entrada = QLineEdit(datos.get(clave, ""))
            secl.addWidget(entrada, i, 1)
            self._entradas[clave] = entrada

        lbl_nota = QLabel("* Campo obligatorio")
        lbl_nota.setStyleSheet(f"color: {COLOR_TEXTO_SECUNDARIO};")
        lbl_nota.setFont(fuente(8, cursiva=True))
        cuerpo.addWidget(lbl_nota)
        cuerpo.addStretch()

        fila_btn = QHBoxLayout()
        fila_btn.addStretch()
        btn_cancelar = QPushButton("Cancelar")
        poner_clase(btn_cancelar, "secundario")
        btn_cancelar.clicked.connect(self.reject)
        fila_btn.addWidget(btn_cancelar)
        btn_guardar = QPushButton("💾  Guardar proveedor")
        btn_guardar.clicked.connect(self._guardar)
        fila_btn.addWidget(btn_guardar)
        cuerpo.addLayout(fila_btn)

        centrar_ventana(self, 460, 380)

    def _guardar(self):
        razon = self._entradas["razon_social"].text().strip()
        if not razon:
            self._msg.mostrar("La razón social es obligatoria.", "error")
            return
        datos = dict(
            razon_social=razon,
            ruc=self._entradas["ruc"].text().strip() or None,
            contacto=self._entradas["contacto"].text().strip(),
            telefono=self._entradas["telefono"].text().strip(),
            email=self._entradas["email"].text().strip(),
        )
        try:
            if self.proveedor_id:
                actualizar_proveedor(self.proveedor_id, **datos)
            else:
                crear_proveedor(**datos)
        except Exception as error:
            self._msg.mostrar(f"No se pudo guardar el proveedor: {error}", "error", 0)
            return
        self.al_guardar()
        self.accept()

    def keyPressEvent(self, evento):
        if evento.key() == Qt.Key_Escape:
            self.reject()
        else:
            super().keyPressEvent(evento)


# ══════════════════════════════════════════════════════════════════
#  Formulario Nueva Orden de Compra
# ══════════════════════════════════════════════════════════════════

class VentanaNuevaOrden(QDialog):
    """No modal (se usa .show(), no .exec()) para que el tutorial /
    práctica guiada de una fase futura pueda seguir interactuando con
    la ventana principal detrás mientras este formulario está abierto."""

    def __init__(self, parent, al_guardar, producto_preseleccionado: int = None,
                 cantidad_sugerida: float = None):
        super().__init__(parent)
        self.setWindowTitle("Nueva orden de compra")
        self.setModal(False)
        self.al_guardar = al_guardar
        self.items_agregados = []
        self._producto_preseleccionado = producto_preseleccionado
        self._cantidad_sugerida = cantidad_sugerida

        with nueva_sesion() as db:
            self.proveedores = listar_proveedores_activos(db)
            # El catálogo de productos y los precios YA NO son fijos ni
            # globales: dependen del proveedor elegido (ver
            # _al_cambiar_proveedor). Se dejan vacíos aquí; se llenan en
            # cuanto el usuario selecciona un proveedor.
            self.productos: list[Producto] = []
            self._ultimos_precios: dict = {}

        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(0)

        from app.ui.estilos import fondo
        franja = QWidget()
        fondo(franja, COLOR_PRIMARIO)
        fl = QVBoxLayout(franja)
        fl.setContentsMargins(20, 12, 20, 12)
        lbl1 = QLabel("＋  Nueva orden de compra")
        lbl1.setStyleSheet("background: transparent; color: white;")
        lbl1.setFont(fuente(13, negrita=True))
        fl.addWidget(lbl1)
        lbl2 = QLabel("Selecciona proveedor, agrega productos y guarda la orden")
        lbl2.setStyleSheet("background: transparent; color: #F2D9B8;")
        lbl2.setFont(fuente(9))
        fl.addWidget(lbl2)
        layout.addWidget(franja)

        cuerpo = QVBoxLayout()
        cuerpo.setContentsMargins(20, 12, 20, 12)
        layout.addLayout(cuerpo)

        self._msg = MensajeEstado()
        cuerpo.addWidget(self._msg)

        # ── Proveedor ──────────────────────────────────────────
        sec_prov = SeccionFormulario("Proveedor")
        spl = QVBoxLayout(sec_prov)
        cuerpo.addWidget(sec_prov)
        lbl_prov = QLabel("Proveedor *")
        lbl_prov.setFont(fuente(9, negrita=True))
        spl.addWidget(lbl_prov)
        self.combo_proveedor = QComboBox()
        for p in self.proveedores:
            self.combo_proveedor.addItem(f"{p.id} — {p.razon_social}", p.id)
        self.combo_proveedor.setCurrentIndex(-1)
        self.combo_proveedor.currentIndexChanged.connect(self._al_cambiar_proveedor)
        spl.addWidget(self.combo_proveedor)
        # Sección "COMPRAS" del reporte de bugs: un tester se encontró
        # con que solo puede elegir un proveedor por orden y no supo si
        # era un límite del sistema o algo que se le escapaba. Es a
        # propósito — así funciona una orden de compra en cualquier
        # ERP — así que se aclara aquí mismo en vez de dejarlo a que
        # cada usuario lo intuya por su cuenta.
        lbl_nota_proveedor = QLabel(
            "ℹ Cada orden es a UN solo proveedor (así se documenta correctamente qué le "
            "compraste a quién). Si necesitas productos de varios proveedores, crea una "
            "orden nueva por cada uno.")
        lbl_nota_proveedor.setStyleSheet(f"color: {COLOR_TEXTO_SECUNDARIO};")
        lbl_nota_proveedor.setFont(fuente(8, cursiva=True))
        lbl_nota_proveedor.setWordWrap(True)
        spl.addWidget(lbl_nota_proveedor)

        # ── Agregar producto ────────────────────────────────────
        sec_prod = SeccionFormulario("Agregar producto a la orden")
        spr = QVBoxLayout(sec_prod)
        cuerpo.addWidget(sec_prod)

        lbl_prod = QLabel("Producto *")
        lbl_prod.setFont(fuente(9, negrita=True))
        spr.addWidget(lbl_prod)
        self.combo_producto = QComboBox()
        self.combo_producto.setPlaceholderText("Elige primero un proveedor…")
        self.combo_producto.setEnabled(False)
        self.combo_producto.currentIndexChanged.connect(self._autocompletar_precio)
        spr.addWidget(self.combo_producto)
        # Aclara si la lista de productos es el catálogo real de este
        # proveedor (según su historial de compras) o solo un respaldo
        # porque todavía no le hemos comprado nada — antes esto no se
        # distinguía en ningún lado y el formulario daba a entender que
        # cualquier proveedor vende cualquier insumo.
        self.lbl_catalogo_hint = QLabel("")
        self.lbl_catalogo_hint.setStyleSheet(f"color: {COLOR_TEXTO_SECUNDARIO};")
        self.lbl_catalogo_hint.setFont(fuente(8, cursiva=True))
        self.lbl_catalogo_hint.setWordWrap(True)
        spr.addWidget(self.lbl_catalogo_hint)


        f_nums = QHBoxLayout()
        spr.addLayout(f_nums)

        col_cant = QVBoxLayout()
        lbl_cant = QLabel("Cantidad *")
        lbl_cant.setFont(fuente(9, negrita=True))
        col_cant.addWidget(lbl_cant)
        self.entry_cantidad = QLineEdit()
        self.entry_cantidad.setFixedWidth(100)
        col_cant.addWidget(self.entry_cantidad)
        f_nums.addLayout(col_cant)

        col_precio = QVBoxLayout()
        lbl_precio = QLabel("Precio unitario (S/)")
        lbl_precio.setFont(fuente(9, negrita=True))
        col_precio.addWidget(lbl_precio)
        self.entry_precio = QLineEdit()
        self.entry_precio.setFixedWidth(100)
        col_precio.addWidget(self.entry_precio)
        self.lbl_precio_hint = QLabel("")
        self.lbl_precio_hint.setStyleSheet(f"color: {COLOR_TEXTO_SECUNDARIO};")
        self.lbl_precio_hint.setFont(fuente(8, cursiva=True))
        col_precio.addWidget(self.lbl_precio_hint)
        f_nums.addLayout(col_precio)

        col_venc = QVBoxLayout()
        lbl_venc = QLabel("Vencimiento (AAAA-MM-DD)")
        lbl_venc.setFont(fuente(9))
        col_venc.addWidget(lbl_venc)
        self.entry_vencimiento = QLineEdit()
        self.entry_vencimiento.setFixedWidth(120)
        self.entry_vencimiento.setPlaceholderText("opcional")
        col_venc.addWidget(self.entry_vencimiento)
        f_nums.addLayout(col_venc)
        f_nums.addStretch()

        self.btn_agregar_item = QPushButton("＋  Agregar a la orden")
        self.btn_agregar_item.clicked.connect(self._agregar_item)
        spr.addWidget(self.btn_agregar_item, alignment=Qt.AlignLeft)

        # ── Tabla de items ────────────────────────────────────
        sec_tabla = SeccionFormulario("Productos en esta orden")
        stl = QVBoxLayout(sec_tabla)
        cuerpo.addWidget(sec_tabla, stretch=1)

        self.lbl_total = QLabel("Total: S/ 0.00")
        self.lbl_total.setFont(fuente(14, negrita=True))
        self.lbl_total.setStyleSheet(f"color: {COLOR_PRIMARIO};")
        self.lbl_total.setAlignment(Qt.AlignRight)
        stl.addWidget(self.lbl_total)

        self.tabla_items = TablaDatos(
            ["Producto", "Cantidad", "Precio Unit. (S/)", "Vence", "Subtotal (S/)"],
            con_id=False, permitir_orden=False,
            anchos={"Producto": 180, "Cantidad": 80, "Precio Unit. (S/)": 120,
                    "Vence": 110, "Subtotal (S/)": 110},
        )
        stl.addWidget(self.tabla_items, stretch=1)

        # Sección A / OTROS del reporte de bugs: no había forma de
        # quitar un producto ya agregado a la orden — si el usuario se
        # equivocaba, tenía que cerrar el formulario y empezar de cero.
        fila_quitar = QHBoxLayout()
        fila_quitar.addStretch()
        self.btn_quitar_item = QPushButton("🗑  Quitar producto seleccionado")
        poner_clase(self.btn_quitar_item, "secundario")
        self.btn_quitar_item.setEnabled(False)
        self.btn_quitar_item.clicked.connect(self._quitar_item)
        fila_quitar.addWidget(self.btn_quitar_item)
        stl.addLayout(fila_quitar)
        self.tabla_items.itemSelectionChanged.connect(
            lambda: self.btn_quitar_item.setEnabled(self.tabla_items.currentRow() >= 0))

        # ── Botones finales ───────────────────────────────────
        fila_btn = QHBoxLayout()
        lbl_oblig = QLabel("* Campos obligatorios")
        lbl_oblig.setStyleSheet(f"color: {COLOR_TEXTO_SECUNDARIO};")
        lbl_oblig.setFont(fuente(8, cursiva=True))
        fila_btn.addWidget(lbl_oblig)
        fila_btn.addStretch()
        btn_cancelar = QPushButton("Cancelar")
        poner_clase(btn_cancelar, "secundario")
        btn_cancelar.clicked.connect(self.close)
        fila_btn.addWidget(btn_cancelar)
        self.btn_guardar = QPushButton("💾  Guardar orden de compra")
        self.btn_guardar.clicked.connect(self._guardar_orden)
        fila_btn.addWidget(self.btn_guardar)
        cuerpo.addLayout(fila_btn)

        centrar_ventana(self, 780, 640)

        if self._producto_preseleccionado is not None:
            # El producto viene de una recomendación del Centro de
            # Inteligencia, sin proveedor todavía: se deja pendiente y
            # se aplica en cuanto el usuario elige uno (ver
            # _al_cambiar_proveedor), en vez de forzarlo contra un
            # catálogo que todavía no se cargó.
            self._msg.mostrar(
                "Cantidad prellenada desde una recomendación del Centro de Inteligencia. "
                "Elige el proveedor y confirma el producto y el precio antes de agregarlo.",
                tipo="info", duracion_ms=8000,
            )

    def _al_cambiar_proveedor(self):
        proveedor_id = self.combo_proveedor.currentData()
        self.combo_producto.clear()
        if proveedor_id is None:
            self.combo_producto.setEnabled(False)
            self.combo_producto.setPlaceholderText("Elige primero un proveedor…")
            self.lbl_catalogo_hint.setText("")
            self._ultimos_precios = {}
            return

        with nueva_sesion() as db:
            self.productos, es_catalogo_real = productos_ofrecidos_por_proveedor(db, proveedor_id)
            self._ultimos_precios = ultimos_precios_por_proveedor(db, proveedor_id)

        self.combo_producto.setEnabled(bool(self.productos))
        for p in self.productos:
            self.combo_producto.addItem(f"{p.id} — {p.nombre}", p.id)
        self.combo_producto.setCurrentIndex(-1)

        if not self.productos:
            self.lbl_catalogo_hint.setText(
                "⚠ No hay insumos activos registrados en el sistema.")
        elif es_catalogo_real:
            self.lbl_catalogo_hint.setText(
                f"✓ {len(self.productos)} producto(s) que este proveedor ha vendido antes.")
        else:
            self.lbl_catalogo_hint.setText(
                "ℹ Este proveedor todavía no tiene compras registradas — se muestra el "
                "catálogo completo de insumos como referencia.")

        if self._producto_preseleccionado is not None:
            idx = self.combo_producto.findData(self._producto_preseleccionado)
            if idx >= 0:
                self.combo_producto.setCurrentIndex(idx)
            if self._cantidad_sugerida:
                self.entry_cantidad.setText(f"{self._cantidad_sugerida:.2f}")

    def _autocompletar_precio(self):
        producto_id = self.combo_producto.currentData()
        if producto_id is None:
            return
        ultimo = self._ultimos_precios.get(producto_id)
        if ultimo:
            self.entry_precio.setText(f"{ultimo:.2f}")
            self.lbl_precio_hint.setText("↑ último precio registrado")
        else:
            self.entry_precio.setText("")
            self.lbl_precio_hint.setText("(sin compra previa)")

    def _agregar_item(self):
        producto_id = self.combo_producto.currentData()
        if producto_id is None:
            self._msg.mostrar("Selecciona un producto antes de agregar.", "advertencia")
            return
        try:
            cantidad = float(self.entry_cantidad.text())
            precio = float(self.entry_precio.text())
            if cantidad <= 0:
                raise ValueError("cantidad negativa")
            if precio < 0:
                raise ValueError("precio negativo")
        except ValueError:
            self._msg.mostrar(
                "La cantidad debe ser mayor que 0 y el precio debe ser un número válido.", "error")
            return

        texto_fecha = self.entry_vencimiento.text().strip()
        fecha_vencimiento = None
        if texto_fecha:
            try:
                fecha_vencimiento = datetime.strptime(texto_fecha, "%Y-%m-%d").date()
            except ValueError:
                self._msg.mostrar(
                    "Formato de fecha incorrecto. Usa AAAA-MM-DD (ej: 2027-06-30).", "error")
                return

        self.items_agregados.append({
            "producto_id": producto_id, "cantidad": cantidad,
            "precio_unitario": precio, "fecha_vencimiento": fecha_vencimiento,
        })
        self._msg.mostrar("Producto agregado a la orden.", "exito", 2000)
        self._refrescar_tabla_items()
        self.entry_cantidad.clear()
        self.entry_precio.clear()
        self.entry_vencimiento.clear()
        self.lbl_precio_hint.setText("")
        self.combo_producto.setCurrentIndex(-1)

    def _refrescar_tabla_items(self):
        filas = []
        total = 0.0
        with nueva_sesion() as db:
            for item in self.items_agregados:
                producto = db.get(Producto, item["producto_id"])
                subtotal = item["cantidad"] * item["precio_unitario"]
                total += subtotal
                filas.append([
                    producto.nombre, item["cantidad"], f"S/ {item['precio_unitario']:.2f}",
                    str(item["fecha_vencimiento"]) if item["fecha_vencimiento"] else "—",
                    f"S/ {subtotal:.2f}",
                ])
        self.tabla_items.cargar_filas(filas)
        self.lbl_total.setText(f"Total: S/ {total:,.2f}")

    def _quitar_item(self):
        fila = self.tabla_items.currentRow()
        if fila < 0 or fila >= len(self.items_agregados):
            return
        del self.items_agregados[fila]
        self._msg.mostrar("Producto quitado de la orden.", "info", 2000)
        self._refrescar_tabla_items()
        self.btn_quitar_item.setEnabled(False)

    def _guardar_orden(self):
        proveedor_id = self.combo_proveedor.currentData()
        if proveedor_id is None:
            self._msg.mostrar("Selecciona un proveedor para la orden.", "error")
            return
        if not self.items_agregados:
            self._msg.mostrar("Agrega al menos un producto a la orden antes de guardar.", "error")
            return

        try:
            orden = registrar_compra(
                proveedor_id=proveedor_id,
                items=self.items_agregados,
                usuario_id=sesion_actual.usuario_id,
            )
        except Exception as error:
            QMessageBox.critical(
                self, "No se pudo registrar la orden",
                f"Ocurrió un error al guardar la orden de compra.\n\n"
                f"Detalle: {error}\n\nVerifica los datos e inténtalo nuevamente.")
            return

        QMessageBox.information(
            self, "✓ Orden registrada correctamente",
            f"La orden {orden.numero} fue guardada.\n"
            f"Proveedor: {self.combo_proveedor.currentText().split(' — ')[1]}\n"
            f"Productos: {len(self.items_agregados)}\n"
            f"El stock del inventario fue actualizado.")
        self.al_guardar()
        self.close()

    def keyPressEvent(self, evento):
        if evento.key() == Qt.Key_Escape:
            self.close()
        else:
            super().keyPressEvent(evento)
