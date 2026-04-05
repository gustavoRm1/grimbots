"""
Migration: Add failure tracking columns to bots table
Adiciona circuit breaker e contadores de falha para bots.

Revision ID: 001_add_bot_failure_tracking
Revises: (base)
Create Date: 2026-04-04
"""

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

# revision identifiers, used by Alembic.
revision = '001_add_bot_failure_tracking'
down_revision = None
branch_labels = None
depends_on = None


def upgrade():
    """Adiciona colunas de tracking de falhas na tabela bots."""
    
    # Adicionar colunas para circuit breaker e failure tracking
    op.add_column('bots', sa.Column('consecutive_failures', sa.Integer(), 
                                    server_default='0', nullable=False))
    op.add_column('bots', sa.Column('last_failure_at', sa.DateTime(), 
                                    nullable=True))
    op.add_column('bots', sa.Column('circuit_breaker_until', sa.DateTime(), 
                                    nullable=True))
    op.add_column('bots', sa.Column('failure_count_24h', sa.Integer(), 
                                    server_default='0', nullable=False))
    op.add_column('bots', sa.Column('failure_reset_at', sa.DateTime(), 
                                    nullable=True))
    
    # Criar índices para queries eficientes
    op.create_index('idx_bots_consecutive_failures', 'bots', ['consecutive_failures'])
    op.create_index('idx_bots_circuit_breaker', 'bots', ['circuit_breaker_until'])
    op.create_index('idx_bots_last_failure', 'bots', ['last_failure_at'])
    
    # Comentários explicativos
    op.execute("""
        COMMENT ON COLUMN bots.consecutive_failures IS 
        'Número de falhas consecutivas (404, 401, etc). Resetado em caso de sucesso.';
    """)
    op.execute("""
        COMMENT ON COLUMN bots.circuit_breaker_until IS 
        'Timestamp até quando o bot está em circuit breaker (pausa após falhas).';
    """)
    op.execute("""
        COMMENT ON COLUMN bots.failure_count_24h IS 
        'Contador de falhas nas últimas 24h. Usado para auto-desativação.';
    """)


def downgrade():
    """Remove colunas de tracking de falhas."""
    
    op.drop_index('idx_bots_consecutive_failures', table_name='bots')
    op.drop_index('idx_bots_circuit_breaker', table_name='bots')
    op.drop_index('idx_bots_last_failure', table_name='bots')
    
    op.drop_column('bots', 'consecutive_failures')
    op.drop_column('bots', 'last_failure_at')
    op.drop_column('bots', 'circuit_breaker_until')
    op.drop_column('bots', 'failure_count_24h')
    op.drop_column('bots', 'failure_reset_at')
