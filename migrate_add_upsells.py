"""
Migration: Adicionar campos de UPSELL ao BotConfig

Autor: Senior QI 240
Data: 16/10/2025
Versão: Simplificada (reutiliza lógica de downsell)
"""
import sqlite3
import os

def migrate():
    """Adiciona colunas de upsell ao bot_configs"""
    # Encontrar banco de dados
    db_path = 'instance/grpay.db'
    if not os.path.exists(db_path):
        db_path = 'grpay.db'
    
    if not os.path.exists(db_path):
        print("[ERRO] Banco de dados nao encontrado!")
        print("       Procurado em: instance/grpay.db e grpay.db")
        return
    
    print(f"[INFO] Usando banco: {db_path}")
    
    try:
        conn = sqlite3.connect(db_path)
        cursor = conn.cursor()
        
        # Verificar se tabela existe
        cursor.execute("SELECT name FROM sqlite_master WHERE type='table' AND name='bot_configs'")
        if not cursor.fetchone():
            print("[ERRO] Tabela 'bot_configs' nao existe!")
            conn.close()
            return
        
        # Verificar colunas existentes
        cursor.execute("PRAGMA table_info(bot_configs)")
        columns = [row[1] for row in cursor.fetchall()]
        
        if 'upsells' in columns and 'upsells_enabled' in columns:
            print("[OK] Colunas de upsell ja existem. Migration nao necessaria.")
            conn.close()
            return
        
        print("[INFO] Iniciando migration: Adicionar upsells ao BotConfig...")
        
        # Adicionar coluna upsells (TEXT)
        if 'upsells' not in columns:
            cursor.execute("ALTER TABLE bot_configs ADD COLUMN upsells TEXT")
            print("  [OK] Coluna 'upsells' adicionada")
        
        # Adicionar coluna upsells_enabled (BOOLEAN)
        if 'upsells_enabled' not in columns:
            cursor.execute("ALTER TABLE bot_configs ADD COLUMN upsells_enabled BOOLEAN DEFAULT 0")
            print("  [OK] Coluna 'upsells_enabled' adicionada")
        
        conn.commit()
        conn.close()
        
        print("[OK] Migration concluida com sucesso!")
        print("\nPROXIMOS PASSOS:")
        print("1. Upsells podem ser configurados em /bots/{id}/config")
        print("2. Formato JSON: [{\"trigger_product\": \"Produto\", \"delay_minutes\": 0, \"message\": \"...\", \"price\": 97}]")
        print("3. Sistema dispara automaticamente apos compra aprovada")
        
    except Exception as e:
        print(f"[ERRO] Erro na migration: {e}")
        import traceback
        traceback.print_exc()

if __name__ == '__main__':
    migrate()

