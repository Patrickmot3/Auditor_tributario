"""add aliquotas_grupo

Revision ID: e3a7c1f8b920
Revises: d1936ed0d328
Create Date: 2026-04-28 00:00:00.000000

"""
from alembic import op
import sqlalchemy as sa

revision = 'e3a7c1f8b920'
down_revision = 'd1936ed0d328'
branch_labels = None
depends_on = None


def upgrade():
    op.create_table(
        'aliquotas_grupo',
        sa.Column('id', sa.Integer(), nullable=False),
        sa.Column('grupo_tributario_id', sa.Integer(), nullable=False),
        sa.Column('pis_fabricante', sa.Numeric(precision=7, scale=4), nullable=False),
        sa.Column('cofins_fabricante', sa.Numeric(precision=7, scale=4), nullable=False),
        sa.Column('pis_varejista', sa.Numeric(precision=7, scale=4), nullable=False),
        sa.Column('cofins_varejista', sa.Numeric(precision=7, scale=4), nullable=False),
        sa.Column('vigencia_inicio', sa.Date(), nullable=False),
        sa.Column('vigencia_fim', sa.Date(), nullable=True),
        sa.Column('lei_referencia', sa.String(length=300), nullable=True),
        sa.Column('observacao', sa.Text(), nullable=True),
        sa.Column('ativo', sa.Boolean(), nullable=True),
        sa.Column('created_at', sa.DateTime(), nullable=True),
        sa.Column('updated_at', sa.DateTime(), nullable=True),
        sa.ForeignKeyConstraint(['grupo_tributario_id'], ['grupos_tributarios.id']),
        sa.PrimaryKeyConstraint('id'),
    )
    op.create_index(
        'ix_aliquotas_grupo_grupo_vigencia',
        'aliquotas_grupo',
        ['grupo_tributario_id', 'vigencia_inicio'],
    )


def downgrade():
    op.drop_index('ix_aliquotas_grupo_grupo_vigencia', table_name='aliquotas_grupo')
    op.drop_table('aliquotas_grupo')
