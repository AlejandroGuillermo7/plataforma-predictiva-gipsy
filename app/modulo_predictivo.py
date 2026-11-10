"""
modulo_predictivo.py
--------------------
Módulo principal de la Plataforma de Análisis Predictivo Gipsy (Sprint 2).

Flujo:
    1. Leer el historial de ventas de la base de datos.
    2. Convertirlo en ventas mensuales por variante (producto + talla + color).
    3. Crear las variables de entrada del modelo.
    4. Entrenar y comparar dos algoritmos; elegir el de menor MAE.
    5. Pronosticar el siguiente mes y guardar el resultado en la tabla `prediccion`.

Autores: Equipo 4 - Gestión de Proyectos de Software, ITO.
"""

import pandas as pd
from sklearn.ensemble import RandomForestRegressor
from sklearn.linear_model import LinearRegression
from sklearn.metrics import mean_absolute_error
from sqlalchemy import text

VARIABLES = ["mes_del_anio", "lag_1", "lag_12", "promedio_3"]
MESES_PRUEBA = 3  # últimos meses que se reservan para evaluar el modelo


def leer_ventas(motor) -> pd.DataFrame:
    """Lee las ventas activas (del sistema e históricas) con su variante y fecha."""
    consulta = """
        SELECT dv.id_variante, v.fecha, dv.cantidad
        FROM detalle_venta dv
        JOIN venta v ON v.id_venta = dv.id_venta
        WHERE v.estado = 'Activa'
    """
    return pd.read_sql(consulta, motor, parse_dates=["fecha"])


def ventas_mensuales(ventas: pd.DataFrame) -> pd.DataFrame:
    """Agrupa las piezas vendidas por variante y mes.

    Los meses sin ventas se rellenan con 0 para que la serie de cada
    variante sea continua (necesario para calcular los rezagos).
    """
    ventas = ventas.assign(mes=ventas["fecha"].dt.to_period("M").dt.to_timestamp())
    tabla = ventas.pivot_table(index="mes", columns="id_variante",
                               values="cantidad", aggfunc="sum")
    meses = pd.date_range(tabla.index.min(), tabla.index.max(), freq="MS")
    tabla = tabla.reindex(meses).fillna(0)
    tabla.index.name = "mes"
    return tabla.stack().rename("piezas").reset_index()


def construir_variables(serie: pd.DataFrame) -> pd.DataFrame:
    """Crea las variables de entrada del modelo para cada variante y mes.

    - mes_del_anio: captura la temporada (1 = enero ... 12 = diciembre).
    - lag_1: piezas vendidas el mes anterior.
    - lag_12: piezas vendidas el mismo mes del año anterior (0 si no hay historial).
    - promedio_3: promedio de los tres meses anteriores.
    """
    df = serie.sort_values(["id_variante", "mes"]).copy()
    por_variante = df.groupby("id_variante")["piezas"]
    df["mes_del_anio"] = df["mes"].dt.month
    df["lag_1"] = por_variante.shift(1)
    df["lag_12"] = por_variante.shift(12).fillna(0)
    df["promedio_3"] = por_variante.transform(lambda s: s.shift(1).rolling(3).mean())
    return df


def entrenar_y_elegir(df: pd.DataFrame):
    """Entrena dos algoritmos y devuelve el de menor error absoluto medio (MAE).

    Se usa una división temporal: los últimos MESES_PRUEBA meses se reservan
    para evaluar, porque un pronóstico siempre se hace hacia el futuro.
    """
    datos = df.dropna(subset=VARIABLES + ["piezas"])
    corte = datos["mes"].max() - pd.DateOffset(months=MESES_PRUEBA)
    entrenamiento = datos[datos["mes"] <= corte]
    prueba = datos[datos["mes"] > corte]

    candidatos = {
        "Regresión lineal": LinearRegression(),
        "Random Forest": RandomForestRegressor(n_estimators=200, random_state=42),
    }
    resultados = {}
    for nombre, modelo in candidatos.items():
        modelo.fit(entrenamiento[VARIABLES], entrenamiento["piezas"])
        error = mean_absolute_error(prueba["piezas"], modelo.predict(prueba[VARIABLES]))
        resultados[nombre] = (modelo, error)

    mejor = min(resultados, key=lambda n: resultados[n][1])
    modelo, error = resultados[mejor]
    modelo.fit(datos[VARIABLES], datos["piezas"])  # se reentrena con todos los datos
    errores = {n: round(e, 2) for n, (_, e) in resultados.items()}
    return mejor, modelo, error, errores


def pronosticar_siguiente_mes(serie: pd.DataFrame, modelo) -> pd.DataFrame:
    """Calcula las piezas que se venderán de cada variante el próximo mes."""
    siguiente = serie["mes"].max() + pd.DateOffset(months=1)
    nuevas = pd.DataFrame({"id_variante": serie["id_variante"].unique(),
                           "mes": siguiente, "piezas": float("nan")})
    completo = construir_variables(pd.concat([serie, nuevas], ignore_index=True))
    futuro = completo[completo["mes"] == siguiente].dropna(subset=VARIABLES)
    estimado = modelo.predict(futuro[VARIABLES]).clip(min=0).round().astype(int)
    return futuro.assign(cantidad_estimada=estimado)[["id_variante", "mes", "cantidad_estimada"]]


def guardar_predicciones(pron: pd.DataFrame, algoritmo: str, mae: float, motor) -> int:
    """Guarda las predicciones en la tabla `prediccion`.

    Si ya había predicciones para ese mismo periodo, se reemplazan.
    """
    registros = pd.DataFrame({
        "id_variante": pron["id_variante"].astype(int),
        "periodo_inicio": pron["mes"].dt.date,
        "periodo_fin": (pron["mes"] + pd.offsets.MonthEnd(0)).dt.date,
        "cantidad_estimada": pron["cantidad_estimada"].astype(int),
        "algoritmo": algoritmo,
        "mae": round(mae, 2),
        "fecha_generacion": pd.Timestamp.now().floor("s"),  # hora local del equipo
    })
    with motor.begin() as conexion:
        conexion.execute(text("DELETE FROM prediccion WHERE periodo_inicio = :inicio"),
                         {"inicio": registros["periodo_inicio"].iloc[0]})
        registros.to_sql("prediccion", conexion, if_exists="append", index=False)
    return len(registros)


def generar_predicciones(motor) -> dict:
    """Punto de entrada: ejecuta todo el flujo y devuelve un resumen.

    Lo llama la ruta /predicciones/actualizar cuando el gerente presiona
    "Actualizar predicciones".
    """
    ventas = leer_ventas(motor)
    # Solo meses completos: el mes en curso todavía no termina y bajaría el promedio
    inicio_mes_actual = pd.Timestamp.today().normalize().replace(day=1)
    ventas = ventas[ventas["fecha"] < inicio_mes_actual]
    if ventas.empty:
        raise ValueError("No hay ventas registradas para entrenar el modelo.")
    serie = ventas_mensuales(ventas)
    if serie["mes"].nunique() < MESES_PRUEBA + 4:
        raise ValueError("No hay suficiente historial: se necesitan al menos 7 meses de ventas.")
    algoritmo, modelo, mae, errores = entrenar_y_elegir(construir_variables(serie))
    pronostico = pronosticar_siguiente_mes(serie, modelo)
    total = guardar_predicciones(pronostico, algoritmo, mae, motor)
    return {"algoritmo": algoritmo, "mae": round(mae, 2), "predicciones": total,
            "errores": errores, "periodo": pronostico["mes"].iloc[0].strftime("%m/%Y")}
