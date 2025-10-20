"""
Migration: Tracking de Mensagem de Boas-Vindas
===============================================
Adiciona flag 'welcome_sent' para rastrear se usuário já recebeu mensagem inicial.

BENEFÍCIO:
- Recuperação automática de leads que crasharam
- Evita enviar mensagem duplicada
- Permite re-engajamento inteligente

Execução: python migrate_add_welcome_tracking.py
"""

import sys
import sqlite3
from pathlib import Path
from datetime import datetime

def migrate_add_welcome_tracking():
    """Adiciona campos de tracking de boas-vindas"""
    
    db_path = Path(__file__).parent / 'instance' / 'saas_bot_manager.db'
    
    if not db_path.exists():
        print(f"❌ ERRO: Banco não encontrado em {db_path}")
        return False
    
    print("=" * 80)
    print("MIGRAÇÃO: Tracking de Mensagem de Boas-Vindas")
    print("=" * 80)
    print()
    
    try:
        conn = sqlite3.connect(str(db_path))
        cursor = conn.cursor()
        
        # Verificar se coluna já existe
        cursor.execute("PRAGMA table_info(bot_users)")
        columns = [row[1] for row in cursor.fetchall()]
        
        if 'welcome_sent' in columns:
            print("✓ Coluna 'welcome_sent' já existe")
            conn.close()
            return True
        
        print("➕ Adicionando coluna 'welcome_sent'...")
        
        # Adicionar coluna
        cursor.execute("""
            ALTER TABLE bot_users 
            ADD COLUMN welcome_sent BOOLEAN DEFAULT 0
        """)
        
        print("   ✅ Coluna adicionada")
        
        # Marcar todos os usuários EXISTENTES como já tendo recebido
        # (assumindo que foram criados com sucesso = receberam mensagem)
        print("\n🔄 Atualizando usuários existentes...")
        cursor.execute("""
            UPDATE bot_users 
            SET welcome_sent = 1 
            WHERE welcome_sent = 0
        """)
        
        updated = cursor.rowcount
        print(f"   ✅ {updated} usuários marcados como 'welcome_sent=True'")
        
        # Adicionar timestamp de quando enviou
        print("\n➕ Adicionando coluna 'welcome_sent_at'...")
        cursor.execute("""
            ALTER TABLE bot_users 
            ADD COLUMN welcome_sent_at DATETIME
        """)
        print("   ✅ Coluna adicionada")
        
        # Marcar timestamp dos existentes como first_interaction
        cursor.execute("""
            UPDATE bot_users 
            SET welcome_sent_at = first_interaction 
            WHERE welcome_sent = 1 AND welcome_sent_at IS NULL
        """)
        print(f"   ✅ Timestamps atualizados")
        
        # Commit
        conn.commit()
        
        # Validar
        print("\n🔍 Validando migração...")
        cursor.execute("PRAGMA table_info(bot_users)")
        final_columns = {row[1]: row[2] for row in cursor.fetchall()}
        
        required = ['welcome_sent', 'welcome_sent_at']
        all_ok = True
        
        for col in required:
            if col in final_columns:
                print(f"   ✅ {col}: {final_columns[col]}")
            else:
                print(f"   ❌ {col}: FALTANDO")
                all_ok = False
        
        # Estatísticas
        cursor.execute("SELECT COUNT(*) FROM bot_users WHERE welcome_sent = 1")
        with_welcome = cursor.fetchone()[0]
        
        cursor.execute("SELECT COUNT(*) FROM bot_users WHERE welcome_sent = 0")
        without_welcome = cursor.fetchone()[0]
        
        print(f"\n📊 Estatísticas:")
        print(f"   Usuários com boas-vindas enviadas: {with_welcome}")
        print(f"   Usuários sem boas-vindas: {without_welcome}")
        
        conn.close()
        
        if all_ok:
            print("\n" + "=" * 80)
            print("✅ MIGRAÇÃO CONCLUÍDA COM SUCESSO!")
            print("=" * 80)
            print()
            print("📌 Agora o sistema irá:")
            print("   1. Rastrear quando mensagem de boas-vindas é enviada")
            print("   2. Re-enviar automaticamente se não foi enviada antes")
            print("   3. Evitar spam (não envia duplicado)")
            print()
            return True
        else:
            print("\n❌ ERRO: Schema inválido")
            return False
            
    except sqlite3.Error as e:
        print(f"\n❌ ERRO SQLite: {e}")
        return False
    except Exception as e:
        print(f"\n❌ ERRO: {e}")
        import traceback
        traceback.print_exc()
        return False

if __name__ == '__main__':
    print()
    success = migrate_add_welcome_tracking()
    print()
    
    if success:
        print("🚀 Próximo passo: Atualizar bot_manager.py para usar a flag")
        sys.exit(0)
    else:
        print("❌ Migração falhou")
        sys.exit(1)

