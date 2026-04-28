from flask import Blueprint, render_template, redirect, url_for, flash, request, jsonify
from flask_login import login_required, current_user
from functools import wraps
from app.extensions import db
from app.models.usuario import Usuario
from app.models.base_tributaria import LogAtualizacao
from app.models.empresa import Empresa

admin_bp = Blueprint('admin', __name__)


def admin_required(f):
    @wraps(f)
    def decorated(*args, **kwargs):
        if not current_user.is_authenticated or not current_user.is_admin:
            flash('Acesso restrito a administradores.', 'danger')
            return redirect(url_for('consulta.individual'))
        return f(*args, **kwargs)
    return decorated


@admin_bp.route('/dashboard')
@login_required
@admin_required
def dashboard():
    from app.models.consulta import Consulta
    total_empresas = Empresa.query.filter_by(ativo=True).count()
    total_consultas = Consulta.query.count()
    total_usuarios = Usuario.query.filter_by(ativo=True).count()

    logs = LogAtualizacao.query.order_by(LogAtualizacao.data_importacao.desc()).limit(10).all()
    return render_template('admin/dashboard.html',
                           total_empresas=total_empresas,
                           total_consultas=total_consultas,
                           total_usuarios=total_usuarios,
                           logs=logs)


@admin_bp.route('/atualizacao/status')
@login_required
def atualizacao_status():
    tabelas = ['4.3.10', '4.3.11', '4.3.13', '4.3.15']
    status_tabelas = []

    for tabela in tabelas:
        log = LogAtualizacao.query.filter(
            LogAtualizacao.tabela_sped == tabela,
        ).order_by(LogAtualizacao.data_importacao.desc()).first()

        status_tabelas.append({
            'tabela': tabela,
            'versao': log.versao if log else 'N/A',
            'data_rfb': log.data_atualizacao_rfb.strftime('%d/%m/%Y') if log and log.data_atualizacao_rfb else 'N/A',
            'data_importacao': log.data_importacao.strftime('%d/%m/%Y %H:%M') if log else 'N/A',
            'status': log.status if log else 'sem_dados',
        })

    from app.services.scheduler import get_proximas_execucoes
    proximas = get_proximas_execucoes()

    return render_template('admin/atualizacao_status.html',
                           status_tabelas=status_tabelas, proximas=proximas)


@admin_bp.route('/atualizacao/executar', methods=['POST'])
@login_required
@admin_required
def atualizacao_executar():
    tabela = request.form.get('tabela', '4.3.10')
    from app.services.rfb_scraper import atualizar_tabela
    resultado = atualizar_tabela(tabela, executado_por=current_user.email)
    if resultado.get('status') == 'sucesso':
        flash(f'Tabela {tabela} atualizada: {resultado["inseridos"]} inseridos, {resultado["atualizados"]} atualizados.', 'success')
    else:
        flash(f'Erro ao atualizar tabela {tabela}: {resultado.get("mensagem")}', 'danger')
    return redirect(url_for('admin.atualizacao_status'))


@admin_bp.route('/usuarios')
@login_required
@admin_required
def usuarios():
    lista = Usuario.query.order_by(Usuario.nome).all()
    return render_template('admin/usuarios.html', usuarios=lista)


@admin_bp.route('/usuarios/novo', methods=['GET', 'POST'])
@login_required
@admin_required
def novo_usuario():
    if request.method == 'POST':
        nome = request.form.get('nome', '').strip()
        email = request.form.get('email', '').strip().lower()
        senha = request.form.get('senha', '')
        perfil = request.form.get('perfil', 'operador')

        if Usuario.query.filter_by(email=email).first():
            flash('E-mail já cadastrado.', 'danger')
        else:
            u = Usuario(nome=nome, email=email, perfil=perfil)
            u.set_senha(senha)
            db.session.add(u)
            db.session.commit()
            flash(f'Usuário "{nome}" criado com sucesso!', 'success')
            return redirect(url_for('admin.usuarios'))

    return render_template('admin/usuario_form.html')


@admin_bp.route('/logs')
@login_required
@admin_required
def logs():
    page = request.args.get('page', 1, type=int)
    logs_pag = LogAtualizacao.query.order_by(
        LogAtualizacao.data_importacao.desc()
    ).paginate(page=page, per_page=20)
    return render_template('admin/logs.html', logs=logs_pag)
