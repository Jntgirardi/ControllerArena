from pymongo import DESCENDING, MongoClient
from pymongo.errors import ServerSelectionTimeoutError


class MongoDatabase:
    def __init__(self, uri: str, db_name: str):
        self.client = MongoClient(uri, serverSelectionTimeoutMS=3000)

        try:
            self.client.admin.command("ping")
        except ServerSelectionTimeoutError as exc:
            raise RuntimeError(
                "Nao foi possivel conectar ao MongoDB. Verifique se o servico esta em execucao "
                f"e se a URI '{uri}' esta correta."
            ) from exc

        self.db = self.client[db_name]

        self.users = self.db["usuarios"]
        self.players = self.db["jogadores"]
        self.teams = self.db["times"]
        self.championships = self.db["campeonatos"]
        self.matches = self.db["partidas"]

    def _ensure_index(self, collection, keys, name: str, **options):
        existing = collection.index_information().get(name)
        normalized_keys = keys if isinstance(keys, list) else [(keys, 1)]

        if existing:
            existing_keys = existing.get("key")
            existing_unique = bool(existing.get("unique", False))
            existing_sparse = bool(existing.get("sparse", False))
            wanted_unique = bool(options.get("unique", False))
            wanted_sparse = bool(options.get("sparse", False))

            if (
                existing_keys != normalized_keys
                or existing_unique != wanted_unique
                or existing_sparse != wanted_sparse
            ):
                collection.drop_index(name)

        collection.create_index(keys, name=name, **options)

    def ensure_indexes(self):
        # usuarios
        self._ensure_index(self.users, "username", "username_1", unique=True, sparse=True)
        self._ensure_index(self.users, "login", "login_1", unique=True, sparse=True)
        self._ensure_index(self.users, "role", "role_1")
        self._ensure_index(self.users, "admin_id", "admin_id_1")
        self._ensure_index(self.users, "access_code", "access_code_1", unique=True, sparse=True)

        # jogadores
        self._ensure_index(self.players, "nick", "nick_1")
        self._ensure_index(self.players, "login", "login_1", unique=True, sparse=True)
        self._ensure_index(self.players, "admin_id", "admin_id_1")
        self._ensure_index(self.players, "jogo_principal", "jogo_principal_1")
        self._ensure_index(self.players, [("estatisticas.vitorias", DESCENDING)], "estatisticas.vitorias_-1")

        # times
        self._ensure_index(self.teams, "admin_id", "admin_id_1")
        self._ensure_index(self.teams, "jogo", "jogo_1")

        # campeonatos
        self._ensure_index(self.championships, "admin_id", "admin_id_1")
        self._ensure_index(self.championships, "status", "status_1")
        self._ensure_index(self.championships, "jogo", "jogo_1")
        self._ensure_index(self.championships, [("datas.inicio", DESCENDING)], "datas.inicio_-1")

        # partidas
        self._ensure_index(self.matches, "admin_id", "admin_id_1")
        self._ensure_index(self.matches, "campeonato_id", "campeonato_id_1")
