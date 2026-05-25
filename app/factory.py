from flask import Flask

from .application import build_services
from .config import Config
from .infrastructure.cache import build_cache
from .infrastructure.db.mongo import MongoDatabase
from .infrastructure.db.migrations import migrate_legacy_data
from .infrastructure.discord_service import DiscordService
from .infrastructure.repositories import (
    MongoChampionshipRepository,
    MongoEventRepository,
    MongoLogRepository,
    MongoMatchRepository,
    MongoPlayerRepository,
    MongoTicketRepository,
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

    mongo = MongoDatabase(app.config["MONGO_URI"], app.config["MONGO_DB_NAME"])
    mongo.ensure_indexes()
    migrate_legacy_data(mongo)

    repositories = {
        "users": MongoUserRepository(mongo.users),
        "players": MongoPlayerRepository(mongo.players),
        "teams": MongoTeamRepository(mongo.teams),
        "championships": MongoChampionshipRepository(mongo.championships),
        "matches": MongoMatchRepository(mongo.matches),
        "events": MongoEventRepository(mongo.events),
        "tickets": MongoTicketRepository(mongo.tickets),
        "logs": MongoLogRepository(mongo.logs),
        "arbitros": MongoArbitroRepository(mongo.arbitros),
        "notifications": MongoNotificationRepository(mongo.notifications),
    }
    discord_service = DiscordService(timeout=app.config["DISCORD_WEBHOOK_TIMEOUT"])
    services = build_services(repositories, PasswordHasher(), cache, discord_service)

    app.extensions["cache"] = cache
    app.extensions["mongo"] = mongo
    app.extensions["services"] = services

    register_routes(app, services)
    return app
