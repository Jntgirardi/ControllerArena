from flask import Flask, render_template, request

from .application import build_services
from .config import Config
from .infrastructure.cache import build_cache
from .infrastructure.db.mongo import MongoDatabase
from .infrastructure.db.migrations import migrate_legacy_data
from .infrastructure.repositories import (
    MongoChampionshipRepository,
    MongoLogRepository,
    MongoMatchRepository,
    MongoPlayerRepository,
    MongoTeamRepository,
    MongoUserRepository,
    MongoArbitroRepository,
    MongoNotificationRepository,
)
from .infrastructure.security.password_hasher import PasswordHasher
from .interfaces.web import register_routes


def _register_error_handlers(app: Flask) -> None:
    from werkzeug.exceptions import Forbidden, HTTPException, NotFound

    @app.errorhandler(404)
    def not_found(_e):
        return (
            render_template(
                "error.html",
                code=404,
                title="Página não encontrada",
                message="O endereço que você acessou não existe ou foi movido.",
            ),
            404,
        )

    @app.errorhandler(403)
    def forbidden(_e):
        return (
            render_template(
                "error.html",
                code=403,
                title="Acesso negado",
                message="Você não tem permissão para acessar esta página.",
            ),
            403,
        )

    @app.errorhandler(Exception)
    def internal_error(e):
        import logging
        import traceback

        logger = logging.getLogger(__name__)
        logger.error("Erro nao tratado em %s: %s\n%s", request.path, e, traceback.format_exc())
        code = e.code if isinstance(e, HTTPException) else 500
        if code == 404:
            return not_found(e)
        if code == 403:
            return forbidden(e)
        return (
            render_template(
                "error.html",
                code=500,
                title="Algo deu errado",
                message="Ocorreu um erro inesperado. Tente novamente em instantes.",
            ),
            500,
        )


def create_app():
    app = Flask(__name__, template_folder="../templates")
    app.config.from_object(Config)
    app.jinja_env.globals["enumerate"] = enumerate

    cache = build_cache(
        app.config["REDIS_URL"],
        app.config["REDIS_TTL"],
        app.config["REDIS_ENABLED"],
    )

    import os
    mongo = MongoDatabase(app.config["MONGO_URI"], app.config["MONGO_DB_NAME"])
    if os.environ.get("VERCEL") != "1":
        mongo.ensure_indexes()
        migrate_legacy_data(mongo)

    repositories = {
        "users": MongoUserRepository(mongo.users),
        "players": MongoPlayerRepository(mongo.players),
        "teams": MongoTeamRepository(mongo.teams),
        "championships": MongoChampionshipRepository(mongo.championships),
        "matches": MongoMatchRepository(mongo.matches),
        "logs": MongoLogRepository(mongo.logs),
        "arbitros": MongoArbitroRepository(mongo.arbitros),
        "notifications": MongoNotificationRepository(mongo.notifications),
    }
    services = build_services(repositories, PasswordHasher(), cache)

    app.extensions["cache"] = cache
    app.extensions["mongo"] = mongo
    app.extensions["services"] = services

    register_routes(app, services)
    _register_error_handlers(app)
    return app
