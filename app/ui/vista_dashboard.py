"""
vista_dashboard.py
===================
Pantalla de inicio: muestra números resumidos (KPIs) y alertas de
stock bajo. No permite crear ni editar nada, solo informa.
"""

from tkinter import ttk
from datetime import date

from app.basedatos import nueva_sesion
from app.modelos import Producto, Proveedor, Cliente, OrdenVenta, OrdenProduccion
from app.logica_inventario import productos_bajo_minimo, lotes_proximos_a_vencer
from app.logica_configuracion import obtener_parametro_numerico
from app.ui.widgets import EncabezadoModulo, TarjetaKPI
from app.ui.estilos import COLOR_ALERTA, COLOR_EXITO, COLOR_TEXTO_SECUNDARIO


class VistaDashboard(ttk.Frame):
    def __init__(self, parent):
        super().__init__(parent)
        EncabezadoModulo(
            self,
            "Sistema de la Cervecería del Valle Sagrado",
            "Resumen general de operaciones y alertas de inventario",
        ).pack(fill="x")

        cuerpo = ttk.Frame(self, padding=16)
        cuerpo.pack(fill="both", expand=True)

        # ── Fila 1: métricas generales ───────────────────────────
        fila1 = ttk.Frame(cuerpo)
        fila1.pack(fill="x", pady=(0, 10))
        self.kpi_productos    = TarjetaKPI(fila1, "Productos activos en catálogo")
        self.kpi_proveedores  = TarjetaKPI(fila1, "Proveedores registrados")
        self.kpi_clientes     = TarjetaKPI(fila1, "Clientes registrados")
        self.kpi_ventas       = TarjetaKPI(fila1, "Órdenes de venta totales")
        for tarjeta in (self.kpi_productos, self.kpi_proveedores,
                        self.kpi_clientes, self.kpi_ventas):
            tarjeta.pack(side="left", fill="x", expand=True, padx=4)

        # ── Fila 2: alertas e indicadores clave ──────────────────
        fila2 = ttk.Frame(cuerpo)
        fila2.pack(fill="x", pady=(0, 10))
        self.kpi_stock_bajo        = TarjetaKPI(fila2, "Productos con stock bajo mínimo",
                                                variante="alerta")
        self.kpi_produccion_activa = TarjetaKPI(fila2, "Lotes en producción activa")
        self.kpi_por_vencer        = TarjetaKPI(fila2, "Lotes próximos a vencer (30 días)",
                                                variante="alerta")
        self.kpi_ingresos_mes      = TarjetaKPI(fila2, "Ingresos del mes en curso (S/)",
                                                variante="exito")
        for tarjeta in (self.kpi_stock_bajo, self.kpi_produccion_activa,
                        self.kpi_por_vencer, self.kpi_ingresos_mes):
            tarjeta.pack(side="left", fill="x", expand=True, padx=4)

        # ── Fila 3: capital de referencia ─────────────────────────
        fila3 = ttk.Frame(cuerpo)
        fila3.pack(fill="x", pady=(0, 16))
        self.kpi_capital_inicial = TarjetaKPI(fila3, "Capital inicial asignado (S/)")
        self.kpi_capital_inicial.pack(side="left", fill="x", expand=True, padx=4)
        ttk.Label(
            fila3,
            text="Monto de referencia con el que arrancó el negocio.\n"
                 "No incluye ingresos ni egresos posteriores (no es un\n"
                 "módulo de tesorería completo).",
            foreground=COLOR_TEXTO_SECUNDARIO, justify="left",
        ).pack(side="left", padx=(12, 0))

        # ── Alertas de stock ──────────────────────────────────────
        grupo_alertas = ttk.LabelFrame(cuerpo, text="⚠  Alertas de stock bajo mínimo",
                                        padding=12)
        grupo_alertas.pack(fill="both", expand=True)
        self.etiqueta_alertas = ttk.Label(grupo_alertas, text="—",
                                           justify="left", wraplength=780)
        self.etiqueta_alertas.pack(anchor="w")

        self.refrescar()

    def refrescar(self):
        with nueva_sesion() as db:
            n_productos        = db.query(Producto).filter_by(activo=True).count()
            n_proveedores      = db.query(Proveedor).filter_by(activo=True).count()
            n_clientes         = db.query(Cliente).filter_by(activo=True).count()
            n_ventas           = db.query(OrdenVenta).count()
            n_produccion_activa = db.query(OrdenProduccion).filter(
                OrdenProduccion.estado.in_(["INICIADA", "EN_PROCESO"])
            ).count()

            bajos      = productos_bajo_minimo(db)
            por_vencer = lotes_proximos_a_vencer(db, dias=30)

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

        if bajos:
            texto = "\n".join(
                f"• {b['nombre']} — stock actual: {b['stock']:.1f} {b['unidad']}"
                f"  (mínimo requerido: {b['minimo']})"
                for b in bajos
            )
            self.etiqueta_alertas.config(text=texto, foreground=COLOR_ALERTA)
        else:
            self.etiqueta_alertas.config(
                text="✔  Todos los productos tienen stock igual o superior al mínimo requerido.",
                foreground=COLOR_EXITO)