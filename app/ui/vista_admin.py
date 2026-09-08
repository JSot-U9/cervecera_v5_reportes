"""
vista_admin.py
===============
Módulo de Administración — mejoras UX:
- Estados visuales de usuarios (🟢 Activo / ⚪ Inactivo)
- Confirmación mejorada para desactivar
- Formularios con secciones y validación inline
- Mensajes descriptivos
"""

import tkinter as tk
from tkinter import ttk, messagebox

from app.basedatos import nueva_sesion
from app.modelos import LogAcceso, Usuario
from app.logica_autenticacion import (
    listar_usuarios, crear_usuario, desactivar_usuario, reactivar_usuario, ErrorAutenticacion,
)
from app.logica_configuracion import obtener_datos_empresa, guardar_datos_empresa
from app.ui.widgets import (
    EncabezadoModulo, BarraBusqueda, TablaDatos, ajustar_ventana_a_contenido,
    centrar_ventana, SeccionFormulario, MensajeEstado, confirmar
)
from app.ui.estilos import COLOR_TEXTO_SECUNDARIO, COLOR_FONDO, COLOR_PRIMARIO, COLOR_ALERTA

ROLES_DISPONIBLES = ["ADMIN", "COMPRAS", "INVENTARIO", "PRODUCCION", "VENTAS", "COSTOS"]

_ROL_DESCRIPCION = {
    "ADMIN":      "Acceso total a todos los módulos",
    "COMPRAS":    "Módulo de compras y proveedores",
    "INVENTARIO": "Módulo de inventario y catálogo",
    "PRODUCCION": "Módulo de producción",
    "VENTAS":     "Módulo de ventas y clientes",
    "COSTOS":     "Módulo de costos (solo lectura)",
}


class VistaAdmin(ttk.Frame):
    def __init__(self, parent):
        super().__init__(parent)
        EncabezadoModulo(
            self,
            "Administración",
            "Cuentas de usuario · Configuración de la empresa · Registros de acceso",
            icono="⚙️",
        ).pack(fill="x")

        notebook = ttk.Notebook(self)
        notebook.pack(fill="both", expand=True, padx=12, pady=8)

        self._pestana_usuarios(notebook)
        self._pestana_empresa(notebook)
        self._pestana_logs(notebook)

        self.refrescar()

    def _pestana_usuarios(self, notebook):
        pestana = ttk.Frame(notebook, padding=8)
        notebook.add(pestana, text="  👤  Usuarios  ")

        barra = BarraBusqueda(pestana, al_escribir=lambda t: self.tabla_usuarios.filtrar(t),
                               placeholder="🔎  Buscar usuario...")
        barra.agregar_boton("＋  Nuevo usuario", self._abrir_nuevo_usuario)
        barra.agregar_boton("✓  Reactivar", self._reactivar,
                             estilo="Exito.TButton")
        barra.agregar_boton("✗  Desactivar", self._desactivar,
                             estilo="Peligro.TButton")
        barra.pack(fill="x", pady=(0, 8))

        contenedor = ttk.Frame(pestana)
        contenedor.pack(fill="both", expand=True)
        self.tabla_usuarios = TablaDatos(
            contenedor,
            ["Usuario (login)", "Nombre Completo", "Rol", "Estado"],
            anchos={"Usuario (login)": 140, "Nombre Completo": 200,
                    "Rol": 120, "Estado": 120},
        )
        self.tabla_usuarios.empaquetar()

    def _pestana_empresa(self, notebook):
        pestana = ttk.Frame(notebook, padding=20)
        notebook.add(pestana, text="  🏢  Empresa  ")

        self._msg_empresa = MensajeEstado(pestana)
        self._msg_empresa.pack(fill="x", pady=(0, 8))

        ttk.Label(
            pestana,
            text="Estos datos aparecen en el encabezado de todos los reportes (PDF, Excel, CSV).",
            foreground=COLOR_TEXTO_SECUNDARIO,
            font=("Segoe UI", 9, "italic"),
        ).pack(anchor="w", pady=(0, 12))

        sec = SeccionFormulario(pestana, "Datos de la empresa")
        sec.pack(fill="x", pady=(0, 12))
        sec.columnconfigure(1, weight=1)

        campos = [
            ("empresa_nombre",    "Nombre de la empresa *"),
            ("empresa_ruc",       "RUC / N° de identificación fiscal"),
            ("empresa_direccion", "Dirección"),
            ("empresa_ciudad",    "Ciudad y País"),
            ("empresa_telefono",  "Teléfono"),
            ("empresa_email",     "Correo electrónico"),
            ("empresa_web",       "Sitio web"),
        ]
        self._vars_empresa = {}
        for fila, (clave, etiqueta) in enumerate(campos, start=0):
            negrita = "*" in etiqueta
            ttk.Label(sec, text=etiqueta,
                      font=("Segoe UI", 9, "bold") if negrita else ("Segoe UI", 9)
                      ).grid(row=fila, column=0, sticky="w", padx=(0, 16), pady=4)
            var = tk.StringVar()
            ttk.Entry(sec, textvariable=var, width=46
                      ).grid(row=fila, column=1, sticky="ew", pady=4)
            self._vars_empresa[clave] = var

        ttk.Label(pestana, text="* Campo obligatorio",
                  style="CampoAuto.TLabel").pack(anchor="w", pady=(0, 10))

        ttk.Button(
            pestana, text="💾  Guardar datos de la empresa",
            command=self._guardar_empresa,
        ).pack(anchor="w")

        self._cargar_datos_empresa()

    def _cargar_datos_empresa(self):
        emp = obtener_datos_empresa()
        for clave, var in self._vars_empresa.items():
            var.set(emp.get(clave, ""))

    def _guardar_empresa(self):
        vals = {clave: var.get().strip() for clave, var in self._vars_empresa.items()}
        if not vals["empresa_nombre"]:
            self._msg_empresa.mostrar("El nombre de la empresa es obligatorio.", "error")
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
        self._msg_empresa.mostrar(
            "Datos de la empresa guardados. El nuevo encabezado aparecerá en el próximo reporte.",
            "exito")

    def _pestana_logs(self, notebook):
        pestana = ttk.Frame(notebook, padding=8)
        notebook.add(pestana, text="  📋  Registros de Acceso  ")

        barra = BarraBusqueda(pestana, al_escribir=lambda t: self.tabla_logs.filtrar(t),
                               placeholder="🔎  Buscar registro...")
        barra.pack(fill="x", pady=(0, 8))

        contenedor = ttk.Frame(pestana)
        contenedor.pack(fill="both", expand=True)
        self.tabla_logs = TablaDatos(
            contenedor,
            ["Usuario", "Acción", "Detalle", "Fecha y Hora"],
            anchos={"Usuario": 130, "Acción": 130, "Detalle": 260, "Fecha y Hora": 150},
        )
        self.tabla_logs.empaquetar()

    def refrescar(self):
        # Usuarios con estados visuales
        filas_usuarios = []
        tags_usuarios = []
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
            messagebox.showwarning("Aviso", "Selecciona un usuario de la lista primero.")
            return

        # Obtener nombre del usuario seleccionado
        sel = self.tabla_usuarios.selection()
        vals = self.tabla_usuarios.item(sel[0], "values") if sel else []
        nombre_usuario = vals[1] if len(vals) > 1 else "este usuario"

        ok = confirmar(
            self,
            titulo="Desactivar usuario",
            mensaje=f"¿Deseas desactivar la cuenta de «{nombre_usuario}»?\n\n"
                    f"El usuario no podrá iniciar sesión hasta que se reactive.",
            texto_confirmar="Desactivar cuenta",
            texto_cancelar="Cancelar",
            peligro=True,
        )
        if not ok:
            return
        try:
            desactivar_usuario(usuario_id)
        except ErrorAutenticacion as error:
            messagebox.showerror("No se pudo desactivar",
                                  f"Ocurrió un error: {error}")
            return
        self.refrescar()

    def _reactivar(self):
        usuario_id = self.tabla_usuarios.id_seleccionado()
        if not usuario_id:
            messagebox.showwarning("Aviso", "Selecciona un usuario de la lista primero.")
            return
        try:
            reactivar_usuario(usuario_id)
        except ErrorAutenticacion as error:
            messagebox.showerror("No se pudo reactivar",
                                  f"Ocurrió un error: {error}")
            return
        messagebox.showinfo("✓ Cuenta reactivada",
                             "El usuario puede iniciar sesión nuevamente.")
        self.refrescar()


# ══════════════════════════════════════════════════════════════════

class VentanaNuevoUsuario(tk.Toplevel):
    def __init__(self, parent, al_guardar):
        super().__init__(parent)
        self.title("Crear nuevo usuario")
        self.resizable(False, False)
        self.grab_set()
        self.al_guardar = al_guardar

        franja = tk.Frame(self, bg=COLOR_PRIMARIO, pady=12, padx=20)
        franja.pack(fill="x")
        tk.Label(franja, text="＋  Crear nuevo usuario",
                 bg=COLOR_PRIMARIO, fg="white",
                 font=("Segoe UI", 13, "bold")).pack(anchor="w")

        cuerpo = ttk.Frame(self, padding=(20, 16))
        cuerpo.pack(fill="both", expand=True)

        self._msg = MensajeEstado(cuerpo)
        self._msg.pack(fill="x", pady=(0, 8))

        sec = SeccionFormulario(cuerpo, "Datos de la cuenta")
        sec.pack(fill="x", pady=(0, 10))
        sec.columnconfigure(1, weight=1)

        self.var_usuario    = tk.StringVar()
        self.var_nombre     = tk.StringVar()
        self.var_contrasena = tk.StringVar()
        self.var_rol        = tk.StringVar(value=ROLES_DISPONIBLES[0])

        campos = [
            ("Nombre de usuario (login) *", self.var_usuario, None, "Para iniciar sesión"),
            ("Nombre completo *", self.var_nombre, None, "Nombre que aparece en el sistema"),
            ("Contraseña inicial *", self.var_contrasena, None, "El usuario puede cambiarla después"),
            ("Rol *", self.var_rol, ROLES_DISPONIBLES, ""),
        ]
        for i, (etiqueta, var, opciones, hint) in enumerate(campos):
            ttk.Label(sec, text=etiqueta,
                      font=("Segoe UI", 9, "bold")).grid(
                row=i, column=0, sticky="w", padx=(0, 16), pady=4)
            if opciones:
                ttk.Combobox(sec, textvariable=var, state="readonly",
                              values=opciones, width=30
                              ).grid(row=i, column=1, sticky="ew", pady=4)
            else:
                f = ttk.Frame(sec)
                f.grid(row=i, column=1, sticky="ew", pady=4)
                f.columnconfigure(0, weight=1)
                entry = ttk.Entry(f, textvariable=var, width=32,
                                   show="*" if "Contraseña" in etiqueta else "")
                entry.grid(row=0, column=0, sticky="w")
                if hint:
                    ttk.Label(f, text=hint, style="CampoAuto.TLabel"
                              ).grid(row=1, column=0, sticky="w")

        # Descripción dinámica del rol
        self._lbl_rol_desc = ttk.Label(sec, text="",
                                        foreground=COLOR_TEXTO_SECUNDARIO,
                                        font=("Segoe UI", 8, "italic"))
        self._lbl_rol_desc.grid(row=len(campos), column=1, sticky="w", pady=(0, 4))
        self.var_rol.trace_add("write", self._actualizar_desc_rol)
        self._actualizar_desc_rol()

        ttk.Label(cuerpo, text="* Campos obligatorios",
                  style="CampoAuto.TLabel").pack(anchor="w", pady=(4, 8))

        fila_btn = ttk.Frame(cuerpo)
        fila_btn.pack(fill="x")
        ttk.Button(fila_btn, text="Cancelar", style="Secundario.TButton",
                   command=self.destroy).pack(side="right", padx=(8, 0))
        ttk.Button(fila_btn, text="💾  Crear usuario",
                   command=self._guardar).pack(side="right")

        self.bind("<Escape>", lambda e: self.destroy())
        centrar_ventana(self, 460, 400)

    def _actualizar_desc_rol(self, *_):
        rol = self.var_rol.get()
        desc = _ROL_DESCRIPCION.get(rol, "")
        self._lbl_rol_desc.config(text=desc)

    def _guardar(self):
        usuario    = self.var_usuario.get().strip()
        nombre     = self.var_nombre.get().strip()
        contrasena = self.var_contrasena.get()
        if not all([usuario, nombre, contrasena]):
            self._msg.mostrar("Todos los campos son obligatorios.", "error")
            return
        if len(contrasena) < 4:
            self._msg.mostrar("La contraseña debe tener al menos 4 caracteres.", "error")
            return
        try:
            crear_usuario(
                usuario=usuario,
                nombre_completo=nombre,
                contrasena=contrasena,
                rol=self.var_rol.get(),
            )
        except ErrorAutenticacion as error:
            self._msg.mostrar(f"No se pudo crear el usuario: {error}", "error", 0)
            return
        self.al_guardar()
        self.destroy()
