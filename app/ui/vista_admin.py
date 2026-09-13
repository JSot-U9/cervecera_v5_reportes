"""vista_admin.py (PySide6)
============================
Cuentas de usuario · Configuración de la empresa · Registros de acceso.
"""

from PySide6.QtCore import Qt
from PySide6.QtWidgets import (
    QWidget, QDialog, QVBoxLayout, QHBoxLayout, QGridLayout, QLabel,
    QLineEdit, QComboBox, QPushButton, QTabWidget, QMessageBox,
)

from app.basedatos import nueva_sesion
from app.modelos import LogAcceso, Usuario
from app.logica_autenticacion import (
    listar_usuarios, crear_usuario, desactivar_usuario, reactivar_usuario, ErrorAutenticacion,
)
from app.logica_configuracion import obtener_datos_empresa, guardar_datos_empresa
from app.ui.widgets import (
    EncabezadoModulo, BarraBusqueda, TablaDatos, SeccionFormulario, MensajeEstado,
    centrar_ventana, confirmar,
)
from app.ui.estilos import COLOR_TEXTO_SECUNDARIO, COLOR_PRIMARIO, fuente, poner_clase, fondo

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

        self.refrescar()

    def _pestana_usuarios(self):
        pestana = QWidget()
        pl = QVBoxLayout(pestana)
        pl.setContentsMargins(10, 10, 10, 10)
        self.notebook.addTab(pestana, "👤  Usuarios")

        barra = BarraBusqueda(al_escribir=lambda t: self.tabla_usuarios.filtrar(t),
                               placeholder="🔎  Buscar usuario...")
        barra.agregar_boton("＋  Nuevo usuario", self._abrir_nuevo_usuario)
        barra.agregar_boton("✓  Reactivar", self._reactivar, estilo="exito")
        barra.agregar_boton("✗  Desactivar", self._desactivar, estilo="peligro")
        pl.addWidget(barra)

        self.tabla_usuarios = TablaDatos(
            ["Usuario (login)", "Nombre Completo", "Rol", "Estado"],
            anchos={"Usuario (login)": 140, "Nombre Completo": 200, "Rol": 120, "Estado": 120},
        )
        pl.addWidget(self.tabla_usuarios, stretch=1)

    def _pestana_empresa(self):
        pestana = QWidget()
        pl = QVBoxLayout(pestana)
        pl.setContentsMargins(20, 20, 20, 20)
        self.notebook.addTab(pestana, "🏢  Empresa")

        self._msg_empresa = MensajeEstado()
        pl.addWidget(self._msg_empresa)

        lbl_info = QLabel("Estos datos aparecen en el encabezado de todos los reportes (PDF, Excel, CSV).")
        lbl_info.setStyleSheet(f"color: {COLOR_TEXTO_SECUNDARIO};")
        lbl_info.setFont(fuente(9, cursiva=True))
        pl.addWidget(lbl_info)
        pl.addSpacing(8)

        sec = SeccionFormulario("Datos de la empresa")
        secl = QGridLayout(sec)
        secl.setColumnStretch(1, 1)
        pl.addWidget(sec)

        campos = [
            ("empresa_nombre", "Nombre de la empresa *"),
            ("empresa_ruc", "RUC / N° de identificación fiscal"),
            ("empresa_direccion", "Dirección"),
            ("empresa_ciudad", "Ciudad y País"),
            ("empresa_telefono", "Teléfono"),
            ("empresa_email", "Correo electrónico"),
            ("empresa_web", "Sitio web"),
        ]
        self._entradas_empresa = {}
        for fila, (clave, etiqueta) in enumerate(campos):
            lbl = QLabel(etiqueta)
            lbl.setFont(fuente(9, negrita=("*" in etiqueta)))
            secl.addWidget(lbl, fila, 0)
            entrada = QLineEdit()
            secl.addWidget(entrada, fila, 1)
            self._entradas_empresa[clave] = entrada

        lbl_nota = QLabel("* Campo obligatorio")
        lbl_nota.setStyleSheet(f"color: {COLOR_TEXTO_SECUNDARIO};")
        lbl_nota.setFont(fuente(8, cursiva=True))
        pl.addWidget(lbl_nota)
        pl.addSpacing(4)

        btn_guardar = QPushButton("💾  Guardar datos de la empresa")
        btn_guardar.clicked.connect(self._guardar_empresa)
        pl.addWidget(btn_guardar, alignment=Qt.AlignLeft)
        pl.addStretch()

        self._cargar_datos_empresa()

    def _cargar_datos_empresa(self):
        emp = obtener_datos_empresa()
        for clave, entrada in self._entradas_empresa.items():
            entrada.setText(emp.get(clave, ""))

    def _guardar_empresa(self):
        vals = {clave: entrada.text().strip() for clave, entrada in self._entradas_empresa.items()}
        if not vals["empresa_nombre"]:
            self._msg_empresa.mostrar("El nombre de la empresa es obligatorio.", "error")
            return
        guardar_datos_empresa(
            nombre=vals["empresa_nombre"], ruc=vals["empresa_ruc"],
            direccion=vals["empresa_direccion"], telefono=vals["empresa_telefono"],
            email=vals["empresa_email"], ciudad=vals["empresa_ciudad"], web=vals["empresa_web"],
        )
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
        )
        pl.addWidget(self.tabla_logs, stretch=1)

    def refrescar(self):
        filas_usuarios, tags_usuarios = [], []
        for u in listar_usuarios():
            estado = "🟢 Activo" if u.activo else "⚪ Inactivo"
            tag = "exito" if u.activo else "normal"
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

        ok = confirmar(
            self, "Desactivar usuario",
            f"¿Deseas desactivar la cuenta de «{nombre_usuario}»?\n\n"
            f"El usuario no podrá iniciar sesión hasta que se reactive.",
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
        secl = QGridLayout(sec)
        secl.setColumnStretch(1, 1)
        cuerpo.addWidget(sec)

        lbl1 = QLabel("Nombre de usuario (login) *")
        lbl1.setFont(fuente(9, negrita=True))
        secl.addWidget(lbl1, 0, 0)
        self.entrada_usuario = QLineEdit()
        secl.addWidget(self.entrada_usuario, 0, 1)

        lbl2 = QLabel("Nombre completo *")
        lbl2.setFont(fuente(9, negrita=True))
        secl.addWidget(lbl2, 1, 0)
        self.entrada_nombre = QLineEdit()
        secl.addWidget(self.entrada_nombre, 1, 1)

        lbl3 = QLabel("Contraseña inicial *")
        lbl3.setFont(fuente(9, negrita=True))
        secl.addWidget(lbl3, 2, 0)
        self.entrada_contrasena = QLineEdit()
        self.entrada_contrasena.setEchoMode(QLineEdit.Password)
        secl.addWidget(self.entrada_contrasena, 2, 1)

        lbl4 = QLabel("Rol *")
        lbl4.setFont(fuente(9, negrita=True))
        secl.addWidget(lbl4, 3, 0)
        self.combo_rol = QComboBox()
        self.combo_rol.addItems(ROLES_DISPONIBLES)
        self.combo_rol.currentTextChanged.connect(self._actualizar_desc_rol)
        secl.addWidget(self.combo_rol, 3, 1)

        self._lbl_rol_desc = QLabel("")
        self._lbl_rol_desc.setStyleSheet(f"color: {COLOR_TEXTO_SECUNDARIO};")
        self._lbl_rol_desc.setFont(fuente(8, cursiva=True))
        secl.addWidget(self._lbl_rol_desc, 4, 1)
        self._actualizar_desc_rol(self.combo_rol.currentText())

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
        btn_guardar = QPushButton("💾  Crear usuario")
        btn_guardar.clicked.connect(self._guardar)
        fila_btn.addWidget(btn_guardar)
        cuerpo.addLayout(fila_btn)

        centrar_ventana(self, 480, 420)

    def _actualizar_desc_rol(self, rol):
        self._lbl_rol_desc.setText(_ROL_DESCRIPCION.get(rol, ""))

    def _guardar(self):
        usuario = self.entrada_usuario.text().strip()
        nombre = self.entrada_nombre.text().strip()
        contrasena = self.entrada_contrasena.text()
        if not all([usuario, nombre, contrasena]):
            self._msg.mostrar("Todos los campos son obligatorios.", "error")
            return
        if len(contrasena) < 4:
            self._msg.mostrar("La contraseña debe tener al menos 4 caracteres.", "error")
            return
        try:
            crear_usuario(usuario=usuario, nombre_completo=nombre,
                          contrasena=contrasena, rol=self.combo_rol.currentText())
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
