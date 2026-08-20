"""
Migration: Add manually_disabled column to bots table
Distingue "desligado pelo usuário" de "desligado por falha de saúde".

Revision ID: add_manually_disabled
Revises: 001_add_bot_failure_tracking
Create Date: 2026-08-20
"""

from alembic import op
import sqlalchemy as sa

revision = 'add_manually_disabled'
down_revision = '001_add_bot_failure_tracking'
branch_labels = None
depends_on = None


def upgrade():
    """Adiciona coluna manually_disabled na tabela bots."""
    op.add_column('bots', sa.Column('manually_disabled', sa.Boolean(),
                                    server_default='0', nullable=False))
    op.create_index('idx_bots_manually_disabled', 'bots', ['manually_disabled'])

    op.execute("""
        COMMENT ON COLUMN bots.manually_disabled IS
        'True quando o usuário desligou o bot manualmente (toggle). Health worker NÃO deve reativar.';
    """)


def downgrade():
    """Remove coluna manually_disabled."""
    op.drop_index('idx_bots_manually_disabled', table_name='bots')
    op.drop_column('bots', 'manually_disabled')
