"""
logica_ventas.py
=================
Registrar una venta hace lo siguiente, todo en una sola transacción:
  1) Verifica que haya stock suficiente de TODOS los productos pedidos
     (si falta uno solo, no se registra nada de la venta).
  2) Descuenta el inventario usando FIFO.
  3) Guarda la orden de venta con una línea por cada lote consumido
     (esto da trazabilidad: se puede saber exactamente de qué lote
     salió cada botella vendida).
"""

from app.basedatos import nueva_sesion
from app.modelos import OrdenVenta, DetalleVenta, Cliente
from app.logica_inventario import stock_total, consumir_fifo, StockInsuficiente
from app.modelos import Producto


def registrar_venta(cliente_id: int, items: list[dict], observaciones: str = "",
                     usuario_id: int = None) -> OrdenVenta:
    """
    'items': lista de {"producto_id": 1, "cantidad": 5, "precio_unitario": 45.0}
    """
    with nueva_sesion() as db:
        # 1) Verificar stock ANTES de tocar nada
        for item in items:
            stock = stock_total(db, item["producto_id"])
            if stock < item["cantidad"]:
                producto = db.get(Producto, item["producto_id"])
                nombre = producto.nombre if producto else str(item["producto_id"])
                raise StockInsuficiente(
                    f"Stock insuficiente para '{nombre}': "
                    f"disponible {stock:.2f}, solicitado {item['cantidad']:.2f}."
                )

        ultimo = db.query(OrdenVenta).order_by(OrdenVenta.id.desc()).first()
        if ultimo:
            try:
                siguiente_numero = int(ultimo.numero.split("-")[1]) + 1
            except (IndexError, ValueError):
                siguiente_numero = ultimo.id + 1
        else:
            siguiente_numero = 1
        numero = f"OV-{siguiente_numero:04d}"
        total = sum(item["cantidad"] * item["precio_unitario"] for item in items)

        orden = OrdenVenta(
            numero=numero, cliente_id=cliente_id, total=total,
            observaciones=observaciones, creado_por=usuario_id,
        )
        db.add(orden)
        db.flush()

        # 2) Descontar inventario (FIFO) y crear una línea por lote usado
        for item in items:
            consumidos = consumir_fifo(
                db, producto_id=item["producto_id"], cantidad_requerida=item["cantidad"],
                tipo_movimiento="VENTA", referencia=numero, usuario_id=usuario_id,
            )
            for lote, cantidad_tomada in consumidos:
                db.add(DetalleVenta(
                    orden_id=orden.id, producto_id=item["producto_id"], lote_id=lote.id,
                    cantidad=cantidad_tomada, precio_unitario=item["precio_unitario"],
                    subtotal=round(cantidad_tomada * item["precio_unitario"], 2),
                ))

        db.commit()
        db.refresh(orden)
        return orden


def listar_ordenes_venta(db=None):
    if db is not None:
        return db.query(OrdenVenta).order_by(OrdenVenta.id.desc()).all()
    with nueva_sesion() as db:
        from sqlalchemy.orm import joinedload
        return (
            db.query(OrdenVenta)
            .options(joinedload(OrdenVenta.cliente))
            .order_by(OrdenVenta.id.desc())
            .all()
        )


def listar_clientes_activos(db=None):
    if db is not None:
        return db.query(Cliente).filter_by(activo=True).all()
    with nueva_sesion() as db:
        return db.query(Cliente).filter_by(activo=True).all()


def crear_cliente(tipo: str, nombre: str, documento: str = "", telefono: str = "",
                   email: str = "") -> Cliente:
    with nueva_sesion() as db:
        c = Cliente(tipo=tipo, nombre=nombre, documento=documento or None,
                     telefono=telefono, email=email, activo=True)
        db.add(c)
        db.commit()
        db.refresh(c)
        return c


def actualizar_cliente(cliente_id: int, **campos):
    """Edita los datos de un cliente ya registrado.

    Antes la ventana de Ventas solo permitía buscar clientes o crear
    uno nuevo — si el número de teléfono o el documento de un cliente
    existente estaba mal, no había forma de corregirlo sin editar la
    base de datos directamente.
    """
    with nueva_sesion() as db:
        c = db.get(Cliente, cliente_id)
        if not c:
            raise ValueError("Cliente no encontrado.")
        for clave, valor in campos.items():
            setattr(c, clave, valor)
        db.commit()
