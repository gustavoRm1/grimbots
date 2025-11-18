#!/usr/bin/env python3
"""
Migration: Adicionar flow_enabled, flow_steps ao BotConfig e flow_step_id ao Payment
"""
import sys
import os

# Adicionar diretório atual ao path
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

# ✅ Importar app diretamente (tem configuração correta do banco)
try:
    from app import app, db
except ImportError:
    # Fallback: criar app mínimo se app.py não puder ser importado
    from flask import Flask
    from flask_sqlalchemy import SQLAlchemy
    import os
    
    app = Flask(__name__)
    # Usar mesmo padrão do app.py
    database_path = os.path.join(os.path.dirname(os.path.dirname(__file__)), 'instance', 'saas_bot_manager.db')
    app.config['SQLALCHEMY_DATABASE_URI'] = f'sqlite:///{database_path}'
    app.config['SQLALCHEMY_TRACK_MODIFICATIONS'] = False
    
    db = SQLAlchemy(app)

from sqlalchemy import inspect, text

def migrate():
    with app.app_context():
        try:
            inspector = inspect(db.engine)
            
            # ✅ Adicionar flow_enabled ao BotConfig
            bot_configs_columns = [col['name'] for col in inspector.get_columns('bot_configs')]
            if 'flow_enabled' not in bot_configs_columns:
                print("🔄 Adicionando campo flow_enabled na tabela bot_configs...")
                db.session.execute(text("""
                    ALTER TABLE bot_configs 
                    ADD COLUMN flow_enabled BOOLEAN DEFAULT FALSE
                """))
                db.session.execute(text("""
                    CREATE INDEX IF NOT EXISTS idx_bot_configs_flow_enabled 
                    ON bot_configs(flow_enabled)
                """))
                print("✅ Campo flow_enabled adicionado com sucesso!")
            else:
                print("✅ Campo flow_enabled já existe na tabela bot_configs")
            
            # ✅ Adicionar flow_steps ao BotConfig
            if 'flow_steps' not in bot_configs_columns:
                print("🔄 Adicionando campo flow_steps na tabela bot_configs...")
                db.session.execute(text("""
                    ALTER TABLE bot_configs 
                    ADD COLUMN flow_steps TEXT
                """))
                print("✅ Campo flow_steps adicionado com sucesso!")
            else:
                print("✅ Campo flow_steps já existe na tabela bot_configs")
            
            # ✅ Adicionar flow_step_id ao Payment
            payments_columns = [col['name'] for col in inspector.get_columns('payments')]
            if 'flow_step_id' not in payments_columns:
                print("🔄 Adicionando campo flow_step_id na tabela payments...")
                db.session.execute(text("""
                    ALTER TABLE payments 
                    ADD COLUMN flow_step_id VARCHAR(50)
                """))
                db.session.execute(text("""
                    CREATE INDEX IF NOT EXISTS idx_payments_flow_step_id 
                    ON payments(flow_step_id)
                """))
                print("✅ Campo flow_step_id adicionado com sucesso!")
            else:
                print("✅ Campo flow_step_id já existe na tabela payments")
            
            db.session.commit()
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

