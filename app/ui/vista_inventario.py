"""vista_inventario.py (PySide6)
=================================
Stock actual · Lotes FIFO · Movimientos · Catálogo de productos.
"""

from PySide6.QtCore import Qt
from PySide6.QtWidgets import (
    QWidget, QDialog, QVBoxLayout, QHBoxLayout, QGridLayout, QLabel,
    QLineEdit, QComboBox, QPushButton, QTabWidget, QMessageBox,
)

from app.basedatos import nueva_sesion
from app.modelos import Producto, LoteInventario, MovimientoInventario
from app.sesion import sesion_actual
from app.seguridad import puede, modulos_visibles
from app.logica_inventario import stock_total, ajustar_stock, siguiente_codigo
from app.ui.widgets import (
    EncabezadoModulo, BarraBusqueda, TablaDatos, SeccionFormulario, MensajeEstado,
    centrar_ventana, formatear_estado, BotonAyuda,
)
from app.ui.estilos import COLOR_TEXTO_SECUNDARIO, COLOR_PRIMARIO, fuente, poner_clase, fondo

_TEXTO_FIFO = (
    "FIFO significa \"el primero en entrar es el primero en salir\". Cuando compras el "
    "mismo insumo varias veces, cada compra crea un lote nuevo. Al usarlo en producción "
    "(o venderlo), el sistema descuenta siempre del lote con la fecha de ingreso más "
    "antigua antes de tocar los más nuevos."
)


class VistaInventario(QWidget):
    def __init__(self, parent=None):
        super().__init__(parent)
        self.tutorial_targets = {}

        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(0)
        layout.addWidget(EncabezadoModulo(
            "Inventario", "Stock actual · Lotes FIFO · Movimientos · Catálogo de productos",
            icono="📦",
        ))

        self.notebook = QTabWidget()
        layout.addWidget(self.notebook, stretch=1)

        self._pestana_stock()
        self._pestana_lotes()
        self._pestana_movimientos()
        self._pestana_catalogo()

        self.refrescar()

    def _pestana_stock(self):
        pestana = QWidget()
        pl = QVBoxLayout(pestana)
        pl.setContentsMargins(10, 10, 10, 10)
        self.notebook.addTab(pestana, "📊  Stock Actual")

        barra = BarraBusqueda(al_escribir=lambda t: self.tabla_stock.filtrar(t),
                               placeholder="🔎  Buscar producto...")
        self.tutorial_targets["btn_reporte"] = barra.agregar_boton(
            "📊  Reporte", lambda: self._abrir_dialogo_reporte("stock"), estilo="accionSecundaria")
        if "centro_inteligencia" in modulos_visibles(sesion_actual.rol):
            barra.agregar_boton(
                "🧠  Riesgo de quiebre", lambda: self._ir_a_inteligencia(),
                estilo="accionSecundaria")
        pl.addWidget(barra)

        self.tabla_stock = TablaDatos(
            ["Código", "Nombre", "Tipo", "Stock", "Unidad", "Stock Mín.", "Estado"],
            anchos={"Código": 90, "Nombre": 180, "Tipo": 120, "Stock": 90,
                    "Unidad": 80, "Stock Mín.": 90, "Estado": 110},
        )
        pl.addWidget(self.tabla_stock, stretch=1)
        self.tutorial_targets["tabla_stock"] = self.tabla_stock

    def _pestana_lotes(self):
        pestana = QWidget()
        pl = QVBoxLayout(pestana)
        pl.setContentsMargins(10, 10, 10, 10)
        self.notebook.addTab(pestana, "🗂  Lotes FIFO")

        puede_ajustar = puede(sesion_actual.rol, "inventario", "ajuste")
        barra = BarraBusqueda(al_escribir=lambda t: self.tabla_lotes.filtrar(t),
                               placeholder="🔎  Buscar lote...")
        if puede_ajustar:
            barra.agregar_boton("⚖  Ajustar cantidad", self._abrir_ajuste, estilo="accionSecundaria")
        pl.addWidget(barra)

        fila_fifo = QHBoxLayout()
        lbl_fifo = QLabel(
            "Los lotes se consumen del más antiguo al más nuevo (FIFO). El sistema "
            "descuenta siempre del lote con la fecha de ingreso más temprana.")
        lbl_fifo.setStyleSheet(f"color: {COLOR_TEXTO_SECUNDARIO};")
        lbl_fifo.setFont(fuente(8, cursiva=True))
        fila_fifo.addWidget(lbl_fifo)
        btn_ayuda_fifo = BotonAyuda("¿Qué es FIFO?", _TEXTO_FIFO)
        fila_fifo.addWidget(btn_ayuda_fifo)
        fila_fifo.addStretch()
        pl.addLayout(fila_fifo)

        self.tabla_lotes = TablaDatos(
            ["N° Lote", "Producto", "Ingresado", "Vencimiento", "Cantidad", "Estado"],
            anchos={"N° Lote": 130, "Producto": 170, "Ingresado": 110,
                    "Vencimiento": 110, "Cantidad": 90, "Estado": 120},
        )
        pl.addWidget(self.tabla_lotes, stretch=1)
        self.tutorial_targets["tabla_lotes"] = self.tabla_lotes

    def _pestana_movimientos(self):
        pestana = QWidget()
        pl = QVBoxLayout(pestana)
        pl.setContentsMargins(10, 10, 10, 10)
        self.notebook.addTab(pestana, "📋  Movimientos")

        barra = BarraBusqueda(al_escribir=lambda t: self.tabla_movimientos.filtrar(t),
                               placeholder="🔎  Buscar movimiento...")
        pl.addWidget(barra)

        self.tabla_movimientos = TablaDatos(
            ["Producto", "Lote", "Tipo", "Cantidad", "Referencia", "Fecha"],
            anchos={"Producto": 160, "Lote": 120, "Tipo": 100,
                    "Cantidad": 80, "Referencia": 160, "Fecha": 130},
        )
        pl.addWidget(self.tabla_movimientos, stretch=1)
        self.tutorial_targets["tabla_movimientos"] = self.tabla_movimientos

    def _pestana_catalogo(self):
        pestana = QWidget()
        pl = QVBoxLayout(pestana)
        pl.setContentsMargins(10, 10, 10, 10)
        self.notebook.addTab(pestana, "📦  Catálogo")

        puede_editar = puede(sesion_actual.rol, "inventario", "entrada")
        barra = BarraBusqueda(al_escribir=lambda t: self.tabla_catalogo.filtrar(t),
                               placeholder="🔎  Buscar en catálogo...")
        if puede_editar:
            barra.agregar_boton("＋  Nuevo producto", self._abrir_nuevo_producto)
        pl.addWidget(barra)

        self.tabla_catalogo = TablaDatos(
            ["Código", "Nombre", "Tipo", "Unidad", "Precio Venta (S/)", "Stock Mín."],
            anchos={"Código": 90, "Nombre": 180, "Tipo": 120, "Unidad": 70,
                    "Precio Venta (S/)": 130, "Stock Mín.": 90},
        )
        pl.addWidget(self.tabla_catalogo, stretch=1)
        self.tutorial_targets["tabla_catalogo"] = self.tabla_catalogo

    def _ir_a_inteligencia(self):
        """Enlace de integración IA (sección 28): lleva al Centro de
        Inteligencia para ver la reposición recomendada de insumos."""
        ventana = self.window()
        if hasattr(ventana, "navegar"):
            ventana.navegar("centro_inteligencia")

    def refrescar(self):
        with nueva_sesion() as db:
            filas_stock, tags_stock = [], []
            for p in db.query(Producto).filter_by(activo=True).order_by(
                    Producto.tipo, Producto.nombre).all():
                stock = stock_total(db, p.id)
                if stock <= 0:
                    estado, tag = "🔴 Agotado", "alerta"
                elif stock < p.stock_minimo:
                    estado, tag = "🟡 Stock bajo", "advertencia"
                else:
                    estado, tag = "🟢 Normal", "exito"
                filas_stock.append([
                    p.id, p.codigo, p.nombre, p.tipo, f"{stock:.2f}",
                    p.unidad_medida or "—", f"{p.stock_minimo:.2f}", estado,
                ])
                tags_stock.append(tag)

            filas_lotes, tags_lotes = [], []
            lotes = (db.query(LoteInventario)
                     .order_by(LoteInventario.fecha_ingreso.asc(), LoteInventario.id.asc()).all())
            for lote in lotes:
                estado = formatear_estado(lote.estado)
                tag = "alerta" if lote.estado in ("VENCIDO", "AGOTADO") else "normal"
                filas_lotes.append([
                    lote.id, lote.numero_lote, lote.producto.nombre,
                    str(lote.fecha_ingreso),
                    str(lote.fecha_vencimiento) if lote.fecha_vencimiento else "—",
                    f"{lote.cantidad_disponible:.2f}", estado,
                ])
                tags_lotes.append(tag)

            filas_movimientos = []
            movimientos = (db.query(MovimientoInventario)
                            .order_by(MovimientoInventario.fecha.desc()).limit(300).all())
            for m in movimientos:
                filas_movimientos.append([
                    m.id, m.lote.producto.nombre if m.lote else "—",
                    m.lote.numero_lote if m.lote else "—", m.tipo,
                    f"{m.cantidad:.2f}", m.referencia or "—", str(m.fecha)[:16],
                ])

            filas_catalogo = []
            for p in db.query(Producto).filter_by(activo=True).order_by(
                    Producto.tipo, Producto.nombre).all():
                filas_catalogo.append([
                    p.id, p.codigo, p.nombre, p.tipo, p.unidad_medida or "—",
                    f"S/ {p.precio_venta:.2f}", f"{p.stock_minimo:.2f}",
                ])

        self.tabla_stock.cargar_filas(filas_stock, tags_por_fila=tags_stock)
        self.tabla_lotes.cargar_filas(filas_lotes, tags_por_fila=tags_lotes)
        self.tabla_movimientos.cargar_filas(filas_movimientos)
        self.tabla_catalogo.cargar_filas(filas_catalogo)

    def _abrir_ajuste(self):
        lote_id = self.tabla_lotes.id_seleccionado()
        if not lote_id:
            QMessageBox.warning(self, "Aviso", "Selecciona un lote de la lista primero.")
            return
        VentanaAjusteStock(self.window(), lote_id, al_guardar=self.refrescar).exec()

    def _abrir_nuevo_producto(self):
        VentanaProducto(self.window(), al_guardar=self.refrescar).exec()

    def _abrir_dialogo_reporte(self, clave="stock"):
        from app.ui.dialogo_reporte import DialogoReporte
        dlg = DialogoReporte(self.window(), modulo=clave)
        dlg.show()
        return dlg


# ══════════════════════════════════════════════════════════════════
#  Ajuste de stock
# ══════════════════════════════════════════════════════════════════

class VentanaAjusteStock(QDialog):
    def __init__(self, parent, lote_id, al_guardar):
        super().__init__(parent)
        self.setWindowTitle("Ajustar cantidad de lote")
        self.lote_id = lote_id
        self.al_guardar = al_guardar

        with nueva_sesion() as db:
            lote = db.get(LoteInventario, lote_id)
            texto_lote = f"{lote.numero_lote}  —  {lote.producto.nombre}"
            self.cantidad_actual = lote.cantidad_disponible

        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(0)

        franja = QWidget()
        fondo(franja, COLOR_PRIMARIO)
        fl = QVBoxLayout(franja)
        fl.setContentsMargins(20, 12, 20, 12)
        lbl = QLabel("⚖  Ajustar cantidad de lote")
        lbl.setStyleSheet("background: transparent; color: white;")
        lbl.setFont(fuente(13, negrita=True))
        fl.addWidget(lbl)
        layout.addWidget(franja)

        cuerpo = QVBoxLayout()
        cuerpo.setContentsMargins(20, 16, 20, 16)
        layout.addLayout(cuerpo)

        self._msg = MensajeEstado()
        cuerpo.addWidget(self._msg)

        lbl_lote = QLabel(texto_lote)
        lbl_lote.setFont(fuente(11, negrita=True))
        cuerpo.addWidget(lbl_lote)
        lbl_actual = QLabel(f"Cantidad disponible actual: {self.cantidad_actual:.2f}")
        lbl_actual.setStyleSheet(f"color: {COLOR_TEXTO_SECUNDARIO};")
        cuerpo.addWidget(lbl_actual)
        cuerpo.addSpacing(8)

        sec = SeccionFormulario("Datos del ajuste")
        secl = QVBoxLayout(sec)
        cuerpo.addWidget(sec)

        lbl_cant = QLabel("Nueva cantidad disponible *")
        lbl_cant.setFont(fuente(9, negrita=True))
        secl.addWidget(lbl_cant)
        self.entrada_cantidad = QLineEdit(str(self.cantidad_actual))
        secl.addWidget(self.entrada_cantidad)
        secl.addSpacing(6)

        lbl_motivo = QLabel("Motivo del ajuste *")
        lbl_motivo.setFont(fuente(9, negrita=True))
        secl.addWidget(lbl_motivo)
        self.entrada_motivo = QLineEdit()
        secl.addWidget(self.entrada_motivo)

        cuerpo.addStretch()
        fila_btn = QHBoxLayout()
        fila_btn.addStretch()
        btn_cancelar = QPushButton("Cancelar")
        poner_clase(btn_cancelar, "secundario")
        btn_cancelar.clicked.connect(self.reject)
        fila_btn.addWidget(btn_cancelar)
        btn_guardar = QPushButton("💾  Guardar ajuste")
        btn_guardar.clicked.connect(self._guardar)
        fila_btn.addWidget(btn_guardar)
        cuerpo.addLayout(fila_btn)

        centrar_ventana(self, 440, 380)

    def _guardar(self):
        try:
            nueva_cantidad = float(self.entrada_cantidad.text())
            if nueva_cantidad < 0:
                raise ValueError
        except ValueError:
            self._msg.mostrar("La cantidad debe ser un número mayor o igual a 0.", "error")
            return
        if not self.entrada_motivo.text().strip():
            self._msg.mostrar("El motivo del ajuste es obligatorio.", "error")
            return

        with nueva_sesion() as db:
            try:
                ajustar_stock(db, self.lote_id, nueva_cantidad,
                               motivo=self.entrada_motivo.text().strip(),
                               usuario_id=sesion_actual.usuario_id)
                db.commit()
            except Exception as error:
                self._msg.mostrar(f"No se pudo guardar el ajuste: {error}", "error", 0)
                return

        self.al_guardar()
        self.accept()

    def keyPressEvent(self, evento):
        if evento.key() == Qt.Key_Escape:
            self.reject()
        else:
            super().keyPressEvent(evento)


class VentanaProducto(QDialog):
    def __init__(self, parent, al_guardar):
        super().__init__(parent)
        self.setWindowTitle("Nuevo producto en el catálogo")
        self.al_guardar = al_guardar

        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(0)

        franja = QWidget()
        fondo(franja, COLOR_PRIMARIO)
        fl = QVBoxLayout(franja)
        fl.setContentsMargins(20, 12, 20, 12)
        lbl = QLabel("＋  Registrar nuevo producto")
        lbl.setStyleSheet("background: transparent; color: white;")
        lbl.setFont(fuente(13, negrita=True))
        fl.addWidget(lbl)
        layout.addWidget(franja)

        cuerpo = QVBoxLayout()
        cuerpo.setContentsMargins(20, 16, 20, 16)
        layout.addLayout(cuerpo)

        self._msg = MensajeEstado()
        cuerpo.addWidget(self._msg)

        sec = SeccionFormulario("Información del producto")
        secl = QGridLayout(sec)
        secl.setColumnStretch(1, 1)
        cuerpo.addWidget(sec)

        self.entrada_codigo = QLineEdit()
        self.entrada_codigo.setReadOnly(True)
        self.entrada_codigo.setStyleSheet(f"color: {COLOR_TEXTO_SECUNDARIO};")
        self.entrada_nombre = QLineEdit()
        self.combo_tipo = QComboBox()
        self.combo_tipo.addItems(["Insumo", "Producto terminado"])
        self.combo_tipo.currentTextChanged.connect(self._actualizar_codigo_sugerido)
        self.entrada_unidad = QLineEdit()
        self.entrada_unidad.setPlaceholderText("kg, L, g, unidad...")
        self.entrada_precio = QLineEdit("0")
        self.entrada_stock_minimo = QLineEdit("0")

        filas = [
            ("Código único", self.entrada_codigo, False),
            ("Nombre del producto *", self.entrada_nombre, True),
            ("Tipo de producto", self.combo_tipo, False),
            ("Unidad de medida", self.entrada_unidad, False),
            ("Precio de venta (S/)", self.entrada_precio, False),
            ("Stock mínimo", self.entrada_stock_minimo, False),
        ]
        for i, (etiqueta, widget, obligatorio) in enumerate(filas):
            lbl_campo = QLabel(etiqueta)
            lbl_campo.setFont(fuente(9, negrita=obligatorio))
            secl.addWidget(lbl_campo, i, 0)
            secl.addWidget(widget, i, 1)

        lbl_nota = QLabel("* Campo obligatorio  ·  el código se genera automáticamente según el tipo")
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
        btn_guardar = QPushButton("💾  Registrar producto")
        btn_guardar.clicked.connect(self._guardar)
        fila_btn.addWidget(btn_guardar)
        cuerpo.addLayout(fila_btn)

        centrar_ventana(self, 480, 420)
        self._actualizar_codigo_sugerido()

    def _actualizar_codigo_sugerido(self):
        with nueva_sesion() as db:
            self.entrada_codigo.setText(siguiente_codigo(db, self.combo_tipo.currentText()))

    def _guardar(self):
        nombre = self.entrada_nombre.text().strip()
        if not nombre:
            self._msg.mostrar("El nombre es obligatorio.", "error")
            return
        try:
            precio = float(self.entrada_precio.text() or 0)
            stock_minimo = float(self.entrada_stock_minimo.text() or 0)
        except ValueError:
            self._msg.mostrar("El precio y el stock mínimo deben ser números válidos.", "error")
            return

        with nueva_sesion() as db:
            # Se regenera el código aquí mismo, en vez de confiar en el
            # que se muestra en el campo (solo lectura, calculado al
            # abrir el diálogo o al cambiar el tipo): si alguien más
            # registró un producto del mismo tipo mientras este diálogo
            # estaba abierto, el código sugerido podría haber quedado
            # desactualizado. Así nunca puede chocar con uno existente.
            codigo = siguiente_codigo(db, self.combo_tipo.currentText())
            db.add(Producto(
                codigo=codigo, nombre=nombre, tipo=self.combo_tipo.currentText(),
                unidad_medida=self.entrada_unidad.text().strip(),
                precio_venta=precio, stock_minimo=stock_minimo, activo=True,
            ))
            db.commit()

        self.al_guardar()
        self.accept()

    def keyPressEvent(self, evento):
        if evento.key() == Qt.Key_Escape:
            self.reject()
        else:
            super().keyPressEvent(evento)
