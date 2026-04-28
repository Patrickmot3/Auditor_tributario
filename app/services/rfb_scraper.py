"""
Serviço de consulta e atualização das tabelas oficiais SPED/RFB.
"""
import logging
import time
from datetime import datetime, timezone, date
import requests
from app.extensions import db
from app.models.ncm import NcmTributario, GrupoTributario
from app.models.base_tributaria import LogAtualizacao

logger = logging.getLogger(__name__)

TABELAS_SPED = {
    '4.3.10': {
        'url_download': 'http://sped.rfb.gov.br/arquivo/download/1638',
        'url_show': 'http://sped.rfb.gov.br/arquivo/show/1638',
        'nome': 'Veículos e Autopeças',
    },
    '4.3.11': {
        'url_download': 'http://sped.rfb.gov.br/arquivo/download/5786',
        'url_show': 'http://sped.rfb.gov.br/arquivo/show/5786',
        'nome': 'Combustíveis',
    },
    '4.3.13': {
        'url_download': 'http://sped.rfb.gov.br/arquivo/download/1643',
        'url_show': 'http://sped.rfb.gov.br/arquivo/show/1643',
        'nome': 'Fármacos e Perfumaria',
    },
    '4.3.15': {
        'url_download': 'http://sped.rfb.gov.br/arquivo/download/1645',
        'url_show': 'http://sped.rfb.gov.br/arquivo/show/1645',
        'nome': 'Bebidas Frias',
    },
}

HEADERS = {
    'User-Agent': 'Mozilla/5.0 (compatible; TribSync/1.0; +https://tribsync.com.br)',
}

MAX_TENTATIVAS = 3
INTERVALO_RETRY = 5


def _get_com_retry(url, tentativas=MAX_TENTATIVAS, stream=False):
    for i in range(tentativas):
        try:
            resp = requests.get(url, headers=HEADERS, timeout=30, stream=stream)
            resp.raise_for_status()
            return resp
        except requests.RequestException as e:
            logger.warning(f'Tentativa {i+1}/{tentativas} falhou para {url}: {e}')
            if i < tentativas - 1:
                time.sleep(INTERVALO_RETRY)
    raise Exception(f'Falha ao acessar {url} após {tentativas} tentativas')


def _checar_versao(tabela_id):
    """Verifica versão atual da tabela na página RFB."""
    info = TABELAS_SPED.get(tabela_id)
    if not info:
        return None
    try:
        resp = _get_com_retry(info['url_show'])
        texto = resp.text
        # Tentar extrair versão do HTML (padrão: "Versão X.XX" ou data)
        import re
        match = re.search(r'Vers[aã]o\s*:?\s*([\d.]+)', texto, re.IGNORECASE)
        if match:
            return match.group(1)
        # Fallback: data de atualização
        match = re.search(r'(\d{2}/\d{2}/\d{4})', texto)
        if match:
            return match.group(1)
    except Exception as e:
        logger.error(f'Erro ao checar versão {tabela_id}: {e}')
    return None


def verificar_atualizacao(tabela_id, executado_por='scheduler_auto'):
    """
    Verifica se há nova versão da tabela SPED.
    Retorna True se houver atualização, False caso contrário.
    """
    versao_rfb = _checar_versao(tabela_id)
    if not versao_rfb:
        return False

    ultimo_log = LogAtualizacao.query.filter(
        LogAtualizacao.tabela_sped == tabela_id,
        LogAtualizacao.status.in_(['sucesso', 'seed_inicial']),
    ).order_by(LogAtualizacao.data_importacao.desc()).first()

    versao_atual = ultimo_log.versao if ultimo_log else None

    if versao_atual == versao_rfb:
        log = LogAtualizacao(
            tabela_sped=tabela_id,
            versao=versao_rfb,
            data_importacao=datetime.now(timezone.utc),
            status='sem_alteracoes',
            mensagem=f'Tabela {tabela_id} já está na versão {versao_rfb}',
            executado_por=executado_por,
        )
        db.session.add(log)
        db.session.commit()
        return False

    return True


def atualizar_tabela(tabela_id, executado_por='scheduler_auto'):
    """
    Baixa e processa a tabela SPED, atualizando ncms_tributarios.
    """
    info = TABELAS_SPED.get(tabela_id)
    if not info:
        return {'erro': f'Tabela {tabela_id} não configurada'}

    versao_rfb = _checar_versao(tabela_id)
    inseridos = 0
    atualizados = 0
    status = 'erro'
    mensagem = ''

    try:
        resp = _get_com_retry(info['url_download'], stream=True)
        conteudo = resp.content

        # Tentar parsear como DOCX
        inseridos, atualizados = _processar_docx(conteudo, tabela_id)
        status = 'sucesso'
        mensagem = f'Tabela {tabela_id} atualizada. Inseridos: {inseridos}, Atualizados: {atualizados}'

    except Exception as e:
        status = 'erro'
        mensagem = str(e)
        logger.error(f'Erro ao atualizar tabela {tabela_id}: {e}')

    log = LogAtualizacao(
        tabela_sped=tabela_id,
        versao=versao_rfb,
        data_atualizacao_rfb=date.today(),
        data_importacao=datetime.now(timezone.utc),
        status=status,
        registros_inseridos=inseridos,
        registros_atualizados=atualizados,
        mensagem=mensagem,
        executado_por=executado_por,
    )
    db.session.add(log)
    db.session.commit()

    return {
        'status': status,
        'inseridos': inseridos,
        'atualizados': atualizados,
        'mensagem': mensagem,
    }


def _processar_docx(conteudo_bytes, tabela_id):
    """Extrai NCMs de arquivo DOCX da RFB."""
    import io
    from docx import Document
    import re

    inseridos = 0
    atualizados = 0

    grupo = GrupoTributario.query.filter_by(tabela_sped=tabela_id).first()
    if not grupo:
        raise Exception(f'Grupo tributário para tabela {tabela_id} não encontrado no banco')

    try:
        doc = Document(io.BytesIO(conteudo_bytes))
    except Exception as e:
        raise Exception(f'Erro ao abrir DOCX: {e}')

    for tabela in doc.tables:
        for linha in tabela.rows:
            celulas = [c.text.strip() for c in linha.cells]
            if len(celulas) < 2:
                continue

            # Extrair NCM da primeira célula
            ncm_raw = celulas[0].replace('.', '').replace('-', '').strip()
            if not re.match(r'^\d{4,10}$', ncm_raw):
                continue

            descricao = celulas[1] if len(celulas) > 1 else ''
            tipo_ref = 'ncm_exato' if len(ncm_raw) == 8 else f'posicao_{len(ncm_raw)}'

            existente = NcmTributario.query.filter_by(
                ncm=ncm_raw,
                grupo_tributario_id=grupo.id,
            ).first()

            if existente:
                existente.descricao = descricao
                existente.updated_at = datetime.now(timezone.utc)
                atualizados += 1
            else:
                novo = NcmTributario(
                    ncm=ncm_raw,
                    descricao=descricao,
                    grupo_tributario_id=grupo.id,
                    monofasico=True,
                    tipo_referencia=tipo_ref,
                    lei=grupo.lei_base,
                    cst_entrada='70',
                    cst_saida='04',
                    cfop_entrada_simples='1102',
                    cfop_saida_simples='5102',
                    pis_aliquota_fabricante=1.5,
                    cofins_aliquota_fabricante=7.0,
                    pis_aliquota_varejista=0.0,
                    cofins_aliquota_varejista=0.0,
                    vigencia_inicio=date.today(),
                    fonte_url=TABELAS_SPED[tabela_id]['url_download'],
                    ativo=True,
                )
                db.session.add(novo)
                inseridos += 1

    db.session.commit()
    return inseridos, atualizados
