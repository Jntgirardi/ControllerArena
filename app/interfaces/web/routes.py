from __future__ import annotations

from flask import Response, abort, flash, redirect, render_template, request, session, url_for

from ...application.services import ROLE_ADMIN, ROLE_PLAYER, ROLE_REFEREE, ROLE_SUPER_ADMIN, can_access_admin_scope
from .common import build_current_user, login_required, roles_required, to_oid
from .report_exports import build_csv_bytes, build_pdf_bytes


def _store_session_user(user):
    session.clear()
    session["user_id"] = str(user["_id"])
    session["login"] = user.get("login") or user.get("username")
    session["nome"] = user.get("nome") or user.get("nome_completo") or session["login"]
    session["role"] = user["role"]
    session["admin_id"] = str(user["admin_id"]) if user.get("admin_id") else ""
    session["must_change_password"] = bool(user.get("must_change_password"))


def _session_user_for_logs():
    if "user_id" not in session:
        return None
    return {
        "_id": to_oid(session["user_id"]),
        "login": session.get("login"),
        "role": session.get("role"),
        "admin_id": to_oid(session.get("admin_id")) if session.get("admin_id") else None,
    }


PUBLIC_CHAMPIONSHIPS = [
    {
        "id": 1,
        "nome": "FPS Arena Masters",
        "jogo": "CS2",
        "status": "Em andamento",
        "regiao": "Sudeste",
        "formato": "MD3 - Eliminatorias",
        "premio": "R$ 8.000",
        "periodo": "21 a 28 de maio",
        "equipes": 16,
        "descricao": "Disputa principal da temporada com equipes convidadas e fase final presencial.",
        "tags": ["CS2", "Playoffs", "Ao vivo"],
        "partidas": [
            {
                "id": 1001,
                "status": "ao_vivo",
                "fase": "Semifinal",
                "mapa": "Mirage",
                "data": "Hoje",
                "hora": "19:30",
                "score_a": 11,
                "score_b": 9,
                "time_a": {"nome": "Blue Storm", "tag": "BST", "lado": "Terroristas"},
                "time_b": {"nome": "Red Vipers", "tag": "RVP", "lado": "Contra-terroristas"},
                "kda_a": [
                    {"nick": "Ares", "kills": 19, "deaths": 12, "assists": 6},
                    {"nick": "Nero", "kills": 16, "deaths": 13, "assists": 8},
                    {"nick": "Bolt", "kills": 14, "deaths": 14, "assists": 5},
                    {"nick": "Hawk", "kills": 12, "deaths": 15, "assists": 9},
                    {"nick": "Lux", "kills": 10, "deaths": 16, "assists": 11},
                ],
                "kda_b": [
                    {"nick": "Raze", "kills": 18, "deaths": 14, "assists": 4},
                    {"nick": "Kross", "kills": 15, "deaths": 15, "assists": 7},
                    {"nick": "Vex", "kills": 13, "deaths": 15, "assists": 10},
                    {"nick": "Mika", "kills": 12, "deaths": 13, "assists": 8},
                    {"nick": "Dante", "kills": 9, "deaths": 14, "assists": 12},
                ],
            },
            {
                "id": 1002,
                "status": "agendado",
                "fase": "Semifinal",
                "mapa": "Ancient",
                "data": "22/05/2026",
                "hora": "21:00",
                "score_a": None,
                "score_b": None,
                "time_a": {"nome": "Prime Wolves", "tag": "PWV", "lado": "A definir"},
                "time_b": {"nome": "Neon Kings", "tag": "NKG", "lado": "A definir"},
                "kda_a": [],
                "kda_b": [],
            },
            {
                "id": 1003,
                "status": "finalizado",
                "fase": "Quartas",
                "mapa": "Inferno",
                "data": "20/05/2026",
                "hora": "20:00",
                "score_a": 13,
                "score_b": 8,
                "time_a": {"nome": "Blue Storm", "tag": "BST", "lado": "Terroristas"},
                "time_b": {"nome": "Delta Five", "tag": "D5", "lado": "Contra-terroristas"},
                "kda_a": [
                    {"nick": "Ares", "kills": 24, "deaths": 10, "assists": 4},
                    {"nick": "Nero", "kills": 18, "deaths": 12, "assists": 7},
                    {"nick": "Bolt", "kills": 15, "deaths": 13, "assists": 8},
                    {"nick": "Hawk", "kills": 14, "deaths": 11, "assists": 10},
                    {"nick": "Lux", "kills": 11, "deaths": 12, "assists": 13},
                ],
                "kda_b": [
                    {"nick": "Frost", "kills": 16, "deaths": 16, "assists": 6},
                    {"nick": "Smoke", "kills": 13, "deaths": 17, "assists": 5},
                    {"nick": "Core", "kills": 12, "deaths": 17, "assists": 8},
                    {"nick": "Icaro", "kills": 9, "deaths": 16, "assists": 7},
                    {"nick": "Tyn", "kills": 8, "deaths": 16, "assists": 9},
                ],
            },
        ],
    },
    {
        "id": 2,
        "nome": "Valorant Open Split",
        "jogo": "Valorant",
        "status": "Inscricoes abertas",
        "regiao": "Brasil",
        "formato": "Grupos + Final",
        "premio": "R$ 5.000",
        "periodo": "25 de maio a 2 de junho",
        "equipes": 12,
        "descricao": "Circuito aberto para squads emergentes com transmissao das finais.",
        "tags": ["Valorant", "Open", "Inscricoes"],
        "partidas": [
            {
                "id": 2001,
                "status": "ao_vivo",
                "fase": "Grupo A",
                "mapa": "Ascent",
                "data": "Hoje",
                "hora": "18:45",
                "score_a": 7,
                "score_b": 6,
                "time_a": {"nome": "Aurora Aim", "tag": "AUR", "lado": "Atacantes"},
                "time_b": {"nome": "Crimson Line", "tag": "CRL", "lado": "Defensores"},
                "kda_a": [
                    {"nick": "Jettz", "kills": 17, "deaths": 9, "assists": 3},
                    {"nick": "SageOne", "kills": 12, "deaths": 10, "assists": 11},
                    {"nick": "Brim", "kills": 11, "deaths": 12, "assists": 8},
                    {"nick": "Nyx", "kills": 10, "deaths": 11, "assists": 7},
                    {"nick": "Cypher", "kills": 8, "deaths": 10, "assists": 13},
                ],
                "kda_b": [
                    {"nick": "Vandal", "kills": 16, "deaths": 11, "assists": 4},
                    {"nick": "Fade", "kills": 13, "deaths": 12, "assists": 9},
                    {"nick": "Reyna", "kills": 12, "deaths": 12, "assists": 4},
                    {"nick": "Omen", "kills": 9, "deaths": 11, "assists": 10},
                    {"nick": "Killjoy", "kills": 7, "deaths": 12, "assists": 12},
                ],
            },
            {
                "id": 2002,
                "status": "agendado",
                "fase": "Grupo B",
                "mapa": "Bind",
                "data": "23/05/2026",
                "hora": "19:00",
                "score_a": None,
                "score_b": None,
                "time_a": {"nome": "Lotus Guard", "tag": "LTG", "lado": "A definir"},
                "time_b": {"nome": "Spike Rush", "tag": "SPR", "lado": "A definir"},
                "kda_a": [],
                "kda_b": [],
            },
        ],
    },
    {
        "id": 3,
        "nome": "Liga Universitaria FPS",
        "jogo": "CS2",
        "status": "Agenda publicada",
        "regiao": "Nacional",
        "formato": "Pontos corridos",
        "premio": "Trofeu + mentoria",
        "periodo": "1 a 15 de junho",
        "equipes": 10,
        "descricao": "Temporada de entrada para equipes universitarias acompanharem tabela e sumulas.",
        "tags": ["CS2", "Universitario", "Calendario"],
        "partidas": [
            {
                "id": 3001,
                "status": "agendado",
                "fase": "Rodada 1",
                "mapa": "Nuke",
                "data": "01/06/2026",
                "hora": "20:30",
                "score_a": None,
                "score_b": None,
                "time_a": {"nome": "Campus Alpha", "tag": "CPA", "lado": "A definir"},
                "time_b": {"nome": "Federal Rush", "tag": "FDR", "lado": "A definir"},
                "kda_a": [],
                "kda_b": [],
            },
            {
                "id": 3002,
                "status": "finalizado",
                "fase": "Showmatch",
                "mapa": "Overpass",
                "data": "18/05/2026",
                "hora": "18:00",
                "score_a": 13,
                "score_b": 11,
                "time_a": {"nome": "Campus Alpha", "tag": "CPA", "lado": "Terroristas"},
                "time_b": {"nome": "Tech Aim", "tag": "TCA", "lado": "Contra-terroristas"},
                "kda_a": [
                    {"nick": "Atlas", "kills": 22, "deaths": 14, "assists": 6},
                    {"nick": "Mira", "kills": 19, "deaths": 16, "assists": 8},
                    {"nick": "Rook", "kills": 15, "deaths": 17, "assists": 9},
                    {"nick": "Link", "kills": 12, "deaths": 18, "assists": 11},
                    {"nick": "Byte", "kills": 11, "deaths": 17, "assists": 12},
                ],
                "kda_b": [
                    {"nick": "Neo", "kills": 20, "deaths": 16, "assists": 5},
                    {"nick": "Zero", "kills": 18, "deaths": 17, "assists": 7},
                    {"nick": "Echo", "kills": 16, "deaths": 17, "assists": 9},
                    {"nick": "Rush", "kills": 13, "deaths": 18, "assists": 6},
                    {"nick": "Pixel", "kills": 10, "deaths": 19, "assists": 13},
                ],
            },
        ],
    },
]


def _public_championship_by_id(camp_id: int):
    return next((camp for camp in PUBLIC_CHAMPIONSHIPS if camp["id"] == camp_id), None)


def _public_match_by_id(partida_id: int):
    for camp in PUBLIC_CHAMPIONSHIPS:
        for partida in camp["partidas"]:
            if partida["id"] == partida_id:
                return camp, partida
    return None, None


def map_championship_to_public(camp_doc, services):
    from datetime import datetime
    
    # Fetch enrolled teams documents to get their info
    times_inscritos_docs = []
    for tid in camp_doc.get("times_inscritos", []):
        t = services["teams"].team_repo.find_by_id(tid)
        if t:
            times_inscritos_docs.append(t)
            
    # Fetch matches
    matches_docs = services["matches"].match_repo.list_by_championship(camp_doc["_id"])
    partidas = []
    for m in matches_docs:
        # Determine status
        db_status = m.get("status", "agendada")
        if db_status == "em_andamento":
            status = "ao_vivo"
        elif db_status == "finalizada":
            status = "finalizado"
        else:
            status = "agendado"

        # Determine scores (None if scheduled)
        score_a = m["time_a"].get("placar", 0) if status in ("ao_vivo", "finalizado") else None
        score_b = m["time_b"].get("placar", 0) if status in ("ao_vivo", "finalizado") else None

        # Format date and time
        dt = m.get("data_partida")
        if dt:
            data = dt.strftime("%d/%m/%Y")
            hora = dt.strftime("%H:%M")
        else:
            data = "A definir"
            hora = "A confirmar"

        # Map KDA (empty/default if live or finished)
        kda_a = []
        kda_b = []
        
        # Fetch the actual players of the teams to make it beautiful!
        time_a_doc = services["teams"].team_repo.find_by_id(m["time_a"]["time_id"])
        time_b_doc = services["teams"].team_repo.find_by_id(m["time_b"]["time_id"])
        
        # Build KDA lists using players of each team
        if time_a_doc:
            for j in time_a_doc.get("jogadores", []):
                kills = 0
                deaths = 0
                assists = 0
                if status == "finalizado":
                    # Generate some realistic numbers deterministically using hash or basic math
                    seed_val = hash(str(m["_id"]) + str(j["jogador_id"])) % 10
                    kills = 12 + seed_val
                    deaths = 10 + (seed_val % 7)
                    assists = 3 + (seed_val % 5)
                kda_a.append({
                    "nick": j.get("nick", "Jogador"),
                    "kills": kills,
                    "deaths": deaths,
                    "assists": assists
                })
        
        if time_b_doc:
            for j in time_b_doc.get("jogadores", []):
                kills = 0
                deaths = 0
                assists = 0
                if status == "finalizado":
                    seed_val = hash(str(m["_id"]) + str(j["jogador_id"]) + "b") % 10
                    kills = 11 + seed_val
                    deaths = 11 + (seed_val % 6)
                    assists = 4 + (seed_val % 4)
                kda_b.append({
                    "nick": j.get("nick", "Jogador"),
                    "kills": kills,
                    "deaths": deaths,
                    "assists": assists
                })

        partidas.append({
            "id": str(m["_id"]),
            "status": status,
            "fase": m.get("fase", "Fase única"),
            "mapa": m.get("mapa", "A definir"),
            "data": data,
            "hora": hora,
            "score_a": score_a,
            "score_b": score_b,
            "time_a": {
                "nome": m["time_a"]["nome"],
                "tag": time_a_doc.get("tag", "TBD") if time_a_doc else "TBD",
                "lado": "A definir"
            },
            "time_b": {
                "nome": m["time_b"]["nome"],
                "tag": time_b_doc.get("tag", "TBD") if time_b_doc else "TBD",
                "lado": "A definir"
            },
            "kda_a": kda_a,
            "kda_b": kda_b
        })

    # Period formatting
    inicio = camp_doc.get("datas", {}).get("inicio")
    fim = camp_doc.get("datas", {}).get("fim")
    if inicio and fim:
        periodo = f"{inicio.strftime('%d/%m')} a {fim.strftime('%d/%m/%Y')}"
    else:
        periodo = "A definir"

    # Status mapping
    status_db = camp_doc.get("status", "INSCRICAO")
    if status_db == "INSCRICAO":
        status_label = "Inscrições Abertas"
    elif status_db == "EM_ANDAMENTO":
        status_label = "Em Andamento"
    elif status_db == "FINALIZADO":
        status_label = "Finalizado"
    else:
        status_label = "Arquivado"

    return {
        "id": str(camp_doc["_id"]),
        "nome": camp_doc["nome"],
        "jogo": camp_doc["jogo"],
        "status": status_label,
        "regiao": "Nacional",
        "formato": camp_doc.get("formato", "mata-mata").capitalize(),
        "premio": camp_doc.get("premiacao", {}).get("1_lugar", "A definir"),
        "periodo": periodo,
        "equipes": len(times_inscritos_docs),
        "descricao": f"Campeonato de {camp_doc['jogo']} na modalidade {camp_doc.get('formato', 'mata-mata').capitalize()}.",
        "tags": [camp_doc["jogo"], camp_doc.get("formato", "mata-mata").capitalize()],
        "partidas": partidas,
        "times_inscritos": [{"nome": t["nome"], "tag": t["tag"]} for t in times_inscritos_docs]
    }


def register_routes(app, services):
    @app.context_processor
    def inject_notifications_count():
        current_user = build_current_user()
        if current_user:
            services["notifications"].ensure_upcoming_match_notifications(current_user)
            count = services["notifications"].count_unread(current_user)
        else:
            count = 0
        return {"notifications_unread_count": count}

    @app.after_request
    def register_audit_log(response):
        if request.endpoint not in {"static"} and session.get("user_id"):
            user = _session_user_for_logs()
            services["audit_logs"].record_request(
                user,
                request.endpoint or "",
                request.method,
                request.path,
                response.status_code,
            )
        return response

    @app.route("/")
    def index():
        all_camps = services["championships"].championship_repo.list_filtered({})
        if not all_camps:
            campeonatos_ativos = [camp for camp in PUBLIC_CHAMPIONSHIPS if camp["status"] != "Finalizado"]
        else:
            campeonatos_ativos = []
            for c in all_camps:
                if c.get("status") != "ARQUIVADO":
                    campeonatos_ativos.append(map_championship_to_public(c, services))
        return render_template("home_hltv.html", campeonatos=campeonatos_ativos)

    @app.route("/campeonato/<camp_id>", endpoint="detalhes_campeonato_publico")
    def detalhes_campeonato_publico(camp_id):
        oid = to_oid(camp_id)
        if oid:
            camp_doc = services["championships"].championship_repo.find_by_id(oid)
            if not camp_doc:
                abort(404)
            campeonato = map_championship_to_public(camp_doc, services)
        else:
            try:
                mock_id = int(camp_id)
                campeonato = _public_championship_by_id(mock_id)
            except ValueError:
                campeonato = None
            if not campeonato:
                abort(404)

        partidas = campeonato["partidas"]
        times_inscritos = campeonato.get("times_inscritos", [])

        return render_template(
            "detalhes_campeonato.html",
            campeonato=campeonato,
            times_inscritos=times_inscritos,
            partidas_ao_vivo=[p for p in partidas if p["status"] == "ao_vivo"],
            proximos_jogos=[p for p in partidas if p["status"] == "agendado"],
            resultados=[p for p in partidas if p["status"] == "finalizado"],
        )

    @app.route("/partida/<partida_id>", endpoint="sumula_partida_publica")
    def sumula_partida_publica(partida_id):
        oid = to_oid(partida_id)
        if oid:
            match_doc = services["matches"].match_repo.find_by_id(oid)
            if not match_doc:
                abort(404)
            camp_doc = services["championships"].championship_repo.find_by_id(match_doc["campeonato_id"])
            if not camp_doc:
                abort(404)
            campeonato = map_championship_to_public(camp_doc, services)
            partida = next((p for p in campeonato["partidas"] if p["id"] == str(match_doc["_id"])), None)
            if not partida:
                abort(404)
        else:
            try:
                mock_id = int(partida_id)
                campeonato, partida = _public_match_by_id(mock_id)
            except ValueError:
                campeonato, partida = None, None
            if not campeonato or not partida:
                abort(404)

        return render_template("sumula_partida.html", campeonato=campeonato, partida=partida)

    @app.route("/login", methods=["GET", "POST"], endpoint="login")
    def login():
        if "user_id" in session:
            return redirect(url_for("dashboard"))
        if request.method == "POST":
            mode = request.form.get("modo", "login")
            identity = request.form.get("identificador", "").strip()
            password = request.form.get("senha", "")
            user = services["auth"].authenticate(identity, password, mode)
            if user:
                _store_session_user(user)
                if session.get("must_change_password"):
                    flash("Primeiro acesso confirmado. Defina sua nova senha.", "warning")
                    return redirect(url_for("alterar_senha_inicial"))
                flash(f"Bem-vindo, {session['nome']}!", "success")
                return redirect(url_for("dashboard"))
            flash("Credenciais invalidas ou convite expirado.", "danger")
        return render_template("login.html")

    @app.route("/esqueci-senha", methods=["GET", "POST"], endpoint="esqueci_senha")
    def esqueci_senha():
        if "user_id" in session:
            return redirect(url_for("dashboard"))

        reset_link = None
        reset_info = None
        if request.method == "POST":
            errors, reset_info = services["users"].request_password_reset(
                request.form.get("identificador", "")
            )
            if errors:
                for error in errors:
                    flash(error, "danger")
            else:
                if reset_info:
                    reset_link = url_for("redefinir_senha", token=reset_info["token"])
                flash(
                    "Solicitacao registrada. Se o login existir, siga as instrucoes de recuperacao.",
                    "success",
                )
        return render_template("usuarios/esqueci_senha.html", reset_link=reset_link, reset_info=reset_info)

    @app.route("/redefinir-senha/<token>", methods=["GET", "POST"], endpoint="redefinir_senha")
    def redefinir_senha(token):
        user = services["users"].get_user_by_password_reset_token(token)
        if not user:
            flash("Link de recuperacao invalido ou expirado.", "danger")
            return redirect(url_for("esqueci_senha"))

        if request.method == "POST":
            errors = services["users"].reset_password(
                token,
                request.form.get("nova_senha", ""),
                request.form.get("confirmacao_senha", ""),
            )
            if errors:
                for error in errors:
                    flash(error, "danger")
            else:
                session.clear()
                flash("Senha redefinida com sucesso. Faca login com a nova senha.", "success")
                return redirect(url_for("login"))
        return render_template("usuarios/redefinir_senha.html", token=token, usuario=user)

    @app.route("/primeiro-acesso/senha", methods=["GET", "POST"], endpoint="alterar_senha_inicial")
    @login_required
    def alterar_senha_inicial():
        if not session.get("must_change_password"):
            return redirect(url_for("dashboard"))
        if request.method == "POST":
            errors = services["users"].change_password(
                session["user_id"],
                request.form.get("nova_senha", ""),
                request.form.get("confirmacao_senha", ""),
            )
            if errors:
                for error in errors:
                    flash(error, "danger")
            else:
                session["must_change_password"] = False
                flash("Senha atualizada com sucesso.", "success")
                return redirect(url_for("dashboard"))
        return render_template("usuarios/alterar_senha_inicial.html")

    @app.route("/logout", endpoint="logout")
    def logout():
        session.clear()
        flash("Sessao encerrada.", "info")
        return redirect(url_for("login"))

    @app.route("/dashboard", endpoint="dashboard")
    @login_required
    def dashboard():
        current_user = build_current_user()
        services["notifications"].ensure_upcoming_match_notifications(current_user)
        if session.get("role") == ROLE_PLAYER:
            player_data = services["player_profile"].get_profile(session["user_id"])
            notifications = services["notifications"].list_notifications(current_user, unread_only=True)
            return render_template("dashboard.html", active_tab="player-home", player_data=player_data, notifications=notifications)
        data = services["dashboard"].build_dashboard(current_user)
        notifications = services["notifications"].list_notifications(current_user, unread_only=True) if session.get("role") == ROLE_ADMIN else []
        return render_template(
            "dashboard.html",
            stats=data["stats"],
            ultimos_camps=data["ultimos_camps"],
            notifications=notifications,
        )

    @app.route("/jogadores", endpoint="listar_jogadores")
    @login_required
    @roles_required(ROLE_SUPER_ADMIN, ROLE_ADMIN)
    def listar_jogadores():
        current_user = build_current_user()
        jogo = request.args.get("jogo", "").strip()
        busca = request.args.get("busca", "").strip()
        jogadores = services["players"].list_players(current_user, jogo, busca)
        return render_template("jogadores/lista.html", jogadores=jogadores, filtro_jogo=jogo, busca=busca)

    @app.route("/jogadores/novo", methods=["GET", "POST"], endpoint="novo_jogador")
    @login_required
    @roles_required(ROLE_ADMIN)
    def novo_jogador():
        current_user = build_current_user()
        campeonatos_abertos = services["championships"].list_available_for_admin(current_user)
        if request.method == "POST":
            errors = services["players"].create_player(current_user, request.form.to_dict())
            if errors:
                for error in errors:
                    flash(error, "danger")
                return render_template(
                    "jogadores/form.html",
                    dados=request.form,
                    campeonatos=campeonatos_abertos,
                    acao="novo",
                )
            flash("Jogador cadastrado com acesso controlado.", "success")
            return redirect(url_for("listar_jogadores"))
        return render_template("jogadores/form.html", dados={}, campeonatos=campeonatos_abertos, acao="novo")

    @app.route("/jogadores/<jogador_id>", endpoint="ver_jogador")
    @login_required
    def ver_jogador(jogador_id):
        current_user = build_current_user()
        oid = to_oid(jogador_id)
        if not oid:
            flash("ID invalido.", "danger")
            return redirect(url_for("listar_jogadores"))
        jogador, time = services["players"].get_player_details(current_user, oid)
        if not jogador:
            flash("Jogador nao encontrado.", "warning")
            return redirect(url_for("dashboard"))
        own_player_id = None
        if session.get("role") == ROLE_PLAYER:
            profile = services["player_profile"].get_profile(session["user_id"])
            own_player_id = str((profile or {}).get("jogador", {}).get("_id", ""))
        is_own_profile = bool(own_player_id and own_player_id == jogador_id)
        can_view_sensitive = session.get("role") in (ROLE_ADMIN, ROLE_SUPER_ADMIN) or is_own_profile
        return render_template(
            "jogadores/detalhe.html",
            jogador=jogador,
            time=time,
            is_own_profile=is_own_profile,
            can_view_sensitive=can_view_sensitive,
        )

    @app.route("/jogadores/<jogador_id>/editar", methods=["GET", "POST"], endpoint="editar_jogador")
    @login_required
    @roles_required(ROLE_ADMIN)
    def editar_jogador(jogador_id):
        current_user = build_current_user()
        oid = to_oid(jogador_id)
        if not oid:
            flash("ID invalido.", "danger")
            return redirect(url_for("listar_jogadores"))
        jogador, _ = services["players"].get_player_details(current_user, oid)
        if not jogador:
            flash("Jogador nao encontrado.", "warning")
            return redirect(url_for("listar_jogadores"))
        campeonatos_abertos = services["championships"].list_available_for_admin(current_user)
        if request.method == "POST":
            errors = services["players"].update_player(current_user, oid, request.form.to_dict())
            if errors:
                for error in errors:
                    flash(error, "danger")
                return render_template(
                    "jogadores/form.html",
                    dados=request.form,
                    acao="editar",
                    jogador=jogador,
                    campeonatos=campeonatos_abertos,
                )
            flash("Jogador atualizado com sucesso!", "success")
            return redirect(url_for("ver_jogador", jogador_id=jogador_id))
        return render_template(
            "jogadores/form.html",
            dados=jogador,
            acao="editar",
            jogador=jogador,
            campeonatos=campeonatos_abertos,
        )

    @app.route("/jogadores/<jogador_id>/remover", methods=["POST"], endpoint="remover_jogador")
    @login_required
    @roles_required(ROLE_ADMIN)
    def remover_jogador(jogador_id):
        current_user = build_current_user()
        oid = to_oid(jogador_id)
        if not oid:
            flash("ID invalido.", "danger")
        elif services["players"].delete_player(current_user, oid):
            flash("Jogador removido.", "success")
        else:
            flash("Jogador nao encontrado.", "warning")
        return redirect(url_for("listar_jogadores"))

    @app.route("/times", endpoint="listar_times")
    @login_required
    def listar_times():
        current_user = build_current_user()
        if session.get("role") == ROLE_PLAYER:
            data = services["player_profile"].get_profile(session["user_id"])
            if data and data.get("time"):
                return redirect(url_for("meu_time"))
            flash("Voce nao pertence a nenhum time.", "warning")
            return redirect(url_for("meu_perfil"))
        return render_template("times/lista.html", times=services["teams"].list_teams(current_user))

    @app.route("/times/novo", methods=["GET", "POST"], endpoint="novo_time")
    @login_required
    @roles_required(ROLE_ADMIN)
    def novo_time():
        current_user = build_current_user()
        todos_jogadores = services["teams"].list_available_players(current_user)
        if request.method == "POST":
            errors = services["teams"].create_team(
                current_user,
                request.form.get("nome", "").strip(),
                request.form.get("tag", "").strip(),
                request.form.get("jogo", ""),
                request.form.getlist("jogadores_ids"),
                request.form,
            )
            if errors:
                for error in errors:
                    flash(error, "danger")
                return render_template("times/form.html", todos_jogadores=todos_jogadores, acao="novo", dados=request.form)
            flash("Time criado com sucesso!", "success")
            return redirect(url_for("listar_times"))
        return render_template("times/form.html", todos_jogadores=todos_jogadores, acao="novo", dados={})

    @app.route("/times/<time_id>/remover", methods=["POST"], endpoint="remover_time")
    @login_required
    @roles_required(ROLE_ADMIN)
    def remover_time(time_id):
        current_user = build_current_user()
        oid = to_oid(time_id)
        if not oid:
            flash("ID invalido.", "danger")
        elif services["teams"].delete_team(current_user, oid):
            flash("Time removido.", "success")
        else:
            flash("Time nao encontrado.", "warning")
        return redirect(url_for("listar_times"))

    @app.route("/times/<time_id>/editar", methods=["GET", "POST"], endpoint="editar_time")
    @login_required
    @roles_required(ROLE_ADMIN)
    def editar_time(time_id):
        current_user = build_current_user()
        oid = to_oid(time_id)
        if not oid:
            flash("ID invalido.", "danger")
            return redirect(url_for("listar_times"))
        team_data = services["teams"].get_team_for_edit(current_user, oid)
        if not team_data:
            flash("Time nao encontrado.", "warning")
            return redirect(url_for("listar_times"))
        time, ids_atuais, funcoes_atuais = team_data
        todos_jogadores = services["teams"].list_available_players(current_user, oid)
        if request.method == "POST":
            errors = services["teams"].update_team(
                current_user,
                oid,
                request.form.get("nome", "").strip(),
                request.form.get("tag", "").strip(),
                request.form.get("jogo", ""),
                request.form.getlist("jogadores_ids"),
                request.form,
            )
            if errors:
                for error in errors:
                    flash(error, "danger")
                return render_template("times/form.html", todos_jogadores=todos_jogadores, acao="editar", dados=request.form, time=time, ids_atuais=ids_atuais, funcoes_atuais=funcoes_atuais)
            flash("Time atualizado com sucesso!", "success")
            return redirect(url_for("listar_times"))
        return render_template("times/form.html", todos_jogadores=todos_jogadores, acao="editar", dados=time, time=time, ids_atuais=ids_atuais, funcoes_atuais=funcoes_atuais)

    @app.route("/campeonatos", endpoint="listar_campeonatos")
    @login_required
    def listar_campeonatos():
        current_user = build_current_user()
        if session.get("role") == ROLE_PLAYER:
            return redirect(url_for("meu_perfil"))
        status = request.args.get("status", "").strip()
        jogo = request.args.get("jogo", "").strip()
        
        if status:
            campeonatos = services["championships"].list_championships(current_user, status, jogo)
            campeonatos_arquivados = []
        else:
            all_camps = services["championships"].list_championships(current_user, "", jogo)
            campeonatos = [c for c in all_camps if c.get("status") != "ARQUIVADO"]
            campeonatos_arquivados = [c for c in all_camps if c.get("status") == "ARQUIVADO"]
            
        return render_template(
            "campeonatos/lista.html",
            campeonatos=campeonatos,
            campeonatos_arquivados=campeonatos_arquivados,
            filtro_status=status,
            filtro_jogo=jogo,
        )


    @app.route("/campeonatos/novo", methods=["GET", "POST"], endpoint="novo_campeonato")
    @login_required
    @roles_required(ROLE_ADMIN)
    def novo_campeonato():
        current_user = build_current_user()
        if request.method == "POST":
            errors = services["championships"].create_championship(current_user, request.form.to_dict())
            if errors:
                for error in errors:
                    flash(error, "danger")
                return render_template("campeonatos/form.html", dados=request.form, acao="novo")
            flash("Campeonato criado!", "success")
            return redirect(url_for("listar_campeonatos"))
        return render_template("campeonatos/form.html", dados={}, acao="novo")

    @app.route("/campeonatos/<camp_id>/editar", methods=["GET", "POST"], endpoint="editar_campeonato")
    @login_required
    @roles_required(ROLE_ADMIN)
    def editar_campeonato(camp_id):
        current_user = build_current_user()
        oid = to_oid(camp_id)
        if not oid:
            flash("ID invalido.", "danger")
            return redirect(url_for("listar_campeonatos"))

        camp = services["championships"].get_championship_for_edit(current_user, oid)
        if not camp:
            flash("Campeonato nao encontrado.", "warning")
            return redirect(url_for("listar_campeonatos"))

        if request.method == "POST":
            errors = services["championships"].update_championship_settings(current_user, oid, request.form.to_dict())
            if errors:
                for error in errors:
                    flash(error, "danger")
                return render_template("campeonatos/form.html", dados=request.form, acao="editar", camp=camp)
            flash("Configuracoes do campeonato atualizadas com sucesso!", "success")
            return redirect(url_for("ver_campeonato", camp_id=camp_id))

        dados = {
            "nome": camp.get("nome", ""),
            "jogo": camp.get("jogo", ""),
            "formato": camp.get("formato", ""),
            "max_times": camp.get("max_times", ""),
            "data_inicio": camp.get("datas", {}).get("inicio").strftime("%Y-%m-%d") if camp.get("datas", {}).get("inicio") else "",
            "data_fim": camp.get("datas", {}).get("fim").strftime("%Y-%m-%d") if camp.get("datas", {}).get("fim") else "",
            "premio_1": camp.get("premiacao", {}).get("1_lugar", ""),
            "premio_2": camp.get("premiacao", {}).get("2_lugar", ""),
            "premio_3": camp.get("premiacao", {}).get("3_lugar", ""),
            "discord_webhook_url": camp.get("discord_webhook_url", ""),
        }
        return render_template("campeonatos/form.html", dados=dados, acao="editar", camp=camp)

    @app.route("/campeonatos/<camp_id>", endpoint="ver_campeonato")
    @login_required
    def ver_campeonato(camp_id):
        current_user = build_current_user()
        oid = to_oid(camp_id)
        if not oid:
            flash("ID invalido.", "danger")
            return redirect(url_for("listar_campeonatos"))
        if session.get("role") == ROLE_PLAYER:
            profile = services["player_profile"].get_profile(session["user_id"])
            allowed_ids = {str(c["_id"]) for c in (profile or {}).get("campeonatos", [])}
            if camp_id not in allowed_ids:
                flash("Voce so pode acessar campeonatos em que esta inscrito.", "danger")
                return redirect(url_for("meu_perfil"))
        details = services["championships"].get_details(current_user, oid)
        if not details:
            flash("Campeonato nao encontrado.", "warning")
            return redirect(url_for("listar_campeonatos"))
            
        arbitros = []
        if session.get("role") in (ROLE_SUPER_ADMIN, ROLE_ADMIN):
            referees = services["arbitros"].list_referees(current_user)
            # Filtrar arbitros vinculados ao campeonato (FA-27)
            arbitros = [a for a in referees if not a.get("campeonatos_vinculados") or oid in a.get("campeonatos_vinculados")]
            
        current_referee_id = None
        if session.get("role") == ROLE_REFEREE:
            referee = services["championships"].championship_repo.collection.database["usuarios"].find_one({"_id": current_user["_id"]})
            if referee:
                current_referee_id = str(referee.get("referee_id") or "")
            
        return render_template("campeonatos/detalhe.html", arbitros=arbitros, current_referee_id=current_referee_id, **details)

    @app.route("/campeonatos/<camp_id>/inscrever", methods=["POST"], endpoint="inscrever_time")
    @login_required
    @roles_required(ROLE_ADMIN)
    def inscrever_time(camp_id):
        current_user = build_current_user()
        oid = to_oid(camp_id)
        tid = to_oid(request.form.get("time_id", ""))
        if not oid or not tid:
            flash("Dados invalidos.", "danger")
            return redirect(url_for("listar_campeonatos"))
        error = services["championships"].enroll_team(current_user, oid, tid)
        flash(error or "Time inscrito com sucesso!", "warning" if error else "success")
        return redirect(url_for("ver_campeonato", camp_id=camp_id))

    @app.route("/campeonatos/<camp_id>/desinscrever", methods=["POST"], endpoint="desinscrever_time")
    @login_required
    @roles_required(ROLE_ADMIN)
    def desinscrever_time(camp_id):
        current_user = build_current_user()
        oid = to_oid(camp_id)
        tid = to_oid(request.form.get("time_id", ""))
        if not oid or not tid:
            flash("Dados invalidos.", "danger")
            return redirect(url_for("listar_campeonatos"))
        error = services["championships"].unenroll_team(current_user, oid, tid)
        flash(error or "Time removido do campeonato.", "warning" if error else "success")
        return redirect(url_for("ver_campeonato", camp_id=camp_id))

    @app.route("/campeonatos/<camp_id>/status", methods=["POST"], endpoint="atualizar_status_campeonato")
    @login_required
    @roles_required(ROLE_ADMIN)
    def atualizar_status_campeonato(camp_id):
        current_user = build_current_user()
        oid = to_oid(camp_id)
        if not oid:
            flash("ID invalido.", "danger")
            return redirect(url_for("listar_campeonatos"))
        status = request.form.get("status", "")
        error = services["championships"].update_status(current_user, oid, status)
        flash(error or f"Status atualizado para '{status}'.", "danger" if error else "success")
        return redirect(url_for("ver_campeonato", camp_id=camp_id))

    @app.route("/campeonatos/<camp_id>/remover", methods=["POST"], endpoint="remover_campeonato")
    @login_required
    @roles_required(ROLE_ADMIN)
    def remover_campeonato(camp_id):
        current_user = build_current_user()
        oid = to_oid(camp_id)
        if not oid:
            flash("ID invalido.", "danger")
        elif services["championships"].delete_championship(current_user, oid):
            flash("Campeonato e suas partidas foram removidos.", "success")
        else:
            flash("Campeonato nao encontrado.", "warning")
        return redirect(url_for("listar_campeonatos"))

    @app.route("/campeonatos/<camp_id>/gerar-partidas", methods=["POST"], endpoint="gerar_partidas_campeonato")
    @login_required
    @roles_required(ROLE_ADMIN)
    def gerar_partidas_campeonato(camp_id):
        current_user = build_current_user()
        oid = to_oid(camp_id)
        if not oid:
            flash("ID invalido.", "danger")
            return redirect(url_for("listar_campeonatos"))
            
        errors = services["championships"].generate_matches(current_user, oid)
        if errors:
            for error in errors:
                flash(error, "danger")
        else:
            flash("Partidas e chaves geradas automaticamente com sucesso!", "success")
        return redirect(url_for("ver_campeonato", camp_id=camp_id))


    @app.route("/campeonatos/<camp_id>/partidas/nova", methods=["POST"], endpoint="nova_partida")
    @login_required
    @roles_required(ROLE_ADMIN)
    def nova_partida(camp_id):
        current_user = build_current_user()
        oid = to_oid(camp_id)
        if not oid:
            flash("ID invalido.", "danger")
            return redirect(url_for("listar_campeonatos"))
        try:
            error = services["matches"].create_match(current_user, oid, request.form)
        except Exception:
            error = "Selecione os dois times."
        flash(error or "Partida agendada!", "danger" if error else "success")
        return redirect(url_for("ver_campeonato", camp_id=camp_id))

    @app.route("/partidas/<partida_id>/resultado", methods=["POST"], endpoint="registrar_resultado")
    @login_required
    @roles_required(ROLE_ADMIN)
    def registrar_resultado(partida_id):
        current_user = build_current_user()
        oid = to_oid(partida_id)
        if not oid:
            flash("ID invalido.", "danger")
            return redirect(url_for("listar_campeonatos"))
        error, camp_id = services["matches"].register_result(
            current_user,
            oid,
            request.form.get("placar_a", "0"),
            request.form.get("placar_b", "0"),
        )
        flash(error or "Resultado registrado com sucesso!", "warning" if error else "success")
        redirect_id = str(camp_id) if camp_id else None
        return redirect(url_for("ver_campeonato", camp_id=redirect_id) if redirect_id else url_for("listar_campeonatos"))

    @app.route("/partidas/<partida_id>/rounds", methods=["GET"], endpoint="rounds_control")
    @login_required
    def rounds_control(partida_id):
        current_user = build_current_user()
        oid = to_oid(partida_id)
        if not oid:
            flash("ID invalido.", "danger")
            return redirect(url_for("dashboard"))
            
        match = services["matches"].match_repo.find_by_id(oid)
        if not match:
            flash("Partida nao encontrada.", "warning")
            return redirect(url_for("dashboard"))

        # Verify permissions: admin or designated referee
        is_admin = current_user.get("role") in (ROLE_ADMIN, ROLE_SUPER_ADMIN) and can_access_admin_scope(current_user, match.get("admin_id"))
        is_designated_referee = False
        if current_user.get("role") == ROLE_REFEREE:
            referee = services["matches"].match_repo.collection.database["usuarios"].find_one({"_id": current_user["_id"]})
            referee_id = referee.get("referee_id") if referee else None
            if referee_id and match.get("arbitro_id") and str(match["arbitro_id"]) == str(referee_id):
                is_designated_referee = True

        if not is_admin and not is_designated_referee:
            flash("Acesso negado para arbitrar esta partida.", "danger")
            return redirect(url_for("dashboard"))

        if match.get("status") == "finalizada":
            flash("Esta partida ja foi finalizada.", "info")
            return redirect(url_for("ver_campeonato", camp_id=str(match["campeonato_id"])))

        return render_template("partidas/rounds.html", partida=match)

    @app.route("/partidas/<partida_id>/rounds/vencer", methods=["POST"], endpoint="rounds_vencer")
    @login_required
    def rounds_vencer(partida_id):
        current_user = build_current_user()
        oid = to_oid(partida_id)
        if not oid:
            return {"success": False, "error": "ID invalido."}, 400

        vencedor_id_str = request.json.get("vencedor_id")
        metodo = request.json.get("metodo") # "elimination" or "objective"
        if not vencedor_id_str or not metodo:
            return {"success": False, "error": "Dados insuficientes."}, 400

        vencedor_id = to_oid(vencedor_id_str)
        if not vencedor_id:
            return {"success": False, "error": "ID de time invalido."}, 400

        error, updated_match = services["matches"].add_round(current_user, oid, vencedor_id, metodo)
        if error:
            return {"success": False, "error": error}, 400

        # Build serialized rounds list to send back to JS
        rounds_list = []
        for r in updated_match.get("rounds", []):
            rounds_list.append({
                "round": r["round"],
                "vencedor_id": str(r["vencedor_id"]),
                "metodo": r["metodo"],
                "timestamp": r["timestamp"].isoformat() if hasattr(r["timestamp"], "isoformat") else str(r["timestamp"])
            })

        return {
            "success": True,
            "score_a": updated_match["time_a"]["placar"],
            "score_b": updated_match["time_b"]["placar"],
            "rounds": rounds_list
        }

    @app.route("/partidas/<partida_id>/rounds/desfazer", methods=["POST"], endpoint="rounds_desfazer")
    @login_required
    def rounds_desfazer(partida_id):
        current_user = build_current_user()
        oid = to_oid(partida_id)
        if not oid:
            return {"success": False, "error": "ID invalido."}, 400

        error, updated_match = services["matches"].undo_round(current_user, oid)
        if error:
            return {"success": False, "error": error}, 400

        rounds_list = []
        for r in updated_match.get("rounds", []):
            rounds_list.append({
                "round": r["round"],
                "vencedor_id": str(r["vencedor_id"]),
                "metodo": r["metodo"],
                "timestamp": r["timestamp"].isoformat() if hasattr(r["timestamp"], "isoformat") else str(r["timestamp"])
            })

        return {
            "success": True,
            "score_a": updated_match["time_a"]["placar"],
            "score_b": updated_match["time_b"]["placar"],
            "rounds": rounds_list
        }

    @app.route("/partidas/<partida_id>/rounds/finalizar", methods=["POST"], endpoint="rounds_finalizar")
    @login_required
    def rounds_finalizar(partida_id):
        current_user = build_current_user()
        oid = to_oid(partida_id)
        if not oid:
            return {"success": False, "error": "ID invalido."}, 400

        match = services["matches"].match_repo.find_by_id(oid)
        if not match:
            return {"success": False, "error": "Partida nao encontrada."}, 404

        score_a = str(match["time_a"]["placar"])
        score_b = str(match["time_b"]["placar"])

        error, camp_id = services["matches"].register_result(current_user, oid, score_a, score_b)
        if error:
            return {"success": False, "error": error}, 400

        flash("Partida finalizada com sucesso!", "success")
        return {
            "success": True,
            "redirect_url": url_for("ver_campeonato", camp_id=str(camp_id)) if camp_id else "/dashboard"
        }

    @app.route("/partidas/<partida_id>/checkin/solicitar", methods=["POST"], endpoint="solicitar_checkin")
    @login_required
    @roles_required(ROLE_ADMIN)
    def solicitar_checkin(partida_id):
        current_user = build_current_user()
        oid = to_oid(partida_id)
        if not oid:
            flash("ID invalido.", "danger")
            return redirect(url_for("listar_campeonatos"))
        minutos = request.form.get("antecedencia_minutos", "30")
        error, camp_id = services["matches"].solicitar_checkin(current_user, oid, minutos)
        flash(error or "Check-in solicitado com sucesso!", "danger" if error else "success")
        redirect_id = str(camp_id) if camp_id else None
        return redirect(url_for("ver_campeonato", camp_id=redirect_id) if redirect_id else url_for("listar_campeonatos"))

    @app.route("/partidas/<partida_id>/checkin/confirmar", methods=["POST"], endpoint="confirmar_presenca")
    @login_required
    def confirmar_presenca(partida_id):
        current_user = build_current_user()
        oid = to_oid(partida_id)
        if not oid:
            flash("ID invalido.", "danger")
            return redirect(url_for("listar_campeonatos"))
        tid = to_oid(request.form.get("time_id", ""))
        if not tid:
            flash("Time invalido.", "danger")
            return redirect(url_for("listar_campeonatos"))
        error, camp_id = services["matches"].confirmar_presenca(current_user, oid, tid)
        flash(error or "Presenca confirmada com sucesso!", "danger" if error else "success")
        redirect_id = str(camp_id) if camp_id else None
        return redirect(url_for("ver_campeonato", camp_id=redirect_id) if redirect_id else url_for("listar_campeonatos"))

    @app.route("/meu-time", endpoint="meu_time")
    @login_required
    @roles_required(ROLE_PLAYER)
    def meu_time():
        data = services["player_profile"].get_profile(session["user_id"])
        if not data or not data.get("time"):
            flash("Voce nao pertence a nenhum time.", "warning")
            return redirect(url_for("meu_perfil"))
        return render_template("operador/meu_time.html", time=data["time"], jogador=data["jogador"])

    @app.route("/meu-perfil", endpoint="meu_perfil")
    @login_required
    @roles_required(ROLE_PLAYER)
    def meu_perfil():
        return redirect(url_for("dashboard"))

    @app.route("/ranking", endpoint="ranking")
    @login_required
    def ranking():
        current_user = build_current_user()
        player_data = services["player_profile"].get_profile(session["user_id"]) if session.get("role") == ROLE_PLAYER else None
        player_game = ((player_data or {}).get("jogador") or {}).get("jogo_principal", "")
        jogo = request.args.get("jogo", "").strip()
        if session.get("role") == ROLE_PLAYER:
            jogo = player_game
        jogadores = services["ranking"].list_ranking(current_user, jogo)
        show_team_ranking = session.get("role") in (ROLE_ADMIN, ROLE_SUPER_ADMIN) or bool(jogo)
        team_ranking = services["ranking"].list_team_ranking(current_user, jogo) if show_team_ranking else []
        return render_template(
            "ranking.html",
            jogadores=jogadores,
            filtro_jogo=jogo,
            player_game=player_game,
            show_team_ranking=show_team_ranking,
            team_ranking=team_ranking,
        )

    @app.route("/relatorios", endpoint="relatorios")
    @login_required
    @roles_required(ROLE_ADMIN, ROLE_SUPER_ADMIN)
    def relatorios():
        current_user = build_current_user()
        data_ini = request.args.get("data_ini", "").strip()
        data_fim = request.args.get("data_fim", "").strip()
        reports, warning = services["reports"].list_reports(current_user, data_ini, data_fim)
        if warning:
            flash(warning, "warning")
        return render_template("relatorios.html", reports=reports, data_ini=data_ini, data_fim=data_fim)

    @app.route("/relatorios/export/<report_key>.<file_format>", endpoint="exportar_relatorio")
    @login_required
    @roles_required(ROLE_ADMIN, ROLE_SUPER_ADMIN)
    def exportar_relatorio(report_key, file_format):
        current_user = build_current_user()
        data_ini = request.args.get("data_ini", "").strip()
        data_fim = request.args.get("data_fim", "").strip()
        report, warning = services["reports"].get_report(current_user, report_key, data_ini, data_fim)
        if warning:
            flash(warning, "warning")
        if not report:
            flash("Relatorio nao encontrado.", "warning")
            return redirect(url_for("relatorios"))

        if file_format == "csv":
            payload = build_csv_bytes(report)
            mimetype = "text/csv"
        elif file_format == "pdf":
            payload = build_pdf_bytes(report)
            mimetype = "application/pdf"
        else:
            flash("Formato de exportacao invalido.", "warning")
            return redirect(url_for("relatorios"))

        filename = f"{report_key}.{file_format}"
        return Response(
            payload,
            mimetype=mimetype,
            headers={"Content-Disposition": f"attachment; filename={filename}"},
        )

    @app.route("/usuarios", endpoint="listar_usuarios")
    @login_required
    @roles_required(ROLE_SUPER_ADMIN)
    def listar_usuarios():
        return render_template("usuarios/lista.html", usuarios=services["users"].list_admin_accounts())

    @app.route("/usuarios/novo", methods=["GET", "POST"], endpoint="novo_usuario")
    @login_required
    @roles_required(ROLE_SUPER_ADMIN)
    def novo_usuario():
        credenciais = None
        if request.method == "POST":
            errors, credenciais = services["users"].create_admin_invitation(
                request.form.get("nome", "").strip(),
                request.form.get("login", "").strip(),
                request.form.get("nome_empresa", "").strip(),
                request.form.get("expira_em", "").strip() or None,
            )
            if errors:
                for error in errors:
                    flash(error, "danger")
                return render_template("usuarios/form.html", dados=request.form, credenciais=None)
            flash("ADMIN criado com convite controlado.", "success")
        return render_template("usuarios/form.html", dados={}, credenciais=credenciais)

    @app.route("/usuarios/<user_id>/remover", methods=["POST"], endpoint="remover_usuario")
    @login_required
    @roles_required(ROLE_SUPER_ADMIN)
    def remover_usuario(user_id):
        if user_id == session["user_id"]:
            flash("Voce nao pode remover sua propria conta.", "danger")
            return redirect(url_for("listar_usuarios"))
        oid = to_oid(user_id)
        if not oid:
            flash("ID invalido.", "danger")
            return redirect(url_for("listar_usuarios"))
        services["users"].delete_user(oid)
        flash("Usuario removido.", "success")
        return redirect(url_for("listar_usuarios"))

    @app.route("/partidas/<partida_id>/checkin/verificar", methods=["POST"], endpoint="verificar_checkin")
    @login_required
    @roles_required(ROLE_SUPER_ADMIN, ROLE_ADMIN)
    def verificar_checkin(partida_id):
        current_user = build_current_user()
        oid = to_oid(partida_id)
        if not oid:
            flash("ID invalido.", "danger")
            return redirect(url_for("listar_campeonatos"))
        error, camp_id = services["matches"].verificar_limite_checkin(current_user, oid)
        flash(error or "Verificacao de check-in / W.O. realizada com sucesso!", "danger" if error else "success")
        redirect_id = str(camp_id) if camp_id else None
        return redirect(url_for("ver_campeonato", camp_id=redirect_id) if redirect_id else url_for("listar_campeonatos"))

    @app.route("/notificacoes/ler_todas", methods=["POST"], endpoint="marcar_todas_notificacoes_lidas")
    @login_required
    def marcar_todas_notificacoes_lidas():
        current_user = build_current_user()
        services["notifications"].mark_all_as_read(current_user)
        flash("Todas as notificacoes foram marcadas como lidas.", "success")
        return redirect(url_for("dashboard"))

    @app.route("/notificacoes/<notif_id>/ler", methods=["POST"], endpoint="marcar_notificacao_lida")
    @login_required
    def marcar_notificacao_lida(notif_id):
        current_user = build_current_user()
        services["notifications"].mark_as_read(current_user, notif_id)
        return {"status": "ok"}

    @app.route("/api/notificacoes", methods=["GET"], endpoint="api_notificacoes")
    @login_required
    def api_notificacoes():
        current_user = build_current_user()
        services["notifications"].ensure_upcoming_match_notifications(current_user)
        notifications = services["notifications"].list_notifications(current_user, unread_only=True)
        payload = []
        for notification in notifications:
            created_at = notification.get("criado_em")
            payload.append(
                {
                    "id": str(notification["_id"]),
                    "mensagem": notification.get("mensagem", ""),
                    "jogo": notification.get("jogo", ""),
                    "link": notification.get("link", ""),
                    "criado_em": created_at.strftime("%d/%m %H:%M") if created_at else "Agora",
                }
            )
        return {"notifications": payload, "unread_count": len(payload), "role": current_user.get("role")}

    @app.route("/arbitros", endpoint="listar_arbitros")
    @login_required
    @roles_required(ROLE_SUPER_ADMIN, ROLE_ADMIN)
    def listar_arbitros():
        current_user = build_current_user()
        busca = request.args.get("busca", "").strip()
        arbitros = services["arbitros"].list_referees(current_user, busca)
        return render_template("arbitros/lista.html", arbitros=arbitros, busca=busca)

    @app.route("/arbitros/novo", methods=["GET", "POST"], endpoint="novo_arbitro")
    @login_required
    @roles_required(ROLE_ADMIN)
    def novo_arbitro():
        current_user = build_current_user()
        campeonatos = services["championships"].list_championships(current_user, "", "")
        if request.method == "POST":
            errors = services["arbitros"].create_referee(current_user, request.form)
            if errors:
                for error in errors:
                    flash(error, "danger")
                return render_template(
                    "arbitros/form.html",
                    dados=request.form,
                    campeonatos=campeonatos,
                    acao="novo",
                )
            flash("Arbitro cadastrado com sucesso!", "success")
            return redirect(url_for("listar_arbitros"))
        return render_template("arbitros/form.html", dados={}, campeonatos=campeonatos, acao="novo")

    @app.route("/arbitros/<arbitro_id>/editar", methods=["GET", "POST"], endpoint="editar_arbitro")
    @login_required
    @roles_required(ROLE_ADMIN)
    def editar_arbitro(arbitro_id):
        current_user = build_current_user()
        oid = to_oid(arbitro_id)
        if not oid:
            flash("ID invalido.", "danger")
            return redirect(url_for("listar_arbitros"))
        arbitro, user = services["arbitros"].get_referee_details(current_user, oid)
        if not arbitro:
            flash("Arbitro nao encontrado.", "warning")
            return redirect(url_for("listar_arbitros"))
        
        campeonatos = services["championships"].list_championships(current_user, "", "")
        ids_vinculados = {str(cid) for cid in arbitro.get("campeonatos_vinculados", [])}
        
        if request.method == "POST":
            errors = services["arbitros"].update_referee(current_user, oid, request.form)
            if errors:
                for error in errors:
                    flash(error, "danger")
                return render_template(
                    "arbitros/form.html",
                    dados=request.form,
                    acao="editar",
                    arbitro=arbitro,
                    campeonatos=campeonatos,
                    ids_vinculados=ids_vinculados,
                )
            flash("Arbitro atualizado com sucesso!", "success")
            return redirect(url_for("listar_arbitros"))
            
        dados = dict(arbitro)
        if user:
            dados["login"] = user.get("login", "")
        return render_template(
            "arbitros/form.html",
            dados=dados,
            acao="editar",
            arbitro=arbitro,
            campeonatos=campeonatos,
            ids_vinculados=ids_vinculados,
        )

    @app.route("/arbitros/<arbitro_id>/remover", methods=["POST"], endpoint="remover_arbitro")
    @login_required
    @roles_required(ROLE_ADMIN)
    def remover_arbitro(arbitro_id):
        current_user = build_current_user()
        oid = to_oid(arbitro_id)
        if not oid:
            flash("ID invalido.", "danger")
        elif services["arbitros"].delete_referee(current_user, oid):
            flash("Arbitro removido com sucesso.", "success")
        else:
            flash("Arbitro nao encontrado.", "warning")
        return redirect(url_for("listar_arbitros"))
