import os
from flask import (Blueprint, render_template, redirect, url_for,
                   flash, request, session, current_app, send_file, abort)
from flask_login import login_required, current_user
from app.extensions import db
from app.models.empresa import Empresa
from app.models.consulta import Consulta, LoteConsulta, LoteItem, RevisaoLog
from app.services.ncm_validator import validar_ncm, _normalizar_ncm, CST_DESCRICAO, derivar_cfop


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


def _aplicar_critica_cnae(relatorio, empresa):
    """Anota critica_cnae em cada item e totaliza por nota e por relatorio."""
    from app.services.cnae_segmento import validar_ncm_vs_empresa as _validar

    total_criticas = total_alertas = 0

    def _anotar(itens):
        c = a = 0
        for it in itens:
            v = _validar(it, empresa)
            it['critica_cnae'] = v
            if v['severidade'] == 'CRITICA':
                c += 1
            elif v['severidade'] == 'ALERTA':
                a += 1
        return c, a

    if 'notas' in relatorio:
        for nota in relatorio['notas']:
            c, a = _anotar(nota.get('itens') or [])
            nota['criticas_cnae'] = c
            nota['alertas_cnae'] = a
            total_criticas += c
            total_alertas += a
    elif 'itens' in relatorio:
        total_criticas, total_alertas = _anotar(relatorio.get('itens') or [])
        relatorio['criticas_cnae'] = total_criticas
        relatorio['alertas_cnae'] = total_alertas

    relatorio['total_criticas_cnae'] = total_criticas
    relatorio['total_alertas_cnae'] = total_alertas
    return relatorio


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
    destino  = 'interna'
    tem_st   = False
    natureza = 'revendedor'

    if request.method == 'POST':
        ncm       = request.form.get('ncm', '').strip()
        cst_atual = request.form.get('cst_atual', '').strip() or None
        empresa_id = request.form.get('empresa_id', type=int)
        destino   = request.form.get('destino', 'interna')
        tem_st    = request.form.get('icms_st') == 'com_st'
        natureza  = request.form.get('natureza', 'revendedor')

        if not empresa_id:
            flash('Selecione uma empresa antes de consultar.', 'warning')
        elif not ncm:
            flash('Informe o NCM.', 'warning')
        else:
            session['empresa_id'] = empresa_id
            empresa = db.session.get(Empresa, empresa_id)
            resultado = validar_ncm(ncm, empresa_id, cst_atual)
            if resultado and 'erro' not in resultado:
                resultado['cfop_sugerido'] = derivar_cfop(
                    resultado.get('grupo'), destino, tem_st
                )

    empresas = current_user.empresas if not current_user.is_admin else Empresa.query.filter_by(ativo=True).all()
    return render_template('consulta/individual.html',
                           empresa=empresa, resultado=resultado, empresas=empresas,
                           destino=destino, tem_st=tem_st, natureza=natureza)


@consulta_bp.route('/lote/manual', methods=['POST'])
@login_required
def lote_manual():
    empresa_id = request.form.get('empresa_id', type=int)
    ncms_raw   = request.form.get('ncms', '')
    destino    = request.form.get('destino', 'interna')
    tem_st     = request.form.get('icms_st') == 'com_st'
    natureza   = request.form.get('natureza', 'revendedor')

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
        if 'erro' not in res:
            res['cfop_sugerido'] = derivar_cfop(res.get('grupo'), destino, tem_st)
        resultados.append(res)

    empresa  = db.session.get(Empresa, empresa_id)
    empresas = current_user.empresas if not current_user.is_admin else Empresa.query.filter_by(ativo=True).all()
    return render_template('consulta/lote_resultado.html',
                           empresa=empresa, resultados=resultados, empresas=empresas,
                           cst_descricao=CST_DESCRICAO,
                           destino=destino, tem_st=tem_st, natureza=natureza)


@consulta_bp.route('/lote/excel/modelo')
@login_required
def modelo_excel():
    from app.services.export_excel import gerar_template_importacao
    output = gerar_template_importacao()
    return send_file(output, download_name='tribsync_modelo_importacao.xlsx',
                     as_attachment=True,
                     mimetype='application/vnd.openxmlformats-officedocument.spreadsheetml.sheet')


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

        _aplicar_critica_cnae(relatorio, empresa)
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
        if not empresa_id:
            flash('Selecione uma empresa.', 'warning')
            return render_template('consulta/lote_xml.html', empresa=empresa, empresas=empresas)

        session['empresa_id'] = empresa_id
        empresa = db.session.get(Empresa, empresa_id)
        upload_dir = current_app.config.get('UPLOAD_FOLDER', 'uploads')
        os.makedirs(upload_dir, exist_ok=True)

        from app.services.xml_processor import (
            processar_xml_nfe, processar_lote_compactado, _processar_xml_bytes,
        )

        # ── Modo 1: múltiplos XMLs selecionados diretamente ──────────────────
        arquivos_xml = request.files.getlist('xmls')
        arquivos_xml = [f for f in arquivos_xml if f and f.filename.lower().endswith('.xml')]

        if arquivos_xml:
            total = ok = duplicados = erros = monofasicos = nao_monofasicos = inconsistencias = 0
            notas = []
            for arq in arquivos_xml:
                conteudo = arq.read()
                try:
                    res = _processar_xml_bytes(conteudo, empresa_id)
                except Exception as e:
                    res = {'erro': str(e), 'total': 0, 'ok': 0, 'duplicados': 0,
                           'erros': 1, 'monofasicos': 0, 'nao_monofasicos': 0,
                           'inconsistencias': 0}
                total           += res.get('total', 0)
                ok              += res.get('ok', 0)
                duplicados      += res.get('duplicados', 0)
                erros           += res.get('erros', 0)
                monofasicos     += res.get('monofasicos', 0)
                nao_monofasicos += res.get('nao_monofasicos', 0)
                inconsistencias += res.get('inconsistencias', 0)
                notas.append({
                    'arquivo': arq.filename,
                    'lote_id': res.get('lote_id'),
                    'ch_nfe': res.get('ch_nfe', ''),
                    'n_nf': res.get('n_nf', ''),
                    'serie': res.get('serie', ''),
                    'razao_emitente': res.get('razao_emitente', ''),
                    'cnpj_emitente': res.get('cnpj_emitente', ''),
                    'data_emissao': res.get('data_emissao', ''),
                    'total': res.get('total', 0),
                    'monofasicos': res.get('monofasicos', 0),
                    'inconsistencias': res.get('inconsistencias', 0),
                    'erro': res.get('erro'),
                    'itens': res.get('itens', []),
                })
            lote_ids = [n['lote_id'] for n in notas if n.get('lote_id')]
            relatorio = {
                'arquivo_origem': f'{len(arquivos_xml)} arquivo(s) XML',
                'total_arquivos': len(arquivos_xml),
                'total': total, 'ok': ok, 'duplicados': duplicados, 'erros': erros,
                'monofasicos': monofasicos, 'nao_monofasicos': nao_monofasicos,
                'inconsistencias': inconsistencias, 'notas': notas,
                'lote_ids': lote_ids,
            }
            _aplicar_critica_cnae(relatorio, empresa)
            return render_template('consulta/lote_relatorio.html',
                                   empresa=empresa, relatorio=relatorio, tipo='xml_lote')

        # ── Modo 2: ZIP (ou XML único) ────────────────────────────────────────
        arquivo = request.files.get('arquivo')
        if not arquivo or not arquivo.filename:
            flash('Selecione os arquivos XML ou um ZIP.', 'warning')
            return render_template('consulta/lote_xml.html', empresa=empresa, empresas=empresas)

        nome_arquivo = os.path.basename(arquivo.filename)
        ext = nome_arquivo.rsplit('.', 1)[-1].lower() if '.' in nome_arquivo else ''
        caminho = os.path.join(upload_dir, nome_arquivo)
        arquivo.save(caminho)

        try:
            if ext == 'xml':
                relatorio = processar_xml_nfe(caminho, empresa_id)
                tipo_rel = 'xml'
            elif ext == 'zip':
                relatorio = processar_lote_compactado(caminho, empresa_id, nome_arquivo)
                tipo_rel = 'xml_lote'
            else:
                flash('Formato não suportado. Use XML(s) ou ZIP.', 'danger')
                return render_template('consulta/lote_xml.html', empresa=empresa, empresas=empresas)
        finally:
            if os.path.exists(caminho):
                os.remove(caminho)

        if 'erro' in relatorio:
            flash(f'Erro ao processar: {relatorio["erro"]}', 'danger')
            return render_template('consulta/lote_xml.html', empresa=empresa, empresas=empresas)

        _aplicar_critica_cnae(relatorio, empresa)
        return render_template('consulta/lote_relatorio.html',
                               empresa=empresa, relatorio=relatorio, tipo=tipo_rel)

    return render_template('consulta/lote_xml.html', empresa=empresa, empresas=empresas)


@consulta_bp.route('/historico')
@login_required
def historico():
    from datetime import datetime as _dt
    page = request.args.get('page', 1, type=int)
    empresa_id = request.args.get('empresa_id', type=int)
    monofasico = request.args.get('monofasico')
    inconsistencia = request.args.get('inconsistencia')
    ncm_filtro = request.args.get('ncm', '').strip()
    tipo_filtro = request.args.get('tipo')
    data_nf_de  = request.args.get('data_nf_de', '').strip()
    data_nf_ate = request.args.get('data_nf_ate', '').strip()

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
    if data_nf_de or data_nf_ate:
        subq = db.session.query(LoteItem.consulta_id).distinct()
        if data_nf_de:
            try:
                subq = subq.filter(LoteItem.data_nf >= _dt.strptime(data_nf_de, '%Y-%m-%d').date())
            except ValueError:
                pass
        if data_nf_ate:
            try:
                subq = subq.filter(LoteItem.data_nf <= _dt.strptime(data_nf_ate, '%Y-%m-%d').date())
            except ValueError:
                pass
        query = query.filter(Consulta.id.in_(subq))

    consultas = query.order_by(Consulta.created_at.desc()).paginate(page=page, per_page=20)
    empresas = current_user.empresas if not current_user.is_admin else Empresa.query.filter_by(ativo=True).all()

    from sqlalchemy import func as _func
    consulta_ids = [c.id for c in consultas.items]
    lote_item_map = {}
    if consulta_ids:
        rows = (db.session.query(
                    LoteItem.consulta_id,
                    _func.max(LoteItem.data_nf).label('data_nf'),
                    _func.sum(LoteItem.valor_item).label('total_valor'))
                .filter(LoteItem.consulta_id.in_(consulta_ids))
                .group_by(LoteItem.consulta_id)
                .all())
        lote_item_map = {r.consulta_id: {'data_nf': r.data_nf, 'valor_item': r.total_valor}
                         for r in rows}

    from app.services.ncm_validator import CST_DESCRICAO
    return render_template('consulta/historico.html',
                           consultas=consultas, empresas=empresas,
                           empresa_id=empresa_id, monofasico=monofasico,
                           inconsistencia=inconsistencia, ncm_filtro=ncm_filtro,
                           tipo_filtro=tipo_filtro,
                           data_nf_de=data_nf_de, data_nf_ate=data_nf_ate,
                           lote_item_map=lote_item_map,
                           cst_descricao=CST_DESCRICAO)


@consulta_bp.route('/revisao')
@login_required
def revisao():
    aba = request.args.get('aba', 'pendente')
    empresa_id = request.args.get('empresa_id', type=int)

    from sqlalchemy import or_, and_

    base = Consulta.query.join(Empresa, Consulta.empresa_id == Empresa.id)
    if not current_user.is_admin:
        ids = [e.id for e in current_user.empresas]
        base = base.filter(Consulta.empresa_id.in_(ids))
    if empresa_id:
        base = base.filter(Consulta.empresa_id == empresa_id)

    # Simples Nacional → apenas monofásico (02/03/04) e ST (05)
    # Outros regimes  → tudo com Grupo Tributário preenchido
    filtro_regime = or_(
        and_(Empresa.regime_tributario == 'simples_nacional',
             Consulta.cst_sugerido.in_(('02', '03', '04', '05'))),
        and_(Empresa.regime_tributario != 'simples_nacional',
             Consulta.grupo_tributario.isnot(None),
             Consulta.grupo_tributario != ''),
    )
    base = base.filter(filtro_regime)

    pendentes        = base.filter(Consulta.status_revisao == 'pendente').order_by(Consulta.created_at.desc()).all()
    aceitos          = base.filter(Consulta.status_revisao == 'aceito').order_by(Consulta.revisado_em.desc()).all()
    aceitos_ressalva = base.filter(Consulta.status_revisao == 'aceito_ressalva').order_by(Consulta.revisado_em.desc()).all()
    recusados        = base.filter(Consulta.status_revisao == 'recusado').order_by(Consulta.revisado_em.desc()).all()

    log_q = RevisaoLog.query.order_by(RevisaoLog.criado_em.desc())
    if not current_user.is_admin:
        ids = [e.id for e in current_user.empresas]
        log_q = log_q.join(Consulta, RevisaoLog.consulta_id == Consulta.id).filter(Consulta.empresa_id.in_(ids))
    historico = log_q.limit(300).all()

    empresas = current_user.empresas if not current_user.is_admin else Empresa.query.filter_by(ativo=True).all()

    return render_template('consulta/revisao.html',
                           pendentes=pendentes, aceitos=aceitos,
                           aceitos_ressalva=aceitos_ressalva, recusados=recusados,
                           historico=historico, aba=aba,
                           empresa_id=empresa_id, empresas=empresas)


@consulta_bp.route('/revisao/exportar')
@login_required
def revisao_exportar():
    from sqlalchemy import or_, and_
    aba        = request.args.get('aba', 'aceito')
    empresa_id = request.args.get('empresa_id', type=int)

    base = Consulta.query.join(Empresa, Consulta.empresa_id == Empresa.id)
    if not current_user.is_admin:
        ids = [e.id for e in current_user.empresas]
        base = base.filter(Consulta.empresa_id.in_(ids))
    if empresa_id:
        base = base.filter(Consulta.empresa_id == empresa_id)

    filtro_regime = or_(
        and_(Empresa.regime_tributario == 'simples_nacional',
             Consulta.cst_sugerido.in_(('02', '03', '04', '05'))),
        and_(Empresa.regime_tributario != 'simples_nacional',
             Consulta.grupo_tributario.isnot(None),
             Consulta.grupo_tributario != ''),
    )

    status_map  = {'aceito': 'aceito', 'aceito_ressalva': 'aceito_ressalva', 'recusado': 'recusado'}
    status_rev  = status_map.get(aba, 'aceito')
    labels_exp  = {'aceito': 'Aceitos', 'aceito_ressalva': 'Aceitos c Ressalva', 'recusado': 'Recusados'}

    consultas = (base.filter(filtro_regime, Consulta.status_revisao == status_rev)
                 .order_by(Consulta.ncm_consultado).all())

    from app.services.export_excel import gerar_excel_revisao
    output = gerar_excel_revisao(consultas, labels_exp.get(aba, 'Revisão'))
    nome   = f'tribsync_revisao_{aba}.xlsx'
    return send_file(output, download_name=nome, as_attachment=True,
                     mimetype='application/vnd.openxmlformats-officedocument.spreadsheetml.sheet')


@consulta_bp.route('/revisao/acao', methods=['POST'])
@login_required
def revisao_acao():
    from datetime import datetime as _dt
    import pytz as _pytz

    acao     = request.form.get('acao', '').strip()
    motivo   = request.form.get('motivo', '').strip()
    ids_raw  = request.form.getlist('consulta_ids')
    cons_ids = [int(x) for x in ids_raw if x.strip().isdigit()]

    status_map = {'aceitar': 'aceito', 'aceitar_ressalva': 'aceito_ressalva', 'recusar': 'recusado',
                  'reverter': 'pendente'}
    novo_status = status_map.get(acao)

    if not novo_status or not cons_ids:
        flash('Nenhum item selecionado ou ação inválida.', 'warning')
        return redirect(url_for('consulta.revisao'))

    if acao in ('recusar', 'aceitar_ressalva') and not motivo:
        flash('Informe o motivo antes de continuar.', 'warning')
        return redirect(url_for('consulta.revisao'))

    ids_autorizados = {e.id for e in current_user.empresas} if not current_user.is_admin else None
    agora = _dt.now(_pytz.timezone('America/Sao_Paulo'))

    consultas = Consulta.query.filter(Consulta.id.in_(cons_ids)).all()
    atualizados = 0
    for c in consultas:
        if ids_autorizados and c.empresa_id not in ids_autorizados:
            continue
        log = RevisaoLog(
            consulta_id=c.id,
            usuario_id=current_user.id,
            status_anterior=c.status_revisao,
            status_novo=novo_status,
            motivo=motivo or None,
            criado_em=agora,
        )
        db.session.add(log)
        c.status_revisao  = novo_status
        c.revisado_por_id = current_user.id
        c.revisado_em     = agora
        c.motivo_revisao  = motivo or None
        atualizados += 1

    db.session.commit()

    labels = {'aceito': 'aceitos', 'aceito_ressalva': 'aceitos com ressalva',
              'recusado': 'recusados', 'pendente': 'revertidos para pendente'}
    flash(f'{atualizados} item(s) {labels.get(novo_status, novo_status)}.', 'success')

    aba_dest = {'aceito': 'aceito', 'aceito_ressalva': 'aceito_ressalva',
                'recusado': 'recusado', 'pendente': 'pendente'}
    return redirect(url_for('consulta.revisao', aba=aba_dest.get(novo_status, 'pendente')))


@consulta_bp.route('/<int:id>')
@login_required
def detalhe(id):
    consulta = db.get_or_404(Consulta, id)
    _checar_acesso_consulta(consulta)
    return render_template('consulta/detalhe.html', consulta=consulta)


@consulta_bp.route('/exportar')
@login_required
def exportar():
    from datetime import datetime as _dt
    empresa_id = request.args.get('empresa_id', type=int)
    monofasico = request.args.get('monofasico')
    inconsistencia = request.args.get('inconsistencia')
    lote_id = request.args.get('lote_id', type=int)
    lote_ids_str = request.args.get('lote_ids', '')
    data_nf_de  = request.args.get('data_nf_de', '').strip()
    data_nf_ate = request.args.get('data_nf_ate', '').strip()

    # Montar lista de lote_ids quando vindo da tela de resultado de lote
    lote_ids = []
    if lote_id:
        lote_ids = [lote_id]
    elif lote_ids_str:
        lote_ids = [int(x) for x in lote_ids_str.split(',') if x.strip().isdigit()]

    query = Consulta.query
    if not current_user.is_admin:
        ids = [e.id for e in current_user.empresas]
        query = query.filter(Consulta.empresa_id.in_(ids))

    if lote_ids:
        # Exportar lote linha-a-linha via LoteItem — preserva NCMs duplicados com
        # descrições diferentes que seriam colapsados na tabela Consulta
        from app.services.export_excel import gerar_excel_lote_items
        output = gerar_excel_lote_items(lote_ids)
        return send_file(output, download_name='tribsync_lote.xlsx',
                         as_attachment=True,
                         mimetype='application/vnd.openxmlformats-officedocument.spreadsheetml.sheet')

    if empresa_id:
        query = query.filter(Consulta.empresa_id == empresa_id)
    if monofasico == '1':
        query = query.filter(Consulta.monofasico == True)
    elif monofasico == '0':
        query = query.filter(Consulta.monofasico == False)
    if inconsistencia == '1':
        query = query.filter(Consulta.inconsistencia_detectada == True)
    if data_nf_de or data_nf_ate:
        subq = db.session.query(LoteItem.consulta_id).distinct()
        if data_nf_de:
            try:
                subq = subq.filter(LoteItem.data_nf >= _dt.strptime(data_nf_de, '%Y-%m-%d').date())
            except ValueError:
                pass
        if data_nf_ate:
            try:
                subq = subq.filter(LoteItem.data_nf <= _dt.strptime(data_nf_ate, '%Y-%m-%d').date())
            except ValueError:
                pass
        query = query.filter(Consulta.id.in_(subq))

    consultas = query.order_by(Consulta.created_at.desc()).all()

    from app.services.export_excel import gerar_excel_consultas
    output = gerar_excel_consultas(consultas)
    return send_file(output, download_name='tribsync_consultas.xlsx',
                     as_attachment=True, mimetype='application/vnd.openxmlformats-officedocument.spreadsheetml.sheet')
