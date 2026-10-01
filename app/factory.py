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


def get_game_badge_class(game_name: str | None) -> str:
    g = (game_name or "").strip().lower()
    if "valorant" in g:
        return "bg-rose-500/15 text-rose-500 border-rose-500/30"
    if "league" in g or "lol" in g:
        return "bg-sky-500/15 text-sky-500 border-sky-500/30"
    if "clash" in g:
        return "bg-purple-500/15 text-purple-500 border-purple-500/30"
    if "cs2" in g or "counter" in g:
        return "bg-warning/15 text-warning border-warning/30"
    return "bg-neutral-500/15 text-neutral-400 border-neutral-500/30"


def get_game_badge_bg(game_name: str | None) -> str:
    g = (game_name or "").strip().lower()
    if "valorant" in g:
        return "bg-rose-600"
    if "league" in g or "lol" in g:
        return "bg-sky-600"
    if "clash" in g:
        return "bg-purple-600"
    if "cs2" in g or "counter" in g:
        return "bg-amber-600"
    return "bg-primary"


def get_game_image_url(game_name: str | None) -> str:
    g = (game_name or "").strip().lower()
    if "valorant" in g:
        return "https://images.unsplash.com/photo-1553481187-be93c21490a9?w=600&auto=format&fit=crop"
    if "league" in g or "lol" in g:
        return "https://images.unsplash.com/photo-1560419015-7c427e8ae5ba?w=600&auto=format&fit=crop"
    if "clash" in g:
        return "https://images.unsplash.com/photo-1511512578047-dfb367046420?w=600&auto=format&fit=crop"
    if "cs2" in g or "counter" in g:
        return "https://images.unsplash.com/photo-1542751371-adc38448a05e?w=600&auto=format&fit=crop"
    return "https://images.unsplash.com/photo-1542751371-adc38448a05e?w=600&auto=format&fit=crop"


def create_app():
    app = Flask(__name__, template_folder="../templates")
    app.config.from_object(Config)
    app.jinja_env.globals["enumerate"] = enumerate
    app.jinja_env.globals["get_game_badge_class"] = get_game_badge_class
    app.jinja_env.globals["get_game_badge_bg"] = get_game_badge_bg
    app.jinja_env.globals["get_game_image_url"] = get_game_image_url

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
