

def task_process_broadcast_campaign(campaign_data: Dict[str, Any], bot_ids: list, group_id: str = None):
    """
    ✅ Worker RQ para processar campanhas de remarketing em background.
    
    🏗️ REFATORADO: Arquitetura em 2 Fases (Pre-Allocation + Processing)
    - FASE 1: Pré-alocação instantânea de todas as campanhas no banco
    - FASE 2: Processamento assíncrono usando IDs pré-alocados
    
    Isso elimina a Race Condition onde History/Analytics não enxergavam todos os bots.
    
    Args:
        campaign_data: Dicionário com dados da campanha (message, media_url, etc.)
        bot_ids: Lista de IDs dos bots alvo
        group_id: UUID opcional para agrupar campanhas multi-bot
    """
    from app import app, db
    from internal_logic.core.models import Bot, BotUser, Payment, RemarketingBlacklist, RemarketingCampaign, get_brazil_time
    from bot_manager import BotManager
    from datetime import timedelta
    from redis_manager import get_redis_connection
    import json
    import time
    
    with app.app_context():
        try:
            # ✅ EXTRAIR DADOS DA CAMPANHA
            message_template = campaign_data.get('message', '')
            media_url = campaign_data.get('media_url')
            media_type = campaign_data.get('media_type', 'video')
            audio_enabled = campaign_data.get('audio_enabled', False)
            audio_url = campaign_data.get('audio_url', '')
            buttons = campaign_data.get('buttons', [])
            days_since_last_contact = campaign_data.get('days_since_last_contact', 7)
            audience_segment = campaign_data.get('audience_segment', 'all_users')
            user_id = campaign_data.get('user_id')
            
            # Mapeamento de segmento
            target_audience_mapping = {
                'all_users': 'all',
                'buyers': 'buyers',
                'pix_generated': 'abandoned_cart',
                'downsell_buyers': 'downsell_buyers',
                'order_bump_buyers': 'order_bump_buyers',
                'upsell_buyers': 'upsell_buyers',
                'remarketing_buyers': 'remarketing_buyers',
                'non_buyers': 'non_buyers'
            }
            target_audience = target_audience_mapping.get(audience_segment, 'all')
            
            # ✅ INICIALIZAR CONEXÕES
            redis_conn = get_redis_connection()
            bot_manager = BotManager(None, None)
            contact_limit = get_brazil_time() - timedelta(days=days_since_last_contact)
            
            # Taxa limit: Telegram permite 30 mensagens/segundo
            RATE_LIMIT_MSGS_PER_SEC = 30
            rate_limit_delay = 1.0 / RATE_LIMIT_MSGS_PER_SEC
            
            logger.info(f"🚀 [REMARKETING WORKER] Iniciando campanha | bots={len(bot_ids)} | segment={audience_segment}")
            
            # ==========================================
            # 🏗️ FASE 1: PRE-ALLOCATION (Instantânea)
            # ==========================================
            logger.info(f"📦 [PRE-ALLOCATION] Fase 1: Pré-alocando {len(bot_ids)} campanha(s) no banco...")
            
            allocated_campaigns = {}  # Mapeamento: bot_id -> campaign_id
            campaigns_to_commit = []  # Lista de campanhas para commit em batch
            
            for bot_id in bot_ids:
                try:
                    # Buscar bot e validar propriedade
                    bot = Bot.query.get(bot_id)
                    if not bot or bot.user_id != user_id:
                        logger.warning(f"⚠️ [PRE-ALLOCATION] Bot {bot_id} não encontrado ou não pertence ao usuário {user_id}")
                        continue
                    
                    # Verificar leads elegíveis ANTES de criar (para saber total_targets)
                    q = db.session.query(BotUser).filter(
                        BotUser.bot_id == bot_id,
                        BotUser.archived == False
                    )
                    
                    if days_since_last_contact > 0:
                        q = q.filter(BotUser.last_interaction <= contact_limit)
                    
                    # Filtrar blacklist
                    blacklist_ids = db.session.query(RemarketingBlacklist.telegram_user_id).filter_by(
                        bot_id=bot_id
                    ).all()
                    blacklist_ids = [b[0] for b in blacklist_ids if b[0]]
                    if blacklist_ids:
                        q = q.filter(~BotUser.telegram_user_id.in_(blacklist_ids))
                    
                    # Filtros de segmento
                    if target_audience == 'buyers':
                        buyer_ids = db.session.query(Payment.customer_user_id).filter(
                            Payment.bot_id == bot_id,
                            Payment.status == 'paid'
                        ).distinct().all()
                        buyer_ids = [b[0] for b in buyer_ids if b[0]]
                        if buyer_ids:
                            q = q.filter(BotUser.telegram_user_id.in_(buyer_ids))
                        else:
                            logger.info(f"ℹ️ [PRE-ALLOCATION] Bot {bot_id}: 0 compradores encontrados")
                            continue
                    elif target_audience == 'non_buyers':
                        buyer_ids = db.session.query(Payment.customer_user_id).filter(
                            Payment.bot_id == bot_id,
                            Payment.status == 'paid'
                        ).distinct().all()
                        buyer_ids = [b[0] for b in buyer_ids if b[0]]
                        if buyer_ids:
                            q = q.filter(~BotUser.telegram_user_id.in_(buyer_ids))
                    
                    total_leads = q.count()
                    
                    # SEMPRE criar campanha (mesmo com 0 leads, para manter consistência do grupo)
                    # Status inicial: 'queued' (pronto para processar)
                    campaign = RemarketingCampaign(
                        bot_id=bot_id,
                        group_id=group_id,
                        name=campaign_data.get('name', f'Campanha Remarketing'),
                        message=message_template,
                        media_url=media_url,
                        media_type=media_type,
                        audio_enabled=audio_enabled,
                        audio_url=audio_url,
                        buttons=json.dumps(buttons) if buttons else None,
                        target_audience=target_audience,
                        days_since_last_contact=days_since_last_contact,
                        status='queued',  # ✅ NOVO: Status inicial é 'queued'
                        total_targets=total_leads,  # ✅ Já definimos o total aqui
                        started_at=get_brazil_time()
                    )
                    
                    db.session.add(campaign)
                    campaigns_to_commit.append((bot_id, bot.name, campaign, total_leads))
                    
                except Exception as pre_alloc_error:
                    logger.error(f"❌ [PRE-ALLOCATION] Erro pré-alocando bot {bot_id}: {pre_alloc_error}")
                    continue
            
            # ✅ COMMIT ÚNICO DE TODAS AS CAMPANHAS (Instantâneo)
            if campaigns_to_commit:
                try:
                    db.session.commit()
                    
                    # Preencher dicionário de mapeamento após commit (agora temos os IDs)
                    for bot_id, bot_name, campaign, total_leads in campaigns_to_commit:
                        allocated_campaigns[bot_id] = campaign.id
                        logger.info(f"✅ [PRE-ALLOCATION] Bot {bot_name} (ID: {bot_id}) | Campaign ID: {campaign.id} | Leads: {total_leads}")
                    
                    logger.info(f"🎉 [PRE-ALLOCATION] Concluída! {len(allocated_campaigns)} campanha(s) materializada(s) no banco")
                except Exception as commit_error:
                    logger.error(f"🚨 [PRE-ALLOCATION] Erro no commit: {commit_error}")
                    db.session.rollback()
                    return
            else:
                logger.warning("⚠️ [PRE-ALLOCATION] Nenhuma campanha para pré-alocar")
                return
            
            # ==========================================
            # 🚀 FASE 2: PROCESSING (Demorada/Assíncrona)
            # ==========================================
            logger.info(f"📤 [PROCESSING] Fase 2: Iniciando envio para {len(allocated_campaigns)} bot(s)...")
            
            total_stats = {
                'total_targets': 0,
                'total_sent': 0,
                'total_failed': 0,
                'total_blocked': 0,
                'total_skipped': 0
            }
            
            for bot_id in bot_ids:
                # Se o bot não foi pré-alocado (não tinha leads ou erro), pular
                if bot_id not in allocated_campaigns:
                    logger.info(f"ℹ️ [PROCESSING] Bot {bot_id}: Pulando (não pré-alocado)")
                    continue
                
                campaign_id = allocated_campaigns[bot_id]
                
                try:
                    # ✅ Atualizar status para 'sending' usando UPDATE direto (eficiente)
                    db.session.query(RemarketingCampaign).filter(
                        RemarketingCampaign.id == campaign_id
                    ).update({
                        'status': 'sending',
                        'started_at': get_brazil_time()
                    })
                    db.session.commit()
                    
                    # Buscar bot para processamento
                    bot = Bot.query.get(bot_id)
                    if not bot:
                        logger.error(f"❌ [PROCESSING] Bot {bot_id} não encontrado na Fase 2")
                        continue
                    
                    # Chaves Redis (usando campaign_id pré-alocado)
                    sent_set_key = f"remarketing:sent:{campaign_id}"
                    stats_key = f"remarketing:stats:{campaign_id}"
                    blacklist_key = f"remarketing:blacklist:{bot_id}"
                    
                    logger.info(f"📊 [PROCESSING] Processando bot {bot.name} (ID: {bot_id}) | Campaign: {campaign_id}")
                    
                    # ✅ RECONSTRUIR QUERY DE LEADS (igual Fase 1)
                    q = db.session.query(BotUser).filter(
                        BotUser.bot_id == bot_id,
                        BotUser.archived == False
                    )
                    
                    if days_since_last_contact > 0:
                        q = q.filter(BotUser.last_interaction <= contact_limit)
                    
                    # Filtrar blacklist
                    blacklist_ids = db.session.query(RemarketingBlacklist.telegram_user_id).filter_by(
                        bot_id=bot_id
                    ).all()
                    blacklist_ids = [b[0] for b in blacklist_ids if b[0]]
                    if blacklist_ids:
                        q = q.filter(~BotUser.telegram_user_id.in_(blacklist_ids))
                    
                    # Filtros de segmento
                    if target_audience == 'buyers':
                        buyer_ids = db.session.query(Payment.customer_user_id).filter(
                            Payment.bot_id == bot_id,
                            Payment.status == 'paid'
                        ).distinct().all()
                        buyer_ids = [b[0] for b in buyer_ids if b[0]]
                        if buyer_ids:
                            q = q.filter(BotUser.telegram_user_id.in_(buyer_ids))
                        else:
                            logger.info(f"ℹ️ [PROCESSING] Bot {bot_id}: 0 compradores")
                            continue
                    elif target_audience == 'non_buyers':
                        buyer_ids = db.session.query(Payment.customer_user_id).filter(
                            Payment.bot_id == bot_id,
                            Payment.status == 'paid'
                        ).distinct().all()
                        buyer_ids = [b[0] for b in buyer_ids if b[0]]
                        if buyer_ids:
                            q = q.filter(~BotUser.telegram_user_id.in_(buyer_ids))
                    
                    total_leads = q.count()
                    
                    # Se 0 leads, apenas finalizar como 'completed' sem envios
                    if total_leads == 0:
                        logger.info(f"ℹ️ [PROCESSING] Bot {bot_id}: 0 leads elegíveis, finalizando")
                        db.session.query(RemarketingCampaign).filter(
                            RemarketingCampaign.id == campaign_id
                        ).update({
                            'status': 'completed',
                            'completed_at': get_brazil_time(),
                            'total_sent': 0,
                            'total_failed': 0
                        })
                        db.session.commit()
                        continue
                    
                    logger.info(f"🎯 [PROCESSING] Bot {bot_id}: {total_leads} leads para enviar")
                    
                    # ✅ EXTRAÇÃO DE VARIÁVEIS PRIMITIVAS
                    bot_token_str = str(bot.token)
                    campaign_id_int = int(campaign_id)
                    
                    # ✅ LOOP DE ENVIO COM RATE LIMIT (Código original preservado)
                    batch_size = 200
                    offset = 0
                    sent_count = 0
                    failed_count = 0
                    skipped_count = 0
                    bot_is_dead = False
                    
                    while offset < total_leads:
                        batch = q.offset(offset).limit(batch_size).all()
                        if not batch:
                            break
                        
                        for lead in batch:
                            try:
                                # Validar chat_id
                                if not lead.telegram_user_id:
                                    skipped_count += 1
                                    continue
                                
                                try:
                                    chat_int = int(str(lead.telegram_user_id))
                                    if chat_int == 0:
                                        skipped_count += 1
                                        continue
                                except:
                                    skipped_count += 1
                                    continue
                                
                                # Verificar se já enviou (Redis)
                                if redis_conn.sismember(sent_set_key, str(lead.telegram_user_id)):
                                    skipped_count += 1
                                    continue
                                
                                # Verificar blacklist (Redis)
                                if redis_conn.sismember(blacklist_key, str(lead.telegram_user_id)):
                                    skipped_count += 1
                                    continue
                                
                                # Verificar opt-out
                                if getattr(lead, 'opt_out', False) or getattr(lead, 'unsubscribed', False):
                                    skipped_count += 1
                                    continue
                                
                                # ✅ MONTAR MENSAGEM PERSONALIZADA
                                personalized_message = message_template.replace('{nome}', lead.first_name or 'Cliente')
                                personalized_message = personalized_message.replace('{primeiro_nome}', (lead.first_name or 'Cliente').split()[0])
                                
                                # ✅ MONTAR BOTÕES
                                remarketing_buttons = []
                                if buttons:
                                    for btn_idx, btn in enumerate(buttons):
                                        if btn.get('price') and btn.get('description'):
                                            remarketing_buttons.append({
                                                'text': btn.get('text', 'Comprar'),
                                                'callback_data': f"rmkt_{campaign_id_int}_{btn_idx}"
                                            })
                                        elif btn.get('url'):
                                            remarketing_buttons.append({
                                                'text': btn.get('text', 'Link'),
                                                'url': btn.get('url')
                                            })
                                
                                # ✅ LOOP DE RETRY (máximo 3 tentativas por lead)
                                lead_sent = False
                                for attempt in range(3):
                                    try:
                                        result = bot_manager.send_telegram_message(
                                            token=bot_token_str,
                                            chat_id=str(lead.telegram_user_id),
                                            message=personalized_message,
                                            media_url=media_url,
                                            media_type=media_type if media_url else None,
                                            buttons=remarketing_buttons if remarketing_buttons else None
                                        )
                                        
                                        # 🚨 VALIDAÇÃO STRICT
                                        if isinstance(result, dict) and result.get('error'):
                                            raise Exception(f"status={result.get('error_code', 'unknown')}, desc={result.get('description', '')}")
                                        elif not result:
                                            raise Exception("Falha silenciosa: Função retornou False ou None")
                                        
                                        # ✅ SUCESSO REAL
                                        sent_count += 1
                                        redis_conn.sadd(sent_set_key, str(lead.telegram_user_id))
                                        lead_sent = True
                                        
                                        if sent_count % 100 == 0:
                                            logger.info(f"📤 [PROCESSING] Bot {bot_id} | Progresso: {sent_count}/{total_leads} | Campaign: {campaign_id_int}")
                                        break
                                        
                                    except Exception as send_error:
                                        error_str = str(send_error).lower()
                                        
                                        # ✅ SMART BLACKLIST
                                        blocked_keywords = [
                                            'bot was blocked by the user', 'forbidden', 'user is deactivated',
                                            'chat not found', 'user not found', 'bot was kicked', 'bot was stopped',
                                            'chat not accessible', 'user blocked'
                                        ]
                                        
                                        is_blocked = any(keyword in error_str for keyword in blocked_keywords)
                                        
                                        if is_blocked:
                                            redis_conn.sadd(blacklist_key, str(lead.telegram_user_id))
                                            lead.unsubscribed = True
                                            lead.inactive = True
                                            logger.info(f"🚫 [PROCESSING] Lead {lead.telegram_user_id} bloqueado/desativado")
                                            break
                                        
                                        # ✅ EXPONENTIAL BACKOFF: Erros 429
                                        elif 'too many requests' in error_str or 'retry after' in error_str:
                                            import re
                                            retry_seconds = 5
                                            try:
                                                match = re.search(r'retry\s+after\s*(?::)?\s*(\d+)', error_str)
                                                if match:
                                                    retry_seconds = int(match.group(1))
                                                    retry_seconds = max(retry_seconds, 5)
                                            except:
                                                retry_seconds = 5
                                            
                                            logger.warning(f"⏸️ [PROCESSING] Rate limit (429) na tentativa {attempt + 1}/3. Aguardando {retry_seconds}s...")
                                            time.sleep(retry_seconds)
                                            
                                            if attempt == 2:
                                                logger.error(f"❌ [PROCESSING] Esgotadas 3 tentativas para {lead.telegram_user_id} (429)")
                                            continue
                                        
                                        # 🚨 CIRCUIT BREAKER: Erros 401/404
                                        elif any(keyword in error_str for keyword in ['unauthorized', '401', 'not found', '404']):
                                            logger.error(f"🚨 [CIRCUIT BREAKER] Bot {bot_id} morto ou revogado (Erro 401/404)")
                                            bot_is_dead = True
                                            db.session.query(Bot).filter(Bot.id == bot_id).update({
                                                'is_active': False,
                                                'last_error': f"Desativado automaticamente: {send_error}"
                                            })
                                            db.session.commit()
                                            break
                                        
                                        else:
                                            logger.warning(f"⚠️ [PROCESSING] Erro na tentativa {attempt + 1}/3 para {lead.telegram_user_id}: {send_error}")
                                            if attempt == 2:
                                                logger.error(f"❌ [PROCESSING] Esgotadas 3 tentativas para {lead.telegram_user_id}")
                                
                                if not lead_sent and not bot_is_dead:
                                    time.sleep(rate_limit_delay)
                                
                                if not lead_sent:
                                    failed_count += 1
                                
                                if bot_is_dead:
                                    break
                                
                                time.sleep(rate_limit_delay)
                                
                            except Exception as lead_error:
                                failed_count += 1
                                logger.error(f"❌ [PROCESSING] Erro processando lead {lead.id}: {lead_error}")
                                continue
                        
                        if bot_is_dead:
                            logger.warning(f"🚨 [CIRCUIT BREAKER] Abortando campanha do bot {bot_id}")
                            break
                        
                        offset += batch_size
                        
                        # ✅ UPDATE DIRETO DO PROGRESSO
                        db.session.query(RemarketingCampaign).filter(
                            RemarketingCampaign.id == campaign_id_int
                        ).update({
                            'total_sent': sent_count,
                            'total_failed': failed_count
                        })
                        db.session.commit()
                        
                        # ✅ LIMPEZA DE MEMÓRIA
                        db.session.expunge_all()
                    
                    # ✅ FINALIZAR CAMPANHA
                    db.session.query(RemarketingCampaign).filter(
                        RemarketingCampaign.id == campaign_id_int
                    ).update({
                        'status': 'completed',
                        'completed_at': get_brazil_time(),
                        'total_sent': sent_count,
                        'total_failed': failed_count
                    })
                    db.session.commit()
                    
                    # Atualizar estatísticas globais
                    total_stats['total_targets'] += total_leads
                    total_stats['total_sent'] += sent_count
                    total_stats['total_failed'] += failed_count
                    total_stats['total_skipped'] += skipped_count
                    
                    logger.info(f"✅ [PROCESSING] Bot {bot_id} concluído | Enviados: {sent_count} | Falhas: {failed_count}")
                    
                except Exception as processing_error:
                    logger.error(f"❌ [PROCESSING] Erro processando bot {bot_id}: {processing_error}", exc_info=True)
                    # Marcar campanha como failed
                    try:
                        db.session.query(RemarketingCampaign).filter(
                            RemarketingCampaign.id == campaign_id
                        ).update({
                            'status': 'failed',
                            'completed_at': get_brazil_time()
                        })
                        db.session.commit()
                    except:
                        pass
                    continue
            
            logger.info(f"🎉 [PROCESSING] Campanha concluída | Total enviados: {total_stats['total_sent']} | Total falhas: {total_stats['total_failed']}")
            
        except Exception as e:
            logger.error(f"❌ [REMARKETING WORKER] Erro fatal na campanha: {e}", exc_info=True)
            raise
