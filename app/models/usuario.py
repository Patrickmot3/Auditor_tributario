import secrets
from datetime import datetime, timezone, timedelta
from flask_login import UserMixin
from werkzeug.security import generate_password_hash, check_password_hash
from app.extensions import db


class Usuario(UserMixin, db.Model):
    __tablename__ = 'usuarios'

    id = db.Column(db.Integer, primary_key=True)
    nome = db.Column(db.String(150), nullable=False)
    email = db.Column(db.String(150), unique=True, nullable=False)
    cpf_cnpj = db.Column(db.String(18))
    senha_hash = db.Column(db.String(256), nullable=False)
    perfil = db.Column(db.String(20), nullable=False, default='operador')
    ativo = db.Column(db.Boolean, default=True)
    created_at = db.Column(db.DateTime, default=lambda: datetime.now(timezone.utc))
    ultimo_acesso = db.Column(db.DateTime)
    reset_token = db.Column(db.String(100), unique=True, nullable=True)
    reset_token_expiry = db.Column(db.DateTime, nullable=True)

    empresas = db.relationship('Empresa', secondary='usuario_empresa', back_populates='usuarios')

    def set_senha(self, senha):
        self.senha_hash = generate_password_hash(senha)

    def check_senha(self, senha):
        return check_password_hash(self.senha_hash, senha)

    @property
    def is_admin(self):
        return self.perfil == 'admin'

    def gerar_reset_token(self):
        self.reset_token = secrets.token_urlsafe(48)
        self.reset_token_expiry = datetime.now(timezone.utc) + timedelta(hours=2)
        return self.reset_token

    def reset_token_valido(self):
        if not self.reset_token or not self.reset_token_expiry:
            return False
        expiry = self.reset_token_expiry
        if expiry.tzinfo is None:
            expiry = expiry.replace(tzinfo=timezone.utc)
        return datetime.now(timezone.utc) < expiry

    def limpar_reset_token(self):
        self.reset_token = None
        self.reset_token_expiry = None

    def __repr__(self):
        return f'<Usuario {self.email}>'
