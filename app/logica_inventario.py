"""
logica_inventario.py
=====================
Todo lo relacionado a lotes, movimientos y la regla FIFO
("First In, First Out" / "el lote más antiguo sale primero").

Idea clave del FIFO: cuando hay que sacar cantidad de un producto
(para venderlo o para usarlo en producción), primero se agota el
lote más antiguo, y solo si no alcanza se pasa al siguiente. Esto
evita que se acumulen productos vencidos en el fondo del almacén.
"""

from datetime import date, timedelta

from app.modelos import LoteInventario, MovimientoInventario, Producto

_PREFIJO_CODIGO = {"Insumo": "INS", "Producto terminado": "PRD"}


def siguiente_codigo(db, tipo: str) -> str:
    """Código único que le correspondería al PRÓXIMO producto de este
    tipo, con el mismo formato que ya usa el catálogo (INS-001,
    PRD-001, ...) — cada tipo lleva su propia numeración.

    Antes el código era un campo de texto libre que el usuario debía
    inventar a mano (con el placeholder "Ej: INS-014" solo como
    sugerencia visual), así que nada impedía que alguien usara un
    formato distinto al del resto del catálogo. Ahora se autogenera a
    partir del tipo elegido, igual que ya funciona el resto de la
    numeración del sistema (OC-, V-, etc.).
    """
    prefijo = _PREFIJO_CODIGO.get(tipo, "PRD")
    ultimo = (
        db.query(Producto)
        .filter(Producto.codigo.like(f"{prefijo}-%"))
        .order_by(Producto.codigo.desc())
        .first()
    )
    siguiente_numero = 1
    if ultimo is not None:
        sufijo = ultimo.codigo.split("-")[-1]
        if sufijo.isdigit():
            siguiente_numero = int(sufijo) + 1
    codigo = f"{prefijo}-{siguiente_numero:03d}"
    # Por si algún código antiguo no siguió la numeración secuencial
    # (importado manualmente, etc.), se sigue avanzando hasta
    # encontrar uno que de verdad esté libre.
    while db.query(Producto).filter_by(codigo=codigo).first() is not None:
        siguiente_numero += 1
        codigo = f"{prefijo}-{siguiente_numero:03d}"
    return codigo


class StockInsuficiente(Exception):
    """Se lanza cuando se pide sacar más cantidad de la que hay disponible."""
    pass


def crear_lote(db, producto_id: int, numero_lote: str, cantidad: float,
               costo_unitario: float = 0.0, proveedor_id: int = None,
               orden_produccion_id: int = None, fecha_vencimiento=None,
               referencia: str = "", usuario_id: int = None) -> LoteInventario:
    """
    Registra la ENTRADA de un lote nuevo al almacén (por compra o
    por producción terminada) y crea su movimiento de tipo ENTRADA.

    Nota: esta función NO hace commit. Quien la llama decide cuándo
    confirmar la transacción completa (así una compra con varios
    productos se guarda toda junta, o no se guarda nada).
    """
    lote = LoteInventario(
        numero_lote=numero_lote,
        producto_id=producto_id,
        proveedor_id=proveedor_id,
        orden_produccion_id=orden_produccion_id,
        fecha_ingreso=date.today(),
        fecha_vencimiento=fecha_vencimiento,
        cantidad_inicial=cantidad,
        cantidad_disponible=cantidad,
        costo_unitario=costo_unitario,
        estado="DISPONIBLE",
    )
    db.add(lote)
    db.flush()  # para que lote.id quede disponible antes del commit

    db.add(MovimientoInventario(
        lote_id=lote.id, tipo="ENTRADA", cantidad=cantidad,
        referencia=referencia, usuario_id=usuario_id,
    ))
    return lote


def lotes_disponibles_fifo(db, producto_id: int):
    """Lotes con stock, ordenados del más antiguo al más nuevo (orden FIFO)."""
    return (
        db.query(LoteInventario)
        .filter(
            LoteInventario.producto_id == producto_id,
            LoteInventario.estado == "DISPONIBLE",
            LoteInventario.cantidad_disponible > 0,
        )
        .order_by(LoteInventario.fecha_ingreso.asc())
        .all()
    )


def stock_total(db, producto_id: int) -> float:
    """Suma la cantidad disponible en TODOS los lotes de un producto."""
    lotes = lotes_disponibles_fifo(db, producto_id)
    return sum(lote.cantidad_disponible for lote in lotes)


def consumir_fifo(db, producto_id: int, cantidad_requerida: float,
                   tipo_movimiento: str, referencia: str = "",
                   usuario_id: int = None):
    """
    Descuenta 'cantidad_requerida' del producto, sacando primero de
    los lotes más antiguos. Se usa tanto para VENTAS como para
    CONSUMO en producción.

    Devuelve una lista de tuplas (lote, cantidad_tomada_de_ese_lote),
    útil para dejar trazabilidad de exactamente qué lotes se usaron.

    Lanza StockInsuficiente si no hay suficiente cantidad en total.
    """
    lotes = lotes_disponibles_fifo(db, producto_id)
    stock_disponible = sum(l.cantidad_disponible for l in lotes)

    if stock_disponible < cantidad_requerida:
        producto = db.get(Producto, producto_id)
        nombre = producto.nombre if producto else f"ID {producto_id}"
        raise StockInsuficiente(
            f"Stock insuficiente para '{nombre}': "
            f"disponible {stock_disponible:.2f}, requerido {cantidad_requerida:.2f}."
        )

    pendiente = cantidad_requerida
    consumidos = []

    for lote in lotes:
        if pendiente <= 0:
            break
        cantidad_a_tomar = min(lote.cantidad_disponible, pendiente)

        lote.cantidad_disponible -= cantidad_a_tomar
        if lote.cantidad_disponible <= 0:
            lote.estado = "AGOTADO"

        db.add(MovimientoInventario(
            lote_id=lote.id, tipo=tipo_movimiento, cantidad=cantidad_a_tomar,
            referencia=referencia, usuario_id=usuario_id,
        ))
        consumidos.append((lote, cantidad_a_tomar))
        pendiente -= cantidad_a_tomar

    return consumidos


def ajustar_stock(db, lote_id: int, nueva_cantidad: float, motivo: str = "",
                   usuario_id: int = None):
    """Corrección manual de inventario (por ejemplo, tras un conteo físico)."""
    lote = db.get(LoteInventario, lote_id)
    if not lote:
        raise ValueError("Lote no encontrado.")

    diferencia = nueva_cantidad - lote.cantidad_disponible
    lote.cantidad_disponible = nueva_cantidad
    lote.estado = "AGOTADO" if nueva_cantidad <= 0 else "DISPONIBLE"

    db.add(MovimientoInventario(
        lote_id=lote_id, tipo="AJUSTE", cantidad=abs(diferencia),
        referencia=f"AJUSTE: {motivo}", usuario_id=usuario_id,
    ))


def productos_bajo_minimo(db):
    """Lista de productos cuyo stock actual está por debajo del mínimo configurado.

    Se resuelve con UNA sola consulta agregada en vez de recorrer los
    productos uno por uno llamando a stock_total() (lo que disparaba
    una consulta extra por producto: el clásico problema "N+1"). Con un
    catálogo de varios cientos de productos esa versión tardaba
    segundos, y como esta función alimenta tanto el Dashboard como el
    contador de notificaciones y el motor de reposición, ese costo se
    pagaba en cada navegación.
    """
    from sqlalchemy import func

    # Stock disponible por producto, sumando solo lotes vigentes.
    stock_por_producto = dict(
        db.query(
            LoteInventario.producto_id,
            func.coalesce(func.sum(LoteInventario.cantidad_disponible), 0.0),
        )
        .filter(
            LoteInventario.estado == "DISPONIBLE",
            LoteInventario.cantidad_disponible > 0,
        )
        .group_by(LoteInventario.producto_id)
        .all()
    )

    resultado = []
    for producto in db.query(Producto).filter_by(activo=True).all():
        stock = float(stock_por_producto.get(producto.id, 0.0))
        if stock < (producto.stock_minimo or 0.0):
            resultado.append({
                "id": producto.id, "codigo": producto.codigo, "nombre": producto.nombre,
                "stock": stock, "minimo": producto.stock_minimo,
                "unidad": producto.unidad_medida or "",
            })
    return resultado


def lotes_proximos_a_vencer(db, dias: int = 30):
    """Lotes disponibles cuya fecha de vencimiento cae dentro de los próximos N días."""
    limite = date.today() + timedelta(days=dias)
    return (
        db.query(LoteInventario)
        .filter(
            LoteInventario.estado == "DISPONIBLE",
            LoteInventario.fecha_vencimiento.isnot(None),
            LoteInventario.fecha_vencimiento <= limite,
        )
        .order_by(LoteInventario.fecha_vencimiento.asc())
        .all()
    )
