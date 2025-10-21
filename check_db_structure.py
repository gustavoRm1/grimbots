#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Script para verificar estrutura do banco de dados
"""

import sqlite3
import os

def check_db_structure():
    """Verifica estrutura do banco de dados"""
    
    db_path = "instance/saas_bot_manager.db"
    
    if not os.path.exists(db_path):
        print(f"BANCO NAO ENCONTRADO: {db_path}")
        return
    
    try:
        conn = sqlite3.connect(db_path)
        cursor = conn.cursor()
        
        print("ESTRUTURA DO BANCO DE DADOS:")
        print("=" * 60)
        
        # Listar todas as tabelas
        cursor.execute("SELECT name FROM sqlite_master WHERE type='table';")
        tables = cursor.fetchall()
        
        for table in tables:
            table_name = table[0]
            print(f"\nTABELA: {table_name}")
            print("-" * 40)
            
            # Listar colunas da tabela
            cursor.execute(f"PRAGMA table_info({table_name});")
            columns = cursor.fetchall()
            
            for col in columns:
                col_id, col_name, col_type, not_null, default_val, pk = col
                print(f"  {col_name:<25} | {col_type:<15} | {'NOT NULL' if not_null else 'NULL':<8} | {'PK' if pk else ''}")
        
        conn.close()
        
    except Exception as e:
        print(f"ERRO ao acessar banco: {e}")

if __name__ == "__main__":
    check_db_structure()
