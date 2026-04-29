"""
Serviço de importação de planilha Excel para consulta em lote.
Colunas esperadas: Código | Descrição | Tipo do Item | Cód. NBM | Cód. NCM | Cód. CEST | CST Atual
Também aceita o formato de relatório de produtos do sistema Domínio Sistemas.
"""
import os
import logging
from datetime import datetime, timezone
import pandas as pd
from app.extensions import db
from app.models.consulta import LoteConsulta, LoteItem, Consulta
from app.services.ncm_validator import validar_ncm, _normalizar_ncm

logger = logging.getLogger(__name__)

COLUNAS_ESPERADAS = {
    'codigo':   ['código', 'codigo', 'cod', 'cód', 'cód.', 'cod.'],
    'descricao': ['descrição', 'descricao', 'desc', 'nome', 'produto'],
    'tipo':     ['tipo do item', 'tipo item', 'tipo'],
    'nbm':      ['cód. nbm', 'cod. nbm', 'nbm', 'cód nbm'],
    'ncm':      ['cód. ncm', 'cod. ncm', 'ncm', 'cód ncm', 'código ncm'],
    'cest':     ['cód. cest', 'cod. cest', 'cest', 'cód cest'],
    'cst':      ['cst atual', 'cst', 'cst pis', 'cst cofins'],
}


def _ler_excel(caminho_arquivo, **kwargs):
    """
    Lê arquivo Excel retornando DataFrame. Suporta .xlsx e .xls.
    Para .xls usa xlrd como engine principal e calamine como fallback
    (necessário para arquivos exportados pelo Domínio Sistemas).
    """
    ext = os.path.splitext(caminho_arquivo)[1].lower()
    if ext == '.xlsx':
        return pd.read_excel(caminho_arquivo, dtype=str, **kwargs)
    # .xls: xlrd primeiro, calamine como fallback
    for engine in ('xlrd', 'calamine'):
        try:
            return pd.read_excel(caminho_arquivo, dtype=str, engine=engine, **kwargs)
        except Exception:
            continue
    raise Exception(
        'Não foi possível ler o arquivo .xls. '
        'Abra no Excel, salve como .xlsx e importe novamente.'
    )


def _detectar_coluna(colunas_df, candidatos):
    colunas_lower = [str(c).lower().strip() for c in colunas_df]
    for candidato in candidatos:
        for i, col in enumerate(colunas_lower):
            if candidato in col:
                return colunas_df[i]
    return None


def _detectar_cabecalho(df_raw):
    """Detecta a linha de cabeçalho buscando a coluna NCM."""
    for i in range(min(10, len(df_raw))):
        linha = [str(c).lower().strip() for c in df_raw.iloc[i].values]
        if any('ncm' in c for c in linha):
            return i
    return 0


def processar_excel(caminho_arquivo, empresa_id, nome_lote=None):
    """
    Processa planilha Excel e valida cada NCM.
    Aceita o modelo TribSync e o relatório de produtos do sistema Domínio.
    Retorna dict com relatório do processamento.
    """
    try:
        df_raw = _ler_excel(caminho_arquivo, header=None)
    except Exception as e:
        logger.error(f'Erro ao ler Excel: {e}')
        return {'erro': str(e)}

    linha_cab = _detectar_cabecalho(df_raw)
    df = _ler_excel(caminho_arquivo, header=linha_cab)
    df.columns = [str(c).strip() for c in df.columns]

    col_ncm      = _detectar_coluna(df.columns, COLUNAS_ESPERADAS['ncm'])
    col_codigo   = _detectar_coluna(df.columns, COLUNAS_ESPERADAS['codigo'])
    col_descricao = _detectar_coluna(df.columns, COLUNAS_ESPERADAS['descricao'])
    col_cest     = _detectar_coluna(df.columns, COLUNAS_ESPERADAS['cest'])
    col_nbm      = _detectar_coluna(df.columns, COLUNAS_ESPERADAS['nbm'])
    col_cst      = _detectar_coluna(df.columns, COLUNAS_ESPERADAS['cst'])

    if not col_ncm:
        return {'erro': 'Coluna NCM não encontrada na planilha.'}

    lote = LoteConsulta(
        empresa_id=empresa_id,
        nome_lote=nome_lote or 'Importação Excel',
        tipo='excel',
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

    for idx, row in df.iterrows():
        ncm_raw = str(row.get(col_ncm, '') or '').strip()
        if not ncm_raw or ncm_raw.lower() in ('nan', 'none', ''):
            continue

        ncm_limpo = _normalizar_ncm(ncm_raw)
        if not ncm_limpo:
            continue

        total += 1
        linha_num = idx + linha_cab + 2

        codigo    = str(row.get(col_codigo, '') or '').strip() if col_codigo else None
        descricao = str(row.get(col_descricao, '') or '').strip() if col_descricao else None
        cest      = str(row.get(col_cest, '') or '').strip() if col_cest else None
        nbm       = str(row.get(col_nbm, '') or '').strip() if col_nbm else None
        cst_atual = str(row.get(col_cst, '') or '').strip() if col_cst else None
        if cst_atual and cst_atual.lower() in ('nan', 'none'):
            cst_atual = None

        # Verificar duplicidade
        existente = Consulta.query.filter_by(
            empresa_id=empresa_id,
            ncm_consultado=ncm_limpo,
        ).first()
        status_item = 'duplicado' if existente else 'ok'

        try:
            resultado = validar_ncm(ncm_limpo, empresa_id, cst_atual)

            # Atualizar campos adicionais na consulta gravada
            consulta = Consulta.query.filter_by(
                empresa_id=empresa_id,
                ncm_consultado=ncm_limpo,
            ).first()
            if consulta:
                consulta.tipo_consulta = 'excel'
                consulta.origem = 'excel'
                if descricao:
                    consulta.descricao_produto = descricao
                if codigo:
                    consulta.codigo_produto = codigo
                if cest:
                    consulta.codigo_cest = cest
                if nbm:
                    consulta.codigo_nbm = nbm
                db.session.commit()

            item = LoteItem(
                lote_id=lote.id,
                consulta_id=consulta.id if consulta else None,
                linha_original=linha_num,
                ncm=ncm_limpo,
                descricao=descricao,
                codigo_produto=codigo,
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
                'ncm':           ncm_limpo,
                'descricao':     descricao,
                'codigo':        codigo,
                'cst_atual':     cst_atual,
                'monofasico':    resultado.get('monofasico'),
                'cst_sugerido':  resultado.get('cst_sugerido'),
                'inconsistencia': resultado.get('inconsistencia_detectada'),
                'grupo':         resultado.get('grupo'),
                'status':        status_item,
            })

        except Exception as e:
            logger.error(f'Erro ao processar NCM {ncm_limpo} (linha {linha_num}): {e}')
            item = LoteItem(
                lote_id=lote.id,
                linha_original=linha_num,
                ncm=ncm_limpo,
                descricao=descricao,
                codigo_produto=codigo,
                status_processamento='erro',
                mensagem_erro=str(e)[:300],
            )
            db.session.add(item)
            erros += 1
            itens_resultado.append({
                'ncm': ncm_limpo, 'descricao': descricao, 'codigo': codigo,
                'cst_atual': cst_atual, 'monofasico': None, 'cst_sugerido': None,
                'inconsistencia': False, 'grupo': None, 'status': 'erro',
            })
            db.session.rollback()

    # Atualizar resumo do lote
    lote.total_itens = total
    lote.itens_monofasicos = monofasicos
    lote.itens_nao_monofasicos = nao_monofasicos
    lote.itens_com_inconsistencia = inconsistencias
    lote.status = 'concluido'
    lote.concluido_at = datetime.now(timezone.utc)
    db.session.commit()

    return {
        'lote_id': lote.id,
        'total': total,
        'ok': ok,
        'duplicados': duplicados,
        'erros': erros,
        'monofasicos': monofasicos,
        'nao_monofasicos': nao_monofasicos,
        'inconsistencias': inconsistencias,
        'itens': itens_resultado,
    }
