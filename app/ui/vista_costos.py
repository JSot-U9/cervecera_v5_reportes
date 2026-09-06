"""
vista_costos.py
================
Módulo de Costos: análisis de costos y márgenes por lote de producción.

Vista de solo lectura: los costos se calculan automáticamente al cerrar
cada orden de producción.

El botón «Reportes» abre el DialogoReporte, donde el usuario puede:
  - elegir el tipo de reporte y el formato (PDF / XLSX / CSV)
  - ver una vista previa de los datos
  - guardar el archivo en la ruta que prefiera
"""

from tkinter import ttk

from app.logica_costos import resumen_costos, kpis_costos
from app.ui.widgets import EncabezadoModulo, TarjetaKPI, BarraBusqueda, TablaDatos


class VistaCostos(ttk.Frame):
    def __init__(self, parent):
        super().__init__(parent)
        EncabezadoModulo(
            self,
            "Módulo de Costos",
            "Análisis de costos reales y márgenes de ganancia por cada lote de producción cerrado",
        ).pack(fill="x")

        cuerpo = ttk.Frame(self, padding=12)
        cuerpo.pack(fill="both", expand=True)

        # ── KPIs ────────────────────────────────────────────────
        fila_kpis = ttk.Frame(cuerpo)
        fila_kpis.pack(fill="x", pady=(0, 10))
        self.kpi_costo_total     = TarjetaKPI(fila_kpis, "Costo total acumulado (S/)")
        self.kpi_margen_prom     = TarjetaKPI(fila_kpis, "Margen de ganancia promedio (%)")
        self.kpi_costo_unit_prom = TarjetaKPI(fila_kpis, "Costo unitario promedio (S/)")
        self.kpi_n_lotes         = TarjetaKPI(fila_kpis, "Lotes de producción costeados")
        for tarjeta in (self.kpi_costo_total, self.kpi_margen_prom,
                        self.kpi_costo_unit_prom, self.kpi_n_lotes):
            tarjeta.pack(side="left", fill="x", expand=True, padx=4)

        # ── Barra con búsqueda y botón de reportes ──────────────
        barra = BarraBusqueda(cuerpo, al_escribir=lambda t: self.tabla.filtrar(t))
        barra.agregar_boton("📊  Generar reporte…", self._abrir_dialogo_reporte)
        barra.pack(fill="x", pady=(0, 8))

        # ── Tabla de costos ──────────────────────────────────────
        contenedor_tabla = ttk.Frame(cuerpo)
        contenedor_tabla.pack(fill="both", expand=True)
        self.tabla = TablaDatos(
            contenedor_tabla,
            [
                "N° de Orden de Producción", "N° de Lote", "Producto Elaborado",
                "Cantidad (L)", "Costo Insumos (S/)", "Costo M.O. (S/)",
                "Costos Indirectos (S/)", "Costo Total (S/)",
                "Costo Unitario (S/)", "Margen de Ganancia (%)",
            ],
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
