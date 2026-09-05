"""
modelos.py
==========
Aquí viven TODAS las "tablas" del sistema, escritas como clases de
Python. Esto se llama un "ORM" (Object-Relational Mapper): en vez de
escribir SQL a mano, escribimos clases y SQLAlchemy las convierte
en tablas de la base de datos.

Se usa la sintaxis CLÁSICA de SQLAlchemy (Column, no "Mapped[...]"),
porque es la forma más simple y la que más se enseña en tutoriales
para gente que recién empieza.

Patrón que se repite en casi todas las clases:

    class NombreDeLaTabla(Base):
        __tablename__ = "nombre_de_la_tabla"      # nombre real en SQL

        id = Column(Integer, primary_key=True)     # llave primaria
        algun_campo = Column(String(100))           # una columna de texto

Todas las clases heredan de "Base", que viene de basedatos.py.
"""

from datetime import datetime, date
from sqlalchemy import (
    Column, Integer, String, Float, Boolean, Date, DateTime, Text,
    ForeignKey,
)
from sqlalchemy.orm import relationship

from app.basedatos import Base


# ══════════════════════════════════════════════════════════════════
#  USUARIOS Y SEGURIDAD
# ══════════════════════════════════════════════════════════════════
class Usuario(Base):
    """Una persona que puede entrar al sistema (login)."""
    __tablename__ = "usuarios"

    id = Column(Integer, primary_key=True)
    usuario = Column(String(50), unique=True, nullable=False)   # con qué inicia sesión
    contrasena_hash = Column(String(255), nullable=False)       # NUNCA se guarda la clave en texto plano
    nombre_completo = Column(String(100), nullable=False)
    rol = Column(String(30), nullable=False)                    # ADMIN, COMPRAS, INVENTARIO...
    activo = Column(Boolean, default=True)
    creado_en = Column(DateTime, default=datetime.now)

    def __repr__(self):
        return f"<Usuario {self.usuario} [{self.rol}]>"


class LogAcceso(Base):
    """Registro de cada intento de inicio de sesión (para auditoría)."""
    __tablename__ = "logs_acceso"

    id = Column(Integer, primary_key=True)
    usuario_id = Column(Integer, ForeignKey("usuarios.id"), nullable=True)
    accion = Column(String(50))       # LOGIN_OK, LOGIN_FAIL, LOGOUT
    detalle = Column(Text)
    fecha = Column(DateTime, default=datetime.now)


# ══════════════════════════════════════════════════════════════════
#  COMPRAS
# ══════════════════════════════════════════════════════════════════
class Proveedor(Base):
    __tablename__ = "proveedores"

    id = Column(Integer, primary_key=True)
    razon_social = Column(String(150), nullable=False)
    ruc = Column(String(11), unique=True)
    contacto = Column(String(100))
    telefono = Column(String(20))
    email = Column(String(100))
    activo = Column(Boolean, default=True)


class OrdenCompra(Base):
    __tablename__ = "ordenes_compra"

    id = Column(Integer, primary_key=True)
    numero = Column(String(20), unique=True, nullable=False)      # ej: OC-0001
    proveedor_id = Column(Integer, ForeignKey("proveedores.id"), nullable=False)
    fecha = Column(Date, default=date.today)
    documento_referencia = Column(String(50))
    total = Column(Float, default=0.0)
    observaciones = Column(Text)
    creado_por = Column(Integer, ForeignKey("usuarios.id"))

    proveedor = relationship("Proveedor")
    detalles = relationship("DetalleCompra", back_populates="orden", cascade="all, delete-orphan")


class DetalleCompra(Base):
    """Una línea (un producto) dentro de una orden de compra."""
    __tablename__ = "detalles_compra"

    id = Column(Integer, primary_key=True)
    orden_id = Column(Integer, ForeignKey("ordenes_compra.id"), nullable=False)
    producto_id = Column(Integer, ForeignKey("productos.id"), nullable=False)
    cantidad = Column(Float, nullable=False)
    precio_unitario = Column(Float, nullable=False)
    subtotal = Column(Float, nullable=False)

    orden = relationship("OrdenCompra", back_populates="detalles")
    producto = relationship("Producto")


# ══════════════════════════════════════════════════════════════════
#  PRODUCTOS E INVENTARIO (con trazabilidad FIFO)
# ══════════════════════════════════════════════════════════════════
class Producto(Base):
    """
    Puede ser un insumo (materia prima, como malta o lúpulo) o un
    producto terminado (como una cerveza lista para vender).
    El campo "tipo" distingue entre ambos.
    """
    __tablename__ = "productos"

    id = Column(Integer, primary_key=True)
    codigo = Column(String(20), unique=True, nullable=False)
    nombre = Column(String(150), nullable=False)
    descripcion = Column(Text)
    tipo = Column(String(30), nullable=False)   # "Insumo" o "Producto terminado"
    unidad_medida = Column(String(20))          # kg, L, g, unidad...
    precio_venta = Column(Float, default=0.0)   # solo aplica a productos terminados
    stock_minimo = Column(Float, default=0.0)
    activo = Column(Boolean, default=True)


class LoteInventario(Base):
    """
    Cada vez que entra mercadería (por compra o por producción) se
    crea un LOTE. Guardar por lotes es lo que permite trazabilidad:
    saber exactamente de dónde vino cada unidad de producto y
    aplicar la regla FIFO (el lote más antiguo se consume primero).
    """
    __tablename__ = "lotes_inventario"

    id = Column(Integer, primary_key=True)
    numero_lote = Column(String(40), unique=True, nullable=False)
    producto_id = Column(Integer, ForeignKey("productos.id"), nullable=False)
    proveedor_id = Column(Integer, ForeignKey("proveedores.id"), nullable=True)
    orden_produccion_id = Column(Integer, ForeignKey("ordenes_produccion.id"), nullable=True)
    fecha_ingreso = Column(Date, default=date.today)
    fecha_vencimiento = Column(Date, nullable=True)
    cantidad_inicial = Column(Float, nullable=False)
    cantidad_disponible = Column(Float, nullable=False)   # esta baja con cada consumo
    costo_unitario = Column(Float, default=0.0)
    estado = Column(String(20), default="DISPONIBLE")     # DISPONIBLE | AGOTADO

    producto = relationship("Producto")
    proveedor = relationship("Proveedor")


class MovimientoInventario(Base):
    """
    Historial de TODO lo que entra o sale de un lote: entradas,
    salidas, consumos de producción, ventas y ajustes manuales.
    Sirve para poder auditar qué pasó con cada lote.
    """
    __tablename__ = "movimientos_inventario"

    id = Column(Integer, primary_key=True)
    lote_id = Column(Integer, ForeignKey("lotes_inventario.id"), nullable=False)
    tipo = Column(String(20), nullable=False)   # ENTRADA, SALIDA, CONSUMO, VENTA, AJUSTE
    cantidad = Column(Float, nullable=False)
    referencia = Column(String(100))            # ej: número de OC, OV u OP relacionada
    usuario_id = Column(Integer, ForeignKey("usuarios.id"), nullable=True)
    fecha = Column(DateTime, default=datetime.now)

    lote = relationship("LoteInventario")


# ══════════════════════════════════════════════════════════════════
#  RECETAS Y PRODUCCIÓN
# ══════════════════════════════════════════════════════════════════
class Receta(Base):
    """La 'fórmula' para fabricar un producto terminado."""
    __tablename__ = "recetas"

    id = Column(Integer, primary_key=True)
    producto_terminado_id = Column(Integer, ForeignKey("productos.id"), nullable=False)
    descripcion = Column(Text)
    rendimiento = Column(Float, nullable=False)   # cuánto produce un lote "estándar"
    unidad_rendimiento = Column(String(20), default="L")
    activa = Column(Boolean, default=True)

    producto_terminado = relationship("Producto")
    ingredientes = relationship(
        "IngredienteReceta", back_populates="receta", cascade="all, delete-orphan"
    )


class IngredienteReceta(Base):
    """Una línea de la receta: 'para producir X, se necesita Y de este insumo'."""
    __tablename__ = "ingredientes_receta"

    id = Column(Integer, primary_key=True)
    receta_id = Column(Integer, ForeignKey("recetas.id"), nullable=False)
    insumo_id = Column(Integer, ForeignKey("productos.id"), nullable=False)
    cantidad = Column(Float, nullable=False)
    unidad = Column(String(20))

    receta = relationship("Receta", back_populates="ingredientes")
    insumo = relationship("Producto")


class OrdenProduccion(Base):
    """Un lote de fabricación en curso o ya terminado."""
    __tablename__ = "ordenes_produccion"

    id = Column(Integer, primary_key=True)
    numero = Column(String(20), unique=True, nullable=False)          # ej: OP-0001
    receta_id = Column(Integer, ForeignKey("recetas.id"), nullable=False)
    numero_lote = Column(String(40), unique=True, nullable=False)
    cantidad_planeada = Column(Float, nullable=False)
    cantidad_real = Column(Float, nullable=True)
    fecha_inicio = Column(Date, default=date.today)
    fecha_fin = Column(Date, nullable=True)
    estado = Column(String(20), default="INICIADA")   # INICIADA | EN_PROCESO | COMPLETADA
    observaciones = Column(Text)
    creado_por = Column(Integer, ForeignKey("usuarios.id"))

    receta = relationship("Receta")


class Merma(Base):
    """Pérdida registrada durante una producción (evaporación, derrame, etc.)."""
    __tablename__ = "mermas"

    id = Column(Integer, primary_key=True)
    orden_id = Column(Integer, ForeignKey("ordenes_produccion.id"), nullable=False)
    cantidad = Column(Float, nullable=False)
    causa = Column(String(200))
    fecha = Column(DateTime, default=datetime.now)


# ══════════════════════════════════════════════════════════════════
#  VENTAS
# ══════════════════════════════════════════════════════════════════
class Cliente(Base):
    __tablename__ = "clientes"

    id = Column(Integer, primary_key=True)
    tipo = Column(String(15), nullable=False)   # NATURAL | JURIDICA
    nombre = Column(String(150), nullable=False)
    documento = Column(String(15), unique=True)  # DNI o RUC
    telefono = Column(String(20))
    email = Column(String(100))
    activo = Column(Boolean, default=True)


class OrdenVenta(Base):
    __tablename__ = "ordenes_venta"

    id = Column(Integer, primary_key=True)
    numero = Column(String(20), unique=True, nullable=False)   # ej: OV-0001
    cliente_id = Column(Integer, ForeignKey("clientes.id"), nullable=False)
    fecha = Column(Date, default=date.today)
    total = Column(Float, default=0.0)
    observaciones = Column(Text)
    creado_por = Column(Integer, ForeignKey("usuarios.id"))

    cliente = relationship("Cliente")
    detalles = relationship("DetalleVenta", back_populates="orden", cascade="all, delete-orphan")


class DetalleVenta(Base):
    """
    Una línea de venta. Puede haber varias líneas para el MISMO
    producto si tuvo que salir de dos lotes distintos (por FIFO) —
    eso es justamente lo que da trazabilidad a la venta.
    """
    __tablename__ = "detalles_venta"

    id = Column(Integer, primary_key=True)
    orden_id = Column(Integer, ForeignKey("ordenes_venta.id"), nullable=False)
    producto_id = Column(Integer, ForeignKey("productos.id"), nullable=False)
    lote_id = Column(Integer, ForeignKey("lotes_inventario.id"), nullable=True)
    cantidad = Column(Float, nullable=False)
    precio_unitario = Column(Float, nullable=False)
    subtotal = Column(Float, nullable=False)

    orden = relationship("OrdenVenta", back_populates="detalles")
    producto = relationship("Producto")


# ══════════════════════════════════════════════════════════════════
#  COSTOS
# ══════════════════════════════════════════════════════════════════
class CostoProduccion(Base):
    """
    Se crea automáticamente cuando se CIERRA una orden de producción
    (ver logica_produccion.py). Junta el costo de insumos + mano de
    obra + indirectos, y calcula el margen respecto al precio de venta.
    """
    __tablename__ = "costos_produccion"

    id = Column(Integer, primary_key=True)
    orden_id = Column(Integer, ForeignKey("ordenes_produccion.id"), unique=True, nullable=False)
    costo_insumos = Column(Float, default=0.0)
    costo_mano_obra = Column(Float, default=0.0)
    costos_indirectos = Column(Float, default=0.0)
    costo_total = Column(Float, default=0.0)
    costo_unitario = Column(Float, default=0.0)
    margen_unitario = Column(Float, default=0.0)
    margen_porcentaje = Column(Float, default=0.0)
    creado_en = Column(DateTime, default=datetime.now)

    orden = relationship("OrdenProduccion")


# ══════════════════════════════════════════════════════════════════
#  PARÁMETROS DEL SISTEMA
# ══════════════════════════════════════════════════════════════════
class ParametroSistema(Base):
    """
    Tabla genérica de "clave -> valor" para guardar datos sueltos de
    configuración que no ameritan su propia tabla — por ejemplo, el
    capital inicial con el que arrancó el negocio.

    Se guarda todo como texto (String) a propósito, para mantener la
    tabla simple: cada pantalla que lee un parámetro decide si lo
    convierte a número, fecha, etc. Ver logica_configuracion.py.

    Nota: esto es un lugar simple para guardar un dato de referencia,
    NO un módulo de Tesorería/contabilidad completo (eso implicaría
    registrar ingresos, egresos y saldo en el tiempo — una posible
    ampliación futura, ver GUIA_ARQUITECTURA.md).
    """
    __tablename__ = "parametros_sistema"

    id = Column(Integer, primary_key=True)
    clave = Column(String(50), unique=True, nullable=False)
    valor = Column(String(200), nullable=False)
