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
        'nome': 'Alimentos Básicos e Livros — Isenção PIS/COFINS',
        'lei_base': 'Lei nº 10.925/2004, Art. 150 CF/88',
        'tabela_sped': '4.3.14',
        'url_tabela_sped': 'http://sped.rfb.gov.br/pasta/show/1616',
        'descricao': 'Alimentos básicos, livros, jornais e periódicos isentos de PIS/COFINS (CST 07).',
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
]

FARMACOS_PREFIXOS = ['3003', '3004', '3303', '3304', '3305', '3306', '3307', '3401']

BEBIDAS_PREFIXOS = ['2201', '2202', '2203', '2204', '2205', '2206', '2207', '2208']

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

# ── Tabela 4.3.16 — Suspensão PIS/COFINS (CST 09) ────────────────────────────
INSUMOS_SUSPENSAO = [
    ('1209', 'Sementes, frutos e esporos para semeadura'),
    ('3101', 'Adubos de origem animal ou vegetal'),
    ('3102', 'Adubos minerais ou químicos nitrogenados'),
    ('3103', 'Adubos minerais ou químicos fosfatados'),
    ('3104', 'Adubos minerais ou químicos potássicos'),
    ('3105', 'Outros adubos e fertilizantes minerais ou químicos'),
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
                cst_entrada='04', cst_saida='04',
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

        # --- Bebidas frias (prefixos) ---
        g_beb = grupos_map['G400']
        for pref in BEBIDAS_PREFIXOS:
            ok = _criar_ncm(
                pref, f'Bebida fria — prefixo {pref}', g_beb, 'posicao_4',
                'Lei nº 13.097/2015', 1.86, 8.54, 0.0, 0.0,
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

        # --- G700 — Isenção PIS/COFINS (CST 07 / Tabela 4.3.14) ---
        g_isen = grupos_map.get('G700')
        if g_isen:
            lei_isen = 'Lei nº 10.925/2004'
            fonte_isen = 'https://www.planalto.gov.br/ccivil_03/_ato2004-2006/2004/lei/l10.925.htm'
            for pref, desc in ALIMENTOS_ISENTOS_PREFIXOS:
                ok = _criar_ncm(
                    pref, desc, g_isen, 'prefixo', lei_isen,
                    0.0, 0.0, 0.0, 0.0,
                    cst_entrada='07', cst_saida='07', monofasico=False,
                    vigencia=date(2004, 7, 23), fonte=fonte_isen,
                )
                if ok:
                    inseridos += 1
            for pos, desc in LIVROS_ISENTOS:
                ok = _criar_ncm(
                    pos, desc, g_isen, 'posicao_4',
                    'Art. 150, VI, d CF/88 e Lei nº 10.833/2003',
                    0.0, 0.0, 0.0, 0.0,
                    cst_entrada='07', cst_saida='07', monofasico=False,
                    vigencia=date(2004, 1, 1),
                    fonte='https://www.planalto.gov.br/ccivil_03/leis/2003/l10.833.htm',
                )
                if ok:
                    inseridos += 1
            db.session.commit()
            click.echo(f'  Isenção (CST 07): {len(ALIMENTOS_ISENTOS_PREFIXOS) + len(LIVROS_ISENTOS)} entradas processadas')

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
            ('G700', 0.00,  0.00,  0.0, 0.0, date(2004,  7, 23), 'Lei nº 10.925/2004 (Isenção — CST 07)'),
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
