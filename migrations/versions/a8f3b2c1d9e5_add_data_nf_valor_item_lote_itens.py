"""add data_nf e valor_item em lote_itens

Revision ID: a8f3b2c1d9e5
Revises: f9b2d4e1c308
Create Date: 2026-05-18 00:00:00.000000

Adiciona campos para Data da NF e Valor do Item aos itens de lote,
permitindo exportação e filtragem por data de emissão e valor unitário.
"""
import sqlalchemy as sa
from alembic import op

revision = 'a8f3b2c1d9e5'
down_revision = 'f9b2d4e1c308'
branch_labels = None
depends_on = None


def upgrade():
    with op.batch_alter_table('lote_itens') as batch_op:
        batch_op.add_column(sa.Column('data_nf', sa.Date(), nullable=True))
        batch_op.add_column(sa.Column('valor_item', sa.Numeric(15, 2), nullable=True))


def downgrade():
    with op.batch_alter_table('lote_itens') as batch_op:
        batch_op.drop_column('valor_item')
        batch_op.drop_column('data_nf')
