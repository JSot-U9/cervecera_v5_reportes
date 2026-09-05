"""
vista_ventas.py
================
Módulo de Ventas: registro de ventas y gestión de clientes.

Al seleccionar un producto terminado en VentanaNuevaVenta, el precio
unitario se autocompleta con el precio de venta del catálogo.
"""

import tkinter as tk
from tkinter import ttk, messagebox

from app.basedatos import nueva_sesion
from app.modelos import Producto
from app.sesion import sesion_actual
from app.seguridad import puede
from app.logica_ventas import (
    registrar_venta, listar_ordenes_venta, listar_clientes_activos, crear_cliente,
)
from app.logica_inventario import StockInsuficiente
from app.ui.widgets import EncabezadoModulo, BarraBusqueda, TablaDatos, ajustar_ventana_a_contenido


class VistaVentas(ttk.Frame):
    def __init__(self, parent):
        super().__init__(parent)
        EncabezadoModulo(
            self,
            "Módulo de Ventas",
            "Registro de órdenes de venta y gestión de clientes — el inventario se descuenta automáticamente (FIFO)",
        ).pack(fill="x")

        notebook = ttk.Notebook(self)
        notebook.pack(fill="both", expand=True, padx=12, pady=8)

        self._pestana_ordenes(notebook)
        self._pestana_clientes(notebook)

        self.refrescar()

    def _pestana_ordenes(self, notebook):
        pestana = ttk.Frame(notebook, padding=8)
        notebook.add(pestana, text="Órdenes de Venta")

        puede_crear = puede(sesion_actual.rol, "ventas", "crear")
        barra = BarraBusqueda(pestana, al_escribir=lambda t: self.tabla_ventas.filtrar(t))
        if puede_crear:
            barra.agregar_boton("+ Nueva venta", self._abrir_nueva_venta)
        barra.pack(fill="x", pady=(0, 8))

        contenedor = ttk.Frame(pestana)
        contenedor.pack(fill="both", expand=True)
        self.tabla_ventas = TablaDatos(
            contenedor,
            ["N° Orden de Venta", "Cliente", "Fecha de Venta", "Total (S/)"],
        )
        self.tabla_ventas.empaquetar()

    def _pestana_clientes(self, notebook):
        pestana = ttk.Frame(notebook, padding=8)
        notebook.add(pestana, text="Clientes")

        puede_crear = puede(sesion_actual.rol, "ventas", "crear")
        barra = BarraBusqueda(pestana, al_escribir=lambda t: self.tabla_clientes.filtrar(t))
        if puede_crear:
            barra.agregar_boton("+ Nuevo cliente", self._abrir_nuevo_cliente)
        barra.pack(fill="x", pady=(0, 8))

        contenedor = ttk.Frame(pestana)
        contenedor.pack(fill="both", expand=True)
        self.tabla_clientes = TablaDatos(
            contenedor,
            ["Tipo de Cliente", "Nombre / Razón Social", "N° de Documento", "Teléfono"],
        )
        self.tabla_clientes.empaquetar()

    def refrescar(self):
        with nueva_sesion() as db:
            filas_ventas = [
                [o.id, o.numero, o.cliente.nombre, str(o.fecha), f"S/ {o.total:,.2f}"]
                for o in listar_ordenes_venta(db)
            ]
            filas_clientes = [
                [c.id, c.tipo, c.nombre, c.documento or "—", c.telefono or "—"]
                for c in listar_clientes_activos(db)
            ]
        self.tabla_ventas.cargar_filas(filas_ventas)
        self.tabla_clientes.cargar_filas(filas_clientes)

    def _abrir_nueva_venta(self):
        VentanaNuevaVenta(self, al_guardar=self.refrescar)

    def _abrir_nuevo_cliente(self):
        VentanaCliente(self, al_guardar=self.refrescar)


class VentanaCliente(tk.Toplevel):
    def __init__(self, parent, al_guardar):
        super().__init__(parent)
        self.title("Registrar nuevo cliente")
        self.al_guardar = al_guardar

        contenedor = ttk.Frame(self, padding=16)
        contenedor.pack(fill="both", expand=True)

        self.var_tipo      = tk.StringVar(value="NATURAL")
        self.var_nombre    = tk.StringVar()
        self.var_documento = tk.StringVar()
        self.var_telefono  = tk.StringVar()
        self.var_email     = tk.StringVar()

        ttk.Label(contenedor, text="Tipo de persona:").pack(anchor="w")
        ttk.Combobox(contenedor, textvariable=self.var_tipo, state="readonly",
                     values=["NATURAL", "JURIDICA"]).pack(fill="x", pady=(0, 8))

        for etiqueta, variable in [
            ("Nombre completo o razón social:", self.var_nombre),
            ("Número de documento (DNI o RUC):", self.var_documento),
            ("Teléfono de contacto:", self.var_telefono),
            ("Correo electrónico:", self.var_email),
        ]:
            ttk.Label(contenedor, text=etiqueta).pack(anchor="w")
            ttk.Entry(contenedor, textvariable=variable).pack(fill="x", pady=(0, 8))

        ttk.Button(contenedor, text="Registrar cliente",
                   command=self._guardar).pack(fill="x", pady=(6, 0))

        ajustar_ventana_a_contenido(self, ancho=360)

    def _guardar(self):
        if not self.var_nombre.get().strip():
            messagebox.showwarning("Aviso", "El nombre del cliente es obligatorio.")
            return
        try:
            crear_cliente(
                tipo=self.var_tipo.get(),
                nombre=self.var_nombre.get().strip(),
                documento=self.var_documento.get().strip(),
                telefono=self.var_telefono.get().strip(),
                email=self.var_email.get().strip(),
            )
        except Exception as error:
            messagebox.showerror("Error", str(error))
            return
        self.al_guardar()
        self.destroy()


class VentanaNuevaVenta(tk.Toplevel):
    def __init__(self, parent, al_guardar):
        super().__init__(parent)
        self.title("Registrar nueva venta")
        self.al_guardar = al_guardar
        self.items_agregados = []

        with nueva_sesion() as db:
            self.clientes  = listar_clientes_activos(db)
            self.productos = db.query(Producto).filter_by(
                tipo="Producto terminado", activo=True).all()

        contenedor = ttk.Frame(self, padding=16)
        contenedor.pack(fill="both", expand=True)

        ttk.Label(contenedor, text="Cliente:").pack(anchor="w")
        self.combo_cliente = ttk.Combobox(
            contenedor, state="readonly",
            values=[f"{c.id} — {c.nombre}" for c in self.clientes])
        self.combo_cliente.pack(fill="x", pady=(0, 12))

        # ── Agregar productos a la venta ─────────────────────────
        sep = ttk.LabelFrame(contenedor, text="Agregar producto a la venta", padding=8)
        sep.pack(fill="x", pady=(0, 8))

        fila_producto = ttk.Frame(sep)
        fila_producto.pack(fill="x", pady=(0, 4))
        ttk.Label(fila_producto, text="Producto terminado:").pack(side="left")
        self.combo_producto = ttk.Combobox(
            fila_producto, state="readonly", width=34,
            values=[f"{p.id} — {p.nombre} (S/ {p.precio_venta:.2f})" for p in self.productos])
        self.combo_producto.pack(side="left", padx=6)
        self.combo_producto.bind("<<ComboboxSelected>>", self._autocompletar_precio)

        fila_nums = ttk.Frame(sep)
        fila_nums.pack(fill="x", pady=(0, 4))
        ttk.Label(fila_nums, text="Cantidad:").pack(side="left")
        self.var_cantidad = tk.StringVar()
        ttk.Entry(fila_nums, textvariable=self.var_cantidad, width=10).pack(
            side="left", padx=6)
        ttk.Label(fila_nums, text="Precio unitario de venta (S/):").pack(
            side="left", padx=(14, 0))
        self.var_precio = tk.StringVar()
        ttk.Entry(fila_nums, textvariable=self.var_precio, width=10).pack(side="left", padx=6)
        ttk.Button(fila_nums, text="+ Agregar a la venta",
                   command=self._agregar_item).pack(side="left", padx=10)

        # ── Tabla de items en la venta ───────────────────────────
        ttk.Label(contenedor, text="Productos en esta venta:").pack(anchor="w", pady=(10, 2))
        contenedor_tabla = ttk.Frame(contenedor)
        contenedor_tabla.pack(fill="both", expand=True)
        self.tabla_items = TablaDatos(
            contenedor_tabla,
            ["Nombre del Producto", "Cantidad", "Precio Unitario (S/)", "Subtotal (S/)"],
            con_id=False,
        )
        self.tabla_items.empaquetar()

        ttk.Button(contenedor, text="Registrar venta y descontar del inventario",
                   command=self._guardar_venta).pack(fill="x", pady=(10, 0))

        ajustar_ventana_a_contenido(self, ancho=700)

    def _autocompletar_precio(self, evento=None):
        """Autocompleta el precio con el precio de venta del catálogo del producto."""
        if not self.combo_producto.get():
            return
        producto_id = int(self.combo_producto.get().split(" — ")[0])
        for p in self.productos:
            if p.id == producto_id:
                self.var_precio.set(str(p.precio_venta))
                break

    def _agregar_item(self):
        if not self.combo_producto.get():
            messagebox.showwarning("Aviso", "Selecciona un producto.")
            return
        try:
            cantidad = float(self.var_cantidad.get())
            precio   = float(self.var_precio.get())
            if cantidad <= 0 or precio < 0:
                raise ValueError
        except ValueError:
            messagebox.showwarning("Aviso",
                                    "La cantidad y el precio deben ser números válidos y positivos.")
            return

        producto_id = int(self.combo_producto.get().split(" — ")[0])
        self.items_agregados.append({
            "producto_id": producto_id,
            "cantidad":    cantidad,
            "precio_unitario": precio,
        })
        self._refrescar_tabla_items()
        self.var_cantidad.set("")

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
                    f"S/ {subtotal:.2f}",
                ])
        self.tabla_items.cargar_filas(filas)

    def _guardar_venta(self):
        if not self.combo_cliente.get():
            messagebox.showwarning("Aviso", "Selecciona un cliente.")
            return
        if not self.items_agregados:
            messagebox.showwarning("Aviso", "Agrega al menos un producto a la venta.")
            return

        cliente_id = int(self.combo_cliente.get().split(" — ")[0])
        try:
            orden = registrar_venta(
                cliente_id=cliente_id,
                items=self.items_agregados,
                usuario_id=sesion_actual.usuario_id,
            )
            messagebox.showinfo(
                "Venta registrada",
                f"Venta {orden.numero} registrada correctamente.\n"
                f"El stock fue descontado del inventario (FIFO).")
        except StockInsuficiente as error:
            messagebox.showerror("Stock insuficiente", str(error))
            return
        except Exception as error:
            messagebox.showerror("Error", str(error))
            return

        self.al_guardar()
        self.destroy()