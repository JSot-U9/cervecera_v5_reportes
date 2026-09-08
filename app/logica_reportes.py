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

NOTA DE ESTA VERSIÓN:
  - El PDF ahora se genera SIEMPRE en orientación vertical (portrait),
    sin importar lo que indique la clave "orientacion" del dict de datos
    (se deja esa clave en los dicts por compatibilidad, pero ya no se usa
    para decidir el pagesize).
  - Los anchos de columna de la tabla principal del PDF se calculan
    automáticamente según el contenido más largo de cada columna
    (incluyendo el encabezado), en vez de repartir el ancho en partes
    iguales. Además, cada celda se envuelve en un Paragraph para que el
    texto largo haga salto de línea dentro de su columna en vez de
    desbordarse.
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
from reportlab.pdfbase.pdfmetrics import stringWidth
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
#  UTILIDADES DE MAQUETACIÓN (PDF)
# ══════════════════════════════════════════════════════════════════

def _anchos_columnas(tabla_data, ancho_disponible,
                      fuente="Helvetica", fuente_negrita="Helvetica-Bold",
                      tam=8, min_col=1.8 * cm, max_col=7 * cm, padding=12):
    """Calcula el ancho ideal de cada columna según el contenido más largo
    (incluyendo el encabezado en negrita), y escala el resultado para que
    la suma de todas las columnas encaje exactamente en `ancho_disponible`.

    - min_col / max_col evitan columnas ilegibles o desproporcionadas.
    - padding es el margen interno aproximado (izq+der) de cada celda.
    """
    ncols = len(tabla_data[0])
    anchos = [0.0] * ncols
    for i, fila in enumerate(tabla_data):
        f = fuente_negrita if i == 0 else fuente
        for j, val in enumerate(fila):
            texto = str(val)
            # Si el valor ya es multilínea (contiene \n), medimos la línea más larga
            linea_mas_larga = max(texto.split("\n"), key=len) if "\n" in texto else texto
            ancho_txt = stringWidth(linea_mas_larga, f, tam) + padding
            anchos[j] = max(anchos[j], ancho_txt)

    # aplicar límites mínimo/máximo por columna
    anchos = [min(max(a, min_col), max_col) for a in anchos]

    # escalar proporcionalmente para ocupar exactamente el ancho disponible
    total = sum(anchos)
    if total <= 0:
        return [ancho_disponible / ncols] * ncols
    factor = ancho_disponible / total
    return [a * factor for a in anchos]


# ══════════════════════════════════════════════════════════════════
#  EXPORTADORES
# ══════════════════════════════════════════════════════════════════

def guardar_pdf(datos: dict, ruta) -> object:
    """Genera un PDF con los datos del reporte.

    ruta puede ser un Path/str (guarda en disco) o un io.BytesIO
    (escribe en memoria).  Devuelve ruta tal cual se recibió.

    El PDF siempre se genera en orientación vertical (portrait) y las
    columnas de la tabla principal se ajustan automáticamente según el
    contenido más largo de cada una.
    """
    import io as _io
    from app.logica_configuracion import obtener_datos_empresa
    emp = obtener_datos_empresa()

    _es_buffer = isinstance(ruta, _io.IOBase)
    if not _es_buffer:
        ruta = Path(ruta)
    destino = ruta if _es_buffer else str(ruta)

    # Orientación siempre vertical, independientemente de datos.get("orientacion")
    orientacion = A4
    doc = SimpleDocTemplate(
        destino, pagesize=orientacion,
        leftMargin=1.5*cm, rightMargin=1.5*cm,
        topMargin=1.5*cm, bottomMargin=1.5*cm,
    )

    base = getSampleStyleSheet()
    est = {
        "empresa_nombre": ParagraphStyle(
            "empresa_nombre", parent=base["Normal"],
            textColor=_BLANCO, fontSize=15, fontName="Helvetica-Bold",
            leading=18,
        ),
        "empresa_detalle": ParagraphStyle(
            "empresa_detalle", parent=base["Normal"],
            textColor=colors.HexColor("#E9E2C6"), fontSize=8,
            leading=12,
        ),
        "subtitulo": ParagraphStyle(
            "subtitulo", parent=base["Normal"],
            textColor=_TEXTO_SEC, fontSize=10, spaceAfter=2,
        ),
        "seccion": ParagraphStyle(
            "seccion", parent=base["Heading2"],
            textColor=_LEATHER, fontSize=11, spaceBefore=10, spaceAfter=4,
        ),
        "celda_hdr": ParagraphStyle(
            "celda_hdr", parent=base["Normal"],
            textColor=_BLANCO, fontSize=8, leading=10,
            fontName="Helvetica-Bold", alignment=1,  # centrado
        ),
        "celda": ParagraphStyle(
            "celda", parent=base["Normal"],
            textColor=_TEXTO, fontSize=8, leading=10,
        ),
    }

    # ── Cabecera de empresa ──────────────────────────────────────────
    # Tabla de dos columnas: bloque de datos (izq.) + franja decorativa (der.)
    # La franja derecha es un rectángulo ámbar que da "peso" visual al encabezado.
    bloque_datos = [
        Paragraph(emp["empresa_nombre"].upper(), est["empresa_nombre"]),
        Spacer(1, 3),
        Paragraph(
            f"RUC {emp['empresa_ruc']}  ·  {emp['empresa_direccion']}  ·  {emp['empresa_ciudad']}",
            est["empresa_detalle"],
        ),
        Paragraph(
            f"Tel. {emp['empresa_telefono']}  ·  {emp['empresa_email']}"
            + (f"  ·  {emp['empresa_web']}" if emp["empresa_web"] else ""),
            est["empresa_detalle"],
        ),
    ]

    ancho_total = doc.width
    cabecera = Table(
        [[bloque_datos, ""]],
        colWidths=[ancho_total * 0.80, ancho_total * 0.20],
    )
    cabecera.setStyle(TableStyle([
        ("BACKGROUND",   (0, 0), (0, 0), _VERDE_OSCURO),
        ("BACKGROUND",   (1, 0), (1, 0), _LEATHER),
        ("VALIGN",       (0, 0), (-1, -1), "MIDDLE"),
        ("LEFTPADDING",  (0, 0), (0, 0), 14),
        ("RIGHTPADDING", (0, 0), (0, 0), 10),
        ("TOPPADDING",   (0, 0), (-1, -1), 12),
        ("BOTTOMPADDING",(0, 0), (-1, -1), 12),
    ]))

    ahora = datetime.now().strftime("%d/%m/%Y %H:%M")
    historia = [
        cabecera,
        Spacer(1, 0.25*cm),
        HRFlowable(width="100%", thickness=1.5, color=_LEATHER, spaceAfter=4),
        Paragraph(datos["titulo"].upper(), est["seccion"]),
        Paragraph(f"Generado el {ahora}", est["subtitulo"]),
        Spacer(1, 0.25*cm),
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

    # ── Tabla de datos ────────────────────────────────────────────────
    columnas = datos["columnas"]
    filas_originales = datos["filas"] or [["Sin datos registrados"] + [""] * (len(columnas) - 1)]

    # Para el cálculo de anchos usamos los valores como texto plano
    tabla_texto = [columnas] + [[str(v) for v in fila] for fila in filas_originales]
    ncols = len(columnas)
    anchos = _anchos_columnas(tabla_texto, doc.width)

    # Para el render envolvemos cada celda en Paragraph, así el texto largo
    # hace salto de línea dentro de su columna en vez de desbordarse.
    tabla_data = [
        [Paragraph(str(col), est["celda_hdr"]) for col in columnas]
    ] + [
        [Paragraph(str(v), est["celda"]) for v in fila]
        for fila in filas_originales
    ]

    t = Table(tabla_data, colWidths=anchos, repeatRows=1)
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
    historia += [
        Spacer(1, 0.4*cm),
        HRFlowable(width="100%", thickness=0.5, color=_GRIS_LINEA),
        Paragraph(
            f"Documento generado automáticamente por el sistema de gestión de "
            f"{emp['empresa_nombre']} — {emp['empresa_ciudad']}.",
            est["subtitulo"],
        ),
    ]

    doc.build(historia)
    return ruta


def guardar_xlsx(datos: dict, ruta: Path) -> Path:
    """Genera un archivo Excel (.xlsx) con los datos del reporte."""
    from app.logica_configuracion import obtener_datos_empresa
    emp = obtener_datos_empresa()

    ruta = Path(ruta)
    wb = Workbook()
    ws = wb.active
    ws.title = datos["titulo"][:31]  # Excel limita a 31 chars

    # Estilos
    fill_header   = PatternFill("solid", fgColor=_XL_VERDE)
    fill_kpi_hdr  = PatternFill("solid", fgColor=_XL_AMBER)
    fill_alt      = PatternFill("solid", fgColor=_XL_SEPIA)
    fill_empresa  = PatternFill("solid", fgColor=_XL_VERDE)
    fill_franja   = PatternFill("solid", fgColor=_XL_AMBER)
    font_hdr      = Font(bold=True, color="FFFFFF", size=10)
    font_kpi_lbl  = Font(bold=True, color=_XL_VERDE, size=10)
    border_thin   = Border(
        bottom=Side(style="thin", color="E5D6B3"),
        right=Side(style="thin",  color="E5D6B3"),
    )
    alin_centro = Alignment(horizontal="center", vertical="center", wrap_text=True)
    alin_izq    = Alignment(horizontal="left",   vertical="center", wrap_text=True)

    ncols = len(datos["columnas"])
    col_fin = get_column_letter(max(ncols, 2))

    # ── Cabecera de empresa (filas 1-4) ──────────────────────────────
    # Fila 1: nombre de la empresa sobre fondo verde oscuro
    ws.merge_cells(f"A1:{col_fin}1")
    c = ws["A1"]
    c.value     = emp["empresa_nombre"].upper()
    c.font      = Font(bold=True, color="FFFFFF", size=14)
    c.fill      = fill_empresa
    c.alignment = alin_izq
    c.alignment = Alignment(horizontal="left", vertical="center",
                             indent=1, wrap_text=False)
    ws.row_dimensions[1].height = 26

    # Fila 2: RUC + dirección
    ws.merge_cells(f"A2:{col_fin}2")
    c = ws["A2"]
    c.value     = f"RUC {emp['empresa_ruc']}  ·  {emp['empresa_direccion']}  ·  {emp['empresa_ciudad']}"
    c.font      = Font(color="E9E2C6", size=9)
    c.fill      = fill_empresa
    c.alignment = Alignment(horizontal="left", vertical="center", indent=1)
    ws.row_dimensions[2].height = 16

    # Fila 3: teléfono + email + web
    web_txt = f"  ·  {emp['empresa_web']}" if emp["empresa_web"] else ""
    ws.merge_cells(f"A3:{col_fin}3")
    c = ws["A3"]
    c.value     = f"Tel. {emp['empresa_telefono']}  ·  {emp['empresa_email']}{web_txt}"
    c.font      = Font(color="E9E2C6", size=9)
    c.fill      = fill_empresa
    c.alignment = Alignment(horizontal="left", vertical="center", indent=1)
    ws.row_dimensions[3].height = 16

    # Fila 4: título del reporte sobre fondo ámbar
    ws.merge_cells(f"A4:{col_fin}4")
    c = ws["A4"]
    c.value     = datos["titulo"].upper()
    c.font      = Font(bold=True, color="FFFFFF", size=11)
    c.fill      = fill_franja
    c.alignment = alin_centro
    ws.row_dimensions[4].height = 20

    # Fila 5: fecha de generación
    ahora = datetime.now().strftime("%d/%m/%Y %H:%M")
    ws.merge_cells(f"A5:{col_fin}5")
    c = ws["A5"]
    c.value     = f"Generado el {ahora}"
    c.font      = Font(color="74795A", size=9, italic=True)
    c.alignment = alin_centro
    ws.row_dimensions[5].height = 14

    fila_cursor = 7  # dejamos una fila vacía (6) como separador visual

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
    from app.logica_configuracion import obtener_datos_empresa
    emp = obtener_datos_empresa()

    ruta = Path(ruta)
    ahora = datetime.now().strftime("%d/%m/%Y %H:%M")
    with open(ruta, "w", newline="", encoding="utf-8-sig") as f:
        writer = csv.writer(f)
        writer.writerow([emp["empresa_nombre"],
                         f"RUC {emp['empresa_ruc']}",
                         emp["empresa_ciudad"]])
        writer.writerow([emp["empresa_direccion"],
                         emp["empresa_telefono"],
                         emp["empresa_email"]])
        writer.writerow([])
        writer.writerow([datos["titulo"], f"Generado: {ahora}"])
        writer.writerow([])
        if datos.get("kpis"):
            writer.writerow(["INDICADOR", "VALOR"])
            for k in datos["kpis"]:
                writer.writerow([k["etiqueta"], k["valor"]])
            writer.writerow([])
        writer.writerow(datos["columnas"])
        writer.writerows(datos["filas"])
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