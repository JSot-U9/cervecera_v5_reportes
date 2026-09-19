"""
test_smoke_ui.py
=================
Smoke test headless (QT_QPA_PLATFORM=offscreen, sin necesidad de Xvfb)
para el rediseño UI/UX — PARTE 1 (badges de estado + EstadoVacio en
tablas) y PARTE 2 (breadcrumb de pestaña interna en el header).

No reemplaza test_logica.py: aquí NO se prueba lógica de negocio, solo
que las vistas se construyen sin errores y que los componentes nuevos
se comportan como se espera.

Ejecutar con:
    pytest tests/test_smoke_ui.py
"""

import os
os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

# ── Motor de pruebas ANTES de importar cualquier módulo de la app ─────────
# Si tests/test_logica.py ya corrió su propio parche en este mismo
# proceso (pytest importa todos los módulos de test antes de
# ejecutarlos), _bd.engine ya apunta a UN motor SQLite en memoria — se
# reutiliza ese mismo objeto en vez de reemplazarlo, porque el fixture
# autouse de test_logica.py quedó con una referencia directa a su
# propio motor y reemplazar _bd.engine aquí lo dejaría reventado por
# un "no such table" al correr ambos archivos juntos.
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
import app.basedatos as _bd

if ":memory:" in str(_bd.engine.url):
    _TEST_ENGINE = _bd.engine
else:
    _TEST_ENGINE = create_engine("sqlite:///:memory:", connect_args={"check_same_thread": False})
    _bd.engine = _TEST_ENGINE
    _bd.SesionLocal = sessionmaker(bind=_TEST_ENGINE, expire_on_commit=False)
# ───────────────────────────────────────────────────────────────────────────

import pytest
from PySide6.QtWidgets import QApplication, QWidget, QTabWidget, QVBoxLayout

from app.basedatos import Base
import app.modelos  # noqa: F401 — registra todas las tablas en Base.metadata
from app.basedatos import nueva_sesion
from app.sesion import sesion_actual

from app.ui.widgets import (
    TablaDatos, EstadoVacio, formatear_estado, tag_para_estado,
    texto_pestana_legible, conectar_pestanas_a_header,
)


@pytest.fixture(scope="module")
def qapp():
    app = QApplication.instance() or QApplication([])
    yield app


@pytest.fixture()
def base_de_datos_limpia():
    Base.metadata.drop_all(_TEST_ENGINE)
    Base.metadata.create_all(_TEST_ENGINE)
    yield


@pytest.fixture()
def sin_sesion():
    sesion_actual.cerrar()
    yield
    sesion_actual.cerrar()


def _iniciar_como(rol: str):
    sesion_actual.iniciar(usuario_id=1, usuario="test", nombre_completo="Test", rol=rol)


# ══════════════════════════════════════════════════════════════════
#  PARTE 1 — badges de estado unificados
# ══════════════════════════════════════════════════════════════════

def test_formatear_estado_y_tag_usan_la_misma_fuente():
    assert formatear_estado("ACTIVO") == "🟢 Activo"
    assert tag_para_estado("ACTIVO") == "exito"
    assert formatear_estado("AGOTADO") == "🔴 Agotado"
    assert tag_para_estado("AGOTADO") == "alerta"
    assert formatear_estado("ALTA") == "🔴 Alta"
    assert tag_para_estado("ALTA") == "alerta"
    assert formatear_estado("BAJA") == "🟢 Baja"
    assert tag_para_estado("BAJA") == "normal"
    # Un estado desconocido no debe reventar: se devuelve tal cual /
    # con el tag neutro.
    assert formatear_estado("no_existe") == "no_existe"
    assert tag_para_estado("no_existe") == "normal"


def test_tabla_vacia_muestra_estado_vacio(qapp):
    tabla = TablaDatos(
        ["Nombre"],
        estado_vacio=EstadoVacio("📦", "Sin datos", "Descripción de prueba"),
    )
    tabla.resize(400, 300)  # dispara resizeEvent -> geometry del overlay
    # isVisibleTo(tabla), no isVisible(): la tabla nunca se muestra en
    # pantalla en este test (no hay .show()), así que isVisible() sería
    # False de todas formas por la cadena de ancestros — lo que importa
    # acá es si el overlay quedó marcado visible/oculto respecto a su
    # propio padre, que es lo que después decide qué se ve al mostrar
    # la ventana real.
    tabla.cargar_filas([])
    assert tabla._estado_vacio.isVisibleTo(tabla) is True

    tabla.cargar_filas([[1, "Producto A"]])
    assert tabla._estado_vacio.isVisibleTo(tabla) is False

    tabla.filtrar("texto-que-no-matchea-nada")
    assert tabla._estado_vacio.isVisibleTo(tabla) is True

    tabla.filtrar("")
    assert tabla._estado_vacio.isVisibleTo(tabla) is False


def test_tabla_sin_estado_vacio_no_falla(qapp):
    # Las tablas que NO reciben estado_vacio (ninguna todavía en este
    # proyecto, pero el parámetro es opcional) deben seguir funcionando
    # exactamente igual que antes.
    tabla = TablaDatos(["Nombre"])
    tabla.cargar_filas([])
    tabla.cargar_filas([[1, "Producto A"]])


# ══════════════════════════════════════════════════════════════════
#  PARTE 2 — breadcrumb de pestaña interna en el header
# ══════════════════════════════════════════════════════════════════

class _VentanaFalsa(QWidget):
    """Sustituto mínimo de VentanaPrincipal: solo necesita exponer
    actualizar_pestana_interna() para que conectar_pestanas_a_header
    la encuentre vía widget.window()."""

    def __init__(self):
        super().__init__()
        self.llamadas = []
        self.llamadas_migas = []

    def actualizar_pestana_interna(self, nombre_pestana, migas_extra=None):
        self.llamadas.append(nombre_pestana)
        self.llamadas_migas.append((nombre_pestana, migas_extra))


def test_texto_pestana_legible_quita_el_icono():
    assert texto_pestana_legible("🗂  Lotes FIFO") == "Lotes FIFO"
    assert texto_pestana_legible("👤  Usuarios") == "Usuarios"
    assert texto_pestana_legible("Sin ícono") == "Sin ícono"


def test_conectar_pestanas_a_header_actualiza_el_header(qapp):
    ventana = _VentanaFalsa()
    layout = QVBoxLayout(ventana)
    notebook = QTabWidget()
    layout.addWidget(notebook)

    notebook.addTab(QWidget(), "📊  Stock Actual")
    notebook.addTab(QWidget(), "🗂  Lotes FIFO")
    notebook.addTab(QWidget(), "📋  Movimientos")

    conectar_pestanas_a_header(notebook, notebook)

    notebook.setCurrentIndex(1)
    notebook.setCurrentIndex(2)

    assert ventana.llamadas == ["Lotes FIFO", "Movimientos"]


# ══════════════════════════════════════════════════════════════════
#  Construcción real de vistas, para 2 roles distintos
# ══════════════════════════════════════════════════════════════════

def test_vista_inventario_se_construye_para_admin_y_produccion(
    qapp, base_de_datos_limpia, sin_sesion,
):
    from app.ui.vista_inventario import VistaInventario

    # ADMIN: catálogo vacío -> EstadoVacio visible, CON botón de acción
    # (tiene permiso "entrada" en el módulo inventario).
    _iniciar_como("ADMIN")
    vista_admin = VistaInventario()
    vista_admin.resize(900, 600)
    assert vista_admin.tabla_catalogo._estado_vacio.isVisibleTo(vista_admin.tabla_catalogo) is True

    # PRODUCCION: mismo catálogo vacío -> EstadoVacio visible, SIN botón
    # de acción (ese rol solo tiene "ver" en inventario, no "entrada").
    sesion_actual.cerrar()
    _iniciar_como("PRODUCCION")
    vista_prod = VistaInventario()
    vista_prod.resize(900, 600)
    assert vista_prod.tabla_catalogo._estado_vacio.isVisibleTo(vista_prod.tabla_catalogo) is True

    # El botón de acción del EstadoVacio de "Catálogo" solo debe existir
    # para el rol que puede crear productos.
    from PySide6.QtWidgets import QPushButton
    botones_admin = vista_admin.tabla_catalogo._estado_vacio.findChildren(QPushButton)
    botones_prod = vista_prod.tabla_catalogo._estado_vacio.findChildren(QPushButton)
    assert len(botones_admin) == 1
    assert len(botones_prod) == 0


def test_cambiar_de_pestana_en_inventario_actualiza_el_header(
    qapp, base_de_datos_limpia, sin_sesion,
):
    """Reproduce, con la vista real dentro de una ventana anfitriona
    falsa, lo que pide la Parte 2: cambiar de 'Stock Actual' a 'Lotes'
    debe reflejarse en el header, no solo en la pestaña resaltada."""
    from app.ui.vista_inventario import VistaInventario

    _iniciar_como("ADMIN")
    ventana = _VentanaFalsa()
    layout = QVBoxLayout(ventana)
    vista = VistaInventario()
    layout.addWidget(vista)

    indice_lotes = next(
        i for i in range(vista.notebook.count())
        if "Lotes" in vista.notebook.tabText(i)
    )
    vista.notebook.setCurrentIndex(indice_lotes)

    assert ventana.llamadas
    assert "Lotes" in ventana.llamadas[-1]


# ══════════════════════════════════════════════════════════════════
#  PARTE 3 — vista de detalle de producto
# ══════════════════════════════════════════════════════════════════

def _crear_producto_con_historial(db):
    """Crea un producto terminado con un lote, un movimiento y una
    venta, para poder ejercer las 4 pestañas con datos reales (la de
    Inteligencia se prueba aparte porque necesita rol/tipo distintos)."""
    from datetime import date
    import app.modelos as m

    p = m.Producto(codigo="PRD-1", nombre="Anka Chida", tipo="Producto terminado",
                    unidad_medida="L", precio_venta=15, stock_minimo=20, activo=True)
    db.add(p)
    db.flush()
    lote = m.LoteInventario(numero_lote="LT-0001", producto_id=p.id,
                             fecha_ingreso=date.today(), cantidad_inicial=50,
                             cantidad_disponible=32, estado="DISPONIBLE")
    db.add(lote)
    db.flush()
    db.add(m.MovimientoInventario(lote_id=lote.id, tipo="ENTRADA",
                                   cantidad=50, referencia="OP-0001"))
    cliente = m.Cliente(tipo="NATURAL", nombre="Juan Pérez", documento="12345678")
    db.add(cliente)
    db.flush()
    ov = m.OrdenVenta(numero="OV-0001", cliente_id=cliente.id, fecha=date.today(), total=150)
    db.add(ov)
    db.flush()
    db.add(m.DetalleVenta(orden_id=ov.id, producto_id=p.id, lote_id=lote.id,
                           cantidad=10, precio_unitario=15, subtotal=150))
    db.commit()
    return p.id


def test_doble_clic_abre_el_detalle_con_los_kpis_correctos(
    qapp, base_de_datos_limpia, sin_sesion,
):
    """Reproduce el mockup: Stock actual 32, Stock mínimo 20, Estado
    🟢 Normal, con las 5 pestañas (para un rol con acceso a IA)."""
    from app.ui.vista_inventario import VistaInventario

    _iniciar_como("ADMIN")
    db = nueva_sesion()
    producto_id = _crear_producto_con_historial(db)
    db.close()

    vista = VistaInventario()
    vista._abrir_detalle_producto(producto_id)

    assert vista._stack.currentWidget() is vista._detalle_producto
    detalle = vista._detalle_producto
    assert detalle._lbl_nombre.text() == "Anka Chida"
    assert detalle.kpi_stock._lbl_valor.text() == "32.00 L"
    assert detalle.kpi_stock_minimo._lbl_valor.text() == "20.00 L"
    assert detalle.kpi_estado._lbl_valor.text() == "🟢 Normal"

    nombres_tabs = [detalle.notebook.tabText(i) for i in range(detalle.notebook.count())]
    assert len(nombres_tabs) == 5
    for esperado in ("Información", "Lotes", "Movimientos", "Ventas", "Inteligencia"):
        assert any(esperado in t for t in nombres_tabs)

    assert detalle.tabla_lotes_detalle.rowCount() == 1
    assert detalle.tabla_movimientos_detalle.rowCount() == 1
    assert detalle.tabla_ventas_detalle.rowCount() == 1

    # Navega las 5 pestañas sin que nada reviente.
    for i in range(detalle.notebook.count()):
        detalle.notebook.setCurrentIndex(i)

    # "‹ Volver" regresa a la tabla (misma instancia, sin reconstruir).
    vista._volver_de_detalle()
    assert vista._stack.currentWidget() is vista.notebook


def test_pestana_inteligencia_solo_aparece_con_acceso_al_modulo(
    qapp, base_de_datos_limpia, sin_sesion,
):
    """2 roles distintos: ADMIN tiene Centro de Inteligencia,
    INVENTARIO no (ver MODULOS_POR_ROL en app/seguridad.py) — la
    pestaña "Inteligencia" no debe existir para el segundo."""
    from app.ui.vista_inventario import VistaInventario

    with _bd.SesionLocal() as db:
        producto_id = _crear_producto_con_historial(db)

    _iniciar_como("ADMIN")
    vista_admin = VistaInventario()
    vista_admin._abrir_detalle_producto(producto_id)
    nombres_admin = [vista_admin._detalle_producto.notebook.tabText(i)
                     for i in range(vista_admin._detalle_producto.notebook.count())]
    assert any("Inteligencia" in t for t in nombres_admin)

    sesion_actual.cerrar()
    _iniciar_como("INVENTARIO")
    vista_inv = VistaInventario()
    vista_inv._abrir_detalle_producto(producto_id)
    nombres_inv = [vista_inv._detalle_producto.notebook.tabText(i)
                   for i in range(vista_inv._detalle_producto.notebook.count())]
    assert not any("Inteligencia" in t for t in nombres_inv)


def test_volver_del_detalle_actualiza_el_breadcrumb_del_header(
    qapp, base_de_datos_limpia, sin_sesion,
):
    from app.ui.vista_inventario import VistaInventario

    _iniciar_como("ADMIN")
    with _bd.SesionLocal() as db:
        producto_id = _crear_producto_con_historial(db)

    ventana = _VentanaFalsa()
    layout = QVBoxLayout(ventana)
    vista = VistaInventario()
    layout.addWidget(vista)

    vista._abrir_detalle_producto(producto_id)
    assert ventana.llamadas_migas[-1] == ("Anka Chida", ["Productos", "Anka Chida"])

    vista._volver_de_detalle()
    assert ventana.llamadas[-1] == "Stock Actual"
