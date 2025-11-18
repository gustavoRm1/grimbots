"""
Migration: Adicionar campo utmify_pixel_id na tabela redirect_pools

Data: 2025-01-17
Descrição: Adiciona campo para armazenar o Pixel ID da Utmify para rastreamento avançado de UTMs
"""

import sys
import os

# Adicionar diretório raiz ao path
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from app import app, db
from models import RedirectPool

def migrate():
    """Adiciona campo utmify_pixel_id na tabela redirect_pools"""
    with app.app_context():
        try:
            # Verificar se campo já existe
            from sqlalchemy import inspect
            inspector = inspect(db.engine)
            columns = [col['name'] for col in inspector.get_columns('redirect_pools')]
            
            if 'utmify_pixel_id' in columns:
                print("✅ Campo utmify_pixel_id já existe na tabela redirect_pools")
                return True
            
            # Adicionar coluna
            print("🔄 Adicionando campo utmify_pixel_id na tabela redirect_pools...")
            db.session.execute("""
                ALTER TABLE redirect_pools 
                ADD COLUMN utmify_pixel_id VARCHAR(100) NULL
            """)
            db.session.commit()
            
            print("✅ Campo utmify_pixel_id adicionado com sucesso!")
            return True
            
        except Exception as e:
            db.session.rollback()
            print(f"❌ Erro ao adicionar campo utmify_pixel_id: {e}")
            return False

if __name__ == '__main__':
    print("=" * 60)
    print("MIGRATION: Adicionar utmify_pixel_id")
    print("=" * 60)
    
    if migrate():
        print("\n✅ MIGRATION CONCLUÍDA COM SUCESSO!")
    else:
        print("\n❌ MIGRATION FALHOU!")
        sys.exit(1)

