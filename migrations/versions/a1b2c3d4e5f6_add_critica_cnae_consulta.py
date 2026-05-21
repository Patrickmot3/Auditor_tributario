"""add critica_cnae_severidade e critica_cnae_mensagem à tabela consultas

Revision ID: a1b2c3d4e5f6
Revises: f1a2b3c4d5e6
Create Date: 2026-05-21
"""
from alembic import op
import sqlalchemy as sa

revision = 'a1b2c3d4e5f6'
down_revision = 'f1a2b3c4d5e6'
branch_labels = None
depends_on = None


def upgrade():
    with op.batch_alter_table('consultas') as batch_op:
        batch_op.add_column(sa.Column('critica_cnae_severidade', sa.String(10), nullable=True))
        batch_op.add_column(sa.Column('critica_cnae_mensagem',   sa.Text(),     nullable=True))


def downgrade():
    with op.batch_alter_table('consultas') as batch_op:
        batch_op.drop_column('critica_cnae_mensagem')
        batch_op.drop_column('critica_cnae_severidade')
