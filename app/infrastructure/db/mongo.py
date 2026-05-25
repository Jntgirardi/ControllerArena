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
        self.events = self.db["eventos"]
        self.tickets = self.db["ingressos"]
        self.logs = self.db["logs"]
        self.arbitros = self.db["arbitros"]

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
        self._ensure_index(self.users, [("criado_em", DESCENDING)], "criado_em_-1")

        # jogadores
        self._ensure_index(self.players, "nick", "nick_1")
        self._ensure_index(self.players, "login", "login_1", unique=True, sparse=True)
        self._ensure_index(self.players, "admin_id", "admin_id_1")
        self._ensure_index(self.players, "jogo_principal", "jogo_principal_1")
        self._ensure_index(self.players, [("admin_id", 1), ("nick", 1)], "admin_id_1_nick_1")
        self._ensure_index(
            self.players,
            [("estatisticas.vitorias", DESCENDING), ("estatisticas.kd_ratio", DESCENDING)],
            "estatisticas.vitorias_-1_estatisticas.kd_ratio_-1"
        )
        if "estatisticas.vitorias_-1" in self.players.index_information():
            self.players.drop_index("estatisticas.vitorias_-1")

        # times
        self._ensure_index(self.teams, "admin_id", "admin_id_1")
        self._ensure_index(self.teams, "jogo", "jogo_1")
        self._ensure_index(self.teams, "jogadores.jogador_id", "jogadores.jogador_id_1")
        self._ensure_index(self.teams, [("admin_id", 1), ("nome", 1)], "admin_id_1_nome_1")
        self._ensure_index(self.teams, [("admin_id", 1), ("jogo", 1), ("nome", 1)], "admin_id_1_jogo_1_nome_1")

        # campeonatos
        self._ensure_index(self.championships, "admin_id", "admin_id_1")
        self._ensure_index(self.championships, "status", "status_1")
        self._ensure_index(self.championships, "jogo", "jogo_1")
        self._ensure_index(self.championships, [("datas.inicio", DESCENDING)], "datas.inicio_-1")
        self._ensure_index(self.championships, [("admin_id", 1), ("criado_em", DESCENDING)], "admin_id_1_criado_em_-1")
        self._ensure_index(self.championships, [("times_inscritos", 1), ("datas.inicio", DESCENDING)], "times_inscritos_1_datas.inicio_-1")

        # partidas
        self._ensure_index(self.matches, "admin_id", "admin_id_1")
        self._ensure_index(self.matches, "campeonato_id", "campeonato_id_1")
        self._ensure_index(self.matches, [("campeonato_id", 1), ("data_partida", 1)], "campeonato_id_1_data_partida_1")
        self._ensure_index(self.matches, [("admin_id", 1), ("data_partida", DESCENDING)], "admin_id_1_data_partida_-1")

        # eventos
        self._ensure_index(self.events, "admin_id", "admin_id_1")
        self._ensure_index(self.events, "data_evento", "data_evento_1")

        # ingressos
        self._ensure_index(self.tickets, "admin_id", "admin_id_1")
        self._ensure_index(self.tickets, "evento_id", "evento_id_1")
        self._ensure_index(self.tickets, "status", "status_1")
        self._ensure_index(self.tickets, [("admin_id", 1), ("vendido_em", DESCENDING)], "admin_id_1_vendido_em_-1")

        # logs
        self._ensure_index(self.logs, "user_id", "user_id_1")
        self._ensure_index(self.logs, "role", "role_1")
        self._ensure_index(self.logs, [("created_at", DESCENDING)], "created_at_-1")

        # arbitros
        self._ensure_index(self.arbitros, "email", "email_1", unique=True, sparse=True)
        self._ensure_index(self.arbitros, "admin_id", "admin_id_1")
