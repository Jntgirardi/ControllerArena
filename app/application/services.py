from __future__ import annotations

from datetime import UTC, datetime
from typing import Any
from uuid import uuid4

from bson import ObjectId
from pymongo import DESCENDING


ROLE_SUPER_ADMIN = "SUPER_ADMIN"
ROLE_ADMIN = "ADMIN"
ROLE_PLAYER = "PLAYER"

STATUS_INSCRICAO = "INSCRICAO"
STATUS_EM_ANDAMENTO = "EM_ANDAMENTO"
STATUS_FINALIZADO = "FINALIZADO"
VALID_STATUSES = (STATUS_INSCRICAO, STATUS_EM_ANDAMENTO, STATUS_FINALIZADO)
RANKING_CACHE_PREFIX = "fps_arena:ranking"


def utc_now_naive() -> datetime:
    return datetime.now(UTC).replace(tzinfo=None)


def normalize_utc_naive(value: datetime) -> datetime:
    if value.tzinfo is None:
        return value
    return value.astimezone(UTC).replace(tzinfo=None)


def get_scope_admin_id(current_user: dict[str, Any]) -> ObjectId | None:
    role = current_user.get("role")
    if role == ROLE_ADMIN:
        return current_user["_id"]
    if role == ROLE_PLAYER:
        return current_user.get("admin_id")
    return None


def can_access_admin_scope(current_user: dict[str, Any], admin_id: ObjectId | None) -> bool:
    if current_user.get("role") == ROLE_SUPER_ADMIN:
        return True
    return get_scope_admin_id(current_user) == admin_id


def invalidate_ranking_cache(cache) -> None:
    cache.delete_pattern(f"{RANKING_CACHE_PREFIX}:*")


class AuthService:
    def __init__(self, user_repo, password_hasher):
        self.user_repo = user_repo
        self.password_hasher = password_hasher

    def authenticate(self, identity: str, password: str, mode: str = "login") -> dict[str, Any] | None:
        if mode == "access_code":
            user = self.user_repo.find_admin_by_access_code(identity)
            if not user:
                return None
            expires_at = user.get("access_code_expires_at")
            if expires_at and normalize_utc_naive(expires_at) < utc_now_naive():
                return None
        else:
            user = self.user_repo.find_by_login(identity)
            if not user:
                user = self.user_repo.find_by_username(identity)
        if not user or not user.get("ativo", True):
            return None
        if not self.password_hasher.verify(password, user["senha_hash"]):
            return None
        return user


class DashboardService:
    def __init__(self, user_repo, player_repo, team_repo, championship_repo, match_repo):
        self.user_repo = user_repo
        self.player_repo = player_repo
        self.team_repo = team_repo
        self.championship_repo = championship_repo
        self.match_repo = match_repo

    def build_dashboard(self, current_user: dict[str, Any]) -> dict[str, Any]:
        role = current_user["role"]
        if role == ROLE_SUPER_ADMIN:
            stats = {
                "admins": len(self.user_repo.list_all({"role": ROLE_ADMIN})),
                "jogadores": self.player_repo.count_all(),
                "campeonatos": self.championship_repo.count_all(),
                "partidas": self.match_repo.count_all(),
            }
            ultimos_camps = self.championship_repo.list_recent(limit=5)
            return {"stats": stats, "ultimos_camps": ultimos_camps}

        admin_id = get_scope_admin_id(current_user)
        scoped = {"admin_id": admin_id}
        stats = {
            "jogadores": self.player_repo.count_all(scoped),
            "times": self.team_repo.count_all(scoped),
            "campeonatos": self.championship_repo.count_all(scoped),
            "partidas": self.match_repo.count_all(scoped),
            "camp_inscricao": self.championship_repo.count_by_status(STATUS_INSCRICAO, scoped),
            "camp_andamento": self.championship_repo.count_by_status(STATUS_EM_ANDAMENTO, scoped),
        }
        ultimos_camps = self.championship_repo.list_recent(scoped, limit=5)
        return {"stats": stats, "ultimos_camps": ultimos_camps}


class PlayerService:
    def __init__(self, player_repo, user_repo, team_repo, password_hasher, cache):
        self.player_repo = player_repo
        self.user_repo = user_repo
        self.team_repo = team_repo
        self.password_hasher = password_hasher
        self.cache = cache

    def _base_filter(self, current_user: dict[str, Any], jogo: str = "") -> dict[str, Any]:
        filtro = {}
        admin_id = get_scope_admin_id(current_user)
        if current_user["role"] != ROLE_SUPER_ADMIN:
            filtro["admin_id"] = admin_id
        if jogo:
            filtro["jogo_principal"] = jogo
        return filtro

    def validate(self, data: dict[str, Any], creating: bool = True) -> list[str]:
        errors = []
        if not data.get("nick", "").strip():
            errors.append("Nick e obrigatorio.")
        if not data.get("nome", "").strip():
            errors.append("Nome do jogador e obrigatorio.")
        if data.get("jogo_principal") not in ("CS2", "Valorant"):
            errors.append("Jogo principal invalido.")
        if creating:
            if not data.get("login", "").strip():
                errors.append("Login do jogador e obrigatorio.")
            if len(data.get("senha", "")) < 6:
                errors.append("Senha do jogador deve ter ao menos 6 caracteres.")
        if data.get("jogo_principal") == "CS2":
            try:
                if int(data.get("premier_rating") or 0) < 0:
                    errors.append("Premier Rating nao pode ser negativo.")
            except ValueError:
                errors.append("Premier Rating deve ser um numero inteiro.")
        return errors

    def list_players(self, current_user: dict[str, Any], jogo: str, busca: str) -> list[dict[str, Any]]:
        return self.player_repo.list_filtered(self._base_filter(current_user, jogo), busca)

    def create_player(self, current_user: dict[str, Any], data: dict[str, Any]) -> list[str]:
        errors = self.validate(data, creating=True)
        if errors:
            return errors
        admin_id = get_scope_admin_id(current_user)
        login = data["login"].strip()
        if self.user_repo.find_by_login(login):
            return ["Login ja existe."]
        if self.player_repo.find_by_nick_case_insensitive(data["nick"].strip(), admin_id):
            return ["Este nick ja esta cadastrado para este organizador."]

        player_document = {
            "nick": data["nick"].strip(),
            "nome": data["nome"].strip(),
            "nome_real": data["nome"].strip(),
            "login": login,
            "jogo_principal": data["jogo_principal"],
            "contato": data.get("contato", "").strip(),
            "admin_id": admin_id,
            "campeonato_id": ObjectId(data["campeonato_id"]) if data.get("campeonato_id") else None,
            "estatisticas": {"partidas_jogadas": 0, "vitorias": 0, "derrotas": 0, "kd_ratio": 0.0},
            "criado_em": datetime.utcnow(),
        }
        if data["jogo_principal"] == "CS2":
            player_document["rank_competitivo"] = data.get("rank_competitivo", "Sem Rank")
            player_document["premier_rating"] = int(data.get("premier_rating") or 0)
        else:
            player_document["rank_ato"] = data.get("rank_ato", "Sem Rank")
            player_document["agente_principal"] = data.get("agente_principal", "").strip()

        player_id = self.player_repo.insert(player_document)
        self.user_repo.insert(
            {
                "nome": data["nome"].strip(),
                "login": login,
                "senha_hash": self.password_hasher.hash(data["senha"]),
                "role": ROLE_PLAYER,
                "admin_id": admin_id,
                "player_id": player_id,
                "ativo": True,
                "must_change_password": False,
                "criado_em": datetime.utcnow(),
            }
        )
        invalidate_ranking_cache(self.cache)
        return []

    def get_player_details(self, current_user: dict[str, Any], object_id):
        player = self.player_repo.find_by_id(object_id)
        if not player or not can_access_admin_scope(current_user, player.get("admin_id")):
            return None, None
        team = self.team_repo.find_by_player_id(object_id)
        return player, team

    def update_player(self, current_user: dict[str, Any], object_id, data: dict[str, Any]) -> list[str]:
        player = self.player_repo.find_by_id(object_id)
        if not player or not can_access_admin_scope(current_user, player.get("admin_id")):
            return ["Jogador nao encontrado."]

        errors = self.validate(data, creating=False)
        if errors:
            return errors

        update = {
            "nick": data["nick"].strip(),
            "nome": data["nome"].strip(),
            "nome_real": data["nome"].strip(),
            "jogo_principal": data["jogo_principal"],
            "contato": data.get("contato", "").strip(),
            "campeonato_id": ObjectId(data["campeonato_id"]) if data.get("campeonato_id") else None,
        }
        if data["jogo_principal"] == "CS2":
            update["rank_competitivo"] = data.get("rank_competitivo", "Sem Rank")
            update["premier_rating"] = int(data.get("premier_rating") or 0)
            self.player_repo.unset_fields(object_id, {"rank_ato": "", "agente_principal": ""})
        else:
            update["rank_ato"] = data.get("rank_ato", "Sem Rank")
            update["agente_principal"] = data.get("agente_principal", "").strip()
            self.player_repo.unset_fields(object_id, {"rank_competitivo": "", "premier_rating": ""})
        self.player_repo.update_fields(object_id, update)
        invalidate_ranking_cache(self.cache)
        return []

    def delete_player(self, current_user: dict[str, Any], object_id) -> bool:
        player = self.player_repo.find_by_id(object_id)
        if not player or not can_access_admin_scope(current_user, player.get("admin_id")):
            return False
        deleted = self.player_repo.delete_by_id(object_id)
        if deleted:
            self.team_repo.remove_player_from_all_teams(object_id)
            invalidate_ranking_cache(self.cache)
        return deleted


class TeamService:
    def __init__(self, team_repo, player_repo):
        self.team_repo = team_repo
        self.player_repo = player_repo

    def _scope_filter(self, current_user: dict[str, Any]) -> dict[str, Any]:
        if current_user["role"] == ROLE_SUPER_ADMIN:
            return {}
        return {"admin_id": get_scope_admin_id(current_user)}

    def list_teams(self, current_user: dict[str, Any]):
        return self.team_repo.list_all(self._scope_filter(current_user))

    def list_available_players(self, current_user: dict[str, Any]):
        filtro = self._scope_filter(current_user)
        filtro["time_id"] = {"$exists": False}
        return self.player_repo.list_for_team_selector(filtro)

    def validate(self, nome: str, tag: str, jogo: str, ids_selecionados: list[str]) -> list[str]:
        errors = []
        if not nome:
            errors.append("Nome do time e obrigatorio.")
        if not tag:
            errors.append("Tag do time e obrigatoria.")
        if not jogo:
            errors.append("Jogo e obrigatorio.")
        if not ids_selecionados:
            errors.append("Selecione ao menos 1 jogador.")
        return errors

    def build_members(self, ids_selecionados: list[str], form_data, current_user: dict[str, Any]) -> tuple[list[dict[str, Any]], list[str]]:
        membros = []
        errors = []
        admin_id = get_scope_admin_id(current_user)
        for jid in ids_selecionados:
            jog = self.player_repo.find_by_id(ObjectId(jid))
            if not jog or (current_user["role"] != ROLE_SUPER_ADMIN and jog.get("admin_id") != admin_id):
                errors.append("Um dos jogadores selecionados nao pertence ao seu escopo.")
                continue
            membros.append(
                {
                    "jogador_id": jog["_id"],
                    "nick": jog["nick"],
                    "funcao": form_data.get(f"funcao_{jid}", "Jogador").strip(),
                }
            )
        return membros, errors

    def create_team(self, current_user: dict[str, Any], nome: str, tag: str, jogo: str, ids_selecionados: list[str], form_data) -> list[str]:
        errors = self.validate(nome, tag, jogo, ids_selecionados)
        membros, build_errors = self.build_members(ids_selecionados, form_data, current_user)
        errors.extend(build_errors)
        if errors:
            return errors
        inserted_id = self.team_repo.insert(
            {
                "nome": nome,
                "tag": tag.upper(),
                "jogo": jogo,
                "admin_id": get_scope_admin_id(current_user),
                "jogadores": membros,
                "criado_em": datetime.utcnow(),
            }
        )
        for membro in membros:
            self.player_repo.set_team(membro["jogador_id"], inserted_id)
        return []

    def get_team_for_edit(self, current_user: dict[str, Any], object_id):
        team = self.team_repo.find_by_id(object_id)
        if not team or not can_access_admin_scope(current_user, team.get("admin_id")):
            return None
        ids_atuais = {str(m["jogador_id"]) for m in team.get("jogadores", [])}
        funcoes_atuais = {str(m["jogador_id"]): m.get("funcao", "Jogador") for m in team.get("jogadores", [])}
        return team, ids_atuais, funcoes_atuais

    def delete_team(self, current_user: dict[str, Any], object_id) -> bool:
        team = self.team_repo.find_by_id(object_id)
        if not team or not can_access_admin_scope(current_user, team.get("admin_id")):
            return False
        for membro in team.get("jogadores", []):
            self.player_repo.clear_team(membro["jogador_id"])
        self.team_repo.delete_by_id(object_id)
        return True

    def update_team(self, current_user: dict[str, Any], object_id, nome: str, tag: str, jogo: str, ids_selecionados: list[str], form_data) -> list[str]:
        team = self.team_repo.find_by_id(object_id)
        if not team or not can_access_admin_scope(current_user, team.get("admin_id")):
            return ["Time nao encontrado."]
        errors = self.validate(nome, tag, jogo, ids_selecionados)
        membros, build_errors = self.build_members(ids_selecionados, form_data, current_user)
        errors.extend(build_errors)
        if errors:
            return errors

        ids_atuais = {str(m["jogador_id"]) for m in team.get("jogadores", [])}
        novos_ids = set(ids_selecionados)
        for jid in ids_atuais - novos_ids:
            self.player_repo.clear_team(ObjectId(jid))

        self.team_repo.update_fields(object_id, {"nome": nome, "tag": tag.upper(), "jogo": jogo, "jogadores": membros})
        for jid in novos_ids:
            self.player_repo.set_team(ObjectId(jid), object_id)
        return []


class ChampionshipService:
    def __init__(self, championship_repo, team_repo, match_repo):
        self.championship_repo = championship_repo
        self.team_repo = team_repo
        self.match_repo = match_repo

    def _scope_filter(self, current_user: dict[str, Any], status: str = "", jogo: str = "") -> dict[str, Any]:
        filtro = {}
        if current_user["role"] != ROLE_SUPER_ADMIN:
            filtro["admin_id"] = get_scope_admin_id(current_user)
        if status:
            filtro["status"] = status
        if jogo:
            filtro["jogo"] = jogo
        return filtro

    def validate(self, data: dict[str, Any]) -> list[str]:
        errors = []
        if not data.get("nome", "").strip():
            errors.append("Nome do campeonato e obrigatorio.")
        if data.get("jogo") not in ("CS2", "Valorant"):
            errors.append("Jogo invalido.")
        try:
            inicio = datetime.strptime(data.get("data_inicio", ""), "%Y-%m-%d")
            fim = datetime.strptime(data.get("data_fim", ""), "%Y-%m-%d")
            if fim <= inicio:
                errors.append("Data de fim deve ser posterior a data de inicio.")
        except ValueError:
            errors.append("Datas invalidas. Use o formato AAAA-MM-DD.")
        try:
            if int(data.get("max_times") or 0) < 2:
                errors.append("O campeonato deve ter ao menos 2 times.")
        except ValueError:
            errors.append("Maximo de times deve ser um numero inteiro.")
        return errors

    def list_championships(self, current_user: dict[str, Any], status: str, jogo: str):
        return self.championship_repo.list_filtered(self._scope_filter(current_user, status, jogo))

    def list_available_for_admin(self, current_user: dict[str, Any]) -> list[dict[str, Any]]:
        return self.championship_repo.list_filtered(self._scope_filter(current_user, STATUS_INSCRICAO, ""))

    def create_championship(self, current_user: dict[str, Any], data: dict[str, Any]) -> list[str]:
        errors = self.validate(data)
        if errors:
            return errors
        self.championship_repo.insert(
            {
                "nome": data["nome"].strip(),
                "jogo": data["jogo"],
                "formato": data.get("formato", "mata-mata"),
                "max_times": int(data["max_times"]),
                "premiacao": {
                    "1_lugar": data.get("premio_1", "").strip(),
                    "2_lugar": data.get("premio_2", "").strip(),
                    "3_lugar": data.get("premio_3", "").strip(),
                },
                "datas": {
                    "inicio": datetime.strptime(data["data_inicio"], "%Y-%m-%d"),
                    "fim": datetime.strptime(data["data_fim"], "%Y-%m-%d"),
                },
                "status": STATUS_INSCRICAO,
                "admin_id": get_scope_admin_id(current_user),
                "times_inscritos": [],
                "criado_por": current_user["_id"],
                "criado_em": datetime.utcnow(),
            }
        )
        return []

    def get_details(self, current_user: dict[str, Any], object_id):
        camp = self.championship_repo.find_by_id(object_id)
        if not camp or not can_access_admin_scope(current_user, camp.get("admin_id")):
            return None
        times_inscritos_docs = [team for tid in camp.get("times_inscritos", []) if (team := self.team_repo.find_by_id(tid))]
        partidas = self.match_repo.list_by_championship(object_id)
        todos_times = self.team_repo.list_by_game(camp["jogo"], {"admin_id": camp.get("admin_id")})
        return {"camp": camp, "times_inscritos": times_inscritos_docs, "partidas": partidas, "todos_times": todos_times}

    def enroll_team(self, current_user: dict[str, Any], championship_id, team_id) -> str | None:
        camp = self.championship_repo.find_by_id(championship_id)
        team = self.team_repo.find_by_id(team_id)
        if not camp or not team:
            return "Campeonato ou time nao encontrado."
        if not can_access_admin_scope(current_user, camp.get("admin_id")) or team.get("admin_id") != camp.get("admin_id"):
            return "Acesso negado ao escopo deste campeonato."
        if camp["status"] != STATUS_INSCRICAO:
            return "Este campeonato nao esta aceitando inscricoes."
        if len(camp.get("times_inscritos", [])) >= camp["max_times"]:
            return "Campeonato lotado."
        if team_id in camp.get("times_inscritos", []):
            return "Time ja inscrito."
        self.championship_repo.push_team(championship_id, team_id)
        return None

    def unenroll_team(self, current_user: dict[str, Any], championship_id, team_id) -> str | None:
        camp = self.championship_repo.find_by_id(championship_id)
        if not camp or not can_access_admin_scope(current_user, camp.get("admin_id")):
            return "Campeonato nao encontrado."
        if camp["status"] == STATUS_FINALIZADO:
            return "Nao e possivel alterar times de um campeonato finalizado."
        if team_id not in camp.get("times_inscritos", []):
            return "Time nao esta inscrito neste campeonato."
        self.championship_repo.pull_team(championship_id, team_id)
        return None

    def update_status(self, current_user: dict[str, Any], championship_id, status: str) -> str | None:
        camp = self.championship_repo.find_by_id(championship_id)
        if not camp or not can_access_admin_scope(current_user, camp.get("admin_id")):
            return "Campeonato nao encontrado."
        if status not in VALID_STATUSES:
            return "Status invalido."
        self.championship_repo.update_fields(championship_id, {"status": status})
        return None

    def delete_championship(self, current_user: dict[str, Any], championship_id):
        camp = self.championship_repo.find_by_id(championship_id)
        if not camp or not can_access_admin_scope(current_user, camp.get("admin_id")):
            return False
        self.championship_repo.delete_by_id(championship_id)
        self.match_repo.delete_by_championship(championship_id)
        return True


class MatchService:
    def __init__(self, match_repo, championship_repo, team_repo, player_repo, cache):
        self.match_repo = match_repo
        self.championship_repo = championship_repo
        self.team_repo = team_repo
        self.player_repo = player_repo
        self.cache = cache

    def create_match(self, current_user: dict[str, Any], championship_id, form_data) -> str | None:
        camp = self.championship_repo.find_by_id(championship_id)
        if not camp or not can_access_admin_scope(current_user, camp.get("admin_id")):
            return "Campeonato nao encontrado."
        time_a_id = ObjectId(form_data.get("time_a_id", ""))
        time_b_id = ObjectId(form_data.get("time_b_id", ""))
        if time_a_id == time_b_id:
            return "Os dois times devem ser diferentes."
        time_a = self.team_repo.find_by_id(time_a_id)
        time_b = self.team_repo.find_by_id(time_b_id)
        if not time_a or not time_b:
            return "Um dos times nao foi encontrado."
        data_str = form_data.get("data_partida", "").strip()
        try:
            data_partida = datetime.strptime(data_str, "%Y-%m-%dT%H:%M") if data_str else datetime.utcnow()
        except ValueError:
            data_partida = datetime.utcnow()
        self.match_repo.insert(
            {
                "admin_id": camp.get("admin_id"),
                "campeonato_id": championship_id,
                "fase": form_data.get("fase", "").strip(),
                "time_a": {"time_id": time_a["_id"], "nome": time_a["nome"], "placar": 0},
                "time_b": {"time_id": time_b["_id"], "nome": time_b["nome"], "placar": 0},
                "vencedor_id": None,
                "mapa": form_data.get("mapa", "").strip(),
                "data_partida": data_partida,
                "status": "agendada",
            }
        )
        return None

    def register_result(self, current_user: dict[str, Any], match_id, placar_a: str, placar_b: str) -> tuple[str | None, ObjectId | None]:
        match = self.match_repo.find_by_id(match_id)
        if not match or not can_access_admin_scope(current_user, match.get("admin_id")):
            return "Partida nao encontrada.", None
        if match["status"] == "finalizada":
            return "Esta partida ja foi finalizada.", match["campeonato_id"]
        try:
            score_a = int(placar_a)
            score_b = int(placar_b)
        except ValueError:
            return "Placares invalidos.", match["campeonato_id"]
        if score_a == score_b:
            return "Partida nao pode terminar em empate.", match["campeonato_id"]

        vencedor_tid = match["time_a"]["time_id"] if score_a > score_b else match["time_b"]["time_id"]
        perdedor_tid = match["time_b"]["time_id"] if score_a > score_b else match["time_a"]["time_id"]
        self.match_repo.update_fields(
            match_id,
            {
                "time_a.placar": score_a,
                "time_b.placar": score_b,
                "vencedor_id": vencedor_tid,
                "status": "finalizada",
            },
        )

        increments = [
            (vencedor_tid, {"estatisticas.vitorias": 1, "estatisticas.partidas_jogadas": 1}),
            (perdedor_tid, {"estatisticas.derrotas": 1, "estatisticas.partidas_jogadas": 1}),
        ]
        for team_id, increment in increments:
            team = self.team_repo.find_by_id(team_id)
            if team:
                for membro in team.get("jogadores", []):
                    self.player_repo.increment_stats(membro["jogador_id"], increment)
        invalidate_ranking_cache(self.cache)
        return None, match["campeonato_id"]


class RankingService:
    def __init__(self, player_repo, team_repo, cache):
        self.player_repo = player_repo
        self.team_repo = team_repo
        self.cache = cache

    def _cache_key(self, current_user: dict[str, Any], jogo: str) -> str:
        scope = "global"
        if current_user["role"] != ROLE_SUPER_ADMIN:
            scope = str(get_scope_admin_id(current_user))
        game = jogo or "todos"
        return f"{RANKING_CACHE_PREFIX}:{scope}:{game}"

    def list_ranking(self, current_user: dict[str, Any], jogo: str):
        cache_key = self._cache_key(current_user, jogo)
        cached = self.cache.get(cache_key)
        if cached is not None:
            return cached

        filtro = {}
        if current_user["role"] != ROLE_SUPER_ADMIN:
            filtro["admin_id"] = get_scope_admin_id(current_user)
        if jogo:
            filtro["jogo_principal"] = jogo
        ranking = self.player_repo.list_ranking(filtro)
        self.cache.set(cache_key, ranking)
        return ranking

    def list_team_ranking(self, current_user: dict[str, Any], jogo: str):
        filtro = {}
        if current_user["role"] != ROLE_SUPER_ADMIN:
            filtro["admin_id"] = get_scope_admin_id(current_user)
        if jogo:
            filtro["jogo"] = jogo

        teams = self.team_repo.list_all(filtro)
        ranking = []
        for team in teams:
            partidas = 0
            vitorias = 0
            derrotas = 0
            jogadores = []
            for member in team.get("jogadores", []):
                player = self.player_repo.find_by_id(member.get("jogador_id"))
                if not player:
                    continue
                stats = player.get("estatisticas", {})
                partidas += int(stats.get("partidas_jogadas", 0) or 0)
                vitorias += int(stats.get("vitorias", 0) or 0)
                derrotas += int(stats.get("derrotas", 0) or 0)
                jogadores.append(player.get("nick", "-"))

            membros_count = max(len(team.get("jogadores", [])), 1)
            media_vitorias = round(vitorias / membros_count, 1)
            win_rate = round((vitorias / partidas) * 100, 1) if partidas else 0.0
            ranking.append(
                {
                    "_id": team["_id"],
                    "nome": team.get("nome", "-"),
                    "tag": team.get("tag", "-"),
                    "jogo": team.get("jogo", "-"),
                    "partidas": partidas,
                    "vitorias": vitorias,
                    "derrotas": derrotas,
                    "media_vitorias": media_vitorias,
                    "win_rate": win_rate,
                    "jogadores": jogadores,
                }
            )

        ranking.sort(key=lambda team: (-team["vitorias"], -team["win_rate"], team["nome"]))
        return ranking


class AuditLogService:
    def __init__(self, log_repo):
        self.log_repo = log_repo

    def record_request(self, user: dict[str, Any], endpoint: str, method: str, path: str, status_code: int) -> None:
        if not user or not endpoint:
            return
        self.log_repo.insert(
            {
                "user_id": user.get("_id"),
                "admin_id": get_scope_admin_id(user),
                "login": user.get("login", ""),
                "role": user.get("role", ""),
                "endpoint": endpoint,
                "method": method,
                "path": path,
                "status_code": status_code,
                "created_at": datetime.utcnow(),
            }
        )


class ReportService:
    SUMMARY_PREVIEW_LIMIT = 5

    def __init__(self, championship_repo, match_repo, player_repo, team_repo, event_repo, ticket_repo, log_repo):
        self.championship_repo = championship_repo
        self.match_repo = match_repo
        self.player_repo = player_repo
        self.team_repo = team_repo
        self.event_repo = event_repo
        self.ticket_repo = ticket_repo
        self.log_repo = log_repo
        self.report_builders = {
            "system-logs": self._build_system_logs_report,
            "player-ranking": self._build_player_ranking_report,
            "match-history": self._build_match_history_report,
            "championship-stats": self._build_championship_stats_report,
            "tournament-players": self._build_tournament_players_report,
            "ticket-sales": self._build_ticket_sales_report,
            "capacity-control": self._build_capacity_control_report,
        }

    def _base_filter(self, current_user: dict[str, Any]) -> dict[str, Any]:
        filtro = {}
        if current_user["role"] != ROLE_SUPER_ADMIN:
            filtro["admin_id"] = get_scope_admin_id(current_user)
        return filtro

    def _parse_date_filters(self, data_ini: str, data_fim: str) -> tuple[datetime | None, datetime | None, str | None]:
        warning = None
        try:
            start = datetime.strptime(data_ini, "%Y-%m-%d") if data_ini else None
            end = datetime.strptime(data_fim, "%Y-%m-%d") if data_fim else None
        except ValueError:
            warning = "Datas invalidas para o filtro."
            start = None
            end = None
        return start, end, warning

    def _filter_by_date_range(self, value: datetime | None, start: datetime | None, end: datetime | None) -> bool:
        if value is None:
            return start is None and end is None
        value = normalize_utc_naive(value)
        if start and value < start:
            return False
        if end and value > end:
            return False
        return True

    def _serialize_date(self, value: datetime | None) -> str:
        return normalize_utc_naive(value).strftime("%d/%m/%Y") if value else "-"

    def _normalize_status_label(self, status: str) -> str:
        mapping = {
            STATUS_INSCRICAO: "Inscricoes",
            STATUS_EM_ANDAMENTO: "Em andamento",
            STATUS_FINALIZADO: "Finalizado",
            "agendada": "Agendada",
            "finalizada": "Finalizada",
            "cancelado": "Cancelado",
            "pago": "Pago",
            "reservado": "Reservado",
        }
        return mapping.get(status, status.replace("_", " ").title() if status else "-")

    def _build_summary(self, rows: list[dict[str, Any]]) -> list[dict[str, Any]]:
        return rows[: self.SUMMARY_PREVIEW_LIMIT]

    def _is_report_allowed(self, current_user: dict[str, Any], report: dict[str, Any]) -> bool:
        return current_user.get("role") in report.get("allowed_roles", [ROLE_ADMIN, ROLE_SUPER_ADMIN])

    def _build_system_logs_report(self, current_user: dict[str, Any], start, end):
        logs = self.log_repo.list_by_query(self._base_filter(current_user), sort=[("created_at", DESCENDING)])
        rows = []
        for log in logs:
            created_at = log.get("created_at")
            if not self._filter_by_date_range(created_at, start, end):
                continue
            created_at = normalize_utc_naive(created_at) if created_at else None
            rows.append(
                {
                    "Horario": created_at.strftime("%H:%M:%S") if created_at else "-",
                    "Dia": created_at.strftime("%d/%m/%Y") if created_at else "-",
                    "Usuario": log.get("login", "-"),
                    "Perfil": log.get("role", "-"),
                    "Acao": f"{log.get('method', '-')}: {log.get('endpoint', '-')}",
                    "Rota": log.get("path", "-"),
                    "Status": log.get("status_code", "-"),
                }
            )
        return {
            "key": "system-logs",
            "title": "Relatorio de logs",
            "category": "E-Sports & Gaming",
            "admin_only": False,
            "allowed_roles": [ROLE_ADMIN, ROLE_SUPER_ADMIN],
            "summary_columns": ["Horario", "Dia", "Usuario", "Acao"],
            "columns": ["Horario", "Dia", "Usuario", "Perfil", "Acao", "Rota", "Status"],
            "rows": rows,
            "summary_rows": self._build_summary(rows),
            "metrics": [
                {"label": "Registros", "value": len(rows)},
                {"label": "Ultimo usuario", "value": rows[0]["Usuario"] if rows else "-"},
            ],
        }

    def _build_player_ranking_report(self, current_user: dict[str, Any], start, end):
        players = self.player_repo.list_by_query(
            self._base_filter(current_user),
            sort=[("estatisticas.vitorias", DESCENDING), ("estatisticas.kd_ratio", DESCENDING), ("nick", 1)],
        )
        rows = []
        for index, player in enumerate(players, start=1):
            stats = player.get("estatisticas", {})
            partidas = int(stats.get("partidas_jogadas", 0) or 0)
            vitorias = int(stats.get("vitorias", 0) or 0)
            win_rate = round((vitorias / partidas) * 100, 1) if partidas else 0.0
            rows.append(
                {
                    "Posicao": index,
                    "Nick": player.get("nick", "-"),
                    "Nome": player.get("nome", "-"),
                    "Jogo": player.get("jogo_principal", "-"),
                    "Vitorias": vitorias,
                    "Partidas": partidas,
                    "Win Rate (%)": win_rate,
                }
            )
        return {
            "key": "player-ranking",
            "title": "Ranking de jogadores",
            "category": "E-Sports & Gaming",
            "admin_only": False,
            "allowed_roles": [ROLE_ADMIN, ROLE_SUPER_ADMIN],
            "summary_columns": ["Posicao", "Nick", "Jogo", "Vitorias", "Win Rate (%)"],
            "columns": ["Posicao", "Nick", "Nome", "Jogo", "Vitorias", "Partidas", "Win Rate (%)"],
            "rows": rows,
            "summary_rows": self._build_summary(rows),
            "metrics": [
                {"label": "Jogadores ranqueados", "value": len(rows)},
                {"label": "Topo", "value": rows[0]["Nick"] if rows else "-"},
            ],
        }

    def _build_match_history_report(self, current_user: dict[str, Any], start, end):
        championships = self.championship_repo.list_by_query(self._base_filter(current_user), "datas.inicio", DESCENDING)
        championship_names = {camp["_id"]: camp.get("nome", "-") for camp in championships}
        matches = self.match_repo.list_by_query(self._base_filter(current_user), sort=[("data_partida", DESCENDING)])
        rows = []
        for match in matches:
            match_date = match.get("data_partida")
            if not self._filter_by_date_range(match_date, start, end):
                continue
            rows.append(
                {
                    "Campeonato": championship_names.get(match.get("campeonato_id"), "-"),
                    "Data": self._serialize_date(match_date),
                    "Fase": match.get("fase", "-"),
                    "Time A": match.get("time_a", {}).get("nome", "-"),
                    "Placar": f"{match.get('time_a', {}).get('placar', 0)} x {match.get('time_b', {}).get('placar', 0)}",
                    "Time B": match.get("time_b", {}).get("nome", "-"),
                    "Mapa": match.get("mapa", "-"),
                    "Status": self._normalize_status_label(match.get("status", "")),
                }
            )
        return {
            "key": "match-history",
            "title": "Historico de partidas por campeonato",
            "category": "E-Sports & Gaming",
            "admin_only": False,
            "allowed_roles": [ROLE_ADMIN, ROLE_SUPER_ADMIN],
            "summary_columns": ["Campeonato", "Data", "Fase", "Placar", "Status"],
            "columns": ["Campeonato", "Data", "Fase", "Time A", "Placar", "Time B", "Mapa", "Status"],
            "rows": rows,
            "summary_rows": self._build_summary(rows),
            "metrics": [
                {"label": "Partidas", "value": len(rows)},
                {"label": "Finalizadas", "value": sum(1 for row in rows if row["Status"] == "Finalizada")},
            ],
        }

    def _build_championship_stats_report(self, current_user: dict[str, Any], start, end):
        championships = self.championship_repo.list_by_query(self._base_filter(current_user), "datas.inicio", DESCENDING)
        rows = []
        for camp in championships:
            start_date = (camp.get("datas") or {}).get("inicio")
            if not self._filter_by_date_range(start_date, start, end):
                continue
            match_count = self.match_repo.count_by_championship(camp["_id"])
            matches = self.match_repo.list_by_championship(camp["_id"])
            finalized = sum(1 for match in matches if match.get("status") == "finalizada")
            inscritos = len(camp.get("times_inscritos", []))
            ocupacao = round((inscritos / camp["max_times"]) * 100, 1) if camp.get("max_times") else 0.0
            rows.append(
                {
                    "Campeonato": camp.get("nome", "-"),
                    "Jogo": camp.get("jogo", "-"),
                    "Status": self._normalize_status_label(camp.get("status", "")),
                    "Inicio": self._serialize_date(start_date),
                    "Fim": self._serialize_date((camp.get("datas") or {}).get("fim")),
                    "Times inscritos": inscritos,
                    "Limite de times": camp.get("max_times", 0),
                    "Taxa de ocupacao (%)": ocupacao,
                    "Partidas": match_count,
                    "Partidas finalizadas": finalized,
                }
            )
        return {
            "key": "championship-stats",
            "title": "Estatisticas de campeonatos",
            "category": "E-Sports & Gaming",
            "admin_only": False,
            "allowed_roles": [ROLE_ADMIN, ROLE_SUPER_ADMIN],
            "summary_columns": ["Campeonato", "Status", "Times inscritos", "Partidas", "Taxa de ocupacao (%)"],
            "columns": ["Campeonato", "Jogo", "Status", "Inicio", "Fim", "Times inscritos", "Limite de times", "Taxa de ocupacao (%)", "Partidas", "Partidas finalizadas"],
            "rows": rows,
            "summary_rows": self._build_summary(rows),
            "metrics": [
                {"label": "Campeonatos", "value": len(rows)},
                {"label": "Em andamento", "value": sum(1 for row in rows if row["Status"] == "Em andamento")},
            ],
        }

    def _build_tournament_players_report(self, current_user: dict[str, Any], start, end):
        championships = self.championship_repo.list_by_query(self._base_filter(current_user), "datas.inicio", DESCENDING)
        rows = []
        for camp in championships:
            start_date = (camp.get("datas") or {}).get("inicio")
            if not self._filter_by_date_range(start_date, start, end):
                continue
            teams = self.team_repo.list_by_ids(camp.get("times_inscritos", []))
            for team in teams:
                for member in team.get("jogadores", []):
                    player = self.player_repo.find_by_id(member.get("jogador_id"))
                    rows.append(
                        {
                            "Campeonato": camp.get("nome", "-"),
                            "Jogo": camp.get("jogo", "-"),
                            "Time": team.get("nome", "-"),
                            "Tag": team.get("tag", "-"),
                            "Jogador": member.get("nick", player.get("nick") if player else "-"),
                            "Nome": player.get("nome", "-") if player else "-",
                            "Funcao": member.get("funcao", "-"),
                        }
                    )
        return {
            "key": "tournament-players",
            "title": "Jogadores inscritos por torneio",
            "category": "E-Sports & Gaming",
            "admin_only": False,
            "allowed_roles": [ROLE_ADMIN, ROLE_SUPER_ADMIN],
            "summary_columns": ["Campeonato", "Time", "Jogador", "Funcao"],
            "columns": ["Campeonato", "Jogo", "Time", "Tag", "Jogador", "Nome", "Funcao"],
            "rows": rows,
            "summary_rows": self._build_summary(rows),
            "metrics": [
                {"label": "Inscricoes", "value": len(rows)},
                {"label": "Torneios com inscritos", "value": len({row['Campeonato'] for row in rows})},
            ],
        }

    def _build_ticket_sales_report(self, current_user: dict[str, Any], start, end):
        base_filter = self._base_filter(current_user)
        events = self.event_repo.list_by_query(base_filter, sort=[("data_evento", DESCENDING)])
        event_names = {event["_id"]: event.get("nome", "-") for event in events}
        tickets = self.ticket_repo.list_by_query(base_filter, sort=[("vendido_em", DESCENDING)])
        rows = []
        faturamento = 0.0
        vendidos = 0
        for ticket in tickets:
            sold_at = ticket.get("vendido_em")
            if not self._filter_by_date_range(sold_at, start, end):
                continue
            quantidade = int(ticket.get("quantidade", 0) or 0)
            valor_total = float(ticket.get("valor_total", 0) or 0)
            faturamento += valor_total
            vendidos += quantidade
            rows.append(
                {
                    "Evento": event_names.get(ticket.get("evento_id"), "-"),
                    "Comprador": ticket.get("comprador", "-"),
                    "Lote": ticket.get("lote", "-"),
                    "Quantidade": quantidade,
                    "Valor total (R$)": f"{valor_total:.2f}",
                    "Status": self._normalize_status_label(ticket.get("status", "")),
                    "Venda": self._serialize_date(sold_at),
                }
            )
        return {
            "key": "ticket-sales",
            "title": "Relatorio de vendas de ingressos",
            "category": "Shows e Eventos",
            "admin_only": True,
            "allowed_roles": [ROLE_ADMIN],
            "summary_columns": ["Evento", "Lote", "Quantidade", "Valor total (R$)", "Status"],
            "columns": ["Evento", "Comprador", "Lote", "Quantidade", "Valor total (R$)", "Status", "Venda"],
            "rows": rows,
            "summary_rows": self._build_summary(rows),
            "metrics": [
                {"label": "Ingressos vendidos", "value": vendidos},
                {"label": "Faturamento", "value": f"R$ {faturamento:.2f}"},
            ],
        }

    def _build_capacity_control_report(self, current_user: dict[str, Any], start, end):
        events = self.event_repo.list_by_query(self._base_filter(current_user), sort=[("data_evento", DESCENDING)])
        tickets = self.ticket_repo.list_by_query(self._base_filter(current_user))
        sold_by_event = {}
        for ticket in tickets:
            sold_by_event[ticket.get("evento_id")] = sold_by_event.get(ticket.get("evento_id"), 0) + int(ticket.get("quantidade", 0) or 0)

        rows = []
        for event in events:
            event_date = event.get("data_evento")
            if not self._filter_by_date_range(event_date, start, end):
                continue
            capacidade = int(event.get("capacidade_total", 0) or 0)
            vendidos = sold_by_event.get(event["_id"], 0)
            disponivel = max(capacidade - vendidos, 0)
            ocupacao = round((vendidos / capacidade) * 100, 1) if capacidade else 0.0
            rows.append(
                {
                    "Evento": event.get("nome", "-"),
                    "Data": self._serialize_date(event_date),
                    "Local": event.get("local", "-"),
                    "Capacidade total": capacidade,
                    "Ingressos vendidos": vendidos,
                    "Disponivel": disponivel,
                    "Ocupacao (%)": ocupacao,
                }
            )
        return {
            "key": "capacity-control",
            "title": "Controle de lotacao",
            "category": "Shows e Eventos",
            "admin_only": True,
            "allowed_roles": [ROLE_ADMIN],
            "summary_columns": ["Evento", "Data", "Capacidade total", "Ingressos vendidos", "Ocupacao (%)"],
            "columns": ["Evento", "Data", "Local", "Capacidade total", "Ingressos vendidos", "Disponivel", "Ocupacao (%)"],
            "rows": rows,
            "summary_rows": self._build_summary(rows),
            "metrics": [
                {"label": "Eventos monitorados", "value": len(rows)},
                {"label": "Maior ocupacao", "value": f"{max((row['Ocupacao (%)'] for row in rows), default=0):.1f}%"},
            ],
        }

    def list_reports(self, current_user: dict[str, Any], data_ini: str, data_fim: str) -> tuple[list[dict[str, Any]], str | None]:
        start, end, warning = self._parse_date_filters(data_ini, data_fim)
        reports = []
        for builder in self.report_builders.values():
            report = builder(current_user, start, end)
            if self._is_report_allowed(current_user, report):
                reports.append(report)
        return reports, warning

    def get_report(self, current_user: dict[str, Any], report_key: str, data_ini: str, data_fim: str) -> tuple[dict[str, Any] | None, str | None]:
        start, end, warning = self._parse_date_filters(data_ini, data_fim)
        builder = self.report_builders.get(report_key)
        if not builder:
            return None, warning
        report = builder(current_user, start, end)
        if not self._is_report_allowed(current_user, report):
            return None, warning
        return report, warning


class PlayerProfileService:
    def __init__(self, user_repo, player_repo, team_repo, championship_repo):
        self.user_repo = user_repo
        self.player_repo = player_repo
        self.team_repo = team_repo
        self.championship_repo = championship_repo

    def get_profile(self, user_id: str) -> dict[str, Any] | None:
        user = self.user_repo.find_by_id(ObjectId(user_id))
        if not user or user.get("role") != ROLE_PLAYER or not user.get("player_id"):
            return None
        jogador = self.player_repo.find_by_id(user["player_id"])
        if not jogador:
            return None
        time = self.team_repo.find_by_player_id(user["player_id"])
        campeonatos = self.championship_repo.list_by_team_id(time["_id"]) if time else []
        return {"jogador": jogador, "time": time, "campeonatos": campeonatos}


class UserService:
    def __init__(self, user_repo, password_hasher):
        self.user_repo = user_repo
        self.password_hasher = password_hasher

    def get_user(self, user_id: str):
        return self.user_repo.find_by_id(ObjectId(user_id))

    def list_admin_accounts(self):
        return self.user_repo.list_all({"role": {"$in": [ROLE_SUPER_ADMIN, ROLE_ADMIN]}})

    def create_admin_invitation(self, nome: str, login: str, nome_empresa: str, expires_at: str | None) -> tuple[list[str], dict[str, Any] | None]:
        errors = []
        if not nome.strip():
            errors.append("Nome do administrador e obrigatorio.")
        if not login.strip():
            errors.append("Login do administrador e obrigatorio.")
        if not nome_empresa.strip():
            errors.append("Nome da empresa e obrigatorio.")
        if self.user_repo.find_by_login(login.strip()):
            errors.append("Login ja existe.")
        expiry = None
        if expires_at:
            try:
                expiry = datetime.strptime(expires_at, "%Y-%m-%d")
            except ValueError:
                errors.append("Data de expiracao invalida.")
        if errors:
            return errors, None

        access_code = str(uuid4())
        initial_password = uuid4().hex[:10]
        user_id = self.user_repo.insert(
            {
                "nome": nome.strip(),
                "login": login.strip(),
                "nome_empresa": nome_empresa.strip(),
                "role": ROLE_ADMIN,
                "admin_id": None,
                "access_code": access_code,
                "access_code_expires_at": expiry,
                "senha_hash": self.password_hasher.hash(initial_password),
                "ativo": True,
                "must_change_password": True,
                "criado_em": datetime.utcnow(),
            }
        )
        return [], {"user_id": user_id, "codigo_acesso": access_code, "senha_inicial": initial_password}

    def change_password(self, user_id: str, new_password: str, confirm_password: str) -> list[str]:
        errors = []
        if len(new_password) < 6:
            errors.append("A nova senha deve ter ao menos 6 caracteres.")
        if new_password != confirm_password:
            errors.append("A confirmacao de senha nao confere.")
        if errors:
            return errors
        self.user_repo.update_fields(
            ObjectId(user_id),
            {"senha_hash": self.password_hasher.hash(new_password), "must_change_password": False},
        )
        return []

    def delete_user(self, object_id):
        self.user_repo.delete_by_id(object_id)


def build_services(repositories: dict[str, Any], password_hasher, cache):
    return {
        "auth": AuthService(repositories["users"], password_hasher),
        "dashboard": DashboardService(
            repositories["users"],
            repositories["players"],
            repositories["teams"],
            repositories["championships"],
            repositories["matches"],
        ),
        "players": PlayerService(
            repositories["players"],
            repositories["users"],
            repositories["teams"],
            password_hasher,
            cache,
        ),
        "teams": TeamService(repositories["teams"], repositories["players"]),
        "championships": ChampionshipService(repositories["championships"], repositories["teams"], repositories["matches"]),
        "matches": MatchService(
            repositories["matches"],
            repositories["championships"],
            repositories["teams"],
            repositories["players"],
            cache,
        ),
        "ranking": RankingService(repositories["players"], repositories["teams"], cache),
        "audit_logs": AuditLogService(repositories["logs"]),
        "reports": ReportService(
            repositories["championships"],
            repositories["matches"],
            repositories["players"],
            repositories["teams"],
            repositories["events"],
            repositories["tickets"],
            repositories["logs"],
        ),
        "users": UserService(repositories["users"], password_hasher),
        "player_profile": PlayerProfileService(
            repositories["users"],
            repositories["players"],
            repositories["teams"],
            repositories["championships"],
        ),
    }
