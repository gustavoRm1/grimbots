#!/usr/bin/env python3
"""
Migração: Adicionar campos Meta Pixel aos modelos Bot e Payment
Data: 2024-10-20
Autor: Senior QI 300
"""

import sqlite3
import os
import sys
from datetime import datetime

def get_db_path():
    """Retorna o caminho do banco de dados"""
    return os.path.join('instance', 'saas_bot_manager.db')

def backup_database():
    """Cria backup do banco antes da migração"""
    db_path = get_db_path()
    backup_path = f"{db_path}.backup_{datetime.now().strftime('%Y%m%d_%H%M%S')}"
    
    if os.path.exists(db_path):
        import shutil
        shutil.copy2(db_path, backup_path)
        print(f"✅ Backup criado: {backup_path}")
        return backup_path
    return None

def check_column_exists(cursor, table_name, column_name):
    """Verifica se uma coluna existe na tabela"""
    cursor.execute(f"PRAGMA table_info({table_name})")
    columns = [row[1] for row in cursor.fetchall()]
    return column_name in columns

def migrate_bot_table(cursor):
    """Adiciona campos Meta Pixel à tabela bots"""
    print("🔧 Migrando tabela 'bots'...")
    
    # Campos para adicionar
    new_columns = [
        ('meta_pixel_id', 'VARCHAR(50)'),
        ('meta_access_token', 'TEXT'),  # Será criptografado
        ('meta_tracking_enabled', 'BOOLEAN DEFAULT 0'),
        ('meta_test_event_code', 'VARCHAR(100)'),
        ('meta_events_pageview', 'BOOLEAN DEFAULT 1'),
        ('meta_events_viewcontent', 'BOOLEAN DEFAULT 1'),
        ('meta_events_purchase', 'BOOLEAN DEFAULT 1'),
        ('meta_cloaker_enabled', 'BOOLEAN DEFAULT 0'),
        ('meta_cloaker_param_name', 'VARCHAR(20) DEFAULT "apx"'),
        ('meta_cloaker_param_value', 'VARCHAR(50)')
    ]
    
    for column_name, column_type in new_columns:
        if not check_column_exists(cursor, 'bots', column_name):
            try:
                cursor.execute(f"ALTER TABLE bots ADD COLUMN {column_name} {column_type}")
                print(f"  ✅ Adicionada coluna: {column_name}")
            except Exception as e:
                print(f"  ❌ Erro ao adicionar {column_name}: {e}")
        else:
            print(f"  ⚠️ Coluna {column_name} já existe")

def migrate_payment_table(cursor):
    """Adiciona campos Meta Pixel à tabela payments"""
    print("🔧 Migrando tabela 'payments'...")
    
    # Campos para adicionar
    new_columns = [
        ('meta_purchase_sent', 'BOOLEAN DEFAULT 0'),
        ('meta_purchase_sent_at', 'DATETIME'),
        ('meta_event_id', 'VARCHAR(100)'),
        ('meta_viewcontent_sent', 'BOOLEAN DEFAULT 0'),
        ('meta_viewcontent_sent_at', 'DATETIME'),
        ('utm_source', 'VARCHAR(50)'),
        ('utm_campaign', 'VARCHAR(100)'),
        ('utm_content', 'VARCHAR(100)'),
        ('utm_medium', 'VARCHAR(50)'),
        ('utm_term', 'VARCHAR(100)'),
        ('fbclid', 'VARCHAR(200)'),
        ('campaign_code', 'VARCHAR(50)')
    ]
    
    for column_name, column_type in new_columns:
        if not check_column_exists(cursor, 'payments', column_name):
            try:
                cursor.execute(f"ALTER TABLE payments ADD COLUMN {column_name} {column_type}")
                print(f"  ✅ Adicionada coluna: {column_name}")
            except Exception as e:
                print(f"  ❌ Erro ao adicionar {column_name}: {e}")
        else:
            print(f"  ⚠️ Coluna {column_name} já existe")

def migrate_bot_user_table(cursor):
    """Adiciona campos Meta Pixel à tabela bot_users"""
    print("🔧 Migrando tabela 'bot_users'...")
    
    # Campos para adicionar
    new_columns = [
        ('meta_pageview_sent', 'BOOLEAN DEFAULT 0'),
        ('meta_pageview_sent_at', 'DATETIME'),
        ('meta_viewcontent_sent', 'BOOLEAN DEFAULT 0'),
        ('meta_viewcontent_sent_at', 'DATETIME'),
        ('utm_source', 'VARCHAR(50)'),
        ('utm_campaign', 'VARCHAR(100)'),
        ('utm_content', 'VARCHAR(100)'),
        ('utm_medium', 'VARCHAR(50)'),
        ('utm_term', 'VARCHAR(100)'),
        ('fbclid', 'VARCHAR(200)'),
        ('campaign_code', 'VARCHAR(50)'),
        ('external_id', 'VARCHAR(100)')  # Para tracking de cliques
    ]
    
    for column_name, column_type in new_columns:
        if not check_column_exists(cursor, 'bot_users', column_name):
            try:
                cursor.execute(f"ALTER TABLE bot_users ADD COLUMN {column_name} {column_type}")
                print(f"  ✅ Adicionada coluna: {column_name}")
            except Exception as e:
                print(f"  ❌ Erro ao adicionar {column_name}: {e}")
        else:
            print(f"  ⚠️ Coluna {column_name} já existe")

def create_indexes(cursor):
    """Cria índices para performance"""
    print("🔧 Criando índices...")
    
    indexes = [
        "CREATE INDEX IF NOT EXISTS idx_bots_meta_tracking ON bots(meta_tracking_enabled)",
        "CREATE INDEX IF NOT EXISTS idx_payments_meta_sent ON payments(meta_purchase_sent)",
        "CREATE INDEX IF NOT EXISTS idx_payments_meta_event_id ON payments(meta_event_id)",
        "CREATE INDEX IF NOT EXISTS idx_bot_users_meta_pageview ON bot_users(meta_pageview_sent)",
        "CREATE INDEX IF NOT EXISTS idx_bot_users_meta_viewcontent ON bot_users(meta_viewcontent_sent)",
        "CREATE INDEX IF NOT EXISTS idx_payments_utm_source ON payments(utm_source)",
        "CREATE INDEX IF NOT EXISTS idx_bot_users_utm_source ON bot_users(utm_source)"
    ]
    
    for index_sql in indexes:
        try:
            cursor.execute(index_sql)
            print(f"  ✅ Índice criado")
        except Exception as e:
            print(f"  ❌ Erro ao criar índice: {e}")

def main():
    """Executa a migração completa"""
    print("🚀 INICIANDO MIGRAÇÃO META PIXEL")
    print("=" * 50)
    
    # Backup do banco
    backup_path = backup_database()
    
    db_path = get_db_path()
    if not os.path.exists(db_path):
        print(f"❌ Banco de dados não encontrado: {db_path}")
        return False
    
    try:
        # Conectar ao banco
        conn = sqlite3.connect(db_path)
        cursor = conn.cursor()
        
        print(f"📊 Banco conectado: {db_path}")
        
        # Executar migrações
        migrate_bot_table(cursor)
        migrate_payment_table(cursor)
        migrate_bot_user_table(cursor)
        create_indexes(cursor)
        
        # Commit das alterações
        conn.commit()
        print("\n✅ MIGRAÇÃO CONCLUÍDA COM SUCESSO!")
        
        # Verificar estrutura final
        print("\n📋 VERIFICAÇÃO FINAL:")
        cursor.execute("PRAGMA table_info(bots)")
        bot_columns = [row[1] for row in cursor.fetchall()]
        meta_bot_columns = [col for col in bot_columns if col.startswith('meta_')]
        print(f"  Bot Meta columns: {len(meta_bot_columns)}")
        
        cursor.execute("PRAGMA table_info(payments)")
        payment_columns = [row[1] for row in cursor.fetchall()]
        meta_payment_columns = [col for col in payment_columns if col.startswith('meta_')]
        print(f"  Payment Meta columns: {len(meta_payment_columns)}")
        
        cursor.execute("PRAGMA table_info(bot_users)")
        bot_user_columns = [row[1] for row in cursor.fetchall()]
        meta_bot_user_columns = [col for col in bot_user_columns if col.startswith('meta_')]
        print(f"  BotUser Meta columns: {len(meta_bot_user_columns)}")
        
        conn.close()
        
        print(f"\n💾 Backup disponível em: {backup_path}")
        print("🎯 Próximo passo: Implementar utils/meta_pixel.py")
        
        return True
        
    except Exception as e:
        print(f"❌ ERRO NA MIGRAÇÃO: {e}")
        if backup_path and os.path.exists(backup_path):
            print(f"🔄 Restaure o backup: {backup_path}")
        return False

if __name__ == "__main__":
    success = main()
    sys.exit(0 if success else 1)
