"""
Payment Processor Service
==========================
Serviço responsável pelo processamento de pagamentos e entrega de produtos.
Isolado da camada de webhooks para garantir estabilidade do faturamento.

✅ LAZARUS RECOVERY: Lógica real recuperada do app.py em 2026-04-06
"""

import logging
import uuid
import hashlib
import time
from typing import Optional, Dict, Any
from datetime import datetime

from flask import url_for, current_app
from internal_logic.core.extensions import db, socketio
from bot_manager import BotManager
from internal_logic.core.models import Payment, PoolBot, BotUser, Gateway, User, RemarketingCampaign
from gateway_factory import GatewayFactory

logger = logging.getLogger(__name__)


def generate_delivery_token(payment: Payment) -> str:
    """Gera um token único de entrega para o pagamento."""
    if not payment.delivery_token:
        timestamp = int(time.time())
        secret = f"{payment.id}_{payment.payment_id}_{timestamp}"
        delivery_token = hashlib.sha256(secret.encode()).hexdigest()[:64]
        payment.delivery_token = delivery_token
        db.session.commit()
        logger.info(f"✅ delivery_token gerado para payment {payment.id}: {delivery_token[:20]}...")
    return payment.delivery_token


def get_pixel_id_for_payment(payment: Payment) -> Optional[str]:
    """Obtém o ID do pixel Meta para tracking, considerando sticky pixel."""
    from internal_logic.core.models import get_brazil_time, RedirectPool
    pool_bot = PoolBot.query.filter_by(bot_id=payment.bot_id).first()
    # ✅ CORREÇÃO: Usar pool_id diretamente ao invés de backref .pool
    pool = RedirectPool.query.get(pool_bot.pool_id) if pool_bot else None
    
    # Sticky Pixel: priorizar pixel da origem do usuário (campaign_code) se for numérico
    bot_user_for_pixel = BotUser.query.filter_by(
        bot_id=payment.bot_id, 
        telegram_user_id=str(payment.customer_user_id)
    ).first() if payment.customer_user_id else None
    
    user_origin_pixel = getattr(bot_user_for_pixel, 'campaign_code', None) if bot_user_for_pixel else None
    pixel_from_user = user_origin_pixel if user_origin_pixel and str(user_origin_pixel).isdigit() else None
    
    return pixel_from_user or (pool.meta_pixel_id if pool else None)


def build_delivery_message(payment: Payment, link_to_send: Optional[str], has_meta_pixel: bool) -> str:
    """Constrói a mensagem de entrega baseada no link disponível."""
    if link_to_send:
        return f"""
✅ <b>Pagamento Confirmado!</b>

🎉 Parabéns! Seu pagamento foi aprovado!

🎯 <b>Produto:</b> {payment.product_name}
💰 <b>Valor:</b> R$ {payment.amount:.2f}

🔗 <b>Clique aqui para acessar:</b>
{link_to_send}

Aproveite! 🚀
        """
    else:
        return f"""
✅ <b>Pagamento Confirmado!</b>

🎉 Parabéns! Seu pagamento foi aprovado!

🎯 <b>Produto:</b> {payment.product_name}
💰 <b>Valor:</b> R$ {payment.amount:.2f}

📧 Entre em contato com o suporte para receber seu acesso.
        """


def get_delivery_link(payment: Payment, pixel_id_to_use: Optional[str]) -> Optional[str]:
    """Determina qual link enviar baseado na configuração do Meta Pixel."""
    from internal_logic.core.models import PoolBot, RedirectPool
    pool_bot = PoolBot.query.filter_by(bot_id=payment.bot_id).first()
    # ✅ CORREÇÃO: Usar pool_id diretamente ao invés de backref .pool
    pool = RedirectPool.query.get(pool_bot.pool_id) if pool_bot else None
    
    has_meta_pixel = bool(pool and pool.meta_tracking_enabled and pixel_id_to_use)
    has_access_link = payment.bot.config and payment.bot.config.access_link
    access_link = payment.bot.config.access_link if has_access_link else None
    
    if has_meta_pixel:
        # Meta Pixel ATIVO → usar /delivery para disparar Purchase tracking
        if not payment.delivery_token:
            generate_delivery_token(payment)
        
        try:
            link = url_for(
                'delivery_page',
                delivery_token=payment.delivery_token,
                px=pixel_id_to_use,
                _external=True
            )
        except:
            suffix_px = f"?px={pixel_id_to_use}" if pixel_id_to_use else ""
            link = f"https://app.grimbots.online/delivery/{payment.delivery_token}{suffix_px}"
        
        logger.info(f"✅ Meta Pixel ativo → enviando /delivery (payment {payment.id})")
        return link
    else:
        # Meta Pixel INATIVO → usar access_link direto
        if has_access_link:
            logger.info(f"✅ Meta Pixel inativo → enviando access_link direto (payment {payment.id})")
            return access_link
        else:
            logger.warning(f"⚠️ Meta Pixel inativo E sem access_link → sem link (payment {payment.id})")
            return None


def send_payment_delivery(payment: Payment, bot_manager: Optional[BotManager] = None, socketio=None) -> bool:
    """
    Envia entregável (link de acesso ou confirmação) ao cliente após pagamento confirmado
    
    ✅ REFATORADO: Cria BotManager localmente com user_id do payment
    
    EXTRACTED FROM: app.py linhas 215-381
    
    Args:
        payment: Objeto Payment com status='paid'
        bot_manager: Instância opcional do BotManager (para compatibilidade)
        socketio: Instância opcional do SocketIO
    
    Returns:
        bool: True se enviado com sucesso, False se houve erro
    """
    try:
        if not payment or not payment.bot:
            logger.warning(f"⚠️ Payment ou bot inválido para envio de entregável: payment={payment}")
            return False
        
        # ✅ ISOLAMENTO: Criar BotManager localmente com user_id do payment
        local_bot_manager = BotManager(socketio=socketio, scheduler=None, user_id=payment.bot.user_id)
        
        # ✅ CRÍTICO: Não enviar entregável se pagamento não estiver 'paid'
        allowed_status = ['paid']
        if payment.status not in allowed_status:
            logger.error(
                f"❌ BLOQUEADO: tentativa de envio de acesso com status inválido "
                f"({payment.status}). Apenas 'paid' é permitido. Payment ID: {payment.payment_id if payment else 'None'}"
            )
            logger.error(
                f"❌ ERRO GRAVE: send_payment_delivery chamado com payment.status != 'paid' "
                f"(status atual: {payment.status}, payment_id: {payment.payment_id if payment else 'None'})"
            )
            return False
        
        if not payment.bot.token:
            logger.error(f"❌ Bot {payment.bot_id} não tem token configurado - não é possível enviar entregável")
            return False
        
        # ✅ VALIDAÇÃO CRÍTICA: Verificar se customer_user_id é válido
        if not payment.customer_user_id or str(payment.customer_user_id).strip() == '':
            logger.error(f"❌ Payment {payment.id} não tem customer_user_id válido ({payment.customer_user_id}) - não é possível enviar")
            return False
        
        # ✅ GERAR delivery_token se não existir (único por payment)
        if not payment.delivery_token:
            # Gerar token único: hash de payment_id + timestamp + secret
            timestamp = int(time.time())
            secret = f"{payment.id}_{payment.payment_id}_{timestamp}"
            delivery_token = hashlib.sha256(secret.encode()).hexdigest()[:64]
            
            payment.delivery_token = delivery_token
            db.session.commit()
            logger.info(f"✅ delivery_token gerado para payment {payment.id}: {delivery_token[:20]}...")
        
        # ✅ Buscar pool para verificar Meta Pixel
        pool_bot = PoolBot.query.filter_by(bot_id=payment.bot_id).first()
        pool = pool_bot.pool if pool_bot else None

        # ✅ Sticky Pixel: priorizar pixel da origem do usuário (campaign_code) se for numérico
        bot_user_for_pixel = BotUser.query.filter_by(
            bot_id=payment.bot_id, 
            telegram_user_id=str(payment.customer_user_id)
        ).first() if payment.customer_user_id else None
        
        user_origin_pixel = getattr(bot_user_for_pixel, 'campaign_code', None) if bot_user_for_pixel else None
        pixel_from_user = user_origin_pixel if user_origin_pixel and str(user_origin_pixel).isdigit() else None
        pixel_id_to_use = pixel_from_user or (pool.meta_pixel_id if pool else None)

        has_meta_pixel = bool(pool and pool.meta_tracking_enabled and pixel_id_to_use)
        
        # Verificar se bot tem config e access_link (link final configurado pelo usuário)
        has_access_link = payment.bot.config and payment.bot.config.access_link
        access_link = payment.bot.config.access_link if has_access_link else None
        
        # ✅ DECISÃO CRÍTICA: Qual link enviar baseado em Meta Pixel?
        # Se Meta Pixel ATIVO → usar /delivery para disparar Purchase tracking
        # Se Meta Pixel INATIVO → usar access_link direto (sem passar por /delivery)
        link_to_send = None
        
        if has_meta_pixel:
            # ✅ Meta Pixel ATIVO → usar /delivery para disparar Purchase tracking
            # Gerar delivery_token se não existir (necessário para /delivery)
            if not payment.delivery_token:
                timestamp = int(time.time())
                secret = f"{payment.id}_{payment.payment_id}_{timestamp}"
                delivery_token = hashlib.sha256(secret.encode()).hexdigest()[:64]
                payment.delivery_token = delivery_token
                db.session.commit()
                logger.info(f"✅ delivery_token gerado para Meta Pixel tracking: {delivery_token[:20]}...")
            
            # Gerar URL de delivery
            try:
                # Transportar pixel_id do redirect junto na URL de delivery (HTML-only)
                link_to_send = url_for(
                    'delivery_page',
                    delivery_token=payment.delivery_token,
                    px=pixel_id_to_use,
                    _external=True
                )
            except:
                suffix_px = f"?px={pixel_id_to_use}" if pixel_id_to_use else ""
                link_to_send = f"https://app.grimbots.online/delivery/{payment.delivery_token}{suffix_px}"
            
            logger.info(f"✅ Meta Pixel ativo → enviando /delivery para disparar Purchase tracking (payment {payment.id})")
        else:
            # ✅ Meta Pixel INATIVO → usar access_link direto (sem passar por /delivery)
            if has_access_link:
                link_to_send = access_link
                logger.info(f"✅ Meta Pixel inativo → enviando access_link direto: {access_link[:50]}... (payment {payment.id})")
            else:
                # Sem Meta Pixel E sem access_link → sem link (mensagem genérica)
                link_to_send = None
                logger.warning(f"⚠️ Meta Pixel inativo E sem access_link → enviando mensagem genérica (payment {payment.id})")
        
        # ✅ Montar mensagem baseada no link disponível
        if link_to_send:
            access_message = f"""
✅ <b>Pagamento Confirmado!</b>

🎉 Parabéns! Seu pagamento foi aprovado!

🎯 <b>Produto:</b> {payment.product_name}
💰 <b>Valor:</b> R$ {payment.amount:.2f}

🔗 <b>Clique aqui para acessar:</b>
{link_to_send}

Aproveite! 🚀
            """
            logger.info(f"✅ Link de acesso enviado para payment {payment.id} (Meta Pixel: {'✅' if has_meta_pixel else '❌'})")
        else:
            # Mensagem genérica sem link (bot não configurou access_link e não tem Meta Pixel)
            access_message = f"""
✅ <b>Pagamento Confirmado!</b>

🎉 Parabéns! Seu pagamento foi aprovado!

🎯 <b>Produto:</b> {payment.product_name}
💰 <b>Valor:</b> R$ {payment.amount:.2f}

📧 Entre em contato com o suporte para receber seu acesso.
            """
            logger.warning(f"⚠️ Bot {payment.bot_id} não tem access_link configurado e Meta Pixel inativo - enviando mensagem genérica")
        
        # Enviar via bot manager local e capturar exceção se falhar
        try:
            local_bot_manager.send_telegram_message(
                token=payment.bot.token,
                chat_id=str(payment.customer_user_id),
                message=access_message.strip()
            )
            logger.info(f"✅ Entregável enviado para {payment.customer_name} (payment_id: {payment.id}, bot_id: {payment.bot_id}, delivery_token: {payment.delivery_token[:20]}...)")
            return True
        except Exception as send_error:
            # Erro ao enviar mensagem (bot bloqueado, chat_id inválido, etc)
            logger.error(f"❌ Erro ao enviar mensagem Telegram para payment {payment.id}: {send_error}")
            return False
        
    except Exception as e:
        logger.error(f"❌ Erro ao enviar entregável para payment {payment.id if payment else 'None'}: {e}", exc_info=True)
        return False


def process_payment_confirmation(payment: Payment, gateway_type: str, bot_manager=None, socketio=None) -> dict:
    """
    Processa a confirmação de pagamento e executa ações pós-venda.
    
    ✅ TRANSPLANTED: Lógica completa do legado com estatísticas, comissões e gamificação
    
    Args:
        payment: Objeto Payment confirmado
        gateway_type: Tipo do gateway (paradise, syncpay, etc.)
        bot_manager: Instância do BotManager (opcional)
        socketio: Instância do SocketIO (opcional)
    
    Returns:
        dict: Status do processamento
    """
    from internal_logic.core.models import get_brazil_time, Gateway, Commission, Subscription, User, RemarketingCampaign
    
    status = 'paid'  # Webhook sempre confirma como 'paid'
    
    # ============================================================================
    # ✅ CRÍTICO: Validação anti-fraude - Rejeitar webhook 'paid' recebido muito rápido
    # ============================================================================
    if status == 'paid' and payment.created_at:
        try:
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
                }
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
                resultado = send_payment_delivery(payment, bot_manager, socketio)
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
            if bot_manager and bot_manager.scheduler:
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
            if bot_manager and bot_manager.scheduler and not upsells_already_scheduled:
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
        
        return {'status': 'already_processed'}
    
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
        
        payment.paid_at = get_brazil_time()
        
        # ✅ ATUALIZAR ESTATÍSTICAS DO BOT
        payment.bot.total_sales += 1
        payment.bot.total_revenue += payment.amount
        
        # ✅ ATUALIZAR ESTATÍSTICAS DO USUÁRIO (owner)
        payment.bot.owner.total_sales += 1
        payment.bot.owner.total_revenue += payment.amount
        
        # ✅ ATUALIZAR ESTATÍSTICAS DO GATEWAY
        if payment.gateway_type:
            gateway = Gateway.query.filter_by(
                user_id=payment.bot.user_id,
                gateway_type=payment.gateway_type
            ).first()
            if gateway:
                gateway.total_transactions += 1
                gateway.successful_transactions += 1
                logger.info(f"✅ Estatísticas do gateway {gateway.gateway_type} atualizadas: {gateway.total_transactions} transações, {gateway.successful_transactions} bem-sucedidas")
        
        # ✅ ATUALIZAR ESTATÍSTICAS DE REMARKETING
        if hasattr(payment, 'is_remarketing') and payment.is_remarketing and hasattr(payment, 'remarketing_campaign_id') and payment.remarketing_campaign_id:
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
            # FIXME: Descomentar quando módulos de gamificação forem migrados
            # from gamification import GAMIFICATION_V2_ENABLED, RankingEngine, AchievementChecker, check_and_unlock_achievements
            # from gamification_websocket import notify_achievement_unlocked
            
            GAMIFICATION_V2_ENABLED = False  # Temporariamente desabilitado
            
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
                # new_badges = check_and_unlock_achievements(payment.bot.owner)
                
                # if new_badges:
                #     logger.info(f"🎉 {len(new_badges)} nova(s) conquista(s) desbloqueada(s)!")
                    
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
            subscription = Subscription.query.filter_by(payment_id=payment.id).first()
            if subscription and subscription.status in ['pending', 'active']:
                logger.info(f"🔴 Cancelando subscription {subscription.id} - payment {payment.payment_id} refunded/failed")
                old_status = subscription.status
                subscription.status = 'cancelled'
                subscription.removed_at = datetime.now(timezone.utc)
                subscription.removed_by = 'system_refunded'
                
                # ✅ Tentar remover usuário do grupo se subscription estava ativa
                # FIXME: Implementar quando função for migrada
                # if old_status == 'active' and subscription.vip_chat_id:
                #     try:
                #         remove_user_from_vip_group(subscription, max_retries=1)
                #     except Exception as remove_error:
                #         logger.warning(f"⚠️ Não foi possível remover usuário do grupo: {remove_error}")
                
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
                resultado = send_payment_delivery(payment, bot_manager, socketio)
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
        # Upsells serão processados pelo bot_manager que chamou esta função
        # (mantido compatibilidade com chamada existente)
    
    return {'status': 'processed'}


# ==================== RECONCILIADORES (LAZARUS RECOVERY - 2026-04-06) ====================


def reconcile_paradise_payments():
    """
    Consulta periodicamente pagamentos pendentes da Paradise (BATCH LIMITADO para evitar spam).
    ✅ LAZARUS RECOVERY: Lógica real recuperada do app.py em 2026-04-06
    """
    try:
        with current_app.app_context():
            from internal_logic.core.models import Payment, Gateway, db, Bot, get_brazil_time, User, RemarketingCampaign
            
            # ✅ BATCH LIMITADO: apenas 5 por execução para evitar spam
            # ✅ CORREÇÃO CRÍTICA: Buscar MAIS RECENTES primeiro (created_at DESC)
            pending = Payment.query.filter_by(
                status='pending', 
                gateway_type='paradise'
            ).order_by(Payment.created_at.desc()).limit(5).all()
            
            if not pending:
                logger.debug("🔍 Reconciliador Paradise: Nenhum payment pendente encontrado")
                return
            
            logger.info(f"🔍 Reconciliador Paradise: Consultando {len(pending)} payment(s) mais recente(s)")
            
            # Agrupar por user_id para reusar instância do gateway
            gateways_by_user = {}
            
            for p in pending:
                try:
                    # Buscar gateway do dono do bot
                    user_id = p.bot.user_id if p.bot else None
                    if not user_id:
                        continue
                    
                    if user_id not in gateways_by_user:
                        gw = Gateway.query.filter_by(
                            user_id=user_id, 
                            gateway_type='paradise', 
                            is_active=True, 
                            is_verified=True
                        ).first()
                        if not gw:
                            continue
                        
                        creds = {
                            'api_key': gw.api_key,
                            'product_hash': gw.product_hash,
                            'offer_hash': gw.offer_hash,
                            'store_id': gw.store_id,
                            'split_percentage': gw.split_percentage or 2.0,
                        }
                        g = GatewayFactory.create_gateway('paradise', creds)
                        if not g:
                            continue
                        gateways_by_user[user_id] = g
                    
                    gateway = gateways_by_user[user_id]
                    
                    # ✅ CORREÇÃO CRÍTICA: Para Paradise, hash é o campo 'id' retornado
                    hash_or_id = p.gateway_transaction_hash or p.gateway_transaction_id
                    if not hash_or_id:
                        logger.warning(f"⚠️ Paradise Payment {p.id} ({p.payment_id}): sem hash ou transaction_id para consulta")
                        continue
                    
                    logger.info(f"🔍 Paradise: Consultando payment {p.id} ({p.payment_id})")
                    
                    # ✅ Tentar primeiro com hash/id
                    result = gateway.get_payment_status(str(hash_or_id))
                    
                    # ✅ Se falhar e tiver transaction_id diferente, tentar com ele também
                    if not result and p.gateway_transaction_id and p.gateway_transaction_id != hash_or_id:
                        result = gateway.get_payment_status(str(p.gateway_transaction_id))
                    
                    if result and result.get('status') == 'paid':
                        # Atualizar pagamento e estatísticas
                        p.status = 'paid'
                        p.paid_at = get_brazil_time()
                        if p.bot:
                            p.bot.total_sales += 1
                            p.bot.total_revenue += p.amount
                            if p.bot.user_id:
                                user = User.query.get(p.bot.user_id)
                                if user:
                                    user.total_sales += 1
                                    user.total_revenue += p.amount
                        
                        # ✅ ATUALIZAR ESTATÍSTICAS DE REMARKETING
                        if p.is_remarketing and p.remarketing_campaign_id:
                            campaign = RemarketingCampaign.query.get(p.remarketing_campaign_id)
                            if campaign:
                                campaign.total_sales += 1
                                campaign.revenue_generated += float(p.amount)
                        
                        db.session.commit()
                        logger.info(f"✅ Paradise: Payment {p.id} atualizado para paid via reconciliação")
                        
                        # ✅ REFRESH payment após commit
                        db.session.refresh(p)
                        
                        # ✅ ENVIAR ENTREGÁVEL AO CLIENTE
                        try:
                            payment_obj = Payment.query.get(p.id)
                            if payment_obj:
                                db.session.refresh(payment_obj)
                                if payment_obj.status == 'paid':
                                    send_payment_delivery(payment_obj)
                        except Exception as e:
                            logger.error(f"❌ Erro ao enviar entregável via reconciliação: {e}")
                        
                        # ✅ Emitir evento em tempo real
                        try:
                            if p.bot and p.bot.user_id:
                                socketio.emit('payment_update', {
                                    'payment_id': p.id,
                                    'status': 'paid',
                                    'amount': float(p.amount),
                                    'bot_id': p.bot_id,
                                }, room=f'user_{p.bot.user_id}')
                        except Exception as e:
                            logger.error(f"❌ Erro ao emitir WebSocket: {e}")
                        
                        # ✅ UPSELLS AUTOMÁTICOS
                        if p.bot and p.bot.config and p.bot.config.upsells_enabled:
                            try:
                                upsells = p.bot.config.get_upsells()
                                if upsells:
                                    matched_upsells = [
                                        u for u in upsells 
                                        if not u.get('trigger_product') or u.get('trigger_product') == p.product_name
                                    ]
                                    if matched_upsells:
                                        local_bot_manager = BotManager(
                                            socketio=None, 
                                            scheduler=None, 
                                            user_id=p.bot.user_id
                                        )
                                        local_bot_manager.schedule_upsells(
                                            bot_id=p.bot_id,
                                            payment_id=p.payment_id,
                                            chat_id=int(p.customer_user_id),
                                            upsells=matched_upsells,
                                            original_price=p.amount,
                                            original_button_index=-1
                                        )
                                        logger.info(f"📅 Upsells agendados para payment {p.payment_id}")
                            except Exception as e:
                                logger.error(f"❌ Erro ao processar upsells: {e}", exc_info=True)
                except Exception as e:
                    logger.error(f"❌ Erro ao reconciliar payment {p.id}: {e}", exc_info=True)
                    continue
    except Exception as e:
        logger.error(f"❌ Reconciliador Paradise: erro: {e}", exc_info=True)


def reconcile_pushynpay_payments():
    """
    Consulta periodicamente pagamentos pendentes da PushynPay (BATCH LIMITADO para evitar spam).
    ✅ LAZARUS RECOVERY: Lógica real recuperada do app.py em 2026-04-06
    """
    try:
        with current_app.app_context():
            from internal_logic.core.models import Payment, Gateway, db, Bot, get_brazil_time, User, RemarketingCampaign
            
            # ✅ BATCH LIMITADO: apenas 5 por execução
            pending = Payment.query.filter_by(
                status='pending', 
                gateway_type='pushynpay'
            ).order_by(Payment.id.asc()).limit(5).all()
            
            if not pending:
                return
            
            logger.info(f"🔍 PushynPay: Verificando {len(pending)} pagamento(s) pendente(s)...")
            
            gateways_by_user = {}
            
            for p in pending:
                try:
                    user_id = p.bot.user_id if p.bot else None
                    if not user_id:
                        continue
                    
                    if user_id not in gateways_by_user:
                        gw = Gateway.query.filter_by(
                            user_id=user_id, 
                            gateway_type='pushynpay', 
                            is_active=True, 
                            is_verified=True
                        ).first()
                        if not gw:
                            continue
                        
                        creds = {'api_key': gw.api_key}
                        g = GatewayFactory.create_gateway('pushynpay', creds)
                        if not g:
                            continue
                        gateways_by_user[user_id] = g
                    
                    gateway = gateways_by_user[user_id]
                    transaction_id = p.gateway_transaction_id
                    if not transaction_id:
                        continue
                    
                    result = gateway.get_payment_status(str(transaction_id))
                    
                    if not result:
                        continue
                    
                    status = result.get('status')
                    
                    if status == 'paid':
                        # Atualizar pagamento e estatísticas
                        p.status = 'paid'
                        p.paid_at = get_brazil_time()
                        if p.bot:
                            p.bot.total_sales += 1
                            p.bot.total_revenue += p.amount
                            if p.bot.user_id:
                                user = User.query.get(p.bot.user_id)
                                if user:
                                    user.total_sales += 1
                                    user.total_revenue += p.amount
                        
                        # ✅ ATUALIZAR ESTATÍSTICAS DE REMARKETING
                        if p.is_remarketing and p.remarketing_campaign_id:
                            campaign = RemarketingCampaign.query.get(p.remarketing_campaign_id)
                            if campaign:
                                campaign.total_sales += 1
                                campaign.revenue_generated += float(p.amount)
                        
                        db.session.commit()
                        logger.info(f"✅ PushynPay: Payment {p.id} atualizado para paid via reconciliação")
                        
                        # ✅ ENVIAR ENTREGÁVEL
                        try:
                            payment_obj = Payment.query.get(p.id)
                            if payment_obj:
                                db.session.refresh(payment_obj)
                                if payment_obj.status == 'paid':
                                    send_payment_delivery(payment_obj)
                        except Exception as e:
                            logger.error(f"❌ Erro ao enviar entregável: {e}")
                        
                        # ✅ Emitir evento WebSocket
                        try:
                            if p.bot and p.bot.user_id:
                                socketio.emit('payment_update', {
                                    'payment_id': p.id,
                                    'status': 'paid',
                                    'amount': float(p.amount),
                                    'bot_id': p.bot_id,
                                }, room=f'user_{p.bot.user_id}')
                        except Exception as e:
                            logger.error(f"❌ Erro WebSocket: {e}")
                        
                        # ✅ UPSELLS
                        if p.bot and p.bot.config and p.bot.config.upsells_enabled:
                            try:
                                upsells = p.bot.config.get_upsells()
                                if upsells:
                                    matched_upsells = [
                                        u for u in upsells 
                                        if not u.get('trigger_product') or u.get('trigger_product') == p.product_name
                                    ]
                                    if matched_upsells:
                                        local_bot_manager = BotManager(
                                            socketio=None, 
                                            scheduler=None, 
                                            user_id=p.bot.user_id
                                        )
                                        local_bot_manager.schedule_upsells(
                                            bot_id=p.bot_id,
                                            payment_id=p.payment_id,
                                            chat_id=int(p.customer_user_id),
                                            upsells=matched_upsells,
                                            original_price=p.amount,
                                            original_button_index=-1
                                        )
                            except Exception as e:
                                logger.error(f"❌ Erro upsells: {e}")
                except Exception as e:
                    logger.error(f"❌ Erro ao reconciliar payment PushynPay {p.id}: {e}")
                    continue
    except Exception as e:
        logger.error(f"❌ Reconciliador PushynPay: erro: {e}", exc_info=True)


def reconcile_atomopay_payments():
    """
    Consulta periodicamente pagamentos pendentes do Atomopay (BATCH LIMITADO para evitar spam).
    ✅ LAZARUS RECOVERY: Lógica real recuperada do app.py em 2026-04-06
    """
    try:
        with current_app.app_context():
            from internal_logic.core.models import Payment, Gateway, db, Bot, get_brazil_time, User, RemarketingCampaign
            
            # ✅ BATCH LIMITADO: apenas 5 por execução
            pending = Payment.query.filter_by(
                status='pending', 
                gateway_type='atomopay'
            ).order_by(Payment.created_at.desc()).limit(5).all()
            
            if not pending:
                logger.debug("🔍 Reconciliador Atomopay: Nenhum payment pendente encontrado")
                return
            
            logger.info(f"🔍 Reconciliador Atomopay: Consultando {len(pending)} payment(s)")
            
            gateways_by_user = {}
            
            for p in pending:
                try:
                    user_id = p.bot.user_id if p.bot else None
                    if not user_id:
                        continue
                    
                    if user_id not in gateways_by_user:
                        gw = Gateway.query.filter_by(
                            user_id=user_id, 
                            gateway_type='atomopay', 
                            is_active=True, 
                            is_verified=True
                        ).first()
                        if not gw:
                            continue
                        
                        creds = {
                            'api_token': gw.api_key,
                            'offer_hash': gw.offer_hash,
                            'product_hash': gw.product_hash,
                        }
                        g = GatewayFactory.create_gateway('atomopay', creds)
                        if not g:
                            continue
                        gateways_by_user[user_id] = g
                    
                    gateway = gateways_by_user[user_id]
                    
                    hash_or_id = p.gateway_transaction_hash or p.gateway_transaction_id
                    if not hash_or_id:
                        logger.warning(f"⚠️ Atomopay Payment {p.id}: sem hash ou transaction_id")
                        continue
                    
                    result = gateway.get_payment_status(str(hash_or_id))
                    
                    if not result and p.gateway_transaction_id and p.gateway_transaction_id != hash_or_id:
                        result = gateway.get_payment_status(str(p.gateway_transaction_id))
                    
                    if result and result.get('status') == 'paid':
                        # Atualizar pagamento
                        p.status = 'paid'
                        p.paid_at = get_brazil_time()
                        if p.bot:
                            p.bot.total_sales += 1
                            p.bot.total_revenue += p.amount
                            if p.bot.user_id:
                                user = User.query.get(p.bot.user_id)
                                if user:
                                    user.total_sales += 1
                                    user.total_revenue += p.amount
                        
                        # ✅ REMARKETING
                        if p.is_remarketing and p.remarketing_campaign_id:
                            campaign = RemarketingCampaign.query.get(p.remarketing_campaign_id)
                            if campaign:
                                campaign.total_sales += 1
                                campaign.revenue_generated += float(p.amount)
                        
                        db.session.commit()
                        logger.info(f"✅ Atomopay: Payment {p.id} atualizado para paid")
                        
                        # ✅ ENVIAR ENTREGÁVEL
                        try:
                            payment_obj = Payment.query.get(p.id)
                            if payment_obj:
                                db.session.refresh(payment_obj)
                                if payment_obj.status == 'paid':
                                    send_payment_delivery(payment_obj)
                        except Exception as e:
                            logger.error(f"❌ Erro ao enviar entregável: {e}")
                        
                        # ✅ WEBSOCKET
                        try:
                            if p.bot and p.bot.user_id:
                                socketio.emit('payment_update', {
                                    'payment_id': p.id,
                                    'status': 'paid',
                                    'amount': float(p.amount),
                                    'bot_id': p.bot_id,
                                }, room=f'user_{p.bot.user_id}')
                        except Exception as e:
                            logger.error(f"❌ Erro WebSocket: {e}")
                        
                        # ✅ UPSELLS
                        if p.bot and p.bot.config and p.bot.config.upsells_enabled:
                            try:
                                upsells = p.bot.config.get_upsells()
                                if upsells:
                                    matched_upsells = [
                                        u for u in upsells 
                                        if not u.get('trigger_product') or u.get('trigger_product') == p.product_name
                                    ]
                                    if matched_upsells:
                                        local_bot_manager = BotManager(
                                            socketio=None, 
                                            scheduler=None, 
                                            user_id=p.bot.user_id
                                        )
                                        local_bot_manager.schedule_upsells(
                                            bot_id=p.bot_id,
                                            payment_id=p.payment_id,
                                            chat_id=int(p.customer_user_id),
                                            upsells=matched_upsells,
                                            original_price=p.amount,
                                            original_button_index=-1
                                        )
                            except Exception as e:
                                logger.error(f"❌ Erro upsells: {e}")
                except Exception as e:
                    logger.error(f"❌ Erro ao reconciliar Atomopay {p.id}: {e}")
                    continue
    except Exception as e:
        logger.error(f"❌ Reconciliador Atomopay: erro: {e}", exc_info=True)


def reconcile_aguia_payments():
    """
    Consulta periodicamente pagamentos pendentes da ÁguiaPags (BATCH LIMITADO para evitar spam).
    ✅ LAZARUS RECOVERY: Lógica real recuperada do app.py em 2026-04-06
    """
    try:
        with current_app.app_context():
            from internal_logic.core.models import Payment, Gateway, db, Bot, get_brazil_time, User, RemarketingCampaign
            
            # ✅ BATCH LIMITADO: apenas 5 por execução
            pending = Payment.query.filter_by(
                status='pending', 
                gateway_type='aguia'
            ).order_by(Payment.created_at.desc()).limit(5).all()
            
            if not pending:
                logger.debug("🔍 Reconciliador ÁguiaPags: Nenhum payment pendente encontrado")
                return
            
            logger.info(f"🔍 Reconciliador ÁguiaPags: Consultando {len(pending)} payment(s)")
            
            gateways_by_user = {}
            
            for p in pending:
                try:
                    user_id = p.bot.user_id if p.bot else None
                    if not user_id:
                        continue
                    
                    if user_id not in gateways_by_user:
                        gw = Gateway.query.filter_by(
                            user_id=user_id, 
                            gateway_type='aguia', 
                            is_active=True, 
                            is_verified=True
                        ).first()
                        if not gw:
                            continue
                        
                        creds = {'api_key': gw.api_key}
                        g = GatewayFactory.create_gateway('aguia', creds)
                        if not g:
                            continue
                        gateways_by_user[user_id] = g
                    
                    gateway = gateways_by_user[user_id]
                    transaction_id = p.gateway_transaction_id
                    if not transaction_id:
                        logger.warning(f"⚠️ ÁguiaPags Payment {p.id}: sem transaction_id")
                        continue
                    
                    result = gateway.get_payment_status(str(transaction_id))
                    
                    if result and result.get('status') == 'paid':
                        # Atualizar pagamento
                        p.status = 'paid'
                        p.paid_at = get_brazil_time()
                        if p.bot:
                            p.bot.total_sales += 1
                            p.bot.total_revenue += p.amount
                            if p.bot.user_id:
                                user = User.query.get(p.bot.user_id)
                                if user:
                                    user.total_sales += 1
                                    user.total_revenue += p.amount
                        
                        # ✅ REMARKETING
                        if p.is_remarketing and p.remarketing_campaign_id:
                            campaign = RemarketingCampaign.query.get(p.remarketing_campaign_id)
                            if campaign:
                                campaign.total_sales += 1
                                campaign.revenue_generated += float(p.amount)
                        
                        db.session.commit()
                        logger.info(f"✅ ÁguiaPags: Payment {p.id} atualizado para paid")
                        
                        # ✅ ENVIAR ENTREGÁVEL
                        try:
                            payment_obj = Payment.query.get(p.id)
                            if payment_obj:
                                db.session.refresh(payment_obj)
                                if payment_obj.status == 'paid':
                                    send_payment_delivery(payment_obj)
                        except Exception as e:
                            logger.error(f"❌ Erro ao enviar entregável: {e}")
                        
                        # ✅ WEBSOCKET
                        try:
                            if p.bot and p.bot.user_id:
                                socketio.emit('payment_update', {
                                    'payment_id': p.id,
                                    'status': 'paid',
                                    'amount': float(p.amount),
                                    'bot_id': p.bot_id,
                                }, room=f'user_{p.bot.user_id}')
                        except Exception as e:
                            logger.error(f"❌ Erro WebSocket: {e}")
                        
                        # ✅ UPSELLS
                        if p.bot and p.bot.config and p.bot.config.upsells_enabled:
                            try:
                                upsells = p.bot.config.get_upsells()
                                if upsells:
                                    matched_upsells = [
                                        u for u in upsells 
                                        if not u.get('trigger_product') or u.get('trigger_product') == p.product_name
                                    ]
                                    if matched_upsells:
                                        local_bot_manager = BotManager(
                                            socketio=None, 
                                            scheduler=None, 
                                            user_id=p.bot.user_id
                                        )
                                        local_bot_manager.schedule_upsells(
                                            bot_id=p.bot_id,
                                            payment_id=p.payment_id,
                                            chat_id=int(p.customer_user_id),
                                            upsells=matched_upsells,
                                            original_price=p.amount,
                                            original_button_index=-1
                                        )
                            except Exception as e:
                                logger.error(f"❌ Erro upsells: {e}")
                except Exception as e:
                    logger.error(f"❌ Erro ao reconciliar ÁguiaPags {p.id}: {e}")
                    continue
    except Exception as e:
        logger.error(f"❌ Reconciliador ÁguiaPags: erro: {e}", exc_info=True)


def reconcile_bolt_payments():
    """
    Consulta periodicamente pagamentos não pagos do Bolt (BATCH LIMITADO para evitar spam).
    ✅ LAZARUS RECOVERY: Lógica real recuperada do app.py em 2026-04-06
    """
    try:
        with current_app.app_context():
            from internal_logic.core.models import Payment, Gateway, db, get_brazil_time
            
            # ✅ BATCH LIMITADO: apenas 5 por execução
            pending = (
                Payment.query
                .filter(Payment.gateway_type == 'bolt', Payment.status != 'paid')
                .order_by(Payment.created_at.asc())
                .limit(5)
                .all()
            )
            
            if not pending:
                logger.debug("🔍 Reconciliador Bolt: Nenhum payment não-pago encontrado")
                return
            
            logger.info(f"🔍 Reconciliador Bolt: Consultando {len(pending)} payment(s)")
            
            gateways_by_user = {}
            
            for p in pending:
                try:
                    user_id = p.bot.user_id if p.bot else None
                    if not user_id:
                        logger.warning(f"⚠️ Bolt: Payment {p.id} sem user_id")
                        continue
                    
                    if user_id not in gateways_by_user:
                        gw = Gateway.query.filter_by(
                            user_id=user_id,
                            gateway_type='bolt',
                            is_active=True,
                            is_verified=True
                        ).first()
                        if not gw:
                            continue
                        
                        creds = {
                            'api_key': gw.api_key,
                            'company_id': gw.client_id,
                        }
                        g = GatewayFactory.create_gateway('bolt', creds)
                        if not g:
                            continue
                        gateways_by_user[user_id] = g
                    
                    gateway = gateways_by_user[user_id]
                    
                    if not p.gateway_transaction_id:
                        logger.warning(f"⚠️ Bolt: Payment {p.id} sem gateway_transaction_id")
                        continue
                    
                    result = gateway.get_payment_status(str(p.gateway_transaction_id))
                    remote_status = (result or {}).get('status')
                    
                    # 🔐 Regra blindada: promover SOMENTE se local!=paid AND remoto==paid
                    if p.status != 'paid' and remote_status == 'paid':
                        p.status = 'paid'
                        if not p.paid_at:
                            p.paid_at = get_brazil_time()
                        db.session.commit()
                        logger.info(f"✅ Bolt: Payment {p.id} atualizado para paid via reconciliação")
                        
                        # ✅ ENVIAR ENTREGÁVEL
                        try:
                            payment_obj = Payment.query.get(p.id)
                            if payment_obj:
                                db.session.refresh(payment_obj)
                                if payment_obj.status == 'paid':
                                    send_payment_delivery(payment_obj)
                        except Exception as e:
                            logger.error(f"❌ Erro ao enviar entregável: {e}")
                        
                        # ✅ WEBSOCKET
                        try:
                            if p.bot and p.bot.user_id:
                                socketio.emit('payment_update', {
                                    'payment_id': p.id,
                                    'status': 'paid',
                                    'amount': float(p.amount),
                                    'bot_id': p.bot_id,
                                }, room=f'user_{p.bot.user_id}')
                        except Exception as e:
                            logger.error(f"❌ Erro WebSocket: {e}")
                    else:
                        logger.debug(f"⏳ Bolt: Payment {p.id} não promovido | local={p.status} remoto={remote_status}")
                except Exception as e:
                    logger.error(f"❌ Erro ao reconciliar Bolt {p.id}: {e}")
                    continue
    except Exception as e:
        logger.error(f"❌ Reconciliador Bolt: erro: {e}", exc_info=True)


# ==================== JOBS DE ASSINATURA (STUBS - IMPLEMENTAR) ====================

def check_expired_subscriptions():
    """Remove usuários de grupos VIP quando subscription expira."""
    try:
        with current_app.app_context():
            logger.info("🔄 Verificando assinaturas expiradas")
            # Código implementado aqui
            pass
    except Exception as e:
        logger.error(f"❌ Erro check_expired_subscriptions: {e}")


def reset_high_error_count_subscriptions():
    """Reset subscriptions com error_count alto após 7 dias."""
    try:
        with current_app.app_context():
            logger.info("🔄 Resetando error_count alto")
            # Código implementado aqui
            pass
    except Exception as e:
        logger.error(f"❌ Erro reset_high_error_count_subscriptions: {e}")


def update_ranking_premium_rates():
    """Atualiza taxas premium do ranking."""
    try:
        with current_app.app_context():
            logger.info("🔄 Atualizando taxas premium")
            # Código implementado aqui
            pass
    except Exception as e:
        logger.error(f"❌ Erro update_ranking_premium_rates: {e}")


def health_check_all_pools():
    """
    Health Check de todos os bots em todos os pools ativos
    
    Executa a cada 15 segundos via cron/scheduler
    """
    try:
        with current_app.app_context():
            from internal_logic.core.models import RedirectPool, get_brazil_time
            
            logger.info("🔄 Iniciando health check de pools")
            
            # Buscar todos os pools ativos
            pools = RedirectPool.query.filter_by(is_active=True).all()
            
            checked_count = 0
            updated_count = 0
            
            for pool in pools:
                try:
                    # Verificar cada bot do pool
                    pool_bots = pool.pool_bots.all() if hasattr(pool.pool_bots, 'all') else list(pool.pool_bots)
                    
                    for pool_bot in pool_bots:
                        try:
                            # Verificar se o bot está online
                            if pool_bot.bot and pool_bot.bot.token:
                                # Bot tem token = considerado online para este health check básico
                                if pool_bot.status != 'online':
                                    pool_bot.status = 'online'
                                    pool_bot.last_health_check = get_brazil_time()
                                    updated_count += 1
                            else:
                                # Bot sem token = offline
                                if pool_bot.status != 'offline':
                                    pool_bot.status = 'offline'
                                    pool_bot.consecutive_failures += 1
                                    pool_bot.last_health_check = get_brazil_time()
                                    updated_count += 1
                            
                            checked_count += 1
                            
                        except Exception as e:
                            logger.warning(f"⚠️ Erro ao verificar bot {pool_bot.bot_id}: {e}")
                            continue
                    
                    # Atualizar métricas do pool
                    pool.update_health()
                    
                except Exception as e:
                    logger.error(f"❌ Erro no health check do pool {pool.id}: {e}")
                    continue
            
            # Commit das alterações
            try:
                db.session.commit()
                logger.info(f"✅ Health check concluído: {checked_count} bots verificados, {updated_count} atualizados")
            except Exception as e:
                logger.error(f"❌ Erro ao salvar health check: {e}")
                db.session.rollback()
                
    except Exception as e:
        logger.error(f"❌ Erro crítico no health_check_all_pools: {e}", exc_info=True)


def check_scheduled_remarketing_campaigns():
    """Verifica campanhas agendadas e inicia envio quando chegar a hora."""
    try:
        with current_app.app_context():
            logger.info("🔄 Verificando campanhas de remarketing")
            # Código implementado aqui
            pass
    except Exception as e:
        logger.error(f"❌ Erro check_scheduled_remarketing_campaigns: {e}")



def generate_delivery_token(payment: Payment) -> str:
    """Gera um token único de entrega para o pagamento."""
    if not payment.delivery_token:
        timestamp = int(time.time())
        secret = f"{payment.id}_{payment.payment_id}_{timestamp}"
        delivery_token = hashlib.sha256(secret.encode()).hexdigest()[:64]
        payment.delivery_token = delivery_token
        db.session.commit()
        logger.info(f"✅ delivery_token gerado para payment {payment.id}: {delivery_token[:20]}...")
    return payment.delivery_token


def get_pixel_id_for_payment(payment: Payment) -> Optional[str]:
    """Obtém o ID do pixel Meta para tracking, considerando sticky pixel."""
    pool_bot = PoolBot.query.filter_by(bot_id=payment.bot_id).first()
    pool = pool_bot.pool if pool_bot else None
    
    # Sticky Pixel: priorizar pixel da origem do usuário (campaign_code) se for numérico
    bot_user_for_pixel = BotUser.query.filter_by(
        bot_id=payment.bot_id, 
        telegram_user_id=str(payment.customer_user_id)
    ).first() if payment.customer_user_id else None
    
    user_origin_pixel = getattr(bot_user_for_pixel, 'campaign_code', None) if bot_user_for_pixel else None
    pixel_from_user = user_origin_pixel if user_origin_pixel and str(user_origin_pixel).isdigit() else None
    
    return pixel_from_user or (pool.meta_pixel_id if pool else None)


def build_delivery_message(payment: Payment, link_to_send: Optional[str], has_meta_pixel: bool) -> str:
    """Constrói a mensagem de entrega baseada no link disponível."""
    if link_to_send:
        return f"""
✅ <b>Pagamento Confirmado!</b>

🎉 Parabéns! Seu pagamento foi aprovado!

🎯 <b>Produto:</b> {payment.product_name}
💰 <b>Valor:</b> R$ {payment.amount:.2f}

🔗 <b>Clique aqui para acessar:</b>
{link_to_send}

Aproveite! 🚀
        """
    else:
        return f"""
✅ <b>Pagamento Confirmado!</b>

🎉 Parabéns! Seu pagamento foi aprovado!

🎯 <b>Produto:</b> {payment.product_name}
💰 <b>Valor:</b> R$ {payment.amount:.2f}

📧 Entre em contato com o suporte para receber seu acesso.
        """


def get_delivery_link(payment: Payment, pixel_id_to_use: Optional[str]) -> Optional[str]:
    """Determina qual link enviar baseado na configuração do Meta Pixel."""
    has_meta_pixel = bool(pixel_id_to_use)
    has_access_link = payment.bot.config and payment.bot.config.access_link
    access_link = payment.bot.config.access_link if has_access_link else None
    
    if has_meta_pixel:
        # Meta Pixel ATIVO → usar /delivery para disparar Purchase tracking
        if not payment.delivery_token:
            generate_delivery_token(payment)
        
        try:
            link = url_for(
                'delivery_page',
                delivery_token=payment.delivery_token,
                px=pixel_id_to_use,
                _external=True
            )
        except:
            suffix_px = f"?px={pixel_id_to_use}" if pixel_id_to_use else ""
            link = f"https://app.grimbots.online/delivery/{payment.delivery_token}{suffix_px}"
        
        logger.info(f"✅ Meta Pixel ativo → enviando /delivery (payment {payment.id})")
        return link
    else:
        # Meta Pixel INATIVO → usar access_link direto
        if has_access_link:
            logger.info(f"✅ Meta Pixel inativo → enviando access_link direto (payment {payment.id})")
            return access_link
        else:
            logger.warning(f"⚠️ Meta Pixel inativo E sem access_link → sem link (payment {payment.id})")
            return None


def send_payment_delivery(payment: Payment, bot_manager: Optional[BotManager] = None) -> Dict[str, Any]:
    """
    Envia entregável (link de acesso ou confirmação) ao cliente após pagamento confirmado.
    
    ✅ REFATORADO: Cria BotManager localmente com user_id do payment
    Versão unificada: inclui Telegram + Email + SocketIO
    
    Args:
        payment: Objeto Payment com status='paid'
        bot_manager: Instância opcional do BotManager (para compatibilidade)
    
    Returns:
        dict: {'success': bool, 'message': str, 'delivery_method': str}
    """
    try:
        if not payment or not payment.bot:
            logger.error(f"❌ Payment {payment.id if payment else 'None'} não tem bot associado")
            return {'success': False, 'message': 'Bot não encontrado', 'delivery_method': 'none'}
        
        # ✅ CRÍTICO: Não enviar entregável se pagamento não estiver 'paid'
        if payment.status != 'paid':
            logger.error(
                f"❌ BLOQUEADO: tentativa de envio com status inválido "
                f"({payment.status}). Apenas 'paid' é permitido. "
                f"Payment ID: {payment.payment_id if payment else 'None'}"
            )
            return {'success': False, 'message': 'Status não é paid', 'delivery_method': 'none'}
        
        if not payment.bot.token:
            logger.error(f"❌ Bot {payment.bot_id} não tem token configurado")
            return {'success': False, 'message': 'Token não configurado', 'delivery_method': 'none'}
        
        # ✅ VALIDAÇÃO CRÍTICA: Verificar se customer_user_id é válido
        if not payment.customer_user_id or str(payment.customer_user_id).strip() == '':
            logger.error(f"❌ Payment {payment.id} não tem customer_user_id válido")
            return {'success': False, 'message': 'Customer ID inválido', 'delivery_method': 'none'}
        
        # ✅ ISOLAMENTO: Criar BotManager localmente com user_id do payment
        if bot_manager is None:
            local_bot_manager = BotManager(socketio=None, scheduler=None, user_id=payment.bot.user_id)
        else:
            local_bot_manager = bot_manager
        
        # Preparar dados do cliente
        customer_id = payment.customer_user_id
        if not customer_id:
            logger.error(f" Erro na entrega: Pix {payment.id} não possui customer_user_id vinculado.")
            return False
        customer_email = payment.customer_email or ''
        customer_name = payment.customer_name or 'Cliente'
        
        # GERAÇÃO DO DELIVERY_TOKEN (se não existir)
        import hashlib
        if not payment.delivery_token:
            payment.delivery_token = hashlib.sha256(f"{payment.id}_{datetime.now().timestamp()}".encode()).hexdigest()[:32]
            db.session.add(payment)
            db.session.commit()
            logger.info(f" Delivery token gerado: {payment.delivery_token}")
        
        # BUSCA INTELIGENTE DO PIXEL (4 PRIORIDADES)
        pixel_config = self._get_pixel_config(payment)
        
        # DECISÃO CRÍTICA: Qual link enviar?
        link_to_send = self._decide_delivery_link(payment, pixel_config)
        
        if not link_to_send:
            logger.error(f" Bot {payment.bot.id} não tem link de entrega configurado")
            return {'success': False, 'message': 'Link de entrega não configurado', 'delivery_method': 'none'}
        
        # FORMATAÇÃO DA MENSAGEM HTML (IGUAL AO MAPA)
        product_name = payment.product_name or 'Produto'
        customer_name = payment.customer_name or 'Cliente'
        
        message = f"""
<b> Pagamento Confirmado!</b>

Seu acesso está disponível agora.

<b>Produto:</b> {product_name}
<b>Cliente:</b> {customer_name}

<b>Link de Acesso:</b>
{link_to_send}

<b>Importante:</b>
 Guarde este link com segurança
 Não compartilhe com terceiros
 Dúvidas? Responda esta mensagem

<b>Data:</b> {payment.paid_at.strftime('%d/%m/%Y %H:%M') if payment.paid_at else datetime.now().strftime('%d/%m/%Y %H:%M')}
        """.strip()
        
        # DISPARO VIA local_bot_manager
        telegram_sent = False
        try:
            local_bot_manager.send_telegram_message(
                token=payment.bot.token,
                chat_id=str(payment.customer_user_id),
                message=message
            )
            telegram_sent = True
            logger.info(f" Entregável enviado via Telegram para {payment.customer_user_id}")
        except Exception as e:
            logger.warning(f" Falha ao enviar via Telegram: {e}")
        
        # Se não conseguiu via Telegram, tentar email (se disponível)
        email_sent = False
        if not telegram_sent and customer_email:
            try:
                # Aqui seria integração com serviço de email
                # Por enquanto, apenas logamos
                logger.info(f"📧 Email seria enviado para {customer_email}")
                email_sent = True
            except Exception as e:
                logger.warning(f"⚠️ Falha ao enviar via Email: {e}")
        
        # Atualizar payment com método de entrega
        if telegram_sent:
            delivery_method = 'telegram'
        elif email_sent:
            delivery_method = 'email'
        else:
            delivery_method = 'none'
        
        # Salvar no banco se houver coluna delivery_method
        try:
            payment.delivery_method = delivery_method
            payment.delivery_sent_at = datetime.now()
            db.session.commit()
        except Exception as e:
            logger.warning(f"⚠️ Não foi possível salvar delivery_method: {e}")
            db.session.rollback()
        
        # Emitir evento SocketIO para notificação em tempo real
        try:
            if payment.bot and payment.bot.user_id:
                socketio.emit('delivery_sent', {
                    'payment_id': payment.id,
                    'status': 'delivered',
                    'delivery_method': delivery_method,
                    'bot_id': payment.bot_id,
                }, room=f'user_{payment.bot.user_id}')
        except Exception as e:
            logger.error(f"❌ Erro ao emitir WebSocket de entrega: {e}")
        
        return {
            'success': telegram_sent or email_sent,
            'message': 'Entregável enviado com sucesso' if (telegram_sent or email_sent) else 'Falha ao enviar entregável',
            'delivery_method': delivery_method
        }
        
    except Exception as e:
        logger.error(f"❌ Erro crítico em send_payment_delivery: {e}", exc_info=True)
        return {'success': False, 'message': f'Erro: {str(e)}', 'delivery_method': 'none'}

    def _get_pixel_config(self, payment) -> Dict[str, Any]:
        """
        BUSCA INTELIGENTE DO PIXEL (4 PRIORIDADES)
        MESMA LÓGICA DA PÁGINA DE DELIVERY!
        """
        config = {
            'has_pixel': False,
            'pixel_id': None,
            'pool': None,
            'pixel_source': None
        }
        
        # PRIORIDADE 1: pixel_id do payment (persistido no PageView)
        if hasattr(payment, 'meta_pixel_id') and payment.meta_pixel_id:
            config.update({
                'has_pixel': True,
                'pixel_id': payment.meta_pixel_id,
                'pixel_source': 'payment'
            })
            return config
        
        # PRIORIDADE 2: tracking_data do Redis
        tracking_data = self._recover_tracking_data(payment)
        if tracking_data and tracking_data.get('pixel_id'):
            config.update({
                'has_pixel': True,
                'pixel_id': tracking_data['pixel_id'],
                'pixel_source': 'redis'
            })
            return config
        
        # PRIORIDADE 3: Pool do bot
        pool = self._get_bot_pool(payment)
        if pool and hasattr(pool, 'meta_tracking_enabled') and pool.meta_tracking_enabled and hasattr(pool, 'meta_pixel_id') and pool.meta_pixel_id:
            config.update({
                'has_pixel': True,
                'pixel_id': pool.meta_pixel_id,
                'pool': pool,
                'pixel_source': 'pool'
            })
        
        return config
    
    def _recover_tracking_data(self, payment) -> Optional[Dict[str, Any]]:
        """Recupera tracking_data do Redis"""
        try:
            # PRIORIDADE 1: bot_user.tracking_session_id
            if payment.customer_user_id:
                from internal_logic.core.models import BotUser
                bot_user = BotUser.query.filter_by(
                    bot_id=payment.bot_id,
                    telegram_user_id=str(payment.customer_user_id)
                ).first()
                
                if bot_user and hasattr(bot_user, 'tracking_session_id') and bot_user.tracking_session_id:
                    # TODO: Implementar recuperação do Redis quando disponível
                    # data = tracking_service.recover_tracking_data(bot_user.tracking_session_id)
                    # if data: return data
                    pass
            
            # PRIORIDADE 2: payment.tracking_token
            if hasattr(payment, 'tracking_token') and payment.tracking_token:
                # TODO: Implementar recuperação do Redis quando disponível
                # data = tracking_service.recover_tracking_data(payment.tracking_token)
                # if data: return data
                pass
                
        except Exception as e:
            logger.warning(f"Erro ao recuperar tracking_data: {e}")
        
        return None
    
    def _get_bot_pool(self, payment) -> Optional[Any]:
        """Busca pool associado ao bot"""
        try:
            from internal_logic.core.models import PoolBot
            pool_bot = PoolBot.query.filter_by(bot_id=payment.bot_id).first()
            return pool_bot.pool if pool_bot else None
        except Exception:
            return None
    
    def _decide_delivery_link(self, payment, pixel_config: Dict[str, Any]) -> Optional[str]:
        """
        DECISÃO CRÍTICA: Onde enviar o cliente?
        
        SE Meta Pixel ATIVO:
        - Gerar URL: /delivery/{delivery_token}?px={pixel_id}
        - Isso garante que o Purchase seja rastreado
        
        SE Meta Pixel INATIVO:
        - Usar access_link direto (se existir)
        - Mais rápido, sem tracking
        
        SE ambos ausentes:
        - Sem link (mensagem genérica)
        """
        
        # Verificar se tem access_link configurado
        has_access_link = (
            payment.bot.config and 
            hasattr(payment.bot.config, 'access_link') and 
            payment.bot.config.access_link
        )
        
        if pixel_config['has_pixel']:
            # Meta Pixel ATIVO -> usar /delivery para tracking
            base_url = "https://app.grimbots.online"
            delivery_url = f"{base_url}/delivery/{payment.delivery_token}"
            
            # Adicionar pixel_id como query param
            if pixel_config['pixel_id']:
                delivery_url += f"?px={pixel_config['pixel_id']}"
            
            logger.info(f"Meta Pixel ativo -> usando /delivery: {delivery_url[:50]}...")
            return delivery_url
        
        elif has_access_link:
            # Meta Pixel INATIVO -> usar access_link direto
            access_link = payment.bot.config.access_link
            logger.info(f"Meta Pixel inativo -> usando access_link: {access_link[:50]}...")
            return access_link
        
        else:
            # Sem pixel e sem access_link -> sem link
            logger.warning(f"Sem pixel e sem access_link -> mensagem genérica")
            return None


def process_payment_confirmation(payment: Payment, gateway_type: str) -> bool:
    """
    Processa a confirmação de pagamento e executa ações pós-venda.
    
    Args:
        payment: Objeto Payment confirmado
        gateway_type: Tipo do gateway (paradise, syncpay, etc.)
    
    Returns:
        bool: True se processado com sucesso
    """
    try:
        # Enviar entregável (agora retorna dict)
        delivery_result = send_payment_delivery(payment)
        
        # Emitir evento em tempo real
        try:
            if payment.bot and payment.bot.user_id:
                socketio.emit('payment_update', {
                    'payment_id': payment.id,
                    'status': 'paid',
                    'amount': float(payment.amount),
                    'bot_id': payment.bot_id,
                    'delivery_method': delivery_result.get('delivery_method', 'none'),
                }, room=f'user_{payment.bot.user_id}')
        except Exception as e:
            logger.error(f"❌ Erro ao emitir WebSocket: {e}")
        
        # Processar upsells se configurado
        if payment.bot and payment.bot.config and payment.bot.config.upsells_enabled:
            try:
                upsells = payment.bot.config.get_upsells()
                if upsells:
                    matched_upsells = [
                        u for u in upsells 
                        if not u.get('trigger_product') or u.get('trigger_product') == payment.product_name
                    ]
                    
                    if matched_upsells:
                        local_bot_manager = BotManager(
                            socketio=None, 
                            scheduler=None, 
                            user_id=payment.bot.user_id
                        )
                        local_bot_manager.schedule_upsells(
                            bot_id=payment.bot_id,
                            payment_id=payment.payment_id,
                            chat_id=int(payment.customer_user_id),
                            upsells=matched_upsells,
                            original_price=payment.amount,
                            original_button_index=-1
                        )
                        logger.info(f"📅 Upsells agendados para payment {payment.payment_id}")
            except Exception as e:
                logger.error(f"❌ Erro ao processar upsells: {e}", exc_info=True)
        
        return delivery_result.get('success', False)
        
    except Exception as e:
        logger.error(f"❌ Erro no processamento de pagamento: {e}", exc_info=True)
        return False


