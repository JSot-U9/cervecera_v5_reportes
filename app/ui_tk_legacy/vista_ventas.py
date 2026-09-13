"""
vista_ventas.py
================
Módulo de Ventas — mejoras UX:
- Modelo mental de carrito de compra
- Total destacado visualmente
- Mensajes descriptivos
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
from app.ui.widgets import (
    EncabezadoModulo, BarraBusqueda, TablaDatos, ajustar_ventana_a_contenido,
    centrar_ventana, SeccionFormulario, MensajeEstado
)
from app.ui.estilos import COLOR_TEXTO_SECUNDARIO, COLOR_PRIMARIO, COLOR_EXITO


class VistaVentas(ttk.Frame):
    def __init__(self, parent):
        super().__init__(parent)
        self.tutorial_targets = {}
        EncabezadoModulo(
            self,
            "Ventas",
            "Registro de órdenes de venta · El inventario se descuenta automáticamente (FIFO)",
            icono="💰",
        ).pack(fill="x")

        self.notebook = ttk.Notebook(self)
        self.notebook.pack(fill="both", expand=True, padx=12, pady=8)
        notebook = self.notebook

        self._pestana_ordenes(notebook)
        self._pestana_clientes(notebook)

        self.refrescar()

    def _pestana_ordenes(self, notebook):
        pestana = ttk.Frame(notebook, padding=8)
        notebook.add(pestana, text="  🧾  Órdenes de Venta  ")

        puede_crear = puede(sesion_actual.rol, "ventas", "crear")
        barra = BarraBusqueda(pestana, al_escribir=lambda t: self.tabla_ventas.filtrar(t),
                               placeholder="🔎  Buscar orden, cliente...")
        if puede_crear:
            self.tutorial_targets["btn_nueva_venta"] = barra.agregar_boton(
                "＋  Nueva venta", self._abrir_nueva_venta)
        self.tutorial_targets["btn_reporte"] = barra.agregar_boton(
            "📊  Reporte", self._abrir_dialogo_reporte, estilo="AccionSecundaria.TButton")
        barra.pack(fill="x", pady=(0, 8))

        contenedor = ttk.Frame(pestana)
        contenedor.pack(fill="both", expand=True)
        self.tabla_ventas = TablaDatos(
            contenedor,
            ["N° Orden", "Cliente", "Fecha", "Total (S/)"],
            anchos={"N° Orden": 110, "Cliente": 220, "Fecha": 120, "Total (S/)": 130},
        )
        self.tabla_ventas.empaquetar()
        self.tutorial_targets["tabla_ventas"] = self.tabla_ventas

    def _pestana_clientes(self, notebook):
        pestana = ttk.Frame(notebook, padding=8)
        notebook.add(pestana, text="  👥  Clientes  ")

        puede_crear = puede(sesion_actual.rol, "ventas", "crear")
        barra = BarraBusqueda(pestana, al_escribir=lambda t: self.tabla_clientes.filtrar(t),
                               placeholder="🔎  Buscar cliente...")
        if puede_crear:
            barra.agregar_boton("＋  Nuevo cliente", self._abrir_nuevo_cliente)
        barra.pack(fill="x", pady=(0, 8))

        contenedor = ttk.Frame(pestana)
        contenedor.pack(fill="both", expand=True)
        self.tabla_clientes = TablaDatos(
            contenedor,
            ["Tipo", "Nombre / Razón Social", "N° Documento", "Teléfono"],
            anchos={"Tipo": 90, "Nombre / Razón Social": 220,
                    "N° Documento": 130, "Teléfono": 130},
        )
        self.tabla_clientes.empaquetar()
        self.tutorial_targets["tabla_clientes"] = self.tabla_clientes

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

    def _abrir_dialogo_reporte(self):
        from app.ui.dialogo_reporte import DialogoReporte
        DialogoReporte(self.winfo_toplevel(), modulo="ventas")


# ══════════════════════════════════════════════════════════════════

class VentanaCliente(tk.Toplevel):
    def __init__(self, parent, al_guardar):
        super().__init__(parent)
        self.title("Nuevo cliente")
        self.resizable(False, False)
        self.grab_set()
        self.al_guardar = al_guardar

        franja = tk.Frame(self, bg=COLOR_PRIMARIO, pady=12, padx=20)
        franja.pack(fill="x")
        tk.Label(franja, text="＋  Registrar nuevo cliente",
                 bg=COLOR_PRIMARIO, fg="white",
                 font=("Segoe UI", 13, "bold")).pack(anchor="w")

        cuerpo = ttk.Frame(self, padding=(20, 16))
        cuerpo.pack(fill="both", expand=True)

        self._msg = MensajeEstado(cuerpo)
        self._msg.pack(fill="x", pady=(0, 8))

        sec = SeccionFormulario(cuerpo, "Datos del cliente")
        sec.pack(fill="x", pady=(0, 10))
        sec.columnconfigure(1, weight=1)

        self.var_tipo      = tk.StringVar(value="NATURAL")
        self.var_nombre    = tk.StringVar()
        self.var_documento = tk.StringVar()
        self.var_telefono  = tk.StringVar()
        self.var_email     = tk.StringVar()

        campos = [
            ("Tipo de persona", self.var_tipo, ["NATURAL", "JURIDICA"]),
            ("Nombre / Razón social *", self.var_nombre, None),
            ("N° de documento (DNI o RUC)", self.var_documento, None),
            ("Teléfono", self.var_telefono, None),
            ("Correo electrónico", self.var_email, None),
        ]
        for i, (etiqueta, var, opciones) in enumerate(campos):
            negrita = "*" in etiqueta
            ttk.Label(sec, text=etiqueta,
                      font=("Segoe UI", 9, "bold") if negrita else ("Segoe UI", 9)
                      ).grid(row=i, column=0, sticky="w", padx=(0, 12), pady=4)
            if opciones:
                ttk.Combobox(sec, textvariable=var, state="readonly",
                              values=opciones, width=28
                              ).grid(row=i, column=1, sticky="ew", pady=4)
            else:
                ttk.Entry(sec, textvariable=var, width=30
                          ).grid(row=i, column=1, sticky="ew", pady=4)

        ttk.Label(cuerpo, text="* Campo obligatorio",
                  style="CampoAuto.TLabel").pack(anchor="w", pady=(0, 8))

        fila_btn = ttk.Frame(cuerpo)
        fila_btn.pack(fill="x")
        ttk.Button(fila_btn, text="Cancelar", style="Secundario.TButton",
                   command=self.destroy).pack(side="right", padx=(8, 0))
        ttk.Button(fila_btn, text="💾  Registrar cliente",
                   command=self._guardar).pack(side="right")

        self.bind("<Escape>", lambda e: self.destroy())
        centrar_ventana(self, 420, 360)

    def _guardar(self):
        if not self.var_nombre.get().strip():
            self._msg.mostrar("El nombre del cliente es obligatorio.", "error")
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
            self._msg.mostrar(f"No se pudo registrar el cliente: {error}", "error", 0)
            return
        self.al_guardar()
        self.destroy()


class VentanaNuevaVenta(tk.Toplevel):
    """Formulario de venta con modelo mental de carrito."""

    def __init__(self, parent, al_guardar):
        super().__init__(parent)
        self.title("Nueva venta")
        self.resizable(True, True)
        self.grab_set()
        self.al_guardar = al_guardar
        self.items_agregados = []

        with nueva_sesion() as db:
            self.clientes  = listar_clientes_activos(db)
            self.productos = db.query(Producto).filter_by(
                tipo="Producto terminado", activo=True).all()

        # Encabezado
        franja = tk.Frame(self, bg=COLOR_PRIMARIO, pady=12, padx=20)
        franja.pack(fill="x")
        tk.Label(franja, text="💰  Nueva venta",
                 bg=COLOR_PRIMARIO, fg="white",
                 font=("Segoe UI", 13, "bold")).pack(anchor="w")
        tk.Label(franja, text="Selecciona cliente, agrega productos y registra la venta",
                 bg=COLOR_PRIMARIO, fg="#D4A369",
                 font=("Segoe UI", 9)).pack(anchor="w")

        cuerpo = ttk.Frame(self, padding=(20, 12))
        cuerpo.pack(fill="both", expand=True)

        self._msg = MensajeEstado(cuerpo)
        self._msg.pack(fill="x", pady=(0, 8))

        # ── Cliente ────────────────────────────────────────────────
        sec_cli = SeccionFormulario(cuerpo, "Cliente")
        sec_cli.pack(fill="x", pady=(0, 10))
        ttk.Label(sec_cli, text="Cliente *",
                  font=("Segoe UI", 9, "bold")).pack(anchor="w")
        self.combo_cliente = ttk.Combobox(
            sec_cli, state="readonly",
            values=[f"{c.id} — {c.nombre}" for c in self.clientes],
            width=50)
        self.combo_cliente.pack(fill="x", pady=(2, 0))

        # ── Agregar producto ───────────────────────────────────────
        sec_prod = SeccionFormulario(cuerpo, "Agregar producto")
        sec_prod.pack(fill="x", pady=(0, 10))

        ttk.Label(sec_prod, text="Producto terminado *",
                  font=("Segoe UI", 9, "bold")).pack(anchor="w")
        self.combo_producto = ttk.Combobox(
            sec_prod, state="readonly", width=55,
            values=[f"{p.id} — {p.nombre} (S/ {p.precio_venta:.2f})" for p in self.productos])
        self.combo_producto.pack(fill="x", pady=(2, 8))
        self.combo_producto.bind("<<ComboboxSelected>>", self._autocompletar_precio)

        f_nums = ttk.Frame(sec_prod)
        f_nums.pack(fill="x")

        col_cant = ttk.Frame(f_nums)
        col_cant.pack(side="left", padx=(0, 16))
        ttk.Label(col_cant, text="Cantidad *",
                  font=("Segoe UI", 9, "bold")).pack(anchor="w")
        self.var_cantidad = tk.StringVar()
        ttk.Entry(col_cant, textvariable=self.var_cantidad, width=12).pack(pady=(2, 0))

        col_precio = ttk.Frame(f_nums)
        col_precio.pack(side="left", padx=(0, 16))
        ttk.Label(col_precio, text="Precio unitario (S/)",
                  font=("Segoe UI", 9, "bold")).pack(anchor="w")
        self.var_precio = tk.StringVar()
        ttk.Entry(col_precio, textvariable=self.var_precio, width=12).pack(pady=(2, 0))
        ttk.Label(col_precio, text="Autocompletado del catálogo",
                  style="CampoAuto.TLabel").pack(anchor="w")

        ttk.Button(sec_prod, text="＋  Agregar al carrito",
                   command=self._agregar_item).pack(anchor="w", pady=(8, 0))

        # ── Carrito / tabla ────────────────────────────────────────
        sec_carrito = SeccionFormulario(cuerpo, "Carrito de venta")
        sec_carrito.pack(fill="both", expand=True, pady=(0, 10))

        # Total destacado
        self.lbl_total = ttk.Label(sec_carrito, text="TOTAL:  S/ 0.00",
                                    font=("Segoe UI", 16, "bold"),
                                    foreground=COLOR_EXITO)
        self.lbl_total.pack(anchor="e", pady=(0, 6))

        contenedor_tabla = ttk.Frame(sec_carrito)
        contenedor_tabla.pack(fill="both", expand=True)
        self.tabla_items = TablaDatos(
            contenedor_tabla,
            ["Producto", "Cantidad", "Precio Unit. (S/)", "Subtotal (S/)"],
            con_id=False,
            anchos={"Producto": 200, "Cantidad": 80,
                    "Precio Unit. (S/)": 130, "Subtotal (S/)": 120},
        )
        self.tabla_items.empaquetar()

        # ── Botones ────────────────────────────────────────────────
        fila_btn = ttk.Frame(cuerpo)
        fila_btn.pack(fill="x")
        ttk.Label(fila_btn, text="* Campos obligatorios",
                  style="CampoAuto.TLabel").pack(side="left")
        ttk.Button(fila_btn, text="Cancelar", style="Secundario.TButton",
                   command=self.destroy).pack(side="right", padx=(8, 0))
        ttk.Button(fila_btn, text="💰  Registrar venta",
                   command=self._guardar_venta).pack(side="right")

        self.bind("<Escape>", lambda e: self.destroy())
        centrar_ventana(self, 720, 580)

    def _autocompletar_precio(self, evento=None):
        if not self.combo_producto.get():
            return
        producto_id = int(self.combo_producto.get().split(" — ")[0])
        for p in self.productos:
            if p.id == producto_id:
                self.var_precio.set(str(p.precio_venta))
                break

    def _agregar_item(self):
        if not self.combo_producto.get():
            self._msg.mostrar("Selecciona un producto antes de agregar.", "advertencia")
            return
        try:
            cantidad = float(self.var_cantidad.get())
            precio   = float(self.var_precio.get())
            if cantidad <= 0:
                raise ValueError("cantidad")
            if precio < 0:
                raise ValueError("precio")
        except ValueError:
            self._msg.mostrar(
                "La cantidad debe ser mayor que 0 y el precio debe ser un número válido.",
                "error")
            return

        producto_id = int(self.combo_producto.get().split(" — ")[0])
        self.items_agregados.append({
            "producto_id":    producto_id,
            "cantidad":       cantidad,
            "precio_unitario": precio,
        })
        self._msg.mostrar("Producto agregado al carrito.", "exito", 2000)
        self._refrescar_tabla_items()
        self.var_cantidad.set("")
        self.combo_producto.set("")
        self.var_precio.set("")

    def _refrescar_tabla_items(self):
        filas = []
        total = 0.0
        with nueva_sesion() as db:
            for item in self.items_agregados:
                producto = db.get(Producto, item["producto_id"])
                subtotal = item["cantidad"] * item["precio_unitario"]
                total += subtotal
                filas.append([
                    producto.nombre,
                    item["cantidad"],
                    f"S/ {item['precio_unitario']:.2f}",
                    f"S/ {subtotal:.2f}",
                ])
        self.tabla_items.cargar_filas(filas)
        self.lbl_total.config(text=f"TOTAL:  S/ {total:,.2f}")

    def _guardar_venta(self):
        if not self.combo_cliente.get():
            self._msg.mostrar("Selecciona un cliente para la venta.", "error")
            return
        if not self.items_agregados:
            self._msg.mostrar("Agrega al menos un producto al carrito antes de registrar.", "error")
            return

        total = sum(i["cantidad"] * i["precio_unitario"] for i in self.items_agregados)
        cliente_id = int(self.combo_cliente.get().split(" — ")[0])
        nombre_cliente = self.combo_cliente.get().split(" — ")[1]

        try:
            orden = registrar_venta(
                cliente_id=cliente_id,
                items=self.items_agregados,
                usuario_id=sesion_actual.usuario_id,
            )
        except StockInsuficiente as error:
            messagebox.showerror(
                "Stock insuficiente",
                f"No hay suficiente stock para completar la venta.\n\n"
                f"Detalle: {error}\n\n"
                f"Verifica el inventario antes de intentar nuevamente.")
            return
        except Exception as error:
            messagebox.showerror(
                "No se pudo registrar la venta",
                f"Ocurrió un error inesperado.\n\nDetalle: {error}")
            return

        messagebox.showinfo(
            "✓ Venta registrada correctamente",
            f"Venta {orden.numero} registrada.\n"
            f"Cliente: {nombre_cliente}\n"
            f"Productos: {len(self.items_agregados)}\n"
            f"Total: S/ {total:,.2f}\n\n"
            f"El stock fue descontado del inventario (FIFO).")
        self.al_guardar()
        self.destroy()
