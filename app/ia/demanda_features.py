"""
demanda_features.py
===================
Ingeniería de características para la serie temporal de ventas.
Genera variables temporales, lags y ventanas móviles sin filtración
de datos futura (data leakage).
"""

from __future__ import annotations

import pandas as pd
import numpy as np


# Columnas de características que produce este módulo
COLUMNAS_FEATURES = [
    "dia_semana",
    "dia_mes",
    "mes",
    "semana_anio",
    "es_fin_semana",
    "lag_1",
    "lag_7",
    "lag_14",
    "lag_28",
    "media_7",
    "media_14",
    "media_28",
    "std_7",
]

COLUMNA_OBJETIVO = "cantidad"


def construir_features(df: pd.DataFrame) -> pd.DataFrame:
    """
    Recibe un DataFrame con columnas [fecha, cantidad] (ordenado
    cronológicamente) y devuelve un DataFrame enriquecido con todas
    las características.  Las filas con NaN en lags críticos se
    eliminan para no entrenar con datos incompletos.

    Parámetros
    ----------
    df : DataFrame con columnas fecha (date) y cantidad (float).

    Retorna
    -------
    DataFrame con todas las features + columna 'cantidad'.
    """
    df = df.copy().sort_values("fecha").reset_index(drop=True)
    df["fecha"] = pd.to_datetime(df["fecha"])

    # ── Variables temporales ──────────────────────────────────────
    df["dia_semana"]  = df["fecha"].dt.dayofweek          # 0=lunes … 6=domingo
    df["dia_mes"]     = df["fecha"].dt.day
    df["mes"]         = df["fecha"].dt.month
    df["semana_anio"] = df["fecha"].dt.isocalendar().week.astype(int)
    df["es_fin_semana"] = (df["dia_semana"] >= 5).astype(int)

    # ── Lags (rezagos) ────────────────────────────────────────────
    for lag in [1, 7, 14, 28]:
        df[f"lag_{lag}"] = df["cantidad"].shift(lag)

    # ── Ventanas móviles (hacia atrás, sin leakage) ───────────────
    for ventana in [7, 14, 28]:
        df[f"media_{ventana}"] = (
            df["cantidad"].shift(1).rolling(window=ventana, min_periods=1).mean()
        )
    df["std_7"] = (
        df["cantidad"].shift(1).rolling(window=7, min_periods=2).std().fillna(0.0)
    )

    # Eliminar filas donde los lags más importantes son NaN
    df = df.dropna(subset=["lag_1", "lag_7"]).reset_index(drop=True)
    return df


def construir_features_futuro(
    df_historico: pd.DataFrame,
    horizonte: int,
) -> pd.DataFrame:
    """
    Genera las características para los 'horizonte' días futuros.
    Usa un enfoque recursivo: las predicciones anteriores alimentan
    los lags de los días siguientes.

    Parámetros
    ----------
    df_historico : DataFrame [fecha, cantidad] con historia completa.
    horizonte    : número de días a predecir.

    Retorna
    -------
    DataFrame con las features para cada día futuro (sin 'cantidad').
    """
    df_hist = df_historico.copy().sort_values("fecha").reset_index(drop=True)
    df_hist["fecha"] = pd.to_datetime(df_hist["fecha"])

    ultima_fecha = df_hist["fecha"].max()

    # Trabajamos con una serie extendida: historia real + placeholders
    serie = df_hist["cantidad"].tolist()
    fechas = df_hist["fecha"].tolist()

    filas_futuro = []
    for i in range(1, horizonte + 1):
        nueva_fecha = ultima_fecha + pd.Timedelta(days=i)
        fechas.append(nueva_fecha)
        # Placeholder 0 — se reemplazará con la predicción del modelo
        serie.append(0.0)

        n = len(serie) - 1  # índice del día a predecir

        def _lag(k):
            idx = n - k
            return serie[idx] if idx >= 0 else 0.0

        def _media(ventana):
            start = max(0, n - ventana)
            vals = serie[start:n]
            return float(np.mean(vals)) if vals else 0.0

        def _std(ventana):
            start = max(0, n - ventana)
            vals = serie[start:n]
            return float(np.std(vals)) if len(vals) > 1 else 0.0

        fila = {
            "fecha": nueva_fecha,
            "dia_semana":   nueva_fecha.dayofweek,
            "dia_mes":      nueva_fecha.day,
            "mes":          nueva_fecha.month,
            "semana_anio":  nueva_fecha.isocalendar()[1],
            "es_fin_semana": int(nueva_fecha.dayofweek >= 5),
            "lag_1":  _lag(1),
            "lag_7":  _lag(7),
            "lag_14": _lag(14),
            "lag_28": _lag(28),
            "media_7":  _media(7),
            "media_14": _media(14),
            "media_28": _media(28),
            "std_7":    _std(7),
        }
        filas_futuro.append(fila)

    df_futuro = pd.DataFrame(filas_futuro)
    return df_futuro


def actualizar_predicciones_en_serie(
    df_futuro: pd.DataFrame,
    predicciones: list[float],
) -> pd.DataFrame:
    """
    Devuelve el df_futuro con una columna 'pred_cantidad' añadida.
    """
    df = df_futuro.copy()
    df["pred_cantidad"] = predicciones
    return df
