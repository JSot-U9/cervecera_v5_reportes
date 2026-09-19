"""tutorial_data.py (PySide6)
==============================
Contenido DECLARATIVO del tutorial: los pasos de cada recorrido y el
guardado/lectura del progreso del usuario. Ver el docstring de
`tutorial.py` para cómo se ejecuta esto.

Cada paso resuelve su widget objetivo con una función (`target`) que
recibe un contexto:
    {"ventana": VentanaPrincipal, "vista": vista_actual_o_None,
     "dialogo": dialogo_real_abierto_o_None}
y devuelve el widget Qt a resaltar (o None).
"""

from __future__ import annotations

import json
from dataclasses import dataclass, field
from typing import Callable, Optional

from app.logica_configuracion import obtener_parametro, establecer_parametro
from app.seguridad import modulos_visibles


@dataclass
class PasoTutorial:
    titulo: str
    texto: str
    icono: str = "💡"
    modulo: Optional[str] = None
    tab: Optional[str] = None
    abrir: Optional[Callable[[object], object]] = None
    cerrar_dialogo: bool = False
    target: Optional[Callable[[dict], object]] = None


@dataclass
class Tutorial:
    clave: str
    titulo: str
    icono: str
    descripcion: str
    pasos: list = field(default_factory=list)
    requiere_modulo: Optional[str] = None


# ══════════════════════════════════════════════════════════════════
#  PROGRESO DEL USUARIO (ParametroSistema — sin tabla nueva)
# ══════════════════════════════════════════════════════════════════

def _clave_progreso(usuario_id: int, clave_tutorial: str) -> str:
    return f"tutorial_progreso_usuario_{usuario_id}_{clave_tutorial}"


def obtener_progreso(usuario_id: int, clave_tutorial: str) -> dict:
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
        json.dumps({"completado": completado, "paso_actual": paso_actual, "total_pasos": total_pasos}),
    )


def marcar_completado(usuario_id: int, clave_tutorial: str, total_pasos: int):
    guardar_progreso(usuario_id, clave_tutorial, total_pasos, total_pasos, completado=True)


def reiniciar_progreso(usuario_id: int, clave_tutorial: str):
    guardar_progreso(usuario_id, clave_tutorial, 0, 0, completado=False)


def estado_tutorial(usuario_id: int, clave_tutorial: str) -> str:
    p = obtener_progreso(usuario_id, clave_tutorial)
    if p["completado"]:
        return "completado"
    if p["paso_actual"] > 0:
        return "en_progreso"
    return "no_iniciado"


def _clave_visto_legacy(usuario_id: int) -> str:
    return f"tutorial_visto_usuario_{usuario_id}"


def tutorial_general_pendiente(usuario_id: int) -> bool:
    if obtener_parametro(_clave_visto_legacy(usuario_id), "") == "1":
        return False
    return not obtener_progreso(usuario_id, "general")["completado"]


def marcar_tutorial_general_visto(usuario_id: int):
    establecer_parametro(_clave_visto_legacy(usuario_id), "1")
    marcar_completado(usuario_id, "general", obtener_progreso(usuario_id, "general")["total_pasos"] or 1)


# ══════════════════════════════════════════════════════════════════
#  TOUR GENERAL
# ══════════════════════════════════════════════════════════════════

_ICONOS_MODULO = {
    "dashboard": "🏠", "compras": "🛒", "inventario": "📦",
    "produccion": "🍺", "ventas": "💰", "costos": "📊",
    "centro_inteligencia": "🧠", "admin": "⚙️",
}
_NOMBRES_MODULO = {
    "dashboard": "Inicio", "compras": "Compras", "inventario": "Inventario",
    "produccion": "Producción", "ventas": "Realizar ventas", "costos": "Reportes de ventas",
    "centro_inteligencia": "Centro de Inteligencia", "admin": "Administración",
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
    "centro_inteligencia": "Reúne las recomendaciones de IA del sistema: qué "
                            "reponer, cuánta merma esperar y cuánta demanda "
                            "prevista tiene cada producto.",
    "admin": "Configura los datos de la empresa y administra usuarios del "
             "sistema.",
}


def construir_tutorial_general(nombre_empresa: str, rol: str) -> Tutorial:
    modulos_rol = modulos_visibles(rol)
    orden = ["dashboard", "compras", "inventario", "produccion", "ventas", "costos",
             "centro_inteligencia", "admin"]

    pasos = [
        PasoTutorial(
            icono="👋", titulo=f"¡Bienvenido(a) a {nombre_empresa}!",
            texto="Este recorrido rápido te muestra las partes principales del "
                  "sistema mientras interactúas con ellas. Puedes salir cuando "
                  "quieras con «Saltar tutorial» o la tecla ESC.",
            target=lambda ctx: None,
        ),
        PasoTutorial(
            icono="📋", titulo="Menú lateral",
            texto="Desde aquí accedes a los módulos disponibles para tu "
                  "usuario. Los botones que ves dependen de tu rol.",
            target=lambda ctx: ctx["ventana"].widget_sidebar(),
        ),
    ]

    for clave in orden:
        if clave not in modulos_rol:
            continue
        pasos.append(PasoTutorial(
            icono=_ICONOS_MODULO[clave], titulo=_NOMBRES_MODULO[clave],
            texto=_DESCRIPCIONES_MODULO[clave],
            target=(lambda ctx, c=clave: ctx["ventana"].boton_menu(c)),
        ))

    pasos.append(PasoTutorial(
        icono="❓", titulo="¿Necesitas repasar algo?",
        texto="Vuelve a ver este recorrido o abre el tutorial de cualquier "
              "módulo cuando quieras desde «Ayuda y tutorial», en la parte "
              "inferior del menú lateral.",
        target=lambda ctx: ctx["ventana"].boton_ayuda(),
    ))

    return Tutorial("general", "Tutorial general", "🎓", f"Aprende a utilizar {nombre_empresa}", pasos)


# ══════════════════════════════════════════════════════════════════
#  TUTORIALES POR MÓDULO
# ══════════════════════════════════════════════════════════════════

def _t(vista_key):
    def resolver(ctx):
        vista = ctx.get("vista")
        if vista is None:
            return None
        return getattr(vista, "tutorial_targets", {}).get(vista_key)
    return resolver


def _td(dialogo_key):
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
            modulo="compras", tab="Órdenes", icono="＋", titulo="Nueva orden de compra",
            texto="Este botón abre el formulario para registrar una compra. "
                  "Vamos a abrirlo para ver sus partes.",
            target=_t("btn_nueva_orden"),
        ),
        PasoTutorial(
            modulo="compras", tab="Órdenes",
            abrir=lambda vista: vista.abrir_nueva_orden_para_tutorial(),
            icono="🏭", titulo="Selecciona el proveedor",
            texto="Elige de la lista el proveedor al que le compraste. Si "
                  "aún no está registrado, se crea desde la pestaña «Proveedores».",
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
                  "fecha de vencimiento es opcional (útil para insumos perecibles).",
            target=_td("entry_cantidad"),
        ),
        PasoTutorial(
            modulo="compras", icono="💾", titulo="Registrar la orden",
            texto="Después de agregar todos los productos, este botón "
                  "guarda la orden y actualiza el inventario automáticamente.",
            target=_td("btn_guardar"), cerrar_dialogo=True,
        ),
        PasoTutorial(
            modulo="compras", tab="Órdenes", icono="🧾", titulo="Historial de compras",
            texto="Todas las órdenes registradas quedan aquí, con su "
                  "proveedor, fecha y total.",
            target=_t("tabla_ordenes"),
        ),
        PasoTutorial(
            modulo="compras", tab="Órdenes", icono="📊", titulo="Reportes",
            texto="Este botón genera un reporte de compras en PDF, Excel o "
                  "CSV — lo encontrarás con el mismo ícono en casi todos los módulos.",
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
            modulo="inventario", tab="Stock", icono="📊", titulo="Stock actual",
            texto="Muestra el stock disponible de cada producto, con un "
                  "indicador de color: verde (normal), amarillo (stock bajo) "
                  "o rojo (agotado).",
            target=_t("tabla_stock"),
        ),
        PasoTutorial(
            modulo="inventario", tab="Lotes", icono="🗂", titulo="Lotes FIFO",
            texto="Cada compra o producción crea un lote. El sistema "
                  "siempre consume primero el lote más antiguo (FIFO).",
            target=_t("tabla_lotes"),
        ),
        PasoTutorial(
            modulo="inventario", tab="Movimientos", icono="📋", titulo="Movimientos",
            texto="Aquí queda el historial de entradas y salidas de cada "
                  "lote: compras, consumos de producción, ventas y ajustes.",
            target=_t("tabla_movimientos"),
        ),
        PasoTutorial(
            modulo="inventario", tab="Catálogo", icono="🏷", titulo="Catálogo de productos",
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
            modulo="ventas", tab="Órdenes", icono="＋", titulo="Nueva venta",
            texto="Abre el formulario para registrar una venta: cliente, "
                  "productos, cantidades y el total se calcula solo.",
            target=_t("btn_nueva_venta"),
        ),
        PasoTutorial(
            modulo="ventas", tab="Órdenes", icono="🧾", titulo="Historial de ventas",
            texto="Aquí quedan todas las órdenes de venta registradas, con "
                  "su cliente, fecha y total.",
            target=_t("tabla_ventas"),
        ),
        PasoTutorial(
            modulo="ventas", tab="Clientes", icono="👥", titulo="Clientes",
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
    return Tutorial("ventas", "Realizar ventas", "💰", "Aprende a registrar ventas", pasos)


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
    return Tutorial("costos", "Reportes de ventas", "📊", "Aprende a consultar costos", pasos)


def _tutorial_reportes() -> Tutorial:
    pasos = [
        PasoTutorial(
            icono="📈", titulo="Reportes",
            texto="Cervecera no tiene un módulo de reportes aparte: cada "
                  "módulo trae su propio botón «📊 Reporte» para exportar "
                  "sus datos. Vamos a ver un ejemplo en Compras.",
            target=lambda ctx: None,
        ),
        PasoTutorial(
            modulo="compras", tab="Órdenes", icono="📊", titulo="Botón de reporte",
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
            target=_td("btn_guardar"), cerrar_dialogo=True,
        ),
    ]
    return Tutorial("reportes", "Reportes", "📈", "Aprende a utilizar los reportes",
                     pasos, requiere_modulo="compras")


def _tutorial_centro_inteligencia() -> Tutorial:
    pasos = [
        PasoTutorial(
            modulo="centro_inteligencia", icono="🧠", titulo="Centro de Inteligencia",
            texto="Aquí se concentran los tres resultados de IA del sistema: qué "
                  "insumos conviene reponer, cuánta merma se espera en una "
                  "producción y cuánta demanda se prevé por producto. Tú siempre "
                  "decides la acción — el sistema solo recomienda.",
            target=lambda ctx: None,
        ),
        PasoTutorial(
            modulo="centro_inteligencia", icono="📊", titulo="Indicadores generales",
            texto="Resumen rápido: cuántos insumos están en riesgo de quiebre, "
                  "cuántos tienen reposición sugerida y la merma histórica "
                  "promedio, calculados con datos reales del sistema.",
            target=_t("kpi_riesgo"),
        ),
        PasoTutorial(
            modulo="centro_inteligencia", tab="Reposición inteligente",
            icono="📦", titulo="Reposición inteligente",
            texto="Calcula, por horizonte de días, cuánto conviene comprar de "
                  "cada insumo según el stock disponible y la demanda esperada.",
            target=_t("btn_calcular_reposicion"),
        ),
        PasoTutorial(
            modulo="centro_inteligencia", tab="Reposición inteligente",
            icono="🛒", titulo="Generar la compra",
            texto="Selecciona un insumo de la tabla y, si tiene reposición "
                  "sugerida, este botón abre una orden de compra en el módulo "
                  "de Compras ya prellenada con el producto y la cantidad.",
            target=_t("btn_generar_compra"),
        ),
        PasoTutorial(
            modulo="centro_inteligencia", tab="Predicción de merma",
            icono="🍺", titulo="Predicción de merma",
            texto="Antes de planear o cerrar una producción, estima qué "
                  "porcentaje de merma es esperable para esa receta y esa "
                  "cantidad, comparado con el historial de esa misma receta.",
            target=_t("combo_receta_merma"),
        ),
        PasoTutorial(
            modulo="centro_inteligencia", tab="Predicción de merma",
            icono="🔍", titulo="Estimar merma esperada",
            texto="Con la receta y la cantidad planeada elegidas, este botón "
                  "calcula el rendimiento y la merma esperados.",
            target=_t("btn_estimar_merma"),
        ),
        PasoTutorial(
            modulo="centro_inteligencia", tab="Demanda prevista (resumen)",
            icono="🔮", titulo="Demanda prevista — resumen",
            texto="Vista rápida de la demanda estimada de TODOS los productos a "
                  "la vez, para un mismo horizonte de días — útil para detectar "
                  "de un vistazo qué productos tienen riesgo de quiebre.",
            target=_t("btn_actualizar_demanda"),
        ),
        PasoTutorial(
            modulo="centro_inteligencia", tab="Demanda prevista (resumen)",
            icono="📋", titulo="Tabla de demanda",
            texto="Cada fila indica la demanda total prevista, el promedio "
                  "diario y si la estimación usa el modelo de IA entrenado o "
                  "todavía un cálculo básico (mientras se acumula historial).",
            target=_t("tabla_demanda"),
        ),
        PasoTutorial(
            modulo="centro_inteligencia", tab="Predicción de demanda (detalle)",
            icono="📈", titulo="Predicción de demanda — detalle",
            texto="Aquí puedes elegir UN producto a la vez y ver su gráfico "
                  "histórico junto con la predicción, con más detalle que el "
                  "resumen multi-producto de la pestaña anterior.",
            target=_t("combo_producto_prediccion"),
        ),
        PasoTutorial(
            modulo="centro_inteligencia", tab="Predicción de demanda (detalle)",
            icono="🔮", titulo="Generar la predicción",
            texto="Elige el producto y el horizonte, y este botón genera la "
                  "predicción con el modelo entrenado para ese producto.",
            target=_t("btn_predecir_prediccion"),
        ),
    ]
    return Tutorial("centro_inteligencia", "Centro de Inteligencia", "🧠",
                     "Aprende a usar la reposición, la merma y la predicción de demanda", pasos)


TUTORIALES_MODULO: dict[str, Callable[[], Tutorial]] = {
    "compras": _tutorial_compras,
    "inventario": _tutorial_inventario,
    "produccion": _tutorial_produccion,
    "ventas": _tutorial_ventas,
    "costos": _tutorial_costos,
    "centro_inteligencia": _tutorial_centro_inteligencia,
    "reportes": _tutorial_reportes,
}

# Sección I.3 del reporte de bugs: antes no había ningún tutorial que
# explicara "Centro de Inteligencia" ni "Predicción de demanda" — se
# agrega aquí, entre Costos y Reportes, siguiendo el mismo orden que
# tiene el módulo en el menú lateral.
ORDEN_CENTRO_AYUDA = ["general", "compras", "inventario", "produccion", "ventas", "costos",
                      "centro_inteligencia", "reportes"]


def tutoriales_disponibles_para_rol(rol: str) -> list[str]:
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
