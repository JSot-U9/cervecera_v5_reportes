"""
vista_inventario.py
====================
Módulo de Inventario — 4 pestañas con mejoras UX:
- Estados visuales en tabla de stock
- Filas coloreadas por estado
- Encabezados simplificados
"""

import tkinter as tk
from tkinter import ttk, messagebox

from app.basedatos import nueva_sesion
from app.modelos import Producto, LoteInventario
from app.sesion import sesion_actual
from app.seguridad import puede
from app.logica_inventario import stock_total, ajustar_stock
from app.ui.widgets import (
    EncabezadoModulo, BarraBusqueda, TablaDatos, ajustar_ventana_a_contenido,
    centrar_ventana, SeccionFormulario, MensajeEstado, formatear_estado
)
from app.ui.estilos import COLOR_TEXTO_SECUNDARIO, COLOR_PRIMARIO, COLOR_ALERTA, COLOR_EXITO


class VistaInventario(ttk.Frame):
    def __init__(self, parent):
        super().__init__(parent)
        EncabezadoModulo(
            self,
            "Inventario",
            "Stock actual · Lotes FIFO · Movimientos · Catálogo de productos",
            icono="📦",
        ).pack(fill="x")

        notebook = ttk.Notebook(self)
        notebook.pack(fill="both", expand=True, padx=12, pady=8)

        self._pestana_stock(notebook)
        self._pestana_lotes(notebook)
        self._pestana_movimientos(notebook)
        self._pestana_catalogo(notebook)

        self.refrescar()

    def _pestana_stock(self, notebook):
        pestana = ttk.Frame(notebook, padding=8)
        notebook.add(pestana, text="  📊  Stock Actual  ")

        barra = BarraBusqueda(pestana, al_escribir=lambda t: self.tabla_stock.filtrar(t),
                               placeholder="🔎  Buscar producto...")
        barra.agregar_boton("📊  Reporte", self._abrir_dialogo_reporte,
                             estilo="AccionSecundaria.TButton")
        barra.pack(fill="x", pady=(0, 8))

        contenedor = ttk.Frame(pestana)
        contenedor.pack(fill="both", expand=True)
        self.tabla_stock = TablaDatos(
            contenedor,
            ["Código", "Nombre", "Tipo", "Stock", "Unidad", "Stock Mín.", "Estado"],
            anchos={"Código": 90, "Nombre": 180, "Tipo": 120, "Stock": 90,
                    "Unidad": 80, "Stock Mín.": 90, "Estado": 110},
        )
        self.tabla_stock.empaquetar()

    def _pestana_lotes(self, notebook):
        pestana = ttk.Frame(notebook, padding=8)
        notebook.add(pestana, text="  🗂  Lotes FIFO  ")

        puede_ajustar = puede(sesion_actual.rol, "inventario", "ajuste")
        barra = BarraBusqueda(pestana, al_escribir=lambda t: self.tabla_lotes.filtrar(t),
                               placeholder="🔎  Buscar lote...")
        if puede_ajustar:
            barra.agregar_boton("⚖  Ajustar cantidad", self._abrir_ajuste,
                                 estilo="AccionSecundaria.TButton")
        barra.pack(fill="x", pady=(0, 6))

        ttk.Label(
            pestana,
            text="Los lotes se consumen del más antiguo al más nuevo (FIFO). "
                 "El sistema descuenta siempre del lote con la fecha de ingreso más temprana.",
            foreground=COLOR_TEXTO_SECUNDARIO,
            font=("Segoe UI", 8, "italic"),
        ).pack(anchor="w", pady=(0, 6))

        contenedor = ttk.Frame(pestana)
        contenedor.pack(fill="both", expand=True)
        self.tabla_lotes = TablaDatos(
            contenedor,
            ["N° Lote", "Producto", "Ingresado", "Vencimiento", "Cantidad", "Estado"],
            anchos={"N° Lote": 130, "Producto": 170, "Ingresado": 110,
                    "Vencimiento": 110, "Cantidad": 90, "Estado": 120},
        )
        self.tabla_lotes.empaquetar()

    def _pestana_movimientos(self, notebook):
        pestana = ttk.Frame(notebook, padding=8)
        notebook.add(pestana, text="  📋  Movimientos  ")

        barra = BarraBusqueda(pestana, al_escribir=lambda t: self.tabla_movimientos.filtrar(t),
                               placeholder="🔎  Buscar movimiento...")
        barra.pack(fill="x", pady=(0, 8))

        contenedor = ttk.Frame(pestana)
        contenedor.pack(fill="both", expand=True)
        self.tabla_movimientos = TablaDatos(
            contenedor,
            ["Producto", "Lote", "Tipo", "Cantidad", "Referencia", "Fecha"],
            anchos={"Producto": 160, "Lote": 120, "Tipo": 100,
                    "Cantidad": 80, "Referencia": 160, "Fecha": 130},
        )
        self.tabla_movimientos.empaquetar()

    def _pestana_catalogo(self, notebook):
        pestana = ttk.Frame(notebook, padding=8)
        notebook.add(pestana, text="  📦  Catálogo  ")

        puede_editar = puede(sesion_actual.rol, "inventario", "entrada")
        barra = BarraBusqueda(pestana, al_escribir=lambda t: self.tabla_catalogo.filtrar(t),
                               placeholder="🔎  Buscar en catálogo...")
        if puede_editar:
            barra.agregar_boton("＋  Nuevo producto", self._abrir_nuevo_producto)
        barra.pack(fill="x", pady=(0, 8))

        contenedor = ttk.Frame(pestana)
        contenedor.pack(fill="both", expand=True)
        self.tabla_catalogo = TablaDatos(
            contenedor,
            ["Código", "Nombre", "Tipo", "Unidad", "Precio Venta (S/)", "Stock Mín."],
            anchos={"Código": 90, "Nombre": 180, "Tipo": 120, "Unidad": 70,
                    "Precio Venta (S/)": 130, "Stock Mín.": 90},
        )
        self.tabla_catalogo.empaquetar()

    def refrescar(self):
        with nueva_sesion() as db:
            # Stock con estados visuales y colores
            filas_stock = []
            tags_stock = []
            for p in db.query(Producto).filter_by(activo=True).order_by(
                    Producto.tipo, Producto.nombre).all():
                stock = stock_total(db, p.id)
                if stock <= 0:
                    estado = "🔴 Agotado"
                    tag = "alerta"
                elif stock < p.stock_minimo:
                    estado = "🟡 Stock bajo"
                    tag = "advertencia"
                else:
                    estado = "🟢 Normal"
                    tag = "exito"
                filas_stock.append([
                    p.id, p.codigo, p.nombre, p.tipo,
                    f"{stock:.2f}", p.unidad_medida or "—",
                    f"{p.stock_minimo:.2f}", estado,
                ])
                tags_stock.append(tag)

            # Lotes FIFO con estados
            filas_lotes = []
            tags_lotes = []
            lotes = (db.query(LoteInventario)
                     .order_by(LoteInventario.fecha_ingreso.asc(), LoteInventario.id.asc())
                     .all())
            for i, lote in enumerate(lotes):
                estado = formatear_estado(lote.estado)
                tag = "normal" if i % 2 == 0 else "par"
                if lote.estado == "VENCIDO":
                    tag = "alerta"
                elif lote.estado == "AGOTADO":
                    tag = "alerta"
                filas_lotes.append([
                    lote.id,
                    lote.numero_lote,
                    lote.producto.nombre,
                    str(lote.fecha_ingreso),
                    str(lote.fecha_vencimiento) if lote.fecha_vencimiento else "—",
                    f"{lote.cantidad_disponible:.2f}",
                    estado,
                ])
                tags_lotes.append(tag)

            # Movimientos
            filas_movimientos = []
            from app.modelos import MovimientoInventario
            movimientos = (
                db.query(MovimientoInventario)
                .order_by(MovimientoInventario.fecha.desc())
                .limit(300)
                .all()
            )
            for i, m in enumerate(movimientos):
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

        self.tabla_stock.cargar_filas(filas_stock, tags_por_fila=tags_stock)
        self.tabla_lotes.cargar_filas(filas_lotes, tags_por_fila=tags_lotes)
        self.tabla_movimientos.cargar_filas(filas_movimientos)
        self.tabla_catalogo.cargar_filas(filas_catalogo)

    def _abrir_ajuste(self):
        lote_id = self.tabla_lotes.id_seleccionado()
        if not lote_id:
            messagebox.showwarning("Aviso", "Selecciona un lote de la lista primero.")
            return
        VentanaAjusteStock(self, lote_id, al_guardar=self.refrescar)

    def _abrir_nuevo_producto(self):
        VentanaProducto(self, al_guardar=self.refrescar)

    def _abrir_dialogo_reporte(self):
        from app.ui.dialogo_reporte import DialogoReporte
        DialogoReporte(self.winfo_toplevel(), modulo="stock")


# ══════════════════════════════════════════════════════════════════

class VentanaAjusteStock(tk.Toplevel):
    def __init__(self, parent, lote_id, al_guardar):
        super().__init__(parent)
        self.title("Ajustar cantidad de lote")
        self.resizable(False, False)
        self.grab_set()
        self.lote_id = lote_id
        self.al_guardar = al_guardar

        with nueva_sesion() as db:
            lote = db.get(LoteInventario, lote_id)
            texto_lote = f"{lote.numero_lote}  —  {lote.producto.nombre}"
            self.cantidad_actual = lote.cantidad_disponible

        franja = tk.Frame(self, bg=COLOR_PRIMARIO, pady=12, padx=20)
        franja.pack(fill="x")
        tk.Label(franja, text="⚖  Ajustar cantidad de lote",
                 bg=COLOR_PRIMARIO, fg="white",
                 font=("Segoe UI", 13, "bold")).pack(anchor="w")

        cuerpo = ttk.Frame(self, padding=(20, 16))
        cuerpo.pack(fill="both", expand=True)

        self._msg = MensajeEstado(cuerpo)
        self._msg.pack(fill="x", pady=(0, 8))

        ttk.Label(cuerpo, text=texto_lote,
                  font=("Segoe UI", 11, "bold")).pack(anchor="w")
        ttk.Label(cuerpo,
                  text=f"Cantidad disponible actual: {self.cantidad_actual:.2f}",
                  foreground=COLOR_TEXTO_SECUNDARIO).pack(anchor="w", pady=(2, 12))

        sec = SeccionFormulario(cuerpo, "Datos del ajuste")
        sec.pack(fill="x", pady=(0, 12))

        ttk.Label(sec, text="Nueva cantidad disponible *",
                  font=("Segoe UI", 9, "bold")).pack(anchor="w")
        self.var_nueva_cantidad = tk.StringVar(value=str(self.cantidad_actual))
        ttk.Entry(sec, textvariable=self.var_nueva_cantidad, width=20).pack(
            anchor="w", pady=(2, 8))

        ttk.Label(sec, text="Motivo del ajuste *",
                  font=("Segoe UI", 9, "bold")).pack(anchor="w")
        self.var_motivo = tk.StringVar()
        ttk.Entry(sec, textvariable=self.var_motivo, width=40).pack(
            anchor="w", pady=(2, 0))

        ttk.Label(cuerpo, text="* Campos obligatorios",
                  style="CampoAuto.TLabel").pack(anchor="w", pady=(4, 8))

        fila_btn = ttk.Frame(cuerpo)
        fila_btn.pack(fill="x")
        ttk.Button(fila_btn, text="Cancelar", style="Secundario.TButton",
                   command=self.destroy).pack(side="right", padx=(8, 0))
        ttk.Button(fila_btn, text="💾  Guardar ajuste",
                   command=self._guardar).pack(side="right")

        self.bind("<Escape>", lambda e: self.destroy())
        centrar_ventana(self, 420, 360)

    def _guardar(self):
        try:
            nueva_cantidad = float(self.var_nueva_cantidad.get())
            if nueva_cantidad < 0:
                raise ValueError
        except ValueError:
            self._msg.mostrar("La cantidad debe ser un número mayor o igual a 0.", "error")
            return
        if not self.var_motivo.get().strip():
            self._msg.mostrar("El motivo del ajuste es obligatorio.", "error")
            return

        with nueva_sesion() as db:
            try:
                ajustar_stock(db, self.lote_id, nueva_cantidad,
                               motivo=self.var_motivo.get().strip(),
                               usuario_id=sesion_actual.usuario_id)
                db.commit()
            except Exception as error:
                self._msg.mostrar(f"No se pudo guardar el ajuste: {error}", "error", 0)
                return

        self.al_guardar()
        self.destroy()


class VentanaProducto(tk.Toplevel):
    def __init__(self, parent, al_guardar):
        super().__init__(parent)
        self.title("Nuevo producto en el catálogo")
        self.resizable(False, False)
        self.grab_set()
        self.al_guardar = al_guardar

        franja = tk.Frame(self, bg=COLOR_PRIMARIO, pady=12, padx=20)
        franja.pack(fill="x")
        tk.Label(franja, text="＋  Registrar nuevo producto",
                 bg=COLOR_PRIMARIO, fg="white",
                 font=("Segoe UI", 13, "bold")).pack(anchor="w")

        cuerpo = ttk.Frame(self, padding=(20, 16))
        cuerpo.pack(fill="both", expand=True)

        self._msg = MensajeEstado(cuerpo)
        self._msg.pack(fill="x", pady=(0, 8))

        sec = SeccionFormulario(cuerpo, "Información del producto")
        sec.pack(fill="x", pady=(0, 8))
        sec.columnconfigure(1, weight=1)

        self.var_codigo       = tk.StringVar()
        self.var_nombre       = tk.StringVar()
        self.var_tipo         = tk.StringVar(value="Insumo")
        self.var_unidad       = tk.StringVar()
        self.var_precio       = tk.StringVar(value="0")
        self.var_stock_minimo = tk.StringVar(value="0")

        campos = [
            ("Código único *", self.var_codigo, None, "Ej: INS-014"),
            ("Nombre del producto *", self.var_nombre, None, ""),
            ("Tipo de producto", self.var_tipo, ["Insumo", "Producto terminado"], ""),
            ("Unidad de medida", self.var_unidad, None, "kg, L, g, unidad..."),
            ("Precio de venta (S/)", self.var_precio, None, "Solo para producto terminado"),
            ("Stock mínimo", self.var_stock_minimo, None, "Cantidad mínima para alerta"),
        ]

        for i, (etiqueta, var, opciones, hint) in enumerate(campos):
            negrita = "*" in etiqueta
            ttk.Label(sec, text=etiqueta,
                      font=("Segoe UI", 9, "bold") if negrita else ("Segoe UI", 9)
                      ).grid(row=i, column=0, sticky="w", padx=(0, 12), pady=3)
            if opciones:
                ttk.Combobox(sec, textvariable=var, state="readonly",
                              values=opciones, width=30
                              ).grid(row=i, column=1, sticky="ew", pady=3)
            else:
                f = ttk.Frame(sec)
                f.grid(row=i, column=1, sticky="ew", pady=3)
                f.columnconfigure(0, weight=1)
                ttk.Entry(f, textvariable=var, width=32).grid(row=0, column=0, sticky="w")
                if hint:
                    ttk.Label(f, text=hint,
                              style="CampoAuto.TLabel").grid(row=1, column=0, sticky="w")

        ttk.Label(cuerpo, text="* Campo obligatorio",
                  style="CampoAuto.TLabel").pack(anchor="w", pady=(4, 8))

        fila_btn = ttk.Frame(cuerpo)
        fila_btn.pack(fill="x")
        ttk.Button(fila_btn, text="Cancelar", style="Secundario.TButton",
                   command=self.destroy).pack(side="right", padx=(8, 0))
        ttk.Button(fila_btn, text="💾  Registrar producto",
                   command=self._guardar).pack(side="right")

        self.bind("<Escape>", lambda e: self.destroy())
        centrar_ventana(self, 460, 400)

    def _guardar(self):
        if not self.var_codigo.get().strip() or not self.var_nombre.get().strip():
            self._msg.mostrar("El código y el nombre son obligatorios.", "error")
            return
        try:
            precio = float(self.var_precio.get() or 0)
            stock_minimo = float(self.var_stock_minimo.get() or 0)
        except ValueError:
            self._msg.mostrar("El precio y el stock mínimo deben ser números válidos.", "error")
            return

        with nueva_sesion() as db:
            if db.query(Producto).filter_by(codigo=self.var_codigo.get().strip()).first():
                self._msg.mostrar(
                    "Ya existe un producto con ese código en el catálogo. "
                    "Usa un código diferente.", "error", 0)
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
