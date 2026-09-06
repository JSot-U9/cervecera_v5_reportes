"""
dialogo_reporte.py
==================
Ventana emergente para generar y guardar reportes.

Flujo:
  1. Pulsa «Vista previa» → se cargan los datos del reporte y se
     muestran en una tabla dentro de la propia ventana (misma tabla —
     TablaDatos — que usan los demás módulos, para que se vea igual
     de familiar). De paso se genera el PDF en memoria, listo para
     guardarse sin tener que regenerarlo.
  2. Pulsa «Guardar como…» → se abre el gestor de archivos nativo del
     sistema operativo para elegir la ruta y el formato (PDF / XLSX / CSV).
  3. El archivo se genera en la ruta elegida y se ofrece abrirlo.

Compatibilidad del diálogo nativo:
  - Linux GNOME  : zenity (preinstalado en Ubuntu Desktop)
  - Linux KDE    : kdialog
  - Windows 10/11: PowerShell SaveFileDialog (Explorador de Windows)
  - Fallback      : tkinter filedialog
"""

import io
import os
import subprocess
import sys
import tkinter as tk
from pathlib import Path
from tkinter import ttk, messagebox

from app.logica_reportes import (
    REPORTES, NOMBRES_LEGIBLES,
    guardar_pdf, guardar_xlsx, guardar_csv,
)
from app.ui.estilos import (
    COLOR_PRIMARIO, COLOR_SIDEBAR, COLOR_TEXTO,
    COLOR_TEXTO_SECUNDARIO, COLOR_FONDO,
)
from app.ui.widgets import TablaDatos


_FORMATOS = {
    "PDF   (.pdf)":  ("pdf",  "Archivos PDF",  "*.pdf"),
    "Excel (.xlsx)": ("xlsx", "Archivos Excel", "*.xlsx"),
    "CSV   (.csv)":  ("csv",  "Archivos CSV",   "*.csv"),
}

_ICONOS_REPORTE = {
    "costos":     "💰",
    "stock":      "📦",
    "compras":    "🛒",
    "ventas":     "💵",
    "produccion": "🍺",
}


# ══════════════════════════════════════════════════════════════════
#  DIÁLOGO NATIVO DEL SISTEMA OPERATIVO
# ══════════════════════════════════════════════════════════════════

def _guardar_nativo(titulo: str, nombre_sugerido: str, ext: str, desc: str) -> str | None:
    if sys.platform == "win32":
        return _dialogo_windows(titulo, nombre_sugerido, ext, desc)
    return _dialogo_linux(titulo, nombre_sugerido, ext, desc)


def _dialogo_windows(titulo, nombre_sugerido, ext, desc):
    filtro = f"{desc} (*.{ext})|*.{ext}|Todos los archivos (*.*)|*.*"
    titulo_ps          = titulo.replace("'", "\\'")
    nombre_sugerido_ps = nombre_sugerido.replace("'", "\\'")
    filtro_ps          = filtro.replace("'", "\\'")
    ps_script = (
        "Add-Type -AssemblyName System.Windows.Forms; "
        "$dlg = New-Object System.Windows.Forms.SaveFileDialog; "
        f"$dlg.Title = '{titulo_ps}'; "
        f"$dlg.FileName = '{nombre_sugerido_ps}'; "
        f"$dlg.Filter = '{filtro_ps}'; "
        f"$dlg.DefaultExt = '{ext}'; "
        "$dlg.OverwritePrompt = $true; "
        "if ($dlg.ShowDialog() -eq 'OK') { Write-Output $dlg.FileName }"
    )
    try:
        r = subprocess.run(
            ["powershell", "-NoProfile", "-NonInteractive", "-Command", ps_script],
            capture_output=True, text=True, timeout=120,
        )
        ruta = r.stdout.strip()
        if ruta:
            if not ruta.lower().endswith(f".{ext}"):
                ruta += f".{ext}"
            return ruta
        return None
    except Exception:
        return _dialogo_tkinter(titulo, nombre_sugerido, ext, desc)


def _dialogo_linux(titulo, nombre_sugerido, ext, desc):
    try:
        r = subprocess.run(
            [
                "zenity", "--file-selection", "--save",
                "--confirm-overwrite",
                f"--title={titulo}",
                f"--filename={Path.home() / nombre_sugerido}",
                f"--file-filter={desc} | *.{ext}",
                "--file-filter=Todos los archivos | *",
            ],
            capture_output=True, text=True, timeout=120,
        )
        if r.returncode == 0:
            ruta = r.stdout.strip()
            if ruta:
                if not ruta.lower().endswith(f".{ext}"):
                    ruta += f".{ext}"
                return ruta
        return None
    except FileNotFoundError:
        pass
    try:
        r = subprocess.run(
            [
                "kdialog", "--getsavefilename",
                str(Path.home() / nombre_sugerido),
                f"*.{ext}", "--title", titulo,
            ],
            capture_output=True, text=True, timeout=120,
        )
        if r.returncode == 0:
            ruta = r.stdout.strip()
            if ruta:
                if not ruta.lower().endswith(f".{ext}"):
                    ruta += f".{ext}"
                return ruta
        return None
    except FileNotFoundError:
        pass
    return _dialogo_tkinter(titulo, nombre_sugerido, ext, desc)


def _dialogo_tkinter(titulo, nombre_sugerido, ext, desc):
    from tkinter import filedialog
    ruta = filedialog.asksaveasfilename(
        title=titulo,
        initialfile=nombre_sugerido,
        defaultextension=f".{ext}",
        filetypes=[(desc, f"*.{ext}"), ("Todos los archivos", "*.*")],
    )
    return ruta or None


def _abrir_archivo(ruta: Path):
    try:
        os.startfile(str(ruta))
    except AttributeError:
        try:
            subprocess.Popen(["xdg-open", str(ruta)])
        except FileNotFoundError:
            subprocess.Popen(["open", str(ruta)])


# ══════════════════════════════════════════════════════════════════
#  VISTA DE TABLA (reemplaza al antiguo visor de PDF renderizado)
# ══════════════════════════════════════════════════════════════════

class _VistaTablaReporte(ttk.Frame):
    """
    Muestra los datos de un reporte como tabla, en vez de renderizar
    el PDF: una fila de tarjetas KPI arriba (si el reporte las trae)
    y debajo la misma TablaDatos (Treeview) que usan los demás
    módulos, para que la vista previa se sienta consistente con el
    resto del programa.
    """

    def __init__(self, parent, datos: dict):
        super().__init__(parent)

        # ── KPIs (si el reporte los trae; stock y producción no) ───
        if datos.get("kpis"):
            fila_kpis = ttk.Frame(self)
            fila_kpis.pack(fill="x", padx=6, pady=(6, 10))
            for kpi in datos["kpis"]:
                tarjeta = ttk.Frame(fila_kpis, style="Tarjeta.TFrame", padding=10)
                tarjeta.pack(side="left", fill="x", expand=True, padx=4)
                ttk.Label(tarjeta, text=kpi["valor"], style="TarjetaValor.TLabel",
                          font=("Segoe UI", 15, "bold")).pack(anchor="w")
                ttk.Label(tarjeta, text=kpi["etiqueta"],
                          style="TarjetaEtiqueta.TLabel").pack(anchor="w")

        # ── Tabla de datos ──────────────────────────────────────────
        contenedor = ttk.Frame(self)
        contenedor.pack(fill="both", expand=True, padx=6, pady=(0, 6))

        self._tabla = TablaDatos(contenedor, columnas=datos["columnas"], con_id=False)
        self._tabla.empaquetar()
        self._tabla.cargar_filas(datos["filas"])


# ══════════════════════════════════════════════════════════════════
#  VENTANA DEL DIÁLOGO
# ══════════════════════════════════════════════════════════════════

class DialogoReporte(tk.Toplevel):
    """Ventana modal para previsualizar y exportar un reporte."""

    def __init__(self, parent, modulo: str | None = None):
        super().__init__(parent)
        self.resizable(True, True)
        self.configure(bg=COLOR_FONDO)

        self._modulo_fijo  = modulo
        self._datos        = None
        self._pdf_bytes    = None   # bytes del PDF generado en preview
        self._tipo_var     = tk.StringVar(value=modulo or "costos")
        self._formato_var  = tk.StringVar(value="PDF   (.pdf)")
        self._vista_tabla  = None   # widget _VistaTablaReporte activo

        titulo = (f"Generar Reporte — {NOMBRES_LEGIBLES[modulo]}"
                  if modulo else "Generar Reporte")
        self.title(titulo)

        self._construir_ui()

        ancho, alto = 1000, 760
        self.update_idletasks()
        px = parent.winfo_rootx() + (parent.winfo_width()  - ancho) // 2
        py = parent.winfo_rooty() + (parent.winfo_height() - alto)  // 2
        self.geometry(f"{ancho}x{alto}+{px}+{py}")

        self.grab_set()
        self.focus_set()

        if self._modulo_fijo:
            self.after(50, self._cargar_preview)

    # ── Construcción de la UI ─────────────────────────────────────

    def _construir_ui(self):
        # Encabezado
        panel_top = tk.Frame(self, bg=COLOR_SIDEBAR, pady=14, padx=18)
        panel_top.pack(fill="x")
        tk.Label(
            panel_top, text="Generador de Reportes",
            font=("Helvetica", 15, "bold"),
            bg=COLOR_SIDEBAR, fg="#E9E2C6",
        ).pack(side="left")

        # Fila de opciones
        panel_opts = tk.Frame(self, bg=COLOR_FONDO, pady=10, padx=18)
        panel_opts.pack(fill="x")

        self._mapa_tipo = {
            f"{_ICONOS_REPORTE[k]}  {NOMBRES_LEGIBLES[k]}": k for k in REPORTES
        }

        if self._modulo_fijo:
            icono  = _ICONOS_REPORTE.get(self._modulo_fijo, "")
            nombre = NOMBRES_LEGIBLES.get(self._modulo_fijo, self._modulo_fijo)
            tk.Label(panel_opts, text=f"{icono}  {nombre}",
                     bg=COLOR_FONDO, fg=COLOR_PRIMARIO,
                     font=("Helvetica", 10, "bold")).grid(
                row=0, column=0, columnspan=2, sticky="w", padx=(0, 20))
            self._combo_tipo = None
        else:
            tk.Label(panel_opts, text="Tipo de reporte:", bg=COLOR_FONDO,
                     fg=COLOR_TEXTO, font=("Helvetica", 9, "bold")).grid(
                row=0, column=0, sticky="w", padx=(0, 6))
            self._combo_tipo = ttk.Combobox(
                panel_opts,
                textvariable=self._tipo_var,
                values=list(self._mapa_tipo.keys()),
                state="readonly", width=24,
            )
            self._combo_tipo.set("💰  Costos")
            self._combo_tipo.grid(row=0, column=1, sticky="w", padx=(0, 20))

        tk.Label(panel_opts, text="Formato al guardar:", bg=COLOR_FONDO,
                 fg=COLOR_TEXTO, font=("Helvetica", 9, "bold")).grid(
            row=0, column=2, sticky="w", padx=(0, 6))

        for i, texto in enumerate(_FORMATOS):
            ttk.Radiobutton(
                panel_opts, text=texto,
                variable=self._formato_var, value=texto,
            ).grid(row=0, column=3 + i, sticky="w", padx=4)

        ttk.Button(
            panel_opts, text="🔍  Vista previa",
            command=self._cargar_preview,
        ).grid(row=0, column=6, padx=(20, 4))

        self._btn_guardar = ttk.Button(
            panel_opts, text="💾  Guardar como…",
            command=self._guardar, state="disabled",
        )
        self._btn_guardar.grid(row=0, column=7, padx=4)

        ttk.Separator(self, orient="horizontal").pack(fill="x", padx=18, pady=(4, 0))

        self._var_estado = tk.StringVar(
            value="Pulsa «Vista previa» para ver los datos del reporte.")
        tk.Label(
            self, textvariable=self._var_estado,
            bg=COLOR_FONDO, fg=COLOR_TEXTO_SECUNDARIO,
            font=("Helvetica", 9), anchor="w", padx=18,
        ).pack(fill="x", pady=(4, 0))

        # Área de contenido (tabla del reporte o placeholder)
        self._frame_contenido = tk.Frame(self, bg=COLOR_FONDO)
        self._frame_contenido.pack(fill="both", expand=True, padx=18, pady=6)

        self._lbl_placeholder = tk.Label(
            self._frame_contenido,
            text="La tabla del reporte aparecerá aquí.",
            bg=COLOR_FONDO, fg=COLOR_TEXTO_SECUNDARIO,
            font=("Helvetica", 11),
        )
        self._lbl_placeholder.pack(expand=True)

        # Barra inferior
        barra_inf = tk.Frame(self, bg=COLOR_FONDO, pady=10, padx=18)
        barra_inf.pack(fill="x")
        ttk.Button(barra_inf, text="Cerrar", command=self.destroy).pack(side="right")

    # ── Lógica ────────────────────────────────────────────────────

    def _clave_tipo(self) -> str:
        if self._modulo_fijo:
            return self._modulo_fijo
        return self._mapa_tipo.get(self._combo_tipo.get(), "costos")

    def _cargar_preview(self):
        clave = self._clave_tipo()
        self._var_estado.set("Cargando datos del reporte…")
        self.update_idletasks()

        try:
            self._datos = REPORTES[clave]()
        except Exception as e:
            self._var_estado.set(f"Error al cargar datos: {e}")
            messagebox.showerror("Error", str(e), parent=self)
            return

        # Generar el PDF en memoria de una vez, aunque la vista previa
        # sea una tabla: así «Guardar como…» no tiene que regenerarlo
        # si el formato elegido termina siendo PDF.
        buf = io.BytesIO()
        try:
            guardar_pdf(self._datos, buf)
            self._pdf_bytes = buf.getvalue()
        except Exception as e:
            self._var_estado.set(f"Error al generar PDF: {e}")
            messagebox.showerror("Error al generar PDF", str(e), parent=self)
            return

        n = len(self._datos["filas"])
        nombre = NOMBRES_LEGIBLES[clave]
        self._var_estado.set(
            f"Vista previa de «{nombre}» — "
            f"{n} registro{'s' if n != 1 else ''} encontrado{'s' if n != 1 else ''}."
        )
        self._btn_guardar.configure(state="normal")

        self._mostrar_tabla()

    def _mostrar_tabla(self):
        """Destruye el contenido anterior y muestra los datos como tabla."""
        for w in self._frame_contenido.winfo_children():
            w.destroy()
        self._vista_tabla = _VistaTablaReporte(self._frame_contenido, self._datos)
        self._vista_tabla.pack(fill="both", expand=True)

    def _guardar(self):
        if self._datos is None:
            messagebox.showwarning("Sin datos",
                                   "Primero genera la vista previa.", parent=self)
            return

        clave   = self._clave_tipo()
        formato = self._formato_var.get()
        ext, desc_tipo, _ = _FORMATOS[formato]

        import datetime
        ts = datetime.datetime.now().strftime("%Y%m%d_%H%M%S")
        nombre_sugerido = f"Reporte_{NOMBRES_LEGIBLES[clave]}_{ts}.{ext}"

        self.grab_release()
        ruta_str = _guardar_nativo(
            titulo=f"Guardar reporte de {NOMBRES_LEGIBLES[clave]}",
            nombre_sugerido=nombre_sugerido,
            ext=ext,
            desc=desc_tipo,
        )
        self.grab_set()

        if not ruta_str:
            return

        ruta = Path(ruta_str)
        try:
            if ext == "pdf":
                # Reutilizar los bytes ya generados
                ruta.write_bytes(self._pdf_bytes)
            elif ext == "xlsx":
                guardar_xlsx(self._datos, ruta)
            else:
                guardar_csv(self._datos, ruta)
        except Exception as e:
            messagebox.showerror("Error al guardar", str(e), parent=self)
            return

        self._var_estado.set(f"✓ Guardado en: {ruta}")
        if messagebox.askyesno(
            "Reporte guardado",
            f"El reporte fue guardado en:\n\n{ruta}\n\n¿Deseas abrirlo ahora?",
            parent=self,
        ):
            _abrir_archivo(ruta)
