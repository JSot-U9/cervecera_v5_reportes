"""vista_inventario.py (PySide6)
=================================
Stock actual · Lotes FIFO · Movimientos · Catálogo de productos.
"""

from PySide6.QtCore import Qt
from PySide6.QtGui import QShortcut, QKeySequence
from PySide6.QtWidgets import (
    QWidget, QDialog, QVBoxLayout, QHBoxLayout, QGridLayout, QLabel,
    QLineEdit, QComboBox, QPushButton, QTabWidget, QStackedWidget, QMessageBox,
)

from app.basedatos import nueva_sesion
from app.modelos import Producto, LoteInventario, MovimientoInventario
from app.sesion import sesion_actual
from app.seguridad import puede, modulos_visibles
from app.logica_inventario import (
    stock_total, ajustar_stock, siguiente_codigo,
    desactivar_producto, lotes_con_stock_de_producto,
)
from app.ui.widgets import (
    EncabezadoModulo, BarraBusqueda, TablaDatos, SeccionFormulario, MensajeEstado,
    centrar_ventana, formatear_estado, tag_para_estado, BotonAyuda,
    EstadoVacio, conectar_pestanas_a_header, texto_pestana_legible,
    CampoFormulario, conectar_boton_a_validez, confirmar,
)
from app.ui.vista_detalle_producto import VistaDetalleProducto
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

        # Un QStackedWidget con dos páginas: [0] las pestañas normales
        # del módulo, [1] el detalle de un producto (Parte 3). Antes no
        # existía forma de "entrar" a un producto — Inventario era
        # solo tablas planas. Usar la misma instancia de página en vez
        # de una ventana/diálogo aparte es lo que permite que "‹
        # Volver" regrese exactamente al filtro y a la pestaña donde
        # el usuario los dejó, sin reconstruir nada.
        self._stack = QStackedWidget()
        layout.addWidget(self._stack, stretch=1)

        self.notebook = QTabWidget()
        self._stack.addWidget(self.notebook)

        self._detalle_producto = VistaDetalleProducto(
            volver=self._volver_de_detalle, al_guardar=self.refrescar)
        self._stack.addWidget(self._detalle_producto)

        self._pestana_stock()
        self._pestana_lotes()
        self._pestana_movimientos()
        self._pestana_catalogo()
        conectar_pestanas_a_header(self.notebook, self)

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
            al_doble_clic=self._abrir_detalle_producto,
            estado_vacio=EstadoVacio(
                "📦", "Sin productos que mostrar",
                "No hay productos activos con stock registrado, o el filtro no "
                "encontró coincidencias.",
            ),
        )
        pl.addWidget(self.tabla_stock, stretch=1)
        self.tutorial_targets["tabla_stock"] = self.tabla_stock

        lbl_pista = QLabel("💡 Doble clic en un producto para ver su detalle completo.")
        lbl_pista.setStyleSheet(f"color: {COLOR_TEXTO_SECUNDARIO};")
        lbl_pista.setFont(fuente(8, cursiva=True))
        pl.addWidget(lbl_pista)

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
            estado_vacio=EstadoVacio(
                "🗂", "Sin lotes que mostrar",
                "Todavía no se registró ningún lote de inventario, o el filtro no "
                "encontró coincidencias. Los lotes se crean automáticamente al "
                "registrar una compra o cerrar una producción.",
            ),
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
            estado_vacio=EstadoVacio(
                "📋", "Sin movimientos que mostrar",
                "Todavía no hay movimientos de inventario registrados, o el "
                "filtro no encontró coincidencias.",
            ),
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
            self.accion_nuevo = self._abrir_nuevo_producto  # Ctrl+N global
            barra.agregar_boton("🗑  Desactivar", self._desactivar_producto, estilo="peligro")
        pl.addWidget(barra)

        self.tabla_catalogo = TablaDatos(
            ["Código", "Nombre", "Tipo", "Unidad", "Precio Venta (S/)", "Stock Mín."],
            anchos={"Código": 90, "Nombre": 180, "Tipo": 120, "Unidad": 70,
                    "Precio Venta (S/)": 130, "Stock Mín.": 90},
            estado_vacio=EstadoVacio(
                "📦", "Sin productos en el catálogo",
                "Todavía no se registró ningún producto, o el filtro no encontró "
                "coincidencias.",
                texto_accion=("＋ Nuevo producto" if puede_editar else ""),
                accion=(self._abrir_nuevo_producto if puede_editar else None),
            ),
        )
        pl.addWidget(self.tabla_catalogo, stretch=1)
        self.tutorial_targets["tabla_catalogo"] = self.tabla_catalogo

    def _ir_a_inteligencia(self):
        """Enlace de integración IA (sección 28): lleva al Centro de
        Inteligencia para ver la reposición recomendada de insumos."""
        ventana = self.window()
        if hasattr(ventana, "navegar"):
            ventana.navegar("centro_inteligencia")

    def _abrir_detalle_producto(self, producto_id):
        """Doble clic en una fila de Stock Actual: entra a la vista de
        detalle (Parte 3), cambiando de página del QStackedWidget sin
        reconstruir la tabla que queda detrás."""
        if not producto_id:
            return
        self._detalle_producto.cargar(producto_id)
        self._stack.setCurrentWidget(self._detalle_producto)

    def _volver_de_detalle(self):
        """'‹ Volver' desde el detalle de producto: regresa a las
        pestañas del módulo en el mismo estado de filtro/pestaña en
        que estaban (nunca se reconstruyeron), y reacomoda el
        breadcrumb del header a la pestaña interna que sigue activa."""
        self._stack.setCurrentWidget(self.notebook)
        ventana = self.window()
        if hasattr(ventana, "actualizar_pestana_interna"):
            ventana.actualizar_pestana_interna(
                texto_pestana_legible(self.notebook.tabText(self.notebook.currentIndex()))
            )

    def refrescar(self):
        with nueva_sesion() as db:
            filas_stock, tags_stock = [], []
            for p in db.query(Producto).filter_by(activo=True).order_by(
                    Producto.tipo, Producto.nombre).all():
                stock = stock_total(db, p.id)
                if stock <= 0:
                    estado_interno = "AGOTADO"
                elif stock < p.stock_minimo:
                    estado_interno = "BAJO"
                else:
                    estado_interno = "NORMAL"
                estado, tag = formatear_estado(estado_interno), tag_para_estado(estado_interno)
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
                tag = tag_para_estado(lote.estado)
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
                    m.lote.numero_lote if m.lote else "—",
                    formatear_estado(m.tipo),   # ícono + texto legible, nunca solo el string interno
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

    def _desactivar_producto(self):
        """Desactiva el producto seleccionado en Catálogo (Parte 5):
        soft-delete con confirmación destructiva que muestra el
        impacto real (cuántos lotes con stock quedarían huérfanos del
        catálogo activo), no solo una advertencia genérica."""
        fila = self.tabla_catalogo.currentRow()
        producto_id = self.tabla_catalogo.id_seleccionado()
        if not producto_id:
            QMessageBox.warning(self, "Aviso", "Selecciona un producto de la lista primero.")
            return
        item_nombre = self.tabla_catalogo.item(fila, 1)
        nombre_producto = item_nombre.text() if item_nombre else "este producto"

        with nueva_sesion() as db:
            n_lotes = lotes_con_stock_de_producto(db, producto_id)
        detalle_stock = (
            f"Tiene {n_lotes} lote{'s' if n_lotes != 1 else ''} con stock disponible; "
            "seguirán existiendo en el historial, pero el producto dejará de "
            "aparecer en el catálogo activo y en los selectores de nuevas "
            "órdenes o producción."
            if n_lotes > 0 else
            "No tiene lotes con stock disponible en este momento."
        )
        ok = confirmar(
            self, "Desactivar producto",
            f"¿Deseas desactivar «{nombre_producto}»?\n\n{detalle_stock}",
            texto_confirmar="Desactivar producto", texto_cancelar="Cancelar", peligro=True,
        )
        if not ok:
            return
        with nueva_sesion() as db:
            try:
                desactivar_producto(db, producto_id)
            except ValueError as error:
                QMessageBox.critical(self, "No se pudo desactivar", str(error))
                return
        self.refrescar()

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

        self.campo_cantidad = CampoFormulario(
            "Nueva cantidad disponible", obligatorio=True, tipo="numero",
            permitir_negativo=False)
        self.campo_cantidad.set(str(self.cantidad_actual))
        self.campo_motivo = CampoFormulario("Motivo del ajuste", obligatorio=True)
        secl.addWidget(self.campo_cantidad)
        secl.addWidget(self.campo_motivo)

        cuerpo.addStretch()
        fila_btn = QHBoxLayout()
        fila_btn.addStretch()
        btn_cancelar = QPushButton("Cancelar")
        poner_clase(btn_cancelar, "secundario")
        btn_cancelar.clicked.connect(self.reject)
        fila_btn.addWidget(btn_cancelar)
        self.btn_guardar = QPushButton("💾  Guardar ajuste")
        self.btn_guardar.clicked.connect(self._guardar)
        QShortcut(QKeySequence("Ctrl+S"), self).activated.connect(self.btn_guardar.click)
        fila_btn.addWidget(self.btn_guardar)
        cuerpo.addLayout(fila_btn)

        conectar_boton_a_validez(self.btn_guardar, [self.campo_cantidad, self.campo_motivo])
        centrar_ventana(self, 440, 380)

    def _guardar(self):
        campos = (self.campo_cantidad, self.campo_motivo)
        if not all(c.validar() for c in campos):
            return
        nueva_cantidad = self.campo_cantidad.valor_numero()
        motivo = self.campo_motivo.get()

        with nueva_sesion() as db:
            try:
                ajustar_stock(db, self.lote_id, nueva_cantidad,
                               motivo=motivo, usuario_id=sesion_actual.usuario_id)
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
        secl = QVBoxLayout(sec)
        cuerpo.addWidget(sec)

        self.campo_codigo = CampoFormulario("Código único", readonly=True)
        self.campo_nombre = CampoFormulario("Nombre del producto", obligatorio=True)
        self.campo_tipo = CampoFormulario(
            "Tipo de producto", tipo="combobox",
            opciones=["Insumo", "Producto terminado"],
        )
        self.campo_tipo.widget.currentTextChanged.connect(self._actualizar_codigo_sugerido)
        self.campo_unidad = CampoFormulario("Unidad de medida")
        self.campo_unidad.widget.setPlaceholderText("kg, L, g, unidad...")
        self.campo_precio = CampoFormulario(
            "Precio de venta (S/)", tipo="numero", permitir_negativo=False)
        self.campo_precio.set("0")
        self.campo_stock_minimo = CampoFormulario(
            "Stock mínimo", tipo="numero", permitir_negativo=False)
        self.campo_stock_minimo.set("0")

        for campo in (self.campo_codigo, self.campo_nombre, self.campo_tipo,
                      self.campo_unidad, self.campo_precio, self.campo_stock_minimo):
            secl.addWidget(campo)

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
        self.btn_guardar = QPushButton("💾  Registrar producto")
        self.btn_guardar.clicked.connect(self._guardar)
        QShortcut(QKeySequence("Ctrl+S"), self).activated.connect(self.btn_guardar.click)
        fila_btn.addWidget(self.btn_guardar)
        cuerpo.addLayout(fila_btn)

        conectar_boton_a_validez(
            self.btn_guardar,
            [self.campo_nombre, self.campo_precio, self.campo_stock_minimo],
        )

        centrar_ventana(self, 480, 420)
        self._actualizar_codigo_sugerido()

    def _actualizar_codigo_sugerido(self):
        with nueva_sesion() as db:
            self.campo_codigo.set(siguiente_codigo(db, self.campo_tipo.get()))

    def _guardar(self):
        # La validación en tiempo real ya mantiene "Guardar"
        # deshabilitado mientras haya errores — este validar() final
        # solo cubre el caso de un campo que el usuario nunca llegó a
        # tocar (ej. hizo clic en Guardar sin pasar por el campo
        # obligatorio vacío).
        campos = (self.campo_nombre, self.campo_precio, self.campo_stock_minimo)
        if not all(c.validar() for c in campos):
            return
        nombre = self.campo_nombre.get()
        precio = self.campo_precio.valor_numero()
        stock_minimo = self.campo_stock_minimo.valor_numero()

        with nueva_sesion() as db:
            # Se regenera el código aquí mismo, en vez de confiar en el
            # que se muestra en el campo (solo lectura, calculado al
            # abrir el diálogo o al cambiar el tipo): si alguien más
            # registró un producto del mismo tipo mientras este diálogo
            # estaba abierto, el código sugerido podría haber quedado
            # desactualizado. Así nunca puede chocar con uno existente.
            codigo = siguiente_codigo(db, self.campo_tipo.get())
            db.add(Producto(
                codigo=codigo, nombre=nombre, tipo=self.campo_tipo.get(),
                unidad_medida=self.campo_unidad.get(),
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
