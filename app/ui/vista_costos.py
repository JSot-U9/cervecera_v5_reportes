"""
vista_costos.py
================
Módulo de Costos — mejoras UX:
- KPIs con iconos y variantes de color
- Formato monetario consistente S/ X,XXX.XX
- Encabezado simplificado
"""

from tkinter import ttk

from app.logica_costos import resumen_costos, kpis_costos
from app.ui.widgets import EncabezadoModulo, TarjetaKPI, BarraBusqueda, TablaDatos


class VistaCostos(ttk.Frame):
    def __init__(self, parent):
        super().__init__(parent)
        EncabezadoModulo(
            self,
            "Costos",
            "Análisis de costos reales y márgenes de ganancia por lote de producción cerrado",
            icono="📊",
        ).pack(fill="x")

        cuerpo = ttk.Frame(self, padding=12)
        cuerpo.pack(fill="both", expand=True)

        # ── KPIs ────────────────────────────────────────────────
        fila_kpis = ttk.Frame(cuerpo)
        fila_kpis.pack(fill="x", pady=(0, 12))
        fila_kpis.columnconfigure((0, 1, 2, 3), weight=1)

        self.kpi_costo_total     = TarjetaKPI(fila_kpis, "Costo total acumulado",
                                               variante="alerta", icono="💸")
        self.kpi_margen_prom     = TarjetaKPI(fila_kpis, "Margen de ganancia promedio",
                                               variante="exito", icono="📈")
        self.kpi_costo_unit_prom = TarjetaKPI(fila_kpis, "Costo unitario promedio",
                                               icono="🔢")
        self.kpi_n_lotes         = TarjetaKPI(fila_kpis, "Lotes de producción costeados",
                                               icono="🍺")
        for i, t in enumerate((self.kpi_costo_total, self.kpi_margen_prom,
                                self.kpi_costo_unit_prom, self.kpi_n_lotes)):
            t.grid(row=0, column=i, sticky="nsew", padx=4)

        # ── Barra búsqueda + reporte ───────────────────────────
        barra = BarraBusqueda(cuerpo, al_escribir=lambda t: self.tabla.filtrar(t),
                               placeholder="🔎  Buscar lote, producto...")
        barra.agregar_boton("📊  Reporte", self._abrir_dialogo_reporte,
                             estilo="AccionSecundaria.TButton")
        barra.pack(fill="x", pady=(0, 8))

        # ── Tabla de costos ──────────────────────────────────────
        contenedor_tabla = ttk.Frame(cuerpo)
        contenedor_tabla.pack(fill="both", expand=True)
        self.tabla = TablaDatos(
            contenedor_tabla,
            [
                "N° Orden", "N° Lote", "Producto",
                "Cantidad (L)", "Insumos (S/)", "M.O. (S/)",
                "Indirectos (S/)", "Total (S/)",
                "Unit. (S/)", "Margen (%)",
            ],
            anchos={
                "N° Orden": 95, "N° Lote": 110, "Producto": 160,
                "Cantidad (L)": 90, "Insumos (S/)": 100, "M.O. (S/)": 90,
                "Indirectos (S/)": 100, "Total (S/)": 100,
                "Unit. (S/)": 90, "Margen (%)": 90,
            },
        )
        self.tabla.empaquetar()

        self.refrescar()

    def refrescar(self):
        filas_resumen = resumen_costos()
        kpis = kpis_costos()

        self.kpi_costo_total.actualizar(f"S/ {kpis['costo_total']:,.2f}")
        self.kpi_margen_prom.actualizar(f"{kpis['margen_promedio']:.1f} %")
        self.kpi_costo_unit_prom.actualizar(f"S/ {kpis['costo_unitario_promedio']:.2f}")
        self.kpi_n_lotes.actualizar(str(kpis["n_lotes"]))

        filas = [
            [
                i + 1,
                f["orden"], f["lote"], f["producto"],
                f"{f['cantidad']:.1f}",
                f"S/ {f['costo_insumos']:.2f}",
                f"S/ {f['costo_mano_obra']:.2f}",
                f"S/ {f['costo_indirectos']:.2f}",
                f"S/ {f['costo_total']:.2f}",
                f"S/ {f['costo_unitario']:.2f}",
                f"{f['margen_porcentaje']:.1f} %",
            ]
            for i, f in enumerate(filas_resumen)
        ]
        self.tabla.cargar_filas(filas)

    def _abrir_dialogo_reporte(self):
        from app.ui.dialogo_reporte import DialogoReporte
        DialogoReporte(self.winfo_toplevel(), modulo="costos")
