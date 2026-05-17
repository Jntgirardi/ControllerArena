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
    estatisticas: dict[str, Any] = field(default_factory=dict)


@dataclass
class Time:
    nome: str
    tag: str
    jogo: str
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
