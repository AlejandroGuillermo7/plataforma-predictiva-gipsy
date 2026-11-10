"""
Inicio y cierre de sesión, y control de acceso por rol (HU01, RNF03, RNF11).
"""

from functools import wraps

from flask import Blueprint, abort, flash, redirect, render_template, request, url_for
from flask_login import current_user, login_required, login_user, logout_user

from .models import Usuario

bp = Blueprint("auth", __name__)


def requiere_rol(*roles: str):
    """Decorador: permite entrar a la vista solo a los roles indicados."""
    def decorador(vista):
        @wraps(vista)
        @login_required
        def envoltura(*args, **kwargs):
            if not current_user.tiene_rol(*roles):
                abort(403)
            return vista(*args, **kwargs)
        return envoltura
    return decorador


@bp.route("/login", methods=["GET", "POST"])
def login():
    """Pantalla 1: inicio de sesión."""
    if current_user.is_authenticated:
        return redirect(url_for("views.panel"))
    if request.method == "POST":
        usuario = Usuario.query.filter_by(usuario=request.form.get("usuario", "").strip()).first()
        if usuario and usuario.activo and usuario.verificar_contrasena(request.form.get("contrasena", "")):
            login_user(usuario)
            destino = request.args.get("next", "")
            if not destino.startswith("/") or destino.startswith("//"):
                destino = url_for("views.panel")  # evita redirecciones a otros sitios
            return redirect(destino)
        flash("Usuario o contraseña incorrectos.", "error")
    return render_template("login.html")


@bp.route("/logout")
@login_required
def logout():
    logout_user()
    return redirect(url_for("auth.login"))
