"""
vista_compras.py
=================
Módulo de Compras: gestión de órdenes de compra y proveedores.

VentanaNuevaOrden permite armar una orden con VARIOS productos antes
de guardarla. Al seleccionar un producto, el precio unitario se
autocompleta con el último precio de compra registrado (si existe).
Solo al presionar "Guardar orden" se llama a logica_compras.registrar_compra().
"""

import tkinter as tk
from tkinter import ttk, messagebox
from datetime import datetime

from app.basedatos import nueva_sesion
from app.modelos import Producto, LoteInventario
from app.sesion import sesion_actual
from app.seguridad import puede
from app.logica_compras import (
    registrar_compra, listar_ordenes_compra, listar_proveedores_activos,
    crear_proveedor, actualizar_proveedor,
)
from app.ui.widgets import EncabezadoModulo, BarraBusqueda, TablaDatos, ajustar_ventana_a_contenido


class VistaCompras(ttk.Frame):
    def __init__(self, parent):
        super().__init__(parent)
        EncabezadoModulo(
            self,
            "Módulo de Compras",
            "Gestión de órdenes de compra a proveedores y registro de insumos al inventario",
        ).pack(fill="x")

        notebook = ttk.Notebook(self)
        notebook.pack(fill="both", expand=True, padx=12, pady=8)

        self._pestana_ordenes(notebook)
        self._pestana_proveedores(notebook)

        self.refrescar()

    # ── Pestaña: Órdenes de compra ──────────────────────────────
    def _pestana_ordenes(self, notebook):
        pestana = ttk.Frame(notebook, padding=8)
        notebook.add(pestana, text="Órdenes de Compra")

        puede_crear = puede(sesion_actual.rol, "compras", "crear")
        barra = BarraBusqueda(pestana, al_escribir=lambda t: self.tabla_ordenes.filtrar(t))
        if puede_crear:
            barra.agregar_boton("+ Nueva orden de compra", self._abrir_nueva_orden)
        barra.agregar_boton("📊  Generar reporte…", self._abrir_dialogo_reporte)
        barra.pack(fill="x", pady=(0, 8))

        contenedor_tabla = ttk.Frame(pestana)
        contenedor_tabla.pack(fill="both", expand=True)
        # con_id=True: el ID de la orden queda oculto como iid
        self.tabla_ordenes = TablaDatos(
            contenedor_tabla,
            ["N° Orden de Compra", "Proveedor", "Fecha de Compra", "Doc. Referencia",
             "Total (S/)"],
        )
        self.tabla_ordenes.empaquetar()

    # ── Pestaña: Proveedores ────────────────────────────────────
    def _pestana_proveedores(self, notebook):
        pestana = ttk.Frame(notebook, padding=8)
        notebook.add(pestana, text="Proveedores")

        puede_crear = puede(sesion_actual.rol, "compras", "crear")
        barra = BarraBusqueda(pestana, al_escribir=lambda t: self.tabla_proveedores.filtrar(t))
        if puede_crear:
            barra.agregar_boton("+ Nuevo proveedor", self._abrir_nuevo_proveedor)
            barra.agregar_boton("Editar proveedor", self._abrir_editar_proveedor)
        barra.pack(fill="x", pady=(0, 8))

        contenedor_tabla = ttk.Frame(pestana)
        contenedor_tabla.pack(fill="both", expand=True)
        self.tabla_proveedores = TablaDatos(
            contenedor_tabla,
            ["Razón Social", "RUC", "Persona de Contacto", "Teléfono", "Correo Electrónico"],
        )
        self.tabla_proveedores.empaquetar()

    # ── Refrescar datos ──────────────────────────────────────────
    def refrescar(self):
        with nueva_sesion() as db:
            filas_ordenes = [
                [o.id, o.numero, o.proveedor.razon_social, str(o.fecha),
                 o.documento_referencia or "—", f"S/ {o.total:,.2f}"]
                for o in listar_ordenes_compra(db)
            ]
            filas_proveedores = [
                [p.id, p.razon_social, p.ruc or "—", p.contacto or "—",
                 p.telefono or "—", p.email or "—"]
                for p in listar_proveedores_activos(db)
            ]
        self.tabla_ordenes.cargar_filas(filas_ordenes)
        self.tabla_proveedores.cargar_filas(filas_proveedores)

    # ── Acciones ─────────────────────────────────────────────────
    def _abrir_nueva_orden(self):
        VentanaNuevaOrden(self, al_guardar=self.refrescar)

    def _abrir_nuevo_proveedor(self):
        VentanaProveedor(self, al_guardar=self.refrescar)

    def _abrir_editar_proveedor(self):
        proveedor_id = self.tabla_proveedores.id_seleccionado()
        if not proveedor_id:
            messagebox.showwarning("Aviso", "Selecciona un proveedor de la lista.")
            return
        with nueva_sesion() as db:
            from app.modelos import Proveedor
            p = db.get(Proveedor, proveedor_id)
            datos = {"razon_social": p.razon_social, "ruc": p.ruc or "",
                     "contacto": p.contacto or "", "telefono": p.telefono or "",
                     "email": p.email or ""}
        VentanaProveedor(self, al_guardar=self.refrescar, proveedor_id=proveedor_id, datos=datos)


    def _abrir_dialogo_reporte(self):
        from app.ui.dialogo_reporte import DialogoReporte
        DialogoReporte(self.winfo_toplevel(), modulo="compras")

class VentanaProveedor(tk.Toplevel):
    """Formulario para crear o editar un proveedor."""

    def __init__(self, parent, al_guardar, proveedor_id=None, datos=None):
        super().__init__(parent)
        self.title("Editar proveedor" if proveedor_id else "Nuevo proveedor")
        self.al_guardar = al_guardar
        self.proveedor_id = proveedor_id
        datos = datos or {}

        campos = ttk.Frame(self, padding=16)
        campos.pack(fill="both", expand=True)

        self.var_razon_social = tk.StringVar(value=datos.get("razon_social", ""))
        self.var_ruc          = tk.StringVar(value=datos.get("ruc", ""))
        self.var_contacto     = tk.StringVar(value=datos.get("contacto", ""))
        self.var_telefono     = tk.StringVar(value=datos.get("telefono", ""))
        self.var_email        = tk.StringVar(value=datos.get("email", ""))

        for etiqueta, variable in [
            ("Razón social o nombre del proveedor:", self.var_razon_social),
            ("RUC (número de identificación tributaria):", self.var_ruc),
            ("Persona de contacto:", self.var_contacto),
            ("Teléfono de contacto:", self.var_telefono),
            ("Correo electrónico:", self.var_email),
        ]:
            ttk.Label(campos, text=etiqueta).pack(anchor="w")
            ttk.Entry(campos, textvariable=variable).pack(fill="x", pady=(0, 8))

        ttk.Button(campos, text="Guardar proveedor", command=self._guardar).pack(fill="x", pady=(8, 0))

        ajustar_ventana_a_contenido(self, ancho=390)

    def _guardar(self):
        if not self.var_razon_social.get().strip():
            messagebox.showwarning("Aviso", "La razón social es obligatoria.")
            return
        datos = dict(
            razon_social=self.var_razon_social.get().strip(),
            ruc=self.var_ruc.get().strip() or None,
            contacto=self.var_contacto.get().strip(),
            telefono=self.var_telefono.get().strip(),
            email=self.var_email.get().strip(),
        )
        try:
            if self.proveedor_id:
                actualizar_proveedor(self.proveedor_id, **datos)
            else:
                crear_proveedor(**datos)
        except Exception as error:
            messagebox.showerror("Error", str(error))
            return
        self.al_guardar()
        self.destroy()


class VentanaNuevaOrden(tk.Toplevel):
    """Formulario para armar y guardar una orden de compra con varios productos."""

    def __init__(self, parent, al_guardar):
        super().__init__(parent)
        self.title("Nueva orden de compra")
        self.al_guardar = al_guardar
        self.items_agregados = []

        with nueva_sesion() as db:
            self.proveedores = listar_proveedores_activos(db)
            self.productos = db.query(Producto).filter_by(tipo="Insumo", activo=True).all()
            # Pre-cargar último precio de compra por producto (desde lotes)
            self._ultimos_precios = {}
            for p in self.productos:
                lote = (db.query(LoteInventario)
                        .filter_by(producto_id=p.id)
                        .order_by(LoteInventario.id.desc())
                        .first())
                if lote and lote.costo_unitario:
                    self._ultimos_precios[p.id] = lote.costo_unitario

        contenedor = ttk.Frame(self, padding=16)
        contenedor.pack(fill="both", expand=True)

        # ── Selección de proveedor ──────────────────────────────
        ttk.Label(contenedor, text="Proveedor:").pack(anchor="w")
        self.combo_proveedor = ttk.Combobox(
            contenedor, state="readonly",
            values=[f"{p.id} — {p.razon_social}" for p in self.proveedores])
        self.combo_proveedor.pack(fill="x", pady=(0, 12))

        # ── Formulario para agregar un producto a la lista ──────
        sep = ttk.LabelFrame(contenedor, text="Agregar producto a la orden", padding=8)
        sep.pack(fill="x", pady=(0, 8))

        fila_producto = ttk.Frame(sep)
        fila_producto.pack(fill="x", pady=(0, 4))
        ttk.Label(fila_producto, text="Producto (insumo):").pack(side="left")
        self.combo_producto = ttk.Combobox(
            fila_producto, state="readonly", width=34,
            values=[f"{p.id} — {p.nombre}" for p in self.productos])
        self.combo_producto.pack(side="left", padx=6)
        self.combo_producto.bind("<<ComboboxSelected>>", self._autocompletar_precio)

        fila_nums = ttk.Frame(sep)
        fila_nums.pack(fill="x", pady=(0, 4))
        ttk.Label(fila_nums, text="Cantidad:").pack(side="left")
        self.var_cantidad = tk.StringVar()
        ttk.Entry(fila_nums, textvariable=self.var_cantidad, width=10).pack(side="left", padx=6)

        ttk.Label(fila_nums, text="Precio unitario (S/):").pack(side="left", padx=(14, 0))
        self.var_precio = tk.StringVar()
        self.entry_precio = ttk.Entry(fila_nums, textvariable=self.var_precio, width=10)
        self.entry_precio.pack(side="left", padx=6)
        self.lbl_precio_hint = ttk.Label(fila_nums, text="", foreground="#636B3F",
                                          font=("Segoe UI", 8))
        self.lbl_precio_hint.pack(side="left", padx=(4, 0))

        fila_venc = ttk.Frame(sep)
        fila_venc.pack(fill="x", pady=(0, 4))
        ttk.Label(fila_venc, text="Fecha de vencimiento (AAAA-MM-DD, opcional):").pack(side="left")
        self.var_fecha_vencimiento = tk.StringVar()
        ttk.Entry(fila_venc, textvariable=self.var_fecha_vencimiento, width=14).pack(
            side="left", padx=6)
        ttk.Button(fila_venc, text="+ Agregar a la orden",
                   command=self._agregar_item).pack(side="left", padx=12)

        # ── Tabla con los productos ya agregados ─────────────────
        ttk.Label(contenedor, text="Productos en esta orden de compra:").pack(
            anchor="w", pady=(10, 2))
        contenedor_tabla = ttk.Frame(contenedor)
        contenedor_tabla.pack(fill="both", expand=True)
        self.tabla_items = TablaDatos(
            contenedor_tabla,
            ["Nombre del Producto", "Cantidad", "Precio Unitario (S/)", "Vence", "Subtotal (S/)"],
            con_id=False,
        )
        self.tabla_items.empaquetar()

        ttk.Button(contenedor, text="Guardar orden de compra completa",
                   command=self._guardar_orden).pack(fill="x", pady=(10, 0))

        ajustar_ventana_a_contenido(self, ancho=720)

    def _autocompletar_precio(self, evento=None):
        """Rellena el precio unitario con el último precio de compra del producto."""
        if not self.combo_producto.get():
            return
        producto_id = int(self.combo_producto.get().split(" — ")[0])
        ultimo = self._ultimos_precios.get(producto_id)
        if ultimo:
            self.var_precio.set(f"{ultimo:.2f}")
            self.lbl_precio_hint.config(text=f"↑ último precio registrado")
        else:
            self.var_precio.set("")
            self.lbl_precio_hint.config(text="(sin compra previa)")

    def _agregar_item(self):
        if not self.combo_producto.get():
            messagebox.showwarning("Aviso", "Selecciona un producto.")
            return
        try:
            cantidad = float(self.var_cantidad.get())
            precio = float(self.var_precio.get())
            if cantidad <= 0 or precio < 0:
                raise ValueError
        except ValueError:
            messagebox.showwarning("Aviso",
                                    "La cantidad y el precio deben ser números válidos y positivos.")
            return

        texto_fecha = self.var_fecha_vencimiento.get().strip()
        fecha_vencimiento = None
        if texto_fecha:
            try:
                fecha_vencimiento = datetime.strptime(texto_fecha, "%Y-%m-%d").date()
            except ValueError:
                messagebox.showwarning(
                    "Aviso",
                    "La fecha de vencimiento debe tener el formato AAAA-MM-DD "
                    "(por ejemplo: 2027-06-30).")
                return

        producto_id = int(self.combo_producto.get().split(" — ")[0])
        self.items_agregados.append({
            "producto_id": producto_id, "cantidad": cantidad,
            "precio_unitario": precio, "fecha_vencimiento": fecha_vencimiento,
        })
        self._refrescar_tabla_items()
        self.var_cantidad.set("")
        self.var_precio.set("")
        self.var_fecha_vencimiento.set("")
        self.lbl_precio_hint.config(text="")

    def _refrescar_tabla_items(self):
        filas = []
        with nueva_sesion() as db:
            for item in self.items_agregados:
                producto = db.get(Producto, item["producto_id"])
                subtotal = item["cantidad"] * item["precio_unitario"]
                filas.append([
                    producto.nombre,
                    item["cantidad"],
                    f"S/ {item['precio_unitario']:.2f}",
                    str(item["fecha_vencimiento"]) if item["fecha_vencimiento"] else "—",
                    f"S/ {subtotal:.2f}",
                ])
        self.tabla_items.cargar_filas(filas)

    def _guardar_orden(self):
        if not self.combo_proveedor.get():
            messagebox.showwarning("Aviso", "Selecciona un proveedor.")
            return
        if not self.items_agregados:
            messagebox.showwarning("Aviso", "Agrega al menos un producto a la orden.")
            return

        proveedor_id = int(self.combo_proveedor.get().split(" — ")[0])
        try:
            orden = registrar_compra(
                proveedor_id=proveedor_id,
                items=self.items_agregados,
                usuario_id=sesion_actual.usuario_id,
            )
            messagebox.showinfo(
                "Orden registrada",
                f"Orden {orden.numero} guardada correctamente.\n"
                f"El stock del inventario fue actualizado.")
        except Exception as error:
            messagebox.showerror("Error al guardar", str(error))
            return

        self.al_guardar()
        self.destroy()