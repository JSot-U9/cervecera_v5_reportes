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
    CampoFormulario, conectar_boton_a_validez,
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

    # La columna "Tipo" de Movimientos debe pasar por formatear_estado(),
    # igual que ya se hacía en Inventario principal — no el valor crudo
    # de BD ("ENTRADA") sin ícono ni capitalización.
    indice_col_tipo = next(
        i for i in range(detalle.tabla_movimientos_detalle.columnCount())
        if detalle.tabla_movimientos_detalle.horizontalHeaderItem(i).text() == "Tipo"
    )
    assert detalle.tabla_movimientos_detalle.item(0, indice_col_tipo).text() == "⬇ Entrada"

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
    assert ventana.llamadas_migas[-1] == (
        "Anka Chida · Información", ["Productos", "Anka Chida", "Información"],
    )

    # Cambiar de pestaña DENTRO del detalle también debe reflejar el
    # nombre del producto en el breadcrumb, no solo el nombre de la
    # pestaña (si no, se perdería el contexto de qué producto se está
    # viendo: "Inventario · Lotes" en vez de "Inventario · Productos ·
    # Anka Chida · Lotes").
    indice_lotes = next(
        i for i in range(vista._detalle_producto.notebook.count())
        if "Lotes" in vista._detalle_producto.notebook.tabText(i)
    )
    vista._detalle_producto.notebook.setCurrentIndex(indice_lotes)
    assert ventana.llamadas_migas[-1] == (
        "Anka Chida · Lotes", ["Productos", "Anka Chida", "Lotes"],
    )

    vista._volver_de_detalle()
    assert ventana.llamadas[-1] == "Stock Actual"


# ══════════════════════════════════════════════════════════════════
#  PARTE 4 — validación inline en formularios
# ══════════════════════════════════════════════════════════════════

def test_campo_formulario_valida_obligatorio_en_vivo(qapp):
    campo = CampoFormulario("Nombre", obligatorio=True)
    assert campo.es_valido() is False  # vacío al construirse

    campo.widget.setText("")
    campo.widget.editingFinished.emit()
    assert campo.es_valido() is False
    assert "obligatorio" in campo._lbl_error.text().lower()

    campo.widget.setText("Malta Pilsen")
    campo.widget.editingFinished.emit()
    assert campo.es_valido() is True
    assert campo._lbl_error.text() == ""


def test_campo_formulario_numero_rechaza_negativos_en_vivo(qapp):
    campo = CampoFormulario("Stock mínimo", tipo="numero", permitir_negativo=False)
    campo.widget.setText("-5")
    campo.widget.editingFinished.emit()
    assert campo.es_valido() is False
    assert "negativo" in campo._lbl_error.text().lower()

    campo.widget.setText("5")
    campo.widget.editingFinished.emit()
    assert campo.es_valido() is True


def test_campo_formulario_valida_tras_dejar_de_escribir(qapp):
    """El debounce (QTimer) también debe disparar la validación, no
    solo editingFinished — simula "dejar de escribir" sin salir del
    campo, disparando el timeout directamente en vez de esperar los
    600ms reales."""
    campo = CampoFormulario("Stock mínimo", tipo="numero", permitir_negativo=False)
    campo.widget.setText("-3")  # dispara textChanged -> arranca el temporizador
    assert campo._temporizador.isActive()
    campo._temporizador.timeout.emit()
    assert campo.es_valido() is False
    assert "negativo" in campo._lbl_error.text().lower()


def test_conectar_boton_a_validez_bloquea_hasta_corregir(qapp):
    from PySide6.QtWidgets import QPushButton

    campo_nombre = CampoFormulario("Nombre", obligatorio=True)
    campo_stock = CampoFormulario("Stock mínimo", tipo="numero", permitir_negativo=False)
    boton = QPushButton("Guardar")
    conectar_boton_a_validez(boton, [campo_nombre, campo_stock])

    assert boton.isEnabled() is False  # nombre vacío al arrancar

    campo_nombre.widget.setText("Malta")
    campo_nombre.widget.editingFinished.emit()
    assert boton.isEnabled() is True  # ambos campos válidos (stock vacío = 0.0, válido)

    campo_stock.widget.setText("-10")
    campo_stock.widget.editingFinished.emit()
    assert boton.isEnabled() is False  # se bloquea de nuevo

    campo_stock.widget.setText("10")
    campo_stock.widget.editingFinished.emit()
    assert boton.isEnabled() is True  # corregido -> se reactiva


def test_producto_con_stock_minimo_negativo_muestra_error_inline_y_bloquea_guardado(
    qapp, base_de_datos_limpia, sin_sesion,
):
    """El caso pedido explícitamente: llenar el formulario de un
    producto con un stock mínimo negativo debe mostrar el error
    inline debajo del campo y dejar "Guardar" deshabilitado hasta que
    se corrija — sin tener que hacer clic en Guardar para enterarse."""
    from app.ui.vista_inventario import VentanaProducto

    _iniciar_como("ADMIN")
    ventana = VentanaProducto(None, al_guardar=lambda: None)

    # Con el nombre puesto y el stock mínimo en su valor por defecto
    # ("0", válido), ya se podría guardar.
    ventana.campo_nombre.set("Levadura Ale")
    ventana.campo_nombre.widget.editingFinished.emit()
    assert ventana.btn_guardar.isEnabled() is True

    # Stock mínimo negativo -> error inline + botón bloqueado.
    ventana.campo_stock_minimo.widget.setText("-5")
    ventana.campo_stock_minimo.widget.editingFinished.emit()
    assert ventana.campo_stock_minimo.es_valido() is False
    assert "negativo" in ventana.campo_stock_minimo._lbl_error.text().lower()
    assert ventana.btn_guardar.isEnabled() is False

    # Se corrige -> el error inline desaparece y el botón se reactiva,
    # sin haber tocado "Guardar" en ningún momento.
    ventana.campo_stock_minimo.widget.setText("20")
    ventana.campo_stock_minimo.widget.editingFinished.emit()
    assert ventana.campo_stock_minimo.es_valido() is True
    assert ventana.campo_stock_minimo._lbl_error.text() == ""
    assert ventana.btn_guardar.isEnabled() is True


def test_ajuste_stock_cantidad_negativa_bloquea_guardado(
    qapp, base_de_datos_limpia, sin_sesion,
):
    from datetime import date
    import app.modelos as m
    from app.ui.vista_inventario import VentanaAjusteStock

    _iniciar_como("ADMIN")
    db = nueva_sesion()
    p = m.Producto(codigo="INS-1", nombre="Malta", tipo="Insumo",
                    unidad_medida="kg", stock_minimo=5, activo=True)
    db.add(p)
    db.flush()
    lote = m.LoteInventario(numero_lote="LT-0001", producto_id=p.id,
                             fecha_ingreso=date.today(), cantidad_inicial=10,
                             cantidad_disponible=10, estado="DISPONIBLE")
    db.add(lote)
    db.commit()
    lote_id = lote.id
    db.close()

    ventana = VentanaAjusteStock(None, lote_id, al_guardar=lambda: None)
    ventana.campo_motivo.set("Conteo físico")
    ventana.campo_motivo.widget.editingFinished.emit()
    assert ventana.btn_guardar.isEnabled() is True  # cantidad ya viene con "10" (válida)

    ventana.campo_cantidad.widget.setText("-1")
    ventana.campo_cantidad.widget.editingFinished.emit()
    assert ventana.campo_cantidad.es_valido() is False
    assert ventana.btn_guardar.isEnabled() is False


def test_usuario_nuevo_contrasena_corta_bloquea_guardado(
    qapp, base_de_datos_limpia, sin_sesion,
):
    """Regla que YA existía (antes solo se avisaba al guardar): la
    contraseña debe tener al menos 4 caracteres."""
    from app.ui.vista_admin import VentanaNuevoUsuario

    _iniciar_como("ADMIN")
    ventana = VentanaNuevoUsuario(None, al_guardar=lambda: None)
    ventana.campo_usuario.set("juanp")
    ventana.campo_nombre.set("Juan Pérez")
    ventana.campo_contrasena.set("123")
    ventana.campo_contrasena.widget.editingFinished.emit()

    assert ventana.campo_contrasena.es_valido() is False
    assert "4 caracteres" in ventana.campo_contrasena._lbl_error.text()
    assert ventana.btn_guardar.isEnabled() is False

    ventana.campo_contrasena.set("1234")
    ventana.campo_contrasena.widget.editingFinished.emit()
    assert ventana.btn_guardar.isEnabled() is True


# ══════════════════════════════════════════════════════════════════
#  PARTE 1 (ampliación) — badges en tabla_items y tipos de movimiento
# ══════════════════════════════════════════════════════════════════

def test_tipos_de_movimiento_en_estado_map():
    """Todos los tipos que genera el sistema deben tener ícono en
    _ESTADO_MAP para que tabla_movimientos nunca muestre texto crudo."""
    for tipo in ("ENTRADA", "SALIDA", "CONSUMO", "VENTA", "AJUSTE"):
        resultado = formatear_estado(tipo)
        # Debe contener al menos un carácter no-ASCII (el ícono)
        assert resultado != tipo, f"formatear_estado({tipo!r}) devolvió el mismo string sin ícono"
        assert tag_para_estado(tipo) == "normal"


def test_tabla_items_compras_muestra_estado_vacio(qapp):
    """La tabla de ítems de una nueva orden de compra debe mostrar
    EstadoVacio mientras no se haya agregado ningún producto."""
    from app.ui.vista_compras import VentanaNuevaOrden

    # VentanaNuevaOrden necesita sesión activa para consultar proveedores
    _iniciar_como("ADMIN")

    # Construir sin mostrar en pantalla
    dialogo = VentanaNuevaOrden(None, al_guardar=lambda: None)
    dialogo.resize(800, 600)

    # Al abrirse, la tabla de ítems está vacía -> EstadoVacio visible
    assert dialogo.tabla_items._estado_vacio is not None
    dialogo.tabla_items.cargar_filas([])
    assert dialogo.tabla_items._estado_vacio.isVisibleTo(dialogo.tabla_items) is True

    # Simular un ítem agregado -> EstadoVacio se oculta
    dialogo.tabla_items.cargar_filas([["Malta Pilsen", "50", "S/ 2.50", "2027-01-01", "S/ 125.00"]])
    assert dialogo.tabla_items._estado_vacio.isVisibleTo(dialogo.tabla_items) is False


def test_tabla_items_ventas_muestra_estado_vacio(qapp):
    """La tabla del carrito de una nueva venta debe mostrar EstadoVacio
    cuando no se ha seleccionado ningún producto todavía."""
    from app.ui.vista_ventas import VentanaNuevaVenta

    _iniciar_como("ADMIN")

    dialogo = VentanaNuevaVenta(None, al_guardar=lambda: None)
    dialogo.resize(800, 600)

    assert dialogo.tabla_items._estado_vacio is not None
    dialogo.tabla_items.cargar_filas([])
    assert dialogo.tabla_items._estado_vacio.isVisibleTo(dialogo.tabla_items) is True

    dialogo.tabla_items.cargar_filas([["Anka Chida", "6", "S/ 15.00", "S/ 90.00"]])
    assert dialogo.tabla_items._estado_vacio.isVisibleTo(dialogo.tabla_items) is False


def test_tabla_items_filtra_y_muestra_estado_vacio(qapp):
    """Si el usuario aplica un filtro que no coincide con ningún ítem
    ya agregado, debe aparecer EstadoVacio (no una tabla en blanco)."""
    from app.ui.vista_compras import VentanaNuevaOrden

    _iniciar_como("COMPRAS")

    dialogo = VentanaNuevaOrden(None, al_guardar=lambda: None)
    dialogo.resize(800, 600)

    dialogo.tabla_items.cargar_filas([["Malta Pilsen", "50", "S/ 2.50", "2027-01-01", "S/ 125.00"]])
    assert dialogo.tabla_items._estado_vacio.isVisibleTo(dialogo.tabla_items) is False

    dialogo.tabla_items.filtrar("xxxxxxxxxxx")
    assert dialogo.tabla_items._estado_vacio.isVisibleTo(dialogo.tabla_items) is True

    dialogo.tabla_items.filtrar("")
    assert dialogo.tabla_items._estado_vacio.isVisibleTo(dialogo.tabla_items) is False


def test_tabla_movimientos_usa_formatear_estado(qapp, base_de_datos_limpia, sin_sesion):
    """Después del parche, la columna Tipo de la tabla de movimientos
    debe contener el texto formateado (ícono + etiqueta), no el string
    interno crudo como 'ENTRADA' o 'CONSUMO'."""
    from datetime import date
    import app.modelos as m
    from app.ui.vista_inventario import VistaInventario

    _iniciar_como("ADMIN")

    # Crear un producto con un lote y varios tipos de movimiento
    with _bd.SesionLocal() as db:
        p = m.Producto(codigo="INS-MOV", nombre="Lúpulo Cascade", tipo="Insumo",
                        unidad_medida="kg", stock_minimo=5, activo=True)
        db.add(p)
        db.flush()
        lote = m.LoteInventario(numero_lote="LT-MOV-1", producto_id=p.id,
                                  fecha_ingreso=date.today(), cantidad_inicial=100,
                                  cantidad_disponible=80, estado="DISPONIBLE")
        db.add(lote)
        db.flush()
        for tipo in ("ENTRADA", "SALIDA", "AJUSTE"):
            db.add(m.MovimientoInventario(
                lote_id=lote.id, tipo=tipo, cantidad=10, referencia="TEST"))
        db.commit()

    vista = VistaInventario()
    vista.resize(900, 600)

    # La columna índice 3 es "Tipo" (después de id, producto, lote)
    # Los textos de esa columna deben contener íconos, no strings crudos
    tipos_crudos = {"ENTRADA", "SALIDA", "CONSUMO", "VENTA", "AJUSTE"}
    for fila_data in vista.tabla_movimientos._filas_actuales:
        tipo_celda = str(fila_data[3])  # índice 3 = Tipo en filas_movimientos
        assert tipo_celda not in tipos_crudos, (
            f"La columna Tipo contiene el string interno crudo '{tipo_celda}' "
            "en vez del texto formateado con ícono."
        )


# ══════════════════════════════════════════════════════════════════
#  PARTE 5 — confirmaciones destructivas (producto y usuario)
# ══════════════════════════════════════════════════════════════════

def test_desactivar_producto_pide_confirmacion_y_usa_conteo_real(
    qapp, base_de_datos_limpia, sin_sesion, monkeypatch,
):
    """El botón "Desactivar" de Catálogo debe mostrar un diálogo de
    confirmación con el conteo real de lotes con stock antes de
    desactivar, y no tocar nada si el usuario cancela."""
    from datetime import date
    import app.modelos as m
    import app.ui.vista_inventario as vi

    _iniciar_como("ADMIN")
    with _bd.SesionLocal() as db:
        p = m.Producto(codigo="INS-DES", nombre="Levadura Test", tipo="Insumo",
                        unidad_medida="g", stock_minimo=5, activo=True)
        db.add(p)
        db.flush()
        db.add(m.LoteInventario(numero_lote="LT-DES-1", producto_id=p.id,
                                 fecha_ingreso=date.today(),
                                 cantidad_inicial=100, cantidad_disponible=100,
                                 estado="DISPONIBLE"))
        db.commit()
        producto_id = p.id

    vista = vi.VistaInventario()
    vista.resize(900, 600)
    vista.refrescar()
    vista.tabla_catalogo.selectRow(0)  # único producto en la BD limpia

    mensajes_confirmacion = []

    def _confirmar_falso(parent, titulo, mensaje, **kw):
        mensajes_confirmacion.append(mensaje)
        return False  # simula que el usuario cancela

    monkeypatch.setattr(vi, "confirmar", _confirmar_falso)
    vista._desactivar_producto()

    assert mensajes_confirmacion  # se mostró el diálogo
    assert "1 lote" in mensajes_confirmacion[-1]
    with _bd.SesionLocal() as db:
        assert db.get(m.Producto, producto_id).activo is True  # cancelar no cambia nada

    monkeypatch.setattr(vi, "confirmar", lambda *a, **kw: True)
    vista._desactivar_producto()
    with _bd.SesionLocal() as db:
        assert db.get(m.Producto, producto_id).activo is False


def test_desactivar_usuario_muestra_conteo_de_ordenes(
    qapp, base_de_datos_limpia, sin_sesion, monkeypatch,
):
    import app.modelos as m
    import app.ui.vista_admin as va
    from app.logica_autenticacion import crear_usuario

    _iniciar_como("ADMIN")
    u = crear_usuario("comprador1", "Comprador Uno", "clave123", "COMPRAS")
    with _bd.SesionLocal() as db:
        prov = m.Proveedor(razon_social="Proveedor Test", ruc="20111111111", activo=True)
        db.add(prov)
        db.flush()
        db.add(m.OrdenCompra(numero="OC-DES-1", proveedor_id=prov.id,
                              total=100.0, creado_por=u.id))
        db.commit()

    vista = va.VistaAdmin()
    vista.resize(900, 600)
    vista.refrescar()
    fila = next(
        r for r in range(vista.tabla_usuarios.rowCount())
        if vista.tabla_usuarios.item(r, 0) and vista.tabla_usuarios.item(r, 0).text() == "comprador1"
    )
    vista.tabla_usuarios.selectRow(fila)

    mensajes = []
    monkeypatch.setattr(va, "confirmar", lambda parent, titulo, mensaje, **kw: mensajes.append(mensaje) or True)
    vista._desactivar()

    assert "1 orden" in mensajes[-1]
    with _bd.SesionLocal() as db:
        assert db.get(m.Usuario, u.id).activo is False


# ══════════════════════════════════════════════════════════════════
#  PARTE 6 — atajos de teclado (Ctrl+N global, Ctrl+S en formularios)
# ══════════════════════════════════════════════════════════════════

def test_ctrl_n_disponible_cuando_el_rol_puede_crear(qapp, base_de_datos_limpia, sin_sesion):
    """VentanaPrincipal._nuevo_en_modulo_activo() llama a
    vista_activa().accion_nuevo() — cada vista solo debe exponer ese
    atributo si el rol activo puede crear ahí (mismo permiso que ya
    gatea el botón "＋", ver vista_compras.py)."""
    import app.ui.vista_compras as vc
    import app.ui.vista_ventas as vv
    import app.ui.vista_admin as va

    _iniciar_como("ADMIN")
    vista_compras = vc.VistaCompras()
    assert vista_compras.accion_nuevo == vista_compras._abrir_nueva_orden

    vista_ventas = vv.VistaVentas()
    assert vista_ventas.accion_nuevo == vista_ventas._abrir_nueva_venta

    vista_admin = va.VistaAdmin()
    assert vista_admin.accion_nuevo == vista_admin._abrir_nuevo_usuario


def test_ctrl_n_no_disponible_si_el_rol_no_puede_crear(qapp, base_de_datos_limpia, sin_sesion):
    """El rol PRODUCCION solo puede *ver* Inventario ("ver", sin
    "entrada") — ni el botón "＋ Nuevo producto" ni accion_nuevo deben
    existir, para que Ctrl+N no abra un formulario que ese rol no
    podría guardar."""
    import app.ui.vista_inventario as vi

    _iniciar_como("PRODUCCION")
    vista = vi.VistaInventario()
    assert getattr(vista, "accion_nuevo", None) is None


def test_ctrl_n_en_ventana_principal_dispara_accion_nuevo_del_modulo_activo(
    qapp, base_de_datos_limpia, sin_sesion,
):
    """Prueba de integración del handler _nuevo_en_modulo_activo(): con
    Compras como módulo activo, debe llamar exactamente a la misma
    acción que el botón "＋ Nueva orden" (sin necesidad de simular la
    pulsación real de teclado — el QShortcut ya es una API de Qt bien
    probada; lo que hay que probar es que el handler pesca la vista
    activa correcta)."""
    import app.ui.ventana_principal as vp

    _iniciar_como("ADMIN")
    ventana = vp.VentanaPrincipal()
    ventana._navegar("compras")
    llamadas = []
    ventana._vistas["compras"].accion_nuevo = lambda: llamadas.append("compras")
    ventana._nuevo_en_modulo_activo()
    assert llamadas == ["compras"]

    # Un módulo sin "nuevo" (Dashboard) no debe romper nada.
    ventana._navegar("dashboard")
    ventana._nuevo_en_modulo_activo()  # no debe lanzar excepción


def test_ctrl_s_guarda_solo_si_el_formulario_es_valido(qapp, base_de_datos_limpia, sin_sesion):
    """El atajo Ctrl+S dispara btn_guardar.click() — como Qt no
    permite click() en un botón deshabilitado, heredar la validación
    inline existente (conectar_boton_a_validez) es automático: no hace
    falta duplicar la lógica de validación para el atajo."""
    import app.ui.vista_inventario as vi

    _iniciar_como("ADMIN")
    dialogo = vi.VentanaProducto(None, al_guardar=lambda: None)
    dialogo.campo_nombre.set("")  # inválido: nombre vacío
    dialogo.campo_nombre.widget.editingFinished.emit()
    assert not dialogo.btn_guardar.isEnabled()
    dialogo.btn_guardar.click()  # equivalente a lo que hace el atajo Ctrl+S
    # No debe haber guardado nada (no hay excepción ni producto creado).

    dialogo.campo_nombre.set("Producto de prueba Ctrl+S")
    dialogo.campo_nombre.widget.editingFinished.emit()
    assert dialogo.btn_guardar.isEnabled()
