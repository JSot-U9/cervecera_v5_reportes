"""
logica_compras.py
==================
Registrar una compra hace DOS cosas a la vez, en una sola transacción:
  1) Guarda la orden de compra y sus líneas (qué se compró, a quién,
     a qué precio).
  2) Crea un LOTE de inventario nuevo por cada producto comprado,
     para que el stock quede actualizado automáticamente.

"En una sola transacción" significa: o se guarda todo, o si algo
falla a la mitad, no se guarda nada (evitamos que quede una compra
"a medias" en la base de datos).
"""

from app.basedatos import nueva_sesion
from app.modelos import OrdenCompra, DetalleCompra, Proveedor
from app.logica_inventario import crear_lote


def registrar_compra(proveedor_id: int, items: list[dict], documento_referencia: str = "",
                      observaciones: str = "", usuario_id: int = None) -> OrdenCompra:
    """
    'items' es una lista de diccionarios, uno por producto comprado:
        {"producto_id": 1, "cantidad": 10, "precio_unitario": 5.0,
         "numero_lote": "L-001" (opcional), "fecha_vencimiento": None (opcional)}
    """
    with nueva_sesion() as db:
        ultimo = db.query(OrdenCompra).order_by(OrdenCompra.id.desc()).first()
        if ultimo:
            try:
                siguiente_numero = int(ultimo.numero.split("-")[1]) + 1
            except (IndexError, ValueError):
                siguiente_numero = ultimo.id + 1
        else:
            siguiente_numero = 1
        numero = f"OC-{siguiente_numero:04d}"

        total = sum(item["cantidad"] * item["precio_unitario"] for item in items)

        orden = OrdenCompra(
            numero=numero, proveedor_id=proveedor_id,
            documento_referencia=documento_referencia, total=total,
            observaciones=observaciones, creado_por=usuario_id,
        )
        db.add(orden)
        db.flush()  # necesitamos orden.id para las líneas de abajo

        for item in items:
            subtotal = item["cantidad"] * item["precio_unitario"]
            db.add(DetalleCompra(
                orden_id=orden.id, producto_id=item["producto_id"],
                cantidad=item["cantidad"], precio_unitario=item["precio_unitario"],
                subtotal=subtotal,
            ))
            numero_lote = item.get("numero_lote") or f"{numero}-{item['producto_id']}"
            crear_lote(
                db, producto_id=item["producto_id"], numero_lote=numero_lote,
                cantidad=item["cantidad"], costo_unitario=item["precio_unitario"],
                proveedor_id=proveedor_id, fecha_vencimiento=item.get("fecha_vencimiento"),
                referencia=numero, usuario_id=usuario_id,
            )

        db.commit()
        db.refresh(orden)
        return orden


def listar_ordenes_compra(db=None):
    if db is not None:
        return db.query(OrdenCompra).order_by(OrdenCompra.id.desc()).all()
    with nueva_sesion() as db:
        from sqlalchemy.orm import joinedload
        return (
            db.query(OrdenCompra)
            .options(joinedload(OrdenCompra.proveedor))
            .order_by(OrdenCompra.id.desc())
            .all()
        )


def listar_proveedores_activos(db=None):
    if db is not None:
        return db.query(Proveedor).filter_by(activo=True).all()
    with nueva_sesion() as db:
        return db.query(Proveedor).filter_by(activo=True).all()


def crear_proveedor(razon_social: str, ruc: str = "", contacto: str = "",
                     telefono: str = "", email: str = "") -> Proveedor:
    with nueva_sesion() as db:
        p = Proveedor(razon_social=razon_social, ruc=ruc or None, contacto=contacto,
                       telefono=telefono, email=email, activo=True)
        db.add(p)
        db.commit()
        db.refresh(p)
        return p


def actualizar_proveedor(proveedor_id: int, **campos):
    with nueva_sesion() as db:
        p = db.get(Proveedor, proveedor_id)
        if not p:
            raise ValueError("Proveedor no encontrado.")
        for clave, valor in campos.items():
            setattr(p, clave, valor)
        db.commit()
