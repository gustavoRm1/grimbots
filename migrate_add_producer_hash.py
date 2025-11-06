#!/usr/bin/env python3
"""
Migração: Adicionar campo producer_hash ao Gateway (Átomo Pay)

Este campo permite identificar qual conta do Átomo Pay enviou o webhook,
permitindo que múltiplos usuários usem a mesma URL de webhook.
"""

import sys
import os

# Adicionar diretório raiz ao path
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from app import app, db
from models import Gateway
from sqlalchemy import text

def migrate():
    """Adiciona campo producer_hash ao Gateway"""
    with app.app_context():
        try:
            # Verificar se coluna já existe
            inspector = db.inspect(db.engine)
            columns = [col['name'] for col in inspector.get_columns('gateways')]
            
            if 'producer_hash' in columns:
                print("✅ Campo 'producer_hash' já existe na tabela 'gateways'")
                return
            
            # Adicionar coluna
            print("📝 Adicionando campo 'producer_hash' à tabela 'gateways'...")
            db.session.execute(text("""
                ALTER TABLE gateways 
                ADD COLUMN producer_hash VARCHAR(100) NULL
            """))
            
            # Criar índice para busca rápida
            print("📝 Criando índice para 'producer_hash'...")
            db.session.execute(text("""
                CREATE INDEX IF NOT EXISTS idx_gateways_producer_hash 
                ON gateways(producer_hash)
            """))
            
            db.session.commit()
            print("✅ Migração concluída com sucesso!")
            print("   - Campo 'producer_hash' adicionado")
            print("   - Índice criado para busca rápida")
            
        except Exception as e:
            db.session.rollback()
            print(f"❌ Erro na migração: {e}")
            import traceback
            traceback.print_exc()
            sys.exit(1)

if __name__ == '__main__':
    migrate()

