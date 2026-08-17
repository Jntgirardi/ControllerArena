from pymongo import DESCENDING, MongoClient
from pymongo.errors import ServerSelectionTimeoutError


class MongoDatabase:
    def __init__(self, uri: str, db_name: str):
        import os
        is_mock = False
        if os.environ.get("VERCEL") == "1" or os.environ.get("FLASK_ENV") == "production" or uri.startswith("mongodb+srv://"):
            self.client = MongoClient(uri)
        else:
            try:
                self.client = MongoClient(uri, serverSelectionTimeoutMS=2000)
                self.client.admin.command("ping")
            except Exception as exc:
                import mongomock
                print("==========================================================================")
                print("MongoDB nao disponivel no host local. Utilizando banco em memoria (mongomock)!")
                print("==========================================================================")
                self.client = mongomock.MongoClient()
                is_mock = True

        self.db = self.client[db_name]

        # Inicializa o ODM MongoEngine para conformidade acadêmica completa
        import mongoengine as me
        try:
            if not is_mock:
                me.connect(db=db_name, host=uri, uuidRepresentation="standard")
            else:
                me.connect(db=db_name, mongo_client=self.client, uuidRepresentation="standard")
        except Exception as exc:
            pass

        self.users = self.db["usuarios"]
        self.players = self.db["jogadores"]
        self.teams = self.db["times"]
        self.championships = self.db["campeonatos"]
        self.matches = self.db["partidas"]
        self.events = self.db["eventos"]
        self.logs = self.db["logs"]
        self.arbitros = self.db["arbitros"]
        self.notifications = self.db["notificacoes"]

        import os
        if not os.environ.get("PYTEST_CURRENT_TEST"):
            if is_mock or self.users.count_documents({}) == 0:
                self._auto_seed()

    def _auto_seed(self):
        # Prevent seeding multiple times if it has data already
        if self.users.count_documents({}) > 0:
            return

        print("Semeando banco de dados em memoria...")
        from datetime import UTC, datetime, timedelta
        from uuid import uuid4
        import bcrypt
        
        db = self.db
        
        def utc_now():
            return datetime.now(UTC)
            
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
                        "status": "INSCRICAO",
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
                        "status": "INSCRICAO",
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
        print("Banco de dados semeado com sucesso em memoria!")

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
        self._ensure_index(self.users, "password_reset_token", "password_reset_token_1", unique=True, sparse=True)
        self._ensure_index(self.users, "password_reset_expires_at", "password_reset_expires_at_1")
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

        # logs
        self._ensure_index(self.logs, "user_id", "user_id_1")
        self._ensure_index(self.logs, "role", "role_1")
        self._ensure_index(self.logs, [("created_at", DESCENDING)], "created_at_-1")

        # arbitros
        self._ensure_index(self.arbitros, "email", "email_1", unique=True, sparse=True)
        self._ensure_index(self.arbitros, "admin_id", "admin_id_1")

        # notificacoes
        self._ensure_index(self.notifications, "user_id", "user_id_1")
        self._ensure_index(self.notifications, "lida", "lida_1")
        self._ensure_index(self.notifications, [("criado_em", DESCENDING)], "criado_em_-1")
