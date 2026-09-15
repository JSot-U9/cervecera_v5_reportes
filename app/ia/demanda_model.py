"""
demanda_model.py
================
Definición de los modelos de predicción:
  - BaselinePromedio : promedio de los últimos N días
  - ModeloXGBoost    : XGBoost Regressor con las features de demanda_features.py

Ambos exponen la misma interfaz: fit(X, y) / predict(X).
"""

from __future__ import annotations

import numpy as np
import pandas as pd

from app.ia.demanda_features import COLUMNAS_FEATURES


class BaselinePromedio:
    """
    Modelo de referencia: predice siempre el promedio de los últimos
    N días del historial de entrenamiento. No usa features.
    """

    def __init__(self, ventana: int = 7):
        self.ventana = ventana
        self._media: float = 0.0

    def fit(self, X: pd.DataFrame, y: np.ndarray) -> "BaselinePromedio":
        ultimos = y[-self.ventana:] if len(y) >= self.ventana else y
        self._media = float(np.mean(ultimos)) if len(ultimos) > 0 else 0.0
        return self

    def predict(self, X: pd.DataFrame) -> np.ndarray:
        return np.full(len(X), max(0.0, self._media))


class ModeloXGBoost:
    """
    Envoltorio sobre XGBRegressor con las características definidas
    en demanda_features.py.
    """

    def __init__(self, **kwargs):
        from xgboost import XGBRegressor

        params = {
            "n_estimators": 300,
            "max_depth": 4,
            "learning_rate": 0.05,
            "subsample": 0.8,
            "colsample_bytree": 0.8,
            "random_state": 42,
            "n_jobs": -1,
            "verbosity": 0,
        }
        params.update(kwargs)
        self._modelo = XGBRegressor(**params)

    def fit(self, X: pd.DataFrame, y: np.ndarray) -> "ModeloXGBoost":
        self._modelo.fit(X[COLUMNAS_FEATURES], y)
        return self

    def predict(self, X: pd.DataFrame) -> np.ndarray:
        preds = self._modelo.predict(X[COLUMNAS_FEATURES])
        return np.clip(preds, 0, None).astype(float)

    @property
    def feature_importances(self) -> dict:
        imp = self._modelo.feature_importances_
        return dict(zip(COLUMNAS_FEATURES, [round(float(v), 4) for v in imp]))
