"""
vista_dashboard.py
===================
Centro de operaciones: KPIs, alertas accionables y resumen operacional.
"""

import tkinter as tk
from tkinter import ttk
from datetime import date

from app.basedatos import nueva_sesion
from app.modelos import Producto, Proveedor, Cliente, OrdenVenta, OrdenProduccion
from app.logica_inventario import productos_bajo_minimo, lotes_proximos_a_vencer
from app.logica_configuracion import obtener_parametro_numerico
from app.ui.widgets import EncabezadoModulo, TarjetaKPI, MensajeEstado
from app.ui.estilos import (
    COLOR_ALERTA, COLOR_EXITO, COLOR_ADVERTENCIA,
    COLOR_TEXTO_SECUNDARIO, COLOR_FONDO, COLOR_PRIMARIO, COLOR_TARJETA
)


class VistaDashboard(ttk.Frame):
    def __init__(self, parent):
        super().__init__(parent)
        EncabezadoModulo(
            self,
            "Inicio — Panel de Control",
            "Resumen general de operaciones, alertas y estado del negocio",
            icono="🏠",
        ).pack(fill="x")

        # Área con scroll para el contenido
        self._canvas = tk.Canvas(self, bg=COLOR_FONDO, highlightthickness=0)
        scrollbar = ttk.Scrollbar(self, orient="vertical", command=self._canvas.yview)
        self._canvas.configure(yscrollcommand=scrollbar.set)
        scrollbar.pack(side="right", fill="y")
        self._canvas.pack(side="left", fill="both", expand=True)

        self._cuerpo = ttk.Frame(self._canvas, padding=(20, 16))
        self._cuerpo_id = self._canvas.create_window((0, 0), window=self._cuerpo, anchor="nw")
        self._cuerpo.bind("<Configure>", self._on_cuerpo_configure)
        self._canvas.bind("<Configure>", self._on_canvas_configure)

        self._construir_ui()
        self.refrescar()

    def _on_cuerpo_configure(self, event):
        self._canvas.configure(scrollregion=self._canvas.bbox("all"))

    def _on_canvas_configure(self, event):
        self._canvas.itemconfig(self._cuerpo_id, width=event.width)

    def _construir_ui(self):
        cuerpo = self._cuerpo

        # ── Sección: Indicadores principales ──────────────────────
        lbl_seccion1 = ttk.Label(cuerpo, text="INDICADORES GENERALES",
                                  font=("Segoe UI", 9, "bold"),
                                  foreground=COLOR_TEXTO_SECUNDARIO)
        lbl_seccion1.pack(anchor="w", pady=(0, 6))

        fila1 = ttk.Frame(cuerpo)
        fila1.pack(fill="x", pady=(0, 4))
        fila1.columnconfigure((0, 1, 2, 3), weight=1)

        self.kpi_productos = TarjetaKPI(fila1, "Productos activos", icono="📦")
        self.kpi_proveedores = TarjetaKPI(fila1, "Proveedores registrados", icono="🏭")
        self.kpi_clientes = TarjetaKPI(fila1, "Clientes registrados", icono="👥")
        self.kpi_ventas = TarjetaKPI(fila1, "Órdenes de venta", icono="🧾")
        for i, t in enumerate((self.kpi_productos, self.kpi_proveedores,
                                self.kpi_clientes, self.kpi_ventas)):
            t.grid(row=0, column=i, sticky="nsew", padx=4, pady=4)

        # ── Sección: Alertas e indicadores clave ──────────────────
        lbl_seccion2 = ttk.Label(cuerpo, text="ALERTAS Y ESTADO OPERACIONAL",
                                  font=("Segoe UI", 9, "bold"),
                                  foreground=COLOR_TEXTO_SECUNDARIO)
        lbl_seccion2.pack(anchor="w", pady=(16, 6))

        fila2 = ttk.Frame(cuerpo)
        fila2.pack(fill="x", pady=(0, 4))
        fila2.columnconfigure((0, 1, 2, 3), weight=1)

        self.kpi_stock_bajo = TarjetaKPI(fila2, "Productos con stock bajo",
                                          variante="alerta", icono="⚠️")
        self.kpi_produccion_activa = TarjetaKPI(fila2, "Lotes en producción",
                                                 variante="advertencia", icono="🍺")
        self.kpi_por_vencer = TarjetaKPI(fila2, "Lotes por vencer (30 días)",
                                          variante="alerta", icono="📅")
        self.kpi_ingresos_mes = TarjetaKPI(fila2, "Ingresos del mes",
                                            variante="exito", icono="💰")
        for i, t in enumerate((self.kpi_stock_bajo, self.kpi_produccion_activa,
                                self.kpi_por_vencer, self.kpi_ingresos_mes)):
            t.grid(row=0, column=i, sticky="nsew", padx=4, pady=4)

        # ── Capital inicial ────────────────────────────────────────
        fila3 = ttk.Frame(cuerpo)
        fila3.pack(fill="x", pady=(4, 16))
        self.kpi_capital_inicial = TarjetaKPI(fila3, "Capital inicial asignado (S/)")
        self.kpi_capital_inicial.pack(side="left", padx=4)
        ttk.Label(
            fila3,
            text="Monto de referencia con el que arrancó el negocio.\n"
                 "No incluye ingresos ni egresos posteriores.",
            foreground=COLOR_TEXTO_SECUNDARIO,
            font=("Segoe UI", 9),
        ).pack(side="left", padx=(12, 0))

        # ── Panel de alertas accionables ───────────────────────────
        self._frame_alertas = ttk.LabelFrame(
            cuerpo,
            text="  ⚠  Alertas de stock",
            padding=(16, 12)
        )
        self._frame_alertas.pack(fill="both", expand=True, pady=(0, 16))
        self._contenido_alertas = ttk.Frame(self._frame_alertas)
        self._contenido_alertas.pack(fill="both", expand=True)

        # ── Panel de vencimientos próximos ─────────────────────────
        self._frame_vencimientos = ttk.LabelFrame(
            cuerpo,
            text="  📅  Lotes próximos a vencer",
            padding=(16, 12)
        )
        self._frame_vencimientos.pack(fill="both", expand=True)
        self._contenido_vencimientos = ttk.Frame(self._frame_vencimientos)
        self._contenido_vencimientos.pack(fill="both", expand=True)

    def refrescar(self):
        with nueva_sesion() as db:
            n_productos         = db.query(Producto).filter_by(activo=True).count()
            n_proveedores       = db.query(Proveedor).filter_by(activo=True).count()
            n_clientes          = db.query(Cliente).filter_by(activo=True).count()
            n_ventas            = db.query(OrdenVenta).count()
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

        # Actualizar panel de alertas
        for w in self._contenido_alertas.winfo_children():
            w.destroy()
        if bajos:
            for b in bajos:
                fila = tk.Frame(self._contenido_alertas, bg=COLOR_FONDO)
                fila.pack(fill="x", pady=2)
                tk.Label(
                    fila,
                    text=f"🔴  {b['nombre']}",
                    bg=COLOR_FONDO, fg=COLOR_ALERTA,
                    font=("Segoe UI", 9, "bold"),
                    anchor="w"
                ).pack(side="left")
                tk.Label(
                    fila,
                    text=f" — Stock actual: {b['stock']:.1f} {b['unidad']}  "
                         f"(mínimo requerido: {b['minimo']})",
                    bg=COLOR_FONDO, fg=COLOR_TEXTO_SECUNDARIO,
                    font=("Segoe UI", 9),
                    anchor="w"
                ).pack(side="left")
        else:
            tk.Label(
                self._contenido_alertas,
                text="✅  Todos los productos tienen stock igual o superior al mínimo requerido.",
                bg=COLOR_FONDO, fg=COLOR_EXITO,
                font=("Segoe UI", 9),
            ).pack(anchor="w")

        # Actualizar panel de vencimientos
        for w in self._contenido_vencimientos.winfo_children():
            w.destroy()
        if por_vencer:
            for lote in por_vencer:
                fila = tk.Frame(self._contenido_vencimientos, bg=COLOR_FONDO)
                fila.pack(fill="x", pady=2)
                dias_restantes = (lote.fecha_vencimiento - date.today()).days if lote.fecha_vencimiento else "?"
                color = COLOR_ALERTA if isinstance(dias_restantes, int) and dias_restantes <= 7 else COLOR_ADVERTENCIA
                icono = "🔴" if isinstance(dias_restantes, int) and dias_restantes <= 7 else "🟡"
                tk.Label(
                    fila,
                    text=f"{icono}  {getattr(lote, 'producto', lote).nombre if hasattr(lote, 'producto') else lote.numero}",
                    bg=COLOR_FONDO, fg=color,
                    font=("Segoe UI", 9, "bold"),
                    anchor="w"
                ).pack(side="left")
                if lote.fecha_vencimiento:
                    tk.Label(
                        fila,
                        text=f"  — Vence el {lote.fecha_vencimiento.strftime('%d/%m/%Y')}"
                             f"  ({dias_restantes} días)",
                        bg=COLOR_FONDO, fg=COLOR_TEXTO_SECUNDARIO,
                        font=("Segoe UI", 9),
                    ).pack(side="left")
        else:
            tk.Label(
                self._contenido_vencimientos,
                text="✅  No hay lotes próximos a vencer en los próximos 30 días.",
                bg=COLOR_FONDO, fg=COLOR_EXITO,
                font=("Segoe UI", 9),
            ).pack(anchor="w")
