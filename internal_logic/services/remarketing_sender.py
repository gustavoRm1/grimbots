"""
Remarketing Sender Service
==========================
Servico para envio de campanhas de remarketing em background.
Extraido do BotManager (Fase 3). Preserva o fluxo legado:
  - Path A: enqueue_jobs em thread -> Redis list -> _remarketing_worker_loop
  - Path B: fallback send_campaign em thread direto (envio sincrono com rate limit)
  - send_campaign_with_limit: wrapper com semaforo e concorrencia

Modo de uso (delegacao do BotManager):
  sender = RemarketingSender(user_id, send_message_func)
  sender.send_remarketing_campaign(campaign_id, bot_token)
  sender.start_remarketing_worker(bot_id=..., bot_token=...)
"""

import threading
import logging
import time
import json
import random
from typing import Dict, Any, Optional, List, Callable

logger = logging.getLogger(__name__)


class RemarketingSender:
    """Encapsula envio de campanhas de remarketing e workers de fila"""

    def __init__(
        self,
        user_id: int,
        send_message_func: Callable,
    ):
        self.user_id = user_id
        self.send_message_func = send_message_func

        # Controle de concorrencia
        self.remarketing_semaphore = threading.BoundedSemaphore(15)
        self.remarketing_queue: list = []
        self.active_remarketing_campaigns: set = set()

        # Workers por bot (Path A: Redis queue polling)
        self._remarketing_workers_lock = threading.Lock()
        self._remarketing_workers: Dict[int, Dict[str, Any]] = {}

    # ------------------------------------------------------------------ #
    #  Metodos publicos (delegados do BotManager)
    # ------------------------------------------------------------------ #

    def send_remarketing_campaign(self, campaign_id: int, bot_token: str) -> None:
        """Envia campanha de remarketing em background"""
        try:
            from internal_logic.core.redis_manager import get_redis_connection
            from flask import current_app
            from internal_logic.core.extensions import db, socketio
            from internal_logic.core.models import (
                RemarketingCampaign, BotUser, Payment,
                RemarketingBlacklist, get_brazil_time, Bot
            )
            from datetime import timedelta

            def enqueue_jobs():
                with current_app.app_context():
                    campaign = db.session.get(RemarketingCampaign, campaign_id)
                    if not campaign:
                        logger.warning(f"Remarketing enqueue abortado: campaign_id={campaign_id} nao encontrada")
                        return

                    campaign.status = 'sending'
                    campaign.started_at = get_brazil_time()
                    db.session.commit()

                    redis_conn = get_redis_connection()
                    queue_key = f"gb:{self.user_id}:remarketing:queue:{campaign.bot_id}"
                    sent_set_key = f"remarketing:sent:{campaign.id}"
                    stats_key = f"remarketing:stats:{campaign.id}"

                    contact_limit = get_brazil_time() - timedelta(days=campaign.days_since_last_contact)
                    query = BotUser.query.filter_by(bot_id=campaign.bot_id, archived=False)
                    if campaign.days_since_last_contact > 0:
                        query = query.filter(BotUser.last_interaction <= contact_limit)

                    blacklist_ids = db.session.query(RemarketingBlacklist.telegram_user_id).filter_by(
                        bot_id=campaign.bot_id
                    ).all()
                    blacklist_ids = [b[0] for b in blacklist_ids if b[0]]
                    if blacklist_ids:
                        query = query.filter(~BotUser.telegram_user_id.in_(blacklist_ids))

                    target_audience = campaign.target_audience
                    if target_audience == 'all':
                        pass
                    elif target_audience == 'buyers':
                        buyer_ids = db.session.query(Payment.customer_user_id).filter(
                            Payment.bot_id == campaign.bot_id,
                            Payment.status == 'paid'
                        ).distinct().all()
                        buyer_ids = [b[0] for b in buyer_ids if b[0]]
                        if buyer_ids:
                            query = query.filter(BotUser.telegram_user_id.in_(buyer_ids))
                        else:
                            campaign.total_targets = 0
                            campaign.status = 'completed'
                            campaign.completed_at = get_brazil_time()
                            db.session.commit()
                            return
                    elif target_audience == 'downsell_buyers':
                        downsell_ids = db.session.query(Payment.customer_user_id).filter(
                            Payment.bot_id == campaign.bot_id,
                            Payment.status == 'paid',
                            Payment.is_downsell == True
                        ).distinct().all()
                        downsell_ids = [b[0] for b in downsell_ids if b[0]]
                        if downsell_ids:
                            query = query.filter(BotUser.telegram_user_id.in_(downsell_ids))
                        else:
                            campaign.total_targets = 0
                            campaign.status = 'completed'
                            campaign.completed_at = get_brazil_time()
                            db.session.commit()
                            return
                    elif target_audience == 'order_bump_buyers':
                        orderbump_ids = db.session.query(Payment.customer_user_id).filter(
                            Payment.bot_id == campaign.bot_id,
                            Payment.status == 'paid',
                            Payment.order_bump_accepted == True
                        ).distinct().all()
                        orderbump_ids = [b[0] for b in orderbump_ids if b[0]]
                        if orderbump_ids:
                            query = query.filter(BotUser.telegram_user_id.in_(orderbump_ids))
                        else:
                            campaign.total_targets = 0
                            campaign.status = 'completed'
                            campaign.completed_at = get_brazil_time()
                            db.session.commit()
                            return
                    elif target_audience == 'upsell_buyers':
                        upsell_ids = db.session.query(Payment.customer_user_id).filter(
                            Payment.bot_id == campaign.bot_id,
                            Payment.status == 'paid',
                            Payment.is_upsell == True
                        ).distinct().all()
                        upsell_ids = [b[0] for b in upsell_ids if b[0]]
                        if upsell_ids:
                            query = query.filter(BotUser.telegram_user_id.in_(upsell_ids))
                        else:
                            campaign.total_targets = 0
                            campaign.status = 'completed'
                            campaign.completed_at = get_brazil_time()
                            db.session.commit()
                            return
                    elif target_audience == 'remarketing_buyers':
                        remarketing_ids = db.session.query(Payment.customer_user_id).filter(
                            Payment.bot_id == campaign.bot_id,
                            Payment.status == 'paid',
                            Payment.is_remarketing == True
                        ).distinct().all()
                        remarketing_ids = [b[0] for b in remarketing_ids if b[0]]
                        if remarketing_ids:
                            query = query.filter(BotUser.telegram_user_id.in_(remarketing_ids))
                        else:
                            campaign.total_targets = 0
                            campaign.status = 'completed'
                            campaign.completed_at = get_brazil_time()
                            db.session.commit()
                            return
                    elif target_audience == 'abandoned_cart':
                        abandoned_ids = db.session.query(Payment.customer_user_id).filter(
                            Payment.bot_id == campaign.bot_id,
                            Payment.status == 'pending'
                        ).distinct().all()
                        abandoned_ids = [b[0] for b in abandoned_ids if b[0]]
                        if abandoned_ids:
                            query = query.filter(BotUser.telegram_user_id.in_(abandoned_ids))
                        else:
                            campaign.total_targets = 0
                            campaign.status = 'completed'
                            campaign.completed_at = get_brazil_time()
                            db.session.commit()
                            return
                    elif target_audience == 'inactive':
                        inactive_limit = get_brazil_time() - timedelta(days=7)
                        query = query.filter(BotUser.last_interaction <= inactive_limit)
                    elif target_audience == 'non_buyers':
                        buyer_ids = db.session.query(Payment.customer_user_id).filter(
                            Payment.bot_id == campaign.bot_id,
                            Payment.status == 'paid'
                        ).distinct().all()
                        buyer_ids = [b[0] for b in buyer_ids if b[0]]
                        if buyer_ids:
                            query = query.filter(~BotUser.telegram_user_id.in_(buyer_ids))
                    else:
                        if campaign.exclude_buyers:
                            buyer_ids = db.session.query(Payment.customer_user_id).filter(
                                Payment.bot_id == campaign.bot_id,
                                Payment.status == 'paid'
                            ).distinct().all()
                            buyer_ids = [b[0] for b in buyer_ids if b[0]]
                            if buyer_ids:
                                query = query.filter(~BotUser.telegram_user_id.in_(buyer_ids))

                    total_leads = query.count()
                    if total_leads == 0:
                        campaign.total_targets = 0
                        campaign.status = 'completed'
                        campaign.completed_at = get_brazil_time()
                        db.session.commit()
                        return

                    enqueued = 0
                    skipped_blacklist = 0
                    skipped_sent = 0
                    skipped_invalid = 0
                    skipped_not_eligible = 0
                    debug_logged = 0
                    debug_mode = False

                    def _is_valid_chat_id(chat_id):
                        try:
                            if chat_id is None:
                                return False
                            chat_int = int(str(chat_id))
                            return chat_int != 0
                        except Exception:
                            return False
                    batch_size = 200
                    offset = 0

                    while offset < total_leads:
                        batch = query.offset(offset).limit(batch_size).all()
                        if not batch:
                            break

                        for lead in batch:
                            if not getattr(lead, 'telegram_user_id', None):
                                skipped_invalid += 1
                                if debug_mode and debug_logged < 10:
                                    logger.info(f"SKIP_ENQUEUE reason=invalid_chat_id campaign_id={campaign.id} bot_id={campaign.bot_id} chat_id={getattr(lead, 'telegram_user_id', None)}")
                                    debug_logged += 1
                                continue
                            if not _is_valid_chat_id(lead.telegram_user_id):
                                skipped_invalid += 1
                                if debug_mode and debug_logged < 10:
                                    logger.info(f"SKIP_ENQUEUE reason=invalid_chat_id campaign_id={campaign.id} bot_id={campaign.bot_id} chat_id={lead.telegram_user_id}")
                                    debug_logged += 1
                                continue

                            blk_key = f"remarketing:blacklist:{campaign.bot_id}"
                            if redis_conn.sismember(blk_key, str(lead.telegram_user_id)):
                                skipped_blacklist += 1
                                if debug_mode and debug_logged < 10:
                                    logger.info(f"SKIP_ENQUEUE reason=blacklist campaign_id={campaign.id} bot_id={campaign.bot_id} chat_id={lead.telegram_user_id}")
                                    debug_logged += 1
                                continue

                            if redis_conn.sismember(sent_set_key, str(lead.telegram_user_id)):
                                skipped_sent += 1
                                if debug_mode and debug_logged < 10:
                                    logger.info(f"SKIP_ENQUEUE reason=already_received campaign_id={campaign.id} bot_id={campaign.bot_id} chat_id={lead.telegram_user_id}")
                                    debug_logged += 1
                                continue

                            if getattr(lead, 'opt_out', False) or getattr(lead, 'unsubscribed', False) or getattr(lead, 'inactive', False):
                                skipped_not_eligible += 1
                                if debug_mode and debug_logged < 10:
                                    logger.info(f"SKIP_ENQUEUE reason=not_eligible campaign_id={campaign.id} bot_id={campaign.bot_id} chat_id={lead.telegram_user_id}")
                                    debug_logged += 1
                                continue

                            bot_obj = Bot.query.get(campaign.bot_id)
                            current_bot_token = bot_obj.telegram_token if bot_obj else None
                            if not current_bot_token:
                                logger.error(f"Bot sem token no enqueue | bot_id={campaign.bot_id} campaign_id={campaign.id} chat_id={lead.telegram_user_id}")
                                skipped_not_eligible += 1
                                continue

                            message = campaign.message.replace('{nome}', lead.first_name or 'Cliente')
                            message = message.replace('{primeiro_nome}', (lead.first_name or 'Cliente').split()[0])

                            remarketing_buttons = []
                            if campaign.buttons:
                                buttons_list = campaign.buttons
                                if isinstance(campaign.buttons, str):
                                    try:
                                        buttons_list = json.loads(campaign.buttons)
                                    except Exception:
                                        buttons_list = []
                                for btn_idx, btn in enumerate(buttons_list):
                                    if btn.get('price') and btn.get('description'):
                                        remarketing_buttons.append({
                                            'text': btn.get('text', 'Comprar'),
                                            'callback_data': f"rmkt_{campaign.id}_{btn_idx}"
                                        })
                                    elif btn.get('url'):
                                        remarketing_buttons.append({
                                            'text': btn.get('text', 'Link'),
                                            'url': btn.get('url')
                                        })

                            job = {
                                'type': 'send',
                                'campaign_id': campaign.id,
                                'bot_id': campaign.bot_id,
                                'telegram_user_id': str(lead.telegram_user_id),
                                'message': message,
                                'media_url': campaign.media_url,
                                'media_type': campaign.media_type,
                                'buttons': remarketing_buttons,
                                'audio_enabled': bool(campaign.audio_enabled),
                                'audio_url': campaign.audio_url or '',
                                'bot_token': current_bot_token
                            }
                            try:
                                redis_conn.rpush(queue_key, json.dumps(job))
                                redis_conn.hincrby(stats_key, 'enqueued', 1)
                                if debug_mode and debug_logged < 10:
                                    logger.info(f"ENQUEUE OK campaign_id={campaign.id} bot_id={campaign.bot_id} chat_id={lead.telegram_user_id}")
                                    debug_logged += 1
                                enqueued += 1
                            except Exception as enqueue_error:
                                logger.warning(f"Falha ao enfileirar job remarketing: campaign_id={campaign.id} chat_id={lead.telegram_user_id} err={enqueue_error}")

                        offset += batch_size

                    if skipped_blacklist:
                        redis_conn.hincrby(stats_key, 'skipped_blacklist', skipped_blacklist)
                    if skipped_sent:
                        redis_conn.hincrby(stats_key, 'skipped_already_received', skipped_sent)
                    if skipped_invalid:
                        redis_conn.hincrby(stats_key, 'skipped_invalid_chat', skipped_invalid)
                    if skipped_not_eligible:
                        redis_conn.hincrby(stats_key, 'skipped_not_eligible', skipped_not_eligible)

                    campaign.total_targets = enqueued
                    db.session.commit()

                    try:
                        socketio.emit('remarketing_progress', {
                            'campaign_id': campaign.id,
                            'sent': campaign.total_sent,
                            'failed': campaign.total_failed,
                            'blocked': campaign.total_blocked,
                            'total': campaign.total_targets,
                            'percentage': 0
                        })
                    except Exception:
                        pass

                    try:
                        redis_conn.rpush(queue_key, json.dumps({'type': 'campaign_done', 'campaign_id': campaign.id}))
                    except Exception:
                        pass

                    logger.info(f"Remarketing jobs enfileirados: campaign_id={campaign.id} bot_id={campaign.bot_id} total={enqueued} queue={queue_key}")

            thread = threading.Thread(target=enqueue_jobs, name=f"remarketing-enqueue-{campaign_id}")
            thread.daemon = True
            thread.start()
            logger.info(f"Remarketing enqueue thread disparada: campaign_id={campaign_id} thread_name={thread.name}")
            return
        except Exception as orchestration_error:
            logger.error(f"Falha no remarketing orchestration (fallback para modo legado): {orchestration_error}", exc_info=True)

        from flask import current_app
        from internal_logic.core.extensions import db, socketio
        from internal_logic.core.models import RemarketingCampaign, BotUser, Payment, RemarketingBlacklist
        from datetime import datetime, timedelta
        import time

        def send_campaign():
            import time
            with current_app.app_context():
                try:
                    campaign = db.session.get(RemarketingCampaign, campaign_id)
                    if not campaign:
                        logger.warning(f"Remarketing abortado: campaign_id={campaign_id} nao encontrada (db.session.get retornou None)")
                        return

                    campaign.status = 'sending'
                    from internal_logic.core.models import get_brazil_time
                    campaign.started_at = get_brazil_time()
                    db.session.commit()

                    logger.info(f"Iniciando envio de remarketing: {campaign.name}")

                    from internal_logic.core.models import get_brazil_time
                    contact_limit = get_brazil_time() - timedelta(days=campaign.days_since_last_contact)

                    query = BotUser.query.filter_by(bot_id=campaign.bot_id, archived=False)

                    if campaign.days_since_last_contact > 0:
                        query = query.filter(BotUser.last_interaction <= contact_limit)

                    blacklist_ids = db.session.query(RemarketingBlacklist.telegram_user_id).filter_by(
                        bot_id=campaign.bot_id
                    ).all()
                    blacklist_ids = [b[0] for b in blacklist_ids if b[0]]
                    if blacklist_ids:
                        query = query.filter(~BotUser.telegram_user_id.in_(blacklist_ids))
                        logger.info(f"Blacklist para bot {campaign.bot_id}: {len(blacklist_ids)} usuarios excluidos da campanha")

                    target_audience = campaign.target_audience

                    if target_audience == 'all':
                        pass
                    elif target_audience == 'buyers':
                        buyer_ids = db.session.query(Payment.customer_user_id).filter(
                            Payment.bot_id == campaign.bot_id,
                            Payment.status == 'paid'
                        ).distinct().all()
                        buyer_ids = [b[0] for b in buyer_ids if b[0]]
                        if buyer_ids:
                            query = query.filter(BotUser.telegram_user_id.in_(buyer_ids))
                        else:
                            leads = []
                            campaign.total_targets = 0
                            db.session.commit()
                            logger.info(f"0 leads elegiveis (nenhum comprador encontrado)")
                            return
                    elif target_audience == 'downsell_buyers':
                        downsell_ids = db.session.query(Payment.customer_user_id).filter(
                            Payment.bot_id == campaign.bot_id,
                            Payment.status == 'paid',
                            Payment.is_downsell == True
                        ).distinct().all()
                        downsell_ids = [b[0] for b in downsell_ids if b[0]]
                        if downsell_ids:
                            query = query.filter(BotUser.telegram_user_id.in_(downsell_ids))
                        else:
                            leads = []
                            campaign.total_targets = 0
                            db.session.commit()
                            logger.info(f"0 leads elegiveis (nenhum comprador via downsell encontrado)")
                            return
                    elif target_audience == 'order_bump_buyers':
                        orderbump_ids = db.session.query(Payment.customer_user_id).filter(
                            Payment.bot_id == campaign.bot_id,
                            Payment.status == 'paid',
                            Payment.order_bump_accepted == True
                        ).distinct().all()
                        orderbump_ids = [b[0] for b in orderbump_ids if b[0]]
                        if orderbump_ids:
                            query = query.filter(BotUser.telegram_user_id.in_(orderbump_ids))
                        else:
                            leads = []
                            campaign.total_targets = 0
                            db.session.commit()
                            logger.info(f"0 leads elegiveis (nenhum comprador com order bump encontrado)")
                            return
                    elif target_audience == 'upsell_buyers':
                        upsell_ids = db.session.query(Payment.customer_user_id).filter(
                            Payment.bot_id == campaign.bot_id,
                            Payment.status == 'paid',
                            Payment.is_upsell == True
                        ).distinct().all()
                        upsell_ids = [b[0] for b in upsell_ids if b[0]]
                        if upsell_ids:
                            query = query.filter(BotUser.telegram_user_id.in_(upsell_ids))
                        else:
                            leads = []
                            campaign.total_targets = 0
                            db.session.commit()
                            logger.info(f"0 leads elegiveis (nenhum comprador via upsell encontrado)")
                            return
                    elif target_audience == 'remarketing_buyers':
                        remarketing_ids = db.session.query(Payment.customer_user_id).filter(
                            Payment.bot_id == campaign.bot_id,
                            Payment.status == 'paid',
                            Payment.is_remarketing == True
                        ).distinct().all()
                        remarketing_ids = [b[0] for b in remarketing_ids if b[0]]
                        if remarketing_ids:
                            query = query.filter(BotUser.telegram_user_id.in_(remarketing_ids))
                        else:
                            leads = []
                            campaign.total_targets = 0
                            db.session.commit()
                            logger.info(f"0 leads elegiveis (nenhum comprador via remarketing encontrado)")
                            return
                    elif target_audience == 'abandoned_cart':
                        abandoned_ids = db.session.query(Payment.customer_user_id).filter(
                            Payment.bot_id == campaign.bot_id,
                            Payment.status == 'pending'
                        ).distinct().all()
                        abandoned_ids = [b[0] for b in abandoned_ids if b[0]]
                        if abandoned_ids:
                            query = query.filter(BotUser.telegram_user_id.in_(abandoned_ids))
                        else:
                            leads = []
                            campaign.total_targets = 0
                            db.session.commit()
                            logger.info(f"0 leads elegiveis (nenhum PIX gerado encontrado)")
                            return
                    elif target_audience == 'inactive':
                        from internal_logic.core.models import get_brazil_time
                        inactive_limit = get_brazil_time() - timedelta(days=7)
                        query = query.filter(BotUser.last_interaction <= inactive_limit)
                    elif target_audience == 'non_buyers':
                        buyer_ids = db.session.query(Payment.customer_user_id).filter(
                            Payment.bot_id == campaign.bot_id,
                            Payment.status == 'paid'
                        ).distinct().all()
                        buyer_ids = [b[0] for b in buyer_ids if b[0]]
                        if buyer_ids:
                            query = query.filter(~BotUser.telegram_user_id.in_(buyer_ids))
                    else:
                        if campaign.exclude_buyers:
                            buyer_ids = db.session.query(Payment.customer_user_id).filter(
                                Payment.bot_id == campaign.bot_id,
                                Payment.status == 'paid'
                            ).distinct().all()
                            buyer_ids = [b[0] for b in buyer_ids if b[0]]
                            if buyer_ids:
                                query = query.filter(~BotUser.telegram_user_id.in_(buyer_ids))

                    total_leads = query.count()
                    campaign.total_targets = total_leads
                    try:
                        db.session.commit()
                        db.session.refresh(campaign)
                    except Exception as commit_error:
                        logger.error(f"Erro ao salvar total_targets: {commit_error}")
                        db.session.rollback()

                    logger.info(f"{campaign.total_targets} leads elegiveis")

                    if total_leads == 0:
                        logger.warning(f"Nenhum lead elegivel para campanha {campaign_id}")
                        campaign.status = 'completed'
                        from internal_logic.core.models import get_brazil_time
                        campaign.completed_at = get_brazil_time()
                        db.session.commit()
                        return

                    active_count = len(self.active_remarketing_campaigns)
                    if active_count <= 5:
                        batch_size = 30
                    elif active_count <= 10:
                        batch_size = 25
                    else:
                        batch_size = 20

                    offset = 0
                    batch_number = 0

                    logger.info(f"Iniciando processamento de {total_leads} leads em batches de {batch_size} (campanhas ativas: {active_count})")

                    while offset < total_leads:
                        batch_number += 1
                        remaining = total_leads - offset
                        batch_expected = min(batch_size, remaining)
                        logger.info(f"[Batch {batch_number}/{((total_leads + batch_size - 1) // batch_size)}] Processando offset {offset}-{offset + batch_expected - 1} de {total_leads} leads")

                        logger.info(f"Remarketing campaign media: campaign_id={campaign.id} media_type={campaign.media_type!r} media_url={campaign.media_url!r}")

                        try:
                            batch = query.offset(offset).limit(batch_size).all()
                        except Exception as query_error:
                            logger.error(f"Erro ao buscar batch {batch_number} (offset {offset}): {query_error}", exc_info=True)
                            offset += batch_size
                            continue

                        if not batch:
                            logger.warning(f"Batch {batch_number} vazio (offset: {offset}), finalizando processamento")
                            break

                        logger.info(f"Batch {batch_number} carregado: {len(batch)} leads encontrados")

                        batch_sent = 0
                        batch_failed = 0
                        batch_blocked = 0
                        consecutive_401_errors = 0
                        max_401_errors = 20
                        first_lead_logged = False

                        for lead in batch:
                            try:
                                if not first_lead_logged:
                                    logger.warning(f"LOOP ATIVO: entrando no envio por lead | campaign_id={campaign.id} bot_id={campaign.bot_id} batch={batch_number} batch_size={len(batch)}")
                                    first_lead_logged = True

                                if not getattr(lead, 'telegram_user_id', None):
                                    batch_failed += 1
                                    logger.warning(f"FALHA: bot={campaign.bot_id} lead_id={getattr(lead, 'id', None)} motivo=missing_telegram_user_id batch={batch_number}")
                                    continue

                                if consecutive_401_errors >= max_401_errors:
                                    logger.error(f"Token do bot {campaign.bot_id} esta INVALIDO ({consecutive_401_errors} erros 401 consecutivos) - PARANDO envio para este bot")
                                    logger.error(f"Acao necessaria: Verificar/atualizar token do bot {campaign.bot_id} no painel")
                                    batch_failed += len(batch) - (batch_sent + batch_failed + batch_blocked)
                                    break

                                is_blocked = db.session.query(RemarketingBlacklist).filter_by(
                                    bot_id=campaign.bot_id,
                                    telegram_user_id=lead.telegram_user_id
                                ).first()

                                if is_blocked:
                                    batch_blocked += 1
                                    logger.info(f"BLOQUEADO: bot={campaign.bot_id} chat_id={lead.telegram_user_id} batch={batch_number}")
                                    continue

                                message = campaign.message.replace('{nome}', lead.first_name or 'Cliente')
                                message = message.replace('{primeiro_nome}', (lead.first_name or 'Cliente').split()[0])

                                remarketing_buttons = []
                                if campaign.buttons:
                                    buttons_list = campaign.buttons
                                    if isinstance(campaign.buttons, str):
                                        import json
                                        try:
                                            buttons_list = json.loads(campaign.buttons)
                                        except:
                                            buttons_list = []

                                    for btn_idx, btn in enumerate(buttons_list):
                                        if btn.get('price') and btn.get('description'):
                                            remarketing_buttons.append({
                                                'text': btn.get('text', 'Comprar'),
                                                'callback_data': f"rmkt_{campaign.id}_{btn_idx}"
                                            })
                                        elif btn.get('url'):
                                            remarketing_buttons.append({
                                                'text': btn.get('text', 'Link'),
                                                'url': btn.get('url')
                                            })

                                logger.warning(f"TENTATIVA_ENVIO: bot={campaign.bot_id} campaign_id={campaign.id} chat_id={lead.telegram_user_id} lead_id={getattr(lead, 'id', None)} media_type={campaign.media_type!r} batch={batch_number}")
                                result = self.send_message_func(
                                    token=bot_token,
                                    chat_id=lead.telegram_user_id,
                                    message=message,
                                    media_url=campaign.media_url,
                                    media_type=campaign.media_type,
                                    buttons=remarketing_buttons
                                )

                                if not first_lead_logged:
                                    first_lead_logged = True

                                if first_lead_logged is True and batch_sent == 0 and batch_failed == 0 and batch_blocked == 0:
                                    logger.warning(f"RETORNO_ENVIO (1 lead do batch): bot={campaign.bot_id} campaign_id={campaign.id} chat_id={lead.telegram_user_id} result_type={type(result).__name__}")

                                if isinstance(result, dict) and result.get('error'):
                                    error_code = result.get('error_code', 0)
                                    error_description = result.get('description', '').lower()

                                    if error_code == 401:
                                        consecutive_401_errors += 1
                                        batch_failed += 1
                                        logger.error(f"Token INVALIDO para bot {campaign.bot_id} (erro 401 #{consecutive_401_errors}/{max_401_errors}) - lead {lead.telegram_user_id}")
                                        if consecutive_401_errors >= max_401_errors:
                                            logger.error(f"Token do bot {campaign.bot_id} esta claramente INVALIDO - PARANDO envio para evitar desperdicio de recursos")
                                            remaining_leads = len(batch) - (batch_sent + batch_failed + batch_blocked)
                                            batch_failed += remaining_leads
                                            break
                                    elif error_code == 403 and ("bot was blocked" in error_description or "forbidden: bot was blocked" in error_description):
                                        batch_blocked += 1
                                        consecutive_401_errors = 0
                                        logger.warning(f"Bot bloqueado pelo usuario {lead.telegram_user_id} (erro 403)")

                                        try:
                                            existing = db.session.query(RemarketingBlacklist).filter_by(
                                                bot_id=campaign.bot_id,
                                                telegram_user_id=lead.telegram_user_id
                                            ).first()

                                            if not existing:
                                                blacklist = RemarketingBlacklist(
                                                    bot_id=campaign.bot_id,
                                                    telegram_user_id=lead.telegram_user_id,
                                                    reason='bot_blocked'
                                                )
                                                db.session.add(blacklist)
                                                try:
                                                    db.session.commit()
                                                    logger.info(f"Usuario {lead.telegram_user_id} adicionado a blacklist do bot {campaign.bot_id} (bloqueado via erro 403)")
                                                except Exception as commit_error:
                                                    logger.error(f"Erro ao commitar blacklist: {commit_error}")
                                                    db.session.rollback()
                                            else:
                                                logger.debug(f"Usuario {lead.telegram_user_id} ja esta na blacklist do bot {campaign.bot_id}")
                                        except Exception as blacklist_error:
                                            logger.warning(f"Erro ao adicionar blacklist: {blacklist_error}")
                                            db.session.rollback()
                                    else:
                                        consecutive_401_errors = 0
                                        batch_failed += 1
                                        logger.warning(f"FALHA: bot={campaign.bot_id} chat_id={lead.telegram_user_id} error_code={error_code} desc={error_description[:120]} batch={batch_number}")
                                elif result:
                                    logger.debug(f"Remarketing enviado com sucesso para {lead.telegram_user_id}")
                                    logger.info(f"ENVIADO: bot={campaign.bot_id} chat_id={lead.telegram_user_id} type={campaign.media_type} batch={batch_number}")
                                    batch_sent += 1
                                    consecutive_401_errors = 0

                                    if campaign.audio_enabled and campaign.audio_url:
                                        try:
                                            audio_result = self.send_message_func(
                                                token=bot_token,
                                                chat_id=lead.telegram_user_id,
                                                message="",
                                                media_url=campaign.audio_url,
                                                media_type='audio',
                                                buttons=None
                                            )
                                            if isinstance(audio_result, dict) and audio_result.get('error'):
                                                logger.warning(f"Audio nao foi enviado para {lead.telegram_user_id} (erro {audio_result.get('error_code', 'desconhecido')})")
                                            elif not audio_result:
                                                logger.warning(f"Audio nao foi enviado para {lead.telegram_user_id} (result=False)")
                                        except Exception as audio_error:
                                            logger.warning(f"Erro ao enviar audio para {lead.telegram_user_id}: {audio_error}")
                                else:
                                    logger.warning(f"FALHA: bot={campaign.bot_id} chat_id={lead.telegram_user_id} result=False batch={batch_number}")
                                    batch_failed += 1

                            except Exception as e:
                                error_msg = str(e).lower()
                                logger.warning(f"Erro ao enviar para {lead.telegram_user_id}: {e}")

                                if "bot was blocked" in error_msg or "forbidden: bot was blocked" in error_msg:
                                    batch_blocked += 1
                                    consecutive_401_errors = 0
                                    try:
                                        existing = db.session.query(RemarketingBlacklist).filter_by(
                                            bot_id=campaign.bot_id,
                                            telegram_user_id=lead.telegram_user_id
                                        ).first()

                                        if not existing:
                                            blacklist = RemarketingBlacklist(
                                                bot_id=campaign.bot_id,
                                                telegram_user_id=lead.telegram_user_id,
                                                reason='bot_blocked'
                                            )
                                            db.session.add(blacklist)
                                            try:
                                                db.session.commit()
                                                logger.info(f"Usuario {lead.telegram_user_id} adicionado a blacklist do bot {campaign.bot_id} (bloqueado)")
                                            except Exception as commit_error:
                                                logger.error(f"Erro ao commitar blacklist: {commit_error}")
                                                db.session.rollback()
                                        else:
                                            logger.debug(f"Usuario {lead.telegram_user_id} ja esta na blacklist do bot {campaign.bot_id}")
                                    except Exception as blacklist_error:
                                        logger.warning(f"Erro ao adicionar blacklist: {blacklist_error}")
                                        db.session.rollback()
                                elif "rate limit" in error_msg or "too many requests" in error_msg or "error_code\":429" in error_msg:
                                    batch_failed += 1
                                    consecutive_401_errors = 0
                                    logger.warning(f"Rate limit do Telegram atingido para {lead.telegram_user_id} - aguardando 1 segundo...")
                                    time.sleep(1)
                                elif "unauthorized" in error_msg or "error_code\":401" in error_msg:
                                    batch_failed += 1
                                    consecutive_401_errors += 1
                                    logger.error(f"Token INVALIDO para bot {campaign.bot_id} (erro 401 #{consecutive_401_errors}/{max_401_errors}) - lead {lead.telegram_user_id}")
                                    if consecutive_401_errors >= max_401_errors:
                                        logger.error(f"Token do bot {campaign.bot_id} esta claramente INVALIDO - PARANDO envio para evitar desperdicio de recursos")
                                elif "chat not found" in error_msg or "error_code\":400" in error_msg:
                                    batch_failed += 1
                                    consecutive_401_errors = 0
                                    logger.warning(f"Chat nao encontrado para lead {lead.telegram_user_id}")
                                elif "user is deactivated" in error_msg:
                                    batch_failed += 1
                                    consecutive_401_errors = 0
                                    logger.warning(f"Usuario desativado: {lead.telegram_user_id}")
                                else:
                                    batch_failed += 1
                                    consecutive_401_errors = 0
                                    logger.warning(f"Erro desconhecido para lead {lead.telegram_user_id}: {e}")

                        try:
                            db.session.refresh(campaign)
                            campaign.total_sent += batch_sent
                            campaign.total_failed += batch_failed
                            campaign.total_blocked += batch_blocked

                            total_in_batch = batch_sent + batch_failed + batch_blocked
                            if total_in_batch > 0:
                                failure_rate = (batch_failed + batch_blocked) / total_in_batch
                                if failure_rate > 0.8:
                                    logger.debug(f"Taxa de falha alta ({failure_rate*100:.1f}%) - pausando por mais tempo...")
                                    time.sleep(2.5)
                                else:
                                    time.sleep(0.8)
                            else:
                                time.sleep(0.8)

                            db.session.commit()
                            db.session.refresh(campaign)

                            progress_pct = round((campaign.total_sent / campaign.total_targets) * 100, 1) if campaign.total_targets > 0 else 0
                            logger.info(f"Batch {batch_number} concluido: {batch_sent} enviados | {batch_failed} falhas | {batch_blocked} bloqueados | Total geral: {campaign.total_sent}/{campaign.total_targets} ({progress_pct}%)")

                        except Exception as commit_error:
                            logger.error(f"Erro ao commitar batch {batch_number}: {commit_error}", exc_info=True)
                            try:
                                db.session.rollback()
                                db.session.refresh(campaign)
                                campaign.total_sent += batch_sent
                                campaign.total_failed += batch_failed
                                campaign.total_blocked += batch_blocked
                                db.session.commit()
                                db.session.refresh(campaign)
                                logger.info(f"Batch {batch_number} recuperado apos rollback: Total {campaign.total_sent}/{campaign.total_targets}")
                            except Exception as retry_error:
                                logger.error(f"Erro critico ao recuperar batch {batch_number}: {retry_error}", exc_info=True)
                                logger.warning(f"Batch {batch_number} nao foi salvo no banco, mas processamento continuara")

                        try:
                            socketio.emit('remarketing_progress', {
                                'campaign_id': campaign.id,
                                'sent': campaign.total_sent,
                                'failed': campaign.total_failed,
                                'blocked': campaign.total_blocked,
                                'total': campaign.total_targets,
                                'percentage': round((campaign.total_sent / campaign.total_targets) * 100, 1) if campaign.total_targets > 0 else 0
                            })
                        except Exception as socket_error:
                            logger.warning(f"Erro ao emitir progresso WebSocket: {socket_error}")

                        offset += batch_size
                        progress_pct = round((offset / total_leads) * 100, 1) if total_leads > 0 else 0
                        logger.info(f"Progresso geral: {offset}/{total_leads} leads processados ({progress_pct}%)")

                    logger.info(f"Finalizando campanha {campaign_id} apos processar todos os batches")
                    try:
                        db.session.refresh(campaign)
                        campaign.status = 'completed'
                        from internal_logic.core.models import get_brazil_time
                        campaign.completed_at = get_brazil_time()
                        db.session.commit()
                        db.session.refresh(campaign)

                        total_processed = campaign.total_sent + campaign.total_failed + campaign.total_blocked
                        success_rate = round((campaign.total_sent / campaign.total_targets) * 100, 1) if campaign.total_targets > 0 else 0

                        logger.info(f"CAMPANHA {campaign_id} CONCLUIDA: {campaign.total_sent}/{campaign.total_targets} enviados ({success_rate}%) | Falhas: {campaign.total_failed} | Bloqueados: {campaign.total_blocked} | Total processado: {total_processed}")

                    except Exception as final_error:
                        logger.error(f"Erro ao finalizar campanha: {final_error}", exc_info=True)
                        try:
                            db.session.rollback()
                            db.session.refresh(campaign)
                            campaign.status = 'completed'
                            campaign.completed_at = get_brazil_time()
                            db.session.commit()
                            logger.info(f"Campanha finalizada apos rollback")
                        except Exception as retry_error:
                            logger.error(f"Erro critico ao finalizar campanha: {retry_error}", exc_info=True)

                    try:
                        socketio.emit('remarketing_completed', {
                            'campaign_id': campaign.id,
                            'total_sent': campaign.total_sent,
                            'total_failed': campaign.total_failed,
                            'total_blocked': campaign.total_blocked
                        })
                    except Exception as socket_error:
                        logger.warning(f"Erro ao emitir conclusao WebSocket: {socket_error}")
                except KeyboardInterrupt:
                    logger.warning(f"Campanha {campaign_id} interrompida pelo usuario")
                    try:
                        campaign = db.session.get(RemarketingCampaign, campaign_id)
                        if campaign:
                            campaign.status = 'paused'
                            db.session.commit()
                    except:
                        pass
                    raise
                except SystemExit:
                    logger.warning(f"Campanha {campaign_id} interrompida por SystemExit")
                    try:
                        campaign = db.session.get(RemarketingCampaign, campaign_id)
                        if campaign:
                            campaign.status = 'failed'
                            campaign.error_message = 'Sistema reiniciando'
                            db.session.commit()
                    except:
                        pass
                    raise
                except MemoryError:
                    logger.error(f"MEMORIA INSUFICIENTE na campanha {campaign_id} - pausando")
                    try:
                        campaign = db.session.get(RemarketingCampaign, campaign_id)
                        if campaign:
                            campaign.status = 'failed'
                            campaign.error_message = 'Memoria insuficiente - sistema sobrecarregado'
                            db.session.commit()
                    except:
                        pass
                    return
                except Exception as e:
                    logger.error(f"Erro ao enviar campanha de remarketing {campaign_id}: {e}", exc_info=True)
                    try:
                        campaign = db.session.get(RemarketingCampaign, campaign_id)
                        if campaign and campaign.status == 'sending':
                            if campaign.total_sent and campaign.total_sent > 0:
                                campaign.status = 'completed'
                                from internal_logic.core.models import get_brazil_time
                                if not campaign.completed_at:
                                    campaign.completed_at = get_brazil_time()
                                db.session.commit()
                                logger.info(f"Status atualizado para 'completed' apos erro (campanha {campaign_id}: {campaign.total_sent} enviados)")
                            else:
                                campaign.status = 'failed'
                                db.session.commit()
                                logger.info(f"Status atualizado para 'failed' apos erro (campanha {campaign_id})")
                    except Exception as update_error:
                        logger.error(f"Erro ao atualizar status apos falha: {update_error}", exc_info=True)
                        db.session.rollback()

        def send_campaign_with_limit():
            self.active_remarketing_campaigns.add(campaign_id)
            logger.info(f"Remarketing worker iniciado: campaign_id={campaign_id} (aguardando slot do semaforo)")

            max_retries = 360
            retry_count = 0

            while retry_count < max_retries:
                try:
                    acquired = self.remarketing_semaphore.acquire(timeout=60)

                    if acquired:
                        logger.info(f"Slot adquirido: campaign_id={campaign_id} (tentativa {retry_count + 1})")
                        break
                    else:
                        retry_count += 1
                        if retry_count % 10 == 0:
                            logger.info(f"Campanha {campaign_id} aguardando slot... (tentativa {retry_count}/{max_retries})")
                        time.sleep(5)
                        continue

                except Exception as acquire_error:
                    logger.warning(f"Erro ao adquirir slot para campanha {campaign_id}: {acquire_error}")
                    time.sleep(10)
                    retry_count += 1
                    continue

            if retry_count >= max_retries:
                logger.error(f"Campanha {campaign_id} nao conseguiu slot apos {max_retries} tentativas")
                try:
                    from flask import current_app
                    from internal_logic.core.extensions import db
                    with current_app.app_context():
                        campaign = db.session.get(RemarketingCampaign, campaign_id)
                        if campaign and campaign.status == 'sending':
                            campaign.error_message = 'Sistema muito ocupado - aguardando processamento'
                            db.session.commit()
                except:
                    pass
                return

            try:
                logger.info(f"Iniciando send_campaign(): campaign_id={campaign_id}")
                send_campaign()
                logger.info(f"send_campaign() retornou: campaign_id={campaign_id}")

            except Exception as outer_error:
                logger.error(f"Erro critico na campanha {campaign_id}: {outer_error}", exc_info=True)
                try:
                    from flask import current_app
                    from internal_logic.core.extensions import db
                    with current_app.app_context():
                        campaign = db.session.get(RemarketingCampaign, campaign_id)
                        if campaign:
                            campaign.status = 'failed'
                            campaign.error_message = f'Erro critico: {str(outer_error)[:200]}'
                            db.session.commit()
                except:
                    pass
            finally:
                self.remarketing_semaphore.release()
                self.active_remarketing_campaigns.discard(campaign_id)
                logger.info(f"Slot liberado - Campanha {campaign_id} concluida")

        thread = threading.Thread(target=send_campaign_with_limit)
        thread.daemon = True
        thread.start()
        logger.info(f"Thread disparada para remarketing: campaign_id={campaign_id} thread_name={thread.name}")

    def start_remarketing_worker(self, *, bot_id: int, bot_token: str) -> None:
        """Inicia worker que drena a fila Redis de remarketing para um bot"""
        try:
            if not bot_id or not bot_token:
                return

            with self._remarketing_workers_lock:
                existing = self._remarketing_workers.get(bot_id)
                if existing and existing.get('thread') and existing['thread'].is_alive():
                    if existing.get('token') != bot_token:
                        existing['token'] = bot_token
                    return

                stop_event = threading.Event()

                def _worker():
                    self._remarketing_worker_loop(bot_id=bot_id, stop_event=stop_event)

                thread = threading.Thread(target=_worker, name=f"remarketing-worker-bot-{bot_id}")
                thread.daemon = True
                self._remarketing_workers[bot_id] = {
                    'thread': thread,
                    'stop_event': stop_event,
                    'token': bot_token
                }
                thread.start()
                logger.info(f"Remarketing worker por bot iniciado: bot_id={bot_id} thread_name={thread.name}")
        except Exception as e:
            logger.error(f"Erro ao iniciar remarketing worker: bot_id={bot_id} err={e}", exc_info=True)

    def get_remarketing_worker_token(self, bot_id: int) -> Optional[str]:
        """Retorna token do worker de remarketing para um bot"""
        try:
            with self._remarketing_workers_lock:
                info = self._remarketing_workers.get(bot_id) or {}
                return info.get('token')
        except Exception:
            return None

    def _remarketing_worker_loop(self, *, bot_id: int, stop_event: threading.Event) -> None:
        """Loop principal do worker que drena a fila Redis e envia mensagens"""
        from internal_logic.core.redis_manager import get_redis_connection
        import json
        import random
        import time

        queue_key = f"gb:{self.user_id}:remarketing:queue:{bot_id}"
        logger.info(f"Remarketing worker ativo e drenando fila: {queue_key}")
        msg_counter = 0
        next_long_pause_after = random.randint(15, 25)

        while not stop_event.is_set():
            try:
                redis_conn = get_redis_connection()
                item = redis_conn.blpop(queue_key, timeout=5)
                if not item:
                    continue

                _, raw = item
                try:
                    job = json.loads(raw) if isinstance(raw, str) else json.loads(raw.decode('utf-8'))
                except Exception:
                    logger.warning(f"Remarketing job invalido (JSON parse falhou): bot_id={bot_id}")
                    continue
                logger.debug(f"Remarketing dequeue bot_id={bot_id} chat_id={job.get('telegram_user_id')}")

                job_type = job.get('type')
                if job_type == 'campaign_done':
                    campaign_id = job.get('campaign_id')
                    try:
                        from flask import current_app
                        from internal_logic.core.extensions import db, socketio
                        from internal_logic.core.models import RemarketingCampaign, get_brazil_time
                        with current_app.app_context():
                            campaign = db.session.get(RemarketingCampaign, int(campaign_id)) if campaign_id else None
                            if campaign:
                                db.session.refresh(campaign)
                                campaign.status = 'completed'
                                campaign.completed_at = get_brazil_time()
                                db.session.commit()
                                logger.info(f"Campaign DONE bot_id={bot_id} sent={campaign.total_sent} failed={campaign.total_failed} blocked={campaign.total_blocked}")
                                try:
                                    socketio.emit('remarketing_completed', {
                                        'campaign_id': campaign.id,
                                        'total_sent': campaign.total_sent,
                                        'total_failed': campaign.total_failed,
                                        'total_blocked': campaign.total_blocked
                                    })
                                except Exception:
                                    pass
                                logger.info(f"Remarketing campaign finalizada via sentinel: campaign_id={campaign.id}")
                    except Exception as e:
                        logger.error(f"Erro ao finalizar campanha via sentinel: bot_id={bot_id} err={e}", exc_info=True)
                    continue

                campaign_id = job.get('campaign_id')
                chat_id = job.get('telegram_user_id')
                message = job.get('message')
                media_url = job.get('media_url')
                media_type = job.get('media_type')
                buttons = job.get('buttons')
                audio_enabled = bool(job.get('audio_enabled'))
                audio_url = job.get('audio_url')

                token = self.get_remarketing_worker_token(bot_id)
                if not token:
                    token = job.get('bot_token')
                if not token:
                    logger.error(f"Remarketing worker sem token: bot_id={bot_id} campaign_id={campaign_id}")
                    continue

                send_result = None
                try:
                    send_result = self.send_message_func(
                        token=token,
                        chat_id=str(chat_id),
                        message=message,
                        media_url=media_url,
                        media_type=media_type,
                        buttons=buttons
                    )
                except Exception as send_error:
                    logger.error(f"ERRO REAL AO ENVIAR REMARKETING | bot_id={bot_id} campaign_id={campaign_id} chat_id={chat_id} err={send_error}", exc_info=True)
                    send_result = {'error': True, 'error_code': -1, 'description': str(send_error)}

                sent_inc = 0
                failed_inc = 0
                blocked_inc = 0

                error_code = None
                if isinstance(send_result, dict) and send_result.get('error'):
                    error_code = int(send_result.get('error_code') or 0)
                    desc = (send_result.get('description') or '').lower()
                    if error_code == 403 and ('bot was blocked' in desc or 'forbidden: bot was blocked' in desc):
                        blocked_inc = 1
                        try:
                            from flask import current_app
                            from internal_logic.core.extensions import db
                            from internal_logic.core.models import RemarketingBlacklist
                            with current_app.app_context():
                                existing = db.session.query(RemarketingBlacklist).filter_by(
                                    bot_id=bot_id,
                                    telegram_user_id=str(chat_id)
                                ).first()
                                if not existing:
                                    db.session.add(RemarketingBlacklist(bot_id=bot_id, telegram_user_id=str(chat_id), reason='bot_blocked'))
                                    db.session.commit()
                        except Exception:
                            pass
                    elif error_code == 401:
                        failed_inc = 1
                    else:
                        failed_inc = 1
                elif send_result:
                    sent_inc = 1
                    if audio_enabled and audio_url:
                        try:
                            self.send_message_func(
                                token=token,
                                chat_id=str(chat_id),
                                message="",
                                media_url=audio_url,
                                media_type='audio',
                                buttons=None
                            )
                        except Exception:
                            pass
                else:
                    failed_inc = 1

                if failed_inc and error_code in (0, -1):
                    time.sleep(2)
                    continue

                try:
                    if campaign_id:
                        from flask import current_app
                        from internal_logic.core.extensions import db, socketio
                        from internal_logic.core.models import RemarketingCampaign
                        with current_app.app_context():
                            campaign = db.session.get(RemarketingCampaign, int(campaign_id))
                            if campaign:
                                db.session.refresh(campaign)
                                campaign.total_sent += sent_inc
                                campaign.total_failed += failed_inc
                                campaign.total_blocked += blocked_inc
                                db.session.commit()
                                try:
                                    socketio.emit('remarketing_progress', {
                                        'campaign_id': campaign.id,
                                        'sent': campaign.total_sent,
                                        'failed': campaign.total_failed,
                                        'blocked': campaign.total_blocked,
                                        'total': campaign.total_targets,
                                        'percentage': round((campaign.total_sent / campaign.total_targets) * 100, 1) if campaign.total_targets > 0 else 0
                                    })
                                except Exception:
                                    pass
                except Exception as update_error:
                    logger.debug(f"Falha ao atualizar contadores do remarketing (nao critico): {update_error}")

                msg_counter += 1
                time.sleep(random.uniform(1.2, 2.5))

                if msg_counter % 100 == 0:
                    logger.info(f"Micro pause remarketing bot_id={bot_id} msgs={msg_counter}")
                    time.sleep(random.uniform(10, 20))
            except Exception as e:
                logger.error(f"Erro no remarketing worker loop: bot_id={bot_id} err={e}", exc_info=True)
                try:
                    time.sleep(5)
                except Exception:
                    pass


def count_eligible_leads(bot_id: int, target_audience: str = 'non_buyers',
                         days_since_last_contact: int = 3, exclude_buyers: bool = True,
                         audience_segment: str = None) -> int:
    from flask import current_app
    from internal_logic.core.extensions import db
    from internal_logic.core.models import BotUser, Payment, RemarketingBlacklist
    from datetime import datetime, timedelta

    with current_app.app_context():
        from internal_logic.core.models import get_brazil_time
        contact_limit = get_brazil_time() - timedelta(days=days_since_last_contact)

        query = BotUser.query.filter_by(bot_id=bot_id, archived=False)

        if days_since_last_contact > 0:
            query = query.filter(BotUser.last_interaction <= contact_limit)

        blacklist_ids = db.session.query(RemarketingBlacklist.telegram_user_id).filter_by(
            bot_id=bot_id
        ).all()
        blacklist_ids = [b[0] for b in blacklist_ids if b[0]]
        if blacklist_ids:
            query = query.filter(~BotUser.telegram_user_id.in_(blacklist_ids))
            logger.debug(f"Blacklist para bot {bot_id}: {len(blacklist_ids)} usuarios excluidos")

        if audience_segment:
            if audience_segment == 'all_users':
                pass
            elif audience_segment == 'buyers':
                buyer_ids = db.session.query(Payment.customer_user_id).filter(
                    Payment.bot_id == bot_id,
                    Payment.status == 'paid'
                ).distinct().all()
                buyer_ids = [b[0] for b in buyer_ids if b[0]]
                if buyer_ids:
                    query = query.filter(BotUser.telegram_user_id.in_(buyer_ids))
                else:
                    return 0
            elif audience_segment == 'pix_generated':
                pix_ids = db.session.query(Payment.customer_user_id).filter(
                    Payment.bot_id == bot_id,
                    Payment.status == 'pending'
                ).distinct().all()
                pix_ids = [b[0] for b in pix_ids if b[0]]
                if pix_ids:
                    query = query.filter(BotUser.telegram_user_id.in_(pix_ids))
                else:
                    return 0
            elif audience_segment == 'downsell_buyers':
                downsell_ids = db.session.query(Payment.customer_user_id).filter(
                    Payment.bot_id == bot_id,
                    Payment.status == 'paid',
                    Payment.is_downsell == True
                ).distinct().all()
                downsell_ids = [b[0] for b in downsell_ids if b[0]]
                if downsell_ids:
                    query = query.filter(BotUser.telegram_user_id.in_(downsell_ids))
                else:
                    return 0
            elif audience_segment == 'order_bump_buyers':
                orderbump_ids = db.session.query(Payment.customer_user_id).filter(
                    Payment.bot_id == bot_id,
                    Payment.status == 'paid',
                    Payment.order_bump_accepted == True
                ).distinct().all()
                orderbump_ids = [b[0] for b in orderbump_ids if b[0]]
                if orderbump_ids:
                    query = query.filter(BotUser.telegram_user_id.in_(orderbump_ids))
                else:
                    return 0
            elif audience_segment == 'upsell_buyers':
                upsell_ids = db.session.query(Payment.customer_user_id).filter(
                    Payment.bot_id == bot_id,
                    Payment.status == 'paid',
                    Payment.is_upsell == True
                ).distinct().all()
                upsell_ids = [b[0] for b in upsell_ids if b[0]]
                if upsell_ids:
                    query = query.filter(BotUser.telegram_user_id.in_(upsell_ids))
                else:
                    return 0
            elif audience_segment == 'remarketing_buyers':
                remarketing_ids = db.session.query(Payment.customer_user_id).filter(
                    Payment.bot_id == bot_id,
                    Payment.status == 'paid',
                    Payment.is_remarketing == True
                ).distinct().all()
                remarketing_ids = [b[0] for b in remarketing_ids if b[0]]
                if remarketing_ids:
                    query = query.filter(BotUser.telegram_user_id.in_(remarketing_ids))
                else:
                    return 0
            else:
                logger.warning(f"Segmento desconhecido: {audience_segment}")
                return 0
        else:
            if exclude_buyers:
                buyer_ids = db.session.query(Payment.customer_user_id).filter(
                    Payment.bot_id == bot_id,
                    Payment.status == 'paid'
                ).distinct().all()
                buyer_ids = [b[0] for b in buyer_ids if b[0]]
                if buyer_ids:
                    query = query.filter(~BotUser.telegram_user_id.in_(buyer_ids))
            if target_audience == 'abandoned_cart':
                abandoned_ids = db.session.query(Payment.customer_user_id).filter(
                    Payment.bot_id == bot_id,
                    Payment.status == 'pending'
                ).distinct().all()
                abandoned_ids = [b[0] for b in abandoned_ids if b[0]]
                if abandoned_ids:
                    query = query.filter(BotUser.telegram_user_id.in_(abandoned_ids))
                else:
                    return 0
            elif target_audience == 'inactive':
                from internal_logic.core.models import get_brazil_time
                inactive_limit = get_brazil_time() - timedelta(days=7)
                query = query.filter(BotUser.last_interaction <= inactive_limit)

        return query.count()
