from __future__ import annotations

import json
import logging
from urllib import error as urllib_error
from urllib import request as urllib_request
from datetime import UTC, datetime, timedelta
from typing import Any
from uuid import uuid4

from bson import ObjectId
from pymongo import DESCENDING


ROLE_SUPER_ADMIN = "SUPER_ADMIN"
ROLE_ADMIN = "ADMIN"
ROLE_PLAYER = "PLAYER"
ROLE_REFEREE = "REFEREE"

STATUS_INSCRICAO = "INSCRICAO"
STATUS_EM_ANDAMENTO = "EM_ANDAMENTO"
STATUS_FINALIZADO = "FINALIZADO"
STATUS_ARQUIVADO = "ARQUIVADO"
VALID_STATUSES = (STATUS_INSCRICAO, STATUS_EM_ANDAMENTO, STATUS_FINALIZADO, STATUS_ARQUIVADO)

RANKING_CACHE_PREFIX = "fps_arena:ranking"
DISCORD_WEBHOOK_PREFIXES = (
    "https://discord.com/api/webhooks/",
    "https://discordapp.com/api/webhooks/",
)

logger = logging.getLogger(__name__)


def utc_now_naive() -> datetime:
    return datetime.now(UTC).replace(tzinfo=None)


def local_now_naive() -> datetime:
    return datetime.now().replace(tzinfo=None)


def normalize_utc_naive(value: datetime) -> datetime:
    if value.tzinfo is None:
        return value
    return value.astimezone(UTC).replace(tzinfo=None)


def get_scope_admin_id(current_user: dict[str, Any]) -> ObjectId | None:
    role = current_user.get("role")
    if role == ROLE_ADMIN:
        return current_user["_id"]
    if role in (ROLE_PLAYER, ROLE_REFEREE):
        return current_user.get("admin_id")
    return None



def can_access_admin_scope(current_user: dict[str, Any], admin_id: ObjectId | None) -> bool:
    if current_user.get("role") == ROLE_SUPER_ADMIN:
        return True
    return get_scope_admin_id(current_user) == admin_id


def invalidate_ranking_cache(cache) -> None:
    cache.delete_pattern(f"{RANKING_CACHE_PREFIX}:*")


class DiscordWebhookNotifier:
    def __init__(self, timeout_seconds: int = 5):
        self.timeout_seconds = timeout_seconds

    def send_message(self, webhook_url: str | None, content: str) -> bool:
        webhook_url = (webhook_url or "").strip()
        if not webhook_url:
            return False

        payload = json.dumps(
            {
                "username": "Controller Arena",
                "content": content[:2000],
            }
        ).encode("utf-8")
        req = urllib_request.Request(
            webhook_url,
            data=payload,
            headers={
                "Content-Type": "application/json",
                "User-Agent": "FPS-Arena/1.0",
            },
            method="POST",
        )

        try:
            with urllib_request.urlopen(req, timeout=self.timeout_seconds) as response:
                return 200 <= response.status < 300
        except (urllib_error.URLError, TimeoutError, OSError) as exc:
            logger.warning("Falha ao enviar notificacao para o Discord: %s", exc)
            return False


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

        if role == ROLE_REFEREE:
            referee = self.user_repo.collection.find_one({"_id": current_user["_id"]})
            referee_id = referee.get("referee_id") if referee else None
            
            matches = list(self.match_repo.collection.find({"arbitro_id": referee_id}).sort("data_partida", 1))
            notifications = list(self.user_repo.collection.database["notificacoes"].find({"user_id": current_user["_id"], "lida": False}).sort("criado_em", -1))
            
            return {
                "stats": {
                    "referee_mode": True,
                    "partidas": matches,
                    "notificacoes": notifications
                },
                "ultimos_camps": []
            }

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
        if self.player_repo.find_by_nick_case_insensitive(data["nick"].strip(), admin_id):
            return ["Este nick ja esta cadastrado para este organizador."]

        player_document = {
            "nick": data["nick"].strip(),
            "nome": data["nome"].strip(),
            "nome_real": data["nome"].strip(),
            "login": None,
            "jogo_principal": data["jogo_principal"],
            "contato": data.get("contato", "").strip(),
            "admin_id": admin_id,
            "campeonato_id": ObjectId(data["campeonato_id"]) if data.get("campeonato_id") else None,
            "estatisticas": {"partidas_jogadas": 0, "vitorias": 0, "derrotas": 0, "kd_ratio": 0.0},
            "criado_em": utc_now_naive(),
        }
        if data["jogo_principal"] == "CS2":
            player_document["rank_competitivo"] = data.get("rank_competitivo", "Sem Rank")
            player_document["premier_rating"] = int(data.get("premier_rating") or 0)
        else:
            player_document["rank_ato"] = data.get("rank_ato", "Sem Rank")
            player_document["agente_principal"] = data.get("agente_principal", "").strip()

        player_id = self.player_repo.insert(player_document)
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
            self.user_repo.delete_by_player_id(object_id)
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

    def list_available_players(self, current_user: dict[str, Any], include_team_id: Any = None):
        filtro = self._scope_filter(current_user)
        if include_team_id:
            filtro["$or"] = [
                {"time_id": {"$exists": False}},
                {"time_id": include_team_id}
            ]
        else:
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

    def create_team(self, current_user: dict[str, Any], nome: str, tag: str, jogo: str, ids_selecionados: list[str], form_data, logo_path: str | None = None) -> list[str]:
        errors = self.validate(nome, tag, jogo, ids_selecionados)
        membros, build_errors = self.build_members(ids_selecionados, form_data, current_user)
        errors.extend(build_errors)
        if errors:
            return errors
        document = {
            "nome": nome,
            "tag": tag.upper(),
            "jogo": jogo,
            "admin_id": get_scope_admin_id(current_user),
            "jogadores": membros,
            "criado_em": utc_now_naive(),
        }
        if logo_path:
            document["logo_path"] = logo_path
        inserted_id = self.team_repo.insert(document)
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

    def update_team(self, current_user: dict[str, Any], object_id, nome: str, tag: str, jogo: str, ids_selecionados: list[str], form_data, logo_path: str | None = None) -> list[str]:
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

        update_fields = {"nome": nome, "tag": tag.upper(), "jogo": jogo, "jogadores": membros}
        if logo_path:
            update_fields["logo_path"] = logo_path
        self.team_repo.update_fields(object_id, update_fields)
        for jid in novos_ids:
            self.player_repo.set_team(ObjectId(jid), object_id)
        return []


class ChampionshipService:
    def __init__(self, championship_repo, team_repo, match_repo):
        self.championship_repo = championship_repo
        self.team_repo = team_repo
        self.match_repo = match_repo
        self.valid_formats = ("mata-mata", "grupos")

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
        if data.get("formato") not in self.valid_formats:
            errors.append("Formato invalido.")
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
        webhook_url = data.get("discord_webhook_url", "").strip()
        if webhook_url and not webhook_url.startswith(DISCORD_WEBHOOK_PREFIXES):
            errors.append("Webhook do Discord deve ser uma URL valida de webhook do Discord.")
        return errors

    def list_championships(self, current_user: dict[str, Any], status: str, jogo: str):
        return self.championship_repo.list_filtered(self._scope_filter(current_user, status, jogo))

    def list_available_for_admin(self, current_user: dict[str, Any]) -> list[dict[str, Any]]:
        return self.championship_repo.list_filtered(self._scope_filter(current_user, STATUS_INSCRICAO, ""))

    def validate_edit_settings(self, data: dict[str, Any], current_registered_teams: int = 0) -> list[str]:
        errors = self.validate(data)
        try:
            max_times = int(data.get("max_times") or 0)
            if max_times < current_registered_teams:
                errors.append("O maximo de times nao pode ser menor que a quantidade de times ja inscritos.")
        except ValueError:
            pass
        return errors

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
                "discord_webhook_url": data.get("discord_webhook_url", "").strip(),
                "datas": {
                    "inicio": datetime.strptime(data["data_inicio"], "%Y-%m-%d"),
                    "fim": datetime.strptime(data["data_fim"], "%Y-%m-%d"),
                },
                "status": STATUS_INSCRICAO,
                "admin_id": get_scope_admin_id(current_user),
                "times_inscritos": [],
                "criado_por": current_user["_id"],
                "criado_em": utc_now_naive(),
            }
        )
        return []

    def get_championship_for_edit(self, current_user: dict[str, Any], championship_id):
        camp = self.championship_repo.find_by_id(championship_id)
        if not camp or not can_access_admin_scope(current_user, camp.get("admin_id")):
            return None
        return camp

    def update_championship_settings(self, current_user: dict[str, Any], championship_id, data: dict[str, Any]) -> list[str]:
        camp = self.championship_repo.find_by_id(championship_id)
        if not camp or not can_access_admin_scope(current_user, camp.get("admin_id")):
            return ["Campeonato nao encontrado."]
        if camp.get("status") == STATUS_ARQUIVADO:
            return ["Nao e possivel editar um campeonato arquivado."]

        errors = self.validate_edit_settings(data, len(camp.get("times_inscritos", [])))
        if errors:
            return errors

        self.championship_repo.update_fields(
            championship_id,
            {
                "nome": data["nome"].strip(),
                "jogo": data["jogo"],
                "formato": data["formato"],
                "max_times": int(data["max_times"]),
                "premiacao.1_lugar": data.get("premio_1", "").strip(),
                "premiacao.2_lugar": data.get("premio_2", "").strip(),
                "premiacao.3_lugar": data.get("premio_3", "").strip(),
                "discord_webhook_url": data.get("discord_webhook_url", "").strip(),
                "datas.inicio": datetime.strptime(data["data_inicio"], "%Y-%m-%d"),
                "datas.fim": datetime.strptime(data["data_fim"], "%Y-%m-%d"),
            },
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
        if camp["status"] in (STATUS_FINALIZADO, STATUS_ARQUIVADO):
            return "Nao e possivel alterar times de um campeonato finalizado ou arquivado."
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
        if camp.get("status") == STATUS_ARQUIVADO:
            return False
        self.championship_repo.delete_by_id(championship_id)
        self.match_repo.delete_by_championship(championship_id)
        return True

    def generate_matches(self, current_user: dict[str, Any], championship_id) -> list[str]:
        camp = self.championship_repo.find_by_id(championship_id)
        if not camp or not can_access_admin_scope(current_user, camp.get("admin_id")):
            return ["Campeonato nao encontrado."]
        if camp.get("status") == STATUS_ARQUIVADO:
            return ["Nao e possivel gerar partidas para um campeonato arquivado."]
        if camp.get("status") != STATUS_INSCRICAO:
            return ["A geracao automatica so e permitida para campeonatos em fase de inscricao."]
        
        # Check if matches already exist
        existing_matches = self.match_repo.list_by_championship(championship_id)
        if existing_matches:
            return ["Este campeonato ja possui partidas geradas. Remova-as ou finalize-as primeiro."]

        times_inscritos_ids = camp.get("times_inscritos", [])
        if len(times_inscritos_ids) < 2:
            return ["E necessario ter pelo menos 2 times inscritos para gerar as partidas."]

        # Load team documents
        times = []
        for tid in times_inscritos_ids:
            t = self.team_repo.find_by_id(tid)
            if t:
                times.append(t)
        
        if len(times) != len(times_inscritos_ids):
            return ["Erro ao carregar informacoes de alguns times inscritos."]

        formato = camp.get("formato", "mata-mata")
        matches_to_insert = []
        base_date = camp.get("datas", {}).get("inicio") or utc_now_naive()
        
        if formato == "mata-mata":
            n = len(times)
            # perfect brackets are powers of 2 (2, 4, 8, 16, 32)
            if n not in (2, 4, 8, 16, 32):
                return ["Para o formato Mata-Mata, a quantidade de times inscritos deve ser uma potencia de 2 (2, 4, 8 ou 16)."]
            
            # Determine Phase Name
            if n == 2:
                fase = "Grande Final"
            elif n == 4:
                fase = "Semifinal"
            elif n == 8:
                fase = "Quartas de Final"
            elif n == 16:
                fase = "Oitavas de Final"
            else:
                fase = "Primeira Rodada"

            # Pair sequentially
            for i in range(0, n, 2):
                time_a = times[i]
                time_b = times[i+1]
                data_partida = base_date + timedelta(hours=i)
                matches_to_insert.append({
                    "admin_id": camp.get("admin_id"),
                    "campeonato_id": championship_id,
                    "fase": fase,
                    "time_a": {"time_id": time_a["_id"], "nome": time_a["nome"], "placar": 0},
                    "time_b": {"time_id": time_b["_id"], "nome": time_b["nome"], "placar": 0},
                    "vencedor_id": None,
                    "mapa": "",
                    "data_partida": data_partida,
                    "status": "agendada",
                    "arbitro_id": None,
                })
        
        elif formato == "grupos":
            n = len(times)
            if n < 4:
                # 1 Group: Grupo A
                grupos = {"Grupo A": times}
            else:
                # 2 Groups: Grupo A and Grupo B
                grupo_a = []
                grupo_b = []
                for idx, t in enumerate(times):
                    if idx % 2 == 0:
                        grupo_a.append(t)
                    else:
                        grupo_b.append(t)
                grupos = {"Grupo A": grupo_a, "Grupo B": grupo_b}

            match_count = 0
            for nome_grupo, membros in grupos.items():
                m_len = len(membros)
                # Generate Round-Robin within the group
                for i in range(m_len):
                    for j in range(i + 1, m_len):
                        time_a = membros[i]
                        time_b = membros[j]
                        data_partida = base_date + timedelta(hours=match_count * 2)
                        matches_to_insert.append({
                            "admin_id": camp.get("admin_id"),
                            "campeonato_id": championship_id,
                            "fase": nome_grupo,
                            "time_a": {"time_id": time_a["_id"], "nome": time_a["nome"], "placar": 0},
                            "time_b": {"time_id": time_b["_id"], "nome": time_b["nome"], "placar": 0},
                            "vencedor_id": None,
                            "mapa": "",
                            "data_partida": data_partida,
                            "status": "agendada",
                            "arbitro_id": None,
                        })
                        match_count += 1
        
        else:
            return ["Formato de campeonato nao suportado para geracao automatica."]

        # Insert matches
        for m in matches_to_insert:
            self.match_repo.insert(m)
        
        # Update championship status to EM_ANDAMENTO
        self.championship_repo.update_fields(championship_id, {"status": STATUS_EM_ANDAMENTO})
        
        return []




class MatchService:
    def __init__(self, match_repo, championship_repo, team_repo, player_repo, cache, discord_notifier=None):
        self.match_repo = match_repo
        self.championship_repo = championship_repo
        self.team_repo = team_repo
        self.player_repo = player_repo
        self.cache = cache
        self.discord_notifier = discord_notifier or DiscordWebhookNotifier()

    def _match_label(self, match: dict[str, Any]) -> str:
        return f"{match['time_a']['nome']} x {match['time_b']['nome']}"

    def _send_discord_notification(self, camp: dict[str, Any] | None, message: str) -> None:
        if not camp:
            return
        try:
            self.discord_notifier.send_message(camp.get("discord_webhook_url"), message)
        except Exception as exc:
            logger.warning("Falha inesperada ao notificar Discord: %s", exc)

    def _format_match_datetime(self, match: dict[str, Any]) -> str:
        data_partida = match.get("data_partida")
        if not data_partida:
            return "horario a confirmar"
        return data_partida.strftime("%d/%m/%Y %H:%M")

    def _notify_match_started(self, camp: dict[str, Any] | None, match: dict[str, Any]) -> None:
        mapa = f" - {match.get('mapa')}" if match.get("mapa") else ""
        self._send_discord_notification(
            camp,
            (
                f"Partida iniciada em {camp.get('nome', 'campeonato')}: "
                f"{self._match_label(match)}{mapa}. "
                f"Horario previsto: {self._format_match_datetime(match)}."
            ),
        )

    def _notify_match_result(self, camp: dict[str, Any] | None, match: dict[str, Any], score_a: int, score_b: int) -> None:
        winner = match["time_a"]["nome"] if score_a > score_b else match["time_b"]["nome"]
        self._send_discord_notification(
            camp,
            (
                f"Resultado registrado em {camp.get('nome', 'campeonato')}: "
                f"{match['time_a']['nome']} {score_a} x {score_b} {match['time_b']['nome']}. "
                f"Vencedor: {winner}."
            ),
        )

    def create_match(self, current_user: dict[str, Any], championship_id, form_data) -> str | None:
        camp = self.championship_repo.find_by_id(championship_id)
        if not camp or not can_access_admin_scope(current_user, camp.get("admin_id")):
            return "Campeonato nao encontrado."
        if camp.get("status") in (STATUS_FINALIZADO, STATUS_ARQUIVADO):
            return "Nao e possivel adicionar partidas a um campeonato finalizado ou arquivado."
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
            data_partida = datetime.strptime(data_str, "%Y-%m-%dT%H:%M") if data_str else utc_now_naive()
        except ValueError:
            data_partida = utc_now_naive()
            
        arbitro_id = form_data.get("arbitro_id")
        if arbitro_id:
            arbitro_id = ObjectId(arbitro_id)
        else:
            arbitro_id = None

        match_id = self.match_repo.insert(
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
                "arbitro_id": arbitro_id,
            }
        )
        
        # Enviar notificacao ao arbitro caso tenha sido designado
        if arbitro_id:
            db = self.match_repo.collection.database
            user = db["usuarios"].find_one({"referee_id": arbitro_id})
            if user:
                db["notificacoes"].insert_one({
                    "user_id": user["_id"],
                    "mensagem": f"Voce foi designado como arbitro para a partida {time_a['nome']} x {time_b['nome']}.",
                    "lida": False,
                    "link": f"/campeonato/{championship_id}",
                    "criado_em": utc_now_naive(),
                })
        return None

    def register_result(
        self, current_user: dict[str, Any], match_id, placar_a: str, placar_b: str, kda_a: list = None, kda_b: list = None
    ) -> tuple[str | None, ObjectId | None]:
        match = self.match_repo.find_by_id(match_id)
        if not match:
            return "Partida nao encontrada.", None

        is_admin = current_user.get("role") in (ROLE_ADMIN, ROLE_SUPER_ADMIN) and can_access_admin_scope(current_user, match.get("admin_id"))
        is_designated_referee = False
        if current_user.get("role") == ROLE_REFEREE:
            referee = self.match_repo.collection.database["usuarios"].find_one({"_id": current_user["_id"]})
            referee_id = referee.get("referee_id") if referee else None
            if referee_id and match.get("arbitro_id") and str(match["arbitro_id"]) == str(referee_id):
                is_designated_referee = True

        if not is_admin and not is_designated_referee:
            return "Partida nao encontrada.", None
        camp = self.championship_repo.find_by_id(match["campeonato_id"])
        if camp and camp.get("status") == STATUS_ARQUIVADO:
            return "Nao e possivel alterar partidas de um campeonato arquivado.", match["campeonato_id"]
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
        
        update_fields = {
            "time_a.placar": score_a,
            "time_b.placar": score_b,
            "vencedor_id": vencedor_tid,
            "status": "finalizada",
        }
        
        # Save KDA lists into the match document if provided
        if kda_a is not None:
            mapped_kda_a = []
            for item in kda_a:
                mapped_kda_a.append({
                    "jogador_id": ObjectId(item["jogador_id"]) if isinstance(item.get("jogador_id"), str) else item.get("jogador_id"),
                    "nick": item.get("nick", "Jogador"),
                    "kills": int(item.get("kills") or 0),
                    "deaths": int(item.get("deaths") or 0),
                    "assists": int(item.get("assists") or 0),
                })
            update_fields["kda_a"] = mapped_kda_a
            
        if kda_b is not None:
            mapped_kda_b = []
            for item in kda_b:
                mapped_kda_b.append({
                    "jogador_id": ObjectId(item["jogador_id"]) if isinstance(item.get("jogador_id"), str) else item.get("jogador_id"),
                    "nick": item.get("nick", "Jogador"),
                    "kills": int(item.get("kills") or 0),
                    "deaths": int(item.get("deaths") or 0),
                    "assists": int(item.get("assists") or 0),
                })
            update_fields["kda_b"] = mapped_kda_b

        self.match_repo.update_fields(match_id, update_fields)

        increments = [
            (vencedor_tid, {"estatisticas.vitorias": 1, "estatisticas.partidas_jogadas": 1}),
            (perdedor_tid, {"estatisticas.derrotas": 1, "estatisticas.partidas_jogadas": 1}),
        ]
        for team_id, increment in increments:
            team = self.team_repo.find_by_id(team_id)
            if team:
                for membro in team.get("jogadores", []):
                    self.player_repo.increment_stats(membro["jogador_id"], increment)
                    
        # Update player KDA global stats in the player profiles
        for item in (kda_a or []):
            try:
                pid = ObjectId(item["jogador_id"]) if isinstance(item.get("jogador_id"), str) else item.get("jogador_id")
                if pid:
                    kills = int(item.get("kills") or 0)
                    deaths = int(item.get("deaths") or 0)
                    assists = int(item.get("assists") or 0)
                    player = self.player_repo.find_by_id(pid)
                    if player:
                        old_stats = player.get("estatisticas", {})
                        new_kills = old_stats.get("total_kills", 0) + kills
                        new_deaths = old_stats.get("total_deaths", 0) + deaths
                        new_assists = old_stats.get("total_assists", 0) + assists
                        kd = round(float(new_kills) / float(new_deaths), 2) if new_deaths > 0 else float(new_kills)
                        self.player_repo.update_fields(pid, {
                            "estatisticas.total_kills": new_kills,
                            "estatisticas.total_deaths": new_deaths,
                            "estatisticas.total_assists": new_assists,
                            "estatisticas.kd_ratio": kd
                        })
            except Exception as e:
                logger.warning("Falha ao salvar estatistica KDA para o jogador: %s", e)

        for item in (kda_b or []):
            try:
                pid = ObjectId(item["jogador_id"]) if isinstance(item.get("jogador_id"), str) else item.get("jogador_id")
                if pid:
                    kills = int(item.get("kills") or 0)
                    deaths = int(item.get("deaths") or 0)
                    assists = int(item.get("assists") or 0)
                    player = self.player_repo.find_by_id(pid)
                    if player:
                        old_stats = player.get("estatisticas", {})
                        new_kills = old_stats.get("total_kills", 0) + kills
                        new_deaths = old_stats.get("total_deaths", 0) + deaths
                        new_assists = old_stats.get("total_assists", 0) + assists
                        kd = round(float(new_kills) / float(new_deaths), 2) if new_deaths > 0 else float(new_kills)
                        self.player_repo.update_fields(pid, {
                            "estatisticas.total_kills": new_kills,
                            "estatisticas.total_deaths": new_deaths,
                            "estatisticas.total_assists": new_assists,
                            "estatisticas.kd_ratio": kd
                        })
            except Exception as e:
                logger.warning("Falha ao salvar estatistica KDA para o jogador: %s", e)

        invalidate_ranking_cache(self.cache)
        self._notify_match_result(camp, match, score_a, score_b)
        return None, match["campeonato_id"]

    def solicitar_checkin(self, current_user: dict[str, Any], match_id, antecedencia_minutos: str) -> tuple[str | None, ObjectId | None]:
        match = self.match_repo.find_by_id(match_id)
        if not match or not can_access_admin_scope(current_user, match.get("admin_id")):
            return "Partida nao encontrada.", None
        camp = self.championship_repo.find_by_id(match["campeonato_id"])
        if camp and camp.get("status") == STATUS_ARQUIVADO:
            return "Nao e possivel gerenciar check-in de partidas em campeonatos arquivados.", match["campeonato_id"]
        if match.get("status") == "finalizada":
            return "Esta partida ja foi finalizada.", match["campeonato_id"]
        try:
            minutos = int(antecedencia_minutos)
            if minutos < 5:
                return "A antecedencia minima e de 5 minutos.", match["campeonato_id"]
        except ValueError:
            return "Antecedencia invalida.", match["campeonato_id"]

        self.match_repo.update_fields(
            match_id,
            {
                "checkin": {
                    "solicitado": True,
                    "antecedencia_minutos": minutos,
                    "solicitado_em": utc_now_naive(),
                    "time_a_confirmado": False,
                    "time_b_confirmado": False,
                }
            }
        )
        
        # Notificar o arbitro se estiver designado
        arbitro_id = match.get("arbitro_id")
        if arbitro_id:
            db = self.match_repo.collection.database
            user = db["usuarios"].find_one({"referee_id": arbitro_id})
            if user:
                db["notificacoes"].insert_one({
                    "user_id": user["_id"],
                    "mensagem": f"O check-in para a partida {match['time_a']['nome']} x {match['time_b']['nome']} foi solicitado.",
                    "lida": False,
                    "link": f"/campeonato/{match['campeonato_id']}",
                    "criado_em": utc_now_naive(),
                })
        return None, match["campeonato_id"]

    def confirmar_presenca(self, current_user: dict[str, Any], match_id, team_id: ObjectId) -> tuple[str | None, ObjectId | None]:
        match = self.match_repo.find_by_id(match_id)
        if not match:
            return "Partida nao encontrada.", None
        camp = self.championship_repo.find_by_id(match["campeonato_id"])
        if camp and camp.get("status") == STATUS_ARQUIVADO:
            return "O check-in nao e permitido para campeonatos arquivados.", match["campeonato_id"]
        if match.get("status") == "finalizada":
            return "Esta partida ja foi finalizada.", match["campeonato_id"]


        checkin = match.get("checkin")
        if not checkin or not checkin.get("solicitado"):
            return "O check-in nao foi solicitado para esta partida.", match["campeonato_id"]

        # Validate team in match
        time_a_id = match["time_a"]["time_id"]
        time_b_id = match["time_b"]["time_id"]
        if team_id not in (time_a_id, time_b_id):
            return "Este time nao pertence a esta partida.", match["campeonato_id"]

        # Validate permission
        is_admin = can_access_admin_scope(current_user, match.get("admin_id"))
        is_player_on_team = False
        if current_user.get("role") == ROLE_PLAYER and current_user.get("player_id"):
            # Check if player belongs to team_id
            team = self.team_repo.find_by_id(team_id)
            if team:
                member_ids = {m["jogador_id"] for m in team.get("jogadores", [])}
                if current_user["player_id"] in member_ids:
                    is_player_on_team = True

        if not is_admin and not is_player_on_team:
            return "Acesso negado para confirmar presenca deste time.", match["campeonato_id"]

        # Validate time window
        data_partida = match.get("data_partida")
        if data_partida:
            agora = utc_now_naive()
            antecedencia = timedelta(minutes=checkin["antecedencia_minutos"])
            inicio_janela = data_partida - antecedencia
            # Only players are restricted to the window, admins can confirm at any time
            if not is_admin:
                if agora < inicio_janela:
                    minutos_restantes = int((inicio_janela - agora).total_seconds() / 60)
                    return f"A janela de check-in ainda nao abriu. Tente novamente em {minutos_restantes} minutos.", match["campeonato_id"]
                if agora > data_partida:
                    return "O horario de inicio da partida ja passou. Nao e mais possivel confirmar presenca.", match["campeonato_id"]

        # Update confirmation field
        field_to_update = "checkin.time_a_confirmado" if team_id == time_a_id else "checkin.time_b_confirmado"
        self.match_repo.update_fields(match_id, {field_to_update: True})
        
        # Notificar o arbitro do check-in realizado
        arbitro_id = match.get("arbitro_id")
        if arbitro_id:
            db = self.match_repo.collection.database
            user = db["usuarios"].find_one({"referee_id": arbitro_id})
            if user:
                team = self.team_repo.find_by_id(team_id)
                team_name = team.get("nome", "Um time") if team else "Um time"
                db["notificacoes"].insert_one({
                    "user_id": user["_id"],
                    "mensagem": f"O time '{team_name}' confirmou presenca na partida {match['time_a']['nome']} x {match['time_b']['nome']}.",
                    "lida": False,
                    "link": f"/campeonato/{match['campeonato_id']}",
                    "criado_em": utc_now_naive(),
                })
        return None, match["campeonato_id"]

    def verificar_limite_checkin(self, current_user: dict[str, Any], match_id) -> tuple[str | None, ObjectId | None]:
        match = self.match_repo.find_by_id(match_id)
        if not match or not can_access_admin_scope(current_user, match.get("admin_id")):
            return "Partida nao encontrada.", None
        if match.get("status") == "finalizada":
            return "Esta partida ja foi finalizada.", match["campeonato_id"]
            
        checkin = match.get("checkin")
        if not checkin or not checkin.get("solicitado"):
            return "Check-in nao foi solicitado para esta partida.", match["campeonato_id"]
            
        agora = utc_now_naive()
        data_partida = match.get("data_partida")
        if data_partida and agora < data_partida:
            return "O horario da partida ainda nao chegou. Aguarde o prazo limite.", match["campeonato_id"]
            
        confirm_a = checkin.get("time_a_confirmado", False)
        confirm_b = checkin.get("time_b_confirmado", False)
        
        if confirm_a and confirm_b:
            return "Ambos os times confirmaram presenca. A partida deve ser jogada normalmente.", match["campeonato_id"]
            
        placar_a = 0
        placar_b = 0
        vencedor_tid = None
        perdedor_tid = None
        
        if confirm_a and not confirm_b:
            placar_a = 13
            placar_b = 0
            vencedor_tid = match["time_a"]["time_id"]
            perdedor_tid = match["time_b"]["time_id"]
            mensagem = f"W.O. aplicado! O time {match['time_b']['nome']} faltou e o time {match['time_a']['nome']} venceu por 13x0."
        elif confirm_b and not confirm_a:
            placar_a = 0
            placar_b = 13
            vencedor_tid = match["time_b"]["time_id"]
            perdedor_tid = match["time_a"]["time_id"]
            mensagem = f"W.O. aplicado! O time {match['time_a']['nome']} faltou e o time {match['time_b']['nome']} venceu por 13x0."
        else:
            placar_a = 0
            placar_b = 0
            vencedor_tid = None
            mensagem = f"Duplo W.O. aplicado! Ambos os times ({match['time_a']['nome']} e {match['time_b']['nome']}) faltaram a partida."
            
        self.match_repo.update_fields(
            match_id,
            {
                "time_a.placar": placar_a,
                "time_b.placar": placar_b,
                "vencedor_id": vencedor_tid,
                "status": "finalizada",
                "checkin.wo_aplicado": True,
                "checkin.mensagem_wo": mensagem
            }
        )
        
        db = self.match_repo.collection.database
        
        if vencedor_tid and perdedor_tid:
            increments = [
                (vencedor_tid, {"estatisticas.vitorias": 1, "estatisticas.partidas_jogadas": 1}),
                (perdedor_tid, {"estatisticas.derrotas": 1, "estatisticas.partidas_jogadas": 1}),
            ]
            for team_id, increment in increments:
                team = self.team_repo.find_by_id(team_id)
                if team:
                    for membro in team.get("jogadores", []):
                        db["jogadores"].update_one({"_id": membro["jogador_id"]}, {"$inc": increment})
                        
        arbitro_id = match.get("arbitro_id")
        if arbitro_id:
            user = db["usuarios"].find_one({"referee_id": arbitro_id})
            if user:
                db["notificacoes"].insert_one({
                    "user_id": user["_id"],
                    "mensagem": f"ALERTA W.O. - {mensagem}",
                    "lida": False,
                    "link": f"/campeonato/{match['campeonato_id']}",
                    "criado_em": utc_now_naive(),
                })
                
        for side in ("time_a", "time_b"):
            team = self.team_repo.find_by_id(match[side]["time_id"])
            if team:
                for member in team.get("jogadores", []):
                    player_user = db["usuarios"].find_one({"player_id": member["jogador_id"]})
                    if player_user:
                        db["notificacoes"].insert_one({
                            "user_id": player_user["_id"],
                            "mensagem": f"Check-in Encerrado: {mensagem}",
                            "lida": False,
                            "link": f"/dashboard",
                            "criado_em": utc_now_naive(),
                        })

        self.cache.delete_pattern("fps_arena:ranking:*")
        return None, match["campeonato_id"]

    def add_round(self, current_user: dict[str, Any], match_id, vencedor_id: ObjectId, metodo: str) -> tuple[str | None, dict[str, Any] | None]:
        match = self.match_repo.find_by_id(match_id)
        if not match:
            return "Partida nao encontrada.", None
        
        # Check permissions: must be designated referee or admin
        is_admin = current_user.get("role") in (ROLE_ADMIN, ROLE_SUPER_ADMIN) and can_access_admin_scope(current_user, match.get("admin_id"))
        is_designated_referee = False
        if current_user.get("role") == ROLE_REFEREE:
            referee = self.match_repo.collection.database["usuarios"].find_one({"_id": current_user["_id"]})
            referee_id = referee.get("referee_id") if referee else None
            if referee_id and match.get("arbitro_id") and str(match["arbitro_id"]) == str(referee_id):
                is_designated_referee = True
                
        if not is_admin and not is_designated_referee:
            return "Acesso negado para arbitrar esta partida.", None
            
        if match.get("status") == "finalizada":
            return "Esta partida ja foi finalizada.", None

        camp = self.championship_repo.find_by_id(match["campeonato_id"])
        if camp and camp.get("status") == STATUS_ARQUIVADO:
            return "O campeonato esta arquivado.", None

        # Determine side (time_a or time_b)
        time_a_id = match["time_a"]["time_id"]
        time_b_id = match["time_b"]["time_id"]
        if vencedor_id not in (time_a_id, time_b_id):
            return "Time invalido para esta partida.", None

        side_to_inc = "time_a.placar" if vencedor_id == time_a_id else "time_b.placar"
        
        # Append round log
        rounds = match.get("rounds", [])
        round_num = len(rounds) + 1
        round_started_match = len(rounds) == 0
        new_round = {
            "round": round_num,
            "vencedor_id": vencedor_id,
            "metodo": metodo,
            "timestamp": utc_now_naive()
        }
        update_doc = {
            "$inc": {side_to_inc: 1},
            "$push": {"rounds": new_round}
        }
        if round_started_match:
            update_doc["$set"] = {"status": "em_andamento", "iniciada_em": new_round["timestamp"]}
        
        self.match_repo.collection.update_one(
            {"_id": match_id},
            update_doc
        )
        
        # Reload and return updated match
        updated_match = self.match_repo.find_by_id(match_id)
        if round_started_match:
            self._notify_match_started(camp, updated_match or match)
        return None, updated_match

    def undo_round(self, current_user: dict[str, Any], match_id) -> tuple[str | None, dict[str, Any] | None]:
        match = self.match_repo.find_by_id(match_id)
        if not match:
            return "Partida nao encontrada.", None
            
        # Check permissions: must be designated referee or admin
        is_admin = current_user.get("role") in (ROLE_ADMIN, ROLE_SUPER_ADMIN) and can_access_admin_scope(current_user, match.get("admin_id"))
        is_designated_referee = False
        if current_user.get("role") == ROLE_REFEREE:
            referee = self.match_repo.collection.database["usuarios"].find_one({"_id": current_user["_id"]})
            referee_id = referee.get("referee_id") if referee else None
            if referee_id and match.get("arbitro_id") and str(match["arbitro_id"]) == str(referee_id):
                is_designated_referee = True
                
        if not is_admin and not is_designated_referee:
            return "Acesso negado para arbitrar esta partida.", None
            
        if match.get("status") == "finalizada":
            return "Esta partida ja foi finalizada.", None

        camp = self.championship_repo.find_by_id(match["campeonato_id"])
        if camp and camp.get("status") == STATUS_ARQUIVADO:
            return "O campeonato esta arquivado.", None

        rounds = match.get("rounds", [])
        if not rounds:
            return "Nao ha rounds para desfazer.", None
            
        # Get last round
        last_round = rounds[-1]
        vencedor_id = last_round["vencedor_id"]
        
        # Determine side to decrement
        time_a_id = match["time_a"]["time_id"]
        side_to_dec = "time_a.placar" if vencedor_id == time_a_id else "time_b.placar"
        
        self.match_repo.collection.update_one(
            {"_id": match_id},
            {
                "$inc": {side_to_dec: -1},
                "$pop": {"rounds": 1}
            }
        )
        
        # Reload and return updated match
        updated_match = self.match_repo.find_by_id(match_id)
        return None, updated_match



class RankingService:
    def __init__(self, player_repo, team_repo, cache):
        self.player_repo = player_repo
        self.team_repo = team_repo
        self.cache = cache

    def _cache_key(self, current_user: dict[str, Any] | None, jogo: str) -> str:
        scope = "global"
        if current_user and current_user["role"] != ROLE_SUPER_ADMIN:
            scope = str(get_scope_admin_id(current_user))
        game = jogo or "todos"
        return f"{RANKING_CACHE_PREFIX}:{scope}:{game}"

    def list_ranking(self, current_user: dict[str, Any] | None, jogo: str):
        cache_key = self._cache_key(current_user, jogo)
        cached = self.cache.get(cache_key)
        if cached is not None:
            return cached

        filtro = {}
        if current_user and current_user["role"] != ROLE_SUPER_ADMIN:
            filtro["admin_id"] = get_scope_admin_id(current_user)
        if jogo:
            filtro["jogo_principal"] = jogo
        ranking = self.player_repo.list_ranking(filtro)
        
        # Enrich players with team info
        for player in ranking:
            tid = player.get("time_id")
            if tid:
                team = self.team_repo.find_by_id(tid)
                if team:
                    player["time_nome"] = team.get("nome", "-")
                    player["time_tag"] = team.get("tag", "-")
                else:
                    player["time_nome"] = "Sem time"
                    player["time_tag"] = ""
            else:
                player["time_nome"] = "Sem time"
                player["time_tag"] = ""

        self.cache.set(cache_key, ranking)
        return ranking

    def list_team_ranking(self, current_user: dict[str, Any] | None, jogo: str):
        filtro = {}
        if current_user and current_user["role"] != ROLE_SUPER_ADMIN:
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
                    "logo_path": team.get("logo_path", ""),
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
                "created_at": utc_now_naive(),
            }
        )


class ReportService:
    SUMMARY_PREVIEW_LIMIT = 5

    def __init__(self, championship_repo, match_repo, player_repo, team_repo, log_repo):
        self.championship_repo = championship_repo
        self.match_repo = match_repo
        self.player_repo = player_repo
        self.team_repo = team_repo
        self.log_repo = log_repo
        self.report_builders = {
            "system-logs": self._build_system_logs_report,
            "player-ranking": self._build_player_ranking_report,
            "match-history": self._build_match_history_report,
            "championship-stats": self._build_championship_stats_report,
            "tournament-players": self._build_tournament_players_report,
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
            STATUS_ARQUIVADO: "Arquivado",
            "agendada": "Agendada",
            "em_andamento": "Em andamento",
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
        index = 1
        for player in players:
            criado_em = player.get("criado_em")
            if not self._filter_by_date_range(criado_em, start, end):
                continue
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
            index += 1
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
    PASSWORD_RESET_TOKEN_HOURS = 1

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
                "criado_em": utc_now_naive(),
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

    def request_password_reset(self, identity: str) -> tuple[list[str], dict[str, Any] | None]:
        identity = identity.strip()
        if not identity:
            return ["Informe o login para recuperar a senha."], None

        user = self.user_repo.find_by_login(identity)
        if not user:
            user = self.user_repo.find_by_username(identity)
        if not user or not user.get("ativo", True):
            return [], None

        token = uuid4().hex
        expires_at = utc_now_naive() + timedelta(hours=self.PASSWORD_RESET_TOKEN_HOURS)
        self.user_repo.update_fields(
            user["_id"],
            {
                "password_reset_token": token,
                "password_reset_expires_at": expires_at,
                "password_reset_requested_at": utc_now_naive(),
            },
        )
        return [], {"token": token, "expires_at": expires_at, "login": user.get("login") or user.get("username")}

    def get_user_by_password_reset_token(self, token: str) -> dict[str, Any] | None:
        token = (token or "").strip()
        if not token:
            return None
        user = self.user_repo.find_by_password_reset_token(token)
        if not user or not user.get("ativo", True):
            return None
        expires_at = user.get("password_reset_expires_at")
        if not expires_at or normalize_utc_naive(expires_at) < utc_now_naive():
            return None
        return user

    def reset_password(self, token: str, new_password: str, confirm_password: str) -> list[str]:
        user = self.get_user_by_password_reset_token(token)
        errors = []
        if not user:
            errors.append("Link de recuperacao invalido ou expirado.")
        if len(new_password) < 6:
            errors.append("A nova senha deve ter ao menos 6 caracteres.")
        if new_password != confirm_password:
            errors.append("A confirmacao de senha nao confere.")
        if errors:
            return errors

        self.user_repo.update_fields(
            user["_id"],
            {"senha_hash": self.password_hasher.hash(new_password), "must_change_password": False},
        )
        self.user_repo.unset_fields(
            user["_id"],
            {
                "password_reset_token": "",
                "password_reset_expires_at": "",
                "password_reset_requested_at": "",
            },
        )
        return []

    def delete_user(self, object_id):
        self.user_repo.delete_by_id(object_id)


class ArbitroService:
    def __init__(self, arbitro_repo, user_repo, password_hasher):
        self.arbitro_repo = arbitro_repo
        self.user_repo = user_repo
        self.password_hasher = password_hasher

    def _base_filter(self, current_user: dict[str, Any]) -> dict[str, Any]:
        filtro = {}
        if current_user["role"] != ROLE_SUPER_ADMIN:
            filtro["admin_id"] = get_scope_admin_id(current_user)
        return filtro

    def validate(self, data: dict[str, Any], creating: bool = True) -> list[str]:
        errors = []
        if not data.get("nome", "").strip():
            errors.append("Nome e obrigatorio.")
        
        email = data.get("email", "").strip()
        if not email:
            errors.append("E-mail e obrigatorio.")
        elif "@" not in email:
            errors.append("E-mail invalido.")
            
        if not data.get("disponibilidade", "").strip():
            errors.append("Disponibilidade e obrigatoria.")

        if creating:
            if not data.get("login", "").strip():
                errors.append("Login e obrigatorio.")
            if len(data.get("senha", "")) < 6:
                errors.append("Senha deve ter ao menos 6 caracteres.")
        return errors

    def list_referees(self, current_user: dict[str, Any], busca: str = "") -> list[dict[str, Any]]:
        return self.arbitro_repo.list_filtered(self._base_filter(current_user), busca)

    def create_referee(self, current_user: dict[str, Any], data: dict[str, Any]) -> list[str]:
        errors = self.validate(data, creating=True)
        if errors:
            return errors
        admin_id = get_scope_admin_id(current_user)
        login = data["login"].strip()
        email = data["email"].strip()
        
        if self.user_repo.find_by_login(login):
            return ["Login ja existe."]
        if self.arbitro_repo.find_by_email_case_insensitive(email, admin_id):
            return ["Este e-mail ja esta cadastrado para este organizador."]

        camp_ids = []
        if "campeonatos_ids" in data:
            ids = data.getlist("campeonatos_ids") if hasattr(data, "getlist") else data.get("campeonatos_ids", [])
            for cid in ids:
                if cid:
                    camp_ids.append(ObjectId(cid))

        referee_document = {
            "nome": data["nome"].strip(),
            "email": email,
            "contato": data.get("contato", "").strip(),
            "disponibilidade": data["disponibilidade"].strip(),
            "admin_id": admin_id,
            "campeonatos_vinculados": camp_ids,
            "criado_em": utc_now_naive(),
        }
        referee_id = self.arbitro_repo.insert(referee_document)
        
        self.user_repo.insert(
            {
                "nome": data["nome"].strip(),
                "login": login,
                "senha_hash": self.password_hasher.hash(data["senha"]),
                "role": ROLE_REFEREE,
                "admin_id": admin_id,
                "referee_id": referee_id,
                "ativo": True,
                "must_change_password": False,
                "criado_em": utc_now_naive(),
            }
        )
        return []

    def get_referee_details(self, current_user: dict[str, Any], object_id):
        referee = self.arbitro_repo.find_by_id(object_id)
        if not referee or not can_access_admin_scope(current_user, referee.get("admin_id")):
            return None, None
        user = self.user_repo.collection.find_one({"referee_id": object_id})
        return referee, user

    def update_referee(self, current_user: dict[str, Any], object_id, data: dict[str, Any]) -> list[str]:
        referee = self.arbitro_repo.find_by_id(object_id)
        if not referee or not can_access_admin_scope(current_user, referee.get("admin_id")):
            return ["Arbitro nao encontrado."]

        errors = self.validate(data, creating=False)
        if errors:
            return errors
            
        email = data["email"].strip()
        admin_id = referee.get("admin_id")
        
        existing = self.arbitro_repo.find_by_email_case_insensitive(email, admin_id)
        if existing and existing["_id"] != object_id:
            return ["Este e-mail ja esta cadastrado para este organizador."]

        camp_ids = []
        if "campeonatos_ids" in data:
            ids = data.getlist("campeonatos_ids") if hasattr(data, "getlist") else data.get("campeonatos_ids", [])
            for cid in ids:
                if cid:
                    camp_ids.append(ObjectId(cid))

        update = {
            "nome": data["nome"].strip(),
            "email": email,
            "contato": data.get("contato", "").strip(),
            "disponibilidade": data["disponibilidade"].strip(),
            "campeonatos_vinculados": camp_ids,
        }
        self.arbitro_repo.update_fields(object_id, update)
        self.user_repo.collection.update_one({"referee_id": object_id}, {"$set": {"nome": data["nome"].strip()}})
        return []

    def delete_referee(self, current_user: dict[str, Any], object_id) -> bool:
        referee = self.arbitro_repo.find_by_id(object_id)
        if not referee or not can_access_admin_scope(current_user, referee.get("admin_id")):
            return False
        deleted = self.arbitro_repo.delete_by_id(object_id)
        if deleted:
            self.user_repo.collection.delete_many({"referee_id": object_id})
        return deleted


class NotificationService:
    UPCOMING_ALERT_TYPE = "match_start_1h"

    def __init__(self, notification_repo, user_repo, player_repo, team_repo, championship_repo, match_repo):
        self.notification_repo = notification_repo
        self.user_repo = user_repo
        self.player_repo = player_repo
        self.team_repo = team_repo
        self.championship_repo = championship_repo
        self.match_repo = match_repo

    def _notification_exists(self, user_id, match_id) -> bool:
        return self.notification_repo.collection.count_documents(
            {
                "user_id": user_id,
                "tipo": self.UPCOMING_ALERT_TYPE,
                "partida_id": match_id,
            }
        ) > 0

    def _match_game(self, match: dict[str, Any], championship_cache: dict[ObjectId, dict[str, Any]]) -> str:
        if match.get("jogo"):
            return match["jogo"]
        championship_id = match.get("campeonato_id")
        if championship_id not in championship_cache:
            championship_cache[championship_id] = self.championship_repo.find_by_id(championship_id) or {}
        return championship_cache[championship_id].get("jogo", "")

    def _match_team_ids(self, match: dict[str, Any]) -> set[ObjectId]:
        team_ids = set()
        time_a = (match.get("time_a") or {}).get("time_id")
        time_b = (match.get("time_b") or {}).get("time_id")
        if time_a:
            team_ids.add(time_a)
        if time_b:
            team_ids.add(time_b)
        return team_ids

    def _build_match_alert_message(self, match: dict[str, Any], game: str, team_name: str | None = None) -> str:
        inicio = match.get("data_partida")
        horario = inicio.strftime("%H:%M") if inicio else "--:--"
        if team_name:
            opponent = match["time_b"]["nome"] if team_name == match["time_a"]["nome"] else match["time_a"]["nome"]
            return f"[{game}] O seu time {team_name} enfrenta {opponent} as {horario}."
        return f"[{game}] A partida {match['time_a']['nome']} x {match['time_b']['nome']} comeca as {horario}."

    def _match_starts_within_one_hour(self, match: dict[str, Any]) -> bool:
        start = match.get("data_partida")
        if not start:
            return False
        now_candidates = (local_now_naive(), utc_now_naive())
        return any(now <= start <= (now + timedelta(hours=1)) for now in now_candidates)

    def ensure_upcoming_match_notifications(self, current_user: dict[str, Any] | None) -> None:
        if not current_user:
            return

        role = current_user.get("role")
        if role not in (ROLE_ADMIN, ROLE_PLAYER):
            return

        match_filter = {"status": "agendada"}
        if role == ROLE_ADMIN:
            admin_id = get_scope_admin_id(current_user)
            if admin_id:
                match_filter["admin_id"] = admin_id
            users_to_notify = [{"user_id": current_user["_id"], "team_id": None}]
        else:
            user = self.user_repo.find_by_id(current_user["_id"])
            if not user or not user.get("player_id"):
                return
            player = self.player_repo.find_by_id(user["player_id"])
            if not player:
                return
            team = self.team_repo.find_by_player_id(player["_id"])
            if not team:
                return
            admin_id = user.get("admin_id")
            if admin_id:
                match_filter["admin_id"] = admin_id
            users_to_notify = [{"user_id": current_user["_id"], "team_id": team["_id"]}]

        championship_cache: dict[ObjectId, dict[str, Any]] = {}
        matches = self.match_repo.list_by_query(match_filter, sort=[("data_partida", 1)])
        for match in matches:
            match_id = match.get("_id")
            if not match_id:
                continue
            if not self._match_starts_within_one_hour(match):
                continue
            game = self._match_game(match, championship_cache)
            match_team_ids = self._match_team_ids(match)
            for target in users_to_notify:
                user_id = target["user_id"]
                team_id = target["team_id"]
                if team_id and team_id not in match_team_ids:
                    continue
                team_name = None
                if team_id:
                    team_name = match["time_a"]["nome"] if match["time_a"]["time_id"] == team_id else match["time_b"]["nome"]
                message = self._build_match_alert_message(match, game or "Jogo", team_name=team_name)
                existing = self.notification_repo.collection.find_one(
                    {
                        "user_id": user_id,
                        "tipo": self.UPCOMING_ALERT_TYPE,
                        "partida_id": match_id,
                    }
                )
                if existing:
                    if existing.get("mensagem") != message or existing.get("jogo") != game:
                        self.notification_repo.collection.update_one(
                            {"_id": existing["_id"]},
                            {
                                "$set": {
                                    "mensagem": message,
                                    "jogo": game,
                                    "link": f"/campeonatos/{match['campeonato_id']}",
                                    "criado_em": local_now_naive(),
                                }
                            },
                        )
                    continue
                self.notification_repo.insert(
                    {
                        "user_id": user_id,
                        "mensagem": message,
                        "jogo": game,
                        "tipo": self.UPCOMING_ALERT_TYPE,
                        "partida_id": match_id,
                        "campeonato_id": match.get("campeonato_id"),
                        "lida": False,
                        "link": f"/campeonatos/{match['campeonato_id']}",
                        "criado_em": local_now_naive(),
                    }
                )

    def list_notifications(self, current_user: dict[str, Any], limit: int = 50, unread_only: bool = False) -> list[dict[str, Any]]:
        return self.notification_repo.list_by_user(current_user["_id"], limit, unread_only=unread_only)

    def count_unread(self, current_user: dict[str, Any]) -> int:
        if not current_user:
            return 0
        return self.notification_repo.count_unread(current_user["_id"])

    def mark_as_read(self, current_user: dict[str, Any], object_id) -> bool:
        self.notification_repo.mark_as_read(ObjectId(object_id))
        return True

    def mark_all_as_read(self, current_user: dict[str, Any]) -> bool:
        self.notification_repo.mark_all_as_read(current_user["_id"])
        return True


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
            repositories["logs"],
        ),
        "users": UserService(repositories["users"], password_hasher),
        "player_profile": PlayerProfileService(
            repositories["users"],
            repositories["players"],
            repositories["teams"],
            repositories["championships"],
        ),
        "arbitros": ArbitroService(repositories["arbitros"], repositories["users"], password_hasher),
        "notifications": NotificationService(
            repositories["notifications"],
            repositories["users"],
            repositories["players"],
            repositories["teams"],
            repositories["championships"],
            repositories["matches"],
        ),
    }
