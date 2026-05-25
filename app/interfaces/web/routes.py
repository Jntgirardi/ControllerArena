from __future__ import annotations

from flask import Response, abort, flash, redirect, render_template, request, session, url_for

from ...application.services import ROLE_ADMIN, ROLE_PLAYER, ROLE_REFEREE, ROLE_SUPER_ADMIN
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


def register_routes(app, services):
    @app.context_processor
    def inject_notifications_count():
        current_user = build_current_user()
        if current_user:
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
        campeonatos_ativos = [camp for camp in PUBLIC_CHAMPIONSHIPS if camp["status"] != "Finalizado"]
        return render_template("home_hltv.html", campeonatos=campeonatos_ativos)

    @app.route("/campeonato/<int:camp_id>", endpoint="detalhes_campeonato_publico")
    def detalhes_campeonato_publico(camp_id):
        campeonato = _public_championship_by_id(camp_id)
        if not campeonato:
            abort(404)
        partidas = campeonato["partidas"]
        
        times_seen = set()
        times_inscritos = []
        for p in partidas:
            for side in ("time_a", "time_b"):
                team_data = p.get(side)
                if team_data and team_data.get("nome"):
                    nome = team_data["nome"]
                    tag = team_data.get("tag", "TBD")
                    if nome not in times_seen:
                        times_seen.add(nome)
                        times_inscritos.append({"nome": nome, "tag": tag})

        return render_template(
            "detalhes_campeonato.html",
            campeonato=campeonato,
            times_inscritos=times_inscritos,
            partidas_ao_vivo=[p for p in partidas if p["status"] == "ao_vivo"],
            proximos_jogos=[p for p in partidas if p["status"] == "agendado"],
            resultados=[p for p in partidas if p["status"] == "finalizado"],
        )

    @app.route("/partida/<int:partida_id>", endpoint="sumula_partida_publica")
    def sumula_partida_publica(partida_id):
        campeonato, partida = _public_match_by_id(partida_id)
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
        if session.get("role") == ROLE_PLAYER:
            player_data = services["player_profile"].get_profile(session["user_id"])
            return render_template("dashboard.html", active_tab="player-home", player_data=player_data)
        data = services["dashboard"].build_dashboard(current_user)
        return render_template(
            "dashboard.html",
            stats=data["stats"],
            ultimos_camps=data["ultimos_camps"],
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
        todos_jogadores = services["teams"].list_available_players(current_user)
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
            
        return render_template("campeonatos/detalhe.html", arbitros=arbitros, **details)

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
