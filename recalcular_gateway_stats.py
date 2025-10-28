"""
Recalcular estatísticas de TODOS os gateways baseado em pagamentos reais
"""

from app import app, db
from models import Payment, Gateway

def recalcular_gateway_stats():
    with app.app_context():
        print("=" * 80)
        print("🔄 RECALCULANDO GATEWAY STATS - TODOS OS GATEWAYS")
        print("=" * 80)
        
        # Pegar TODOS os gateways
        gateways = Gateway.query.all()
        
        if not gateways:
            print("❌ Nenhum gateway encontrado")
            return
        
        for gateway in gateways:
            print(f"\n{'=' * 80}")
            print(f"📊 GATEWAY: {gateway.name} ({gateway.gateway_type})")
            print(f"{'=' * 80}")
            print(f"STATS ANTIGOS:")
            print(f"   Total: {gateway.total_transactions}")
            print(f"   Successful: {gateway.successful_transactions}")
            print(f"   Failed: {gateway.failed_transactions}")
            
            # Recalcular baseado em pagamentos REAIS
            all_payments = Payment.query.filter_by(gateway_type=gateway.gateway_type).count()
            paid_payments = Payment.query.filter_by(gateway_type=gateway.gateway_type, status='paid').count()
            pending_payments = Payment.query.filter_by(gateway_type=gateway.gateway_type, status='pending').count()
            failed_payments = Payment.query.filter_by(gateway_type=gateway.gateway_type, status='failed').count()
            
            print(f"\n📦 PAGAMENTOS REAIS NO BANCO:")
            print(f"   Total: {all_payments}")
            print(f"   Paid: {paid_payments}")
            print(f"   Pending: {pending_payments}")
            print(f"   Failed: {failed_payments}")
            
            # Atualizar stats
            gateway.total_transactions = all_payments
            gateway.successful_transactions = paid_payments
            gateway.failed_transactions = failed_payments
            
            # Taxa de sucesso
            if all_payments > 0:
                success_rate = (paid_payments / all_payments * 100)
            else:
                success_rate = 0
            
            print(f"\n✅ STATS ATUALIZADOS:")
            print(f"   Total Transactions: {gateway.total_transactions}")
            print(f"   Successful: {gateway.successful_transactions}")
            print(f"   Failed: {gateway.failed_transactions}")
            print(f"   Taxa de Sucesso: {success_rate:.2f}%")
        
        db.session.commit()
        
        print("\n" + "=" * 80)
        print("✅ TODOS OS GATEWAYS RECALCULADOS!")
        print("=" * 80)

if __name__ == '__main__':
    recalcular_gateway_stats()

