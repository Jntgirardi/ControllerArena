from datetime import UTC, datetime, timedelta

import mongomock
import fakeredis
from bson import ObjectId

import app.infrastructure.cache.redis_cache as cache_module
import app.infrastructure.db.mongo as mongo_module
from app.infrastructure.security.password_hasher import PasswordHasher


def build_test_app(monkeypatch):
    monkeypatch.setattr(mongo_module, "MongoClient", mongomock.MongoClient)
    monkeypatch.setattr(cache_module.redis, "from_url", fakeredis.FakeRedis.from_url)

    from app import create_app

    return create_app()


def test_public_championship_flow_uses_mock_data(monkeypatch):
    flask_app = build_test_app(monkeypatch)
    client = flask_app.test_client()

    home = client.get("/")
    assert home.status_code == 200
    assert b"FPS Arena Masters" in home.data
    assert b"Area do Competidor" in home.data
    assert b"/campeonato/1" in home.data

    details = client.get("/campeonato/1")
    assert details.status_code == 200
    assert b"Partidas Ao Vivo" in details.data
    assert b"Proximos Jogos" in details.data
    assert b"Resultados" in details.data
    assert b"/partida/1001" in details.data

    summary = client.get("/partida/1001")
    assert summary.status_code == 200
    assert b"Abates" in summary.data
    assert b"Mortes" in summary.data
    assert b"Assistencias" in summary.data
    assert b"Blue Storm" in summary.data
    assert b"Red Vipers" in summary.data


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


def test_player_login_opens_dashboard_profile(monkeypatch):
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
    dashboard_response = client.get("/dashboard")
    profile_response = client.get("/meu-perfil", follow_redirects=False)

    assert login_response.status_code == 302
    assert login_response.headers["Location"] == "/dashboard"
    assert dashboard_response.status_code == 200
    assert b"Dashboard do Jogador" in dashboard_response.data
    assert b"PlayerOne" in dashboard_response.data
    assert profile_response.status_code == 302
    assert profile_response.headers["Location"] == "/dashboard"


def test_player_ranking_includes_team_ranking_for_player_game(monkeypatch):
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

    player_one_id = mongo.players.insert_one(
        {
            "nick": "PlayerOne",
            "nome": "Jogador Um",
            "login": "player.one",
            "jogo_principal": "CS2",
            "admin_id": admin_id,
            "estatisticas": {"partidas_jogadas": 10, "vitorias": 7, "derrotas": 3, "kd_ratio": 1.2},
            "criado_em": datetime.now(UTC),
        }
    ).inserted_id
    player_two_id = mongo.players.insert_one(
        {
            "nick": "PlayerTwo",
            "nome": "Jogador Dois",
            "login": "player.two",
            "jogo_principal": "CS2",
            "admin_id": admin_id,
            "estatisticas": {"partidas_jogadas": 8, "vitorias": 5, "derrotas": 3, "kd_ratio": 1.1},
            "criado_em": datetime.now(UTC),
        }
    ).inserted_id

    mongo.teams.insert_one(
        {
            "nome": "Alpha Team",
            "tag": "ALP",
            "jogo": "CS2",
            "admin_id": admin_id,
            "jogadores": [
                {"jogador_id": player_one_id, "nick": "PlayerOne", "funcao": "IGL"},
                {"jogador_id": player_two_id, "nick": "PlayerTwo", "funcao": "AWPer"},
            ],
            "criado_em": datetime.now(UTC),
        }
    )

    mongo.users.insert_one(
        {
            "nome": "Jogador Um",
            "login": "player.one",
            "role": "PLAYER",
            "admin_id": admin_id,
            "player_id": player_one_id,
            "senha_hash": password_hasher.hash("player123"),
            "ativo": True,
            "must_change_password": False,
            "criado_em": datetime.now(UTC),
        }
    )

    client = flask_app.test_client()
    client.post("/login", data={"modo": "login", "identificador": "player.one", "senha": "player123"})
    ranking_response = client.get("/ranking")

    assert ranking_response.status_code == 200
    assert b"Ranking de Times" in ranking_response.data
    assert b"Alpha Team" in ranking_response.data
    assert b"PlayerOne" in ranking_response.data


def test_admin_ranking_displays_team_ranking_with_game_filter(monkeypatch):
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

    cs_player_id = mongo.players.insert_one(
        {
            "nick": "EntryFrag",
            "nome": "Jogador CS",
            "login": "entry.frag",
            "jogo_principal": "CS2",
            "admin_id": admin_id,
            "estatisticas": {"partidas_jogadas": 12, "vitorias": 8, "derrotas": 4, "kd_ratio": 1.3},
            "criado_em": datetime.now(UTC),
        }
    ).inserted_id
    valorant_player_id = mongo.players.insert_one(
        {
            "nick": "SiteAnchor",
            "nome": "Jogador Valorant",
            "login": "site.anchor",
            "jogo_principal": "Valorant",
            "admin_id": admin_id,
            "estatisticas": {"partidas_jogadas": 9, "vitorias": 6, "derrotas": 3, "kd_ratio": 1.1},
            "criado_em": datetime.now(UTC),
        }
    ).inserted_id

    mongo.teams.insert_one(
        {
            "nome": "Alpha Team",
            "tag": "ALP",
            "jogo": "CS2",
            "admin_id": admin_id,
            "jogadores": [{"jogador_id": cs_player_id, "nick": "EntryFrag", "funcao": "IGL"}],
            "criado_em": datetime.now(UTC),
        }
    )
    mongo.teams.insert_one(
        {
            "nome": "Beta Squad",
            "tag": "BET",
            "jogo": "Valorant",
            "admin_id": admin_id,
            "jogadores": [{"jogador_id": valorant_player_id, "nick": "SiteAnchor", "funcao": "Sentinela"}],
            "criado_em": datetime.now(UTC),
        }
    )

    client = flask_app.test_client()
    client.post("/login", data={"modo": "login", "identificador": "organizador", "senha": "admin123"})

    ranking_response = client.get("/ranking?jogo=CS2")

    assert ranking_response.status_code == 200
    assert b"Ranking de Times" in ranking_response.data
    assert b"Alpha Team" in ranking_response.data
    assert b"Beta Squad" not in ranking_response.data


def test_player_can_view_other_player_with_sensitive_fields_hidden(monkeypatch):
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
    player_one_id = mongo.players.insert_one(
        {
            "nick": "PlayerOne",
            "nome": "Jogador Um",
            "login": "player.one",
            "contato": "player.one@email.com",
            "jogo_principal": "CS2",
            "admin_id": admin_id,
            "estatisticas": {"partidas_jogadas": 2, "vitorias": 1, "derrotas": 1, "kd_ratio": 1.0},
            "criado_em": datetime.now(UTC),
        }
    ).inserted_id
    player_two_id = mongo.players.insert_one(
        {
            "nick": "PlayerTwo",
            "nome": "Jogador Dois",
            "login": "player.two",
            "contato": "player.two@email.com",
            "jogo_principal": "CS2",
            "admin_id": admin_id,
            "estatisticas": {"partidas_jogadas": 3, "vitorias": 2, "derrotas": 1, "kd_ratio": 1.1},
            "criado_em": datetime.now(UTC),
        }
    ).inserted_id
    mongo.users.insert_one(
        {
            "nome": "Jogador Um",
            "login": "player.one",
            "role": "PLAYER",
            "admin_id": admin_id,
            "player_id": player_one_id,
            "senha_hash": password_hasher.hash("player123"),
            "ativo": True,
            "must_change_password": False,
            "criado_em": datetime.now(UTC),
        }
    )

    client = flask_app.test_client()
    client.post("/login", data={"modo": "login", "identificador": "player.one", "senha": "player123"})
    detail_response = client.get(f"/jogadores/{player_two_id}")

    assert detail_response.status_code == 200
    assert b"PlayerTwo" in detail_response.data
    assert b"player.two" not in detail_response.data
    assert b"player.two@email.com" not in detail_response.data


def test_reports_page_lists_new_exports(monkeypatch):
    flask_app = build_test_app(monkeypatch)
    mongo = flask_app.extensions["mongo"]
    password_hasher = PasswordHasher()

    admin_id = mongo.users.insert_one(
        {
            "nome": "Admin Reports",
            "login": "admin.reports",
            "role": "ADMIN",
            "senha_hash": password_hasher.hash("admin123"),
            "ativo": True,
            "must_change_password": False,
            "criado_em": datetime.now(UTC),
        }
    ).inserted_id

    player_id = mongo.players.insert_one(
        {
            "nick": "Ace",
            "nome": "Aline Costa",
            "login": "aline.ace",
            "jogo_principal": "CS2",
            "admin_id": admin_id,
            "estatisticas": {"partidas_jogadas": 8, "vitorias": 6, "derrotas": 2, "kd_ratio": 1.4},
            "criado_em": datetime.now(UTC),
        }
    ).inserted_id

    team_id = mongo.teams.insert_one(
        {
            "nome": "Alpha Team",
            "tag": "ALP",
            "jogo": "CS2",
            "admin_id": admin_id,
            "jogadores": [{"jogador_id": player_id, "nick": "Ace", "funcao": "Captain"}],
            "criado_em": datetime.now(UTC),
        }
    ).inserted_id

    camp_id = mongo.championships.insert_one(
        {
            "nome": "Arena Masters",
            "jogo": "CS2",
            "formato": "mata-mata",
            "max_times": 8,
            "status": "EM_ANDAMENTO",
            "admin_id": admin_id,
            "times_inscritos": [team_id],
            "datas": {"inicio": datetime.now(UTC), "fim": datetime.now(UTC) + timedelta(days=7)},
            "criado_em": datetime.now(UTC),
        }
    ).inserted_id

    mongo.matches.insert_one(
        {
            "admin_id": admin_id,
            "campeonato_id": camp_id,
            "fase": "Final",
            "time_a": {"time_id": team_id, "nome": "Alpha Team", "placar": 13},
            "time_b": {"time_id": ObjectId(), "nome": "Beta Team", "placar": 10},
            "mapa": "Nuke",
            "status": "finalizada",
            "data_partida": datetime.now(UTC),
        }
    )

    event_id = mongo.events.insert_one(
        {
            "nome": "Arena Music Clash",
            "local": "Main Stage",
            "data_evento": datetime.now(UTC) + timedelta(days=3),
            "capacidade_total": 300,
            "admin_id": admin_id,
            "criado_em": datetime.now(UTC),
        }
    ).inserted_id
    mongo.tickets.insert_one(
        {
            "evento_id": event_id,
            "admin_id": admin_id,
            "comprador": "Julia",
            "lote": "1o lote",
            "quantidade": 2,
            "valor_total": 150.0,
            "status": "pago",
            "vendido_em": datetime.now(UTC),
        }
    )
    mongo.logs.insert_one(
        {
            "user_id": admin_id,
            "admin_id": admin_id,
            "login": "admin.reports",
            "role": "ADMIN",
            "endpoint": "dashboard",
            "method": "GET",
            "path": "/dashboard",
            "status_code": 200,
            "created_at": datetime.now(UTC),
        }
    )

    client = flask_app.test_client()
    login_response = client.post(
        "/login",
        data={"modo": "login", "identificador": "admin.reports", "senha": "admin123"},
        follow_redirects=False,
    )
    reports_response = client.get("/relatorios")

    assert login_response.status_code == 302
    assert reports_response.status_code == 200
    assert reports_response.data.find(b"Relatorio de logs") < reports_response.data.find(b"Ranking de jogadores")
    assert b"Relatorio de logs" in reports_response.data
    assert b"Ranking de jogadores" in reports_response.data
    assert b"Historico de partidas por campeonato" in reports_response.data
    assert b"Estatisticas de campeonatos" in reports_response.data
    assert b"Jogadores inscritos por torneio" in reports_response.data
    assert b"Relatorio de vendas de ingressos" in reports_response.data
    assert b"Controle de lotacao" in reports_response.data


def test_report_exports_return_complete_files(monkeypatch):
    flask_app = build_test_app(monkeypatch)
    mongo = flask_app.extensions["mongo"]
    password_hasher = PasswordHasher()

    admin_id = mongo.users.insert_one(
        {
            "nome": "Admin Export",
            "login": "admin.export",
            "role": "ADMIN",
            "senha_hash": password_hasher.hash("admin123"),
            "ativo": True,
            "must_change_password": False,
            "criado_em": datetime.now(UTC),
        }
    ).inserted_id

    mongo.players.insert_one(
        {
            "nick": "Ace",
            "nome": "Aline Costa",
            "login": "aline.ace",
            "jogo_principal": "CS2",
            "admin_id": admin_id,
            "estatisticas": {"partidas_jogadas": 8, "vitorias": 6, "derrotas": 2, "kd_ratio": 1.4},
            "criado_em": datetime.now(UTC),
        }
    )

    event_id = mongo.events.insert_one(
        {
            "nome": "Arena Music Clash",
            "local": "Main Stage",
            "data_evento": datetime.now(UTC) + timedelta(days=3),
            "capacidade_total": 300,
            "admin_id": admin_id,
            "criado_em": datetime.now(UTC),
        }
    ).inserted_id
    mongo.tickets.insert_one(
        {
            "evento_id": event_id,
            "admin_id": admin_id,
            "comprador": "Julia",
            "lote": "1o lote",
            "quantidade": 2,
            "valor_total": 150.0,
            "status": "pago",
            "vendido_em": datetime.now(UTC),
        }
    )
    mongo.logs.insert_one(
        {
            "user_id": admin_id,
            "admin_id": admin_id,
            "login": "admin.export",
            "role": "ADMIN",
            "endpoint": "dashboard",
            "method": "GET",
            "path": "/dashboard",
            "status_code": 200,
            "created_at": datetime.now(UTC),
        }
    )

    client = flask_app.test_client()
    client.post("/login", data={"modo": "login", "identificador": "admin.export", "senha": "admin123"})

    csv_response = client.get("/relatorios/export/player-ranking.csv")
    pdf_response = client.get("/relatorios/export/ticket-sales.pdf")

    assert csv_response.status_code == 200
    assert csv_response.mimetype == "text/csv"
    assert "attachment; filename=player-ranking.csv" == csv_response.headers["Content-Disposition"]
    assert b"Ace" in csv_response.data

    assert pdf_response.status_code == 200
    assert pdf_response.mimetype == "application/pdf"
    assert pdf_response.data.startswith(b"%PDF-1.4")


def test_superadmin_reports_hide_shows_and_events(monkeypatch):
    flask_app = build_test_app(monkeypatch)
    client = flask_app.test_client()

    login_response = client.post(
        "/login",
        data={"modo": "login", "identificador": "superadmin", "senha": "super123"},
        follow_redirects=False,
    )
    reports_response = client.get("/relatorios")

    assert login_response.status_code == 302
    assert reports_response.status_code == 200
    assert b"Relatorio de vendas de ingressos" not in reports_response.data
    assert b"Controle de lotacao" not in reports_response.data


def test_dashboard_hides_users_and_reports_tabs(monkeypatch):
    flask_app = build_test_app(monkeypatch)
    client = flask_app.test_client()

    client.post("/login", data={"modo": "login", "identificador": "superadmin", "senha": "super123"})
    dashboard_response = client.get("/dashboard")

    assert dashboard_response.status_code == 200
    assert b"nav nav-tabs" not in dashboard_response.data
    assert b"tab='usuarios'" not in dashboard_response.data
    assert b"tab='relatorios'" not in dashboard_response.data


def test_player_cannot_access_reports(monkeypatch):
    flask_app = build_test_app(monkeypatch)
    mongo = flask_app.extensions["mongo"]
    password_hasher = PasswordHasher()

    admin_id = mongo.users.insert_one(
        {
            "nome": "Admin Scope",
            "login": "admin.scope",
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
    client.post("/login", data={"modo": "login", "identificador": "player.one", "senha": "player123"})
    response = client.get("/relatorios", follow_redirects=False)

    assert response.status_code == 302
    assert response.headers["Location"] == "/dashboard"
