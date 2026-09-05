"""
sesion.py
=========
Guarda quién es el usuario que inició sesión AHORA MISMO, mientras
el programa está corriendo. No se guarda en la base de datos: vive
solo en la memoria del programa, y desaparece al cerrar la app.

¿Por qué una clase con una sola instancia global (un "singleton")?
Porque muchas pantallas necesitan saber "¿quién soy y qué rol tengo?"
y sería incómodo pasar esa información de función en función. Con
este objeto global, cualquier archivo puede hacer:

    from app.sesion import sesion_actual
    print(sesion_actual.nombre_completo)
"""


class Sesion:
    def __init__(self):
        self.usuario_id = None
        self.usuario = None
        self.nombre_completo = None
        self.rol = None

    @property
    def hay_sesion_activa(self) -> bool:
        return self.usuario_id is not None

    def iniciar(self, usuario_id: int, usuario: str, nombre_completo: str, rol: str):
        self.usuario_id = usuario_id
        self.usuario = usuario
        self.nombre_completo = nombre_completo
        self.rol = rol

    def cerrar(self):
        self.usuario_id = None
        self.usuario = None
        self.nombre_completo = None
        self.rol = None


# Instancia única, compartida por todo el programa.
sesion_actual = Sesion()
