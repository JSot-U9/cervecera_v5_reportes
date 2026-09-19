"""vista_costos.py (PySide6)
=============================
Análisis de costos reales y márgenes de ganancia por lote de producción cerrado.
"""

from PySide6.QtWidgets import QWidget, QVBoxLayout, QHBoxLayout, QGridLayout, QPushButton, QMessageBox

from app.logica_costos import resumen_costos, kpis_costos
from app.ui.widgets import EncabezadoModulo, TarjetaKPI, BarraBusqueda, TablaDatos
from app.ui.estilos import poner_clase

_TEXTO_COSTOS = (
    "Al cerrar una orden de producción, el sistema suma el costo de los insumos "
    "consumidos (FIFO), la mano de obra y los costos indirectos. Con ese total "
    "calcula el costo unitario y, comparándolo con el precio de venta, el margen "
    "de ganancia."
)


class VistaCostos(QWidget):
    def __init__(self, parent=None):
        super().__init__(parent)
        self.tutorial_targets = {}

        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(0)
        layout.addWidget(EncabezadoModulo(
            "Reportes de ventas", "Análisis de costos reales y márgenes de ganancia por lote de producción cerrado",
            icono="📊",
        ))

        cuerpo = QVBoxLayout()
        cuerpo.setContentsMargins(12, 10, 12, 10)
        layout.addLayout(cuerpo, stretch=1)

        fila_titulo = QHBoxLayout()
        fila_titulo.addStretch()
        btn_ayuda = QPushButton("❓")
        btn_ayuda.setFixedWidth(30)
        poner_clase(btn_ayuda, "secundario")
        btn_ayuda.clicked.connect(
            lambda: QMessageBox.information(self, "¿Cómo se calculan los costos?", _TEXTO_COSTOS))
        fila_titulo.addWidget(btn_ayuda)
        cuerpo.addLayout(fila_titulo)

        fila_kpis = QGridLayout()
        cuerpo.addLayout(fila_kpis)
        self.kpi_costo_total = TarjetaKPI("Costo total acumulado", variante="alerta", icono="💸")
        self.kpi_margen_prom = TarjetaKPI("Margen de ganancia promedio", variante="exito", icono="📈")
        self.kpi_costo_unit_prom = TarjetaKPI("Costo unitario promedio", icono="🔢")
        self.kpi_n_lotes = TarjetaKPI("Lotes de producción costeados", icono="🍺")
        for i, t in enumerate((self.kpi_costo_total, self.kpi_margen_prom,
                                self.kpi_costo_unit_prom, self.kpi_n_lotes)):
            fila_kpis.addWidget(t, 0, i)
            fila_kpis.setColumnStretch(i, 1)
        self.tutorial_targets["kpi_costo_total"] = self.kpi_costo_total
        cuerpo.addSpacing(8)

        barra = BarraBusqueda(al_escribir=lambda t: self.tabla.filtrar(t),
                               placeholder="🔎  Buscar lote, producto...")
        self.tutorial_targets["btn_reporte"] = barra.agregar_boton(
            "📊  Reporte", self._abrir_dialogo_reporte, estilo="accionSecundaria")
        cuerpo.addWidget(barra)

        self.tabla = TablaDatos(
            ["N° Orden", "N° Lote", "Producto", "Cantidad (L)", "Insumos (S/)",
             "M.O. (S/)", "Indirectos (S/)", "Total (S/)", "Unit. (S/)", "Margen (%)"],
            con_id=False,
            anchos={"N° Orden": 95, "N° Lote": 110, "Producto": 160, "Cantidad (L)": 90,
                    "Insumos (S/)": 100, "M.O. (S/)": 90, "Indirectos (S/)": 100,
                    "Total (S/)": 100, "Unit. (S/)": 90, "Margen (%)": 90},
        )
        cuerpo.addWidget(self.tabla, stretch=1)
        self.tutorial_targets["tabla"] = self.tabla

        self.refrescar()

    def refrescar(self):
        filas_resumen = resumen_costos()
        kpis = kpis_costos()

        self.kpi_costo_total.actualizar(f"S/ {kpis['costo_total']:,.2f}")
        self.kpi_margen_prom.actualizar(f"{kpis['margen_promedio']:.1f} %")
        self.kpi_costo_unit_prom.actualizar(f"S/ {kpis['costo_unitario_promedio']:.2f}")
        self.kpi_n_lotes.actualizar(str(kpis["n_lotes"]))

        filas = [
            [f["orden"], f["lote"], f["producto"], f"{f['cantidad']:.1f}",
             f"S/ {f['costo_insumos']:.2f}", f"S/ {f['costo_mano_obra']:.2f}",
             f"S/ {f['costo_indirectos']:.2f}", f"S/ {f['costo_total']:.2f}",
             f"S/ {f['costo_unitario']:.2f}", f"{f['margen_porcentaje']:.1f} %"]
            for f in filas_resumen
        ]
        self.tabla.cargar_filas(filas)

    def _abrir_dialogo_reporte(self):
        from app.ui.dialogo_reporte import DialogoReporte
        dlg = DialogoReporte(self.window(), modulo="costos")
        dlg.show()
        return dlg
