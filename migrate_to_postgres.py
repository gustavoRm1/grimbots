#!/usr/bin/env python
"""
Script de Migração SQLite → PostgreSQL
✅ Migra todos os dados preservando integridade
✅ Backup automático antes da migração
✅ Validação de dados após migração
"""

import sqlite3
import psycopg2
from psycopg2.extras import execute_values
import os
import json
from datetime import datetime
import sys

def backup_sqlite(db_path):
    """Cria backup do banco SQLite antes da migração"""
    backup_path = f"{db_path}.backup_{datetime.now().strftime('%Y%m%d_%H%M%S')}"
    
    print(f"📦 Criando backup: {backup_path}")
    
    import shutil
    shutil.copy2(db_path, backup_path)
    
    print(f"✅ Backup criado com sucesso")
    return backup_path


def get_table_schema(sqlite_cursor, table_name):
    """Retorna schema da tabela do SQLite"""
    sqlite_cursor.execute(f"PRAGMA table_info({table_name})")
    return sqlite_cursor.fetchall()


def migrate_table(sqlite_conn, pg_conn, table_name, batch_size=1000):
    """Migra uma tabela específica do SQLite para PostgreSQL"""
    sqlite_cursor = sqlite_conn.cursor()
    sqlite_cursor.row_factory = sqlite3.Row
    pg_cursor = pg_conn.cursor()
    
    print(f"\n📋 Migrando tabela: {table_name}")
    
    # Contar linhas
    sqlite_cursor.execute(f"SELECT COUNT(*) FROM {table_name}")
    total_rows = sqlite_cursor.fetchone()[0]
    
    if total_rows == 0:
        print(f"  ⚠️  Tabela vazia, pulando...")
        return 0
    
    print(f"  Total de linhas: {total_rows}")
    
    # Ler todas as linhas
    sqlite_cursor.execute(f"SELECT * FROM {table_name}")
    rows = sqlite_cursor.fetchall()
    
    if not rows:
        return 0
    
    # Obter colunas
    columns = [desc[0] for desc in sqlite_cursor.description]

    # Identificar colunas booleanas no PostgreSQL para conversão adequada
    pg_cursor.execute(
        """
        SELECT column_name
        FROM information_schema.columns
        WHERE table_name = %s AND data_type = 'boolean'
        """,
        (table_name,)
    )
    boolean_columns = {row[0] for row in pg_cursor.fetchall()}
    
    # Converter rows para tuplas
    values = []
    for row in rows:
        row_values = []
        for idx, value in enumerate(row):
            column_name = columns[idx]
            # Converter valores especiais
            if isinstance(value, str):
                # Tentar decodificar JSON se parecer JSON
                if value.startswith('{') or value.startswith('['):
                    try:
                        json.loads(value)  # Validar JSON
                        row_values.append(value)
                    except:
                        row_values.append(value)
                else:
                    row_values.append(value)
            else:
                row_values.append(value)

            # Ajustar valores booleanos (SQLite armazena como 0/1)
            if column_name in boolean_columns:
                raw_value = row_values[-1]
                if raw_value is None:
                    converted = None
                elif isinstance(raw_value, bool):
                    converted = raw_value
                elif isinstance(raw_value, (int, float)):
                    converted = bool(raw_value)
                elif isinstance(raw_value, str):
                    lowered = raw_value.strip().lower()
                    if lowered in {'true', 't', 'yes', 'y', '1'}:
                        converted = True
                    elif lowered in {'false', 'f', 'no', 'n', '0'}:
                        converted = False
                    else:
                        # Fallback: qualquer string não vazia vira True
                        converted = bool(raw_value)
                else:
                    converted = bool(raw_value)

                row_values[-1] = converted
        
        values.append(tuple(row_values))
    
    # Inserir em lotes
    migrated = 0
    for i in range(0, len(values), batch_size):
        batch = values[i:i + batch_size]
        
        # Preparar query
        placeholders = ','.join(['%s'] * len(columns))
        columns_str = ','.join([f'"{col}"' for col in columns])
        insert_query = f'INSERT INTO {table_name} ({columns_str}) VALUES %s ON CONFLICT DO NOTHING'
        
        try:
            execute_values(pg_cursor, insert_query, batch)
            pg_conn.commit()
            migrated += len(batch)
            print(f"  Progresso: {migrated}/{total_rows} ({migrated*100//total_rows}%)", end='\r')
        except Exception as e:
            print(f"\n  ❌ Erro ao inserir batch: {e}")
            pg_conn.rollback()
            # Tentar inserir linha por linha
            for value in batch:
                try:
                    single_query = f'INSERT INTO {table_name} ({columns_str}) VALUES ({placeholders}) ON CONFLICT DO NOTHING'
                    pg_cursor.execute(single_query, value)
                    pg_conn.commit()
                    migrated += 1
                except Exception as e2:
                    print(f"\n  ⚠️  Erro ao inserir linha: {e2}")
                    pg_conn.rollback()
    
    print(f"\n  ✅ {migrated}/{total_rows} linhas migradas")
    return migrated


def validate_migration(sqlite_conn, pg_conn, table_name):
    """Valida se a migração foi bem-sucedida"""
    sqlite_cursor = sqlite_conn.cursor()
    pg_cursor = pg_conn.cursor()
    
    # Contar linhas em ambos
    sqlite_cursor.execute(f"SELECT COUNT(*) FROM {table_name}")
    sqlite_count = sqlite_cursor.fetchone()[0]
    
    pg_cursor.execute(f"SELECT COUNT(*) FROM {table_name}")
    pg_count = pg_cursor.fetchone()[0]
    
    if sqlite_count == pg_count:
        print(f"  ✅ Validação OK: {pg_count} linhas")
        return True
    else:
        print(f"  ⚠️  Diferença detectada: SQLite={sqlite_count}, PostgreSQL={pg_count}")
        return False


def main():
    """Função principal de migração"""
    print("="*70)
    print(" MIGRAÇÃO SQLite → PostgreSQL - GRIMBOTS QI 500")
    print("="*70)
    print()
    
    # Configurações
    sqlite_db = os.environ.get('SQLITE_DB', 'instance/saas_bot_manager.db')
    pg_host = os.environ.get('PG_HOST', 'localhost')
    pg_port = os.environ.get('PG_PORT', '5432')
    pg_user = os.environ.get('PG_USER', 'grimbots')
    pg_password = os.environ.get('PG_PASSWORD', '')
    pg_database = os.environ.get('PG_DATABASE', 'grimbots')
    
    if not pg_password:
        print("❌ ERRO: PG_PASSWORD não configurado!")
        print("Configure: export PG_PASSWORD='sua_senha'")
        sys.exit(1)
    
    print(f"SQLite: {sqlite_db}")
    print(f"PostgreSQL: {pg_user}@{pg_host}:{pg_port}/{pg_database}")
    print()
    
    # Confirmar
    confirm = input("⚠️  Esta operação irá migrar dados. Continuar? (s/N): ")
    if confirm.lower() != 's':
        print("❌ Migração cancelada")
        sys.exit(0)
    
    # Backup
    backup_path = backup_sqlite(sqlite_db)
    
    # Conectar aos bancos
    print("\n🔌 Conectando aos bancos de dados...")
    
    try:
        sqlite_conn = sqlite3.connect(sqlite_db)
        print("  ✅ SQLite conectado")
    except Exception as e:
        print(f"  ❌ Erro ao conectar SQLite: {e}")
        sys.exit(1)
    
    try:
        pg_conn = psycopg2.connect(
            host=pg_host,
            port=pg_port,
            user=pg_user,
            password=pg_password,
            database=pg_database
        )
        print("  ✅ PostgreSQL conectado")
    except Exception as e:
        print(f"  ❌ Erro ao conectar PostgreSQL: {e}")
        print(f"     Verifique se PostgreSQL está rodando e as credenciais estão corretas")
        sys.exit(1)
    
    # Lista de tabelas em ordem (respeitando foreign keys)
    tables = [
        'users',
        'bots',
        'bot_configs',
        'gateways',
        'redirect_pools',
        'pool_bots',
        'bot_users',
        'bot_messages',
        'payments',
        'commissions',
        'achievements',
        'user_achievements',
        'audit_logs',
        'remarketing_campaigns',
        'remarketing_blacklist',
        'push_subscriptions',
        'notification_settings'
    ]
    
    # Migrar cada tabela
    total_migrated = 0
    successful_tables = 0
    
    for table in tables:
        try:
            # Verificar se tabela existe no SQLite
            sqlite_cursor = sqlite_conn.cursor()
            sqlite_cursor.execute(f"SELECT name FROM sqlite_master WHERE type='table' AND name='{table}'")
            if not sqlite_cursor.fetchone():
                print(f"\n⚠️  Tabela {table} não existe no SQLite, pulando...")
                continue
            
            # Migrar
            migrated = migrate_table(sqlite_conn, pg_conn, table)
            total_migrated += migrated
            
            # Validar
            if validate_migration(sqlite_conn, pg_conn, table):
                successful_tables += 1
            
        except Exception as e:
            print(f"\n❌ Erro ao migrar tabela {table}: {e}")
            print(f"   Continuando com próxima tabela...")
    
    # Atualizar sequences (PostgreSQL)
    print("\n🔢 Atualizando sequences do PostgreSQL...")
    pg_cursor = pg_conn.cursor()
    
    for table in tables:
        try:
            # Verificar se tabela tem coluna id
            pg_cursor.execute(f"""
                SELECT column_name 
                FROM information_schema.columns 
                WHERE table_name = '{table}' AND column_name = 'id'
            """)
            
            if pg_cursor.fetchone():
                # Atualizar sequence
                pg_cursor.execute(f"""
                    SELECT setval(pg_get_serial_sequence('{table}', 'id'), 
                    (SELECT MAX(id) FROM {table}))
                """)
                pg_conn.commit()
                print(f"  ✅ Sequence atualizada: {table}")
        except Exception as e:
            print(f"  ⚠️  Erro ao atualizar sequence de {table}: {e}")
            pg_conn.rollback()
    
    # Fechar conexões
    sqlite_conn.close()
    pg_conn.close()
    
    # Resumo
    print("\n" + "="*70)
    print(" RESUMO DA MIGRAÇÃO")
    print("="*70)
    print(f"  Tabelas migradas: {successful_tables}/{len(tables)}")
    print(f"  Total de linhas: {total_migrated}")
    print(f"  Backup salvo em: {backup_path}")
    print("="*70)
    
    if successful_tables == len(tables):
        print("\n✅ MIGRAÇÃO CONCLUÍDA COM SUCESSO!")
        print("\nPróximos passos:")
        print("  1. Validar dados no PostgreSQL")
        print("  2. Atualizar DATABASE_URL no .env")
        print("  3. Reiniciar aplicação")
        print("  4. Testar funcionalidade")
        print(f"\n  DATABASE_URL=postgresql://{pg_user}:{pg_password}@{pg_host}:{pg_port}/{pg_database}")
    else:
        print("\n⚠️  MIGRAÇÃO PARCIAL - Algumas tabelas falharam")
        print("Verifique os erros acima")
    
    return 0 if successful_tables == len(tables) else 1


if __name__ == '__main__':
    try:
        exit_code = main()
        sys.exit(exit_code)
    except KeyboardInterrupt:
        print("\n\n❌ Migração interrompida pelo usuário")
        sys.exit(1)
    except Exception as e:
        print(f"\n\n❌ ERRO CRÍTICO: {e}")
        import traceback
        traceback.print_exc()
        sys.exit(1)

