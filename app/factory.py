from flask import Flask

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

    import traceback as _traceback

    @app.errorhandler(Exception)
    def _debug_traceback(e):
        if os.environ.get("VERCEL") == "1" or os.environ.get("FLASK_ENV") == "production":
            body = _traceback.format_exc()
            print("TRACEBACK:", body)
            try:
                from flask import request
                if request.headers.get("X-Debug-Trace") == "1":
                    return body, 500
            except Exception:
                pass
        raise e

    return app
