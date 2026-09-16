"""
merma_data.py
=============
Extracción y preparación de datos históricos de producción para el
módulo de predicción de merma. Consulta directamente las tablas del
ERP (OrdenProduccion + Merma + Receta) sin duplicar información.

Cada fila del dataset resultante representa UNA orden de producción
ya completada, con:
  - cuánto se planeó producir (cantidad_planeada)
  - cuánto se obtuvo realmente (cantidad_real)
  - cuánta merma se registró explícitamente (tabla Merma, puede ser
    0 si no hubo pérdidas dignas de anotar)
  - el porcentaje de merma respecto de lo planeado, que es la
    variable objetivo del modelo (merma_pct)
"""

from __future__ import annotations

from datetime import date
from typing import Optional

import pandas as pd

from app.basedatos import nueva_sesion
from app.modelos import OrdenProduccion, Merma, Receta, Producto

# Mínimo de órdenes completadas necesarias para intentar el modelo de IA
MIN_ORDENES_ML = 15
# Mínimo absoluto para un baseline (promedio histórico) con algo de sentido
MIN_ORDENES_BASELINE = 3


def listar_recetas_con_historial() -> list[dict]:
    """
    Devuelve las recetas que tienen al menos una orden de producción
    COMPLETADA, ordenadas por nombre del producto terminado.
    """
    with nueva_sesion() as db:
        filas = (
            db.query(Receta.id, Producto.nombre, Producto.unidad_medida)
            .join(Producto, Producto.id == Receta.producto_terminado_id)
            .join(OrdenProduccion, OrdenProduccion.receta_id == Receta.id)
            .filter(OrdenProduccion.estado == "COMPLETADA")
            .distinct()
            .order_by(Producto.nombre)
            .all()
        )
        return [
            {"id": f.id, "nombre": f.nombre, "unidad": f.unidad_medida or "L"}
            for f in filas
        ]


def obtener_dataset_ordenes(receta_id: Optional[int] = None) -> pd.DataFrame:
    """
    Construye el dataset histórico de órdenes de producción completadas.

    Parámetros
    ----------
    receta_id : int | None — si se indica, filtra solo esa receta.

    Retorna
    -------
    DataFrame ordenado cronológicamente con columnas:
      orden_id, receta_id, fecha, cantidad_planeada, cantidad_real,
      merma_cantidad, merma_pct
    """
    with nueva_sesion() as db:
        q = db.query(OrdenProduccion).filter(OrdenProduccion.estado == "COMPLETADA")
        if receta_id is not None:
            q = q.filter(OrdenProduccion.receta_id == receta_id)
        ordenes = q.order_by(OrdenProduccion.fecha_fin.asc(), OrdenProduccion.id.asc()).all()

        filas = []
        for orden in ordenes:
            if not orden.cantidad_real or orden.cantidad_planeada <= 0:
                continue
            merma_total = (
                db.query(Merma)
                .filter(Merma.orden_id == orden.id)
                .with_entities(Merma.cantidad)
                .all()
            )
            merma_cantidad = sum(m[0] for m in merma_total) if merma_total else 0.0
            merma_pct = merma_cantidad / orden.cantidad_planeada
            filas.append({
                "orden_id": orden.id,
                "receta_id": orden.receta_id,
                "fecha": orden.fecha_fin or orden.fecha_inicio,
                "cantidad_planeada": float(orden.cantidad_planeada),
                "cantidad_real": float(orden.cantidad_real),
                "merma_cantidad": float(merma_cantidad),
                "merma_pct": float(max(0.0, min(1.0, merma_pct))),
            })

    if not filas:
        return pd.DataFrame(columns=[
            "orden_id", "receta_id", "fecha", "cantidad_planeada",
            "cantidad_real", "merma_cantidad", "merma_pct",
        ])

    df = pd.DataFrame(filas)
    df["fecha"] = pd.to_datetime(df["fecha"])
    return df.sort_values("fecha").reset_index(drop=True)


def diagnostico_historial(receta_id: Optional[int] = None) -> dict:
    """
    Diagnóstico rápido sobre la disponibilidad de datos para entrenar
    o estimar merma. Si receta_id es None, evalúa el historial global
    (todas las recetas juntas).
    """
    df = obtener_dataset_ordenes(receta_id)
    total = len(df)

    if total == 0:
        return {
            "ordenes_totales": 0,
            "merma_promedio_pct": 0.0,
            "merma_desviacion_pct": 0.0,
            "suficiente_ml": False,
            "suficiente_baseline": False,
            "mensaje": "No hay órdenes de producción completadas con este criterio.",
        }

    mensaje = ""
    if total < MIN_ORDENES_BASELINE:
        mensaje = (
            f"Solo hay {total} orden(es) completada(s). "
            "Se necesitan al menos 3 para una estimación básica."
        )
    elif total < MIN_ORDENES_ML:
        mensaje = (
            f"Historial limitado ({total} órdenes). "
            "La estimación se basará en el promedio histórico, no en el modelo de IA."
        )

    return {
        "ordenes_totales": total,
        "merma_promedio_pct": round(float(df["merma_pct"].mean()) * 100, 2),
        "merma_desviacion_pct": round(float(df["merma_pct"].std(ddof=0) or 0.0) * 100, 2),
        "suficiente_ml": total >= MIN_ORDENES_ML,
        "suficiente_baseline": total >= MIN_ORDENES_BASELINE,
        "mensaje": mensaje,
    }
