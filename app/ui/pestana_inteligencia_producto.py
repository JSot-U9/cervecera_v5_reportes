"""pestana_inteligencia_producto.py (PySide6)
============================================
Pestaña «🧠 Inteligencia» del detalle de producto.

Muestra, para UN producto, el resultado más reciente de los motores de
IA — sin volver a correr nada al abrirla:

  · Insumo             -> reposición sugerida (motor de Reposición).
  · Producto terminado -> demanda prevista + merma esperada de sus
                          recetas (motores de Demanda y de Merma).

Los resultados salen de app/ia/resultados_recientes.py, donde los
propios motores dejan su último cálculo (lo haya pedido el Centro de
Inteligencia, la pantalla de Predicción o esta misma pestaña). El botón
«Recalcular» corre el motor SOLO para este producto:

  · Reposición: calcular_recomendaciones(insumo_id=...) analiza un único
    insumo y únicamente las recetas que lo usan, no todo el catálogo.
  · Demanda/Merma: los motores ya trabajan por producto/receta.

Esta pestaña solo existe para roles con acceso al módulo Centro de
Inteligencia (la decide VistaDetalleProducto al construirse).
"""

from __future__ import annotations

from datetime import date

from PySide6.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QLabel, QPushButton, QStackedWidget,
)

from app.basedatos import nueva_sesion
from app.sesion import sesion_actual
from app.seguridad import puede
from app.ia import resultados_recientes
from app.logica_produccion import recetas_activas_de_producto
from app.ui.estilos import COLOR_TEXTO_SECUNDARIO, COLOR_TEXTO, fuente, poner_clase
from app.ui.widgets import (
    TarjetaKPI, MensajeEstado, EstadoVacio, SeccionFormulario, ejecutar_en_hilo,
    formatear_estado, tag_para_estado,
)

# Mismo horizonte por defecto que usa el motor de Reposición en el Centro.
HORIZONTE_DIAS = 14

_PAGINA_VACIA, _PAGINA_INSUMO, _PAGINA_TERMINADO = 0, 1, 2


def _fecha_legible(cuando) -> str:
    return cuando.strftime("%d/%m/%Y %H:%M")


class PestanaInteligenciaProducto(QWidget):
    def __init__(self, parent=None):
        super().__init__(parent)
        self._producto: dict | None = None

        raiz = QVBoxLayout(self)
        raiz.setContentsMargins(10, 10, 10, 10)
        raiz.setSpacing(10)

        intro = QLabel(
            "Resultado más reciente de los modelos de IA para este producto. "
            "Abrir esta pestaña no recalcula nada; «Recalcular» analiza solo "
            "este producto, no el resto del catálogo."
        )
        intro.setWordWrap(True)
        intro.setFont(fuente(8, cursiva=True))
        intro.setStyleSheet(f"color: {COLOR_TEXTO_SECUNDARIO};")
        raiz.addWidget(intro)

        self._msg = MensajeEstado()
        raiz.addWidget(self._msg)

        self._pila = QStackedWidget()
        raiz.addWidget(self._pila, stretch=1)

        puede_calcular = puede(sesion_actual.rol, "centro_inteligencia", "predecir")
        self._pila.addWidget(EstadoVacio(
            "🧠", "Todavía no hay un resultado calculado para este producto",
            "Ni el Centro de Inteligencia ni esta pestaña han analizado este producto "
            "desde que se abrió el programa.",
            texto_accion=("▶  Calcular ahora" if puede_calcular else ""),
            accion=(self.recalcular if puede_calcular else None),
        ))
        self._pila.addWidget(self._construir_pagina_insumo())
        self._pila.addWidget(self._construir_pagina_terminado())

        pie = QHBoxLayout()
        self._lbl_calculado = QLabel("")
        self._lbl_calculado.setFont(fuente(8))
        self._lbl_calculado.setStyleSheet(f"color: {COLOR_TEXTO_SECUNDARIO};")
        pie.addWidget(self._lbl_calculado)
        pie.addStretch()
        self._btn_centro = QPushButton("🧠  Abrir Centro de Inteligencia")
        poner_clase(self._btn_centro, "secundario")
        self._btn_centro.clicked.connect(self._abrir_centro)
        pie.addWidget(self._btn_centro)
        self._btn_recalcular = QPushButton("🔄  Recalcular este producto")
        self._btn_recalcular.clicked.connect(self.recalcular)
        self._btn_recalcular.setVisible(puede_calcular)
        pie.addWidget(self._btn_recalcular)
        raiz.addLayout(pie)

    # ── Construcción de las dos variantes de contenido ────────────
    def _fila_kpis(self, definiciones):
        fila = QHBoxLayout()
        fila.setSpacing(10)
        tarjetas = []
        for etiqueta, icono in definiciones:
            t = TarjetaKPI(etiqueta, "—", "normal", icono)
            fila.addWidget(t)
            tarjetas.append(t)
        return fila, tarjetas

    def _construir_pagina_insumo(self) -> QWidget:
        pagina = QWidget()
        v = QVBoxLayout(pagina)
        v.setContentsMargins(0, 0, 0, 0)
        v.setSpacing(10)

        self._lbl_titulo_insumo = QLabel("Reposición sugerida")
        self._lbl_titulo_insumo.setFont(fuente(11, negrita=True))
        v.addWidget(self._lbl_titulo_insumo)

        fila, (self.kpi_reponer, self.kpi_demanda_insumo,
               self.kpi_seguridad, self.kpi_prioridad) = self._fila_kpis([
            ("Cantidad a reponer", "📦"), ("Demanda esperada", "📈"),
            ("Stock de seguridad", "🛡"), ("Prioridad", "🚦"),
        ])
        v.addLayout(fila)

        self._lbl_motivo = QLabel("")
        self._lbl_motivo.setWordWrap(True)
        self._lbl_motivo.setFont(fuente(9))
        self._lbl_motivo.setStyleSheet(f"color: {COLOR_TEXTO};")
        v.addWidget(self._lbl_motivo)
        v.addStretch()
        return pagina

    def _construir_pagina_terminado(self) -> QWidget:
        pagina = QWidget()
        v = QVBoxLayout(pagina)
        v.setContentsMargins(0, 0, 0, 0)
        v.setSpacing(10)

        self._lbl_titulo_demanda = QLabel("Demanda prevista")
        self._lbl_titulo_demanda.setFont(fuente(11, negrita=True))
        v.addWidget(self._lbl_titulo_demanda)

        fila, (self.kpi_demanda_total, self.kpi_promedio,
               self.kpi_rango, self.kpi_modelo) = self._fila_kpis([
            ("Demanda total prevista", "🔮"), ("Promedio diario", "📅"),
            ("Rango diario (mín – máx)", "↕"), ("Modelo usado", "⚙"),
        ])
        v.addLayout(fila)

        self._lbl_aviso_demanda = QLabel("")
        self._lbl_aviso_demanda.setWordWrap(True)
        self._lbl_aviso_demanda.setFont(fuente(9))
        self._lbl_aviso_demanda.setStyleSheet(f"color: {COLOR_TEXTO_SECUNDARIO};")
        v.addWidget(self._lbl_aviso_demanda)

        seccion = SeccionFormulario("Merma esperada al producir")
        sl = QVBoxLayout(seccion)
        self._lbl_merma = QLabel("")
        self._lbl_merma.setWordWrap(True)
        self._lbl_merma.setFont(fuente(9))
        sl.addWidget(self._lbl_merma)
        v.addWidget(seccion)
        v.addStretch()
        return pagina

    # ── API pública ────────────────────────────────────────────────
    def cargar(self, producto: dict):
        """Asocia la pestaña a un producto (dict de resumen_producto) y
        muestra lo último que se haya calculado para él."""
        self._producto = producto
        self.repintar()

    def repintar(self):
        """Vuelve a leer lo último calculado (barato, no corre ningún
        motor) — se llama al abrir el producto y al entrar a la pestaña,
        por si el Centro de Inteligencia calculó algo mientras tanto."""
        if self._producto is None:
            return
        if self._producto["tipo"] == "Insumo":
            self._pintar_insumo()
        else:
            self._pintar_terminado()

    def recalcular(self):
        """Corre el motor SOLO para este producto, en un hilo aparte."""
        if self._producto is None:
            return
        producto = dict(self._producto)
        self._btn_recalcular.setEnabled(False)

        def _calcular():
            # Imports aquí dentro: los motores traen pandas/xgboost y no
            # hace falta cargarlos hasta que alguien pide un cálculo.
            if producto["tipo"] == "Insumo":
                from app.ia.reposicion import calcular_recomendaciones
                calcular_recomendaciones(
                    horizonte_dias=HORIZONTE_DIAS, insumo_id=producto["id"],
                    incluir_sin_necesidad=True,
                )
            else:
                from app.ia.demanda_prediction import predecir_demanda
                from app.ia.merma_prediction import predecir_merma
                predecir_demanda(producto["id"], HORIZONTE_DIAS)
                with nueva_sesion() as db:
                    recetas = recetas_activas_de_producto(db, producto["id"])
                for receta in recetas:
                    predecir_merma(receta["id"], receta["rendimiento"], date.today())
            return producto["id"]

        ejecutar_en_hilo(
            self, _calcular,
            al_terminar=lambda resultado, error: self._al_terminar(producto["id"], error),
            mensaje="🧠  Analizando este producto...",
            submensaje="Solo se calcula este producto, no todo el catálogo.",
        )

    # ── Internos ───────────────────────────────────────────────────
    def _al_terminar(self, producto_id: int, error):
        self._btn_recalcular.setEnabled(True)
        if error is not None:
            self._msg.mostrar(f"No se pudo calcular: {error}", tipo="error")
            return
        # El resultado ya quedó guardado por el propio motor; si mientras
        # tanto el usuario cambió de producto, no hay nada que pintar.
        if self._producto is not None and self._producto["id"] == producto_id:
            self.repintar()
            self._msg.mostrar("Resultado actualizado para este producto.", tipo="exito")

    def _abrir_centro(self):
        ventana = self.window()
        if hasattr(ventana, "navegar"):
            ventana.navegar("centro_inteligencia")

    def _mostrar_pagina(self, indice: int, cuando=None):
        self._pila.setCurrentIndex(indice)
        hay_resultado = indice != _PAGINA_VACIA
        self._btn_recalcular.setText("🔄  Recalcular este producto")
        # Sin resultado, el botón de acción vive en el propio estado vacío.
        self._btn_recalcular.setVisible(
            hay_resultado and puede(sesion_actual.rol, "centro_inteligencia", "predecir"))
        self._lbl_calculado.setText(
            f"Calculado el {_fecha_legible(cuando)}" if (hay_resultado and cuando) else "")

    def _pintar_insumo(self):
        pid = self._producto["id"]
        entrada = resultados_recientes.obtener(f"reposicion:{pid}")
        if entrada is None:
            self._mostrar_pagina(_PAGINA_VACIA)
            return
        dato, cuando = entrada
        rec, horizonte = dato["rec"], dato["horizonte"]
        unidad = self._producto["unidad"]

        self._lbl_titulo_insumo.setText(f"Reposición sugerida (próximos {horizonte} días)")
        if rec is None:
            # Se calculó (con el Centro) y este insumo no necesitó reposición.
            for k in (self.kpi_demanda_insumo, self.kpi_seguridad, self.kpi_prioridad):
                k.actualizar("—")
                k.establecer_variante("normal")
            self.kpi_reponer.actualizar(f"0.00 {unidad}".strip())
            self.kpi_reponer.establecer_variante("exito")
            self._lbl_motivo.setText(
                "✅ En el último cálculo este insumo no necesitó reposición: el stock "
                "disponible cubre la demanda esperada más el stock de seguridad.")
        else:
            self.kpi_reponer.actualizar(f"{rec['cantidad_recomendada']:.2f} {unidad}".strip())
            self.kpi_demanda_insumo.actualizar(f"{rec['demanda_esperada']:.2f}")
            self.kpi_seguridad.actualizar(f"{rec['stock_seguridad']:.2f}")
            self.kpi_prioridad.actualizar(formatear_estado(rec["prioridad"]))
            variante_prioridad = tag_para_estado(rec["prioridad"])
            self.kpi_prioridad.establecer_variante(variante_prioridad)
            self.kpi_reponer.establecer_variante(
                "alerta" if rec["prioridad"] == "ALTA"
                else "advertencia" if rec["cantidad_recomendada"] > 0 else "exito")
            self.kpi_demanda_insumo.establecer_variante("normal")
            self.kpi_seguridad.establecer_variante("normal")
            self._lbl_motivo.setText(f"💡 {rec['motivo']}")
        self._mostrar_pagina(_PAGINA_INSUMO, cuando)

    def _pintar_terminado(self):
        pid = self._producto["id"]
        demanda = resultados_recientes.obtener(f"demanda:{pid}")
        with nueva_sesion() as db:
            recetas = recetas_activas_de_producto(db, pid)
        mermas = [(r, resultados_recientes.obtener(f"merma:{r['id']}")) for r in recetas]
        mermas_calculadas = [m for _r, m in mermas if m is not None]

        if demanda is None and not mermas_calculadas:
            self._mostrar_pagina(_PAGINA_VACIA)
            return

        # ── Demanda ──
        cuando_demanda = None
        if demanda is None:
            self._lbl_titulo_demanda.setText("Demanda prevista")
            for k in (self.kpi_demanda_total, self.kpi_promedio, self.kpi_rango, self.kpi_modelo):
                k.actualizar("—")
            self._lbl_aviso_demanda.setText("La demanda de este producto aún no se calculó.")
        else:
            d, cuando_demanda = demanda
            self._lbl_titulo_demanda.setText(f"Demanda prevista (próximos {d['horizonte']} días)")
            if d.get("exito"):
                unidad = self._producto["unidad"]
                self.kpi_demanda_total.actualizar(f"{d['demanda_total']:.1f} {unidad}".strip())
                self.kpi_promedio.actualizar(f"{d['promedio_diario']:.1f}")
                self.kpi_rango.actualizar(f"{d['demanda_min']:.1f} – {d['demanda_max']:.1f}")
                self.kpi_modelo.actualizar("IA" if d["usando_ml"] else "Prom. móvil")
                self._lbl_aviso_demanda.setText(d.get("advertencia") or "")
            else:
                for k in (self.kpi_demanda_total, self.kpi_promedio, self.kpi_rango, self.kpi_modelo):
                    k.actualizar("—")
                self._lbl_aviso_demanda.setText(f"⚠ {d.get('mensaje', 'No se pudo calcular la demanda.')}")

        # ── Merma por receta ──
        if not recetas:
            self._lbl_merma.setText("Este producto no tiene una receta activa, así que no hay merma que estimar.")
        else:
            lineas = []
            for receta, entrada in mermas:
                nombre = f"Receta #{receta['id']} (rinde {receta['rendimiento']:g} {receta['unidad']})"
                if entrada is None:
                    lineas.append(f"• {nombre}: aún sin calcular.")
                    continue
                m, _cuando = entrada
                if not m.get("exito"):
                    lineas.append(f"• {nombre}: ⚠ {m.get('mensaje', 'no se pudo estimar')}")
                    continue
                historica = m.get("merma_promedio_historica_receta")
                extra = f" · promedio histórico {historica:.1f} %" if historica is not None else ""
                alerta = "  ⚠ por encima de lo habitual" if m.get("alerta_sobre_historico") else ""
                lineas.append(f"• {nombre}: {m['merma_pct_esperada']:.1f} % esperada{extra}{alerta}")
            self._lbl_merma.setText("\n".join(lineas))

        cuando = max([c for c in [cuando_demanda] + [m[1] for m in mermas_calculadas] if c])
        self._mostrar_pagina(_PAGINA_TERMINADO, cuando)
