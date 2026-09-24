"""vista_admin.py (PySide6)
============================
Cuentas de usuario · Configuración de la empresa · Registros de acceso.
"""

from PySide6.QtCore import Qt
from PySide6.QtGui import QShortcut, QKeySequence
from PySide6.QtWidgets import (
    QWidget, QDialog, QVBoxLayout, QHBoxLayout, QGridLayout, QLabel,
    QLineEdit, QComboBox, QPushButton, QTabWidget, QMessageBox, QScrollArea,
)

from app.basedatos import nueva_sesion
from app.modelos import LogAcceso, Usuario, OrdenCompra
from app.logica_autenticacion import (
    listar_usuarios, crear_usuario, desactivar_usuario, reactivar_usuario, ErrorAutenticacion,
)
from app.logica_configuracion import obtener_datos_empresa, guardar_datos_empresa
from app.ui.widgets import (
    EncabezadoModulo, BarraBusqueda, TablaDatos, SeccionFormulario, MensajeEstado,
    centrar_ventana, confirmar, formatear_estado, tag_para_estado, EstadoVacio,
    conectar_pestanas_a_header, CampoFormulario, conectar_boton_a_validez,
)
from app.ui.estilos import (
    COLOR_TEXTO_SECUNDARIO, COLOR_PRIMARIO, COLOR_TEXTO, COLOR_CAMPO_DESHABILITADO,
    fuente, poner_clase, fondo,
)

ROLES_DISPONIBLES = ["ADMIN", "COMPRAS", "INVENTARIO", "PRODUCCION", "VENTAS", "COSTOS"]

_ROL_DESCRIPCION = {
    "ADMIN": "Acceso total a todos los módulos",
    "COMPRAS": "Módulo de compras y proveedores",
    "INVENTARIO": "Módulo de inventario y catálogo",
    "PRODUCCION": "Módulo de producción",
    "VENTAS": "Módulo de ventas y clientes",
    "COSTOS": "Módulo de costos (solo lectura)",
}


class VistaAdmin(QWidget):
    def __init__(self, parent=None):
        super().__init__(parent)
        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(0)
        layout.addWidget(EncabezadoModulo(
            "Administración", "Cuentas de usuario · Configuración de la empresa · Registros de acceso",
            icono="⚙️",
        ))

        self.notebook = QTabWidget()
        layout.addWidget(self.notebook, stretch=1)

        self._pestana_usuarios()
        self._pestana_empresa()
        self._pestana_logs()
        conectar_pestanas_a_header(self.notebook, self)

        self.refrescar()

    def _pestana_usuarios(self):
        pestana = QWidget()
        pl = QVBoxLayout(pestana)
        pl.setContentsMargins(10, 10, 10, 10)
        self.notebook.addTab(pestana, "👤  Usuarios")

        barra = BarraBusqueda(al_escribir=lambda t: self.tabla_usuarios.filtrar(t),
                               placeholder="🔎  Buscar usuario...")
        barra.agregar_boton("＋  Nuevo usuario", self._abrir_nuevo_usuario)
        self.accion_nuevo = self._abrir_nuevo_usuario  # Ctrl+N global
        barra.agregar_boton("✓  Reactivar", self._reactivar, estilo="exito")
        barra.agregar_boton("✗  Desactivar", self._desactivar, estilo="peligro")
        pl.addWidget(barra)

        self.tabla_usuarios = TablaDatos(
            ["Usuario (login)", "Nombre Completo", "Rol", "Estado"],
            anchos={"Usuario (login)": 140, "Nombre Completo": 200, "Rol": 120, "Estado": 120},
            estado_vacio=EstadoVacio(
                "👤", "Sin usuarios que mostrar",
                "Todavía no se registró ningún usuario, o el filtro no encontró "
                "coincidencias.",
                texto_accion="＋ Nuevo usuario", accion=self._abrir_nuevo_usuario,
            ),
        )
        pl.addWidget(self.tabla_usuarios, stretch=1)

    def _pestana_empresa(self):
        pestana = QWidget()
        pl = QVBoxLayout(pestana)
        pl.setContentsMargins(0, 0, 0, 0)
        pl.setSpacing(0)
        self.notebook.addTab(pestana, "🏢  Empresa")

        # En una ventana chica, 7 campos apilados uno debajo del otro no
        # entraban ni se podían desplazar: se veían cortados o
        # amontonados sin ninguna forma de llegar a los de más abajo.
        # Con un QScrollArea (mismo patrón que ya usa el Dashboard) el
        # contenido siempre queda accesible, sin importar el tamaño de
        # la ventana.
        scroll = QScrollArea()
        scroll.setWidgetResizable(True)
        scroll.setFrameShape(QScrollArea.NoFrame)
        pl.addWidget(scroll, stretch=1)

        cuerpo = QWidget()
        scroll.setWidget(cuerpo)
        cl = QVBoxLayout(cuerpo)
        cl.setContentsMargins(20, 20, 20, 20)
        cl.setSpacing(8)

        self._msg_empresa = MensajeEstado()
        cl.addWidget(self._msg_empresa)

        lbl_info = QLabel("Estos datos aparecen en el encabezado de todos los reportes (PDF, Excel, CSV).")
        lbl_info.setStyleSheet(f"color: {COLOR_TEXTO_SECUNDARIO};")
        lbl_info.setFont(fuente(9, cursiva=True))
        lbl_info.setWordWrap(True)
        cl.addWidget(lbl_info)

        sec = SeccionFormulario("Datos de la empresa")
        # Antes los 7 campos iban uno debajo del otro (7 filas
        # completas); en pares de a dos por fila ocupan bastante menos
        # alto, así que se aprecian mejor incluso sin tener que
        # desplazarse.
        secl = QGridLayout(sec)
        secl.setHorizontalSpacing(16)
        secl.setVerticalSpacing(4)
        secl.setColumnStretch(0, 1)
        secl.setColumnStretch(1, 1)
        cl.addWidget(sec)

        campos = [
            ("empresa_nombre", "Nombre de la empresa", True),
            ("empresa_ruc", "RUC / N° de identificación fiscal", False),
            ("empresa_direccion", "Dirección", False),
            ("empresa_ciudad", "Ciudad y País", False),
            ("empresa_telefono", "Teléfono", False),
            ("empresa_email", "Correo electrónico", False),
            ("empresa_web", "Sitio web", False),
        ]
        self._entradas_empresa = {}
        for i, (clave, etiqueta, obligatorio) in enumerate(campos):
            campo = CampoFormulario(etiqueta, obligatorio=obligatorio)
            secl.addWidget(campo, i // 2, i % 2)
            self._entradas_empresa[clave] = campo

        lbl_nota = QLabel("* Campo obligatorio")
        lbl_nota.setStyleSheet(f"color: {COLOR_TEXTO_SECUNDARIO};")
        lbl_nota.setFont(fuente(8, cursiva=True))
        cl.addWidget(lbl_nota)
        cl.addSpacing(4)

        # Sección "ADMINISTRACIÓN" del reporte de bugs: los campos se
        # podían editar directamente, sin ningún aviso ni confirmación
        # — un descuido de teclado bastaba para cambiar el nombre de la
        # empresa que sale en TODOS los reportes. Ahora arrancan
        # bloqueados (solo lectura) y hace falta pulsar "Editar" a
        # propósito para poder modificarlos.
        fila_botones = QHBoxLayout()
        self.btn_editar_empresa = QPushButton("✏  Editar datos")
        poner_clase(self.btn_editar_empresa, "secundario")
        self.btn_editar_empresa.clicked.connect(self._activar_edicion_empresa)
        fila_botones.addWidget(self.btn_editar_empresa)

        self.btn_cancelar_empresa = QPushButton("Cancelar")
        poner_clase(self.btn_cancelar_empresa, "secundario")
        self.btn_cancelar_empresa.clicked.connect(self._cancelar_edicion_empresa)
        self.btn_cancelar_empresa.setVisible(False)
        fila_botones.addWidget(self.btn_cancelar_empresa)

        self.btn_guardar_empresa = QPushButton("💾  Guardar datos de la empresa")
        self.btn_guardar_empresa.clicked.connect(self._guardar_empresa)
        self.btn_guardar_empresa.setVisible(False)
        fila_botones.addWidget(self.btn_guardar_empresa)
        fila_botones.addStretch()
        cl.addLayout(fila_botones)
        cl.addStretch()

        conectar_boton_a_validez(self.btn_guardar_empresa, list(self._entradas_empresa.values()))
        self._bloquear_campos_empresa(True)
        self._cargar_datos_empresa()

    def _bloquear_campos_empresa(self, bloqueado: bool):
        for campo in self._entradas_empresa.values():
            campo.widget.setReadOnly(bloqueado)
            campo.widget.setStyleSheet(
                f"background-color: {COLOR_CAMPO_DESHABILITADO if bloqueado else 'white'}; "
                f"color: {COLOR_TEXTO_SECUNDARIO if bloqueado else COLOR_TEXTO};"
            )
        self.btn_editar_empresa.setVisible(bloqueado)
        self.btn_cancelar_empresa.setVisible(not bloqueado)
        self.btn_guardar_empresa.setVisible(not bloqueado)

    def _activar_edicion_empresa(self):
        self._bloquear_campos_empresa(False)
        self._msg_empresa.mostrar(
            "Modo edición activado — recuerda guardar los cambios.", "info", 4000)

    def _cancelar_edicion_empresa(self):
        self._cargar_datos_empresa()
        self._bloquear_campos_empresa(True)
        self._msg_empresa.mostrar("Edición cancelada — no se guardó ningún cambio.", "info", 3000)

    def _cargar_datos_empresa(self):
        emp = obtener_datos_empresa()
        for clave, campo in self._entradas_empresa.items():
            campo.set(emp.get(clave, ""))

    def _guardar_empresa(self):
        campos = list(self._entradas_empresa.values())
        if not all(c.validar() for c in campos):
            return
        vals = {clave: campo.get() for clave, campo in self._entradas_empresa.items()}
        guardar_datos_empresa(
            nombre=vals["empresa_nombre"], ruc=vals["empresa_ruc"],
            direccion=vals["empresa_direccion"], telefono=vals["empresa_telefono"],
            email=vals["empresa_email"], ciudad=vals["empresa_ciudad"], web=vals["empresa_web"],
        )
        self._bloquear_campos_empresa(True)
        self._msg_empresa.mostrar(
            "Datos de la empresa guardados. El nuevo encabezado aparecerá en el próximo reporte.",
            "exito")

    def _pestana_logs(self):
        pestana = QWidget()
        pl = QVBoxLayout(pestana)
        pl.setContentsMargins(10, 10, 10, 10)
        self.notebook.addTab(pestana, "📋  Registros de Acceso")

        barra = BarraBusqueda(al_escribir=lambda t: self.tabla_logs.filtrar(t),
                               placeholder="🔎  Buscar registro...")
        pl.addWidget(barra)

        self.tabla_logs = TablaDatos(
            ["Usuario", "Acción", "Detalle", "Fecha y Hora"],
            anchos={"Usuario": 130, "Acción": 130, "Detalle": 260, "Fecha y Hora": 150},
            estado_vacio=EstadoVacio(
                "📋", "Sin registros de acceso",
                "Todavía no hay registros de acceso guardados, o el filtro no "
                "encontró coincidencias.",
            ),
        )
        pl.addWidget(self.tabla_logs, stretch=1)

    def refrescar(self):
        filas_usuarios, tags_usuarios = [], []
        for u in listar_usuarios():
            estado = formatear_estado("ACTIVO" if u.activo else "INACTIVO")
            tag = tag_para_estado("ACTIVO" if u.activo else "INACTIVO")
            filas_usuarios.append([u.id, u.usuario, u.nombre_completo, u.rol, estado])
            tags_usuarios.append(tag)
        self.tabla_usuarios.cargar_filas(filas_usuarios, tags_por_fila=tags_usuarios)

        with nueva_sesion() as db:
            logs = db.query(LogAcceso).order_by(LogAcceso.id.desc()).limit(200).all()
            nombres_por_id = {u.id: u.usuario for u in db.query(Usuario).all()}
            filas_logs = [
                [l.id, nombres_por_id.get(l.usuario_id, "—"), l.accion, l.detalle or "—",
                 str(l.fecha)[:19]]
                for l in logs
            ]
        self.tabla_logs.cargar_filas(filas_logs)

    def _abrir_nuevo_usuario(self):
        VentanaNuevoUsuario(self.window(), al_guardar=self.refrescar).exec()

    def _desactivar(self):
        fila = self.tabla_usuarios.currentRow()
        usuario_id = self.tabla_usuarios.id_seleccionado()
        if not usuario_id:
            QMessageBox.warning(self, "Aviso", "Selecciona un usuario de la lista primero.")
            return
        item_nombre = self.tabla_usuarios.item(fila, 1)
        nombre_usuario = item_nombre.text() if item_nombre else "este usuario"

        # Conteo real (no una advertencia genérica): cuántas órdenes de
        # compra registró este usuario, para que quien desactiva vea el
        # impacto real antes de confirmar. El historial se conserva
        # igual — desactivar solo bloquea el inicio de sesión.
        with nueva_sesion() as db:
            n_ordenes = db.query(OrdenCompra).filter_by(creado_por=usuario_id).count()
        detalle_ordenes = (
            f"Registró {n_ordenes} orden{'es' if n_ordenes != 1 else ''} de compra; "
            "quedarán intactas en el historial."
            if n_ordenes > 0 else
            "No tiene órdenes de compra registradas."
        )

        ok = confirmar(
            self, "Desactivar usuario",
            f"¿Deseas desactivar la cuenta de «{nombre_usuario}»?\n\n"
            f"El usuario no podrá iniciar sesión hasta que se reactive. "
            f"{detalle_ordenes}",
            texto_confirmar="Desactivar cuenta", texto_cancelar="Cancelar", peligro=True,
        )
        if not ok:
            return
        try:
            desactivar_usuario(usuario_id)
        except ErrorAutenticacion as error:
            QMessageBox.critical(self, "No se pudo desactivar", f"Ocurrió un error: {error}")
            return
        self.refrescar()

    def _reactivar(self):
        usuario_id = self.tabla_usuarios.id_seleccionado()
        if not usuario_id:
            QMessageBox.warning(self, "Aviso", "Selecciona un usuario de la lista primero.")
            return
        try:
            reactivar_usuario(usuario_id)
        except ErrorAutenticacion as error:
            QMessageBox.critical(self, "No se pudo reactivar", f"Ocurrió un error: {error}")
            return
        QMessageBox.information(self, "✓ Cuenta reactivada", "El usuario puede iniciar sesión nuevamente.")
        self.refrescar()


class VentanaNuevoUsuario(QDialog):
    def __init__(self, parent, al_guardar):
        super().__init__(parent)
        self.setWindowTitle("Crear nuevo usuario")
        self.al_guardar = al_guardar

        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(0)

        franja = QWidget()
        fondo(franja, COLOR_PRIMARIO)
        fl = QVBoxLayout(franja)
        fl.setContentsMargins(20, 12, 20, 12)
        lbl = QLabel("＋  Crear nuevo usuario")
        lbl.setStyleSheet("background: transparent; color: white;")
        lbl.setFont(fuente(13, negrita=True))
        fl.addWidget(lbl)
        layout.addWidget(franja)

        cuerpo = QVBoxLayout()
        cuerpo.setContentsMargins(20, 16, 20, 16)
        layout.addLayout(cuerpo)

        self._msg = MensajeEstado()
        cuerpo.addWidget(self._msg)

        sec = SeccionFormulario("Datos de la cuenta")
        secl = QVBoxLayout(sec)
        cuerpo.addWidget(sec)

        self.campo_usuario = CampoFormulario("Nombre de usuario (login)", obligatorio=True)
        self.campo_nombre = CampoFormulario("Nombre completo", obligatorio=True)
        self.campo_contrasena = CampoFormulario(
            "Contraseña inicial", obligatorio=True,
            validador_extra=lambda v: (
                "Debe tener al menos 4 caracteres." if len(v) < 4 else None
            ),
        )
        self.campo_contrasena.widget.setEchoMode(QLineEdit.Password)
        self.campo_rol = CampoFormulario(
            "Rol", tipo="combobox", opciones=ROLES_DISPONIBLES)
        self.campo_rol.widget.currentTextChanged.connect(self._actualizar_desc_rol)

        for campo in (self.campo_usuario, self.campo_nombre,
                      self.campo_contrasena, self.campo_rol):
            secl.addWidget(campo)

        self._lbl_rol_desc = QLabel("")
        self._lbl_rol_desc.setStyleSheet(f"color: {COLOR_TEXTO_SECUNDARIO};")
        self._lbl_rol_desc.setFont(fuente(8, cursiva=True))
        secl.addWidget(self._lbl_rol_desc)
        self._actualizar_desc_rol(self.campo_rol.get())

        lbl_nota = QLabel("* Campos obligatorios")
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
        self.btn_guardar = QPushButton("💾  Crear usuario")
        self.btn_guardar.clicked.connect(self._guardar)
        QShortcut(QKeySequence("Ctrl+S"), self).activated.connect(self.btn_guardar.click)
        fila_btn.addWidget(self.btn_guardar)
        cuerpo.addLayout(fila_btn)

        conectar_boton_a_validez(
            self.btn_guardar,
            [self.campo_usuario, self.campo_nombre, self.campo_contrasena],
        )
        centrar_ventana(self, 480, 420)

    def _actualizar_desc_rol(self, rol):
        self._lbl_rol_desc.setText(_ROL_DESCRIPCION.get(rol, ""))

    def _guardar(self):
        campos = (self.campo_usuario, self.campo_nombre, self.campo_contrasena)
        if not all(c.validar() for c in campos):
            return
        try:
            crear_usuario(usuario=self.campo_usuario.get(), nombre_completo=self.campo_nombre.get(),
                          contrasena=self.campo_contrasena.get(), rol=self.campo_rol.get())
        except ErrorAutenticacion as error:
            self._msg.mostrar(f"No se pudo crear el usuario: {error}", "error", 0)
            return
        self.al_guardar()
        self.accept()

    def keyPressEvent(self, evento):
        if evento.key() == Qt.Key_Escape:
            self.reject()
        else:
            super().keyPressEvent(evento)
