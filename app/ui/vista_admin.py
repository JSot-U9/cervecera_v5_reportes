"""
vista_admin.py
===============
Solo el rol ADMIN ve este módulo (ver MODULOS_POR_ROL en seguridad.py).
Permite crear usuarios nuevos, desactivar/reactivar usuarios, revisar
el historial de inicios de sesión, y configurar los datos de la empresa
que aparecen en los reportes.
"""

import tkinter as tk
from tkinter import ttk, messagebox

from app.basedatos import nueva_sesion
from app.modelos import LogAcceso, Usuario
from app.logica_autenticacion import (
    listar_usuarios, crear_usuario, desactivar_usuario, reactivar_usuario, ErrorAutenticacion,
)
from app.logica_configuracion import obtener_datos_empresa, guardar_datos_empresa
from app.ui.widgets import EncabezadoModulo, BarraBusqueda, TablaDatos, ajustar_ventana_a_contenido
from app.ui.estilos import COLOR_TEXTO_SECUNDARIO, COLOR_FONDO

ROLES_DISPONIBLES = ["ADMIN", "COMPRAS", "INVENTARIO", "PRODUCCION", "VENTAS", "COSTOS"]


class VistaAdmin(ttk.Frame):
    def __init__(self, parent):
        super().__init__(parent)
        EncabezadoModulo(
            self,
            "Administración del Sistema",
            "Usuarios, registros de acceso y configuración de la empresa",
        ).pack(fill="x")

        notebook = ttk.Notebook(self)
        notebook.pack(fill="both", expand=True, padx=12, pady=8)

        self._pestana_usuarios(notebook)
        self._pestana_empresa(notebook)
        self._pestana_logs(notebook)

        self.refrescar()

    def _pestana_usuarios(self, notebook):
        pestana = ttk.Frame(notebook, padding=8)
        notebook.add(pestana, text="Cuentas de Usuario")

        barra = BarraBusqueda(pestana, al_escribir=lambda t: self.tabla_usuarios.filtrar(t))
        barra.agregar_boton("+ Nuevo usuario", self._abrir_nuevo_usuario)
        barra.agregar_boton("Reactivar cuenta", self._reactivar).configure(style="Exito.TButton")
        barra.agregar_boton("Desactivar cuenta", self._desactivar).configure(
            style="Peligro.TButton")
        barra.pack(fill="x", pady=(0, 8))

        contenedor = ttk.Frame(pestana)
        contenedor.pack(fill="both", expand=True)
        self.tabla_usuarios = TablaDatos(
            contenedor,
            ["Nombre de Usuario (login)", "Nombre Completo", "Rol Asignado", "Estado de la Cuenta"],
        )
        self.tabla_usuarios.empaquetar()

    def _pestana_empresa(self, notebook):
        """
        Pestaña para editar los datos de la empresa que aparecen en
        todos los reportes (nombre, RUC, dirección, contacto, etc.).

        Los datos se leen y guardan en la tabla ParametroSistema usando
        las funciones de logica_configuracion.py.
        """
        pestana = ttk.Frame(notebook, padding=20)
        notebook.add(pestana, text="Empresa")

        nota = ttk.Label(
            pestana,
            text="Estos datos aparecen en el encabezado de todos los reportes (PDF, Excel, CSV).",
            foreground=COLOR_TEXTO_SECUNDARIO,
            font=("Segoe UI", 9, "italic"),
        )
        nota.grid(row=0, column=0, columnspan=2, sticky="w", pady=(0, 16))

        campos = [
            ("empresa_nombre",    "Nombre de la empresa:"),
            ("empresa_ruc",       "RUC / Nº de identificación fiscal:"),
            ("empresa_direccion", "Dirección:"),
            ("empresa_ciudad",    "Ciudad y País:"),
            ("empresa_telefono",  "Teléfono:"),
            ("empresa_email",     "Correo electrónico:"),
            ("empresa_web",       "Sitio web (opcional):"),
        ]
        self._vars_empresa = {}

        for fila, (clave, etiqueta) in enumerate(campos, start=1):
            ttk.Label(pestana, text=etiqueta, font=("Segoe UI", 9, "bold")).grid(
                row=fila, column=0, sticky="w", padx=(0, 12), pady=4,
            )
            var = tk.StringVar()
            ttk.Entry(pestana, textvariable=var, width=48).grid(
                row=fila, column=1, sticky="ew", pady=4,
            )
            self._vars_empresa[clave] = var

        pestana.columnconfigure(1, weight=1)

        ttk.Button(
            pestana, text="💾  Guardar datos de la empresa",
            command=self._guardar_empresa,
        ).grid(row=len(campos) + 1, column=0, columnspan=2, sticky="w", pady=(18, 0))

        self._cargar_datos_empresa()

    def _cargar_datos_empresa(self):
        """Carga los valores actuales de la BD en los campos del formulario."""
        emp = obtener_datos_empresa()
        for clave, var in self._vars_empresa.items():
            var.set(emp.get(clave, ""))

    def _guardar_empresa(self):
        vals = {clave: var.get().strip() for clave, var in self._vars_empresa.items()}
        if not vals["empresa_nombre"]:
            messagebox.showwarning("Aviso", "El nombre de la empresa no puede estar vacío.")
            return
        guardar_datos_empresa(
            nombre    = vals["empresa_nombre"],
            ruc       = vals["empresa_ruc"],
            direccion = vals["empresa_direccion"],
            telefono  = vals["empresa_telefono"],
            email     = vals["empresa_email"],
            ciudad    = vals["empresa_ciudad"],
            web       = vals["empresa_web"],
        )
        messagebox.showinfo(
            "Guardado",
            "Los datos de la empresa fueron guardados.\n"
            "El nuevo encabezado aparecerá en el próximo reporte que generes.",
        )

    def _pestana_logs(self, notebook):
        pestana = ttk.Frame(notebook, padding=8)
        notebook.add(pestana, text="Registros de Acceso")

        contenedor = ttk.Frame(pestana)
        contenedor.pack(fill="both", expand=True)
        self.tabla_logs = TablaDatos(
            contenedor,
            ["Usuario", "Acción Realizada", "Detalle", "Fecha y Hora"],
        )
        self.tabla_logs.empaquetar()

    def refrescar(self):
        filas_usuarios = [
            [u.id, u.usuario, u.nombre_completo, u.rol, "Activa" if u.activo else "Desactivada"]
            for u in listar_usuarios()
        ]
        self.tabla_usuarios.cargar_filas(filas_usuarios)

        with nueva_sesion() as db:
            logs = db.query(LogAcceso).order_by(LogAcceso.id.desc()).limit(200).all()
            nombres_por_id = {u.id: u.usuario for u in db.query(Usuario).all()}
            filas_logs = [
                [l.id, nombres_por_id.get(l.usuario_id, "—"),
                 l.accion, l.detalle or "—", str(l.fecha)[:19]]
                for l in logs
            ]
        self.tabla_logs.cargar_filas(filas_logs)

    def _abrir_nuevo_usuario(self):
        VentanaNuevoUsuario(self, al_guardar=self.refrescar)

    def _desactivar(self):
        usuario_id = self.tabla_usuarios.id_seleccionado()
        if not usuario_id:
            messagebox.showwarning("Aviso", "Selecciona un usuario de la lista.")
            return
        if not messagebox.askyesno("Confirmar", "¿Desactivar la cuenta de este usuario?\n"
                                    "No podrá iniciar sesión hasta que se reactive."):
            return
        try:
            desactivar_usuario(usuario_id)
        except ErrorAutenticacion as error:
            messagebox.showerror("Error", str(error))
            return
        self.refrescar()

    def _reactivar(self):
        usuario_id = self.tabla_usuarios.id_seleccionado()
        if not usuario_id:
            messagebox.showwarning("Aviso", "Selecciona un usuario de la lista.")
            return
        try:
            reactivar_usuario(usuario_id)
        except ErrorAutenticacion as error:
            messagebox.showerror("Error", str(error))
            return
        messagebox.showinfo("Cuenta reactivada", "El usuario puede iniciar sesión nuevamente.")
        self.refrescar()


class VentanaNuevoUsuario(tk.Toplevel):
    def __init__(self, parent, al_guardar):
        super().__init__(parent)
        self.title("Crear nuevo usuario del sistema")
        self.al_guardar = al_guardar

        contenedor = ttk.Frame(self, padding=16)
        contenedor.pack(fill="both", expand=True)

        self.var_usuario    = tk.StringVar()
        self.var_nombre     = tk.StringVar()
        self.var_contrasena = tk.StringVar()
        self.var_rol        = tk.StringVar(value=ROLES_DISPONIBLES[0])

        ttk.Label(contenedor, text="Nombre de usuario (para iniciar sesión):").pack(anchor="w")
        ttk.Entry(contenedor, textvariable=self.var_usuario).pack(fill="x", pady=(0, 8))

        ttk.Label(contenedor, text="Nombre completo de la persona:").pack(anchor="w")
        ttk.Entry(contenedor, textvariable=self.var_nombre).pack(fill="x", pady=(0, 8))

        ttk.Label(contenedor, text="Contraseña inicial:").pack(anchor="w")
        ttk.Entry(contenedor, textvariable=self.var_contrasena, show="*").pack(
            fill="x", pady=(0, 8))

        ttk.Label(contenedor, text="Rol (define qué módulos puede usar):").pack(anchor="w")
        ttk.Combobox(contenedor, textvariable=self.var_rol, state="readonly",
                     values=ROLES_DISPONIBLES).pack(fill="x", pady=(0, 10))

        ttk.Button(contenedor, text="Crear usuario", command=self._guardar).pack(fill="x")

        ajustar_ventana_a_contenido(self, ancho=360)

    def _guardar(self):
        if not all([self.var_usuario.get().strip(), self.var_nombre.get().strip(),
                    self.var_contrasena.get()]):
            messagebox.showwarning("Aviso", "Todos los campos son obligatorios.")
            return
        try:
            crear_usuario(
                usuario=self.var_usuario.get().strip(),
                nombre_completo=self.var_nombre.get().strip(),
                contrasena=self.var_contrasena.get(),
                rol=self.var_rol.get(),
            )
        except ErrorAutenticacion as error:
            messagebox.showerror("Error", str(error))
            return
        self.al_guardar()
        self.destroy()