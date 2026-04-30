"""
Serviço de importação de XML NF-e (versão 4.00).
Suporta: XML único, múltiplos XMLs, ZIP com XMLs, RAR com XMLs.
"""
import io
import logging
import os
import tempfile
import zipfile
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
    n_nf = _tag(ide, 'nNF') if ide is not None else ''
    serie = _tag(ide, 'serie') if ide is not None else ''

    dets = inf_nfe.findall('nfe:det', NS) or inf_nfe.findall('det')

    numero_lote = (f'NF-e {serie.zfill(3)}-{n_nf.zfill(9)}' if n_nf
                   else (f'NF-e {ch_nfe[:10]}...' if ch_nfe else 'XML NF-e'))
    lote = LoteConsulta(
        empresa_id=empresa_id,
        nome_lote=numero_lote,
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

        # CST atual da NF-e — busca por iter() para ignorar namespace
        imposto = det.find('nfe:imposto', NS) or det.find('imposto')
        cst_atual = None
        if imposto is not None:
            for el in imposto.iter():
                tag = el.tag
                if (tag.endswith('}CST') or tag == 'CST') and el.text and el.text.strip():
                    cst_atual = el.text.strip()
                    break

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
                'lei': resultado.get('lei'),
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
        'n_nf': n_nf,
        'serie': serie,
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


# ─── Lote compactado (ZIP / RAR / múltiplos XMLs) ────────────────────────────

def _extrair_xmls_zip(caminho: str) -> dict[str, bytes]:
    """Extrai XMLs de um arquivo ZIP. Retorna {nome_arquivo: conteúdo}."""
    xmls = {}
    with zipfile.ZipFile(caminho) as z:
        for nome in z.namelist():
            # Ignora diretórios e arquivos não-XML
            if nome.endswith('/') or not nome.lower().endswith('.xml'):
                continue
            xmls[os.path.basename(nome)] = z.read(nome)
    return xmls


def _extrair_xmls_rar(caminho: str) -> dict[str, bytes]:
    """
    Extrai XMLs de um arquivo RAR.
    Estratégia em cascata:
      1. subprocess com unrar (se disponível)
      2. subprocess com 7z / 7za / 7zr (p7zip)
      3. rarfile via Python (último recurso)
    """
    import shutil
    import subprocess

    RAR_MAGIC = (b'Rar!\x1a\x07',)  # RAR3 e RAR5 começam com esses bytes

    # Validar assinatura antes de tentar qualquer extração
    with open(caminho, 'rb') as f:
        header = f.read(8)
    if not any(header.startswith(m) for m in RAR_MAGIC):
        preview = header.hex()
        raise Exception(
            f'O arquivo não possui assinatura RAR válida (bytes: {preview}). '
            'Verifique se o arquivo não está corrompido ou renomeado. Use ZIP.'
        )

    def _ler_xmls_de_dir(tmpdir: str) -> dict[str, bytes]:
        xmls = {}
        for fname in os.listdir(tmpdir):
            if fname.lower().endswith('.xml'):
                with open(os.path.join(tmpdir, fname), 'rb') as f:
                    xmls[fname] = f.read()
        return xmls

    # Tentar extração via subprocess (mais robusto que a lib rarfile)
    for tool in filter(None, [
        shutil.which('unrar'),
        shutil.which('7z'),
        shutil.which('7za'),
        shutil.which('7zr'),
    ]):
        try:
            import tempfile as _tf
            with _tf.TemporaryDirectory() as tmpdir:
                if os.path.basename(tool) == 'unrar':
                    cmd = [tool, 'e', '-y', '-inul', caminho, tmpdir]
                else:
                    cmd = [tool, 'e', caminho, f'-o{tmpdir}', '-y', '-bso0']
                result = subprocess.run(cmd, capture_output=True, timeout=120)
                if result.returncode == 0:
                    xmls = _ler_xmls_de_dir(tmpdir)
                    if xmls:
                        logger.info(f'_extrair_xmls_rar: {len(xmls)} XMLs extraídos via {tool}')
                        return xmls
        except Exception as e:
            logger.warning(f'_extrair_xmls_rar: {tool} falhou — {e}')

    # Último recurso: rarfile (puro Python para leitura de índice + tool para extração)
    try:
        import rarfile
        unrar_bin = shutil.which('unrar') or shutil.which('7z') or shutil.which('7za')
        if unrar_bin:
            rarfile.UNRAR_TOOL = unrar_bin
            rarfile.ALT_TOOL = unrar_bin
        xmls = {}
        with rarfile.RarFile(caminho) as r:
            for info in r.infolist():
                nome = info.filename
                if not nome.lower().endswith('.xml'):
                    continue
                xmls[os.path.basename(nome)] = r.read(nome)
        return xmls
    except Exception as e:
        raise Exception(
            f'Não foi possível extrair o RAR ({e}). '
            'Use ZIP no lugar de RAR — o servidor pode não ter o utilitário necessário.'
        )


def _processar_xml_bytes(conteudo: bytes, empresa_id: int) -> dict:
    """Processa XML a partir de bytes, sem precisar de arquivo em disco."""
    with tempfile.NamedTemporaryFile(suffix='.xml', delete=False) as tmp:
        tmp.write(conteudo)
        tmp_path = tmp.name
    try:
        return processar_xml_nfe(tmp_path, empresa_id)
    finally:
        os.unlink(tmp_path)


def processar_lote_compactado(caminho: str, empresa_id: int, nome_arquivo: str) -> dict:
    """
    Processa um lote de XMLs NF-e a partir de:
      - Arquivo ZIP contendo XMLs
      - Arquivo RAR contendo XMLs
    Retorna relatório agregado com resultado por NF-e.
    """
    ext = nome_arquivo.rsplit('.', 1)[-1].lower() if '.' in nome_arquivo else ''

    # Extrair XMLs do compactado
    if ext == 'zip':
        try:
            xmls = _extrair_xmls_zip(caminho)
        except zipfile.BadZipFile:
            return {'erro': 'Arquivo ZIP inválido ou corrompido.'}
    elif ext == 'rar':
        try:
            xmls = _extrair_xmls_rar(caminho)
        except Exception as e:
            return {'erro': str(e)}
    else:
        return {'erro': f'Formato "{ext}" não suportado. Use ZIP ou RAR.'}

    if not xmls:
        return {'erro': 'Nenhum arquivo .xml encontrado dentro do compactado.'}

    # Processar cada XML individualmente
    total_geral = ok_geral = duplicados_geral = erros_geral = 0
    monofasicos_geral = nao_monofasicos_geral = inconsistencias_geral = 0
    notas = []

    for nome_xml, conteudo in sorted(xmls.items()):
        try:
            resultado = _processar_xml_bytes(conteudo, empresa_id)
        except Exception as e:
            resultado = {
                'erro': str(e),
                'total': 0, 'ok': 0, 'duplicados': 0, 'erros': 1,
                'monofasicos': 0, 'nao_monofasicos': 0, 'inconsistencias': 0,
                'itens': [],
            }

        total_geral          += resultado.get('total', 0)
        ok_geral             += resultado.get('ok', 0)
        duplicados_geral     += resultado.get('duplicados', 0)
        erros_geral          += resultado.get('erros', 0)
        monofasicos_geral    += resultado.get('monofasicos', 0)
        nao_monofasicos_geral+= resultado.get('nao_monofasicos', 0)
        inconsistencias_geral+= resultado.get('inconsistencias', 0)

        notas.append({
            'arquivo': nome_xml,
            'lote_id': resultado.get('lote_id'),
            'ch_nfe': resultado.get('ch_nfe', ''),
            'n_nf': resultado.get('n_nf', ''),
            'serie': resultado.get('serie', ''),
            'razao_emitente': resultado.get('razao_emitente', ''),
            'cnpj_emitente': resultado.get('cnpj_emitente', ''),
            'data_emissao': resultado.get('data_emissao', ''),
            'total': resultado.get('total', 0),
            'monofasicos': resultado.get('monofasicos', 0),
            'inconsistencias': resultado.get('inconsistencias', 0),
            'erro': resultado.get('erro'),
            'itens': resultado.get('itens', []),
        })

    lote_ids = [n['lote_id'] for n in notas if n.get('lote_id')]

    return {
        'arquivo_origem': nome_arquivo,
        'total_arquivos': len(xmls),
        'total': total_geral,
        'ok': ok_geral,
        'duplicados': duplicados_geral,
        'erros': erros_geral,
        'monofasicos': monofasicos_geral,
        'nao_monofasicos': nao_monofasicos_geral,
        'inconsistencias': inconsistencias_geral,
        'notas': notas,
        'lote_ids': lote_ids,
    }
