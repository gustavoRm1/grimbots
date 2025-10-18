#!/usr/bin/env python3
"""
Script para remover todos os registros de HooPay do banco de dados
Executar: python remove_hoopay_from_db.py
"""

import os
import sys
from datetime import datetime

# Configurar path
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from app import app, db
from models import Gateway, Payment, Bot

def remove_hoopay_gateways():
    """Remove todos os gateways HooPay do banco"""
    print("=" * 60)
    print("🗑️  REMOVENDO HOOPAY DO BANCO DE DADOS")
    print("=" * 60)
    print()
    
    with app.app_context():
        try:
            # 1. Buscar todos os gateways HooPay
            hoopay_gateways = Gateway.query.filter_by(gateway_type='hoopay').all()
            
            if not hoopay_gateways:
                print("✅ Nenhum gateway HooPay encontrado no banco!")
                return True
            
            print(f"📊 Encontrados {len(hoopay_gateways)} gateway(s) HooPay")
            print()
            
            # 2. Para cada gateway HooPay
            for gateway in hoopay_gateways:
                print(f"🔍 Gateway ID {gateway.id} - User ID {gateway.user_id}")
                
                # 2.1. Verificar pagamentos associados
                payments = Payment.query.filter_by(gateway_type='hoopay').filter(
                    (Payment.user_id == gateway.user_id) | (Payment.gateway_type == 'hoopay')
                ).all()
                
                if payments:
                    print(f"   ⚠️  Encontrados {len(payments)} pagamento(s) HooPay")
                    print(f"   📝 Atualizando status dos pagamentos...")
                    
                    for payment in payments:
                        # Marcar como cancelado se ainda estiver pendente
                        if payment.status == 'pending':
                            payment.status = 'cancelled'
                            payment.updated_at = datetime.utcnow()
                    
                    print(f"   ✅ {len(payments)} pagamento(s) atualizados")
                
                # 2.2. Verificar bots usando este gateway
                bots = Bot.query.filter_by(gateway_id=gateway.id).all()
                
                if bots:
                    print(f"   ⚠️  Encontrados {len(bots)} bot(s) usando este gateway")
                    print(f"   📝 Removendo associação dos bots...")
                    
                    for bot in bots:
                        bot.gateway_id = None
                        bot.updated_at = datetime.utcnow()
                    
                    print(f"   ✅ {len(bots)} bot(s) desassociados")
                
                # 2.3. Remover o gateway
                print(f"   🗑️  Removendo gateway...")
                db.session.delete(gateway)
                print(f"   ✅ Gateway removido")
                print()
            
            # 3. Commit das mudanças
            db.session.commit()
            
            print("=" * 60)
            print("✅ HOOPAY REMOVIDO COM SUCESSO!")
            print("=" * 60)
            print()
            print(f"📊 Resumo:")
            print(f"   • {len(hoopay_gateways)} gateway(s) removido(s)")
            print(f"   • Pagamentos HooPay marcados como cancelados")
            print(f"   • Bots desassociados do gateway HooPay")
            print()
            
            return True
            
        except Exception as e:
            db.session.rollback()
            print()
            print("=" * 60)
            print("❌ ERRO AO REMOVER HOOPAY!")
            print("=" * 60)
            print(f"Erro: {e}")
            print()
            import traceback
            traceback.print_exc()
            return False

if __name__ == '__main__':
    success = remove_hoopay_gateways()
    sys.exit(0 if success else 1)

