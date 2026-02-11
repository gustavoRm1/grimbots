"""
Job de Sincronização Periódica - UmbrellaPay

Objetivo:
- Buscar payments PENDING no sistema há > 10 minutos
- Consultar status no gateway UmbrellaPay
- Atualizar se gateway mostrar paid
- Registrar logs detalhados
- Reenviar purchase do meta pixel se necessário

Executado a cada 5 minutos via APScheduler
"""

import logging
from datetime import datetime, timedelta
from typing import List, Dict, Any, Optional

logger = logging.getLogger(__name__)


def sync_umbrellapay_payments():
    """
    Sincroniza pagamentos UmbrellaPay pendentes com o gateway
    
    Busca payments PENDING criados há mais de 10 minutos e consulta
    o status no gateway. Se o gateway retornar 'paid', atualiza o
    sistema e reenvia Meta Pixel Purchase se necessário.
    """
    try:
        from app import app, db
        from models import Payment, Gateway, Bot, get_brazil_time
        from gateway_factory import GatewayFactory
        from app import send_meta_pixel_purchase_event
        
        with app.app_context():
            logger.info("=" * 80)
            logger.info("🔄 [SYNC UMBRELLAPAY] Iniciando sincronização periódica")
            logger.info("=" * 80)
            
            # ✅ Buscar payments PENDING (Entre 10 minutos e 24 horas atrás)
            # FIX: Previne requisições infinitas para PIX antigos (zumbis)
            dez_minutos_atras = get_brazil_time() - timedelta(minutes=10)
            vinte_quatro_horas_atras = get_brazil_time() - timedelta(hours=24)
            
            payments_pendentes = Payment.query.filter(
                Payment.gateway_type == 'umbrellapag',
                Payment.status == 'pending',
                Payment.created_at <= dez_minutos_atras,
                Payment.created_at >= vinte_quatro_horas_atras  # A TESOURA: Ignora PIX mais velhos que 24h
            ).all()
            
            # ✅ DEBOUNCE: Filtrar payments atualizados recentemente (<5 minutos)
            # Evita processar mesmo payment múltiplas vezes se job rodar antes de 5min
            cinco_minutos_atras = get_brazil_time() - timedelta(minutes=5)
            from models import WebhookEvent
            
            payments_para_processar = []
            for payment in payments_pendentes:
                # ✅ Verificar se payment foi atualizado recentemente (debounce)
                # ✅ FALLBACK: Se updated_at não existir, usar paid_at ou created_at
                updated_time = None
                if hasattr(payment, 'updated_at') and payment.updated_at:
                    updated_time = payment.updated_at
                elif payment.paid_at:
                    updated_time = payment.paid_at
                elif payment.created_at:
                    updated_time = payment.created_at
                
                if updated_time and updated_time >= cinco_minutos_atras:
                    logger.debug(f"⏭️ [SYNC UMBRELLAPAY] Pulando {payment.payment_id} - atualizado recentemente ({updated_time})")
                    continue
                
                # ✅ Verificar se existe webhook recente (<5 minutos) antes de consultar API
                try:
                    webhook_recente = WebhookEvent.query.filter(
                        WebhookEvent.gateway_type == 'umbrellapag',
                        WebhookEvent.transaction_id == payment.gateway_transaction_id,
                        WebhookEvent.received_at >= cinco_minutos_atras
                    ).order_by(WebhookEvent.received_at.desc()).first()
                    
                    if webhook_recente:
                        logger.debug(f"⏭️ [SYNC UMBRELLAPAY] Pulando {payment.payment_id} - webhook recente encontrado ({webhook_recente.received_at})")
                        continue
                except Exception as e:
                    logger.warning(f"⚠️ [SYNC UMBRELLAPAY] Erro ao verificar webhook recente para {payment.payment_id}: {e}")
                    # Continuar processamento mesmo se houver erro na verificação
                
                payments_para_processar.append(payment)
            
            payments_pendentes = payments_para_processar
            
            total_pendentes = len(payments_pendentes)
            logger.info(f"📊 [SYNC UMBRELLAPAY] Payments pendentes encontrados: {total_pendentes}")
            
            if total_pendentes == 0:
                logger.info("✅ [SYNC UMBRELLAPAY] Nenhum payment pendente para sincronizar")
                return
            
            atualizados = 0
            erros = 0
            ainda_pendentes = 0
            
            for payment in payments_pendentes:
                try:
                    logger.info("-" * 80)
                    logger.info(f"🔍 [SYNC UMBRELLAPAY] Processando: {payment.payment_id}")
                    logger.info(f"   Gateway Transaction ID: {payment.gateway_transaction_id}")
                    logger.info(f"   Valor: R$ {payment.amount:.2f}")
                    logger.info(f"   Criado em: {payment.created_at}")
                    logger.info(f"   Tempo pendente: {(get_brazil_time() - payment.created_at).total_seconds() / 60:.1f} minutos")
                    
                    # ✅ Buscar gateway configurado
                    bot = payment.bot
                    gateway = Gateway.query.filter_by(
                        user_id=bot.user_id,
                        gateway_type='umbrellapag',
                        is_verified=True
                    ).first()
                    
                    if not gateway:
                        logger.warning(f"⚠️ [SYNC UMBRELLAPAY] Gateway não encontrado para payment {payment.payment_id}")
                        erros += 1
                        continue
                    
                    # ✅ Criar instância do gateway
                    credentials = {
                        'api_key': gateway.api_key,
                        'product_hash': gateway.product_hash
                    }
                    
                    payment_gateway = GatewayFactory.create_gateway(
                        gateway_type='umbrellapag',
                        credentials=credentials
                    )
                    
                    if not payment_gateway:
                        logger.error(f"❌ [SYNC UMBRELLAPAY] Não foi possível criar instância do gateway para {payment.payment_id}")
                        erros += 1
                        continue
                    
                    # ✅ VALIDAÇÃO: Verificar se gateway_transaction_id existe
                    if not payment.gateway_transaction_id or not payment.gateway_transaction_id.strip():
                        logger.warning(f"⚠️ [SYNC UMBRELLAPAY] gateway_transaction_id não encontrado para {payment.payment_id}")
                        erros += 1
                        continue
                    
                    # ✅ Consultar status no gateway (com retry automático via get_payment_status)
                    logger.info(f"🔍 [SYNC UMBRELLAPAY] Consultando status no gateway...")
                    logger.info(f"   Payment ID: {payment.payment_id}")
                    logger.info(f"   Transaction ID: {payment.gateway_transaction_id}")
                    
                    try:
                        api_status = payment_gateway.get_payment_status(payment.gateway_transaction_id)
                    except Exception as e:
                        logger.error(f"❌ [SYNC UMBRELLAPAY] Erro ao consultar status do gateway: {e}", exc_info=True)
                        logger.error(f"   Payment ID: {payment.payment_id}")
                        logger.error(f"   Transaction ID: {payment.gateway_transaction_id}")
                        erros += 1
                        continue
                    
                    if not api_status:
                        logger.warning(f"⚠️ [SYNC UMBRELLAPAY] Não foi possível obter status do gateway para {payment.payment_id}")
                        logger.warning(f"   Transaction ID: {payment.gateway_transaction_id}")
                        erros += 1
                        continue
                    
                    status_gateway = api_status.get('status')
                    logger.info(f"📊 [SYNC UMBRELLAPAY] Status no gateway: {status_gateway}")
                    
                    # ✅ Verificar se payment ainda está pending (evitar race condition)
                    db.session.refresh(payment)
                    if payment.status != 'pending':
                        logger.info(f"ℹ️ [SYNC UMBRELLAPAY] Payment {payment.payment_id} já foi atualizado (status: {payment.status})")
                        continue
                    
                    # ✅ Atualizar se gateway mostrar paid
                    if status_gateway == 'paid':
                        logger.info(f"✅ [SYNC UMBRELLAPAY] Gateway confirmou pagamento! Atualizando sistema...")
                        logger.info(f"   Payment ID: {payment.payment_id}")
                        logger.info(f"   Transaction ID: {payment.gateway_transaction_id}")
                        
                        try:
                            payment.status = 'paid'
                            payment.paid_at = get_brazil_time()
                            payment.bot.total_sales += 1
                            payment.bot.total_revenue += payment.amount
                            payment.bot.owner.total_sales += 1
                            payment.bot.owner.total_revenue += payment.amount
                            
                            # ✅ NOVA ARQUITETURA: Purchase NÃO é disparado quando pagamento é confirmado
                            # ✅ Purchase é disparado APENAS quando lead acessa link de entrega (/delivery/<token>)
                            logger.info(f"✅ [SYNC UMBRELLAPAY] Purchase será disparado apenas quando lead acessar link de entrega: /delivery/<token>")
                            
                            # ✅ COMMIT ATÔMICO com rollback em caso de erro
                            db.session.commit()
                            logger.info(f"💾 [SYNC UMBRELLAPAY] Payment {payment.payment_id} atualizado para 'paid'")
                            
                            # ✅ Validação pós-update: Refresh e assert
                            db.session.refresh(payment)
                            if payment.status == 'paid':
                                logger.info(f"✅ [SYNC UMBRELLAPAY] Validação pós-update: Status confirmado como 'paid'")
                                atualizados += 1
                            else:
                                logger.error(f"🚨 [SYNC UMBRELLAPAY] ERRO CRÍTICO: Status não foi atualizado corretamente!")
                                logger.error(f"   Esperado: 'paid', Atual: {payment.status}")
                                logger.error(f"   Payment ID: {payment.payment_id}")
                                erros += 1
                                
                        except Exception as e:
                            logger.error(f"❌ [SYNC UMBRELLAPAY] Erro ao atualizar payment {payment.payment_id}: {e}", exc_info=True)
                            db.session.rollback()
                            logger.error(f"   Rollback executado. Payment não foi atualizado.")
                            erros += 1
                    else:
                        logger.info(f"⏳ [SYNC UMBRELLAPAY] Payment ainda pendente no gateway (status: {status_gateway})")
                        ainda_pendentes += 1
                
                except Exception as e:
                    logger.error(f"❌ [SYNC UMBRELLAPAY] Erro ao processar payment {payment.payment_id}: {e}", exc_info=True)
                    erros += 1
                    db.session.rollback()
            
            # ✅ Resumo final
            logger.info("=" * 80)
            logger.info(f"📊 [SYNC UMBRELLAPAY] Resumo da sincronização:")
            logger.info(f"   Total processados: {total_pendentes}")
            logger.info(f"   ✅ Atualizados para 'paid': {atualizados}")
            logger.info(f"   ⏳ Ainda pendentes: {ainda_pendentes}")
            logger.info(f"   ❌ Erros: {erros}")
            logger.info("=" * 80)
    
    except Exception as e:
        logger.error(f"❌ [SYNC UMBRELLAPAY] Erro crítico na sincronização: {e}", exc_info=True)

