from functools import wraps

from bson import ObjectId
from bson.errors import InvalidId
from flask import flash, redirect, request, session, url_for


ALLOWED_WITH_PENDING_PASSWORD = {"logout", "alterar_senha_inicial"}


def login_required(view):
    @wraps(view)
    def wrapped(*args, **kwargs):
        if "user_id" not in session:
            flash("Faca login para continuar.", "warning")
            return redirect(url_for("login"))
        if session.get("must_change_password") and request.endpoint not in ALLOWED_WITH_PENDING_PASSWORD:
            flash("Altere sua senha inicial para continuar.", "warning")
            return redirect(url_for("alterar_senha_inicial"))
        return view(*args, **kwargs)

    return wrapped


def roles_required(*allowed_roles):
    def decorator(view):
        @wraps(view)
        def wrapped(*args, **kwargs):
            if session.get("role") not in allowed_roles:
                flash("Voce nao tem permissao para acessar esta area.", "danger")
                return redirect(url_for("dashboard"))
            return view(*args, **kwargs)

        return wrapped

    return decorator


def to_oid(id_str: str):
    try:
        return ObjectId(id_str)
    except (InvalidId, TypeError):
        return None


def build_current_user():
    if "user_id" not in session:
        return None
    return {
        "_id": to_oid(session["user_id"]),
        "role": session.get("role"),
        "login": session.get("login"),
        "admin_id": to_oid(session.get("admin_id")) if session.get("admin_id") else None,
    }
