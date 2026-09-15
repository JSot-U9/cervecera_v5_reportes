"""
demanda_metrics.py
==================
Métricas de evaluación para el modelo de predicción de demanda.
"""

from __future__ import annotations

import numpy as np


def mae(y_real: np.ndarray, y_pred: np.ndarray) -> float:
    """Error Absoluto Medio."""
    return float(np.mean(np.abs(y_real - y_pred)))


def rmse(y_real: np.ndarray, y_pred: np.ndarray) -> float:
    """Raíz del Error Cuadrático Medio."""
    return float(np.sqrt(np.mean((y_real - y_pred) ** 2)))


def mape(y_real: np.ndarray, y_pred: np.ndarray, epsilon: float = 1e-8) -> float:
    """
    Error Porcentual Absoluto Medio.
    Se usa epsilon para evitar división por cero cuando la demanda real es 0.
    """
    mascara = y_real > epsilon
    if not mascara.any():
        return float("nan")
    return float(100 * np.mean(np.abs((y_real[mascara] - y_pred[mascara]) / y_real[mascara])))


def calcular_todas(y_real: np.ndarray, y_pred: np.ndarray) -> dict:
    """Devuelve un diccionario con MAE, RMSE y MAPE."""
    y_real = np.asarray(y_real, dtype=float)
    y_pred = np.clip(np.asarray(y_pred, dtype=float), 0, None)
    return {
        "mae":  round(mae(y_real, y_pred), 4),
        "rmse": round(rmse(y_real, y_pred), 4),
        "mape": round(mape(y_real, y_pred), 2),
    }
