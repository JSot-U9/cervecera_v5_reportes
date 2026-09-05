"""
logica_autenticacion.py
========================
Funciones para iniciar sesión, cerrar sesión y crear usuarios.

Cada función recibe los datos que necesita, abre su propia sesión de
base de datos, hace su trabajo, y la cierra. Así cada función es
independiente y fácil de probar por separado (ver tests/test_logica.py).
"""

from app.basedatos import nueva_sesion
from app.modelos import Usuario, LogAcceso
from app.seguridad import hash_contrasena, verificar_contrasena
from app.sesion import sesion_actual


class ErrorAutenticacion(Exception):
    """Se lanza cuando el usuario o la contraseña no son correctos."""
    pass


def iniciar_sesion(usuario: str, contrasena: str) -> dict:
    """
    Verifica usuario y contraseña. Si son correctos, guarda la sesión
    activa en sesion_actual y devuelve los datos del usuario.
    Si no son correctos, lanza ErrorAutenticacion.
    """
    if not usuario or not contrasena:
        raise ErrorAutenticacion("Completa usuario y contraseña.")

    with nueva_sesion() as db:
        u = db.query(Usuario).filter_by(usuario=usuario).first()

        if not u or not u.activo:
            db.add(LogAcceso(usuario_id=None, accion="LOGIN_FAIL",
                              detalle=f"Usuario '{usuario}' no existe o está inactivo"))
            db.commit()
            raise ErrorAutenticacion("Usuario o contraseña incorrectos.")

        if not verificar_contrasena(contrasena, u.contrasena_hash):
            db.add(LogAcceso(usuario_id=u.id, accion="LOGIN_FAIL",
                              detalle="Contraseña incorrecta"))
            db.commit()
            raise ErrorAutenticacion("Usuario o contraseña incorrectos.")

        db.add(LogAcceso(usuario_id=u.id, accion="LOGIN_OK"))
        db.commit()

        datos = {
            "id": u.id,
            "usuario": u.usuario,
            "nombre_completo": u.nombre_completo,
            "rol": u.rol,
        }

    sesion_actual.iniciar(**{
        "usuario_id": datos["id"],
        "usuario": datos["usuario"],
        "nombre_completo": datos["nombre_completo"],
        "rol": datos["rol"],
    })
    return datos


def cerrar_sesion():
    """Registra el LOGOUT en el log y limpia la sesión activa."""
    if sesion_actual.hay_sesion_activa:
        with nueva_sesion() as db:
            db.add(LogAcceso(usuario_id=sesion_actual.usuario_id, accion="LOGOUT"))
            db.commit()
    sesion_actual.cerrar()


def crear_usuario(usuario: str, nombre_completo: str, contrasena: str, rol: str) -> Usuario:
    """Crea un usuario nuevo. Lanza ErrorAutenticacion si el nombre ya existe."""
    with nueva_sesion() as db:
        if db.query(Usuario).filter_by(usuario=usuario).first():
            raise ErrorAutenticacion(f"El usuario '{usuario}' ya existe.")
        u = Usuario(
            usuario=usuario,
            nombre_completo=nombre_completo,
            contrasena_hash=hash_contrasena(contrasena),
            rol=rol,
            activo=True,
        )
        db.add(u)
        db.commit()
        db.refresh(u)
        return u


def listar_usuarios():
    with nueva_sesion() as db:
        return db.query(Usuario).order_by(Usuario.id).all()


def desactivar_usuario(usuario_id: int):
    with nueva_sesion() as db:
        u = db.get(Usuario, usuario_id)
        if not u:
            raise ErrorAutenticacion("Usuario no encontrado.")
        if not u.activo:
            raise ErrorAutenticacion(f"El usuario '{u.usuario}' ya estaba desactivado.")
        u.activo = False
        db.commit()


def reactivar_usuario(usuario_id: int):
    with nueva_sesion() as db:
        u = db.get(Usuario, usuario_id)
        if not u:
            raise ErrorAutenticacion("Usuario no encontrado.")
        if u.activo:
            raise ErrorAutenticacion(f"El usuario '{u.usuario}' ya estaba activo.")
        u.activo = True
        db.commit()
