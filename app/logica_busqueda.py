"""logica_busqueda.py
=====================
Búsqueda global del ERP (usada por el header superior — sección 8 del
rediseño UI/UX). Busca coincidencias de texto en las entidades
principales del sistema y devuelve resultados agrupados por
categoría, listos para mostrarse en un popup y navegar directamente
al módulo correspondiente.

No inventa datos ni depende de IA: son consultas directas a la base
de datos existente, de solo lectura.
"""

from __future__ import annotations

from app.basedatos import nueva_sesion
from app.modelos import (
    Producto, Cliente, Proveedor, OrdenVenta, OrdenCompra,
    LoteInventario, OrdenProduccion,
)

LIMITE_POR_CATEGORIA = 5


def buscar_global(texto: str, limite: int = LIMITE_POR_CATEGORIA) -> list[dict]:
    """
    Devuelve una lista de resultados con las claves:
      categoria, tipo, titulo, subtitulo, texto_filtro
    "tipo" identifica a qué módulo/tabla pertenece el resultado, para
    que quien reciba la lista sepa a dónde navegar (ver
    ventana_principal._ir_a_resultado).
    """
    texto = (texto or "").strip()
    if len(texto) < 2:
        return []
    patron = f"%{texto}%"
    resultados: list[dict] = []

    with nueva_sesion() as db:
        productos = (
            db.query(Producto)
            .filter(Producto.activo.is_(True))
            .filter((Producto.nombre.ilike(patron)) | (Producto.codigo.ilike(patron)))
            .order_by(Producto.nombre)
            .limit(limite)
            .all()
        )
        for p in productos:
            resultados.append({
                "categoria": "Productos", "tipo": "producto",
                "titulo": p.nombre, "subtitulo": f"{p.codigo} · {p.tipo}",
                "texto_filtro": p.nombre,
            })

        lotes = (
            db.query(LoteInventario)
            .filter(LoteInventario.numero_lote.ilike(patron))
            .order_by(LoteInventario.fecha_ingreso.desc())
            .limit(limite)
            .all()
        )
        for l in lotes:
            nombre_prod = l.producto.nombre if l.producto else ""
            resultados.append({
                "categoria": "Lotes", "tipo": "lote",
                "titulo": l.numero_lote, "subtitulo": f"{nombre_prod} · {l.estado}",
                "texto_filtro": l.numero_lote,
            })

        producciones = (
            db.query(OrdenProduccion)
            .filter((OrdenProduccion.numero.ilike(patron)) |
                    (OrdenProduccion.numero_lote.ilike(patron)))
            .order_by(OrdenProduccion.fecha_inicio.desc())
            .limit(limite)
            .all()
        )
        for op in producciones:
            resultados.append({
                "categoria": "Producción", "tipo": "produccion",
                "titulo": op.numero, "subtitulo": f"Lote {op.numero_lote} · {op.estado}",
                "texto_filtro": op.numero,
            })

        compras = (
            db.query(OrdenCompra)
            .filter(OrdenCompra.numero.ilike(patron))
            .order_by(OrdenCompra.fecha.desc())
            .limit(limite)
            .all()
        )
        for oc in compras:
            proveedor = oc.proveedor.razon_social if oc.proveedor else ""
            resultados.append({
                "categoria": "Compras", "tipo": "compra",
                "titulo": oc.numero, "subtitulo": proveedor,
                "texto_filtro": oc.numero,
            })

        proveedores = (
            db.query(Proveedor)
            .filter(Proveedor.activo.is_(True))
            .filter(Proveedor.razon_social.ilike(patron))
            .order_by(Proveedor.razon_social)
            .limit(limite)
            .all()
        )
        for prov in proveedores:
            resultados.append({
                "categoria": "Proveedores", "tipo": "proveedor",
                "titulo": prov.razon_social, "subtitulo": prov.ruc or "",
                "texto_filtro": prov.razon_social,
            })

        ventas = (
            db.query(OrdenVenta)
            .filter(OrdenVenta.numero.ilike(patron))
            .order_by(OrdenVenta.fecha.desc())
            .limit(limite)
            .all()
        )
        for ov in ventas:
            cliente = ov.cliente.nombre if ov.cliente else ""
            resultados.append({
                "categoria": "Ventas", "tipo": "venta",
                "titulo": ov.numero, "subtitulo": cliente,
                "texto_filtro": ov.numero,
            })

        clientes = (
            db.query(Cliente)
            .filter(Cliente.activo.is_(True))
            .filter(Cliente.nombre.ilike(patron))
            .order_by(Cliente.nombre)
            .limit(limite)
            .all()
        )
        for c in clientes:
            resultados.append({
                "categoria": "Clientes", "tipo": "cliente",
                "titulo": c.nombre, "subtitulo": c.documento or "",
                "texto_filtro": c.nombre,
            })

    return resultados
