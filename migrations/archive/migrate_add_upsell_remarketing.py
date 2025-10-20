#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""
==============================================================================
MIGRAÇÃO: ADICIONAR CAMPOS UPSELL E REMARKETING
==============================================================================

OBJETIVO:
- Adicionar is_upsell e is_remarketing em payments
- Permitir Meta Pixel identificar tipo de venda corretamente

AUTOR: QI 540
DATA: 2025-10-20
==============================================================================
"""

import sys
import sqlite3
from datetime import datetime
import os

def migrate_database(db_path):
    """Adiciona campos de upsell e remarketing"""
    
    print("\n" + "="*70)
    print("🚀 MIGRAÇÃO: UPSELL + REMARKETING")
    print("="*70 + "\n")
    
    if not os.path.exists(db_path):
        print(f"❌ Banco não encontrado: {db_path}")
        return False
    
    conn = None
    try:
        conn = sqlite3.connect(db_path)
        cursor = conn.cursor()
        
        print(f"✅ Conectado: {db_path}")
        
        # Adicionar campos
        fields = [
            ("is_upsell", "BOOLEAN DEFAULT 0"),
            ("upsell_index", "INTEGER"),
            ("is_remarketing", "BOOLEAN DEFAULT 0"),
            ("remarketing_campaign_id", "INTEGER"),
        ]
        
        for field_name, field_type in fields:
            try:
                cursor.execute(f"ALTER TABLE payments ADD COLUMN {field_name} {field_type}")
                print(f"✅ Campo adicionado: {field_name}")
            except sqlite3.OperationalError as e:
                if "duplicate column" in str(e).lower():
                    print(f"⚠️  Campo já existe: {field_name}")
                else:
                    raise
        
        conn.commit()
        
        print("\n" + "="*70)
        print("✅ MIGRAÇÃO CONCLUÍDA!")
        print("="*70)
        
        return True
    
    except Exception as e:
        print(f"❌ Erro: {e}")
        if conn:
            conn.rollback()
        return False
    
    finally:
        if conn:
            conn.close()

if __name__ == "__main__":
    DB_PATH = "instance/saas_bot_manager.db"
    
    if len(sys.argv) > 1:
        DB_PATH = sys.argv[1]
    
    success = migrate_database(DB_PATH)
    sys.exit(0 if success else 1)

