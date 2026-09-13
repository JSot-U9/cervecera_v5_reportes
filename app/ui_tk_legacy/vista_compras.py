"""
vista_compras.py
=================
Módulo de Compras — mejoras UX:
- Encabezados simplificados
- Mensajes de éxito/error descriptivos
- Validación inline en formularios
- Estados visuales en tablas
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
from app.ui.widgets import (
    EncabezadoModulo, BarraBusqueda, TablaDatos, ajustar_ventana_a_contenido,
    centrar_ventana, SeccionFormulario, MensajeEstado
)
from app.ui.estilos import COLOR_TEXTO_SECUNDARIO, COLOR_PRIMARIO, COLOR_ALERTA


class VistaCompras(ttk.Frame):
    def __init__(self, parent):
        super().__init__(parent)
        # Referencia al último diálogo "Nueva orden" abierto: la usan
        # el tutorial y la práctica guiada para resaltar sus campos
        # reales sin duplicar este formulario.
        self.ultimo_dialogo_nueva_orden = None
        self.ultimo_dialogo_reporte = None
        self.tutorial_targets = {}

        EncabezadoModulo(
            self,
            "Compras",
            "Órdenes de compra a proveedores · El inventario se actualiza automáticamente",
            icono="🛒",
        ).pack(fill="x")

        self.notebook = ttk.Notebook(self)
        self.notebook.pack(fill="both", expand=True, padx=12, pady=8)
        notebook = self.notebook

        self._pestana_ordenes(notebook)
        self._pestana_proveedores(notebook)

        self.refrescar()

    def _pestana_ordenes(self, notebook):
        pestana = ttk.Frame(notebook, padding=8)
        notebook.add(pestana, text="  🧾  Órdenes de Compra  ")

        puede_crear = puede(sesion_actual.rol, "compras", "crear")
        barra = BarraBusqueda(pestana, al_escribir=lambda t: self.tabla_ordenes.filtrar(t),
                               placeholder="🔎  Buscar orden, proveedor...")
        if puede_crear:
            self.tutorial_targets["btn_nueva_orden"] = barra.agregar_boton(
                "＋  Nueva orden", self._abrir_nueva_orden)
        self.tutorial_targets["btn_reporte"] = barra.agregar_boton(
            "📊  Reporte", self._abrir_dialogo_reporte, estilo="AccionSecundaria.TButton")
        barra.pack(fill="x", pady=(0, 8))

        contenedor_tabla = ttk.Frame(pestana)
        contenedor_tabla.pack(fill="both", expand=True)
        self.tabla_ordenes = TablaDatos(
            contenedor_tabla,
            ["N° Orden", "Proveedor", "Fecha", "Doc. Referencia", "Total (S/)"],
            anchos={"N° Orden": 100, "Proveedor": 200, "Fecha": 110,
                    "Doc. Referencia": 140, "Total (S/)": 110},
        )
        self.tabla_ordenes.empaquetar()
        self.tutorial_targets["tabla_ordenes"] = self.tabla_ordenes

    def _pestana_proveedores(self, notebook):
        pestana = ttk.Frame(notebook, padding=8)
        notebook.add(pestana, text="  🏭  Proveedores  ")

        puede_crear = puede(sesion_actual.rol, "compras", "crear")
        barra = BarraBusqueda(pestana, al_escribir=lambda t: self.tabla_proveedores.filtrar(t),
                               placeholder="🔎  Buscar proveedor...")
        if puede_crear:
            barra.agregar_boton("＋  Nuevo proveedor", self._abrir_nuevo_proveedor)
            barra.agregar_boton("✏  Editar", self._abrir_editar_proveedor,
                                 estilo="AccionSecundaria.TButton")
        barra.pack(fill="x", pady=(0, 8))

        contenedor_tabla = ttk.Frame(pestana)
        contenedor_tabla.pack(fill="both", expand=True)
        self.tabla_proveedores = TablaDatos(
            contenedor_tabla,
            ["Razón Social", "RUC", "Contacto", "Teléfono", "Correo"],
            anchos={"Razón Social": 200, "RUC": 110, "Contacto": 150,
                    "Teléfono": 120, "Correo": 180},
        )
        self.tabla_proveedores.empaquetar()

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

    def _abrir_nueva_orden(self):
        self.ultimo_dialogo_nueva_orden = VentanaNuevaOrden(self, al_guardar=self.refrescar)
        return self.ultimo_dialogo_nueva_orden

    def abrir_nueva_orden_para_tutorial(self):
        """Usado por tutorial.py / tutorial_practice.py: abre el
        formulario real de Nueva orden (mismo camino que el botón) y
        devuelve el diálogo para poder resaltar sus campos."""
        if not puede(sesion_actual.rol, "compras", "crear"):
            return None
        return self._abrir_nueva_orden()

    def abrir_reporte_para_tutorial(self):
        """Usado por el tutorial de Reportes: abre el mismo diálogo
        real que el botón «📊 Reporte» de este módulo."""
        self._abrir_dialogo_reporte()
        return self.ultimo_dialogo_reporte

    def _abrir_nuevo_proveedor(self):
        VentanaProveedor(self, al_guardar=self.refrescar)

    def _abrir_editar_proveedor(self):
        proveedor_id = self.tabla_proveedores.id_seleccionado()
        if not proveedor_id:
            messagebox.showwarning("Aviso", "Selecciona un proveedor de la lista primero.")
            return
        with nueva_sesion() as db:
            from app.modelos import Proveedor
            p = db.get(Proveedor, proveedor_id)
            datos = {"razon_social": p.razon_social, "ruc": p.ruc or "",
                     "contacto": p.contacto or "", "telefono": p.telefono or "",
                     "email": p.email or ""}
        VentanaProveedor(self, al_guardar=self.refrescar,
                          proveedor_id=proveedor_id, datos=datos)

    def _abrir_dialogo_reporte(self):
        from app.ui.dialogo_reporte import DialogoReporte
        self.ultimo_dialogo_reporte = DialogoReporte(self.winfo_toplevel(), modulo="compras")
        return self.ultimo_dialogo_reporte


# ══════════════════════════════════════════════════════════════════
#  Formulario Proveedor
# ══════════════════════════════════════════════════════════════════

class VentanaProveedor(tk.Toplevel):
    """Crear o editar un proveedor con validación mejorada."""

    def __init__(self, parent, al_guardar, proveedor_id=None, datos=None):
        super().__init__(parent)
        self.title("Editar proveedor" if proveedor_id else "Nuevo proveedor")
        self.resizable(False, False)
        self.grab_set()
        self.al_guardar = al_guardar
        self.proveedor_id = proveedor_id
        datos = datos or {}

        # Encabezado
        franja = tk.Frame(self, bg=COLOR_PRIMARIO, pady=12, padx=20)
        franja.pack(fill="x")
        icono = "✏" if proveedor_id else "＋"
        tk.Label(franja, text=f"{icono}  {'Editar proveedor' if proveedor_id else 'Nuevo proveedor'}",
                 bg=COLOR_PRIMARIO, fg="white",
                 font=("Segoe UI", 13, "bold")).pack(anchor="w")

        cuerpo = ttk.Frame(self, padding=(20, 16))
        cuerpo.pack(fill="both", expand=True)

        self._msg = MensajeEstado(cuerpo)
        self._msg.pack(fill="x", pady=(0, 8))

        # Sección info
        sec = SeccionFormulario(cuerpo, "Información del proveedor")
        sec.pack(fill="x", pady=(0, 12))
        sec.columnconfigure(1, weight=1)

        campos = [
            ("Razón social *", "razon_social", True),
            ("RUC", "ruc", False),
            ("Persona de contacto", "contacto", False),
            ("Teléfono", "telefono", False),
            ("Correo electrónico", "email", False),
        ]
        self._vars = {}
        for i, (etiqueta, clave, obligatorio) in enumerate(campos):
            ttk.Label(sec, text=etiqueta,
                      font=("Segoe UI", 9, "bold") if obligatorio else ("Segoe UI", 9)
                      ).grid(row=i, column=0, sticky="w", padx=(0, 12), pady=4)
            var = tk.StringVar(value=datos.get(clave, ""))
            ttk.Entry(sec, textvariable=var, width=35).grid(row=i, column=1, sticky="ew", pady=4)
            self._vars[clave] = var

        # Nota campos obligatorios
        ttk.Label(cuerpo, text="* Campo obligatorio",
                  style="CampoAuto.TLabel").pack(anchor="w", pady=(0, 12))

        # Botones
        fila_btn = ttk.Frame(cuerpo)
        fila_btn.pack(fill="x")
        ttk.Button(fila_btn, text="Cancelar", style="Secundario.TButton",
                   command=self.destroy).pack(side="right", padx=(8, 0))
        ttk.Button(fila_btn, text="💾  Guardar proveedor",
                   command=self._guardar).pack(side="right")

        self.bind("<Escape>", lambda e: self.destroy())
        centrar_ventana(self, 430, 340)

    def _guardar(self):
        razon = self._vars["razon_social"].get().strip()
        if not razon:
            self._msg.mostrar("La razón social es obligatoria.", "error")
            return
        datos = dict(
            razon_social=razon,
            ruc=self._vars["ruc"].get().strip() or None,
            contacto=self._vars["contacto"].get().strip(),
            telefono=self._vars["telefono"].get().strip(),
            email=self._vars["email"].get().strip(),
        )
        try:
            if self.proveedor_id:
                actualizar_proveedor(self.proveedor_id, **datos)
            else:
                crear_proveedor(**datos)
        except Exception as error:
            self._msg.mostrar(f"No se pudo guardar el proveedor: {error}", "error", 0)
            return
        self.al_guardar()
        self.destroy()


# ══════════════════════════════════════════════════════════════════
#  Formulario Nueva Orden de Compra
# ══════════════════════════════════════════════════════════════════

class VentanaNuevaOrden(tk.Toplevel):
    """Formulario para armar y guardar una orden de compra con varios productos."""

    def __init__(self, parent, al_guardar):
        super().__init__(parent)
        self.title("Nueva orden de compra")
        self.resizable(True, True)
        self.grab_set()
        self.al_guardar = al_guardar
        self.items_agregados = []

        with nueva_sesion() as db:
            self.proveedores = listar_proveedores_activos(db)
            self.productos = db.query(Producto).filter_by(tipo="Insumo", activo=True).all()
            self._ultimos_precios = {}
            for p in self.productos:
                lote = (db.query(LoteInventario)
                        .filter_by(producto_id=p.id)
                        .order_by(LoteInventario.id.desc())
                        .first())
                if lote and lote.costo_unitario:
                    self._ultimos_precios[p.id] = lote.costo_unitario

        # Encabezado
        franja = tk.Frame(self, bg=COLOR_PRIMARIO, pady=12, padx=20)
        franja.pack(fill="x")
        tk.Label(franja, text="＋  Nueva orden de compra",
                 bg=COLOR_PRIMARIO, fg="white",
                 font=("Segoe UI", 13, "bold")).pack(anchor="w")
        tk.Label(franja, text="Selecciona proveedor, agrega productos y guarda la orden",
                 bg=COLOR_PRIMARIO, fg="#D4A369",
                 font=("Segoe UI", 9)).pack(anchor="w")

        cuerpo = ttk.Frame(self, padding=(20, 12))
        cuerpo.pack(fill="both", expand=True)

        self._msg = MensajeEstado(cuerpo)
        self._msg.pack(fill="x", pady=(0, 8))

        # ── Proveedor ──────────────────────────────────────────────
        sec_prov = SeccionFormulario(cuerpo, "Proveedor")
        sec_prov.pack(fill="x", pady=(0, 10))
        ttk.Label(sec_prov, text="Proveedor *",
                  font=("Segoe UI", 9, "bold")).pack(anchor="w")
        self.combo_proveedor = ttk.Combobox(
            sec_prov, state="readonly",
            values=[f"{p.id} — {p.razon_social}" for p in self.proveedores],
            width=50)
        self.combo_proveedor.pack(fill="x", pady=(2, 0))

        # ── Agregar producto ───────────────────────────────────────
        sec_prod = SeccionFormulario(cuerpo, "Agregar producto a la orden")
        sec_prod.pack(fill="x", pady=(0, 10))

        # Fila producto
        f_prod = ttk.Frame(sec_prod)
        f_prod.pack(fill="x", pady=(0, 6))
        ttk.Label(f_prod, text="Producto *",
                  font=("Segoe UI", 9, "bold")).pack(anchor="w")
        self.combo_producto = ttk.Combobox(
            f_prod, state="readonly", width=55,
            values=[f"{p.id} — {p.nombre}" for p in self.productos])
        self.combo_producto.pack(fill="x", pady=(2, 0))
        self.combo_producto.bind("<<ComboboxSelected>>", self._autocompletar_precio)

        # Fila cantidades
        f_nums = ttk.Frame(sec_prod)
        f_nums.pack(fill="x", pady=(0, 6))

        col_cant = ttk.Frame(f_nums)
        col_cant.pack(side="left", padx=(0, 16))
        ttk.Label(col_cant, text="Cantidad *",
                  font=("Segoe UI", 9, "bold")).pack(anchor="w")
        self.var_cantidad = tk.StringVar()
        self.entry_cantidad = ttk.Entry(col_cant, textvariable=self.var_cantidad, width=12)
        self.entry_cantidad.pack(pady=(2, 0))

        col_precio = ttk.Frame(f_nums)
        col_precio.pack(side="left", padx=(0, 16))
        ttk.Label(col_precio, text="Precio unitario (S/)",
                  font=("Segoe UI", 9, "bold")).pack(anchor="w")
        self.var_precio = tk.StringVar()
        ttk.Entry(col_precio, textvariable=self.var_precio, width=12).pack(pady=(2, 0))
        self.lbl_precio_hint = ttk.Label(col_precio, text="",
                                          foreground=COLOR_TEXTO_SECUNDARIO,
                                          font=("Segoe UI", 8, "italic"))
        self.lbl_precio_hint.pack(anchor="w")

        col_venc = ttk.Frame(f_nums)
        col_venc.pack(side="left")
        ttk.Label(col_venc, text="Vencimiento (AAAA-MM-DD)",
                  font=("Segoe UI", 9)).pack(anchor="w")
        self.var_fecha_vencimiento = tk.StringVar()
        ttk.Entry(col_venc, textvariable=self.var_fecha_vencimiento, width=14).pack(pady=(2, 0))
        ttk.Label(col_venc, text="Opcional",
                  style="CampoAuto.TLabel").pack(anchor="w")

        self.btn_agregar_item = ttk.Button(sec_prod, text="＋  Agregar a la orden",
                                            command=self._agregar_item)
        self.btn_agregar_item.pack(anchor="w", pady=(4, 0))

        # ── Tabla de items ─────────────────────────────────────────
        sec_tabla = SeccionFormulario(cuerpo, "Productos en esta orden")
        sec_tabla.pack(fill="both", expand=True, pady=(0, 10))

        self.lbl_total = ttk.Label(sec_tabla, text="Total: S/ 0.00",
                                    font=("Segoe UI", 14, "bold"),
                                    foreground=COLOR_PRIMARIO)
        self.lbl_total.pack(anchor="e", pady=(0, 4))

        contenedor_tabla = ttk.Frame(sec_tabla)
        contenedor_tabla.pack(fill="both", expand=True)
        self.tabla_items = TablaDatos(
            contenedor_tabla,
            ["Producto", "Cantidad", "Precio Unit. (S/)", "Vence", "Subtotal (S/)"],
            con_id=False,
            anchos={"Producto": 180, "Cantidad": 80, "Precio Unit. (S/)": 120,
                    "Vence": 110, "Subtotal (S/)": 110}
        )
        self.tabla_items.empaquetar()

        # ── Botones finales ────────────────────────────────────────
        fila_btn = ttk.Frame(cuerpo)
        fila_btn.pack(fill="x")
        ttk.Label(fila_btn, text="* Campos obligatorios",
                  style="CampoAuto.TLabel").pack(side="left")
        ttk.Button(fila_btn, text="Cancelar", style="Secundario.TButton",
                   command=self.destroy).pack(side="right", padx=(8, 0))
        self.btn_guardar = ttk.Button(fila_btn, text="💾  Guardar orden de compra",
                                       command=self._guardar_orden)
        self.btn_guardar.pack(side="right")

        self.bind("<Escape>", lambda e: self.destroy())
        centrar_ventana(self, 760, 620)

    def _autocompletar_precio(self, evento=None):
        if not self.combo_producto.get():
            return
        producto_id = int(self.combo_producto.get().split(" — ")[0])
        ultimo = self._ultimos_precios.get(producto_id)
        if ultimo:
            self.var_precio.set(f"{ultimo:.2f}")
            self.lbl_precio_hint.config(text="↑ último precio registrado")
        else:
            self.var_precio.set("")
            self.lbl_precio_hint.config(text="(sin compra previa)")

    def _agregar_item(self):
        if not self.combo_producto.get():
            self._msg.mostrar("Selecciona un producto antes de agregar.", "advertencia")
            return
        try:
            cantidad = float(self.var_cantidad.get())
            precio = float(self.var_precio.get())
            if cantidad <= 0:
                raise ValueError("cantidad negativa")
            if precio < 0:
                raise ValueError("precio negativo")
        except ValueError:
            self._msg.mostrar(
                "La cantidad debe ser mayor que 0 y el precio debe ser un número válido.",
                "error")
            return

        texto_fecha = self.var_fecha_vencimiento.get().strip()
        fecha_vencimiento = None
        if texto_fecha:
            try:
                fecha_vencimiento = datetime.strptime(texto_fecha, "%Y-%m-%d").date()
            except ValueError:
                self._msg.mostrar(
                    "Formato de fecha incorrecto. Usa AAAA-MM-DD (ej: 2027-06-30).",
                    "error")
                return

        producto_id = int(self.combo_producto.get().split(" — ")[0])
        self.items_agregados.append({
            "producto_id": producto_id, "cantidad": cantidad,
            "precio_unitario": precio, "fecha_vencimiento": fecha_vencimiento,
        })
        self._msg.mostrar("Producto agregado a la orden.", "exito", 2000)
        self._refrescar_tabla_items()
        self.var_cantidad.set("")
        self.var_precio.set("")
        self.var_fecha_vencimiento.set("")
        self.lbl_precio_hint.config(text="")
        self.combo_producto.set("")

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
                    str(item["fecha_vencimiento"]) if item["fecha_vencimiento"] else "—",
                    f"S/ {subtotal:.2f}",
                ])
        self.tabla_items.cargar_filas(filas)
        self.lbl_total.config(text=f"Total: S/ {total:,.2f}")

    def _guardar_orden(self):
        if not self.combo_proveedor.get():
            self._msg.mostrar("Selecciona un proveedor para la orden.", "error")
            return
        if not self.items_agregados:
            self._msg.mostrar("Agrega al menos un producto a la orden antes de guardar.", "error")
            return

        proveedor_id = int(self.combo_proveedor.get().split(" — ")[0])
        try:
            orden = registrar_compra(
                proveedor_id=proveedor_id,
                items=self.items_agregados,
                usuario_id=sesion_actual.usuario_id,
            )
        except Exception as error:
            messagebox.showerror(
                "No se pudo registrar la orden",
                f"Ocurrió un error al guardar la orden de compra.\n\n"
                f"Detalle: {error}\n\n"
                f"Verifica los datos e inténtalo nuevamente.")
            return

        messagebox.showinfo(
            "✓ Orden registrada correctamente",
            f"La orden {orden.numero} fue guardada.\n"
            f"Proveedor: {self.combo_proveedor.get().split(' — ')[1]}\n"
            f"Productos: {len(self.items_agregados)}\n"
            f"El stock del inventario fue actualizado."
        )
        self.al_guardar()
        self.destroy()
