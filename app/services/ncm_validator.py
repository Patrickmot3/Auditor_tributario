"""
Serviço core de validação tributária NCM.
Busca correspondência em cascata: 8 dígitos → 6 → 4 → 2.
"""
import logging
from datetime import date
from sqlalchemy import and_, or_
from app.extensions import db
from app.models.ncm import NcmTributario, GrupoTributario
from app.models.empresa import Empresa
from app.models.consulta import Consulta
from app.models.base_tributaria import LogAtualizacao

logger = logging.getLogger(__name__)

# Mapeamento CST → descrição do regime de tributação PIS/COFINS
CST_DESCRICAO = {
    '01': 'Tributável — Alíquota Básica (regime geral)',
    '02': 'Monofásico — Fabricante/Importador com Alíquota Diferenciada',
    '03': 'Monofásico — Cobrança por Unidade de Medida (fabricante/importador)',
    '04': 'Monofásico — Revenda a Alíquota Zero (varejista/atacadista)',
    '05': 'Substituição Tributária — PIS/COFINS retido pelo substituto',
    '06': 'Alíquota Zero — Produto com tributação reduzida a 0% por lei',
    '07': 'Isento — Operação isenta de PIS/COFINS por lei',
    '08': 'Sem Incidência — Operação não sujeita à contribuição',
    '09': 'Suspensão — Cobrança de PIS/COFINS suspensa por lei',
    '49': 'Outras Operações de Saída',
    '50': 'Entrada — Aquisição vinculada a receita tributada (direito a crédito)',
    '70': 'Entrada Monofásico — Aquisição a Alíquota Zero',
    '73': 'Entrada — Aquisição a Alíquota Zero (importação)',
    '75': 'Entrada — Aquisição sem Incidência da Contribuição',
    '98': 'Outras Operações de Entrada',
    '99': 'Outras Operações',
}

# CNAEs automotivos (Lei 10.485/2002 — regra de destinação)
CNAES_AUTOMOTIVOS = {
    '4511', '4512', '4520', '4541', '4542',
    '45111', '45129', '45201', '45411', '45421',
    '4511-1', '4512-9', '4520-0', '4541-2', '4542-1',
}


def _normalizar_ncm(ncm: str) -> str:
    if not ncm:
        return ''
    return ncm.replace('.', '').replace('-', '').replace(' ', '').strip()


def _cnae_automotivo(cnae: str) -> bool:
    if not cnae:
        return False
    c = cnae.replace('.', '').replace('-', '').strip()
    return c[:4] in CNAES_AUTOMOTIVOS or c[:5] in CNAES_AUTOMOTIVOS or cnae in CNAES_AUTOMOTIVOS


def _buscar_ncm_em_cascata(ncm_limpo: str):
    """Busca NcmTributario por correspondência em cascata."""
    hoje = date.today()
    filtro_vigencia = and_(
        NcmTributario.ativo == True,
        NcmTributario.vigencia_inicio <= hoje,
        or_(NcmTributario.vigencia_fim == None, NcmTributario.vigencia_fim >= hoje),
    )

    # 1. NCM exato (8 dígitos)
    registro = NcmTributario.query.filter(
        filtro_vigencia,
        NcmTributario.ncm == ncm_limpo,
        NcmTributario.tipo_referencia == 'ncm_exato',
    ).first()
    if registro:
        return registro

    # 2. Posição de 6 dígitos
    registro = NcmTributario.query.filter(
        filtro_vigencia,
        NcmTributario.ncm == ncm_limpo[:6],
        NcmTributario.tipo_referencia == 'posicao_6',
    ).first()
    if registro:
        return registro

    # 3. Posição de 4 dígitos (subposição)
    registro = NcmTributario.query.filter(
        filtro_vigencia,
        NcmTributario.ncm == ncm_limpo[:4],
        NcmTributario.tipo_referencia == 'posicao_4',
    ).first()
    if registro:
        return registro

    # 4. Capítulo (2 dígitos / prefixo)
    registro = NcmTributario.query.filter(
        filtro_vigencia,
        NcmTributario.ncm == ncm_limpo[:2],
        NcmTributario.tipo_referencia == 'prefixo',
    ).first()
    return registro


def _ultima_atualizacao_tabela():
    log = LogAtualizacao.query.filter(
        LogAtualizacao.status.in_(['sucesso', 'seed_inicial'])
    ).order_by(LogAtualizacao.data_importacao.desc()).first()
    if log:
        return log
    return None


def validar_ncm(ncm: str, empresa_id: int, cst_atual: str = None):
    """
    Valida um NCM para uma empresa e retorna dict completo com resultado tributário.
    Grava ou atualiza registro em `consultas` (sem duplicar).
    """
    ncm_limpo = _normalizar_ncm(ncm)
    if not ncm_limpo:
        return {'erro': 'NCM inválido ou vazio'}

    empresa = db.session.get(Empresa, empresa_id)
    if not empresa:
        return {'erro': 'Empresa não encontrada'}

    registro = _buscar_ncm_em_cascata(ncm_limpo)
    log_tabela = _ultima_atualizacao_tabela()

    ultima_atualizacao_str = None
    versao_tabela = None
    if log_tabela:
        if log_tabela.data_atualizacao_rfb:
            ultima_atualizacao_str = log_tabela.data_atualizacao_rfb.strftime('%d/%m/%Y')
        elif log_tabela.data_importacao:
            ultima_atualizacao_str = log_tabela.data_importacao.strftime('%d/%m/%Y')
        versao_tabela = log_tabela.versao

    if not registro:
        resultado = {
            'ncm': ncm_limpo,
            'monofasico': False,
            'grupo': None,
            'tabela_sped': None,
            'lei': None,
            'cst_sugerido': None,
            'cst_entrada': None,
            'cfop_sugerido': None,
            'pis_aliquota': None,
            'cofins_aliquota': None,
            'posicao_cadeia': empresa.posicao_cadeia,
            'inconsistencia_detectada': False,
            'observacao': 'NCM não localizado nas tabelas SPED. Verificar manualmente.',
            'ultima_atualizacao_tabela': ultima_atualizacao_str,
            'versao_tabela': versao_tabela,
            'encontrado': False,
            'descricao_tributacao': 'NCM não localizado — verificar tributação manualmente',
        }
        _gravar_consulta(ncm_limpo, empresa, resultado, cst_atual)
        return resultado

    grupo = registro.grupo
    posicao = empresa.posicao_cadeia
    e_varejista = posicao in ('varejista', 'atacadista')
    e_fabricante = posicao in ('fabricante', 'importador')

    # Determinar alíquotas conforme posição na cadeia
    if e_varejista:
        pis = float(registro.pis_aliquota_varejista or 0)
        cofins = float(registro.cofins_aliquota_varejista or 0)
        cst_sugerido = registro.cst_saida or '04'
    else:
        pis = float(registro.pis_aliquota_fabricante or 0)
        cofins = float(registro.cofins_aliquota_fabricante or 0)
        cst_sugerido = registro.cst_entrada or '02'

    cfop_sugerido = registro.cfop_saida_simples if empresa.regime_tributario == 'simples_nacional' else '5102'

    observacao = registro.observacao or ''

    # Regra especial: autopeças e CNAE
    if grupo and 'auto' in grupo.nome.lower():
        if not _cnae_automotivo(empresa.cnae_principal):
            observacao += (
                ' Verificar destinação — produto pode não se enquadrar no regime '
                'monofásico se não for para uso automotivo '
                '(Solução de Consulta COSIT nº 55/2018).'
            )

    # Regra Simples Nacional x exclusão do DAS:
    # Monofásico (CST 02/03/04) e ST (CST 05) permitem segregar a receita da base do DAS.
    # Isenção (CST 07) e Alíquota Zero (CST 06) NÃO excluem do DAS — o optante paga
    # PIS/COFINS embutido na alíquota do Anexo I normalmente (LC 123/2006, art. 18, § 4º-A).
    if empresa.regime_tributario == 'simples_nacional':
        if cst_sugerido in {'02', '03', '04'}:
            observacao += (
                ' Simples Nacional: receita pode ser segregada e excluída da base do DAS '
                '(tributação monofásica — LC 123/2006, art. 18, § 4º-A).'
            )
        elif cst_sugerido == '05':
            observacao += (
                ' Simples Nacional: receita pode ser segregada e excluída da base do DAS '
                '(Substituição Tributária — LC 123/2006, art. 18, § 4º-A).'
            )
        elif cst_sugerido in {'06', '07', '08', '09'}:
            observacao += (
                ' Atenção (Simples Nacional): este CST não permite exclusão do DAS — '
                'PIS/COFINS são pagos normalmente pela alíquota do Anexo I '
                '(sem previsão na LC 123/2006 para segregação).'
            )

    # Detectar inconsistência: CST da NF-e difere do CST que o sistema sugere
    inconsistencia = False
    if cst_atual and cst_sugerido and cst_atual.strip() != cst_sugerido.strip():
        inconsistencia = True
        observacao += (
            f' CST informado na NF-e ({cst_atual.strip()}) '
            f'difere do CST sugerido ({cst_sugerido}).'
        )

    resultado = {
        'ncm': ncm_limpo,
        'monofasico': registro.monofasico,
        'grupo': grupo.nome if grupo else None,
        'tabela_sped': grupo.tabela_sped if grupo else None,
        'lei': registro.lei,
        'cst_sugerido': cst_sugerido,
        'cst_entrada': registro.cst_entrada,
        'cfop_sugerido': cfop_sugerido,
        'pis_aliquota': pis,
        'cofins_aliquota': cofins,
        'posicao_cadeia': posicao,
        'inconsistencia_detectada': inconsistencia,
        'observacao': observacao.strip(),
        'ultima_atualizacao_tabela': ultima_atualizacao_str,
        'versao_tabela': versao_tabela,
        'encontrado': True,
        'tipo_referencia': registro.tipo_referencia,
        'descricao_ncm': registro.descricao,
        'descricao_tributacao': CST_DESCRICAO.get(cst_sugerido, f'CST {cst_sugerido}'),
    }

    _gravar_consulta(ncm_limpo, empresa, resultado, cst_atual)
    return resultado


def _gravar_consulta(ncm_limpo, empresa, resultado, cst_atual):
    """Grava ou atualiza consulta no banco (sem duplicar)."""
    try:
        consulta = Consulta.query.filter_by(
            empresa_id=empresa.id,
            ncm_consultado=ncm_limpo,
        ).first()

        if consulta:
            consulta.monofasico = resultado['monofasico']
            consulta.grupo_tributario = resultado.get('grupo')
            consulta.lei_aplicada = resultado.get('lei')
            consulta.cst_atual = cst_atual
            consulta.cst_sugerido = resultado['cst_sugerido']
            consulta.cfop_sugerido = resultado.get('cfop_sugerido')
            consulta.pis_aliquota = resultado['pis_aliquota']
            consulta.cofins_aliquota = resultado['cofins_aliquota']
            consulta.inconsistencia_detectada = resultado['inconsistencia_detectada']
            consulta.observacao = resultado.get('observacao')
            consulta.posicao_cadeia = empresa.posicao_cadeia
        else:
            consulta = Consulta(
                empresa_id=empresa.id,
                tipo_consulta='individual',
                origem='manual',
                ncm_consultado=ncm_limpo,
                descricao_produto=resultado.get('descricao_ncm'),
                monofasico=resultado['monofasico'],
                grupo_tributario=resultado.get('grupo'),
                lei_aplicada=resultado.get('lei'),
                cst_atual=cst_atual,
                cst_sugerido=resultado['cst_sugerido'],
                cfop_sugerido=resultado.get('cfop_sugerido'),
                pis_aliquota=resultado['pis_aliquota'],
                cofins_aliquota=resultado['cofins_aliquota'],
                inconsistencia_detectada=resultado['inconsistencia_detectada'],
                observacao=resultado.get('observacao'),
                posicao_cadeia=empresa.posicao_cadeia,
            )
            db.session.add(consulta)

        db.session.commit()
    except Exception as e:
        db.session.rollback()
        logger.error(f'Erro ao gravar consulta NCM {ncm_limpo}: {e}')
