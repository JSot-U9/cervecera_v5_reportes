"""
estilos.py
==========
Sistema visual centralizado del ERP Cervecería.
Paleta "cervecera artesanal" con jerarquía visual mejorada.
"""

import ttkbootstrap as tb

TEMA_TTKBOOTSTRAP = "flatly"

# ══════════════════════════════════════════════════════════════════
#  PALETA DE COLORES
#  (versión "alto contraste": tonos más saturados para reforzar la
#  jerarquía visual y facilitar identificar botones, estados y
#  secciones de un vistazo)
# ══════════════════════════════════════════════════════════════════
COLOR_FONDO          = "#FDF6E3"   # crema — fondo general
COLOR_TARJETA        = "#FFFFFF"   # blanco — tarjetas, tablas

COLOR_PRIMARIO       = "#C1600C"   # Ámbar intenso — botones primarios, encabezados
COLOR_PRIMARIO_OSCURO = "#8F4400"  # Ámbar oscuro — hover
COLOR_PRIMARIO_CLARO  = "#F2A649"  # Ámbar claro — fondos suaves, acentos

COLOR_SIDEBAR        = "#16240D"   # Verde bosque intenso — menú lateral
COLOR_SIDEBAR_TEXTO  = "#E9E2C6"   # crema — texto sobre sidebar
COLOR_SIDEBAR_ACTIVO = "#4C7A29"   # verde vivo — hover/activo sidebar
COLOR_SIDEBAR_SELECCIONADO = "#3A6019"  # verde vivo más oscuro — estado activo persistente

COLOR_TEXTO          = "#1B2A12"   # verde muy oscuro — texto principal
COLOR_TEXTO_SECUNDARIO = "#5C6650" # verde grisáceo — texto secundario

COLOR_EXITO          = "#1E8A3C"   # verde intenso — éxito, stock OK
COLOR_ALERTA         = "#D62B1F"   # rojo intenso — errores, peligro
COLOR_ADVERTENCIA    = "#E8A100"   # dorado intenso — advertencias

# Derivados internos
_COLOR_SECUNDARIO        = "#F0D9A8"
_COLOR_SECUNDARIO_HOVER  = "#E6C27D"
_COLOR_DISABLED          = "#E6DAC0"
_COLOR_SEPARADOR         = "#E5D6B3"
_COLOR_FILA_PAR          = "#FFFDF5"   # filas alternas tabla
_COLOR_FILA_IMPAR        = "#FFFFFF"
_COLOR_ENCABEZADO_HOVER  = "#A64E0A"


def aplicar_estilos(ventana):
    """
    Configura todos los estilos ttk. Llamar una vez por ventana raíz.
    """
    ventana.configure(bg=COLOR_FONDO)

    tb.Style.instance = None
    estilo = tb.Style(theme=TEMA_TTKBOOTSTRAP)

    # ── Widgets genéricos ──────────────────────────────────────────
    estilo.configure("TFrame", background=COLOR_FONDO)
    estilo.configure("TLabel", background=COLOR_FONDO, foreground=COLOR_TEXTO,
                     font=("Segoe UI", 10))
    estilo.configure("TLabelframe", background=COLOR_FONDO, foreground=COLOR_TEXTO,
                     font=("Segoe UI", 10, "bold"))
    estilo.configure("TLabelframe.Label", background=COLOR_FONDO, foreground=COLOR_TEXTO,
                     font=("Segoe UI", 10, "bold"))

    # ── Botón primario ─────────────────────────────────────────────
    estilo.configure("TButton",
                     background=COLOR_PRIMARIO, foreground="white",
                     padding=(14, 8), borderwidth=0,
                     font=("Segoe UI", 10, "bold"), relief="flat")
    estilo.map("TButton",
               background=[("active", COLOR_PRIMARIO_OSCURO),
                            ("disabled", _COLOR_DISABLED)],
               foreground=[("disabled", "#A0927A")])

    # ── Botón de peligro ───────────────────────────────────────────
    estilo.configure("Peligro.TButton",
                     background=COLOR_ALERTA, foreground="white",
                     padding=(14, 8), borderwidth=0,
                     font=("Segoe UI", 10, "bold"))
    estilo.map("Peligro.TButton",
               background=[("active", "#A61F16")])

    # ── Botón secundario ───────────────────────────────────────────
    estilo.configure("Secundario.TButton",
                     background=_COLOR_SECUNDARIO, foreground=COLOR_TEXTO,
                     padding=(14, 8), borderwidth=0,
                     font=("Segoe UI", 10))
    estilo.map("Secundario.TButton",
               background=[("active", _COLOR_SECUNDARIO_HOVER)])

    # ── Botón de éxito ─────────────────────────────────────────────
    estilo.configure("Exito.TButton",
                     background=COLOR_EXITO, foreground="white",
                     padding=(14, 8), borderwidth=0,
                     font=("Segoe UI", 10, "bold"))
    estilo.map("Exito.TButton",
               background=[("active", "#166B2E")])

    # ── Botón acción pequeña (dentro de tablas, barras) ────────────
    estilo.configure("Accion.TButton",
                     background=COLOR_PRIMARIO, foreground="white",
                     padding=(10, 6), borderwidth=0,
                     font=("Segoe UI", 9, "bold"))
    estilo.map("Accion.TButton",
               background=[("active", COLOR_PRIMARIO_OSCURO)])

    estilo.configure("AccionSecundaria.TButton",
                     background=_COLOR_SECUNDARIO, foreground=COLOR_TEXTO,
                     padding=(10, 6), borderwidth=0,
                     font=("Segoe UI", 9))
    estilo.map("AccionSecundaria.TButton",
               background=[("active", _COLOR_SECUNDARIO_HOVER)])

    # ── Campos de entrada ──────────────────────────────────────────
    estilo.configure("TEntry",
                     fieldbackground="white", foreground=COLOR_TEXTO,
                     padding=(6, 5), font=("Segoe UI", 10))
    estilo.configure("TCombobox",
                     fieldbackground="white", foreground=COLOR_TEXTO,
                     padding=(4, 4), font=("Segoe UI", 10))

    # ── Encabezado de módulo ───────────────────────────────────────
    estilo.configure("Encabezado.TFrame", background=COLOR_PRIMARIO)
    estilo.configure("Encabezado.TLabel", background=COLOR_PRIMARIO)
    estilo.configure("EncabezadoTitulo.TLabel",
                     background=COLOR_PRIMARIO, foreground="white",
                     font=("Segoe UI", 15, "bold"))
    estilo.configure("EncabezadoSubtitulo.TLabel",
                     background=COLOR_PRIMARIO, foreground=COLOR_PRIMARIO_CLARO,
                     font=("Segoe UI", 9))

    # ── Menú lateral ───────────────────────────────────────────────
    estilo.configure("Sidebar.TFrame", background=COLOR_SIDEBAR)
    estilo.configure("Sidebar.TLabel",
                     background=COLOR_SIDEBAR, foreground=COLOR_SIDEBAR_TEXTO,
                     font=("Segoe UI", 10))
    estilo.configure("SidebarTitulo.TLabel",
                     background=COLOR_SIDEBAR, foreground="white",
                     font=("Segoe UI", 11, "bold"))
    estilo.configure("SidebarRol.TLabel",
                     background=COLOR_SIDEBAR, foreground=COLOR_PRIMARIO_CLARO,
                     font=("Segoe UI", 8, "bold"))
    estilo.configure("Sidebar.TButton",
                     background=COLOR_SIDEBAR, foreground=COLOR_SIDEBAR_TEXTO,
                     borderwidth=0, anchor="w",
                     padding=(14, 10), font=("Segoe UI", 10))
    estilo.map("Sidebar.TButton",
               background=[("active", COLOR_SIDEBAR_ACTIVO)],
               foreground=[("active", "white")])
    estilo.configure("SidebarActivo.TButton",
                     background=COLOR_SIDEBAR_SELECCIONADO, foreground="white",
                     borderwidth=0, anchor="w",
                     padding=(14, 10), font=("Segoe UI", 10, "bold"))
    estilo.map("SidebarActivo.TButton",
               background=[("active", COLOR_SIDEBAR_ACTIVO)],
               foreground=[("active", "white")])
    estilo.configure("Sidebar.TSeparator", background=COLOR_SIDEBAR_ACTIVO)

    # ── Tarjetas KPI ───────────────────────────────────────────────
    estilo.configure("Tarjeta.TFrame",
                     background=COLOR_TARJETA, relief="flat")
    estilo.configure("Tarjeta.TLabel",
                     background=COLOR_TARJETA, foreground=COLOR_TEXTO)
    estilo.configure("TarjetaValor.TLabel",
                     background=COLOR_TARJETA, foreground=COLOR_PRIMARIO,
                     font=("Segoe UI", 22, "bold"))
    estilo.configure("TarjetaValorAlerta.TLabel",
                     background=COLOR_TARJETA, foreground=COLOR_ALERTA,
                     font=("Segoe UI", 22, "bold"))
    estilo.configure("TarjetaValorExito.TLabel",
                     background=COLOR_TARJETA, foreground=COLOR_EXITO,
                     font=("Segoe UI", 22, "bold"))
    estilo.configure("TarjetaValorAdvertencia.TLabel",
                     background=COLOR_TARJETA, foreground=COLOR_ADVERTENCIA,
                     font=("Segoe UI", 22, "bold"))
    estilo.configure("TarjetaEtiqueta.TLabel",
                     background=COLOR_TARJETA, foreground=COLOR_TEXTO_SECUNDARIO,
                     font=("Segoe UI", 9))
    estilo.configure("TarjetaIcono.TLabel",
                     background=COLOR_TARJETA, foreground=COLOR_TEXTO_SECUNDARIO,
                     font=("Segoe UI", 11))

    # ── Pestañas ───────────────────────────────────────────────────
    estilo.configure("TNotebook",
                     background=COLOR_FONDO, borderwidth=0)
    estilo.configure("TNotebook.Tab",
                     background=COLOR_PRIMARIO_CLARO, foreground=COLOR_TEXTO,
                     padding=(16, 8), font=("Segoe UI", 9))
    estilo.map("TNotebook.Tab",
               background=[("selected", COLOR_PRIMARIO), ("!selected", COLOR_PRIMARIO_CLARO)],
               foreground=[("selected", "white")],
               padding=[("selected", (16, 12)), ("!selected", (16, 8))],
               font=[("selected", ("Segoe UI", 9, "bold"))])

    # ── Tablas ─────────────────────────────────────────────────────
    estilo.configure("Treeview",
                     background="white", fieldbackground="white",
                     foreground=COLOR_TEXTO, rowheight=30, borderwidth=0,
                     font=("Segoe UI", 9))
    estilo.configure("Treeview.Heading",
                     background=COLOR_PRIMARIO, foreground="white",
                     font=("Segoe UI", 9, "bold"), padding=(8, 8))
    estilo.map("Treeview.Heading",
               background=[("active", _COLOR_ENCABEZADO_HOVER)])
    estilo.map("Treeview",
               background=[("selected", COLOR_PRIMARIO_CLARO)],
               foreground=[("selected", COLOR_TEXTO)])

    # ── Barra de estado inferior ───────────────────────────────────
    estilo.configure("BarraEstado.TFrame",
                     background=COLOR_SIDEBAR)
    estilo.configure("BarraEstado.TLabel",
                     background=COLOR_SIDEBAR, foreground="#B9C7A9",
                     font=("Segoe UI", 8))
    estilo.configure("BarraEstadoOK.TLabel",
                     background=COLOR_SIDEBAR, foreground="#5FDD73",
                     font=("Segoe UI", 8))

    # ── Sección de formulario ──────────────────────────────────────
    estilo.configure("SeccionFormulario.TLabelframe",
                     background=COLOR_FONDO, foreground=COLOR_PRIMARIO,
                     font=("Segoe UI", 9, "bold"), relief="groove", borderwidth=1)
    estilo.configure("SeccionFormulario.TLabelframe.Label",
                     background=COLOR_FONDO, foreground=COLOR_PRIMARIO,
                     font=("Segoe UI", 9, "bold"))

    # ── Etiqueta de campo automático ──────────────────────────────
    estilo.configure("CampoAuto.TLabel",
                     background=COLOR_FONDO, foreground=COLOR_TEXTO_SECUNDARIO,
                     font=("Segoe UI", 8, "italic"))

    # ── Etiqueta para mensajes de error inline ─────────────────────
    estilo.configure("ErrorInline.TLabel",
                     background=COLOR_FONDO, foreground=COLOR_ALERTA,
                     font=("Segoe UI", 8))

    # ── Alertas y mensajes ────────────────────────────────────────
    estilo.configure("AlertaFrame.TFrame",
                     background="#FFF3CD")
    estilo.configure("AlertaLabel.TLabel",
                     background="#FFF3CD", foreground="#856404",
                     font=("Segoe UI", 9))
    estilo.configure("ExitoFrame.TFrame",
                     background="#D4EDDA")
    estilo.configure("ExitoLabel.TLabel",
                     background="#D4EDDA", foreground="#155724",
                     font=("Segoe UI", 9))

    _habilitar_seleccionar_todo(ventana)
    _habilitar_atajos_globales(ventana)


def _habilitar_seleccionar_todo(ventana):
    def seleccionar_todo(evento):
        widget = evento.widget
        widget.select_range(0, "end")
        widget.icursor("end")
        return "break"
    for clase in ("Entry", "TEntry", "TCombobox"):
        ventana.bind_class(clase, "<Control-a>", seleccionar_todo)
        ventana.bind_class(clase, "<Control-A>", seleccionar_todo)


def _habilitar_atajos_globales(ventana):
    """Atajos de teclado globales: F5 recarga la vista activa."""
    pass  # Los módulos registran sus propios atajos en refrescar()