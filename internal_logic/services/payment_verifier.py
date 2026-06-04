"""
Payment Verifier Service
=======================
Verificacao de status de pagamento e liberacao de acesso.
Extraido do BotManager para isolamento e testabilidade.
"""

import logging
import json
from typing import Dict, Any

from gateways import GatewayFactory

logger = logging.getLogger(__name__)


def verify_payment(bot_manager, bot_id: int, token: str, chat_id: int,
                   payment_id: str, user_info: Dict[str, Any]):
    try:
        from internal_logic.core.models import Payment, Bot, Gateway
        from internal_logic.core.extensions import db
        from flask import current_app
        
        with current_app.app_context():
            # Buscar pagamento no banco
            payment_lookup = str(payment_id).strip() if payment_id is not None else ''
            payment = None
            if payment_lookup.isdigit():
                payment = Payment.query.get(int(payment_lookup))
            if not payment and payment_lookup:
                payment = Payment.query.filter_by(payment_id=payment_lookup).first()
            if not payment and payment_lookup:
                payment = Payment.query.filter_by(gateway_transaction_id=payment_lookup).first()
            
            if not payment:
                logger.warning(f"⚠️ Pagamento não encontrado: {payment_id}")
                bot_manager.send_telegram_message(
                    token=token,
                    chat_id=str(chat_id),
                    message="❌ Pagamento não encontrado. Entre em contato com o suporte."
                )
                return
            
            logger.info(f"📊 Status do pagamento LOCAL: {payment.status}")
            
            # ✅ PARADISE: Consulta manual DESATIVADA (usa apenas webhooks)
            # O job automático (check_paradise_pending_sales.py) processa pagamentos a cada 2 minutos
            # Se Paradise enviar webhook, o sistema marca automaticamente
            # Ao clicar em "Verificar Pagamento", apenas verifica o status NO BANCO
            if payment.status == 'pending':
                if payment.gateway_type == 'paradise':
                    logger.info(f"📡 Paradise: Webhook será processado automaticamente pelo job")
                    logger.info(f"⏰ Se pagamento já está aprovado no painel Paradise, aguarde até 2 minutos")
                elif payment.gateway_type == 'umbrellapag':
                    # ✅ CORREÇÃO CRÍTICA UMBRELLAPAY: Verificação dupla com intervalo
                    logger.info(f"🔍 [VERIFY UMBRELLAPAY] Iniciando verificação dupla para payment_id={payment.payment_id}")
                    logger.info(f"   Transaction ID: {payment.gateway_transaction_id}")
                    logger.info(f"   Status atual: {payment.status}")
                    
                    # ✅ VALIDAÇÃO CRÍTICA: Verificar se gateway_transaction_id existe
                    if not payment.gateway_transaction_id or not payment.gateway_transaction_id.strip():
                        logger.error(f"❌ [VERIFY UMBRELLAPAY] gateway_transaction_id não encontrado para payment_id={payment.payment_id}")
                        return
                    
                    # ✅ ETAPA 1: Verificar se existe webhook recente (<2 minutos)
                    from internal_logic.core.models import WebhookEvent, get_brazil_time
                    from datetime import timedelta
                    import time
                    
                    dois_minutos_atras = get_brazil_time() - timedelta(minutes=2)
                    try:
                        webhook_recente = WebhookEvent.query.filter(
                            WebhookEvent.gateway_type == 'umbrellapag',
                            WebhookEvent.transaction_id == payment.gateway_transaction_id,
                            WebhookEvent.received_at >= dois_minutos_atras
                        ).order_by(WebhookEvent.received_at.desc()).first()
                    except Exception as e:
                        logger.error(f"❌ [VERIFY UMBRELLAPAY] Erro ao buscar webhook recente: {e}", exc_info=True)
                        webhook_recente = None
                    
                    if webhook_recente:
                        logger.info(f"⏳ [VERIFY UMBRELLAPAY] Webhook recente encontrado (recebido em {webhook_recente.received_at})")
                        logger.info(f"   Transaction ID: {payment.gateway_transaction_id}")
                        logger.info(f"   Status do webhook: {webhook_recente.status}")
                        logger.info(f"   Aguardando processamento do webhook... Não atualizando manualmente")
                        
                        # Recarregar payment para ver se webhook já atualizou
                        try:
                            db.session.refresh(payment)
                            if payment.status == 'paid':
                                logger.info(f"✅ [VERIFY UMBRELLAPAY] Webhook já atualizou o pagamento! Status: {payment.status}")
                            else:
                                logger.info(f"⏳ [VERIFY UMBRELLAPAY] Webhook ainda não processou. Aguarde até 2 minutos.")
                        except Exception as e:
                            logger.error(f"❌ [VERIFY UMBRELLAPAY] Erro ao recarregar payment: {e}", exc_info=True)
                        return  # Não fazer consulta manual se webhook recente existe
                    
                    # ✅ ETAPA 2: Verificação dupla com intervalo (3 segundos)
                    try:
                        bot = payment.bot
                        if not bot:
                            logger.error(f"❌ [VERIFY UMBRELLAPAY] Bot não encontrado para payment_id={payment.payment_id}")
                            return
                        
                        gateway = Gateway.query.filter_by(
                            user_id=bot.user_id,
                            gateway_type=payment.gateway_type,
                            is_verified=True
                        ).first()
                        
                        if not gateway:
                            logger.warning(f"⚠️ [VERIFY UMBRELLAPAY] Gateway não encontrado para gateway_type={payment.gateway_type}, user_id={bot.user_id}")
                            return
                        
                        # ✅ RANKING V2.0: Usar commission_percentage do USUÁRIO diretamente
                        user_commission = bot.owner.commission_percentage or gateway.split_percentage or 2.0
                        
                        credentials = {
                            'api_key': gateway.api_key,
                            'product_hash': gateway.product_hash
                        }
                        
                        payment_gateway = GatewayFactory.create_gateway(
                            gateway_type=payment.gateway_type,
                            credentials=credentials
                        )
                        
                        if not payment_gateway:
                            logger.error(f"❌ [VERIFY UMBRELLAPAY] Não foi possível criar instância do gateway")
                            return
                        
                        # ✅ CONSULTA 1 com retry e tratamento de erro
                        logger.info(f"🔍 [VERIFY UMBRELLAPAY] Consulta 1/2: Verificando status na API...")
                        logger.info(f"   Transaction ID: {payment.gateway_transaction_id}")
                        
                        try:
                            api_status_1 = payment_gateway.get_payment_status(payment.gateway_transaction_id)
                            status_1 = api_status_1.get('status') if api_status_1 else None
                            logger.info(f"📊 [VERIFY UMBRELLAPAY] Consulta 1 retornou: status={status_1}")
                        except Exception as e:
                            logger.error(f"❌ [VERIFY UMBRELLAPAY] Erro na consulta 1: {e}", exc_info=True)
                            logger.error(f"   Transaction ID: {payment.gateway_transaction_id}")
                            return
                        
                        # ✅ VALIDAÇÃO: Não atualizar se payment já está paid
                        try:
                            db.session.refresh(payment)
                            if not payment:  # Payment pode ter sido deletado
                                logger.warning(f"⚠️ [VERIFY UMBRELLAPAY] Payment não encontrado após refresh")
                                return
                            
                            if payment.status == 'paid':
                                logger.info(f"✅ [VERIFY UMBRELLAPAY] Pagamento já está PAID no sistema. Não atualizar.")
                                return
                        except Exception as e:
                            logger.error(f"❌ [VERIFY UMBRELLAPAY] Erro ao recarregar payment: {e}", exc_info=True)
                            return
                        
                        # ✅ Aguardar 3 segundos
                        logger.info(f"⏳ [VERIFY UMBRELLAPAY] Aguardando 3 segundos antes da consulta 2...")
                        time.sleep(3)
                        
                        # ✅ CONSULTA 2 com retry e tratamento de erro
                        logger.info(f"🔍 [VERIFY UMBRELLAPAY] Consulta 2/2: Verificando status na API novamente...")
                        logger.info(f"   Transaction ID: {payment.gateway_transaction_id}")
                        
                        try:
                            api_status_2 = payment_gateway.get_payment_status(payment.gateway_transaction_id)
                            status_2 = api_status_2.get('status') if api_status_2 else None
                            logger.info(f"📊 [VERIFY UMBRELLAPAY] Consulta 2 retornou: status={status_2}")
                        except Exception as e:
                            logger.error(f"❌ [VERIFY UMBRELLAPAY] Erro na consulta 2: {e}", exc_info=True)
                            logger.error(f"   Transaction ID: {payment.gateway_transaction_id}")
                            return
                        
                        # ✅ VALIDAÇÃO FINAL: Só atualizar se AMBAS as consultas retornarem 'paid'
                        if status_1 == 'paid' and status_2 == 'paid':
                            # ✅ Verificar novamente se payment ainda está pending (evitar race condition)
                            try:
                                db.session.refresh(payment)
                                if not payment:  # Payment pode ter sido deletado
                                    logger.warning(f"⚠️ [VERIFY UMBRELLAPAY] Payment não encontrado após refresh final")
                                    return
                                
                                if payment.status == 'paid':
                                    logger.info(f"✅ [VERIFY UMBRELLAPAY] Pagamento já foi atualizado por outro processo. Não atualizar novamente.")
                                    return
                            except Exception as e:
                                logger.error(f"❌ [VERIFY UMBRELLAPAY] Erro ao recarregar payment final: {e}", exc_info=True)
                                return
                            
                            logger.info(f"✅ [VERIFY UMBRELLAPAY] VERIFICAÇÃO DUPLA CONFIRMADA: Ambas consultas retornaram 'paid'")
                            logger.info(f"   Payment ID: {payment.payment_id}")
                            logger.info(f"   Transaction ID: {payment.gateway_transaction_id}")
                            logger.info(f"   Atualizando pagamento para 'paid'...")
                            
                            # ============================================================================
                            # ✅ FASE 1: GARANTIA DE RECEITA - Commit Imediato do Status
                            # ============================================================================
                            try:
                                payment.status = 'paid'
                                payment.paid_at = get_brazil_time()
                                
                                # ✅ COMMIT IMEDIATO - Nunca rollback após confirmar receita
                                db.session.commit()
                                logger.info(f"💰 [VERIFY UMBRELLAPAY] Pagamento CONFIRMADO e COMMITADO - ID: {payment.payment_id}")
                                
                            except Exception as commit_error:
                                db.session.rollback()
                                logger.error(f"❌ [VERIFY UMBRELLAPAY] ERRO CRÍTICO ao confirmar pagamento: {commit_error}", exc_info=True)
                                return  # Abortar sem processar liberação
                            
                            # ============================================================================
                            # ✅ FASE 2: PROCESSAMENTO DE LIBERAÇÃO (Isolado - pode falhar sem perder venda)
                            # ============================================================================
                            try:
                                # ✅ Recarregar objeto para garantir estado atualizado
                                db.session.refresh(payment)
                                
                                # ✅ NOVA ARQUITETURA: Purchase NÃO é disparado quando pagamento é confirmado
                                # ✅ Purchase é disparado APENAS quando lead acessa link de entrega (/delivery/<token>)
                                logger.info(f"✅ [VERIFY UMBRELLAPAY] Purchase será disparado apenas quando lead acessar link de entrega")
                                
                                # ✅ VERIFICAR CONQUISTAS (não crítico)
                                try:
                                    from internal_logic.services.achievements import check_and_unlock_achievements
                                    new_achievements = check_and_unlock_achievements(payment.bot.owner)
                                    if new_achievements:
                                        logger.info(f"🏆 [VERIFY UMBRELLAPAY] {len(new_achievements)} conquista(s) desbloqueada(s)!")
                                except Exception as e:
                                    logger.warning(f"⚠️ [VERIFY UMBRELLAPAY] Erro ao verificar conquistas (não crítico): {e}")
                                
                            except Exception as phase2_error:
                                # ✅ FASE 2 é NÃO-CRÍTICA: Falhas aqui não afetam a venda confirmada
                                logger.error(f"❌ [VERIFY UMBRELLAPAY] Erro não crítico após confirmação: {phase2_error}", exc_info=True)
                            
                            # ============================================================================
                            # ✅ UPSELLS AUTOMÁTICOS - APÓS VERIFICAÇÃO MANUAL
                            # ✅ CORREÇÃO CRÍTICA QI 500: Processar upsells quando pagamento é confirmado via verificação manual
                            # ============================================================================
                            logger.info(f"🔍 [UPSELLS VERIFY] Verificando condições: status='{payment.status}', has_config={payment.bot.config is not None if payment.bot else False}, upsells_enabled={payment.bot.config.upsells_enabled if (payment.bot and payment.bot.config) else 'N/A'}")
                            
                            if payment.status == 'paid' and payment.bot.config and payment.bot.config.upsells_enabled:
                                logger.info(f"✅ [UPSELLS VERIFY] Condições atendidas! Processando upsells para payment {payment.payment_id}")
                                try:
                                    # ✅ CORREÇÃO CRÍTICA QI 500: Verificar scheduler ANTES de verificar jobs
                                    if not bot_manager.scheduler:
                                        logger.error(f"❌ CRÍTICO: Scheduler não está disponível! Upsells NÃO serão agendados!")
                                        logger.error(f"   Payment ID: {payment.payment_id}")
                                        logger.error(f"   Verificar se APScheduler foi inicializado corretamente")
                                    else:
                                        # ✅ DIAGNÓSTICO: Verificar se scheduler está rodando
                                        try:
                                            scheduler_running = bot_manager.scheduler.running
                                            if not scheduler_running:
                                                logger.error(f"❌ CRÍTICO: Scheduler existe mas NÃO está rodando!")
                                                logger.error(f"   Payment ID: {payment.payment_id}")
                                                logger.error(f"   Upsells NÃO serão executados se scheduler não estiver rodando!")
                                        except Exception as scheduler_check_error:
                                            logger.warning(f"⚠️ Não foi possível verificar se scheduler está rodando: {scheduler_check_error}")
                                        
                                        # ✅ ANTI-DUPLICAÇÃO: Verificar se upsells já foram agendados para este payment
                                        upsells_already_scheduled = False
                                        try:
                                            # Verificar se já existe job de upsell para este payment
                                            for i in range(10):  # Verificar até 10 upsells possíveis
                                                job_id = f"upsell_{payment.bot_id}_{payment.payment_id}_{i}"
                                                existing_job = bot_manager.scheduler.get_job(job_id)
                                                if existing_job:
                                                    upsells_already_scheduled = True
                                                    logger.info(f"ℹ️ Upsells já foram agendados para payment {payment.payment_id} (job {job_id} existe)")
                                                    logger.info(f"   Job encontrado: {job_id}, próxima execução: {existing_job.next_run_time}")
                                                    break
                                        except Exception as check_error:
                                            logger.error(f"❌ ERRO ao verificar jobs existentes: {check_error}", exc_info=True)
                                            logger.warning(f"⚠️ Continuando mesmo com erro na verificação (pode causar duplicação)")
                                            # ✅ Não bloquear se houver erro na verificação - deixar tentar agendar
                                        
                                        if bot_manager.scheduler and not upsells_already_scheduled:
                                            upsells = payment.bot.config.get_upsells()
                                            
                                            if upsells:
                                                logger.info(f"🎯 [UPSELLS VERIFY] Verificando upsells para produto: {payment.product_name}")
                                                
                                                # Filtrar upsells que fazem match com o produto comprado
                                                matched_upsells = []
                                                for upsell in upsells:
                                                    trigger_product = upsell.get('trigger_product', '')
                                                    
                                                    # Match: trigger vazio (todas compras) OU produto específico
                                                    if not trigger_product or trigger_product == payment.product_name:
                                                        matched_upsells.append(upsell)
                                                
                                                if matched_upsells:
                                                    logger.info(f"✅ [UPSELLS VERIFY] {len(matched_upsells)} upsell(s) encontrado(s) para '{payment.product_name}'")
                                                    
                                                    # ✅ CORREÇÃO: Usar função específica para upsells (não downsells)
                                                    bot_manager.schedule_upsells(
                                                        bot_id=payment.bot_id,
                                                        payment_id=payment.payment_id,
                                                        chat_id=int(payment.customer_user_id),
                                                        upsells=matched_upsells,
                                                        original_price=payment.amount,
                                                        original_button_index=payment.button_index if payment.button_index is not None else -1
                                                    )
                                                    
                                                    logger.info(f"📅 [UPSELLS VERIFY] Upsells agendados com sucesso para payment {payment.payment_id}!")
                                                else:
                                                    logger.info(f"ℹ️ [UPSELLS VERIFY] Nenhum upsell configurado para '{payment.product_name}' (trigger_product não faz match)")
                                            else:
                                                logger.info(f"ℹ️ [UPSELLS VERIFY] Lista de upsells vazia no config do bot")
                                        else:
                                            if not bot_manager.scheduler:
                                                logger.error(f"❌ [UPSELLS VERIFY] Scheduler não disponível - upsells não serão agendados")
                                            else:
                                                logger.info(f"ℹ️ [UPSELLS VERIFY] Upsells já foram agendados anteriormente para payment {payment.payment_id} (evitando duplicação)")
                                    
                                except Exception as upsell_error:
                                    logger.error(f"❌ [UPSELLS VERIFY] Erro ao processar upsells: {upsell_error}", exc_info=True)
                            
                        elif status_1 == 'paid' and status_2 != 'paid':
                            logger.warning(f"⚠️ [VERIFY UMBRELLAPAY] DISCREPÂNCIA DETECTADA: Consulta 1=paid, Consulta 2={status_2}")
                            logger.warning(f"   Transaction ID: {payment.gateway_transaction_id}")
                            logger.warning(f"   Não atualizando - inconsistência detectada. Aguardando webhook ou próxima verificação.")
                        
                        elif status_1 != 'paid' and status_2 == 'paid':
                            logger.warning(f"⚠️ [VERIFY UMBRELLAPAY] DISCREPÂNCIA DETECTADA: Consulta 1={status_1}, Consulta 2=paid")
                            logger.warning(f"   Transaction ID: {payment.gateway_transaction_id}")
                            logger.warning(f"   Não atualizando - inconsistência detectada. Aguardando webhook ou próxima verificação.")
                        
                        else:
                            logger.info(f"⏳ [VERIFY UMBRELLAPAY] Ambas consultas retornaram: {status_1} e {status_2} (não é 'paid')")
                            logger.info(f"   Transaction ID: {payment.gateway_transaction_id}")
                            logger.info(f"   Pagamento ainda pendente no gateway")
                            
                    except Exception as e:
                        logger.error(f"❌ [VERIFY UMBRELLAPAY] Erro crítico na verificação: {e}", exc_info=True)
                        logger.error(f"   Payment ID: {payment.payment_id}")
                        logger.error(f"   Transaction ID: {payment.gateway_transaction_id}")
                        return
                else:
                    # Outros gateways podem ter consulta manual (comportamento antigo)
                    logger.info(f"🔍 Gateway {payment.gateway_type}: Consultando status na API...")
                    
                    bot = payment.bot
                    gateway = Gateway.query.filter_by(
                        user_id=bot.user_id,
                        gateway_type=payment.gateway_type,
                        is_verified=True
                    ).first()
                    
                    if gateway:
                        # ✅ RANKING V2.0: Usar commission_percentage do USUÁRIO diretamente
                        user_commission = bot.owner.commission_percentage or gateway.split_percentage or 2.0
                        
                        credentials = {
                            'client_id': gateway.client_id,
                            'client_secret': gateway.client_secret,
                            'api_key': gateway.api_key,
                            'product_hash': gateway.product_hash,
                            'offer_hash': gateway.offer_hash,
                            'store_id': gateway.store_id,
                            'split_user_id': gateway.split_user_id,
                            'split_percentage': user_commission
                        }
                        
                        payment_gateway = GatewayFactory.create_gateway(
                            gateway_type=payment.gateway_type,
                            credentials=credentials
                        )
                        
                        if payment_gateway:
                            api_status = payment_gateway.get_payment_status(payment.gateway_transaction_id)
                            
                            if api_status and api_status.get('status') == 'paid':
                                if payment.status == 'pending':
                                    logger.info(f"✅ API confirmou pagamento! Atualizando status...")
                                    
                                    # ============================================================================
                                    # ✅ FASE 1: GARANTIA DE RECEITA - Commit Imediato do Status
                                    # ============================================================================
                                    try:
                                        payment.status = 'paid'
                                        from internal_logic.core.models import get_brazil_time
                                        payment.paid_at = get_brazil_time()
                                        
                                        # ✅ COMMIT IMEDIATO - Nunca rollback após confirmar receita
                                        db.session.commit()
                                        logger.info(f"💰 Pagamento CONFIRMADO e COMMITADO - ID: {payment.payment_id}")
                                        
                                    except Exception as commit_error:
                                        db.session.rollback()
                                        logger.error(f"❌ ERRO CRÍTICO ao confirmar pagamento: {commit_error}", exc_info=True)
                                        return  # Abortar sem processar liberação
                                    
                                    # ============================================================================
                                    # ✅ FASE 2: PROCESSAMENTO DE LIBERAÇÃO (Isolado)
                                    # ============================================================================
                                    try:
                                        # ✅ Recarregar objeto para garantir estado atualizado
                                        db.session.refresh(payment)
                                        
                                        # ✅ NOVA ARQUITETURA: Purchase NÃO é disparado quando pagamento é confirmado
                                        logger.info(f"✅ Purchase será disparado apenas quando lead acessar link de entrega")
                                        
                                        # ✅ VERIFICAR CONQUISTAS (não crítico)
                                        try:
                                            from internal_logic.services.achievements import check_and_unlock_achievements
                                            new_achievements = check_and_unlock_achievements(payment.bot.owner)
                                            if new_achievements:
                                                logger.info(f"🏆 {len(new_achievements)} conquista(s) desbloqueada(s)!")
                                        except Exception as e:
                                            logger.warning(f"⚠️ Erro ao verificar conquistas (não crítico): {e}")
                                    
                                    except Exception as phase2_error:
                                        # ✅ FASE 2 é NÃO-CRÍTICA: Falhas aqui não afetam a venda confirmada
                                        logger.error(f"❌ Erro não crítico após confirmação de pagamento: {phase2_error}", exc_info=True)
                                    
                                    # ============================================================================
                                    # ✅ UPSELLS AUTOMÁTICOS - APÓS VERIFICAÇÃO MANUAL (OUTROS GATEWAYS)
                                    # ✅ CORREÇÃO CRÍTICA QI 500: Processar upsells quando pagamento é confirmado via verificação manual (outros gateways)
                                    # ============================================================================
                                    logger.info(f"🔍 [UPSELLS VERIFY OTHER] Verificando condições: status='paid', has_config={payment.bot.config is not None if payment.bot else False}, upsells_enabled={payment.bot.config.upsells_enabled if (payment.bot and payment.bot.config) else 'N/A'}")
                                    
                                    if payment.status == 'paid' and payment.bot.config and payment.bot.config.upsells_enabled:
                                        logger.info(f"✅ [UPSELLS VERIFY OTHER] Condições atendidas! Processando upsells para payment {payment.payment_id}")
                                        try:
                                            # ✅ CORREÇÃO CRÍTICA QI 500: Verificar scheduler ANTES de verificar jobs
                                            if not bot_manager.scheduler:
                                                logger.error(f"❌ CRÍTICO: Scheduler não está disponível! Upsells NÃO serão agendados!")
                                                logger.error(f"   Payment ID: {payment.payment_id}")
                                                logger.error(f"   Verificar se APScheduler foi inicializado corretamente")
                                            else:
                                                # ✅ DIAGNÓSTICO: Verificar se scheduler está rodando
                                                try:
                                                    scheduler_running = bot_manager.scheduler.running
                                                    if not scheduler_running:
                                                        logger.error(f"❌ CRÍTICO: Scheduler existe mas NÃO está rodando!")
                                                        logger.error(f"   Payment ID: {payment.payment_id}")
                                                        logger.error(f"   Upsells NÃO serão executados se scheduler não estiver rodando!")
                                                except Exception as scheduler_check_error:
                                                    logger.warning(f"⚠️ Não foi possível verificar se scheduler está rodando: {scheduler_check_error}")
                                                
                                                # ✅ ANTI-DUPLICAÇÃO: Verificar se upsells já foram agendados para este payment
                                                upsells_already_scheduled = False
                                                try:
                                                    # Verificar se já existe job de upsell para este payment
                                                    for i in range(10):  # Verificar até 10 upsells possíveis
                                                        job_id = f"upsell_{payment.bot_id}_{payment.payment_id}_{i}"
                                                        existing_job = bot_manager.scheduler.get_job(job_id)
                                                        if existing_job:
                                                            upsells_already_scheduled = True
                                                            logger.info(f"ℹ️ Upsells já foram agendados para payment {payment.payment_id} (job {job_id} existe)")
                                                            logger.info(f"   Job encontrado: {job_id}, próxima execução: {existing_job.next_run_time}")
                                                            break
                                                except Exception as check_error:
                                                    logger.error(f"❌ ERRO ao verificar jobs existentes: {check_error}", exc_info=True)
                                                    logger.warning(f"⚠️ Continuando mesmo com erro na verificação (pode causar duplicação)")
                                                    # ✅ Não bloquear se houver erro na verificação - deixar tentar agendar
                                            
                                            if bot_manager.scheduler and not upsells_already_scheduled:
                                                upsells = payment.bot.config.get_upsells()
                                                
                                                if upsells:
                                                    logger.info(f"🎯 [UPSELLS VERIFY OTHER] Verificando upsells para produto: {payment.product_name}")
                                                    
                                                    # Filtrar upsells que fazem match com o produto comprado
                                                    matched_upsells = []
                                                    for upsell in upsells:
                                                        trigger_product = upsell.get('trigger_product', '')
                                                        
                                                        # Match: trigger vazio (todas compras) OU produto específico
                                                        if not trigger_product or trigger_product == payment.product_name:
                                                            matched_upsells.append(upsell)
                                                    
                                                    if matched_upsells:
                                                        logger.info(f"✅ [UPSELLS VERIFY OTHER] {len(matched_upsells)} upsell(s) encontrado(s) para '{payment.product_name}'")
                                                        
                                                        # ✅ CORREÇÃO: Usar função específica para upsells (não downsells)
                                                        bot_manager.schedule_upsells(
                                                            bot_id=payment.bot_id,
                                                            payment_id=payment.payment_id,
                                                            chat_id=int(payment.customer_user_id),
                                                            upsells=matched_upsells,
                                                            original_price=payment.amount,
                                                            original_button_index=-1
                                                        )
                                                        
                                                        logger.info(f"📅 [UPSELLS VERIFY OTHER] Upsells agendados com sucesso para payment {payment.payment_id}!")
                                                    else:
                                                        logger.info(f"ℹ️ [UPSELLS VERIFY OTHER] Nenhum upsell configurado para '{payment.product_name}' (trigger_product não faz match)")
                                                else:
                                                    logger.info(f"ℹ️ [UPSELLS VERIFY OTHER] Lista de upsells vazia no config do bot")
                                            else:
                                                if not bot_manager.scheduler:
                                                    logger.error(f"❌ [UPSELLS VERIFY OTHER] Scheduler não disponível - upsells não serão agendados")
                                                else:
                                                    logger.info(f"ℹ️ [UPSELLS VERIFY OTHER] Upsells já foram agendados anteriormente para payment {payment.payment_id} (evitando duplicação)")
                                                
                                        except Exception as e:
                                            logger.error(f"❌ [UPSELLS VERIFY OTHER] Erro ao processar upsells: {e}", exc_info=True)
                                            import traceback
                                            traceback.print_exc()
                                    
                                    # ✅ ENVIAR ENTREGÁVEL após confirmar pagamento (outros gateways)
                                    try:
                                        from internal_logic.services.payment_processor import send_payment_delivery
                                        logger.info(f"📦 [VERIFY OTHER] Enviando entregável via send_payment_delivery para {payment.payment_id}")
                                        
                                        db.session.refresh(payment)
                                        
                                        if payment.status == 'paid':
                                            resultado = send_payment_delivery(payment, bot_manager)
                                            if resultado:
                                                logger.info(f"✅ [VERIFY OTHER] Entregável enviado com sucesso via send_payment_delivery")
                                            else:
                                                logger.warning(f"⚠️ [VERIFY OTHER] send_payment_delivery retornou False para {payment.payment_id}")
                                    except Exception as e:
                                        logger.error(f"❌ [VERIFY OTHER] Erro ao enviar entregável via send_payment_delivery: {e}", exc_info=True)
                            elif api_status:
                                logger.info(f"⏳ API retornou status: {api_status.get('status')}")
            
            # ✅ CRÍTICO: Recarregar objeto do banco antes de verificar status final
            db.session.refresh(payment)
            logger.info(f"📊 Status FINAL do pagamento: {payment.status}")
            
            # ✅ CRÍTICO: Validação dupla - verificar status ANTES de qualquer ação
            if payment.status == 'paid':
                # ✅ CRÍTICO: Refresh novamente para garantir que não há race condition
                db.session.refresh(payment)
                
                # ✅ CRÍTICO: Validação final antes de liberar acesso
                if payment.status != 'paid':
                    logger.error(
                        f"❌ ERRO GRAVE: Status mudou após refresh! Esperado: 'paid', Atual: {payment.status}"
                    )
                    logger.error(f"   Payment ID: {payment.payment_id}")
                    return
                
                # PAGAMENTO CONFIRMADO! Liberar acesso
                logger.info(f"✅ PAGAMENTO CONFIRMADO! Liberando acesso...")
                
                # ============================================================================
                # ✅ V∞: FLOW ENGINE - INTEGRAÇÃO COMPLETA COM PAGAMENTO
                # ============================================================================
                flow_processed = False
                if payment.flow_step_id:
                    bot_flow = Bot.query.get(bot_id)
                    if bot_flow and bot_flow.config:
                        flow_config = bot_flow.config.to_dict()
                        flow_enabled = flow_config.get('flow_enabled', False)
                        
                        # Parsear flow_steps se necessário
                        import json
                        flow_steps_raw = flow_config.get('flow_steps', [])
                        if isinstance(flow_steps_raw, str):
                            try:
                                flow_steps = json.loads(flow_steps_raw)
                            except Exception:
                                flow_steps = []
                        else:
                            flow_steps = flow_steps_raw if isinstance(flow_steps_raw, list) else []
                        
                        if flow_enabled and flow_steps:
                            # Buscar step atual do fluxo
                            current_step = bot_manager._find_step_by_id(flow_steps, payment.flow_step_id)
                            
                            if current_step:
                                connections = current_step.get('connections', {})
                                telegram_user_id = str(user_info.get('id', ''))
                                
                                # ✅ V∞: Determinar próximo step baseado em status
                                if payment.status == 'paid':
                                    next_step_id = connections.get('next')
                                else:
                                    next_step_id = connections.get('pending')
                                
                                # ✅ V∞: EXECUTAR PRÓXIMO STEP DIRETAMENTE (não assíncrono)
                                if next_step_id:
                                    logger.info(f"🚀 [FLOW V∞] Payment {payment.status} - executando step: {next_step_id}")
                                    
                                    # Buscar snapshot do Redis
                                    flow_snapshot = bot_manager._get_flow_snapshot_from_redis(bot_id, telegram_user_id)
                                    
                                    try:
                                        # Executar próximo step diretamente
                                        bot_manager._execute_flow_recursive(
                                            bot_id, token, flow_config,
                                            chat_id, telegram_user_id,
                                            next_step_id,
                                            recursion_depth=0,
                                            visited_steps=set(),
                                            flow_snapshot=flow_snapshot
                                        )
                                        flow_processed = True
                                        logger.info(f"✅ [FLOW V∞] Próximo step executado: {next_step_id}")
                                        return  # ✅ SAIR - fluxo processado, não executar código tradicional
                                    except Exception as e:
                                        logger.error(f"❌ [FLOW V∞] Erro ao executar próximo step: {e}", exc_info=True)
                                        # Continuar para fallback tradicional
                            else:
                                logger.error(f"❌ [FLOW V∞] Step {payment.flow_step_id} não encontrado mais na config atual")
                
                # ✅ FALLBACK: Se fluxo não processou, usar comportamento tradicional
                if not flow_processed:
                    # ============================================================================
                    # ✅ NOVA ARQUITETURA: Purchase NÃO é disparado via botão verify
                    # ============================================================================
                    # ✅ Purchase é disparado APENAS quando lead acessa link de entrega (/delivery/<token>)
                    # ✅ Não disparar Purchase quando pagamento é confirmado (via webhook ou botão verify)
                    logger.info(f"✅ Purchase será disparado apenas quando lead acessar link de entrega: /delivery/<token>")
                    
                    # Cancelar downsells agendados
                    bot_manager.cancel_downsells(payment.payment_id)
                
                    # ✅ CRÍTICO: Usar send_payment_delivery para garantir validação consistente
                    try:
                        from internal_logic.services.payment_processor import send_payment_delivery
                        logger.info(f"📦 [VERIFY] Enviando entregável via send_payment_delivery para {payment.payment_id}")
                        
                        # ✅ CRÍTICO: Refresh antes de chamar send_payment_delivery
                        db.session.refresh(payment)
                        
                        # ✅ CRÍTICO: Validar status ANTES de chamar send_payment_delivery
                        if payment.status == 'paid':
                            resultado = send_payment_delivery(payment, bot_manager)
                            if resultado:
                                logger.info(f"✅ [VERIFY] Entregável enviado com sucesso via send_payment_delivery")
                                
                                # ============================================================================
                                # ✅ UPSELLS AUTOMÁTICOS - APÓS VERIFICAÇÃO MANUAL (PAGAMENTO JÁ PAID)
                                # ✅ CORREÇÃO CRÍTICA QI 500: Processar upsells quando pagamento já está paid
                                # ============================================================================
                                logger.info(f"🔍 [UPSELLS VERIFY] Verificando condições: status='{payment.status}', has_config={payment.bot.config is not None if payment.bot else False}, upsells_enabled={payment.bot.config.upsells_enabled if (payment.bot and payment.bot.config) else 'N/A'}")
                                
                                if payment.status == 'paid' and payment.bot.config and payment.bot.config.upsells_enabled:
                                    logger.info(f"✅ [UPSELLS VERIFY] Condições atendidas! Processando upsells para payment {payment.payment_id}")
                                    try:
                                        # ✅ CORREÇÃO CRÍTICA QI 500: Verificar scheduler ANTES de verificar jobs
                                        if not bot_manager.scheduler:
                                            logger.error(f"❌ CRÍTICO: Scheduler não está disponível! Upsells NÃO serão agendados!")
                                            logger.error(f"   Payment ID: {payment.payment_id}")
                                            logger.error(f"   Verificar se APScheduler foi inicializado corretamente")
                                        else:
                                            # ✅ DIAGNÓSTICO: Verificar se scheduler está rodando
                                            try:
                                                scheduler_running = bot_manager.scheduler.running
                                                if not scheduler_running:
                                                    logger.error(f"❌ CRÍTICO: Scheduler existe mas NÃO está rodando!")
                                                    logger.error(f"   Payment ID: {payment.payment_id}")
                                                    logger.error(f"   Upsells NÃO serão executados se scheduler não estiver rodando!")
                                            except Exception as scheduler_check_error:
                                                logger.warning(f"⚠️ Não foi possível verificar se scheduler está rodando: {scheduler_check_error}")
                                            
                                            # ✅ ANTI-DUPLICAÇÃO: Verificar se upsells já foram agendados para este payment
                                            upsells_already_scheduled = False
                                            try:
                                                # Verificar se já existe job de upsell para este payment
                                                for i in range(10):  # Verificar até 10 upsells possíveis
                                                    job_id = f"upsell_{payment.bot_id}_{payment.payment_id}_{i}"
                                                    existing_job = bot_manager.scheduler.get_job(job_id)
                                                    if existing_job:
                                                        upsells_already_scheduled = True
                                                        logger.info(f"ℹ️ Upsells já foram agendados para payment {payment.payment_id} (job {job_id} existe)")
                                                        logger.info(f"   Job encontrado: {job_id}, próxima execução: {existing_job.next_run_time}")
                                                        break
                                            except Exception as check_error:
                                                logger.error(f"❌ ERRO ao verificar jobs existentes: {check_error}", exc_info=True)
                                                logger.warning(f"⚠️ Continuando mesmo com erro na verificação (pode causar duplicação)")
                                                # ✅ Não bloquear se houver erro na verificação - deixar tentar agendar
                                        
                                        if bot_manager.scheduler and not upsells_already_scheduled:
                                            upsells = payment.bot.config.get_upsells()
                                            
                                            if upsells:
                                                logger.info(f"🎯 [UPSELLS VERIFY] Verificando upsells para produto: {payment.product_name}")
                                                
                                                # Filtrar upsells que fazem match com o produto comprado
                                                matched_upsells = []
                                                for upsell in upsells:
                                                    trigger_product = upsell.get('trigger_product', '')
                                                    
                                                    # Match: trigger vazio (todas compras) OU produto específico
                                                    if not trigger_product or trigger_product == payment.product_name:
                                                        matched_upsells.append(upsell)
                                                
                                                if matched_upsells:
                                                    logger.info(f"✅ [UPSELLS VERIFY] {len(matched_upsells)} upsell(s) encontrado(s) para '{payment.product_name}'")
                                                    
                                                    # ✅ CORREÇÃO: Usar função específica para upsells (não downsells)
                                                    bot_manager.schedule_upsells(
                                                        bot_id=payment.bot_id,
                                                        payment_id=payment.payment_id,
                                                        chat_id=int(payment.customer_user_id),
                                                        upsells=matched_upsells,
                                                        original_price=payment.amount,
                                                        original_button_index=payment.button_index if payment.button_index is not None else -1
                                                    )
                                                    
                                                    logger.info(f"📅 [UPSELLS VERIFY] Upsells agendados com sucesso para payment {payment.payment_id}!")
                                                else:
                                                    logger.info(f"ℹ️ [UPSELLS VERIFY] Nenhum upsell configurado para '{payment.product_name}' (trigger_product não faz match)")
                                            else:
                                                logger.info(f"ℹ️ [UPSELLS VERIFY] Lista de upsells vazia no config do bot")
                                        else:
                                            if not bot_manager.scheduler:
                                                logger.error(f"❌ [UPSELLS VERIFY] Scheduler não disponível - upsells não serão agendados")
                                            else:
                                                logger.info(f"ℹ️ [UPSELLS VERIFY] Upsells já foram agendados anteriormente para payment {payment.payment_id} (evitando duplicação)")
                                            
                                    except Exception as e:
                                        logger.error(f"❌ [UPSELLS VERIFY] Erro ao processar upsells: {e}", exc_info=True)
                                        import traceback
                                        traceback.print_exc()
                            else:
                                logger.warning(f"⚠️ [VERIFY] send_payment_delivery retornou False para {payment.payment_id}")
                        else:
                            logger.error(
                                f"❌ ERRO GRAVE: Tentativa de enviar entregável com status inválido "
                                f"(status: {payment.status}, payment_id: {payment.payment_id})"
                            )
                    except Exception as e:
                        logger.error(f"❌ [VERIFY] Erro ao enviar entregável via send_payment_delivery: {e}", exc_info=True)
                        
                        # ✅ FALLBACK: Se send_payment_delivery falhar, usar método antigo (mas com validação)
                        logger.warning(f"⚠️ [VERIFY] Usando fallback para envio de mensagem (send_payment_delivery falhou)")
                        
                        bot = payment.bot
                        # ✅ REDIS BRAIN: Buscar config do Redis
                        bot_data = bot_manager.bot_state.get_bot_data(bot_id)
                        bot_config = bot_data.get('config', {}) if bot_data else {}
                        access_link = bot_config.get('access_link', '')
                        custom_success_message = bot_config.get('success_message', '').strip()
                        
                        # Usar mensagem personalizada ou padrão
                        if custom_success_message:
                            # Substituir variáveis
                            success_message = custom_success_message
                            success_message = success_message.replace('{produto}', payment.product_name or 'Produto')
                            success_message = success_message.replace('{valor}', f'R$ {payment.amount:.2f}')
                            success_message = success_message.replace('{link}', access_link or 'Link não configurado')
                        elif access_link:
                            success_message = f"""
✅ <b>PAGAMENTO CONFIRMADO!</b>

🎉 <b>Parabéns!</b> Seu pagamento foi aprovado com sucesso!

🎯 <b>Produto:</b> {payment.product_name}
💰 <b>Valor pago:</b> R$ {payment.amount:.2f}

🔗 <b>Seu acesso:</b>
{access_link}

<b>Aproveite!</b> 🚀
                            """
                        else:
                            success_message = "✅ Pagamento confirmado! Entre em contato com o suporte para receber seu acesso."
                        
                        bot_manager.send_telegram_message(
                            token=token,
                            chat_id=str(chat_id),
                            message=success_message.strip()
                        )
                    
                    logger.info(f"✅ Acesso liberado para {user_info.get('first_name')}")
            else:
                # PAGAMENTO AINDA PENDENTE
                logger.info(f"⏳ Pagamento ainda pendente...")
                
                # ============================================================================
                # ✅ V∞: FLOW ENGINE - INTEGRAÇÃO COMPLETA COM PAGAMENTO PENDENTE
                # ============================================================================
                flow_processed = False
                if payment.flow_step_id:
                    bot_flow = Bot.query.get(bot_id)
                    if bot_flow and bot_flow.config:
                        flow_config = bot_flow.config.to_dict()
                        flow_enabled = flow_config.get('flow_enabled', False)
                        
                        # Parsear flow_steps se necessário
                        import json
                        flow_steps_raw = flow_config.get('flow_steps', [])
                        if isinstance(flow_steps_raw, str):
                            try:
                                flow_steps = json.loads(flow_steps_raw)
                            except Exception:
                                flow_steps = []
                        else:
                            flow_steps = flow_steps_raw if isinstance(flow_steps_raw, list) else []
                        
                        if flow_enabled and flow_steps:
                            # Buscar step atual do fluxo
                            current_step = bot_manager._find_step_by_id(flow_steps, payment.flow_step_id)
                            
                            if current_step:
                                connections = current_step.get('connections', {})
                                telegram_user_id = str(user_info.get('id', ''))
                                
                                # ✅ V∞: Se payment pendente, executar pending step
                                if payment.status == 'pending':
                                    pending_step_id = connections.get('pending')
                                    
                                    if pending_step_id:
                                        logger.info(f"🚀 [FLOW V∞] Payment pendente - executando step: {pending_step_id}")
                                        
                                        # Buscar snapshot do Redis
                                        flow_snapshot = bot_manager._get_flow_snapshot_from_redis(bot_id, telegram_user_id)
                                        
                                        try:
                                            # Executar pending step diretamente
                                            bot_manager._execute_flow_recursive(
                                                bot_id, token, flow_config,
                                                chat_id, telegram_user_id,
                                                pending_step_id,
                                                recursion_depth=0,
                                                visited_steps=set(),
                                                flow_snapshot=flow_snapshot
                                            )
                                            flow_processed = True
                                            logger.info(f"✅ [FLOW V∞] Pending step executado: {pending_step_id}")
                                            return  # ✅ SAIR - fluxo processado, não executar código tradicional
                                        except Exception as e:
                                            logger.error(f"❌ [FLOW V∞] Erro ao executar pending step: {e}", exc_info=True)
                                            # Continuar para fallback tradicional
                
                # ✅ FALLBACK: Se fluxo não processou, usar comportamento tradicional
                if not flow_processed:
                    bot = payment.bot
                    # ✅ REDIS BRAIN: Buscar config do Redis
                    bot_data = bot_manager.bot_state.get_bot_data(bot_id)
                    bot_config = bot_data.get('config', {}) if bot_data else {}
                    custom_pending_message = bot_config.get('pending_message', '').strip()
                
                # ✅ CORREÇÃO: Buscar PIX code do product_description (onde é salvo)
                logger.info(f"🔍 [VERIFY DEBUG] product_description='{str(payment.product_description)[:80] if payment.product_description else None}', gateway={payment.gateway_type}, payment_id={payment.payment_id}")
                pix_code = payment.product_description or 'Aguardando...'
                logger.info(f"🔍 [VERIFY DEBUG] pix_code result: '{str(pix_code)[:60] if pix_code else None}'")
                
                # ✅ FALLBACK: Se PIX code não está salvo, tentar buscar do gateway (apenas para UmbrellaPay)
                if (pix_code == 'Aguardando...' or not pix_code or len(pix_code) < 20) and payment.gateway_type == 'umbrellapag':
                    try:
                        # Buscar gateway e tentar obter PIX code novamente
                        gateway = Gateway.query.filter_by(
                            user_id=bot.user_id,
                            gateway_type='umbrellapag',
                            is_verified=True
                        ).first()
                        
                        if gateway and payment.gateway_transaction_id:
                            credentials = {
                                'api_key': gateway.api_key,
                                'product_hash': gateway.product_hash
                            }
                            payment_gateway = GatewayFactory.create_gateway(
                                gateway_type='umbrellapag',
                                credentials=credentials
                            )
                            
                            if payment_gateway:
                                # ✅ Tentar buscar PIX code diretamente da API (GET /user/transactions/{id})
                                # A resposta da API inclui o PIX code em data.pix.qrCode
                                try:
                                    # Fazer requisição direta para obter PIX code
                                    response = payment_gateway._make_request('GET', f'/user/transactions/{payment.gateway_transaction_id}')
                                    if response and response.status_code == 200:
                                        api_data = response.json()
                                        
                                        # ✅ Tratar estrutura aninhada (data.data)
                                        inner_data = api_data
                                        if isinstance(api_data, dict) and 'data' in api_data:
                                            inner_data = api_data.get('data', {})
                                            if isinstance(inner_data, dict) and 'data' in inner_data:
                                                inner_data = inner_data.get('data', {})
                                        
                                        # ✅ Extrair PIX code
                                        if isinstance(inner_data, dict):
                                            pix_obj = inner_data.get('pix', {})
                                            if isinstance(pix_obj, dict):
                                                fallback_pix = (
                                                    pix_obj.get('qrCode') or
                                                    pix_obj.get('qr_code') or
                                                    pix_obj.get('code') or
                                                    None
                                                )
                                                if fallback_pix and len(fallback_pix) > 20:
                                                    pix_code = fallback_pix
                                                    logger.info(f"✅ [VERIFY] PIX code recuperado do gateway via API para {payment.payment_id}")
                                except Exception as api_error:
                                    logger.debug(f"🔍 [VERIFY] Não foi possível buscar PIX code via API (não crítico): {api_error}")
                    except Exception as e:
                        logger.warning(f"⚠️ [VERIFY] Erro ao buscar PIX code do gateway (fallback): {e}")
                        # Continuar com pix_code atual (pode ser 'Aguardando...')
                
                # Usar mensagem personalizada ou padrão
                if custom_pending_message:
                    # Substituir variáveis
                    pending_message = custom_pending_message
                    pending_message = pending_message.replace('{pix_code}', f'<code>{pix_code}</code>')
                    pending_message = pending_message.replace('{produto}', payment.product_name or 'Produto')
                    pending_message = pending_message.replace('{valor}', f'R$ {payment.amount:.2f}')
                else:
                    # ✅ PIX em linha única dentro de <code> para copiar com um toque
                    # ✅ Paradise usa APENAS webhooks agora - mensagem específica
                    if payment.gateway_type == 'paradise':
                        pending_message = f"""⏳ <b>Aguardando confirmação</b>

Seu pagamento está sendo processado.

📱 <b>PIX Copia e Cola:</b>
<code>{pix_code}</code>

<i>👆 Toque no código acima para copiar</i>

⏱️ <b>Confirmação automática:</b>
Se você já pagou, o sistema confirmará automaticamente em até 2 minutos via webhook.

✅ Você será notificado assim que o pagamento for confirmado!"""
                    elif payment.gateway_type == 'umbrellapag':
                        # ✅ CORREÇÃO: Mensagem específica para UmbrellaPay (similar ao Paradise)
                        pending_message = f"""⏳ <b>Aguardando confirmação</b>

Seu pagamento está sendo processado.

📱 <b>PIX Copia e Cola:</b>
<code>{pix_code}</code>

<i>👆 Toque no código acima para copiar</i>

⏱️ <b>Confirmação automática:</b>
Se você já pagou, o sistema confirmará automaticamente em até 5 minutos via webhook ou job de sincronização.

💡 <b>Dica:</b> Você pode clicar novamente em "Verificar Pagamento" para consultar o status manualmente.

✅ Você será notificado assim que o pagamento for confirmado!"""
                    else:
                        pending_message = f"""⏳ <b>Pagamento ainda não identificado</b>

Seu pagamento ainda não foi confirmado.

📱 <b>PIX Copia e Cola:</b>
<code>{pix_code}</code>

<i>👆 Toque no código acima para copiar</i>

💡 <b>O que fazer:</b>
1. Verifique se você realmente pagou o PIX
2. Aguarde alguns minutos (pode levar até 5 min)
3. Clique novamente em "Verificar Pagamento"

⏰ Se já pagou, aguarde a confirmação automática!"""
                
                # Reenviar botão de verificar
                buttons = [{
                    'text': '✅ Verificar Pagamento',
                    'callback_data': f'verify_{payment_id}'
                }]
                
                bot_manager.send_telegram_message(
                    token=token,
                    chat_id=str(chat_id),
                    message=pending_message.strip(),
                    buttons=buttons
                )
                
                logger.info(f"⏳ Cliente avisado que pagamento ainda está pendente")
    
    except Exception as e:
        logger.error(f"❌ Erro ao verificar pagamento: {e}")
        import traceback
        traceback.print_exc()

