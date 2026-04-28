"""
Serviço de consulta e atualização das tabelas oficiais SPED/RFB.
Detecta automaticamente o formato do arquivo (DOCX, XLSX ou HTML).
"""
import io
import logging
import re
import time
import zipfile
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
    'User-Agent': 'Mozilla/5.0 (compatible; TribSync/1.0)',
}
MAX_TENTATIVAS = 3
INTERVALO_RETRY = 5


# ─── HTTP ─────────────────────────────────────────────────────────────────────

def _get_com_retry(url, tentativas=MAX_TENTATIVAS):
    for i in range(tentativas):
        try:
            resp = requests.get(url, headers=HEADERS, timeout=30)
            resp.raise_for_status()
            return resp
        except requests.RequestException as e:
            logger.warning(f'Tentativa {i+1}/{tentativas} falhou: {url} — {e}')
            if i < tentativas - 1:
                time.sleep(INTERVALO_RETRY)
    raise Exception(f'Falha ao acessar {url} após {tentativas} tentativas')


# ─── Detecção de formato ──────────────────────────────────────────────────────

def _detectar_formato(conteudo: bytes, content_type: str) -> str:
    """
    Detecta o formato do arquivo retornado pela RFB.
    Lê [Content_Types].xml dentro do ZIP para identificação definitiva.
    Retorna: 'docx', 'xlsx', 'html' ou 'desconhecido'.
    """
    ct = content_type.lower()

    # Arquivo ZIP (magic bytes PK) → DOCX ou XLSX
    if conteudo[:2] == b'PK':
        try:
            with zipfile.ZipFile(io.BytesIO(conteudo)) as z:
                # Fonte mais confiável: [Content_Types].xml declara o tipo real
                if '[Content_Types].xml' in z.namelist():
                    ct_xml = z.read('[Content_Types].xml').decode('utf-8', errors='ignore')
                    if 'wordprocessingml' in ct_xml:
                        return 'docx'
                    if 'spreadsheetml' in ct_xml:
                        return 'xlsx'
                # Fallback por estrutura de pastas
                nomes = z.namelist()
                if any('xl/worksheets' in n or 'xl/workbook' in n for n in nomes):
                    return 'xlsx'
                if any('word/document' in n for n in nomes):
                    return 'docx'
        except Exception as e:
            logger.warning(f'Erro ao inspecionar ZIP: {e}')

    # Content-Type do servidor como segundo critério
    if 'spreadsheet' in ct or 'excel' in ct or 'xlsx' in ct or 'xls' in ct:
        return 'xlsx'
    if 'word' in ct or 'docx' in ct or 'msword' in ct:
        return 'docx'
    if 'html' in ct or 'text/plain' in ct:
        return 'html'

    # Tentar pelo conteúdo textual
    try:
        texto = conteudo[:200].decode('utf-8', errors='ignore').lower()
        if '<html' in texto or '<!doctype' in texto:
            return 'html'
    except Exception:
        pass

    return 'desconhecido'


# ─── Parsers ──────────────────────────────────────────────────────────────────

def _extrair_ncms_docx(conteudo: bytes) -> list[tuple[str, str]]:
    """Extrai pares (ncm, descricao) de arquivo DOCX."""
    from docx import Document
    doc = Document(io.BytesIO(conteudo))
    resultado = []
    for tabela in doc.tables:
        for linha in tabela.rows:
            celulas = [c.text.strip() for c in linha.cells]
            if len(celulas) < 2:
                continue
            ncm_raw = celulas[0].replace('.', '').replace('-', '').strip()
            if re.match(r'^\d{4,10}$', ncm_raw):
                resultado.append((ncm_raw, celulas[1]))
    # Também varrer parágrafos para NCMs em texto corrido
    for para in doc.paragraphs:
        match = re.match(r'^(\d[\d.]{3,})\s+(.*)', para.text.strip())
        if match:
            ncm_raw = match.group(1).replace('.', '').replace('-', '').strip()
            if re.match(r'^\d{4,10}$', ncm_raw):
                resultado.append((ncm_raw, match.group(2).strip()))
    return resultado


def _extrair_ncms_xlsx(conteudo: bytes) -> list[tuple[str, str]]:
    """Extrai pares (ncm, descricao) de arquivo XLSX."""
    import openpyxl
    wb = openpyxl.load_workbook(io.BytesIO(conteudo), read_only=True, data_only=True)
    resultado = []
    for ws in wb.worksheets:
        for row in ws.iter_rows(values_only=True):
            if not row or row[0] is None:
                continue
            ncm_raw = str(row[0]).replace('.', '').replace('-', '').strip()
            if re.match(r'^\d{4,10}$', ncm_raw):
                descricao = str(row[1]).strip() if len(row) > 1 and row[1] else ''
                resultado.append((ncm_raw, descricao))
    return resultado


def _extrair_ncms_html(conteudo: bytes) -> list[tuple[str, str]]:
    """Extrai pares (ncm, descricao) de HTML com tabelas."""
    from bs4 import BeautifulSoup
    soup = BeautifulSoup(conteudo, 'lxml')
    resultado = []
    for tr in soup.find_all('tr'):
        tds = [td.get_text(strip=True) for td in tr.find_all(['td', 'th'])]
        if len(tds) < 2:
            continue
        ncm_raw = tds[0].replace('.', '').replace('-', '').strip()
        if re.match(r'^\d{4,10}$', ncm_raw):
            resultado.append((ncm_raw, tds[1]))
    return resultado


# ─── Persistência ─────────────────────────────────────────────────────────────

def _salvar_ncms(pares: list[tuple[str, str]], tabela_id: str, grupo) -> tuple[int, int]:
    inseridos = atualizados = 0
    for ncm_raw, descricao in pares:
        tipo_ref = 'ncm_exato' if len(ncm_raw) == 8 else f'posicao_{len(ncm_raw)}'
        existente = NcmTributario.query.filter_by(
            ncm=ncm_raw, grupo_tributario_id=grupo.id,
        ).first()
        if existente:
            existente.descricao = descricao
            existente.updated_at = datetime.now(timezone.utc)
            atualizados += 1
        else:
            db.session.add(NcmTributario(
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
            ))
            inseridos += 1
    db.session.commit()
    return inseridos, atualizados


# ─── API pública ──────────────────────────────────────────────────────────────

def _checar_versao(tabela_id):
    info = TABELAS_SPED.get(tabela_id)
    if not info:
        return None
    try:
        resp = _get_com_retry(info['url_show'])
        match = re.search(r'Vers[aã]o\s*:?\s*([\d.]+)', resp.text, re.IGNORECASE)
        if match:
            return match.group(1)
        match = re.search(r'(\d{2}/\d{2}/\d{4})', resp.text)
        if match:
            return match.group(1)
    except Exception as e:
        logger.error(f'Erro ao checar versão {tabela_id}: {e}')
    return None


def verificar_atualizacao(tabela_id, executado_por='scheduler_auto'):
    versao_rfb = _checar_versao(tabela_id)
    if not versao_rfb:
        return False

    ultimo = LogAtualizacao.query.filter(
        LogAtualizacao.tabela_sped == tabela_id,
        LogAtualizacao.status.in_(['sucesso', 'seed_inicial']),
    ).order_by(LogAtualizacao.data_importacao.desc()).first()

    if ultimo and ultimo.versao == versao_rfb:
        db.session.add(LogAtualizacao(
            tabela_sped=tabela_id, versao=versao_rfb,
            data_importacao=datetime.now(timezone.utc),
            status='sem_alteracoes',
            mensagem=f'Tabela {tabela_id} já está na versão {versao_rfb}',
            executado_por=executado_por,
        ))
        db.session.commit()
        return False
    return True


def atualizar_tabela(tabela_id, executado_por='scheduler_auto'):
    info = TABELAS_SPED.get(tabela_id)
    if not info:
        return {'erro': f'Tabela {tabela_id} não configurada'}

    versao_rfb = _checar_versao(tabela_id)
    inseridos = atualizados = 0
    status = 'erro'
    mensagem = ''

    try:
        grupo = GrupoTributario.query.filter_by(tabela_sped=tabela_id).first()
        if not grupo:
            raise Exception(f'Grupo tributário para tabela {tabela_id} não encontrado')

        resp = _get_com_retry(info['url_download'])
        conteudo = resp.content
        content_type = resp.headers.get('Content-Type', '')
        fmt = _detectar_formato(conteudo, content_type)

        logger.info(f'Tabela {tabela_id}: formato detectado = {fmt} | Content-Type = {content_type}')

        # Ordem de tentativa: formato detectado primeiro, depois os outros
        ordem = {
            'xlsx': [_extrair_ncms_xlsx, _extrair_ncms_docx, _extrair_ncms_html],
            'docx': [_extrair_ncms_docx, _extrair_ncms_xlsx, _extrair_ncms_html],
            'html': [_extrair_ncms_html, _extrair_ncms_xlsx, _extrair_ncms_docx],
        }.get(fmt, [_extrair_ncms_xlsx, _extrair_ncms_docx, _extrair_ncms_html])

        pares = []
        ultimo_erro = None
        for fn in ordem:
            try:
                pares = fn(conteudo)
                if pares:
                    logger.info(f'Tabela {tabela_id}: extraídos {len(pares)} NCMs via {fn.__name__}')
                    break
            except Exception as e:
                ultimo_erro = e
                logger.warning(f'Tabela {tabela_id}: {fn.__name__} falhou — {e}')

        if not pares:
            raise Exception(f'Nenhum NCM extraído da tabela {tabela_id}. Último erro: {ultimo_erro}')

        inseridos, atualizados = _salvar_ncms(pares, tabela_id, grupo)
        status = 'sucesso'
        mensagem = f'Tabela {tabela_id} ({fmt}): {inseridos} inseridos, {atualizados} atualizados'
        logger.info(mensagem)

    except Exception as e:
        status = 'erro'
        mensagem = str(e)
        logger.error(f'Erro ao atualizar tabela {tabela_id}: {e}')

    db.session.add(LogAtualizacao(
        tabela_sped=tabela_id,
        versao=versao_rfb,
        data_atualizacao_rfb=date.today(),
        data_importacao=datetime.now(timezone.utc),
        status=status,
        registros_inseridos=inseridos,
        registros_atualizados=atualizados,
        mensagem=mensagem,
        executado_por=executado_por,
    ))
    db.session.commit()

    return {'status': status, 'inseridos': inseridos,
            'atualizados': atualizados, 'mensagem': mensagem}
