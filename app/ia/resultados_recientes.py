"""
resultados_recientes.py
=======================
Memoria en proceso con el ÚLTIMO resultado calculado por cada motor de
IA (reposición, demanda, merma), para poder mostrarlo en otras
pantallas —p. ej. la pestaña «Inteligencia» del detalle de producto—
sin volver a correr el motor.

Es deliberadamente simple:
  - Vive solo mientras el programa está abierto (no toca la base de
    datos ni el disco): un resultado es una foto del momento en que se
    calculó, y por eso siempre se muestra junto a su fecha y hora.
  - Es seguro entre hilos: los cálculos pesados corren en un QThread
    (ver widgets.ejecutar_en_hilo) mientras la interfaz lee.
  - Guarda copias, no referencias: quien lee no puede alterar lo
    guardado por accidente.

Claves usadas (las escriben los propios motores, no las pantallas):
    "reposicion:<insumo_id>"  -> {"horizonte": int, "rec": dict | None}
                                 rec=None significa «se calculó y este
                                 insumo no necesita reposición».
    "demanda:<producto_id>"   -> resumen de predecir_demanda()
    "merma:<receta_id>"       -> resumen de predecir_merma()
"""

from __future__ import annotations

import copy
import threading
from datetime import datetime

_candado = threading.Lock()
_almacen: dict[str, tuple[object, datetime]] = {}


def guardar(clave: str, valor) -> None:
    """Guarda (una copia de) `valor` como el resultado más reciente de `clave`."""
    with _candado:
        _almacen[clave] = (copy.deepcopy(valor), datetime.now())


def obtener(clave: str):
    """Devuelve (valor, fecha_de_cálculo) o None si esa clave nunca se calculó."""
    with _candado:
        entrada = _almacen.get(clave)
    if entrada is None:
        return None
    valor, cuando = entrada
    return copy.deepcopy(valor), cuando


def limpiar() -> None:
    """Olvida todo lo guardado (lo usan las pruebas para arrancar limpias)."""
    with _candado:
        _almacen.clear()
