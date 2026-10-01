from datetime import UTC, datetime, timedelta
import os
from uuid import uuid4

import bcrypt
from pymongo import MongoClient


mongo_uri = os.environ.get("MONGO_URI", "mongodb://localhost:27017/")
mongo_db_name = os.environ.get("MONGO_DB_NAME", "fps_arena")

client = MongoClient(mongo_uri)
db = client[mongo_db_name]


def utc_now():
    return datetime.now(UTC)

# Clean all collections
for col in ["usuarios", "jogadores", "times", "campeonatos", "partidas", "eventos", "logs", "notificacoes"]:
    db[col].drop()

print("Banco limpo para reinício da semeadura.")

# 1. Super Admin
super_admin_id = db.usuarios.insert_one(
    {
        "nome": "Plataforma Controller Arena",
        "login": "superadmin",
        "senha_hash": bcrypt.hashpw(b"super123", bcrypt.gensalt()),
        "role": "SUPER_ADMIN",
        "ativo": True,
        "must_change_password": False,
        "criado_em": utc_now(),
    }
).inserted_id

# 2. Main Admin (Organizador Demo - arena.demo)
# Populated with 4 running championships, 8 teams, 5 players each
demo_admin_id = db.usuarios.insert_one(
    {
        "nome": "Organizador Demo",
        "login": "arena.demo",
        "nome_empresa": "Arena Demo",
        "access_code": str(uuid4()),
        "access_code_expires_at": utc_now() + timedelta(days=30),
        "senha_hash": bcrypt.hashpw(b"admin123", bcrypt.gensalt()),
        "role": "ADMIN",
        "ativo": True,
        "must_change_password": False,
        "criado_em": utc_now(),
    }
).inserted_id

# 3. Two Additional Admin Accounts (admin.two, admin.three)
extra_admins = [
    ("Organizador Alpha", "admin.one", "admin123"),
    ("Organizador Beta", "admin.two", "admin123"),
    ("Organizador Gamma", "admin.three", "admin123")
]

# We will loop over 3 admin accounts to populate each with 4 running championships and at least 8 teams with 5 players
all_admins = [demo_admin_id]
admin_configs = [
    (demo_admin_id, "Demo", "demo"),
]

for name, login, pwd in extra_admins:
    adm_id = db.usuarios.insert_one(
        {
            "nome": name,
            "login": login,
            "senha_hash": bcrypt.hashpw(pwd.encode(), bcrypt.gensalt()),
            "role": "ADMIN",
            "ativo": True,
            "must_change_password": False,
            "criado_em": utc_now(),
        }
    ).inserted_id
    all_admins.append(adm_id)
    admin_configs.append((adm_id, name.split()[-1], login.replace(".", "")))

hoje = utc_now()

# 14 Equipes de Valorant com exatamente 5 jogadores cada
# Campeonatos iniciam zerados (vazios)
valorant_teams_data = [
    ("LOUD FINC", "LOU"),
    ("FURIA Esports", "FUR"),
    ("Sentinels FINC", "SEN"),
    ("FNATIC Academy", "FNC"),
    ("Paper Rex Academic", "PRX"),
    ("KRÜ Esports", "KRU"),
    ("Leviatán Academy", "LEV"),
    ("Team Liquid FINC", "TLQ"),
    ("Cloud9 Academic", "C9A"),
    ("NRG Esports", "NRG"),
    ("DRX FINC", "DRX"),
    ("Gen.G Academic", "GEN"),
    ("Team Vitality", "VIT"),
    ("Karmine Corp FINC", "KC"),
]

cursos_finc = [
    "Engenharia de Software",
    "Ciência da Computação",
    "Sistemas de Informação",
    "Engenharia da Computação",
    "Análise e Desenv. de Sistemas",
]
agentes_val = ["Jett", "Omen", "Sova", "Killjoy", "Cypher"]
ranks_val = ["Radiant", "Imortal 3", "Imortal 2", "Ascendente 3", "Ascendente 2", "Diamante 3"]

for adm_id in all_admins:
    for t_idx, (t_nome, t_tag) in enumerate(valorant_teams_data, start=1):
        team_id = db.times.insert_one(
            {
                "nome": t_nome,
                "tag": t_tag,
                "jogo": "Valorant",
                "admin_id": adm_id,
                "jogadores": [],
                "criado_em": utc_now(),
            }
        ).inserted_id

        team_players = []
        for p_idx in range(1, 6):
            funcao = "Capitão" if p_idx == 1 else "Jogador"
            p_nick = f"{t_tag}_{'Cap' if p_idx == 1 else 'P' + str(p_idx)}"
            p_name = f"Atleta {p_idx} ({t_nome})"
            p_login = f"val_t{t_idx}_p{p_idx}_{str(adm_id)[-4:]}"
            curso = cursos_finc[(t_idx + p_idx) % len(cursos_finc)]
            agente = agentes_val[(p_idx - 1) % len(agentes_val)]
            rank = ranks_val[(t_idx + p_idx) % len(ranks_val)]

            player_doc = {
                "nick": p_nick,
                "nome": p_name,
                "nome_real": p_name,
                "login": p_login,
                "contato": f"{p_login}@finc.edu.br",
                "jogo_principal": "Valorant",
                "admin_id": adm_id,
                "time_id": team_id,
                "campeonato_id": None,
                "matricula": f"2024{t_idx:02d}{p_idx:02d}",
                "curso": curso,
                "ingresso_finc": "2024.1",
                "data_nascimento": "2003-04-15",
                "rank_ato": rank,
                "agente_principal": agente,
                "estatisticas": {"partidas_jogadas": 0, "vitorias": 0, "derrotas": 0, "kd_ratio": 1.0},
                "criado_em": utc_now(),
            }
            p_id = db.jogadores.insert_one(player_doc).inserted_id
            team_players.append({"jogador_id": p_id, "nick": p_nick, "funcao": funcao})

        db.times.update_one({"_id": team_id}, {"$set": {"jogadores": team_players}})

# Create mock audit logs and events for the demo admin
db.eventos.insert_one(
    {
        "nome": "Arena Music Clash",
        "local": "Arena Demo Stage",
        "data_evento": hoje + timedelta(days=12),
        "capacidade_total": 500,
        "admin_id": demo_admin_id,
        "criado_em": hoje,
    }
)
db.eventos.insert_one(
    {
        "nome": "Valorant Fan Fest",
        "local": "Expo Center",
        "data_evento": hoje + timedelta(days=25),
        "capacidade_total": 800,
        "admin_id": demo_admin_id,
        "criado_em": hoje,
    }
)

db.logs.insert_many(
    [
        {
            "user_id": demo_admin_id,
            "admin_id": demo_admin_id,
            "login": "arena.demo",
            "role": "ADMIN",
            "endpoint": "dashboard",
            "method": "GET",
            "path": "/dashboard",
            "status_code": 200,
            "created_at": hoje - timedelta(hours=3),
        },
        {
            "user_id": demo_admin_id,
            "admin_id": demo_admin_id,
            "login": "arena.demo",
            "role": "ADMIN",
            "endpoint": "relatorios",
            "method": "GET",
            "path": "/relatorios",
            "status_code": 200,
            "created_at": hoje - timedelta(hours=1),
        },
    ]
)

print("Seed de dados rico concluído com sucesso!")
