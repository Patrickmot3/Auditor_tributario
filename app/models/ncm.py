from datetime import datetime, timezone
from app.extensions import db


class GrupoTributario(db.Model):
    __tablename__ = 'grupos_tributarios'

    id = db.Column(db.Integer, primary_key=True)
    codigo = db.Column(db.String(10), unique=True, nullable=False)
    nome = db.Column(db.String(100), nullable=False)
    lei_base = db.Column(db.String(200))
    tabela_sped = db.Column(db.String(50))
    url_tabela_sped = db.Column(db.Text)
    descricao = db.Column(db.Text)
    created_at = db.Column(db.DateTime, default=lambda: datetime.now(timezone.utc))
    updated_at = db.Column(db.DateTime, onupdate=lambda: datetime.now(timezone.utc))

    ncms = db.relationship('NcmTributario', back_populates='grupo', lazy='dynamic')

    def __repr__(self):
        return f'<GrupoTributario {self.codigo} - {self.nome}>'


class NcmTributario(db.Model):
    __tablename__ = 'ncms_tributarios'

    id = db.Column(db.Integer, primary_key=True)
    ncm = db.Column(db.String(10), nullable=False)
    descricao = db.Column(db.String(500))
    grupo_tributario_id = db.Column(db.Integer, db.ForeignKey('grupos_tributarios.id'))
    monofasico = db.Column(db.Boolean, nullable=False, default=True)
    tipo_referencia = db.Column(db.String(30))  # ncm_exato, posicao_4, posicao_6, prefixo
    lei = db.Column(db.String(300))
    cst_entrada = db.Column(db.String(3))
    cst_saida = db.Column(db.String(3))
    cfop_entrada_simples = db.Column(db.String(5))
    cfop_saida_simples = db.Column(db.String(5))
    pis_aliquota_fabricante = db.Column(db.Numeric(6, 4), default=0)
    cofins_aliquota_fabricante = db.Column(db.Numeric(6, 4), default=0)
    pis_aliquota_varejista = db.Column(db.Numeric(6, 4), default=0)
    cofins_aliquota_varejista = db.Column(db.Numeric(6, 4), default=0)
    vigencia_inicio = db.Column(db.Date)
    vigencia_fim = db.Column(db.Date, nullable=True)
    observacao = db.Column(db.Text)
    fonte_url = db.Column(db.Text)
    ativo = db.Column(db.Boolean, default=True)
    created_at = db.Column(db.DateTime, default=lambda: datetime.now(timezone.utc))
    updated_at = db.Column(db.DateTime, onupdate=lambda: datetime.now(timezone.utc))

    grupo = db.relationship('GrupoTributario', back_populates='ncms')

    __table_args__ = (
        db.UniqueConstraint('ncm', 'grupo_tributario_id', 'vigencia_inicio',
                            name='unique_ncm_grupo_vigencia'),
    )

    def __repr__(self):
        return f'<NcmTributario {self.ncm}>'
