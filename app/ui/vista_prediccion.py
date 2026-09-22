"""
vista_prediccion.py (PySide6)
==============================
Vista del módulo de Predicción de Demanda.

Layout:
  ┌─ Encabezado ──────────────────────────────────────────────────┐
  │  🔮 Predicción de Demanda                                      │
  └───────────────────────────────────────────────────────────────┘
  ┌─ Panel izquierdo (config) ──┐  ┌─ Panel derecho (resultados) ─┐
  │  Producto                   │  │  Gráfico histórico + pred.   │
  │  Horizonte                  │  │  KPIs numéricos              │
  │  [Generar predicción]       │  │  Tabla diaria                │
  │  ─────────────────────────  │  │  Interpretación              │
  │  Estado del modelo          │  └──────────────────────────────┘
  │  [Entrenar / actualizar]    │
  └─────────────────────────────┘
"""

from __future__ import annotations

import traceback
from datetime import date, datetime

from PySide6.QtCore import Qt, QThread, Signal, QObject
from PySide6.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QLabel, QPushButton,
    QComboBox, QGroupBox, QSplitter, QScrollArea, QFrame,
    QTableWidget, QTableWidgetItem, QHeaderView, QProgressBar,
    QMessageBox, QSizePolicy,
)
from PySide6.QtGui import QColor

from app.ui.estilos import (
    COLOR_PRIMARIO, COLOR_PRIMARIO_CLARO, COLOR_PRIMARIO_OSCURO,
    COLOR_TEXTO, COLOR_TEXTO_SECUNDARIO, COLOR_EXITO, COLOR_ALERTA,
    COLOR_ADVERTENCIA, COLOR_FONDO, COLOR_TARJETA, _COLOR_SEPARADOR,
    fuente, fondo, poner_clase,
)
from app.ui.widgets import EncabezadoModulo, TarjetaKPI, MensajeEstado
from app.sesion import sesion_actual
from app.seguridad import puede


# ══════════════════════════════════════════════════════════════════
#  WORKER DE ENTRENAMIENTO (hilo separado para no bloquear UI)
# ══════════════════════════════════════════════════════════════════

class _WorkerEntrenamiento(QObject):
    progreso = Signal(str)
    terminado = Signal(dict)

    def __init__(self, producto_id=None):
        super().__init__()
        self._pid = producto_id

    def ejecutar(self):
        try:
            from app.ia.demanda_training import entrenar
            resultado = entrenar(
                producto_id=self._pid,
                callback_progreso=lambda m: self.progreso.emit(m),
            )
            self.terminado.emit(resultado)
        except Exception as e:
            self.terminado.emit({"exito": False, "mensaje": str(e), "metricas": {}})


class _WorkerPrediccion(QObject):
    terminado = Signal(dict)

    def __init__(self, producto_id: int, horizonte: int):
        super().__init__()
        self._pid = producto_id
        self._horizonte = horizonte

    def ejecutar(self):
        try:
            from app.ia.demanda_prediction import predecir_demanda
            resultado = predecir_demanda(self._pid, self._horizonte)
            self.terminado.emit(resultado)
        except Exception as e:
            self.terminado.emit({"exito": False, "mensaje": str(e)})


# ══════════════════════════════════════════════════════════════════
#  WIDGET DE GRÁFICO SVG INCRUSTADO
# ══════════════════════════════════════════════════════════════════

class GraficoSVG(QLabel):
    """
    Genera un mini-gráfico de línea usando matplotlib en memoria
    y lo muestra como pixmap en un QLabel.
    """

    def __init__(self, parent=None):
        super().__init__(parent)
        self.setMinimumHeight(260)
        self.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Expanding)
        self.setAlignment(Qt.AlignCenter)
        fondo(self, COLOR_TARJETA,
              f"border: 1px solid {_COLOR_SEPARADOR}; border-radius: 6px;")
        self._mostrar_placeholder()

    def _mostrar_placeholder(self):
        self.setText("Selecciona un producto y ejecuta la predicción\npara visualizar el gráfico.")
        self.setStyleSheet(
            f"color: {COLOR_TEXTO_SECUNDARIO}; font-size: 10pt; background: transparent;"
        )

    def actualizar(self, df_historico, fechas_pred, cantidades_pred):
        """Renderiza el gráfico histórico + predicción."""
        try:
            import matplotlib
            matplotlib.use("Agg")
            import matplotlib.pyplot as plt
            import matplotlib.dates as mdates
            from io import BytesIO
            from PySide6.QtGui import QPixmap

            fig, ax = plt.subplots(figsize=(9, 3.2), dpi=100)
            fig.patch.set_facecolor("#FFFFFF")
            ax.set_facecolor("#FDFAF3")

            # Serie histórica (últimos 60 días para no saturar)
            df_vis = df_historico.tail(60).copy()
            import pandas as pd
            df_vis["fecha"] = pd.to_datetime(df_vis["fecha"])
            ax.plot(
                df_vis["fecha"], df_vis["cantidad"],
                color=COLOR_PRIMARIO_OSCURO, linewidth=1.8,
                label="Ventas históricas", alpha=0.85,
            )
            ax.fill_between(df_vis["fecha"], df_vis["cantidad"],
                            color=COLOR_PRIMARIO, alpha=0.08)

            # Serie predicha
            fechas_pd = pd.to_datetime(fechas_pred)
            ax.plot(
                fechas_pd, cantidades_pred,
                color=COLOR_EXITO, linewidth=2.2, linestyle="--",
                marker="o", markersize=4,
                label="Demanda estimada", alpha=0.9,
            )

            # Línea vertical divisoria
            if not df_vis.empty:
                ax.axvline(
                    df_vis["fecha"].max(), color=COLOR_TEXTO_SECUNDARIO,
                    linestyle=":", linewidth=1.2, alpha=0.6,
                )
                ax.text(
                    df_vis["fecha"].max(), ax.get_ylim()[1] * 0.95,
                    " Hoy", fontsize=7, color=COLOR_TEXTO_SECUNDARIO,
                    va="top",
                )

            ax.xaxis.set_major_formatter(mdates.DateFormatter("%d/%m"))
            ax.xaxis.set_major_locator(mdates.AutoDateLocator())
            plt.setp(ax.xaxis.get_majorticklabels(), rotation=30, ha="right", fontsize=7)
            ax.tick_params(axis="y", labelsize=7)
            ax.set_ylabel("Unidades", fontsize=8, color=COLOR_TEXTO_SECUNDARIO)
            ax.legend(fontsize=8, loc="upper left", framealpha=0.7)
            ax.spines[["top", "right"]].set_visible(False)
            ax.spines["left"].set_color(_COLOR_SEPARADOR)
            ax.spines["bottom"].set_color(_COLOR_SEPARADOR)
            ax.grid(axis="y", color=_COLOR_SEPARADOR, linewidth=0.6, alpha=0.6)

            plt.tight_layout(pad=0.5)

            buf = BytesIO()
            fig.savefig(buf, format="png", bbox_inches="tight")
            plt.close(fig)
            buf.seek(0)

            pixmap = QPixmap()
            pixmap.loadFromData(buf.getvalue())
            self.setPixmap(
                pixmap.scaledToWidth(
                    self.width() - 20,
                    Qt.SmoothTransformation,
                )
            )
            self.setStyleSheet("")

        except Exception:
            self._mostrar_placeholder()


# ══════════════════════════════════════════════════════════════════
#  VISTA PRINCIPAL
# ══════════════════════════════════════════════════════════════════

class VistaPrediccion(QWidget):
    """Vista completa del módulo de Predicción de Demanda."""

    def __init__(self, parent=None, embebido: bool = False):
        super().__init__(parent)
        self._productos: list[dict] = []
        self._resultado_actual: dict | None = None
        self._hilo: QThread | None = None

        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(0)

        # embebido=True: se usa dentro de una pestaña de Centro de
        # Inteligencia (sección G del reporte de bugs), que ya tiene su
        # propio encabezado "🧠 Centro de Inteligencia" — repetir aquí
        # un segundo encabezado se veía redundante.
        if not embebido:
            layout.addWidget(EncabezadoModulo(
                "Predicción de Demanda",
                "Estimación de demanda futura basada en historial de ventas · Modelo XGBoost",
                icono="🔮",
            ))

        self._banner = MensajeEstado()
        layout.addWidget(self._banner)

        # Splitter principal: panel izq (config) + panel der (resultados)
        splitter = QSplitter(Qt.Horizontal)
        splitter.setContentsMargins(8, 8, 8, 8)
        splitter.setHandleWidth(6)
        layout.addWidget(splitter, stretch=1)

        splitter.addWidget(self._construir_panel_config())
        splitter.addWidget(self._construir_panel_resultados())
        splitter.setSizes([310, 700])

        self.refrescar()

    # ── Panel de configuración ────────────────────────────────────

    def _construir_panel_config(self) -> QWidget:
        contenedor = QWidget()
        contenedor.setMaximumWidth(330)
        vl = QVBoxLayout(contenedor)
        vl.setContentsMargins(4, 4, 4, 4)
        vl.setSpacing(10)

        # ── Grupo: configuración de predicción ──
        grp_pred = QGroupBox("⚙️  Configurar predicción")
        gl = QVBoxLayout(grp_pred)
        gl.setSpacing(8)

        gl.addWidget(QLabel("Producto:"))
        self._combo_producto = QComboBox()
        self._combo_producto.setPlaceholderText("— Selecciona un producto —")
        gl.addWidget(self._combo_producto)

        gl.addWidget(QLabel("Horizonte de predicción:"))
        self._combo_horizonte = QComboBox()
        self._combo_horizonte.addItems([
            "7 días — semana próxima",
            "14 días — dos semanas",
            "30 días — próximo mes",
        ])
        gl.addWidget(self._combo_horizonte)

        self._btn_predecir = QPushButton("🔮  Generar predicción")
        poner_clase(self._btn_predecir, "exito")
        self._btn_predecir.setMinimumHeight(40)
        self._btn_predecir.clicked.connect(self._ejecutar_prediccion)
        gl.addWidget(self._btn_predecir)

        self._progreso_pred = QProgressBar()
        self._progreso_pred.setRange(0, 0)  # indeterminado
        self._progreso_pred.setVisible(False)
        self._progreso_pred.setMaximumHeight(8)
        gl.addWidget(self._progreso_pred)

        vl.addWidget(grp_pred)

        # ── Grupo: estado del modelo ──
        grp_modelo = QGroupBox("🤖  Estado del modelo")
        ml = QVBoxLayout(grp_modelo)
        ml.setSpacing(6)

        self._lbl_modelo_estado = QLabel("Sin modelo entrenado")
        self._lbl_modelo_estado.setFont(fuente(9))
        self._lbl_modelo_estado.setWordWrap(True)
        ml.addWidget(self._lbl_modelo_estado)

        self._lbl_modelo_fecha = QLabel("")
        self._lbl_modelo_fecha.setFont(fuente(8))
        self._lbl_modelo_fecha.setStyleSheet(f"color: {COLOR_TEXTO_SECUNDARIO};")
        self._lbl_modelo_fecha.setWordWrap(True)
        ml.addWidget(self._lbl_modelo_fecha)

        self._lbl_modelo_metricas = QLabel("")
        self._lbl_modelo_metricas.setFont(fuente(8))
        self._lbl_modelo_metricas.setStyleSheet(f"color: {COLOR_TEXTO_SECUNDARIO};")
        self._lbl_modelo_metricas.setWordWrap(True)
        ml.addWidget(self._lbl_modelo_metricas)

        if puede(sesion_actual.rol, "centro_inteligencia", "entrenar"):
            self._btn_entrenar = QPushButton("🔄  Entrenar / actualizar modelo")
            poner_clase(self._btn_entrenar, "secundario")
            self._btn_entrenar.setToolTip(
                "Reentrenar el modelo con todos los datos actuales del ERP.\n"
                "Esto puede tardar unos segundos."
            )
            self._btn_entrenar.clicked.connect(self._ejecutar_entrenamiento)
            ml.addWidget(self._btn_entrenar)
        else:
            self._btn_entrenar = None

        self._progreso_entreno = QProgressBar()
        self._progreso_entreno.setRange(0, 0)
        self._progreso_entreno.setVisible(False)
        self._progreso_entreno.setMaximumHeight(8)
        ml.addWidget(self._progreso_entreno)

        self._lbl_log_entreno = QLabel("")
        self._lbl_log_entreno.setFont(fuente(8))
        self._lbl_log_entreno.setStyleSheet(f"color: {COLOR_TEXTO_SECUNDARIO};")
        self._lbl_log_entreno.setWordWrap(True)
        ml.addWidget(self._lbl_log_entreno)

        vl.addWidget(grp_modelo)
        vl.addStretch()

        return contenedor

    # ── Panel de resultados ───────────────────────────────────────

    def _construir_panel_resultados(self) -> QWidget:
        scroll = QScrollArea()
        scroll.setWidgetResizable(True)
        scroll.setFrameShape(QFrame.NoFrame)

        contenedor = QWidget()
        vl = QVBoxLayout(contenedor)
        vl.setContentsMargins(4, 4, 8, 8)
        vl.setSpacing(10)

        # Gráfico
        self._grafico = GraficoSVG()
        vl.addWidget(self._grafico)

        # KPIs
        fila_kpis = QHBoxLayout()
        self._kpi_total   = TarjetaKPI("Demanda total estimada", "—", "normal", "📦")
        self._kpi_diario  = TarjetaKPI("Promedio diario",        "—", "normal", "📅")
        self._kpi_min     = TarjetaKPI("Mínimo estimado",        "—", "normal", "⬇️")
        self._kpi_max     = TarjetaKPI("Máximo estimado",        "—", "advertencia", "⬆️")
        self._kpi_mae     = TarjetaKPI("MAE del modelo",         "—", "normal", "📐")
        self._kpi_rmse    = TarjetaKPI("RMSE del modelo",        "—", "normal", "📏")
        for kpi in [self._kpi_total, self._kpi_diario, self._kpi_min,
                    self._kpi_max, self._kpi_mae, self._kpi_rmse]:
            fila_kpis.addWidget(kpi)
        vl.addLayout(fila_kpis)

        # Interpretación textual
        self._lbl_interpretacion = QLabel(
            "Selecciona un producto y haz clic en «Generar predicción» para ver los resultados."
        )
        self._lbl_interpretacion.setFont(fuente(9, cursiva=True))
        self._lbl_interpretacion.setWordWrap(True)
        self._lbl_interpretacion.setStyleSheet(
            f"color: {COLOR_TEXTO_SECUNDARIO}; padding: 6px;"
        )
        vl.addWidget(self._lbl_interpretacion)

        # Tabla diaria
        grp_tabla = QGroupBox("📋  Detalle por día")
        tl = QVBoxLayout(grp_tabla)
        self._tabla = QTableWidget(0, 3)
        self._tabla.setHorizontalHeaderLabels(["Fecha", "Día", "Demanda estimada"])
        self._tabla.horizontalHeader().setSectionResizeMode(QHeaderView.Stretch)
        self._tabla.setEditTriggers(QTableWidget.NoEditTriggers)
        self._tabla.setAlternatingRowColors(True)
        self._tabla.setMaximumHeight(280)
        tl.addWidget(self._tabla)
        vl.addWidget(grp_tabla)

        vl.addStretch()
        scroll.setWidget(contenedor)
        return scroll

    # ── Lógica: refrescar ─────────────────────────────────────────

    def refrescar(self):
        self._cargar_productos()
        self._actualizar_estado_modelo()

    def _cargar_productos(self):
        try:
            from app.ia.demanda_data import listar_productos_con_ventas
            self._productos = listar_productos_con_ventas()
        except Exception:
            self._productos = []

        actual = self._combo_producto.currentText()
        self._combo_producto.blockSignals(True)
        self._combo_producto.clear()
        for p in self._productos:
            self._combo_producto.addItem(p["nombre"], userData=p["id"])
        # Restaurar selección previa si existe
        idx = self._combo_producto.findText(actual)
        if idx >= 0:
            self._combo_producto.setCurrentIndex(idx)
        self._combo_producto.blockSignals(False)

    def _actualizar_estado_modelo(self):
        try:
            from app.ia.demanda_training import modelo_disponible, leer_metadata
            if not modelo_disponible():
                self._lbl_modelo_estado.setText(
                    "⚠️ Sin modelo entrenado. Haz clic en «Entrenar» para comenzar."
                )
                self._lbl_modelo_estado.setStyleSheet(f"color: {COLOR_ADVERTENCIA};")
                self._lbl_modelo_fecha.setText("")
                self._lbl_modelo_metricas.setText("")
                return

            meta = leer_metadata() or {}
            fecha_str = meta.get("fecha_entrenamiento", "")
            if fecha_str:
                try:
                    dt = datetime.fromisoformat(fecha_str)
                    fecha_str = dt.strftime("%d/%m/%Y %H:%M")
                except Exception:
                    pass

            n_prods = len(meta.get("productos_incluidos", []))
            self._lbl_modelo_estado.setText(
                f"✅ Modelo XGBoost entrenado\n{n_prods} producto(s) incluido(s)"
            )
            self._lbl_modelo_estado.setStyleSheet(f"color: {COLOR_EXITO};")
            self._lbl_modelo_fecha.setText(f"Último entrenamiento: {fecha_str}")

            m = meta.get("metricas_test_xgboost", {})
            if m:
                self._lbl_modelo_metricas.setText(
                    f"MAE={m.get('mae','—')}  RMSE={m.get('rmse','—')}"
                )
        except Exception:
            self._lbl_modelo_estado.setText("Error al leer estado del modelo.")

    # ── Lógica: predicción ────────────────────────────────────────

    def _ejecutar_prediccion(self):
        if self._combo_producto.count() == 0:
            self._banner.mostrar("No hay productos con ventas registradas.", "advertencia")
            return

        prod_id = self._combo_producto.currentData()
        if prod_id is None:
            self._banner.mostrar("Selecciona un producto.", "advertencia")
            return

        horizonte_map = {0: 7, 1: 14, 2: 30}
        horizonte = horizonte_map[self._combo_horizonte.currentIndex()]

        self._btn_predecir.setEnabled(False)
        self._progreso_pred.setVisible(True)
        self._banner.mostrar("Generando predicción...", "info")

        self._hilo_pred = QThread()
        self._worker_pred = _WorkerPrediccion(prod_id, horizonte)
        self._worker_pred.moveToThread(self._hilo_pred)
        self._hilo_pred.started.connect(self._worker_pred.ejecutar)
        self._worker_pred.terminado.connect(self._on_prediccion_terminada)
        self._worker_pred.terminado.connect(self._hilo_pred.quit)
        self._hilo_pred.start()

    def _on_prediccion_terminada(self, resultado: dict):
        self._btn_predecir.setEnabled(True)
        self._progreso_pred.setVisible(False)

        if not resultado.get("exito"):
            self._banner.mostrar(resultado.get("mensaje", "Error en la predicción."), "error")
            return

        self._resultado_actual = resultado
        self._renderizar_resultados(resultado)

        if resultado.get("advertencia"):
            self._banner.mostrar(resultado["advertencia"], "advertencia")
        else:
            usando = "modelo XGBoost" if resultado.get("usando_ml") else "promedio móvil baseline"
            self._banner.mostrar(f"Predicción generada con {usando}.", "exito")

    def _renderizar_resultados(self, r: dict):
        prod_nombre = self._combo_producto.currentText()
        horizonte_map = {0: 7, 1: 14, 2: 30}
        horizonte = horizonte_map[self._combo_horizonte.currentIndex()]
        unidad = ""
        for p in self._productos:
            if p["id"] == self._combo_producto.currentData():
                unidad = p["unidad"]
                break

        # KPIs
        def _fmt(v):
            return f"{v:.1f} {unidad}".strip()

        self._kpi_total.actualizar(_fmt(r["demanda_total"]))
        self._kpi_diario.actualizar(_fmt(r["promedio_diario"]))
        self._kpi_min.actualizar(_fmt(r["demanda_min"]))
        self._kpi_max.actualizar(_fmt(r["demanda_max"]))

        m = r.get("metricas", {})
        self._kpi_mae.actualizar(str(m.get("mae", "—")))
        self._kpi_rmse.actualizar(str(m.get("rmse", "—")))

        # Interpretación
        modelo_txt = "modelo XGBoost" if r.get("usando_ml") else "promedio móvil (historial limitado)"
        self._lbl_interpretacion.setText(
            f"El {modelo_txt} estima una demanda aproximada de "
            f"{r['demanda_total']:.1f} {unidad} para «{prod_nombre}» "
            f"durante los próximos {horizonte} días, basándose en el "
            f"comportamiento histórico de ventas. "
            f"Promedio diario esperado: {r['promedio_diario']:.1f} {unidad}. "
            f"Rango estimado: entre {r['demanda_min']:.1f} y {r['demanda_max']:.1f} {unidad}."
        )

        # Gráfico
        self._grafico.actualizar(
            r["df_historico"],
            r["fechas"],
            r["pred_cantidad"],
        )

        # Tabla diaria
        DIAS = ["Lunes", "Martes", "Miércoles", "Jueves", "Viernes", "Sábado", "Domingo"]
        self._tabla.setRowCount(len(r["fechas"]))
        for i, (fecha, cant) in enumerate(zip(r["fechas"], r["pred_cantidad"])):
            if hasattr(fecha, "weekday"):
                dia_txt = DIAS[fecha.weekday()]
                fecha_txt = fecha.strftime("%d/%m/%Y")
            else:
                fecha_txt = str(fecha)
                dia_txt = ""

            self._tabla.setItem(i, 0, QTableWidgetItem(fecha_txt))
            self._tabla.setItem(i, 1, QTableWidgetItem(dia_txt))
            item_cant = QTableWidgetItem(f"{cant:.1f}")
            item_cant.setTextAlignment(Qt.AlignRight | Qt.AlignVCenter)
            self._tabla.setItem(i, 2, item_cant)

    # ── Lógica: entrenamiento ─────────────────────────────────────

    def _ejecutar_entrenamiento(self):
        if self._btn_entrenar is None:
            return
        self._btn_entrenar.setEnabled(False)
        self._progreso_entreno.setVisible(True)
        self._lbl_log_entreno.setText("Iniciando entrenamiento...")

        self._hilo_ent = QThread()
        self._worker_ent = _WorkerEntrenamiento()
        self._worker_ent.moveToThread(self._hilo_ent)
        self._hilo_ent.started.connect(self._worker_ent.ejecutar)
        self._worker_ent.progreso.connect(self._on_progreso_entrenamiento)
        self._worker_ent.terminado.connect(self._on_entrenamiento_terminado)
        self._worker_ent.terminado.connect(self._hilo_ent.quit)
        self._hilo_ent.start()

    def _on_progreso_entrenamiento(self, msg: str):
        self._lbl_log_entreno.setText(msg)

    def _on_entrenamiento_terminado(self, resultado: dict):
        if self._btn_entrenar is not None:
            self._btn_entrenar.setEnabled(True)
        self._progreso_entreno.setVisible(False)

        if resultado.get("exito"):
            m = resultado.get("metricas", {})
            self._lbl_log_entreno.setText(
                f"✓ Completado — MAE={m.get('mae','—')}  RMSE={m.get('rmse','—')}"
            )
            self._banner.mostrar(
                f"Modelo entrenado correctamente. MAE={m.get('mae','—')}  RMSE={m.get('rmse','—')}",
                "exito",
            )
        else:
            self._lbl_log_entreno.setText(f"✗ Error: {resultado.get('mensaje','')}")
            self._banner.mostrar(resultado.get("mensaje", "Error en el entrenamiento."), "error")

        self._actualizar_estado_modelo()
