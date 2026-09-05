"""
logica_configuracion.py
========================
Funciones muy simples para leer y guardar "parámetros" sueltos del
sistema (tabla ParametroSistema) — por ejemplo, el capital inicial
con el que arrancó el negocio.

Todo se guarda como texto; estas funciones se encargan de convertir
a número cuando hace falta (ver obtener_parametro_numerico).
"""

from app.basedatos import nueva_sesion
from app.modelos import ParametroSistema


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
