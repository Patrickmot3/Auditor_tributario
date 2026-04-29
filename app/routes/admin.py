from flask import Blueprint, render_template, redirect, url_for, flash, request, jsonify
from flask_login import login_required, current_user
from functools import wraps
from datetime import date, timezone, timedelta
from app.extensions import db

_BRT = timezone(timedelta(hours=-3))


def _fmt_brt(dt, fmt='%d/%m/%Y %H:%M'):
    if not dt:
        return 'N/A'
    if dt.tzinfo is None:
        dt = dt.replace(tzinfo=timezone.utc)
    return dt.astimezone(_BRT).strftime(fmt)
from app.models.usuario import Usuario
from app.models.base_tributaria import LogAtualizacao, AliquotaGrupo
from app.models.empresa import Empresa
from app.models.ncm import GrupoTributario

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
    from app.models.ncm import GrupoTributario, NcmTributario
    from sqlalchemy import func

    DESCRICAO_TABELA = {
        '4.3.10': 'Monofásicos — Alíquotas Diferenciadas (CST 02/04)',
        '4.3.11': 'Monofásicos por Unidade de Medida (CST 03/04)',
        '4.3.12': 'Substituição Tributária (CST 05)',
        '4.3.13': 'Alíquota Zero (CST 06)',
        '4.3.14': 'Isenção PIS/COFINS (CST 07)',
        '4.3.15': 'Sem Incidência (CST 08)',
        '4.3.16': 'Suspensão PIS/COFINS (CST 09)',
    }

    # Agrupa grupos por tabela_sped
    grupos = GrupoTributario.query.order_by(GrupoTributario.tabela_sped, GrupoTributario.codigo).all()
    tabelas_map = {}
    for g in grupos:
        ts = g.tabela_sped or 'N/A'
        tabelas_map.setdefault(ts, {'grupos': []})['grupos'].append(g)

    # Contagem de NCMs ativos por tabela
    ncm_counts = (
        db.session.query(GrupoTributario.tabela_sped, func.count(NcmTributario.id))
        .join(NcmTributario, NcmTributario.grupo_tributario_id == GrupoTributario.id)
        .filter(NcmTributario.ativo == True)
        .group_by(GrupoTributario.tabela_sped)
        .all()
    )
    ncm_por_tabela = {ts: cnt for ts, cnt in ncm_counts}

    # Log de seed como fallback para tabelas sem log próprio
    seed_log = LogAtualizacao.query.filter(
        LogAtualizacao.tabela_sped == 'seed'
    ).order_by(LogAtualizacao.data_importacao.desc()).first()

    status_tabelas = []
    for ts in sorted(tabelas_map.keys()):
        grupos_ts = tabelas_map[ts]['grupos']
        log = LogAtualizacao.query.filter(
            LogAtualizacao.tabela_sped == ts,
        ).order_by(LogAtualizacao.data_importacao.desc()).first()

        tem_log_proprio = log is not None
        if not log:
            log = seed_log

        grupos_str = ' / '.join(f"{g.codigo} — {g.nome}" for g in grupos_ts)
        status_tabelas.append({
            'tabela': ts,
            'descricao': DESCRICAO_TABELA.get(ts, ''),
            'grupos': grupos_str,
            'ncm_count': ncm_por_tabela.get(ts, 0),
            'versao': log.versao if log else 'N/A',
            'data_rfb': log.data_atualizacao_rfb.strftime('%d/%m/%Y') if log and log.data_atualizacao_rfb else 'N/A',
            'data_importacao': _fmt_brt(log.data_importacao) if log else 'N/A',
            'status': (log.status if tem_log_proprio else 'seed_inicial') if log else 'sem_dados',
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


# ── Alíquotas por grupo/vigência ─────────────────────────────────────────────

@admin_bp.route('/aliquotas')
@login_required
@admin_required
def aliquotas():
    grupos = GrupoTributario.query.order_by(GrupoTributario.codigo).all()
    aliquotas_list = (
        AliquotaGrupo.query
        .join(GrupoTributario)
        .order_by(GrupoTributario.codigo, AliquotaGrupo.vigencia_inicio.desc())
        .all()
    )
    return render_template('admin/aliquotas.html', grupos=grupos, aliquotas=aliquotas_list)


@admin_bp.route('/aliquotas/nova', methods=['GET', 'POST'])
@login_required
@admin_required
def nova_aliquota():
    grupos = GrupoTributario.query.order_by(GrupoTributario.codigo).all()
    if request.method == 'POST':
        grupo_id = request.form.get('grupo_tributario_id', type=int)
        try:
            vigencia_inicio = date.fromisoformat(request.form.get('vigencia_inicio', ''))
            vigencia_fim_raw = request.form.get('vigencia_fim', '').strip()
            vigencia_fim = date.fromisoformat(vigencia_fim_raw) if vigencia_fim_raw else None

            alq = AliquotaGrupo(
                grupo_tributario_id=grupo_id,
                pis_fabricante=float(request.form.get('pis_fabricante', 0)),
                cofins_fabricante=float(request.form.get('cofins_fabricante', 0)),
                pis_varejista=float(request.form.get('pis_varejista', 0)),
                cofins_varejista=float(request.form.get('cofins_varejista', 0)),
                vigencia_inicio=vigencia_inicio,
                vigencia_fim=vigencia_fim,
                lei_referencia=request.form.get('lei_referencia', '').strip(),
                observacao=request.form.get('observacao', '').strip(),
                ativo=True,
            )
            db.session.add(alq)
            db.session.commit()
            flash('Alíquota cadastrada com sucesso!', 'success')
            return redirect(url_for('admin.aliquotas'))
        except (ValueError, TypeError) as e:
            flash(f'Dados inválidos: {e}', 'danger')

    return render_template('admin/aliquota_form.html', grupos=grupos, aliquota=None)


@admin_bp.route('/aliquotas/<int:id>/editar', methods=['GET', 'POST'])
@login_required
@admin_required
def editar_aliquota(id):
    alq = db.get_or_404(AliquotaGrupo, id)
    grupos = GrupoTributario.query.order_by(GrupoTributario.codigo).all()
    if request.method == 'POST':
        try:
            alq.grupo_tributario_id = request.form.get('grupo_tributario_id', type=int)
            alq.pis_fabricante = float(request.form.get('pis_fabricante', 0))
            alq.cofins_fabricante = float(request.form.get('cofins_fabricante', 0))
            alq.pis_varejista = float(request.form.get('pis_varejista', 0))
            alq.cofins_varejista = float(request.form.get('cofins_varejista', 0))
            alq.vigencia_inicio = date.fromisoformat(request.form.get('vigencia_inicio', ''))
            vigencia_fim_raw = request.form.get('vigencia_fim', '').strip()
            alq.vigencia_fim = date.fromisoformat(vigencia_fim_raw) if vigencia_fim_raw else None
            alq.lei_referencia = request.form.get('lei_referencia', '').strip()
            alq.observacao = request.form.get('observacao', '').strip()
            alq.ativo = bool(request.form.get('ativo'))
            db.session.commit()
            flash('Alíquota atualizada!', 'success')
            return redirect(url_for('admin.aliquotas'))
        except (ValueError, TypeError) as e:
            flash(f'Dados inválidos: {e}', 'danger')

    return render_template('admin/aliquota_form.html', grupos=grupos, aliquota=alq)


@admin_bp.route('/aliquotas/<int:id>/desativar', methods=['POST'])
@login_required
@admin_required
def desativar_aliquota(id):
    alq = db.get_or_404(AliquotaGrupo, id)
    alq.ativo = False
    db.session.commit()
    flash('Alíquota desativada.', 'warning')
    return redirect(url_for('admin.aliquotas'))
