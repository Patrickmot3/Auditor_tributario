"""add cnae segmentos to empresa

Revision ID: f1a2b3c4d5e6
Revises: c2d4f6a8b1e3
Create Date: 2026-05-21 00:00:00.000000

Adiciona colunas JSON para CNAEs secundários e segmentos tributários
inferidos/manuais na tabela empresas.
"""
import sqlalchemy as sa
from alembic import op

revision = 'f1a2b3c4d5e6'
down_revision = 'c2d4f6a8b1e3'
branch_labels = None
depends_on = None


def upgrade():
    with op.batch_alter_table('empresas') as batch_op:
        batch_op.add_column(sa.Column('cnaes_secundarios',  sa.JSON(), nullable=True))
        batch_op.add_column(sa.Column('segmentos_override',  sa.JSON(), nullable=True))
        batch_op.add_column(sa.Column('segmentos_inferidos', sa.JSON(), nullable=True))


def downgrade():
    with op.batch_alter_table('empresas') as batch_op:
        batch_op.drop_column('segmentos_inferidos')
        batch_op.drop_column('segmentos_override')
        batch_op.drop_column('cnaes_secundarios')
