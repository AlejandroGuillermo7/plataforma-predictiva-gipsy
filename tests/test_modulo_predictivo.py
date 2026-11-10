"""Pruebas unitarias del modulo predictivo (Sprint 2)."""
import pandas as pd
import pytest
from sklearn.linear_model import LinearRegression

from app import modulo_predictivo as mp


@pytest.fixture
def ventas():
    """Ventas de ejemplo: 2 variantes, una venta de 3 piezas cada dia 1 y 15 durante 2 anios."""
    fechas = pd.date_range("2024-01-01", "2025-12-31", freq="SMS")  # dias 1 y 15
    filas = [(v, f, 3) for v in (1, 2) for f in fechas]
    return pd.DataFrame(filas, columns=["id_variante", "fecha", "cantidad"])


def test_ventas_mensuales_suma_por_mes(ventas):
    """Cada variante debe sumar 6 piezas por mes (2 ventas de 3 piezas)."""
    serie = mp.ventas_mensuales(ventas)
    assert len(serie) == 2 * 24
    assert (serie["piezas"] == 6).all()


def test_rellena_meses_sin_ventas(ventas):
    """Un mes sin ventas debe aparecer con 0 piezas, no desaparecer."""
    sin_marzo = ventas[ventas["fecha"].dt.month != 3]
    serie = mp.ventas_mensuales(sin_marzo)
    marzo = serie[serie["mes"].dt.month == 3]
    assert len(marzo) == 4 and (marzo["piezas"] == 0).all()


def test_variables_usan_solo_meses_anteriores(ventas):
    """lag_1 debe ser la venta del mes anterior (sin mirar el futuro)."""
    df = mp.construir_variables(mp.ventas_mensuales(ventas))
    fila = df[(df["id_variante"] == 1) & (df["mes"] == "2024-02-01")].iloc[0]
    assert fila["lag_1"] == 6


def test_pronostico_no_negativo(ventas):
    """El pronostico nunca debe dar piezas negativas y debe cubrir todas las variantes."""
    serie = mp.ventas_mensuales(ventas)
    datos = mp.construir_variables(serie).dropna(subset=mp.VARIABLES)
    modelo = LinearRegression().fit(datos[mp.VARIABLES], datos["piezas"])
    pron = mp.pronosticar_siguiente_mes(serie, modelo)
    assert set(pron["id_variante"]) == {1, 2}
    assert (pron["cantidad_estimada"] >= 0).all()
