"""main.py (PySide6)
====================
Punto de entrada del programa. Ejecutar con:

    python main.py

1. Crea las tablas de la base de datos si todavía no existen.
2. Carga datos de ejemplo la primera vez.
3. Muestra el login. Si entra, muestra la ventana principal.
4. Si cierra sesión (en vez de cerrar la app), vuelve a mostrar el
   login sin reiniciar el proceso.
"""

import sys

from PySide6.QtWidgets import QApplication

from app.basedatos import crear_tablas
from app.datos_iniciales import cargar_datos_iniciales
from app.ui.estilos import aplicar_estilos
from app.ui.login import VentanaLogin
from app.ui.ventana_principal import VentanaPrincipal


def main():
    crear_tablas()
    cargar_datos_iniciales()

    app = QApplication(sys.argv)
    aplicar_estilos(app)

    while True:
        login = VentanaLogin()
        login.exec()
        if not login.acepto:
            break

        ventana = VentanaPrincipal()
        ventana.show()
        app.exec()

        if not ventana.quiere_reiniciar_login:
            break

    sys.exit(0)


if __name__ == "__main__":
    main()
