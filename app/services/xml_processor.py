"""
Serviço de importação de XML NF-e (versão 4.00).
"""
import logging
from datetime import datetime, timezone
from xml.etree import ElementTree as ET
from app.extensions import db
from app.models.consulta import LoteConsulta, LoteItem, Consulta
from app.services.ncm_validator import validar_ncm, _normalizar_ncm

logger = logging.getLogger(__name__)

NS = {'nfe': 'http://www.portalfiscal.inf.br/nfe'}


def _tag(elemento, nome):
    el = elemento.find(f'nfe:{nome}', NS)
    if el is None:
        el = elemento.find(nome)
    return el.text.strip() if el is not None and el.text else ''


def processar_xml_nfe(caminho_arquivo, empresa_id):
    """
    Processa XML de NF-e e valida NCMs dos produtos.
    Retorna dict com dados da nota e resumo.
    """
    try:
        tree = ET.parse(caminho_arquivo)
        root = tree.getroot()
    except Exception as e:
        return {'erro': f'Erro ao ler XML: {e}'}

    # Localizar nfeProc ou nfe raiz
    nfe = root.find('.//nfe:NFe', NS)
    if nfe is None:
        nfe = root.find('.//NFe')
    if nfe is None:
        nfe = root

    inf_nfe = nfe.find('nfe:infNFe', NS) or nfe.find('infNFe') or nfe

    # Dados da nota
    ch_nfe = inf_nfe.get('Id', '').replace('NFe', '') if inf_nfe.get('Id') else ''
    ide = inf_nfe.find('nfe:ide', NS) or inf_nfe.find('ide')
    emit = inf_nfe.find('nfe:emit', NS) or inf_nfe.find('emit')

    data_emissao = _tag(ide, 'dhEmi') or _tag(ide, 'dEmi') if ide is not None else ''
    cnpj_emit = _tag(emit, 'CNPJ') if emit is not None else ''
    razao_emit = _tag(emit, 'xNome') if emit is not None else ''

    dets = inf_nfe.findall('nfe:det', NS) or inf_nfe.findall('det')

    lote = LoteConsulta(
        empresa_id=empresa_id,
        nome_lote=f'NF-e {ch_nfe[:10]}...' if ch_nfe else 'XML NF-e',
        tipo='xml_nfe',
        status='processando',
    )
    db.session.add(lote)
    db.session.commit()

    total = 0
    ok = 0
    duplicados = 0
    erros = 0
    monofasicos = 0
    nao_monofasicos = 0
    inconsistencias = 0

    itens_resultado = []

    for det in dets:
        prod = det.find('nfe:prod', NS) or det.find('prod')
        if prod is None:
            continue

        ncm_raw = _tag(prod, 'NCM')
        ncm_limpo = _normalizar_ncm(ncm_raw)
        if not ncm_limpo:
            continue

        total += 1
        c_prod = _tag(prod, 'cProd')
        x_prod = _tag(prod, 'xProd')
        cest = _tag(prod, 'CEST')

        # CST atual da NF-e
        imposto = det.find('nfe:imposto', NS) or det.find('imposto')
        cst_atual = None
        if imposto:
            pis_el = imposto.find('.//nfe:CST', NS) or imposto.find('.//CST')
            if pis_el is not None:
                cst_atual = pis_el.text.strip()

        existente = Consulta.query.filter_by(
            empresa_id=empresa_id, ncm_consultado=ncm_limpo
        ).first()
        status_item = 'duplicado' if existente else 'ok'

        try:
            resultado = validar_ncm(ncm_limpo, empresa_id, cst_atual)

            consulta = Consulta.query.filter_by(
                empresa_id=empresa_id, ncm_consultado=ncm_limpo
            ).first()
            if consulta:
                consulta.tipo_consulta = 'xml_nfe'
                consulta.origem = 'xml'
                if x_prod:
                    consulta.descricao_produto = x_prod
                if c_prod:
                    consulta.codigo_produto = c_prod
                if cest:
                    consulta.codigo_cest = cest
                db.session.commit()

            item = LoteItem(
                lote_id=lote.id,
                consulta_id=consulta.id if consulta else None,
                linha_original=total,
                ncm=ncm_limpo,
                descricao=x_prod,
                codigo_produto=c_prod,
                codigo_cest=cest,
                status_processamento=status_item,
            )
            db.session.add(item)

            if status_item == 'duplicado':
                duplicados += 1
            else:
                ok += 1

            if resultado.get('monofasico'):
                monofasicos += 1
            else:
                nao_monofasicos += 1

            if resultado.get('inconsistencia_detectada'):
                inconsistencias += 1

            itens_resultado.append({
                'ncm': ncm_limpo,
                'descricao': x_prod,
                'codigo': c_prod,
                'cst_atual': cst_atual,
                'monofasico': resultado.get('monofasico'),
                'cst_sugerido': resultado.get('cst_sugerido'),
                'inconsistencia': resultado.get('inconsistencia_detectada'),
                'grupo': resultado.get('grupo'),
            })

        except Exception as e:
            logger.error(f'Erro ao processar NCM {ncm_limpo}: {e}')
            item = LoteItem(
                lote_id=lote.id,
                linha_original=total,
                ncm=ncm_limpo,
                descricao=x_prod,
                status_processamento='erro',
                mensagem_erro=str(e)[:300],
            )
            db.session.add(item)
            erros += 1
            db.session.rollback()

    lote.total_itens = total
    lote.itens_monofasicos = monofasicos
    lote.itens_nao_monofasicos = nao_monofasicos
    lote.itens_com_inconsistencia = inconsistencias
    lote.status = 'concluido'
    lote.concluido_at = datetime.now(timezone.utc)
    db.session.commit()

    return {
        'lote_id': lote.id,
        'ch_nfe': ch_nfe,
        'cnpj_emitente': cnpj_emit,
        'razao_emitente': razao_emit,
        'data_emissao': data_emissao,
        'total': total,
        'ok': ok,
        'duplicados': duplicados,
        'erros': erros,
        'monofasicos': monofasicos,
        'nao_monofasicos': nao_monofasicos,
        'inconsistencias': inconsistencias,
        'itens': itens_resultado,
    }
