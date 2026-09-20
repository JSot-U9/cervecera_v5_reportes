"""filas_inventario.py
=====================
Convierte lotes y movimientos de inventario en filas listas para una
TablaDatos. Existe para que la pantalla de Inventario (todos los
productos) y el detalle de producto (uno solo) compartan EXACTAMENTE
la misma consulta y el mismo formato en vez de tener cada una su copia:
si cambia cómo se muestra un lote, cambia en los dos lugares a la vez.

Las dos funciones reciben `producto_id=None` para «todos los productos»
o un id para filtrar por ese producto.
"""

from app.modelos import LoteInventario, MovimientoInventario
from app.ui.widgets import formatear_estado, tag_para_estado

COLUMNAS_LOTES_TODOS = ["N° Lote", "Producto", "Ingresado", "Vencimiento", "Cantidad", "Estado"]
COLUMNAS_LOTES_PRODUCTO = ["N° Lote", "Ingresado", "Vencimiento", "Cantidad", "Estado"]
COLUMNAS_MOVIMIENTOS_TODOS = ["Producto", "Lote", "Tipo", "Cantidad", "Referencia", "Fecha"]
COLUMNAS_MOVIMIENTOS_PRODUCTO = ["Lote", "Tipo", "Cantidad", "Referencia", "Fecha"]

LIMITE_MOVIMIENTOS = 300


def filas_lotes(db, producto_id=None):
    """(filas, tags) de los lotes, en orden FIFO (más antiguo primero).
    Con producto_id se omite la columna «Producto» (ya se sabe cuál es)."""
    consulta = db.query(LoteInventario)
    if producto_id is not None:
        consulta = consulta.filter(LoteInventario.producto_id == producto_id)
    lotes = consulta.order_by(LoteInventario.fecha_ingreso.asc(), LoteInventario.id.asc()).all()

    filas, tags = [], []
    for lote in lotes:
        fila = [lote.id, lote.numero_lote]
        if producto_id is None:
            fila.append(lote.producto.nombre)
        fila += [
            str(lote.fecha_ingreso),
            str(lote.fecha_vencimiento) if lote.fecha_vencimiento else "—",
            f"{lote.cantidad_disponible:.2f}",
            formatear_estado(lote.estado),
        ]
        filas.append(fila)
        tags.append(tag_para_estado(lote.estado))
    return filas, tags


def filas_movimientos(db, producto_id=None, limite=LIMITE_MOVIMIENTOS):
    """Filas de los movimientos de inventario, más reciente primero.
    Con producto_id se omite la columna «Producto»."""
    consulta = db.query(MovimientoInventario)
    if producto_id is not None:
        consulta = (consulta
                    .join(LoteInventario, LoteInventario.id == MovimientoInventario.lote_id)
                    .filter(LoteInventario.producto_id == producto_id))
    movimientos = consulta.order_by(MovimientoInventario.fecha.desc(),
                                    MovimientoInventario.id.desc()).limit(limite).all()

    filas = []
    for m in movimientos:
        fila = [m.id]
        if producto_id is None:
            fila.append(m.lote.producto.nombre if m.lote else "—")
        fila += [
            m.lote.numero_lote if m.lote else "—", m.tipo,
            f"{m.cantidad:.2f}", m.referencia or "—", str(m.fecha)[:16],
        ]
        filas.append(fila)
    return filas
