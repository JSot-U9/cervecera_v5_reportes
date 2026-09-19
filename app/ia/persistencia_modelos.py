"""persistencia_modelos.py
=========================
Utilidad compartida por demanda_training.py y merma_training.py para
cargar un modelo XGBoost persistido con joblib.

Por qué existe
--------------
Los modelos (.pkl) se entrenan y se suben al repo en un momento dado,
con la versión de xgboost instalada en ESE momento. Si la máquina que
después CARGA el modelo tiene una versión distinta de xgboost
instalada (algo normal: cada quien instala en su propio entorno
virtual), xgboost emite un UserWarning cada vez que se deserializa el
Booster, avisando que el formato viene de "una versión distinta" y
sugiriendo re-exportarlo con Booster.save_model(). No es un error: la
predicción sigue funcionando igual, pero el aviso se repite cada vez
que se abre el Centro de Inteligencia, lo cual es ruidoso y alarmante
sin necesidad.

La solución no es "silenciar y listo": la primera vez que se detecta
el aviso, se vuelve a guardar el mismo modelo (los mismos pesos, sin
reentrenar nada) con la versión de xgboost que está instalada AHORA
en esta máquina. Así el aviso sale como máximo una vez por máquina —
la siguiente carga ya no encuentra ningún desfase de versión.
"""

from __future__ import annotations

import logging
import warnings
from pathlib import Path

import joblib

logger = logging.getLogger(__name__)


def cargar_xgboost_con_auto_migracion(ruta: Path):
    """Carga un modelo (pickled con joblib) desde `ruta`.

    Si al cargarlo xgboost emite su aviso de "versión distinta a la
    que se usó para entrenar", se re-guarda el modelo en el mismo
    lugar inmediatamente después — con eso, esa máquina no vuelve a
    ver el aviso para este archivo hasta que se reentrene o se
    actualice xgboost otra vez.
    """
    with warnings.catch_warnings(record=True) as capturadas:
        warnings.simplefilter("always")
        modelo = joblib.load(ruta)

    hubo_aviso_de_version = any(
        issubclass(w.category, UserWarning)
        and ("older version of XGBoost" in str(w.message)
             or "newer version of XGBoost" in str(w.message))
        for w in capturadas
    )
    if hubo_aviso_de_version:
        try:
            joblib.dump(modelo, ruta)
            logger.info(
                "%s: re-guardado con la versión de xgboost instalada en esta "
                "máquina (se resolvió el aviso de versión para las próximas cargas).",
                ruta.name,
            )
        except Exception:
            # Si no se pudo re-guardar (permisos de archivo, disco de solo
            # lectura, etc.) no es grave: el modelo ya está cargado en
            # memoria y la predicción de esta sesión funciona igual. Solo
            # se pierde la oportunidad de dejar de ver el aviso a futuro.
            logger.debug("No se pudo re-guardar %s tras la auto-migración.", ruta.name)

    return modelo
