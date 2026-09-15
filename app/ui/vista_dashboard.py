"""vista_dashboard.py (PySide6)
================================
Centro de operaciones: KPIs, alertas accionables y resumen operacional.
"""

from datetime import date

from PySide6.QtCore import Qt
from PySide6.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QGridLayout, QLabel,
    QScrollArea,
)

from app.basedatos import nueva_sesion
from app.modelos import Producto, Proveedor, Cliente, OrdenVenta, OrdenProduccion
from app.logica_inventario import productos_bajo_minimo, lotes_proximos_a_vencer
from app.logica_configuracion import obtener_parametro_numerico
from app.ui.widgets import EncabezadoModulo, TarjetaKPI, PanelTitulado
from app.ui.estilos import COLOR_ALERTA, COLOR_EXITO, COLOR_ADVERTENCIA, COLOR_TEXTO_SECUNDARIO, fuente


class VistaDashboard(QWidget):
    def __init__(self, parent=None):
        super().__init__(parent)
        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(0)

        layout.addWidget(EncabezadoModulo(
            "Inicio — Panel de Control",
            "Resumen general de operaciones, alertas y estado del negocio",
            icono="🏠",
        ))

        scroll = QScrollArea()
        scroll.setWidgetResizable(True)
        scroll.setFrameShape(QScrollArea.NoFrame)
        layout.addWidget(scroll, stretch=1)

        cuerpo = QWidget()
        scroll.setWidget(cuerpo)
        self._cuerpo_layout = QVBoxLayout(cuerpo)
        self._cuerpo_layout.setContentsMargins(20, 16, 20, 16)
        self._cuerpo_layout.setSpacing(6)

        self._construir_ui()
        self.refrescar()

    def _titulo_seccion(self, texto: str) -> QLabel:
        lbl = QLabel(texto)
        lbl.setFont(fuente(9, negrita=True))
        lbl.setStyleSheet(f"color: {COLOR_TEXTO_SECUNDARIO};")
        return lbl

    def _construir_ui(self):
        cl = self._cuerpo_layout

        cl.addWidget(self._titulo_seccion("INDICADORES GENERALES"))
        fila1 = QGridLayout()
        fila1.setSpacing(8)
        self.kpi_productos = TarjetaKPI("Productos activos", icono="📦")
        self.kpi_proveedores = TarjetaKPI("Proveedores registrados", icono="🏭")
        self.kpi_clientes = TarjetaKPI("Clientes registrados", icono="👥")
        self.kpi_ventas = TarjetaKPI("Órdenes de venta", icono="🧾")
        for i, t in enumerate((self.kpi_productos, self.kpi_proveedores,
                                self.kpi_clientes, self.kpi_ventas)):
            fila1.addWidget(t, 0, i)
            fila1.setColumnStretch(i, 1)
        cl.addLayout(fila1)
        cl.addSpacing(10)

        cl.addWidget(self._titulo_seccion("ALERTAS Y ESTADO OPERACIONAL"))
        fila2 = QGridLayout()
        fila2.setSpacing(8)
        self.kpi_stock_bajo = TarjetaKPI("Productos con stock bajo", variante="alerta", icono="⚠️")
        self.kpi_produccion_activa = TarjetaKPI("Lotes en producción", variante="advertencia", icono="🍺")
        self.kpi_por_vencer = TarjetaKPI("Lotes por vencer (30 días)", variante="alerta", icono="📅")
        self.kpi_ingresos_mes = TarjetaKPI("Ingresos del mes", variante="exito", icono="💰")
        for i, t in enumerate((self.kpi_stock_bajo, self.kpi_produccion_activa,
                                self.kpi_por_vencer, self.kpi_ingresos_mes)):
            fila2.addWidget(t, 0, i)
            fila2.setColumnStretch(i, 1)
        cl.addLayout(fila2)
        cl.addSpacing(10)

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
        cl.addSpacing(6)

        self._grupo_alertas = PanelTitulado("⚠  Alertas de stock")
        self._layout_alertas = self._grupo_alertas.layout_interior
        cl.addWidget(self._grupo_alertas)

        self._grupo_vencimientos = PanelTitulado("📅  Lotes próximos a vencer")
        self._layout_vencimientos = self._grupo_vencimientos.layout_interior
        cl.addWidget(self._grupo_vencimientos)

        cl.addStretch()

    def _limpiar_layout(self, layout):
        while layout.count():
            item = layout.takeAt(0)
            w = item.widget()
            if w is not None:
                w.deleteLater()

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
        self.kpi_stock_bajo.actualizar(str(len(bajos)))
        self.kpi_produccion_activa.actualizar(str(n_produccion_activa))
        self.kpi_por_vencer.actualizar(str(len(por_vencer)))
        self.kpi_ingresos_mes.actualizar(f"S/ {total_mes:,.2f}")
        self.kpi_capital_inicial.actualizar(f"S/ {capital_inicial:,.2f}")

        self._limpiar_layout(self._layout_alertas)
        if bajos:
            for b in bajos:
                fila = QHBoxLayout()
                lbl1 = QLabel(f"🔴  {b['nombre']}")
                lbl1.setStyleSheet(f"color: {COLOR_ALERTA};")
                lbl1.setFont(fuente(9, negrita=True))
                fila.addWidget(lbl1)
                lbl2 = QLabel(f" — Stock actual: {b['stock']:.1f} {b['unidad']}  "
                              f"(mínimo requerido: {b['minimo']})")
                lbl2.setStyleSheet(f"color: {COLOR_TEXTO_SECUNDARIO};")
                lbl2.setFont(fuente(9))
                fila.addWidget(lbl2)
                fila.addStretch()
                contenedor = QWidget()
                contenedor.setLayout(fila)
                self._layout_alertas.addWidget(contenedor)
        else:
            lbl_ok = QLabel("✅  Todos los productos tienen stock igual o superior al mínimo requerido.")
            lbl_ok.setStyleSheet(f"color: {COLOR_EXITO};")
            lbl_ok.setFont(fuente(9))
            self._layout_alertas.addWidget(lbl_ok)

        self._limpiar_layout(self._layout_vencimientos)
        if por_vencer:
            for lote in por_vencer:
                fila = QHBoxLayout()
                fv = lote["fecha_vencimiento"]
                dias_restantes = (fv - date.today()).days if fv else "?"
                critico = isinstance(dias_restantes, int) and dias_restantes <= 7
                color = COLOR_ALERTA if critico else COLOR_ADVERTENCIA
                icono = "🔴" if critico else "🟡"
                nombre = lote["nombre"]
                lbl1 = QLabel(f"{icono}  {nombre}")
                lbl1.setStyleSheet(f"color: {color};")
                lbl1.setFont(fuente(9, negrita=True))
                fila.addWidget(lbl1)
                if fv:
                    lbl2 = QLabel(f"  — Vence el {fv.strftime('%d/%m/%Y')}"
                                  f"  ({dias_restantes} días)")
                    lbl2.setStyleSheet(f"color: {COLOR_TEXTO_SECUNDARIO};")
                    lbl2.setFont(fuente(9))
                    fila.addWidget(lbl2)
                fila.addStretch()
                contenedor = QWidget()
                contenedor.setLayout(fila)
                self._layout_vencimientos.addWidget(contenedor)
        else:
            lbl_ok = QLabel("✅  No hay lotes próximos a vencer en los próximos 30 días.")
            lbl_ok.setStyleSheet(f"color: {COLOR_EXITO};")
            lbl_ok.setFont(fuente(9))
            self._layout_vencimientos.addWidget(lbl_ok)