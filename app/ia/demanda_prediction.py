"""
demanda_prediction.py
=====================
Motor de predicción: usa el modelo entrenado para generar la
estimación de demanda futura para un producto y horizonte dados.
"""

from __future__ import annotations

from datetime import date, timedelta

import numpy as np
import pandas as pd

from app.ia.demanda_data import obtener_serie_diaria, diagnostico_historial, MIN_DIAS_BASELINE
from app.ia.demanda_features import construir_features_futuro, COLUMNAS_FEATURES
from app.ia.demanda_training import cargar_modelos, modelo_disponible, leer_metadata
from app.ia.demanda_metrics import calcular_todas


def predecir_demanda(producto_id: int, horizonte: int) -> dict:
    """
    Genera la predicción de demanda para los próximos `horizonte` días.

    Parámetros
    ----------
    producto_id : int
    horizonte   : 7, 14 o 30

    Retorna
    -------
    dict con claves:
      exito (bool), mensaje (str),
      fechas (list[date]), pred_cantidad (list[float]),
      demanda_total (float), promedio_diario (float),
      demanda_min (float), demanda_max (float),
      df_historico (pd.DataFrame [fecha, cantidad]),
      metricas (dict), metadata (dict),
      usando_ml (bool)
    """
    # ── Validar historial ─────────────────────────────────────────
    diag = diagnostico_historial(producto_id)
    if not diag["suficiente_baseline"]:
        return {
            "exito": False,
            "mensaje": diag["mensaje"] or (
                "No existe suficiente historial de ventas para generar "
                "una predicción confiable para este producto."
            ),
        }

    # ── Obtener historial ─────────────────────────────────────────
    df_hist = obtener_serie_diaria(producto_id)

    # ── Seleccionar modelo ────────────────────────────────────────
    usar_ml = diag["suficiente_ml"] and modelo_disponible()
    metadata = leer_metadata() if usar_ml else {}

    if usar_ml:
        try:
            modelo_xgb, _ = cargar_modelos()
            # Predictor recursivo: cada predicción alimenta los lags del día siguiente
            df_futuro = construir_features_futuro(
                df_hist, horizonte,
                predictor=lambda fila: modelo_xgb.predict(fila[COLUMNAS_FEATURES])[0],
            )
            predicciones = df_futuro["pred_cantidad"].tolist()
            usando_ml = True
        except Exception:
            # Fallback a baseline si el modelo falla
            usar_ml = False
            usando_ml = False

    if not usar_ml:
        # Baseline: promedio de los últimos 7 días
        ultimos_7 = df_hist["cantidad"].tail(7).values
        media = float(np.mean(ultimos_7)) if len(ultimos_7) > 0 else 0.0
        predicciones = [max(0.0, media)] * horizonte
        usando_ml = False

        ultima_fecha = df_hist["fecha"].iloc[-1]
        if isinstance(ultima_fecha, str):
            from datetime import datetime
            ultima_fecha = datetime.strptime(ultima_fecha, "%Y-%m-%d").date()
        elif hasattr(ultima_fecha, "date"):
            ultima_fecha = ultima_fecha.date()

        fechas = [ultima_fecha + timedelta(days=i + 1) for i in range(horizonte)]
    else:
        fechas = [row.date() if hasattr(row, "date") else row
                  for row in df_futuro["fecha"].tolist()]

    predicciones = [round(max(0.0, p), 2) for p in predicciones]

    demanda_total    = round(sum(predicciones), 2)
    promedio_diario  = round(demanda_total / horizonte, 2)
    demanda_min      = round(min(predicciones), 2)
    demanda_max      = round(max(predicciones), 2)

    # ── Métricas del modelo (del último entrenamiento) ────────────
    metricas = {}
    if metadata:
        metricas = metadata.get("metricas_test_xgboost", {})

    advertencia = ""
    if not diag["suficiente_ml"]:
        advertencia = (
            "Historial limitado: la estimación se basa en promedio móvil simple, "
            "no en el modelo de IA."
        )

    return {
        "exito": True,
        "mensaje": advertencia,
        "fechas": fechas,
        "pred_cantidad": predicciones,
        "demanda_total": demanda_total,
        "promedio_diario": promedio_diario,
        "demanda_min": demanda_min,
        "demanda_max": demanda_max,
        "df_historico": df_hist,
        "metricas": metricas,
        "metadata": metadata,
        "usando_ml": usando_ml,
        "advertencia": advertencia,
    }
