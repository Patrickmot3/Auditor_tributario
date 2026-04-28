from datetime import datetime, timezone
from app.extensions import db


class Consulta(db.Model):
    __tablename__ = 'consultas'

    id = db.Column(db.Integer, primary_key=True)
    empresa_id = db.Column(db.Integer, db.ForeignKey('empresas.id'), nullable=False)
    tipo_consulta = db.Column(db.String(20), nullable=False)  # individual, lote, excel, xml_nfe
    origem = db.Column(db.String(20), default='manual')       # manual, excel, xml
    ncm_consultado = db.Column(db.String(10))
    descricao_produto = db.Column(db.String(500))
    codigo_produto = db.Column(db.String(50))
    codigo_nbm = db.Column(db.String(15))
    codigo_cest = db.Column(db.String(10))
    monofasico = db.Column(db.Boolean)
    grupo_tributario = db.Column(db.String(100))
    lei_aplicada = db.Column(db.String(300))
    cst_atual = db.Column(db.String(3))
    cst_sugerido = db.Column(db.String(3))
    cfop_sugerido = db.Column(db.String(5))
    pis_aliquota = db.Column(db.Numeric(6, 4))
    cofins_aliquota = db.Column(db.Numeric(6, 4))
    posicao_cadeia = db.Column(db.String(20))
    observacao = db.Column(db.Text)
    inconsistencia_detectada = db.Column(db.Boolean, default=False)
    created_at = db.Column(db.DateTime, default=lambda: datetime.now(timezone.utc))

    empresa = db.relationship('Empresa', back_populates='consultas')
    lote_itens = db.relationship('LoteItem', back_populates='consulta', lazy='dynamic')

    __table_args__ = (
        db.UniqueConstraint('empresa_id', 'ncm_consultado', name='unique_empresa_ncm'),
    )

    def __repr__(self):
        return f'<Consulta {self.ncm_consultado} - empresa {self.empresa_id}>'


class LoteConsulta(db.Model):
    __tablename__ = 'lotes_consulta'

    id = db.Column(db.Integer, primary_key=True)
    empresa_id = db.Column(db.Integer, db.ForeignKey('empresas.id'))
    nome_lote = db.Column(db.String(200))
    tipo = db.Column(db.String(20))  # excel, xml_nfe, manual
    total_itens = db.Column(db.Integer, default=0)
    itens_monofasicos = db.Column(db.Integer, default=0)
    itens_nao_monofasicos = db.Column(db.Integer, default=0)
    itens_com_inconsistencia = db.Column(db.Integer, default=0)
    status = db.Column(db.String(20), default='processando')
    created_at = db.Column(db.DateTime, default=lambda: datetime.now(timezone.utc))
    concluido_at = db.Column(db.DateTime)

    empresa = db.relationship('Empresa', back_populates='lotes')
    itens = db.relationship('LoteItem', back_populates='lote', lazy='dynamic')

    def __repr__(self):
        return f'<LoteConsulta {self.nome_lote}>'


class LoteItem(db.Model):
    __tablename__ = 'lote_itens'

    id = db.Column(db.Integer, primary_key=True)
    lote_id = db.Column(db.Integer, db.ForeignKey('lotes_consulta.id'))
    consulta_id = db.Column(db.Integer, db.ForeignKey('consultas.id'), nullable=True)
    linha_original = db.Column(db.Integer)
    ncm = db.Column(db.String(10))
    descricao = db.Column(db.String(500))
    codigo_produto = db.Column(db.String(50))
    codigo_cest = db.Column(db.String(10))
    status_processamento = db.Column(db.String(20), default='ok')  # ok, erro, duplicado
    mensagem_erro = db.Column(db.String(300))

    lote = db.relationship('LoteConsulta', back_populates='itens')
    consulta = db.relationship('Consulta', back_populates='lote_itens')

    def __repr__(self):
        return f'<LoteItem {self.ncm} - {self.status_processamento}>'
