import os


class Config:
    SECRET_KEY = os.environ.get("SECRET_KEY")
    if not SECRET_KEY:
        if os.environ.get("FLASK_ENV") == "production":
            import secrets
            SECRET_KEY = secrets.token_hex(32)
        else:
            SECRET_KEY = "fps-arena-secret-2026"

    # Configurações de Segurança para Cookies de Sessão
    SESSION_COOKIE_HTTPONLY = True
    SESSION_COOKIE_SECURE = os.environ.get("SESSION_COOKIE_SECURE", "false").lower() == "true"
    SESSION_COOKIE_SAMESITE = "Lax"

    # MongoDB
    MONGO_URI = os.environ.get("MONGO_URI", "mongodb://localhost:27017/")
    MONGO_DB_NAME = os.environ.get("MONGO_DB_NAME", "fps_arena")

    # Redis
    REDIS_URL = os.environ.get("REDIS_URL", "redis://localhost:6379/0")
    REDIS_TTL = int(os.environ.get("REDIS_TTL", 120))
    REDIS_ENABLED = os.environ.get("REDIS_ENABLED", "true").lower() == "true"
