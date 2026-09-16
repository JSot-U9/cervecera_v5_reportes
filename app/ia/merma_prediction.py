"""
merma_prediction.py
====================
Motor de predicción: estima el porcentaje (y la cantidad) de merma
esperada de una producción ANTES de que ocurra, para poder mostrarla
al planear una orden o antes de cerrarla — tal como lo describe la
sección 3.2 de la propuesta de IA.
"""

from __future__ import annotations

from datetime import date

import numpy as np

from app.basedatos import nueva_sesion
from app.modelos import Receta

from app.ia.merma_data import (
    obtener_dataset_ordenes,
    diagnostico_historial,
    MIN_ORDENES_BASELINE,
)
from app.ia.merma_features import construir_features_prediccion
from app.ia.merma_training import cargar_modelos, modelo_disponible, leer_metadata


def predecir_merma(receta_id: int, cantidad_planeada: float, fecha_planeada=None) -> dict:
    """
    Estima la merma esperada para una nueva orden de producción.

    Parámetros
    ----------
    receta_id         : receta que se va a producir.
    cantidad_planeada : cantidad planeada (mismas unidades que la receta).
    fecha_planeada    : fecha estimada de la producción (por defecto hoy).

    Retorna
    -------
    dict con claves:
      exito (bool), mensaje,
      merma_pct_esperada (float, 0-100), merma_cantidad_esperada (float),
      rendimiento_esperado (float),
      merma_promedio_historica_receta (float, 0-100),
      alerta_sobre_historico (bool),
      usando_ml (bool), advertencia (str)
    """
    fecha_planeada = fecha_planeada or date.today()

    diag_receta = diagnostico_historial(receta_id)
    diag_global = diagnostico_historial(None)

    if diag_global["ordenes_totales"] < MIN_ORDENES_BASELINE:
        return {
            "exito": False,
            "mensaje": (
                "Aún no hay suficientes órdenes de producción completadas en el "
                "sistema para estimar la merma esperada."
            ),
        }

    df_receta = obtener_dataset_ordenes(receta_id)
    df_global = obtener_dataset_ordenes()

    usar_ml = diag_global["suficiente_ml"] and modelo_disponible()
    metadata = leer_metadata() if usar_ml else {}
    usando_ml = False

    if usar_ml:
        try:
            modelo_xgb, _ = cargar_modelos()
            X_pred = construir_features_prediccion(
                receta_id, cantidad_planeada, fecha_planeada, df_receta, df_global,
            )
            merma_pct = float(modelo_xgb.predict(X_pred)[0])
            usando_ml = True
        except Exception:
            usar_ml = False

    if not usar_ml:
        # Baseline: promedio histórico de la receta (o global si es nueva)
        if len(df_receta) > 0:
            merma_pct = float(df_receta["merma_pct"].mean())
        elif len(df_global) > 0:
            merma_pct = float(df_global["merma_pct"].mean())
        else:
            merma_pct = 0.0

    merma_pct = max(0.0, min(1.0, merma_pct))
    merma_cantidad_esperada = round(cantidad_planeada * merma_pct, 2)
    rendimiento_esperado = round(cantidad_planeada - merma_cantidad_esperada, 2)

    merma_promedio_historica_receta = (
        round(float(df_receta["merma_pct"].mean()) * 100, 2) if len(df_receta) > 0 else None
    )

    # Alerta: la predicción supera claramente el comportamiento histórico de la receta
    alerta_sobre_historico = False
    if merma_promedio_historica_receta is not None:
        alerta_sobre_historico = (merma_pct * 100) > (merma_promedio_historica_receta * 1.25 + 1.0)

    advertencia = ""
    if not diag_global["suficiente_ml"]:
        advertencia = (
            "Historial global limitado: la estimación se basa en el promedio "
            "histórico de la receta, no en el modelo de IA."
        )
    elif len(df_receta) == 0:
        advertencia = (
            "Esta receta no tiene producciones previas: se usa el promedio "
            "histórico general de merma del sistema."
        )

    return {
        "exito": True,
        "mensaje": advertencia,
        "merma_pct_esperada": round(merma_pct * 100, 2),
        "merma_cantidad_esperada": merma_cantidad_esperada,
        "rendimiento_esperado": rendimiento_esperado,
        "merma_promedio_historica_receta": merma_promedio_historica_receta,
        "alerta_sobre_historico": alerta_sobre_historico,
        "usando_ml": usando_ml,
        "advertencia": advertencia,
        "metadata": metadata,
    }


def listar_recetas_para_prediccion() -> list[dict]:
    """
    Todas las recetas activas (tengan o no historial todavía), para
    poblar el selector de la UI — a diferencia de
    merma_data.listar_recetas_con_historial(), que solo devuelve las
    que ya tienen producciones completadas.
    """
    with nueva_sesion() as db:
        recetas = db.query(Receta).filter_by(activa=True).all()
        return [
            {
                "id": r.id,
                "nombre": r.producto_terminado.nombre if r.producto_terminado else f"Receta {r.id}",
                "rendimiento": r.rendimiento,
                "unidad": r.unidad_rendimiento or "L",
            }
            for r in recetas
        ]
