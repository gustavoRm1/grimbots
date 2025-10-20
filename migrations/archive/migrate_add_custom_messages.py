#!/usr/bin/env python3
"""
Migração: Adiciona campos success_message e pending_message em bot_configs
"""

from app import app, db
import logging

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

def migrate():
    """Adiciona colunas de mensagens personalizadas"""
    with app.app_context():
        from sqlalchemy import text
        
        try:
            # Adicionar success_message
            db.session.execute(text("""
                ALTER TABLE bot_configs 
                ADD COLUMN success_message TEXT;
            """))
            logger.info("✅ Coluna success_message adicionada")
        except Exception as e:
            if 'duplicate column' in str(e).lower() or 'already exists' in str(e).lower():
                logger.info("✅ Coluna success_message já existe")
            else:
                logger.error(f"❌ Erro ao adicionar success_message: {e}")
        
        try:
            # Adicionar pending_message
            db.session.execute(text("""
                ALTER TABLE bot_configs 
                ADD COLUMN pending_message TEXT;
            """))
            logger.info("✅ Coluna pending_message adicionada")
        except Exception as e:
            if 'duplicate column' in str(e).lower() or 'already exists' in str(e).lower():
                logger.info("✅ Coluna pending_message já existe")
            else:
                logger.error(f"❌ Erro ao adicionar pending_message: {e}")
        
        db.session.commit()
        
        print("\n" + "=" * 60)
        print("[OK] MIGRAÇÃO CONCLUÍDA!")
        print("=" * 60)
        print("\nCampos adicionados em bot_configs:")
        print("  - success_message (TEXT)")
        print("  - pending_message (TEXT)")
        print("\nAgora os bots podem ter mensagens personalizadas!")

if __name__ == "__main__":
    migrate()

