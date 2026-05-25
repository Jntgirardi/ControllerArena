from __future__ import annotations

from pymongo import DESCENDING


class MongoUserRepository:
    def __init__(self, collection):
        self.collection = collection

    def find_by_login(self, login: str):
        return self.collection.find_one({"login": login})

    def find_by_username(self, username: str):
        return self.collection.find_one({"$or": [{"login": username}, {"username": username}]})

    def find_admin_by_access_code(self, access_code: str):
        return self.collection.find_one({"access_code": access_code, "role": "ADMIN"})

    def find_by_id(self, object_id):
        return self.collection.find_one({"_id": object_id})

    def list_all(self, filtro=None, projection=None):
        filtro = filtro or {}
        projection = projection or {"senha_hash": 0}
        return list(self.collection.find(filtro, projection).sort("criado_em", DESCENDING))

    def insert(self, document):
        result = self.collection.insert_one(document)
        return result.inserted_id

    def update_fields(self, object_id, fields):
        self.collection.update_one({"_id": object_id}, {"$set": fields})

    def delete_by_id(self, object_id):
        self.collection.delete_one({"_id": object_id})

    def delete_by_player_id(self, player_id):
        self.collection.delete_one({"player_id": player_id})


class MongoPlayerRepository:
    def __init__(self, collection):
        self.collection = collection

    def count_all(self, filtro=None):
        return self.collection.count_documents(filtro or {})

    def list_filtered(self, filtro, busca: str):
        query = dict(filtro or {})
        if busca:
            query["$or"] = [
                {"nick": {"$regex": busca, "$options": "i"}},
                {"nome": {"$regex": busca, "$options": "i"}},
                {"nome_real": {"$regex": busca, "$options": "i"}},
                {"login": {"$regex": busca, "$options": "i"}},
            ]
        return list(self.collection.find(query).sort("nick", 1))

    def list_for_team_selector(self, filtro=None):
        return list(self.collection.find(filtro or {}, {"nick": 1, "jogo_principal": 1}))

    def list_ranking(self, filtro=None):
        return list(
            self.collection.find(filtro or {})
            .sort([("estatisticas.vitorias", DESCENDING), ("estatisticas.kd_ratio", DESCENDING)])
            .limit(50)
        )

    def list_by_query(self, filtro=None, projection=None, sort=None):
        cursor = self.collection.find(filtro or {}, projection)
        if sort:
            cursor = cursor.sort(sort)
        return list(cursor)

    def find_by_id(self, object_id):
        return self.collection.find_one({"_id": object_id})

    def find_by_login(self, login: str):
        return self.collection.find_one({"login": login})

    def find_by_nick_case_insensitive(self, nick: str, admin_id=None):
        filtro = {"nick": {"$regex": f"^{nick}$", "$options": "i"}}
        if admin_id:
            filtro["admin_id"] = admin_id
        return self.collection.find_one(filtro)

    def insert(self, document):
        result = self.collection.insert_one(document)
        return result.inserted_id

    def update_fields(self, object_id, fields):
        self.collection.update_one({"_id": object_id}, {"$set": fields})

    def unset_fields(self, object_id, fields):
        self.collection.update_one({"_id": object_id}, {"$unset": fields})

    def delete_by_id(self, object_id):
        result = self.collection.delete_one({"_id": object_id})
        return result.deleted_count > 0

    def set_team(self, object_id, team_id):
        self.collection.update_one({"_id": object_id}, {"$set": {"time_id": team_id}})

    def clear_team(self, object_id):
        self.collection.update_one({"_id": object_id}, {"$unset": {"time_id": ""}})

    def increment_stats(self, object_id, increment):
        self.collection.update_one({"_id": object_id}, {"$inc": increment})


class MongoTeamRepository:
    def __init__(self, collection):
        self.collection = collection

    def count_all(self, filtro=None):
        return self.collection.count_documents(filtro or {})

    def list_all(self, filtro=None):
        return list(self.collection.find(filtro or {}).sort("nome", 1))

    def list_by_game(self, jogo: str, filtro=None):
        query = dict(filtro or {})
        query["jogo"] = jogo
        return list(self.collection.find(query, {"nome": 1, "tag": 1, "jogo": 1}).sort("nome", 1))

    def list_by_ids(self, ids):
        return list(self.collection.find({"_id": {"$in": list(ids or [])}}).sort("nome", 1))

    def find_by_id(self, object_id):
        return self.collection.find_one({"_id": object_id})

    def find_by_player_id(self, player_id):
        return self.collection.find_one({"jogadores.jogador_id": player_id})

    def insert(self, document):
        result = self.collection.insert_one(document)
        return result.inserted_id

    def update_fields(self, object_id, fields):
        self.collection.update_one({"_id": object_id}, {"$set": fields})

    def delete_by_id(self, object_id):
        self.collection.delete_one({"_id": object_id})

    def remove_player_from_all_teams(self, player_id):
        self.collection.update_many({}, {"$pull": {"jogadores": {"jogador_id": player_id}}})


class MongoChampionshipRepository:
    def __init__(self, collection):
        self.collection = collection

    def count_all(self, filtro=None):
        return self.collection.count_documents(filtro or {})

    def count_by_status(self, status: str, filtro=None):
        query = dict(filtro or {})
        query["status"] = status
        return self.collection.count_documents(query)

    def list_recent(self, filtro=None, limit: int = 5):
        return list(self.collection.find(filtro or {}).sort("criado_em", DESCENDING).limit(limit))

    def list_filtered(self, filtro):
        return list(self.collection.find(filtro or {}).sort("datas.inicio", DESCENDING))

    def list_by_query(self, filtro, sort_key: str, sort_order):
        return list(self.collection.find(filtro or {}).sort(sort_key, sort_order))

    def find_by_id(self, object_id):
        return self.collection.find_one({"_id": object_id})

    def insert(self, document):
        result = self.collection.insert_one(document)
        return result.inserted_id

    def update_fields(self, object_id, fields):
        self.collection.update_one({"_id": object_id}, {"$set": fields})

    def push_team(self, championship_id, team_id):
        self.collection.update_one({"_id": championship_id}, {"$push": {"times_inscritos": team_id}})

    def pull_team(self, championship_id, team_id):
        self.collection.update_one({"_id": championship_id}, {"$pull": {"times_inscritos": team_id}})

    def delete_by_id(self, object_id):
        self.collection.delete_one({"_id": object_id})

    def list_by_team_id(self, team_id):
        return list(self.collection.find({"times_inscritos": team_id}).sort("datas.inicio", DESCENDING))


class MongoMatchRepository:
    def __init__(self, collection):
        self.collection = collection

    def count_all(self, filtro=None):
        return self.collection.count_documents(filtro or {})

    def count_by_championship(self, championship_id):
        return self.collection.count_documents({"campeonato_id": championship_id})

    def list_by_championship(self, championship_id):
        return list(self.collection.find({"campeonato_id": championship_id}).sort("data_partida", 1))

    def list_by_query(self, filtro=None, sort=None):
        cursor = self.collection.find(filtro or {})
        if sort:
            cursor = cursor.sort(sort)
        return list(cursor)

    def find_by_id(self, object_id):
        return self.collection.find_one({"_id": object_id})

    def insert(self, document):
        result = self.collection.insert_one(document)
        return result.inserted_id

    def update_fields(self, object_id, fields):
        self.collection.update_one({"_id": object_id}, {"$set": fields})

    def delete_by_championship(self, championship_id):
        self.collection.delete_many({"campeonato_id": championship_id})


class MongoEventRepository:
    def __init__(self, collection):
        self.collection = collection

    def list_by_query(self, filtro=None, sort=None):
        cursor = self.collection.find(filtro or {})
        if sort:
            cursor = cursor.sort(sort)
        return list(cursor)


class MongoTicketRepository:
    def __init__(self, collection):
        self.collection = collection

    def list_by_query(self, filtro=None, sort=None):
        cursor = self.collection.find(filtro or {})
        if sort:
            cursor = cursor.sort(sort)
        return list(cursor)


class MongoLogRepository:
    def __init__(self, collection):
        self.collection = collection

    def insert(self, document):
        result = self.collection.insert_one(document)
        return result.inserted_id

    def list_by_query(self, filtro=None, sort=None):
        cursor = self.collection.find(filtro or {})
        if sort:
            cursor = cursor.sort(sort)
        return list(cursor)


class MongoArbitroRepository:
    def __init__(self, collection):
        self.collection = collection

    def count_all(self, filtro=None):
        return self.collection.count_documents(filtro or {})

    def list_filtered(self, filtro, busca: str):
        query = dict(filtro or {})
        if busca:
            query["$or"] = [
                {"nome": {"$regex": busca, "$options": "i"}},
                {"email": {"$regex": busca, "$options": "i"}},
            ]
        return list(self.collection.find(query).sort("nome", 1))

    def find_by_id(self, object_id):
        return self.collection.find_one({"_id": object_id})

    def find_by_email_case_insensitive(self, email: str, admin_id=None):
        filtro = {"email": {"$regex": f"^{email}$", "$options": "i"}}
        if admin_id:
            filtro["admin_id"] = admin_id
        return self.collection.find_one(filtro)

    def insert(self, document):
        result = self.collection.insert_one(document)
        return result.inserted_id

    def update_fields(self, object_id, fields):
        self.collection.update_one({"_id": object_id}, {"$set": fields})

    def delete_by_id(self, object_id):
        result = self.collection.delete_one({"_id": object_id})
        return result.deleted_count > 0

