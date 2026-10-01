from datetime import UTC, datetime, timedelta
import mongomock
import fakeredis
from bson import ObjectId

import app.infrastructure.cache.redis_cache as cache_module
import app.infrastructure.db.mongo as mongo_module
from app.application.services import (
    GAME_VALORANT,
    GAME_LOL,
    GAME_CLASH_ROYALE,
    GAME_CS2,
    normalize_game_name,
)


def build_test_app(monkeypatch):
    monkeypatch.setattr(mongo_module, "MongoClient", mongomock.MongoClient)
    monkeypatch.setattr(cache_module.redis, "from_url", fakeredis.FakeRedis.from_url)

    from app import create_app

    return create_app()


def test_game_name_normalization():
    assert normalize_game_name("lol") == GAME_LOL
    assert normalize_game_name("League of Legends") == GAME_LOL
    assert normalize_game_name("cr") == GAME_CLASH_ROYALE
    assert normalize_game_name("Clash Royale") == GAME_CLASH_ROYALE
    assert normalize_game_name("vlr") == GAME_VALORANT
    assert normalize_game_name("Valorant") == GAME_VALORANT
    assert normalize_game_name("cs:go") == GAME_CS2
    assert normalize_game_name("CS2") == GAME_CS2


def test_create_player_lol_and_clash_royale(monkeypatch):
    flask_app = build_test_app(monkeypatch)
    services = flask_app.extensions["services"]
    admin_id = ObjectId()
    current_user = {"_id": admin_id, "role": "ADMIN"}

    # 1. League of Legends Player
    lol_data = {
        "nick": "FakerJunior",
        "nome": "Lee Sang-hyeok",
        "jogo_principal": "League of Legends",
        "elo_lol": "Desafiante",
        "rota_principal": "Meio",
        "campeao_favorito": "Ahri",
        "contato": "11999999999",
    }
    errors = services["players"].create_player(current_user, lol_data)
    assert errors == []

    p_lol = services["players"].player_repo.find_by_nick_case_insensitive("FakerJunior", admin_id)
    assert p_lol is not None
    assert p_lol["jogo_principal"] == "League of Legends"
    assert p_lol["elo_lol"] == "Desafiante"
    assert p_lol["rota_principal"] == "Meio"
    assert p_lol["campeao_favorito"] == "Ahri"

    # 2. Clash Royale Player
    clash_data = {
        "nick": "MortenBR",
        "nome": "Lucas Silva",
        "jogo_principal": "Clash Royale",
        "trofeus_clash": 7500,
        "arena_clash": "Campeão Supremo",
        "carta_favorita": "Corredor",
        "contato": "75988888888",
    }
    errors = services["players"].create_player(current_user, clash_data)
    assert errors == []

    p_clash = services["players"].player_repo.find_by_nick_case_insensitive("MortenBR", admin_id)
    assert p_clash is not None
    assert p_clash["jogo_principal"] == "Clash Royale"
    assert p_clash["trofeus_clash"] == 7500
    assert p_clash["arena_clash"] == "Campeão Supremo"
    assert p_clash["carta_favorita"] == "Corredor"


def test_create_championships_and_solo_team_for_finc(monkeypatch):
    flask_app = build_test_app(monkeypatch)
    services = flask_app.extensions["services"]
    admin_id = ObjectId()
    current_user = {"_id": admin_id, "role": "ADMIN"}

    # 1. Create Clash Royale Championship (1x1)
    cr_camp_data = {
        "nome": "FINC 2026 - Clash Royale",
        "jogo": "Clash Royale",
        "formato": "mata-mata",
        "max_times": 32,
        "data_inicio": "2026-10-20",
        "data_fim": "2026-10-22",
    }
    errors = services["championships"].validate(cr_camp_data)
    assert errors == []

    # 2. Create League of Legends Championship
    lol_camp_data = {
        "nome": "FINC 2026 - League of Legends",
        "jogo": "League of Legends",
        "formato": "mata-mata",
        "max_times": 16,
        "data_inicio": "2026-10-20",
        "data_fim": "2026-10-22",
    }
    errors = services["championships"].validate(lol_camp_data)
    assert errors == []

    # 3. Create a Clash Royale solo competitor team (1 player)
    p_id = services["players"].player_repo.insert({
        "nick": "RoyaleKing",
        "nome": "Arthur Pendelton",
        "nome_real": "Arthur Pendelton",
        "jogo_principal": "Clash Royale",
        "admin_id": admin_id,
        "estatisticas": {},
        "criado_em": datetime.now(UTC),
    })

    form_data = {f"funcao_{p_id}": "Competidor"}
    team_errors = services["teams"].create_team(
        current_user=current_user,
        nome="RoyaleKing",
        tag="RK",
        jogo="Clash Royale",
        ids_selecionados=[str(p_id)],
        form_data=form_data,
    )
    assert team_errors == []
    teams = services["teams"].team_repo.list_all({"nome": "RoyaleKing", "admin_id": admin_id})
    assert len(teams) == 1
    team = teams[0]
    assert team["jogo"] == "Clash Royale"
    assert len(team["jogadores"]) == 1
    assert team["jogadores"][0]["nick"] == "RoyaleKing"


def test_finc_eligibility_and_academic_fields(monkeypatch):
    flask_app = build_test_app(monkeypatch)
    services = flask_app.extensions["services"]
    admin_id = ObjectId()
    current_user = {"_id": admin_id, "role": "ADMIN"}

    # 1. Underage participant (born 2008-10-21: will be 17 on 2026-10-20)
    underage_data = {
        "nick": "KidGamer",
        "nome": "Menor de Idade",
        "jogo_principal": "Valorant",
        "data_nascimento": "2008-10-21",
    }
    errors = services["players"].validate(underage_data)
    assert any("18 anos completos" in err for err in errors)

    # 2. Invalid date format
    bad_date_data = {
        "nick": "InvalidDate",
        "nome": "Data Invalida",
        "jogo_principal": "Valorant",
        "data_nascimento": "31-02-2000",
    }
    errors = services["players"].validate(bad_date_data)
    assert any("Data de nascimento invalida" in err for err in errors)

    # 3. Invalid email
    bad_email_data = {
        "nick": "InvalidEmail",
        "nome": "Email Invalido",
        "jogo_principal": "Valorant",
        "email": "notanemail",
    }
    errors = services["players"].validate(bad_email_data)
    assert any("E-mail invalido" in err for err in errors)

    # 4. Valid eligible participant (born 2004-03-15)
    valid_data = {
        "nick": "AspasUNEF",
        "nome": "Erick Santos",
        "jogo_principal": "Valorant",
        "email": "erick.santos@unef.edu.br",
        "contato": "75999887766",
        "data_nascimento": "2004-03-15",
        "instituicao": "UNEF",
        "curso": "Engenharia de Software",
        "matricula": "202410992",
        "numero_ingresso_finc": "FINC-774921",
        "rank_ato": "Radiante",
        "agente_principal": "Jett",
    }
    create_errors = services["players"].create_player(current_user, valid_data)
    assert create_errors == []

    player = services["players"].player_repo.find_by_nick_case_insensitive("AspasUNEF", admin_id)
    assert player is not None
    assert player["email"] == "erick.santos@unef.edu.br"
    assert player["contato"] == "75999887766"
    assert player["data_nascimento"] == "2004-03-15"
    assert player["instituicao"] == "UNEF"
    assert player["curso"] == "Engenharia de Software"
    assert player["matricula"] == "202410992"
    assert player["numero_ingresso_finc"] == "FINC-774921"

    # 5. Update academic fields
    update_data = {
        "nick": "AspasUNEF",
        "nome": "Erick Santos Atualizado",
        "jogo_principal": "Valorant",
        "email": "erick.santos@unef.edu.br",
        "contato": "75999887766",
        "data_nascimento": "2004-03-15",
        "instituicao": "UNEF Centro Universitário",
        "curso": "Ciência da Computação",
        "matricula": "202410992",
        "numero_ingresso_finc": "FINC-774921-VIP",
        "rank_ato": "Radiante",
        "agente_principal": "Jett",
    }
    update_errors = services["players"].update_player(current_user, player["_id"], update_data)
    assert update_errors == []

    updated = services["players"].player_repo.find_by_id(player["_id"])
    assert updated["nome"] == "Erick Santos Atualizado"
    assert updated["instituicao"] == "UNEF Centro Universitário"
    assert updated["curso"] == "Ciência da Computação"
    assert updated["numero_ingresso_finc"] == "FINC-774921-VIP"


def test_series_format_and_fearless_draft_rules():
    from app.application.services import (
        SERIES_MD1,
        SERIES_MD3,
        SERIES_MD5,
        get_default_series_format,
        is_fearless_draft,
    )

    # Clash Royale (Anexo I.1.1): Quartas e Semis em MD3; Grande Final em MD5
    assert get_default_series_format("Clash Royale", "Quartas de Final") == SERIES_MD3
    assert get_default_series_format("Clash Royale", "Semifinal") == SERIES_MD3
    assert get_default_series_format("Clash Royale", "Grande Final") == SERIES_MD5

    # VALORANT (Anexo II.1.1): Semifinais em MD1; Grande Final em MD3
    assert get_default_series_format("Valorant", "Quartas de Final") == SERIES_MD1
    assert get_default_series_format("Valorant", "Semifinal") == SERIES_MD1
    assert get_default_series_format("Valorant", "Grande Final") == SERIES_MD3

    # League of Legends (Anexo III.1.1 & III.2.2): Semis MD1; Grande Final MD3 Fearless Draft
    assert get_default_series_format("League of Legends", "Semifinal") == SERIES_MD1
    assert get_default_series_format("League of Legends", "Grande Final") == SERIES_MD3
    assert is_fearless_draft("League of Legends", "Grande Final") is True
    assert is_fearless_draft("League of Legends", "Semifinal") is False
    assert is_fearless_draft("Valorant", "Grande Final") is False
    assert is_fearless_draft("Clash Royale", "Grande Final") is False


def test_generate_matches_sets_series_format(monkeypatch):
    flask_app = build_test_app(monkeypatch)
    services = flask_app.extensions["services"]
    admin_id = ObjectId()
    current_user = {"_id": admin_id, "role": "ADMIN"}

    # Create 2 teams
    tid_1 = services["teams"].team_repo.insert({
        "admin_id": admin_id,
        "nome": "Team Alpha",
        "tag": "ALP",
        "jogo": "League of Legends",
        "jogadores": [],
        "criado_em": datetime.now(UTC),
    })
    tid_2 = services["teams"].team_repo.insert({
        "admin_id": admin_id,
        "nome": "Team Omega",
        "tag": "OMG",
        "jogo": "League of Legends",
        "jogadores": [],
        "criado_em": datetime.now(UTC),
    })

    # Create LoL Championship with 2 teams -> Grande Final
    camp_id = services["championships"].championship_repo.insert({
        "admin_id": admin_id,
        "nome": "FINC 2026 - LoL Finals",
        "jogo": "League of Legends",
        "formato": "mata-mata",
        "max_times": 2,
        "status": "INSCRICAO",
        "times_inscritos": [tid_1, tid_2],
        "datas": {"inicio": datetime.now(UTC), "fim": datetime.now(UTC)},
    })

    errors = services["championships"].generate_matches(current_user, camp_id)
    assert errors == []

    matches = services["matches"].match_repo.list_by_championship(camp_id)
    assert len(matches) == 1
    match = matches[0]
    assert match["fase"] == "Grande Final"
    assert match["formato_serie"] == "MD3"
    assert match["fearless_draft"] is True
    assert match["placar_serie_a"] == 0
    assert match["placar_serie_b"] == 0
    assert match["campeoes_banidos_fearless"] == []


def test_record_series_game_and_fearless_draft_lockouts(monkeypatch):
    flask_app = build_test_app(monkeypatch)
    services = flask_app.extensions["services"]
    admin_id = ObjectId()
    current_user = {"_id": admin_id, "role": "ADMIN"}

    tid_a = services["teams"].team_repo.insert({
        "admin_id": admin_id,
        "nome": "Alpha",
        "tag": "ALP",
        "jogo": "League of Legends",
        "jogadores": [],
        "criado_em": datetime.now(UTC),
    })
    tid_b = services["teams"].team_repo.insert({
        "admin_id": admin_id,
        "nome": "Beta",
        "tag": "BET",
        "jogo": "League of Legends",
        "jogadores": [],
        "criado_em": datetime.now(UTC),
    })
    camp_id = services["championships"].championship_repo.insert({
        "admin_id": admin_id,
        "nome": "FINC LoL",
        "jogo": "League of Legends",
        "formato": "mata-mata",
        "max_times": 2,
        "status": "EM_ANDAMENTO",
        "times_inscritos": [tid_a, tid_b],
    })
    match_id = services["matches"].match_repo.insert({
        "admin_id": admin_id,
        "campeonato_id": camp_id,
        "fase": "Grande Final",
        "time_a": {"time_id": tid_a, "nome": "Alpha", "placar": 0},
        "time_b": {"time_id": tid_b, "nome": "Beta", "placar": 0},
        "status": "agendada",
        "formato_serie": "MD3",
        "fearless_draft": True,
        "campeoes_banidos_fearless": [],
        "jogos_serie": [],
    })

    # Jogo 1 da Série
    champs_a_game1 = ["Ahri", "Lee Sin", "Aatrox", "Jinx", "Thresh"]
    champs_b_game1 = ["Syndra", "Vi", "Renekton", "Kaisa", "Nautilus"]
    err, m1 = services["matches"].record_series_game(
        current_user=current_user,
        match_id=match_id,
        vencedor_id=tid_a,
        score_a=1,
        score_b=0,
        mapa="Summoner's Rift",
        campeoes_a=champs_a_game1,
        campeoes_b=champs_b_game1,
    )
    assert err is None
    assert m1["placar_serie_a"] == 1
    assert m1["placar_serie_b"] == 0
    assert m1["status"] == "em_andamento"
    assert len(m1["jogos_serie"]) == 1
    assert len(m1["campeoes_banidos_fearless"]) == 10
    assert "Ahri" in m1["campeoes_banidos_fearless"]
    assert "Syndra" in m1["campeoes_banidos_fearless"]

    # Jogo 2: Team B attempts to pick Ahri (used by Team A in Game 1)
    err_illegal, _ = services["matches"].record_series_game(
        current_user=current_user,
        match_id=match_id,
        vencedor_id=tid_b,
        campeoes_a=["Azir", "Sejuani", "Jax", "Ashe", "Braum"],
        campeoes_b=["Ahri", "Jarvan Iv", "Gnar", "Ezreal", "Leona"],
    )
    assert err_illegal is not None
    assert "bloqueado pelo Fearless Draft" in err_illegal

    # Jogo 2: Legal picks
    champs_a_game2 = ["Azir", "Sejuani", "Jax", "Ashe", "Braum"]
    champs_b_game2 = ["Orianna", "Jarvan Iv", "Gnar", "Ezreal", "Leona"]
    err2, m2 = services["matches"].record_series_game(
        current_user=current_user,
        match_id=match_id,
        vencedor_id=tid_a,
        score_a=1,
        score_b=0,
        mapa="Summoner's Rift",
        campeoes_a=champs_a_game2,
        campeoes_b=champs_b_game2,
    )
    assert err2 is None
    # Alpha reached 2 wins in MD3 -> Finished!
    assert m2["placar_serie_a"] == 2
    assert m2["placar_serie_b"] == 0
    assert m2["status"] == "finalizada"
    assert m2["vencedor_id"] == tid_a
    assert len(m2["campeoes_banidos_fearless"]) == 20

    # Undo series game
    err_undo, m_undo = services["matches"].undo_series_game(current_user, match_id)
    assert err_undo is None
    assert m_undo["placar_serie_a"] == 1
    assert m_undo["placar_serie_b"] == 0
    assert m_undo["status"] == "em_andamento"
    assert m_undo["vencedor_id"] is None
    assert len(m_undo["jogos_serie"]) == 1
    assert len(m_undo["campeoes_banidos_fearless"]) == 10


def test_checkin_tolerance_10_minutes_and_series_wo(monkeypatch):
    import app.application.services as services_mod

    flask_app = build_test_app(monkeypatch)
    services = flask_app.extensions["services"]
    admin_id = ObjectId()
    current_user_admin = {"_id": admin_id, "role": "ADMIN"}

    p_a_id = ObjectId()
    current_user_player_a = {"_id": ObjectId(), "role": "PLAYER", "player_id": p_a_id}

    p_b_id = ObjectId()
    current_user_player_b = {"_id": ObjectId(), "role": "PLAYER", "player_id": p_b_id}

    tid_a = services["teams"].team_repo.insert({
        "admin_id": admin_id,
        "nome": "Time Alpha",
        "tag": "ALP",
        "jogo": "Valorant",
        "jogadores": [{"jogador_id": p_a_id, "nick": "PlayerA"}],
        "criado_em": datetime.now(UTC),
    })
    tid_b = services["teams"].team_repo.insert({
        "admin_id": admin_id,
        "nome": "Time Beta",
        "tag": "BET",
        "jogo": "Valorant",
        "jogadores": [{"jogador_id": p_b_id, "nick": "PlayerB"}],
        "criado_em": datetime.now(UTC),
    })
    camp_id = services["championships"].championship_repo.insert({
        "admin_id": admin_id,
        "nome": "FINC Valorant",
        "jogo": "Valorant",
        "formato": "mata-mata",
        "max_times": 2,
        "status": "EM_ANDAMENTO",
        "times_inscritos": [tid_a, tid_b],
    })

    # Official match time: 14:00 (base_time)
    base_time = datetime(2026, 10, 20, 14, 0, 0)
    match_id = services["matches"].match_repo.insert({
        "admin_id": admin_id,
        "campeonato_id": camp_id,
        "fase": "Grande Final",
        "time_a": {"time_id": tid_a, "nome": "Time Alpha", "placar": 0},
        "time_b": {"time_id": tid_b, "nome": "Time Beta", "placar": 0},
        "data_partida": base_time,
        "status": "agendada",
        "formato_serie": "MD3",
    })

    # Admin requests checkin with default 10m
    err, _ = services["matches"].solicitar_checkin(current_user_admin, match_id)
    assert err is None
    m = services["matches"].match_repo.find_by_id(match_id)
    assert m["checkin"]["solicitado"] is True
    assert m["checkin"]["tolerancia_minutos"] == 10

    # 1. At 13:45 (before 10 min antecedence window 13:50-14:10):
    monkeypatch.setattr(services_mod, "utc_now_naive", lambda: base_time - timedelta(minutes=15))
    err_early, _ = services["matches"].confirmar_presenca(current_user_player_a, match_id, tid_a)
    assert err_early is not None
    assert "ainda nao abriu" in err_early

    # 2. At 14:05 (5 minutes after official time, within 10 min tolerance):
    monkeypatch.setattr(services_mod, "utc_now_naive", lambda: base_time + timedelta(minutes=5))
    err_ok, _ = services["matches"].confirmar_presenca(current_user_player_a, match_id, tid_a)
    assert err_ok is None
    m_confirmed = services["matches"].match_repo.find_by_id(match_id)
    assert m_confirmed["checkin"]["time_a_confirmado"] is True

    # 3. At 14:08 (8 minutes after official time, tolerance still active):
    monkeypatch.setattr(services_mod, "utc_now_naive", lambda: base_time + timedelta(minutes=8))
    err_tol, _ = services["matches"].verificar_limite_checkin(current_user_admin, match_id)
    assert err_tol is not None
    assert "prazo de tolerancia" in err_tol

    # 4. At 14:12 (12 minutes after official time, tolerance expired):
    monkeypatch.setattr(services_mod, "utc_now_naive", lambda: base_time + timedelta(minutes=12))
    err_late, _ = services["matches"].confirmar_presenca(current_user_player_b, match_id, tid_b)
    assert err_late is not None
    assert "tolerancia de 10 minutos ja passou" in err_late

    # 5. Decreeing W.O. in MD3 -> victory must be 2x0 (Item 4)!
    err_wo, _ = services["matches"].verificar_limite_checkin(current_user_admin, match_id)
    assert err_wo is None
    m_wo = services["matches"].match_repo.find_by_id(match_id)
    assert m_wo["status"] == "finalizada"
    assert m_wo["vencedor_id"] == tid_a
    assert m_wo["time_a"]["placar"] == 2
    assert m_wo["time_b"]["placar"] == 0
    assert m_wo["placar_serie_a"] == 2
    assert m_wo["placar_serie_b"] == 0
    assert m_wo["checkin"]["wo_aplicado"] is True
    assert "2x0" in m_wo["checkin"]["mensagem_wo"]
    assert "MD3" in m_wo["checkin"]["mensagem_wo"]


def test_wo_scores_across_md1_and_md5(monkeypatch):
    flask_app = build_test_app(monkeypatch)
    services = flask_app.extensions["services"]
    admin_id = ObjectId()
    current_user_admin = {"_id": admin_id, "role": "ADMIN"}

    tid_a = services["teams"].team_repo.insert({
        "admin_id": admin_id,
        "nome": "Time 1",
        "tag": "T1",
        "jogo": "Clash Royale",
        "jogadores": [],
        "criado_em": datetime.now(UTC),
    })
    tid_b = services["teams"].team_repo.insert({
        "admin_id": admin_id,
        "nome": "Time 2",
        "tag": "T2",
        "jogo": "Clash Royale",
        "jogadores": [],
        "criado_em": datetime.now(UTC),
    })
    camp_id = services["championships"].championship_repo.insert({
        "admin_id": admin_id,
        "nome": "FINC CR",
        "jogo": "Clash Royale",
        "formato": "mata-mata",
        "max_times": 2,
        "status": "EM_ANDAMENTO",
        "times_inscritos": [tid_a, tid_b],
    })

    # MD1 W.O. -> 1x0
    match_md1 = services["matches"].match_repo.insert({
        "admin_id": admin_id,
        "campeonato_id": camp_id,
        "fase": "Semifinal",
        "time_a": {"time_id": tid_a, "nome": "Time 1", "placar": 0},
        "time_b": {"time_id": tid_b, "nome": "Time 2", "placar": 0},
        "status": "agendada",
        "formato_serie": "MD1",
    })
    err_md1, _ = services["matches"].aplicar_wo(current_user_admin, match_md1, vencedor_id=tid_a)
    assert err_md1 is None
    m1 = services["matches"].match_repo.find_by_id(match_md1)
    assert m1["placar_serie_a"] == 1
    assert m1["placar_serie_b"] == 0
    assert m1["vencedor_id"] == tid_a

    # MD5 W.O. -> 3x0 (Clash Royale Grande Final)
    match_md5 = services["matches"].match_repo.insert({
        "admin_id": admin_id,
        "campeonato_id": camp_id,
        "fase": "Grande Final",
        "time_a": {"time_id": tid_a, "nome": "Time 1", "placar": 0},
        "time_b": {"time_id": tid_b, "nome": "Time 2", "placar": 0},
        "status": "agendada",
        "formato_serie": "MD5",
    })
    err_md5, _ = services["matches"].aplicar_wo(current_user_admin, match_md5, vencedor_id=tid_b)
    assert err_md5 is None
    m5 = services["matches"].match_repo.find_by_id(match_md5)
    assert m5["placar_serie_a"] == 0
    assert m5["placar_serie_b"] == 3
    assert m5["vencedor_id"] == tid_b


def test_bracket_generation_with_byes_non_power_of_two(monkeypatch):
    flask_app = build_test_app(monkeypatch)
    services = flask_app.extensions["services"]
    admin_id = ObjectId()
    current_user_admin = {"_id": admin_id, "role": "ADMIN", "admin_id": admin_id}

    # Helper to create teams
    def make_teams(count):
        ids = []
        for i in range(count):
            tid = services["teams"].team_repo.insert({
                "admin_id": admin_id,
                "nome": f"Time {i+1}",
                "tag": f"T{i+1}",
                "jogo": "League of Legends",
                "jogadores": []
            })
            ids.append(tid)
        return ids

    # 1. Test 3 Teams (Next power 4: 1 Bye + 1 preliminary match)
    t_ids_3 = make_teams(3)
    camp_3 = services["championships"].championship_repo.insert({
        "admin_id": admin_id,
        "nome": "Torneio 3 Times",
        "jogo": "League of Legends",
        "formato": "mata-mata",
        "max_times": 8,
        "status": "INSCRICAO",
        "times_inscritos": t_ids_3,
    })
    errors = services["championships"].generate_matches(current_user_admin, camp_3)
    assert errors == []
    matches_3 = services["matches"].match_repo.list_by_championship(camp_3)
    assert len(matches_3) == 2  # 1 bye match + 1 playable match
    bye_m = next((m for m in matches_3 if m.get("is_bye")), None)
    assert bye_m is not None
    assert bye_m["status"] == "finalizada"
    assert bye_m["vencedor_id"] == t_ids_3[0]
    assert bye_m["time_b"]["nome"] == "FOLGA (BYE)"

    play_m = next((m for m in matches_3 if not m.get("is_bye")), None)
    assert play_m is not None
    assert play_m["status"] == "agendada"
    assert play_m["time_a"]["time_id"] == t_ids_3[1]
    assert play_m["time_b"]["time_id"] == t_ids_3[2]

    # 2. Test 5 Teams (Next power 8: 3 Byes + 1 playable match)
    t_ids_5 = make_teams(5)
    camp_5 = services["championships"].championship_repo.insert({
        "admin_id": admin_id,
        "nome": "Torneio 5 Times",
        "jogo": "Valorant",
        "formato": "mata-mata",
        "max_times": 8,
        "status": "INSCRICAO",
        "times_inscritos": t_ids_5,
    })
    errors_5 = services["championships"].generate_matches(current_user_admin, camp_5)
    assert errors_5 == []
    matches_5 = services["matches"].match_repo.list_by_championship(camp_5)
    assert len(matches_5) == 4  # 3 byes + 1 playable match = 4 match slots in Quartas
    byes_5 = [m for m in matches_5 if m.get("is_bye")]
    assert len(byes_5) == 3
    playable_5 = [m for m in matches_5 if not m.get("is_bye")]
    assert len(playable_5) == 1

    # 3. Test Phase Advancement (generate_next_phase_matches)
    # Finish the playable match of camp_5
    services["matches"].match_repo.update_fields(playable_5[0]["_id"], {
        "status": "finalizada",
        "vencedor_id": playable_5[0]["time_a"]["time_id"],
        "placar_serie_a": 1,
        "placar_serie_b": 0,
    })

    # Now all 4 Quartas matches are finalized -> advance to Semifinal
    advance_err = services["championships"].generate_next_phase_matches(current_user_admin, camp_5)
    assert advance_err == []
    semis = [m for m in services["matches"].match_repo.list_by_championship(camp_5) if m.get("fase") == "Semifinal"]
    assert len(semis) == 2  # 4 winners paired into 2 semifinal matches!


def test_sumula_oficial_anexo_iv_flow(monkeypatch):
    flask_app = build_test_app(monkeypatch)
    services = flask_app.extensions["services"]
    admin_id = ObjectId()
    current_user_admin = {"_id": admin_id, "role": "ADMIN", "admin_id": admin_id, "nome": "Prof. Coordenador"}

    # Setup players with FINC registration
    pid_a = services["players"].player_repo.insert({
        "admin_id": admin_id,
        "nick": "CapitaoAlpha",
        "nome": "Carlos Silva",
        "matricula": "20231001",
        "curso": "Engenharia de Software",
        "ingresso_finc": "2023.1",
        "contato": "carlos@finc.br"
    })
    pid_b = services["players"].player_repo.insert({
        "admin_id": admin_id,
        "nick": "CapitaoBeta",
        "nome": "Mariana Santos",
        "matricula": "20231002",
        "curso": "Sistemas de Informação",
        "ingresso_finc": "2023.2",
        "contato": "mariana@finc.br"
    })

    tid_a = services["teams"].team_repo.insert({
        "admin_id": admin_id,
        "nome": "Equipe Alpha",
        "tag": "ALP",
        "jogo": "League of Legends",
        "jogadores": [{"jogador_id": pid_a, "nick": "CapitaoAlpha", "funcao": "Capitão"}]
    })
    tid_b = services["teams"].team_repo.insert({
        "admin_id": admin_id,
        "nome": "Equipe Beta",
        "tag": "BET",
        "jogo": "League of Legends",
        "jogadores": [{"jogador_id": pid_b, "nick": "CapitaoBeta", "funcao": "Capitão"}]
    })

    camp_id = services["championships"].championship_repo.insert({
        "admin_id": admin_id,
        "nome": "Torneio FINC LoL 2026",
        "jogo": "League of Legends",
        "formato": "mata-mata",
        "max_times": 4,
        "status": "EM_ANDAMENTO",
        "times_inscritos": [tid_a, tid_b]
    })

    match_id = services["matches"].match_repo.insert({
        "admin_id": admin_id,
        "campeonato_id": camp_id,
        "fase": "Grande Final",
        "time_a": {"time_id": tid_a, "nome": "Equipe Alpha", "placar": 2},
        "time_b": {"time_id": tid_b, "nome": "Equipe Beta", "placar": 1},
        "placar_serie_a": 2,
        "placar_serie_b": 1,
        "vencedor_id": tid_a,
        "status": "finalizada",
        "formato_serie": "MD3",
        "fearless_draft": True,
        "jogos_serie": [
            {"jogo_numero": 1, "vencedor_id": tid_a, "score_a": 1, "score_b": 0, "mapa": "SR 1"},
            {"jogo_numero": 2, "vencedor_id": tid_b, "score_a": 0, "score_b": 1, "mapa": "SR 2"},
            {"jogo_numero": 3, "vencedor_id": tid_a, "score_a": 1, "score_b": 0, "mapa": "SR 3"},
        ]
    })

    # 1. Test get_sumula_oficial
    sumula = services["matches"].get_sumula_oficial(match_id)
    assert sumula is not None
    assert sumula["identificacao"]["modalidade"] == "League of Legends"
    assert sumula["identificacao"]["fase"] == "Grande Final"
    assert sumula["identificacao"]["formato_serie"] == "MD3"
    assert "Carlos Silva" in sumula["identificacao"]["lado_a"]
    assert "20231001" in sumula["identificacao"]["lado_a"]
    assert len(sumula["resultados"]["jogos"]) == 3
    assert sumula["resultados"]["vencedor_serie"] == "Equipe Alpha"

    # 2. Test add_sumula_ocorrencia (Art. 12 FINC)
    err_oc, updated_oc = services["matches"].add_sumula_ocorrencia(
        current_user_admin,
        match_id,
        texto="Pausa técnica solicitada aos 14min por problema no cabo de rede.",
        tipo="Pausa Técnica",
        artigo="Item 7.8"
    )
    assert err_oc is None
    assert len(updated_oc.get("sumula_ocorrencias", [])) == 1
    assert updated_oc["sumula_ocorrencias"][0]["artigo"] == "Item 7.8"

    # 3. Test assinar_sumula_oficial (Árbitro e Capitães)
    err_sig_arb, updated_arb = services["matches"].assinar_sumula_oficial(
        current_user_admin, match_id, papel="arbitro", nome_assinante="Árbitro Oficial FINC"
    )
    assert err_sig_arb is None
    assert updated_arb["sumula_assinaturas"]["arbitro"]["assinado"] is True
    assert updated_arb["sumula_assinaturas"]["arbitro"]["hash"].startswith("FINC-SIG-")

    err_sig_cap, updated_cap = services["matches"].assinar_sumula_oficial(
        current_user_admin, match_id, papel="capitao_a", nome_assinante="Carlos Silva", matricula="20231001"
    )
    assert err_sig_cap is None
    assert updated_cap["sumula_assinaturas"]["capitao_a"]["assinado"] is True
    assert updated_cap["sumula_assinaturas"]["capitao_a"]["matricula"] == "20231001"

    # 4. Test Web Routes for Súmula Oficial
    client = flask_app.test_client()
    resp_view = client.get(f"/partidas/{match_id}/sumula-oficial")
    assert resp_view.status_code == 200
    html = resp_view.get_data(as_text=True)
    assert "REGULAMENTO OFICIAL · ANEXO IV" in html
    assert "Modelo de Súmula Oficial" in html
    assert "Equipe Alpha" in html
    assert "FINC-SIG-" in html

    # Test PDF download endpoint
    resp_pdf = client.get(f"/partidas/{match_id}/sumula-oficial/pdf")
    assert resp_pdf.status_code == 200
    assert resp_pdf.headers["Content-Type"] == "application/pdf"
    assert resp_pdf.data.startswith(b"%PDF")




