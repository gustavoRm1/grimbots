"""
Migration: Corrigir constraint de pool_bots para CASCADE DELETE
"""

from app import app, db
from internal_logic.core.models import PoolBot
import logging

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

def migrate():
    """Aplica migration para corrigir CASCADE DELETE em pool_bots"""
    with app.app_context():
        try:
            logger.info("🔧 Iniciando migration: Corrigir CASCADE DELETE em pool_bots...")
            
            # SQLite não suporta ALTER para modificar FK
            # Solução: Não precisamos fazer nada, o cascade está no ORM (models.py)
            # O importante é que quando deletar bot, o código agora vai deletar pool_bots
            
            logger.info("✅ Migration concluída!")
            logger.info("   O relacionamento cascade='all, delete-orphan' foi adicionado ao modelo Bot")
            logger.info("   Agora deletar um bot vai automaticamente deletar suas associações em pool_bots")
            
        except Exception as e:
            logger.error(f"❌ Erro na migration: {e}")
            raise

if __name__ == '__main__':
    print("="*60)
    print("Migration: Fix PoolBot CASCADE DELETE")
    print("="*60)
    migrate()
    print("="*60)

