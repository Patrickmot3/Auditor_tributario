"""fix unique constraint ncm_grupo_vigencia

Revision ID: f9b2d4e1c308
Revises: e3a7c1f8b920
Create Date: 2026-04-28 00:00:00.000000

Remove a constraint (ncm, vigencia_inicio) que causava conflito ao inserir
o mesmo NCM em grupos tributários diferentes no mesmo dia, e substitui por
(ncm, grupo_tributario_id, vigencia_inicio).
"""
from alembic import op

revision = 'f9b2d4e1c308'
down_revision = 'e3a7c1f8b920'
branch_labels = None
depends_on = None


def upgrade():
    # Remove constraint antiga (pode não existir se o banco foi criado após a correção)
    with op.batch_alter_table('ncms_tributarios') as batch_op:
        try:
            batch_op.drop_constraint('unique_ncm_vigencia', type_='unique')
        except Exception:
            pass  # já removida ou nunca existiu
        batch_op.create_unique_constraint(
            'unique_ncm_grupo_vigencia',
            ['ncm', 'grupo_tributario_id', 'vigencia_inicio'],
        )


def downgrade():
    with op.batch_alter_table('ncms_tributarios') as batch_op:
        batch_op.drop_constraint('unique_ncm_grupo_vigencia', type_='unique')
        batch_op.create_unique_constraint(
            'unique_ncm_vigencia',
            ['ncm', 'vigencia_inicio'],
        )
