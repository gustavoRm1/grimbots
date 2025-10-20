"""
Migration: Fix Gateway Statistics
=================================
Corrige as estatísticas dos gateways (total_transactions e successful_transactions)
baseado nos pagamentos já existentes no banco de dados.

Execução: python migrate_fix_gateway_stats.py
"""

import sys
from app import app, db
from models import Gateway, Payment
from sqlalchemy import func

def fix_gateway_statistics():
    """Recalcula estatísticas de todos os gateways baseado nos pagamentos existentes"""
    
    with app.app_context():
        print("=" * 80)
        print("MIGRAÇÃO: Corrigir Estatísticas de Gateways")
        print("=" * 80)
        print()
        
        # Buscar todos os gateways
        gateways = Gateway.query.all()
        
        if not gateways:
            print("[ERRO] Nenhum gateway encontrado no banco de dados.")
            return
        
        print(f"[OK] {len(gateways)} gateway(s) encontrado(s)")
        print()
        
        total_fixed = 0
        
        for gateway in gateways:
            print(f"[INFO] Processando gateway: {gateway.gateway_type} (ID: {gateway.id})")
            print(f"   Usuário: {gateway.owner.email}")
            print(f"   Estatísticas atuais:")
            print(f"     - Total de transações: {gateway.total_transactions}")
            print(f"     - Transações bem-sucedidas: {gateway.successful_transactions}")
            
            # Contar pagamentos deste gateway através dos bots do usuário
            # Um pagamento está associado a um gateway através do gateway_type e do user_id do bot
            
            # Total de transações (todos os pagamentos com esse gateway_type)
            total_transactions = db.session.query(func.count(Payment.id)).join(
                Payment.bot
            ).filter(
                Payment.gateway_type == gateway.gateway_type,
                Payment.bot.has(user_id=gateway.user_id)
            ).scalar() or 0
            
            # Transações bem-sucedidas (status = 'paid')
            successful_transactions = db.session.query(func.count(Payment.id)).join(
                Payment.bot
            ).filter(
                Payment.gateway_type == gateway.gateway_type,
                Payment.bot.has(user_id=gateway.user_id),
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
                print(f"   [OK] Estatisticas corretas, nenhuma alteracao necessaria.")
            
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
    print(" " * 20 + "MIGRACAO DE GATEWAYS")
    print("=" * 80)
    print()
    
    try:
        fix_gateway_statistics()
        print()
        print("[SUCESSO] Migracao concluida com sucesso!")
        print()
    except Exception as e:
        print()
        print(f"[ERRO CRITICO] {e}")
        print()
        import traceback
        traceback.print_exc()
        sys.exit(1)

