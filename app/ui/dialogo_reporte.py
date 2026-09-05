"""
dialogo_reporte.py
==================
Ventana emergente para generar y guardar reportes.

Flujo:
  1. Elige el tipo de reporte (costos / stock / compras / ventas / producción).
  2. Elige el formato: PDF, XLSX o CSV.
  3. Pulsa "Vista previa" → la tabla inferior muestra los datos reales.
  4. Pulsa "Guardar como…" → se abre el gestor de archivos nativo del sistema
     (Nautilus en Ubuntu/GNOME, Explorador en Windows).
  5. El archivo se genera en la ruta elegida y se ofrece abrirlo.

Compatibilidad del diálogo nativo:
  - Linux GNOME  : zenity (preinstalado en Ubuntu Desktop)
  - Linux KDE    : kdialog
  - Windows 10/11: PowerShell SaveFileDialog (Explorador de Windows)
  - Fallback      : tkinter filedialog
"""

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
    """
    Abre el gestor de archivos nativo para guardar un archivo.
    Retorna la ruta elegida como string, o None si el usuario canceló.

    Orden de intento:
      1. Windows  → PowerShell SaveFileDialog (Explorador de Windows)
      2. Linux    → zenity (GNOME/Nautilus, preinstalado en Ubuntu Desktop)
      3. Linux    → kdialog (KDE)
      4. Fallback → tkinter filedialog
    """
    if sys.platform == "win32":
        return _dialogo_windows(titulo, nombre_sugerido, ext, desc)
    return _dialogo_linux(titulo, nombre_sugerido, ext, desc)


def _dialogo_windows(titulo: str, nombre_sugerido: str, ext: str, desc: str) -> str | None:
    """
    Invoca el Explorador de Windows nativo via PowerShell + Windows.Forms.
    No requiere dependencias extra — PowerShell está disponible en
    todas las instalaciones de Windows 10/11.
    """
    filtro = f"{desc} (*.{ext})|*.{ext}|Todos los archivos (*.*)|*.*"
    # Escapar comillas simples en strings que van a PowerShell
    titulo_ps           = titulo.replace("'", "\\'")
    nombre_sugerido_ps  = nombre_sugerido.replace("'", "\\'")
    filtro_ps           = filtro.replace("'", "\\'")

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


def _dialogo_linux(titulo: str, nombre_sugerido: str, ext: str, desc: str) -> str | None:
    """Intenta zenity (GNOME), luego kdialog (KDE), luego tkinter."""

    # ── zenity — Ubuntu Desktop / GNOME (preinstalado) ────────────
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
        # returncode == 1 significa que el usuario canceló → devolver None
        return None
    except FileNotFoundError:
        pass   # zenity no instalado, probar siguiente

    # ── kdialog — KDE Plasma ──────────────────────────────────────
    try:
        r = subprocess.run(
            [
                "kdialog", "--getsavefilename",
                str(Path.home() / nombre_sugerido),
                f"*.{ext}",
                "--title", titulo,
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

    # ── Fallback tkinter ──────────────────────────────────────────
    return _dialogo_tkinter(titulo, nombre_sugerido, ext, desc)


def _dialogo_tkinter(titulo: str, nombre_sugerido: str, ext: str, desc: str) -> str | None:
    """Fallback: diálogo genérico de Tkinter."""
    from tkinter import filedialog
    ruta = filedialog.asksaveasfilename(
        title=titulo,
        initialfile=nombre_sugerido,
        defaultextension=f".{ext}",
        filetypes=[(desc, f"*.{ext}"), ("Todos los archivos", "*.*")],
    )
    return ruta or None


def _abrir_archivo(ruta: Path):
    """Abre el archivo con la aplicación predeterminada del sistema."""
    try:
        os.startfile(str(ruta))          # Windows
    except AttributeError:
        try:
            subprocess.Popen(["xdg-open", str(ruta)])   # Linux
        except FileNotFoundError:
            subprocess.Popen(["open", str(ruta)])        # macOS


# ══════════════════════════════════════════════════════════════════
#  VENTANA DEL DIÁLOGO
# ══════════════════════════════════════════════════════════════════

class DialogoReporte(tk.Toplevel):
    """Ventana modal para elegir, previsualizar y exportar un reporte."""

    def __init__(self, parent):
        super().__init__(parent)
        self.title("Generar Reporte")
        self.resizable(True, True)
        self.configure(bg=COLOR_FONDO)

        self._datos = None
        self._tipo_var    = tk.StringVar(value="costos")
        self._formato_var = tk.StringVar(value="PDF   (.pdf)")

        self._construir_ui()

        ancho, alto = 960, 680
        self.update_idletasks()
        px = parent.winfo_rootx() + (parent.winfo_width()  - ancho) // 2
        py = parent.winfo_rooty() + (parent.winfo_height() - alto)  // 2
        self.geometry(f"{ancho}x{alto}+{px}+{py}")

        self.grab_set()
        self.focus_set()

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

        tk.Label(panel_opts, text="Tipo de reporte:", bg=COLOR_FONDO,
                 fg=COLOR_TEXTO, font=("Helvetica", 9, "bold")).grid(
            row=0, column=0, sticky="w", padx=(0, 6))

        self._mapa_tipo = {
            f"{_ICONOS_REPORTE[k]}  {NOMBRES_LEGIBLES[k]}": k for k in REPORTES
        }
        self._combo_tipo = ttk.Combobox(
            panel_opts,
            textvariable=self._tipo_var,
            values=list(self._mapa_tipo.keys()),
            state="readonly", width=24,
        )
        self._combo_tipo.set(f"💰  Costos")
        self._combo_tipo.grid(row=0, column=1, sticky="w", padx=(0, 20))

        tk.Label(panel_opts, text="Formato:", bg=COLOR_FONDO,
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

        # Panel KPIs
        self._frame_kpis = tk.Frame(self, bg=COLOR_FONDO, padx=18)
        self._frame_kpis.pack(fill="x")

        ttk.Separator(self, orient="horizontal").pack(fill="x", padx=18, pady=(4, 0))

        self._var_estado = tk.StringVar(
            value="Elige un tipo de reporte y pulsa «Vista previa».")
        tk.Label(
            self, textvariable=self._var_estado,
            bg=COLOR_FONDO, fg=COLOR_TEXTO_SECUNDARIO,
            font=("Helvetica", 9), anchor="w", padx=18,
        ).pack(fill="x", pady=(4, 0))

        # Tabla de vista previa
        contenedor = tk.Frame(self, bg=COLOR_FONDO, padx=18, pady=6)
        contenedor.pack(fill="both", expand=True)

        self._tree = ttk.Treeview(contenedor, show="headings", selectmode="browse")
        sy = ttk.Scrollbar(contenedor, orient="vertical",   command=self._tree.yview)
        sx = ttk.Scrollbar(contenedor, orient="horizontal", command=self._tree.xview)
        self._tree.configure(yscrollcommand=sy.set, xscrollcommand=sx.set)
        sy.pack(side="right",  fill="y")
        sx.pack(side="bottom", fill="x")
        self._tree.pack(side="left", fill="both", expand=True)

        # Barra inferior
        barra_inf = tk.Frame(self, bg=COLOR_FONDO, pady=10, padx=18)
        barra_inf.pack(fill="x")
        ttk.Button(barra_inf, text="Cerrar", command=self.destroy).pack(side="right")

    # ── Lógica ───────────────────────────────────────────────────

    def _clave_tipo(self) -> str:
        return self._mapa_tipo.get(self._combo_tipo.get(), "costos")

    def _cargar_preview(self):
        clave = self._clave_tipo()
        self._var_estado.set("Cargando datos…")
        self.update_idletasks()
        try:
            self._datos = REPORTES[clave]()
        except Exception as e:
            self._var_estado.set(f"Error al cargar datos: {e}")
            messagebox.showerror("Error", str(e), parent=self)
            return

        # KPIs
        for w in self._frame_kpis.winfo_children():
            w.destroy()
        if self._datos.get("kpis"):
            for kpi in self._datos["kpis"]:
                card = tk.Frame(
                    self._frame_kpis, bg="#FFFFFF",
                    highlightbackground="#E5D6B3", highlightthickness=1,
                    padx=12, pady=6,
                )
                card.pack(side="left", padx=(0, 8), pady=6)
                tk.Label(card, text=kpi["valor"],
                         font=("Helvetica", 13, "bold"),
                         bg="#FFFFFF", fg=COLOR_PRIMARIO).pack(anchor="w")
                tk.Label(card, text=kpi["etiqueta"],
                         font=("Helvetica", 8),
                         bg="#FFFFFF", fg=COLOR_TEXTO_SECUNDARIO).pack(anchor="w")

        # Tabla
        columnas = self._datos["columnas"]
        self._tree.configure(columns=columnas)
        for col in columnas:
            self._tree.heading(col, text=col)
            self._tree.column(col, width=max(100, len(col) * 9), minwidth=60, anchor="w")

        self._tree.delete(*self._tree.get_children())
        for fila in self._datos["filas"]:
            self._tree.insert("", "end", values=fila)

        n = len(self._datos["filas"])
        nombre = NOMBRES_LEGIBLES[clave]
        self._var_estado.set(
            f"Vista previa de «{nombre}» — "
            f"{n} registro{'s' if n != 1 else ''} encontrado{'s' if n != 1 else ''}."
        )
        self._btn_guardar.configure(state="normal")

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

        # Diálogo nativo del sistema operativo
        self.grab_release()   # liberar foco modal para que el diálogo OS pueda abrirse
        ruta_str = _guardar_nativo(
            titulo=f"Guardar reporte de {NOMBRES_LEGIBLES[clave]}",
            nombre_sugerido=nombre_sugerido,
            ext=ext,
            desc=desc_tipo,
        )
        self.grab_set()       # restaurar modal

        if not ruta_str:
            return            # usuario canceló

        ruta = Path(ruta_str)
        try:
            if ext == "pdf":
                guardar_pdf(self._datos, ruta)
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
