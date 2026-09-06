"""
estilos.py
==========
Aquí vive TODA la paleta de colores del programa, en un solo lugar.
Si algún día quieres cambiar el "tema" de la aplicación (por ejemplo,
usar otro color en vez del ámbar), solo tienes que tocar este archivo
— ninguna pantalla necesita cambiar.

¿Cómo le pone color Tkinter a los widgets "ttk" (botones, labels,
tablas, etc.)? A diferencia de los widgets clásicos de Tkinter (que
aceptan bg="rojo" directamente), los widgets "ttk" usan un sistema de
"estilos con nombre":

    1. Se define un estilo una vez, con ttk.Style().configure(...)
    2. Se le pone ese nombre a un widget con style="NombreDelEstilo"

Por ejemplo, más abajo definimos el estilo "Sidebar.TButton". Para
usarlo en un botón, se escribe:

    ttk.Button(parent, text="Compras", style="Sidebar.TButton")

Este archivo define los estilos, pero es cada pantalla (en la carpeta
app/ui/) la que decide cuándo usarlos.

Motor de tema — ttkbootstrap
-----------------------------
Antes se usaba el tema base "clam" de ttk (plano, pero de aspecto
anticuado: sin bordes redondeados, sin estados hover suaves, iconos
de flecha/checkbox muy básicos). Ahora se usa **ttkbootstrap**, que
reemplaza solo esa capa de "tema base": todos los estilos con nombre
de este archivo (Sidebar.TButton, Tarjeta.TFrame, TarjetaValor.TLabel,
etc.) se siguen definiendo exactamente igual con
``ttk.Style().configure(...)`` — ttkbootstrap.Style es 100% compatible
con ttk.Style, solo agrega temas nuevos y widgets propios (Meter,
DateEntry, Tooltip...) que este proyecto no usa todavía.

Detalle importante de ttkbootstrap: su clase Style es un "singleton"
pensado para una sola ventana raíz (tk.Tk) por proceso. Esta app crea
DOS raíces tk.Tk() sucesivas (VentanaLogin y, después, VentanaPrincipal),
así que aplicar_estilos() resetea el singleton en cada llamada — ver
el comentario dentro de la función.
"""

import ttkbootstrap as tb

# Tema base de ttkbootstrap. "flatly" es un tema claro, neutro y
# moderno que combina bien con la paleta cálida (ámbar/verde lúpulo)
# definida más abajo, ya que casi todos los widgets tienen un estilo
# con nombre propio que sobrescribe sus colores por defecto.
TEMA_TTKBOOTSTRAP = "flatly"

# ══════════════════════════════════════════════════════════════════
#  1) PALETA DE COLORES
# ══════════════════════════════════════════════════════════════════
# Paleta "cervecera artesanal", inspirada en los colores reales de una
# cerveza y sus ingredientes: verdes de lúpulo (Marine Green / Deep
# Green) para el menú lateral, un fondo cálido de malta clara (Barium
# Yellow), y cobre/cuero (Sepia / Leather) como color de acento — el
# mismo tono ámbar de una cerveza servida a la luz. Al usar los CINCO
# tonos (en vez de solo variaciones de un mismo ámbar) la interfaz
# gana contraste y variedad sin perder la identidad cervecera.

COLOR_FONDO = "#FEFAE3"              # Barium Yellow — fondo general, como malta clara
COLOR_TARJETA = "#FFFFFF"            # blanco — tarjetas KPI, tablas (resaltan sobre el fondo cálido)

COLOR_PRIMARIO = "#B17036"           # Leather — color principal (botones, acentos, encabezados)
COLOR_PRIMARIO_OSCURO = "#8C5726"    # Leather oscuro — botones al pasar el mouse
COLOR_PRIMARIO_CLARO = "#D4A369"     # Sepia — fondos suaves, pestaña inactiva

COLOR_SIDEBAR = "#2B361C"            # Deep Green — menú lateral (verde lúpulo oscuro)
COLOR_SIDEBAR_TEXTO = "#E9E2C6"      # crema claro — texto sobre el menú oscuro
COLOR_SIDEBAR_ACTIVO = "#636B3F"     # Marine Green — botón del menú al pasar el mouse

COLOR_TEXTO = "#2B361C"              # Deep Green — texto principal (oscuro, con carácter)
COLOR_TEXTO_SECUNDARIO = "#74795A"   # verde grisáceo — texto secundario / descripciones

COLOR_EXITO = "#4B7B3F"              # verde fresco — mensajes de éxito, stock OK
COLOR_ALERTA = "#B3432B"             # rojo cobrizo — errores, stock bajo
COLOR_ADVERTENCIA = "#C9922D"        # dorado — advertencias intermedias

# Tonos derivados, usados solo dentro de este archivo para botones
# secundarios, separadores y estados "disabled".
_COLOR_SECUNDARIO = "#E9D9B9"        # Sepia muy claro — botón secundario
_COLOR_SECUNDARIO_HOVER = "#DEC79A"  # Sepia claro — botón secundario al pasar el mouse
_COLOR_DISABLED = "#E6DAC0"          # botones deshabilitados
_COLOR_SEPARADOR = "#E5D6B3"         # líneas separadoras (actualmente sin
                                      # usar — ver nota de TSeparator más abajo)


def aplicar_estilos(ventana):
    """
    Configura todos los estilos "ttk" para una ventana (Tk o Toplevel).
    Se debe llamar UNA vez, justo después de crear cada ventana raíz
    (VentanaLogin y VentanaPrincipal ya lo hacen en su __init__).

    Nota: los diálogos (Toplevel) que se abren DESDE la ventana
    principal heredan los estilos automáticamente, porque ttk.Style
    se configura a nivel de toda la aplicación, no ventana por ventana.
    """
    ventana.configure(bg=COLOR_FONDO)

    # ttkbootstrap.Style es un singleton ligado a la ventana raíz que
    # existía cuando se creó. Como esta app abre una raíz tk.Tk() nueva
    # para el login y luego OTRA para la ventana principal (la anterior
    # ya fue destruida), hay que soltar la instancia vieja antes de
    # pedir una nueva — si no, ttkbootstrap intentaría seguir hablando
    # con una ventana que ya no existe. Los diálogos (Toplevel) que se
    # abren DESDE una de estas dos raíces no necesitan esto: heredan el
    # estilo de su propia raíz sin volver a llamar aplicar_estilos().
    tb.Style.instance = None
    estilo = tb.Style(theme=TEMA_TTKBOOTSTRAP)

    # ── Widgets genéricos (los que no llevan un style con nombre) ──
    estilo.configure("TFrame", background=COLOR_FONDO)
    estilo.configure("TLabel", background=COLOR_FONDO, foreground=COLOR_TEXTO)
    estilo.configure("TLabelframe", background=COLOR_FONDO, foreground=COLOR_TEXTO)
    estilo.configure("TLabelframe.Label", background=COLOR_FONDO, foreground=COLOR_TEXTO)

    estilo.configure("TButton", background=COLOR_PRIMARIO, foreground="white",
                      padding=(10, 6), borderwidth=0, font=("Segoe UI", 9))
    estilo.map("TButton",
               background=[("active", COLOR_PRIMARIO_OSCURO), ("disabled", _COLOR_DISABLED)])

    estilo.configure("TEntry", fieldbackground="white", foreground=COLOR_TEXTO, padding=4)
    estilo.configure("TCombobox", fieldbackground="white", foreground=COLOR_TEXTO, padding=4)

    # ── Botón de "peligro" (desactivar usuario, cerrar sesión...) ──
    estilo.configure("Peligro.TButton", background=COLOR_ALERTA, foreground="white",
                      padding=(10, 6), borderwidth=0)
    estilo.map("Peligro.TButton", background=[("active", "#8E3220")])

    # ── Botón "secundario" (acciones menos importantes, ej: Salir) ──
    estilo.configure("Secundario.TButton", background=_COLOR_SECUNDARIO, foreground=COLOR_TEXTO,
                      padding=(10, 6), borderwidth=0)
    estilo.map("Secundario.TButton", background=[("active", _COLOR_SECUNDARIO_HOVER)])

    # ── Botón de "éxito" (reactivar usuario, confirmar algo positivo...) ──
    estilo.configure("Exito.TButton", background=COLOR_EXITO, foreground="white",
                      padding=(10, 6), borderwidth=0)
    estilo.map("Exito.TButton", background=[("active", "#3B6231")])

    # ── Encabezado de cada módulo (franja de color arriba) ──────────
    estilo.configure("Encabezado.TFrame", background=COLOR_PRIMARIO)
    estilo.configure("Encabezado.TLabel", background=COLOR_PRIMARIO)
    estilo.configure("EncabezadoTitulo.TLabel", background=COLOR_PRIMARIO,
                      foreground="white", font=("Segoe UI", 16, "bold"))
    estilo.configure("EncabezadoSubtitulo.TLabel", background=COLOR_PRIMARIO,
                      foreground=COLOR_PRIMARIO_CLARO, font=("Segoe UI", 9))

    # ── Menú lateral ─────────────────────────────────────────────────
    estilo.configure("Sidebar.TFrame", background=COLOR_SIDEBAR)
    estilo.configure("Sidebar.TLabel", background=COLOR_SIDEBAR, foreground=COLOR_SIDEBAR_TEXTO)
    estilo.configure("SidebarTitulo.TLabel", background=COLOR_SIDEBAR, foreground="white",
                      font=("Segoe UI", 13, "bold"))
    estilo.configure("Sidebar.TButton", background=COLOR_SIDEBAR, foreground=COLOR_SIDEBAR_TEXTO,
                      borderwidth=0, anchor="w", padding=(10, 8), font=("Segoe UI", 10))
    estilo.map("Sidebar.TButton",
               background=[("active", COLOR_SIDEBAR_ACTIVO)],
               foreground=[("active", "white")])
    estilo.configure("Sidebar.TSeparator", background=COLOR_SIDEBAR_ACTIVO)

    # ── Tarjetas KPI (dashboard, costos) ─────────────────────────────
    estilo.configure("Tarjeta.TFrame", background=COLOR_TARJETA, relief="flat")
    estilo.configure("Tarjeta.TLabel", background=COLOR_TARJETA, foreground=COLOR_TEXTO)
    estilo.configure("TarjetaValor.TLabel", background=COLOR_TARJETA,
                      foreground=COLOR_PRIMARIO, font=("Segoe UI", 19, "bold"))
    estilo.configure("TarjetaValorAlerta.TLabel", background=COLOR_TARJETA,
                      foreground=COLOR_ALERTA, font=("Segoe UI", 19, "bold"))
    estilo.configure("TarjetaValorExito.TLabel", background=COLOR_TARJETA,
                      foreground=COLOR_EXITO, font=("Segoe UI", 19, "bold"))
    estilo.configure("TarjetaEtiqueta.TLabel", background=COLOR_TARJETA,
                      foreground=COLOR_TEXTO_SECUNDARIO, font=("Segoe UI", 9))

    # ── Pestañas (Notebook) ──────────────────────────────────────────
    # Nota: en varios temas base de ttk (incluido "clam") la pestaña NO
    # seleccionada se dibuja más alta que la seleccionada (el borde
    # inferior de la seleccionada se "hunde" para unirse visualmente
    # con el contenido). Eso confunde al usuario, porque parece que la
    # pestaña activa es la más chica. Para evitarlo, forzamos
    # explícitamente que la pestaña seleccionada
    # tenga MÁS padding vertical que las demás, así siempre se ve más
    # grande — reforzando que esa es la pestaña activa.
    estilo.configure("TNotebook", background=COLOR_FONDO, borderwidth=0)
    estilo.configure("TNotebook.Tab", background=COLOR_PRIMARIO_CLARO, foreground=COLOR_TEXTO,
                      padding=(14, 6), font=("Segoe UI", 9))
    estilo.map("TNotebook.Tab",
               background=[("selected", COLOR_PRIMARIO), ("!selected", COLOR_PRIMARIO_CLARO)],
               foreground=[("selected", "white")],
               padding=[("selected", (14, 12)), ("!selected", (14, 6))],
               font=[("selected", ("Segoe UI", 9, "bold"))])

    # ── Tablas (Treeview) ─────────────────────────────────────────────
    estilo.configure("Treeview", background="white", fieldbackground="white",
                      foreground=COLOR_TEXTO, rowheight=26, borderwidth=0)
    estilo.configure("Treeview.Heading", background=COLOR_PRIMARIO, foreground="white",
                      font=("Segoe UI", 9, "bold"), padding=(6, 6))
    estilo.map("Treeview.Heading", background=[("active", COLOR_PRIMARIO_OSCURO)])
    estilo.map("Treeview", background=[("selected", COLOR_PRIMARIO_CLARO)],
               foreground=[("selected", COLOR_TEXTO)])

    # ── Scrollbar y separador ─────────────────────────────────────────
    # OJO: a diferencia de los estilos de arriba, "TScrollbar" y
    # "TSeparator" son nombres de estilo "base" (sin prefijo con
    # nombre propio, como "Sidebar.TButton"). Cuando ttkbootstrap ve
    # un .configure() sobre uno de esos nombres base con un color que
    # no reconoce como palabra clave suya (ej. un hex crudo), intenta
    # generar sobre la marcha los elementos gráficos del widget — y en
    # varias combinaciones de Tk/Tcl en Linux eso revienta con un
    # error "Duplicate element" al crear el Scrollbar. Por eso NO se
    # sobrescriben aquí: se deja que el tema "flatly" les ponga su
    # propio color por defecto (ya se ve bien y combina con el resto).
    # Si en algún momento quieres un color propio, hazlo con la sintaxis
    # de ttkbootstrap (ej. style="secondary.Vertical.TScrollbar" al
    # crear el widget) en vez de sobrescribir el nombre base aquí.

    _habilitar_seleccionar_todo(ventana)


def _habilitar_seleccionar_todo(ventana):
    """
    Por defecto, Tkinter en Linux NO selecciona todo el texto de un
    campo con Ctrl+A (en vez de eso, mueve el cursor al inicio de la
    línea, como en Emacs). La mayoría de la gente espera el
    comportamiento "estilo Windows": Ctrl+A selecciona todo el texto.

    Esta función agrega ese atajo a TODOS los campos de texto
    (Entry, campos de las Combobox, y también los campos "ttk") de
    la ventana dada. Se llama una sola vez por ventana raíz, dentro
    de aplicar_estilos().
    """

    def seleccionar_todo(evento):
        widget = evento.widget
        # select_range/icursor existen tanto en Entry clásico como en
        # los campos de texto de ttk.Entry y ttk.Combobox.
        widget.select_range(0, "end")
        widget.icursor("end")
        return "break"  # evita que Tkinter también mueva el cursor (comportamiento viejo)

    for clase in ("Entry", "TEntry", "TCombobox"):
        ventana.bind_class(clase, "<Control-a>", seleccionar_todo)
        ventana.bind_class(clase, "<Control-A>", seleccionar_todo)
