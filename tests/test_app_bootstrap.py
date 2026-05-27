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
    assert b"Times Inscritos" in details.data
    assert b"Blue Storm" in details.data
    assert b"Red Vipers" in details.data
    assert b"Delta Five" in details.data

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


def test_password_reset_flow_updates_password_and_invalidates_token(monkeypatch):
    flask_app = build_test_app(monkeypatch)
    mongo = flask_app.extensions["mongo"]
    password_hasher = PasswordHasher()

    mongo.users.insert_one(
        {
            "nome": "Player Reset",
            "login": "player.reset",
            "role": "PLAYER",
            "senha_hash": password_hasher.hash("oldpass123"),
            "ativo": True,
            "must_change_password": False,
            "criado_em": datetime.now(UTC),
        }
    )

    client = flask_app.test_client()
    login_page = client.get("/login")
    assert login_page.status_code == 200
    assert b"Esqueci minha senha" in login_page.data

    request_page = client.get("/esqueci-senha")
    assert request_page.status_code == 200

    request_response = client.post("/esqueci-senha", data={"identificador": "player.reset"})
    assert request_response.status_code == 200
    assert b"/redefinir-senha/" in request_response.data

    user = mongo.users.find_one({"login": "player.reset"})
    token = user["password_reset_token"]
    assert user["password_reset_expires_at"] > datetime.now(UTC).replace(tzinfo=None)

    reset_page = client.get(f"/redefinir-senha/{token}")
    assert reset_page.status_code == 200
    assert b"player.reset" in reset_page.data

    mismatch_response = client.post(
        f"/redefinir-senha/{token}",
        data={"nova_senha": "newpass123", "confirmacao_senha": "diferente"},
    )
    assert mismatch_response.status_code == 200
    assert b"A confirmacao de senha nao confere." in mismatch_response.data

    success_response = client.post(
        f"/redefinir-senha/{token}",
        data={"nova_senha": "newpass123", "confirmacao_senha": "newpass123"},
        follow_redirects=False,
    )
    assert success_response.status_code == 302
    assert success_response.headers["Location"] == "/login"

    updated_user = mongo.users.find_one({"login": "player.reset"})
    assert "password_reset_token" not in updated_user
    assert password_hasher.verify("newpass123", updated_user["senha_hash"])
    assert not password_hasher.verify("oldpass123", updated_user["senha_hash"])

    reused_token_response = client.get(f"/redefinir-senha/{token}", follow_redirects=False)
    assert reused_token_response.status_code == 302
    assert reused_token_response.headers["Location"] == "/esqueci-senha"

    old_login_response = client.post(
        "/login",
        data={"modo": "login", "identificador": "player.reset", "senha": "oldpass123"},
    )
    assert old_login_response.status_code == 200
    assert b"Credenciais invalidas" in old_login_response.data

    new_login_response = client.post(
        "/login",
        data={"modo": "login", "identificador": "player.reset", "senha": "newpass123"},
        follow_redirects=False,
    )
    assert new_login_response.status_code == 302
    assert new_login_response.headers["Location"] == "/dashboard"


def test_expired_password_reset_token_is_rejected(monkeypatch):
    flask_app = build_test_app(monkeypatch)
    mongo = flask_app.extensions["mongo"]
    password_hasher = PasswordHasher()

    mongo.users.insert_one(
        {
            "nome": "Expired User",
            "login": "expired.user",
            "role": "ADMIN",
            "senha_hash": password_hasher.hash("admin123"),
            "ativo": True,
            "must_change_password": False,
            "password_reset_token": "expired-token",
            "password_reset_expires_at": datetime.now(UTC).replace(tzinfo=None) - timedelta(minutes=1),
            "criado_em": datetime.now(UTC),
        }
    )

    client = flask_app.test_client()
    response = client.get("/redefinir-senha/expired-token", follow_redirects=False)

    assert response.status_code == 302
    assert response.headers["Location"] == "/esqueci-senha"


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


def test_mongodb_optimized_indexes_are_created(monkeypatch):
    flask_app = build_test_app(monkeypatch)
    mongo = flask_app.extensions["mongo"]

    # Verify users indexes
    users_indexes = mongo.users.index_information()
    assert "criado_em_-1" in users_indexes
    assert users_indexes["criado_em_-1"]["key"] == [("criado_em", -1)]

    # Verify players indexes
    players_indexes = mongo.players.index_information()
    assert "admin_id_1_nick_1" in players_indexes
    assert players_indexes["admin_id_1_nick_1"]["key"] == [("admin_id", 1), ("nick", 1)]
    assert "estatisticas.vitorias_-1_estatisticas.kd_ratio_-1" in players_indexes
    assert players_indexes["estatisticas.vitorias_-1_estatisticas.kd_ratio_-1"]["key"] == [
        ("estatisticas.vitorias", -1),
        ("estatisticas.kd_ratio", -1),
    ]

    # Verify teams indexes
    teams_indexes = mongo.teams.index_information()
    assert "jogadores.jogador_id_1" in teams_indexes
    assert teams_indexes["jogadores.jogador_id_1"]["key"] == [("jogadores.jogador_id", 1)]
    assert "admin_id_1_nome_1" in teams_indexes
    assert teams_indexes["admin_id_1_nome_1"]["key"] == [("admin_id", 1), ("nome", 1)]
    assert "admin_id_1_jogo_1_nome_1" in teams_indexes
    assert teams_indexes["admin_id_1_jogo_1_nome_1"]["key"] == [("admin_id", 1), ("jogo", 1), ("nome", 1)]

    # Verify championships indexes
    championships_indexes = mongo.championships.index_information()
    assert "admin_id_1_criado_em_-1" in championships_indexes
    assert championships_indexes["admin_id_1_criado_em_-1"]["key"] == [("admin_id", 1), ("criado_em", -1)]
    assert "times_inscritos_1_datas.inicio_-1" in championships_indexes
    assert championships_indexes["times_inscritos_1_datas.inicio_-1"]["key"] == [
        ("times_inscritos", 1),
        ("datas.inicio", -1),
    ]

    # Verify matches indexes
    matches_indexes = mongo.matches.index_information()
    assert "campeonato_id_1_data_partida_1" in matches_indexes
    assert matches_indexes["campeonato_id_1_data_partida_1"]["key"] == [("campeonato_id", 1), ("data_partida", 1)]
    assert "admin_id_1_data_partida_-1" in matches_indexes
    assert matches_indexes["admin_id_1_data_partida_-1"]["key"] == [("admin_id", 1), ("data_partida", -1)]

    # Verify tickets indexes
    tickets_indexes = mongo.tickets.index_information()
    assert "admin_id_1_vendido_em_-1" in tickets_indexes
    assert tickets_indexes["admin_id_1_vendido_em_-1"]["key"] == [("admin_id", 1), ("vendido_em", -1)]


def test_player_deletion_removes_user_account(monkeypatch):
    flask_app = build_test_app(monkeypatch)
    mongo = flask_app.extensions["mongo"]
    services = flask_app.extensions["services"]

    # 1. Create admin and player
    admin_id = ObjectId()
    current_user = {"role": "ADMIN", "_id": admin_id}

    player_data = {
        "nick": "TestPlayer",
        "nome": "Test Name",
        "login": "test.player",
        "senha": "password123",
        "jogo_principal": "CS2",
        "rank_competitivo": "Sem Rank",
        "premier_rating": "0",
    }

    errors = services["players"].create_player(current_user, player_data)
    assert not errors

    # Verify both documents exist
    player = mongo.players.find_one({"nick": "TestPlayer"})
    assert player is not None
    player_id = player["_id"]

    user = mongo.users.find_one({"player_id": player_id})
    assert user is not None

    # 2. Delete player
    deleted = services["players"].delete_player(current_user, player_id)
    assert deleted is True

    # Verify both documents are deleted
    assert mongo.players.find_one({"_id": player_id}) is None
    assert mongo.users.find_one({"player_id": player_id}) is None


def test_player_ranking_report_filters_by_date(monkeypatch):
    flask_app = build_test_app(monkeypatch)
    mongo = flask_app.extensions["mongo"]
    services = flask_app.extensions["services"]

    admin_id = ObjectId()
    current_user = {"role": "ADMIN", "_id": admin_id}

    # 1. Insert players with different created_at dates
    now = datetime.now(UTC).replace(tzinfo=None)
    mongo.players.insert_many([
        {
            "nick": "OldPlayer",
            "nome": "Old",
            "jogo_principal": "CS2",
            "admin_id": admin_id,
            "estatisticas": {"partidas_jogadas": 10, "vitorias": 8, "derrotas": 2, "kd_ratio": 1.5},
            "criado_em": now - timedelta(days=10),
        },
        {
            "nick": "NewPlayer",
            "nome": "New",
            "jogo_principal": "CS2",
            "admin_id": admin_id,
            "estatisticas": {"partidas_jogadas": 5, "vitorias": 4, "derrotas": 1, "kd_ratio": 1.2},
            "criado_em": now,
        }
    ])

    # 2. Get report with date range filtering only today/recent
    start_date = (now - timedelta(days=2)).strftime("%Y-%m-%d")
    end_date = (now + timedelta(days=2)).strftime("%Y-%m-%d")

    # Get ranking report
    report, warning = services["reports"].get_report(
        current_user,
        "player-ranking",
        start_date,
        end_date
    )
    assert not warning
    assert report is not None

    # Should only contain NewPlayer, not OldPlayer
    nicks = [row["Nick"] for row in report["rows"]]
    assert "NewPlayer" in nicks
    assert "OldPlayer" not in nicks
    assert len(report["rows"]) == 1
    assert report["rows"][0]["Posicao"] == 1


def test_championship_discord_webhook_configuration(monkeypatch):
    flask_app = build_test_app(monkeypatch)
    mongo = flask_app.extensions["mongo"]
    services = flask_app.extensions["services"]

    admin_id = ObjectId()
    current_user = {"role": "ADMIN", "_id": admin_id}
    webhook_url = "https://discord.com/api/webhooks/123/token"

    errors = services["championships"].create_championship(
        current_user,
        {
            "nome": "Discord Cup",
            "jogo": "CS2",
            "formato": "mata-mata",
            "max_times": "8",
            "data_inicio": "2026-05-25",
            "data_fim": "2026-05-30",
            "discord_webhook_url": webhook_url,
        },
    )

    assert not errors
    camp = mongo.championships.find_one({"nome": "Discord Cup"})
    assert camp["discord_webhook_url"] == webhook_url

    errors = services["championships"].update_championship_settings(
        current_user,
        camp["_id"],
        {
            "nome": "Discord Cup Atualizada",
            "jogo": "Valorant",
            "formato": "grupos",
            "max_times": "10",
            "data_inicio": "2026-06-01",
            "data_fim": "2026-06-10",
            "discord_webhook_url": "",
        },
    )

    assert not errors
    updated = mongo.championships.find_one({"_id": camp["_id"]})
    assert updated["discord_webhook_url"] == ""


def test_discord_notifications_are_sent_on_match_start_and_result(monkeypatch):
    flask_app = build_test_app(monkeypatch)
    mongo = flask_app.extensions["mongo"]
    services = flask_app.extensions["services"]

    class FakeNotifier:
        def __init__(self):
            self.messages = []

        def send_message(self, webhook_url, content):
            self.messages.append((webhook_url, content))
            return True

    notifier = FakeNotifier()
    services["matches"].discord_notifier = notifier

    admin_id = ObjectId()
    current_user = {"role": "ADMIN", "_id": admin_id}
    webhook_url = "https://discord.com/api/webhooks/123/token"
    time_a_id = mongo.teams.insert_one({"nome": "Team A", "tag": "A", "jogo": "CS2", "admin_id": admin_id, "jogadores": []}).inserted_id
    time_b_id = mongo.teams.insert_one({"nome": "Team B", "tag": "B", "jogo": "CS2", "admin_id": admin_id, "jogadores": []}).inserted_id
    camp_id = mongo.championships.insert_one(
        {
            "nome": "Arena Discord",
            "jogo": "CS2",
            "status": "EM_ANDAMENTO",
            "admin_id": admin_id,
            "discord_webhook_url": webhook_url,
            "datas": {"inicio": datetime.now(UTC), "fim": datetime.now(UTC) + timedelta(days=1)},
        }
    ).inserted_id
    match_id = mongo.matches.insert_one(
        {
            "admin_id": admin_id,
            "campeonato_id": camp_id,
            "fase": "Final",
            "time_a": {"time_id": time_a_id, "nome": "Team A", "placar": 0},
            "time_b": {"time_id": time_b_id, "nome": "Team B", "placar": 0},
            "mapa": "Mirage",
            "status": "agendada",
            "data_partida": datetime.now(UTC).replace(tzinfo=None),
            "rounds": [],
        }
    ).inserted_id

    error, updated_match = services["matches"].add_round(current_user, match_id, time_a_id, "elimination")
    assert not error
    assert updated_match["status"] == "em_andamento"
    assert len(notifier.messages) == 1
    assert notifier.messages[0][0] == webhook_url
    assert "Partida iniciada" in notifier.messages[0][1]

    error, _ = services["matches"].add_round(current_user, match_id, time_b_id, "objective")
    assert not error
    assert len(notifier.messages) == 1

    error, returned_camp_id = services["matches"].register_result(current_user, match_id, "2", "1")
    assert not error
    assert returned_camp_id == camp_id
    assert len(notifier.messages) == 2
    assert "Resultado registrado" in notifier.messages[1][1]


def test_discord_notification_failure_does_not_interrupt_match_flow(monkeypatch):
    flask_app = build_test_app(monkeypatch)
    mongo = flask_app.extensions["mongo"]
    services = flask_app.extensions["services"]

    class FailingNotifier:
        def send_message(self, webhook_url, content):
            raise RuntimeError("discord offline")

    services["matches"].discord_notifier = FailingNotifier()

    admin_id = ObjectId()
    current_user = {"role": "ADMIN", "_id": admin_id}
    time_a_id = mongo.teams.insert_one({"nome": "Team A", "tag": "A", "jogo": "CS2", "admin_id": admin_id, "jogadores": []}).inserted_id
    time_b_id = mongo.teams.insert_one({"nome": "Team B", "tag": "B", "jogo": "CS2", "admin_id": admin_id, "jogadores": []}).inserted_id
    camp_id = mongo.championships.insert_one(
        {
            "nome": "Arena Discord",
            "jogo": "CS2",
            "status": "EM_ANDAMENTO",
            "admin_id": admin_id,
            "discord_webhook_url": "https://discord.com/api/webhooks/123/token",
            "datas": {"inicio": datetime.now(UTC), "fim": datetime.now(UTC) + timedelta(days=1)},
        }
    ).inserted_id
    match_id = mongo.matches.insert_one(
        {
            "admin_id": admin_id,
            "campeonato_id": camp_id,
            "fase": "Final",
            "time_a": {"time_id": time_a_id, "nome": "Team A", "placar": 0},
            "time_b": {"time_id": time_b_id, "nome": "Team B", "placar": 0},
            "status": "agendada",
            "data_partida": datetime.now(UTC).replace(tzinfo=None),
            "rounds": [],
        }
    ).inserted_id

    error, updated_match = services["matches"].add_round(current_user, match_id, time_a_id, "elimination")
    assert not error
    assert updated_match["status"] == "em_andamento"

    error, returned_camp_id = services["matches"].register_result(current_user, match_id, "1", "0")
    assert not error
    assert returned_camp_id == camp_id
    assert mongo.matches.find_one({"_id": match_id})["status"] == "finalizada"


def test_match_presence_checkin_flow(monkeypatch):
    flask_app = build_test_app(monkeypatch)
    mongo = flask_app.extensions["mongo"]
    services = flask_app.extensions["services"]

    admin_id = ObjectId()
    current_user_admin = {"role": "ADMIN", "_id": admin_id}

    # 1. Create a match
    time_a_id = ObjectId()
    time_b_id = ObjectId()
    camp_id = ObjectId()
    match_id = mongo.matches.insert_one({
        "admin_id": admin_id,
        "campeonato_id": camp_id,
        "fase": "Semifinal",
        "time_a": {"time_id": time_a_id, "nome": "Team A", "placar": 0},
        "time_b": {"time_id": time_b_id, "nome": "Team B", "placar": 0},
        "vencedor_id": None,
        "mapa": "Mirage",
        "data_partida": datetime.now(UTC).replace(tzinfo=None) + timedelta(minutes=15),
        "status": "agendada",
    }).inserted_id

    # 2. Try to confirm check-in before solicitar
    error, _ = services["matches"].confirmar_presenca(current_user_admin, match_id, time_a_id)
    assert error == "O check-in nao foi solicitado para esta partida."

    # 3. Admin solicits check-in (30 minutes in advance)
    error, returned_camp_id = services["matches"].solicitar_checkin(current_user_admin, match_id, "30")
    assert not error
    assert returned_camp_id == camp_id

    # Verify checkin config exists in database
    match = mongo.matches.find_one({"_id": match_id})
    assert match.get("checkin") is not None
    assert match["checkin"]["solicitado"] is True
    assert match["checkin"]["antecedencia_minutos"] == 30

    # 4. Admin forces check-in (allowed at any time)
    error, _ = services["matches"].confirmar_presenca(current_user_admin, match_id, time_a_id)
    assert not error

    # Verify time_a is confirmed
    match = mongo.matches.find_one({"_id": match_id})
    assert match["checkin"]["time_a_confirmado"] is True
    assert match["checkin"]["time_b_confirmado"] is False

    # 5. Non-member player tries to confirm check-in for team_b
    player_id = ObjectId()
    current_user_player = {"role": "PLAYER", "_id": ObjectId(), "player_id": player_id}
    # Create player and assign to a different team
    mongo.players.insert_one({"_id": player_id, "nick": "OtherPlayer", "admin_id": admin_id})
    
    error, _ = services["matches"].confirmar_presenca(current_user_player, match_id, time_b_id)
    assert error == "Acesso negado para confirmar presenca deste time."

    # 6. Member player confirms check-in for team_b (inside the window)
    player_b_id = ObjectId()
    current_user_player_b = {"role": "PLAYER", "_id": ObjectId(), "player_id": player_b_id}
    # Create player and team_b with player as member
    mongo.players.insert_one({"_id": player_b_id, "nick": "PlayerB", "admin_id": admin_id})
    mongo.teams.insert_one({
        "_id": time_b_id,
        "nome": "Team B",
        "tag": "TMB",
        "jogo": "CS2",
        "admin_id": admin_id,
        "jogadores": [{"jogador_id": player_b_id, "nick": "PlayerB", "funcao": "Capitao"}]
    })

    # Player B can confirm because match is in 15 minutes and advance is 30 minutes (current time is inside the 30-min window)
    error, _ = services["matches"].confirmar_presenca(current_user_player_b, match_id, time_b_id)
    assert not error

    # Verify both teams are confirmed
    match = mongo.matches.find_one({"_id": match_id})
    assert match["checkin"]["time_a_confirmado"] is True
    assert match["checkin"]["time_b_confirmado"] is True


def test_referee_crud_and_validation_flow(monkeypatch):
    flask_app = build_test_app(monkeypatch)
    mongo = flask_app.extensions["mongo"]
    services = flask_app.extensions["services"]

    admin_id = ObjectId()
    current_user_admin = {"role": "ADMIN", "_id": admin_id}

    # 1. Create a referee with invalid data (fails validation)
    referee_data_invalid = {
        "nome": "",
        "email": "invalidemail",
        "contato": "123456",
        "disponibilidade": "",
        "login": "ref1",
        "senha": "123"
    }
    errors = services["arbitros"].create_referee(current_user_admin, referee_data_invalid)
    assert len(errors) > 0
    assert "Nome e obrigatorio." in errors
    assert "E-mail invalido." in errors
    assert "Disponibilidade e obrigatoria." in errors
    assert "Senha deve ter ao menos 6 caracteres." in errors

    # 2. Create a referee with valid data
    referee_data_valid = {
        "nome": "Arbitro Um",
        "email": "arbitro.um@email.com",
        "contato": "99999-9999",
        "disponibilidade": "Finais de semana",
        "login": "arbitro.um",
        "senha": "password123",
        "campeonatos_ids": []
    }
    errors = services["arbitros"].create_referee(current_user_admin, referee_data_valid)
    assert not errors

    # Verify referee document is created
    referee = mongo.arbitros.find_one({"email": "arbitro.um@email.com"})
    assert referee is not None
    assert referee["nome"] == "Arbitro Um"
    assert referee["admin_id"] == admin_id

    # Verify associated user account is created with role REFEREE
    user = mongo.users.find_one({"login": "arbitro.um"})
    assert user is not None
    assert user["role"] == "REFEREE"

    # 3. Create a duplicate referee (by login)
    referee_data_dup_login = {
        "nome": "Arbitro Dois",
        "email": "arbitro.dois@email.com",
        "contato": "99999-9999",
        "disponibilidade": "Finais de semana",
        "login": "arbitro.um",
        "senha": "password123"
    }
    errors = services["arbitros"].create_referee(current_user_admin, referee_data_dup_login)
    assert "Login ja existe." in errors

    # 4. Create a duplicate referee (by email, case insensitive)
    referee_data_dup_email = {
        "nome": "Arbitro Dois",
        "email": "ARBITRO.UM@email.com",
        "contato": "99999-9999",
        "disponibilidade": "Finais de semana",
        "login": "arbitro.dois",
        "senha": "password123"
    }
    errors = services["arbitros"].create_referee(current_user_admin, referee_data_dup_email)
    assert "Este e-mail ja esta cadastrado para este organizador." in errors


def test_championship_archiving_blocks_mutations(monkeypatch):
    flask_app = build_test_app(monkeypatch)
    mongo = flask_app.extensions["mongo"]
    services = flask_app.extensions["services"]

    admin_id = ObjectId()
    current_user_admin = {"role": "ADMIN", "_id": admin_id}

    # 1. Create a championship
    camp_id = mongo.championships.insert_one({
        "nome": "Copa Master",
        "jogo": "CS2",
        "formato": "mata-mata",
        "max_times": 8,
        "status": "INSCRICAO",
        "admin_id": admin_id,
        "times_inscritos": [],
        "datas": {"inicio": datetime.now(UTC), "fim": datetime.now(UTC) + timedelta(days=5)},
        "criado_em": datetime.now(UTC)
    }).inserted_id

    # 2. Archive the championship
    err = services["championships"].update_status(current_user_admin, camp_id, "ARQUIVADO")
    assert not err

    # Verify status is updated in db
    camp = mongo.championships.find_one({"_id": camp_id})
    assert camp["status"] == "ARQUIVADO"

    # 3. Try to enroll a team (should be blocked because status is not INSCRICAO)
    time_id = ObjectId()
    mongo.teams.insert_one({"_id": time_id, "nome": "Team A", "tag": "TMA", "jogo": "CS2", "admin_id": admin_id})
    err = services["championships"].enroll_team(current_user_admin, camp_id, time_id)
    assert err == "Este campeonato nao esta aceitando inscricoes."

    # 4. Try to unenroll a team (should be blocked)
    err = services["championships"].unenroll_team(current_user_admin, camp_id, time_id)
    assert "Nao e possivel alterar times de um campeonato finalizado ou arquivado." in err

    # 5. Try to delete the championship (should be blocked)
    deleted = services["championships"].delete_championship(current_user_admin, camp_id)
    assert deleted is False

    # 6. Try to create a match (should be blocked)
    form_data = {
        "time_a_id": str(time_id),
        "time_b_id": str(ObjectId()),
        "fase": "Final",
        "mapa": "Mirage",
        "data_partida": "2026-05-25T12:00"
    }
    err = services["matches"].create_match(current_user_admin, camp_id, form_data)
    assert "Nao e possivel adicionar partidas a um campeonato finalizado ou arquivado." in err

    # 7. Try match operations (register result, check-in)
    match_id = mongo.matches.insert_one({
        "admin_id": admin_id,
        "campeonato_id": camp_id,
        "time_a": {"time_id": time_id, "nome": "Team A", "placar": 0},
        "time_b": {"time_id": ObjectId(), "nome": "Team B", "placar": 0},
        "status": "agendada"
    }).inserted_id

    # Register result
    err, _ = services["matches"].register_result(current_user_admin, match_id, "13", "10")
    assert err == "Nao e possivel alterar partidas de um campeonato arquivado."

    # Solicitar check-in
    err, _ = services["matches"].solicitar_checkin(current_user_admin, match_id, "30")
    assert err == "Nao e possivel gerenciar check-in de partidas em campeonatos arquivados."

    # Confirmar presenca
    err, _ = services["matches"].confirmar_presenca(current_user_admin, match_id, time_id)
    assert err == "O check-in nao e permitido para campeonatos arquivados."


def test_match_rounds_referee_workflow(monkeypatch):
    flask_app = build_test_app(monkeypatch)
    mongo = flask_app.extensions["mongo"]
    password_hasher = PasswordHasher()

    # Create admin, referee, players, championship, teams, and match
    admin_id = mongo.users.insert_one({
        "nome": "Organizador",
        "login": "organizador",
        "role": "ADMIN",
        "senha_hash": password_hasher.hash("admin123"),
        "ativo": True,
        "must_change_password": False,
        "criado_em": datetime.now(UTC),
    }).inserted_id

    # Create referee
    referee_db_id = ObjectId()
    referee_user_id = mongo.users.insert_one({
        "nome": "Arbitro Julio",
        "login": "julio.ref",
        "role": "REFEREE",
        "admin_id": admin_id,
        "referee_id": referee_db_id,
        "senha_hash": password_hasher.hash("julio123"),
        "ativo": True,
        "must_change_password": False,
        "criado_em": datetime.now(UTC),
    }).inserted_id

    # Create an unauthorized referee user
    unauthorized_ref_db_id = ObjectId()
    mongo.users.insert_one({
        "nome": "Arbitro Pedro",
        "login": "pedro.ref",
        "role": "REFEREE",
        "admin_id": admin_id,
        "referee_id": unauthorized_ref_db_id,
        "senha_hash": password_hasher.hash("pedro123"),
        "ativo": True,
        "must_change_password": False,
        "criado_em": datetime.now(UTC),
    })

    # Create championship
    camp_id = mongo.championships.insert_one({
        "nome": "Masters CS2",
        "jogo": "CS2",
        "status": "EM_ANDAMENTO",
        "admin_id": admin_id,
        "datas": {"inicio": datetime.now(UTC), "fim": datetime.now(UTC)},
    }).inserted_id

    # Create teams
    time_a_id = mongo.teams.insert_one({
        "nome": "Team Red",
        "tag": "RED",
        "jogo": "CS2",
        "admin_id": admin_id,
        "jogadores": []
    }).inserted_id

    time_b_id = mongo.teams.insert_one({
        "nome": "Team Blue",
        "tag": "BLU",
        "jogo": "CS2",
        "admin_id": admin_id,
        "jogadores": []
    }).inserted_id

    # Create match with Julio as the designated referee
    match_id = mongo.matches.insert_one({
        "admin_id": admin_id,
        "campeonato_id": camp_id,
        "time_a": {"time_id": time_a_id, "nome": "Team Red", "placar": 0},
        "time_b": {"time_id": time_b_id, "nome": "Team Blue", "placar": 0},
        "status": "agendada",
        "arbitro_id": referee_db_id,
        "rounds": []
    }).inserted_id

    client = flask_app.test_client()

    # 1. Try accessing rounds control without logging in (should redirect)
    resp = client.get(f"/partidas/{match_id}/rounds")
    assert resp.status_code == 302

    # 2. Login as unauthorized referee and try to access (should redirect with flash/permission denied)
    client.post("/login", data={"modo": "login", "identificador": "pedro.ref", "senha": "pedro123"})
    resp = client.get(f"/partidas/{match_id}/rounds")
    assert resp.status_code == 302
    
    # 3. Login as authorized referee (Julio)
    client.get("/logout")
    client.post("/login", data={"modo": "login", "identificador": "julio.ref", "senha": "julio123"})
    
    # Access the HTML page (should succeed)
    resp = client.get(f"/partidas/{match_id}/rounds")
    assert resp.status_code == 200
    assert b"Controle de Rounds" in resp.data
    assert b"Team Red" in resp.data
    assert b"Team Blue" in resp.data

    # 4. Add round via API vencer
    resp = client.post(f"/partidas/{match_id}/rounds/vencer", json={
        "vencedor_id": str(time_a_id),
        "metodo": "elimination"
    })
    assert resp.status_code == 200
    data = resp.get_json()
    assert data["success"] is True
    assert data["score_a"] == 1
    assert data["score_b"] == 0
    assert len(data["rounds"]) == 1
    assert data["rounds"][0]["metodo"] == "elimination"
    assert data["rounds"][0]["vencedor_id"] == str(time_a_id)

    # 5. Add second round via API vencer (objective for Team B)
    resp = client.post(f"/partidas/{match_id}/rounds/vencer", json={
        "vencedor_id": str(time_b_id),
        "metodo": "objective"
    })
    assert resp.status_code == 200
    data = resp.get_json()
    assert data["success"] is True
    assert data["score_a"] == 1
    assert data["score_b"] == 1
    assert len(data["rounds"]) == 2
    assert data["rounds"][1]["metodo"] == "objective"
    assert data["rounds"][1]["vencedor_id"] == str(time_b_id)

    # 6. Undo the last round via API desfazer
    resp = client.post(f"/partidas/{match_id}/rounds/desfazer")
    assert resp.status_code == 200
    data = resp.get_json()
    assert data["success"] is True
    assert data["score_a"] == 1
    assert data["score_b"] == 0
    assert len(data["rounds"]) == 1

    # 7. Finalize the match via API finalizar
    resp = client.post(f"/partidas/{match_id}/rounds/finalizar")
    assert resp.status_code == 200
    data = resp.get_json()
    assert data["success"] is True
    assert "redirect_url" in data

    # Verify match status is updated to finalizada in DB
    updated_match = mongo.matches.find_one({"_id": match_id})
    assert updated_match["status"] == "finalizada"
    assert updated_match["time_a"]["placar"] == 1
    assert updated_match["time_b"]["placar"] == 0


