from dataclasses import dataclass, field
from datetime import datetime
from typing import Any


@dataclass
class Usuario:
    username: str
    perfil: str
    nome_completo: str = ""
    created_at: datetime | None = None


@dataclass
class Jogador:
    nick: str
    nome_real: str
    jogo_principal: str
    contato: str = ""
    email: str = ""
    data_nascimento: str = ""
    instituicao: str = ""
    curso: str = ""
    matricula: str = ""
    numero_ingresso_finc: str = ""
    estatisticas: dict[str, Any] = field(default_factory=dict)


@dataclass
class Time:
    nome: str
    tag: str
    jogo: str
    logo_path: str = ""
    jogadores: list[dict[str, Any]] = field(default_factory=list)


@dataclass
class Campeonato:
    nome: str
    jogo: str
    formato: str
    max_times: int
    status: str = "aberto"


@dataclass
class Partida:
    campeonato_id: str
    fase: str
    status: str
    arbitro_id: str | None = None
    formato_serie: str = "MD1"
    placar_serie_a: int = 0
    placar_serie_b: int = 0
    fearless_draft: bool = False
    jogos_serie: list[dict[str, Any]] = field(default_factory=list)


@dataclass
class Arbitro:
    nome: str
    email: str
    disponibilidade: str
    contato: str = ""
    campeonatos_vinculados: list[str] = field(default_factory=list)


@dataclass
class Notificacao:
    user_id: str
    mensagem: str
    lida: bool = False
    link: str = ""
    criado_em: datetime | None = None


