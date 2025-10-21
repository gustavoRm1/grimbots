#!/usr/bin/env python
"""
MIGRATION: Adicionar campos de tracking elite ao BotUser
Data: 2025-10-21
Autor: QI 500 Elite Team

Adiciona:
- ip_address: IP do usuário no primeiro click
- user_agent: User-Agent do navegador
- tracking_session_id: UUID para correlação
"""

import sys
from pathlib import Path

# Adicionar diretório raiz ao path
sys.path.insert(0, str(Path(__file__).parent))

from app import app, db
from models import BotUser
from sqlalchemy import text

def migrate():
    print("=" * 70)
    print("MIGRATION: Adicionar campos de tracking elite")
    print("=" * 70)
    
    with app.app_context():
        try:
            # Adicionar colunas
            print("\n1. Adicionando campo ip_address...")
            db.session.execute(text(
                "ALTER TABLE bot_users ADD COLUMN ip_address VARCHAR(50)"
            ))
            print("   ✅ ip_address adicionado")
            
            print("\n2. Adicionando campo user_agent...")
            db.session.execute(text(
                "ALTER TABLE bot_users ADD COLUMN user_agent TEXT"
            ))
            print("   ✅ user_agent adicionado")
            
            print("\n3. Adicionando campo tracking_session_id...")
            db.session.execute(text(
                "ALTER TABLE bot_users ADD COLUMN tracking_session_id VARCHAR(100)"
            ))
            print("   ✅ tracking_session_id adicionado")
            
            print("\n4. Adicionando campo click_timestamp...")
            db.session.execute(text(
                "ALTER TABLE bot_users ADD COLUMN click_timestamp DATETIME"
            ))
            print("   ✅ click_timestamp adicionado")
            
            db.session.commit()
            
            print("\n" + "=" * 70)
            print("✅ MIGRATION CONCLUÍDA COM SUCESSO!")
            print("=" * 70)
            
        except Exception as e:
            print(f"\n❌ ERRO: {e}")
            db.session.rollback()
            raise

if __name__ == '__main__':
    migrate()

