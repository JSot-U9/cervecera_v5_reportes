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
    predictor=None,
) -> pd.DataFrame:
    """
    Genera las características para los 'horizonte' días futuros usando
    un enfoque estrictamente recursivo: la predicción de cada día se
    retroalimenta en la serie antes de construir las features del día
    siguiente, evitando así que los lags queden en 0.

    Parámetros
    ----------
    df_historico : DataFrame [fecha, cantidad] con historia completa.
    horizonte    : número de días a predecir.
    predictor    : callable opcional con firma ``f(fila: pd.DataFrame) -> float``
                   que recibe un DataFrame de una fila con COLUMNAS_FEATURES y
                   devuelve la predicción para ese día.  Si se pasa, la columna
                   'pred_cantidad' se incluye en el resultado y la serie se
                   retroalimenta con el valor devuelto (recortado a ≥ 0).
                   Si es None, la serie se rellena con NaN (útil solo para
                   construir las features del primer día, como hace
                   features_de_un_dia).

    Retorna
    -------
    DataFrame con las features para cada día futuro + columna opcional
    'pred_cantidad' si se proporcionó predictor.
    """
    df_hist = df_historico.copy().sort_values("fecha").reset_index(drop=True)
    df_hist["fecha"] = pd.to_datetime(df_hist["fecha"])

    ultima_fecha = df_hist["fecha"].max()
    # serie acumula historia real + predicciones (o NaN) para retroalimentar lags
    serie = df_hist["cantidad"].tolist()

    filas_futuro = []
    for i in range(1, horizonte + 1):
        nueva_fecha = ultima_fecha + pd.Timedelta(days=i)
        n = len(serie)  # índice del nuevo día (todavía no está en serie)

        def _lag(k, _n=n, _s=serie):
            idx = _n - k
            if idx < 0:
                return np.nan
            v = _s[idx]
            return float(v) if v is not None else np.nan

        def _media(ventana, _n=n, _s=serie):
            start = max(0, _n - ventana)
            vals = [v for v in _s[start:_n] if v is not None]
            return float(np.mean(vals)) if vals else np.nan

        def _std(ventana, _n=n, _s=serie):
            start = max(0, _n - ventana)
            vals = [v for v in _s[start:_n] if v is not None]
            # ddof=1 (desviación muestral) a propósito: pandas
            # Series.rolling().std() —usado en construir_features()
            # para entrenar— usa ddof=1 por defecto. np.std() por
            # defecto usa ddof=0 (poblacional), lo que producía un
            # train/serve skew silencioso en std_7 (la predicción
            # usaba una fórmula distinta a la del entrenamiento).
            return float(np.std(vals, ddof=1)) if len(vals) > 1 else 0.0

        fila = {
            "fecha":         nueva_fecha,
            "dia_semana":    nueva_fecha.dayofweek,
            "dia_mes":       nueva_fecha.day,
            "mes":           nueva_fecha.month,
            "semana_anio":   nueva_fecha.isocalendar()[1],
            "es_fin_semana": int(nueva_fecha.dayofweek >= 5),
            "lag_1":   _lag(1),
            "lag_7":   _lag(7),
            "lag_14":  _lag(14),
            "lag_28":  _lag(28),
            "media_7":   _media(7),
            "media_14":  _media(14),
            "media_28":  _media(28),
            "std_7":     _std(7),
        }

        if predictor is not None:
            fila_df = pd.DataFrame([fila])
            pred = max(0.0, float(predictor(fila_df[COLUMNAS_FEATURES])))
            fila["pred_cantidad"] = pred
            serie.append(pred)          # ← retroalimentación correcta
        else:
            serie.append(None)

        filas_futuro.append(fila)

    return pd.DataFrame(filas_futuro)


def features_de_un_dia(
    serie_cantidades: list,
    fecha: pd.Timestamp,
) -> pd.Series:
    """
    Construye las features para un único día futuro dado el historial
    como lista de cantidades y la fecha objetivo.

    Útil para pruebas de consistencia train/serve: permite comparar la
    fila que genera el pronóstico con la que habría generado
    construir_features() al entrenar con ese día ya conocido.

    Devuelve una pd.Series indexada por COLUMNAS_FEATURES (con NaN donde
    el historial es demasiado corto, igual que construir_features).
    """
    inicio = fecha - pd.Timedelta(days=len(serie_cantidades))
    df_hist = pd.DataFrame({
        "fecha":    pd.date_range(inicio, periods=len(serie_cantidades), freq="D"),
        "cantidad": [float(v) for v in serie_cantidades],
    })
    df_futuro = construir_features_futuro(df_hist, horizonte=1)
    return df_futuro.iloc[0][COLUMNAS_FEATURES]


def actualizar_predicciones_en_serie(
    df_futuro: pd.DataFrame,
    predicciones: list[float],
) -> pd.DataFrame:
    """
    Devuelve el df_futuro con una columna 'pred_cantidad' añadida.
    (Conservado por compatibilidad; el flujo recursivo ya lo incluye
    internamente en construir_features_futuro cuando se pasa predictor.)
    """
    df = df_futuro.copy()
    df["pred_cantidad"] = predicciones
    return df
