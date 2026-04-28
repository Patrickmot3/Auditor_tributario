"""
Serviço de exportação de consultas para Excel formatado.
"""
import io
from datetime import datetime
import xlsxwriter


def gerar_excel_consultas(consultas):
    output = io.BytesIO()
    workbook = xlsxwriter.Workbook(output, {'in_memory': True})
    ws = workbook.add_worksheet('Consultas TribSync')

    # Formatos
    fmt_cabecalho = workbook.add_format({
        'bold': True, 'bg_color': '#1e3a5f', 'font_color': 'white',
        'border': 1, 'align': 'center', 'valign': 'vcenter', 'text_wrap': True,
    })
    fmt_monofasico = workbook.add_format({'bg_color': '#d4edda', 'border': 1})
    fmt_inconsistencia = workbook.add_format({'bg_color': '#f8d7da', 'border': 1})
    fmt_normal = workbook.add_format({'border': 1})

    colunas = [
        'Empresa', 'CNPJ', 'NCM', 'Descrição do Produto', 'Código Produto',
        'Cód. CEST', 'Monofásico', 'Grupo Tributário', 'Base Legal',
        'Tabela SPED', 'CST Sugerido Entrada', 'CST Sugerido Saída',
        'CFOP Sugerido', 'Alíquota PIS (%)', 'Alíquota COFINS (%)',
        'Posição na Cadeia', 'Inconsistência Detectada', 'Observação',
        'Data da Consulta',
    ]

    larguras = [30, 20, 12, 40, 15, 12, 12, 25, 40, 12, 20, 20, 15, 15, 18, 18, 22, 50, 20]

    for col_idx, (col, larg) in enumerate(zip(colunas, larguras)):
        ws.write(0, col_idx, col, fmt_cabecalho)
        ws.set_column(col_idx, col_idx, larg)

    ws.set_row(0, 30)
    ws.autofilter(0, 0, 0, len(colunas) - 1)

    for row_idx, c in enumerate(consultas, start=1):
        empresa = c.empresa
        monofasico_str = 'Sim' if c.monofasico else 'Não'
        inconsistencia_str = 'Sim' if c.inconsistencia_detectada else 'Não'

        if c.inconsistencia_detectada:
            fmt = fmt_inconsistencia
        elif c.monofasico:
            fmt = fmt_monofasico
        else:
            fmt = fmt_normal

        linha = [
            empresa.razao_social if empresa else '',
            empresa.cnpj_formatado if empresa else '',
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
