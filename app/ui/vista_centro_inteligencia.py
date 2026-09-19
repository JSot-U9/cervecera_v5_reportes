"""
vista_centro_inteligencia.py (PySide6)
========================================
"Centro de Inteligencia" — vista que reúne los tres resultados del
núcleo de IA descrito en la propuesta (sección 6):

  1. Reposición inteligente : qué insumos conviene reponer y cuánto,
                               con la opción de convertir la
                               recomendación en una orden de compra.
  2. Predicción de merma    : estimar el rendimiento esperado de una
                               producción antes de planearla o cerrarla.
  3. Demanda prevista       : resumen rápido de la demanda estimada
                               de cada producto para 7/14/30 días.

Esta vista NO reemplaza los módulos tradicionales (Compras,
Producción, Predicción de Demanda) — concentra sus resultados y deja
que el usuario decida la acción, tal como pide la propuesta: "el
usuario revisa la recomendación y decide si genera la orden".
"""

from __future__ import annotations

from datetime import date

from PySide6.QtCore import Qt
from PySide6.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QLabel, QPushButton, QComboBox,
    QTabWidget, QDoubleSpinBox, QMessageBox, QApplication, QGroupBox,
)

from app.sesion import sesion_actual
from app.seguridad import puede

from app.ui.estilos import (
    COLOR_TEXTO_SECUNDARIO, COLOR_PRIMARIO, COLOR_EXITO, COLOR_ALERTA,
    COLOR_ADVERTENCIA, fuente, poner_clase,
)
from app.ui.widgets import (
    EncabezadoModulo, TarjetaKPI, MensajeEstado, TablaDatos, SeccionFormulario,
    ejecutar_con_carga, ejecutar_en_hilo,
)

from app.ia import reposicion as motor_reposicion
from app.ia.merma_prediction import predecir_merma, listar_recetas_para_prediccion
from app.ia.demanda_data import listar_productos_con_ventas, diagnostico_historial
from app.ia.demanda_prediction import predecir_demanda
from app.ui.vista_prediccion import VistaPrediccion


_PRIORIDAD_TAG = {"ALTA": "alerta", "MEDIA": "advertencia", "BAJA": "normal"}
_PRIORIDAD_TEXTO = {"ALTA": "🔴 Alta", "MEDIA": "🟠 Media", "BAJA": "🟢 Baja"}


class VistaCentroInteligencia(QWidget):
    def __init__(self, parent=None):
        super().__init__(parent)
        self._recomendaciones_actuales: list[dict] = []
        # Diccionario que el sistema de tutorial usa para resaltar
        # controles reales de esta vista (ver tutorial_data.py, sección
        # I.3 del reporte de bugs: antes no existía ningún tutorial para
        # "Centro de Inteligencia" ni "Predicción de demanda").
        self.tutorial_targets: dict = {}

        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(0)

        layout.addWidget(EncabezadoModulo(
            "Centro de Inteligencia", "Predicción de demanda + Predicción de merma + Reposición inteligente",
            "🧠",
        ))

        cuerpo = QVBoxLayout()
        cuerpo.setContentsMargins(20, 16, 20, 16)
        cuerpo.setSpacing(12)
        layout.addLayout(cuerpo, stretch=1)

        self._msg = MensajeEstado()
        cuerpo.addWidget(self._msg)

        # ── Fila de KPIs ────────────────────────────────────────
        fila_kpi = QHBoxLayout()
        fila_kpi.setSpacing(10)
        self.kpi_riesgo = TarjetaKPI("Insumos en riesgo de quiebre", "—", "alerta", "⚠️")
        self.kpi_reponer = TarjetaKPI("Insumos con reposición sugerida", "—", "advertencia", "📦")
        self.kpi_merma_prom = TarjetaKPI("Merma histórica promedio", "—", "normal", "🍺")
        self.kpi_productos_pronosticados = TarjetaKPI("Productos con pronóstico activo", "—", "exito", "🔮")
        for k in (self.kpi_riesgo, self.kpi_reponer, self.kpi_merma_prom, self.kpi_productos_pronosticados):
            fila_kpi.addWidget(k)
        cuerpo.addLayout(fila_kpi)
        self.tutorial_targets["kpi_riesgo"] = self.kpi_riesgo

        # ── Pestañas ──────────────────────────────────────────
        self.tabs = QTabWidget()
        cuerpo.addWidget(self.tabs, stretch=1)
        self.tutorial_targets["tabs"] = self.tabs
        # Alias para que el motor de tutorial (tutorial.py:_seleccionar_tab,
        # que busca un atributo "notebook" con la misma API de QTabWidget
        # usada por las demás vistas con pestañas) pueda cambiar de
        # pestaña aquí también sin tener que aprender un nombre distinto.
        self.notebook = self.tabs

        self.tabs.addTab(self._construir_tab_reposicion(), "📦  Reposición inteligente")
        self.tabs.addTab(self._construir_tab_merma(), "🍺  Predicción de merma")
        self.tabs.addTab(self._construir_tab_demanda(), "🔮  Demanda prevista (resumen)")
        # Sección G del reporte de bugs: "Predicción Demanda" ya no es un
        # módulo aparte del menú lateral — su vista completa (por
        # producto, con gráfico e historial) vive aquí como una pestaña
        # más, junto al resumen rápido multi-producto de arriba.
        self._indice_tab_prediccion_detalle = self.tabs.count()
        self._vista_prediccion_detalle = VistaPrediccion(embebido=True)
        self.tabs.addTab(self._vista_prediccion_detalle, "📈  Predicción de demanda (detalle)")
        # Se exponen también los controles internos de esa pestaña
        # embebida, para que el tutorial pueda resaltarlos igual que a
        # cualquier otro control propio de esta vista.
        self.tutorial_targets["combo_producto_prediccion"] = self._vista_prediccion_detalle._combo_producto
        self.tutorial_targets["btn_predecir_prediccion"] = self._vista_prediccion_detalle._btn_predecir

    def mostrar_tab_prediccion_detalle(self):
        """API pública: usada por los enlaces "🧠 Demanda prevista" de
        Ventas/Producción para abrir directamente la pestaña de
        predicción de demanda detallada, en vez de solo entrar al
        módulo y dejar al usuario buscando la pestaña correcta."""
        self.tabs.setCurrentIndex(self._indice_tab_prediccion_detalle)

    # ══════════════════════════════════════════════════════════
    #  TAB 1 — REPOSICIÓN INTELIGENTE
    # ══════════════════════════════════════════════════════════
    def _construir_tab_reposicion(self) -> QWidget:
        tab = QWidget()
        v = QVBoxLayout(tab)
        v.setContentsMargins(0, 12, 0, 0)
        v.setSpacing(10)

        intro = QLabel(
            "Cantidad a reponer = Demanda esperada del periodo + Stock de seguridad − Stock disponible.\n"
            "La recomendación NO genera una compra automáticamente: elige un insumo y confirma.\n"
            "Un insumo con demanda esperada en 0 no es un error: significa que todavía no tiene "
            "historial de consumo ni está en ninguna receta activa con ventas suficientes para "
            "proyectarlo (por ejemplo, un insumo recién creado, o material de empaque que no se "
            "modela dentro de ninguna receta). Haz clic en la fila para ver el motivo exacto."
        )
        intro.setStyleSheet(f"color: {COLOR_TEXTO_SECUNDARIO};")
        intro.setFont(fuente(9, cursiva=True))
        intro.setWordWrap(True)
        v.addWidget(intro)

        fila_ctrl = QHBoxLayout()
        fila_ctrl.addWidget(QLabel("Horizonte de cobertura:"))
        self.combo_horizonte_reposicion = QComboBox()
        self.combo_horizonte_reposicion.addItem("7 días", 7)
        self.combo_horizonte_reposicion.addItem("14 días", 14)
        self.combo_horizonte_reposicion.addItem("30 días", 30)
        self.combo_horizonte_reposicion.setCurrentIndex(1)
        fila_ctrl.addWidget(self.combo_horizonte_reposicion)
        fila_ctrl.addSpacing(20)
        self.btn_calcular_reposicion = QPushButton("🔄  Calcular recomendaciones")
        self.btn_calcular_reposicion.clicked.connect(self._calcular_reposicion)
        fila_ctrl.addWidget(self.btn_calcular_reposicion)
        self.tutorial_targets["btn_calcular_reposicion"] = self.btn_calcular_reposicion
        fila_ctrl.addStretch()
        v.addLayout(fila_ctrl)

        self.tabla_reposicion = TablaDatos(
            ["Insumo", "Stock disp.", "Demanda esp.", "Stock seguridad", "Recomendado", "Prioridad"],
            con_id=True,
            anchos={"Insumo": 200, "Stock disp.": 90, "Demanda esp.": 100,
                    "Stock seguridad": 110, "Recomendado": 100, "Prioridad": 90},
        )
        self.tabla_reposicion.cellClicked.connect(self._al_seleccionar_recomendacion)
        v.addWidget(self.tabla_reposicion, stretch=1)
        self.tutorial_targets["tabla_reposicion"] = self.tabla_reposicion

        self.lbl_motivo = QLabel("Selecciona un insumo de la tabla para ver el detalle del cálculo.")
        self.lbl_motivo.setWordWrap(True)
        self.lbl_motivo.setStyleSheet(f"color: {COLOR_TEXTO_SECUNDARIO};")
        self.lbl_motivo.setFont(fuente(9))
        v.addWidget(self.lbl_motivo)

        fila_accion = QHBoxLayout()
        fila_accion.addStretch()
        self.btn_generar_compra = QPushButton("🛒  Generar orden de compra con este insumo")
        self.btn_generar_compra.clicked.connect(self._generar_orden_compra)
        self.btn_generar_compra.setEnabled(False)
        fila_accion.addWidget(self.btn_generar_compra)
        self.tutorial_targets["btn_generar_compra"] = self.btn_generar_compra
        v.addLayout(fila_accion)

        return tab

    def _calcular_reposicion(self):
        horizonte = self.combo_horizonte_reposicion.currentData()
        # ejecutar_en_hilo (y no ejecutar_con_carga): el cálculo de
        # reposición recorre todo el catálogo de insumos con consumo
        # histórico y tardaba unos segundos con datos reales — antes
        # eso significaba una ventana congelada; ahora corre en un hilo
        # aparte y la interfaz sigue respondiendo mientras se anima el
        # overlay de carga.
        self.btn_calcular_reposicion.setEnabled(False)
        ejecutar_en_hilo(
            self, lambda: motor_reposicion.calcular_recomendaciones(horizonte_dias=horizonte),
            al_terminar=self._al_terminar_reposicion,
            mensaje="🧠  Calculando reposición inteligente...",
            submensaje="Analizando stock, demanda y consumo histórico...",
        )

    def _al_terminar_reposicion(self, recomendaciones, error):
        self.btn_calcular_reposicion.setEnabled(True)
        if error is not None:
            self._msg.mostrar(f"No se pudo calcular la reposición: {error}", tipo="error")
            return

        self._recomendaciones_actuales = recomendaciones
        filas = [
            [r["producto_id"], f"{r['nombre']} ({r['unidad']})", f"{r['stock_disponible']:.2f}",
             f"{r['demanda_esperada']:.2f}", f"{r['stock_seguridad']:.2f}",
             f"{r['cantidad_recomendada']:.2f}", _PRIORIDAD_TEXTO.get(r["prioridad"], r["prioridad"])]
            for r in recomendaciones
        ]
        tags = [_PRIORIDAD_TAG.get(r["prioridad"], "normal") for r in recomendaciones]
        self.tabla_reposicion.cargar_filas(filas, tags_por_fila=tags)

        n_alta = sum(1 for r in recomendaciones if r["prioridad"] == "ALTA")
        n_reponer = sum(1 for r in recomendaciones if r["cantidad_recomendada"] > 0)
        self.kpi_riesgo.actualizar(str(n_alta))
        self.kpi_reponer.actualizar(str(n_reponer))

        self.lbl_motivo.setText("Selecciona un insumo de la tabla para ver el detalle del cálculo.")
        self.btn_generar_compra.setEnabled(False)

        if recomendaciones:
            self._msg.mostrar(f"{len(recomendaciones)} insumo(s) con recomendación de reposición.", tipo="info")
        else:
            self._msg.mostrar(
                "Ningún insumo necesita reposición según la demanda y el stock actuales.", tipo="exito"
            )

    def _al_seleccionar_recomendacion(self, fila, _columna):
        if fila < 0 or fila >= len(self._recomendaciones_actuales):
            return
        rec = self._recomendaciones_actuales[fila]
        self.lbl_motivo.setText(f"💡 {rec['nombre']}: {rec['motivo']}")
        self.btn_generar_compra.setEnabled(rec["cantidad_recomendada"] > 0)

    def _generar_orden_compra(self):
        producto_id = self.tabla_reposicion.id_seleccionado()
        rec = next((r for r in self._recomendaciones_actuales if r["producto_id"] == producto_id), None)
        if not rec:
            return
        if not puede(sesion_actual.rol, "compras", "crear"):
            QMessageBox.warning(self, "Aviso", "Tu rol no tiene permiso para crear órdenes de compra.")
            return

        ventana_principal = self.window()
        vista_compras = ventana_principal.obtener_vista("compras") if hasattr(ventana_principal, "obtener_vista") else None
        if vista_compras is None or not hasattr(vista_compras, "abrir_nueva_orden_prellenada"):
            QMessageBox.information(
                self, "Compras",
                "No tienes acceso al módulo de Compras para generar la orden desde aquí.",
            )
            return

        vista_compras.abrir_nueva_orden_prellenada(
            producto_id=rec["producto_id"], cantidad_sugerida=rec["cantidad_recomendada"],
        )
        ventana_principal.navegar("compras")

    # ══════════════════════════════════════════════════════════
    #  TAB 2 — PREDICCIÓN DE MERMA
    # ══════════════════════════════════════════════════════════
    def _construir_tab_merma(self) -> QWidget:
        tab = QWidget()
        v = QVBoxLayout(tab)
        v.setContentsMargins(0, 12, 0, 0)
        v.setSpacing(10)

        sec = SeccionFormulario("Estimar merma antes de planear o cerrar una producción")
        sl = QVBoxLayout(sec)
        v.addWidget(sec)

        fila1 = QHBoxLayout()
        col_r = QVBoxLayout()
        col_r.addWidget(QLabel("Receta"))
        self.combo_receta_merma = QComboBox()
        self._recetas_merma = listar_recetas_para_prediccion()
        for r in self._recetas_merma:
            self.combo_receta_merma.addItem(f"{r['nombre']}", r)
        col_r.addWidget(self.combo_receta_merma)
        fila1.addLayout(col_r, stretch=2)
        self.tutorial_targets["combo_receta_merma"] = self.combo_receta_merma

        col_c = QVBoxLayout()
        col_c.addWidget(QLabel("Cantidad planeada"))
        self.spin_cantidad_merma = QDoubleSpinBox()
        self.spin_cantidad_merma.setRange(0.01, 1_000_000)
        self.spin_cantidad_merma.setDecimals(2)
        self.spin_cantidad_merma.setValue(
            self._recetas_merma[0]["rendimiento"] if self._recetas_merma else 100.0
        )
        col_c.addWidget(self.spin_cantidad_merma)
        fila1.addLayout(col_c, stretch=1)
        sl.addLayout(fila1)

        fila_botones_merma = QHBoxLayout()
        self.btn_estimar_merma = QPushButton("🔍  Estimar merma esperada")
        self.btn_estimar_merma.clicked.connect(self._estimar_merma)
        fila_botones_merma.addWidget(self.btn_estimar_merma)
        self.tutorial_targets["btn_estimar_merma"] = self.btn_estimar_merma

        if puede(sesion_actual.rol, "centro_inteligencia", "entrenar"):
            self.btn_entrenar_merma = QPushButton("🧠  Entrenar / actualizar modelo de merma")
            poner_clase(self.btn_entrenar_merma, "secundario")
            self.btn_entrenar_merma.clicked.connect(self._entrenar_modelo_merma)
            fila_botones_merma.addWidget(self.btn_entrenar_merma)
            self.tutorial_targets["btn_entrenar_merma"] = self.btn_entrenar_merma

        fila_botones_merma.addStretch()
        sl.addLayout(fila_botones_merma)

        self.lbl_estado_modelo_merma = QLabel("")
        self.lbl_estado_modelo_merma.setStyleSheet(f"color: {COLOR_TEXTO_SECUNDARIO};")
        self.lbl_estado_modelo_merma.setFont(fuente(8, cursiva=True))
        self.lbl_estado_modelo_merma.setWordWrap(True)
        sl.addWidget(self.lbl_estado_modelo_merma)
        self._actualizar_estado_modelo_merma()

        fila_resultado = QHBoxLayout()
        self.kpi_merma_pct = TarjetaKPI("Merma esperada", "—", "advertencia", "📉")
        self.kpi_rendimiento_esp = TarjetaKPI("Rendimiento esperado", "—", "exito", "✅")
        self.kpi_merma_hist_receta = TarjetaKPI("Promedio histórico de la receta", "—", "normal", "📊")
        for k in (self.kpi_merma_pct, self.kpi_rendimiento_esp, self.kpi_merma_hist_receta):
            fila_resultado.addWidget(k)
        v.addLayout(fila_resultado)

        self.lbl_alerta_merma = QLabel("")
        self.lbl_alerta_merma.setWordWrap(True)
        self.lbl_alerta_merma.setFont(fuente(9, negrita=True))
        v.addWidget(self.lbl_alerta_merma)
        v.addStretch()

        return tab

    def _actualizar_estado_modelo_merma(self):
        from app.ia.merma_training import modelo_disponible, leer_metadata
        if modelo_disponible():
            meta = leer_metadata() or {}
            fecha = meta.get("fecha_entrenamiento", "")[:16].replace("T", " ")
            n_filas = meta.get("filas_entrenamiento", "?")
            self.lbl_estado_modelo_merma.setText(
                f"Modelo de IA entrenado el {fecha} con {n_filas} órdenes. "
                "Mientras no haya suficiente historial nuevo, se sigue usando este modelo."
            )
        else:
            self.lbl_estado_modelo_merma.setText(
                "Aún no hay modelo de IA entrenado para merma: las estimaciones usan el "
                "promedio histórico por receta hasta que se entrene con suficientes órdenes completadas."
            )

    def _entrenar_modelo_merma(self):
        from app.ia.merma_training import entrenar as entrenar_merma
        self.btn_entrenar_merma.setEnabled(False)
        ejecutar_en_hilo(
            self, entrenar_merma,
            al_terminar=self._al_terminar_entrenamiento_merma,
            mensaje="🧠  Entrenando modelo de merma...",
            submensaje="Procesando el historial de órdenes de producción completadas...",
        )

    def _al_terminar_entrenamiento_merma(self, resultado, error):
        self.btn_entrenar_merma.setEnabled(True)
        if error is not None:
            self._msg.mostrar(f"No se pudo entrenar el modelo de merma: {error}", tipo="error")
            return

        if resultado.get("exito"):
            m = resultado.get("metricas", {})
            self._msg.mostrar(
                f"Modelo de merma entrenado correctamente (MAE≈{m.get('mae', '?')} p.p.).",
                tipo="exito",
            )
        else:
            self._msg.mostrar(resultado.get("mensaje", "No se pudo entrenar el modelo."), tipo="advertencia")

        self._actualizar_estado_modelo_merma()

    def _estimar_merma(self):
        datos_receta = self.combo_receta_merma.currentData()
        if not datos_receta:
            QMessageBox.warning(self, "Aviso", "No hay recetas activas registradas.")
            return
        cantidad = self.spin_cantidad_merma.value()

        resultado = predecir_merma(datos_receta["id"], cantidad, date.today())
        if not resultado.get("exito"):
            self._msg.mostrar(resultado.get("mensaje", "No se pudo estimar la merma."), tipo="advertencia")
            self.kpi_merma_pct.actualizar("—")
            self.kpi_rendimiento_esp.actualizar("—")
            self.kpi_merma_hist_receta.actualizar("—")
            self.lbl_alerta_merma.setText("")
            return

        self.kpi_merma_pct.actualizar(f"{resultado['merma_pct_esperada']:.1f}%")
        self.kpi_rendimiento_esp.actualizar(f"{resultado['rendimiento_esperado']:.2f} {datos_receta['unidad']}")
        hist = resultado.get("merma_promedio_historica_receta")
        self.kpi_merma_hist_receta.actualizar(f"{hist:.1f}%" if hist is not None else "Sin datos")

        if resultado.get("advertencia"):
            self._msg.mostrar(resultado["advertencia"], tipo="info")

        if resultado.get("alerta_sobre_historico"):
            self.lbl_alerta_merma.setText(
                "⚠️  La merma esperada para esta producción es notablemente mayor al comportamiento "
                "histórico de la receta. Conviene revisar el proceso antes de continuar."
            )
            self.lbl_alerta_merma.setStyleSheet(f"color: {COLOR_ALERTA};")
        else:
            self.lbl_alerta_merma.setText("✓ Dentro del comportamiento histórico esperado de la receta.")
            self.lbl_alerta_merma.setStyleSheet(f"color: {COLOR_EXITO};")

    # ══════════════════════════════════════════════════════════
    #  TAB 3 — DEMANDA PREVISTA (resumen rápido multi-producto)
    # ══════════════════════════════════════════════════════════
    def _construir_tab_demanda(self) -> QWidget:
        tab = QWidget()
        v = QVBoxLayout(tab)
        v.setContentsMargins(0, 12, 0, 0)
        v.setSpacing(10)

        fila_ctrl = QHBoxLayout()
        fila_ctrl.addWidget(QLabel("Horizonte:"))
        self.combo_horizonte_demanda = QComboBox()
        self.combo_horizonte_demanda.addItem("7 días", 7)
        self.combo_horizonte_demanda.addItem("14 días", 14)
        self.combo_horizonte_demanda.addItem("30 días", 30)
        self.combo_horizonte_demanda.setCurrentIndex(1)
        fila_ctrl.addWidget(self.combo_horizonte_demanda)
        fila_ctrl.addSpacing(20)
        self.btn_actualizar_demanda = QPushButton("🔄  Actualizar resumen")
        self.btn_actualizar_demanda.clicked.connect(self._actualizar_resumen_demanda)
        fila_ctrl.addWidget(self.btn_actualizar_demanda)
        self.tutorial_targets["btn_actualizar_demanda"] = self.btn_actualizar_demanda
        fila_ctrl.addStretch()
        v.addLayout(fila_ctrl)

        nota = QLabel(
            "Para el detalle diario y el gráfico de cada producto, usa la pestaña "
            "'Predicción de demanda (detalle)' de aquí mismo."
        )
        nota.setStyleSheet(f"color: {COLOR_TEXTO_SECUNDARIO};")
        nota.setFont(fuente(8, cursiva=True))
        v.addWidget(nota)

        self.tabla_demanda = TablaDatos(
            ["Producto", "Demanda prevista", "Promedio diario", "Riesgo de quiebre"],
            con_id=False,
            anchos={"Producto": 220, "Demanda prevista": 130, "Promedio diario": 120, "Riesgo de quiebre": 130},
        )
        v.addWidget(self.tabla_demanda, stretch=1)
        self.tutorial_targets["tabla_demanda"] = self.tabla_demanda

        return tab

    def _actualizar_resumen_demanda(self):
        horizonte = self.combo_horizonte_demanda.currentData()
        productos = listar_productos_con_ventas()

        def _calcular():
            filas, tags = [], []
            n_pronosticados = 0
            for p in productos:
                diag = diagnostico_historial(p["id"])
                if not diag["suficiente_baseline"]:
                    continue
                pred = predecir_demanda(p["id"], horizonte)
                if not pred.get("exito"):
                    continue
                n_pronosticados += 1
                filas.append([
                    f"{p['nombre']} ({p['unidad']})",
                    f"{pred['demanda_total']:.1f}",
                    f"{pred['promedio_diario']:.1f}",
                    "⚠️ Estimación básica" if not pred.get("usando_ml") else "🟢 Modelo IA",
                ])
                tags.append("advertencia" if not pred.get("usando_ml") else "normal")
            return filas, tags, n_pronosticados

        self.btn_actualizar_demanda.setEnabled(False)
        ejecutar_en_hilo(
            self, _calcular,
            al_terminar=self._al_terminar_resumen_demanda,
            mensaje="🧠  Analizando demanda...",
            submensaje="Procesando información histórica de ventas por producto...",
        )

    def _al_terminar_resumen_demanda(self, resultado, error):
        self.btn_actualizar_demanda.setEnabled(True)
        if error is not None:
            self._msg.mostrar(f"No se pudo analizar la demanda: {error}", tipo="error")
            return
        filas, tags, n_pronosticados = resultado

        self.tabla_demanda.cargar_filas(filas, tags_por_fila=tags)
        self.kpi_productos_pronosticados.actualizar(str(n_pronosticados))

        if not filas:
            self._msg.mostrar(
                "Ningún producto tiene todavía historial de ventas suficiente para pronosticar.",
                tipo="advertencia",
            )

    # ══════════════════════════════════════════════════════════
    #  API pública (llamada por ventana_principal al navegar aquí)
    # ══════════════════════════════════════════════════════════
    def refrescar(self):
        from app.ia.merma_data import diagnostico_historial as diag_merma
        diag = diag_merma(None)
        self.kpi_merma_prom.actualizar(
            f"{diag['merma_promedio_pct']:.1f}%" if diag["ordenes_totales"] > 0 else "Sin datos"
        )
        self._calcular_reposicion()
        self._actualizar_resumen_demanda()
