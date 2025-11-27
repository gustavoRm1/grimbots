#!/usr/bin/env python3
"""
Script Python para criar tabela subscriptions no banco de dados
Compatível com PostgreSQL e SQLite
"""
import sys
import os

# Adicionar diretório raiz ao path
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from app import app, db
from sqlalchemy import inspect, text

def main():
    print("=" * 70)
    print("🔧 CRIANDO TABELA subscriptions")
    print("=" * 70)
    print()
    
    with app.app_context():
        inspector = inspect(db.engine)
        
        # Verificar se tabela já existe
        tables = inspector.get_table_names()
        if 'subscriptions' in tables:
            print("⚠️ Tabela 'subscriptions' já existe!")
            print()
            columns = inspector.get_columns('subscriptions')
            print(f"✅ Encontradas {len(columns)} colunas:")
            for col in columns:
                print(f"   - {col['name']}: {col['type']}")
            print()
            print("💡 Se precisar recriar, execute manualmente via SQL")
            return True
        
        # Determinar se é PostgreSQL ou SQLite
        is_postgres = db.engine.dialect.name == 'postgresql'
        
        print(f"📊 Banco de dados: {db.engine.dialect.name}")
        print()
        
        if is_postgres:
            print("📝 Criando tabela subscriptions (PostgreSQL)...")
            try:
                # Criar tabela
                db.session.execute(text("""
                    CREATE TABLE subscriptions (
                        id SERIAL PRIMARY KEY,
                        payment_id INTEGER NOT NULL UNIQUE,
                        bot_id INTEGER NOT NULL,
                        telegram_user_id VARCHAR(255) NOT NULL,
                        customer_name VARCHAR(255),
                        duration_type VARCHAR(20) NOT NULL,
                        duration_value INTEGER NOT NULL,
                        vip_chat_id VARCHAR(100) NOT NULL,
                        vip_group_link VARCHAR(500),
                        started_at TIMESTAMP WITH TIME ZONE,
                        expires_at TIMESTAMP WITH TIME ZONE,
                        removed_at TIMESTAMP WITH TIME ZONE,
                        status VARCHAR(20) DEFAULT 'pending',
                        removed_by VARCHAR(50) DEFAULT 'system',
                        error_count INTEGER DEFAULT 0,
                        last_error TEXT,
                        created_at TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP,
                        updated_at TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP,
                        
                        CONSTRAINT uq_subscription_payment UNIQUE (payment_id),
                        CONSTRAINT fk_subscription_payment FOREIGN KEY (payment_id) REFERENCES payments(id) ON DELETE CASCADE,
                        CONSTRAINT fk_subscription_bot FOREIGN KEY (bot_id) REFERENCES bots(id) ON DELETE CASCADE
                    )
                """))
                
                # Criar índices
                indexes = [
                    "CREATE INDEX idx_subscription_status_expires ON subscriptions(status, expires_at)",
                    "CREATE INDEX idx_subscription_vip_chat ON subscriptions(vip_chat_id, status)",
                    "CREATE INDEX idx_subscription_payment_id ON subscriptions(payment_id)",
                    "CREATE INDEX idx_subscription_bot_id ON subscriptions(bot_id)",
                    "CREATE INDEX idx_subscription_telegram_user_id ON subscriptions(telegram_user_id)",
                    "CREATE INDEX idx_subscription_created_at ON subscriptions(created_at)",
                    "CREATE INDEX idx_subscription_status ON subscriptions(status)"
                ]
                
                for index_sql in indexes:
                    try:
                        db.session.execute(text(index_sql))
                    except Exception as e:
                        print(f"⚠️ Erro ao criar índice (pode já existir): {e}")
                
                db.session.commit()
                print("✅ Tabela subscriptions criada com sucesso!")
                print("✅ Índices criados com sucesso!")
                
            except Exception as e:
                db.session.rollback()
                print(f"❌ Erro ao criar tabela: {e}")
                return False
        else:
            print("📝 Criando tabela subscriptions (SQLite)...")
            try:
                db.session.execute(text("""
                    CREATE TABLE subscriptions (
                        id INTEGER PRIMARY KEY AUTOINCREMENT,
                        payment_id INTEGER NOT NULL UNIQUE,
                        bot_id INTEGER NOT NULL,
                        telegram_user_id VARCHAR(255) NOT NULL,
                        customer_name VARCHAR(255),
                        duration_type VARCHAR(20) NOT NULL,
                        duration_value INTEGER NOT NULL,
                        vip_chat_id VARCHAR(100) NOT NULL,
                        vip_group_link VARCHAR(500),
                        started_at TIMESTAMP,
                        expires_at TIMESTAMP,
                        removed_at TIMESTAMP,
                        status VARCHAR(20) DEFAULT 'pending',
                        removed_by VARCHAR(50) DEFAULT 'system',
                        error_count INTEGER DEFAULT 0,
                        last_error TEXT,
                        created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                        updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                        
                        FOREIGN KEY (payment_id) REFERENCES payments(id) ON DELETE CASCADE,
                        FOREIGN KEY (bot_id) REFERENCES bots(id) ON DELETE CASCADE
                    )
                """))
                
                # Criar índices
                indexes = [
                    "CREATE INDEX idx_subscription_status_expires ON subscriptions(status, expires_at)",
                    "CREATE INDEX idx_subscription_vip_chat ON subscriptions(vip_chat_id, status)",
                    "CREATE INDEX idx_subscription_payment_id ON subscriptions(payment_id)",
                    "CREATE INDEX idx_subscription_bot_id ON subscriptions(bot_id)",
                    "CREATE INDEX idx_subscription_telegram_user_id ON subscriptions(telegram_user_id)",
                    "CREATE INDEX idx_subscription_created_at ON subscriptions(created_at)",
                    "CREATE INDEX idx_subscription_status ON subscriptions(status)"
                ]
                
                for index_sql in indexes:
                    try:
                        db.session.execute(text(index_sql))
                    except Exception as e:
                        print(f"⚠️ Erro ao criar índice (pode já existir): {e}")
                
                db.session.commit()
                print("✅ Tabela subscriptions criada com sucesso!")
                print("✅ Índices criados com sucesso!")
                
            except Exception as e:
                db.session.rollback()
                print(f"❌ Erro ao criar tabela: {e}")
                return False
        
        print()
        print("=" * 70)
        print("✅ VERIFICAÇÃO FINAL")
        print("=" * 70)
        
        # Verificar se tabela foi criada
        inspector = inspect(db.engine)
        tables = inspector.get_table_names()
        if 'subscriptions' in tables:
            columns = inspector.get_columns('subscriptions')
            print(f"✅ Tabela 'subscriptions' criada com {len(columns)} colunas")
            return True
        else:
            print("❌ Tabela 'subscriptions' não foi criada")
            return False

if __name__ == '__main__':
    success = main()
    sys.exit(0 if success else 1)

