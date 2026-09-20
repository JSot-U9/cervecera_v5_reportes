"""
estilos.py (PySide6)
=====================
Sistema visual centralizado del ERP Cervecería — versión Qt.

Misma paleta "cervecera artesanal" que la versión Tkinter (se
mantienen los mismos nombres de color para que el resto del código
no tenga que cambiar), pero aplicada con una hoja de estilos QSS
global en vez de ttk.Style.

¿Cómo se emulan los "estilos con nombre" de ttk (p. ej.
`style="Secundario.TButton"`) en Qt? Con la propiedad dinámica
`clase`: se le pone `widget.setProperty("clase", "secundario")` a un
QPushButton/QLabel y el selector QSS `[clase="secundario"]` lo
recoge. La función `poner_clase()` de más abajo hace ese trabajo.
"""

from PySide6.QtWidgets import QWidget
from PySide6.QtGui import QFont

# ══════════════════════════════════════════════════════════════════
#  PALETA DE COLORES (idéntica a la versión Tkinter)
# ══════════════════════════════════════════════════════════════════
COLOR_FONDO           = "#FDF6E3"   # crema — fondo general
COLOR_TARJETA         = "#FFFFFF"   # blanco — tarjetas, tablas

COLOR_PRIMARIO        = "#C1600C"   # Ámbar intenso — botones primarios, encabezados
COLOR_PRIMARIO_OSCURO = "#8F4400"   # Ámbar oscuro — hover
COLOR_PRIMARIO_CLARO  = "#F2A649"   # Ámbar claro — fondos suaves, acentos

COLOR_SIDEBAR         = "#16240D"   # Verde bosque intenso — menú lateral
COLOR_SIDEBAR_TEXTO   = "#E9E2C6"   # crema — texto sobre sidebar
COLOR_SIDEBAR_ACTIVO  = "#4C7A29"   # verde vivo — hover/activo sidebar
COLOR_SIDEBAR_SELECCIONADO = "#3A6019"  # verde vivo más oscuro — activo persistente

COLOR_TEXTO           = "#1B2A12"   # verde muy oscuro — texto principal
COLOR_TEXTO_SECUNDARIO = "#5C6650"  # verde grisáceo — texto secundario

COLOR_CAMPO_DESHABILITADO = "#E7E4D8"  # gris cálido claro — fondo de un campo de formulario bloqueado/solo lectura

COLOR_EXITO           = "#1E8A3C"
COLOR_ALERTA          = "#D62B1F"
COLOR_ADVERTENCIA     = "#E8A100"

# Derivados internos
_COLOR_SECUNDARIO        = "#F0D9A8"
_COLOR_SECUNDARIO_HOVER  = "#E6C27D"
_COLOR_DISABLED          = "#E6DAC0"
_COLOR_SEPARADOR         = "#E5D6B3"
_COLOR_FILA_PAR          = "#FFFDF5"
_COLOR_ENCABEZADO_HOVER  = "#A64E0A"

FUENTE_BASE = "Segoe UI"


def poner_clase(widget: QWidget, clase: str):
    """Equivalente a `style='Xxx.TButton'` en ttk: marca `widget` con
    una propiedad dinámica que la hoja QSS usa para diferenciarlo."""
    widget.setProperty("clase", clase)
    widget.style().unpolish(widget)
    widget.style().polish(widget)
    widget.update()


_contador_fondo = 0


def estilo_escopado(widget: QWidget, css_body: str):
    """Aplica un bloque QSS a `widget` escopado por su objectName (ver
    `fondo()` para la explicación completa de por qué hace falta)."""
    global _contador_fondo
    _contador_fondo += 1
    nombre = f"w{_contador_fondo}"
    widget.setObjectName(nombre)
    widget.setStyleSheet(f"QWidget#{nombre} {{ {css_body} }}")


def fondo(widget: QWidget, color: str, extra: str = ""):
    """Asigna un color de fondo a `widget` de forma 'escopada' (con un
    selector por objectName), en vez de `widget.setStyleSheet(f"background-color: ...")`.

    ¿Por qué hace falta esto? Es un bug/comportamiento conocido de Qt:
    un stylesheet SIN selector aplicado a un contenedor (p. ej.
    `frame.setStyleSheet("background-color: green;")`) puede bloquear
    que la hoja de estilos GLOBAL de la app siga aplicándose a los
    widgets hijos (botones, labels) — se ven "apagados" o sin color,
    como si perdieran su estilo. Al escoparlo con `#nombre_unico`, la
    regla solo afecta a ESE widget puntual y el resto del árbol sigue
    recibiendo el QSS global con normalidad.
    """
    estilo_escopado(widget, f"background-color: {color}; {extra}")


def fuente(tamano=10, negrita=False, cursiva=False) -> QFont:
    f = QFont(FUENTE_BASE, tamano)
    f.setBold(negrita)
    f.setItalic(cursiva)
    return f


# ══════════════════════════════════════════════════════════════════
#  HOJA DE ESTILOS GLOBAL (QSS)
# ══════════════════════════════════════════════════════════════════

def hoja_estilos() -> str:
    return f"""
    QWidget {{
        background-color: {COLOR_FONDO};
        color: {COLOR_TEXTO};
        font-family: "{FUENTE_BASE}";
        font-size: 10pt;
    }}
    QMainWindow, QDialog {{
        background-color: {COLOR_FONDO};
    }}
    QLabel {{
        background: transparent;
    }}

    /* ── Botón primario (por defecto) ─────────────────────────── */
    QPushButton {{
        background-color: {COLOR_PRIMARIO};
        color: white;
        border: none;
        border-radius: 5px;
        padding: 9px 16px;
        font-weight: bold;
    }}
    QPushButton:hover {{ background-color: {COLOR_PRIMARIO_OSCURO}; }}
    QPushButton:pressed {{ background-color: {COLOR_PRIMARIO_OSCURO}; }}
    QPushButton:disabled {{ background-color: {_COLOR_DISABLED}; color: #A0927A; }}

    QPushButton[clase="secundario"] {{
        background-color: {_COLOR_SECUNDARIO};
        color: {COLOR_TEXTO};
        font-weight: normal;
    }}
    QPushButton[clase="secundario"]:hover {{ background-color: {_COLOR_SECUNDARIO_HOVER}; }}

    QPushButton[clase="peligro"] {{ background-color: {COLOR_ALERTA}; color: white; }}
    QPushButton[clase="peligro"]:hover {{ background-color: #A61F16; }}

    QPushButton[clase="exito"] {{ background-color: {COLOR_EXITO}; color: white; }}
    QPushButton[clase="exito"]:hover {{ background-color: #166B2E; }}

    QPushButton[clase="accion"] {{
        background-color: {COLOR_PRIMARIO}; color: white;
        padding: 6px 12px; font-size: 9pt; font-weight: bold;
    }}
    QPushButton[clase="accion"]:hover {{ background-color: {COLOR_PRIMARIO_OSCURO}; }}

    QPushButton[clase="accionSecundaria"] {{
        background-color: {_COLOR_SECUNDARIO}; color: {COLOR_TEXTO};
        padding: 6px 12px; font-size: 9pt; font-weight: normal;
    }}
    QPushButton[clase="accionSecundaria"]:hover {{ background-color: {_COLOR_SECUNDARIO_HOVER}; }}

    QPushButton[clase="sidebar"] {{
        background-color: {COLOR_SIDEBAR};
        color: {COLOR_SIDEBAR_TEXTO};
        text-align: left;
        padding: 11px 16px;
        border-radius: 0px;
        font-weight: normal;
    }}
    QPushButton[clase="sidebar"]:hover {{ background-color: {COLOR_SIDEBAR_ACTIVO}; color: white; }}

    QPushButton[clase="sidebarActivo"] {{
        background-color: {COLOR_SIDEBAR_SELECCIONADO};
        color: white;
        text-align: left;
        padding: 11px 16px;
        border-radius: 0px;
        font-weight: bold;
    }}
    QPushButton[clase="sidebarActivo"]:hover {{ background-color: {COLOR_SIDEBAR_ACTIVO}; }}

    /* ── Campos de entrada ─────────────────────────────────────── */
    QLineEdit, QComboBox, QDateEdit, QSpinBox, QDoubleSpinBox {{
        background-color: white;
        color: {COLOR_TEXTO};
        border: 1px solid {_COLOR_SEPARADOR};
        border-radius: 4px;
        padding: 6px 8px;
    }}
    QLineEdit:focus, QComboBox:focus {{ border: 1px solid {COLOR_PRIMARIO}; }}
    QComboBox::drop-down {{ border: none; width: 22px; }}
    QComboBox QAbstractItemView {{
        background-color: white; color: {COLOR_TEXTO};
        selection-background-color: {COLOR_PRIMARIO_CLARO};
        selection-color: {COLOR_TEXTO};
    }}

    /* ── Pestañas (QTabWidget = Notebook) ──────────────────────── */
    QTabWidget::pane {{ border: none; background: {COLOR_FONDO}; }}
    QTabBar::tab {{
        background: {COLOR_PRIMARIO_CLARO};
        color: {COLOR_TEXTO};
        padding: 9px 18px;
        margin-right: 2px;
        font-size: 9pt;
    }}
    QTabBar::tab:selected {{
        background: {COLOR_PRIMARIO};
        color: white;
        font-weight: bold;
    }}

    /* ── Tablas ─────────────────────────────────────────────────── */
    QTableWidget {{
        background-color: white;
        alternate-background-color: {_COLOR_FILA_PAR};
        gridline-color: {_COLOR_SEPARADOR};
        border: 1px solid {_COLOR_SEPARADOR};
        font-size: 9pt;
    }}
    QTableWidget::item {{ padding: 6px; }}
    QTableWidget::item:selected {{
        background-color: {COLOR_PRIMARIO_CLARO}; color: {COLOR_TEXTO};
    }}
    QHeaderView::section {{
        background-color: {COLOR_PRIMARIO};
        color: white;
        padding: 8px;
        border: none;
        font-weight: bold;
        font-size: 9pt;
    }}

    /* ── GroupBox (SeccionFormulario) ──────────────────────────── */
    QGroupBox {{
        border: 1px solid {_COLOR_SEPARADOR};
        border-radius: 6px;
        margin-top: 14px;
        padding: 12px 10px 10px 10px;
        font-weight: bold;
        color: {COLOR_PRIMARIO};
    }}
    QGroupBox::title {{
        subcontrol-origin: margin;
        left: 10px;
        padding: 0 6px;
        color: {COLOR_PRIMARIO};
    }}

    QScrollBar:vertical {{ background: {COLOR_FONDO}; width: 12px; }}
    QScrollBar::handle:vertical {{ background: {_COLOR_SECUNDARIO}; border-radius: 5px; min-height: 24px; }}
    QScrollBar:horizontal {{ background: {COLOR_FONDO}; height: 12px; }}
    QScrollBar::handle:horizontal {{ background: {_COLOR_SECUNDARIO}; border-radius: 5px; min-width: 24px; }}

    QToolTip {{
        background-color: {COLOR_SIDEBAR}; color: {COLOR_SIDEBAR_TEXTO};
        border: 1px solid {COLOR_PRIMARIO}; padding: 4px;
    }}
    """


def aplicar_estilos(app):
    """Aplica la hoja de estilos global. Llamar una vez sobre la QApplication."""
    app.setStyleSheet(hoja_estilos())
    app.setFont(fuente(10))
