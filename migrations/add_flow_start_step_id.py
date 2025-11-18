#!/usr/bin/env python3
"""
Migration: Adicionar flow_start_step_id ao BotConfig
"""
import sys
import os

# Adicionar diretório raiz ao path
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

# ✅ Importar do app.py para usar mesma configuração de banco (incluindo .env)
from app import app, db
from sqlalchemy import inspect, text

def migrate():
    """Adiciona campo flow_start_step_id ao BotConfig"""
    with app.app_context():
        try:
            inspector = inspect(db.engine)
            dialect_name = db.engine.dialect.name
            database_uri = app.config['SQLALCHEMY_DATABASE_URI']
            print(f"🔄 Database detectado: {dialect_name}")
            print(f"🔄 URI: {database_uri.split('@')[-1] if '@' in database_uri else database_uri.split('///')[-1]}")
            
            # Verificar se campo já existe
            columns = [col['name'] for col in inspector.get_columns('bot_configs')]
            
            print(f"\n🔄 Verificando campos em bot_configs...")
            
            # Adicionar flow_start_step_id se não existe
            if 'flow_start_step_id' not in columns:
                print(f"➕ Adicionando flow_start_step_id...")
                if dialect_name == 'postgresql':
                    db.session.execute(text("""
                        ALTER TABLE bot_configs 
                        ADD COLUMN IF NOT EXISTS flow_start_step_id VARCHAR(50);
                    """))
                    db.session.commit()
                    
                    # Criar índice
                    db.session.execute(text("""
                        CREATE INDEX IF NOT EXISTS idx_bot_configs_flow_start_step_id 
                        ON bot_configs(flow_start_step_id);
                    """))
                    db.session.commit()
                else:
                    # SQLite
                    db.session.execute(text("""
                        ALTER TABLE bot_configs 
                        ADD COLUMN flow_start_step_id VARCHAR(50);
                    """))
                    db.session.commit()
                
                print(f"✅ Campo flow_start_step_id adicionado à tabela bot_configs")
            else:
                print(f"✅ Campo flow_start_step_id já existe na tabela bot_configs")
            
            print(f"\n✅ Migration concluída com sucesso!")
            return True
            
        except Exception as e:
            print(f"❌ Erro na migration: {e}")
            import traceback
            traceback.print_exc()
            db.session.rollback()
            return False

if __name__ == '__main__':
    success = migrate()
    sys.exit(0 if success else 1)

