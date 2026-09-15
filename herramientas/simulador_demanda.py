"""
simulador_demanda.py
====================
Motor de simulación de demanda diaria para productos terminados de la
cervecería. No toca la base de datos: solo produce series temporales.

Modelo multiplicativo
---------------------
    D_t = Poisson( lambda_t )      con
    lambda_t = base * Tend_t * Sem_t * Anual_t * Fest_t * Promo_t * Shock_t

donde:
  base     nivel medio de litros/día del producto
  Tend_t   tendencia de crecimiento (o caída) anualizada
  Sem_t    estacionalidad semanal (viernes/sábado altos, lunes bajo)
  Anual_t  estacionalidad anual (temporada alta de turismo en Cusco)
  Fest_t   calendario de feriados y festividades peruanas/cusqueñas
  Promo_t  campañas/promociones esporádicas
  Shock_t  choque estocástico calibrado con la volatilidad del sector
           cervecero bursátil:  Shock_t = exp(e_t - sigma_t^2/2)

El término Shock_t es el que incorpora el "índice de volatilidad":
e_t se genera con un GARCH(1,1) cuyos parámetros (alpha, beta) y cuya
sigma salen de los retornos reales de acciones cerveceras. Eso produce
agrupamiento de volatilidad y colas pesadas, igual que en la demanda
real. La corrección -sigma^2/2 mantiene E[Shock_t] = 1, de modo que la
volatilidad NO infla el nivel medio de ventas.

Además se modela la intermitencia: productos de baja rotación tienen
días sin ninguna venta (proceso Bernoulli independiente).
"""

from __future__ import annotations

import math
from dataclasses import dataclass, field
from datetime import date, timedelta
from typing import Optional

import numpy as np
import pandas as pd

from herramientas.volatilidad_mercado import (
    PerfilVolatilidad,
    FACTOR_ESCALA_DEMANDA,
)

# ══════════════════════════════════════════════════════════════════
#  Calendario peruano / cusqueño
# ══════════════════════════════════════════════════════════════════
# (mes, día) -> multiplicador de demanda
FERIADOS_FIJOS = {
    (1, 1):   1.55,   # Año Nuevo
    (5, 1):   1.30,   # Día del Trabajo
    (6, 24):  2.10,   # Inti Raymi — pico turístico de Cusco
    (6, 23):  1.70,   # Víspera de Inti Raymi
    (6, 25):  1.45,
    (7, 28):  2.00,   # Fiestas Patrias
    (7, 29):  1.85,
    (7, 27):  1.50,   # víspera
    (8, 30):  1.25,   # Santa Rosa de Lima
    (10, 8):  1.15,   # Combate de Angamos
    (11, 1):  1.20,   # Todos los Santos
    (12, 8):  1.25,   # Inmaculada Concepción
    (12, 24): 1.90,   # Nochebuena
    (12, 25): 1.35,   # Navidad
    (12, 31): 2.20,   # Fin de año
}

# Ventanas de festividad prolongada (mes, día_inicio, día_fin, factor)
VENTANAS_FESTIVAS = [
    (6, 1, 30, 1.25),    # mes jubilar del Cusco
    (7, 20, 31, 1.20),   # semana de Fiestas Patrias
    (12, 20, 31, 1.30),  # campaña navideña
    (2, 10, 25, 1.15),   # carnavales
]

# Estacionalidad semanal: lunes=0 ... domingo=6
FACTOR_SEMANAL = np.array([0.72, 0.80, 0.92, 1.05, 1.45, 1.70, 1.10])


@dataclass
class ConfigProducto:
    """Parámetros de demanda de un producto terminado."""

    producto_id: int
    nombre: str
    base_diaria: float                 # litros/día promedio
    tendencia_anual: float = 0.08      # +8% al año
    intermitencia: float = 0.05        # prob. de día sin ventas
    sensibilidad_volatilidad: float = 1.0   # multiplica la sigma del sector
    amplitud_anual: float = 0.25       # fuerza de la estacionalidad anual
    fase_anual: float = 172.0          # día del año con el pico (≈21 jun)
    prob_promocion: float = 0.02       # prob. diaria de campaña
    efecto_promocion: float = 1.8


@dataclass
class ResultadoSimulacion:
    """Serie simulada + componentes para diagnóstico."""

    config: ConfigProducto
    df: pd.DataFrame = field(repr=False)
    sigma_efectiva: float = 0.0

    def metricas(self) -> dict:
        y = self.df["cantidad"].to_numpy(float)
        positivos = y[y > 0]
        # volatilidad "estilo mercado" de la demanda: std de log-retornos
        if len(positivos) > 10:
            lr = np.diff(np.log(positivos))
            vol_diaria = float(np.std(lr))
        else:
            vol_diaria = 0.0
        dias_semana = pd.to_datetime(self.df["fecha"]).dt.dayofweek
        fin_semana = y[np.isin(dias_semana, [4, 5])].mean() if len(y) else 0
        entre_semana = y[np.isin(dias_semana, [0, 1, 2])].mean() if len(y) else 0
        sigma_choque = (
            float(np.std(self.df["choque"])) if "choque" in self.df else 0.0
        )
        return {
            "producto": self.config.nombre,
            "sigma_choque": sigma_choque,
            "dias": len(y),
            "media": float(y.mean()),
            "desv": float(y.std()),
            "cv": float(y.std() / y.mean()) if y.mean() else 0.0,
            "min": float(y.min()),
            "max": float(y.max()),
            "pct_ceros": float((y == 0).mean() * 100),
            "vol_log_diaria": vol_diaria,
            "vol_log_anual": vol_diaria * math.sqrt(252),
            "ratio_findesemana": float(fin_semana / entre_semana) if entre_semana else 0.0,
            "total": float(y.sum()),
        }


# ══════════════════════════════════════════════════════════════════
#  Proceso de volatilidad
# ══════════════════════════════════════════════════════════════════
def simular_garch(
    n: int,
    perfil: PerfilVolatilidad,
    rng: np.random.Generator,
    escala: float = FACTOR_ESCALA_DEMANDA,
    modo: str = "garch",
) -> np.ndarray:
    """
    Genera n choques e_t con la estructura de volatilidad del perfil.

    modo="garch"      : GARCH(1,1) con alpha/beta estimados del mercado
                        e innovaciones remuestreadas de los residuos
                        reales (colas pesadas auténticas).
    modo="bootstrap"  : remuestreo por bloques de los retornos reales
                        (conserva tal cual el agrupamiento histórico).
    modo="normal"     : ruido gaussiano homocedástico (control).

    La serie se reescala al final para que su desviación estándar sea
    exactamente sigma_objetivo = sigma_diaria_mercado * escala.
    """
    sigma_objetivo = perfil.sigma_diaria * escala
    z_pool = np.asarray(perfil.retornos_estandarizados or [], float)
    if z_pool.size < 50:
        z_pool = rng.standard_t(6, 500)
        z_pool = z_pool / z_pool.std()

    if modo == "normal":
        e = rng.normal(0.0, 1.0, n)

    elif modo == "bootstrap":
        # bloques de 21 días (≈1 mes bursátil) para conservar racimos
        largo = 21
        bloques = []
        while sum(len(b) for b in bloques) < n:
            i = rng.integers(0, max(1, len(z_pool) - largo))
            bloques.append(z_pool[i:i + largo])
        e = np.concatenate(bloques)[:n]

    else:  # garch
        alpha, beta = perfil.alpha, perfil.beta
        omega = max(perfil.omega, 1e-12)
        var_larga = omega / max(1e-6, 1 - alpha - beta)
        sigma2 = var_larga
        e = np.empty(n)
        idx = rng.integers(0, len(z_pool), n)
        for t in range(n):
            z = z_pool[idx[t]]
            e[t] = math.sqrt(sigma2) * z
            sigma2 = omega + alpha * e[t] ** 2 + beta * sigma2

    s = e.std()
    if s > 0:
        e = e / s * sigma_objetivo
    return e


# ══════════════════════════════════════════════════════════════════
#  Factores determinísticos
# ══════════════════════════════════════════════════════════════════
def factor_festivo(d: date) -> float:
    f = FERIADOS_FIJOS.get((d.month, d.day), 1.0)
    for mes, ini, fin, mult in VENTANAS_FESTIVAS:
        if d.month == mes and ini <= d.day <= fin:
            f *= mult
    return f


def factor_anual(d: date, amplitud: float, fase: float) -> float:
    doy = d.timetuple().tm_yday
    return 1.0 + amplitud * math.cos(2 * math.pi * (doy - fase) / 365.25)


# ══════════════════════════════════════════════════════════════════
#  Simulación de un producto
# ══════════════════════════════════════════════════════════════════
def simular_producto(
    config: ConfigProducto,
    fecha_inicio: date,
    fecha_fin: date,
    perfil: PerfilVolatilidad,
    rng: np.random.Generator,
    escala_volatilidad: float = FACTOR_ESCALA_DEMANDA,
    modo_volatilidad: str = "garch",
    choque_comun: Optional[np.ndarray] = None,
    peso_comun: float = 0.45,
) -> ResultadoSimulacion:
    """
    Simula la demanda diaria de un producto entre dos fechas.

    choque_comun : serie de choques compartida por todos los productos
                   ("clima de mercado" de la empresa). Se mezcla con el
                   choque idiosincrásico del producto con peso
                   peso_comun. Esto genera correlación realista entre
                   productos: los meses malos son malos para todos.
    """
    fechas = pd.date_range(fecha_inicio, fecha_fin, freq="D")
    n = len(fechas)

    e_prop = simular_garch(
        n, perfil, rng,
        escala=escala_volatilidad * config.sensibilidad_volatilidad,
        modo=modo_volatilidad,
    )
    if choque_comun is not None and len(choque_comun) == n:
        # El choque común viene normalizado (std=1): se lleva a la
        # misma escala del choque propio antes de mezclarlos, para que
        # la volatilidad total siga siendo la calibrada del mercado.
        s_prop = e_prop.std() or 1.0
        s_com = choque_comun.std() or 1.0
        comun = choque_comun / s_com * s_prop
        e = peso_comun * comun + math.sqrt(max(0.0, 1 - peso_comun**2)) * e_prop
    else:
        e = e_prop

    sigma_ef = float(np.std(e))

    filas = []
    for i, ts in enumerate(fechas):
        d = ts.date()
        t_anios = i / 365.25
        f_tend = (1.0 + config.tendencia_anual) ** t_anios
        f_sem = FACTOR_SEMANAL[d.weekday()]
        f_anual = factor_anual(d, config.amplitud_anual, config.fase_anual)
        f_fest = factor_festivo(d)
        f_promo = config.efecto_promocion if rng.random() < config.prob_promocion else 1.0
        # E[exp(e - s^2/2)] = 1  → la volatilidad no desplaza la media
        f_shock = math.exp(e[i] - sigma_ef**2 / 2)

        lam = config.base_diaria * f_tend * f_sem * f_anual * f_fest * f_promo * f_shock
        lam = max(lam, 0.0)

        if rng.random() < config.intermitencia:
            cantidad = 0.0
        else:
            cantidad = float(rng.poisson(lam)) if lam > 0 else 0.0

        filas.append({
            "fecha": d,
            "cantidad": cantidad,
            "f_semanal": f_sem,
            "f_anual": f_anual,
            "f_festivo": f_fest,
            "f_promocion": f_promo,
            "f_shock": f_shock,
            "choque": e[i],
        })

    return ResultadoSimulacion(config=config, df=pd.DataFrame(filas), sigma_efectiva=sigma_ef)


def generar_choque_comun(
    n: int, perfil: PerfilVolatilidad, rng: np.random.Generator,
    escala: float = FACTOR_ESCALA_DEMANDA, modo: str = "garch",
) -> np.ndarray:
    """Choque sectorial compartido por todos los productos."""
    e = simular_garch(n, perfil, rng, escala=escala, modo=modo)
    s = e.std()
    return e / s if s > 0 else e   # normalizado: la escala la pone cada producto
