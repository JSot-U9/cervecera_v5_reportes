"""
demanda_training.py
===================
Pipeline completo de entrenamiento:
  1. Extrae datos del ERP
  2. Construye features
  3. División temporal (70/15/15)
  4. Entrena XGBoost + Baseline
  5. Evalúa métricas
  6. Persiste modelo y metadata
"""

from __future__ import annotations

import json
import logging
from datetime import datetime, date
from pathlib import Path
from typing import Optional

import joblib
import numpy as np
import pandas as pd

from app.ia.demanda_data import (
    obtener_serie_diaria,
    listar_productos_con_ventas,
    MIN_DIAS_HISTORIAL,
)
from app.ia.demanda_features import construir_features, COLUMNAS_FEATURES, COLUMNA_OBJETIVO
from app.ia.demanda_metrics import calcular_todas
from app.ia.demanda_model import ModeloXGBoost, BaselinePromedio

logger = logging.getLogger(__name__)

# ── Rutas de persistencia ─────────────────────────────────────────
CARPETA_MODELOS = Path(__file__).resolve().parent.parent.parent / "models" / "demanda"
RUTA_MODELO = CARPETA_MODELOS / "modelo_xgboost.pkl"
RUTA_BASELINE = CARPETA_MODELOS / "modelo_baseline.pkl"
RUTA_METADATA = CARPETA_MODELOS / "metadata.json"

CARPETA_MODELOS.mkdir(parents=True, exist_ok=True)


# ── División temporal ─────────────────────────────────────────────

def dividir_temporal(df: pd.DataFrame, prop_train=0.70, prop_val=0.15):
    """
    Divide el DataFrame cronológicamente en train / val / test.
    No usa shuffle para evitar data leakage.
    """
    n = len(df)
    i_train = int(n * prop_train)
    i_val = int(n * (prop_train + prop_val))
    return df.iloc[:i_train], df.iloc[i_train:i_val], df.iloc[i_val:]


# ── Pipeline principal ────────────────────────────────────────────

def entrenar(
    producto_id: Optional[int] = None,
    callback_progreso=None,
) -> dict:
    """
    Entrena el modelo para un producto específico o para todos los
    productos con ventas si producto_id es None.

    Parámetros
    ----------
    producto_id      : None => todos los productos con historial.
    callback_progreso: función(msg: str) para reportar avance en la UI.

    Retorna
    -------
    dict con claves: exito (bool), mensaje, metricas, metadata.
    """

    def _log(msg: str):
        logger.info(msg)
        if callback_progreso:
            callback_progreso(msg)

    # 1) Determinar productos a entrenar
    if producto_id is not None:
        productos = [producto_id]
    else:
        productos = [p["id"] for p in listar_productos_con_ventas()]

    if not productos:
        return {"exito": False, "mensaje": "No hay productos con ventas registradas.", "metricas": {}}

    _log(f"Iniciando entrenamiento para {len(productos)} producto(s)...")

    # 2) Construir dataset combinado
    frames = []
    for pid in productos:
        df_raw = obtener_serie_diaria(pid)
        if len(df_raw) < MIN_DIAS_HISTORIAL:
            _log(f"  · Producto {pid}: historial insuficiente, se omite.")
            continue
        df_feat = construir_features(df_raw)
        df_feat["producto_id"] = pid
        frames.append(df_feat)

    if not frames:
        return {
            "exito": False,
            "mensaje": "Ningún producto tiene suficiente historial para entrenar.",
            "metricas": {},
        }

    df_total = pd.concat(frames, ignore_index=True).sort_values("fecha")
    _log(f"  Dataset combinado: {len(df_total)} filas.")

    # 3) División temporal
    train_df, val_df, test_df = dividir_temporal(df_total)
    _log(
        f"  División: train={len(train_df)}, val={len(val_df)}, test={len(test_df)}"
    )

    X_train = train_df[COLUMNAS_FEATURES]
    y_train = train_df[COLUMNA_OBJETIVO].values
    X_val   = val_df[COLUMNAS_FEATURES]
    y_val   = val_df[COLUMNA_OBJETIVO].values
    X_test  = test_df[COLUMNAS_FEATURES]
    y_test  = test_df[COLUMNA_OBJETIVO].values

    # 4) Entrenar XGBoost
    _log("  Entrenando XGBoost...")
    modelo = ModeloXGBoost()
    modelo.fit(X_train, y_train)

    # 5) Entrenar Baseline
    _log("  Entrenando Baseline (promedio móvil 7 días)...")
    baseline = BaselinePromedio(ventana=7)
    baseline.fit(X_train, y_train)

    # 6) Evaluar en conjunto de prueba
    _log("  Evaluando métricas...")
    metricas_xgb      = calcular_todas(y_test, modelo.predict(X_test))
    metricas_baseline = calcular_todas(y_test, baseline.predict(X_test))
    metricas_val_xgb  = calcular_todas(y_val,  modelo.predict(X_val))

    _log(f"  XGBoost  — MAE={metricas_xgb['mae']:.2f}  RMSE={metricas_xgb['rmse']:.2f}")
    _log(f"  Baseline — MAE={metricas_baseline['mae']:.2f}  RMSE={metricas_baseline['rmse']:.2f}")

    # 7) Persistencia
    _log("  Guardando modelos...")
    joblib.dump(modelo, RUTA_MODELO)
    joblib.dump(baseline, RUTA_BASELINE)

    metadata = {
        "fecha_entrenamiento": datetime.now().isoformat(),
        "productos_incluidos": productos,
        "filas_entrenamiento": len(train_df),
        "features": COLUMNAS_FEATURES,
        "metricas_test_xgboost": metricas_xgb,
        "metricas_val_xgboost": metricas_val_xgb,
        "metricas_test_baseline": metricas_baseline,
        "fecha_datos_desde": str(df_total["fecha"].min().date()),
        "fecha_datos_hasta": str(df_total["fecha"].max().date()),
        "version": "1.0",
    }
    RUTA_METADATA.write_text(json.dumps(metadata, indent=2, ensure_ascii=False))
    _log("  ✓ Modelos guardados correctamente.")

    return {
        "exito": True,
        "mensaje": "Entrenamiento completado.",
        "metricas": metricas_xgb,
        "metricas_baseline": metricas_baseline,
        "metadata": metadata,
    }


# ── Lectura de metadata ───────────────────────────────────────────

def leer_metadata() -> Optional[dict]:
    """Retorna la metadata del último entrenamiento o None si no existe."""
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

    Se cachea en memoria por el resto del proceso: reposicion.py llama a
    esta función una vez POR CADA receta activa al calcular las
    recomendaciones de reposición, y sin caché eso significaba volver a
    deserializar el mismo archivo XGBoost desde disco una y otra vez
    (el motivo real de la demora al abrir esa pantalla). La clave es la
    fecha de modificación del archivo, así que si se reentrena el modelo
    (entrenar() sobreescribe RUTA_MODELO), el caché se invalida solo.
    """
    if not modelo_disponible():
        raise FileNotFoundError("No hay modelo entrenado. Ejecuta el entrenamiento primero.")
    mtime = RUTA_MODELO.stat().st_mtime
    if mtime not in _cache_modelos:
        _cache_modelos.clear()
        _cache_modelos[mtime] = (joblib.load(RUTA_MODELO), joblib.load(RUTA_BASELINE))
    return _cache_modelos[mtime]
