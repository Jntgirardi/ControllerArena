import mongoengine as me


class UserStats(me.EmbeddedDocument):
    partidas_jogadas = me.IntField(default=0)
    vitorias = me.IntField(default=0)
    derrotas = me.IntField(default=0)
    kd_ratio = me.FloatField(default=1.0)


class PlayerDocument(me.Document):
    meta = {
        "collection": "jogadores",
        "indexes": [
            "nick",
            "login",
            "admin_id",
            "jogo_principal",
            ("admin_id", "nick"),
            ("-estatisticas.vitorias", "-estatisticas.kd_ratio")
        ]
    }
    nick = me.StringField(required=True)
    nome = me.StringField(required=True)
    nome_real = me.StringField()
    login = me.StringField(unique=True)
    contato = me.StringField()
    jogo_principal = me.StringField(required=True)
    admin_id = me.ObjectIdField(required=True)
    time_id = me.ObjectIdField()
    campeonato_id = me.ObjectIdField()
    estatisticas = me.EmbeddedDocumentField(UserStats, default=UserStats)
    rank_competitivo = me.StringField()
    premier_rating = me.IntField()
    rank_ato = me.StringField()
    agente_principal = me.StringField()
    criado_em = me.DateTimeField()


class TeamPlayer(me.EmbeddedDocument):
    jogador_id = me.ObjectIdField(required=True)
    nick = me.StringField(required=True)
    funcao = me.StringField(default="Jogador")


class TeamDocument(me.Document):
    meta = {
        "collection": "times",
        "indexes": [
            "admin_id",
            "jogo",
            "jogadores.jogador_id",
            ("admin_id", "nome"),
            ("admin_id", "jogo", "nome")
        ]
    }
    nome = me.StringField(required=True)
    tag = me.StringField(required=True)
    jogo = me.StringField(required=True)
    logo_path = me.StringField()
    admin_id = me.ObjectIdField(required=True)
    jogadores = me.EmbeddedDocumentListField(TeamPlayer, default=list)
    criado_em = me.DateTimeField()


class DateRange(me.EmbeddedDocument):
    inicio = me.DateTimeField()
    fim = me.DateTimeField()


class ChampionshipDocument(me.Document):
    meta = {
        "collection": "campeonatos",
        "indexes": [
            "admin_id",
            "status",
            "jogo",
            "-datas.inicio",
            ("admin_id", "-criado_em"),
            ("times_inscritos", "-datas.inicio")
        ]
    }
    nome = me.StringField(required=True)
    jogo = me.StringField(required=True)
    formato = me.StringField(required=True)
    max_times = me.IntField(required=True)
    premiacao = me.DictField()
    datas = me.EmbeddedDocumentField(DateRange)
    status = me.StringField(default="INSCRICAO")
    admin_id = me.ObjectIdField(required=True)
    times_inscritos = me.ListField(me.ObjectIdField(), default=list)
    criado_por = me.ObjectIdField()
    criado_em = me.DateTimeField()


class MatchTeam(me.EmbeddedDocument):
    time_id = me.ObjectIdField(required=True)
    nome = me.StringField(required=True)
    placar = me.IntField(default=0)


class RoundLog(me.EmbeddedDocument):
    round = me.IntField(required=True)
    vencedor_id = me.ObjectIdField(required=True)
    metodo = me.StringField(required=True)
    timestamp = me.DateTimeField()


class MatchCheckin(me.EmbeddedDocument):
    solicitado = me.BooleanField(default=False)
    solicitado_em = me.DateTimeField()
    antecedencia_minutos = me.IntField(default=15)
    time_a_confirmado = me.BooleanField(default=False)
    time_b_confirmado = me.BooleanField(default=False)
    wo_aplicado = me.BooleanField(default=False)
    mensagem_wo = me.StringField()


class MatchDocument(me.Document):
    meta = {
        "collection": "partidas",
        "indexes": [
            "admin_id",
            "campeonato_id",
            ("campeonato_id", "data_partida"),
            ("admin_id", "-data_partida")
        ]
    }
    campeonato_id = me.ObjectIdField(required=True)
    admin_id = me.ObjectIdField(required=True)
    arbitro_id = me.ObjectIdField()
    fase = me.StringField(required=True)
    status = me.StringField(default="agendada")
    data_partida = me.DateTimeField()
    mapa = me.StringField()
    time_a = me.EmbeddedDocumentField(MatchTeam, required=True)
    time_b = me.EmbeddedDocumentField(MatchTeam, required=True)
    rounds = me.EmbeddedDocumentListField(RoundLog, default=list)
    checkin = me.EmbeddedDocumentField(MatchCheckin, default=MatchCheckin)
    iniciada_em = me.DateTimeField()


class UserDocument(me.Document):
    meta = {
        "collection": "usuarios",
        "indexes": [
            "username",
            "login",
            "role",
            "admin_id",
            "access_code",
            "password_reset_token",
            "password_reset_expires_at",
            "-criado_em"
        ]
    }
    nome = me.StringField(required=True)
    login = me.StringField(unique=True)
    senha_hash = me.BinaryField(required=True)
    role = me.StringField(required=True)
    admin_id = me.ObjectIdField()
    player_id = me.ObjectIdField()
    referee_id = me.ObjectIdField()
    ativo = me.BooleanField(default=True)
    must_change_password = me.BooleanField(default=False)
    criado_em = me.DateTimeField()
    username = me.StringField()
    access_code = me.StringField()
    access_code_expires_at = me.DateTimeField()
    password_reset_token = me.StringField()
    password_reset_expires_at = me.DateTimeField()


class EventDocument(me.Document):
    meta = {
        "collection": "eventos",
        "indexes": [
            "admin_id",
            "data_evento"
        ]
    }
    nome = me.StringField(required=True)
    local = me.StringField(required=True)
    data_evento = me.DateTimeField(required=True)
    capacidade_total = me.IntField(required=True)
    admin_id = me.ObjectIdField(required=True)
    criado_em = me.DateTimeField()


class TicketDocument(me.Document):
    meta = {
        "collection": "ingressos",
        "indexes": [
            "admin_id",
            "evento_id",
            "status",
            ("admin_id", "-vendido_em")
        ]
    }
    evento_id = me.ObjectIdField(required=True)
    admin_id = me.ObjectIdField(required=True)
    comprador = me.StringField(required=True)
    lote = me.StringField(required=True)
    quantidade = me.IntField(required=True)
    valor_total = me.FloatField(required=True)
    status = me.StringField(required=True)
    vendido_em = me.DateTimeField()


class LogDocument(me.Document):
    meta = {
        "collection": "logs",
        "indexes": [
            "user_id",
            "role",
            "-created_at"
        ]
    }
    user_id = me.ObjectIdField()
    admin_id = me.ObjectIdField()
    login = me.StringField()
    role = me.StringField()
    endpoint = me.StringField()
    method = me.StringField()
    path = me.StringField()
    status_code = me.IntField()
    created_at = me.DateTimeField()


class ArbitroDocument(me.Document):
    meta = {
        "collection": "arbitros",
        "indexes": [
            "email",
            "admin_id"
        ]
    }
    nome = me.StringField(required=True)
    email = me.StringField(unique=True)
    disponibilidade = me.StringField(required=True)
    contato = me.StringField()
    admin_id = me.ObjectIdField(required=True)
    criado_em = me.DateTimeField()


class NotificationDocument(me.Document):
    meta = {
        "collection": "notificacoes",
        "indexes": [
            "user_id",
            "lida",
            "-criado_em"
        ]
    }
    user_id = me.ObjectIdField(required=True)
    mensagem = me.StringField(required=True)
    lida = me.BooleanField(default=False)
    link = me.StringField()
    criado_em = me.DateTimeField()
