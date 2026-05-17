from datetime import UTC, datetime, timedelta

import mongomock
import fakeredis

import app.infrastructure.cache.redis_cache as cache_module
import app.infrastructure.db.mongo as mongo_module
from app.infrastructure.security.password_hasher import PasswordHasher


def build_test_app(monkeypatch):
    monkeypatch.setattr(mongo_module, "MongoClient", mongomock.MongoClient)
    monkeypatch.setattr(cache_module.redis, "from_url", fakeredis.FakeRedis.from_url)

    from app import create_app

    return create_app()


def test_app_boots_with_mongo_and_redis(monkeypatch):
    flask_app = build_test_app(monkeypatch)
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


def test_admin_first_access_accepts_timezone_aware_expiration(monkeypatch):
    flask_app = build_test_app(monkeypatch)
    mongo = flask_app.extensions["mongo"]
    password_hasher = PasswordHasher()

    access_code = "admin-access-code"
    mongo.users.insert_one(
        {
            "nome": "Organizador Teste",
            "login": "arena.teste",
            "role": "ADMIN",
            "access_code": access_code,
            "access_code_expires_at": datetime.now(UTC) + timedelta(days=1),
            "senha_hash": password_hasher.hash("admin123"),
            "ativo": True,
            "must_change_password": True,
            "criado_em": datetime.now(UTC),
        }
    )

    client = flask_app.test_client()
    response = client.post(
        "/login",
        data={"modo": "access_code", "identificador": access_code, "senha": "admin123"},
        follow_redirects=False,
    )

    assert response.status_code == 302
    assert response.headers["Location"] == "/primeiro-acesso/senha"


def test_player_login_opens_own_profile(monkeypatch):
    flask_app = build_test_app(monkeypatch)
    mongo = flask_app.extensions["mongo"]
    password_hasher = PasswordHasher()

    admin_id = mongo.users.insert_one(
        {
            "nome": "Organizador",
            "login": "organizador",
            "role": "ADMIN",
            "senha_hash": password_hasher.hash("admin123"),
            "ativo": True,
            "must_change_password": False,
            "criado_em": datetime.now(UTC),
        }
    ).inserted_id
    player_id = mongo.players.insert_one(
        {
            "nick": "PlayerOne",
            "nome": "Jogador Um",
            "login": "player.one",
            "jogo_principal": "CS2",
            "admin_id": admin_id,
            "estatisticas": {"partidas_jogadas": 0, "vitorias": 0, "derrotas": 0, "kd_ratio": 0.0},
            "criado_em": datetime.now(UTC),
        }
    ).inserted_id
    mongo.users.insert_one(
        {
            "nome": "Jogador Um",
            "login": "player.one",
            "role": "PLAYER",
            "admin_id": admin_id,
            "player_id": player_id,
            "senha_hash": password_hasher.hash("player123"),
            "ativo": True,
            "must_change_password": False,
            "criado_em": datetime.now(UTC),
        }
    )

    client = flask_app.test_client()
    login_response = client.post(
        "/login",
        data={"modo": "login", "identificador": "player.one", "senha": "player123"},
        follow_redirects=False,
    )
    profile_response = client.get("/meu-perfil")

    assert login_response.status_code == 302
    assert login_response.headers["Location"] == "/dashboard"
    assert profile_response.status_code == 200
    assert b"PlayerOne" in profile_response.data
