"""
tutorial_data.py
=================
Contenido DECLARATIVO del tutorial: la lista de pasos de cada
recorrido (general y por módulo), y el guardado/lectura del progreso
del usuario.

Agregar o modificar un tutorial es, en principio, solo tocar este
archivo: armar una lista de `PasoTutorial` y registrarla en
`TUTORIALES_MODULO`. `tutorial.py` se encarga de "ejecutarla" con el
overlay — no hay que programar nada nuevo en la mayoría de los casos.

Cada paso resuelve su widget objetivo con una función (`target`) en
vez de una ruta de texto, porque en Tkinter los widgets reales solo
existen una vez que la pantalla fue construida (y a veces hay que
navegar a un módulo, cambiar de pestaña o abrir un diálogo antes de
poder "verlos"). Esa función recibe un diccionario de contexto:

    contexto = {
        "ventana": <VentanaPrincipal>,
        "vista":   <la vista del módulo actual, o None>,
        "dialogo": <el diálogo real recién abierto, si el paso lo abrió>,
    }

y debe devolver el widget a resaltar, o None si el paso no resalta
nada puntual (se muestra como tarjeta centrada).

El progreso se guarda con el mecanismo de persistencia que YA existe
en el proyecto (`ParametroSistema`, vía `logica_configuracion`), igual
que hacía el tutorial anterior — no se crea ninguna tabla nueva.
"""

from __future__ import annotations

import json
from dataclasses import dataclass, field
from typing import Callable, Optional

from app.logica_configuracion import obtener_parametro, establecer_parametro
from app.seguridad import modulos_visibles


# ══════════════════════════════════════════════════════════════════
#  ESTRUCTURAS DE UN PASO
# ══════════════════════════════════════════════════════════════════

@dataclass
class PasoPractica:
    """Un ítem de checklist dentro de un tutorial PRÁCTICO (ver
    tutorial_practice.py). No lo ejecuta el overlay normal."""
    instruccion: str
    verificar: Callable[[dict], bool]     # True cuando la acción ya se hizo
    objetivo: Callable[[dict], object]    # widget a resaltar mientras se espera la acción
    obligatorio: bool = True


@dataclass
class PasoTutorial:
    titulo: str
    texto: str
    icono: str = "💡"
    # Módulo al que hay que navegar antes de mostrar este paso
    # (None = no navegar, se queda donde esté el usuario; útil para
    # el paso de bienvenida / cierre del tour general).
    modulo: Optional[str] = None
    # Subtexto (o parte de él) de la pestaña del Notebook a
    # seleccionar antes de resaltar (si el módulo tiene pestañas).
    tab: Optional[str] = None
    # Si se define, se llama con la vista del módulo ANTES de
    # resolver el target de este paso, y debe devolver el diálogo
    # abierto (o None). Sirve para mostrar el tutorial "dentro" de
    # una ventana de creación real (ej. Nueva orden de compra).
    abrir: Optional[Callable[[object], object]] = None
    # Si es True, cierra el diálogo que un paso anterior haya abierto
    # antes de continuar (por ejemplo, al terminar de explicarlo).
    cerrar_dialogo: bool = False
    # Widget a resaltar. Recibe el contexto (ver docstring del
    # módulo). None = tarjeta centrada, sin resaltar nada.
    target: Optional[Callable[[dict], object]] = None


@dataclass
class Tutorial:
    clave: str
    titulo: str
    icono: str
    descripcion: str
    pasos: list = field(default_factory=list)
    # Rol(es) que necesitan tener este módulo visible para que el
    # tutorial tenga sentido (se filtra con seguridad.modulos_visibles).
    requiere_modulo: Optional[str] = None


# ══════════════════════════════════════════════════════════════════
#  PROGRESO DEL USUARIO
# ══════════════════════════════════════════════════════════════════
# Se guarda un JSON por usuario y por tutorial, bajo una clave de
# parámetro distinta para cada combinación, reutilizando la misma
# tabla ParametroSistema que ya usa el resto del sistema.

def _clave_progreso(usuario_id: int, clave_tutorial: str) -> str:
    return f"tutorial_progreso_usuario_{usuario_id}_{clave_tutorial}"


def obtener_progreso(usuario_id: int, clave_tutorial: str) -> dict:
    """
    Devuelve {"completado": bool, "paso_actual": int, "total_pasos": int}.
    Si el usuario nunca empezó este tutorial, "paso_actual" es 0 y
    "completado" es False.
    """
    crudo = obtener_parametro(_clave_progreso(usuario_id, clave_tutorial), "")
    if not crudo:
        return {"completado": False, "paso_actual": 0, "total_pasos": 0}
    try:
        datos = json.loads(crudo)
        return {
            "completado": bool(datos.get("completado", False)),
            "paso_actual": int(datos.get("paso_actual", 0)),
            "total_pasos": int(datos.get("total_pasos", 0)),
        }
    except (ValueError, TypeError):
        return {"completado": False, "paso_actual": 0, "total_pasos": 0}


def guardar_progreso(usuario_id: int, clave_tutorial: str, paso_actual: int,
                      total_pasos: int, completado: bool = False):
    establecer_parametro(
        _clave_progreso(usuario_id, clave_tutorial),
        json.dumps({
            "completado": completado,
            "paso_actual": paso_actual,
            "total_pasos": total_pasos,
        }),
    )


def marcar_completado(usuario_id: int, clave_tutorial: str, total_pasos: int):
    guardar_progreso(usuario_id, clave_tutorial, total_pasos, total_pasos, completado=True)


def reiniciar_progreso(usuario_id: int, clave_tutorial: str):
    guardar_progreso(usuario_id, clave_tutorial, 0, 0, completado=False)


def estado_tutorial(usuario_id: int, clave_tutorial: str) -> str:
    """"completado" | "en_progreso" | "no_iniciado" — para el Centro de Ayuda."""
    p = obtener_progreso(usuario_id, clave_tutorial)
    if p["completado"]:
        return "completado"
    if p["paso_actual"] > 0:
        return "en_progreso"
    return "no_iniciado"


# Compatibilidad con el tutorial de bienvenida anterior (una sola
# bandera por usuario). Se mantiene para no perder el estado de
# quienes ya lo vieron con la versión previa del sistema.
def _clave_visto_legacy(usuario_id: int) -> str:
    return f"tutorial_visto_usuario_{usuario_id}"


def tutorial_general_pendiente(usuario_id: int) -> bool:
    """True si el usuario todavía no completó (ni saltó) el tour general."""
    if obtener_parametro(_clave_visto_legacy(usuario_id), "") == "1":
        return False
    return not obtener_progreso(usuario_id, "general")["completado"]


def marcar_tutorial_general_visto(usuario_id: int):
    establecer_parametro(_clave_visto_legacy(usuario_id), "1")
    marcar_completado(usuario_id, "general", obtener_progreso(usuario_id, "general")["total_pasos"] or 1)


# ══════════════════════════════════════════════════════════════════
#  TOUR GENERAL DEL SISTEMA
# ══════════════════════════════════════════════════════════════════
# Se arma dinámicamente porque depende del rol (los módulos visibles)
# y del nombre de la empresa configurado.

_ICONOS_MODULO = {
    "dashboard": "🏠", "compras": "🛒", "inventario": "📦",
    "produccion": "🍺", "ventas": "💰", "costos": "📊", "admin": "⚙️",
}
_NOMBRES_MODULO = {
    "dashboard": "Inicio", "compras": "Compras", "inventario": "Inventario",
    "produccion": "Producción", "ventas": "Ventas", "costos": "Costos",
    "admin": "Administración",
}
_DESCRIPCIONES_MODULO = {
    "dashboard": "Aquí ves de un vistazo los indicadores clave del negocio: "
                 "stock bajo, lotes por vencer, ingresos del mes y más.",
    "compras": "Registra órdenes de compra a tus proveedores. El inventario "
               "se actualiza automáticamente al guardar cada orden.",
    "inventario": "Consulta el stock actual, los lotes FIFO, los movimientos "
                  "y el catálogo completo de productos e insumos.",
    "produccion": "Planifica, inicia y cierra órdenes de elaboración de "
                  "cerveza. Al cerrar una orden se descuentan insumos, se "
                  "registra la merma y se calculan los costos.",
    "ventas": "Registra órdenes de venta a tus clientes. El stock se "
              "descuenta automáticamente siguiendo el orden FIFO.",
    "costos": "Analiza el costo real y el margen de ganancia de cada lote "
              "de producción ya cerrado.",
    "admin": "Configura los datos de la empresa y administra usuarios del "
             "sistema.",
}


def construir_tutorial_general(nombre_empresa: str, rol: str) -> Tutorial:
    modulos_rol = modulos_visibles(rol)
    # Se muestran en el mismo orden en que aparecen en el menú lateral.
    orden = ["dashboard", "compras", "inventario", "produccion", "ventas", "costos", "admin"]

    pasos = [
        PasoTutorial(
            icono="👋",
            titulo=f"¡Bienvenido(a) a {nombre_empresa}!",
            texto="Este recorrido rápido te muestra las partes principales del "
                  "sistema mientras interactúas con ellas. Puedes salir cuando "
                  "quieras con «Saltar tutorial» o la tecla ESC.",
            target=lambda ctx: None,
        ),
        PasoTutorial(
            icono="📋",
            titulo="Menú lateral",
            texto="Desde aquí accedes a los módulos disponibles para tu "
                  "usuario. Los botones que ves dependen de tu rol.",
            target=lambda ctx: ctx["ventana"].widget_sidebar(),
        ),
    ]

    for clave in orden:
        if clave not in modulos_rol:
            continue
        pasos.append(PasoTutorial(
            icono=_ICONOS_MODULO[clave],
            titulo=_NOMBRES_MODULO[clave],
            texto=_DESCRIPCIONES_MODULO[clave],
            target=(lambda ctx, c=clave: ctx["ventana"].boton_menu(c)),
        ))

    pasos.append(PasoTutorial(
        icono="❓",
        titulo="¿Necesitas repasar algo?",
        texto="Vuelve a ver este recorrido o abre el tutorial de cualquier "
              "módulo cuando quieras desde «Ayuda y tutorial», en la parte "
              "inferior del menú lateral.",
        target=lambda ctx: ctx["ventana"].boton_ayuda(),
    ))

    return Tutorial("general", "Tutorial general", "🎓",
                     f"Aprende a utilizar {nombre_empresa}", pasos)


# ══════════════════════════════════════════════════════════════════
#  TUTORIALES POR MÓDULO
# ══════════════════════════════════════════════════════════════════
# Cada uno usa ÚNICAMENTE controles reales, expuestos por cada vista
# en su diccionario `tutorial_targets` (o por el diálogo real que
# `abrir` deja abierto). Si algún target no se encuentra (por permisos
# del rol, por ejemplo), el paso simplemente se salta.

def _t(vista_key):
    """Azúcar sintáctica: helper para resolver un target simple del
    diccionario `tutorial_targets` de la vista actual."""
    def resolver(ctx):
        vista = ctx.get("vista")
        if vista is None:
            return None
        return getattr(vista, "tutorial_targets", {}).get(vista_key)
    return resolver


def _td(dialogo_key):
    """Igual que `_t`, pero busca el atributo dentro del diálogo
    real que un paso anterior haya abierto con `abrir=...`."""
    def resolver(ctx):
        dialogo = ctx.get("dialogo")
        if dialogo is None:
            return None
        return getattr(dialogo, dialogo_key, None)
    return resolver


def _tutorial_compras() -> Tutorial:
    pasos = [
        PasoTutorial(
            modulo="compras", icono="🛒", titulo="Módulo de Compras",
            texto="Aquí registras las órdenes de compra a tus proveedores. "
                  "Al guardarlas, el inventario se actualiza solo.",
            target=lambda ctx: None,
        ),
        PasoTutorial(
            modulo="compras", tab="Órdenes", icono="＋",
            titulo="Nueva orden de compra",
            texto="Este botón abre el formulario para registrar una compra. "
                  "Vamos a abrirlo para ver sus partes.",
            target=_t("btn_nueva_orden"),
        ),
        PasoTutorial(
            modulo="compras", tab="Órdenes",
            abrir=lambda vista: vista.abrir_nueva_orden_para_tutorial(),
            icono="🏭", titulo="Selecciona el proveedor",
            texto="Elige de la lista el proveedor al que le compraste. Si "
                  "aún no está registrado, se crea desde la pestaña "
                  "«Proveedores».",
            target=_td("combo_proveedor"),
        ),
        PasoTutorial(
            modulo="compras", icono="📦", titulo="Elige el producto",
            texto="Selecciona qué producto o insumo estás comprando.",
            target=_td("combo_producto"),
        ),
        PasoTutorial(
            modulo="compras", icono="🔢", titulo="Cantidad y precio",
            texto="Indica cuánto compraste y a qué precio unitario. La "
                  "fecha de vencimiento es opcional (útil para insumos "
                  "perecibles).",
            target=_td("entry_cantidad"),
        ),
        PasoTutorial(
            modulo="compras", icono="💾", titulo="Registrar la orden",
            texto="Después de agregar todos los productos, este botón "
                  "guarda la orden y actualiza el inventario automáticamente.",
            target=_td("btn_guardar"),
            cerrar_dialogo=True,
        ),
        PasoTutorial(
            modulo="compras", tab="Órdenes", icono="🧾",
            titulo="Historial de compras",
            texto="Todas las órdenes registradas quedan aquí, con su "
                  "proveedor, fecha y total.",
            target=_t("tabla_ordenes"),
        ),
        PasoTutorial(
            modulo="compras", tab="Órdenes", icono="📊", titulo="Reportes",
            texto="Este botón genera un reporte de compras en PDF, Excel o "
                  "CSV — lo encontrarás con el mismo ícono en casi todos los "
                  "módulos.",
            target=_t("btn_reporte"),
        ),
    ]
    return Tutorial("compras", "Compras", "🛒", "Aprende a registrar compras", pasos)


def _tutorial_inventario() -> Tutorial:
    pasos = [
        PasoTutorial(
            modulo="inventario", icono="📦", titulo="Módulo de Inventario",
            texto="Aquí consultas el stock, los lotes y los movimientos de "
                  "todos tus productos e insumos.",
            target=lambda ctx: None,
        ),
        PasoTutorial(
            modulo="inventario", tab="Stock", icono="📊",
            titulo="Stock actual",
            texto="Muestra el stock disponible de cada producto, con un "
                  "indicador de color: verde (normal), amarillo (stock "
                  "bajo) o rojo (agotado).",
            target=_t("tabla_stock"),
        ),
        PasoTutorial(
            modulo="inventario", tab="Lotes", icono="🗂",
            titulo="Lotes FIFO",
            texto="Cada compra o producción crea un lote. El sistema "
                  "siempre consume primero el lote más antiguo (FIFO).",
            target=_t("tabla_lotes"),
        ),
        PasoTutorial(
            modulo="inventario", tab="Movimientos", icono="📋",
            titulo="Movimientos",
            texto="Aquí queda el historial de entradas y salidas de cada "
                  "lote: compras, consumos de producción, ventas y ajustes.",
            target=_t("tabla_movimientos"),
        ),
        PasoTutorial(
            modulo="inventario", tab="Catálogo", icono="🏷",
            titulo="Catálogo de productos",
            texto="Aquí se administran los productos e insumos: código, "
                  "nombre, unidad de medida y stock mínimo de alerta.",
            target=_t("tabla_catalogo"),
        ),
        PasoTutorial(
            modulo="inventario", tab="Stock", icono="📊", titulo="Reportes",
            texto="Genera un reporte del stock actual en PDF, Excel o CSV.",
            target=_t("btn_reporte"),
        ),
    ]
    return Tutorial("inventario", "Inventario", "📦", "Aprende a gestionar el inventario", pasos)


def _tutorial_produccion() -> Tutorial:
    pasos = [
        PasoTutorial(
            modulo="produccion", icono="🍺", titulo="Módulo de Producción",
            texto="Aquí planificas y controlas las órdenes de elaboración "
                  "de cerveza, de principio a fin.",
            target=lambda ctx: None,
        ),
        PasoTutorial(
            modulo="produccion", icono="＋", titulo="Nueva orden de producción",
            texto="Crea una orden eligiendo la receta y la cantidad "
                  "planeada. Al crearla queda en estado INICIADA.",
            target=_t("btn_nueva_orden"),
        ),
        PasoTutorial(
            modulo="produccion", icono="▶", titulo="Iniciar el proceso",
            texto="Cuando comienzas a elaborar de verdad, marca la orden "
                  "como EN_PROCESO con este botón.",
            target=_t("btn_iniciar"),
        ),
        PasoTutorial(
            modulo="produccion", icono="✔", titulo="Cerrar la orden",
            texto="Al cerrar la orden, el sistema hace todo junto: "
                  "descuenta los insumos (FIFO), registra la merma si la "
                  "hubo, crea el lote de producto terminado y calcula el "
                  "costo y el margen.",
            target=_t("btn_cerrar"),
        ),
        PasoTutorial(
            modulo="produccion", icono="📋", titulo="Seguimiento de órdenes",
            texto="Aquí ves todas las órdenes con su estado, cantidad "
                  "planeada y cantidad real obtenida.",
            target=_t("tabla_ordenes"),
        ),
        PasoTutorial(
            modulo="produccion", icono="📊", titulo="Reportes",
            texto="Genera un reporte de producción en PDF, Excel o CSV.",
            target=_t("btn_reporte"),
        ),
    ]
    return Tutorial("produccion", "Producción", "🍺", "Aprende a gestionar la producción", pasos)


def _tutorial_ventas() -> Tutorial:
    pasos = [
        PasoTutorial(
            modulo="ventas", icono="💰", titulo="Módulo de Ventas",
            texto="Registra las órdenes de venta a tus clientes. El stock "
                  "se descuenta automáticamente siguiendo FIFO.",
            target=lambda ctx: None,
        ),
        PasoTutorial(
            modulo="ventas", tab="Órdenes", icono="＋",
            titulo="Nueva venta",
            texto="Abre el formulario para registrar una venta: cliente, "
                  "productos, cantidades y el total se calcula solo.",
            target=_t("btn_nueva_venta"),
        ),
        PasoTutorial(
            modulo="ventas", tab="Órdenes", icono="🧾",
            titulo="Historial de ventas",
            texto="Aquí quedan todas las órdenes de venta registradas, con "
                  "su cliente, fecha y total.",
            target=_t("tabla_ventas"),
        ),
        PasoTutorial(
            modulo="ventas", tab="Clientes", icono="👥",
            titulo="Clientes",
            texto="Administra la lista de clientes, sean personas o "
                  "empresas, con su documento y datos de contacto.",
            target=_t("tabla_clientes"),
        ),
        PasoTutorial(
            modulo="ventas", tab="Órdenes", icono="📊", titulo="Reportes",
            texto="Genera un reporte de ventas en PDF, Excel o CSV.",
            target=_t("btn_reporte"),
        ),
    ]
    return Tutorial("ventas", "Ventas", "💰", "Aprende a registrar ventas", pasos)


def _tutorial_costos() -> Tutorial:
    pasos = [
        PasoTutorial(
            modulo="costos", icono="📊", titulo="Módulo de Costos",
            texto="Analiza el costo real y el margen de ganancia de cada "
                  "lote de producción ya cerrado.",
            target=lambda ctx: None,
        ),
        PasoTutorial(
            modulo="costos", icono="💸", titulo="Indicadores generales",
            texto="Estos indicadores resumen el costo total acumulado, el "
                  "margen promedio y el costo unitario promedio de todos "
                  "los lotes.",
            target=_t("kpi_costo_total"),
        ),
        PasoTutorial(
            modulo="costos", icono="🍺", titulo="Detalle por lote",
            texto="Cada fila desglosa el costo de un lote en insumos, "
                  "mano de obra e indirectos, además del margen obtenido.",
            target=_t("tabla"),
        ),
        PasoTutorial(
            modulo="costos", icono="📊", titulo="Reportes",
            texto="Genera un reporte de costos en PDF, Excel o CSV.",
            target=_t("btn_reporte"),
        ),
    ]
    return Tutorial("costos", "Costos", "📊", "Aprende a consultar costos", pasos)


def _tutorial_reportes() -> Tutorial:
    """
    No existe un módulo "Reportes" independiente en el menú lateral:
    cada módulo (Compras, Inventario, Producción, Ventas, Costos)
    tiene su propio botón "📊 Reporte". Este tutorial lo explica y
    muestra un ejemplo real dentro de Compras.
    """
    pasos = [
        PasoTutorial(
            icono="📈", titulo="Reportes",
            texto="Cervecera no tiene un módulo de reportes aparte: cada "
                  "módulo trae su propio botón «📊 Reporte» para exportar "
                  "sus datos. Vamos a ver un ejemplo en Compras.",
            target=lambda ctx: None,
        ),
        PasoTutorial(
            modulo="compras", tab="Órdenes", icono="📊",
            titulo="Botón de reporte",
            texto="Este botón abre el generador de reportes ya filtrado "
                  "para este módulo.",
            target=_t("btn_reporte"),
        ),
        PasoTutorial(
            modulo="compras",
            abrir=lambda vista: vista.abrir_reporte_para_tutorial(),
            icono="🔍", titulo="Vista previa",
            texto="Pulsa «Vista previa» para consultar los datos antes de "
                  "exportarlos — se muestran como tabla, igual que en el "
                  "resto del sistema.",
            target=_td("btn_vista_previa"),
        ),
        PasoTutorial(
            modulo="compras", icono="💾", titulo="Guardar como…",
            texto="Elige el formato (PDF, Excel o CSV) y este botón te deja "
                  "guardar el archivo donde quieras.",
            target=_td("btn_guardar"),
            cerrar_dialogo=True,
        ),
    ]
    return Tutorial("reportes", "Reportes", "📈",
                     "Aprende a utilizar los reportes", pasos, requiere_modulo="compras")


TUTORIALES_MODULO: dict[str, Callable[[], Tutorial]] = {
    "compras": _tutorial_compras,
    "inventario": _tutorial_inventario,
    "produccion": _tutorial_produccion,
    "ventas": _tutorial_ventas,
    "costos": _tutorial_costos,
    "reportes": _tutorial_reportes,
}

# Orden de presentación en el Centro de Ayuda.
ORDEN_CENTRO_AYUDA = ["general", "compras", "inventario", "produccion",
                       "ventas", "costos", "reportes"]


def tutoriales_disponibles_para_rol(rol: str) -> list[str]:
    """Claves de tutorial (sin contar 'general') que tienen sentido para
    este rol, según los módulos que puede ver."""
    modulos_rol = modulos_visibles(rol)
    disponibles = []
    for clave in ORDEN_CENTRO_AYUDA:
        if clave == "general":
            disponibles.append(clave)
            continue
        tutorial = TUTORIALES_MODULO[clave]()
        requerido = tutorial.requiere_modulo or clave
        if requerido in modulos_rol:
            disponibles.append(clave)
    return disponibles


# ══════════════════════════════════════════════════════════════════
#  AYUDA CONTEXTUAL (los botones "?" puntuales)
# ══════════════════════════════════════════════════════════════════

AYUDA_CONTEXTUAL = {
    "fifo": (
        "¿Qué es FIFO?",
        "FIFO significa \"el primero en entrar es el primero en salir\". "
        "Cuando compras el mismo insumo varias veces, cada compra crea un "
        "lote nuevo. Al usarlo en producción (o venderlo), el sistema "
        "descuenta siempre del lote con la fecha de ingreso más antigua "
        "antes de tocar los más nuevos.",
    ),
    "costos": (
        "¿Cómo se calculan los costos?",
        "Al cerrar una orden de producción, el sistema suma el costo de "
        "los insumos consumidos (FIFO), la mano de obra y los costos "
        "indirectos. Con ese total calcula el costo unitario y, "
        "comparándolo con el precio de venta, el margen de ganancia.",
    ),
    "produccion": (
        "¿Cómo funciona una orden de producción?",
        "Una orden pasa por 3 estados: INICIADA (recién creada), "
        "EN_PROCESO (cuando empiezas a elaborar) y COMPLETADA (al "
        "cerrarla). Cerrar la orden hace, en un solo paso, el descuento "
        "de insumos, el registro de la merma, la creación del lote "
        "terminado y el cálculo de costos.",
    ),
    "recetas": (
        "¿Qué es una receta?",
        "Una receta define qué insumos (y en qué cantidad) se necesitan "
        "para elaborar una unidad de un producto terminado. Se usa como "
        "base al crear una orden de producción para saber qué se va a "
        "consumir del inventario.",
    ),
    "reportes": (
        "¿Cómo funcionan los reportes?",
        "Cada módulo tiene un botón «📊 Reporte». Al abrirlo, eliges el "
        "formato (PDF, Excel o CSV), pulsas «Vista previa» para revisar "
        "los datos, y luego «Guardar como…» para exportar el archivo a "
        "donde quieras.",
    ),
}
