"""
Migration: Adicionar campo split_user_id para WiinPay

Autor: Senior QI 240
Data: 16/10/2025
"""
import sqlite3
import os

def migrate():
    """Adiciona coluna split_user_id ao gateways"""
    # Encontrar banco de dados
    db_path = 'instance/grpay.db'
    if not os.path.exists(db_path):
        db_path = 'grpay.db'
    
    if not os.path.exists(db_path):
        print("[INFO] Banco de dados nao encontrado - sera criado no primeiro run")
        return
    
    print(f"[INFO] Usando banco: {db_path}")
    
    try:
        conn = sqlite3.connect(db_path)
        cursor = conn.cursor()
        
        # Verificar se tabela existe
        cursor.execute("SELECT name FROM sqlite_master WHERE type='table' AND name='gateways'")
        if not cursor.fetchone():
            print("[INFO] Tabela 'gateways' ainda nao existe - sera criada no init_db.py")
            conn.close()
            return
        
        # Verificar colunas existentes
        cursor.execute("PRAGMA table_info(gateways)")
        columns = [row[1] for row in cursor.fetchall()]
        
        if 'split_user_id' in columns:
            print("[OK] Coluna 'split_user_id' ja existe. Migration nao necessaria.")
            conn.close()
            return
        
        print("[INFO] Iniciando migration: Adicionar split_user_id para WiinPay...")
        
        # Adicionar coluna split_user_id (TEXT criptografado)
        cursor.execute("ALTER TABLE gateways ADD COLUMN split_user_id TEXT")
        print("  [OK] Coluna 'split_user_id' adicionada")
        
        conn.commit()
        conn.close()
        
        print("[OK] Migration concluida com sucesso!")
        print("\nPROXIMOS PASSOS:")
        print("1. WiinPay pode ser configurado em /settings")
        print("2. Gateway type: 'wiinpay'")
        print("3. Campos: api_key + split_user_id (seu user_id na WiinPay)")
        
    except Exception as e:
        print(f"[ERRO] Erro na migration: {e}")
        import traceback
        traceback.print_exc()

if __name__ == '__main__':
    migrate()

