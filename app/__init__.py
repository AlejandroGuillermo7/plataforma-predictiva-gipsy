"""
Plataforma de Análisis Predictivo Gipsy
---------------------------------------
Fábrica de la aplicación Flask. Configura la base de datos, el inicio de
sesión y registra los módulos (blueprints) del sistema.

Base de datos:
    Por defecto usa SQLite (archivo gipsy.db) para que el sistema funcione
    sin instalar nada. Para usar PostgreSQL, definir la variable de entorno:
        DATABASE_URL=postgresql+psycopg2://usuario:contrasena@localhost/gipsy_db
"""

import os

from flask import Flask
from flask_login import LoginManager
from flask_sqlalchemy import SQLAlchemy

db = SQLAlchemy()
login_manager = LoginManager()


def create_app(config: dict | None = None) -> Flask:
    """Crea y configura la aplicación."""
    app = Flask(__name__, instance_relative_config=True)
    os.makedirs(app.instance_path, exist_ok=True)

    app.config.update(
        SECRET_KEY=os.environ.get("SECRET_KEY", "cambiar-esta-clave-en-produccion"),
        SQLALCHEMY_DATABASE_URI=os.environ.get(
            "DATABASE_URL", "sqlite:///" + os.path.join(app.instance_path, "gipsy.db")
        ),
        MAX_CONTENT_LENGTH=10 * 1024 * 1024,  # archivos de hasta 10 MB
    )
    if config:
        app.config.update(config)

    db.init_app(app)
    login_manager.init_app(app)
    login_manager.login_view = "auth.login"
    login_manager.login_message = "Inicia sesión para continuar."

    from . import models  # noqa: F401  (registra las tablas)
    from .auth import bp as auth_bp
    from .views import bp as views_bp

    app.register_blueprint(auth_bp)
    app.register_blueprint(views_bp)

    @app.template_filter("dinero")
    def dinero(valor):
        return f"${float(valor or 0):,.2f}"

    return app
