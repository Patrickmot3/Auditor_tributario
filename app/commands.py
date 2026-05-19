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
        'lei_base': 'Lei nº 9.718/1998',
        'tabela_sped': '4.3.11',
        'url_tabela_sped': 'http://sped.rfb.gov.br/arquivo/download/5786',
        'descricao': 'Combustíveis sujeitos ao regime monofásico.',
    },
    {
        'codigo': 'G300',
        'nome': 'Fármacos e Perfumaria',
        'lei_base': 'Lei nº 10.147/2000',
        'tabela_sped': '4.3.13',
        'url_tabela_sped': 'http://sped.rfb.gov.br/arquivo/download/1643',
        'descricao': 'Produtos farmacêuticos e de higiene pessoal sujeitos ao regime monofásico.',
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
        'lei_base': 'Lei nº 9.532/1997 e Lei nº 12.715/2012',
        'tabela_sped': '4.3.12',
        'url_tabela_sped': 'http://sped.rfb.gov.br/pasta/show/1616',
        'descricao': 'Produtos sujeitos a PIS/COFINS por Substituição Tributária (CST 05).',
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
        'nome': 'Livros e Publicações — Isenção PIS/COFINS',
        'lei_base': 'Art. 150, VI, d CF/88 e Lei nº 10.833/2003',
        'tabela_sped': '4.3.14',
        'url_tabela_sped': 'http://sped.rfb.gov.br/pasta/show/1616',
        'descricao': 'Livros, jornais e periódicos isentos de PIS/COFINS (CST 07).',
    },
    {
        'codigo': 'G800',
        'nome': 'Insumos Agropecuários — Suspensão PIS/COFINS',
        'lei_base': 'Lei nº 10.865/2004 e Decreto nº 5.630/2005',
        'tabela_sped': '4.3.16',
        'url_tabela_sped': 'http://sped.rfb.gov.br/pasta/show/1616',
        'descricao': 'Insumos agropecuários com recolhimento de PIS/COFINS suspenso (CST 09).',
    },
]

# NCMs Lei 10.485/2002 (Anexo I) — posições de 4 dígitos
AUTOPECAS_POSICOES = [
    '4016', '6813', '7007', '7009', '7320', '8301', '8302', '8407', '8408',
    '8409', '8413', '8414', '8415', '8421', '8431', '8433', '8481', '8483',
    '8505', '8507', '8511', '8512', '8527', '8536', '8539', '8544', '8706',
    '8707', '8708', '9029', '9030', '9032', '9104', '9401',
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

# ── Tabela 4.3.14 — Isenção PIS/COFINS (CST 07) ──────────────────────────────
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

        # --- G750 — Isenção PIS/COFINS (CST 07 / Tabela 4.3.14) ---
        g_isen_livros = grupos_map.get('G750')
        if g_isen_livros:
            for pos, desc in LIVROS_ISENTOS:
                ok = _criar_ncm(
                    pos, desc, g_isen_livros, 'posicao_4',
                    'Art. 150, VI, d CF/88 e Lei nº 10.833/2003',
                    0.0, 0.0, 0.0, 0.0,
                    cst_entrada='07', cst_saida='07', monofasico=False,
                    vigencia=date(1988, 10, 5),
                    fonte='https://www.planalto.gov.br/ccivil_03/constituicao/constituicao.htm',
                )
                if ok:
                    inseridos += 1
            db.session.commit()
            click.echo(f'  Isenção (CST 07): {len(LIVROS_ISENTOS)} posições de livros processadas')

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
            ('G200', 5.08,  23.44, 0.0, 0.0, date(1998,  1,  1), 'Lei nº 9.718/1998'),
            ('G300', 2.10,  9.90,  0.0, 0.0, date(2000,  1,  1), 'Lei nº 10.147/2000'),
            ('G400', 1.86,  8.54,  0.0, 0.0, date(2015,  1,  1), 'Lei nº 13.097/2015'),
            ('G500', 2.00,  9.50,  0.0, 0.0, date(2002,  1,  1), 'Lei nº 10.485/2002 — Art. 5º'),
            ('G600', 0.00,  0.00,  0.0, 0.0, date(1997, 12, 10), 'Lei nº 9.532/1997 (ST — CST 05)'),
            ('G700', 0.00,  0.00,  0.0, 0.0, date(2004,  7, 23), 'Lei nº 10.925/2004 (Alíquota Zero — CST 06)'),
            ('G750', 0.00,  0.00,  0.0, 0.0, date(1988, 10,  5), 'Art. 150, VI, d CF/88 (Isenção — CST 07)'),
            ('G800', 0.00,  0.00,  0.0, 0.0, date(2004,  5, 30), 'Lei nº 10.865/2004 (Suspensão — CST 09)'),
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
        """Corrige classificações tributárias conforme validação SPED (Tab 4.3.x)."""
        atualizados = 0

        # 1. Atualizar G700: Isenção → Alíquota Zero (CST 06, Tab 4.3.13)
        g700 = GrupoTributario.query.filter_by(codigo='G700').first()
        if g700:
            g700.nome = 'Alimentos Básicos — Alíquota Zero PIS/COFINS'
            g700.tabela_sped = '4.3.13'
            g700.lei_base = 'Lei nº 10.925/2004'
            g700.descricao = 'Alimentos básicos com PIS/COFINS a alíquota zero (CST 06) — Lei 10.925/2004.'
            g700.url_tabela_sped = 'http://sped.rfb.gov.br/arquivo/download/1643'
            click.echo('  G700 atualizado: Alíquota Zero CST 06 (Tab 4.3.13)')

        # 2. Criar G750: Livros → Isenção (CST 07, Tab 4.3.14)
        g750 = GrupoTributario.query.filter_by(codigo='G750').first()
        if not g750:
            g750 = GrupoTributario(
                codigo='G750',
                nome='Livros e Publicações — Isenção PIS/COFINS',
                lei_base='Art. 150, VI, d CF/88 e Lei nº 10.833/2003',
                tabela_sped='4.3.14',
                url_tabela_sped='http://sped.rfb.gov.br/pasta/show/1616',
                descricao='Livros, jornais e periódicos isentos de PIS/COFINS (CST 07).',
            )
            db.session.add(g750)
            db.session.flush()
            click.echo('  G750 criado: Livros — Isenção CST 07 (Tab 4.3.14)')

        # 3. Mover livros (4901-4905) do G700 para G750 e corrigir alimentos para CST 06
        livros_pos = {'4901', '4902', '4903', '4904', '4905'}
        if g700 and g750:
            ncms_g700 = NcmTributario.query.filter_by(
                grupo_tributario_id=g700.id, ativo=True
            ).all()
            for r in ncms_g700:
                if r.ncm in livros_pos:
                    r.grupo_tributario_id = g750.id
                    r.cst_saida = '07'
                    r.cst_entrada = '07'
                    atualizados += 1
                elif r.cst_saida in ('07', None):
                    r.cst_saida = '06'
                    r.cst_entrada = '06'
                    atualizados += 1
            click.echo(f'  G700/G750: {atualizados} NCMs corrigidos (alimentos→CST06, livros→G750 CST07)')

        # 4a. Migrar fertilizantes (cap 31) do G800 para G700 → CST 06
        g800 = GrupoTributario.query.filter_by(codigo='G800').first()
        fertilizantes_pos = {'3101', '3102', '3103', '3104', '3105'}
        corr_fert = 0
        if g800 and g700:
            for r in NcmTributario.query.filter_by(
                grupo_tributario_id=g800.id, ativo=True
            ).filter(NcmTributario.ncm.in_(fertilizantes_pos)).all():
                r.grupo_tributario_id = g700.id
                r.cst_saida = '06'
                r.cst_entrada = '06'
                corr_fert += 1
                atualizados += 1
            if corr_fert:
                click.echo(f'  G800→G700: {corr_fert} fertilizantes cap 31 corrigidos para CST 06')

        # 4b. Corrigir G400 (Bebidas Frias) varejista: CST 04 → CST 06 (Tab 4.3.13 code 918)
        g400 = GrupoTributario.query.filter_by(codigo='G400').first()
        corr_g400 = 0
        if g400:
            for r in NcmTributario.query.filter_by(
                grupo_tributario_id=g400.id, ativo=True
            ).filter(NcmTributario.cst_saida == '04').all():
                r.cst_saida = '06'
                corr_g400 += 1
                atualizados += 1
            if corr_g400:
                click.echo(f'  G400: {corr_g400} NCMs bebidas frias corrigidos para CST 06')

        # 5. Garantir CST 09 em todos os registros do G800 (Suspensão)
        corr_g800 = 0
        if g800:
            for r in NcmTributario.query.filter_by(
                grupo_tributario_id=g800.id, ativo=True
            ).filter(db.or_(NcmTributario.cst_saida.is_(None),
                             NcmTributario.cst_saida != '09')).all():
                r.cst_saida = '09'
                r.cst_entrada = '09'
                corr_g800 += 1
                atualizados += 1
            if corr_g800:
                click.echo(f'  G800: {corr_g800} NCMs corrigidos para CST 09')

        # 6. Desativar NCMs cap 87 em G300 (Fármacos) — cap 87 = Veículos, não fármaco
        g300 = GrupoTributario.query.filter_by(codigo='G300').first()
        corr_g300 = 0
        if g300:
            for r in NcmTributario.query.filter_by(
                grupo_tributario_id=g300.id, ativo=True
            ).filter(NcmTributario.ncm.like('87%')).all():
                r.ativo = False
                corr_g300 += 1
                atualizados += 1
            if corr_g300:
                click.echo(f'  G300: {corr_g300} NCMs cap 87 desativados (cap 87 não é fármaco)')

        # 7. Desativar NCMs cap 88 em G800 — cap 88 = Aeronaves, não insumo agropecuário
        corr_g800_88 = 0
        if g800:
            for r in NcmTributario.query.filter_by(
                grupo_tributario_id=g800.id, ativo=True
            ).filter(NcmTributario.ncm.like('88%')).all():
                r.ativo = False
                corr_g800_88 += 1
                atualizados += 1
            if corr_g800_88:
                click.echo(f'  G800: {corr_g800_88} NCMs cap 88 desativados (cap 88 = aeronaves)')

        # 8. Desativar NCMs cap 91 em G100 — cap 91 = Relógios, não autopeça
        g100 = GrupoTributario.query.filter_by(codigo='G100').first()
        corr_g100 = 0
        if g100:
            for r in NcmTributario.query.filter_by(
                grupo_tributario_id=g100.id, ativo=True
            ).filter(NcmTributario.ncm.like('91%')).all():
                r.ativo = False
                corr_g100 += 1
                atualizados += 1
            if corr_g100:
                click.echo(f'  G100: {corr_g100} NCMs cap 91 desativados (cap 91 = relógios)')

        db.session.commit()

        log = LogAtualizacao(
            tabela_sped='correcao_sped',
            versao='1.1',
            data_atualizacao_rfb=date.today(),
            data_importacao=datetime.now(timezone.utc),
            status='sucesso',
            registros_inseridos=0,
            registros_atualizados=atualizados,
            mensagem=(
                'Correção SPED: G700→CST06 Tab4.3.13, G750 criado CST07 Tab4.3.14, '
                'G800→CST09, caps 87/88/91 corrigidos'
            ),
            executado_por='flask corrigir-sped',
        )
        db.session.add(log)
        db.session.commit()
        click.echo(f'\nCorreção SPED concluída! {atualizados} registros atualizados.')

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
