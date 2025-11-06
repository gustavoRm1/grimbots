"""
🔄 REPROCESSAR VENDAS SYNCPAY PENDENTES

Este script:
1. Busca todos os pagamentos PENDING do SyncPay (últimas 7 dias)
2. Para cada payment, tenta reprocessar o webhook manualmente
3. Simula o webhook recebido da SyncPay
4. Atualiza o status no banco de dados

IMPORTANTE: Este script NÃO consulta a API SyncPay (endpoint não documentado).
Ele apenas reprocessa os webhooks que podem ter falhado.

Para vendas que realmente foram pagas mas não chegaram no webhook,
é necessário verificar manualmente no painel SyncPay e atualizar.

Autor: QI 600 + QI 602
"""

from app import app, db
from models import Payment, Gateway, get_brazil_time
from gateway_factory import GatewayFactory
from datetime import timedelta
import logging
import json

logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)

def simulate_syncpay_webhook(payment: Payment, gateway, status="PAID_OUT") -> dict:
    """
    Simula webhook SyncPay para reprocessamento
    
    Estrutura do webhook SyncPay:
    {
        "data": {
            "id": "transaction_id",
            "status": "PAID_OUT",
            "amount": 33.8,
            "externalreference": "payment_id"
        }
    }
    
    Args:
        payment: Payment object
        gateway: Gateway instance
        status: Status a simular ("PAID_OUT", "CANCELLED", etc)
    """
    # Construir webhook simulado
    webhook_data = {
        "data": {
            "id": payment.gateway_transaction_id or payment.payment_id,
            "status": status,  # Status a simular
            "amount": float(payment.amount),
            "externalreference": payment.payment_id
        }
    }
    
    return webhook_data

def reprocess_syncpay_payment(payment: Payment, gateway, assume_paid=False) -> bool:
    """
    Reprocessa um pagamento SyncPay
    
    Returns:
        True se processado com sucesso, False caso contrário
    """
    try:
        logger.info(f"\n{'='*80}")
        logger.info(f"🔄 REPROCESSANDO: {payment.payment_id}")
        logger.info(f"   Bot ID: {payment.bot_id}")
        logger.info(f"   Amount: R$ {payment.amount:.2f}")
        logger.info(f"   Gateway Transaction ID: {payment.gateway_transaction_id}")
        logger.info(f"   Status atual: {payment.status}")
        logger.info(f"   Criado em: {payment.created_at}")
        
        # ⚠️ AVISO: Este script NÃO consulta a API SyncPay
        # Ele apenas simula o webhook. Se assume_paid=False, não faz nada.
        if not assume_paid:
            logger.warning(f"⚠️ Script em modo seguro: não assumindo pagamento")
            logger.warning(f"   Para marcar como pago, execute com --assume-paid")
            logger.warning(f"   OU verifique manualmente no painel SyncPay")
            return False
        
        logger.warning(f"⚠️ ATENÇÃO: Assumindo que o pagamento está PAID_OUT")
        logger.warning(f"   Verifique no painel SyncPay antes de continuar!")
        
        # Simular webhook como PAID_OUT
        webhook_data = simulate_syncpay_webhook(payment, gateway, status="PAID_OUT")
        
        # Processar webhook usando o gateway
        result = gateway.process_webhook(webhook_data)
        
        if not result:
            logger.error(f"❌ Falha ao processar webhook para {payment.payment_id}")
            return False
        
        logger.info(f"✅ Webhook processado:")
        logger.info(f"   Status: {result.get('status')}")
        logger.info(f"   Amount: R$ {result.get('amount', 0):.2f}")
        logger.info(f"   Gateway Transaction ID: {result.get('gateway_transaction_id')}")
        
        # Buscar payment novamente (pode ter mudado)
        payment = Payment.query.filter_by(id=payment.id).first()
        if not payment:
            logger.error(f"❌ Payment não encontrado após processamento")
            return False
        
        # Verificar se status mudou
        new_status = result.get('status')
        old_status = payment.status
        
        if new_status == 'paid' and old_status == 'pending':
            logger.info(f"✅ Status atualizado: {old_status} → {new_status}")
            
            # Atualizar status
            payment.status = new_status
            
            # Atualizar gateway_transaction_id se necessário
            if result.get('gateway_transaction_id') and not payment.gateway_transaction_id:
                payment.gateway_transaction_id = result.get('gateway_transaction_id')
            
            # Commit
            db.session.commit()
            
            # ✅ IMPORTANTE: Enviar entregável e atualizar estatísticas
            # Isso é feito automaticamente pelo webhook handler, mas vamos simular
            logger.info(f"📦 Enviando entregável...")
            
            try:
                from bot_manager import BotManager
                bot_manager = BotManager()
                
                # Buscar bot
                from models import Bot
                bot = Bot.query.filter_by(id=payment.bot_id).first()
                if bot:
                    # Enviar entregável
                    bot_config = bot_manager.active_bots.get(payment.bot_id, {}).get('config', {})
                    if bot_config:
                        token = bot_manager.active_bots[payment.bot_id]['token']
                        chat_id = int(payment.customer_user_id) if payment.customer_user_id else None
                        
                        if chat_id:
                            # Enviar mensagem de confirmação
                            try:
                                import telegram
                                bot_telegram = telegram.Bot(token=token)
                                
                                delivery_message = bot_config.get('delivery_message', '✅ Pagamento confirmado! Seu acesso foi liberado.')
                                
                                bot_telegram.send_message(
                                    chat_id=chat_id,
                                    text=delivery_message,
                                    parse_mode='HTML'
                                )
                                
                                logger.info(f"✅ Entregável enviado para chat {chat_id}")
                            except Exception as e:
                                logger.warning(f"⚠️ Erro ao enviar entregável: {e}")
                    else:
                        logger.warning(f"⚠️ Bot {payment.bot_id} não está ativo, não é possível enviar entregável")
                else:
                    logger.warning(f"⚠️ Bot {payment.bot_id} não encontrado")
                    
            except Exception as e:
                logger.error(f"❌ Erro ao enviar entregável: {e}")
                import traceback
                logger.error(traceback.format_exc())
            
            return True
        elif new_status == old_status:
            logger.info(f"ℹ️ Status não mudou: {old_status}")
            return False
        else:
            logger.warning(f"⚠️ Status diferente do esperado: {old_status} → {new_status}")
            return False
            
    except Exception as e:
        logger.error(f"❌ Erro ao reprocessar {payment.payment_id}: {e}")
        import traceback
        logger.error(traceback.format_exc())
        db.session.rollback()
        return False

def main(assume_paid=False):
    """
    Função principal
    
    Args:
        assume_paid: Se True, assume que todos os pagamentos estão pagos e atualiza
                     Se False, apenas lista os pagamentos pending (modo seguro)
    """
    with app.app_context():
        print("\n" + "=" * 80)
        print("🔄 REPROCESSAR VENDAS SYNCPAY PENDENTES")
        print("=" * 80)
        
        # Buscar pagamentos pending do SyncPay (últimas 7 dias)
        now_brazil = get_brazil_time()
        seven_days_ago = now_brazil - timedelta(days=7)
        
        print(f"\n📅 Buscando pagamentos pending do SyncPay desde {seven_days_ago.strftime('%d/%m/%Y %H:%M')}")
        
        pending_payments = Payment.query.filter(
            Payment.gateway_type == 'syncpay',
            Payment.status == 'pending',
            Payment.created_at >= seven_days_ago
        ).order_by(Payment.created_at.desc()).all()
        
        print(f"\n📊 Encontrados {len(pending_payments)} pagamentos pending do SyncPay")
        
        if not pending_payments:
            print("\n✅ Nenhum pagamento pending encontrado!")
            return
        
        # ⚠️ MODO SEGURO: Apenas listar se não assumir pagamento
        if not assume_paid:
            print("\n" + "=" * 80)
            print("⚠️ MODO SEGURO ATIVADO")
            print("=" * 80)
            print("Este script está em modo seguro e NÃO atualizará nenhum pagamento.")
            print("Ele apenas lista os pagamentos pending para você verificar.")
            print("\nPara atualizar pagamentos, você precisa:")
            print("1. Verificar manualmente no painel SyncPay quais estão pagos")
            print("2. Executar este script com --assume-paid (cuidado!)")
            print("3. OU atualizar manualmente no banco de dados")
            print("\n" + "=" * 80)
            print("📋 LISTA DE PAGAMENTOS PENDING:")
            print("=" * 80)
            
            for i, payment in enumerate(pending_payments, 1):
                bot = payment.bot if hasattr(payment, 'bot') else None
                print(f"\n{i}. Payment ID: {payment.payment_id}")
                print(f"   Bot ID: {payment.bot_id}")
                print(f"   Amount: R$ {payment.amount:.2f}")
                print(f"   Gateway Transaction ID: {payment.gateway_transaction_id or 'N/A'}")
                print(f"   Criado em: {payment.created_at}")
                if bot:
                    print(f"   Bot: {bot.name or 'N/A'}")
            
            print("\n" + "=" * 80)
            print(f"✅ Total: {len(pending_payments)} pagamento(s) pending")
            print("=" * 80)
            return
        
        # Agrupar por gateway (user_id)
        payments_by_gateway = {}
        for payment in pending_payments:
            bot = payment.bot if hasattr(payment, 'bot') else None
            if bot:
                user_id = bot.user_id
                if user_id not in payments_by_gateway:
                    payments_by_gateway[user_id] = []
                payments_by_gateway[user_id].append(payment)
        
        print(f"\n📦 Pagamentos agrupados por {len(payments_by_gateway)} gateway(s)")
        
        total_processed = 0
        total_updated = 0
        total_errors = 0
        
        # Processar cada gateway
        for user_id, payments in payments_by_gateway.items():
            print(f"\n{'='*80}")
            print(f"🔧 Processando gateway do usuário {user_id} ({len(payments)} pagamentos)")
            print(f"{'='*80}")
            
            # Buscar gateway SyncPay do usuário
            gateway_config = Gateway.query.filter_by(
                user_id=user_id,
                gateway_type='syncpay',
                is_active=True
            ).first()
            
            if not gateway_config:
                logger.warning(f"⚠️ Gateway SyncPay não encontrado para usuário {user_id}")
                continue
            
            # Criar instância do gateway
            try:
                gateway = GatewayFactory.create_gateway(
                    gateway_type='syncpay',
                    credentials=gateway_config.credentials
                )
                
                if not gateway:
                    logger.error(f"❌ Erro ao criar gateway SyncPay para usuário {user_id}")
                    continue
                
                logger.info(f"✅ Gateway SyncPay criado com sucesso")
                
            except Exception as e:
                logger.error(f"❌ Erro ao criar gateway: {e}")
                continue
            
            # Processar cada payment
            for payment in payments:
                total_processed += 1
                
                if reprocess_syncpay_payment(payment, gateway, assume_paid=assume_paid):
                    total_updated += 1
                else:
                    total_errors += 1
        
        # Resumo final
        print("\n" + "=" * 80)
        print("📊 RESUMO FINAL")
        print("=" * 80)
        print(f"✅ Total processado: {total_processed}")
        print(f"✅ Total atualizado: {total_updated}")
        print(f"❌ Total com erro: {total_errors}")
        print(f"📈 Taxa de sucesso: {(total_updated/total_processed*100):.1f}%" if total_processed > 0 else "N/A")
        print("=" * 80)
        
        if total_updated > 0:
            print(f"\n✅ {total_updated} venda(s) foram atualizadas com sucesso!")
        else:
            print(f"\n⚠️ Nenhuma venda foi atualizada.")
            print(f"   Isso pode significar que:")
            print(f"   1. Os pagamentos ainda estão realmente pendentes")
            print(f"   2. Os webhooks não chegaram (verificar painel SyncPay)")
            print(f"   3. É necessário verificar manualmente no painel SyncPay")

if __name__ == '__main__':
    import sys
    
    # Verificar argumentos
    assume_paid = '--assume-paid' in sys.argv or '-a' in sys.argv
    
    if assume_paid:
        print("\n" + "⚠️" * 40)
        print("⚠️ ATENÇÃO: MODO ASSUME-PAID ATIVADO")
        print("⚠️" * 40)
        print("\nEste script irá marcar TODOS os pagamentos pending como PAID_OUT")
        print("Certifique-se de que você verificou no painel SyncPay antes!")
        print("\nDeseja continuar? (s/N): ", end='')
        
        try:
            response = input().strip().lower()
            if response != 's' and response != 'sim':
                print("\n❌ Operação cancelada pelo usuário")
                sys.exit(0)
        except KeyboardInterrupt:
            print("\n\n❌ Operação cancelada pelo usuário")
            sys.exit(0)
    
    main(assume_paid=assume_paid)

