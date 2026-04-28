import os
from flask import (Blueprint, render_template, redirect, url_for,
                   flash, request, session, current_app, send_file, abort)
from flask_login import login_required, current_user
from app.extensions import db
from app.models.empresa import Empresa
from app.models.consulta import Consulta, LoteConsulta
from app.services.ncm_validator import validar_ncm, _normalizar_ncm


def _checar_acesso_empresa(empresa_id):
    """Retorna a empresa ou aborta 403 se o usuário não tiver acesso."""
    empresa = db.get_or_404(Empresa, empresa_id)
    if not current_user.is_admin and empresa not in current_user.empresas:
        abort(403)
    return empresa


def _checar_acesso_consulta(consulta):
    """Aborta 403 se o usuário não tem acesso à empresa da consulta."""
    if not current_user.is_admin:
        ids = [e.id for e in current_user.empresas]
        if consulta.empresa_id not in ids:
            abort(403)

consulta_bp = Blueprint('consulta', __name__)


def _empresa_selecionada():
    empresa_id = session.get('empresa_id')
    if not empresa_id:
        return None
    return db.session.get(Empresa, empresa_id)


@consulta_bp.route('/individual', methods=['GET', 'POST'])
@login_required
def individual():
    empresa = _empresa_selecionada()
    resultado = None

    if request.method == 'POST':
        ncm = request.form.get('ncm', '').strip()
        cst_atual = request.form.get('cst_atual', '').strip() or None
        empresa_id = request.form.get('empresa_id', type=int)

        if not empresa_id:
            flash('Selecione uma empresa antes de consultar.', 'warning')
        elif not ncm:
            flash('Informe o NCM.', 'warning')
        else:
            session['empresa_id'] = empresa_id
            empresa = db.session.get(Empresa, empresa_id)
            resultado = validar_ncm(ncm, empresa_id, cst_atual)

    empresas = current_user.empresas if not current_user.is_admin else Empresa.query.filter_by(ativo=True).all()
    return render_template('consulta/individual.html',
                           empresa=empresa, resultado=resultado, empresas=empresas)


@consulta_bp.route('/lote/manual', methods=['POST'])
@login_required
def lote_manual():
    empresa_id = request.form.get('empresa_id', type=int)
    ncms_raw = request.form.get('ncms', '')
    if not empresa_id or not ncms_raw:
        flash('Informe a empresa e a lista de NCMs.', 'warning')
        return redirect(url_for('consulta.individual'))

    session['empresa_id'] = empresa_id
    ncms = [_normalizar_ncm(n) for n in ncms_raw.replace(',', '\n').split('\n') if n.strip()]
    ncms = [n for n in ncms if n]

    resultados = []
    for ncm in ncms:
        res = validar_ncm(ncm, empresa_id)
        res['ncm_formatado'] = ncm
        resultados.append(res)

    empresa = db.session.get(Empresa, empresa_id)
    empresas = current_user.empresas if not current_user.is_admin else Empresa.query.filter_by(ativo=True).all()
    return render_template('consulta/lote_resultado.html',
                           empresa=empresa, resultados=resultados, empresas=empresas)


@consulta_bp.route('/lote/excel', methods=['GET', 'POST'])
@login_required
def lote_excel():
    empresa = _empresa_selecionada()
    empresas = current_user.empresas if not current_user.is_admin else Empresa.query.filter_by(ativo=True).all()

    if request.method == 'POST':
        empresa_id = request.form.get('empresa_id', type=int)
        arquivo = request.files.get('arquivo')

        if not empresa_id or not arquivo:
            flash('Selecione a empresa e o arquivo Excel.', 'warning')
            return render_template('consulta/lote_excel.html', empresa=empresa, empresas=empresas)

        session['empresa_id'] = empresa_id
        empresa = db.session.get(Empresa, empresa_id)

        upload_dir = current_app.config.get('UPLOAD_FOLDER', 'uploads')
        os.makedirs(upload_dir, exist_ok=True)
        caminho = os.path.join(upload_dir, arquivo.filename)
        arquivo.save(caminho)

        from app.services.excel_processor import processar_excel
        relatorio = processar_excel(caminho, empresa_id, arquivo.filename)
        os.remove(caminho)

        if 'erro' in relatorio:
            flash(f'Erro ao processar: {relatorio["erro"]}', 'danger')
            return render_template('consulta/lote_excel.html', empresa=empresa, empresas=empresas)

        return render_template('consulta/lote_relatorio.html',
                               empresa=empresa, relatorio=relatorio, tipo='excel')

    return render_template('consulta/lote_excel.html', empresa=empresa, empresas=empresas)


@consulta_bp.route('/lote/xml', methods=['GET', 'POST'])
@login_required
def lote_xml():
    empresa = _empresa_selecionada()
    empresas = current_user.empresas if not current_user.is_admin else Empresa.query.filter_by(ativo=True).all()

    if request.method == 'POST':
        empresa_id = request.form.get('empresa_id', type=int)
        arquivo = request.files.get('arquivo')

        if not empresa_id or not arquivo:
            flash('Selecione a empresa e o arquivo XML.', 'warning')
            return render_template('consulta/lote_xml.html', empresa=empresa, empresas=empresas)

        session['empresa_id'] = empresa_id
        empresa = db.session.get(Empresa, empresa_id)

        upload_dir = current_app.config.get('UPLOAD_FOLDER', 'uploads')
        os.makedirs(upload_dir, exist_ok=True)
        caminho = os.path.join(upload_dir, arquivo.filename)
        arquivo.save(caminho)

        from app.services.xml_processor import processar_xml_nfe
        relatorio = processar_xml_nfe(caminho, empresa_id)
        os.remove(caminho)

        if 'erro' in relatorio:
            flash(f'Erro ao processar: {relatorio["erro"]}', 'danger')
            return render_template('consulta/lote_xml.html', empresa=empresa, empresas=empresas)

        return render_template('consulta/lote_relatorio.html',
                               empresa=empresa, relatorio=relatorio, tipo='xml')

    return render_template('consulta/lote_xml.html', empresa=empresa, empresas=empresas)


@consulta_bp.route('/historico')
@login_required
def historico():
    page = request.args.get('page', 1, type=int)
    empresa_id = request.args.get('empresa_id', type=int)
    monofasico = request.args.get('monofasico')
    inconsistencia = request.args.get('inconsistencia')
    ncm_filtro = request.args.get('ncm', '').strip()
    tipo_filtro = request.args.get('tipo')

    query = Consulta.query

    if not current_user.is_admin:
        ids = [e.id for e in current_user.empresas]
        query = query.filter(Consulta.empresa_id.in_(ids))

    if empresa_id:
        query = query.filter(Consulta.empresa_id == empresa_id)
    if monofasico == '1':
        query = query.filter(Consulta.monofasico == True)
    elif monofasico == '0':
        query = query.filter(Consulta.monofasico == False)
    if inconsistencia == '1':
        query = query.filter(Consulta.inconsistencia_detectada == True)
    elif inconsistencia == '0':
        query = query.filter(Consulta.inconsistencia_detectada == False)
    if ncm_filtro:
        query = query.filter(Consulta.ncm_consultado.ilike(f'%{ncm_filtro}%'))
    if tipo_filtro:
        query = query.filter(Consulta.tipo_consulta == tipo_filtro)

    consultas = query.order_by(Consulta.created_at.desc()).paginate(page=page, per_page=20)
    empresas = current_user.empresas if not current_user.is_admin else Empresa.query.filter_by(ativo=True).all()

    return render_template('consulta/historico.html',
                           consultas=consultas, empresas=empresas,
                           empresa_id=empresa_id, monofasico=monofasico,
                           inconsistencia=inconsistencia, ncm_filtro=ncm_filtro,
                           tipo_filtro=tipo_filtro)


@consulta_bp.route('/<int:id>')
@login_required
def detalhe(id):
    consulta = db.get_or_404(Consulta, id)
    _checar_acesso_consulta(consulta)
    return render_template('consulta/detalhe.html', consulta=consulta)


@consulta_bp.route('/exportar')
@login_required
def exportar():
    empresa_id = request.args.get('empresa_id', type=int)
    monofasico = request.args.get('monofasico')
    inconsistencia = request.args.get('inconsistencia')

    query = Consulta.query
    if not current_user.is_admin:
        ids = [e.id for e in current_user.empresas]
        query = query.filter(Consulta.empresa_id.in_(ids))
    if empresa_id:
        query = query.filter(Consulta.empresa_id == empresa_id)
    if monofasico == '1':
        query = query.filter(Consulta.monofasico == True)
    elif monofasico == '0':
        query = query.filter(Consulta.monofasico == False)
    if inconsistencia == '1':
        query = query.filter(Consulta.inconsistencia_detectada == True)

    consultas = query.order_by(Consulta.created_at.desc()).all()

    from app.services.export_excel import gerar_excel_consultas
    import io
    output = gerar_excel_consultas(consultas)
    return send_file(output, download_name='tribsync_consultas.xlsx',
                     as_attachment=True, mimetype='application/vnd.openxmlformats-officedocument.spreadsheetml.sheet')
