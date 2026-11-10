"""Configuración común de las pruebas: una base de datos SQLite en memoria."""
import random
import sys
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from app import create_app, db  # noqa: E402
import seed  # noqa: E402


@pytest.fixture
def app():
    app = create_app({"TESTING": True, "SQLALCHEMY_DATABASE_URI": "sqlite://"})
    with app.app_context():
        db.create_all()
        seed.crear_catalogos()
        seed.crear_productos(random.Random(1))
        yield app
        db.session.remove()


@pytest.fixture
def cliente(app):
    return app.test_client()


def entrar(cliente, usuario, contrasena):
    return cliente.post("/login", data={"usuario": usuario, "contrasena": contrasena},
                        follow_redirects=True)
