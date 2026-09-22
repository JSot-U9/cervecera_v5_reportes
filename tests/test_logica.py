"""
test_logica.py
==============
Pruebas automáticas de la lógica de negocio.

Ejecutar con:
    pytest

Qué se prueba aquí (y qué NO):
  ✅  Seguridad       — hash y verificación de contraseñas
  ✅  Autenticación   — login correcto, contraseña mal, usuario inactivo
  ✅  Inventario      — crear lotes, FIFO, stock insuficiente, ajustes
  ✅  Compras         — registrar orden, numeración correlativa, stock
  ✅  Ventas          — registrar venta, descuento de stock, stock insuficiente
  ✅  Producción      — ciclo completo, cálculo de costos, errores de estado
  ❌  Interfaz gráfica — difícil de probar de forma automática (ver GUIA_ARQUITECTURA.md)

Base de datos de prueba:
  Los tests usan una base de datos SQLite EN MEMORIA, completamente separada
  del archivo cervecera.db. Cada test arranca con tablas vacías y limpias
  (el fixture 'base_de_datos_limpia' se encarga de esto).

  IMPORTANTE: el parche del motor de base de datos (las tres líneas al principio
  de este módulo, antes de los imports de la app) debe hacerse ANTES de importar
  cualquier módulo de lógica, porque esos módulos llaman a nueva_sesion() en
  tiempo de ejecución y la función busca SesionLocal en el espacio de nombres
  de app.basedatos. Si se parchea antes, todos los tests usan la BD en memoria.
"""

# ── Parche del motor ANTES de importar cualquier módulo de la app ──────────
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
import app.basedatos as _bd

_TEST_ENGINE = create_engine("sqlite:///:memory:", connect_args={"check_same_thread": False})
_bd.engine       = _TEST_ENGINE
_bd.SesionLocal  = sessionmaker(bind=_TEST_ENGINE, expire_on_commit=False)
# ───────────────────────────────────────────────────────────────────────────

import pytest
from datetime import date, timedelta

from app.basedatos import Base, nueva_sesion
from app.modelos import (
    Usuario, Proveedor, Producto, Cliente,
    Receta, IngredienteReceta, LoteInventario, CostoProduccion,
)
from app.seguridad import hash_contrasena, verificar_contrasena
from app.logica_autenticacion import (
    iniciar_sesion, ErrorAutenticacion, crear_usuario,
    desactivar_usuario, reactivar_usuario,
)
from app.logica_inventario import (
    crear_lote, stock_total, consumir_fifo, StockInsuficiente,
    ajustar_stock, productos_bajo_minimo, lotes_proximos_a_vencer,
    desactivar_producto, reactivar_producto, lotes_con_stock_de_producto,
)
from app.logica_compras import registrar_compra
from app.logica_ventas import registrar_venta
from app.logica_produccion import crear_orden, iniciar_proceso, cerrar_orden
from app.sesion import sesion_actual


# ══════════════════════════════════════════════════════════════════
#  FIXTURES
# ══════════════════════════════════════════════════════════════════

@pytest.fixture(autouse=True)
def base_de_datos_limpia():
    """
    Crea todas las tablas ANTES de cada test y las elimina AL TERMINAR.
    Al ser autouse=True, se aplica automáticamente a todos los tests
    sin necesidad de declararlo explícitamente.
    """
    import app.modelos  # noqa: F401 — necesario para registrar los modelos en Base
    Base.metadata.create_all(_TEST_ENGINE)
    yield
    sesion_actual.cerrar()          # por si algún test dejó sesión abierta
    Base.metadata.drop_all(_TEST_ENGINE)


@pytest.fixture
def db():
    """Sesión de base de datos para usar directamente en los tests."""
    s = nueva_sesion()
    yield s
    s.close()


@pytest.fixture
def usuario_admin(db):
    u = Usuario(
        usuario="admin_test",
        nombre_completo="Admin de Prueba",
        rol="ADMIN",
        contrasena_hash=hash_contrasena("clave123"),
        activo=True,
    )
    db.add(u)
    db.commit()
    db.refresh(u)
    return u


@pytest.fixture
def proveedor(db):
    p = Proveedor(razon_social="Proveedor Test S.A.C.", ruc="20999999999", activo=True)
    db.add(p)
    db.commit()
    db.refresh(p)
    return p


@pytest.fixture
def insumo(db):
    p = Producto(
        codigo="INS-T01", nombre="Malta Test",
        tipo="Insumo", unidad_medida="kg", stock_minimo=10.0, activo=True,
    )
    db.add(p)
    db.commit()
    db.refresh(p)
    return p


@pytest.fixture
def producto_terminado(db):
    p = Producto(
        codigo="PRD-T01", nombre="Cerveza Test",
        tipo="Producto terminado", unidad_medida="L",
        precio_venta=50.0, stock_minimo=5.0, activo=True,
    )
    db.add(p)
    db.commit()
    db.refresh(p)
    return p


@pytest.fixture
def cliente(db):
    c = Cliente(tipo="NATURAL", nombre="Cliente Test", documento="99999999", activo=True)
    db.add(c)
    db.commit()
    db.refresh(c)
    return c


@pytest.fixture
def receta(db, insumo, producto_terminado):
    """
    Receta de prueba: rinde 100 L y necesita 10 kg de insumo.
    Factor de escala: si se producen 80 L reales → se consumen 8 kg.
    """
    r = Receta(
        producto_terminado_id=producto_terminado.id,
        descripcion="Receta de prueba",
        rendimiento=100.0,
        unidad_rendimiento="L",
        activa=True,
    )
    db.add(r)
    db.flush()
    db.add(IngredienteReceta(receta_id=r.id, insumo_id=insumo.id, cantidad=10.0, unidad="kg"))
    db.commit()
    db.refresh(r)
    return r


# ══════════════════════════════════════════════════════════════════
#  1) SEGURIDAD — hash de contraseñas
# ══════════════════════════════════════════════════════════════════

class TestSeguridad:

    def test_hash_no_guarda_texto_plano(self):
        h = hash_contrasena("mi_secreto")
        assert "mi_secreto" not in h

    def test_verificar_contrasena_correcta(self):
        h = hash_contrasena("mi_clave")
        assert verificar_contrasena("mi_clave", h) is True

    def test_verificar_contrasena_incorrecta(self):
        h = hash_contrasena("mi_clave")
        assert verificar_contrasena("otra_clave", h) is False

    def test_cada_hash_tiene_sal_distinta(self):
        """
        La misma contraseña debe generar hashes distintos (por la sal aleatoria).
        Si fueran iguales, un atacante podría usar tablas rainbow.
        """
        h1 = hash_contrasena("igual")
        h2 = hash_contrasena("igual")
        assert h1 != h2
        # Pero ambos deben verificarse correctamente
        assert verificar_contrasena("igual", h1)
        assert verificar_contrasena("igual", h2)

    def test_formato_invalido_devuelve_false(self):
        """Un hash sin '$' no debe provocar excepción — solo devolver False."""
        assert verificar_contrasena("clave", "hashsinformato") is False

    def test_hash_vacio_no_se_verifica(self):
        assert verificar_contrasena("clave", "") is False


# ══════════════════════════════════════════════════════════════════
#  2) AUTENTICACIÓN
# ══════════════════════════════════════════════════════════════════

class TestAutenticacion:

    def test_login_exitoso_devuelve_datos_del_usuario(self, usuario_admin):
        datos = iniciar_sesion("admin_test", "clave123")
        assert datos["usuario"] == "admin_test"
        assert datos["rol"] == "ADMIN"

    def test_login_exitoso_activa_sesion(self, usuario_admin):
        iniciar_sesion("admin_test", "clave123")
        assert sesion_actual.hay_sesion_activa
        assert sesion_actual.usuario == "admin_test"

    def test_login_contrasena_incorrecta(self, usuario_admin):
        with pytest.raises(ErrorAutenticacion):
            iniciar_sesion("admin_test", "MAL_PASSWORD")

    def test_login_usuario_inexistente(self):
        with pytest.raises(ErrorAutenticacion):
            iniciar_sesion("no_existe", "cualquiera")

    def test_login_usuario_inactivo(self, db, usuario_admin):
        usuario_admin.activo = False
        db.commit()
        with pytest.raises(ErrorAutenticacion):
            iniciar_sesion("admin_test", "clave123")

    def test_login_campos_vacios_lanza_error(self):
        with pytest.raises(ErrorAutenticacion):
            iniciar_sesion("", "")

    def test_crear_usuario_nuevo(self):
        u = crear_usuario("vendedor1", "Vendedor Uno", "pass456", "VENTAS")
        assert u.id is not None
        assert u.rol == "VENTAS"
        assert u.activo is True

    def test_crear_usuario_duplicado_lanza_error(self, usuario_admin):
        with pytest.raises(ErrorAutenticacion):
            crear_usuario("admin_test", "Otro Admin", "clave", "ADMIN")

    def test_desactivar_usuario(self, db, usuario_admin):
        desactivar_usuario(usuario_admin.id)
        db.refresh(usuario_admin)
        assert usuario_admin.activo is False

    def test_reactivar_usuario(self, db, usuario_admin):
        desactivar_usuario(usuario_admin.id)
        reactivar_usuario(usuario_admin.id)
        db.refresh(usuario_admin)
        assert usuario_admin.activo is True

    def test_desactivar_usuario_ya_inactivo_lanza_error(self, db, usuario_admin):
        desactivar_usuario(usuario_admin.id)
        with pytest.raises(ErrorAutenticacion):
            desactivar_usuario(usuario_admin.id)


# ══════════════════════════════════════════════════════════════════
#  3) INVENTARIO — lotes y FIFO
# ══════════════════════════════════════════════════════════════════

class TestInventario:

    def test_crear_lote_registra_stock(self, db, insumo):
        crear_lote(db, producto_id=insumo.id, numero_lote="L-001",
                   cantidad=50.0, costo_unitario=5.0)
        db.commit()
        assert stock_total(db, insumo.id) == 50.0

    def test_stock_cero_si_no_hay_lotes(self, db, insumo):
        assert stock_total(db, insumo.id) == 0.0

    def test_stock_suma_varios_lotes(self, db, insumo):
        crear_lote(db, producto_id=insumo.id, numero_lote="L-A", cantidad=30.0)
        crear_lote(db, producto_id=insumo.id, numero_lote="L-B", cantidad=20.0)
        db.commit()
        assert stock_total(db, insumo.id) == 50.0

    def test_fifo_consume_el_lote_mas_antiguo_primero(self, db, insumo):
        """
        Con dos lotes, FIFO debe empezar por el de fecha_ingreso más antigua.
        """
        lote_viejo = LoteInventario(
            numero_lote="L-VIEJO", producto_id=insumo.id,
            fecha_ingreso=date.today() - timedelta(days=5),
            cantidad_inicial=30.0, cantidad_disponible=30.0,
            costo_unitario=4.0, estado="DISPONIBLE",
        )
        lote_nuevo = LoteInventario(
            numero_lote="L-NUEVO", producto_id=insumo.id,
            fecha_ingreso=date.today(),
            cantidad_inicial=30.0, cantidad_disponible=30.0,
            costo_unitario=6.0, estado="DISPONIBLE",
        )
        db.add_all([lote_viejo, lote_nuevo])
        db.commit()

        consumidos = consumir_fifo(db, insumo.id, 20.0, "CONSUMO")
        db.commit()

        assert consumidos[0][0].numero_lote == "L-VIEJO"
        assert consumidos[0][1] == 20.0        # tomó todo de L-VIEJO
        assert len(consumidos) == 1             # no necesitó el segundo

    def test_fifo_pasa_al_siguiente_lote_si_el_primero_no_alcanza(self, db, insumo):
        lote_a = LoteInventario(
            numero_lote="L-A", producto_id=insumo.id,
            fecha_ingreso=date.today() - timedelta(days=1),
            cantidad_inicial=5.0, cantidad_disponible=5.0,
            costo_unitario=4.0, estado="DISPONIBLE",
        )
        lote_b = LoteInventario(
            numero_lote="L-B", producto_id=insumo.id,
            fecha_ingreso=date.today(),
            cantidad_inicial=10.0, cantidad_disponible=10.0,
            costo_unitario=5.0, estado="DISPONIBLE",
        )
        db.add_all([lote_a, lote_b])
        db.commit()

        consumidos = consumir_fifo(db, insumo.id, 8.0, "CONSUMO")
        db.commit()

        assert len(consumidos) == 2
        assert consumidos[0][1] == 5.0    # todo el lote A
        assert consumidos[1][1] == 3.0    # los 3 restantes del lote B

    def test_fifo_marca_lote_agotado_cuando_llega_a_cero(self, db, insumo):
        lote = LoteInventario(
            numero_lote="L-AGO", producto_id=insumo.id,
            cantidad_inicial=10.0, cantidad_disponible=10.0,
            costo_unitario=5.0, estado="DISPONIBLE",
        )
        db.add(lote)
        db.commit()

        consumir_fifo(db, insumo.id, 10.0, "CONSUMO")
        db.commit()
        db.refresh(lote)

        assert lote.estado == "AGOTADO"
        assert lote.cantidad_disponible == 0.0

    def test_stock_insuficiente_lanza_excepcion(self, db, insumo):
        crear_lote(db, producto_id=insumo.id, numero_lote="L-POCO",
                   cantidad=5.0, costo_unitario=3.0)
        db.commit()
        with pytest.raises(StockInsuficiente):
            consumir_fifo(db, insumo.id, 100.0, "CONSUMO")

    def test_stock_cero_lanza_stock_insuficiente(self, db, insumo):
        with pytest.raises(StockInsuficiente):
            consumir_fifo(db, insumo.id, 1.0, "CONSUMO")

    def test_ajustar_stock_hacia_arriba(self, db, insumo):
        crear_lote(db, producto_id=insumo.id, numero_lote="L-AJU",
                   cantidad=20.0, costo_unitario=4.0)
        db.commit()
        lote = db.query(LoteInventario).filter_by(numero_lote="L-AJU").first()
        ajustar_stock(db, lote.id, 30.0, "Conteo físico positivo")
        db.commit()
        db.refresh(lote)
        assert lote.cantidad_disponible == 30.0
        assert lote.estado == "DISPONIBLE"

    def test_ajustar_stock_a_cero_marca_agotado(self, db, insumo):
        crear_lote(db, producto_id=insumo.id, numero_lote="L-AGO2",
                   cantidad=10.0, costo_unitario=4.0)
        db.commit()
        lote = db.query(LoteInventario).filter_by(numero_lote="L-AGO2").first()
        ajustar_stock(db, lote.id, 0.0, "Error de conteo")
        db.commit()
        db.refresh(lote)
        assert lote.estado == "AGOTADO"

    def test_productos_bajo_minimo_detecta_faltante(self, db, insumo):
        """
        insumo tiene stock_minimo=10. Con sólo 2 kg debe aparecer en la lista.
        """
        crear_lote(db, producto_id=insumo.id, numero_lote="L-BAJO",
                   cantidad=2.0, costo_unitario=5.0)
        db.commit()
        resultado = productos_bajo_minimo(db)
        ids_bajos = [r["id"] for r in resultado]
        assert insumo.id in ids_bajos

    def test_productos_bajo_minimo_no_incluye_stock_suficiente(self, db, insumo):
        crear_lote(db, producto_id=insumo.id, numero_lote="L-OK",
                   cantidad=50.0, costo_unitario=5.0)   # 50 > stock_minimo=10
        db.commit()
        resultado = productos_bajo_minimo(db)
        ids_bajos = [r["id"] for r in resultado]
        assert insumo.id not in ids_bajos

    def test_lotes_proximos_a_vencer(self, db, insumo):
        lote = LoteInventario(
            numero_lote="L-VENC", producto_id=insumo.id,
            cantidad_inicial=10.0, cantidad_disponible=10.0,
            costo_unitario=5.0, estado="DISPONIBLE",
            fecha_vencimiento=date.today() + timedelta(days=10),  # vence en 10 días
        )
        db.add(lote)
        db.commit()
        resultado = lotes_proximos_a_vencer(db, dias=30)
        numeros = [l.numero_lote for l in resultado]
        assert "L-VENC" in numeros

    def test_lotes_sin_fecha_vencimiento_no_aparecen_en_proximos(self, db, insumo):
        lote = LoteInventario(
            numero_lote="L-SIN-VEN", producto_id=insumo.id,
            cantidad_inicial=10.0, cantidad_disponible=10.0,
            costo_unitario=5.0, estado="DISPONIBLE",
            fecha_vencimiento=None,
        )
        db.add(lote)
        db.commit()
        resultado = lotes_proximos_a_vencer(db, dias=30)
        numeros = [l.numero_lote for l in resultado]
        assert "L-SIN-VEN" not in numeros

    def test_desactivar_producto(self, db, insumo):
        desactivar_producto(db, insumo.id)
        db.refresh(insumo)
        assert insumo.activo is False

    def test_reactivar_producto(self, db, insumo):
        desactivar_producto(db, insumo.id)
        reactivar_producto(db, insumo.id)
        db.refresh(insumo)
        assert insumo.activo is True

    def test_desactivar_producto_ya_inactivo_lanza_error(self, db, insumo):
        desactivar_producto(db, insumo.id)
        with pytest.raises(ValueError):
            desactivar_producto(db, insumo.id)

    def test_desactivar_producto_inexistente_lanza_error(self, db):
        with pytest.raises(ValueError):
            desactivar_producto(db, 99999)

    def test_lotes_con_stock_de_producto_cuenta_solo_disponibles(self, db, insumo):
        crear_lote(db, producto_id=insumo.id, numero_lote="L-A",
                   cantidad=20.0, costo_unitario=5.0)
        crear_lote(db, producto_id=insumo.id, numero_lote="L-B",
                   cantidad=15.0, costo_unitario=5.0)
        lote_agotado = LoteInventario(
            numero_lote="L-AGOTADO", producto_id=insumo.id,
            cantidad_inicial=10.0, cantidad_disponible=0.0,
            costo_unitario=5.0, estado="AGOTADO",
        )
        db.add(lote_agotado)
        db.commit()
        assert lotes_con_stock_de_producto(db, insumo.id) == 2

    def test_lotes_con_stock_de_producto_sin_lotes_es_cero(self, db, producto_terminado):
        assert lotes_con_stock_de_producto(db, producto_terminado.id) == 0


# ══════════════════════════════════════════════════════════════════
#  4) COMPRAS
# ══════════════════════════════════════════════════════════════════

class TestCompras:

    def test_registrar_compra_crea_orden(self, proveedor, insumo):
        orden = registrar_compra(
            proveedor_id=proveedor.id,
            items=[{"producto_id": insumo.id, "cantidad": 100.0, "precio_unitario": 5.0}],
        )
        assert orden.id is not None
        assert orden.numero.startswith("OC-")

    def test_total_calculado_correctamente(self, proveedor, insumo):
        orden = registrar_compra(
            proveedor_id=proveedor.id,
            items=[
                {"producto_id": insumo.id, "cantidad": 10.0, "precio_unitario": 4.0},
            ],
        )
        assert orden.total == pytest.approx(40.0)

    def test_compra_actualiza_stock(self, db, proveedor, insumo):
        registrar_compra(
            proveedor_id=proveedor.id,
            items=[{"producto_id": insumo.id, "cantidad": 50.0, "precio_unitario": 5.0}],
        )
        assert stock_total(db, insumo.id) == 50.0

    def test_numeracion_correlativa(self, proveedor, insumo):
        orden1 = registrar_compra(
            proveedor_id=proveedor.id,
            items=[{"producto_id": insumo.id, "cantidad": 10.0, "precio_unitario": 5.0}],
        )
        orden2 = registrar_compra(
            proveedor_id=proveedor.id,
            items=[{"producto_id": insumo.id, "cantidad": 20.0, "precio_unitario": 5.0}],
        )
        n1 = int(orden1.numero.split("-")[1])
        n2 = int(orden2.numero.split("-")[1])
        assert n2 == n1 + 1

    def test_compra_multiples_productos_un_lote_por_producto(self, db, proveedor, insumo):
        insumo2 = Producto(
            codigo="INS-T02", nombre="Lúpulo Test",
            tipo="Insumo", unidad_medida="kg", stock_minimo=5.0, activo=True,
        )
        db.add(insumo2)
        db.commit()
        db.refresh(insumo2)

        registrar_compra(
            proveedor_id=proveedor.id,
            items=[
                {"producto_id": insumo.id,  "cantidad": 30.0, "precio_unitario": 4.0},
                {"producto_id": insumo2.id, "cantidad": 10.0, "precio_unitario": 60.0},
            ],
        )
        assert stock_total(db, insumo.id)  == 30.0
        assert stock_total(db, insumo2.id) == 10.0


# ══════════════════════════════════════════════════════════════════
#  5) VENTAS
# ══════════════════════════════════════════════════════════════════

class TestVentas:

    def _cargar_stock(self, db, producto, cantidad, numero="LV-001"):
        crear_lote(db, producto_id=producto.id, numero_lote=numero,
                   cantidad=cantidad, costo_unitario=30.0)
        db.commit()

    def test_registrar_venta_crea_orden(self, db, producto_terminado, cliente):
        self._cargar_stock(db, producto_terminado, 50.0)
        orden = registrar_venta(
            cliente_id=cliente.id,
            items=[{"producto_id": producto_terminado.id,
                    "cantidad": 10.0, "precio_unitario": 50.0}],
        )
        assert orden.id is not None
        assert orden.numero.startswith("OV-")

    def test_venta_descuenta_stock(self, db, producto_terminado, cliente):
        self._cargar_stock(db, producto_terminado, 50.0)
        registrar_venta(
            cliente_id=cliente.id,
            items=[{"producto_id": producto_terminado.id,
                    "cantidad": 20.0, "precio_unitario": 50.0}],
        )
        assert stock_total(db, producto_terminado.id) == 30.0

    def test_venta_total_calculado_correctamente(self, db, producto_terminado, cliente):
        self._cargar_stock(db, producto_terminado, 50.0)
        orden = registrar_venta(
            cliente_id=cliente.id,
            items=[{"producto_id": producto_terminado.id,
                    "cantidad": 10.0, "precio_unitario": 45.0}],
        )
        assert orden.total == pytest.approx(450.0)

    def test_venta_sin_stock_lanza_excepcion(self, cliente, producto_terminado):
        with pytest.raises(StockInsuficiente):
            registrar_venta(
                cliente_id=cliente.id,
                items=[{"producto_id": producto_terminado.id,
                        "cantidad": 100.0, "precio_unitario": 50.0}],
            )

    def test_venta_stock_parcial_no_registra_nada(self, db, producto_terminado, cliente):
        """
        Si un item no tiene stock suficiente, la venta COMPLETA debe fallar
        (no se registra nada a medias — atomicidad).
        """
        self._cargar_stock(db, producto_terminado, 5.0)
        stock_antes = stock_total(db, producto_terminado.id)

        with pytest.raises(StockInsuficiente):
            registrar_venta(
                cliente_id=cliente.id,
                items=[{"producto_id": producto_terminado.id,
                        "cantidad": 100.0, "precio_unitario": 50.0}],
            )
        # El stock no debe haber cambiado
        assert stock_total(db, producto_terminado.id) == stock_antes

    def test_numeracion_correlativa_ventas(self, db, producto_terminado, cliente):
        self._cargar_stock(db, producto_terminado, 100.0, "LV-MULTI")
        ov1 = registrar_venta(
            cliente_id=cliente.id,
            items=[{"producto_id": producto_terminado.id,
                    "cantidad": 5.0, "precio_unitario": 50.0}],
        )
        ov2 = registrar_venta(
            cliente_id=cliente.id,
            items=[{"producto_id": producto_terminado.id,
                    "cantidad": 5.0, "precio_unitario": 50.0}],
        )
        n1 = int(ov1.numero.split("-")[1])
        n2 = int(ov2.numero.split("-")[1])
        assert n2 == n1 + 1


# ══════════════════════════════════════════════════════════════════
#  6) PRODUCCIÓN — ciclo completo
# ══════════════════════════════════════════════════════════════════

class TestProduccion:

    def test_crear_orden_inicia_en_estado_iniciada(self, receta):
        orden = crear_orden(receta_id=receta.id, cantidad_planeada=80.0,
                            numero_lote="LP-001")
        assert orden.estado == "INICIADA"
        assert orden.numero.startswith("OP-")

    def test_iniciar_proceso_cambia_estado_a_en_proceso(self, receta):
        orden = crear_orden(receta_id=receta.id, cantidad_planeada=80.0,
                            numero_lote="LP-002")
        orden = iniciar_proceso(orden.id)
        assert orden.estado == "EN_PROCESO"

    def test_iniciar_proceso_desde_estado_invalido_lanza_error(self, receta):
        orden = crear_orden(receta_id=receta.id, cantidad_planeada=80.0,
                            numero_lote="LP-003")
        iniciar_proceso(orden.id)           # pasa a EN_PROCESO
        with pytest.raises(ValueError):
            iniciar_proceso(orden.id)       # ya no está INICIADA

    def test_cerrar_orden_cambia_estado_a_completada(self, db, insumo, receta):
        # La receta pide 10 kg para 100 L. Producir 100 L consume 10 kg.
        crear_lote(db, producto_id=insumo.id, numero_lote="LI-001",
                   cantidad=20.0, costo_unitario=4.0)
        db.commit()

        orden = crear_orden(receta_id=receta.id, cantidad_planeada=100.0,
                            numero_lote="LP-004")
        iniciar_proceso(orden.id)
        orden = cerrar_orden(orden.id, cantidad_real=100.0, cantidad_merma=0.0,
                             causa_merma="", costo_mano_obra=100.0,
                             costos_indirectos=50.0)
        assert orden.estado == "COMPLETADA"

    def test_cerrar_orden_crea_stock_de_producto_terminado(self, db, insumo, receta,
                                                            producto_terminado):
        crear_lote(db, producto_id=insumo.id, numero_lote="LI-002",
                   cantidad=20.0, costo_unitario=4.0)
        db.commit()

        orden = crear_orden(receta_id=receta.id, cantidad_planeada=100.0,
                            numero_lote="LP-005")
        iniciar_proceso(orden.id)
        cerrar_orden(orden.id, cantidad_real=100.0, cantidad_merma=0.0,
                     causa_merma="", costo_mano_obra=100.0, costos_indirectos=50.0)

        assert stock_total(db, producto_terminado.id) == 100.0

    def test_cerrar_orden_consume_insumos_segun_factor_escala(self, db, insumo, receta):
        """
        Receta: 10 kg para 100 L. Si se producen 80 L (factor 0.8),
        se deben consumir 8 kg.
        """
        crear_lote(db, producto_id=insumo.id, numero_lote="LI-003",
                   cantidad=20.0, costo_unitario=4.0)
        db.commit()

        orden = crear_orden(receta_id=receta.id, cantidad_planeada=80.0,
                            numero_lote="LP-006")
        iniciar_proceso(orden.id)
        cerrar_orden(orden.id, cantidad_real=80.0, cantidad_merma=0.0,
                     causa_merma="", costo_mano_obra=100.0, costos_indirectos=50.0)

        # 20 kg - 8 kg consumidos = 12 kg restantes
        assert stock_total(db, insumo.id) == pytest.approx(12.0, abs=0.01)

    def test_cerrar_orden_sin_stock_lanza_stock_insuficiente(self, receta):
        """Si no hay insumos, cerrar la orden debe fallar con StockInsuficiente."""
        orden = crear_orden(receta_id=receta.id, cantidad_planeada=80.0,
                            numero_lote="LP-007")
        iniciar_proceso(orden.id)
        with pytest.raises(StockInsuficiente):
            cerrar_orden(orden.id, cantidad_real=80.0, cantidad_merma=0.0,
                         causa_merma="", costo_mano_obra=100.0, costos_indirectos=50.0)

    def test_cerrar_orden_registra_costo_de_produccion(self, db, insumo, receta):
        """
        Al cerrar, debe quedar un registro en costos_produccion con los
        valores calculados correctamente.

        Cálculo esperado:
          costo_insumos = 10 kg * 4 S/kg = 40 S/
          costo_total   = 40 + 200 (M.O.) + 100 (indirectos) = 340 S/
          costo_unitario = 340 / 100 L = 3.40 S/L
        """
        crear_lote(db, producto_id=insumo.id, numero_lote="LI-004",
                   cantidad=20.0, costo_unitario=4.0)
        db.commit()

        orden = crear_orden(receta_id=receta.id, cantidad_planeada=100.0,
                            numero_lote="LP-008")
        iniciar_proceso(orden.id)
        orden = cerrar_orden(orden.id, cantidad_real=100.0, cantidad_merma=0.0,
                             causa_merma="", costo_mano_obra=200.0,
                             costos_indirectos=100.0)

        with nueva_sesion() as s:
            costo = s.query(CostoProduccion).filter_by(orden_id=orden.id).first()

        assert costo is not None
        assert costo.costo_insumos    == pytest.approx(40.0,  abs=0.01)
        assert costo.costo_total      == pytest.approx(340.0, abs=0.01)
        assert costo.costo_unitario   == pytest.approx(3.40,  abs=0.01)

    def test_cerrar_orden_calcula_margen_correctamente(self, db, insumo, receta,
                                                        producto_terminado):
        """
        precio_venta del producto terminado = 50 S/L (definido en el fixture).
        costo_unitario = 340 / 100 = 3.40 S/L (ver test anterior).
        margen_unitario = 50 - 3.40 = 46.60 S/L
        margen_porcentaje = 46.60 / 50 * 100 = 93.2%
        """
        crear_lote(db, producto_id=insumo.id, numero_lote="LI-005",
                   cantidad=20.0, costo_unitario=4.0)
        db.commit()

        orden = crear_orden(receta_id=receta.id, cantidad_planeada=100.0,
                            numero_lote="LP-009")
        iniciar_proceso(orden.id)
        orden = cerrar_orden(orden.id, cantidad_real=100.0, cantidad_merma=0.0,
                             causa_merma="", costo_mano_obra=200.0,
                             costos_indirectos=100.0)

        with nueva_sesion() as s:
            costo = s.query(CostoProduccion).filter_by(orden_id=orden.id).first()

        assert costo.margen_unitario   == pytest.approx(46.60, abs=0.01)
        assert costo.margen_porcentaje == pytest.approx(93.2,  abs=0.1)

    def test_numeracion_correlativa_ordenes(self, receta):
        op1 = crear_orden(receta_id=receta.id, cantidad_planeada=50.0,
                          numero_lote="LP-N1")
        op2 = crear_orden(receta_id=receta.id, cantidad_planeada=50.0,
                          numero_lote="LP-N2")
        n1 = int(op1.numero.split("-")[1])
        n2 = int(op2.numero.split("-")[1])
        assert n2 == n1 + 1
