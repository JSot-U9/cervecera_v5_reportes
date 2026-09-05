"""
basedatos.py
============
Este archivo se encarga de UNA sola cosa: conectar el programa con
la base de datos (un archivo SQLite llamado "cervecera.db").

Conceptos que usa este archivo:

- "engine"  -> es el objeto que sabe CÓMO hablar con la base de datos
               (en este caso, con un archivo SQLite).
- "Session" -> es como una "conversación" con la base de datos: abrimos
               una sesión, hacemos operaciones (agregar, leer, modificar)
               y al final confirmamos ("commit") o cancelamos ("rollback").
- "Base"    -> es la clase de la que heredan todos los modelos (las
               tablas) definidos en modelos.py. SQLAlchemy usa esto
               para saber qué clases representan tablas.

Si en el futuro se quisiera cambiar SQLite por otra base de datos
(por ejemplo MySQL o PostgreSQL), en teoría solo habría que cambiar
la variable RUTA_BASE_DATOS de abajo.
"""

from pathlib import Path
from sqlalchemy import create_engine
from sqlalchemy.orm import declarative_base, sessionmaker

# --------------------------------------------------------------------
# 1) ¿Dónde vive el archivo de la base de datos?
# --------------------------------------------------------------------
CARPETA_PROYECTO = Path(__file__).resolve().parent.parent
RUTA_BASE_DATOS = CARPETA_PROYECTO / "cervecera.db"
URL_BASE_DATOS = f"sqlite:///{RUTA_BASE_DATOS}"

# --------------------------------------------------------------------
# 2) El "engine": el traductor entre Python y SQLite
# --------------------------------------------------------------------
# check_same_thread=False es necesario porque la interfaz gráfica
# (Tkinter) y SQLite pueden convivir en un solo hilo sin problema
# en una app de escritorio simple como esta.
engine = create_engine(
    URL_BASE_DATOS,
    connect_args={"check_same_thread": False},
    echo=False,  # poner en True si algún día se quiere ver el SQL generado
)

# --------------------------------------------------------------------
# 3) Base: la clase madre de todos los modelos (tablas)
# --------------------------------------------------------------------
Base = declarative_base()

# --------------------------------------------------------------------
# 4) Fábrica de sesiones
# --------------------------------------------------------------------
# Cada vez que llamamos a SesionLocal() obtenemos una sesión nueva,
# lista para usarse. Se recomienda usarla siempre con "with", así:
#
#     with SesionLocal() as sesion:
#         sesion.add(objeto)
#         sesion.commit()
#
SesionLocal = sessionmaker(bind=engine, expire_on_commit=False)


def nueva_sesion():
    """Devuelve una sesión nueva para hablar con la base de datos."""
    return SesionLocal()


def crear_tablas():
    """
    Crea todas las tablas en el archivo cervecera.db si todavía no
    existen. Se debe llamar UNA vez al iniciar el programa (ver main.py).

    Importamos modelos.py aquí adentro (y no arriba del todo) para
    evitar problemas de "importación circular": modelos.py necesita
    la clase Base de este archivo, así que este archivo no puede
    necesitar cosas de modelos.py al principio.
    """
    import app.modelos  # noqa: F401  (solo para registrar las tablas)
    Base.metadata.create_all(engine)
