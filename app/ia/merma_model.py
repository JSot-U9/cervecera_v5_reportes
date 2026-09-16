"""
merma_model.py
==============
Definición de los modelos de predicción de merma:
  - BaselinePromedioReceta : usa el promedio histórico de merma de
                             la receta (o el global, si la receta es
                             nueva). No requiere entrenamiento por
                             gradiente, es el "piso" de comparación.
  - ModeloXGBoostMerma     : XGBoost Regressor con las features de
                             merma_features.py.

Ambos exponen la misma interfaz: fit(X, y) / predict(X), igual que
demanda_model.py, para que merma_training.py pueda reutilizar el
mismo patrón de entrenamiento/evaluación.
"""

from __future__ import annotations

import numpy as np
import pandas as pd

from app.ia.merma_features import COLUMNAS_FEATURES


class BaselinePromedioReceta:
    """
    Modelo de referencia: predice el porcentaje de merma promedio
    histórico de cada receta (columna ya calculada en las features).
    Si la receta no tiene historial, usa el promedio global.
    """

    def __init__(self):
        self._media_global: float = 0.0

    def fit(self, X: pd.DataFrame, y: np.ndarray) -> "BaselinePromedioReceta":
        self._media_global = float(np.mean(y)) if len(y) > 0 else 0.0
        return self

    def predict(self, X: pd.DataFrame) -> np.ndarray:
        valores = X["merma_promedio_historica_receta"].fillna(self._media_global).values
        # Si la receta no tenía historial (valor 0.0 exacto Y también
        # el promedio global es 0), no hay nada mejor que ofrecer que
        # el propio promedio global calculado en el entrenamiento.
        valores = np.where(valores == 0.0, self._media_global, valores)
        return np.clip(valores.astype(float), 0.0, 1.0)


class ModeloXGBoostMerma:
    """Envoltorio sobre XGBRegressor con las features de merma_features.py."""

    def __init__(self, **kwargs):
        from xgboost import XGBRegressor

        params = {
            "n_estimators": 200,
            "max_depth": 3,
            "learning_rate": 0.05,
            "subsample": 0.85,
            "colsample_bytree": 0.85,
            "random_state": 42,
            "n_jobs": -1,
            "verbosity": 0,
        }
        params.update(kwargs)
        self._modelo = XGBRegressor(**params)

    def fit(self, X: pd.DataFrame, y: np.ndarray) -> "ModeloXGBoostMerma":
        self._modelo.fit(X[COLUMNAS_FEATURES], y)
        return self

    def predict(self, X: pd.DataFrame) -> np.ndarray:
        preds = self._modelo.predict(X[COLUMNAS_FEATURES])
        return np.clip(preds, 0.0, 1.0).astype(float)

    @property
    def feature_importances(self) -> dict:
        imp = self._modelo.feature_importances_
        return dict(zip(COLUMNAS_FEATURES, [round(float(v), 4) for v in imp]))
