"""
logica_costos.py
=================
El módulo de Costos no "crea" datos por sí solo: sencillamente LEE
los costos que se calcularon al cerrar cada orden de producción
(ver logica_produccion.cerrar_orden) y arma reportes con ellos.
"""

from app.basedatos import nueva_sesion
from app.modelos import CostoProduccion


def resumen_costos() -> list[dict]:
    """Una fila por cada orden de producción ya cerrada, con sus costos y margen."""
    with nueva_sesion() as db:
        filas = []
        for costo in db.query(CostoProduccion).order_by(CostoProduccion.id.desc()).all():
            orden = costo.orden
            producto = orden.receta.producto_terminado if orden.receta else None
            filas.append({
                "orden": orden.numero,
                "lote": orden.numero_lote,
                "producto": producto.nombre if producto else "—",
                "cantidad": orden.cantidad_real or 0,
                "costo_insumos": costo.costo_insumos,
                "costo_mano_obra": costo.costo_mano_obra,
                "costo_indirectos": costo.costos_indirectos,
                "costo_total": costo.costo_total,
                "costo_unitario": costo.costo_unitario,
                "margen_unitario": costo.margen_unitario,
                "margen_porcentaje": costo.margen_porcentaje,
            })
        return filas


def kpis_costos() -> dict:
    """Indicadores resumidos para mostrar en tarjetas (dashboard / módulo Costos)."""
    filas = resumen_costos()
    if not filas:
        return {"costo_total": 0, "margen_promedio": 0, "costo_unitario_promedio": 0, "n_lotes": 0}
    return {
        "costo_total": sum(f["costo_total"] for f in filas),
        "margen_promedio": sum(f["margen_porcentaje"] for f in filas) / len(filas),
        "costo_unitario_promedio": sum(f["costo_unitario"] for f in filas) / len(filas),
        "n_lotes": len(filas),
    }
