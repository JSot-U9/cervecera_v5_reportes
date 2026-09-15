"""
generar_ventas_simuladas.py
===========================
Genera historial de ventas SIMULADO para todos los productos
terminados del ERP, con una volatilidad calibrada a partir de datos
reales de la bolsa (empresas cerveceras locales y globales), y lo
inserta en la base de datos para poder probar el módulo de Predicción
de Demanda con un historial largo y realista.

Uso típico (desde la raíz del proyecto, donde está main.py):

    # 1) Vista previa: no toca la base de datos
    python -m herramientas.generar_ventas_simuladas --dias 730 --solo-csv

    # 2) Generar 2 años de ventas e insertarlas en el ERP
    python -m herramientas.generar_ventas_simuladas --dias 730 --con-inventario

    # 3) Volatilidad alta usando solo la referencia artesanal (SAM)
    python -m herramientas.generar_ventas_simuladas --dias 1095 \
        --tickers SAM --volatilidad alta --semilla 7

    # 4) Borrar todo lo simulado y dejar la base como estaba
    python -m herramientas.generar_ventas_simuladas --limpiar

Las órdenes generadas se marcan con el prefijo "[SIMULADO]" en el
campo observaciones, así que se pueden identificar y eliminar sin
tocar las ventas reales cargadas por datos_iniciales.py.
"""

from __future__ import annotations

import argparse
import math
import sys
from datetime import date, timedelta
from pathlib import Path

import numpy as np
import pandas as pd

# Permite ejecutar el script directamente (python herramientas/....py)
RAIZ = Path(__file__).resolve().parent.parent
if str(RAIZ) not in sys.path:
    sys.path.insert(0, str(RAIZ))

from app.basedatos import nueva_sesion, crear_tablas  # noqa: E402
from app.modelos import (  # noqa: E402
    Cliente, DetalleVenta, LoteInventario, MovimientoInventario,
    OrdenVenta, Producto,
)
from herramientas.simulador_demanda import (  # noqa: E402
    ConfigProducto, generar_choque_comun, simular_producto,
)
from herramientas.volatilidad_mercado import (  # noqa: E402
    FACTOR_ESCALA_DEMANDA, TICKERS_TODOS, obtener_perfiles, perfil_cesta,
)

MARCA_SIMULADO = "[SIMULADO]"

# Multiplicadores del índice de volatilidad
NIVELES_VOLATILIDAD = {
    "baja":   0.5,
    "media":  1.0,
    "alta":   1.8,
    "extrema": 2.8,
}


# ══════════════════════════════════════════════════════════════════
#  1) Configuración de productos a partir del catálogo real del ERP
# ══════════════════════════════════════════════════════════════════
def construir_configuraciones(base_global: float, semilla: int) -> list[ConfigProducto]:
    """
    Lee los productos terminados activos del ERP y les asigna
    parámetros de demanda. Los productos más caros rotan menos y son
    más volátiles (comportamiento típico de ediciones premium).
    """
    rng = np.random.default_rng(semilla)
    with nueva_sesion() as db:
        productos = (
            db.query(Producto)
            .filter(Producto.tipo == "Producto terminado", Producto.activo == True)  # noqa: E712
            .order_by(Producto.id)
            .all()
        )
        productos = [
            {"id": p.id, "nombre": p.nombre, "precio": p.precio_venta or 45.0}
            for p in productos
        ]

    if not productos:
        raise SystemExit(
            "No hay productos terminados en la base de datos.\n"
            "Ejecuta primero la aplicación una vez para cargar datos_iniciales.py."
        )

    precios = np.array([p["precio"] for p in productos], float)
    precio_medio = precios.mean()

    configs = []
    for i, p in enumerate(productos):
        # Elasticidad precio simple: cuanto más caro respecto al
        # promedio, menor rotación.
        relacion = p["precio"] / precio_medio
        factor_precio = float(np.clip(relacion ** -1.6, 0.25, 2.2))
        # Heterogeneidad entre productos (unos son estrella, otros de nicho)
        factor_producto = float(np.clip(rng.lognormal(0.0, 0.45), 0.25, 2.5))

        base = base_global * factor_precio * factor_producto
        base = max(base, 1.2)

        configs.append(ConfigProducto(
            producto_id=p["id"],
            nombre=p["nombre"],
            base_diaria=round(base, 2),
            tendencia_anual=float(rng.normal(0.08, 0.06)),
            intermitencia=float(np.clip(0.18 / math.sqrt(base), 0.0, 0.35)),
            sensibilidad_volatilidad=float(np.clip(relacion ** 0.8, 0.6, 2.0)),
            amplitud_anual=float(rng.uniform(0.18, 0.35)),
            fase_anual=float(rng.normal(172, 12)),   # pico cerca de Inti Raymi
            prob_promocion=float(rng.uniform(0.01, 0.035)),
            efecto_promocion=float(rng.uniform(1.5, 2.3)),
        ))
    return configs


# ══════════════════════════════════════════════════════════════════
#  2) Inserción en la base de datos
# ══════════════════════════════════════════════════════════════════
def _siguiente_numero(db) -> int:
    ultimo = db.query(OrdenVenta).order_by(OrdenVenta.id.desc()).first()
    if not ultimo:
        return 1
    try:
        return int(str(ultimo.numero).split("-")[-1]) + 1
    except (ValueError, IndexError):
        return ultimo.id + 1


def limpiar_simulacion(verbose: bool = True) -> int:
    """Elimina todas las ventas marcadas como simuladas (y sus lotes)."""
    with nueva_sesion() as db:
        ordenes = (
            db.query(OrdenVenta)
            .filter(OrdenVenta.observaciones.like(f"{MARCA_SIMULADO}%"))
            .all()
        )
        ids = [o.id for o in ordenes]
        n_det = 0
        if ids:
            n_det = (
                db.query(DetalleVenta)
                .filter(DetalleVenta.orden_id.in_(ids))
                .delete(synchronize_session=False)
            )
            db.query(OrdenVenta).filter(OrdenVenta.id.in_(ids)).delete(
                synchronize_session=False
            )

        lotes = (
            db.query(LoteInventario)
            .filter(LoteInventario.numero_lote.like("SIM-%"))
            .all()
        )
        lote_ids = [l.id for l in lotes]
        if lote_ids:
            db.query(MovimientoInventario).filter(
                MovimientoInventario.lote_id.in_(lote_ids)
            ).delete(synchronize_session=False)
            db.query(LoteInventario).filter(LoteInventario.id.in_(lote_ids)).delete(
                synchronize_session=False
            )
        db.commit()

    if verbose:
        print(f"  Eliminadas {len(ids)} órdenes simuladas "
              f"({n_det} líneas) y {len(lote_ids)} lotes de simulación.")
    return len(ids)


def insertar_en_bd(
    series: dict[int, pd.DataFrame],
    configs: list[ConfigProducto],
    con_inventario: bool,
    semilla: int,
    verbose: bool = True,
) -> dict:
    """
    Convierte las series diarias en órdenes de venta reales del ERP.

    Cada día se reparte la demanda de todos los productos entre 1 y 3
    clientes, creando una OrdenVenta por cliente con sus DetalleVenta.
    """
    rng = np.random.default_rng(semilla + 999)
    nombres = {c.producto_id: c.nombre for c in configs}

    with nueva_sesion() as db:
        clientes = db.query(Cliente).filter_by(activo=True).all()
        if not clientes:
            raise SystemExit("No hay clientes activos en la base de datos.")
        cliente_ids = [c.id for c in clientes]

        precios = {
            p.id: (p.precio_venta or 45.0)
            for p in db.query(Producto).filter(
                Producto.tipo == "Producto terminado"
            ).all()
        }

        # ── Lotes de inventario (opcional) ────────────────────────
        lotes_por_producto: dict[int, list] = {}
        if con_inventario:
            for pid, df in series.items():
                df = df.copy()
                df["periodo"] = pd.to_datetime(df["fecha"]).dt.to_period("M")
                for periodo, grupo in df.groupby("periodo"):
                    total = float(grupo["cantidad"].sum())
                    if total <= 0:
                        continue
                    fecha_ing = grupo["fecha"].iloc[0]
                    lote = LoteInventario(
                        numero_lote=f"SIM-{pid:03d}-{periodo}",
                        producto_id=pid,
                        fecha_ingreso=fecha_ing,
                        fecha_vencimiento=fecha_ing + timedelta(days=180),
                        cantidad_inicial=round(total * 1.08, 2),
                        cantidad_disponible=round(total * 1.08, 2),
                        costo_unitario=round(precios.get(pid, 45.0) * 0.58, 2),
                        estado="DISPONIBLE",
                    )
                    db.add(lote)
                    db.flush()
                    db.add(MovimientoInventario(
                        lote_id=lote.id, tipo="ENTRADA",
                        cantidad=lote.cantidad_inicial,
                        referencia=f"{MARCA_SIMULADO} producción simulada",
                    ))
                    lotes_por_producto.setdefault(pid, []).append(lote)

        # ── Tabla larga: una fila por (fecha, producto, cantidad) ──
        largo = []
        for pid, df in series.items():
            sub = df[df["cantidad"] > 0][["fecha", "cantidad"]].copy()
            sub["producto_id"] = pid
            largo.append(sub)
        tabla = pd.concat(largo, ignore_index=True) if largo else pd.DataFrame()
        if tabla.empty:
            raise SystemExit("La simulación no generó ninguna venta.")

        numero = _siguiente_numero(db)
        n_ordenes = n_lineas = 0
        total_litros = total_soles = 0.0

        for fecha, grupo in tabla.groupby("fecha", sort=True):
            # ¿En cuántas órdenes se reparte el día?
            n_ord = int(rng.integers(1, min(4, len(grupo) + 1) + 1))
            asignacion = rng.integers(0, n_ord, len(grupo))

            for k in range(n_ord):
                lineas = grupo.iloc[asignacion == k]
                if lineas.empty:
                    continue
                orden = OrdenVenta(
                    numero=f"OV-{numero:05d}",
                    cliente_id=int(rng.choice(cliente_ids)),
                    fecha=fecha,
                    total=0.0,
                    observaciones=f"{MARCA_SIMULADO} venta generada por simulación",
                )
                db.add(orden)
                db.flush()
                numero += 1
                total_orden = 0.0

                for _, fila in lineas.iterrows():
                    pid = int(fila["producto_id"])
                    cant = float(fila["cantidad"])
                    # Pequeña dispersión de precio (descuentos por volumen)
                    precio = round(precios.get(pid, 45.0) * float(rng.normal(1.0, 0.03)), 2)
                    precio = max(precio, 1.0)
                    subtotal = round(cant * precio, 2)

                    lote_id = None
                    if con_inventario:
                        for lote in lotes_por_producto.get(pid, []):
                            if lote.fecha_ingreso <= fecha and lote.cantidad_disponible >= cant:
                                lote.cantidad_disponible = round(
                                    lote.cantidad_disponible - cant, 2
                                )
                                if lote.cantidad_disponible <= 0.001:
                                    lote.estado = "AGOTADO"
                                lote_id = lote.id
                                db.add(MovimientoInventario(
                                    lote_id=lote.id, tipo="VENTA", cantidad=cant,
                                    referencia=orden.numero,
                                ))
                                break

                    db.add(DetalleVenta(
                        orden_id=orden.id, producto_id=pid, lote_id=lote_id,
                        cantidad=cant, precio_unitario=precio, subtotal=subtotal,
                    ))
                    total_orden += subtotal
                    total_litros += cant
                    n_lineas += 1

                orden.total = round(total_orden, 2)
                total_soles += total_orden
                n_ordenes += 1

            if verbose and n_ordenes % 500 == 0 and n_ordenes:
                print(f"    ... {n_ordenes} órdenes insertadas", end="\r")

        db.commit()

    if verbose:
        print(f"  Insertadas {n_ordenes} órdenes de venta con {n_lineas} líneas.")
        print(f"  Total simulado: {total_litros:,.0f} L  ≈  S/ {total_soles:,.2f}")

    return {
        "ordenes": n_ordenes, "lineas": n_lineas,
        "litros": total_litros, "soles": total_soles,
        "productos": len(series), "nombres": nombres,
    }


# ══════════════════════════════════════════════════════════════════
#  3) Reporte de validación
# ══════════════════════════════════════════════════════════════════
def imprimir_reporte(resultados, perfil, escala) -> pd.DataFrame:
    filas = [r.metricas() for r in resultados]
    df = pd.DataFrame(filas)

    print("\n" + "═" * 100)
    print("  DIAGNÓSTICO DE LAS SERIES SIMULADAS")
    print("═" * 100)
    print(f"  Perfil de volatilidad de referencia: {perfil.etiqueta}")
    print(f"    σ diaria mercado = {perfil.sigma_diaria*100:.2f}%   "
          f"σ anual = {perfil.sigma_anual*100:.1f}%   "
          f"α+β = {perfil.persistencia:.3f}   curtosis = {perfil.curtosis:.1f}   "
          f"[{perfil.fuente}]")
    print(f"    Factor de escala a demanda = {escala:.1f}×  →  "
          f"σ objetivo de los choques = {perfil.sigma_diaria*escala*100:.1f}%")
    print("-" * 100)
    encabezado = (f"  {'Producto':<34}{'días':>6}{'media':>9}{'CV':>8}"
                  f"{'%ceros':>8}{'σ_choque':>10}{'findes/sem':>12}{'total L':>12}")
    print(encabezado)
    print("-" * 100)
    for _, f in df.iterrows():
        print(f"  {f['producto'][:33]:<34}{f['dias']:>6.0f}{f['media']:>9.1f}"
              f"{f['cv']:>8.2f}{f['pct_ceros']:>8.1f}{f['sigma_choque']*100:>9.1f}%"
              f"{f['ratio_findesemana']:>12.2f}{f['total']:>12,.0f}")
    print("-" * 100)
    print(f"  {'PROMEDIO':<34}{df['dias'].mean():>6.0f}{df['media'].mean():>9.1f}"
          f"{df['cv'].mean():>8.2f}{df['pct_ceros'].mean():>8.1f}"
          f"{df['sigma_choque'].mean()*100:>9.1f}%"
          f"{df['ratio_findesemana'].mean():>12.2f}{df['total'].sum():>12,.0f}")
    print("═" * 100)
    print("  Lectura rápida:")
    print("   · CV entre 0.35 y 0.80 → variabilidad realista para una PYME de consumo.")
    print("   · findes/sem > 1.4     → la estacionalidad semanal quedó bien marcada")
    print("                            (es la señal que el XGBoost debe aprender).")
    print("   · σ_choque debe acercarse al σ objetivo impreso arriba: es la prueba",
          "de que la volatilidad del mercado se trasladó a la demanda.")
    print("   · %ceros alto sólo debería aparecer en productos de baja rotación.")
    return df


def exportar_csv(series, configs, carpeta: Path) -> Path:
    carpeta.mkdir(parents=True, exist_ok=True)
    nombres = {c.producto_id: c.nombre for c in configs}
    frames = []
    for pid, df in series.items():
        sub = df.copy()
        sub.insert(0, "producto_id", pid)
        sub.insert(1, "producto", nombres[pid])
        frames.append(sub)
    salida = carpeta / "ventas_simuladas.csv"
    pd.concat(frames, ignore_index=True).to_csv(salida, index=False)
    return salida


def exportar_grafico(series, configs, ruta: Path) -> Path | None:
    try:
        import matplotlib
        matplotlib.use("Agg")
        import matplotlib.pyplot as plt
    except ImportError:
        return None

    nombres = {c.producto_id: c.nombre for c in configs}
    pids = list(series.keys())[:4]
    fig, ejes = plt.subplots(len(pids), 1, figsize=(13, 2.6 * len(pids)), sharex=True)
    if len(pids) == 1:
        ejes = [ejes]
    for eje, pid in zip(ejes, pids):
        df = series[pid]
        fechas = pd.to_datetime(df["fecha"])
        eje.plot(fechas, df["cantidad"], lw=0.7, color="#8B5E3C")
        eje.plot(fechas, df["cantidad"].rolling(28, min_periods=1).mean(),
                 lw=1.8, color="#1f4e79", label="media móvil 28d")
        eje.set_title(nombres[pid], fontsize=9, loc="left")
        eje.set_ylabel("L/día", fontsize=8)
        eje.legend(fontsize=7, loc="upper left")
        eje.grid(alpha=0.25)
    fig.suptitle("Demanda diaria simulada — volatilidad calibrada con el sector cervecero",
                 fontsize=11)
    fig.tight_layout()
    ruta.parent.mkdir(parents=True, exist_ok=True)
    fig.savefig(ruta, dpi=130)
    plt.close(fig)
    return ruta


# ══════════════════════════════════════════════════════════════════
#  4) CLI
# ══════════════════════════════════════════════════════════════════
def main(argv=None):
    ap = argparse.ArgumentParser(
        description="Genera ventas simuladas para probar el módulo de predicción.",
        formatter_class=argparse.ArgumentDefaultsHelpFormatter,
    )
    ap.add_argument("--dias", type=int, default=730,
                    help="Días de historial a generar (730 = 2 años).")
    ap.add_argument("--fin", type=str, default=None,
                    help="Fecha final YYYY-MM-DD (por defecto, hoy).")
    ap.add_argument("--base", type=float, default=22.0,
                    help="Demanda media global de referencia en L/día por producto.")
    ap.add_argument("--volatilidad", choices=list(NIVELES_VOLATILIDAD),
                    default="media", help="Nivel del índice de volatilidad.")
    ap.add_argument("--escala-vol", type=float, default=None,
                    help="Sobrescribe el factor de escala mercado→demanda.")
    ap.add_argument("--modo-vol", choices=["garch", "bootstrap", "normal"],
                    default="garch", help="Proceso estocástico de los choques.")
    ap.add_argument("--tickers", nargs="*", default=None,
                    help=f"Tickers a usar. Disponibles: {', '.join(TICKERS_TODOS)}")
    ap.add_argument("--anios-mercado", type=int, default=5,
                    help="Años de historial bursátil para calibrar.")
    ap.add_argument("--forzar-descarga", action="store_true",
                    help="Ignora la caché y vuelve a descargar del mercado.")
    ap.add_argument("--semilla", type=int, default=42, help="Semilla aleatoria.")
    ap.add_argument("--con-inventario", action="store_true",
                    help="Crea lotes y movimientos para que el stock sea coherente.")
    ap.add_argument("--solo-csv", action="store_true",
                    help="No escribe en la base de datos: solo CSV + diagnóstico.")
    ap.add_argument("--limpiar", action="store_true",
                    help="Borra las ventas simuladas previas y termina.")
    ap.add_argument("--reemplazar", action="store_true",
                    help="Borra las ventas simuladas previas antes de generar.")
    ap.add_argument("--salida", type=str, default="datos_simulados",
                    help="Carpeta de salida para CSV y gráfico.")
    args = ap.parse_args(argv)

    crear_tablas()

    if args.limpiar:
        print("\n▸ Limpiando ventas simuladas...")
        limpiar_simulacion()
        return 0

    if args.reemplazar:
        print("\n▸ Limpiando simulaciones anteriores...")
        limpiar_simulacion()

    fecha_fin = date.fromisoformat(args.fin) if args.fin else date.today()
    fecha_inicio = fecha_fin - timedelta(days=args.dias - 1)

    # ── 1. Calibrar volatilidad con el mercado ────────────────────
    print("\n▸ Paso 1/4 — Calibrando volatilidad con el sector cervecero bursátil")
    perfiles = obtener_perfiles(
        tickers=args.tickers, anios=args.anios_mercado,
        forzar_descarga=args.forzar_descarga,
    )
    for p in perfiles.values():
        print("  " + p.resumen())
    perfil = perfil_cesta(perfiles, etiqueta="Índice cervecero sintético")
    print("  " + perfil.resumen())

    escala = args.escala_vol if args.escala_vol is not None else (
        FACTOR_ESCALA_DEMANDA * NIVELES_VOLATILIDAD[args.volatilidad]
    )

    # ── 2. Configurar productos ───────────────────────────────────
    print(f"\n▸ Paso 2/4 — Configurando productos del catálogo")
    configs = construir_configuraciones(args.base, args.semilla)
    print(f"  {len(configs)} productos terminados activos.")
    print(f"  Periodo: {fecha_inicio} → {fecha_fin}  ({args.dias} días)")

    # ── 3. Simular ────────────────────────────────────────────────
    print(f"\n▸ Paso 3/4 — Simulando demanda (modo={args.modo_vol}, "
          f"volatilidad={args.volatilidad}, escala={escala:.1f}×)")
    rng = np.random.default_rng(args.semilla)
    n = (fecha_fin - fecha_inicio).days + 1
    choque_comun = generar_choque_comun(n, perfil, rng, escala=escala, modo=args.modo_vol)

    resultados, series = [], {}
    for cfg in configs:
        res = simular_producto(
            cfg, fecha_inicio, fecha_fin, perfil, rng,
            escala_volatilidad=escala, modo_volatilidad=args.modo_vol,
            choque_comun=choque_comun,
        )
        resultados.append(res)
        series[cfg.producto_id] = res.df[["fecha", "cantidad"]].copy()

    df_diag = imprimir_reporte(resultados, perfil, escala)

    carpeta = Path(args.salida)
    ruta_csv = exportar_csv(
        {c.producto_id: r.df for c, r in zip(configs, resultados)}, configs, carpeta
    )
    print(f"\n  CSV detallado: {ruta_csv}")
    df_diag.to_csv(carpeta / "diagnostico_simulacion.csv", index=False)
    ruta_png = exportar_grafico(series, configs, carpeta / "series_simuladas.png")
    if ruta_png:
        print(f"  Gráfico:       {ruta_png}")

    # ── 4. Insertar en la base de datos ───────────────────────────
    if args.solo_csv:
        print("\n▸ Paso 4/4 — Omitido (--solo-csv): la base de datos no fue modificada.")
        return 0

    print("\n▸ Paso 4/4 — Insertando en la base de datos del ERP")
    insertar_en_bd(series, configs, args.con_inventario, args.semilla)
    print("\n✔ Listo. Abre el ERP → módulo «Predicción Demanda» → «Entrenar/actualizar».")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
