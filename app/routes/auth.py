import logging
from datetime import datetime, timezone
from flask import (Blueprint, render_template, redirect, url_for,
                   flash, request, current_app)
from flask_login import login_user, logout_user, login_required, current_user
from app.extensions import db
from app.models.usuario import Usuario

auth_bp = Blueprint('auth', __name__)
logger = logging.getLogger(__name__)


# ─── Login ────────────────────────────────────────────────────────────────────

@auth_bp.route('/login', methods=['GET', 'POST'])
def login():
    if current_user.is_authenticated:
        return redirect(url_for('consulta.individual'))

    if request.method == 'POST':
        email = request.form.get('email', '').strip().lower()
        senha = request.form.get('senha', '')
        usuario = Usuario.query.filter_by(email=email, ativo=True).first()

        if usuario and usuario.check_senha(senha):
            usuario.ultimo_acesso = datetime.now(timezone.utc)
            db.session.commit()
            login_user(usuario, remember=True)
            next_page = request.args.get('next')
            return redirect(next_page or url_for('consulta.individual'))
        flash('E-mail ou senha incorretos.', 'danger')

    return render_template('auth/login.html')


@auth_bp.route('/logout')
@login_required
def logout():
    logout_user()
    flash('Você saiu do sistema.', 'info')
    return redirect(url_for('auth.login'))


# ─── Cadastro ─────────────────────────────────────────────────────────────────

@auth_bp.route('/cadastro', methods=['GET', 'POST'])
def cadastro():
    if current_user.is_authenticated:
        return redirect(url_for('consulta.individual'))

    if request.method == 'POST':
        nome = request.form.get('nome', '').strip()
        email = request.form.get('email', '').strip().lower()
        cpf_cnpj = request.form.get('cpf_cnpj', '').strip()
        senha = request.form.get('senha', '')
        confirmacao = request.form.get('confirmacao', '')

        erro = None
        if not all([nome, email, senha]):
            erro = 'Nome, e-mail e senha são obrigatórios.'
        elif len(senha) < 8:
            erro = 'A senha deve ter pelo menos 8 caracteres.'
        elif senha != confirmacao:
            erro = 'A senha e a confirmação não coincidem.'
        elif Usuario.query.filter_by(email=email).first():
            erro = 'Este e-mail já está cadastrado.'

        if erro:
            flash(erro, 'danger')
            return render_template('auth/cadastro.html',
                                   nome=nome, email=email, cpf_cnpj=cpf_cnpj)

        usuario = Usuario(
            nome=nome,
            email=email,
            cpf_cnpj=_limpar_documento(cpf_cnpj),
            perfil='operador',
        )
        usuario.set_senha(senha)
        db.session.add(usuario)
        db.session.commit()

        login_user(usuario, remember=True)
        flash(f'Bem-vindo, {nome}! Conta criada com sucesso.', 'success')
        return redirect(url_for('empresa.nova'))

    return render_template('auth/cadastro.html')


# ─── Trocar senha (usuário logado) ────────────────────────────────────────────

@auth_bp.route('/trocar-senha', methods=['GET', 'POST'])
@login_required
def trocar_senha():
    if request.method == 'POST':
        senha_atual = request.form.get('senha_atual', '')
        nova_senha = request.form.get('nova_senha', '')
        confirmacao = request.form.get('confirmacao', '')

        if not current_user.check_senha(senha_atual):
            flash('Senha atual incorreta.', 'danger')
        elif nova_senha != confirmacao:
            flash('A nova senha e a confirmação não coincidem.', 'danger')
        elif len(nova_senha) < 8:
            flash('A nova senha deve ter pelo menos 8 caracteres.', 'danger')
        else:
            current_user.set_senha(nova_senha)
            db.session.commit()
            flash('Senha alterada com sucesso!', 'success')
            return redirect(url_for('consulta.individual'))

    return render_template('auth/trocar_senha.html')


# ─── Esqueci minha senha ──────────────────────────────────────────────────────

@auth_bp.route('/esqueci-senha', methods=['GET', 'POST'])
def esqueci_senha():
    if current_user.is_authenticated:
        return redirect(url_for('consulta.individual'))

    link_reset = None

    if request.method == 'POST':
        email = request.form.get('email', '').strip().lower()
        usuario = Usuario.query.filter_by(email=email, ativo=True).first()

        if usuario:
            token = usuario.gerar_reset_token()
            db.session.commit()

            link_reset = url_for('auth.redefinir_senha', token=token, _external=True)

            # Tentar enviar e-mail se Flask-Mail configurado
            _enviar_email_reset(usuario, link_reset)

            logger.info(f'Token de reset gerado para {email}')

        # Sempre exibe a mesma mensagem (não revela se e-mail existe)
        flash('Se este e-mail estiver cadastrado, você receberá as instruções.', 'info')

    return render_template('auth/esqueci_senha.html', link_reset=link_reset)


# ─── Redefinir senha (via token) ──────────────────────────────────────────────

@auth_bp.route('/redefinir-senha/<token>', methods=['GET', 'POST'])
def redefinir_senha(token):
    usuario = Usuario.query.filter_by(reset_token=token).first()

    if not usuario or not usuario.reset_token_valido():
        flash('Link inválido ou expirado. Solicite um novo.', 'danger')
        return redirect(url_for('auth.esqueci_senha'))

    if request.method == 'POST':
        nova_senha = request.form.get('nova_senha', '')
        confirmacao = request.form.get('confirmacao', '')

        if len(nova_senha) < 8:
            flash('A senha deve ter pelo menos 8 caracteres.', 'danger')
        elif nova_senha != confirmacao:
            flash('As senhas não coincidem.', 'danger')
        else:
            usuario.set_senha(nova_senha)
            usuario.limpar_reset_token()
            db.session.commit()
            flash('Senha redefinida com sucesso! Faça login.', 'success')
            return redirect(url_for('auth.login'))

    return render_template('auth/redefinir_senha.html', token=token)


# ─── Helpers ──────────────────────────────────────────────────────────────────

def _limpar_documento(doc):
    if not doc:
        return None
    return doc.replace('.', '').replace('-', '').replace('/', '').strip()


def _enviar_email_reset(usuario, link):
    try:
        from flask_mail import Mail, Message
        mail = Mail(current_app)
        msg = Message(
            subject='TribSync — Redefinição de senha',
            recipients=[usuario.email],
            html=f'''
            <p>Olá, <strong>{usuario.nome}</strong>!</p>
            <p>Clique no link abaixo para redefinir sua senha. O link expira em 2 horas.</p>
            <p><a href="{link}">{link}</a></p>
            <p>Se você não solicitou a redefinição, ignore este e-mail.</p>
            ''',
        )
        mail.send(msg)
    except Exception as e:
        logger.warning(f'E-mail não enviado (Flask-Mail não configurado): {e}')
