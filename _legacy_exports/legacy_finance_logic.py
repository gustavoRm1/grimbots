# ============================================================================
# LEGACY FINANCE LOGIC - EXTRAÇÃO DO CÓDIGO LEGADO (STAGING)
# Arquivo: _legacy_exports/legacy_finance_logic.py
# Origem: app.py (linhas ~12889-13200+)
# ============================================================================
# Este arquivo contém a lógica EXATA de atualização de caixa após webhook "paid"
# NÃO MODIFICAR - Apenas para referência durante migração
# ============================================================================

from flask import jsonify
from datetime import timedelta, datetime, timezone
import logging

logger = logging.getLogger(__name__)

# ============================================================================
# IMPORTS NECESSÁRIOS (do código legado)
# ============================================================================
# from models import Payment, Gateway, Commission, Subscription, Bot
# from internal_logic.core.models import get_brazil_time
# from internal_logic.services.payment_processor import send_payment_delivery
# from celery_app import send_meta_event
# from gamification_websocket import notify_achievement_unlocked
# from gamification import RankingEngine, AchievementChecker, check_and_unlock_achievements, GAMIFICATION_V2_ENABLED


def extract_process_payment_confirmation(payment, status, gateway_type, bot_manager, db, socketio=None):
    """
    EXTRACTED FROM: app.py payment_webhook function
    
    Lógica de processamento de confirmação de pagamento:
    - Validação anti-fraude (webhook muito rápido)
    - Atualização de estatísticas (apenas se era pending)
    - Cálculo de comissões
    - Gamificação V2
    - Envio de entregável
    - Upsells
    """
    
    # ============================================================================
    # ✅ CRÍTICO: Validação anti-fraude - Rejeitar webhook 'paid' recebido muito rápido
    # ============================================================================
    if status == 'paid' and payment.created_at:
        try:
            from internal_logic.core.models import get_brazil_time
            tempo_desde_criacao = (get_brazil_time() - payment.created_at).total_seconds()
            
            if tempo_desde_criacao < 10:  # Menos de 10 segundos
                logger.error(
                    f"🚨 [WEBHOOK {gateway_type.upper()}] BLOQUEADO: Webhook 'paid' recebido muito rápido após criação!"
                )
                logger.error(f"   Payment ID: {payment.payment_id}")
                logger.error(f"   Tempo desde criação: {tempo_desde_criacao:.2f} segundos")
                logger.error(f"   Status do webhook: {status}")
                logger.error(f"   ⚠️ Isso é SUSPEITO - Gateway não confirma pagamento em menos de 10 segundos!")
                logger.error(f"   🔒 REJEITANDO webhook e mantendo status como 'pending'")
                
                return {
                    'status': 'rejected_too_fast',
                    'message': f'Webhook paid rejeitado - recebido {tempo_desde_criacao:.2f}s após criação (mínimo: 10s)'
                }, 200
        except Exception as time_error:
            logger.warning(f"⚠️ [WEBHOOK {gateway_type.upper()}] Erro ao calcular tempo desde criação: {time_error}")
    
    # ============================================================================
    # ✅ VERIFICA STATUS ANTIGO ANTES DE QUALQUER ATUALIZAÇÃO
    # ============================================================================
    was_pending = payment.status == 'pending'
    status_antigo = payment.status
    logger.info(f"📊 Status ANTES: {status_antigo} | Novo status: {status} | Era pending: {was_pending}")
    
    # ============================================================================
    # ✅ PROTEÇÃO: Se já está paid E o webhook também é paid, pode ser duplicado
    # ============================================================================
    if payment.status == 'paid' and status == 'paid':
        logger.info(f"⚠️ Webhook duplicado: {payment.payment_id} já está pago - verificando se entregável foi enviado...")
        
        # ✅ CRÍTICO: Refresh antes de validar status
        db.session.refresh(payment)
        
        # ✅ CRÍTICO: Validar status ANTES de chamar send_payment_delivery
        if payment.status == 'paid':
            try:
                from internal_logic.services.payment_processor import send_payment_delivery
                resultado = send_payment_delivery(payment, bot_manager)
                if resultado:
                    logger.info(f"✅ Entregável reenviado com sucesso (webhook duplicado)")
            except:
                pass
        else:
            logger.error(
                f"❌ ERRO GRAVE: send_payment_delivery chamado com payment.status != 'paid' "
                f"(status atual: {payment.status}, payment_id: {payment.payment_id})"
            )
        
        # ✅ CORREÇÃO CRÍTICA: Processar upsells ANTES do return (webhook duplicado)
        logger.info(f"🔍 [UPSELLS WEBHOOK DUPLICADO] Verificando upsells para payment {payment.payment_id}")
        if payment.bot.config and payment.bot.config.upsells_enabled:
            logger.info(f"✅ [UPSELLS WEBHOOK DUPLICADO] Upsells habilitados - verificando se já foram agendados...")
            # Verificar se upsells já foram agendados (anti-duplicação)
            upsells_already_scheduled = False
            if bot_manager.scheduler:
                try:
                    for i in range(10):
                        job_id = f"upsell_{payment.bot_id}_{payment.payment_id}_{i}"
                        existing_job = bot_manager.scheduler.get_job(job_id)
                        if existing_job:
                            upsells_already_scheduled = True
                            logger.info(f"ℹ️ [UPSELLS WEBHOOK DUPLICADO] Upsells já agendados (job {job_id} existe)")
                            break
                except Exception as check_error:
                    logger.warning(f"⚠️ Erro ao verificar jobs no webhook duplicado: {check_error}")
            
            # Se não foram agendados, agendar agora
            if bot_manager.scheduler and not upsells_already_scheduled:
                try:
                    upsells = payment.bot.config.get_upsells()
                    if upsells:
                        matched_upsells = []
                        for upsell in upsells:
                            trigger_product = upsell.get('trigger_product', '')
                            if not trigger_product or trigger_product == payment.product_name:
                                matched_upsells.append(upsell)
                        
                        if matched_upsells:
                            logger.info(f"✅ [UPSELLS WEBHOOK DUPLICADO] Agendando {len(matched_upsells)} upsell(s) para payment {payment.payment_id}")
                            bot_manager.schedule_upsells(
                                bot_id=payment.bot_id,
                                payment_id=payment.payment_id,
                                chat_id=int(payment.customer_user_id),
                                upsells=matched_upsells,
                                original_price=payment.amount,
                                original_button_index=-1
                            )
                except Exception as upsell_error:
                    logger.error(f"❌ Erro ao processar upsells no webhook duplicado: {upsell_error}", exc_info=True)
        
        return {'status': 'already_processed'}, 200
    
    # ============================================================================
    # ✅ ATUALIZA STATUS DO PAGAMENTO APENAS SE NÃO ERA PAID (SEM COMMIT AINDA!)
    # ============================================================================
    if payment.status != 'paid':
        payment.status = status
    
    # ============================================================================
    # ✅ CORREÇÃO CRÍTICA: Separar lógica de estatísticas e entregável
    # ============================================================================
    deve_processar_estatisticas = (status == 'paid' and was_pending)
    deve_enviar_entregavel = (status == 'paid')  # SEMPRE envia se status é 'paid'
    
    logger.info(f"🔍 [DIAGNÓSTICO] payment {payment.payment_id}: status='{status}' | deve_enviar_entregavel={deve_enviar_entregavel} | status_antigo='{status_antigo}' | was_pending={was_pending}")
    
    # ============================================================================
    # ✅ PROCESSAR ESTATÍSTICAS/COMISSÕES APENAS SE ERA PENDENTE (evita duplicação)
    # ============================================================================
    if deve_processar_estatisticas:
        logger.info(f"✅ Processando pagamento confirmado (era pending): {payment.payment_id}")
        
        from internal_logic.core.models import get_brazil_time
        payment.paid_at = get_brazil_time()
        
        # ✅ ATUALIZAR ESTATÍSTICAS DO BOT
        payment.bot.total_sales += 1
        payment.bot.total_revenue += payment.amount
        
        # ✅ ATUALIZAR ESTATÍSTICAS DO USUÁRIO (owner)
        payment.bot.owner.total_sales += 1
        payment.bot.owner.total_revenue += payment.amount
        
        # ✅ ATUALIZAR ESTATÍSTICAS DO GATEWAY
        if payment.gateway_type:
            from models import Gateway
            gateway = Gateway.query.filter_by(
                user_id=payment.bot.user_id,
                gateway_type=payment.gateway_type
            ).first()
            if gateway:
                gateway.total_transactions += 1
                gateway.successful_transactions += 1
                logger.info(f"✅ Estatísticas do gateway {gateway.gateway_type} atualizadas: {gateway.total_transactions} transações, {gateway.successful_transactions} bem-sucedidas")
        
        # ✅ ATUALIZAR ESTATÍSTICAS DE REMARKETING
        if payment.is_remarketing and payment.remarketing_campaign_id:
            from models import RemarketingCampaign
            campaign = RemarketingCampaign.query.get(payment.remarketing_campaign_id)
            if campaign:
                campaign.total_sales += 1
                campaign.revenue_generated += float(payment.amount)
                logger.info(f"✅ Estatísticas de remarketing atualizadas: Campanha {campaign.id} | Vendas: {campaign.total_sales} | Receita: R$ {campaign.revenue_generated:.2f}")
            else:
                logger.warning(f"⚠️ Campanha de remarketing {payment.remarketing_campaign_id} não encontrada para payment {payment.id}")
        
        # ============================================================================
        # REGISTRAR COMISSÃO
        # ============================================================================
        from models import Commission
        
        # Verificar se já existe comissão para este pagamento
        existing_commission = Commission.query.filter_by(payment_id=payment.id).first()
        
        if not existing_commission:
            # Calcular e registrar receita da plataforma (split payment automático)
            commission_amount = payment.bot.owner.add_commission(payment.amount)
            
            commission = Commission(
                user_id=payment.bot.owner.id,
                payment_id=payment.id,
                bot_id=payment.bot.id,
                sale_amount=payment.amount,
                commission_amount=commission_amount,
                commission_rate=payment.bot.owner.commission_percentage,
                status='paid',  # Split payment cai automaticamente
                paid_at=get_brazil_time()  # Pago no mesmo momento da venda
            )
            db.session.add(commission)
            
            # Atualizar receita já paga (split automático via SyncPay)
            payment.bot.owner.total_commission_paid += commission_amount
            
            logger.info(f"💰 Receita da plataforma: R$ {commission_amount:.2f} (split automático) - Usuário: {payment.bot.owner.email}")
        
        # ============================================================================
        # GAMIFICAÇÃO V2.0 - ATUALIZAR STREAK, RANKING E CONQUISTAS
        # ============================================================================
        try:
            from gamification import GAMIFICATION_V2_ENABLED, RankingEngine, AchievementChecker, check_and_unlock_achievements
            from gamification_websocket import notify_achievement_unlocked
            
            if GAMIFICATION_V2_ENABLED:
                # Atualizar streak
                payment.bot.owner.update_streak(payment.created_at)
                
                # Recalcular ranking com algoritmo V2
                old_points = payment.bot.owner.ranking_points or 0
                payment.bot.owner.ranking_points = RankingEngine.calculate_points(payment.bot.owner)
                new_points = payment.bot.owner.ranking_points
                
                # Verificar conquistas V2
                new_achievements = AchievementChecker.check_all_achievements(payment.bot.owner)
                
                if new_achievements:
                    logger.info(f"🎉 {len(new_achievements)} conquista(s) V2 desbloqueada(s)!")
                    
                    # Notificar via WebSocket
                    if socketio:
                        for ach in new_achievements:
                            notify_achievement_unlocked(socketio, payment.bot.owner.id, ach)
                
                # Atualizar ligas (pode ser async em produção)
                RankingEngine.update_leagues()
                
                logger.info(f"📊 Gamificação V2: {old_points:,} → {new_points:,} pts")
                
            else:
                # Fallback para sistema V1 (antigo)
                payment.bot.owner.update_streak(payment.created_at)
                payment.bot.owner.ranking_points = payment.bot.owner.calculate_ranking_points()
                new_badges = check_and_unlock_achievements(payment.bot.owner)
                
                if new_badges:
                    logger.info(f"🎉 {len(new_badges)} nova(s) conquista(s) desbloqueada(s)!")
                    
        except Exception as e:
            logger.error(f"❌ Erro na gamificação: {e}")
    
    # ============================================================================
    # ✅ CORREÇÃO CRÍTICA: COMMIT ANTES DE ENVIAR ENTREGÁVEL E META PIXEL
    # ============================================================================
    db.session.commit()
    logger.info(f"🔔 Webhook -> payment {payment.payment_id} atualizado para paid e commitado")
    
    # ============================================================================
    # ✅ SISTEMA DE ASSINATURAS - Criar subscription quando payment confirmado
    # ============================================================================
    if status == 'paid' and getattr(payment, 'has_subscription', False):
        try:
            from internal_logic.services.payment_processor import create_subscription_for_payment
            subscription = create_subscription_for_payment(payment)
            if subscription:
                logger.info(f"✅ Subscription criada para payment {payment.payment_id}")
                db.session.commit()
            else:
                logger.debug(f"Subscription não foi criada para payment {payment.payment_id} (não tem config válida)")
        except Exception as subscription_error:
            logger.error(f"❌ Erro ao criar subscription para payment {payment.payment_id}: {subscription_error}", exc_info=True)
            db.session.rollback()
    
    # ============================================================================
    # ✅ SISTEMA DE ASSINATURAS - Cancelar subscription quando payment refunded/failed
    # ============================================================================
    if status in ['refunded', 'failed', 'cancelled']:
        try:
            from models import Subscription
            from app import remove_user_from_vip_group
            
            subscription = Subscription.query.filter_by(payment_id=payment.id).first()
            if subscription and subscription.status in ['pending', 'active']:
                logger.info(f"🔴 Cancelando subscription {subscription.id} - payment {payment.payment_id} refunded/failed")
                old_status = subscription.status
                subscription.status = 'cancelled'
                subscription.removed_at = datetime.now(timezone.utc)
                subscription.removed_by = 'system_refunded'
                
                # ✅ Tentar remover usuário do grupo se subscription estava ativa
                if old_status == 'active' and subscription.vip_chat_id:
                    try:
                        remove_user_from_vip_group(subscription, max_retries=1)
                    except Exception as remove_error:
                        logger.warning(f"⚠️ Não foi possível remover usuário do grupo: {remove_error}")
                
                db.session.commit()
                logger.info(f"✅ Subscription {subscription.id} cancelada")
        except Exception as cancel_error:
            logger.error(f"❌ Erro ao cancelar subscription para payment {payment.payment_id}: {cancel_error}", exc_info=True)
            db.session.rollback()
    
    # ============================================================================
    # ✅ ENVIAR ENTREGÁVEL E META PIXEL SEMPRE QUE STATUS VIRA 'paid' (CRÍTICO!)
    # ============================================================================
    logger.info(f"🔍 [DIAGNÓSTICO] payment {payment.payment_id}: Verificando deve_enviar_entregavel={deve_enviar_entregavel} | status='{status}'")
    
    if deve_enviar_entregavel:
        # ✅ CRÍTICO: Refresh antes de validar status
        db.session.refresh(payment)
        logger.info(f"✅ [DIAGNÓSTICO] payment {payment.payment_id}: deve_enviar_entregavel=True - VAI ENVIAR ENTREGÁVEL")
        
        # ✅ CRÍTICO: Validar status ANTES de chamar send_payment_delivery
        if payment.status == 'paid':
            logger.info(f"📦 Enviando entregável para payment {payment.payment_id} (status: {payment.status})")
            try:
                from internal_logic.services.payment_processor import send_payment_delivery
                resultado = send_payment_delivery(payment, bot_manager)
                if resultado:
                    logger.info(f"✅ Entregável enviado com sucesso para {payment.payment_id}")
                else:
                    logger.warning(f"⚠️ Falha ao enviar entregável para payment {payment.payment_id}")
            except Exception as delivery_error:
                logger.exception(f"❌ Erro ao enviar entregável: {delivery_error}")
        else:
            logger.error(
                f"❌ ERRO GRAVE: send_payment_delivery chamado com payment.status != 'paid' "
                f"(status atual: {payment.status}, payment_id: {payment.payment_id})"
            )
    else:
        logger.error(f"❌ [DIAGNÓSTICO] payment {payment.payment_id}: deve_enviar_entregavel=False - NÃO VAI ENVIAR ENTREGÁVEL! (status='{status}')")
    
    # ============================================================================
    # ✅ META PIXEL: Purchase NÃO é disparado aqui (webhook/reconciliador)
    # ============================================================================
    # ✅ NOVA ARQUITETURA: Purchase é disparado APENAS quando lead acessa link de entrega
    # ✅ Purchase NÃO dispara quando pagamento é confirmado (PIX pago)
    # ✅ Purchase dispara quando lead RECEBE entregável no Telegram e clica no link (/delivery/<token>)
    # ✅ Isso garante tracking 100% preciso: Purchase = conversão REAL (lead acessou produto)
    logger.info(f"✅ Purchase será disparado apenas quando lead acessar link de entrega: /delivery/<token>")
    
    # ============================================================================
    # ✅ UPSELLS AUTOMÁTICOS - APÓS COMPRA APROVADA
    # ============================================================================
    logger.info(f"🔍 [UPSELLS] Verificando condições: status='{status}', has_config={payment.bot.config is not None if payment.bot else False}, upsells_enabled={payment.bot.config.upsells_enabled if (payment.bot and payment.bot.config) else 'N/A'}")
    
    if status == 'paid' and payment.bot.config and payment.bot.config.upsells_enabled:
        logger.info(f"✅ [UPSELLS] Condições atendidas! Processando upsells para payment {payment.payment_id}")
        # ... (lógica de upsells continua)
    
    return {'status': 'processed'}, 200


# ============================================================================
# FUNÇÃO LEGADA AUXILIAR: Criação de Subscription
# Origem: app.py create_subscription_for_payment
# ============================================================================
def create_subscription_for_payment(payment):
    """
    Cria subscription de forma idempotente quando payment é confirmado
    
    ✅ VALIDAÇÕES:
    1. Verifica se já existe (evita duplicação)
    2. Verifica se payment tem subscription config
    3. Cria com tratamento de race condition
    
    Retorna: Subscription object ou None
    """
    from models import Subscription
    from datetime import datetime, timezone
    from sqlalchemy.exc import IntegrityError
    from utils.subscriptions import normalize_vip_chat_id
    import json
    import logging
    
    logger = logging.getLogger(__name__)
    
    try:
        # ✅ VERIFICAÇÃO 1: Já existe subscription para este payment?
        existing = Subscription.query.filter_by(payment_id=payment.id).first()
        if existing:
            logger.info(f"✅ Subscription já existe para payment {payment.id} (idempotência)")
            return existing
        
        # ✅ VERIFICAÇÃO 2: Payment tem subscription config?
        if not getattr(payment, 'has_subscription', False) or not payment.button_config:
            logger.debug(f"Payment {payment.id} não tem subscription config")
            return None
        
        # ✅ VERIFICAÇÃO 3: Parsear button_config e validar
        try:
            if payment.button_config:
                try:
                    button_config = json.loads(payment.button_config)
                    if not isinstance(button_config, dict):
                        logger.error(f"❌ button_config não é um dict válido para payment {payment.id}")
                        return None
                except json.JSONDecodeError as json_error:
                    logger.error(f"❌ button_config JSON corrompido para payment {payment.id}: {json_error}")
                    return None
            else:
                button_config = {}
            
            subscription_config = button_config.get('subscription', {})
            if not isinstance(subscription_config, dict):
                logger.error(f"❌ subscription_config não é um dict válido para payment {payment.id}")
                return None
            
            if not subscription_config.get('enabled'):
                logger.debug(f"Payment {payment.id} tem button_config mas subscription.enabled = False")
                return None
            
            vip_chat_id = subscription_config.get('vip_chat_id')
            if not vip_chat_id:
                logger.error(f"❌ Payment {payment.id} tem subscription.enabled mas sem vip_chat_id")
                return None
            
            duration_type = subscription_config.get('duration_type', 'days')
            duration_value = int(subscription_config.get('duration_value', 30))
            
            if duration_type not in ['hours', 'days', 'weeks', 'months']:
                logger.error(f"❌ Payment {payment.id} tem duration_type inválido: {duration_type}")
                return None
            
            if duration_value <= 0:
                logger.error(f"❌ Payment {payment.id} tem duration_value inválido: {duration_value}")
                return None
            
            # ✅ Validação de máximo de duration_value (120 meses = 10 anos)
            max_duration = {
                'hours': 87600,  # 10 anos em horas
                'days': 3650,    # 10 anos em dias
                'weeks': 520,    # 10 anos em semanas
                'months': 120    # 10 anos em meses
            }
            max_allowed = max_duration.get(duration_type, 120)
            if duration_value > max_allowed:
                logger.error(
                    f"❌ Payment {payment.id} tem duration_value muito grande: "
                    f"{duration_value} {duration_type} (máximo permitido: {max_allowed} {duration_type})"
                )
                return None
            
        except json.JSONDecodeError as e:
            logger.error(f"❌ Erro ao parsear button_config do payment {payment.id}: {e}")
            return None
        except (ValueError, TypeError) as e:
            logger.error(f"❌ Erro ao validar subscription config do payment {payment.id}: {e}")
            return None
        except Exception as e:
            logger.error(f"❌ Erro ao validar subscription config do payment {payment.id}: {e}")
            return None
        
        # ✅ CORREÇÃO CRÍTICA: Validar retorno de normalize_vip_chat_id() ANTES de criar subscription
        normalized_vip_chat_id = normalize_vip_chat_id(vip_chat_id) if vip_chat_id else None
        if not normalized_vip_chat_id:
            logger.error(
                f"❌ Payment {payment.id} tem vip_chat_id inválido após normalização "
                f"(vip_chat_id original: '{vip_chat_id}'). Subscription não será criada."
            )
            return None
        
        # ✅ CRIAR SUBSCRIPTION (pending - será ativada quando entrar no grupo)
        from internal_logic.core.models import get_brazil_time
        subscription = Subscription(
            payment_id=payment.id,
            bot_id=payment.bot_id,
            telegram_user_id=payment.customer_user_id,
            customer_name=payment.customer_name,
            duration_type=duration_type,
            duration_value=duration_value,
            vip_chat_id=normalized_vip_chat_id,
            vip_group_link=subscription_config.get('vip_group_link'),
            status='pending',
            started_at=None,  # ✅ NULL até entrar no grupo
            expires_at=None   # ✅ NULL até ativar
        )
        
        from internal_logic.core.extensions import db
        db.session.add(subscription)
        db.session.commit()
        
        logger.info(f"✅ Subscription criada (pending) para payment {payment.id} | Chat ID: {vip_chat_id[:20]}... | Duração: {duration_value} {duration_type}")
        return subscription
        
    except IntegrityError as e:
        # ✅ RACE CONDITION: Outro processo criou entre verificação e criação
        db.session.rollback()
        logger.warning(f"⚠️ Subscription já criada por outro processo (race condition) para payment {payment.id}")
        existing = Subscription.query.filter_by(payment_id=payment.id).first()
        if existing:
            return existing
        logger.error(f"❌ IntegrityError mas subscription não encontrada: {e}")
        return None
    except Exception as e:
        db.session.rollback()
        logger.error(f"❌ Erro ao criar subscription para payment {payment.id}: {e}", exc_info=True)
        return None
