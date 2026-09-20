"""
test_demanda_recursiva.py
=========================
Pruebas del pronóstico de demanda a varios días (app/ia/demanda_features.py
y app/ia/demanda_prediction.py). No usan base de datos ni interfaz.

Regresión del bug: el pronóstico a 7/14/30 días NO era recursivo. Los días
futuros se rellenaban con 0.0 y nunca se reemplazaban por la predicción, así
que desde el 2.º día el modelo veía lag_1 = 0 y una media móvil que caía a
cero, y la demanda proyectada (y con ella la reposición de insumos) quedaba
sesgada a la baja.
"""

import numpy as np
import pandas as pd
import pytest

from app.ia import demanda_prediction
from app.ia.demanda_features import (
    COLUMNAS_FEATURES, construir_features, construir_features_futuro,
    features_de_un_dia,
)


def _historia(valores, inicio="2026-01-01"):
    return pd.DataFrame({
        "fecha": pd.date_range(inicio, periods=len(valores), freq="D"),
        "cantidad": [float(v) for v in valores],
    })


def _persistencia(fila):
    """Predictor de juguete: «mañana = ayer»."""
    return float(fila["lag_1"].iloc[0])


def test_los_dias_futuros_usan_la_prediccion_del_dia_anterior():
    futuro = construir_features_futuro(_historia([100] * 60), 14, _persistencia)

    # Antes del arreglo: lag_1 = 0 desde el 2.º día y media_7 = 0 al día 8.
    assert futuro["lag_1"].tolist() == [100.0] * 14
    assert futuro["media_7"].tolist() == [100.0] * 14
    assert futuro["pred_cantidad"].tolist() == [100.0] * 14


def test_cada_prediccion_realimenta_los_lags_siguientes():
    # Predictor «ayer + 1»: si la realimentación funciona, sube 1 por día.
    futuro = construir_features_futuro(
        _historia([100] * 30), 10, lambda fila: fila["lag_1"].iloc[0] + 1)
    assert futuro["pred_cantidad"].tolist() == [101.0 + i for i in range(10)]
    # lag_7 del día 8 ya es una PREDICCIÓN (la del día 1), no historia real.
    assert futuro["lag_7"].iloc[7] == futuro["pred_cantidad"].iloc[0]
    # ...y el del día 3 todavía es historia real.
    assert futuro["lag_7"].iloc[2] == 100.0


def test_una_prediccion_negativa_se_recorta_y_no_contamina_los_dias_siguientes():
    futuro = construir_features_futuro(_historia([10] * 30), 5, lambda fila: -50.0)
    assert (futuro["pred_cantidad"] == 0.0).all()
    assert (futuro["lag_1"].iloc[1:] == 0.0).all()      # 0, no -50


def test_features_futuras_son_identicas_a_las_del_entrenamiento():
    """Train/serve skew: para el día que sigue a una serie, la fila que
    construye el pronóstico debe coincidir con la que construir_features()
    habría producido al entrenar con ese día ya conocido."""
    rng = np.random.default_rng(7)
    base = rng.normal(100, 20, 60).round(1)
    siguiente = 137.0

    entrenamiento = construir_features(_historia(list(base) + [siguiente])).iloc[-1]
    fila_futura = features_de_un_dia(list(base), pd.Timestamp("2026-01-01") + pd.Timedelta(days=60))

    for col in COLUMNAS_FEATURES:
        assert fila_futura[col] == pytest.approx(entrenamiento[col], nan_ok=True), col


def test_historia_corta_deja_nan_donde_el_entrenamiento_tambien():
    """Con 10 días de historia, lag_14 y lag_28 no existen: NaN (que XGBoost
    trata como dato faltante), no un 0 inventado."""
    fila = features_de_un_dia([5.0] * 10, pd.Timestamp("2026-02-01"))
    assert np.isnan(fila["lag_14"]) and np.isnan(fila["lag_28"])
    assert fila["lag_7"] == 5.0


# ── predecir_demanda de punta a punta (con un modelo falso) ────────────

class _ModeloPersistencia:
    def predict(self, X):
        return np.asarray(X["lag_1"], dtype=float)


def _parchear_motor(monkeypatch, valores):
    monkeypatch.setattr(demanda_prediction, "diagnostico_historial",
                        lambda _pid: {"suficiente_baseline": True, "suficiente_ml": True, "mensaje": ""})
    monkeypatch.setattr(demanda_prediction, "obtener_serie_diaria", lambda _pid: _historia(valores))
    monkeypatch.setattr(demanda_prediction, "modelo_disponible", lambda: True)
    monkeypatch.setattr(demanda_prediction, "cargar_modelos", lambda: (_ModeloPersistencia(), None))
    monkeypatch.setattr(demanda_prediction, "leer_metadata", lambda: {})


@pytest.mark.parametrize("horizonte", [7, 14, 30])
def test_predecir_demanda_ml_no_se_hunde_con_el_horizonte(monkeypatch, horizonte):
    _parchear_motor(monkeypatch, [100] * 60)
    r = demanda_prediction.predecir_demanda(1, horizonte)
    assert r["exito"] and r["usando_ml"]
    assert r["pred_cantidad"] == [100.0] * horizonte
    assert r["demanda_total"] == 100.0 * horizonte
    assert r["demanda_min"] == r["demanda_max"] == 100.0


def test_modelo_xgboost_real_mantiene_el_nivel_reciente_a_30_dias():
    """Con el XGBoost real sobre una serie cuyo nivel cambia por tramos
    (50, 150, 80, ... y termina estable en ~150), el pronóstico a 30 días
    debe quedarse cerca de 150. Con el código anterior (días futuros en 0)
    el mismo modelo daba ~96/día, un 36 % por debajo: el modelo ya no veía
    el nivel reciente. (En una serie estable sin tramos el modelo ignora
    los lags y el bug no se nota: por eso esta prueba usa niveles.)"""
    pytest.importorskip("xgboost")
    from app.ia.demanda_model import ModeloXGBoost

    rng = np.random.default_rng(3)
    tramos = [50, 150, 80, 200, 60, 180, 100, 160]
    valores = np.concatenate([rng.normal(n, 5, 30) for n in tramos]
                             + [rng.normal(150, 5, 30)]).round(1)
    historia = _historia(valores)
    feats = construir_features(historia)
    modelo = ModeloXGBoost(n_estimators=200, n_jobs=1).fit(feats, feats["cantidad"].values)

    futuro = construir_features_futuro(historia, 30, lambda fila: modelo.predict(fila)[0])
    assert futuro["pred_cantidad"].mean() == pytest.approx(150, abs=15)
    assert futuro["pred_cantidad"].min() > 100
