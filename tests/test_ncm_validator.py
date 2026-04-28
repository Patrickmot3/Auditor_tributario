"""
Testes do validador NCM.
"""
import pytest
from app import create_app
from app.extensions import db as _db


@pytest.fixture(scope='session')
def app():
    app = create_app('development')
    app.config['TESTING'] = True
    with app.app_context():
        yield app


@pytest.fixture(scope='session')
def db(app):
    with app.app_context():
        yield _db


def test_app_cria_sem_erros(app):
    assert app is not None


def test_normalizar_ncm():
    from app.services.ncm_validator import _normalizar_ncm
    assert _normalizar_ncm('8708.40.90') == '87084090'
    assert _normalizar_ncm('8708-40-90') == '87084090'
    assert _normalizar_ncm(' 87084090 ') == '87084090'
    assert _normalizar_ncm('') == ''


def test_cnae_automotivo():
    from app.services.ncm_validator import _cnae_automotivo
    assert _cnae_automotivo('4511') is True
    assert _cnae_automotivo('4511-1') is True
    assert _cnae_automotivo('4711') is False
    assert _cnae_automotivo('') is False


def test_ncm_autopeca_monofasico(db, app):
    """NCM 87084090 deve ser monofásico (autopeça — posição 8708)."""
    with app.app_context():
        from app.models.ncm import NcmTributario
        registro = NcmTributario.query.filter(
            NcmTributario.ncm == '8708',
            NcmTributario.monofasico == True,
        ).first()
        assert registro is not None, 'Posição 8708 deve estar cadastrada como monofásica'


def test_ncm_combustivel_monofasico(db, app):
    """NCM 27101259 (gasolina) deve ser monofásico."""
    with app.app_context():
        from app.models.ncm import NcmTributario
        registro = NcmTributario.query.filter(
            NcmTributario.ncm == '27101259',
            NcmTributario.monofasico == True,
        ).first()
        assert registro is not None, 'NCM 27101259 deve estar cadastrado como monofásico'


def test_ncm_farmaco_monofasico(db, app):
    """Prefixo 3003 (medicamentos) deve ser monofásico."""
    with app.app_context():
        from app.models.ncm import NcmTributario
        registro = NcmTributario.query.filter(
            NcmTributario.ncm == '3003',
            NcmTributario.monofasico == True,
        ).first()
        assert registro is not None, 'Prefixo 3003 deve estar cadastrado como monofásico'


def test_grupos_tributarios_seed(db, app):
    """Todos os 5 grupos tributários devem estar no banco após seed."""
    with app.app_context():
        from app.models.ncm import GrupoTributario
        count = GrupoTributario.query.count()
        assert count >= 5, f'Esperado >= 5 grupos, encontrado {count}'


def test_usuario_admin_criado(db, app):
    """Usuário admin deve existir após seed."""
    with app.app_context():
        from app.models.usuario import Usuario
        admin = Usuario.query.filter_by(email='admin@tribsync.com.br').first()
        assert admin is not None
        assert admin.perfil == 'admin'
        assert admin.check_senha('TribSync@2026!')
