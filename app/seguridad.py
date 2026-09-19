"""
seguridad.py
============
Todo lo relacionado a "quién puede hacer qué" vive en este archivo:

  1) Hash de contraseñas: nunca guardamos la contraseña tal cual en
     la base de datos. Guardamos un "hash" (una huella digital que
     no se puede revertir) más una "sal" (salt) aleatoria.

  2) RBAC (Role-Based Access Control): un diccionario simple que
     dice qué rol puede ver qué módulo y qué acciones puede hacer.

Usamos SOLO la librería estándar de Python (hashlib + secrets) para
el hash de contraseñas. No es la técnica "de moda" (como Argon2 o
bcrypt), pero es una técnica real, ampliamente usada (PBKDF2, la
misma familia que usa Django por defecto) y no requiere instalar
ninguna librería extra — así el proyecto es más fácil de instalar
y de entender.
"""

import hashlib
import hmac
import secrets

# --------------------------------------------------------------------
# 1) HASH DE CONTRASEÑAS
# --------------------------------------------------------------------
# ¿Cómo funciona PBKDF2? Toma la contraseña + una "sal" aleatoria y
# la pasa muchísimas veces (aquí 200,000) por una función hash
# (SHA-256). Repetirlo tantas veces hace que probar contraseñas al
# azar ("fuerza bruta") sea muy lento para un atacante.

_ITERACIONES = 200_000


def hash_contrasena(contrasena_plana: str) -> str:
    """
    Convierte una contraseña de texto plano en un hash seguro.
    El resultado se guarda en la base de datos, JAMÁS la contraseña original.

    El formato guardado es:  "sal_en_hexadecimal$hash_en_hexadecimal"
    """
    sal = secrets.token_hex(16)  # 16 bytes aleatorios, distintos cada vez
    hash_bytes = hashlib.pbkdf2_hmac(
        "sha256", contrasena_plana.encode("utf-8"), bytes.fromhex(sal), _ITERACIONES
    )
    return f"{sal}${hash_bytes.hex()}"


def verificar_contrasena(contrasena_plana: str, hash_guardado: str) -> bool:
    """
    Comprueba si una contraseña escrita por el usuario coincide con
    el hash que tenemos guardado.
    """
    try:
        sal, hash_esperado = hash_guardado.split("$")
    except ValueError:
        return False  # formato inválido / dato corrupto

    hash_calculado = hashlib.pbkdf2_hmac(
        "sha256", contrasena_plana.encode("utf-8"), bytes.fromhex(sal), _ITERACIONES
    )
    # Usamos compare_digest en vez de "==" para evitar "timing attacks"
    # (que un atacante deduzca la contraseña midiendo cuánto tarda la comparación)
    return hmac.compare_digest(hash_calculado.hex(), hash_esperado)


# --------------------------------------------------------------------
# 2) RBAC — control de acceso por rol
# --------------------------------------------------------------------
# Qué módulos ve cada rol en el menú lateral.
MODULOS_POR_ROL = {
    "ADMIN":      {"dashboard", "compras", "inventario", "produccion", "ventas", "costos", "centro_inteligencia", "admin"},
    "COMPRAS":    {"dashboard", "compras", "centro_inteligencia"},
    "INVENTARIO": {"dashboard", "inventario"},
    "PRODUCCION": {"dashboard", "produccion", "inventario", "centro_inteligencia"},
    "VENTAS":     {"dashboard", "ventas", "centro_inteligencia"},
    "COSTOS":     {"dashboard", "costos", "centro_inteligencia"},
}

# Qué acciones puede hacer cada rol dentro de cada módulo.
# Si un rol no aparece en la lista de un módulo, no puede hacer nada ahí.
ACCIONES_POR_ROL = {
    "compras": {
        "ADMIN":   {"ver", "crear"},
        "COMPRAS": {"ver", "crear"},
    },
    "inventario": {
        "ADMIN":      {"ver", "entrada", "salida", "ajuste"},
        "INVENTARIO": {"ver", "entrada", "salida", "ajuste"},
        "PRODUCCION": {"ver"},
    },
    "produccion": {
        "ADMIN":      {"ver", "crear", "iniciar", "cerrar"},
        "PRODUCCION": {"ver", "crear", "iniciar", "cerrar"},
    },
    "ventas": {
        "ADMIN":  {"ver", "crear"},
        "VENTAS": {"ver", "crear"},
    },
    "costos": {
        "ADMIN":  {"ver"},
        "COSTOS": {"ver"},
    },
    "admin": {
        "ADMIN": {"ver", "crear", "desactivar"},
    },
    # "prediccion" ya no es un módulo aparte del menú lateral (sección G
    # del reporte de bugs): la Predicción de Demanda ahora vive como una
    # pestaña más dentro de Centro de Inteligencia. Los roles que antes
    # tenían acceso a "prediccion" (VENTAS, COSTOS) ahora lo tienen aquí.
    "centro_inteligencia": {
        "ADMIN":      {"ver", "predecir", "entrenar", "generar_compra"},
        "COMPRAS":    {"ver", "predecir", "generar_compra"},
        "PRODUCCION": {"ver", "predecir"},
        "VENTAS":     {"ver", "predecir"},
        "COSTOS":     {"ver", "predecir"},
    },
}


def modulos_visibles(rol: str) -> set:
    """Devuelve el conjunto de módulos que un rol puede ver en el menú."""
    return MODULOS_POR_ROL.get(rol, {"dashboard"})


def puede(rol: str, modulo: str, accion: str) -> bool:
    """True si el rol dado puede hacer 'accion' dentro de 'modulo'."""
    return accion in ACCIONES_POR_ROL.get(modulo, {}).get(rol, set())
