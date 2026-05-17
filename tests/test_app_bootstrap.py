import mongomock
import fakeredis

import app.infrastructure.cache.redis_cache as cache_module
import app.infrastructure.db.mongo as mongo_module


def test_app_boots_with_mongo_and_redis(monkeypatch):
    monkeypatch.setattr(mongo_module, "MongoClient", mongomock.MongoClient)
    monkeypatch.setattr(cache_module.redis, "from_url", fakeredis.FakeRedis.from_url)

    from app import create_app

    flask_app = create_app()
    assert type(flask_app.extensions["cache"]).__name__ == "RedisCache"
    assert flask_app.extensions["cache"].ping() is True

    client = flask_app.test_client()

    login_page = client.get("/login")
    assert login_page.status_code == 200

    login_response = client.post(
        "/login",
        data={"modo": "login", "identificador": "superadmin", "senha": "super123"},
        follow_redirects=False,
    )
    assert login_response.status_code == 302
    assert login_response.headers["Location"] == "/dashboard"

    dashboard = client.get("/dashboard")
    assert dashboard.status_code == 200

    ranking = client.get("/ranking")
    assert ranking.status_code == 200

    cached_ranking = flask_app.extensions["cache"].get("fps_arena:ranking:global:todos")
    assert cached_ranking is not None
