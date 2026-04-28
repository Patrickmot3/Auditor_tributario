from flask import Blueprint, jsonify, request
from flask_login import login_required, current_user
from app.extensions import db
from app.models.empresa import Empresa
from app.models.consulta import Consulta
from app.models.base_tributaria import LogAtualizacao
from app.services.ncm_validator import validar_ncm, _normalizar_ncm

api_bp = Blueprint('api', __name__)


@api_bp.route('/status')
def status():
    log = LogAtualizacao.query.filter(
        LogAtualizacao.status.in_(['sucesso', 'seed_inicial'])
    ).order_by(LogAtualizacao.data_importacao.desc()).first()

    return jsonify({
        'status': 'online',
        'sistema': 'TribSync — Validador Tributário NCM',
        'versao': '1.0',
        'ultima_atualizacao_tabela': log.data_importacao.strftime('%d/%m/%Y %H:%M') if log else None,
    })


@api_bp.route('/ncm/validar', methods=['POST'])
@login_required
def validar():
    data = request.get_json(force=True)
    ncm = data.get('ncm', '')
    empresa_id = data.get('empresa_id')
    cst_atual = data.get('cst_atual')

    if not ncm or not empresa_id:
        return jsonify({'erro': 'ncm e empresa_id são obrigatórios'}), 400

    resultado = validar_ncm(ncm, empresa_id, cst_atual)
    return jsonify(resultado)


@api_bp.route('/ncm/validar-lote', methods=['POST'])
@login_required
def validar_lote():
    data = request.get_json(force=True)
    ncms = data.get('ncms', [])
    empresa_id = data.get('empresa_id')

    if not ncms or not empresa_id:
        return jsonify({'erro': 'ncms (lista) e empresa_id são obrigatórios'}), 400

    resultados = []
    for ncm in ncms:
        res = validar_ncm(ncm, empresa_id)
        resultados.append(res)

    return jsonify({'resultados': resultados, 'total': len(resultados)})


@api_bp.route('/consultas/<cnpj>')
@login_required
def consultas_empresa(cnpj):
    cnpj_limpo = cnpj.replace('.', '').replace('/', '').replace('-', '')
    empresa = Empresa.query.filter_by(cnpj=cnpj_limpo).first()
    if not empresa:
        return jsonify({'erro': 'Empresa não encontrada'}), 404

    page = request.args.get('page', 1, type=int)
    consultas = Consulta.query.filter_by(empresa_id=empresa.id).order_by(
        Consulta.created_at.desc()
    ).paginate(page=page, per_page=50)

    return jsonify({
        'empresa': empresa.razao_social,
        'cnpj': empresa.cnpj_formatado,
        'total': consultas.total,
        'pagina': page,
        'consultas': [
            {
                'ncm': c.ncm_consultado,
                'monofasico': c.monofasico,
                'grupo': c.grupo_tributario,
                'cst_sugerido': c.cst_sugerido,
                'inconsistencia': c.inconsistencia_detectada,
                'data': c.created_at.strftime('%d/%m/%Y %H:%M'),
            }
            for c in consultas.items
        ]
    })
