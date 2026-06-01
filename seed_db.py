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

print("Banco limpo.")

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

# 2. Admin (Organizador)
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

# 3. Define 10 CS2 Teams and 1 Valorant Team
teams_data = [
    {"nome": "Shadow Squad", "tag": "SHD", "jogo": "CS2", "players": [("SnipeKing99", "Carlos Melo"), ("BombDefuser", "Pedro Alves")]},
    {"nome": "Void Hunters", "tag": "VHT", "jogo": "CS2", "players": [("SmokeWall", "Lucas Ferreira"), ("AWPer7", "Thiago Costa")]},
    {"nome": "Delta Five", "tag": "D5", "jogo": "CS2", "players": [("Frost", "Felipe Diniz"), ("SmokeCS", "Gabriel Silva")]},
    {"nome": "Blue Storm", "tag": "BST", "jogo": "CS2", "players": [("Ares", "Rodrigo Santos"), ("Nero", "Matheus Oliveira")]},
    {"nome": "Red Vipers", "tag": "RVP", "jogo": "CS2", "players": [("RazeCS", "Artur Lima"), ("Kross", "Igor Souza")]},
    {"nome": "Neon Kings", "tag": "NKG", "jogo": "CS2", "players": [("Vex", "Eduardo Costa"), ("Mika", "Gustavo Ramos")]},
    {"nome": "Prime Wolves", "tag": "PWV", "jogo": "CS2", "players": [("Dante", "Bruno Santos"), ("Bolt", "Vinicius Cruz")]},
    {"nome": "Lotus Guard", "tag": "LTG", "jogo": "CS2", "players": [("Hawk", "Leonardo Melo"), ("Lux", "Daniel Ribeiro")]},
    {"nome": "Spike Rush", "tag": "SPR", "jogo": "CS2", "players": [("Core", "Alexandre Lima"), ("Icaro", "Renato Alves")]},
    {"nome": "Tech Aim", "tag": "TCA", "jogo": "CS2", "players": [("Tyn", "Rafael Dias"), ("Byte", "Diego Santos")]},
    {"nome": "Nova Esports", "tag": "NVE", "jogo": "Valorant", "players": [("FlashPoint", "Ana Souza"), ("PhoenixUp", "Mariana Lima")]},
]

team_ids = []
cs2_team_ids = []
val_team_ids = []

for t_info in teams_data:
    # First create team document with empty players
    team_doc = {
        "nome": t_info["nome"],
        "tag": t_info["tag"],
        "jogo": t_info["jogo"],
        "admin_id": admin_id,
        "jogadores": [],
        "criado_em": utc_now(),
    }
    team_id = db.times.insert_one(team_doc).inserted_id
    team_ids.append(team_id)
    if t_info["jogo"] == "CS2":
        cs2_team_ids.append(team_id)
    else:
        val_team_ids.append(team_id)

    # Now create the 2 players for this team
    team_players = []
    for idx, (nick, nome) in enumerate(t_info["players"]):
        login = f"{nick.lower()}_demo"
        player_doc = {
            "nick": nick,
            "nome": nome,
            "nome_real": nome,
            "login": login,
            "contato": f"{login}@arena.com",
            "jogo_principal": t_info["jogo"],
            "admin_id": admin_id,
            "time_id": team_id,
            "campeonato_id": None,
            "estatisticas": {"partidas_jogadas": 0, "vitorias": 0, "derrotas": 0, "kd_ratio": 1.0},
            "criado_em": utc_now(),
        }
        if t_info["jogo"] == "CS2":
            player_doc["rank_competitivo"] = "Legendary Eagle" if idx == 0 else "Master Guardian"
            player_doc["premier_rating"] = 15000 + (len(team_ids) * 200)
        else:
            player_doc["rank_ato"] = "Diamond 2"
            player_doc["agente_principal"] = "Jett" if idx == 0 else "Sova"

        player_id = db.jogadores.insert_one(player_doc).inserted_id
        team_players.append({"jogador_id": player_id, "nick": nick, "funcao": "Capitão" if idx == 0 else "Jogador"})

        # Create user account for player
        db.usuarios.insert_one(
            {
                "nome": nome,
                "login": login,
                "senha_hash": bcrypt.hashpw(b"jogador123", bcrypt.gensalt()),
                "role": "PLAYER",
                "admin_id": admin_id,
                "player_id": player_id,
                "ativo": True,
                "must_change_password": False,
                "criado_em": utc_now(),
            }
        )
    
    # Update team with player members list
    db.times.update_one({"_id": team_id}, {"$set": {"jogadores": team_players}})

# 4. Championships
hoje = utc_now()

# CS2 Championship (Mata-Mata) in INSCRICAO phase with exactly 8 teams enrolled (perfect power of 2 for testing)
# The other 2 CS2 teams are left uninscribed so the user can test adding them or keeping it at 8 for perfect Mata-Mata!
camp_cs = db.campeonatos.insert_one(
    {
        "nome": "FPS Arena Cup CS2",
        "jogo": "CS2",
        "formato": "mata-mata",
        "max_times": 16,
        "premiacao": {"1_lugar": "R$ 3.000,00", "2_lugar": "R$ 1.000,00", "3_lugar": "R$ 500,00"},
        "datas": {"inicio": hoje + timedelta(days=2), "fim": hoje + timedelta(days=15)},
        "status": "INSCRICAO",
        "admin_id": admin_id,
        "times_inscritos": cs2_team_ids[:8],  # First 8 teams enrolled
        "criado_por": admin_id,
        "criado_em": hoje - timedelta(days=5),
    }
).inserted_id

# Valorant Championship in INSCRICAO phase
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
        "times_inscritos": val_team_ids,
        "criado_por": admin_id,
        "criado_em": hoje - timedelta(days=1),
    }
).inserted_id

# 5. Events
evento_show = db.eventos.insert_one(
    {
        "nome": "Arena Music Clash",
        "local": "Arena Demo Stage",
        "data_evento": hoje + timedelta(days=12),
        "capacidade_total": 500,
        "admin_id": admin_id,
        "criado_em": hoje,
    }
).inserted_id

evento_festival = db.eventos.insert_one(
    {
        "nome": "Valorant Fan Fest",
        "local": "Expo Center",
        "data_evento": hoje + timedelta(days=25),
        "capacidade_total": 800,
        "admin_id": admin_id,
        "criado_em": hoje,
    }
).inserted_id

# 7. Audit Logs
db.logs.insert_many(
    [
        {
            "user_id": admin_id,
            "admin_id": admin_id,
            "login": "arena.demo",
            "role": "ADMIN",
            "endpoint": "dashboard",
            "method": "GET",
            "path": "/dashboard",
            "status_code": 200,
            "created_at": hoje - timedelta(hours=3),
        },
        {
            "user_id": admin_id,
            "admin_id": admin_id,
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
print("   login: snipeking99_demo")
print("   senha: jogador123")
print()
print(f"Total de times CS2 criados: {len(cs2_team_ids)}")
print(f"Times CS2 inscritos por padrão no campeonato: {len(cs2_team_ids[:8])}")
print("Outros 2 times CS2 estão livres para inscrição no painel!")
