"""
reposicion.py
=============
Motor de "Reposición inteligente" — el componente PRESCRIPTIVO del
núcleo de IA (sección 3.3 de la propuesta). Combina:

  1) la demanda esperada de cada producto terminado (módulo de
     Predicción de Demanda, demanda_prediction.py),
  2) la merma esperada de cada receta al producirlo (módulo de
     Predicción de Merma, merma_prediction.py), y
  3) el stock disponible de cada insumo (logica_inventario.py)

...para recomendar CUÁNTO insumo conviene reponer, sin ejecutar
ninguna compra automáticamente. La fórmula usada es exactamente la
de la propuesta, mantenida simple y transparente a propósito:

    Cantidad a reponer = Demanda esperada durante el periodo
                          de cobertura
                        + Stock de seguridad
                        - Stock disponible

El "motivo" de cada recomendación se guarda en texto plano para que
el usuario pueda entender de dónde sale el número antes de decidir
si genera la orden de compra (integración con Compras).
"""

from __future__ import annotations

import math
from datetime import date, timedelta

from app.basedatos import nueva_sesion
from app.modelos import (
    Producto, Receta, IngredienteReceta, MovimientoInventario, LoteInventario,
)
from app.logica_inventario import stock_total

from app.ia.demanda_data import diagnostico_historial as diag_demanda
from app.ia.demanda_prediction import predecir_demanda
from app.ia.merma_prediction import predecir_merma

# Parámetros por defecto del motor (simples y ajustables desde la UI)
HORIZONTE_DIAS_DEFECTO = 14
DIAS_COBERTURA_SEGURIDAD_DEFECTO = 5   # "colchón" expresado en días extra de consumo
DIAS_HISTORIAL_CONSUMO = 90            # ventana para medir consumo histórico de insumos


def _consumo_diario_historico(db, insumo_id: int) -> dict:
    """
    Consumo diario histórico de un insumo (movimientos tipo CONSUMO,
    es decir, lo que se ha usado en producción), de los últimos
    DIAS_HISTORIAL_CONSUMO días. Devuelve promedio y desviación
    diarios, útiles como respaldo transparente cuando no hay
    pronóstico de demanda disponible (por ejemplo, insumos que no
    están ligados a ninguna receta activa).
    """
    desde = date.today() - timedelta(days=DIAS_HISTORIAL_CONSUMO)
    filas = (
        db.query(MovimientoInventario.fecha, MovimientoInventario.cantidad)
        .join(LoteInventario, LoteInventario.id == MovimientoInventario.lote_id)
        .filter(
            LoteInventario.producto_id == insumo_id,
            MovimientoInventario.tipo == "CONSUMO",
            MovimientoInventario.fecha >= desde,
        )
        .all()
    )
    if not filas:
        return {"media_diaria": 0.0, "desviacion_diaria": 0.0, "dias_con_datos": 0}

    import pandas as pd
    df = pd.DataFrame(filas, columns=["fecha", "cantidad"])
    df["fecha"] = pd.to_datetime(df["fecha"]).dt.date
    diario = df.groupby("fecha")["cantidad"].sum()
    # Se completan con 0 los días sin consumo dentro de la ventana observada,
    # para que el promedio no quede inflado.
    rango = pd.date_range(diario.index.min(), date.today(), freq="D")
    diario = diario.reindex(rango.date, fill_value=0.0)
    return {
        "media_diaria": float(diario.mean()),
        "desviacion_diaria": float(diario.std(ddof=0) or 0.0),
        "dias_con_datos": int(len(diario)),
    }


def _demanda_proyectada_insumos(horizonte_dias: int) -> dict:
    """
    Traduce la demanda prevista de cada producto terminado (con
    receta activa) a la cantidad de insumos que haría falta para
    producirlo, inflando la cantidad por la merma esperada de la
    receta (si se espera perder más, hace falta planear producir más
    para llegar a la misma cantidad neta).

    Retorna
    -------
    dict {insumo_id: {"cantidad": float, "origen": str, "detalle": [str, ...]}}
    """
    resultado: dict[int, dict] = {}

    with nueva_sesion() as db:
        recetas = (
            db.query(Receta)
            .filter_by(activa=True)
            .all()
        )
        for receta in recetas:
            if not receta.producto_terminado or receta.rendimiento <= 0:
                continue
            producto_terminado_id = receta.producto_terminado_id
            nombre_producto = receta.producto_terminado.nombre

            diag = diag_demanda(producto_terminado_id)
            if not diag["suficiente_baseline"]:
                continue  # sin historial de ventas suficiente para proyectar este producto

            pred = predecir_demanda(producto_terminado_id, horizonte_dias)
            if not pred.get("exito"):
                continue
            demanda_prevista = pred["demanda_total"]
            if demanda_prevista <= 0:
                continue

            # Inflar por merma esperada de la receta, usando el propio
            # rendimiento como "cantidad planeada" representativa de un lote.
            merma = predecir_merma(receta.id, receta.rendimiento, date.today())
            merma_pct = (merma.get("merma_pct_esperada", 0.0) / 100.0) if merma.get("exito") else 0.0
            merma_pct = min(merma_pct, 0.60)  # tope de seguridad para no distorsionar el cálculo
            factor_merma = 1.0 / (1.0 - merma_pct) if merma_pct < 0.95 else 1.0

            lotes_necesarios = (demanda_prevista * factor_merma) / receta.rendimiento

            for ingrediente in receta.ingredientes:
                cantidad_insumo = ingrediente.cantidad * lotes_necesarios
                entrada = resultado.setdefault(
                    ingrediente.insumo_id, {"cantidad": 0.0, "origen": "modelo_demanda", "detalle": []}
                )
                entrada["cantidad"] += cantidad_insumo
                entrada["detalle"].append(
                    f"{nombre_producto}: {demanda_prevista:.1f} unid. previstas "
                    f"(+{merma_pct * 100:.1f}% merma esperada) → {cantidad_insumo:.2f} "
                    f"{ingrediente.unidad or ''} de este insumo"
                )

    return resultado


def _evaluar_insumo(db, insumo, proyeccion: dict, horizonte_dias: int,
                     dias_cobertura_seguridad: int) -> dict | None:
    """Evalúa la recomendación de reposición de UN insumo puntual.
    Factorizado fuera de calcular_recomendaciones() para que
    calcular_recomendacion_individual() (usada desde el detalle de
    producto) pueda reevaluar un solo insumo sin repetir esta lógica.
    Devuelve None si no hace falta mostrarlo (sin necesidad de
    reposición y no está bajo el stock mínimo)."""
    stock_disponible = stock_total(db, insumo.id)
    consumo_hist = _consumo_diario_historico(db, insumo.id)
    proy = proyeccion.get(insumo.id)

    if proy and proy["cantidad"] > 0:
        demanda_esperada = proy["cantidad"]
        origen = proy["origen"]
        detalle_origen = "; ".join(proy["detalle"][:3])
    elif consumo_hist["dias_con_datos"] > 0 and consumo_hist["media_diaria"] > 0:
        demanda_esperada = consumo_hist["media_diaria"] * horizonte_dias
        origen = "historico"
        detalle_origen = (
            f"consumo histórico promedio de {consumo_hist['media_diaria']:.2f} "
            f"{insumo.unidad_medida or ''}/día en los últimos {DIAS_HISTORIAL_CONSUMO} días"
        )
    else:
        demanda_esperada = 0.0
        origen = "sin_datos"
        detalle_origen = "sin historial de consumo ni pronóstico de demanda disponible"

    if consumo_hist["dias_con_datos"] > 0:
        stock_seguridad = (
            consumo_hist["media_diaria"] * dias_cobertura_seguridad
            + 1.65 * consumo_hist["desviacion_diaria"] * math.sqrt(max(dias_cobertura_seguridad, 1))
        )
    else:
        stock_seguridad = insumo.stock_minimo or 0.0

    cantidad_recomendada = max(0.0, demanda_esperada + stock_seguridad - stock_disponible)

    bajo_minimo = stock_disponible <= (insumo.stock_minimo or 0.0)
    if bajo_minimo:
        prioridad = "ALTA"
    elif cantidad_recomendada > 0 and demanda_esperada > 0:
        cobertura_dias = (
            stock_disponible / consumo_hist["media_diaria"]
            if consumo_hist["media_diaria"] > 0 else None
        )
        prioridad = "MEDIA" if (cobertura_dias is None or cobertura_dias <= horizonte_dias) else "BAJA"
    else:
        prioridad = "BAJA"

    if cantidad_recomendada <= 0 and not bajo_minimo:
        return None  # no hace falta mostrar insumos sin necesidad de reposición

    motivo = (
        f"Demanda esperada ({horizonte_dias} días): {demanda_esperada:.2f} "
        f"{insumo.unidad_medida or ''} [{detalle_origen}] "
        f"+ stock de seguridad {stock_seguridad:.2f} "
        f"− stock disponible {stock_disponible:.2f}."
    )

    return {
        "producto_id": insumo.id,
        "codigo": insumo.codigo,
        "nombre": insumo.nombre,
        "unidad": insumo.unidad_medida or "",
        "stock_disponible": round(stock_disponible, 2),
        "stock_minimo": insumo.stock_minimo or 0.0,
        "demanda_esperada": round(demanda_esperada, 2),
        "stock_seguridad": round(stock_seguridad, 2),
        "cantidad_recomendada": round(cantidad_recomendada, 2),
        "origen_demanda": origen,
        "prioridad": prioridad,
        "motivo": motivo,
    }


def calcular_recomendaciones(
    horizonte_dias: int = HORIZONTE_DIAS_DEFECTO,
    dias_cobertura_seguridad: int = DIAS_COBERTURA_SEGURIDAD_DEFECTO,
) -> list[dict]:
    """
    Calcula la recomendación de reposición para cada insumo activo.

    Retorna una lista de dicts (uno por insumo con cantidad recomendada
    mayor a 0, o en riesgo de quiebre), ordenada por prioridad, con
    claves:
      producto_id, codigo, nombre, unidad,
      stock_disponible, stock_minimo,
      demanda_esperada, stock_seguridad, cantidad_recomendada,
      origen_demanda ("modelo_demanda" | "historico" | "sin_datos"),
      prioridad ("ALTA" | "MEDIA" | "BAJA"),
      motivo (str)
    """
    proyeccion = _demanda_proyectada_insumos(horizonte_dias)
    recomendaciones = []

    with nueva_sesion() as db:
        insumos = db.query(Producto).filter_by(tipo="Insumo", activo=True).all()

        for insumo in insumos:
            r = _evaluar_insumo(db, insumo, proyeccion, horizonte_dias, dias_cobertura_seguridad)
            if r is not None:
                recomendaciones.append(r)

    orden_prioridad = {"ALTA": 0, "MEDIA": 1, "BAJA": 2}
    recomendaciones.sort(
        key=lambda r: (orden_prioridad.get(r["prioridad"], 3), -r["cantidad_recomendada"])
    )
    return recomendaciones


def calcular_recomendacion_individual(
    insumo_id: int,
    horizonte_dias: int = HORIZONTE_DIAS_DEFECTO,
    dias_cobertura_seguridad: int = DIAS_COBERTURA_SEGURIDAD_DEFECTO,
) -> dict | None:
    """Recalcula la recomendación de reposición de UN solo insumo (la
    usa la pestaña "🧠 Inteligencia" del detalle de producto, en
    Inventario, para no tener que disparar el cálculo completo del
    motor — que recorre TODO el catálogo de insumos — solo para ver
    el número de uno.

    Nota honesta sobre el alcance de la optimización: el paso que sigue
    siendo "global" es _demanda_proyectada_insumos(), porque la demanda
    de un insumo depende de TODAS las recetas activas que lo usan — no
    hay forma de acotar ESE cálculo a un solo insumo sin cambiar la
    fórmula del motor. Lo que SÍ se evita es recorrer el stock
    disponible y el consumo histórico de cada insumo del catálogo
    (la parte que crece con el tamaño del catálogo): esa parte se hace
    una sola vez, para el insumo pedido.

    Devuelve el mismo dict que un elemento de calcular_recomendaciones(),
    o None si el insumo no existe, no es de tipo "Insumo", está
    inactivo, o no necesita reposición ahora mismo.
    """
    proyeccion = _demanda_proyectada_insumos(horizonte_dias)
    with nueva_sesion() as db:
        insumo = db.get(Producto, insumo_id)
        if insumo is None or insumo.tipo != "Insumo" or not insumo.activo:
            return None
        return _evaluar_insumo(db, insumo, proyeccion, horizonte_dias, dias_cobertura_seguridad)
