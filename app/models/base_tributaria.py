from datetime import datetime, timezone
from app.extensions import db


class LogAtualizacao(db.Model):
    __tablename__ = 'logs_atualizacao'

    id = db.Column(db.Integer, primary_key=True)
    tabela_sped = db.Column(db.String(20))
    versao = db.Column(db.String(20))
    data_atualizacao_rfb = db.Column(db.Date)
    data_importacao = db.Column(db.DateTime, default=lambda: datetime.now(timezone.utc))
    status = db.Column(db.String(20))  # sucesso, erro, sem_alteracoes, seed_inicial
    registros_inseridos = db.Column(db.Integer, default=0)
    registros_atualizados = db.Column(db.Integer, default=0)
    mensagem = db.Column(db.Text)
    executado_por = db.Column(db.String(50))

    def __repr__(self):
        return f'<LogAtualizacao {self.tabela_sped} - {self.status}>'
