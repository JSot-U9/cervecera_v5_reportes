"""
logica_reportes.py
==================
Genera reportes en PDF, XLSX y CSV.

Cada función de reporte acepta un parámetro opcional `ruta: Path | str`.
Si se omite, devuelve el documento sin guardarlo en disco (útil para la
vista previa). Si se indica, guarda en esa ruta exacta.

Reportes disponibles:
  - reporte_costos()
  - reporte_stock()
  - reporte_compras()
  - reporte_ventas()
  - reporte_produccion()

Cada uno devuelve un dict con:
  {
    "titulo": str,
    "columnas": list[str],
    "filas": list[list],      # valores ya formateados como strings
    "kpis": list[dict],       # [{"etiqueta": ..., "valor": ...}, ...]  (puede ser [])
  }

Las funciones de exportación (guardar_pdf / guardar_xlsx / guardar_csv)
reciben ese dict + una ruta y producen el archivo.
"""

import csv
import io
from datetime import date, datetime
from pathlib import Path

# ── ReportLab ─────────────────────────────────────────────────────
from reportlab.lib import colors
from reportlab.lib.pagesizes import A4, landscape
from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle
from reportlab.lib.units import cm
from reportlab.platypus import (
    SimpleDocTemplate, Paragraph, Spacer, Table, TableStyle, HRFlowable,
)

# ── OpenPyXL ──────────────────────────────────────────────────────
from openpyxl import Workbook
from openpyxl.styles import Font, PatternFill, Alignment, Border, Side
from openpyxl.utils import get_column_letter

# ── Paleta de colores ─────────────────────────────────────────────
_VERDE_OSCURO = colors.HexColor("#2B361C")
_LEATHER      = colors.HexColor("#B17036")
_SEPIA_CLARO  = colors.HexColor("#FEFAE3")
_MARINE_GREEN = colors.HexColor("#636B3F")
_TEXTO        = colors.HexColor("#2B361C")
_TEXTO_SEC    = colors.HexColor("#74795A")
_ROJO         = colors.HexColor("#B3432B")
_VERDE_OK     = colors.HexColor("#4B7B3F")
_BLANCO       = colors.white
_GRIS_LINEA   = colors.HexColor("#E5D6B3")

# Paleta XLSX (hex sin #, para openpyxl)
_XL_VERDE  = "2B361C"
_XL_AMBER  = "B17036"
_XL_SEPIA  = "FEFAE3"
_XL_MARINE = "636B3F"
_XL_ROJO   = "B3432B"
_XL_VERDE_OK = "4B7B3F"


# ══════════════════════════════════════════════════════════════════
#  DATOS CRUDOS — cada función devuelve el dict estándar
# ══════════════════════════════════════════════════════════════════

def datos_costos() -> dict:
    from app.logica_costos import resumen_costos, kpis_costos
    kpis = kpis_costos()
    filas = resumen_costos()
    return {
        "titulo": "Reporte de Costos por Lote de Producción",
        "orientacion": "landscape",
        "columnas": [
            "N° Orden Prod.", "N° de Lote", "Producto",
            "Cantidad (L)", "Costo Insumos (S/)", "Costo M.O. (S/)",
            "Costos Indirectos (S/)", "Costo Total (S/)",
            "Costo Unitario (S/)", "Margen (%)",
        ],
        "filas": [
            [
                f["orden"], f["lote"], f["producto"],
                f"{f['cantidad']:.1f}",
                f"S/ {f['costo_insumos']:.2f}",
                f"S/ {f['costo_mano_obra']:.2f}",
                f"S/ {f['costo_indirectos']:.2f}",
                f"S/ {f['costo_total']:.2f}",
                f"S/ {f['costo_unitario']:.2f}",
                f"{f['margen_porcentaje']:.1f}%",
            ]
            for f in filas
        ],
        "kpis": [
            {"etiqueta": "Lotes costeados",            "valor": str(kpis["n_lotes"])},
            {"etiqueta": "Costo total acumulado",      "valor": f"S/ {kpis['costo_total']:,.2f}"},
            {"etiqueta": "Margen promedio",            "valor": f"{kpis['margen_promedio']:.1f} %"},
            {"etiqueta": "Costo unitario promedio",    "valor": f"S/ {kpis['costo_unitario_promedio']:.2f}"},
        ],
    }


def datos_stock() -> dict:
    from app.basedatos import nueva_sesion
    from app.modelos import Producto
    from app.logica_inventario import stock_total
    filas = []
    with nueva_sesion() as db:
        for p in db.query(Producto).filter_by(activo=True).order_by(Producto.tipo, Producto.nombre).all():
            stock = stock_total(db, p.id)
            estado = "OK" if stock >= p.stock_minimo else "BAJO"
            filas.append([
                p.codigo, p.nombre, p.tipo,
                f"{stock:.2f}", p.unidad_medida or "—",
                f"{p.stock_minimo:.2f}", estado,
            ])
    return {
        "titulo": "Reporte de Stock Actual",
        "orientacion": "portrait",
        "columnas": ["Código", "Nombre del Producto", "Tipo",
                     "Stock Disponible", "Unidad", "Stock Mínimo", "Estado"],
        "filas": filas,
        "kpis": [],
    }


def datos_compras() -> dict:
    from app.logica_compras import listar_ordenes_compra
    ordenes = listar_ordenes_compra()
    filas = []
    total = 0.0
    for o in ordenes:
        filas.append([o.numero, o.proveedor.razon_social,
                      str(o.fecha), o.documento_referencia or "—",
                      f"S/ {o.total:,.2f}"])
        total += o.total
    return {
        "titulo": "Reporte de Órdenes de Compra",
        "orientacion": "portrait",
        "columnas": ["N° Orden Compra", "Proveedor", "Fecha", "Doc. Referencia", "Total (S/)"],
        "filas": filas,
        "kpis": [
            {"etiqueta": "Órdenes de compra", "valor": str(len(filas))},
            {"etiqueta": "Total acumulado",   "valor": f"S/ {total:,.2f}"},
        ],
    }


def datos_ventas() -> dict:
    from app.logica_ventas import listar_ordenes_venta
    ordenes = listar_ordenes_venta()
    filas = []
    total = 0.0
    for o in ordenes:
        filas.append([o.numero, o.cliente.nombre, str(o.fecha), f"S/ {o.total:,.2f}"])
        total += o.total
    return {
        "titulo": "Reporte de Órdenes de Venta",
        "orientacion": "portrait",
        "columnas": ["N° Orden Venta", "Cliente", "Fecha", "Total (S/)"],
        "filas": filas,
        "kpis": [
            {"etiqueta": "Órdenes de venta", "valor": str(len(filas))},
            {"etiqueta": "Total ingresos",   "valor": f"S/ {total:,.2f}"},
        ],
    }


def datos_produccion() -> dict:
    from app.logica_produccion import listar_ordenes
    ordenes = listar_ordenes()
    filas = []
    for o in ordenes:
        producto = o.receta.producto_terminado.nombre if o.receta else "—"
        filas.append([
            o.numero, producto, o.numero_lote,
            f"{o.cantidad_planeada:.1f}",
            f"{o.cantidad_real:.1f}" if o.cantidad_real else "—",
            str(o.fecha_inicio) if o.fecha_inicio else "—",
            str(o.fecha_fin) if o.fecha_fin else "—",
            o.estado,
        ])
    return {
        "titulo": "Reporte de Órdenes de Producción",
        "orientacion": "landscape",
        "columnas": [
            "N° Orden Prod.", "Producto", "N° de Lote",
            "Cant. Planeada", "Cant. Real",
            "Fecha Inicio", "Fecha Fin", "Estado",
        ],
        "filas": filas,
        "kpis": [],
    }


# Mapa público: nombre → función de datos
REPORTES = {
    "costos":     datos_costos,
    "stock":      datos_stock,
    "compras":    datos_compras,
    "ventas":     datos_ventas,
    "produccion": datos_produccion,
}

NOMBRES_LEGIBLES = {
    "costos":     "Costos",
    "stock":      "Stock",
    "compras":    "Compras",
    "ventas":     "Ventas",
    "produccion": "Producción",
}


# ══════════════════════════════════════════════════════════════════
#  EXPORTADORES
# ══════════════════════════════════════════════════════════════════

def guardar_pdf(datos: dict, ruta: Path) -> Path:
    """Genera un PDF con los datos del reporte y lo guarda en ruta."""
    ruta = Path(ruta)
    orientacion = landscape(A4) if datos.get("orientacion") == "landscape" else A4
    doc = SimpleDocTemplate(
        str(ruta), pagesize=orientacion,
        leftMargin=1.5*cm, rightMargin=1.5*cm,
        topMargin=1.5*cm, bottomMargin=1.5*cm,
    )

    base = getSampleStyleSheet()
    est = {
        "titulo": ParagraphStyle("titulo", parent=base["Title"],
                                 textColor=_VERDE_OSCURO, fontSize=18, spaceAfter=4),
        "subtitulo": ParagraphStyle("subtitulo", parent=base["Normal"],
                                    textColor=_TEXTO_SEC, fontSize=10, spaceAfter=2),
        "seccion": ParagraphStyle("seccion", parent=base["Heading2"],
                                  textColor=_LEATHER, fontSize=11, spaceBefore=12, spaceAfter=6),
    }

    historia = [
        Paragraph("CERVECERÍA DEL VALLE SAGRADO", est["titulo"]),
        Paragraph("Cusco, Perú", est["subtitulo"]),
        HRFlowable(width="100%", thickness=2, color=_LEATHER, spaceAfter=6),
        Paragraph(datos["titulo"].upper(), est["seccion"]),
        Paragraph(f"Fecha: {date.today().strftime('%d/%m/%Y')}", est["subtitulo"]),
        Spacer(1, 0.3*cm),
    ]

    # KPIs
    if datos.get("kpis"):
        kpi_data = [["INDICADOR", "VALOR"]] + [[k["etiqueta"], k["valor"]] for k in datos["kpis"]]
        t_kpi = Table(kpi_data, colWidths=[8*cm, 6*cm])
        t_kpi.setStyle(TableStyle([
            ("BACKGROUND",    (0, 0), (1, 0), _LEATHER),
            ("TEXTCOLOR",     (0, 0), (1, 0), _BLANCO),
            ("FONTNAME",      (0, 0), (-1, 0), "Helvetica-Bold"),
            ("FONTNAME",      (0, 1), (0, -1), "Helvetica-Bold"),
            ("FONTSIZE",      (0, 0), (-1, -1), 9),
            ("ROWBACKGROUNDS", (0, 1), (-1, -1), [_BLANCO, _SEPIA_CLARO]),
            ("GRID",          (0, 0), (-1, -1), 0.3, _GRIS_LINEA),
            ("TOPPADDING",    (0, 0), (-1, -1), 5),
            ("BOTTOMPADDING", (0, 0), (-1, -1), 5),
        ]))
        historia += [t_kpi, Spacer(1, 0.5*cm)]

    # Tabla de datos
    tabla_data = [datos["columnas"]] + (datos["filas"] or [["Sin datos registrados"]])
    ncols = len(datos["columnas"])
    ancho_col = (doc.width) / ncols
    t = Table(tabla_data, colWidths=[ancho_col] * ncols, repeatRows=1)
    estilo = TableStyle([
        ("BACKGROUND",    (0, 0), (ncols-1, 0), _VERDE_OSCURO),
        ("TEXTCOLOR",     (0, 0), (ncols-1, 0), _BLANCO),
        ("FONTNAME",      (0, 0), (ncols-1, 0), "Helvetica-Bold"),
        ("FONTSIZE",      (0, 0), (-1, -1), 8),
        ("TOPPADDING",    (0, 0), (-1, -1), 5),
        ("BOTTOMPADDING", (0, 0), (-1, -1), 5),
        ("ROWBACKGROUNDS", (0, 1), (-1, -1), [_BLANCO, _SEPIA_CLARO]),
        ("LINEBELOW",     (0, 0), (-1, 0),  0.8, _LEATHER),
        ("LINEBELOW",     (0, 1), (-1, -1), 0.3, _GRIS_LINEA),
        ("GRID",          (0, 0), (-1, -1), 0.2, _GRIS_LINEA),
        ("VALIGN",        (0, 0), (-1, -1), "MIDDLE"),
    ])
    t.setStyle(estilo)
    historia.append(t)

    # Pie
    ahora = datetime.now().strftime("%d/%m/%Y %H:%M")
    historia += [
        Spacer(1, 0.4*cm),
        HRFlowable(width="100%", thickness=0.5, color=_GRIS_LINEA),
        Paragraph(f"Reporte generado el {ahora} por el Sistema de Gestión.", est["subtitulo"]),
    ]

    doc.build(historia)
    return ruta


def guardar_xlsx(datos: dict, ruta: Path) -> Path:
    """Genera un archivo Excel (.xlsx) con los datos del reporte."""
    ruta = Path(ruta)
    wb = Workbook()
    ws = wb.active
    ws.title = datos["titulo"][:31]  # Excel limita a 31 chars

    # Estilos
    fill_header  = PatternFill("solid", fgColor=_XL_VERDE)
    fill_kpi_hdr = PatternFill("solid", fgColor=_XL_AMBER)
    fill_alt     = PatternFill("solid", fgColor=_XL_SEPIA)
    font_hdr     = Font(bold=True, color="FFFFFF", size=10)
    font_kpi_lbl = Font(bold=True, color=_XL_VERDE, size=10)
    font_title   = Font(bold=True, color=_XL_VERDE, size=14)
    border_thin  = Border(
        bottom=Side(style="thin", color="E5D6B3"),
        right=Side(style="thin",  color="E5D6B3"),
    )
    alin_centro = Alignment(horizontal="center", vertical="center", wrap_text=True)
    alin_izq    = Alignment(horizontal="left",   vertical="center", wrap_text=True)

    ncols = len(datos["columnas"])
    col_fin = get_column_letter(max(ncols, 2))

    # Fila 1: título empresa
    ws.merge_cells(f"A1:{col_fin}1")
    c = ws["A1"]
    c.value = "CERVECERÍA DEL VALLE SAGRADO — Cusco, Perú"
    c.font  = font_title
    c.alignment = alin_centro
    ws.row_dimensions[1].height = 22

    # Fila 2: título reporte
    ws.merge_cells(f"A2:{col_fin}2")
    c = ws["A2"]
    c.value = datos["titulo"].upper()
    c.font  = Font(bold=True, color=_XL_AMBER, size=11)
    c.alignment = alin_centro
    ws.row_dimensions[2].height = 18

    # Fila 3: fecha
    ws.merge_cells(f"A3:{col_fin}3")
    c = ws["A3"]
    c.value = f"Fecha: {date.today().strftime('%d/%m/%Y')}"
    c.font  = Font(color="74795A", size=9)
    c.alignment = alin_centro

    fila_cursor = 5

    # KPIs
    if datos.get("kpis"):
        ws.cell(fila_cursor, 1).value = "INDICADOR"
        ws.cell(fila_cursor, 1).font  = Font(bold=True, color="FFFFFF", size=9)
        ws.cell(fila_cursor, 1).fill  = fill_kpi_hdr
        ws.cell(fila_cursor, 1).alignment = alin_centro
        ws.cell(fila_cursor, 2).value = "VALOR"
        ws.cell(fila_cursor, 2).font  = Font(bold=True, color="FFFFFF", size=9)
        ws.cell(fila_cursor, 2).fill  = fill_kpi_hdr
        ws.cell(fila_cursor, 2).alignment = alin_centro
        fila_cursor += 1
        for k in datos["kpis"]:
            ws.cell(fila_cursor, 1).value = k["etiqueta"]
            ws.cell(fila_cursor, 1).font  = font_kpi_lbl
            ws.cell(fila_cursor, 1).alignment = alin_izq
            ws.cell(fila_cursor, 2).value = k["valor"]
            ws.cell(fila_cursor, 2).alignment = alin_izq
            fila_cursor += 1
        fila_cursor += 1

    # Encabezado tabla
    for j, col in enumerate(datos["columnas"], 1):
        c = ws.cell(fila_cursor, j)
        c.value     = col
        c.font      = font_hdr
        c.fill      = fill_header
        c.alignment = alin_centro
        c.border    = border_thin
    ws.row_dimensions[fila_cursor].height = 30
    fila_cursor += 1

    # Filas de datos
    for i, fila in enumerate(datos["filas"]):
        fill_fila = fill_alt if i % 2 == 1 else None
        for j, val in enumerate(fila, 1):
            c = ws.cell(fila_cursor, j)
            c.value     = val
            c.alignment = alin_izq
            c.border    = border_thin
            if fill_fila:
                c.fill = fill_fila
        fila_cursor += 1

    # Ajuste automático de ancho de columnas
    for j in range(1, ncols + 1):
        col_letter = get_column_letter(j)
        max_ancho = 12
        for fila_ws in ws.iter_rows(min_col=j, max_col=j):
            for cell in fila_ws:
                if cell.value:
                    max_ancho = max(max_ancho, len(str(cell.value)) + 2)
        ws.column_dimensions[col_letter].width = min(max_ancho, 40)

    # Pie
    fila_cursor += 1
    ahora = datetime.now().strftime("%d/%m/%Y %H:%M")
    ws.merge_cells(f"A{fila_cursor}:{col_fin}{fila_cursor}")
    c = ws.cell(fila_cursor, 1)
    c.value = f"Reporte generado el {ahora} por el Sistema de Gestión."
    c.font  = Font(color="74795A", size=8, italic=True)
    c.alignment = alin_izq

    wb.save(str(ruta))
    return ruta


def guardar_csv(datos: dict, ruta: Path) -> Path:
    """Genera un archivo CSV con los datos del reporte."""
    ruta = Path(ruta)
    with open(ruta, "w", newline="", encoding="utf-8-sig") as f:
        writer = csv.writer(f)
        writer.writerow([datos["titulo"], f"Fecha: {date.today().strftime('%d/%m/%Y')}"])
        writer.writerow([])
        if datos.get("kpis"):
            writer.writerow(["INDICADOR", "VALOR"])
            for k in datos["kpis"]:
                writer.writerow([k["etiqueta"], k["valor"]])
            writer.writerow([])
        writer.writerow(datos["columnas"])
        writer.writerows(datos["filas"])
        writer.writerow([])
        writer.writerow([f"Generado: {datetime.now().strftime('%d/%m/%Y %H:%M')}"])
    return ruta


# ══════════════════════════════════════════════════════════════════
#  API de compatibilidad (mantiene los nombres originales)
# ══════════════════════════════════════════════════════════════════

def _nombre_archivo(nombre_base: str, ext: str = "pdf") -> Path:
    home = Path.home()
    for candidato in ("Downloads", "Descargas", "Desktop", "Escritorio"):
        ruta = home / candidato
        if ruta.exists():
            break
    else:
        ruta = home
    ts = datetime.now().strftime("%Y%m%d_%H%M%S")
    return ruta / f"{nombre_base}_{ts}.{ext}"


def reporte_costos()     -> Path: return guardar_pdf(datos_costos(),     _nombre_archivo("Reporte_Costos"))
def reporte_stock()      -> Path: return guardar_pdf(datos_stock(),      _nombre_archivo("Reporte_Stock"))
def reporte_compras()    -> Path: return guardar_pdf(datos_compras(),    _nombre_archivo("Reporte_Compras"))
def reporte_ventas()     -> Path: return guardar_pdf(datos_ventas(),     _nombre_archivo("Reporte_Ventas"))
def reporte_produccion() -> Path: return guardar_pdf(datos_produccion(), _nombre_archivo("Reporte_Produccion"))
