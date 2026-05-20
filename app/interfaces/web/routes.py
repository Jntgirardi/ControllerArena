from __future__ import annotations

from flask import Response, flash, redirect, render_template, request, session, url_for

from ...application.services import ROLE_ADMIN, ROLE_PLAYER, ROLE_SUPER_ADMIN
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


def register_routes(app, services):
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
        return redirect(url_for("dashboard") if "user_id" in session else url_for("login"))

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
        campeonatos = services["championships"].list_championships(current_user, status, jogo)
        return render_template("campeonatos/lista.html", campeonatos=campeonatos, filtro_status=status, filtro_jogo=jogo)

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
        return render_template("campeonatos/detalhe.html", **details)

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
