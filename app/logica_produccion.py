"""
logica_produccion.py
=====================
El ciclo de vida de una orden de producción tiene 3 pasos:

  1) crear_orden()    -> se planea un lote nuevo (estado INICIADA)
  2) iniciar_proceso() -> se marca que ya se está trabajando (EN_PROCESO)
  3) cerrar_orden()    -> se termina el lote. Este es el paso más
                           importante: aquí se consumen los insumos
                           (FIFO), se registra la merma, se crea el
                           lote del producto terminado, y se calculan
                           los costos y el margen.
"""

from datetime import date

from app.basedatos import nueva_sesion
from app.modelos import OrdenProduccion, Merma, CostoProduccion, Receta
from app.logica_inventario import consumir_fifo, crear_lote


def crear_orden(receta_id: int, cantidad_planeada: float, numero_lote: str,
                 observaciones: str = "", usuario_id: int = None) -> OrdenProduccion:
    with nueva_sesion() as db:
        ultimo = db.query(OrdenProduccion).order_by(OrdenProduccion.id.desc()).first()
        if ultimo:
            try:
                siguiente_numero = int(ultimo.numero.split("-")[1]) + 1
            except (IndexError, ValueError):
                siguiente_numero = ultimo.id + 1
        else:
            siguiente_numero = 1
        numero = f"OP-{siguiente_numero:04d}"

        orden = OrdenProduccion(
            numero=numero, receta_id=receta_id, numero_lote=numero_lote,
            cantidad_planeada=cantidad_planeada, estado="INICIADA",
            observaciones=observaciones, creado_por=usuario_id,
        )
        db.add(orden)
        db.commit()
        db.refresh(orden)
        return orden


def iniciar_proceso(orden_id: int) -> OrdenProduccion:
    with nueva_sesion() as db:
        orden = db.get(OrdenProduccion, orden_id)
        if not orden or orden.estado != "INICIADA":
            raise ValueError("La orden no está en estado INICIADA.")
        orden.estado = "EN_PROCESO"
        db.commit()
        db.refresh(orden)
        return orden


def cerrar_orden(orden_id: int, cantidad_real: float, cantidad_merma: float,
                  causa_merma: str, costo_mano_obra: float, costos_indirectos: float,
                  usuario_id: int = None) -> OrdenProduccion:
    """
    Cierra la orden. Paso a paso:

      1. Calcula el "factor de escala": si la receta rinde 100L y en
         este lote se produjeron 80L reales, el factor es 0.8, y
         cada ingrediente de la receta se multiplica por ese factor.
      2. Descuenta cada insumo del inventario usando FIFO.
      3. Si hubo merma, la registra.
      4. Crea un lote NUEVO de inventario, pero del producto TERMINADO
         (esto es lo que hace que el producto quede disponible para
         venderse).
      5. Calcula costo total, costo por unidad, y margen respecto al
         precio de venta configurado en el producto.
    """
    with nueva_sesion() as db:
        orden = db.get(OrdenProduccion, orden_id)
        if not orden:
            raise ValueError("Orden no encontrada.")
        if orden.estado not in ("INICIADA", "EN_PROCESO"):
            raise ValueError(f"No se puede cerrar una orden en estado '{orden.estado}'.")

        receta = db.get(Receta, orden.receta_id)
        factor_escala = cantidad_real / (receta.rendimiento or 1)

        # 1) Consumir cada insumo de la receta (ajustado por el factor de escala)
        costo_insumos_real = 0.0
        for ingrediente in receta.ingredientes:
            cantidad_necesaria = ingrediente.cantidad * factor_escala
            consumidos = consumir_fifo(
                db, producto_id=ingrediente.insumo_id,
                cantidad_requerida=cantidad_necesaria, tipo_movimiento="CONSUMO",
                referencia=orden.numero, usuario_id=usuario_id,
            )
            for lote, cantidad_tomada in consumidos:
                costo_insumos_real += cantidad_tomada * lote.costo_unitario

        # 2) Merma (si hubo)
        if cantidad_merma > 0:
            db.add(Merma(orden_id=orden.id, cantidad=cantidad_merma, causa=causa_merma))

        # 3) Crear el lote del producto terminado
        costo_unitario_estimado = (
            (costo_insumos_real + costo_mano_obra + costos_indirectos) / max(cantidad_real, 1)
        )
        crear_lote(
            db, producto_id=receta.producto_terminado_id, numero_lote=orden.numero_lote,
            cantidad=cantidad_real, costo_unitario=costo_unitario_estimado,
            orden_produccion_id=orden.id, referencia=orden.numero, usuario_id=usuario_id,
        )

        # 4) Calcular costos y margen
        costo_total = costo_insumos_real + costo_mano_obra + costos_indirectos
        costo_unitario = costo_total / max(cantidad_real, 1)
        precio_venta = receta.producto_terminado.precio_venta
        margen_unitario = precio_venta - costo_unitario
        margen_porcentaje = (margen_unitario / precio_venta * 100) if precio_venta > 0 else 0

        db.add(CostoProduccion(
            orden_id=orden.id, costo_insumos=costo_insumos_real,
            costo_mano_obra=costo_mano_obra, costos_indirectos=costos_indirectos,
            costo_total=costo_total, costo_unitario=costo_unitario,
            margen_unitario=margen_unitario, margen_porcentaje=margen_porcentaje,
        ))

        orden.cantidad_real = cantidad_real
        orden.fecha_fin = date.today()
        orden.estado = "COMPLETADA"

        db.commit()
        db.refresh(orden)
        return orden


def listar_ordenes(db=None):
    if db is not None:
        return db.query(OrdenProduccion).order_by(OrdenProduccion.id.desc()).all()
    with nueva_sesion() as db:
        from sqlalchemy.orm import joinedload
        return (
            db.query(OrdenProduccion)
            .options(
                joinedload(OrdenProduccion.receta).joinedload(Receta.producto_terminado)
            )
            .order_by(OrdenProduccion.id.desc())
            .all()
        )


def listar_recetas_activas(db=None):
    if db is not None:
        return db.query(Receta).filter_by(activa=True).all()
    with nueva_sesion() as db:
        return db.query(Receta).filter_by(activa=True).all()


def recetas_activas_de_producto(db, producto_terminado_id: int) -> list[dict]:
    """
    Devuelve las recetas activas del producto terminado indicado como
    lista de dicts con las claves que usa PestanaInteligenciaProducto:
      id, rendimiento, unidad (= unidad_rendimiento del modelo ORM).
    """
    recetas = (
        db.query(Receta)
        .filter_by(activa=True, producto_terminado_id=producto_terminado_id)
        .all()
    )
    return [
        {
            "id":          r.id,
            "rendimiento": r.rendimiento,
            "unidad":      r.unidad_rendimiento or "",
        }
        for r in recetas
    ]
