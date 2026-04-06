@app.route('/api/chat/messages/<int:bot_id>/<telegram_user_id>', methods=['GET'])
@login_required
def get_chat_messages(bot_id, telegram_user_id):
    """✅ CHAT - Retorna mensagens de uma conversa específica"""
    try:
        from internal_logic.core.models import Bot, BotUser, BotMessage
        
        # Verificar se bot pertence ao usuário
        bot = Bot.query.filter_by(id=bot_id, user_id=current_user.id).first_or_404()
        
        # Buscar bot_user
        bot_user = BotUser.query.filter_by(
            bot_id=bot_id,
            telegram_user_id=telegram_user_id,
            archived=False
        ).first()
        
        if not bot_user:
            return jsonify({
                'success': False,
                'error': 'Conversa não encontrada',
                'messages': []
            }), 404
        
        # ✅ OTIMIZAÇÃO QI 600+: Buscar mensagens novas usando timestamp (mais confiável que ID)
        since_timestamp = request.args.get('since_timestamp', type=str)
        
        if since_timestamp:
            try:
                from datetime import datetime, timezone, timedelta
                from internal_logic.core.models import BRAZIL_TZ_OFFSET
                
                # ✅ CORREÇÃO: Tratar diferentes formatos de timestamp
                since_timestamp_clean = since_timestamp.replace('Z', '+00:00')
                if '+' not in since_timestamp_clean and since_timestamp_clean.count(':') == 2:
                    # Formato sem timezone, assumir UTC
                    since_timestamp_clean += '+00:00'
                since_dt_utc = datetime.fromisoformat(since_timestamp_clean)
                
                # ✅ CRÍTICO: Converter UTC (timezone-aware) para UTC (naive)
                if since_dt_utc.tzinfo is not None:
                    since_dt_utc = since_dt_utc.astimezone(timezone.utc).replace(tzinfo=None)
                
                # ✅ CRÍTICO: Converter UTC para horário do Brasil (naive)
                # BotMessage.created_at usa get_brazil_time() = datetime.utcnow() + BRAZIL_TZ_OFFSET
                # Isso significa que created_at está em UTC-3 (naive)
                # Frontend envia UTC, então: since_dt_brazil = since_dt_utc + BRAZIL_TZ_OFFSET
                since_dt_brazil = since_dt_utc + BRAZIL_TZ_OFFSET  # BRAZIL_TZ_OFFSET = -3h
                
                # ✅ CRÍTICO: Adicionar margem de 20 segundos para garantir que não perca mensagens
                # (considerando diferença de timezone, latência de rede, processamento e sincronização)
                since_dt_brazil_with_margin = since_dt_brazil - timedelta(seconds=20)
                
                # Buscar apenas mensagens mais recentes que o timestamp (com margem)
                messages = BotMessage.query.filter(
                    BotMessage.bot_id == bot_id,
                    BotMessage.telegram_user_id == telegram_user_id,
                    BotMessage.created_at > since_dt_brazil_with_margin
                ).order_by(BotMessage.created_at.asc()).limit(50).all()
                
                # ✅ FALLBACK: Se não encontrou mensagens, buscar últimas 10 e comparar no Python
                # (evita problemas de timezone e sincronização)
                if len(messages) == 0:
                    # Buscar últimas 10 mensagens para garantir que não perdemos nada
                    recent_messages = BotMessage.query.filter_by(
                        bot_id=bot_id,
                        telegram_user_id=telegram_user_id
                    ).order_by(BotMessage.created_at.desc()).limit(10).all()
                    
                    # Filtrar mensagens mais recentes que o timestamp (comparação direta no Python)
                    messages = [msg for msg in recent_messages if msg.created_at > since_dt_brazil_with_margin]
                    messages.reverse()  # Ordenar crescente para exibição
                    
                    if len(messages) > 0:
                        logger.info(f"✅ Polling (fallback): {len(messages)} novas mensagens encontradas via fallback")
                
                # ✅ DEBUG: Log detalhado sempre (para produção também)
                if len(messages) > 0:
                    logger.info(f"✅ Polling: {len(messages)} novas mensagens desde {since_timestamp} | "
                               f"since_dt_utc: {since_dt_utc} | since_dt_brazil: {since_dt_brazil} | "
                               f"since_dt_brazil_with_margin: {since_dt_brazil_with_margin}")
                else:
                    logger.debug(f"🔍 Polling: 0 novas mensagens desde {since_timestamp} | "
                               f"since_dt_brazil_with_margin: {since_dt_brazil_with_margin}")
            except Exception as e:
                logger.error(f"Erro ao parsear since_timestamp '{since_timestamp}': {e}")
                # Fallback: buscar últimas 50 mensagens
                messages = BotMessage.query.filter_by(
                    bot_id=bot_id,
                    telegram_user_id=telegram_user_id
                ).order_by(BotMessage.created_at.desc()).limit(50).all()
                messages.reverse()  # Ordenar crescente para exibição
        else:
            # Buscar todas as mensagens (primeira carga)
            messages = BotMessage.query.filter_by(
                bot_id=bot_id,
                telegram_user_id=telegram_user_id
            ).order_by(BotMessage.created_at.asc()).limit(100).all()
            
            # Marcar mensagens como lidas apenas na primeira carga
            BotMessage.query.filter_by(
                bot_id=bot_id,
                telegram_user_id=telegram_user_id,
                direction='incoming',
                is_read=False
            ).update({'is_read': True})
            db.session.commit()
        
        messages_data = [msg.to_dict() for msg in messages]
        
        return jsonify({
            'success': True,
            'bot_user': bot_user.to_dict(),
            'messages': messages_data,
            'total': len(messages_data)
        })
        
    except Exception as e:
        import traceback
        logger.error(f"Erro ao carregar mensagens do chat: {e}")
        logger.error(f"Stack trace: {traceback.format_exc()}")
        return jsonify({
            'success': False,
            'error': 'Erro ao carregar mensagens',
            'messages': []
        }), 500
