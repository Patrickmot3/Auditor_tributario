from datetime import datetime, timezone, date
from app.extensions import db


class AliquotaGrupo(db.Model):
    """
    Alíquotas PIS/COFINS monofásico por grupo tributário e vigência.
    Permite registrar mudanças legislativas sem alterar código-fonte.
    """
    __tablename__ = 'aliquotas_grupo'

    id = db.Column(db.Integer, primary_key=True)
    grupo_tributario_id = db.Column(
        db.Integer, db.ForeignKey('grupos_tributarios.id'), nullable=False,
    )
    # Alíquotas do fabricante/importador (quem recolhe de fato)
    pis_fabricante = db.Column(db.Numeric(7, 4), nullable=False, default=0)
    cofins_fabricante = db.Column(db.Numeric(7, 4), nullable=False, default=0)
    # Alíquota do varejista (Simples Nacional → 0%)
    pis_varejista = db.Column(db.Numeric(7, 4), nullable=False, default=0)
    cofins_varejista = db.Column(db.Numeric(7, 4), nullable=False, default=0)
    # Vigência
    vigencia_inicio = db.Column(db.Date, nullable=False, default=date.today)
    vigencia_fim = db.Column(db.Date, nullable=True)
    # Referência legal
    lei_referencia = db.Column(db.String(300))
    observacao = db.Column(db.Text)
    ativo = db.Column(db.Boolean, default=True)
    created_at = db.Column(db.DateTime, default=lambda: datetime.now(timezone.utc))
    updated_at = db.Column(
        db.DateTime,
        default=lambda: datetime.now(timezone.utc),
        onupdate=lambda: datetime.now(timezone.utc),
    )

    grupo = db.relationship('GrupoTributario', backref='aliquotas')

    def __repr__(self):
        return (
            f'<AliquotaGrupo grupo={self.grupo_tributario_id} '
            f'PIS={self.pis_fabricante} COFINS={self.cofins_fabricante} '
            f'desde={self.vigencia_inicio}>'
        )

    @classmethod
    def vigente_para(cls, grupo_id, referencia=None):
        """Retorna a alíquota vigente para o grupo na data de referência (padrão: hoje)."""
        ref = referencia or date.today()
        return (
            cls.query
            .filter(
                cls.grupo_tributario_id == grupo_id,
                cls.ativo == True,
                cls.vigencia_inicio <= ref,
                db.or_(cls.vigencia_fim == None, cls.vigencia_fim >= ref),
            )
            .order_by(cls.vigencia_inicio.desc())
            .first()
        )


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
