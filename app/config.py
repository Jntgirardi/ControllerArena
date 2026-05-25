import os


class Config:
    SECRET_KEY = os.environ.get("SECRET_KEY", "fps-arena-secret-2026")

    # MongoDB
    MONGO_URI = os.environ.get("MONGO_URI", "mongodb://localhost:27017/")
    MONGO_DB_NAME = os.environ.get("MONGO_DB_NAME", "fps_arena")

    # Redis
    REDIS_URL = os.environ.get("REDIS_URL", "redis://localhost:6379/0")
    REDIS_TTL = int(os.environ.get("REDIS_TTL", 120))
    REDIS_ENABLED = os.environ.get("REDIS_ENABLED", "true").lower() == "true"

    # Discord
    DISCORD_WEBHOOK_TIMEOUT = float(os.environ.get("DISCORD_WEBHOOK_TIMEOUT", 5))
