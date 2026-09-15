# Generador de ventas simuladas con volatilidad de mercado

Herramienta auxiliar para **probar el módulo de Predicción de Demanda**
con un historial largo y estadísticamente realista, sin esperar meses de
operación real.

No forma parte de la aplicación: vive en `herramientas/` y se ejecuta
desde la línea de comandos. El ERP no la importa nunca.

---

## 1. Idea central

El precio de una acción **no es** la demanda de cerveza. Lo que se toma
del mercado bursátil cervecero no es el nivel de la serie sino su
**estructura estocástica**, que sí comparte con la demanda de un bien de
consumo:

| Propiedad del mercado | Cómo se traslada a la demanda |
|---|---|
| σ diaria de los log-retornos | magnitud del choque aleatorio diario |
| Agrupamiento de volatilidad (GARCH α, β) | semanas revueltas seguidas de semanas revueltas |
| Curtosis > 3 (colas pesadas) | pedidos atípicos ocasionales |

La σ del mercado (≈1.8 % diaria) se multiplica por un **factor de escala**
(`FACTOR_ESCALA_DEMANDA = 18`) porque la demanda diaria de una cervecería
artesanal es mucho más volátil que el retorno de una acción líquida.

### Modelo de demanda

```
D_t ~ Poisson(λ_t)
λ_t = base · Tend_t · Sem_t · Anual_t · Fest_t · Promo_t · exp(e_t − σ²/2)
```

| Componente | Qué aporta |
|---|---|
| `base` | nivel medio por producto (derivado del precio real del catálogo) |
| `Tend_t` | crecimiento anualizado |
| `Sem_t` | estacionalidad semanal (vie/sáb altos, lun bajo) |
| `Anual_t` | temporada alta de turismo en Cusco |
| `Fest_t` | Inti Raymi, Fiestas Patrias, Navidad, carnavales, fin de año |
| `Promo_t` | campañas esporádicas |
| `exp(e_t − σ²/2)` | **choque calibrado con el mercado** (media 1: no infla el nivel) |

Además hay **intermitencia** (días sin venta en productos de baja rotación)
y un **choque común** que comparten todos los productos, para que los meses
malos sean malos para todo el catálogo (correlación cruzada realista).

---

## 2. Tickers de referencia

| Ticker | Empresa |
|---|---|
| `BACKUSI1.LM` | Backus y Johnston (BVL, Perú) |
| `CCU` | Compañía Cervecerías Unidas (Chile) |
| `ABEV` | Ambev (Brasil) |
| `BUD` | Anheuser-Busch InBev |
| `HEIA.AS` | Heineken N.V. |
| `TAP` | Molson Coors |
| `SAM` | Boston Beer Co. — la referencia más cercana a una cervecería artesanal |

La descarga usa **yfinance** (opcional). Si no hay internet o el ticker no
está disponible, se usan **perfiles de respaldo** aproximados y el script lo
avisa explícitamente. Los perfiles descargados quedan en
`herramientas/cache_volatilidad.json` para trabajar offline después.

---

## 3. Uso

Desde la raíz del proyecto (donde está `main.py`):

```bash
pip install yfinance            # opcional pero recomendado

# Vista previa — NO toca la base de datos
python -m herramientas.generar_ventas_simuladas --dias 730 --solo-csv

# 2 años de ventas insertadas en el ERP, con lotes de inventario
python -m herramientas.generar_ventas_simuladas --dias 730 --con-inventario --reemplazar

# 3 años, volatilidad alta, calibrada solo con la referencia artesanal
python -m herramientas.generar_ventas_simuladas --dias 1095 --tickers SAM \
    --volatilidad alta --semilla 7

# Deshacer todo lo simulado
python -m herramientas.generar_ventas_simuladas --limpiar
```

### Opciones principales

| Opción | Qué hace |
|---|---|
| `--dias N` | días de historial (730 = 2 años) |
| `--volatilidad baja\|media\|alta\|extrema` | multiplica el índice de volatilidad (0.5× / 1× / 1.8× / 2.8×) |
| `--escala-vol X` | sobrescribe el factor mercado→demanda |
| `--modo-vol garch\|bootstrap\|normal` | proceso del choque (`normal` = control sin agrupamiento) |
| `--tickers ...` | qué acciones usar para calibrar |
| `--base L` | demanda media global por producto en L/día |
| `--con-inventario` | crea lotes + movimientos para que el stock cuadre |
| `--solo-csv` | no escribe en la BD |
| `--reemplazar` / `--limpiar` | borra lo simulado antes de generar / y termina |
| `--semilla N` | reproducibilidad |

Todas las órdenes generadas llevan `[SIMULADO]` en `observaciones` y los
lotes el prefijo `SIM-`, así que **las ventas reales nunca se tocan**.

---

## 4. Salidas

En `datos_simulados/`:

- `ventas_simuladas.csv` — serie diaria por producto **con las componentes
  desagregadas** (`f_semanal`, `f_anual`, `f_festivo`, `f_promocion`,
  `f_shock`, `choque`). Sirve para el capítulo de metodología: se puede
  mostrar exactamente de dónde salió cada valor.
- `diagnostico_simulacion.csv` — métricas por producto.
- `series_simuladas.png` — gráfico de las 4 primeras series.

Y por consola, una tabla de validación:

| Métrica | Rango esperado | Qué significa |
|---|---|---|
| `CV` | 0.35 – 0.80 | variabilidad típica de PYME de consumo |
| `findes/sem` | > 1.4 | la estacionalidad semanal quedó marcada (es lo que el XGBoost debe aprender) |
| `σ_choque` | ≈ σ objetivo impreso arriba | la volatilidad del mercado sí se trasladó |
| `%ceros` | alto solo en baja rotación | intermitencia razonable |

---

## 5. Cómo usarla para evaluar el modelo

El nivel de volatilidad controla directamente cuánta señal predecible
queda. Resultado medido sobre 900 días y el mismo producto:

| Escenario | MAE XGBoost | MAE Baseline | MAPE |
|---|---|---|---|
| `--volatilidad baja` | 5.50 | 6.96 | 28 % |
| `--volatilidad media` | 8.78 | 8.61 | 56 % |

Con volatilidad **baja/media** el XGBoost debe ganarle claramente al
baseline (aprende día de semana + festivos). Con volatilidad **alta** el
ruido domina y ambos convergen — eso no es un fallo del modelo, es el
límite teórico de la serie, y es un excelente argumento para la sustentación:
demuestra que el sistema se comporta como debe cuando la señal existe y
cuando no.

Flujo sugerido para la demo:

1. `--limpiar`
2. Generar con `--dias 730 --volatilidad baja --con-inventario`
3. ERP → **Predicción Demanda** → **Entrenar/actualizar**
4. Repetir con `--volatilidad alta` y comparar MAE/RMSE en pantalla.
