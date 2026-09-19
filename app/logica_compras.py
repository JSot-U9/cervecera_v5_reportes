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
from app.modelos import OrdenCompra, DetalleCompra, Proveedor, Producto, LoteInventario
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


def productos_ofrecidos_por_proveedor(db, proveedor_id: int):
    """Qué insumos ha vendido realmente este proveedor, según el
    historial de compras.

    Antes el formulario de "Nueva orden de compra" ofrecía el catálogo
    COMPLETO de insumos sin importar qué proveedor estuviera
    seleccionado, como si cualquier proveedor pudiera vender cualquier
    cosa. Esto se resuelve con los datos que el sistema YA tiene: cada
    compra registrada indica qué le compró la cervecería a qué
    proveedor, así que ese historial es la fuente de verdad de lo que
    cada proveedor realmente ofrece.

    Devuelve (productos, es_catalogo_real):
      - es_catalogo_real=True  → son los productos que este proveedor
        ha vendido antes.
      - es_catalogo_real=False → el proveedor no tiene compras
        registradas todavía (por ejemplo, recién se dio de alta), así
        que se muestra el catálogo completo de insumos como respaldo,
        dejando claro en la interfaz que es una lista sin confirmar.
    """
    productos = (
        db.query(Producto)
        .join(DetalleCompra, DetalleCompra.producto_id == Producto.id)
        .join(OrdenCompra, OrdenCompra.id == DetalleCompra.orden_id)
        .filter(OrdenCompra.proveedor_id == proveedor_id, Producto.activo.is_(True))
        .distinct()
        .order_by(Producto.nombre)
        .all()
    )
    if productos:
        return productos, True

    todos = db.query(Producto).filter_by(tipo="Insumo", activo=True).order_by(Producto.nombre).all()
    return todos, False


def proveedores_probables_para_producto(db, producto_id: int):
    """Proveedores que probablemente venden este producto, según el
    historial de compras — es la relación inversa de
    productos_ofrecidos_por_proveedor().

    Se usa cuando ya se conoce el producto ANTES de elegir proveedor
    (por ejemplo, al generar una orden de compra desde una
    recomendación del motor de Reposición inteligente): antes, en ese
    flujo, el selector de proveedor mostraba TODA la lista de
    proveedores activos sin importar qué vendiera cada uno (una
    tienda de levadura aparecía igual que una de envases o etiquetas
    como opción para reponer lúpulo). Ahora se prioriza a quienes de
    verdad han vendido ese producto antes, usando el mismo historial
    de OrdenCompra/DetalleCompra que ya es la fuente de verdad en
    productos_ofrecidos_por_proveedor().

    Devuelve (proveedores, es_catalogo_real):
      - es_catalogo_real=True  → son proveedores que han vendido este
        producto antes.
      - es_catalogo_real=False → nadie le ha vendido este producto
        todavía a la cervecería (por ejemplo, un insumo nuevo), así
        que se muestra la lista completa de proveedores activos como
        respaldo, dejando claro en la interfaz que es una lista sin
        confirmar.
    """
    proveedores = (
        db.query(Proveedor)
        .join(OrdenCompra, OrdenCompra.proveedor_id == Proveedor.id)
        .join(DetalleCompra, DetalleCompra.orden_id == OrdenCompra.id)
        .filter(DetalleCompra.producto_id == producto_id, Proveedor.activo.is_(True))
        .distinct()
        .order_by(Proveedor.razon_social)
        .all()
    )
    if proveedores:
        return proveedores, True

    todos = db.query(Proveedor).filter_by(activo=True).order_by(Proveedor.razon_social).all()
    return todos, False


def ultimos_precios_por_proveedor(db, proveedor_id: int) -> dict:
    """Último precio pagado A ESTE proveedor por cada producto.

    Antes el precio se autocompletaba con el último lote comprado de
    ese producto sin importar a quién — es decir, el precio de un
    proveedor "contaminaba" el formulario de otro. Ahora el precio
    sugerido es siempre el que ESE proveedor cobró la última vez.
    """
    lotes = (
        db.query(LoteInventario)
        .filter(LoteInventario.proveedor_id == proveedor_id)
        .order_by(LoteInventario.id.desc())
        .all()
    )
    precios = {}
    for lote in lotes:
        if lote.producto_id not in precios and lote.costo_unitario:
            precios[lote.producto_id] = lote.costo_unitario
    return precios


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
