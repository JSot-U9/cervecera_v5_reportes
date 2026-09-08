"""widgets.py
==========
Design system: componentes reutilizables para el ERP Cervecería.

Componentes:
  - ajustar_ventana_a_contenido
  - EncabezadoModulo     : franja superior con título y subtítulo
  - TarjetaKPI           : tarjeta con valor numérico y etiqueta
  - BarraBusqueda        : campo de filtro + botones de acción
  - BarraAcciones        : contenedor de botones primarios/secundarios/peligro
  - TablaDatos           : Treeview con filas alternas y scrollbar
  - EstadoBadge          : etiqueta visual de estado
  - SeccionFormulario    : LabelFrame estilizado para agrupar campos
  - CampoFormulario      : label + entry/combobox con validación inline
  - DialogoConfirmacion  : diálogo modal de confirmación
  - MensajeEstado        : banda de mensaje éxito/error/advertencia
"""

import tkinter as tk
from tkinter import ttk

from app.ui.estilos import (
    COLOR_TEXTO, COLOR_TEXTO_SECUNDARIO, COLOR_PRIMARIO,
    COLOR_ALERTA, COLOR_EXITO, COLOR_ADVERTENCIA,
    COLOR_FONDO, COLOR_TARJETA, _COLOR_SEPARADOR
)


# ══════════════════════════════════════════════════════════════════
#  UTILIDADES
# ══════════════════════════════════════════════════════════════════

def ajustar_ventana_a_contenido(ventana, ancho: int = None, alto_extra: int = 40):
    """Ajusta la ventana a su contenido real. Llamar tras empaquetar todos los widgets."""
    ventana.update_idletasks()
    ancho_final = ancho if ancho else ventana.winfo_reqwidth()
    alto_final = ventana.winfo_reqheight() + alto_extra
    ventana.geometry(f"{ancho_final}x{alto_final}")


def centrar_ventana(ventana, ancho: int, alto: int):
    """Centra una ventana en la pantalla."""
    ventana.update_idletasks()
    x = (ventana.winfo_screenwidth() - ancho) // 2
    y = (ventana.winfo_screenheight() - alto) // 2
    ventana.geometry(f"{ancho}x{alto}+{x}+{y}")


# ══════════════════════════════════════════════════════════════════
#  ENCABEZADO DE MÓDULO
# ══════════════════════════════════════════════════════════════════

class EncabezadoModulo(ttk.Frame):
    """
    Franja superior de color con el título del módulo y descripción.
    Incluye opcionalmente un ícono a la izquierda.
    """
    def __init__(self, parent, titulo: str, subtitulo: str = "", icono: str = ""):
        super().__init__(parent, style="Encabezado.TFrame", padding=(24, 16))
        fila = ttk.Frame(self, style="Encabezado.TFrame")
        fila.pack(fill="x")
        if icono:
            ttk.Label(fila, text=icono, style="Encabezado.TLabel",
                      font=("Segoe UI", 20)).pack(side="left", padx=(0, 12))
        col = ttk.Frame(fila, style="Encabezado.TFrame")
        col.pack(side="left", fill="x", expand=True)
        ttk.Label(col, text=titulo, style="EncabezadoTitulo.TLabel").pack(anchor="w")
        if subtitulo:
            ttk.Label(col, text=subtitulo, style="EncabezadoSubtitulo.TLabel").pack(anchor="w")


# ══════════════════════════════════════════════════════════════════
#  TARJETA KPI
# ══════════════════════════════════════════════════════════════════

class TarjetaKPI(ttk.Frame):
    """
    Tarjeta blanca con número grande y etiqueta.
    variante: "normal" | "alerta" | "exito" | "advertencia"
    """
    _ESTILOS_VALOR = {
        "normal":      "TarjetaValor.TLabel",
        "alerta":      "TarjetaValorAlerta.TLabel",
        "exito":       "TarjetaValorExito.TLabel",
        "advertencia": "TarjetaValorAdvertencia.TLabel",
    }

    def __init__(self, parent, etiqueta: str, valor_inicial: str = "—",
                 variante: str = "normal", icono: str = ""):
        super().__init__(parent, style="Tarjeta.TFrame", padding=(16, 14))
        self.var_valor = tk.StringVar(value=valor_inicial)
        estilo_valor = self._ESTILOS_VALOR.get(variante, "TarjetaValor.TLabel")

        fila_superior = ttk.Frame(self, style="Tarjeta.TFrame")
        fila_superior.pack(fill="x")
        ttk.Label(fila_superior, textvariable=self.var_valor,
                  style=estilo_valor).pack(side="left", anchor="w")
        if icono:
            ttk.Label(fila_superior, text=icono, style="TarjetaIcono.TLabel").pack(
                side="right", anchor="e")

        ttk.Label(self, text=etiqueta, style="TarjetaEtiqueta.TLabel",
                  wraplength=160).pack(anchor="w", pady=(2, 0))

        # Separador inferior decorativo
        sep = tk.Frame(self, height=3,
                       bg={
                           "normal":      COLOR_PRIMARIO,
                           "alerta":      COLOR_ALERTA,
                           "exito":       COLOR_EXITO,
                           "advertencia": COLOR_ADVERTENCIA,
                       }.get(variante, COLOR_PRIMARIO))
        sep.pack(fill="x", side="bottom")

    def actualizar(self, nuevo_valor: str):
        self.var_valor.set(nuevo_valor)


# ══════════════════════════════════════════════════════════════════
#  BARRA DE BÚSQUEDA
# ══════════════════════════════════════════════════════════════════

class BarraBusqueda(ttk.Frame):
    """
    Campo de búsqueda con placeholder + botones de acción.
    Los botones se agregan con agregar_boton().
    """
    def __init__(self, parent, al_escribir=None, placeholder="🔎  Buscar..."):
        super().__init__(parent)
        self._placeholder = placeholder
        self._mostrando_placeholder = True
        self._al_escribir = al_escribir

        self.var_texto = tk.StringVar()
        self.entrada = ttk.Entry(self, textvariable=self.var_texto, width=36,
                                 font=("Segoe UI", 10))
        self.entrada.pack(side="left", padx=(0, 10), ipady=2)

        self._mostrar_placeholder()
        self.entrada.bind("<FocusIn>", self._al_enfocar)
        self.entrada.bind("<FocusOut>", self._al_perder_foco)
        self.var_texto.trace_add("write", self._al_escribir_interno)

        # Frame para los botones de acción (a la derecha de la búsqueda)
        self._botones_frame = ttk.Frame(self)
        self._botones_frame.pack(side="left")

    def _mostrar_placeholder(self):
        self._mostrando_placeholder = True
        self.entrada.configure(foreground=COLOR_TEXTO_SECUNDARIO)
        self.var_texto.set(self._placeholder)

    def _al_enfocar(self, evento=None):
        if self._mostrando_placeholder:
            self._mostrando_placeholder = False
            self.var_texto.set("")
            self.entrada.configure(foreground=COLOR_TEXTO)

    def _al_perder_foco(self, evento=None):
        if not self.var_texto.get().strip():
            self._mostrar_placeholder()

    def _al_escribir_interno(self, *_args):
        if self._mostrando_placeholder:
            return
        if self._al_escribir:
            self._al_escribir(self.var_texto.get())

    def agregar_boton(self, texto: str, comando, estilo: str = "Accion.TButton"):
        boton = ttk.Button(self._botones_frame, text=texto, command=comando, style=estilo)
        boton.pack(side="left", padx=4)
        return boton

    def limpiar(self):
        self._al_enfocar()
        self.var_texto.set("")
        if self._al_escribir:
            self._al_escribir("")
        self._al_perder_foco()


# ══════════════════════════════════════════════════════════════════
#  TABLA DE DATOS
# ══════════════════════════════════════════════════════════════════

class TablaDatos(ttk.Treeview):
    """
    Treeview mejorado con:
    - Filas alternas de color
    - Tags de estado (verde/rojo/amarillo)
    - Doble clic configurable
    - Scrollbars vertical y horizontal
    - Anchos de columna automáticos

    Modos:
      con_id=True  (defecto): fila[0] = ID oculto como iid
      con_id=False: todos los valores visibles
    """

    _TAG_COLORES = {
        "exito":      {"background": "#E8F5E2", "foreground": "#2D6A22"},
        "alerta":     {"background": "#FDECEA", "foreground": "#8E2A1C"},
        "advertencia":{"background": "#FFF8E1", "foreground": "#7A5A00"},
        "normal":     {"background": "#FFFFFF", "foreground": COLOR_TEXTO},
        "par":        {"background": "#FFFDF5", "foreground": COLOR_TEXTO},
    }

    def __init__(self, parent, columnas: list[str], con_id: bool = True,
                 al_doble_clic=None, anchos: dict = None):
        super().__init__(parent, columns=columnas, show="headings", selectmode="browse")
        self._con_id = con_id
        self._al_doble_clic = al_doble_clic
        self._filas_actuales: list = []

        ancho_default = 120
        for col in columnas:
            ancho = (anchos or {}).get(col, ancho_default)
            self.heading(col, text=col)
            self.column(col, width=ancho, anchor="w", minwidth=60)

        # Tags de colores
        for tag, cfg in self._TAG_COLORES.items():
            self.tag_configure(tag, **cfg)

        # Scrollbars
        self._scroll_v = ttk.Scrollbar(parent, orient="vertical", command=self.yview)
        self._scroll_h = ttk.Scrollbar(parent, orient="horizontal", command=self.xview)
        self.configure(yscrollcommand=self._scroll_v.set,
                       xscrollcommand=self._scroll_h.set)

        if al_doble_clic:
            self.bind("<Double-1>", lambda e: al_doble_clic(self.id_seleccionado()))

    def empaquetar(self, **kwargs):
        """Coloca la tabla con sus dos scrollbars."""
        self._scroll_h.pack(side="bottom", fill="x")
        self.pack(side="left", fill="both", expand=True, **kwargs)
        self._scroll_v.pack(side="right", fill="y")

    def cargar_filas(self, filas: list[list], tags_por_fila: list[str] = None):
        """
        Carga filas en la tabla.
        tags_por_fila: lista de tags ("exito", "alerta", "advertencia", "normal")
        """
        self.delete(*self.get_children())
        self._filas_actuales = filas
        for i, fila in enumerate(filas):
            tag = (tags_por_fila[i] if tags_por_fila and i < len(tags_por_fila)
                   else ("par" if i % 2 == 1 else "normal"))
            if self._con_id:
                self.insert("", "end", iid=str(fila[0]), values=fila[1:], tags=(tag,))
            else:
                self.insert("", "end", values=fila, tags=(tag,))

    def filtrar(self, texto: str):
        """Filtra filas que contengan texto en columnas visibles."""
        texto = (texto or "").lower().strip()
        self.delete(*self.get_children())
        for i, fila in enumerate(self._filas_actuales):
            valores_visibles = fila[1:] if self._con_id else fila
            if not texto or any(texto in str(c).lower() for c in valores_visibles):
                tag = "par" if i % 2 == 1 else "normal"
                if self._con_id:
                    self.insert("", "end", iid=str(fila[0]), values=fila[1:], tags=(tag,))
                else:
                    self.insert("", "end", values=fila, tags=(tag,))

    def id_seleccionado(self):
        sel = self.selection()
        if not sel:
            return None
        if self._con_id:
            try:
                return int(sel[0])
            except (ValueError, IndexError):
                return None
        else:
            vals = self.item(sel[0], "values")
            try:
                return int(vals[0])
            except (ValueError, IndexError):
                return None


# ══════════════════════════════════════════════════════════════════
#  ESTADO BADGE
# ══════════════════════════════════════════════════════════════════

# Mapeo de estados internos a representaciones visuales
_ESTADO_MAP = {
    # Producción
    "INICIADA":    ("🟡", "Iniciada",   "advertencia"),
    "EN_PROCESO":  ("🟠", "En proceso", "advertencia"),
    "COMPLETADA":  ("🟢", "Completada", "exito"),
    "CANCELADA":   ("🔴", "Cancelada",  "alerta"),
    # Inventario
    "DISPONIBLE":  ("🟢", "Disponible", "exito"),
    "AGOTADO":     ("🔴", "Agotado",    "alerta"),
    "VENCIDO":     ("⚫", "Vencido",    "alerta"),
    "BAJO":        ("🟡", "Stock bajo", "advertencia"),
    # Usuarios
    "ACTIVO":      ("🟢", "Activo",     "exito"),
    "INACTIVO":    ("⚪", "Inactivo",   "normal"),
    # Compras/Ventas
    "PENDIENTE":   ("🟡", "Pendiente",  "advertencia"),
    "REGISTRADA":  ("🟢", "Registrada", "exito"),
}


def formatear_estado(estado_interno: str) -> str:
    """Convierte 'EN_PROCESO' → '🟠 En proceso'"""
    info = _ESTADO_MAP.get(str(estado_interno).upper())
    if info:
        return f"{info[0]} {info[1]}"
    return estado_interno


# ══════════════════════════════════════════════════════════════════
#  CAMPO DE FORMULARIO CON VALIDACIÓN INLINE
# ══════════════════════════════════════════════════════════════════

class CampoFormulario(ttk.Frame):
    """
    Label + Entry/Combobox con mensaje de error inline.
    obligatorio=True muestra el asterisco (*).
    """
    def __init__(self, parent, etiqueta: str, obligatorio: bool = False,
                 tipo: str = "entry", opciones: list = None, readonly: bool = False):
        super().__init__(parent)
        self._obligatorio = obligatorio
        self._tipo = tipo

        texto_label = f"{etiqueta} *" if obligatorio else etiqueta
        lbl = ttk.Label(self, text=texto_label, font=("Segoe UI", 9, "bold"))
        lbl.pack(anchor="w")

        self.var = tk.StringVar()
        if tipo == "combobox":
            self.widget = ttk.Combobox(self, textvariable=self.var,
                                        values=opciones or [], state="readonly" if readonly else "normal")
        else:
            self.widget = ttk.Entry(self, textvariable=self.var,
                                     state="readonly" if readonly else "normal")
        self.widget.pack(fill="x", pady=(2, 0))

        self._lbl_error = ttk.Label(self, text="", style="ErrorInline.TLabel")
        self._lbl_error.pack(anchor="w")

        if readonly:
            ttk.Label(self, text="Autocompletado automáticamente",
                      style="CampoAuto.TLabel").pack(anchor="w")

    def get(self) -> str:
        return self.var.get().strip()

    def set(self, valor: str):
        self.var.set(valor)

    def mostrar_error(self, mensaje: str):
        self._lbl_error.config(text=f"❌ {mensaje}")

    def limpiar_error(self):
        self._lbl_error.config(text="")

    def validar(self) -> bool:
        if self._obligatorio and not self.get():
            self.mostrar_error("Este campo es obligatorio")
            return False
        self.limpiar_error()
        return True


# ══════════════════════════════════════════════════════════════════
#  SECCIÓN DE FORMULARIO
# ══════════════════════════════════════════════════════════════════

class SeccionFormulario(ttk.LabelFrame):
    """LabelFrame con estilo mejorado para agrupar campos del formulario."""
    def __init__(self, parent, titulo: str, **kwargs):
        super().__init__(parent, text=f"  {titulo}  ",
                         style="SeccionFormulario.TLabelframe",
                         padding=(12, 8), **kwargs)


# ══════════════════════════════════════════════════════════════════
#  MENSAJE DE ESTADO (BANDA)
# ══════════════════════════════════════════════════════════════════

class MensajeEstado(ttk.Frame):
    """
    Banda de mensaje temporal en la parte superior del formulario.
    tipo: "exito" | "error" | "advertencia"
    """
    def __init__(self, parent):
        super().__init__(parent)
        self._label = None
        self._after_id = None

    def mostrar(self, texto: str, tipo: str = "exito", duracion_ms: int = 4000):
        if self._label:
            self._label.destroy()
        if self._after_id:
            self.after_cancel(self._after_id)

        cfg = {
            "exito":      ("#D4EDDA", "#155724", "✓"),
            "error":      ("#FDECEA", "#7B1111", "✗"),
            "advertencia":("#FFF3CD", "#856404", "⚠"),
        }.get(tipo, ("#D4EDDA", "#155724", "✓"))

        frame = tk.Frame(self, bg=cfg[0], pady=8, padx=12)
        frame.pack(fill="x")
        tk.Label(frame, text=f"{cfg[2]}  {texto}",
                 bg=cfg[0], fg=cfg[1],
                 font=("Segoe UI", 9), anchor="w", justify="left").pack(anchor="w")
        self._label = frame

        if duracion_ms > 0:
            self._after_id = self.after(duracion_ms, self._ocultar)

    def _ocultar(self):
        if self._label:
            self._label.destroy()
            self._label = None


# ══════════════════════════════════════════════════════════════════
#  DIÁLOGO DE CONFIRMACIÓN
# ══════════════════════════════════════════════════════════════════

class DialogoConfirmacion(tk.Toplevel):
    """
    Diálogo modal de confirmación para acciones importantes.
    Retorna True si el usuario confirmó, False si canceló.
    """
    def __init__(self, parent, titulo: str, mensaje: str,
                 texto_confirmar: str = "Confirmar",
                 texto_cancelar: str = "Cancelar",
                 peligro: bool = False):
        super().__init__(parent)
        self.title(titulo)
        self.resizable(False, False)
        self.grab_set()
        self.resultado = False

        # Franja de color arriba
        color_franja = COLOR_ALERTA if peligro else COLOR_PRIMARIO
        franja = tk.Frame(self, bg=color_franja, pady=12, padx=20)
        franja.pack(fill="x")
        icono = "⚠" if peligro else "?"
        tk.Label(franja, text=f"{icono}  {titulo}",
                 bg=color_franja, fg="white",
                 font=("Segoe UI", 13, "bold")).pack(anchor="w")

        # Cuerpo
        cuerpo = ttk.Frame(self, padding=(20, 16))
        cuerpo.pack(fill="both", expand=True)
        ttk.Label(cuerpo, text=mensaje, wraplength=340,
                  font=("Segoe UI", 10), justify="left").pack(anchor="w", pady=(0, 16))

        # Botones
        fila_botones = ttk.Frame(cuerpo)
        fila_botones.pack(fill="x")
        ttk.Button(fila_botones, text=texto_cancelar,
                   style="Secundario.TButton",
                   command=self._cancelar).pack(side="right", padx=(8, 0))
        estilo_confirmar = "Peligro.TButton" if peligro else "TButton"
        ttk.Button(fila_botones, text=texto_confirmar,
                   style=estilo_confirmar,
                   command=self._confirmar).pack(side="right")

        centrar_ventana(self, 400, 200)
        self.bind("<Escape>", lambda e: self._cancelar())

    def _confirmar(self):
        self.resultado = True
        self.destroy()

    def _cancelar(self):
        self.resultado = False
        self.destroy()


def confirmar(parent, titulo: str, mensaje: str,
              texto_confirmar: str = "Confirmar",
              texto_cancelar: str = "Cancelar",
              peligro: bool = False) -> bool:
    """Abre diálogo de confirmación y devuelve True/False."""
    dlg = DialogoConfirmacion(parent, titulo, mensaje,
                               texto_confirmar, texto_cancelar, peligro)
    parent.wait_window(dlg)
    return dlg.resultado


# ══════════════════════════════════════════════════════════════════
#  BARRA DE ESTADO INFERIOR
# ══════════════════════════════════════════════════════════════════

class BarraEstado(ttk.Frame):
    """Barra inferior con información del sistema."""
    def __init__(self, parent, usuario: str = "", rol: str = ""):
        super().__init__(parent, style="BarraEstado.TFrame", padding=(12, 3))
        self._lbl_usuario = ttk.Label(
            self, text=f"Usuario: {usuario}  |  Rol: {rol}",
            style="BarraEstado.TLabel")
        self._lbl_usuario.pack(side="left")
        self._lbl_db = ttk.Label(
            self, text="✓ Base de datos conectada",
            style="BarraEstadoOK.TLabel")
        self._lbl_db.pack(side="right")
