from datetime import datetime, timezone
from app.extensions import db


class UsuarioEmpresa(db.Model):
    __tablename__ = 'usuario_empresa'

    usuario_id = db.Column(db.Integer, db.ForeignKey('usuarios.id'), primary_key=True)
    empresa_id = db.Column(db.Integer, db.ForeignKey('empresas.id'), primary_key=True)


class Empresa(db.Model):
    __tablename__ = 'empresas'

    id = db.Column(db.Integer, primary_key=True)
    razao_social = db.Column(db.String(200), nullable=False)
    nome_fantasia = db.Column(db.String(200))
    cnpj = db.Column(db.String(18), unique=True, nullable=False)
    inscricao_estadual = db.Column(db.String(30))
    inscricao_municipal = db.Column(db.String(30))
    cnae_principal = db.Column(db.String(10), nullable=False)
    regime_tributario = db.Column(db.String(30), nullable=False)
    posicao_cadeia = db.Column(db.String(20), nullable=False)
    logradouro = db.Column(db.String(200))
    numero = db.Column(db.String(20))
    complemento = db.Column(db.String(100))
    bairro = db.Column(db.String(100))
    cidade = db.Column(db.String(100))
    uf = db.Column(db.String(2))
    cep = db.Column(db.String(9))
    telefone = db.Column(db.String(20))
    email = db.Column(db.String(150))
    responsavel_nome = db.Column(db.String(150))
    responsavel_cpf = db.Column(db.String(14))
    ativo = db.Column(db.Boolean, default=True)
    created_at = db.Column(db.DateTime, default=lambda: datetime.now(timezone.utc))
    updated_at = db.Column(db.DateTime, onupdate=lambda: datetime.now(timezone.utc))

    usuarios = db.relationship('Usuario', secondary='usuario_empresa', back_populates='empresas')
    consultas = db.relationship('Consulta', back_populates='empresa', lazy='dynamic')
    lotes = db.relationship('LoteConsulta', back_populates='empresa', lazy='dynamic')

    @property
    def cnpj_formatado(self):
        c = self.cnpj.replace('.', '').replace('/', '').replace('-', '')
        if len(c) == 14:
            return f'{c[:2]}.{c[2:5]}.{c[5:8]}/{c[8:12]}-{c[12:]}'
        return self.cnpj

    @property
    def regime_label(self):
        labels = {
            'simples_nacional': 'Simples Nacional',
            'lucro_presumido': 'Lucro Presumido',
            'lucro_real': 'Lucro Real',
        }
        return labels.get(self.regime_tributario, self.regime_tributario)

    @property
    def posicao_label(self):
        labels = {
            'fabricante': 'Fabricante',
            'importador': 'Importador',
            'atacadista': 'Atacadista',
            'varejista': 'Varejista',
        }
        return labels.get(self.posicao_cadeia, self.posicao_cadeia)

    def __repr__(self):
        return f'<Empresa {self.razao_social}>'
