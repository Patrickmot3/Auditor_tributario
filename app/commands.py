"""
Comandos CLI Flask para inicialização e manutenção do banco.
"""
import click
from datetime import date, datetime, timezone
from flask import current_app
from app.extensions import db
from app.models.ncm import GrupoTributario, NcmTributario
from app.models.usuario import Usuario
from app.models.base_tributaria import LogAtualizacao


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


def _criar_ncm(ncm, descricao, grupo_id, tipo_ref, lei,
               pis_fab=1.5, cofins_fab=7.0, pis_var=0.0, cofins_var=0.0,
               cst_entrada='70', cst_saida='04'):
    existente = NcmTributario.query.filter_by(
        ncm=ncm, grupo_tributario_id=grupo_id
    ).first()
    if existente:
        return False

    n = NcmTributario(
        ncm=ncm,
        descricao=descricao,
        grupo_tributario_id=grupo_id,
        monofasico=True,
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
        vigencia_inicio=date(2002, 1, 1),
        fonte_url='https://www.planalto.gov.br/ccivil_03/leis/2002/L10485compilado.htm',
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
            mensagem='Seed inicial com dados da Lei 10.485/2002, 9.718/98, 10.147/2000 e 13.097/2015',
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
