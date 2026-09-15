"""
volatilidad_mercado.py
======================
Calibración del "índice de volatilidad" que se usará para simular las
ventas, a partir de datos reales de la bolsa de valores de empresas
cerveceras (locales y globales).

IMPORTANTE — justificación metodológica
---------------------------------------
El precio de una acción NO es la demanda de cerveza. Lo que se toma
prestado del mercado bursátil NO es el nivel de la serie, sino su
*estructura estocástica*:

  1. La magnitud del ruido        → sigma diaria de los log-retornos
  2. El agrupamiento de volatilidad → efecto GARCH (días agitados
     vienen seguidos de días agitados)
  3. Las colas pesadas            → curtosis > 3 (shocks extremos
     más frecuentes que en una normal)

Esas tres propiedades sí son compartidas por la demanda real de un
bien de consumo: hay semanas tranquilas y semanas revueltas, y de vez
en cuando aparece un pedido anómalo. Por eso se usa el mercado como
"fuente de realismo estadístico", no como predictor de ventas.

La sigma del mercado se multiplica además por FACTOR_ESCALA_DEMANDA
porque la demanda diaria de una cervecería artesanal es bastante más
volátil que el retorno diario de una acción líquida.

Tickers usados
--------------
Local (Perú, BVL):
  BACKUSI1.LM  Unión de Cervecerías Peruanas Backus y Johnston
  CCU          Compañía Cervecerías Unidas (Chile, referencia andina)
Global:
  ABEV         Ambev (Brasil / LatAm)
  BUD          Anheuser-Busch InBev
  HEIA.AS      Heineken N.V. (Euronext Ámsterdam)
  TAP          Molson Coors
  SAM          Boston Beer Company (cerveza artesanal — la referencia
               más parecida al caso de Cervecera Cusco)

La descarga usa yfinance. Si no hay internet o yfinance no está
instalado, el módulo cae a perfiles de respaldo (ver
PERFILES_RESPALDO) y lo avisa explícitamente.
"""

from __future__ import annotations

import json
import math
from dataclasses import dataclass, asdict
from datetime import date, timedelta
from pathlib import Path
from typing import Optional

import numpy as np

# ── Tickers de referencia ─────────────────────────────────────────
TICKERS_LOCALES = {
    "BACKUSI1.LM": "Backus y Johnston (BVL, Perú)",
    "CCU": "Compañía Cervecerías Unidas (Chile)",
}

TICKERS_GLOBALES = {
    "ABEV": "Ambev S.A. (Brasil)",
    "BUD": "Anheuser-Busch InBev",
    "HEIA.AS": "Heineken N.V.",
    "TAP": "Molson Coors Beverage Co.",
    "SAM": "Boston Beer Company (artesanal)",
}

TICKERS_TODOS = {**TICKERS_LOCALES, **TICKERS_GLOBALES}

# Cuánto más volátil es la demanda diaria de una cervecería artesanal
# respecto al retorno diario de una acción cervecera. Valor empírico
# de referencia: el CV diario de ventas en PYMES de consumo suele
# estar entre 25% y 60%, mientras la sigma diaria bursátil ronda 1–2%.
FACTOR_ESCALA_DEMANDA = 18.0

# Perfiles de respaldo: valores APROXIMADOS de referencia, usados solo
# cuando no se pueden descargar datos reales. Se sobrescriben en cuanto
# la descarga funciona.
PERFILES_RESPALDO = {
    "BACKUSI1.LM": dict(sigma_anual=0.22, curtosis=6.0, alpha=0.10, beta=0.85),
    "CCU":         dict(sigma_anual=0.28, curtosis=5.5, alpha=0.09, beta=0.86),
    "ABEV":        dict(sigma_anual=0.30, curtosis=5.0, alpha=0.08, beta=0.88),
    "BUD":         dict(sigma_anual=0.28, curtosis=5.5, alpha=0.09, beta=0.87),
    "HEIA.AS":     dict(sigma_anual=0.25, curtosis=5.0, alpha=0.08, beta=0.88),
    "TAP":         dict(sigma_anual=0.27, curtosis=5.5, alpha=0.09, beta=0.87),
    "SAM":         dict(sigma_anual=0.38, curtosis=6.5, alpha=0.11, beta=0.83),
}

RUTA_CACHE = Path(__file__).resolve().parent / "cache_volatilidad.json"


# ══════════════════════════════════════════════════════════════════
#  Perfil de volatilidad
# ══════════════════════════════════════════════════════════════════
@dataclass
class PerfilVolatilidad:
    """Resumen estadístico de la volatilidad de un activo (o cesta)."""

    etiqueta: str
    sigma_diaria: float      # desviación estándar diaria de log-retornos
    sigma_anual: float       # sigma_diaria * sqrt(252)
    curtosis: float          # curtosis (3 = normal)
    asimetria: float
    persistencia: float      # alpha + beta del GARCH(1,1)
    alpha: float
    beta: float
    omega: float
    n_observaciones: int
    fuente: str              # "mercado" | "respaldo"
    retornos_estandarizados: Optional[list] = None  # para bootstrap

    def resumen(self) -> str:
        return (
            f"{self.etiqueta:<34} σ_diaria={self.sigma_diaria*100:5.2f}%  "
            f"σ_anual={self.sigma_anual*100:5.1f}%  curtosis={self.curtosis:4.1f}  "
            f"α+β={self.persistencia:.3f}  n={self.n_observaciones}  [{self.fuente}]"
        )

    def a_dict(self, incluir_retornos: bool = False) -> dict:
        d = asdict(self)
        if not incluir_retornos:
            d.pop("retornos_estandarizados", None)
        return d


# ══════════════════════════════════════════════════════════════════
#  Descarga de precios
# ══════════════════════════════════════════════════════════════════
def descargar_retornos(
    tickers: Optional[list[str]] = None,
    anios: int = 5,
    verbose: bool = True,
) -> dict[str, np.ndarray]:
    """
    Descarga precios de cierre ajustado y devuelve los log-retornos
    diarios de cada ticker. Devuelve {} si yfinance no está disponible
    o si ninguna descarga tuvo éxito.
    """
    tickers = tickers or list(TICKERS_TODOS.keys())
    try:
        import yfinance as yf
    except ImportError:
        if verbose:
            print("  ! yfinance no está instalado (pip install yfinance).")
            print("    Se usarán perfiles de respaldo.")
        return {}

    fin = date.today()
    inicio = fin - timedelta(days=int(anios * 365.25))
    retornos: dict[str, np.ndarray] = {}

    for tk in tickers:
        try:
            df = yf.download(
                tk, start=inicio, end=fin, progress=False,
                auto_adjust=True, threads=False,
            )
            if df is None or df.empty or "Close" not in df:
                if verbose:
                    print(f"  · {tk:<12} sin datos en Yahoo Finance — se omite.")
                continue
            precios = df["Close"].dropna().to_numpy().ravel().astype(float)
            if len(precios) < 120:
                if verbose:
                    print(f"  · {tk:<12} historial muy corto ({len(precios)}) — se omite.")
                continue
            r = np.diff(np.log(precios))
            r = r[np.isfinite(r)]
            retornos[tk] = r
            if verbose:
                print(f"  · {tk:<12} {len(r)} retornos descargados.")
        except Exception as exc:  # red caída, ticker inválido, etc.
            if verbose:
                print(f"  · {tk:<12} error al descargar: {exc}")

    return retornos


# ══════════════════════════════════════════════════════════════════
#  Estimación GARCH(1,1)
# ══════════════════════════════════════════════════════════════════
def estimar_garch(r: np.ndarray) -> tuple[float, float, float]:
    """
    Estima (omega, alpha, beta) de un GARCH(1,1) por máxima
    verosimilitud gaussiana. Si scipy no está disponible o la
    optimización falla, devuelve valores típicos de mercado.

    Modelo:  r_t = sigma_t * z_t
             sigma_t^2 = omega + alpha * r_{t-1}^2 + beta * sigma_{t-1}^2
    """
    r = np.asarray(r, dtype=float)
    r = r - r.mean()
    var_muestral = float(np.var(r))
    if var_muestral <= 0:
        return 1e-6, 0.08, 0.88

    def neg_log_ver(params):
        omega, alpha, beta = params
        if omega <= 0 or alpha < 0 or beta < 0 or alpha + beta >= 0.999:
            return 1e12
        sigma2 = np.empty(len(r))
        sigma2[0] = var_muestral
        for t in range(1, len(r)):
            sigma2[t] = omega + alpha * r[t - 1] ** 2 + beta * sigma2[t - 1]
        sigma2 = np.maximum(sigma2, 1e-12)
        return 0.5 * np.sum(np.log(sigma2) + r**2 / sigma2)

    try:
        from scipy.optimize import minimize

        p0 = [var_muestral * 0.05, 0.08, 0.88]
        res = minimize(
            neg_log_ver, p0, method="Nelder-Mead",
            options={"maxiter": 2000, "xatol": 1e-10, "fatol": 1e-8},
        )
        omega, alpha, beta = res.x
        if not (omega > 0 and alpha >= 0 and beta >= 0 and alpha + beta < 0.999):
            raise ValueError("parámetros fuera de rango")
        return float(omega), float(alpha), float(beta)
    except Exception:
        alpha, beta = 0.08, 0.88
        omega = var_muestral * (1 - alpha - beta)
        return float(max(omega, 1e-10)), alpha, beta


def _curtosis(x: np.ndarray) -> float:
    x = np.asarray(x, float)
    s = x.std()
    return float(np.mean(((x - x.mean()) / s) ** 4)) if s > 0 else 3.0


def _asimetria(x: np.ndarray) -> float:
    x = np.asarray(x, float)
    s = x.std()
    return float(np.mean(((x - x.mean()) / s) ** 3)) if s > 0 else 0.0


def construir_perfil(etiqueta: str, r: np.ndarray, fuente: str = "mercado") -> PerfilVolatilidad:
    """Construye el PerfilVolatilidad a partir de una serie de log-retornos."""
    r = np.asarray(r, float)
    sigma_d = float(r.std(ddof=1))
    omega, alpha, beta = estimar_garch(r)

    # Residuos estandarizados por la volatilidad condicional GARCH:
    # sirven para el bootstrap (conservan colas pesadas sin copiar
    # el agrupamiento, que se reintroduce por el propio GARCH).
    sigma2 = np.empty(len(r))
    sigma2[0] = np.var(r)
    for t in range(1, len(r)):
        sigma2[t] = omega + alpha * r[t - 1] ** 2 + beta * sigma2[t - 1]
    z = r / np.sqrt(np.maximum(sigma2, 1e-12))
    z = z / z.std()

    return PerfilVolatilidad(
        etiqueta=etiqueta,
        sigma_diaria=sigma_d,
        sigma_anual=sigma_d * math.sqrt(252),
        curtosis=_curtosis(r),
        asimetria=_asimetria(r),
        persistencia=alpha + beta,
        alpha=alpha,
        beta=beta,
        omega=omega,
        n_observaciones=len(r),
        fuente=fuente,
        retornos_estandarizados=z.tolist(),
    )


def perfil_de_respaldo(ticker: str) -> PerfilVolatilidad:
    """Perfil aproximado usado cuando no hay conexión al mercado."""
    base = PERFILES_RESPALDO.get(ticker, PERFILES_RESPALDO["SAM"])
    sigma_d = base["sigma_anual"] / math.sqrt(252)
    alpha, beta = base["alpha"], base["beta"]
    omega = sigma_d**2 * (1 - alpha - beta)
    # Residuos t-Student estandarizados para imitar las colas pesadas
    gl = max(4.5, 6.0 / max(base["curtosis"] - 3.0, 0.5) + 4.0)
    rng = np.random.default_rng(20250915)
    z = rng.standard_t(df=gl, size=1500)
    z = z / z.std()
    return PerfilVolatilidad(
        etiqueta=f"{ticker} — {TICKERS_TODOS.get(ticker, 'referencia')}",
        sigma_diaria=sigma_d,
        sigma_anual=base["sigma_anual"],
        curtosis=base["curtosis"],
        asimetria=-0.2,
        persistencia=alpha + beta,
        alpha=alpha,
        beta=beta,
        omega=omega,
        n_observaciones=0,
        fuente="respaldo",
        retornos_estandarizados=z.tolist(),
    )


# ══════════════════════════════════════════════════════════════════
#  API principal
# ══════════════════════════════════════════════════════════════════
def obtener_perfiles(
    tickers: Optional[list[str]] = None,
    anios: int = 5,
    usar_cache: bool = True,
    forzar_descarga: bool = False,
    verbose: bool = True,
) -> dict[str, PerfilVolatilidad]:
    """
    Devuelve un perfil de volatilidad por ticker.

    Orden de preferencia: descarga real → caché local → respaldo.
    """
    tickers = tickers or list(TICKERS_TODOS.keys())

    if usar_cache and not forzar_descarga and RUTA_CACHE.exists():
        perfiles = _cargar_cache(tickers)
        if perfiles:
            if verbose:
                print(f"  Perfiles leídos de caché ({RUTA_CACHE.name}).")
            return perfiles

    if verbose:
        print("  Descargando series bursátiles de empresas cerveceras...")
    retornos = descargar_retornos(tickers, anios=anios, verbose=verbose)

    perfiles: dict[str, PerfilVolatilidad] = {}
    for tk in tickers:
        if tk in retornos:
            perfiles[tk] = construir_perfil(
                f"{tk} — {TICKERS_TODOS.get(tk, '')}", retornos[tk], fuente="mercado"
            )
        else:
            perfiles[tk] = perfil_de_respaldo(tk)

    if usar_cache and any(p.fuente == "mercado" for p in perfiles.values()):
        _guardar_cache(perfiles)

    return perfiles


def perfil_cesta(perfiles: dict[str, PerfilVolatilidad],
                 etiqueta: str = "Cesta cervecera") -> PerfilVolatilidad:
    """
    Promedia varios perfiles en uno solo (índice sectorial sintético).
    Útil para darle a toda la empresa un "clima de mercado" común.
    """
    vivos = [p for p in perfiles.values()]
    if not vivos:
        return perfil_de_respaldo("SAM")

    n = len(vivos)
    sigma_d = float(np.mean([p.sigma_diaria for p in vivos]))
    alpha = float(np.mean([p.alpha for p in vivos]))
    beta = float(np.mean([p.beta for p in vivos]))
    z = np.concatenate([np.asarray(p.retornos_estandarizados or [], float) for p in vivos])
    if z.size == 0:
        z = np.random.default_rng(7).standard_t(6, 1000)
    z = z / z.std()

    return PerfilVolatilidad(
        etiqueta=etiqueta,
        sigma_diaria=sigma_d,
        sigma_anual=sigma_d * math.sqrt(252),
        curtosis=float(np.mean([p.curtosis for p in vivos])),
        asimetria=float(np.mean([p.asimetria for p in vivos])),
        persistencia=alpha + beta,
        alpha=alpha,
        beta=beta,
        omega=sigma_d**2 * (1 - alpha - beta),
        n_observaciones=int(np.sum([p.n_observaciones for p in vivos])),
        fuente="mercado" if any(p.fuente == "mercado" for p in vivos) else "respaldo",
        retornos_estandarizados=z.tolist(),
    )


# ── Caché en disco ────────────────────────────────────────────────
def _guardar_cache(perfiles: dict[str, PerfilVolatilidad]) -> None:
    datos = {
        "generado": date.today().isoformat(),
        "perfiles": {tk: p.a_dict(incluir_retornos=True) for tk, p in perfiles.items()},
    }
    RUTA_CACHE.write_text(json.dumps(datos, indent=2), encoding="utf-8")


def _cargar_cache(tickers: list[str]) -> dict[str, PerfilVolatilidad]:
    try:
        datos = json.loads(RUTA_CACHE.read_text(encoding="utf-8"))
        guardados = datos.get("perfiles", {})
        salida = {}
        for tk in tickers:
            if tk in guardados:
                salida[tk] = PerfilVolatilidad(**guardados[tk])
        return salida if len(salida) == len(tickers) else {}
    except Exception:
        return {}


if __name__ == "__main__":
    perfiles = obtener_perfiles()
    print()
    for p in perfiles.values():
        print("  " + p.resumen())
    print("\n  " + perfil_cesta(perfiles).resumen())
