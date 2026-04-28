from flask import Blueprint, render_template, redirect, url_for, flash, request
from flask_login import login_required, current_user
from app.extensions import db
from app.models.empresa import Empresa, UsuarioEmpresa

empresa_bp = Blueprint('empresa', __name__)


@empresa_bp.route('/')
@login_required
def lista():
    if current_user.is_admin:
        empresas = Empresa.query.filter_by(ativo=True).order_by(Empresa.razao_social).all()
    else:
        empresas = current_user.empresas
    return render_template('empresa/lista.html', empresas=empresas)


@empresa_bp.route('/nova', methods=['GET', 'POST'])
@login_required
def nova():
    if request.method == 'POST':
        cnpj = request.form.get('cnpj', '').strip()
        razao = request.form.get('razao_social', '').strip()
        cnae = request.form.get('cnae_principal', '').strip()
        regime = request.form.get('regime_tributario', '').strip()
        posicao = request.form.get('posicao_cadeia', '').strip()
        email = request.form.get('email', '').strip()

        if not all([cnpj, razao, cnae, regime, posicao]):
            flash('Preencha todos os campos obrigatórios.', 'danger')
            return render_template('empresa/form.html', empresa=None)

        # Remover formatação do CNPJ
        cnpj_limpo = cnpj.replace('.', '').replace('/', '').replace('-', '')

        if Empresa.query.filter_by(cnpj=cnpj_limpo).first():
            flash('CNPJ já cadastrado.', 'danger')
            return render_template('empresa/form.html', empresa=None)

        empresa = Empresa(
            razao_social=razao,
            nome_fantasia=request.form.get('nome_fantasia', '').strip(),
            cnpj=cnpj_limpo,
            inscricao_estadual=request.form.get('inscricao_estadual', '').strip(),
            cnae_principal=cnae.replace('.', '').replace('-', ''),
            regime_tributario=regime,
            posicao_cadeia=posicao,
            email=email,
            responsavel_nome=request.form.get('responsavel_nome', '').strip(),
            responsavel_cpf=request.form.get('responsavel_cpf', '').strip(),
            logradouro=request.form.get('logradouro', '').strip(),
            numero=request.form.get('numero', '').strip(),
            complemento=request.form.get('complemento', '').strip(),
            bairro=request.form.get('bairro', '').strip(),
            cidade=request.form.get('cidade', '').strip(),
            uf=request.form.get('uf', '').strip().upper(),
            cep=request.form.get('cep', '').strip(),
            telefone=request.form.get('telefone', '').strip(),
        )
        db.session.add(empresa)
        db.session.flush()

        # Vincular empresa ao usuário atual
        vinculo = UsuarioEmpresa(usuario_id=current_user.id, empresa_id=empresa.id)
        db.session.add(vinculo)
        db.session.commit()

        flash(f'Empresa "{razao}" cadastrada com sucesso!', 'success')
        return redirect(url_for('empresa.detalhe', id=empresa.id))

    return render_template('empresa/form.html', empresa=None)


@empresa_bp.route('/<int:id>')
@login_required
def detalhe(id):
    empresa = db.get_or_404(Empresa, id)
    return render_template('empresa/detalhe.html', empresa=empresa)


@empresa_bp.route('/<int:id>/editar', methods=['GET', 'POST'])
@login_required
def editar(id):
    empresa = db.get_or_404(Empresa, id)
    if request.method == 'POST':
        empresa.razao_social = request.form.get('razao_social', empresa.razao_social).strip()
        empresa.nome_fantasia = request.form.get('nome_fantasia', '').strip()
        empresa.cnae_principal = request.form.get('cnae_principal', '').replace('.', '').replace('-', '').strip()
        empresa.regime_tributario = request.form.get('regime_tributario', empresa.regime_tributario)
        empresa.posicao_cadeia = request.form.get('posicao_cadeia', empresa.posicao_cadeia)
        empresa.email = request.form.get('email', '').strip()
        empresa.telefone = request.form.get('telefone', '').strip()
        empresa.logradouro = request.form.get('logradouro', '').strip()
        empresa.numero = request.form.get('numero', '').strip()
        empresa.complemento = request.form.get('complemento', '').strip()
        empresa.bairro = request.form.get('bairro', '').strip()
        empresa.cidade = request.form.get('cidade', '').strip()
        empresa.uf = request.form.get('uf', '').strip().upper()
        empresa.cep = request.form.get('cep', '').strip()
        db.session.commit()
        flash('Empresa atualizada com sucesso!', 'success')
        return redirect(url_for('empresa.detalhe', id=empresa.id))

    return render_template('empresa/form.html', empresa=empresa)


@empresa_bp.route('/<int:id>/desativar', methods=['POST'])
@login_required
def desativar(id):
    empresa = db.get_or_404(Empresa, id)
    empresa.ativo = False
    db.session.commit()
    flash(f'Empresa "{empresa.razao_social}" desativada.', 'warning')
    return redirect(url_for('empresa.lista'))


@empresa_bp.route('/<int:id>/consultas')
@login_required
def historico_empresa(id):
    empresa = db.get_or_404(Empresa, id)
    page = request.args.get('page', 1, type=int)
    consultas = empresa.consultas.order_by(
        empresa.consultas.property.mapper.class_.created_at.desc()
    ).paginate(page=page, per_page=20)
    return render_template('empresa/historico.html', empresa=empresa, consultas=consultas)
