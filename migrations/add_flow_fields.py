#!/usr/bin/env python3
"""
Migration: Adicionar flow_enabled, flow_steps ao BotConfig e flow_step_id ao Payment
"""
import sys
import os
from pathlib import Path

# Adicionar diretório atual ao path
BASE_DIR = Path(__file__).parent.parent
sys.path.insert(0, str(BASE_DIR))

# ✅ Criar app mínimo para evitar dependências pesadas (SocketIO, etc)
from flask import Flask
from flask_sqlalchemy import SQLAlchemy

app = Flask(__name__)

# ✅ Usar mesmo padrão do app.py para detectar banco
DB_PATH = BASE_DIR / 'instance' / 'saas_bot_manager.db'
database_uri = os.environ.get('DATABASE_URL', f'sqlite:///{DB_PATH}')

app.config['SQLALCHEMY_DATABASE_URI'] = database_uri
app.config['SQLALCHEMY_TRACK_MODIFICATIONS'] = False

# Ajuste para SQLite
connect_args = {'check_same_thread': False} if database_uri.startswith('sqlite') else {}

app.config['SQLALCHEMY_ENGINE_OPTIONS'] = {
    'pool_pre_ping': True,
    'pool_recycle': 3600,
    'connect_args': connect_args
}

db = SQLAlchemy(app)

from sqlalchemy import inspect, text

def migrate():
    """Adiciona campos flow_enabled, flow_steps ao BotConfig e flow_step_id ao Payment"""
    with app.app_context():
        try:
            inspector = inspect(db.engine)
            dialect_name = db.engine.dialect.name
            print(f"🔄 Database detectado: {dialect_name}")
            
            # ✅ Adicionar flow_enabled ao BotConfig
            print("\n🔄 Verificando campos em bot_configs...")
            try:
                bot_configs_columns = [col['name'] for col in inspector.get_columns('bot_configs')]
            except Exception as e:
                print(f"⚠️ Erro ao ler colunas de bot_configs: {e}")
                bot_configs_columns = []
            
            if 'flow_enabled' not in bot_configs_columns:
                print("🔄 Adicionando campo flow_enabled na tabela bot_configs...")
                if dialect_name == 'postgresql':
                    db.session.execute(text("""
                        ALTER TABLE bot_configs 
                        ADD COLUMN IF NOT EXISTS flow_enabled BOOLEAN DEFAULT FALSE
                    """))
                else:
                    db.session.execute(text("""
                        ALTER TABLE bot_configs 
                        ADD COLUMN flow_enabled BOOLEAN DEFAULT FALSE
                    """))
                db.session.commit()
                print("✅ Campo flow_enabled adicionado com sucesso!")
                
                # Criar índice após commit
                try:
                    db.session.execute(text("""
                        CREATE INDEX IF NOT EXISTS idx_bot_configs_flow_enabled 
                        ON bot_configs(flow_enabled)
                    """))
                    db.session.commit()
                    print("✅ Índice flow_enabled criado com sucesso!")
                except Exception as idx_error:
                    print(f"⚠️ Erro ao criar índice (não crítico): {idx_error}")
                    db.session.rollback()
            else:
                print("✅ Campo flow_enabled já existe na tabela bot_configs")
            
            # ✅ Adicionar flow_steps ao BotConfig
            if 'flow_steps' not in bot_configs_columns:
                print("🔄 Adicionando campo flow_steps na tabela bot_configs...")
                if dialect_name == 'postgresql':
                    db.session.execute(text("""
                        ALTER TABLE bot_configs 
                        ADD COLUMN IF NOT EXISTS flow_steps TEXT
                    """))
                else:
                    db.session.execute(text("""
                        ALTER TABLE bot_configs 
                        ADD COLUMN flow_steps TEXT
                    """))
                db.session.commit()
                print("✅ Campo flow_steps adicionado com sucesso!")
            else:
                print("✅ Campo flow_steps já existe na tabela bot_configs")
            
            # ✅ Adicionar flow_step_id ao Payment
            print("\n🔄 Verificando campos em payments...")
            try:
                payments_columns = [col['name'] for col in inspector.get_columns('payments')]
            except Exception as e:
                print(f"⚠️ Erro ao ler colunas de payments: {e}")
                payments_columns = []
            
            if 'flow_step_id' not in payments_columns:
                print("🔄 Adicionando campo flow_step_id na tabela payments...")
                if dialect_name == 'postgresql':
                    db.session.execute(text("""
                        ALTER TABLE payments 
                        ADD COLUMN IF NOT EXISTS flow_step_id VARCHAR(50)
                    """))
                else:
                    db.session.execute(text("""
                        ALTER TABLE payments 
                        ADD COLUMN flow_step_id VARCHAR(50)
                    """))
                db.session.commit()
                print("✅ Campo flow_step_id adicionado com sucesso!")
                
                # Criar índice após commit
                try:
                    db.session.execute(text("""
                        CREATE INDEX IF NOT EXISTS idx_payments_flow_step_id 
                        ON payments(flow_step_id)
                    """))
                    db.session.commit()
                    print("✅ Índice flow_step_id criado com sucesso!")
                except Exception as idx_error:
                    print(f"⚠️ Erro ao criar índice (não crítico): {idx_error}")
                    db.session.rollback()
            else:
                print("✅ Campo flow_step_id já existe na tabela payments")
            
            print("\n✅ Migration concluída com sucesso!")
            return True
            
        except Exception as e:
            db.session.rollback()
            print(f"❌ Erro ao executar migration: {e}")
            import traceback
            traceback.print_exc()
            return False

if __name__ == '__main__':
    migrate()

