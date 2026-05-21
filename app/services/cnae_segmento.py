"""
Motor de inferência CNAE → grupos tributários e validação NCM × empresa.
"""
import re

# ---------------------------------------------------------------------------
# Mapeamento CNAE (prefixo 4 ou 2 dígitos) → grupos tributários
# Longest-prefix match: 4 dígitos tem prioridade sobre 2.
# ---------------------------------------------------------------------------
CNAE_PARA_GRUPOS: dict[str, set[str]] = {
    # ── Veículos, autopeças e pneumáticos (G100 / G500) ──────────────────
    '4511': {'G100', 'G500'},   # comércio varejo/atacado veículos automotores
    '4512': {'G100'},           # comércio de veículos usados
    '4520': {'G100', 'G500'},   # manutenção e reparação de veículos
    '4530': {'G100', 'G500'},   # peças e acessórios para veículos
    '4541': {'G100', 'G500'},   # motocicletas, peças e acessórios
    '4542': {'G100', 'G500'},   # manutenção de motocicletas
    '2910': {'G100'},           # fabricação de automóveis
    '2920': {'G100'},           # fabricação de caminhões e ônibus
    '2930': {'G100'},           # fabricação de carrocerias e reboques
    '2941': {'G100', 'G500'},   # fabricação de peças para veículos
    '2942': {'G100'},           # fabricação de peças para motocicletas
    '2211': {'G500'},           # fabricação de pneumáticos e câmaras de ar
    # ── Combustíveis (G200) ───────────────────────────────────────────────
    '4731': {'G200'},           # comércio varejista combustíveis (postos)
    '4741': {'G200'},           # comércio atacadista combustíveis
    '1921': {'G200'},           # fabricação de produtos do refino de petróleo
    '1922': {'G200'},           # fabricação de álcool
    '0610': {'G200'},           # extração de petróleo e gás natural
    # ── Fármacos e Perfumaria (G300) ──────────────────────────────────────
    '4771': {'G300'},           # farmácias e drogarias (varejo)
    '4772': {'G300'},           # cosméticos, perfumaria e higiene (varejo)
    '4644': {'G300'},           # atacado de produtos farmacêuticos
    '4645': {'G300'},           # atacado de instrumentos médicos
    '2121': {'G300'},           # fabricação de medicamentos uso humano
    '2122': {'G300'},           # fabricação de medicamentos uso veterinário
    '2123': {'G300'},           # fabricação de preparações farmacêuticas
    '2063': {'G300'},           # fabricação de cosméticos e perfumaria
    # ── Bebidas Frias (G400) ─────────────────────────────────────────────
    '4723': {'G400'},           # comércio varejista de bebidas
    '4635': {'G400'},           # comércio atacadista de bebidas
    '1111': {'G400'},           # fabricação de bebidas destiladas
    '1112': {'G400'},           # fabricação de vinho
    '1113': {'G400'},           # fabricação de malte, cerveja e chope
    '1121': {'G400'},           # fabricação de refrigerantes
    '1122': {'G400'},           # fabricação de águas envasadas e refrescos
    # ── Alimentos Básicos (G700) ──────────────────────────────────────────
    '4711': {'G700'},           # supermercados (com predominância alimentos)
    '4712': {'G700'},           # mercearias e armazéns
    '4721': {'G700'},           # carnes e pescados (varejo)
    '4722': {'G700'},           # laticínios, frios e embutidos (varejo)
    '4724': {'G700'},           # hortifrutigranjeiros (varejo)
    '4729': {'G700'},           # produtos alimentícios em geral (varejo)
    '4631': {'G700'},           # cereais e leguminosas beneficiados (atacado)
    '4632': {'G700'},           # açúcar (atacado)
    '4633': {'G700'},           # aves abatidas e ovos (atacado)
    '4634': {'G700'},           # carnes bovinas e suínas (atacado)
    '4637': {'G700'},           # sorvetes e chocolates (atacado)
    '4638': {'G700'},           # frutas e derivados (atacado)
    '1011': {'G700'},           # abate de bovinos
    '1012': {'G700'},           # abate de suínos, ovinos e caprinos
    '1013': {'G700'},           # abate e fabricação de produtos de pesca
    '1020': {'G700'},           # processamento de peixe e crustáceos
    '1031': {'G700'},           # fabricação de conservas de frutas
    '1032': {'G700'},           # fabricação de conservas de legumes
    '1033': {'G700'},           # fabricação de óleos vegetais
    '1061': {'G700'},           # fabricação de produtos do arroz
    '1062': {'G700'},           # fabricação de farinhas e massas alimentícias
    '1091': {'G700'},           # fabricação de panificação
    # ── Insumos Agropecuários — Suspensão (G800) ──────────────────────────
    '4612': {'G800'},           # representantes de insumos agropecuários
    '4683': {'G800'},           # comércio atacadista defensivos agrícolas
    '4684': {'G800'},           # comércio atacadista fertilizantes e corretivos
    '2830': {'G800'},           # fabricação de tratores agrícolas
    '2833': {'G800'},           # fabricação de máquinas e equipamentos agrícolas
    # ── 2 dígitos (fallback quando 4 não casam) ───────────────────────────
    '01': {'G800'},             # agricultura, pecuária e serviços relacionados
    '02': {'G800'},             # produção florestal
    '03': {'G800'},             # pesca e aquicultura
    '06': {'G200'},             # extração de petróleo e gás
    '10': {'G700'},             # fabricação de alimentos em geral
    '11': {'G400'},             # fabricação de bebidas
    '19': {'G200'},             # fabricação de derivados do petróleo
    '20': {'G800'},             # fabricação de químicos (inclui defensivos)
    '21': {'G300'},             # fabricação de produtos farmacêuticos
    '22': {'G300'},             # fabricação de cosméticos (seção 22 inclui perfumaria)
    '28': {'G800'},             # fabricação de máquinas e equipamentos agrícolas
    '29': {'G100'},             # fabricação de veículos automotores
    '45': {'G100', 'G500'},     # comércio e reparação de veículos
    '47': {'G700'},             # comércio varejista em geral
}

# ---------------------------------------------------------------------------
# Mapeamento nome do grupo (como armazenado em consultas.grupo_tributario)
# → código do grupo (G100…G800)
# ---------------------------------------------------------------------------
NOME_PARA_CODIGO: dict[str, str] = {
    'Veículos e Autopeças':                           'G100',
    'Combustíveis e Derivados':                       'G200',
    'Fármacos e Perfumaria':                          'G300',
    'Bebidas Frias':                                  'G400',
    'Pneumáticos':                                    'G500',
    'Substituição Tributária PIS/COFINS':             'G600',
    # G700 — variante canônica (com acento e travessão)
    'Alimentos Básicos — Alíquota Zero PIS/COFINS':   'G700',
    # G700 — variante legada gravada no banco antes da correção
    'Alimentos Basicos - Aliquota Zero PIS/COFINS':   'G700',
    # G750 — variante canônica
    'Livros e Publicações — Alíquota Zero PIS/COFINS': 'G750',
    # G750 — variante legada
    'Livros e Publicacoes - Aliquota Zero PIS/COFINS': 'G750',
    'Insumos Agropecuários — Suspensão PIS/COFINS':   'G800',
}

# Rótulos exibidos nos checkboxes do formulário
GRUPOS_LABEL: dict[str, str] = {
    'G100': 'G100 — Veículos e Autopeças',
    'G200': 'G200 — Combustíveis e Derivados',
    'G300': 'G300 — Fármacos e Perfumaria',
    'G400': 'G400 — Bebidas Frias',
    'G500': 'G500 — Pneumáticos',
    'G600': 'G600 — Substituição Tributária',
    'G700': 'G700 — Alimentos Básicos (Alíq. Zero)',
    'G750': 'G750 — Livros e Publicações (Alíq. Zero)',
    'G800': 'G800 — Insumos Agropecuários (Suspensão)',
}


def _normalizar_cnae(cnae: str) -> str:
    """Remove máscara e retorna apenas dígitos."""
    return re.sub(r'\D', '', cnae or '')


def inferir_segmentos(cnae_principal: str, cnaes_secundarios) -> set:
    """
    Infere grupos tributários a partir de CNAEs usando longest-prefix match.
    4 dígitos têm prioridade sobre 2.
    Retorna set de códigos de grupo (ex.: {'G100', 'G500'}).
    """
    resultado: set[str] = set()
    todos = [cnae_principal] + list(cnaes_secundarios or [])
    for cnae in todos:
        c = _normalizar_cnae(cnae)
        if not c:
            continue
        c4, c2 = c[:4], c[:2]
        if c4 in CNAE_PARA_GRUPOS:
            resultado |= CNAE_PARA_GRUPOS[c4]
        elif c2 in CNAE_PARA_GRUPOS:
            resultado |= CNAE_PARA_GRUPOS[c2]
    return resultado


def validar_ncm_vs_empresa(item: dict, empresa) -> dict:
    """
    Valida se o grupo tributário do NCM é esperado para o CNAE da empresa.

    item : dict com chaves 'ncm' e 'grupo' (nome do grupo tributário)
    empresa : instância de Empresa com .segmentos_efetivos e .regime_tributario

    Retorna dict:
      ok         : bool
      severidade : 'CRITICA' | 'ALERTA' | 'OK'
      mensagem   : str
    """
    efetivos = empresa.segmentos_efetivos if empresa else set()
    if not efetivos:
        # Empresa sem segmentos configurados → sem validação CNAE
        return {'ok': True, 'severidade': 'OK', 'mensagem': ''}

    grupo_nome = (item.get('grupo') or '').strip()
    grupo_cod = NOME_PARA_CODIGO.get(grupo_nome)

    if not grupo_cod:
        # NCM sem grupo mapeado (NCM não localizado) → não valida
        return {'ok': True, 'severidade': 'OK', 'mensagem': ''}

    if grupo_cod in efetivos:
        return {'ok': True, 'severidade': 'OK', 'mensagem': ''}

    # Grupo fora dos segmentos efetivos da empresa
    regime = getattr(empresa, 'regime_tributario', '') or ''
    if regime == 'simples_nacional':
        sev = 'CRITICA'
        msg = (f'Grupo {grupo_cod} ({grupo_nome}) não está entre os segmentos '
               f'do CNAE desta empresa. Para Simples Nacional, pode impactar '
               f'a apuração no PGDAS-D.')
    else:
        sev = 'ALERTA'
        msg = (f'Grupo {grupo_cod} ({grupo_nome}) fora dos segmentos CNAE '
               f'da empresa. Verifique se o enquadramento tributário está correto.')

    return {'ok': False, 'severidade': sev, 'mensagem': msg}
