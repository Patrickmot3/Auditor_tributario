"""
Comandos CLI Flask para inicialização e manutenção do banco.
"""
import click
from datetime import date, datetime, timezone
from flask import current_app
from app.extensions import db
from app.models.ncm import GrupoTributario, NcmTributario
from app.models.usuario import Usuario
from app.models.base_tributaria import LogAtualizacao, AliquotaGrupo


GRUPOS = [
    {
        'codigo': 'G100',
        'nome': 'Veículos e Autopeças',
        'lei_base': 'Lei nº 10.485/2002 — Anexos I e II',
        'tabela_sped': '4.3.10',
        'url_tabela_sped': 'http://sped.rfb.gov.br/arquivo/download/1638',
        'descricao': 'Autopeças e veículos sujeitos ao regime monofásico de PIS/COFINS.',
    },
    {
        'codigo': 'G200',
        'nome': 'Combustíveis e Derivados',
        'lei_base': 'Lei nº 9.718/1998, Art. 4º; Lei nº 10.336/2001 (regime ad rem)',
        'tabela_sped': '4.3.11',
        'url_tabela_sped': 'http://sped.rfb.gov.br/arquivo/download/5786',
        'descricao': 'Combustíveis sujeitos ao regime monofásico. Alíquotas ad rem (R$/m³ ou R$/litro), não percentuais — definidas por Medida Provisória e atualizadas periodicamente pela Receita Federal.',
    },
    {
        'codigo': 'G300',
        'nome': 'Fármacos e Perfumaria',
        'lei_base': 'Lei nº 10.147/2000',
        'tabela_sped': '4.3.10',
        'url_tabela_sped': 'http://sped.rfb.gov.br/arquivo/download/1638',
        'descricao': (
            'Produtos farmacêuticos e de higiene pessoal sujeitos ao regime monofásico (CST 04 varejista / CST 02 fabricante). '
            'Lista positiva — fármacos (capítulos 30, 3001–3004): PIS 2,1% / COFINS 9,9%. '
            'Lista negativa — perfumaria e higiene pessoal (3303–3307, 3401): PIS 2,2% / COFINS 10,3%.'
        ),
    },
    {
        'codigo': 'G400',
        'nome': 'Bebidas Frias',
        'lei_base': 'Lei nº 13.097/2015',
        'tabela_sped': '4.3.15',
        'url_tabela_sped': 'http://sped.rfb.gov.br/arquivo/download/1645',
        'descricao': 'Cervejas, refrigerantes, água mineral e outras bebidas frias.',
    },
    {
        'codigo': 'G500',
        'nome': 'Pneumáticos',
        'lei_base': 'Lei nº 10.485/2002 — Art. 5º',
        'tabela_sped': '4.3.10',
        'url_tabela_sped': 'http://sped.rfb.gov.br/arquivo/download/1638',
        'descricao': 'Pneus e câmaras de ar.',
    },
    {
        'codigo': 'G600',
        'nome': 'Substituição Tributária PIS/COFINS',
        'lei_base': 'Legislação específica por produto — CST 05 (ex.: tabaco: Lei nº 9.715/1998)',
        'tabela_sped': '4.3.12',
        'url_tabela_sped': 'http://sped.rfb.gov.br/pasta/show/1616',
        'descricao': 'Produtos sujeitos a PIS/COFINS por Substituição Tributária (CST 05). Não há lei geral — cada produto tem legislação própria. (Lei nº 9.532/1997 trata de IRPJ/CSLL, não de PIS/COFINS.)',
    },
    {
        'codigo': 'G700',
        'nome': 'Alimentos Básicos — Alíquota Zero PIS/COFINS',
        'lei_base': 'Lei nº 10.925/2004',
        'tabela_sped': '4.3.13',
        'url_tabela_sped': 'http://sped.rfb.gov.br/arquivo/download/1643',
        'descricao': 'Alimentos básicos com PIS/COFINS a alíquota zero (CST 06) — Lei 10.925/2004.',
    },
    {
        'codigo': 'G750',
        'nome': 'Livros e Publicações — Alíquota Zero PIS/COFINS',
        'lei_base': 'Lei nº 10.865/2004, Art. 28, VIII',
        'tabela_sped': '4.3.13',
        'url_tabela_sped': 'http://sped.rfb.gov.br/arquivo/download/1643',
        'descricao': 'Livros, jornais e periódicos com PIS/COFINS a alíquota zero (CST 06) — Lei 10.865/2004, Art. 28, VIII. (A imunidade do Art. 150, VI, d CF/88 alcança ICMS e IPI, não PIS/COFINS.)',
    },
    {
        'codigo': 'G800',
        'nome': 'Insumos Agropecuários — Suspensão PIS/COFINS',
        'lei_base': 'Lei nº 10.925/2004, Art. 9º (doméstico); Lei nº 10.865/2004 (importação)',
        'tabela_sped': '4.3.16',
        'url_tabela_sped': 'http://sped.rfb.gov.br/pasta/show/1616',
        'descricao': 'Insumos agropecuários com PIS/COFINS suspenso (CST 09). Operações domésticas: Lei 10.925/2004, Art. 9º. Importações: Lei 10.865/2004 e Decreto 5.630/2005.',
    },
]

# NCMs Lei 10.485/2002 (Anexo I) — posições de 4 dígitos
AUTOPECAS_POSICOES = [
    '4016', '6813', '7007', '7009', '7320', '8301', '8302', '8407', '8408',
    '8409', '8413', '8414', '8415', '8421', '8431', '8433', '8481', '8483',
    '8505', '8507', '8511', '8512', '8527', '8536', '8539', '8544', '8706',
    '8707', '8708', '9029', '9030', '9032', '9401',
]

COMBUSTIVEIS = [
    ('27101259', 'Gasolina automotiva'),
    ('27101921', 'Óleo diesel'),
    ('27111910', 'Gás natural veicular'),
    ('27101922', 'Óleo diesel marítimo'),
    ('27101500', 'Querosene'),
    ('27101100', 'Gasolina de aviação'),
    # Etanol combustível — Lei 9.718/1998, art. 5°
    ('22071090', 'Álcool etílico não desnaturado — etanol hidratado combustível (EHC)'),
    ('22072000', 'Álcool etílico desnaturado — etanol anidro combustível (EAC)'),
]

FARMACOS_PREFIXOS = ['3003', '3004', '3303', '3304', '3305', '3306', '3307', '3401']

BEBIDAS_PREFIXOS = ['2201', '2202', '2203', '2204', '2205', '2206', '2208']

PNEUMATICOS_POSICOES = ['4011', '4013']

# ── Tabela 4.3.12 — Substituição Tributária PIS/COFINS (CST 05) ──────────────
TABACO_ST = [
    ('2402', 'Charutos, cigarrilhas e cigarros de tabaco ou seus sucedâneos'),
    ('2403', 'Outros produtos de tabaco e sucedâneos manufaturados'),
]

# ── Tabela 4.3.13 — Alíquota Zero PIS/COFINS (CST 06) — alimentos básicos ──
ALIMENTOS_ISENTOS_PREFIXOS = [
    ('01', 'Animais vivos'),
    ('02', 'Carnes e miudezas comestíveis'),
    ('03', 'Peixes, crustáceos e outros invertebrados aquáticos'),
    ('04', 'Leite, laticínios, ovos de aves e mel natural'),
    ('07', 'Produtos hortícolas, plantas, raízes e tubérculos comestíveis'),
    ('08', 'Frutas, cascas de cítricos e de melões'),
    ('10', 'Cereais'),
    ('11', 'Produtos da indústria de moagem; malte; amidos e féculas'),
]

LIVROS_ISENTOS = [
    ('4901', 'Livros, brochuras e impressos semelhantes'),
    ('4902', 'Jornais, revistas e outras publicações periódicas'),
    ('4903', 'Álbuns ou livros de ilustrações para crianças'),
    ('4904', 'Músicas manuscritas ou impressas'),
    ('4905', 'Obras cartográficas de qualquer espécie'),
]

# ── Tabela 4.3.13 — Alíquota Zero PIS/COFINS (CST 06) — fertilizantes ────────
# Cap 31 usa Lei 10.925/2004 (Tab 4.3.13), NÃO Tab 4.3.16 (suspensão)
FERTILIZANTES_ALIQ_ZERO = [
    ('3101', 'Adubos de origem animal ou vegetal'),
    ('3102', 'Adubos minerais ou químicos nitrogenados'),
    ('3103', 'Adubos minerais ou químicos fosfatados'),
    ('3104', 'Adubos minerais ou químicos potássicos'),
    ('3105', 'Outros adubos e fertilizantes minerais ou químicos'),
]

# ── Tabela 4.3.16 — Suspensão PIS/COFINS (CST 09) ────────────────────────────
INSUMOS_SUSPENSAO = [
    ('1209', 'Sementes, frutos e esporos para semeadura'),
    ('3808', 'Inseticidas, rodenticidas, fungicidas, herbicidas e similares'),
]


def _criar_ncm(ncm, descricao, grupo_id, tipo_ref, lei,
               pis_fab=1.5, cofins_fab=7.0, pis_var=0.0, cofins_var=0.0,
               cst_entrada='70', cst_saida='04', monofasico=True,
               vigencia=None, fonte=None):
    existente = NcmTributario.query.filter_by(
        ncm=ncm, grupo_tributario_id=grupo_id
    ).first()
    if existente:
        return False

    n = NcmTributario(
        ncm=ncm,
        descricao=descricao,
        grupo_tributario_id=grupo_id,
        monofasico=monofasico,
        tipo_referencia=tipo_ref,
        lei=lei,
        cst_entrada=cst_entrada,
        cst_saida=cst_saida,
        cfop_entrada_simples='1102',
        cfop_saida_simples='5102',
        pis_aliquota_fabricante=pis_fab,
        cofins_aliquota_fabricante=cofins_fab,
        pis_aliquota_varejista=pis_var,
        cofins_aliquota_varejista=cofins_var,
        vigencia_inicio=vigencia or date(2002, 1, 1),
        fonte_url=fonte or 'https://www.planalto.gov.br/ccivil_03/leis/2002/L10485compilado.htm',
        ativo=True,
    )
    db.session.add(n)
    return True


def register_commands(app):
    @app.cli.command('seed-db')
    def seed_db():
        """Popula banco com dados tributários iniciais."""
        click.echo('Iniciando seed do banco de dados...')
        inseridos = 0

        # --- Grupos tributários ---
        grupos_map = {}
        for g in GRUPOS:
            existente = GrupoTributario.query.filter_by(codigo=g['codigo']).first()
            if not existente:
                grupo = GrupoTributario(**g)
                db.session.add(grupo)
                db.session.flush()
                grupos_map[g['codigo']] = grupo.id
                click.echo(f'  Grupo criado: {g["codigo"]} - {g["nome"]}')
            else:
                grupos_map[g['codigo']] = existente.id
        db.session.commit()

        # --- Autopeças (posições de 4 dígitos) ---
        g_auto = grupos_map['G100']
        for pos in AUTOPECAS_POSICOES:
            ok = _criar_ncm(
                pos, f'Autopeça — posição {pos}', g_auto, 'posicao_4',
                'Lei nº 10.485/2002 — Anexo I', 1.5, 7.0, 0.0, 0.0,
            )
            if ok:
                inseridos += 1
        db.session.commit()
        click.echo(f'  Autopeças: {len(AUTOPECAS_POSICOES)} posições processadas')

        # --- Combustíveis ---
        g_comb = grupos_map['G200']
        for ncm, desc in COMBUSTIVEIS:
            ok = _criar_ncm(
                ncm, desc, g_comb, 'ncm_exato',
                'Lei nº 9.718/1998', 5.08, 23.44, 0.0, 0.0,
                cst_entrada='02', cst_saida='04',
                vigencia=date(1998, 1, 1),
                fonte='https://www.planalto.gov.br/ccivil_03/leis/L9718compilado.htm',
            )
            if ok:
                inseridos += 1
        db.session.commit()
        click.echo(f'  Combustíveis: {len(COMBUSTIVEIS)} NCMs processados')

        # --- Fármacos e Perfumaria (prefixos) ---
        g_farm = grupos_map['G300']
        for pref in FARMACOS_PREFIXOS:
            tipo = 'posicao_4' if len(pref) == 4 else 'prefixo'
            ok = _criar_ncm(
                pref, f'Fármaco/Perfumaria — prefixo {pref}', g_farm, tipo,
                'Lei nº 10.147/2000', 2.1, 9.9, 0.0, 0.0,
            )
            if ok:
                inseridos += 1
        db.session.commit()
        click.echo(f'  Fármacos/Perfumaria: {len(FARMACOS_PREFIXOS)} prefixos processados')

        # --- Bebidas frias (prefixos) — varejista CST 06 (Tab 4.3.13 code 918) ---
        g_beb = grupos_map['G400']
        for pref in BEBIDAS_PREFIXOS:
            ok = _criar_ncm(
                pref, f'Bebida fria — prefixo {pref}', g_beb, 'posicao_4',
                'Lei nº 13.097/2015', 1.86, 8.54, 0.0, 0.0,
                cst_entrada='02', cst_saida='06',
            )
            if ok:
                inseridos += 1
        db.session.commit()
        click.echo(f'  Bebidas frias: {len(BEBIDAS_PREFIXOS)} prefixos processados')

        # --- Pneumáticos ---
        g_pneu = grupos_map['G500']
        for pos in PNEUMATICOS_POSICOES:
            ok = _criar_ncm(
                pos, f'Pneumático — posição {pos}', g_pneu, 'posicao_4',
                'Lei nº 10.485/2002 — Art. 5º', 2.0, 9.5, 0.0, 0.0,
            )
            if ok:
                inseridos += 1
        db.session.commit()
        click.echo(f'  Pneumáticos: {len(PNEUMATICOS_POSICOES)} posições processadas')

        # --- G600 — Substituição Tributária PIS/COFINS (CST 05 / Tabela 4.3.12) ---
        g_st = grupos_map.get('G600')
        if g_st:
            for pos, desc in TABACO_ST:
                ok = _criar_ncm(
                    pos, desc, g_st, 'posicao_4',
                    'Lei nº 9.532/1997 e Lei nº 12.715/2012',
                    0.0, 0.0, 0.0, 0.0,
                    cst_entrada='05', cst_saida='05', monofasico=False,
                    vigencia=date(1997, 12, 10),
                    fonte='https://www.planalto.gov.br/ccivil_03/leis/L9532.htm',
                )
                if ok:
                    inseridos += 1
            db.session.commit()
            click.echo(f'  ST (CST 05): {len(TABACO_ST)} posições processadas')

        # --- G700 — Alíquota Zero PIS/COFINS (CST 06 / Tabela 4.3.13) ---
        g_isen = grupos_map.get('G700')
        if g_isen:
            lei_isen = 'Lei nº 10.925/2004'
            fonte_isen = 'https://www.planalto.gov.br/ccivil_03/_ato2004-2006/2004/lei/l10.925.htm'
            for pref, desc in ALIMENTOS_ISENTOS_PREFIXOS:
                ok = _criar_ncm(
                    pref, desc, g_isen, 'prefixo', lei_isen,
                    0.0, 0.0, 0.0, 0.0,
                    cst_entrada='06', cst_saida='06', monofasico=False,
                    vigencia=date(2004, 7, 23), fonte=fonte_isen,
                )
                if ok:
                    inseridos += 1
            for pos, desc in FERTILIZANTES_ALIQ_ZERO:
                ok = _criar_ncm(
                    pos, desc, g_isen, 'posicao_4', lei_isen,
                    0.0, 0.0, 0.0, 0.0,
                    cst_entrada='06', cst_saida='06', monofasico=False,
                    vigencia=date(2004, 7, 23), fonte=fonte_isen,
                )
                if ok:
                    inseridos += 1
            db.session.commit()
            click.echo(f'  Alíquota Zero (CST 06): {len(ALIMENTOS_ISENTOS_PREFIXOS)} prefixos + {len(FERTILIZANTES_ALIQ_ZERO)} fertilizantes processados')

        # --- G750 — Alíquota Zero PIS/COFINS (CST 06 / Tabela 4.3.13) ---
        g_isen_livros = grupos_map.get('G750')
        if g_isen_livros:
            for pos, desc in LIVROS_ISENTOS:
                ok = _criar_ncm(
                    pos, desc, g_isen_livros, 'posicao_4',
                    'Lei nº 10.925/2004, art. 9º, IX e Art. 150, VI, d CF/88',
                    0.0, 0.0, 0.0, 0.0,
                    cst_entrada='06', cst_saida='06', monofasico=False,
                    vigencia=date(1988, 10, 5),
                    fonte='https://www.planalto.gov.br/ccivil_03/constituicao/constituicao.htm',
                )
                if ok:
                    inseridos += 1
            db.session.commit()
            click.echo(f'  Alíquota Zero livros (CST 06): {len(LIVROS_ISENTOS)} posições processadas')

        # --- G800 — Suspensão PIS/COFINS (CST 09 / Tabela 4.3.16) ---
        g_susp = grupos_map.get('G800')
        if g_susp:
            for pos, desc in INSUMOS_SUSPENSAO:
                ok = _criar_ncm(
                    pos, desc, g_susp, 'posicao_4',
                    'Lei nº 10.865/2004 e Decreto nº 5.630/2005',
                    0.0, 0.0, 0.0, 0.0,
                    cst_entrada='09', cst_saida='09', monofasico=False,
                    vigencia=date(2004, 5, 30),
                    fonte='https://www.planalto.gov.br/ccivil_03/_ato2004-2006/2004/lei/l10.865.htm',
                )
                if ok:
                    inseridos += 1
            db.session.commit()
            click.echo(f'  Suspensão (CST 09): {len(INSUMOS_SUSPENSAO)} posições processadas')

        # --- Alíquotas iniciais por grupo (legislação vigente) ---
        ALIQUOTAS_SEED = [
            # (codigo_grupo, pis_fab, cofins_fab, pis_var, cofins_var, vigencia_inicio, lei)
            ('G100', 1.50,  7.00,  0.0, 0.0, date(2002,  1,  1), 'Lei nº 10.485/2002 — Anexos I e II'),
            # G200: valores ad rem (R$/m³), não percentuais — referência aproximada até MP vigente
            ('G200', 0.00,  0.00,  0.0, 0.0, date(1998,  1,  1), 'Lei nº 9.718/1998, Art. 4º; Lei nº 10.336/2001 — regime ad rem (R$/m³); valores atualizados por MP'),
            # G300 lista positiva (fármacos): PIS 2,1% / COFINS 9,9%
            ('G300', 2.10,  9.90,  0.0, 0.0, date(2000,  1,  1), 'Lei nº 10.147/2000 — lista positiva (fármacos)'),
            ('G400', 1.86,  8.54,  0.0, 0.0, date(2015,  1,  1), 'Lei nº 13.097/2015'),
            ('G500', 2.00,  9.50,  0.0, 0.0, date(2002,  1,  1), 'Lei nº 10.485/2002 — Art. 5º'),
            ('G600', 0.00,  0.00,  0.0, 0.0, date(1997, 12, 10), 'Legislação específica por produto — ST PIS/COFINS (CST 05)'),
            ('G700', 0.00,  0.00,  0.0, 0.0, date(2004,  7, 23), 'Lei nº 10.925/2004 (Alíquota Zero — CST 06)'),
            ('G750', 0.00,  0.00,  0.0, 0.0, date(2004,  5,  3), 'Lei nº 10.865/2004, Art. 28, VIII (Alíquota Zero — CST 06)'),
            ('G800', 0.00,  0.00,  0.0, 0.0, date(2004,  7, 23), 'Lei nº 10.925/2004, Art. 9º (doméstico) e Lei nº 10.865/2004 (importação) — Suspensão CST 09'),
        ]
        for cod, pis_f, cof_f, pis_v, cof_v, vig, lei in ALIQUOTAS_SEED:
            gid = grupos_map.get(cod)
            if not gid:
                continue
            existe = AliquotaGrupo.query.filter_by(
                grupo_tributario_id=gid, vigencia_inicio=vig,
            ).first()
            if not existe:
                db.session.add(AliquotaGrupo(
                    grupo_tributario_id=gid,
                    pis_fabricante=pis_f,
                    cofins_fabricante=cof_f,
                    pis_varejista=pis_v,
                    cofins_varejista=cof_v,
                    vigencia_inicio=vig,
                    vigencia_fim=None,
                    lei_referencia=lei,
                    observacao='Alíquota inicial — seed do sistema',
                    ativo=True,
                ))
        db.session.commit()

        # G300 lista negativa (perfumaria/higiene): PIS 2,2% / COFINS 10,3%
        g300_id = grupos_map.get('G300')
        if g300_id:
            _lei_perf = 'Lei nº 10.147/2000 — lista negativa (perfumaria e higiene pessoal)'
            existe_perf = AliquotaGrupo.query.filter_by(
                grupo_tributario_id=g300_id,
                lei_referencia=_lei_perf,
            ).first()
            if not existe_perf:
                db.session.add(AliquotaGrupo(
                    grupo_tributario_id=g300_id,
                    pis_fabricante=2.20,
                    cofins_fabricante=10.30,
                    pis_varejista=0.0,
                    cofins_varejista=0.0,
                    vigencia_inicio=date(2000, 1, 1),
                    vigencia_fim=None,
                    lei_referencia=_lei_perf,
                    observacao='Lista negativa — perfumaria, cosméticos e higiene pessoal (cap. 3303–3307, 3401). Alíquota diferente da lista positiva (fármacos).',
                    ativo=True,
                ))
                db.session.commit()
                click.echo('  G300 perfumaria (lista negativa) inserida: PIS 2,2% / COFINS 10,3%')

        click.echo('  Alíquotas iniciais por grupo criadas.')

        # --- Usuário admin ---
        admin = Usuario.query.filter_by(email='admin@tribsync.com.br').first()
        if not admin:
            admin = Usuario(
                nome='Administrador',
                email='admin@tribsync.com.br',
                perfil='admin',
                ativo=True,
            )
            admin.set_senha('TribSync@2026!')
            db.session.add(admin)
            db.session.commit()
            click.echo('  Usuário admin criado: admin@tribsync.com.br / TribSync@2026!')
        else:
            click.echo('  Usuário admin já existe.')

        # --- Log inicial ---
        log = LogAtualizacao(
            tabela_sped='seed',
            versao='1.0',
            data_atualizacao_rfb=date.today(),
            data_importacao=datetime.now(timezone.utc),
            status='seed_inicial',
            registros_inseridos=inseridos,
            registros_atualizados=0,
            mensagem='Seed com dados das tabelas SPED 4.3.10–4.3.16 (Leis 10.485/2002, 9.718/98, 10.147/2000, 13.097/2015, 10.925/2004, 10.865/2004)',
            executado_por='flask seed-db',
        )
        db.session.add(log)
        db.session.commit()

        click.echo(f'\nSeed concluído! Total de NCMs/posições inseridos: {inseridos}')
        click.echo('Login admin: admin@tribsync.com.br | Senha: TribSync@2026!')

    @app.cli.command('corrigir-sped')
    def corrigir_sped():
        """Corrige classificações tributárias: sincroniza CSTs e corrige grupos."""
        # CST correto por tabela_sped (knowledge regulatório — estático e oficial)
        TABELA_SPED_CST = {
            '4.3.10': ('04', '70'),  # Monofásico revenda/fabricante (autopeças, pneumáticos)
            '4.3.11': ('04', '02'),  # Combustíveis
            '4.3.12': ('05', '05'),  # Substituição Tributária
            '4.3.13': ('06', '06'),  # Alíquota Zero — Lei 10.925/2004
            '4.3.14': ('07', '07'),  # Isenção
            '4.3.15': ('06', '02'),  # Bebidas Frias (varejista=06 / fabricante=02)
            '4.3.16': ('09', '09'),  # Suspensão — insumos agropecuários
        }
        _campos_modelo = {'nome', 'lei_base', 'tabela_sped', 'url_tabela_sped', 'descricao'}
        atualizados = 0

        # 1. Sincronizar grupos: criar/atualizar todos conforme GRUPOS constant
        click.echo('1. Sincronizando grupos tributários...')
        grupos_map = {}
        for g in GRUPOS:
            existente = GrupoTributario.query.filter_by(codigo=g['codigo']).first()
            if existente:
                for campo in _campos_modelo:
                    if campo in g:
                        setattr(existente, campo, g[campo])
                grupos_map[g['codigo']] = existente.id
            else:
                dados = {k: v for k, v in g.items() if k in _campos_modelo | {'codigo'}}
                novo = GrupoTributario(**dados)
                db.session.add(novo)
                db.session.flush()
                grupos_map[g['codigo']] = novo.id
                click.echo(f'   Grupo criado: {g["codigo"]}')
        db.session.commit()
        click.echo('   Grupos atualizados.')

        # 2. Correções estruturais: reclassificar NCMs em grupos errados por capítulo NCM
        click.echo('2. Corrigindo NCMs em grupos incorretos por capítulo...')

        g700 = GrupoTributario.query.filter_by(codigo='G700').first()
        g800 = GrupoTributario.query.filter_by(codigo='G800').first()

        # Cap 31 (fertilizantes) pertence ao G700 (Alíquota Zero), não G800 (Suspensão)
        if g700 and g800:
            para_mover = NcmTributario.query.filter(
                NcmTributario.grupo_tributario_id == g800.id,
                NcmTributario.ativo == True,
                NcmTributario.ncm.like('31%'),
            ).all()
            for r in para_mover:
                r.grupo_tributario_id = g700.id
                atualizados += 1
            if para_mover:
                click.echo(f'   G800→G700: {len(para_mover)} fertilizantes cap 31 migrados')

        # Cap 49 (livros/publicações) pertence ao G750 (Alíquota Zero), não G700 (Alimentos)
        g750 = GrupoTributario.query.filter_by(codigo='G750').first()
        if g750 and g700:
            para_mover = NcmTributario.query.filter(
                NcmTributario.grupo_tributario_id == g700.id,
                NcmTributario.ativo == True,
                NcmTributario.ncm.like('49%'),
            ).all()
            for r in para_mover:
                r.grupo_tributario_id = g750.id
                atualizados += 1
            if para_mover:
                click.echo(f'   G700→G750: {len(para_mover)} livros cap 49 migrados')

        # Cap 87 (veículos) não pertence ao G300 (Fármacos) — desativar
        g300 = GrupoTributario.query.filter_by(codigo='G300').first()
        if g300:
            errados = NcmTributario.query.filter(
                NcmTributario.grupo_tributario_id == g300.id,
                NcmTributario.ativo == True,
                NcmTributario.ncm.like('87%'),
            ).all()
            for r in errados:
                r.ativo = False
                atualizados += 1
            if errados:
                click.echo(f'   G300: {len(errados)} NCMs cap 87 desativados (veículos ≠ fármacos)')

        # Cap 88 (aeronaves) não pertence ao G800 (Insumos Agro) — desativar
        if g800:
            errados = NcmTributario.query.filter(
                NcmTributario.grupo_tributario_id == g800.id,
                NcmTributario.ativo == True,
                NcmTributario.ncm.like('88%'),
            ).all()
            for r in errados:
                r.ativo = False
                atualizados += 1
            if errados:
                click.echo(f'   G800: {len(errados)} NCMs cap 88 desativados (aeronaves ≠ insumos agro)')

        # Cap 91 (relógios) não pertence ao G100 (Autopeças) — desativar
        g100 = GrupoTributario.query.filter_by(codigo='G100').first()
        if g100:
            errados = NcmTributario.query.filter(
                NcmTributario.grupo_tributario_id == g100.id,
                NcmTributario.ativo == True,
                NcmTributario.ncm.like('91%'),
            ).all()
            for r in errados:
                r.ativo = False
                atualizados += 1
            if errados:
                click.echo(f'   G100: {len(errados)} NCMs cap 91 desativados (relogios != autopecas)')

        db.session.commit()

        # 3. Sincronizar CST de todos os NCMs usando tabela_sped do grupo (sem listas fixas)
        click.echo('3. Sincronizando CST via tabela_sped do grupo...')
        for grupo in GrupoTributario.query.filter(GrupoTributario.tabela_sped.isnot(None)).all():
            par = TABELA_SPED_CST.get(grupo.tabela_sped)
            if not par:
                continue
            cst_saida, cst_entrada = par
            desatualizados = NcmTributario.query.filter(
                NcmTributario.grupo_tributario_id == grupo.id,
                NcmTributario.ativo == True,
                db.or_(
                    NcmTributario.cst_saida != cst_saida,
                    NcmTributario.cst_entrada != cst_entrada,
                    NcmTributario.cst_saida.is_(None),
                    NcmTributario.cst_entrada.is_(None),
                ),
            ).all()
            for r in desatualizados:
                r.cst_saida = cst_saida
                r.cst_entrada = cst_entrada
                atualizados += 1
            if desatualizados:
                click.echo(
                    f'   {grupo.codigo} (Tab {grupo.tabela_sped}): '
                    f'{len(desatualizados)} NCMs → saída={cst_saida} / entrada={cst_entrada}'
                )
        db.session.commit()

        log = LogAtualizacao(
            tabela_sped='correcao_sped',
            versao='1.2',
            data_atualizacao_rfb=date.today(),
            data_importacao=datetime.now(timezone.utc),
            status='sucesso',
            registros_inseridos=0,
            registros_atualizados=atualizados,
            mensagem='Correção SPED: sync CST por tabela_sped do grupo + caps incorretos desativados',
            executado_por='flask corrigir-sped',
        )
        db.session.add(log)
        db.session.commit()
        click.echo(f'\nCorreção SPED concluída! {atualizados} registros atualizados.')

    @app.cli.command('corrigir-aliquotas')
    def corrigir_aliquotas():
        """Corrige lei_referencia e observacao das AliquotaGrupo implantadas com dados errados."""
        atualizados = 0

        # Mapeamento: codigo_grupo → correções a aplicar nos registros existentes
        CORRECOES = {
            'G200': {
                'lei_old': ['Lei nº 9.718/1998', 'Lei nº 9.718/1998 (ad rem — R$/m³)'],
                'lei_new': 'Lei nº 9.718/1998, Art. 4º; Lei nº 10.336/2001 — regime ad rem (R$/m³); valores atualizados por MP',
                'obs_new': 'Atenção: alíquotas ad rem (R$/m³ ou R$/litro), não percentuais. Os campos pis_fabricante/cofins_fabricante não representam % mas servem de referência enquanto o regime ad rem não for implementado no modelo.',
                'pis_fab': None,  # não altera o valor numérico
                'cof_fab': None,
            },
            'G300': {
                # Corrige a entrada existente para deixar claro que é lista positiva
                'lei_old': ['Lei nº 10.147/2000', 'Lei nº 10.147/2000 (Monofásico — CST 04)'],
                'lei_new': 'Lei nº 10.147/2000 — lista positiva (fármacos)',
                'obs_new': 'Fármacos da lista positiva (cap. 30, 3001–3004): PIS 2,1% / COFINS 9,9%. Para perfumaria/higiene (lista negativa 3303–3307, 3401) ver registro separado.',
                'pis_fab': None,
                'cof_fab': None,
            },
            'G600': {
                'lei_old': ['Lei nº 9.532/1997 (ST — CST 05)', 'Lei nº 9.532/1997 e Lei nº 12.715/2012'],
                'lei_new': 'Legislação específica por produto — ST PIS/COFINS (CST 05)',
                'obs_new': 'Não há lei geral para ST de PIS/COFINS — cada produto tem legislação própria. Ex.: tabaco: Lei 9.715/1998. (Lei 9.532/1997 refere-se a IRPJ/CSLL, não a PIS/COFINS.)',
                'pis_fab': None,
                'cof_fab': None,
            },
            'G700': {
                'lei_old': ['Isenção CST 07', 'Lei nº 10.925/2004 (Isenção — CST 07)', 'Art. 150, VI, d CF/88 (Isenção — CST 07)'],
                'lei_new': 'Lei nº 10.925/2004 (Alíquota Zero — CST 06)',
                'obs_new': 'CST correto é 06 (alíquota zero), não 07 (isenção). O sistema já aplica CST 06 nos processamentos de lote.',
                'pis_fab': None,
                'cof_fab': None,
            },
            'G750': {
                'lei_old': [
                    'Art. 150, VI, d CF/88 (Isenção — CST 07)',
                    'Lei nº 10.925/2004, art. 9º, IX e Art. 150, VI, d CF/88',
                    'Art. 150 VI d CF/88',
                ],
                'lei_new': 'Lei nº 10.865/2004, Art. 28, VIII (Alíquota Zero — CST 06)',
                'obs_new': 'O Art. 150, VI, d CF/88 confere imunidade de ICMS e IPI sobre livros, não de PIS/COFINS. Para as contribuições, a alíquota zero está na Lei 10.865/2004, Art. 28, VIII (CST 06).',
                'pis_fab': None,
                'cof_fab': None,
            },
            'G800': {
                'lei_old': [
                    'Lei nº 10.865/2004 (Suspensão — CST 09)',
                    'Lei nº 10.865/2004 e Decreto nº 5.630/2005',
                ],
                'lei_new': 'Lei nº 10.925/2004, Art. 9º (doméstico) e Lei nº 10.865/2004 (importação) — Suspensão CST 09',
                'obs_new': 'Operações domésticas: Lei 10.925/2004, Art. 9º. Importações: Lei 10.865/2004 e Decreto 5.630/2005.',
                'pis_fab': None,
                'cof_fab': None,
            },
        }

        click.echo('Corrigindo AliquotaGrupo — lei_referencia e observacao...')
        for cod, corr in CORRECOES.items():
            grupo = GrupoTributario.query.filter_by(codigo=cod).first()
            if not grupo:
                click.echo(f'  {cod}: grupo não encontrado, pulando.')
                continue
            registros = AliquotaGrupo.query.filter_by(grupo_tributario_id=grupo.id).all()
            for r in registros:
                if r.lei_referencia in corr['lei_old'] or any(
                    old.lower() in (r.lei_referencia or '').lower() for old in corr['lei_old']
                ):
                    r.lei_referencia = corr['lei_new']
                    r.observacao = corr['obs_new']
                    if corr.get('pis_fab') is not None:
                        r.pis_fabricante = corr['pis_fab']
                    if corr.get('cof_fab') is not None:
                        r.cofins_fabricante = corr['cof_fab']
                    atualizados += 1
                    click.echo(f'  {cod}: atualizado (id={r.id})')
        db.session.commit()

        # G300 lista negativa (perfumaria) — adiciona se não existir
        g300 = GrupoTributario.query.filter_by(codigo='G300').first()
        if g300:
            _lei_perf = 'Lei nº 10.147/2000 — lista negativa (perfumaria e higiene pessoal)'
            existe_perf = AliquotaGrupo.query.filter_by(
                grupo_tributario_id=g300.id,
                lei_referencia=_lei_perf,
            ).first()
            if not existe_perf:
                db.session.add(AliquotaGrupo(
                    grupo_tributario_id=g300.id,
                    pis_fabricante=2.20,
                    cofins_fabricante=10.30,
                    pis_varejista=0.0,
                    cofins_varejista=0.0,
                    vigencia_inicio=date(2000, 1, 1),
                    vigencia_fim=None,
                    lei_referencia=_lei_perf,
                    observacao='Lista negativa — perfumaria, cosméticos e higiene pessoal (cap. 3303–3307, 3401). PIS 2,2% / COFINS 10,3% — diferente da lista positiva (fármacos: PIS 2,1% / COFINS 9,9%).',
                    ativo=True,
                ))
                db.session.commit()
                click.echo('  G300: registro de perfumaria (lista negativa) inserido.')
                atualizados += 1

        # Sincroniza lei_base dos grupos conforme constante GRUPOS atualizada
        click.echo('Sincronizando lei_base dos GrupoTributario...')
        for g in GRUPOS:
            existente = GrupoTributario.query.filter_by(codigo=g['codigo']).first()
            if existente:
                existente.lei_base = g['lei_base']
                existente.descricao = g['descricao']
        db.session.commit()
        click.echo('  lei_base e descricao dos grupos atualizados.')

        log = LogAtualizacao(
            tabela_sped='correcao_aliquotas',
            versao='1.0',
            data_atualizacao_rfb=date.today(),
            data_importacao=datetime.now(timezone.utc),
            status='sucesso',
            registros_inseridos=0,
            registros_atualizados=atualizados,
            mensagem='Correção de lei_referencia/observacao: G200 ad rem, G300 dual lista, G600 lei errada, G700 CST 07→06, G750 CF/88→10.865/2004, G800 lei doméstica',
            executado_por='flask corrigir-aliquotas',
        )
        db.session.add(log)
        db.session.commit()
        click.echo(f'\ncorrigir-aliquotas concluído! {atualizados} registros corrigidos/inseridos.')

    @app.cli.command('corrigir-etanol')
    def corrigir_etanol():
        """Migração: desativa 2207 em Bebidas Frias e insere etanol em Combustíveis."""
        g_beb = GrupoTributario.query.filter_by(codigo='G400').first()
        if g_beb:
            registros_beb = NcmTributario.query.filter(
                NcmTributario.grupo_tributario_id == g_beb.id,
                NcmTributario.ncm.like('2207%'),
                NcmTributario.ativo == True,
            ).all()
            for r in registros_beb:
                r.ativo = False
                r.updated_at = datetime.now(timezone.utc)
            if registros_beb:
                click.echo(f'  Desativados {len(registros_beb)} NCM(s) 2207* em Bebidas Frias.')

        g_comb = GrupoTributario.query.filter_by(codigo='G200').first()
        if not g_comb:
            click.echo('Grupo G200 (Combustíveis) não encontrado. Execute seed-db primeiro.')
            return

        etanol = [
            ('22071090', 'Álcool etílico não desnaturado — etanol hidratado combustível (EHC)'),
            ('22072000', 'Álcool etílico desnaturado — etanol anidro combustível (EAC)'),
        ]
        inseridos = 0
        for ncm, desc in etanol:
            existente = NcmTributario.query.filter_by(
                ncm=ncm, grupo_tributario_id=g_comb.id
            ).first()
            if existente:
                existente.ativo = True
                existente.updated_at = datetime.now(timezone.utc)
                click.echo(f'  Reativado: {ncm}')
            else:
                ok = _criar_ncm(
                    ncm, desc, g_comb.id, 'ncm_exato',
                    'Lei nº 9.718/1998', 5.08, 23.44, 0.0, 0.0,
                    cst_entrada='02', cst_saida='04',
                    vigencia=date(1998, 1, 1),
                    fonte='https://www.planalto.gov.br/ccivil_03/leis/L9718compilado.htm',
                )
                if ok:
                    inseridos += 1
                    click.echo(f'  Inserido: {ncm} — {desc}')

        db.session.commit()
        click.echo(f'Correção concluída: {inseridos} NCM(s) inseridos em Combustíveis.')

    @app.cli.command('criar-usuario')
    @click.argument('email')
    @click.argument('senha')
    @click.option('--nome', default='Usuário', help='Nome do usuário')
    @click.option('--perfil', default='operador', help='admin|operador|visualizador')
    def criar_usuario(email, senha, nome, perfil):
        """Cria um novo usuário."""
        if Usuario.query.filter_by(email=email).first():
            click.echo(f'Usuário {email} já existe.')
            return
        u = Usuario(nome=nome, email=email, perfil=perfil)
        u.set_senha(senha)
        db.session.add(u)
        db.session.commit()
        click.echo(f'Usuário criado: {email} ({perfil})')
