"""
vista_inventario.py
====================
Módulo de Inventario — cuatro pestañas:

  1) Stock actual   → resumen de cuánto hay de cada producto
  2) Lotes (FIFO)   → detalle lote por lote, ordenados del más antiguo
                      al más nuevo para visualizar el orden de consumo FIFO
  3) Movimientos    → historial completo de entradas, salidas y ajustes
  4) Catálogo       → alta y edición de productos
"""

import tkinter as tk
from tkinter import ttk, messagebox

from app.basedatos import nueva_sesion
from app.modelos import Producto, LoteInventario
from app.sesion import sesion_actual
from app.seguridad import puede
from app.logica_inventario import stock_total, ajustar_stock
from app.ui.widgets import EncabezadoModulo, BarraBusqueda, TablaDatos, ajustar_ventana_a_contenido
from app.ui.estilos import COLOR_TEXTO_SECUNDARIO


class VistaInventario(ttk.Frame):
    def __init__(self, parent):
        super().__init__(parent)
        EncabezadoModulo(
            self,
            "Módulo de Inventario",
            "Control de stock por producto, lotes con rotación FIFO, historial de movimientos y catálogo",
        ).pack(fill="x")

        notebook = ttk.Notebook(self)
        notebook.pack(fill="both", expand=True, padx=12, pady=8)

        self._pestana_stock(notebook)
        self._pestana_lotes(notebook)
        self._pestana_movimientos(notebook)
        self._pestana_catalogo(notebook)

        self.refrescar()

    # ── Pestaña: Stock actual ────────────────────────────────────
    def _pestana_stock(self, notebook):
        pestana = ttk.Frame(notebook, padding=8)
        notebook.add(pestana, text="Stock Actual")

        barra = BarraBusqueda(pestana, al_escribir=lambda t: self.tabla_stock.filtrar(t))
        barra.pack(fill="x", pady=(0, 8))

        contenedor = ttk.Frame(pestana)
        contenedor.pack(fill="both", expand=True)
        self.tabla_stock = TablaDatos(
            contenedor,
            ["Código", "Nombre del Producto", "Tipo", "Stock Disponible",
             "Unidad de Medida", "Stock Mínimo", "Estado"],
        )
        self.tabla_stock.empaquetar()

    # ── Pestaña: Lotes (FIFO) ────────────────────────────────────
    def _pestana_lotes(self, notebook):
        pestana = ttk.Frame(notebook, padding=8)
        notebook.add(pestana, text="Lotes (FIFO)")

        puede_ajustar = puede(sesion_actual.rol, "inventario", "ajuste")
        barra = BarraBusqueda(pestana, al_escribir=lambda t: self.tabla_lotes.filtrar(t))
        if puede_ajustar:
            barra.agregar_boton("Ajustar cantidad del lote", self._abrir_ajuste)
        barra.pack(fill="x", pady=(0, 8))

        ttk.Label(
            pestana,
            text="Los lotes están ordenados del más antiguo al más nuevo: así se consumen"
                 " primero los insumos ingresados antes (regla FIFO — primero en entrar,"
                 " primero en salir).",
            foreground=COLOR_TEXTO_SECUNDARIO,
        ).pack(anchor="w", pady=(0, 6))

        contenedor = ttk.Frame(pestana)
        contenedor.pack(fill="both", expand=True)
        self.tabla_lotes = TablaDatos(
            contenedor,
            ["N° de Lote", "Nombre del Producto", "Fecha de Ingreso",
             "Fecha de Vencimiento", "Cantidad Disponible", "Estado del Lote"],
        )
        self.tabla_lotes.empaquetar()

    # ── Pestaña: Movimientos ─────────────────────────────────────
    def _pestana_movimientos(self, notebook):
        pestana = ttk.Frame(notebook, padding=8)
        notebook.add(pestana, text="Historial de Movimientos")

        barra = BarraBusqueda(pestana, al_escribir=lambda t: self.tabla_movimientos.filtrar(t))
        barra.pack(fill="x", pady=(0, 8))

        contenedor = ttk.Frame(pestana)
        contenedor.pack(fill="both", expand=True)
        self.tabla_movimientos = TablaDatos(
            contenedor,
            ["Nombre del Producto", "N° de Lote Afectado", "Tipo de Movimiento",
             "Cantidad", "Referencia / Documento", "Fecha y Hora"],
        )
        self.tabla_movimientos.empaquetar()

    # ── Pestaña: Catálogo ────────────────────────────────────────
    def _pestana_catalogo(self, notebook):
        pestana = ttk.Frame(notebook, padding=8)
        notebook.add(pestana, text="Catálogo de Productos")

        puede_editar = puede(sesion_actual.rol, "inventario", "entrada")
        barra = BarraBusqueda(pestana, al_escribir=lambda t: self.tabla_catalogo.filtrar(t))
        if puede_editar:
            barra.agregar_boton("+ Nuevo producto", self._abrir_nuevo_producto)
        barra.pack(fill="x", pady=(0, 8))

        contenedor = ttk.Frame(pestana)
        contenedor.pack(fill="both", expand=True)
        self.tabla_catalogo = TablaDatos(
            contenedor,
            ["Código", "Nombre del Producto", "Tipo de Producto",
             "Unidad de Medida", "Precio de Venta (S/)", "Stock Mínimo"],
        )
        self.tabla_catalogo.empaquetar()

    # ── Refrescar todo ────────────────────────────────────────────
    def refrescar(self):
        with nueva_sesion() as db:
            # Stock
            filas_stock = []
            for p in db.query(Producto).filter_by(activo=True).order_by(
                    Producto.tipo, Producto.nombre).all():
                stock = stock_total(db, p.id)
                estado = "OK" if stock >= p.stock_minimo else "BAJO ⚠"
                filas_stock.append([
                    p.id, p.codigo, p.nombre, p.tipo,
                    f"{stock:.2f}", p.unidad_medida or "—",
                    f"{p.stock_minimo:.2f}", estado,
                ])

            # Lotes FIFO
            filas_lotes = []
            lotes = (db.query(LoteInventario)
                     .order_by(LoteInventario.fecha_ingreso.asc(), LoteInventario.id.asc())
                     .all())
            for lote in lotes:
                filas_lotes.append([
                    lote.id,
                    lote.numero_lote,
                    lote.producto.nombre,
                    str(lote.fecha_ingreso),
                    str(lote.fecha_vencimiento) if lote.fecha_vencimiento else "—",
                    f"{lote.cantidad_disponible:.2f}",
                    lote.estado,
                ])

            # Movimientos
            filas_movimientos = []
            from app.modelos import MovimientoInventario
            movimientos = (
                db.query(MovimientoInventario)
                .order_by(MovimientoInventario.fecha.desc())
                .limit(300)
                .all()
            )
            for m in movimientos:
                filas_movimientos.append([
                    m.id,
                    m.lote.producto.nombre if m.lote else "—",
                    m.lote.numero_lote if m.lote else "—",
                    m.tipo,
                    f"{m.cantidad:.2f}",
                    m.referencia or "—",
                    str(m.fecha)[:16],
                ])

            # Catálogo
            filas_catalogo = []
            for p in db.query(Producto).filter_by(activo=True).order_by(
                    Producto.tipo, Producto.nombre).all():
                filas_catalogo.append([
                    p.id, p.codigo, p.nombre, p.tipo,
                    p.unidad_medida or "—",
                    f"S/ {p.precio_venta:.2f}",
                    f"{p.stock_minimo:.2f}",
                ])

        self.tabla_stock.cargar_filas(filas_stock)
        self.tabla_lotes.cargar_filas(filas_lotes)
        self.tabla_movimientos.cargar_filas(filas_movimientos)
        self.tabla_catalogo.cargar_filas(filas_catalogo)

    # ── Acciones ──────────────────────────────────────────────────
    def _abrir_ajuste(self):
        lote_id = self.tabla_lotes.id_seleccionado()
        if not lote_id:
            messagebox.showwarning("Aviso", "Selecciona un lote de la lista.")
            return
        VentanaAjusteStock(self, lote_id, al_guardar=self.refrescar)

    def _abrir_nuevo_producto(self):
        VentanaProducto(self, al_guardar=self.refrescar)


class VentanaAjusteStock(tk.Toplevel):
    def __init__(self, parent, lote_id, al_guardar):
        super().__init__(parent)
        self.title("Ajustar cantidad de lote de inventario")
        self.lote_id = lote_id
        self.al_guardar = al_guardar

        with nueva_sesion() as db:
            lote = db.get(LoteInventario, lote_id)
            texto_lote = f"{lote.numero_lote}  —  {lote.producto.nombre}"
            cantidad_actual = lote.cantidad_disponible

        contenedor = ttk.Frame(self, padding=16)
        contenedor.pack(fill="both", expand=True)

        ttk.Label(contenedor, text=texto_lote, font=("Segoe UI", 10, "bold")).pack(anchor="w")
        ttk.Label(contenedor,
                  text=f"Cantidad disponible actual: {cantidad_actual:.2f}",
                  foreground=COLOR_TEXTO_SECUNDARIO).pack(anchor="w", pady=(0, 10))

        ttk.Label(contenedor, text="Nueva cantidad disponible (número exacto):").pack(anchor="w")
        self.var_nueva_cantidad = tk.StringVar(value=str(cantidad_actual))
        ttk.Entry(contenedor, textvariable=self.var_nueva_cantidad).pack(fill="x", pady=(0, 8))

        ttk.Label(contenedor, text="Motivo del ajuste (obligatorio):").pack(anchor="w")
        self.var_motivo = tk.StringVar()
        ttk.Entry(contenedor, textvariable=self.var_motivo).pack(fill="x", pady=(0, 10))

        ttk.Button(contenedor, text="Guardar ajuste", command=self._guardar).pack(fill="x")

        ajustar_ventana_a_contenido(self, ancho=380)

    def _guardar(self):
        try:
            nueva_cantidad = float(self.var_nueva_cantidad.get())
            if nueva_cantidad < 0:
                raise ValueError
        except ValueError:
            messagebox.showwarning("Aviso", "La cantidad debe ser un número mayor o igual a 0.")
            return
        if not self.var_motivo.get().strip():
            messagebox.showwarning("Aviso", "Ingresa el motivo del ajuste.")
            return

        with nueva_sesion() as db:
            try:
                ajustar_stock(db, self.lote_id, nueva_cantidad,
                               motivo=self.var_motivo.get().strip(),
                               usuario_id=sesion_actual.usuario_id)
                db.commit()
            except Exception as error:
                messagebox.showerror("Error", str(error))
                return

        self.al_guardar()
        self.destroy()


class VentanaProducto(tk.Toplevel):
    def __init__(self, parent, al_guardar):
        super().__init__(parent)
        self.title("Registrar nuevo producto en el catálogo")
        self.al_guardar = al_guardar

        contenedor = ttk.Frame(self, padding=16)
        contenedor.pack(fill="both", expand=True)

        self.var_codigo       = tk.StringVar()
        self.var_nombre       = tk.StringVar()
        self.var_tipo         = tk.StringVar(value="Insumo")
        self.var_unidad       = tk.StringVar()
        self.var_precio       = tk.StringVar(value="0")
        self.var_stock_minimo = tk.StringVar(value="0")

        ttk.Label(contenedor, text="Código único del producto (ej: INS-014):").pack(anchor="w")
        ttk.Entry(contenedor, textvariable=self.var_codigo).pack(fill="x", pady=(0, 8))

        ttk.Label(contenedor, text="Nombre del producto:").pack(anchor="w")
        ttk.Entry(contenedor, textvariable=self.var_nombre).pack(fill="x", pady=(0, 8))

        ttk.Label(contenedor, text="Tipo de producto:").pack(anchor="w")
        ttk.Combobox(contenedor, textvariable=self.var_tipo, state="readonly",
                     values=["Insumo", "Producto terminado"]).pack(fill="x", pady=(0, 8))

        ttk.Label(contenedor, text="Unidad de medida (kg, L, g, unidad...):").pack(anchor="w")
        ttk.Entry(contenedor, textvariable=self.var_unidad).pack(fill="x", pady=(0, 8))

        ttk.Label(contenedor,
                  text="Precio de venta en S/ (solo si es producto terminado):").pack(anchor="w")
        ttk.Entry(contenedor, textvariable=self.var_precio).pack(fill="x", pady=(0, 8))

        ttk.Label(contenedor,
                  text="Stock mínimo (cantidad mínima requerida para generar alerta):").pack(
            anchor="w")
        ttk.Entry(contenedor, textvariable=self.var_stock_minimo).pack(fill="x", pady=(0, 10))

        ttk.Button(contenedor, text="Registrar producto", command=self._guardar).pack(fill="x")

        ajustar_ventana_a_contenido(self, ancho=430)

    def _guardar(self):
        if not self.var_codigo.get().strip() or not self.var_nombre.get().strip():
            messagebox.showwarning("Aviso", "El código y el nombre del producto son obligatorios.")
            return
        try:
            precio = float(self.var_precio.get() or 0)
            stock_minimo = float(self.var_stock_minimo.get() or 0)
        except ValueError:
            messagebox.showwarning("Aviso", "El precio y el stock mínimo deben ser números.")
            return

        with nueva_sesion() as db:
            if db.query(Producto).filter_by(codigo=self.var_codigo.get().strip()).first():
                messagebox.showerror("Error",
                                      "Ya existe un producto con ese código en el catálogo.")
                return
            db.add(Producto(
                codigo=self.var_codigo.get().strip(),
                nombre=self.var_nombre.get().strip(),
                tipo=self.var_tipo.get(),
                unidad_medida=self.var_unidad.get().strip(),
                precio_venta=precio,
                stock_minimo=stock_minimo,
                activo=True,
            ))
            db.commit()

        self.al_guardar()
        self.destroy()