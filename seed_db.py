from datetime import UTC, datetime, timedelta
from uuid import uuid4

import bcrypt
from pymongo import MongoClient


client = MongoClient("mongodb://localhost:27017/")
db = client["fps_arena"]


def utc_now():
    return datetime.now(UTC)

for col in ["usuarios", "jogadores", "times", "campeonatos", "partidas"]:
    db[col].drop()

print("Banco limpo.")

super_admin_id = db.usuarios.insert_one(
    {
        "nome": "Plataforma FPS Arena",
        "login": "superadmin",
        "senha_hash": bcrypt.hashpw(b"super123", bcrypt.gensalt()),
        "role": "SUPER_ADMIN",
        "ativo": True,
        "must_change_password": False,
        "criado_em": utc_now(),
    }
).inserted_id

admin_initial_password = "admin123"
admin_access_code = str(uuid4())
admin_id = db.usuarios.insert_one(
    {
        "nome": "Organizador Demo",
        "login": "arena.demo",
        "nome_empresa": "Arena Demo",
        "access_code": admin_access_code,
        "access_code_expires_at": utc_now() + timedelta(days=30),
        "senha_hash": bcrypt.hashpw(admin_initial_password.encode(), bcrypt.gensalt()),
        "role": "ADMIN",
        "ativo": True,
        "must_change_password": True,
        "criado_em": utc_now(),
    }
).inserted_id

jogadores = [
    {"nick": "SnipeKing99", "nome": "Carlos Melo", "login": "carlos_snipe", "senha": "jogador1", "jogo_principal": "CS2", "rank_competitivo": "Master Guardian Elite", "premier_rating": 12450},
    {"nick": "BombDefuser", "nome": "Pedro Alves", "login": "pedro_entry", "senha": "jogador2", "jogo_principal": "CS2", "rank_competitivo": "Legendary Eagle", "premier_rating": 15200},
    {"nick": "SmokeWall", "nome": "Lucas Ferreira", "login": "lucas_support", "senha": "jogador5", "jogo_principal": "CS2", "rank_competitivo": "Supreme Master First Class", "premier_rating": 18900},
    {"nick": "AWPer7", "nome": "Thiago Costa", "login": "thiago_awp", "senha": "jogador6", "jogo_principal": "CS2", "rank_competitivo": "Global Elite", "premier_rating": 24100},
    {"nick": "FlashPoint", "nome": "Ana Souza", "login": "ana_flash", "senha": "jogador3", "jogo_principal": "Valorant", "rank_ato": "Diamond 2", "agente_principal": "Jett"},
    {"nick": "PhoenixUp", "nome": "Mariana Lima", "login": "mariana_duelist", "senha": "jogador4", "jogo_principal": "Valorant", "rank_ato": "Immortal 1", "agente_principal": "Phoenix"},
]

player_ids = []
for jogador in jogadores:
    player_doc = {
        "nick": jogador["nick"],
        "nome": jogador["nome"],
        "nome_real": jogador["nome"],
        "login": jogador["login"],
        "contato": "",
        "jogo_principal": jogador["jogo_principal"],
        "admin_id": admin_id,
        "campeonato_id": None,
        "estatisticas": {"partidas_jogadas": 0, "vitorias": 0, "derrotas": 0, "kd_ratio": 1.0},
        "criado_em": utc_now(),
    }
    if jogador["jogo_principal"] == "CS2":
        player_doc["rank_competitivo"] = jogador["rank_competitivo"]
        player_doc["premier_rating"] = jogador["premier_rating"]
    else:
        player_doc["rank_ato"] = jogador["rank_ato"]
        player_doc["agente_principal"] = jogador["agente_principal"]
    player_id = db.jogadores.insert_one(player_doc).inserted_id
    player_ids.append(player_id)

    db.usuarios.insert_one(
        {
            "nome": jogador["nome"],
            "login": jogador["login"],
            "senha_hash": bcrypt.hashpw(jogador["senha"].encode(), bcrypt.gensalt()),
            "role": "PLAYER",
            "admin_id": admin_id,
            "player_id": player_id,
            "ativo": True,
            "must_change_password": False,
            "criado_em": utc_now(),
        }
    )

time_cs = db.times.insert_one(
    {
        "nome": "Shadow Squad",
        "tag": "SHD",
        "jogo": "CS2",
        "admin_id": admin_id,
        "jogadores": [
            {"jogador_id": player_ids[0], "nick": "SnipeKing99", "funcao": "IGL"},
            {"jogador_id": player_ids[1], "nick": "BombDefuser", "funcao": "Entry"},
        ],
        "criado_em": utc_now(),
    }
).inserted_id

time_cs_2 = db.times.insert_one(
    {
        "nome": "Void Hunters",
        "tag": "VHT",
        "jogo": "CS2",
        "admin_id": admin_id,
        "jogadores": [
            {"jogador_id": player_ids[2], "nick": "SmokeWall", "funcao": "Support"},
            {"jogador_id": player_ids[3], "nick": "AWPer7", "funcao": "AWPer"},
        ],
        "criado_em": utc_now(),
    }
).inserted_id

time_val = db.times.insert_one(
    {
        "nome": "Nova Esports",
        "tag": "NVE",
        "jogo": "Valorant",
        "admin_id": admin_id,
        "jogadores": [
            {"jogador_id": player_ids[4], "nick": "FlashPoint", "funcao": "Duelist"},
            {"jogador_id": player_ids[5], "nick": "PhoenixUp", "funcao": "Duelist"},
        ],
        "criado_em": utc_now(),
    }
).inserted_id

for pid, team_id in [
    (player_ids[0], time_cs),
    (player_ids[1], time_cs),
    (player_ids[2], time_cs_2),
    (player_ids[3], time_cs_2),
    (player_ids[4], time_val),
    (player_ids[5], time_val),
]:
    db.jogadores.update_one({"_id": pid}, {"$set": {"time_id": team_id}})

hoje = utc_now()
camp_cs = db.campeonatos.insert_one(
    {
        "nome": "FPS Arena Cup CS2",
        "jogo": "CS2",
        "formato": "mata-mata",
        "max_times": 8,
        "premiacao": {"1_lugar": "R$ 2.000,00", "2_lugar": "R$ 800,00", "3_lugar": "R$ 300,00"},
        "datas": {"inicio": hoje - timedelta(days=2), "fim": hoje + timedelta(days=15)},
        "status": "EM_ANDAMENTO",
        "admin_id": admin_id,
        "times_inscritos": [time_cs, time_cs_2],
        "criado_por": admin_id,
        "criado_em": hoje - timedelta(days=5),
    }
).inserted_id

camp_val = db.campeonatos.insert_one(
    {
        "nome": "FPS Arena Open Valorant",
        "jogo": "Valorant",
        "formato": "grupos",
        "max_times": 8,
        "premiacao": {"1_lugar": "R$ 1.500,00", "2_lugar": "R$ 600,00", "3_lugar": "R$ 200,00"},
        "datas": {"inicio": hoje + timedelta(days=5), "fim": hoje + timedelta(days=35)},
        "status": "INSCRICAO",
        "admin_id": admin_id,
        "times_inscritos": [time_val],
        "criado_por": admin_id,
        "criado_em": hoje - timedelta(days=1),
    }
).inserted_id

db.jogadores.update_many({"_id": {"$in": [player_ids[4], player_ids[5]]}}, {"$set": {"campeonato_id": camp_val}})

db.partidas.insert_one(
    {
        "admin_id": admin_id,
        "campeonato_id": camp_cs,
        "fase": "Semifinal",
        "time_a": {"time_id": time_cs, "nome": "Shadow Squad", "placar": 13},
        "time_b": {"time_id": time_cs_2, "nome": "Void Hunters", "placar": 7},
        "vencedor_id": time_cs,
        "mapa": "Dust2",
        "data_partida": hoje - timedelta(days=1),
        "status": "finalizada",
    }
)

print("Seed concluido.")
print()
print("Perfis base criados:")
print("1. SUPER_ADMIN")
print("   login: superadmin")
print("   senha: super123")
print()
print("2. ADMIN")
print("   login normal: arena.demo")
print(f"   senha inicial: {admin_initial_password}")
print(f"   codigo de primeiro acesso: {admin_access_code}")
print()
print("3. PLAYER")
print("   login: carlos_snipe")
print("   senha: jogador1")
