#!/usr/bin/env python3
"""
Script Python para adicionar colunas de subscription na tabela payments
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
    print("🔧 ADICIONANDO COLUNAS DE SUBSCRIPTION NA TABELA payments")
    print("=" * 70)
    print()
    
    with app.app_context():
        inspector = inspect(db.engine)
        columns = {col['name']: col for col in inspector.get_columns('payments')}
        
        # Verificar e adicionar button_index
        if 'button_index' not in columns:
            try:
                db.session.execute(text("ALTER TABLE payments ADD COLUMN button_index INTEGER"))
                db.session.commit()
                print("✅ Coluna button_index adicionada")
            except Exception as e:
                print(f"❌ Erro ao adicionar button_index: {e}")
                db.session.rollback()
        else:
            print("⚠️ Coluna button_index já existe")
        
        # Verificar e adicionar button_config
        if 'button_config' not in columns:
            try:
                db.session.execute(text("ALTER TABLE payments ADD COLUMN button_config TEXT"))
                db.session.commit()
                print("✅ Coluna button_config adicionada")
            except Exception as e:
                print(f"❌ Erro ao adicionar button_config: {e}")
                db.session.rollback()
        else:
            print("⚠️ Coluna button_config já existe")
        
        # Verificar e adicionar has_subscription
        if 'has_subscription' not in columns:
            try:
                # PostgreSQL usa BOOLEAN, SQLite usa INTEGER
                is_postgres = db.engine.dialect.name == 'postgresql'
                col_type = "BOOLEAN DEFAULT FALSE" if is_postgres else "INTEGER DEFAULT 0"
                
                db.session.execute(text(f"ALTER TABLE payments ADD COLUMN has_subscription {col_type}"))
                db.session.commit()
                print("✅ Coluna has_subscription adicionada")
            except Exception as e:
                print(f"❌ Erro ao adicionar has_subscription: {e}")
                db.session.rollback()
        else:
            print("⚠️ Coluna has_subscription já existe")
        
        # Criar índice (apenas PostgreSQL)
        if db.engine.dialect.name == 'postgresql':
            try:
                db.session.execute(text("""
                    CREATE INDEX IF NOT EXISTS idx_payment_has_subscription 
                    ON payments(has_subscription) 
                    WHERE has_subscription = TRUE
                """))
                db.session.commit()
                print("✅ Índice idx_payment_has_subscription criado")
            except Exception as e:
                print(f"⚠️ Erro ao criar índice (pode já existir): {e}")
                db.session.rollback()
        
        print()
        print("=" * 70)
        print("✅ VERIFICAÇÃO FINAL")
        print("=" * 70)
        
        # Verificar colunas finais
        inspector = inspect(db.engine)
        columns = {col['name']: col for col in inspector.get_columns('payments')}
        
        required = ['button_index', 'button_config', 'has_subscription']
        for col in required:
            if col in columns:
                print(f"✅ {col}: {columns[col]['type']}")
            else:
                print(f"❌ {col}: NÃO EXISTE")
        
        print()
        print("=" * 70)
        all_ok = all(col in columns for col in required)
        if all_ok:
            print("✅ TODAS AS COLUNAS FORAM ADICIONADAS COM SUCESSO!")
        else:
            print("❌ ALGUMAS COLUNAS NÃO FORAM ADICIONADAS!")
        print("=" * 70)
        
        return all_ok

if __name__ == '__main__':
    success = main()
    sys.exit(0 if success else 1)

