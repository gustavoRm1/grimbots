#!/usr/bin/env python3
"""
MIGRAÇÃO CRÍTICA - Paradise Hash
===============================
Adiciona campo gateway_transaction_hash ao modelo Payment
"""

import sys
import os
import sqlite3

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

def migrate_add_transaction_hash():
    """Adiciona campo gateway_transaction_hash ao modelo Payment"""
    
    db_path = "instance/saas_bot_manager.db"
    
    if not os.path.exists(db_path):
        print(f"❌ Banco de dados não encontrado: {db_path}")
        return
    
    print("=" * 80)
    print("MIGRAÇÃO CRÍTICA - PARADISE HASH")
    print("=" * 80)
    
    try:
        conn = sqlite3.connect(db_path)
        cursor = conn.cursor()
        
        # Verificar se a coluna já existe
        cursor.execute("PRAGMA table_info(payments)")
        columns = [column[1] for column in cursor.fetchall()]
        
        if 'gateway_transaction_hash' in columns:
            print("✅ Coluna gateway_transaction_hash já existe")
            return
        
        print("🔧 Adicionando coluna gateway_transaction_hash...")
        
        # Adicionar coluna
        cursor.execute("""
            ALTER TABLE payments 
            ADD COLUMN gateway_transaction_hash VARCHAR(100)
        """)
        
        conn.commit()
        print("✅ Coluna gateway_transaction_hash adicionada com sucesso")
        
        # Verificar se foi adicionada
        cursor.execute("PRAGMA table_info(payments)")
        columns = [column[1] for column in cursor.fetchall()]
        
        if 'gateway_transaction_hash' in columns:
            print("✅ Verificação: Coluna gateway_transaction_hash existe")
        else:
            print("❌ Erro: Coluna não foi adicionada")
        
        conn.close()
        
    except Exception as e:
        print(f"❌ Erro na migração: {e}")
        if 'conn' in locals():
            conn.close()

if __name__ == '__main__':
    migrate_add_transaction_hash()
