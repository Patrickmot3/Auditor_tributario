"""
Serviço de exportação de consultas para Excel formatado.
"""
import io
import xlsxwriter


def gerar_template_importacao():
    """Gera planilha modelo para importação de NCMs no TribSync."""
    output = io.BytesIO()
    wb = xlsxwriter.Workbook(output, {'in_memory': True})
    ws = wb.add_worksheet('Modelo TribSync')

    fmt_cab = wb.add_format({
        'bold': True, 'bg_color': '#1e3a5f', 'font_color': 'white',
        'border': 1, 'align': 'center', 'valign': 'vcenter',
    })
    fmt_obrig = wb.add_format({
        'bold': True, 'bg_color': '#d4edda', 'border': 1, 'align': 'center',
    })
    fmt_exemplo = wb.add_format({'border': 1, 'color': '#6c757d', 'italic': True})

    colunas = [
        ('Código',        10, False),
        ('Descrição',     40, False),
        ('Tipo do Item',  22, False),
        ('Cód. NCM',      14, True),   # obrigatória
        ('Cód. CEST',     12, False),
        ('CST Atual',     12, False),
    ]

    for col_idx, (nome, largura, obrig) in enumerate(colunas):
        fmt = fmt_obrig if obrig else fmt_cab
        ws.write(0, col_idx, nome + (' *' if obrig else ''), fmt)
        ws.set_column(col_idx, col_idx, largura)

    ws.set_row(0, 22)

    # Linha de exemplo
    exemplos = [
        'PROD001', 'Amortecedor traseiro', 'Mercadoria para Revenda',
        '87089990', '01.001.00', '04',
    ]
    for col_idx, val in enumerate(exemplos):
        ws.write(1, col_idx, val, fmt_exemplo)

    # Nota de rodapé
    ws.write(3, 0, '* Coluna obrigatória', wb.add_format({'italic': True, 'color': '#dc3545'}))
    ws.write(4, 0, 'CST Atual: informe o CST usado na NF-e para que o sistema detecte inconsistências.',
             wb.add_format({'italic': True, 'color': '#6c757d'}))

    wb.close()
    output.seek(0)
    return output


def _numero_nfe_por_consulta(consultas):
    """
    Retorna dict {consulta_id: 'serie-nNF'} buscando o lote mais recente de cada consulta.
    Evita N+1 queries usando uma única consulta SQL via ORM.
    """
    from app.models.consulta import LoteItem, LoteConsulta
    from app.extensions import db
    from sqlalchemy import select, func

    if not consultas:
        return {}

    ids = [c.id for c in consultas]

    # Subconsulta: lote_id mais recente para cada consulta_id
    sub = (
        db.session.query(
            LoteItem.consulta_id,
            func.max(LoteConsulta.id).label('max_lote_id'),
        )
        .join(LoteConsulta, LoteItem.lote_id == LoteConsulta.id)
        .filter(LoteItem.consulta_id.in_(ids))
        .filter(LoteConsulta.tipo == 'xml_nfe')
        .group_by(LoteItem.consulta_id)
        .subquery()
    )

    rows = (
        db.session.query(sub.c.consulta_id, LoteConsulta.nome_lote)
        .join(LoteConsulta, LoteConsulta.id == sub.c.max_lote_id)
        .all()
    )

    return {row.consulta_id: row.nome_lote for row in rows}


def gerar_excel_lote_items(lote_ids):
    """
    Exporta um lote linha-a-linha (via LoteItem), preservando produtos duplicados
    com descrições diferentes que pertencem ao mesmo NCM.
    """
    from app.models.consulta import LoteItem, LoteConsulta, Consulta
    from app.extensions import db

    items = (
        LoteItem.query
        .filter(LoteItem.lote_id.in_(lote_ids))
        .order_by(LoteItem.lote_id, LoteItem.linha_original)
        .all()
    )

    lote_cache = {
        l.id: l
        for l in LoteConsulta.query.filter(LoteConsulta.id.in_(lote_ids)).all()
    }
    consulta_ids = [i.consulta_id for i in items if i.consulta_id]
    consulta_cache = {
        c.id: c
        for c in Consulta.query.filter(Consulta.id.in_(consulta_ids)).all()
    }

    output = io.BytesIO()
    wb = xlsxwriter.Workbook(output, {'in_memory': True})
    ws = wb.add_worksheet('Lote TribSync')

    fmt_cab = wb.add_format({
        'bold': True, 'bg_color': '#1e3a5f', 'font_color': 'white',
        'border': 1, 'align': 'center', 'valign': 'vcenter', 'text_wrap': True,
    })
    fmt_mono  = wb.add_format({'bg_color': '#d4edda', 'border': 1})
    fmt_incon = wb.add_format({'bg_color': '#f8d7da', 'border': 1})
    fmt_erro  = wb.add_format({'bg_color': '#e2e3e5', 'border': 1, 'italic': True})
    fmt_norm  = wb.add_format({'border': 1})

    colunas = [
        ('Empresa',              28),
        ('N° Documento NF-e',    20),
        ('Linha',                 7),
        ('NCM',                  12),
        ('Descrição do Produto', 40),
        ('Código Produto',       15),
        ('Cód. CEST',            12),
        ('Monofásico',           12),
        ('Grupo Tributário',     25),
        ('Base Legal',           38),
        ('CST Atual NF-e',       14),
        ('CST Sugerido',         14),
        ('Regime Tributário',     42),
        ('CFOP Sugerido',        14),
        ('Alíq. PIS (%)',        13),
        ('Alíq. COFINS (%)',     15),
        ('Posição Cadeia',       16),
        ('Inconsistência',       16),
        ('Status',               12),
        ('Observação',           45),
    ]

    for ci, (nome, larg) in enumerate(colunas):
        ws.write(0, ci, nome, fmt_cab)
        ws.set_column(ci, ci, larg)
    ws.set_row(0, 30)
    ws.autofilter(0, 0, 0, len(colunas) - 1)

    from app.services.ncm_validator import CST_DESCRICAO

    for ri, item in enumerate(items, start=1):
        lote   = lote_cache.get(item.lote_id)
        c      = consulta_cache.get(item.consulta_id) if item.consulta_id else None
        erro   = item.status_processamento == 'erro'

        empresa_nome = c.empresa.razao_social if c and c.empresa else ''
        doc_nfe      = lote.nome_lote if lote else ''
        mono_str     = ('Sim' if c.monofasico else 'Não') if c else '—'
        incon_str    = ('Sim' if c.inconsistencia_detectada else 'Não') if c else '—'
        cst_sugerido = c.cst_sugerido or '' if c else ''
        grupo_ok     = bool(c and c.grupo_tributario)
        regime_desc  = CST_DESCRICAO.get(cst_sugerido, '') if (cst_sugerido and grupo_ok) else ''

        if erro:
            fmt = fmt_erro
        elif c and c.inconsistencia_detectada:
            fmt = fmt_incon
        elif c and c.monofasico:
            fmt = fmt_mono
        else:
            fmt = fmt_norm

        linha = [
            empresa_nome,
            doc_nfe,
            item.linha_original or '',
            item.ncm or '',
            item.descricao or '',
            item.codigo_produto or '',
            item.codigo_cest or '',
            mono_str,
            (c.grupo_tributario or '') if c else '',
            (c.lei_aplicada or '') if c else '',
            (c.cst_atual or '') if c else '',
            cst_sugerido,
            regime_desc,
            (c.cfop_sugerido or '') if c else '',
            float(c.pis_aliquota) if c and c.pis_aliquota is not None else 0,
            float(c.cofins_aliquota) if c and c.cofins_aliquota is not None else 0,
            (c.posicao_cadeia or '') if c else '',
            incon_str,
            item.status_processamento or '',
            (c.observacao or '') if c else (item.mensagem_erro or ''),
        ]

        for ci, valor in enumerate(linha):
            ws.write(ri, ci, valor, fmt)

    wb.close()
    output.seek(0)
    return output


def gerar_excel_consultas(consultas):
    numero_nfe_map = _numero_nfe_por_consulta(consultas)

    output = io.BytesIO()
    workbook = xlsxwriter.Workbook(output, {'in_memory': True})
    ws = workbook.add_worksheet('Consultas TribSync')

    fmt_cabecalho = workbook.add_format({
        'bold': True, 'bg_color': '#1e3a5f', 'font_color': 'white',
        'border': 1, 'align': 'center', 'valign': 'vcenter', 'text_wrap': True,
    })
    fmt_monofasico = workbook.add_format({'bg_color': '#d4edda', 'border': 1})
    fmt_inconsistencia = workbook.add_format({'bg_color': '#f8d7da', 'border': 1})
    fmt_normal = workbook.add_format({'border': 1})

    colunas = [
        'Empresa', 'CNPJ', 'N° Documento NF-e', 'NCM', 'Descrição do Produto',
        'Código Produto', 'Cód. CEST', 'Monofásico', 'Grupo Tributário', 'Base Legal',
        'Tabela SPED', 'CST Sugerido Entrada', 'CST Sugerido Saída',
        'CFOP Sugerido', 'Alíquota PIS (%)', 'Alíquota COFINS (%)',
        'Posição na Cadeia', 'Inconsistência Detectada', 'Observação',
        'Data da Consulta',
    ]

    larguras = [30, 20, 18, 12, 40, 15, 12, 12, 25, 40, 12, 20, 20, 15, 15, 18, 18, 22, 50, 20]

    for col_idx, (col, larg) in enumerate(zip(colunas, larguras)):
        ws.write(0, col_idx, col, fmt_cabecalho)
        ws.set_column(col_idx, col_idx, larg)

    ws.set_row(0, 30)
    ws.autofilter(0, 0, 0, len(colunas) - 1)

    for row_idx, c in enumerate(consultas, start=1):
        empresa = c.empresa
        monofasico_str = 'Sim' if c.monofasico else 'Não'
        inconsistencia_str = 'Sim' if c.inconsistencia_detectada else 'Não'
        numero_nfe = numero_nfe_map.get(c.id, '')

        if c.inconsistencia_detectada:
            fmt = fmt_inconsistencia
        elif c.monofasico:
            fmt = fmt_monofasico
        else:
            fmt = fmt_normal

        linha = [
            empresa.razao_social if empresa else '',
            empresa.cnpj_formatado if empresa else '',
            numero_nfe,
            c.ncm_consultado or '',
            c.descricao_produto or '',
            c.codigo_produto or '',
            c.codigo_cest or '',
            monofasico_str,
            c.grupo_tributario or '',
            c.lei_aplicada or '',
            '',  # tabela SPED (não armazenada diretamente em consulta)
            c.cst_sugerido or '',
            c.cst_sugerido or '',
            c.cfop_sugerido or '',
            float(c.pis_aliquota) if c.pis_aliquota is not None else 0,
            float(c.cofins_aliquota) if c.cofins_aliquota is not None else 0,
            c.posicao_cadeia or '',
            inconsistencia_str,
            c.observacao or '',
            c.created_at.strftime('%d/%m/%Y %H:%M') if c.created_at else '',
        ]

        for col_idx, valor in enumerate(linha):
            ws.write(row_idx, col_idx, valor, fmt)

    workbook.close()
    output.seek(0)
    return output
