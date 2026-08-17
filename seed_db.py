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
        "nome": "Plataforma FPS Arena",
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

# For each admin, populate 8 teams (4 CS2, 4 Valorant) and 4 running championships (2 CS2, 2 Valorant)
for adm_id, suffix_name, suffix_login in admin_configs:
    cs2_team_ids = []
    val_team_ids = []
    
    # 8 Teams
    for t_idx in range(1, 9):
        is_cs2 = (t_idx <= 4)
        jogo = "CS2" if is_cs2 else "Valorant"
        tag = f"{suffix_login[:2].upper()}{t_idx}"
        team_name = f"Time {t_idx} ({suffix_name})"
        
        team_id = db.times.insert_one(
            {
                "nome": team_name,
                "tag": tag,
                "jogo": jogo,
                "admin_id": adm_id,
                "jogadores": [],
                "criado_em": utc_now(),
            }
        ).inserted_id
        
        if is_cs2:
            cs2_team_ids.append(team_id)
        else:
            val_team_ids.append(team_id)
            
        # 5 Players per Team
        team_players = []
        for p_idx in range(1, 6):
            p_nick = f"Pl{p_idx}T{t_idx}{suffix_login.upper()}"
            p_name = f"Jogador {p_idx} Time {t_idx} ({suffix_name})"
            p_login = f"p{p_idx}t{t_idx}{suffix_login}"
            
            player_doc = {
                "nick": p_nick,
                "nome": p_name,
                "nome_real": p_name,
                "login": p_login,
                "contato": f"{p_login}@arena.com",
                "jogo_principal": jogo,
                "admin_id": adm_id,
                "time_id": team_id,
                "campeonato_id": None,
                "estatisticas": {"partidas_jogadas": 0, "vitorias": 0, "derrotas": 0, "kd_ratio": 1.0},
                "criado_em": utc_now(),
            }
            if is_cs2:
                player_doc["premier_rating"] = 12000 + (t_idx * 800) + (p_idx * 150)
            else:
                player_doc["rank_ato"] = "Diamond 3"
                
            p_id = db.jogadores.insert_one(player_doc).inserted_id
            team_players.append({"jogador_id": p_id, "nick": p_nick, "funcao": "Capitão" if p_idx == 1 else "Jogador"})
            

        db.times.update_one({"_id": team_id}, {"$set": {"jogadores": team_players}})

    # 4 Running Championships (2 CS2, 2 Valorant)
    # CS2 Championships
    for c_idx in range(1, 3):
        db.campeonatos.insert_one(
            {
                "nome": f"Copa CS2 Act {c_idx} ({suffix_name})",
                "jogo": "CS2",
                "formato": "mata-mata",
                "max_times": 8,
                "premiacao": {"1_lugar": f"R$ {c_idx * 1000},00", "2_lugar": "R$ 400,00", "3_lugar": "R$ 100,00"},
                "datas": {"inicio": hoje + timedelta(days=1), "fim": hoje + timedelta(days=15)},
                "status": "EM_ANDAMENTO",
                "admin_id": adm_id,
                "times_inscritos": cs2_team_ids,
                "criado_por": adm_id,
                "criado_em": hoje - timedelta(days=4),
            }
        )
    # Valorant Championships
    for c_idx in range(1, 3):
        db.campeonatos.insert_one(
            {
                "nome": f"Série Val Act {c_idx} ({suffix_name})",
                "jogo": "Valorant",
                "formato": "grupos",
                "max_times": 8,
                "premiacao": {"1_lugar": f"R$ {c_idx * 900},00", "2_lugar": "R$ 300,00", "3_lugar": "R$ 50,00"},
                "datas": {"inicio": hoje + timedelta(days=2), "fim": hoje + timedelta(days=20)},
                "status": "EM_ANDAMENTO",
                "admin_id": adm_id,
                "times_inscritos": val_team_ids,
                "criado_por": adm_id,
                "criado_em": hoje - timedelta(days=3),
            }
        )

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
