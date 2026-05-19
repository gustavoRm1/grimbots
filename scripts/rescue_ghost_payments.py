import sys
import os
import json
from datetime import datetime, timedelta

# Adicionar raiz ao path para encontrar internal_logic
sys.path.append(os.getcwd())

try:
    from app import app
    from internal_logic.core.models import Payment, WebhookEvent, db
    from internal_logic.services.payment_processor import process_payment_confirmation
except ImportError as e:
    print(f"❌ Erro de importação: {e}")
    print("Certifique-se de executar o script na raiz do projeto.")
    sys.exit(1)

def rescue_payments():
    with app.app_context():
        print("🚀 [RESCUE] Iniciando resgate de pagamentos 'fantasmas' (Paradise & Atomopay)...")
        
        # 1. Buscar pagamentos pendentes criados nas últimas 48h
        since = datetime.utcnow() - timedelta(hours=48)
        ghost_payments = Payment.query.filter(
            Payment.status == 'pending',
            Payment.created_at >= since
        ).all()
        
        print(f"🔍 [RESCUE] Analisando {len(ghost_payments)} pagamentos pendentes.")
        
        rescued_count = 0
        
        # Pegar webhooks recentes
        recent_events = WebhookEvent.query.order_by(WebhookEvent.id.desc()).limit(500).all()
        
        print(f"📊 [RESCUE] {len(recent_events)} webhooks encontrados para análise.")

        for payment in ghost_payments:
            match_found = False
            
            for event in recent_events:
                payload = event.payload
                
                # Identificadores do Webhook
                event_ref = str(payload.get('external_reference') or payload.get('reference') or payload.get('external_id') or '').strip()
                event_tx_id = str(payload.get('transaction_id') or payload.get('id') or '').strip()
                event_amount = float(payload.get('amount') or payload.get('value') or 0)
                event_status = str(payload.get('status', '')).lower()
                
                # Status de sucesso nos gateways
                success_status = ['paid', 'approved', 'confirmed', 'completed', 'sucesso']
                
                if event_status in success_status:
                    # Tentar bater por:
                    # 1. Transaction ID (mais forte)
                    # 2. Reference (se bater com payment_id)
                    # 3. Valor + Proximidade de tempo (se for do mesmo gateway)
                    
                    is_match = False
                    
                    if event_tx_id and (event_tx_id == payment.gateway_transaction_id or event_tx_id == payment.payment_id):
                        is_match = True
                    elif event_ref and (event_ref == payment.payment_id or event_ref == payment.gateway_transaction_id):
                        is_match = True
                    elif event_amount == payment.amount and event.gateway_type == payment.gateway_type:
                        # Bate valor e gateway, e tempo próximo (menos de 10 min de diferença)
                        time_diff = abs((event.received_at - payment.created_at).total_seconds())
                        if time_diff < 600: # 10 minutos
                            is_match = True

                    if is_match:
                        print(f"🎯 [MATCH] Pagamento {payment.id} (R$ {payment.amount}) bate com Webhook {event.id} ({event.gateway_type})")
                        
                        # Atualizar o pagamento
                        payment.status = 'paid'
                        payment.paid_at = event.received_at
                        if event_tx_id:
                            payment.gateway_transaction_id = event_tx_id
                        
                        try:
                            db.session.add(payment)
                            db.session.commit()
                            
                            # Processar confirmação (entrega no Telegram + Stats)
                            from internal_logic.services.payment_processor import process_payment_confirmation
                            process_payment_confirmation(payment, event.gateway_type)
                            
                            print(f"✅ [SUCCESS] Pagamento {payment.id} resgatado com sucesso!")
                            rescued_count += 1
                            match_found = True
                            break
                        except Exception as e:
                            db.session.rollback()
                            print(f"❌ [ERROR] Falha ao processar resgate do pagamento {payment.id}: {e}")
        
        print(f"\n🏁 [FINAL] Resgate concluído. {rescued_count} vendas recuperadas.")
        print("💡 As estatísticas do dashboard agora devem refletir esses valores.")

if __name__ == "__main__":
    rescue_payments()
