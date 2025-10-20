#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""
==============================================================================
MIGRAÇÃO: META PIXEL DE BOTS PARA REDIRECT POOLS
==============================================================================

OBJETIVO:
- Mover campos Meta Pixel de 'bots' para 'redirect_pools'
- Migrar configurações existentes
- Garantir zero downtime

AUTOR: Senior Engineer QI 300
DATA: 2025-10-20
==============================================================================
"""

import sys
import sqlite3
from datetime import datetime
import os

def print_header(message):
    print(f"\n{'='*70}")
    print(f"  {message}")
    print(f"{'='*70}\n")

def print_step(step, message):
    print(f"[{step}] {message}")

def print_success(message):
    print(f"✅ {message}")

def print_error(message):
    print(f"❌ {message}")

def print_warning(message):
    print(f"⚠️  {message}")

def create_backup(db_path):
    """Cria backup do banco antes da migração"""
    timestamp = datetime.now().strftime('%Y%m%d_%H%M%S')
    backup_path = f"{db_path}.backup_meta_pool_{timestamp}"
    
    try:
        import shutil
        shutil.copy2(db_path, backup_path)
        print_success(f"Backup criado: {backup_path}")
        return backup_path
    except Exception as e:
        print_error(f"Erro ao criar backup: {e}")
        return None

def column_exists(cursor, table, column):
    """Verifica se coluna existe na tabela"""
    cursor.execute(f"PRAGMA table_info({table})")
    columns = [row[1] for row in cursor.fetchall()]
    return column in columns

def migrate_database(db_path):
    """Executa migração completa"""
    
    print_header("🚀 INICIANDO MIGRAÇÃO: META PIXEL PARA POOLS")
    
    if not os.path.exists(db_path):
        print_error(f"Banco de dados não encontrado: {db_path}")
        return False
    
    # Criar backup
    print_step(1, "Criando backup de segurança...")
    backup_path = create_backup(db_path)
    if not backup_path:
        print_error("Falha ao criar backup. Abortando migração.")
        return False
    
    conn = None
    try:
        # Conectar ao banco
        print_step(2, f"Conectando ao banco: {db_path}")
        conn = sqlite3.connect(db_path)
        cursor = conn.cursor()
        print_success(f"Banco conectado: {db_path}")
        
        # ====================================================================
        # FASE 1: ADICIONAR COLUNAS EM REDIRECT_POOLS
        # ====================================================================
        print_step(3, "Adicionando campos Meta Pixel em 'redirect_pools'...")
        
        meta_columns = [
            ("meta_pixel_id", "VARCHAR(50)"),
            ("meta_access_token", "VARCHAR(255)"),
            ("meta_tracking_enabled", "BOOLEAN DEFAULT 0"),
            ("meta_test_event_code", "VARCHAR(100)"),
            ("meta_events_pageview", "BOOLEAN DEFAULT 1"),
            ("meta_events_viewcontent", "BOOLEAN DEFAULT 1"),
            ("meta_events_purchase", "BOOLEAN DEFAULT 1"),
            ("meta_cloaker_enabled", "BOOLEAN DEFAULT 0"),
            ("meta_cloaker_param_name", "VARCHAR(20) DEFAULT 'grim'"),
            ("meta_cloaker_param_value", "VARCHAR(50)"),
        ]
        
        for col_name, col_type in meta_columns:
            if not column_exists(cursor, "redirect_pools", col_name):
                try:
                    cursor.execute(f"ALTER TABLE redirect_pools ADD COLUMN {col_name} {col_type}")
                    print_success(f"  ✅ Adicionada coluna: {col_name}")
                except sqlite3.OperationalError as e:
                    if "duplicate column" in str(e).lower():
                        print_warning(f"  ⚠️  Coluna já existe: {col_name}")
                    else:
                        raise
            else:
                print_warning(f"  ⚠️  Coluna já existe: {col_name}")
        
        conn.commit()
        print_success("Campos Meta Pixel adicionados em 'redirect_pools'")
        
        # ====================================================================
        # FASE 2: MIGRAR CONFIGURAÇÕES EXISTENTES DE BOTS PARA POOLS
        # ====================================================================
        print_step(4, "Migrando configurações existentes de 'bots' para 'redirect_pools'...")
        
        # Verificar se colunas existem em bots
        if column_exists(cursor, "bots", "meta_pixel_id"):
            # Buscar bots com Meta Pixel configurado
            cursor.execute("""
                SELECT id, meta_pixel_id, meta_access_token, meta_tracking_enabled,
                       meta_test_event_code, meta_events_pageview, meta_events_viewcontent,
                       meta_events_purchase, meta_cloaker_enabled, meta_cloaker_param_name,
                       meta_cloaker_param_value
                FROM bots
                WHERE meta_tracking_enabled = 1
            """)
            
            configured_bots = cursor.fetchall()
            
            if configured_bots:
                print_warning(f"  ⚠️  Encontrados {len(configured_bots)} bots com Meta Pixel configurado")
                
                # Para cada bot com pixel configurado, migrar para o pool associado
                for bot_row in configured_bots:
                    bot_id = bot_row[0]
                    
                    # Buscar pool associado ao bot
                    cursor.execute("""
                        SELECT pool_id 
                        FROM pool_bots 
                        WHERE bot_id = ? 
                        LIMIT 1
                    """, (bot_id,))
                    
                    pool_result = cursor.fetchone()
                    
                    if pool_result:
                        pool_id = pool_result[0]
                        
                        # Migrar configuração para o pool
                        cursor.execute("""
                            UPDATE redirect_pools
                            SET meta_pixel_id = ?,
                                meta_access_token = ?,
                                meta_tracking_enabled = ?,
                                meta_test_event_code = ?,
                                meta_events_pageview = ?,
                                meta_events_viewcontent = ?,
                                meta_events_purchase = ?,
                                meta_cloaker_enabled = ?,
                                meta_cloaker_param_name = ?,
                                meta_cloaker_param_value = ?
                            WHERE id = ?
                        """, (*bot_row[1:], pool_id))
                        
                        print_success(f"  ✅ Bot {bot_id} → Pool {pool_id} migrado")
                    else:
                        print_warning(f"  ⚠️  Bot {bot_id} não está associado a nenhum pool")
                
                conn.commit()
                print_success("Configurações migradas com sucesso")
            else:
                print_warning("  ⚠️  Nenhum bot com Meta Pixel configurado")
        else:
            print_warning("  ⚠️  Colunas Meta Pixel não existem em 'bots' (já foram removidas?)")
        
        # ====================================================================
        # FASE 3: REMOVER COLUNAS DE BOTS
        # ====================================================================
        print_step(5, "Removendo campos Meta Pixel de 'bots'...")
        
        # SQLite não suporta DROP COLUMN diretamente
        # Precisamos recriar a tabela sem as colunas
        
        if column_exists(cursor, "bots", "meta_pixel_id"):
            print_warning("  ⚠️  SQLite não suporta DROP COLUMN diretamente")
            print_warning("  ⚠️  As colunas antigas em 'bots' permanecerão (serão ignoradas)")
            print_warning("  ⚠️  Isso não afeta o funcionamento, apenas ocupa espaço")
            
            # Podemos comentar essas colunas no models.py
            # Elas ficarão no banco mas não serão usadas
        
        # ====================================================================
        # FASE 4: CRIAR ÍNDICES PARA PERFORMANCE
        # ====================================================================
        print_step(6, "Criando índices para otimização...")
        
        indexes = [
            ("idx_pools_meta_tracking", "redirect_pools", "meta_tracking_enabled"),
            ("idx_pools_meta_pixel", "redirect_pools", "meta_pixel_id"),
        ]
        
        for idx_name, table, column in indexes:
            try:
                cursor.execute(f"CREATE INDEX IF NOT EXISTS {idx_name} ON {table}({column})")
                print_success(f"  ✅ Índice criado: {idx_name}")
            except sqlite3.OperationalError as e:
                if "already exists" in str(e).lower():
                    print_warning(f"  ⚠️  Índice já existe: {idx_name}")
                else:
                    raise
        
        conn.commit()
        
        # ====================================================================
        # FASE 5: VALIDAÇÃO
        # ====================================================================
        print_step(7, "Validando migração...")
        
        # Verificar se colunas foram criadas
        cursor.execute("PRAGMA table_info(redirect_pools)")
        pool_columns = [row[1] for row in cursor.fetchall()]
        
        required_columns = ["meta_pixel_id", "meta_access_token", "meta_tracking_enabled"]
        missing_columns = [col for col in required_columns if col not in pool_columns]
        
        if missing_columns:
            print_error(f"Colunas faltando em redirect_pools: {missing_columns}")
            return False
        
        print_success("Validação concluída - todas as colunas foram criadas")
        
        # Contar pools com Meta Pixel configurado
        cursor.execute("SELECT COUNT(*) FROM redirect_pools WHERE meta_tracking_enabled = 1")
        pool_count = cursor.fetchone()[0]
        
        print_success(f"Pools com Meta Pixel configurado: {pool_count}")
        
        print_header("✅ MIGRAÇÃO CONCLUÍDA COM SUCESSO!")
        
        print("\n📋 RESUMO DA MIGRAÇÃO:")
        print(f"  • Backup criado: {backup_path}")
        print(f"  • Colunas adicionadas em redirect_pools: {len(meta_columns)}")
        print(f"  • Pools com Meta Pixel: {pool_count}")
        print(f"  • Índices criados: {len(indexes)}")
        
        print("\n🎯 PRÓXIMOS PASSOS:")
        print("  1. Atualizar código da aplicação (models.py, app.py, bot_manager.py)")
        print("  2. Reiniciar aplicação")
        print("  3. Testar configuração de Meta Pixel nos pools")
        print("  4. Verificar eventos no Meta Events Manager")
        
        print("\n⚠️  IMPORTANTE:")
        print("  • As colunas antigas em 'bots' não foram removidas (limitação SQLite)")
        print("  • Elas permanecerão no banco mas serão IGNORADAS pelo código")
        print("  • Isso não afeta o funcionamento da aplicação")
        
        return True
        
    except Exception as e:
        print_error(f"Erro durante migração: {e}")
        import traceback
        traceback.print_exc()
        
        if conn:
            conn.rollback()
            print_warning("Rollback executado")
        
        print(f"\n🔄 Para restaurar o backup:")
        print(f"   cp {backup_path} {db_path}")
        
        return False
        
    finally:
        if conn:
            conn.close()
            print_success("Conexão fechada")

if __name__ == "__main__":
    # Caminho do banco de dados
    DB_PATH = "instance/saas_bot_manager.db"
    
    if len(sys.argv) > 1:
        DB_PATH = sys.argv[1]
    
    print(f"\n📊 Banco de dados: {DB_PATH}")
    
    # Confirmar migração
    print("\n⚠️  ATENÇÃO: Esta migração vai:")
    print("  1. Criar backup do banco atual")
    print("  2. Adicionar campos Meta Pixel em 'redirect_pools'")
    print("  3. Migrar configurações de 'bots' para 'redirect_pools'")
    print("  4. Colunas antigas em 'bots' permanecerão (serão ignoradas)")
    
    confirm = input("\n🤔 Deseja continuar? (sim/não): ").strip().lower()
    
    if confirm not in ['sim', 's', 'yes', 'y']:
        print("\n❌ Migração cancelada pelo usuário")
        sys.exit(1)
    
    # Executar migração
    success = migrate_database(DB_PATH)
    
    sys.exit(0 if success else 1)

