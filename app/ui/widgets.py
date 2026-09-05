"""widgets.py
==========
Piezas de interfaz que se repiten en varias pantallas, para no
copiar y pegar el mismo código en cada módulo:

  - ajustar_ventana_a_contenido: cambia el tamaño de una ventana para
                      que se ajuste a su contenido real.
  - TablaDatos:      tabla (Treeview) con dos modos:
                       * con_id=True  (por defecto): la primera columna
                         de cada fila es el ID interno — se almacena
                         como iid de la fila y NO se muestra. Los datos
                         que se muestran son fila[1:].
                       * con_id=False: todos los valores se muestran.
                         Se usa en subtablas temporales (lista de items
                         en nueva orden) que no necesitan seleccionar
                         por ID.
  - TarjetaKPI:       "tarjetita" con un número grande y etiqueta.
  - BarraBusqueda:    campo de texto para filtrar la tabla de abajo.
  - EncabezadoModulo: título + subtítulo arriba de cada módulo.
"""

import tkinter as tk
from tkinter import ttk

from app.ui.estilos import COLOR_TEXTO, COLOR_TEXTO_SECUNDARIO


def ajustar_ventana_a_contenido(ventana, ancho: int = None, alto_extra: int = 40):
    """
    Cambia el tamaño de una ventana (Toplevel o Tk) para que se ajuste
    al contenido real que tiene adentro, en vez de depender de un
    tamaño fijo escrito a mano.

    Se debe llamar DESPUÉS de crear y empaquetar (.pack) todos los
    widgets de la ventana — normalmente en la última línea de __init__.
    """
    ventana.update_idletasks()
    ancho_final = ancho if ancho else ventana.winfo_reqwidth()
    alto_final = ventana.winfo_reqheight() + alto_extra
    ventana.geometry(f"{ancho_final}x{alto_final}")


class EncabezadoModulo(ttk.Frame):
    """
    La franja de color que aparece arriba de cada pantalla, con el
    título del módulo y una descripción corta debajo.
    """

    def __init__(self, parent, titulo: str, subtitulo: str = ""):
        super().__init__(parent, style="Encabezado.TFrame", padding=(24, 18))
        ttk.Label(self, text=titulo, style="EncabezadoTitulo.TLabel").pack(anchor="w")
        if subtitulo:
            ttk.Label(self, text=subtitulo, style="EncabezadoSubtitulo.TLabel").pack(anchor="w")


class TarjetaKPI(ttk.Frame):
    """
    Una tarjeta blanca con un valor grande y una etiqueta gris debajo
    (ej: "42" / "Productos activos"). Se usa en el Dashboard y en Costos.

    'variante' cambia el color del número grande:
        "normal" -> ámbar  |  "alerta" -> rojo  |  "exito" -> verde
    """

    _ESTILOS_VALOR = {
        "normal": "TarjetaValor.TLabel",
        "alerta": "TarjetaValorAlerta.TLabel",
        "exito":  "TarjetaValorExito.TLabel",
    }

    def __init__(self, parent, etiqueta: str, valor_inicial: str = "—", variante: str = "normal"):
        super().__init__(parent, style="Tarjeta.TFrame", padding=14)
        self.var_valor = tk.StringVar(value=valor_inicial)
        estilo_valor = self._ESTILOS_VALOR.get(variante, "TarjetaValor.TLabel")
        ttk.Label(self, textvariable=self.var_valor, style=estilo_valor).pack(anchor="w")
        ttk.Label(self, text=etiqueta, style="TarjetaEtiqueta.TLabel").pack(anchor="w")

    def actualizar(self, nuevo_valor: str):
        self.var_valor.set(nuevo_valor)


class BarraBusqueda(ttk.Frame):
    """
    Campo de texto que llama a 'al_escribir(texto)' cada vez que el
    usuario escribe algo. Muestra un placeholder en gris que desaparece
    al hacer clic — así queda claro que ese campo filtra la tabla.
    """

    def __init__(self, parent, al_escribir=None, placeholder="Buscar o filtrar..."):
        super().__init__(parent)
        self._placeholder = placeholder
        self._mostrando_placeholder = True
        self._al_escribir = al_escribir

        self.var_texto = tk.StringVar()
        self.entrada = ttk.Entry(self, textvariable=self.var_texto, width=40)
        self.entrada.pack(side="left", padx=(0, 8))

        self._mostrar_placeholder()
        self.entrada.bind("<FocusIn>", self._al_enfocar)
        self.entrada.bind("<FocusOut>", self._al_perder_foco)
        self.var_texto.trace_add("write", self._al_escribir_interno)

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

    def agregar_boton(self, texto: str, comando):
        boton = ttk.Button(self._botones_frame, text=texto, command=comando)
        boton.pack(side="left", padx=4)
        return boton


class TablaDatos(ttk.Treeview):
    """
    Envuelve un ttk.Treeview para simplificar la carga de filas.

    Dos modos:

      con_id=True  (defecto): el primer elemento de cada fila es el ID
        interno. Se guarda como 'iid' del item (identificador interno
        de Treeview) y NO se muestra como columna. Así la tabla se ve
        limpia y 'id_seleccionado()' devuelve ese ID directamente.
        Ejemplo:
            columnas = ["N° Orden de Compra", "Proveedor", "Total (S/)"]
            filas    = [[3, "OC-0003", "Proveedor X", "S/ 200.00"], ...]

      con_id=False: todos los valores son columnas visibles. Para
        subtablas temporales (lista de items en nueva orden, etc.)
        donde no se necesita seleccionar por ID de base de datos.
    """

    def __init__(self, parent, columnas: list[str], con_id: bool = True):
        super().__init__(parent, columns=columnas, show="headings", selectmode="browse")
        self._con_id = con_id
        for col in columnas:
            self.heading(col, text=col)
            self.column(col, width=130, anchor="w")
        self._filas_actuales: list = []

        barra = ttk.Scrollbar(parent, orient="vertical", command=self.yview)
        self.configure(yscrollcommand=barra.set)
        self._barra_scroll = barra

    def empaquetar(self, **kwargs):
        """Ubica la tabla y su scrollbar juntos (llamar en vez de .pack()/.grid())."""
        self.pack(side="left", fill="both", expand=True, **kwargs)
        self._barra_scroll.pack(side="right", fill="y")

    def cargar_filas(self, filas: list[list]):
        """
        Carga la lista de filas en la tabla.

        Si con_id=True: fila[0] = ID (oculto como iid), fila[1:] = valores visibles.
        Si con_id=False: todos los valores de la fila se muestran.
        """
        self.delete(*self.get_children())
        self._filas_actuales = filas
        for fila in filas:
            if self._con_id:
                self.insert("", "end", iid=str(fila[0]), values=fila[1:])
            else:
                self.insert("", "end", values=fila)

    def filtrar(self, texto: str):
        """Muestra solo las filas que contienen 'texto' en alguna columna visible."""
        texto = (texto or "").lower().strip()
        self.delete(*self.get_children())
        for fila in self._filas_actuales:
            valores_visibles = fila[1:] if self._con_id else fila
            if not texto or any(texto in str(celda).lower() for celda in valores_visibles):
                if self._con_id:
                    self.insert("", "end", iid=str(fila[0]), values=fila[1:])
                else:
                    self.insert("", "end", values=fila)

    def id_seleccionado(self):
        """
        Devuelve el ID de la fila seleccionada:
          - Si con_id=True: devuelve el iid (que es el ID de la BD).
          - Si con_id=False: devuelve el valor de la primera columna visible.
        Devuelve None si no hay selección.
        """
        seleccion = self.selection()
        if not seleccion:
            return None
        if self._con_id:
            try:
                return int(seleccion[0])
            except (ValueError, IndexError):
                return None
        else:
            valores = self.item(seleccion[0], "values")
            try:
                return int(valores[0])
            except (ValueError, IndexError):
                return None