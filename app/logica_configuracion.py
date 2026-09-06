"""
logica_configuracion.py
========================
Funciones muy simples para leer y guardar "parámetros" sueltos del
sistema (tabla ParametroSistema) — por ejemplo, el capital inicial
con el que arrancó el negocio.

Todo se guarda como texto; estas funciones se encargan de convertir
a número cuando hace falta (ver obtener_parametro_numerico).

También vive aquí todo lo relacionado a los DATOS DE LA EMPRESA
(nombre, RUC, dirección, etc.). Estos datos se guardan como parámetros
con prefijo "empresa_" y se usan en los reportes (PDF, Excel) y en
el título de la ventana principal.
"""

from app.basedatos import nueva_sesion
from app.modelos import ParametroSistema


# ── Valores por defecto que se usan si el parámetro todavía no existe ──────
# Esto evita que los reportes aparezcan vacíos la primera vez que se
# ejecuta el programa antes de que el admin haya configurado la empresa.
EMPRESA_DEFAULTS = {
    "empresa_nombre":    "Mi Empresa S.A.C.",
    "empresa_ruc":       "20000000000",
    "empresa_direccion": "Av. Principal 100, Ciudad",
    "empresa_telefono":  "+51 000 000000",
    "empresa_email":     "contacto@miempresa.pe",
    "empresa_ciudad":    "Ciudad, País",
    "empresa_web":       "www.miempresa.pe",
}


def obtener_parametro(clave: str, valor_por_defecto: str = "") -> str:
    with nueva_sesion() as db:
        parametro = db.query(ParametroSistema).filter_by(clave=clave).first()
        return parametro.valor if parametro else valor_por_defecto


def obtener_parametro_numerico(clave: str, valor_por_defecto: float = 0.0) -> float:
    texto = obtener_parametro(clave, str(valor_por_defecto))
    try:
        return float(texto)
    except ValueError:
        return valor_por_defecto


def establecer_parametro(clave: str, valor: str):
    """Crea el parámetro si no existe, o actualiza su valor si ya existía."""
    with nueva_sesion() as db:
        parametro = db.query(ParametroSistema).filter_by(clave=clave).first()
        if parametro:
            parametro.valor = valor
        else:
            db.add(ParametroSistema(clave=clave, valor=valor))
        db.commit()


# ── Datos de la empresa ─────────────────────────────────────────────────────

def obtener_datos_empresa() -> dict:
    """
    Devuelve todos los datos de la empresa como un diccionario.
    Si algún campo no está en la base de datos, usa el valor por defecto
    de EMPRESA_DEFAULTS para que los reportes siempre tengan algo que mostrar.

    Uso típico:
        emp = obtener_datos_empresa()
        print(emp["empresa_nombre"])   # → "Cervecería del Valle Sagrado"
        print(emp["empresa_ruc"])      # → "20123456789"
    """
    return {
        clave: obtener_parametro(clave, default)
        for clave, default in EMPRESA_DEFAULTS.items()
    }


def guardar_datos_empresa(nombre: str, ruc: str, direccion: str,
                           telefono: str, email: str, ciudad: str, web: str):
    """
    Guarda o actualiza todos los datos de la empresa de una sola vez.
    Se usa desde la pantalla de administración (vista_admin.py).
    """
    campos = {
        "empresa_nombre":    nombre.strip(),
        "empresa_ruc":       ruc.strip(),
        "empresa_direccion": direccion.strip(),
        "empresa_telefono":  telefono.strip(),
        "empresa_email":     email.strip(),
        "empresa_ciudad":    ciudad.strip(),
        "empresa_web":       web.strip(),
    }
    for clave, valor in campos.items():
        establecer_parametro(clave, valor)
