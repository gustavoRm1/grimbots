"""
EMERGENCY FIX - Adiciona colunas archived em BotUser
======================================================
EXECUTAR IMEDIATAMENTE EM PRODUCAO

Este script:
1. Adiciona colunas archived, archived_reason, archived_at
2. É idempotente (pode executar múltiplas vezes)
3. Cria índice em archived para performance
4. Valida schema após execução

COMO EXECUTAR:
--------------
cd /root/grimbots
source venv/bin/activate
python fix_production_emergency.py

Após executar, reiniciar os bots:
pm2 restart all
"""

import sys
import sqlite3
from pathlib import Path

def check_column_exists(cursor, table, column):
    """Verifica se coluna existe na tabela"""
    cursor.execute(f"PRAGMA table_info({table})")
    columns = [row[1] for row in cursor.fetchall()]
    return column in columns

def fix_production_db():
    """Adiciona colunas archived no banco de produção"""
    
    # Caminho do banco
    db_path = Path(__file__).parent / 'instance' / 'saas_bot_manager.db'
    
    if not db_path.exists():
        print(f"❌ ERRO: Banco não encontrado em {db_path}")
        return False
    
    print("=" * 80)
    print("🚨 EMERGENCY FIX - BotUser Archived Fields")
    print("=" * 80)
    print(f"\n📁 Banco: {db_path}\n")
    
    try:
        # Conectar ao banco
        conn = sqlite3.connect(str(db_path))
        cursor = conn.cursor()
        
        # Verificar colunas existentes
        print("🔍 Verificando schema atual...")
        cursor.execute("PRAGMA table_info(bot_users)")
        current_columns = [row[1] for row in cursor.fetchall()]
        print(f"   Colunas atuais: {len(current_columns)}")
        
        changes_made = False
        
        # 1. Adicionar coluna archived
        if not check_column_exists(cursor, 'bot_users', 'archived'):
            print("\n➕ Adicionando coluna 'archived'...")
            cursor.execute("""
                ALTER TABLE bot_users 
                ADD COLUMN archived BOOLEAN DEFAULT 0
            """)
            print("   ✅ Coluna 'archived' adicionada")
            changes_made = True
        else:
            print("\n✓ Coluna 'archived' já existe")
        
        # 2. Adicionar coluna archived_reason
        if not check_column_exists(cursor, 'bot_users', 'archived_reason'):
            print("\n➕ Adicionando coluna 'archived_reason'...")
            cursor.execute("""
                ALTER TABLE bot_users 
                ADD COLUMN archived_reason VARCHAR(100)
            """)
            print("   ✅ Coluna 'archived_reason' adicionada")
            changes_made = True
        else:
            print("\n✓ Coluna 'archived_reason' já existe")
        
        # 3. Adicionar coluna archived_at
        if not check_column_exists(cursor, 'bot_users', 'archived_at'):
            print("\n➕ Adicionando coluna 'archived_at'...")
            cursor.execute("""
                ALTER TABLE bot_users 
                ADD COLUMN archived_at DATETIME
            """)
            print("   ✅ Coluna 'archived_at' adicionada")
            changes_made = True
        else:
            print("\n✓ Coluna 'archived_at' já existe")
        
        # 4. Criar índice se não existir
        print("\n📊 Verificando índice 'idx_bot_users_archived'...")
        cursor.execute("""
            SELECT name FROM sqlite_master 
            WHERE type='index' AND name='idx_bot_users_archived'
        """)
        
        if not cursor.fetchone():
            print("   Criando índice para performance...")
            cursor.execute("""
                CREATE INDEX idx_bot_users_archived 
                ON bot_users(archived)
            """)
            print("   ✅ Índice criado")
            changes_made = True
        else:
            print("   ✓ Índice já existe")
        
        # Commit das alterações
        if changes_made:
            conn.commit()
            print("\n💾 Alterações commitadas com sucesso")
        
        # Validar schema final
        print("\n🔍 Validando schema final...")
        cursor.execute("PRAGMA table_info(bot_users)")
        final_columns = {row[1]: row[2] for row in cursor.fetchall()}
        
        required_columns = {
            'archived': 'BOOLEAN',
            'archived_reason': 'VARCHAR(100)',
            'archived_at': 'DATETIME'
        }
        
        all_ok = True
        for col, expected_type in required_columns.items():
            if col not in final_columns:
                print(f"   ❌ ERRO: Coluna '{col}' não encontrada!")
                all_ok = False
            else:
                print(f"   ✅ {col}: {final_columns[col]}")
        
        # Contar registros
        cursor.execute("SELECT COUNT(*) FROM bot_users")
        total = cursor.fetchone()[0]
        
        cursor.execute("SELECT COUNT(*) FROM bot_users WHERE archived = 1")
        archived = cursor.fetchone()[0]
        
        print(f"\n📊 Estatísticas:")
        print(f"   Total de usuários: {total}")
        print(f"   Arquivados: {archived}")
        print(f"   Ativos: {total - archived}")
        
        conn.close()
        
        if all_ok:
            print("\n" + "=" * 80)
            print("✅ MIGRAÇÃO CONCLUÍDA COM SUCESSO!")
            print("=" * 80)
            print("\n📌 PRÓXIMOS PASSOS:")
            print("   1. Executar: pm2 restart all")
            print("   2. Testar comando /start em qualquer bot")
            print("   3. Monitorar logs: pm2 logs\n")
            return True
        else:
            print("\n❌ ERRO: Schema inválido após migração")
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
    success = fix_production_db()
    print()
    
    if success:
        sys.exit(0)
    else:
        print("❌ Migração falhou. Contate o desenvolvedor.")
        sys.exit(1)

