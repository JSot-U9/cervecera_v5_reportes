"""
vista_produccion.py
====================
Módulo de Producción — mejoras UX:
- Estados visuales con colores
- Formularios con secciones y validación mejorada
- Mensajes descriptivos de éxito/error
"""

import tkinter as tk
from tkinter import ttk, messagebox
from datetime import date

from app.basedatos import nueva_sesion
from app.modelos import OrdenProduccion, LoteInventario
from app.sesion import sesion_actual
from app.seguridad import puede
from app.logica_produccion import (
    crear_orden, iniciar_proceso, cerrar_orden, listar_ordenes, listar_recetas_activas,
)
from app.ui.widgets import (
    EncabezadoModulo, BarraBusqueda, TablaDatos, ajustar_ventana_a_contenido,
    centrar_ventana, SeccionFormulario, MensajeEstado, formatear_estado
)
from app.ui.estilos import COLOR_TEXTO_SECUNDARIO, COLOR_PRIMARIO, COLOR_ADVERTENCIA

ESTADOS_QUE_SE_PUEDEN_CERRAR = ("INICIADA", "EN_PROCESO")


class VistaProduccion(ttk.Frame):
    def __init__(self, parent):
        super().__init__(parent)
        self.tutorial_targets = {}
        EncabezadoModulo(
            self,
            "Producción",
            "Planificación, seguimiento y cierre de órdenes de elaboración de cerveza",
            icono="🍺",
        ).pack(fill="x")

        cuerpo = ttk.Frame(self, padding=12)
        cuerpo.pack(fill="both", expand=True)

        puede_crear  = puede(sesion_actual.rol, "produccion", "crear")
        puede_iniciar = puede(sesion_actual.rol, "produccion", "iniciar")
        puede_cerrar  = puede(sesion_actual.rol, "produccion", "cerrar")

        barra = BarraBusqueda(cuerpo, al_escribir=lambda t: self.tabla.filtrar(t),
                               placeholder="🔎  Buscar orden, lote, producto...")
        if puede_crear:
            self.tutorial_targets["btn_nueva_orden"] = barra.agregar_boton(
                "＋  Nueva orden", self._abrir_nueva_orden)
        if puede_iniciar:
            self.tutorial_targets["btn_iniciar"] = barra.agregar_boton(
                "▶  Iniciar", self._iniciar, estilo="AccionSecundaria.TButton")
        if puede_cerrar:
            self.tutorial_targets["btn_cerrar"] = barra.agregar_boton(
                "✔  Cerrar orden", self._abrir_cerrar_orden, estilo="AccionSecundaria.TButton")
        self.tutorial_targets["btn_reporte"] = barra.agregar_boton(
            "📊  Reporte", self._abrir_dialogo_reporte, estilo="AccionSecundaria.TButton")
        from app.ui.tutorial_overlay import boton_ayuda_contextual
        from app.ui.tutorial_data import AYUDA_CONTEXTUAL
        titulo_prod, texto_prod = AYUDA_CONTEXTUAL["produccion"]
        boton_ayuda_contextual(barra, titulo_prod, texto_prod, side="left", padx=4)
        barra.pack(fill="x", pady=(0, 8))

        contenedor_tabla = ttk.Frame(cuerpo)
        contenedor_tabla.pack(fill="both", expand=True)
        self.tabla = TablaDatos(
            contenedor_tabla,
            ["N° Orden", "Producto", "N° Lote", "Cant. Planeada", "Cant. Real", "Estado"],
            anchos={"N° Orden": 110, "Producto": 180, "N° Lote": 130,
                    "Cant. Planeada": 110, "Cant. Real": 100, "Estado": 130},
        )
        self.tabla.empaquetar()
        self.tutorial_targets["tabla_ordenes"] = self.tabla

        self.refrescar()

    def refrescar(self):
        with nueva_sesion() as db:
            filas = []
            tags = []
            for orden in listar_ordenes(db):
                producto = (orden.receta.producto_terminado.nombre
                            if orden.receta else "—")
                estado_visual = formatear_estado(orden.estado)
                tag = {
                    "INICIADA":   "advertencia",
                    "EN_PROCESO": "advertencia",
                    "COMPLETADA": "exito",
                    "CANCELADA":  "alerta",
                }.get(orden.estado, "normal")
                filas.append([
                    orden.id,
                    orden.numero,
                    producto,
                    orden.numero_lote,
                    f"{orden.cantidad_planeada:.1f}",
                    f"{orden.cantidad_real:.1f}" if orden.cantidad_real else "—",
                    estado_visual,
                ])
                tags.append(tag)
        self.tabla.cargar_filas(filas, tags_por_fila=tags)

    def _abrir_nueva_orden(self):
        VentanaNuevaOrdenProduccion(self, al_guardar=self.refrescar)

    def _iniciar(self):
        orden_id = self.tabla.id_seleccionado()
        if not orden_id:
            messagebox.showwarning("Aviso", "Selecciona una orden de la lista primero.")
            return
        try:
            iniciar_proceso(orden_id)
        except Exception as error:
            messagebox.showerror("No se pudo iniciar",
                                  f"No fue posible iniciar el proceso.\n\nDetalle: {error}")
            return
        self.refrescar()

    def _abrir_cerrar_orden(self):
        orden_id = self.tabla.id_seleccionado()
        if not orden_id:
            messagebox.showwarning("Aviso", "Selecciona una orden de la lista primero.")
            return

        with nueva_sesion() as db:
            orden = db.get(OrdenProduccion, orden_id)
        if not orden or orden.estado not in ESTADOS_QUE_SE_PUEDEN_CERRAR:
            estado_actual = orden.estado if orden else "desconocido"
            messagebox.showerror(
                "No se puede cerrar",
                f"La orden está en estado '{estado_actual}'.\n\n"
                f"Solo se pueden cerrar órdenes en estado INICIADA o EN_PROCESO.")
            return

        VentanaCerrarOrden(self, orden_id, al_guardar=self.refrescar)

    def _abrir_dialogo_reporte(self):
        from app.ui.dialogo_reporte import DialogoReporte
        DialogoReporte(self.winfo_toplevel(), modulo="produccion")


# ══════════════════════════════════════════════════════════════════

class VentanaNuevaOrdenProduccion(tk.Toplevel):
    def __init__(self, parent, al_guardar):
        super().__init__(parent)
        self.title("Nueva orden de producción")
        self.resizable(False, False)
        self.grab_set()
        self.al_guardar = al_guardar

        with nueva_sesion() as db:
            self.recetas = listar_recetas_activas(db)
            self.opciones_receta = [
                f"{r.id} — {r.producto_terminado.nombre} "
                f"(rinde {r.rendimiento} {r.unidad_rendimiento})"
                for r in self.recetas
            ]
            n_ordenes = db.query(OrdenProduccion).count()
        numero_lote_auto = f"LOTE-{date.today().year}-{n_ordenes + 1:03d}"

        franja = tk.Frame(self, bg=COLOR_PRIMARIO, pady=12, padx=20)
        franja.pack(fill="x")
        tk.Label(franja, text="🍺  Nueva orden de producción",
                 bg=COLOR_PRIMARIO, fg="white",
                 font=("Segoe UI", 13, "bold")).pack(anchor="w")

        cuerpo = ttk.Frame(self, padding=(20, 16))
        cuerpo.pack(fill="both", expand=True)

        self._msg = MensajeEstado(cuerpo)
        self._msg.pack(fill="x", pady=(0, 8))

        sec = SeccionFormulario(cuerpo, "Datos de la orden")
        sec.pack(fill="x", pady=(0, 10))

        fila_receta = ttk.Frame(sec)
        fila_receta.pack(fill="x")
        ttk.Label(fila_receta, text="Receta de cerveza *",
                  font=("Segoe UI", 9, "bold")).pack(side="left")
        from app.ui.tutorial_overlay import boton_ayuda_contextual
        from app.ui.tutorial_data import AYUDA_CONTEXTUAL
        titulo_recetas, texto_recetas = AYUDA_CONTEXTUAL["recetas"]
        boton_ayuda_contextual(fila_receta, titulo_recetas, texto_recetas,
                                side="right")
        self.combo_receta = ttk.Combobox(
            sec, state="readonly", values=self.opciones_receta, width=50)
        self.combo_receta.pack(fill="x", pady=(2, 8))

        ttk.Label(sec, text="Cantidad planeada a producir *",
                  font=("Segoe UI", 9, "bold")).pack(anchor="w")
        self.var_cantidad = tk.StringVar()
        ttk.Entry(sec, textvariable=self.var_cantidad, width=20).pack(anchor="w", pady=(2, 8))

        sec_lote = SeccionFormulario(cuerpo, "Número de lote")
        sec_lote.pack(fill="x", pady=(0, 10))
        ttk.Label(sec_lote,
                  text="Generado automáticamente. Puedes editarlo si es necesario.",
                  style="CampoAuto.TLabel").pack(anchor="w")
        self.var_numero_lote = tk.StringVar(value=numero_lote_auto)
        ttk.Entry(sec_lote, textvariable=self.var_numero_lote, width=25).pack(
            anchor="w", pady=(4, 0))

        sec_obs = SeccionFormulario(cuerpo, "Observaciones")
        sec_obs.pack(fill="x", pady=(0, 10))
        self.var_observaciones = tk.StringVar()
        ttk.Entry(sec_obs, textvariable=self.var_observaciones, width=50).pack(
            fill="x", pady=(2, 0))
        ttk.Label(sec_obs, text="Opcional", style="CampoAuto.TLabel").pack(anchor="w")

        ttk.Label(cuerpo, text="* Campo obligatorio",
                  style="CampoAuto.TLabel").pack(anchor="w", pady=(4, 8))

        fila_btn = ttk.Frame(cuerpo)
        fila_btn.pack(fill="x")
        ttk.Button(fila_btn, text="Cancelar", style="Secundario.TButton",
                   command=self.destroy).pack(side="right", padx=(8, 0))
        ttk.Button(fila_btn, text="🍺  Crear orden",
                   command=self._guardar).pack(side="right")

        self.bind("<Escape>", lambda e: self.destroy())
        centrar_ventana(self, 480, 460)

    def _guardar(self):
        if not self.combo_receta.get():
            self._msg.mostrar("Selecciona una receta de cerveza.", "error")
            return
        if not self.var_numero_lote.get().strip():
            self._msg.mostrar("El número de lote es obligatorio.", "error")
            return
        try:
            cantidad = float(self.var_cantidad.get())
            if cantidad <= 0:
                raise ValueError
        except ValueError:
            self._msg.mostrar("La cantidad planeada debe ser un número mayor que 0.", "error")
            return

        receta_id = int(self.combo_receta.get().split(" — ")[0])
        try:
            orden = crear_orden(
                receta_id=receta_id,
                cantidad_planeada=cantidad,
                numero_lote=self.var_numero_lote.get().strip(),
                observaciones=self.var_observaciones.get().strip(),
                usuario_id=sesion_actual.usuario_id,
            )
        except Exception as error:
            messagebox.showerror("No se pudo crear la orden",
                                  f"Ocurrió un error:\n\n{error}")
            return

        messagebox.showinfo(
            "✓ Orden creada",
            f"Orden {orden.numero} creada correctamente.\n"
            f"Lote: {self.var_numero_lote.get().strip()}")
        self.al_guardar()
        self.destroy()


class VentanaCerrarOrden(tk.Toplevel):
    def __init__(self, parent, orden_id, al_guardar):
        super().__init__(parent)
        self.title("Cerrar orden de producción")
        self.resizable(False, False)
        self.grab_set()
        self.orden_id = orden_id
        self.al_guardar = al_guardar

        franja = tk.Frame(self, bg=COLOR_PRIMARIO, pady=12, padx=20)
        franja.pack(fill="x")
        tk.Label(franja, text="✔  Cerrar orden de producción",
                 bg=COLOR_PRIMARIO, fg="white",
                 font=("Segoe UI", 13, "bold")).pack(anchor="w")

        cuerpo = ttk.Frame(self, padding=(20, 16))
        cuerpo.pack(fill="both", expand=True)

        self._msg = MensajeEstado(cuerpo)
        self._msg.pack(fill="x", pady=(0, 8))

        ttk.Label(
            cuerpo,
            text="Al cerrar la orden:\n"
                 "  • Se descuentan los insumos del inventario (FIFO)\n"
                 "  • Se crea el lote de producto terminado\n"
                 "  • Se calcula el costo real de producción",
            foreground=COLOR_TEXTO_SECUNDARIO,
            font=("Segoe UI", 9),
            justify="left",
        ).pack(anchor="w", pady=(0, 12))

        sec_prod = SeccionFormulario(cuerpo, "Producción real")
        sec_prod.pack(fill="x", pady=(0, 10))

        f1 = ttk.Frame(sec_prod)
        f1.pack(fill="x", pady=(0, 6))
        c1 = ttk.Frame(f1)
        c1.pack(side="left", padx=(0, 20))
        ttk.Label(c1, text="Cantidad real producida *",
                  font=("Segoe UI", 9, "bold")).pack(anchor="w")
        self.var_cantidad_real = tk.StringVar()
        ttk.Entry(c1, textvariable=self.var_cantidad_real, width=14).pack(pady=(2, 0))

        c2 = ttk.Frame(f1)
        c2.pack(side="left")
        ttk.Label(c2, text="Cantidad de merma",
                  font=("Segoe UI", 9)).pack(anchor="w")
        self.var_merma = tk.StringVar(value="0")
        ttk.Entry(c2, textvariable=self.var_merma, width=14).pack(pady=(2, 0))

        ttk.Label(sec_prod, text="Causa de la merma (dejar en blanco si no hubo)",
                  font=("Segoe UI", 9)).pack(anchor="w", pady=(4, 0))
        self.var_causa_merma = tk.StringVar()
        ttk.Entry(sec_prod, textvariable=self.var_causa_merma, width=45).pack(
            anchor="w", pady=(2, 0))

        sec_costos = SeccionFormulario(cuerpo, "Costos adicionales")
        sec_costos.pack(fill="x", pady=(0, 10))

        f2 = ttk.Frame(sec_costos)
        f2.pack(fill="x")
        c3 = ttk.Frame(f2)
        c3.pack(side="left", padx=(0, 20))
        ttk.Label(c3, text="Mano de obra (S/)",
                  font=("Segoe UI", 9)).pack(anchor="w")
        self.var_mano_obra = tk.StringVar(value="0")
        ttk.Entry(c3, textvariable=self.var_mano_obra, width=14).pack(pady=(2, 0))

        c4 = ttk.Frame(f2)
        c4.pack(side="left")
        ttk.Label(c4, text="Costos indirectos (S/)",
                  font=("Segoe UI", 9)).pack(anchor="w")
        self.var_indirectos = tk.StringVar(value="0")
        ttk.Entry(c4, textvariable=self.var_indirectos, width=14).pack(pady=(2, 0))
        ttk.Label(c4, text="Energía, agua, etc.",
                  style="CampoAuto.TLabel").pack(anchor="w")

        ttk.Label(cuerpo, text="* Campo obligatorio",
                  style="CampoAuto.TLabel").pack(anchor="w", pady=(4, 8))

        fila_btn = ttk.Frame(cuerpo)
        fila_btn.pack(fill="x")
        ttk.Button(fila_btn, text="Cancelar", style="Secundario.TButton",
                   command=self.destroy).pack(side="right", padx=(8, 0))
        ttk.Button(fila_btn, text="✔  Cerrar y costear orden",
                   command=self._guardar).pack(side="right")

        self.bind("<Escape>", lambda e: self.destroy())
        centrar_ventana(self, 480, 520)

    def _guardar(self):
        try:
            cantidad_real = float(self.var_cantidad_real.get())
            merma         = float(self.var_merma.get() or 0)
            mano_obra     = float(self.var_mano_obra.get() or 0)
            indirectos    = float(self.var_indirectos.get() or 0)
            if cantidad_real <= 0:
                raise ValueError
        except ValueError:
            self._msg.mostrar(
                "Revisa que la cantidad real sea mayor que 0 y todos los números sean válidos.",
                "error")
            return

        try:
            orden = cerrar_orden(
                orden_id=self.orden_id,
                cantidad_real=cantidad_real,
                cantidad_merma=merma,
                causa_merma=self.var_causa_merma.get().strip(),
                costo_mano_obra=mano_obra,
                costos_indirectos=indirectos,
                usuario_id=sesion_actual.usuario_id,
            )
        except Exception as error:
            messagebox.showerror("No se pudo cerrar la orden",
                                  f"Ocurrió un error:\n\n{error}")
            return

        messagebox.showinfo(
            "✓ Orden cerrada correctamente",
            f"La orden {orden.numero} fue cerrada y costeada.\n"
            f"Cantidad real: {cantidad_real:.1f}\n"
            f"El inventario de insumos fue descontado.")
        self.al_guardar()
        self.destroy()
