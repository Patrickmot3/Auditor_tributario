from datetime import datetime, timezone
from flask import Blueprint, render_template, redirect, url_for, flash, request
from flask_login import login_user, logout_user, login_required, current_user
from app.extensions import db
from app.models.usuario import Usuario

auth_bp = Blueprint('auth', __name__)


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
