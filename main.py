"""
main.py
=======
Punto de entrada del programa. Ejecutar con:

    python main.py

Qué hace, en orden:
  1. Crea las tablas de la base de datos si todavía no existen.
  2. Carga datos de ejemplo (usuarios, productos, etc.) la primera vez.
  3. Muestra la ventana de login.
  4. Si el login fue exitoso, muestra la ventana principal.
  5. Si el usuario cierra sesión (en vez de cerrar la app), vuelve
     a mostrar el login, para poder entrar con otro usuario sin
     tener que reiniciar el programa.
"""

from app.basedatos import crear_tablas
from app.datos_iniciales import cargar_datos_iniciales
from app.ui.login import VentanaLogin
from app.ui.ventana_principal import VentanaPrincipal


def main():
    crear_tablas()
    cargar_datos_iniciales()

    while True:
        ventana_login = VentanaLogin()
        ventana_login.mainloop()

        if not ventana_login.acepto:
            break  # el usuario cerró la ventana de login sin entrar

        ventana_principal = VentanaPrincipal()
        ventana_principal.mainloop()

        if not ventana_principal.quiere_reiniciar_login:
            break  # se cerró la ventana principal directamente (salir del programa)
        # si quiere_reiniciar_login es True, el bucle vuelve a mostrar el login


if __name__ == "__main__":
    main()
