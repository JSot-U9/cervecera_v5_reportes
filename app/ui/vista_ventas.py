"""vista_ventas.py (PySide6)
=============================
Registro de órdenes de venta + gestión de clientes.
"""

from PySide6.QtCore import Qt
from PySide6.QtWidgets import (
    QWidget, QDialog, QVBoxLayout, QHBoxLayout, QGridLayout, QLabel,
    QLineEdit, QComboBox, QPushButton, QTabWidget, QMessageBox,
)

from app.basedatos import nueva_sesion
from app.modelos import Producto
from app.sesion import sesion_actual
from app.seguridad import puede, modulos_visibles
from app.logica_ventas import registrar_venta, listar_ordenes_venta, listar_clientes_activos, crear_cliente
from app.logica_inventario import StockInsuficiente
from app.ui.widgets import (
    EncabezadoModulo, BarraBusqueda, TablaDatos, SeccionFormulario, MensajeEstado,
    centrar_ventana,
)
from app.ui.estilos import COLOR_TEXTO_SECUNDARIO, COLOR_PRIMARIO, COLOR_EXITO, fuente, poner_clase, fondo


class VistaVentas(QWidget):
    def __init__(self, parent=None):
        super().__init__(parent)
        self.tutorial_targets = {}

        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(0)
        layout.addWidget(EncabezadoModulo(
            "Realizar ventas", "Registro de órdenes de venta · El inventario se descuenta automáticamente (FIFO)",
            icono="💰",
        ))

        self.notebook = QTabWidget()
        layout.addWidget(self.notebook, stretch=1)

        self._pestana_ordenes()
        self._pestana_clientes()

        self.refrescar()

    def _pestana_ordenes(self):
        pestana = QWidget()
        pl = QVBoxLayout(pestana)
        pl.setContentsMargins(10, 10, 10, 10)
        self.notebook.addTab(pestana, "🧾  Órdenes de Venta")

        puede_crear = puede(sesion_actual.rol, "ventas", "crear")
        barra = BarraBusqueda(al_escribir=lambda t: self.tabla_ventas.filtrar(t),
                               placeholder="🔎  Buscar orden, cliente...")
        if puede_crear:
            self.tutorial_targets["btn_nueva_venta"] = barra.agregar_boton(
                "＋  Nueva venta", self._abrir_nueva_venta)
        self.tutorial_targets["btn_reporte"] = barra.agregar_boton(
            "📊  Reporte", self._abrir_dialogo_reporte, estilo="accionSecundaria")
        if "centro_inteligencia" in modulos_visibles(sesion_actual.rol):
            barra.agregar_boton(
                "🧠  Demanda prevista", lambda: self._ir_a_prediccion(),
                estilo="accionSecundaria")
        pl.addWidget(barra)

        self.tabla_ventas = TablaDatos(
            ["N° Orden", "Cliente", "Fecha", "Total (S/)"],
            anchos={"N° Orden": 110, "Cliente": 220, "Fecha": 120, "Total (S/)": 130},
        )
        pl.addWidget(self.tabla_ventas, stretch=1)
        self.tutorial_targets["tabla_ventas"] = self.tabla_ventas

    def _pestana_clientes(self):
        pestana = QWidget()
        pl = QVBoxLayout(pestana)
        pl.setContentsMargins(10, 10, 10, 10)
        self.notebook.addTab(pestana, "👥  Clientes")

        puede_crear = puede(sesion_actual.rol, "ventas", "crear")
        barra = BarraBusqueda(al_escribir=lambda t: self.tabla_clientes.filtrar(t),
                               placeholder="🔎  Buscar cliente...")
        if puede_crear:
            barra.agregar_boton("＋  Nuevo cliente", self._abrir_nuevo_cliente)
        pl.addWidget(barra)

        self.tabla_clientes = TablaDatos(
            ["Tipo", "Nombre / Razón Social", "N° Documento", "Teléfono"],
            anchos={"Tipo": 90, "Nombre / Razón Social": 220, "N° Documento": 130, "Teléfono": 130},
        )
        pl.addWidget(self.tabla_clientes, stretch=1)
        self.tutorial_targets["tabla_clientes"] = self.tabla_clientes

    def _ir_a_prediccion(self):
        """Enlace de integración IA (sección 28): demanda prevista de
        cada producto. Antes navegaba al módulo "prediccion" (ya
        eliminado del sidebar, sección G del reporte de bugs); ahora
        entra a Centro de Inteligencia y abre directamente la pestaña
        de predicción de demanda detallada."""
        ventana = self.window()
        if hasattr(ventana, "navegar"):
            ventana.navegar("centro_inteligencia")
        vista = ventana.obtener_vista("centro_inteligencia") if hasattr(ventana, "obtener_vista") else None
        if vista is not None and hasattr(vista, "mostrar_tab_prediccion_detalle"):
            vista.mostrar_tab_prediccion_detalle()

    def refrescar(self):
        with nueva_sesion() as db:
            filas_ventas = [
                [o.id, o.numero, o.cliente.nombre, str(o.fecha), f"S/ {o.total:,.2f}"]
                for o in listar_ordenes_venta(db)
            ]
            filas_clientes = [
                [c.id, c.tipo, c.nombre, c.documento or "—", c.telefono or "—"]
                for c in listar_clientes_activos(db)
            ]
        self.tabla_ventas.cargar_filas(filas_ventas)
        self.tabla_clientes.cargar_filas(filas_clientes)

    def _abrir_nueva_venta(self):
        VentanaNuevaVenta(self.window(), al_guardar=self.refrescar).exec()

    def _abrir_nuevo_cliente(self):
        VentanaCliente(self.window(), al_guardar=self.refrescar).exec()

    def _abrir_dialogo_reporte(self):
        from app.ui.dialogo_reporte import DialogoReporte
        dlg = DialogoReporte(self.window(), modulo="ventas")
        dlg.show()
        return dlg


def _franja(titulo_texto: str, subtitulo: str = None) -> QWidget:
    franja = QWidget()
    fondo(franja, COLOR_PRIMARIO)
    fl = QVBoxLayout(franja)
    fl.setContentsMargins(20, 12, 20, 12)
    lbl = QLabel(titulo_texto)
    lbl.setStyleSheet("background: transparent; color: white;")
    lbl.setFont(fuente(13, negrita=True))
    fl.addWidget(lbl)
    if subtitulo:
        lbl2 = QLabel(subtitulo)
        lbl2.setStyleSheet("background: transparent; color: #F2D9B8;")
        lbl2.setFont(fuente(9))
        fl.addWidget(lbl2)
    return franja


class VentanaCliente(QDialog):
    def __init__(self, parent, al_guardar):
        super().__init__(parent)
        self.setWindowTitle("Nuevo cliente")
        self.al_guardar = al_guardar

        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(0)
        layout.addWidget(_franja("＋  Registrar nuevo cliente"))

        cuerpo = QVBoxLayout()
        cuerpo.setContentsMargins(20, 16, 20, 16)
        layout.addLayout(cuerpo)

        self._msg = MensajeEstado()
        cuerpo.addWidget(self._msg)

        sec = SeccionFormulario("Datos del cliente")
        secl = QGridLayout(sec)
        secl.setColumnStretch(1, 1)
        cuerpo.addWidget(sec)

        self.combo_tipo = QComboBox()
        self.combo_tipo.addItems(["NATURAL", "JURIDICA"])
        self.entrada_nombre = QLineEdit()
        self.entrada_documento = QLineEdit()
        self.entrada_telefono = QLineEdit()
        self.entrada_email = QLineEdit()

        campos = [
            ("Tipo de persona", self.combo_tipo, False),
            ("Nombre / Razón social *", self.entrada_nombre, True),
            ("N° de documento (DNI o RUC)", self.entrada_documento, False),
            ("Teléfono", self.entrada_telefono, False),
            ("Correo electrónico", self.entrada_email, False),
        ]
        for i, (etiqueta, widget, obligatorio) in enumerate(campos):
            lbl = QLabel(etiqueta)
            lbl.setFont(fuente(9, negrita=obligatorio))
            secl.addWidget(lbl, i, 0)
            secl.addWidget(widget, i, 1)

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
        btn_guardar = QPushButton("💾  Registrar cliente")
        btn_guardar.clicked.connect(self._guardar)
        fila_btn.addWidget(btn_guardar)
        cuerpo.addLayout(fila_btn)

        centrar_ventana(self, 460, 380)

    def _guardar(self):
        nombre = self.entrada_nombre.text().strip()
        if not nombre:
            self._msg.mostrar("El nombre del cliente es obligatorio.", "error")
            return
        try:
            crear_cliente(
                tipo=self.combo_tipo.currentText(), nombre=nombre,
                documento=self.entrada_documento.text().strip(),
                telefono=self.entrada_telefono.text().strip(),
                email=self.entrada_email.text().strip(),
            )
        except Exception as error:
            self._msg.mostrar(f"No se pudo registrar el cliente: {error}", "error", 0)
            return
        self.al_guardar()
        self.accept()

    def keyPressEvent(self, evento):
        if evento.key() == Qt.Key_Escape:
            self.reject()
        else:
            super().keyPressEvent(evento)


class VentanaNuevaVenta(QDialog):
    """Formulario de venta con modelo mental de carrito."""

    def __init__(self, parent, al_guardar):
        super().__init__(parent)
        self.setWindowTitle("Nueva venta")
        self.al_guardar = al_guardar
        self.items_agregados = []

        with nueva_sesion() as db:
            self.clientes = listar_clientes_activos(db)
            self.productos = db.query(Producto).filter_by(tipo="Producto terminado", activo=True).all()

        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(0)
        layout.addWidget(_franja("💰  Nueva venta",
                                  "Selecciona cliente, agrega productos y registra la venta"))

        cuerpo = QVBoxLayout()
        cuerpo.setContentsMargins(20, 12, 20, 12)
        layout.addLayout(cuerpo)

        self._msg = MensajeEstado()
        cuerpo.addWidget(self._msg)

        sec_cli = SeccionFormulario("Cliente")
        scl = QVBoxLayout(sec_cli)
        cuerpo.addWidget(sec_cli)
        lbl_cli = QLabel("Cliente *")
        lbl_cli.setFont(fuente(9, negrita=True))
        scl.addWidget(lbl_cli)
        self.combo_cliente = QComboBox()
        for c in self.clientes:
            self.combo_cliente.addItem(f"{c.id} — {c.nombre}", c.id)
        self.combo_cliente.setCurrentIndex(-1)
        scl.addWidget(self.combo_cliente)

        sec_prod = SeccionFormulario("Agregar producto")
        spl = QVBoxLayout(sec_prod)
        cuerpo.addWidget(sec_prod)

        lbl_prod = QLabel("Producto terminado *")
        lbl_prod.setFont(fuente(9, negrita=True))
        spl.addWidget(lbl_prod)
        self.combo_producto = QComboBox()
        for p in self.productos:
            self.combo_producto.addItem(f"{p.id} — {p.nombre} (S/ {p.precio_venta:.2f})", p.id)
        self.combo_producto.setCurrentIndex(-1)
        self.combo_producto.currentIndexChanged.connect(self._autocompletar_precio)
        spl.addWidget(self.combo_producto)
        spl.addSpacing(6)

        f_nums = QHBoxLayout()
        spl.addLayout(f_nums)
        col_cant = QVBoxLayout()
        lbl_cant = QLabel("Cantidad *")
        lbl_cant.setFont(fuente(9, negrita=True))
        col_cant.addWidget(lbl_cant)
        self.entrada_cantidad = QLineEdit()
        self.entrada_cantidad.setFixedWidth(100)
        col_cant.addWidget(self.entrada_cantidad)
        f_nums.addLayout(col_cant)

        col_precio = QVBoxLayout()
        lbl_precio = QLabel("Precio unitario (S/)")
        lbl_precio.setFont(fuente(9, negrita=True))
        col_precio.addWidget(lbl_precio)
        self.entrada_precio = QLineEdit()
        self.entrada_precio.setFixedWidth(100)
        col_precio.addWidget(self.entrada_precio)
        lbl_auto = QLabel("Autocompletado del catálogo")
        lbl_auto.setStyleSheet(f"color: {COLOR_TEXTO_SECUNDARIO};")
        lbl_auto.setFont(fuente(8, cursiva=True))
        col_precio.addWidget(lbl_auto)
        f_nums.addLayout(col_precio)
        f_nums.addStretch()

        self.btn_agregar_item = QPushButton("＋  Agregar al carrito")
        self.btn_agregar_item.clicked.connect(self._agregar_item)
        spl.addWidget(self.btn_agregar_item, alignment=Qt.AlignLeft)

        sec_carrito = SeccionFormulario("Carrito de venta")
        scarl = QVBoxLayout(sec_carrito)
        cuerpo.addWidget(sec_carrito, stretch=1)

        self.lbl_total = QLabel("TOTAL:  S/ 0.00")
        self.lbl_total.setFont(fuente(16, negrita=True))
        self.lbl_total.setStyleSheet(f"color: {COLOR_EXITO};")
        self.lbl_total.setAlignment(Qt.AlignRight)
        scarl.addWidget(self.lbl_total)

        self.tabla_items = TablaDatos(
            ["Producto", "Cantidad", "Precio Unit. (S/)", "Subtotal (S/)"], con_id=False,
            anchos={"Producto": 200, "Cantidad": 80, "Precio Unit. (S/)": 130, "Subtotal (S/)": 120},
        )
        scarl.addWidget(self.tabla_items, stretch=1)

        fila_btn = QHBoxLayout()
        lbl_oblig = QLabel("* Campos obligatorios")
        lbl_oblig.setStyleSheet(f"color: {COLOR_TEXTO_SECUNDARIO};")
        lbl_oblig.setFont(fuente(8, cursiva=True))
        fila_btn.addWidget(lbl_oblig)
        fila_btn.addStretch()
        btn_cancelar = QPushButton("Cancelar")
        poner_clase(btn_cancelar, "secundario")
        btn_cancelar.clicked.connect(self.reject)
        fila_btn.addWidget(btn_cancelar)
        btn_guardar = QPushButton("💰  Registrar venta")
        btn_guardar.clicked.connect(self._guardar_venta)
        fila_btn.addWidget(btn_guardar)
        cuerpo.addLayout(fila_btn)

        centrar_ventana(self, 740, 600)

    def _autocompletar_precio(self):
        producto_id = self.combo_producto.currentData()
        if producto_id is None:
            return
        for p in self.productos:
            if p.id == producto_id:
                self.entrada_precio.setText(str(p.precio_venta))
                break

    def _agregar_item(self):
        producto_id = self.combo_producto.currentData()
        if producto_id is None:
            self._msg.mostrar("Selecciona un producto antes de agregar.", "advertencia")
            return
        try:
            cantidad = float(self.entrada_cantidad.text())
            precio = float(self.entrada_precio.text())
            if cantidad <= 0:
                raise ValueError("cantidad")
            if precio < 0:
                raise ValueError("precio")
        except ValueError:
            self._msg.mostrar(
                "La cantidad debe ser mayor que 0 y el precio debe ser un número válido.", "error")
            return

        self.items_agregados.append({
            "producto_id": producto_id, "cantidad": cantidad, "precio_unitario": precio,
        })
        self._msg.mostrar("Producto agregado al carrito.", "exito", 2000)
        self._refrescar_tabla_items()
        self.entrada_cantidad.clear()
        self.combo_producto.setCurrentIndex(-1)
        self.entrada_precio.clear()

    def _refrescar_tabla_items(self):
        filas = []
        total = 0.0
        with nueva_sesion() as db:
            for item in self.items_agregados:
                producto = db.get(Producto, item["producto_id"])
                subtotal = item["cantidad"] * item["precio_unitario"]
                total += subtotal
                filas.append([
                    producto.nombre, item["cantidad"],
                    f"S/ {item['precio_unitario']:.2f}", f"S/ {subtotal:.2f}",
                ])
        self.tabla_items.cargar_filas(filas)
        self.lbl_total.setText(f"TOTAL:  S/ {total:,.2f}")

    def _guardar_venta(self):
        cliente_id = self.combo_cliente.currentData()
        if cliente_id is None:
            self._msg.mostrar("Selecciona un cliente para la venta.", "error")
            return
        if not self.items_agregados:
            self._msg.mostrar("Agrega al menos un producto al carrito antes de registrar.", "error")
            return

        total = sum(i["cantidad"] * i["precio_unitario"] for i in self.items_agregados)
        nombre_cliente = self.combo_cliente.currentText().split(" — ")[1]

        try:
            orden = registrar_venta(
                cliente_id=cliente_id, items=self.items_agregados,
                usuario_id=sesion_actual.usuario_id,
            )
        except StockInsuficiente as error:
            QMessageBox.critical(
                self, "Stock insuficiente",
                f"No hay suficiente stock para completar la venta.\n\n"
                f"Detalle: {error}\n\nVerifica el inventario antes de intentar nuevamente.")
            return
        except Exception as error:
            QMessageBox.critical(self, "No se pudo registrar la venta",
                                  f"Ocurrió un error inesperado.\n\nDetalle: {error}")
            return

        QMessageBox.information(
            self, "✓ Venta registrada correctamente",
            f"Venta {orden.numero} registrada.\nCliente: {nombre_cliente}\n"
            f"Productos: {len(self.items_agregados)}\nTotal: S/ {total:,.2f}\n\n"
            f"El stock fue descontado del inventario (FIFO).")
        self.al_guardar()
        self.accept()

    def keyPressEvent(self, evento):
        if evento.key() == Qt.Key_Escape:
            self.reject()
        else:
            super().keyPressEvent(evento)
