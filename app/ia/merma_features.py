"""
merma_features.py
==================
Ingeniería de características para el dataset de órdenes de
producción (ver merma_data.py). El objetivo es estimar el
porcentaje de merma esperado de una NUEVA producción, así que las
características se construyen de forma "expanding" (usando solo el
historial disponible HASTA antes de cada orden) para no filtrar
información futura (data leakage): la orden #5 de una receta solo
puede usar el promedio de merma de las órdenes #1 a #4.
"""

from __future__ import annotations

import pandas as pd
import numpy as np

COLUMNAS_FEATURES = [
    "receta_id",
    "cantidad_planeada",
    "mes",
    "dia_semana",
    "orden_secuencial_receta",
    "merma_promedio_historica_receta",
    "merma_desviacion_historica_receta",
    "merma_promedio_historica_global",
]

COLUMNA_OBJETIVO = "merma_pct"


def construir_features(df: pd.DataFrame) -> pd.DataFrame:
    """
    Recibe el dataset de merma_data.obtener_dataset_ordenes() (todas
    las recetas juntas, ordenado cronológicamente) y agrega las
    columnas de features, calculadas sin mirar hacia el futuro.

    Retorna
    -------
    DataFrame con todas las features + 'merma_pct'. Las primeras
    órdenes de cada receta (sin historial previo) usan el promedio
    global disponible hasta ese momento como respaldo.
    """
    df = df.copy().sort_values("fecha").reset_index(drop=True)

    df["mes"] = df["fecha"].dt.month
    df["dia_semana"] = df["fecha"].dt.dayofweek

    # Promedio histórico global "expanding" (hasta la orden anterior)
    df["merma_promedio_historica_global"] = (
        df["merma_pct"].expanding().mean().shift(1)
    )

    # Promedio y desviación histórica POR RECETA, también "expanding"
    df["merma_promedio_historica_receta"] = (
        df.groupby("receta_id")["merma_pct"]
        .apply(lambda s: s.expanding().mean().shift(1))
        .reset_index(level=0, drop=True)
    )
    df["merma_desviacion_historica_receta"] = (
        df.groupby("receta_id")["merma_pct"]
        .apply(lambda s: s.expanding().std().shift(1))
        .reset_index(level=0, drop=True)
    )
    df["orden_secuencial_receta"] = df.groupby("receta_id").cumcount() + 1

    # Relleno de respaldo para las primeras órdenes de cada receta:
    # usamos el promedio global disponible en ese punto, y si tampoco
    # hay (primerísima orden del sistema), usamos 0.0.
    df["merma_promedio_historica_receta"] = df["merma_promedio_historica_receta"].fillna(
        df["merma_promedio_historica_global"]
    ).fillna(0.0)
    df["merma_desviacion_historica_receta"] = df["merma_desviacion_historica_receta"].fillna(0.0)
    df["merma_promedio_historica_global"] = df["merma_promedio_historica_global"].fillna(0.0)

    return df


def construir_features_prediccion(
    receta_id: int,
    cantidad_planeada: float,
    fecha_planeada,
    df_historico_receta: pd.DataFrame,
    df_historico_global: pd.DataFrame,
) -> pd.DataFrame:
    """
    Construye la fila de features para UNA nueva producción que aún
    no ha ocurrido (para pedir la predicción antes de cerrar/planear
    la orden).

    Parámetros
    ----------
    receta_id              : receta de la nueva producción.
    cantidad_planeada      : cantidad que se planea producir.
    fecha_planeada         : fecha (date/datetime) de la producción.
    df_historico_receta    : dataset de merma_data filtrado a esa receta.
    df_historico_global    : dataset de merma_data con TODAS las recetas.

    Retorna
    -------
    DataFrame de 1 fila con las columnas de COLUMNAS_FEATURES.
    """
    fecha_planeada = pd.to_datetime(fecha_planeada)

    if len(df_historico_receta) > 0:
        promedio_receta = float(df_historico_receta["merma_pct"].mean())
        desviacion_receta = float(df_historico_receta["merma_pct"].std(ddof=0) or 0.0)
        orden_secuencial = len(df_historico_receta) + 1
    else:
        promedio_receta = 0.0
        desviacion_receta = 0.0
        orden_secuencial = 1

    if len(df_historico_global) > 0:
        promedio_global = float(df_historico_global["merma_pct"].mean())
    else:
        promedio_global = 0.0

    if promedio_receta == 0.0 and len(df_historico_receta) == 0:
        promedio_receta = promedio_global

    fila = {
        "receta_id": receta_id,
        "cantidad_planeada": float(cantidad_planeada),
        "mes": fecha_planeada.month,
        "dia_semana": fecha_planeada.dayofweek,
        "orden_secuencial_receta": orden_secuencial,
        "merma_promedio_historica_receta": promedio_receta,
        "merma_desviacion_historica_receta": desviacion_receta,
        "merma_promedio_historica_global": promedio_global,
    }
    return pd.DataFrame([fila])
