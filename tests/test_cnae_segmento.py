"""
Testes do motor de inferência CNAE → grupos tributários.
Todos os testes desta suite são puros (sem acesso ao banco).
"""
import pytest
from app.services.cnae_segmento import inferir_segmentos, validar_ncm_vs_empresa


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

class _FakeEmpresa:
    """Substituto simples de Empresa para testes sem banco."""
    def __init__(self, inferidos=None, override=None, regime='simples_nacional'):
        self.segmentos_inferidos = inferidos or []
        self.segmentos_override = override or []
        self.regime_tributario = regime

    @property
    def segmentos_efetivos(self):
        return set(self.segmentos_inferidos) | set(self.segmentos_override)


# ---------------------------------------------------------------------------
# inferir_segmentos
# ---------------------------------------------------------------------------

def test_inferir_veiculos_prefixo_2():
    assert 'G100' in inferir_segmentos('4511', [])
    assert 'G500' in inferir_segmentos('4511', [])


def test_inferir_combustivel_prefixo_4():
    assert inferir_segmentos('4741', []) == {'G200'}


def test_inferir_farmacia():
    assert inferir_segmentos('4771', []) == {'G300'}


def test_inferir_alimentos_prefixo_4():
    assert 'G700' in inferir_segmentos('4729', [])


def test_inferir_agropecuaria_prefixo_2():
    for cnae in ('01', '02', '03'):
        assert 'G800' in inferir_segmentos(cnae, [])


def test_inferir_prioridade_4_sobre_2():
    # CNAE '4511' deve mapear para G100/G500 (4 dígitos), não para o genérico '45'
    resultado = inferir_segmentos('4511', [])
    assert resultado == {'G100', 'G500'}


def test_inferir_com_mascara():
    # CNAE com máscara deve ser normalizado
    assert 'G300' in inferir_segmentos('4771-7/01', [])
    assert 'G100' in inferir_segmentos('45.11-1', [])


def test_inferir_cnae_vazio():
    assert inferir_segmentos('', []) == set()
    assert inferir_segmentos(None, []) == set()


def test_inferir_cnae_desconhecido():
    # CNAE que não está no mapa
    assert inferir_segmentos('9999', []) == set()


def test_inferir_secundarios():
    # CNAE principal = supermercado (G700) + secundário = farmácia (G300)
    resultado = inferir_segmentos('4711', ['4771'])
    assert 'G700' in resultado
    assert 'G300' in resultado


def test_inferir_prefixo_2_bebidas():
    assert 'G400' in inferir_segmentos('11', [])


def test_inferir_prefixo_2_farmaceutico():
    assert 'G300' in inferir_segmentos('21', [])


# ---------------------------------------------------------------------------
# Empresa.segmentos_efetivos
# ---------------------------------------------------------------------------

def test_segmentos_efetivos_uniao():
    e = _FakeEmpresa(inferidos=['G100'], override=['G300'])
    assert e.segmentos_efetivos == {'G100', 'G300'}


def test_segmentos_efetivos_sobreposicao():
    e = _FakeEmpresa(inferidos=['G100', 'G200'], override=['G100', 'G500'])
    assert e.segmentos_efetivos == {'G100', 'G200', 'G500'}


def test_segmentos_efetivos_ambos_vazios():
    e = _FakeEmpresa()
    assert e.segmentos_efetivos == set()


def test_segmentos_efetivos_so_inferidos():
    e = _FakeEmpresa(inferidos=['G700'])
    assert e.segmentos_efetivos == {'G700'}


def test_segmentos_efetivos_so_override():
    e = _FakeEmpresa(override=['G600'])
    assert e.segmentos_efetivos == {'G600'}


# ---------------------------------------------------------------------------
# validar_ncm_vs_empresa
# ---------------------------------------------------------------------------

def test_validar_sem_segmentos():
    """Empresa sem segmentos configurados → sempre OK."""
    e = _FakeEmpresa()
    item = {'ncm': '87084090', 'grupo': 'Veículos e Autopeças'}
    r = validar_ncm_vs_empresa(item, e)
    assert r['ok'] is True
    assert r['severidade'] == 'OK'


def test_validar_grupo_dentro():
    e = _FakeEmpresa(inferidos=['G100'])
    item = {'ncm': '87084090', 'grupo': 'Veículos e Autopeças'}
    r = validar_ncm_vs_empresa(item, e)
    assert r['ok'] is True
    assert r['severidade'] == 'OK'


def test_validar_critica_simples_nacional():
    e = _FakeEmpresa(inferidos=['G700'], regime='simples_nacional')
    item = {'ncm': '27101259', 'grupo': 'Combustíveis e Derivados'}
    r = validar_ncm_vs_empresa(item, e)
    assert r['ok'] is False
    assert r['severidade'] == 'CRITICA'
    assert 'PGDAS' in r['mensagem']


def test_validar_alerta_lucro_real():
    e = _FakeEmpresa(inferidos=['G700'], regime='lucro_real')
    item = {'ncm': '27101259', 'grupo': 'Combustíveis e Derivados'}
    r = validar_ncm_vs_empresa(item, e)
    assert r['ok'] is False
    assert r['severidade'] == 'ALERTA'


def test_validar_alerta_lucro_presumido():
    e = _FakeEmpresa(inferidos=['G700'], regime='lucro_presumido')
    item = {'ncm': '27101259', 'grupo': 'Combustíveis e Derivados'}
    r = validar_ncm_vs_empresa(item, e)
    assert r['ok'] is False
    assert r['severidade'] == 'ALERTA'


def test_validar_grupo_nao_mapeado():
    """Grupo sem código mapeado (ex: NCM não localizado) → OK."""
    e = _FakeEmpresa(inferidos=['G700'])
    item = {'ncm': '99999999', 'grupo': ''}
    r = validar_ncm_vs_empresa(item, e)
    assert r['ok'] is True


def test_validar_override_permite():
    """Grupo adicionado via override deve ser aceito."""
    e = _FakeEmpresa(inferidos=['G700'], override=['G200'])
    item = {'ncm': '27101259', 'grupo': 'Combustíveis e Derivados'}
    r = validar_ncm_vs_empresa(item, e)
    assert r['ok'] is True


def test_validar_empresa_none():
    r = validar_ncm_vs_empresa({'ncm': '8708', 'grupo': 'Veículos e Autopeças'}, None)
    assert r['ok'] is True
