"""Pruebas de integración de la plataforma (login, roles, ventas e importación)."""
from pathlib import Path

from app import db
from app.models import Importacion, Variante, Venta
from tests.conftest import entrar

EJEMPLO = Path(__file__).resolve().parents[1] / "ejemplos" / "historial_ejemplo.csv"


def test_login_incorrecto(cliente):
    r = entrar(cliente, "admin", "mala")
    assert "incorrectos" in r.get_data(as_text=True)


def test_login_correcto_muestra_panel(cliente):
    r = entrar(cliente, "gerente", "gerente123")
    assert "Resumen de hoy" in r.get_data(as_text=True)


def test_vendedor_no_ve_predicciones(cliente):
    entrar(cliente, "vendedor", "vendedor123")
    assert cliente.get("/predicciones").status_code == 403


def test_venta_descuenta_stock(cliente, app):
    entrar(cliente, "vendedor", "vendedor123")
    v = Variante.query.first()
    antes = v.stock
    cliente.post("/ventas/nueva", data={"variante": [v.id_variante], "cantidad": ["1"]})
    db.session.refresh(v)
    assert v.stock == antes - 1
    assert Venta.query.count() == 1


def test_no_vende_sin_existencia(cliente):
    entrar(cliente, "vendedor", "vendedor123")
    v = Variante.query.first()
    r = cliente.post("/ventas/nueva", data={"variante": [v.id_variante], "cantidad": [str(v.stock + 1)]},
                     follow_redirects=True)
    assert "Sin existencia suficiente" in r.get_data(as_text=True)
    assert Venta.query.count() == 0


def test_gerente_cancela_y_regresa_stock(cliente):
    entrar(cliente, "gerente", "gerente123")
    v = Variante.query.first()
    antes = v.stock
    cliente.post("/ventas/nueva", data={"variante": [v.id_variante], "cantidad": ["2"]})
    venta = Venta.query.one()
    cliente.post(f"/ventas/{venta.id_venta}/cancelar")
    db.session.refresh(v)
    assert venta.estado == "Cancelada" and v.stock == antes


def test_importar_rechaza_filas_invalidas(cliente):
    entrar(cliente, "admin", "admin123")
    with open(EJEMPLO, "rb") as f:
        r = cliente.post("/importar", data={"archivo": (f, "historial_ejemplo.csv")},
                         content_type="multipart/form-data", follow_redirects=True)
    imp = Importacion.query.one()
    # 10 filas: 1 sin fecha, 1 con cantidad 0, 1 con talla "unitalla" y 1 duplicada
    assert imp.filas_rechazadas == 3
    assert imp.filas_cargadas == 6
    assert "Importación terminada" in r.get_data(as_text=True)
