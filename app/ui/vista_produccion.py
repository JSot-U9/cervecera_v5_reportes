"""
vista_produccion.py
====================
Módulo de Producción — gestión de órdenes de elaboración de cerveza.

Permite:
  - Crear una orden nueva: la receta se selecciona y el número de lote
    se genera automáticamente en formato LOTE-{AÑO}-{NNN}.
  - Iniciar el proceso (estado: INICIADA → EN_PROCESO).
  - Cerrar la orden: consume insumos por FIFO, registra merma, crea el
    lote de producto terminado y calcula el costo de producción.
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
from app.ui.widgets import EncabezadoModulo, BarraBusqueda, TablaDatos, ajustar_ventana_a_contenido
from app.ui.estilos import COLOR_TEXTO_SECUNDARIO

ESTADOS_QUE_SE_PUEDEN_CERRAR = ("INICIADA", "EN_PROCESO")


class VistaProduccion(ttk.Frame):
    def __init__(self, parent):
        super().__init__(parent)
        EncabezadoModulo(
            self,
            "Módulo de Producción",
            "Planificación, seguimiento y cierre de órdenes de elaboración de cerveza artesanal",
        ).pack(fill="x")

        cuerpo = ttk.Frame(self, padding=12)
        cuerpo.pack(fill="both", expand=True)

        puede_crear  = puede(sesion_actual.rol, "produccion", "crear")
        puede_iniciar = puede(sesion_actual.rol, "produccion", "iniciar")
        puede_cerrar  = puede(sesion_actual.rol, "produccion", "cerrar")

        barra = BarraBusqueda(cuerpo, al_escribir=lambda t: self.tabla.filtrar(t))
        if puede_crear:
            barra.agregar_boton("+ Nueva orden de producción", self._abrir_nueva_orden)
        if puede_iniciar:
            barra.agregar_boton("▶ Iniciar proceso", self._iniciar)
        if puede_cerrar:
            barra.agregar_boton("✔ Cerrar orden", self._abrir_cerrar_orden)
        barra.agregar_boton("📊  Generar reporte…", self._abrir_dialogo_reporte)
        barra.pack(fill="x", pady=(0, 8))

        contenedor_tabla = ttk.Frame(cuerpo)
        contenedor_tabla.pack(fill="both", expand=True)
        self.tabla = TablaDatos(
            contenedor_tabla,
            ["N° de Orden de Producción", "Producto a Elaborar", "N° de Lote",
             "Cantidad Planeada", "Cantidad Real Obtenida", "Estado"],
        )
        self.tabla.empaquetar()

        self.refrescar()

    def refrescar(self):
        with nueva_sesion() as db:
            filas = []
            for orden in listar_ordenes(db):
                producto = (orden.receta.producto_terminado.nombre
                            if orden.receta else "—")
                filas.append([
                    orden.id,
                    orden.numero,
                    producto,
                    orden.numero_lote,
                    f"{orden.cantidad_planeada:.1f}",
                    f"{orden.cantidad_real:.1f}" if orden.cantidad_real else "—",
                    orden.estado,
                ])
        self.tabla.cargar_filas(filas)

    def _abrir_nueva_orden(self):
        VentanaNuevaOrdenProduccion(self, al_guardar=self.refrescar)

    def _iniciar(self):
        orden_id = self.tabla.id_seleccionado()
        if not orden_id:
            messagebox.showwarning("Aviso", "Selecciona una orden de la lista.")
            return
        try:
            iniciar_proceso(orden_id)
        except Exception as error:
            messagebox.showerror("Error", str(error))
            return
        self.refrescar()

    def _abrir_cerrar_orden(self):
        orden_id = self.tabla.id_seleccionado()
        if not orden_id:
            messagebox.showwarning("Aviso", "Selecciona una orden de la lista.")
            return

        with nueva_sesion() as db:
            orden = db.get(OrdenProduccion, orden_id)
        if not orden or orden.estado not in ESTADOS_QUE_SE_PUEDEN_CERRAR:
            estado_actual = orden.estado if orden else "desconocido"
            messagebox.showerror(
                "No se puede cerrar",
                f"La orden está en estado '{estado_actual}'.\n"
                f"Solo se pueden cerrar órdenes en estado INICIADA o EN_PROCESO.",
            )
            return

        VentanaCerrarOrden(self, orden_id, al_guardar=self.refrescar)


    def _abrir_dialogo_reporte(self):
        from app.ui.dialogo_reporte import DialogoReporte
        DialogoReporte(self.winfo_toplevel(), modulo="produccion")

class VentanaNuevaOrdenProduccion(tk.Toplevel):
    def __init__(self, parent, al_guardar):
        super().__init__(parent)
        self.title("Nueva orden de producción")
        self.al_guardar = al_guardar

        with nueva_sesion() as db:
            self.recetas = listar_recetas_activas(db)
            self.opciones_receta = [
                f"{r.id} — {r.producto_terminado.nombre} "
                f"(rinde {r.rendimiento} {r.unidad_rendimiento})"
                for r in self.recetas
            ]
            # Generar número de lote automáticamente
            n_ordenes = db.query(OrdenProduccion).count()
        numero_lote_auto = f"LOTE-{date.today().year}-{n_ordenes + 1:03d}"

        contenedor = ttk.Frame(self, padding=16)
        contenedor.pack(fill="both", expand=True)

        ttk.Label(contenedor, text="Receta de cerveza a elaborar:").pack(anchor="w")
        self.combo_receta = ttk.Combobox(
            contenedor, state="readonly", values=self.opciones_receta)
        self.combo_receta.pack(fill="x", pady=(0, 8))

        ttk.Label(contenedor, text="Cantidad planeada a producir:").pack(anchor="w")
        self.var_cantidad = tk.StringVar()
        ttk.Entry(contenedor, textvariable=self.var_cantidad).pack(fill="x", pady=(0, 8))

        # Número de lote autocompletado pero editable
        marco_lote = ttk.LabelFrame(contenedor, text="Número de lote de producción", padding=8)
        marco_lote.pack(fill="x", pady=(0, 8))
        ttk.Label(
            marco_lote,
            text="Se generó automáticamente siguiendo el formato LOTE-AÑO-NNN.\n"
                 "Puedes editarlo si necesitas un número diferente.",
            foreground=COLOR_TEXTO_SECUNDARIO,
        ).pack(anchor="w", pady=(0, 4))
        self.var_numero_lote = tk.StringVar(value=numero_lote_auto)
        ttk.Entry(marco_lote, textvariable=self.var_numero_lote).pack(fill="x")

        ttk.Label(contenedor, text="Observaciones (opcional):").pack(anchor="w", pady=(8, 0))
        self.var_observaciones = tk.StringVar()
        ttk.Entry(contenedor, textvariable=self.var_observaciones).pack(fill="x", pady=(0, 10))

        ttk.Button(contenedor, text="Crear orden de producción",
                   command=self._guardar).pack(fill="x")

        ajustar_ventana_a_contenido(self, ancho=420)

    def _guardar(self):
        if not self.combo_receta.get():
            messagebox.showwarning("Aviso", "Selecciona una receta.")
            return
        if not self.var_numero_lote.get().strip():
            messagebox.showwarning("Aviso", "El número de lote es obligatorio.")
            return
        try:
            cantidad = float(self.var_cantidad.get())
            if cantidad <= 0:
                raise ValueError
        except ValueError:
            messagebox.showwarning("Aviso", "La cantidad planeada debe ser un número positivo.")
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
            messagebox.showinfo("Orden creada",
                                 f"Orden {orden.numero} creada con el lote "
                                 f"{self.var_numero_lote.get().strip()}.")
        except Exception as error:
            messagebox.showerror("Error", str(error))
            return

        self.al_guardar()
        self.destroy()


class VentanaCerrarOrden(tk.Toplevel):
    def __init__(self, parent, orden_id, al_guardar):
        super().__init__(parent)
        self.title("Cerrar orden de producción")
        self.orden_id = orden_id
        self.al_guardar = al_guardar

        contenedor = ttk.Frame(self, padding=16)
        contenedor.pack(fill="both", expand=True)

        ttk.Label(
            contenedor,
            text="Al cerrar la orden se descuentan los insumos del inventario (por FIFO),\n"
                 "se crea el lote de producto terminado y se calcula el costo real de producción.",
            foreground=COLOR_TEXTO_SECUNDARIO,
            justify="left",
        ).pack(anchor="w", pady=(0, 12))

        ttk.Label(contenedor, text="Cantidad real producida (litros u otra unidad):").pack(
            anchor="w")
        self.var_cantidad_real = tk.StringVar()
        ttk.Entry(contenedor, textvariable=self.var_cantidad_real).pack(fill="x", pady=(0, 8))

        ttk.Label(contenedor, text="Cantidad de merma (0 si no hubo pérdidas):").pack(anchor="w")
        self.var_merma = tk.StringVar(value="0")
        ttk.Entry(contenedor, textvariable=self.var_merma).pack(fill="x", pady=(0, 8))

        ttk.Label(contenedor, text="Causa de la merma (dejar en blanco si no hubo):").pack(
            anchor="w")
        self.var_causa_merma = tk.StringVar()
        ttk.Entry(contenedor, textvariable=self.var_causa_merma).pack(fill="x", pady=(0, 8))

        ttk.Label(contenedor, text="Costo de mano de obra (S/):").pack(anchor="w")
        self.var_mano_obra = tk.StringVar(value="0")
        ttk.Entry(contenedor, textvariable=self.var_mano_obra).pack(fill="x", pady=(0, 8))

        ttk.Label(contenedor, text="Costos indirectos — energía, agua, etc. (S/):").pack(
            anchor="w")
        self.var_indirectos = tk.StringVar(value="0")
        ttk.Entry(contenedor, textvariable=self.var_indirectos).pack(fill="x", pady=(0, 10))

        ttk.Button(contenedor, text="Cerrar orden y calcular costos de producción",
                   command=self._guardar).pack(fill="x")

        ajustar_ventana_a_contenido(self, ancho=420)

    def _guardar(self):
        try:
            cantidad_real = float(self.var_cantidad_real.get())
            merma         = float(self.var_merma.get() or 0)
            mano_obra     = float(self.var_mano_obra.get() or 0)
            indirectos    = float(self.var_indirectos.get() or 0)
            if cantidad_real <= 0:
                raise ValueError
        except ValueError:
            messagebox.showwarning("Aviso",
                                    "Revisa que los números ingresados sean válidos y positivos.")
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
            messagebox.showinfo("Orden cerrada",
                                 f"Orden {orden.numero} cerrada y costeada correctamente.")
        except Exception as error:
            messagebox.showerror("Error", str(error))
            return

        self.al_guardar()
        self.destroy()