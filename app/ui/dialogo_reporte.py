"""dialogo_reporte.py (PySide6)
================================
Generar y exportar reportes (PDF / Excel / CSV) con vista previa en
tabla. Usa QFileDialog nativo de Qt para guardar — multiplataforma,
sin necesidad de zenity/kdialog/PowerShell como en la versión Tkinter.
"""

import io
import os
import subprocess
import sys
import datetime
from pathlib import Path

from PySide6.QtCore import Qt
from PySide6.QtWidgets import (
    QDialog, QWidget, QVBoxLayout, QHBoxLayout, QLabel, QComboBox,
    QRadioButton, QButtonGroup, QPushButton, QMessageBox, QFileDialog,
)

from app.logica_reportes import REPORTES, NOMBRES_LEGIBLES, guardar_pdf, guardar_xlsx, guardar_csv
from app.ui.estilos import COLOR_PRIMARIO, COLOR_SIDEBAR, COLOR_TEXTO, COLOR_TEXTO_SECUNDARIO, fuente, fondo
from app.ui.widgets import TablaDatos, centrar_ventana

_FORMATOS = {
    "PDF   (.pdf)":  ("pdf", "Archivos PDF (*.pdf)"),
    "Excel (.xlsx)": ("xlsx", "Archivos Excel (*.xlsx)"),
    "CSV   (.csv)":  ("csv", "Archivos CSV (*.csv)"),
}

_ICONOS_REPORTE = {
    "costos": "💰", "stock": "📦", "compras": "🛒", "ventas": "💵", "produccion": "🍺",
}


def _abrir_archivo(ruta: Path):
    try:
        os.startfile(str(ruta))
    except AttributeError:
        try:
            subprocess.Popen(["xdg-open", str(ruta)])
        except FileNotFoundError:
            subprocess.Popen(["open", str(ruta)])


class DialogoReporte(QDialog):
    """Ventana no modal para previsualizar y exportar un reporte."""

    def __init__(self, parent, modulo: str = None):
        super().__init__(parent)
        self.setModal(False)
        self._modulo_fijo = modulo
        self._datos = None
        self._pdf_bytes = None

        titulo = f"Generar Reporte — {NOMBRES_LEGIBLES[modulo]}" if modulo else "Generar Reporte"
        self.setWindowTitle(titulo)

        self._construir_ui()
        centrar_ventana(self, 1000, 760)

        if self._modulo_fijo:
            self._cargar_preview()

    def _construir_ui(self):
        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(0)

        panel_top = QWidget()
        fondo(panel_top, COLOR_SIDEBAR)
        ptl = QHBoxLayout(panel_top)
        ptl.setContentsMargins(18, 14, 18, 14)
        lbl_titulo = QLabel("Generador de Reportes")
        lbl_titulo.setStyleSheet("background: transparent; color: #E9E2C6;")
        lbl_titulo.setFont(fuente(15, negrita=True))
        ptl.addWidget(lbl_titulo)
        ptl.addStretch()
        layout.addWidget(panel_top)

        panel_opts = QHBoxLayout()
        panel_opts.setContentsMargins(18, 10, 18, 10)
        layout.addLayout(panel_opts)

        self._mapa_tipo = {f"{_ICONOS_REPORTE[k]}  {NOMBRES_LEGIBLES[k]}": k for k in REPORTES}

        if self._modulo_fijo:
            icono = _ICONOS_REPORTE.get(self._modulo_fijo, "")
            nombre = NOMBRES_LEGIBLES.get(self._modulo_fijo, self._modulo_fijo)
            lbl_fijo = QLabel(f"{icono}  {nombre}")
            lbl_fijo.setStyleSheet(f"color: {COLOR_PRIMARIO};")
            lbl_fijo.setFont(fuente(10, negrita=True))
            panel_opts.addWidget(lbl_fijo)
            self._combo_tipo = None
        else:
            lbl_tipo = QLabel("Tipo de reporte:")
            lbl_tipo.setFont(fuente(9, negrita=True))
            panel_opts.addWidget(lbl_tipo)
            self._combo_tipo = QComboBox()
            self._combo_tipo.addItems(list(self._mapa_tipo.keys()))
            panel_opts.addWidget(self._combo_tipo)

        panel_opts.addSpacing(20)
        lbl_formato = QLabel("Formato al guardar:")
        lbl_formato.setFont(fuente(9, negrita=True))
        panel_opts.addWidget(lbl_formato)

        self._grupo_formato = QButtonGroup(self)
        self._radios_formato = {}
        for i, texto in enumerate(_FORMATOS):
            radio = QRadioButton(texto)
            if i == 0:
                radio.setChecked(True)
            self._grupo_formato.addButton(radio)
            self._radios_formato[texto] = radio
            panel_opts.addWidget(radio)

        panel_opts.addSpacing(16)
        self.btn_vista_previa = QPushButton("🔍  Vista previa")
        self.btn_vista_previa.clicked.connect(self._cargar_preview)
        panel_opts.addWidget(self.btn_vista_previa)

        self.btn_guardar = QPushButton("💾  Guardar como…")
        self.btn_guardar.setEnabled(False)
        self.btn_guardar.clicked.connect(self._guardar)
        panel_opts.addWidget(self.btn_guardar)
        panel_opts.addStretch()

        self._lbl_estado = QLabel("Pulsa «Vista previa» para ver los datos del reporte.")
        self._lbl_estado.setStyleSheet(f"color: {COLOR_TEXTO_SECUNDARIO}; padding-left: 18px;")
        self._lbl_estado.setFont(fuente(9))
        layout.addWidget(self._lbl_estado)

        self._contenido_layout = QVBoxLayout()
        self._contenido_layout.setContentsMargins(18, 6, 18, 6)
        layout.addLayout(self._contenido_layout, stretch=1)

        self._lbl_placeholder = QLabel("La tabla del reporte aparecerá aquí.")
        self._lbl_placeholder.setStyleSheet(f"color: {COLOR_TEXTO_SECUNDARIO};")
        self._lbl_placeholder.setFont(fuente(11))
        self._lbl_placeholder.setAlignment(Qt.AlignCenter)
        self._contenido_layout.addWidget(self._lbl_placeholder)

        barra_inf = QHBoxLayout()
        barra_inf.setContentsMargins(18, 10, 18, 10)
        barra_inf.addStretch()
        btn_cerrar = QPushButton("Cerrar")
        btn_cerrar.clicked.connect(self.close)
        barra_inf.addWidget(btn_cerrar)
        layout.addLayout(barra_inf)

    def _clave_tipo(self) -> str:
        if self._modulo_fijo:
            return self._modulo_fijo
        return self._mapa_tipo.get(self._combo_tipo.currentText(), "costos")

    def _formato_elegido(self) -> str:
        for texto, radio in self._radios_formato.items():
            if radio.isChecked():
                return texto
        return "PDF   (.pdf)"

    def _cargar_preview(self):
        clave = self._clave_tipo()
        self._lbl_estado.setText("Cargando datos del reporte…")

        try:
            self._datos = REPORTES[clave]()
        except Exception as e:
            self._lbl_estado.setText(f"Error al cargar datos: {e}")
            QMessageBox.critical(self, "Error", str(e))
            return

        buf = io.BytesIO()
        try:
            guardar_pdf(self._datos, buf)
            self._pdf_bytes = buf.getvalue()
        except Exception as e:
            self._lbl_estado.setText(f"Error al generar PDF: {e}")
            QMessageBox.critical(self, "Error al generar PDF", str(e))
            return

        n = len(self._datos["filas"])
        nombre = NOMBRES_LEGIBLES[clave]
        self._lbl_estado.setText(
            f"Vista previa de «{nombre}» — {n} registro{'s' if n != 1 else ''} "
            f"encontrado{'s' if n != 1 else ''}.")
        self.btn_guardar.setEnabled(True)
        self._mostrar_tabla()

    def _mostrar_tabla(self):
        while self._contenido_layout.count():
            item = self._contenido_layout.takeAt(0)
            w = item.widget()
            if w is not None:
                w.deleteLater()

        contenedor = QWidget()
        cl = QVBoxLayout(contenedor)
        cl.setContentsMargins(0, 0, 0, 0)

        if self._datos.get("kpis"):
            fila_kpis = QHBoxLayout()
            cl.addLayout(fila_kpis)
            from app.ui.widgets import TarjetaKPI
            for kpi in self._datos["kpis"]:
                fila_kpis.addWidget(TarjetaKPI(kpi["etiqueta"], kpi["valor"]))

        tabla = TablaDatos(columnas=self._datos["columnas"], con_id=False)
        tabla.cargar_filas(self._datos["filas"])
        cl.addWidget(tabla, stretch=1)

        self._contenido_layout.addWidget(contenedor)

    def _guardar(self):
        if self._datos is None:
            QMessageBox.warning(self, "Sin datos", "Primero genera la vista previa.")
            return

        clave = self._clave_tipo()
        formato = self._formato_elegido()
        ext, filtro = _FORMATOS[formato]

        ts = datetime.datetime.now().strftime("%Y%m%d_%H%M%S")
        nombre_sugerido = str(Path.home() / f"Reporte_{NOMBRES_LEGIBLES[clave]}_{ts}.{ext}")

        ruta_str, _ = QFileDialog.getSaveFileName(
            self, f"Guardar reporte de {NOMBRES_LEGIBLES[clave]}", nombre_sugerido, filtro)
        if not ruta_str:
            return
        if not ruta_str.lower().endswith(f".{ext}"):
            ruta_str += f".{ext}"

        ruta = Path(ruta_str)
        try:
            if ext == "pdf":
                ruta.write_bytes(self._pdf_bytes)
            elif ext == "xlsx":
                guardar_xlsx(self._datos, ruta)
            else:
                guardar_csv(self._datos, ruta)
        except Exception as e:
            QMessageBox.critical(self, "Error al guardar", str(e))
            return

        self._lbl_estado.setText(f"✓ Guardado en: {ruta}")
        respuesta = QMessageBox.question(
            self, "Reporte guardado",
            f"El reporte fue guardado en:\n\n{ruta}\n\n¿Deseas abrirlo ahora?")
        if respuesta == QMessageBox.Yes:
            _abrir_archivo(ruta)

    def keyPressEvent(self, evento):
        if evento.key() == Qt.Key_Escape:
            self.close()
        else:
            super().keyPressEvent(evento)
