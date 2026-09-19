"""
merma_training.py
==================
Pipeline completo de entrenamiento del modelo de predicción de merma:
  1. Extrae las órdenes de producción completadas (todas las recetas)
  2. Construye features "expanding" (sin data leakage)
  3. División temporal (70/15/15)
  4. Entrena XGBoost + Baseline (promedio histórico por receta)
  5. Evalúa métricas
  6. Persiste modelo y metadata

Mismo patrón que demanda_training.py, para que el resto del proyecto
sea consistente y fácil de mantener.
"""

from __future__ import annotations

import json
import logging
from datetime import datetime
from pathlib import Path
from typing import Optional

import joblib
import numpy as np
import pandas as pd

from app.ia.merma_data import (
    obtener_dataset_ordenes,
    MIN_ORDENES_ML,
)
from app.ia.merma_features import construir_features, COLUMNAS_FEATURES, COLUMNA_OBJETIVO
from app.ia.demanda_metrics import calcular_todas  # las métricas MAE/RMSE/MAPE son genéricas
from app.ia.merma_model import ModeloXGBoostMerma, BaselinePromedioReceta
from app.ia.persistencia_modelos import cargar_xgboost_con_auto_migracion

logger = logging.getLogger(__name__)

# ── Rutas de persistencia ─────────────────────────────────────────
CARPETA_MODELOS = Path(__file__).resolve().parent.parent.parent / "models" / "merma"
RUTA_MODELO = CARPETA_MODELOS / "modelo_xgboost.pkl"
RUTA_BASELINE = CARPETA_MODELOS / "modelo_baseline.pkl"
RUTA_METADATA = CARPETA_MODELOS / "metadata.json"

CARPETA_MODELOS.mkdir(parents=True, exist_ok=True)


def dividir_temporal(df: pd.DataFrame, prop_train=0.70, prop_val=0.15):
    """Divide cronológicamente en train / val / test. Sin shuffle (evita leakage)."""
    n = len(df)
    i_train = int(n * prop_train)
    i_val = int(n * (prop_train + prop_val))
    return df.iloc[:i_train], df.iloc[i_train:i_val], df.iloc[i_val:]


def entrenar(callback_progreso=None) -> dict:
    """
    Entrena el modelo de merma con TODAS las órdenes de producción
    completadas del sistema (todas las recetas juntas — el propio
    modelo aprende el efecto de cada receta a través de la columna
    'receta_id' y del promedio histórico por receta).

    Retorna
    -------
    dict con claves: exito (bool), mensaje, metricas, metadata.
    """

    def _log(msg: str):
        logger.info(msg)
        if callback_progreso:
            callback_progreso(msg)

    _log("Extrayendo historial de órdenes de producción completadas...")
    df_raw = obtener_dataset_ordenes()

    if len(df_raw) < MIN_ORDENES_ML:
        return {
            "exito": False,
            "mensaje": (
                f"Solo hay {len(df_raw)} orden(es) de producción completada(s) en total. "
                f"Se necesitan al menos {MIN_ORDENES_ML} para entrenar el modelo de IA."
            ),
            "metricas": {},
        }

    _log(f"  {len(df_raw)} órdenes completadas encontradas.")
    df_feat = construir_features(df_raw)
    _log(f"  Dataset con features: {len(df_feat)} filas.")

    # División temporal
    train_df, val_df, test_df = dividir_temporal(df_feat)
    _log(f"  División: train={len(train_df)}, val={len(val_df)}, test={len(test_df)}")

    if len(test_df) == 0 or len(train_df) == 0:
        return {
            "exito": False,
            "mensaje": "No hay suficientes datos para dividir en entrenamiento/prueba.",
            "metricas": {},
        }

    X_train = train_df[COLUMNAS_FEATURES]
    y_train = train_df[COLUMNA_OBJETIVO].values
    X_val = val_df[COLUMNAS_FEATURES]
    y_val = val_df[COLUMNA_OBJETIVO].values
    X_test = test_df[COLUMNAS_FEATURES]
    y_test = test_df[COLUMNA_OBJETIVO].values

    _log("  Entrenando XGBoost...")
    modelo = ModeloXGBoostMerma()
    modelo.fit(X_train, y_train)

    _log("  Entrenando Baseline (promedio histórico por receta)...")
    baseline = BaselinePromedioReceta()
    baseline.fit(X_train, y_train)

    _log("  Evaluando métricas (en escala de porcentaje de merma)...")
    metricas_xgb = calcular_todas(y_test * 100, modelo.predict(X_test) * 100)
    metricas_baseline = calcular_todas(y_test * 100, baseline.predict(X_test) * 100)
    metricas_val_xgb = calcular_todas(y_val * 100, modelo.predict(X_val) * 100) if len(val_df) else {}

    _log(f"  XGBoost  — MAE={metricas_xgb['mae']:.2f} p.p.  RMSE={metricas_xgb['rmse']:.2f} p.p.")
    _log(f"  Baseline — MAE={metricas_baseline['mae']:.2f} p.p.  RMSE={metricas_baseline['rmse']:.2f} p.p.")

    _log("  Guardando modelos...")
    joblib.dump(modelo, RUTA_MODELO)
    joblib.dump(baseline, RUTA_BASELINE)

    metadata = {
        "fecha_entrenamiento": datetime.now().isoformat(),
        "recetas_incluidas": sorted(df_raw["receta_id"].unique().tolist()),
        "filas_entrenamiento": len(train_df),
        "features": COLUMNAS_FEATURES,
        "metricas_test_xgboost": metricas_xgb,
        "metricas_val_xgboost": metricas_val_xgb,
        "metricas_test_baseline": metricas_baseline,
        "fecha_datos_desde": str(df_raw["fecha"].min().date()),
        "fecha_datos_hasta": str(df_raw["fecha"].max().date()),
        "version": "1.0",
    }
    RUTA_METADATA.write_text(json.dumps(metadata, indent=2, ensure_ascii=False))
    _log("  ✓ Modelos de merma guardados correctamente.")

    return {
        "exito": True,
        "mensaje": "Entrenamiento completado.",
        "metricas": metricas_xgb,
        "metricas_baseline": metricas_baseline,
        "metadata": metadata,
    }


def leer_metadata() -> Optional[dict]:
    if not RUTA_METADATA.exists():
        return None
    try:
        return json.loads(RUTA_METADATA.read_text())
    except Exception:
        return None


def modelo_disponible() -> bool:
    return RUTA_MODELO.exists() and RUTA_METADATA.exists()


_cache_modelos: dict = {}  # {mtime_modelo: (modelo_xgb, modelo_baseline)}


def cargar_modelos():
    """Carga y devuelve (modelo_xgb, modelo_baseline) desde disco.

    Cacheado en memoria por el mismo motivo que en demanda_training.py:
    reposicion.py llama predecir_merma() (y por lo tanto cargar_modelos())
    una vez por cada receta activa, y sin caché eso implicaba releer y
    deserializar el mismo archivo del modelo desde disco repetidamente.
    """
    if not modelo_disponible():
        raise FileNotFoundError("No hay modelo de merma entrenado. Ejecuta el entrenamiento primero.")
    mtime = RUTA_MODELO.stat().st_mtime
    if mtime not in _cache_modelos:
        _cache_modelos.clear()
        _cache_modelos[mtime] = (
            cargar_xgboost_con_auto_migracion(RUTA_MODELO), joblib.load(RUTA_BASELINE)
        )
    return _cache_modelos[mtime]
