from __future__ import annotations

from datetime import UTC, datetime

import bcrypt


STATUS_MAP = {
    "aberto": "INSCRICAO",
    "em_andamento": "EM_ANDAMENTO",
    "finalizado": "FINALIZADO",
}

ROLE_MAP = {
    "admin": "ADMIN",
    "operador": "PLAYER",
}


def migrate_legacy_data(mongo):
    existing_superadmin = mongo.users.find_one(
        {"$or": [{"role": "SUPER_ADMIN"}, {"login": "superadmin"}, {"username": "superadmin"}]}
    )
    if not existing_superadmin:
        mongo.users.insert_one(
            {
                "nome": "Super Admin",
                "login": "superadmin",
                "senha_hash": bcrypt.hashpw(b"super123", bcrypt.gensalt()),
                "role": "SUPER_ADMIN",
                "ativo": True,
                "must_change_password": False,
                "criado_em": datetime.now(UTC).replace(tzinfo=None),
            }
        )

    admin_ids = []
    for user in mongo.users.find():
        updates = {}
        role = user.get("role") or ROLE_MAP.get(user.get("perfil"))
        if role:
            updates["role"] = role
        if not user.get("login") and user.get("username"):
            updates["login"] = user["username"]
        if not user.get("nome"):
            updates["nome"] = user.get("nome_completo") or user.get("username") or user.get("login")
        if "ativo" not in user:
            updates["ativo"] = True
        if "must_change_password" not in user:
            updates["must_change_password"] = False
        if "criado_em" not in user:
            updates["criado_em"] = datetime.now(UTC).replace(tzinfo=None)
        if role == "PLAYER" and "admin_id" not in user:
            updates["admin_id"] = None
        if role == "ADMIN":
            admin_ids.append(user["_id"])
        if updates:
            mongo.users.update_one({"_id": user["_id"]}, {"$set": updates})

    admin_ids = [user["_id"] for user in mongo.users.find({"role": "ADMIN"})]
    default_admin_id = admin_ids[0] if admin_ids else None

    for user in mongo.users.find({"role": "PLAYER"}):
        if user.get("admin_id"):
            continue
        mongo.users.update_one({"_id": user["_id"]}, {"$set": {"admin_id": default_admin_id}})

    for player in mongo.players.find():
        updates = {}
        if not player.get("nome") and player.get("nome_real"):
            updates["nome"] = player["nome_real"]
        if "admin_id" not in player and default_admin_id:
            updates["admin_id"] = default_admin_id
        if updates:
            mongo.players.update_one({"_id": player["_id"]}, {"$set": updates})

    for team in mongo.teams.find():
        if team.get("admin_id"):
            continue
        inferred_admin_id = default_admin_id
        for member in team.get("jogadores", []):
            player = mongo.players.find_one({"_id": member.get("jogador_id")})
            if player and player.get("admin_id"):
                inferred_admin_id = player["admin_id"]
                break
        if inferred_admin_id:
            mongo.teams.update_one({"_id": team["_id"]}, {"$set": {"admin_id": inferred_admin_id}})

    for championship in mongo.championships.find():
        updates = {}
        if not championship.get("admin_id"):
            updates["admin_id"] = championship.get("criado_por") or default_admin_id
        status = championship.get("status")
        updates["status"] = STATUS_MAP.get(status, status or "INSCRICAO")
        if updates:
            mongo.championships.update_one({"_id": championship["_id"]}, {"$set": updates})

    for match in mongo.matches.find():
        if match.get("admin_id"):
            continue
        championship = mongo.championships.find_one({"_id": match.get("campeonato_id")})
        if championship and championship.get("admin_id"):
            mongo.matches.update_one({"_id": match["_id"]}, {"$set": {"admin_id": championship["admin_id"]}})
