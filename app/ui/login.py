"""
login.py
========
Ventana de inicio de sesión. Es una ventana "modal" (bloquea el resto
del programa hasta que el usuario entra o cierra la ventana).

Cómo se usa desde main.py:

    ventana_login = VentanaLogin()
    ventana_login.mainloop()
    if ventana_login.acepto:
        # el usuario inició sesión correctamente, continuar...
"""

import tkinter as tk
from tkinter import ttk

from app.logica_autenticacion import iniciar_sesion, ErrorAutenticacion
from app.ui.estilos import aplicar_estilos, COLOR_ALERTA
from app.ui.widgets import ajustar_ventana_a_contenido
from app.ui.logo import cargar_logo


class VentanaLogin(tk.Tk):
    def __init__(self):
        super().__init__()
        self.title("Iniciar sesión")
        aplicar_estilos(self)

        # 'acepto' es la bandera que revisa main.py para saber si se
        # debe abrir la ventana principal o cerrar el programa.
        self.acepto = False

        # Franja de color arriba, con el logo de la empresa + el nombre.
        franja = ttk.Frame(self, style="Encabezado.TFrame", padding=(30, 20))
        franja.pack(fill="x")

        self._imagen_logo = cargar_logo(self, tamano="grande")
        ttk.Label(franja, image=self._imagen_logo, style="Encabezado.TLabel").pack()
        ttk.Label(franja, text="Sistema de gestión integrada",
                  style="EncabezadoSubtitulo.TLabel").pack(pady=(2, 0))

        contenedor = ttk.Frame(self, padding=30)
        contenedor.pack(expand=True, fill="both")

        ttk.Label(contenedor, text="Usuario:", style="TLabel").pack(anchor="w")
        self.var_usuario = tk.StringVar()
        entrada_usuario = ttk.Entry(contenedor, textvariable=self.var_usuario)
        entrada_usuario.pack(fill="x", pady=(0, 10))

        ttk.Label(contenedor, text="Contraseña:", style="TLabel").pack(anchor="w")
        self.var_contrasena = tk.StringVar()
        entrada_contrasena = ttk.Entry(contenedor, textvariable=self.var_contrasena, show="*")
        entrada_contrasena.pack(fill="x", pady=(0, 6))
        entrada_contrasena.bind("<Return>", lambda evento: self._intentar_login())

        self.etiqueta_error = ttk.Label(contenedor, text="", foreground=COLOR_ALERTA)
        self.etiqueta_error.pack(pady=(0, 10))

        ttk.Button(contenedor, text="Iniciar sesión",
                   command=self._intentar_login).pack(fill="x", pady=(4, 4))
        ttk.Button(contenedor, text="Salir", style="Secundario.TButton",
                   command=self._salir).pack(fill="x")

        entrada_usuario.focus_set()
        ajustar_ventana_a_contenido(self)
        self.resizable(False, False)

    def _intentar_login(self):
        self.etiqueta_error.config(text="")
        try:
            iniciar_sesion(self.var_usuario.get().strip(), self.var_contrasena.get())
            self.acepto = True
            self.destroy()  # cierra esta ventana; el flujo continúa en main.py
        except ErrorAutenticacion as error:
            self.etiqueta_error.config(text=str(error))
            self.var_contrasena.set("")

    def _salir(self):
        self.acepto = False
        self.destroy()
