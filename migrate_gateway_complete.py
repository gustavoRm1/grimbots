"""
Migration: Complete Gateway Update
==================================
1. Adiciona colunas faltantes na tabela gateways
2. Corrige estatísticas baseado em pagamentos existentes

Execução: python migrate_gateway_complete.py
"""

import sys
from app import app, db
from models import Gateway, Payment
from sqlalchemy import func, text

def migrate_gateway_schema():
    """Adiciona colunas faltantes na tabela gateways"""
    
    with app.app_context():
        print("=" * 80)
        print("ETAPA 1: Atualizando Schema do Gateway")
        print("=" * 80)
        print()
        
        # Verificar e adicionar colunas faltantes
        columns_to_add = [
            ("product_hash", "VARCHAR(1000)"),
            ("offer_hash", "VARCHAR(1000)"),
            ("store_id", "VARCHAR(50)"),
            ("organization_id", "VARCHAR(1000)"),
            ("split_user_id", "VARCHAR(1000)"),
            ("split_percentage", "FLOAT DEFAULT 2.0"),
        ]
        
        for column_name, column_type in columns_to_add:
            try:
                # Tentar adicionar a coluna
                db.session.execute(text(f"ALTER TABLE gateways ADD COLUMN {column_name} {column_type}"))
                db.session.commit()
                print(f"[OK] Coluna '{column_name}' adicionada com sucesso")
            except Exception as e:
                db.session.rollback()
                if "duplicate column name" in str(e).lower() or "already exists" in str(e).lower():
                    print(f"[INFO] Coluna '{column_name}' ja existe, pulando...")
                else:
                    print(f"[AVISO] Erro ao adicionar coluna '{column_name}': {e}")
        
        print()
        print("[SUCESSO] Schema atualizado!")
        print()

def fix_gateway_statistics():
    """Recalcula estatísticas de todos os gateways baseado nos pagamentos existentes"""
    
    with app.app_context():
        print("=" * 80)
        print("ETAPA 2: Corrigindo Estatisticas dos Gateways")
        print("=" * 80)
        print()
        
        # Buscar todos os gateways
        gateways = Gateway.query.all()
        
        if not gateways:
            print("[INFO] Nenhum gateway encontrado no banco de dados.")
            return
        
        print(f"[OK] {len(gateways)} gateway(s) encontrado(s)")
        print()
        
        total_fixed = 0
        
        for gateway in gateways:
            print(f"[INFO] Processando: {gateway.gateway_type} (ID: {gateway.id})")
            print(f"   Usuario: {gateway.owner.email}")
            print(f"   Estatisticas atuais:")
            print(f"     - Total de transacoes: {gateway.total_transactions}")
            print(f"     - Transacoes bem-sucedidas: {gateway.successful_transactions}")
            
            # Contar pagamentos deste gateway através dos bots do usuário
            from models import Bot
            
            # Total de transações (todos os pagamentos com esse gateway_type)
            total_transactions = db.session.query(func.count(Payment.id)).join(
                Bot, Payment.bot_id == Bot.id
            ).filter(
                Payment.gateway_type == gateway.gateway_type,
                Bot.user_id == gateway.user_id
            ).scalar() or 0
            
            # Transações bem-sucedidas (status = 'paid')
            successful_transactions = db.session.query(func.count(Payment.id)).join(
                Bot, Payment.bot_id == Bot.id
            ).filter(
                Payment.gateway_type == gateway.gateway_type,
                Bot.user_id == gateway.user_id,
                Payment.status == 'paid'
            ).scalar() or 0
            
            # Atualizar se houver diferença
            if gateway.total_transactions != total_transactions or gateway.successful_transactions != successful_transactions:
                print(f"   [AVISO] Diferenca detectada!")
                print(f"   Valores corretos:")
                print(f"     - Total de transacoes: {total_transactions}")
                print(f"     - Transacoes bem-sucedidas: {successful_transactions}")
                
                gateway.total_transactions = total_transactions
                gateway.successful_transactions = successful_transactions
                
                total_fixed += 1
                print(f"   [OK] Gateway atualizado!")
            else:
                print(f"   [OK] Estatisticas ja estavam corretas.")
            
            print()
        
        # Commit das alterações
        if total_fixed > 0:
            try:
                db.session.commit()
                print("=" * 80)
                print(f"[SUCESSO] {total_fixed} gateway(s) corrigido(s)!")
                print("=" * 80)
            except Exception as e:
                db.session.rollback()
                print("=" * 80)
                print(f"[ERRO] Erro ao salvar alteracoes: {e}")
                print("=" * 80)
                sys.exit(1)
        else:
            print("=" * 80)
            print("[OK] Todos os gateways ja estavam com estatisticas corretas!")
            print("=" * 80)

if __name__ == '__main__':
    print()
    print("=" * 80)
    print(" " * 20 + "MIGRACAO COMPLETA DE GATEWAY")
    print("=" * 80)
    print()
    
    try:
        # Etapa 1: Atualizar schema
        migrate_gateway_schema()
        
        # Etapa 2: Corrigir estatísticas
        fix_gateway_statistics()
        
        print()
        print("=" * 80)
        print("[SUCESSO] Migracao completa concluida com sucesso!")
        print("=" * 80)
        print()
    except Exception as e:
        print()
        print(f"[ERRO CRITICO] {e}")
        print()
        import traceback
        traceback.print_exc()
        sys.exit(1)

