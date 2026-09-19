"""vista_produccion.py (PySide6)
=================================
Planificación, seguimiento y cierre de órdenes de elaboración de cerveza.
"""

from datetime import date

from PySide6.QtCore import Qt
from PySide6.QtWidgets import (
    QWidget, QDialog, QVBoxLayout, QHBoxLayout, QLabel, QLineEdit, QComboBox,
    QPushButton, QMessageBox,
)

from app.basedatos import nueva_sesion
from app.modelos import OrdenProduccion
from app.sesion import sesion_actual
from app.seguridad import puede, modulos_visibles
from app.logica_produccion import (
    crear_orden, iniciar_proceso, cerrar_orden, listar_ordenes, listar_recetas_activas,
)
from app.ui.widgets import (
    EncabezadoModulo, BarraBusqueda, TablaDatos, SeccionFormulario, MensajeEstado,
    centrar_ventana, formatear_estado,
)
from app.ui.estilos import COLOR_TEXTO_SECUNDARIO, COLOR_PRIMARIO, fuente, poner_clase, fondo

ESTADOS_QUE_SE_PUEDEN_CERRAR = ("INICIADA", "EN_PROCESO")

_TEXTO_PRODUCCION = (
    "Una orden pasa por 3 estados: INICIADA (recién creada), EN_PROCESO (cuando "
    "empiezas a elaborar) y COMPLETADA (al cerrarla). Cerrar la orden hace, en un "
    "solo paso, el descuento de insumos, el registro de la merma, la creación del "
    "lote terminado y el cálculo de costos."
)
_TEXTO_RECETAS = (
    "Una receta define qué insumos (y en qué cantidad) se necesitan para elaborar "
    "una unidad de un producto terminado. Se usa como base al crear una orden de "
    "producción para saber qué se va a consumir del inventario."
)


class VistaProduccion(QWidget):
    def __init__(self, parent=None):
        super().__init__(parent)
        self.tutorial_targets = {}

        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(0)
        layout.addWidget(EncabezadoModulo(
            "Producción", "Planificación, seguimiento y cierre de órdenes de elaboración de cerveza",
            icono="🍺",
        ))

        cuerpo = QVBoxLayout()
        cuerpo.setContentsMargins(12, 10, 12, 10)
        layout.addLayout(cuerpo, stretch=1)

        puede_crear = puede(sesion_actual.rol, "produccion", "crear")
        puede_iniciar = puede(sesion_actual.rol, "produccion", "iniciar")
        puede_cerrar = puede(sesion_actual.rol, "produccion", "cerrar")

        barra = BarraBusqueda(al_escribir=lambda t: self.tabla.filtrar(t),
                               placeholder="🔎  Buscar orden, lote, producto...")
        if puede_crear:
            self.tutorial_targets["btn_nueva_orden"] = barra.agregar_boton(
                "＋  Nueva orden", self._abrir_nueva_orden)
        if puede_iniciar:
            self.tutorial_targets["btn_iniciar"] = barra.agregar_boton(
                "▶  Iniciar", self._iniciar, estilo="accionSecundaria")
        if puede_cerrar:
            self.tutorial_targets["btn_cerrar"] = barra.agregar_boton(
                "✔  Cerrar orden", self._abrir_cerrar_orden, estilo="accionSecundaria")
        self.tutorial_targets["btn_reporte"] = barra.agregar_boton(
            "📊  Reporte", self._abrir_dialogo_reporte, estilo="accionSecundaria")
        if "centro_inteligencia" in modulos_visibles(sesion_actual.rol):
            barra.agregar_boton(
                "🧠  Merma esperada", lambda: self._ir_a_inteligencia(),
                estilo="accionSecundaria")
        btn_ayuda = QPushButton("❓")
        btn_ayuda.setFixedWidth(30)
        poner_clase(btn_ayuda, "secundario")
        btn_ayuda.clicked.connect(
            lambda: QMessageBox.information(self, "¿Cómo funciona una orden de producción?",
                                             _TEXTO_PRODUCCION))
        barra._botones_layout.addWidget(btn_ayuda)
        cuerpo.addWidget(barra)

        self.tabla = TablaDatos(
            ["N° Orden", "Producto", "N° Lote", "Cant. Planeada", "Cant. Real", "Estado"],
            anchos={"N° Orden": 110, "Producto": 180, "N° Lote": 130,
                    "Cant. Planeada": 110, "Cant. Real": 100, "Estado": 130},
        )
        cuerpo.addWidget(self.tabla, stretch=1)
        self.tutorial_targets["tabla_ordenes"] = self.tabla

        self.refrescar()

    def _ir_a_inteligencia(self):
        """Enlace de integración IA (sección 28): predicción de merma
        esperada, calculada en el Centro de Inteligencia."""
        ventana = self.window()
        if hasattr(ventana, "navegar"):
            ventana.navegar("centro_inteligencia")

    def refrescar(self):
        with nueva_sesion() as db:
            filas, tags = [], []
            for orden in listar_ordenes(db):
                producto = orden.receta.producto_terminado.nombre if orden.receta else "—"
                estado_visual = formatear_estado(orden.estado)
                tag = {
                    "INICIADA": "advertencia", "EN_PROCESO": "advertencia",
                    "COMPLETADA": "exito", "CANCELADA": "alerta",
                }.get(orden.estado, "normal")
                filas.append([
                    orden.id, orden.numero, producto, orden.numero_lote,
                    f"{orden.cantidad_planeada:.1f}",
                    f"{orden.cantidad_real:.1f}" if orden.cantidad_real else "—",
                    estado_visual,
                ])
                tags.append(tag)
        self.tabla.cargar_filas(filas, tags_por_fila=tags)

    def _abrir_nueva_orden(self):
        VentanaNuevaOrdenProduccion(self.window(), al_guardar=self.refrescar).exec()

    def _iniciar(self):
        orden_id = self.tabla.id_seleccionado()
        if not orden_id:
            QMessageBox.warning(self, "Aviso", "Selecciona una orden de la lista primero.")
            return
        try:
            iniciar_proceso(orden_id)
        except Exception as error:
            QMessageBox.critical(self, "No se pudo iniciar",
                                  f"No fue posible iniciar el proceso.\n\nDetalle: {error}")
            return
        self.refrescar()

    def _abrir_cerrar_orden(self):
        orden_id = self.tabla.id_seleccionado()
        if not orden_id:
            QMessageBox.warning(self, "Aviso", "Selecciona una orden de la lista primero.")
            return
        with nueva_sesion() as db:
            orden = db.get(OrdenProduccion, orden_id)
        if not orden or orden.estado not in ESTADOS_QUE_SE_PUEDEN_CERRAR:
            estado_actual = orden.estado if orden else "desconocido"
            QMessageBox.critical(
                self, "No se puede cerrar",
                f"La orden está en estado '{estado_actual}'.\n\n"
                f"Solo se pueden cerrar órdenes en estado INICIADA o EN_PROCESO.")
            return
        VentanaCerrarOrden(self.window(), orden_id, al_guardar=self.refrescar).exec()

    def _abrir_dialogo_reporte(self):
        from app.ui.dialogo_reporte import DialogoReporte
        dlg = DialogoReporte(self.window(), modulo="produccion")
        dlg.show()
        return dlg


def _franja(titulo_texto: str) -> QWidget:
    franja = QWidget()
    fondo(franja, COLOR_PRIMARIO)
    fl = QVBoxLayout(franja)
    fl.setContentsMargins(20, 12, 20, 12)
    lbl = QLabel(titulo_texto)
    lbl.setStyleSheet("background: transparent; color: white;")
    lbl.setFont(fuente(13, negrita=True))
    fl.addWidget(lbl)
    return franja


class VentanaNuevaOrdenProduccion(QDialog):
    def __init__(self, parent, al_guardar):
        super().__init__(parent)
        self.setWindowTitle("Nueva orden de producción")
        self.al_guardar = al_guardar

        with nueva_sesion() as db:
            self.recetas = listar_recetas_activas(db)
            self.opciones_receta = [
                (r.id, f"{r.id} — {r.producto_terminado.nombre} "
                       f"(rinde {r.rendimiento} {r.unidad_rendimiento})")
                for r in self.recetas
            ]
            n_ordenes = db.query(OrdenProduccion).count()
        numero_lote_auto = f"LOTE-{date.today().year}-{n_ordenes + 1:03d}"

        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(0)
        layout.addWidget(_franja("🍺  Nueva orden de producción"))

        cuerpo = QVBoxLayout()
        cuerpo.setContentsMargins(20, 16, 20, 16)
        layout.addLayout(cuerpo)

        self._msg = MensajeEstado()
        cuerpo.addWidget(self._msg)

        sec = SeccionFormulario("Datos de la orden")
        secl = QVBoxLayout(sec)
        cuerpo.addWidget(sec)

        fila_receta = QHBoxLayout()
        lbl_receta = QLabel("Receta de cerveza *")
        lbl_receta.setFont(fuente(9, negrita=True))
        fila_receta.addWidget(lbl_receta)
        fila_receta.addStretch()
        btn_ayuda = QPushButton("❓")
        btn_ayuda.setFixedWidth(30)
        poner_clase(btn_ayuda, "secundario")
        btn_ayuda.clicked.connect(
            lambda: QMessageBox.information(self, "¿Qué es una receta?", _TEXTO_RECETAS))
        fila_receta.addWidget(btn_ayuda)
        secl.addLayout(fila_receta)

        self.combo_receta = QComboBox()
        for receta_id, texto in self.opciones_receta:
            self.combo_receta.addItem(texto, receta_id)
        self.combo_receta.setCurrentIndex(-1)
        secl.addWidget(self.combo_receta)
        secl.addSpacing(8)

        lbl_cant = QLabel("Cantidad planeada a producir *")
        lbl_cant.setFont(fuente(9, negrita=True))
        secl.addWidget(lbl_cant)
        self.entrada_cantidad = QLineEdit()
        self.entrada_cantidad.setFixedWidth(140)
        secl.addWidget(self.entrada_cantidad)

        sec_lote = SeccionFormulario("Número de lote")
        sll = QVBoxLayout(sec_lote)
        cuerpo.addWidget(sec_lote)
        lbl_auto = QLabel("Generado automáticamente. Puedes editarlo si es necesario.")
        lbl_auto.setStyleSheet(f"color: {COLOR_TEXTO_SECUNDARIO};")
        lbl_auto.setFont(fuente(8, cursiva=True))
        sll.addWidget(lbl_auto)
        self.entrada_lote = QLineEdit(numero_lote_auto)
        sll.addWidget(self.entrada_lote)

        sec_obs = SeccionFormulario("Observaciones")
        sol = QVBoxLayout(sec_obs)
        cuerpo.addWidget(sec_obs)
        self.entrada_observaciones = QLineEdit()
        sol.addWidget(self.entrada_observaciones)
        lbl_opt = QLabel("Opcional")
        lbl_opt.setStyleSheet(f"color: {COLOR_TEXTO_SECUNDARIO};")
        lbl_opt.setFont(fuente(8, cursiva=True))
        sol.addWidget(lbl_opt)

        lbl_nota = QLabel("* Campo obligatorio")
        lbl_nota.setStyleSheet(f"color: {COLOR_TEXTO_SECUNDARIO};")
        lbl_nota.setFont(fuente(8, cursiva=True))
        cuerpo.addWidget(lbl_nota)
        cuerpo.addStretch()

        fila_btn = QHBoxLayout()
        fila_btn.addStretch()
        btn_cancelar = QPushButton("Cancelar")
        poner_clase(btn_cancelar, "secundario")
        btn_cancelar.clicked.connect(self.reject)
        fila_btn.addWidget(btn_cancelar)
        btn_guardar = QPushButton("🍺  Crear orden")
        btn_guardar.clicked.connect(self._guardar)
        fila_btn.addWidget(btn_guardar)
        cuerpo.addLayout(fila_btn)

        centrar_ventana(self, 500, 480)

    def _guardar(self):
        receta_id = self.combo_receta.currentData()
        if receta_id is None:
            self._msg.mostrar("Selecciona una receta de cerveza.", "error")
            return
        numero_lote = self.entrada_lote.text().strip()
        if not numero_lote:
            self._msg.mostrar("El número de lote es obligatorio.", "error")
            return
        try:
            cantidad = float(self.entrada_cantidad.text())
            if cantidad <= 0:
                raise ValueError
        except ValueError:
            self._msg.mostrar("La cantidad planeada debe ser un número mayor que 0.", "error")
            return

        try:
            orden = crear_orden(
                receta_id=receta_id, cantidad_planeada=cantidad, numero_lote=numero_lote,
                observaciones=self.entrada_observaciones.text().strip(),
                usuario_id=sesion_actual.usuario_id,
            )
        except Exception as error:
            QMessageBox.critical(self, "No se pudo crear la orden", f"Ocurrió un error:\n\n{error}")
            return

        QMessageBox.information(
            self, "✓ Orden creada",
            f"Orden {orden.numero} creada correctamente.\nLote: {numero_lote}")
        self.al_guardar()
        self.accept()

    def keyPressEvent(self, evento):
        if evento.key() == Qt.Key_Escape:
            self.reject()
        else:
            super().keyPressEvent(evento)


class VentanaCerrarOrden(QDialog):
    def __init__(self, parent, orden_id, al_guardar):
        super().__init__(parent)
        self.setWindowTitle("Cerrar orden de producción")
        self.orden_id = orden_id
        self.al_guardar = al_guardar
        # Se necesita la cantidad planeada para poder sugerir la merma
        # automáticamente (ver _al_cambiar_cantidad_real más abajo).
        with nueva_sesion() as db:
            orden = db.get(OrdenProduccion, orden_id)
            self.cantidad_planeada = orden.cantidad_planeada if orden else None
        # True en cuanto el usuario escribe algo él mismo en el campo de
        # merma: a partir de ahí se respeta lo que puso y se deja de
        # sobrescribirlo automáticamente.
        self._merma_editada_manualmente = False

        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(0)
        layout.addWidget(_franja("✔  Cerrar orden de producción"))

        cuerpo = QVBoxLayout()
        cuerpo.setContentsMargins(20, 16, 20, 16)
        layout.addLayout(cuerpo)

        self._msg = MensajeEstado()
        cuerpo.addWidget(self._msg)

        lbl_info = QLabel(
            "Al cerrar la orden:\n"
            "  • Se descuentan los insumos del inventario (FIFO)\n"
            "  • Se crea el lote de producto terminado\n"
            "  • Se calcula el costo real de producción")
        lbl_info.setStyleSheet(f"color: {COLOR_TEXTO_SECUNDARIO};")
        lbl_info.setFont(fuente(9))
        cuerpo.addWidget(lbl_info)

        if self.cantidad_planeada:
            lbl_planeada = QLabel(
                f"Cantidad planeada: {self.cantidad_planeada:.1f}. La merma se sugiere "
                f"automáticamente como (planeada − real) — puedes corregirla si lo necesitas.")
            lbl_planeada.setStyleSheet(f"color: {COLOR_TEXTO_SECUNDARIO};")
            lbl_planeada.setFont(fuente(8, cursiva=True))
            lbl_planeada.setWordWrap(True)
            cuerpo.addWidget(lbl_planeada)
        cuerpo.addSpacing(8)

        sec_prod = SeccionFormulario("Producción real")
        spl = QVBoxLayout(sec_prod)
        cuerpo.addWidget(sec_prod)

        f1 = QHBoxLayout()
        spl.addLayout(f1)
        c1 = QVBoxLayout()
        lbl_c1 = QLabel("Cantidad real producida *")
        lbl_c1.setFont(fuente(9, negrita=True))
        c1.addWidget(lbl_c1)
        self.entrada_cantidad_real = QLineEdit()
        self.entrada_cantidad_real.setFixedWidth(120)
        self.entrada_cantidad_real.textEdited.connect(self._al_cambiar_cantidad_real)
        c1.addWidget(self.entrada_cantidad_real)
        f1.addLayout(c1)

        c2 = QVBoxLayout()
        lbl_c2 = QLabel("Cantidad de merma")
        c2.addWidget(lbl_c2)
        self.entrada_merma = QLineEdit("0")
        self.entrada_merma.setFixedWidth(120)
        # textEdited (a diferencia de textChanged) solo se dispara
        # cuando el USUARIO teclea, no cuando el código llama a
        # setText(...) para autocompletar — así se puede distinguir
        # "el sistema sugirió esto" de "el usuario lo corrigió a mano".
        self.entrada_merma.textEdited.connect(self._marcar_merma_editada)
        c2.addWidget(self.entrada_merma)
        f1.addLayout(c2)
        f1.addStretch()

        lbl_causa = QLabel("Causa de la merma (dejar en blanco si no hubo)")
        spl.addWidget(lbl_causa)
        self.entrada_causa_merma = QLineEdit()
        spl.addWidget(self.entrada_causa_merma)

        sec_costos = SeccionFormulario("Costos adicionales")
        scl = QHBoxLayout(sec_costos)
        cuerpo.addWidget(sec_costos)

        c3 = QVBoxLayout()
        lbl_c3 = QLabel("Mano de obra (S/)")
        c3.addWidget(lbl_c3)
        self.entrada_mano_obra = QLineEdit("0")
        self.entrada_mano_obra.setFixedWidth(120)
        c3.addWidget(self.entrada_mano_obra)
        scl.addLayout(c3)

        c4 = QVBoxLayout()
        lbl_c4 = QLabel("Costos indirectos (S/)")
        c4.addWidget(lbl_c4)
        self.entrada_indirectos = QLineEdit("0")
        self.entrada_indirectos.setFixedWidth(120)
        c4.addWidget(self.entrada_indirectos)
        lbl_hint = QLabel("Energía, agua, etc.")
        lbl_hint.setStyleSheet(f"color: {COLOR_TEXTO_SECUNDARIO};")
        lbl_hint.setFont(fuente(8, cursiva=True))
        c4.addWidget(lbl_hint)
        scl.addLayout(c4)
        scl.addStretch()

        lbl_nota = QLabel("* Campo obligatorio")
        lbl_nota.setStyleSheet(f"color: {COLOR_TEXTO_SECUNDARIO};")
        lbl_nota.setFont(fuente(8, cursiva=True))
        cuerpo.addWidget(lbl_nota)
        cuerpo.addStretch()

        fila_btn = QHBoxLayout()
        fila_btn.addStretch()
        btn_cancelar = QPushButton("Cancelar")
        poner_clase(btn_cancelar, "secundario")
        btn_cancelar.clicked.connect(self.reject)
        fila_btn.addWidget(btn_cancelar)
        btn_guardar = QPushButton("✔  Cerrar y costear orden")
        btn_guardar.clicked.connect(self._guardar)
        fila_btn.addWidget(btn_guardar)
        cuerpo.addLayout(fila_btn)

        centrar_ventana(self, 500, 560)

    def _marcar_merma_editada(self, _texto: str):
        self._merma_editada_manualmente = True

    def _al_cambiar_cantidad_real(self, texto: str):
        if self._merma_editada_manualmente or not self.cantidad_planeada:
            return
        try:
            cantidad_real = float(texto)
        except ValueError:
            return
        merma_sugerida = max(0.0, self.cantidad_planeada - cantidad_real)
        # setText no dispara textEdited, así que esto no se confunde
        # con una edición manual del usuario.
        self.entrada_merma.setText(f"{merma_sugerida:.2f}")

    def _guardar(self):
        try:
            cantidad_real = float(self.entrada_cantidad_real.text())
            merma = float(self.entrada_merma.text() or 0)
            mano_obra = float(self.entrada_mano_obra.text() or 0)
            indirectos = float(self.entrada_indirectos.text() or 0)
            if cantidad_real <= 0:
                raise ValueError
        except ValueError:
            self._msg.mostrar(
                "Revisa que la cantidad real sea mayor que 0 y todos los números sean válidos.",
                "error")
            return

        try:
            orden = cerrar_orden(
                orden_id=self.orden_id, cantidad_real=cantidad_real, cantidad_merma=merma,
                causa_merma=self.entrada_causa_merma.text().strip(),
                costo_mano_obra=mano_obra, costos_indirectos=indirectos,
                usuario_id=sesion_actual.usuario_id,
            )
        except Exception as error:
            QMessageBox.critical(self, "No se pudo cerrar la orden", f"Ocurrió un error:\n\n{error}")
            return

        QMessageBox.information(
            self, "✓ Orden cerrada correctamente",
            f"La orden {orden.numero} fue cerrada y costeada.\n"
            f"Cantidad real: {cantidad_real:.1f}\nEl inventario de insumos fue descontado.")
        self.al_guardar()
        self.accept()

    def keyPressEvent(self, evento):
        if evento.key() == Qt.Key_Escape:
            self.reject()
        else:
            super().keyPressEvent(evento)
