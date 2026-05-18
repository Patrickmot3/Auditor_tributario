"""add revisao em consultas e tabela revisao_log

Revision ID: c2d4f6a8b1e3
Revises: a8f3b2c1d9e5
Create Date: 2026-05-18 00:00:00.000000

Adiciona campos de revisão/homologação na tabela consultas e cria
a tabela revisao_log para rastreabilidade completa de auditoria.
"""
import sqlalchemy as sa
from alembic import op

revision = 'c2d4f6a8b1e3'
down_revision = 'a8f3b2c1d9e5'
branch_labels = None
depends_on = None


def upgrade():
    with op.batch_alter_table('consultas') as batch_op:
        batch_op.add_column(sa.Column('status_revisao', sa.String(20), nullable=False,
                                      server_default='pendente'))
        batch_op.add_column(sa.Column('revisado_por_id', sa.Integer(),
                                      sa.ForeignKey('usuarios.id'), nullable=True))
        batch_op.add_column(sa.Column('revisado_em', sa.DateTime(), nullable=True))
        batch_op.add_column(sa.Column('motivo_revisao', sa.Text(), nullable=True))

    op.create_table(
        'revisao_log',
        sa.Column('id', sa.Integer(), primary_key=True),
        sa.Column('consulta_id', sa.Integer(), sa.ForeignKey('consultas.id', ondelete='CASCADE'),
                  nullable=False),
        sa.Column('usuario_id', sa.Integer(), sa.ForeignKey('usuarios.id'), nullable=False),
        sa.Column('status_anterior', sa.String(20), nullable=True),
        sa.Column('status_novo', sa.String(20), nullable=False),
        sa.Column('motivo', sa.Text(), nullable=True),
        sa.Column('criado_em', sa.DateTime(), nullable=False),
    )


def downgrade():
    op.drop_table('revisao_log')
    with op.batch_alter_table('consultas') as batch_op:
        batch_op.drop_column('motivo_revisao')
        batch_op.drop_column('revisado_em')
        batch_op.drop_column('revisado_por_id')
        batch_op.drop_column('status_revisao')
