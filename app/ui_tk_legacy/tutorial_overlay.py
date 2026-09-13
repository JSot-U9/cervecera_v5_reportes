"""
tutorial_overlay.py
====================
El "motor visual" del tutorial interactivo: oscurece la interfaz,
deja un hueco iluminado alrededor del widget que se está explicando,
le dibuja un borde de acento y coloca cerca una tarjeta con el texto
y los botones de navegación.

IMPORTANTE — por qué NO se usan ventanas (Toplevel) separadas ni
transparencia real (`-alpha`):

  La primera versión de este overlay usaba 4 ventanas Toplevel sin
  bordes con `-alpha` para oscurecerlas. Eso falla en la práctica:
  en Linux sin un "compositor" activo (la situación más común en un
  escritorio estándar), Tk no puede mezclar la transparencia y
  termina pintando esas ventanas en NEGRO SÓLIDO en vez de oscurecido
  translúcido — y como son varias ventanas "siempre encima"
  independientes, el orden en que se dibujan unas sobre otras no está
  garantizado, así que la tarjeta con los botones podía quedar TAPADA
  por el oscurecido. Resultado: pantalla negra, sin texto ni botones,
  sin forma de salir.

  La solución robusta (y la técnica estándar para esto en Tkinter) es
  no usar ventanas nuevas: el oscurecido y la tarjeta son simples
  widgets `tk.Frame` **hijos de la propia ventana principal**,
  colocados con `.place()` encima de todo lo demás y traídos al
  frente con `.lift()`. Al ser hijos de la misma ventana:
    - No dependen de transparencia de ningún tipo (colores sólidos).
    - El orden de apilado (`lift`/`lower`) es 100% determinista.
    - Nunca pueden "salirse" de la ventana ni tapar otra aplicación.

Piezas principales:
  - OverlayTutorial        : coordina bandas + marco + tarjeta para UN paso.
  - boton_ayuda_contextual : botón "?" con una burbuja de ayuda puntual.
"""

import tkinter as tk
from tkinter import ttk

from app.ui.estilos import (
    COLOR_PRIMARIO, COLOR_PRIMARIO_CLARO, COLOR_SIDEBAR, COLOR_SIDEBAR_TEXTO,
)

# ── Paleta propia del overlay ────────────────────────────────────
# Antes la tarjeta usaba COLOR_TARJETA (blanco puro), lo que la hacía
# ver como un elemento ajeno pegado sobre el velo oscuro. Ahora se
# reutilizan los colores de marca de Cervecera (el verde del sidebar,
# el ámbar, el crema) para que se sienta parte de la misma interfaz.
_COLOR_VELO = COLOR_SIDEBAR              # velo que oscurece el resto de la pantalla
_COLOR_TARJETA_OSCURA = "#22331C"        # tarjeta: un tono apenas más claro que el velo
_COLOR_TEXTO_TARJETA = COLOR_SIDEBAR_TEXTO
_COLOR_TEXTO_TARJETA_SEC = "#B9C4A4"     # crema-verdoso apagado, para texto secundario

_GROSOR_MARCO = 3
_PADDING_HUECO = 6

_ANCHO_TARJETA = 340


class OverlayTutorial:
    """
    Gestiona el resaltado de un widget dentro de `root` (la ventana
    principal) y la tarjeta explicativa asociada. Todo se dibuja con
    widgets hijos de `root` posicionados con `.place()` — nunca con
    ventanas nuevas — para que sea imposible que quede "negro" por
    problemas de transparencia o de apilado entre ventanas.

    Uso típico:
        overlay = OverlayTutorial(root)
        overlay.mostrar_paso(widget, titulo="...", texto="...", ...)
        ...
        overlay.mostrar_paso(otro_widget, ...)   # mueve el resaltado
        ...
        overlay.cerrar()
    """

    def __init__(self, root: tk.Misc):
        self.root = root
        self._bandas: list[tk.Frame] = []      # arriba, abajo, izq, der
        self._marco: list[tk.Frame] = []       # 4 franjas de acento
        self._tarjeta: tk.Frame | None = None
        self._widget_actual = None
        self._bind_id = None
        self._escape_bind_id = None
        self._after_id = None
        self._cerrado = False
        self._on_saltar_actual = None

    # ── Piezas (bandas / marco) ──────────────────────────────────
    def _crear_banda(self, color) -> tk.Frame:
        f = tk.Frame(self.root, bg=color, highlightthickness=0, bd=0)
        return f

    def _asegurar_piezas(self, n_bandas: int, n_marco: int):
        while len(self._bandas) < n_bandas:
            self._bandas.append(self._crear_banda(_COLOR_VELO))
        while len(self._marco) < n_marco:
            self._marco.append(self._crear_banda(COLOR_PRIMARIO))

    def _quitar_extra(self, piezas: list, n_usadas: int):
        while len(piezas) > n_usadas:
            pieza = piezas.pop()
            try:
                pieza.place_forget()
                pieza.destroy()
            except tk.TclError:
                pass

    def _ubicar(self, widget: tk.Widget, x, y, w, h):
        w, h = max(0, int(w)), max(0, int(h))
        if w <= 0 or h <= 0:
            widget.place_forget()
            return
        widget.place(x=int(x), y=int(y), width=w, height=h)
        widget.lift()

    def _geometria_raiz(self):
        """Tamaño del área de contenido de `root`. Como todo se coloca
        con `.place()` sobre `root` mismo, las coordenadas son
        relativas a `root` — no hace falta ninguna coordenada de
        pantalla."""
        self.root.update_idletasks()
        return self.root.winfo_width(), self.root.winfo_height()

    def _posicion_relativa(self, widget):
        """Posición y tamaño de `widget`, en coordenadas relativas a
        `root` (no de pantalla)."""
        widget.update_idletasks()
        wx = widget.winfo_rootx() - self.root.winfo_rootx()
        wy = widget.winfo_rooty() - self.root.winfo_rooty()
        return wx, wy, widget.winfo_width(), widget.winfo_height()

    def _dibujar_resaltado(self, widget):
        """Coloca las 4 bandas oscuras + el marco alrededor de
        `widget` (coordenadas relativas a `root`). Si `widget` es
        None, oscurece toda la ventana (sin hueco)."""
        rw, rh = self._geometria_raiz()

        hueco_valido = False
        if widget is not None:
            try:
                if widget.winfo_ismapped():
                    wx, wy, ww, wh = self._posicion_relativa(widget)
                    if ww > 1 and wh > 1:
                        hueco_valido = True
            except tk.TclError:
                hueco_valido = False

        if hueco_valido:
            hx = max(0, wx - _PADDING_HUECO)
            hy = max(0, wy - _PADDING_HUECO)
            hx2 = min(rw, wx + ww + _PADDING_HUECO)
            hy2 = min(rh, wy + wh + _PADDING_HUECO)
            hw, hh = max(0, hx2 - hx), max(0, hy2 - hy)
        else:
            # Sin widget real que resaltar: "hueco" de tamaño cero,
            # para que las 4 bandas cubran toda la ventana.
            hx, hy = rw // 2, rh // 2
            hw, hh = 0, 0

        # 4 bandas: arriba, abajo, izquierda, derecha (alrededor del hueco)
        geoms = [
            (0, 0, rw, hy),                          # arriba
            (0, hy + hh, rw, rh - (hy + hh)),        # abajo
            (0, hy, hx, hh),                          # izquierda
            (hx + hw, hy, rw - (hx + hw), hh),        # derecha
        ]
        self._asegurar_piezas(4, 0)
        for banda, (x, y, w, h) in zip(self._bandas, geoms):
            self._ubicar(banda, x, y, w, h)

        # Marco de acento alrededor del hueco (4 franjas delgadas)
        if hueco_valido and hw > 0 and hh > 0:
            marco_geoms = [
                (hx, hy, hw, _GROSOR_MARCO),                                  # borde superior
                (hx, hy + hh - _GROSOR_MARCO, hw, _GROSOR_MARCO),             # borde inferior
                (hx, hy, _GROSOR_MARCO, hh),                                  # borde izquierdo
                (hx + hw - _GROSOR_MARCO, hy, _GROSOR_MARCO, hh),             # borde derecho
            ]
            self._asegurar_piezas(4, 4)
            for franja, (x, y, w, h) in zip(self._marco, marco_geoms):
                self._ubicar(franja, x, y, w, h)
        else:
            self._quitar_extra(self._marco, 0)

        return hx, hy, hw, hh, rw, rh

    def _posicionar_tarjeta(self, hx, hy, hw, hh, rw, rh):
        self._tarjeta.update_idletasks()
        alto_tarjeta = self._tarjeta.winfo_reqheight()
        ancho_tarjeta = _ANCHO_TARJETA
        margen = 14

        candidatos = [
            (hx, hy + hh + margen),                                   # debajo
            (hx, hy - alto_tarjeta - margen),                         # encima
            (hx + hw + margen, hy),                                   # derecha
            (hx - ancho_tarjeta - margen, hy),                        # izquierda
        ]
        x, y = candidatos[0]
        for cx, cy in candidatos:
            if (cx >= 0 and cx + ancho_tarjeta <= rw
                    and cy >= 0 and cy + alto_tarjeta <= rh):
                x, y = cx, cy
                break
        # Si ningún candidato entra perfecto, se recorta a los límites
        # de la ventana principal para que nunca quede fuera de vista.
        x = max(4, min(x, rw - ancho_tarjeta - 4))
        y = max(4, min(y, rh - alto_tarjeta - 4))
        self._tarjeta.place(x=int(x), y=int(y), width=ancho_tarjeta, height=alto_tarjeta)
        self._tarjeta.lift()

    def _centrar_tarjeta(self, rw, rh):
        self._tarjeta.update_idletasks()
        alto_tarjeta = self._tarjeta.winfo_reqheight()
        ancho_tarjeta = _ANCHO_TARJETA + 40
        x = max(4, (rw - ancho_tarjeta) // 2)
        y = max(4, (rh - alto_tarjeta) // 2)
        self._tarjeta.place(x=int(x), y=int(y), width=ancho_tarjeta, height=alto_tarjeta)
        self._tarjeta.lift()

    # ── Construcción de la tarjeta ───────────────────────────────
    def _crear_tarjeta(self, icono, titulo, texto, indice, total,
                        on_anterior, on_siguiente, on_saltar,
                        mostrar_anterior, es_ultimo, texto_siguiente=None,
                        extra_widget_factory=None, mostrar_siguiente=True,
                        texto_saltar="Saltar tutorial ✕"):
        if self._tarjeta is not None:
            try:
                self._tarjeta.destroy()
            except tk.TclError:
                pass

        tarjeta = tk.Frame(self.root, bg=_COLOR_TARJETA_OSCURA,
                            highlightbackground=COLOR_PRIMARIO,
                            highlightthickness=2, bd=0)

        franja = tk.Frame(tarjeta, bg=COLOR_PRIMARIO, padx=16, pady=10)
        franja.pack(fill="x")
        fila_franja = tk.Frame(franja, bg=COLOR_PRIMARIO)
        fila_franja.pack(fill="x")
        if icono:
            tk.Label(fila_franja, text=icono, bg=COLOR_PRIMARIO, fg="white",
                      font=("Segoe UI", 16)).pack(side="left", padx=(0, 10))
        col = tk.Frame(fila_franja, bg=COLOR_PRIMARIO)
        col.pack(side="left", fill="x", expand=True)
        tk.Label(col, text=titulo, bg=COLOR_PRIMARIO, fg="white",
                  font=("Segoe UI", 12, "bold"), anchor="w",
                  wraplength=_ANCHO_TARJETA - 70, justify="left").pack(fill="x")
        if total:
            tk.Label(col, text=f"Paso {indice + 1} de {total}", bg=COLOR_PRIMARIO,
                      fg=COLOR_PRIMARIO_CLARO, font=("Segoe UI", 8)).pack(fill="x")

        cuerpo = tk.Frame(tarjeta, bg=_COLOR_TARJETA_OSCURA, padx=16, pady=12)
        cuerpo.pack(fill="both", expand=True)
        tk.Label(cuerpo, text=texto, bg=_COLOR_TARJETA_OSCURA, fg=_COLOR_TEXTO_TARJETA,
                  font=("Segoe UI", 10), wraplength=_ANCHO_TARJETA - 32,
                  justify="left", anchor="nw").pack(fill="x")

        if extra_widget_factory is not None:
            extra_widget_factory(cuerpo)

        barra = tk.Frame(tarjeta, bg=_COLOR_TARJETA_OSCURA, padx=16, pady=12)
        barra.pack(fill="x")
        ttk.Button(barra, text=texto_saltar, style="Secundario.TButton",
                   command=on_saltar).pack(side="left")
        if mostrar_siguiente:
            ttk.Button(barra, text=(texto_siguiente or ("Finalizar  ✓" if es_ultimo else "Siguiente  ▶")),
                       command=on_siguiente).pack(side="right")
        if mostrar_anterior:
            ttk.Button(barra, text="◀  Anterior", style="Secundario.TButton",
                       command=on_anterior).pack(side="right", padx=(0, 8))

        self._tarjeta = tarjeta
        self._on_saltar_actual = on_saltar
        return tarjeta

    # ── API pública ───────────────────────────────────────────────
    def mostrar_paso(self, widget, *, icono="💡", titulo="", texto="",
                      indice=0, total=0, on_anterior=None, on_siguiente=None,
                      on_saltar=None, mostrar_anterior=True, es_ultimo=False,
                      texto_siguiente=None, extra_widget_factory=None,
                      mostrar_siguiente=True, texto_saltar="Saltar tutorial ✕"):
        """Resalta `widget` (o toda la ventana si es None) y muestra la
        tarjeta explicativa junto a él. Nunca lanza una excepción por
        un widget inválido: en el peor caso, muestra la tarjeta
        centrada sin resaltar nada."""
        if self._cerrado:
            return
        self._widget_actual = widget
        try:
            hx, hy, hw, hh, rw, rh = self._dibujar_resaltado(widget)
        except tk.TclError:
            hx, hy, hw, hh = 0, 0, 0, 0
            rw = max(self.root.winfo_width(), 400)
            rh = max(self.root.winfo_height(), 300)

        self._crear_tarjeta(
            icono, titulo, texto, indice, total,
            on_anterior or (lambda: None), on_siguiente or (lambda: None),
            on_saltar or (lambda: None), mostrar_anterior, es_ultimo,
            texto_siguiente, extra_widget_factory,
            mostrar_siguiente, texto_saltar,
        )
        try:
            if widget is not None and hw > 0 and hh > 0:
                self._posicionar_tarjeta(hx, hy, hw, hh, rw, rh)
            else:
                self._centrar_tarjeta(rw, rh)
        except tk.TclError:
            pass

        self._asegurar_bindings()

    def _asegurar_bindings(self):
        if self._bind_id is None:
            self._bind_id = self.root.bind("<Configure>", self._al_redimensionar, add="+")
        if self._escape_bind_id is None:
            self._escape_bind_id = self.root.bind(
                "<Escape>", lambda e: self._on_saltar_actual and self._on_saltar_actual(), add="+")

    def _al_redimensionar(self, _evento=None):
        if self._cerrado or self._tarjeta is None:
            return
        if self._after_id is not None:
            try:
                self.root.after_cancel(self._after_id)
            except tk.TclError:
                pass
        self._after_id = self.root.after(60, self._reposicionar_todo)

    def _reposicionar_todo(self):
        if self._cerrado or self._tarjeta is None:
            return
        try:
            hx, hy, hw, hh, rw, rh = self._dibujar_resaltado(self._widget_actual)
            if self._widget_actual is not None and hw > 0 and hh > 0:
                self._posicionar_tarjeta(hx, hy, hw, hh, rw, rh)
            else:
                self._centrar_tarjeta(rw, rh)
        except tk.TclError:
            pass

    def cerrar(self):
        if self._cerrado:
            return
        self._cerrado = True
        if self._bind_id is not None:
            try:
                self.root.unbind("<Configure>", self._bind_id)
            except tk.TclError:
                pass
            self._bind_id = None
        if self._escape_bind_id is not None:
            try:
                self.root.unbind("<Escape>", self._escape_bind_id)
            except tk.TclError:
                pass
            self._escape_bind_id = None
        if self._after_id is not None:
            try:
                self.root.after_cancel(self._after_id)
            except tk.TclError:
                pass
        for pieza in self._bandas + self._marco:
            try:
                pieza.place_forget()
                pieza.destroy()
            except tk.TclError:
                pass
        self._bandas, self._marco = [], []
        if self._tarjeta is not None:
            try:
                self._tarjeta.place_forget()
                self._tarjeta.destroy()
            except tk.TclError:
                pass
            self._tarjeta = None


# ══════════════════════════════════════════════════════════════════
#  AYUDA CONTEXTUAL ("?" puntual, sin oscurecer la pantalla)
# ══════════════════════════════════════════════════════════════════
# Esta burbuja SÍ puede ser una ventana Toplevel aparte: no usa
# transparencia y, si en algún sistema aparece detrás de la ventana
# principal, basta con hacer clic de nuevo (a diferencia del overlay,
# nunca deja a la aplicación inutilizable).

class _PopupAyudaContextual(tk.Toplevel):
    """Burbuja pequeña con una explicación puntual (FIFO, costos, etc.)."""

    def __init__(self, parent, boton_origen, titulo: str, texto: str):
        super().__init__(parent)
        self.overrideredirect(True)
        try:
            self.attributes("-topmost", True)
        except tk.TclError:
            pass
        self.configure(bg=_COLOR_TARJETA_OSCURA, highlightbackground=COLOR_PRIMARIO,
                       highlightthickness=2)

        franja = tk.Frame(self, bg=COLOR_PRIMARIO, padx=14, pady=8)
        franja.pack(fill="x")
        tk.Label(franja, text=f"❓  {titulo}", bg=COLOR_PRIMARIO, fg="white",
                  font=("Segoe UI", 11, "bold"), anchor="w").pack(fill="x")

        cuerpo = tk.Frame(self, bg=_COLOR_TARJETA_OSCURA, padx=14, pady=10)
        cuerpo.pack(fill="both", expand=True)
        tk.Label(cuerpo, text=texto, bg=_COLOR_TARJETA_OSCURA, fg=_COLOR_TEXTO_TARJETA,
                  font=("Segoe UI", 9), wraplength=300,
                  justify="left", anchor="nw").pack(fill="x")

        barra = tk.Frame(self, bg=_COLOR_TARJETA_OSCURA, padx=14, pady=10)
        barra.pack(fill="x")
        ttk.Button(barra, text="Entendido", command=self.destroy).pack(side="right")

        self.update_idletasks()
        ancho, alto = 330, self.winfo_reqheight()
        bx = boton_origen.winfo_rootx()
        by = boton_origen.winfo_rooty() + boton_origen.winfo_height() + 6
        pantalla_ancho = self.winfo_screenwidth()
        if bx + ancho > pantalla_ancho:
            bx = pantalla_ancho - ancho - 10
        self.geometry(f"{ancho}x{alto}+{bx}+{by}")

        self.bind("<Escape>", lambda e: self.destroy())
        try:
            self.focus_force()
        except tk.TclError:
            pass
        # Se cierra si el usuario hace clic fuera de la burbuja.
        self.bind("<FocusOut>", self._quiza_cerrar)

    def _quiza_cerrar(self, _evento=None):
        self.after(150, self._cerrar_si_perdio_foco)

    def _cerrar_si_perdio_foco(self):
        try:
            if self.focus_get() is None:
                self.destroy()
        except (tk.TclError, KeyError):
            pass


def boton_ayuda_contextual(parent, titulo: str, texto: str, **pack_kwargs) -> ttk.Button:
    """
    Crea (y empaqueta) un botón "?" pequeño que, al pulsarlo, abre una
    burbuja de ayuda contextual con `titulo`/`texto`. Pensado para
    colocarse junto a controles o conceptos complejos (FIFO, costos,
    recetas, reportes...).
    """
    boton = ttk.Button(parent, text="❓", width=3, style="Secundario.TButton")
    boton.configure(command=lambda: _PopupAyudaContextual(parent.winfo_toplevel(), boton, titulo, texto))
    if pack_kwargs:
        boton.pack(**pack_kwargs)
    return boton
