"""
demanda_data.py
===============
Extracción y preparación de datos de ventas para el módulo de
predicción de demanda. Consulta directamente las tablas del ERP
(OrdenVenta + DetalleVenta + Producto) sin duplicar información.
"""

from __future__ import annotations

from datetime import date, timedelta
from typing import Optional

import pandas as pd

from app.basedatos import nueva_sesion
from app.modelos import DetalleVenta, OrdenVenta, Producto

# Mínimo de días de historial necesarios para generar una predicción confiable
MIN_DIAS_HISTORIAL = 14
# Mínimo absoluto para intentar un baseline
MIN_DIAS_BASELINE = 7


def listar_productos_con_ventas() -> list[dict]:
    """
    Devuelve la lista de productos terminados que tienen al menos
    una venta registrada, ordenados por nombre.
    """
    with nueva_sesion() as db:
        filas = (
            db.query(Producto.id, Producto.nombre, Producto.unidad_medida)
            .join(DetalleVenta, DetalleVenta.producto_id == Producto.id)
            .filter(Producto.tipo == "Producto terminado", Producto.activo == True)
            .distinct()
            .order_by(Producto.nombre)
            .all()
        )
        return [
            {"id": f.id, "nombre": f.nombre, "unidad": f.unidad_medida or "unid."}
            for f in filas
        ]


def obtener_serie_diaria(
    producto_id: int,
    fecha_inicio: Optional[date] = None,
    fecha_fin: Optional[date] = None,
) -> pd.DataFrame:
    """
    Construye la serie temporal diaria de ventas para un producto.

    Parámetros
    ----------
    producto_id : int
    fecha_inicio : date | None   — si None, usa toda la historia disponible
    fecha_fin    : date | None   — si None, usa la fecha de hoy

    Retorna
    -------
    DataFrame con columnas: fecha (date), cantidad (float).
    Cada día desde fecha_inicio hasta fecha_fin está presente;
    los días sin venta tienen cantidad = 0.
    """
    with nueva_sesion() as db:
        q = (
            db.query(OrdenVenta.fecha, DetalleVenta.cantidad)
            .join(DetalleVenta, DetalleVenta.orden_id == OrdenVenta.id)
            .filter(DetalleVenta.producto_id == producto_id)
        )
        if fecha_inicio:
            q = q.filter(OrdenVenta.fecha >= fecha_inicio)
        if fecha_fin:
            q = q.filter(OrdenVenta.fecha <= fecha_fin)

        filas = q.all()

    if not filas:
        return pd.DataFrame(columns=["fecha", "cantidad"])

    df = pd.DataFrame(filas, columns=["fecha", "cantidad"])
    df["fecha"] = pd.to_datetime(df["fecha"])
    df = df.groupby("fecha", as_index=False)["cantidad"].sum()

    # Rellenar días sin ventas con 0 (rango completo)
    fecha_min = df["fecha"].min()
    fecha_max = fecha_fin or date.today()
    idx = pd.date_range(start=fecha_min, end=fecha_max, freq="D")
    df = df.set_index("fecha").reindex(idx, fill_value=0.0).reset_index()
    df.columns = ["fecha", "cantidad"]
    df["fecha"] = df["fecha"].dt.date
    return df.sort_values("fecha").reset_index(drop=True)


def diagnostico_historial(producto_id: int) -> dict:
    """
    Devuelve un diagnóstico rápido sobre la disponibilidad de datos.

    Retorna dict con claves:
      dias_totales, dias_con_ventas, fecha_primera, fecha_ultima,
      suficiente_ml, suficiente_baseline, mensaje
    """
    df = obtener_serie_diaria(producto_id)
    if df.empty:
        return {
            "dias_totales": 0,
            "dias_con_ventas": 0,
            "fecha_primera": None,
            "fecha_ultima": None,
            "suficiente_ml": False,
            "suficiente_baseline": False,
            "mensaje": "No hay ventas registradas para este producto.",
        }

    dias_totales = len(df)
    dias_con_ventas = int((df["cantidad"] > 0).sum())
    msg = ""
    if dias_totales < MIN_DIAS_BASELINE:
        msg = (
            f"Solo hay {dias_totales} día(s) de historial. "
            "Se necesitan al menos 7 días para una estimación básica."
        )
    elif dias_totales < MIN_DIAS_HISTORIAL:
        msg = (
            f"Historial limitado ({dias_totales} días). "
            "La predicción se basará en un promedio móvil simple."
        )
    return {
        "dias_totales": dias_totales,
        "dias_con_ventas": dias_con_ventas,
        "fecha_primera": df["fecha"].iloc[0],
        "fecha_ultima": df["fecha"].iloc[-1],
        "suficiente_ml": dias_totales >= MIN_DIAS_HISTORIAL,
        "suficiente_baseline": dias_totales >= MIN_DIAS_BASELINE,
        "mensaje": msg,
    }
