"""
Start Command Handler Service
==============================
Processa comando /start do Telegram com FAST RESPONSE MODE.
Extraido do BotManager (Fase 9).
"""

import logging
from datetime import datetime
from typing import Dict, Any

from internal_logic.core.redis_manager import get_redis_connection
from internal_logic.services.bot_messenger import checkActiveFlow

logger = logging.getLogger(__name__)


def handle_start_command(bot_manager, bot_id: int, token: str, config: Dict[str, Any],
                         chat_id: int, message: Dict[str, Any], start_param: str = None):
    try:
        user_from = message.get('from', {})
        telegram_user_id = str(user_from.get('id', ''))
        first_name = user_from.get('first_name', 'Usuario')

        logger.info(f"COMANDO /START recebido - Reiniciando funil FORCADAMENTE (regra absoluta)")

        if not start_param:
            try:
                text_msg = message.get('text') if isinstance(message, dict) else None
                if text_msg and isinstance(text_msg, str):
                    parts = text_msg.split()
                    if len(parts) > 1:
                        start_param = parts[1].strip()
                        logger.info(f"start_param recuperado do texto: '{start_param}'")
            except Exception as e:
                logger.warning(f"Falha ao extrair start_param do texto: {e}")

        pixel_id_from_start = None
        if start_param and '__px_' in start_param:
            parts = start_param.split('__px_', 1)
            if parts and parts[0]:
                start_param = parts[0]
            if len(parts) > 1 and parts[1]:
                pixel_id_from_start = parts[1]
                logger.info(f"Pixel transportado no start_param preservado: {pixel_id_from_start}")

        try:
            from flask import current_app
            from internal_logic.core.extensions import db
            from internal_logic.core.models import BotUser
            if start_param:
                with current_app.app_context():
                    bot_user_track = BotUser.query.filter_by(
                        bot_id=bot_id,
                        telegram_user_id=telegram_user_id,
                        archived=False
                    ).first()
                    if bot_user_track and pixel_id_from_start and not bot_user_track.campaign_code:
                        bot_user_track.campaign_code = pixel_id_from_start
                        db.session.commit()
                        logger.info(f"Pixel do funil associado ao BotUser {bot_user_track.id} via start_param (campanha nao sobrescrita)")
                    if bot_user_track:
                        import json as _json
                        tracking_key = f"tracking:{start_param}"
                        redis_conn = get_redis_connection()
                        raw_payload = redis_conn.get(tracking_key) if redis_conn else None
                        if raw_payload:
                            payload = _json.loads(raw_payload)
                            if len(start_param) == 32:
                                bot_user_track.tracking_session_id = start_param
                                logger.info(f"V4.1 - tracking_token salvo: {start_param[:8]}...")
                            if payload.get('pixel_id'):
                                bot_user_track.campaign_code = payload.get('pixel_id')
                                logger.info(f"V4.1 - pixel_id salvo em campaign_code: {payload.get('pixel_id')}")
                            bot_user_track.fbclid = payload.get('fbclid') or bot_user_track.fbclid
                            bot_user_track.fbp = payload.get('fbp') or bot_user_track.fbp
                            bot_user_track.fbc = payload.get('fbc') or bot_user_track.fbc
                            bot_user_track.last_fbclid = payload.get('fbclid') or bot_user_track.last_fbclid
                            bot_user_track.last_fbp = payload.get('fbp') or bot_user_track.last_fbp
                            bot_user_track.last_fbc = payload.get('fbc') or bot_user_track.last_fbc
                            bot_user_track.user_agent = payload.get('client_user_agent') or bot_user_track.user_agent
                            bot_user_track.ip_address = payload.get('client_ip') or bot_user_track.ip_address
                            bot_user_track.utm_source = payload.get('utm_source') or bot_user_track.utm_source
                            bot_user_track.utm_campaign = payload.get('utm_campaign') or bot_user_track.utm_campaign
                            bot_user_track.utm_content = payload.get('utm_content') or bot_user_track.utm_content
                            bot_user_track.utm_medium = payload.get('utm_medium') or bot_user_track.utm_medium
                            bot_user_track.utm_term = payload.get('utm_term') or bot_user_track.utm_term
                            bot_user_track.click_timestamp = datetime.now()
                            db.session.commit()
                            logger.info(f"V4.1 - TRACKING LINKED: User {bot_user_track.id} -> FBCLID: {bot_user_track.fbclid} | Token: {start_param[:8]}...")
        except Exception as e:
            logger.warning(f"Falha na hidratacao inicial de tracking via start_param={start_param}: {e}")

        try:
            import time as _time
            redis_conn = get_redis_connection()
            last_start_key = f"gb:{bot_manager.user_id}:last_start:{chat_id}"
            last_start = redis_conn.get(last_start_key)
            now = int(_time.time())

            if last_start and now - int(last_start) < 5:
                logger.info(f"Bloqueado /start duplicado em menos de 5s: chat_id={chat_id}")
                return

            redis_conn.set(last_start_key, now, ex=5)
        except Exception as e:
            logger.warning(f"Erro ao verificar anti-duplicacao de /start: {e} - continuando processamento")

        try:
            from flask import current_app
            from internal_logic.core.extensions import db
            from internal_logic.core.models import BotUser
            with current_app.app_context():
                bot_user = BotUser.query.filter_by(
                    bot_id=bot_id,
                    telegram_user_id=telegram_user_id,
                    archived=False
                ).first()

                if bot_user and bot_user.welcome_sent:
                    logger.info(f"Flag welcome_sent resetada para permitir novo /start: chat_id={chat_id}")
                    bot_user.welcome_sent = False
                    bot_user.welcome_sent_at = None
                    db.session.commit()
        except Exception as e:
            logger.warning(f"Erro ao verificar/resetar welcome_sent: {e} - continuando processamento")

        if not bot_manager._check_start_lock(chat_id):
            logger.warning(f"/start duplicado bloqueado - ja esta processando")
            return

        from flask import current_app
        from internal_logic.core.extensions import db
        from internal_logic.core.models import Bot, BotUser

        with current_app.app_context():
            bot_manager._reset_user_funnel(bot_id, chat_id, telegram_user_id, db_session=db.session)

            bot = db.session.get(Bot, bot_id)
            if bot and bot.config:
                config = bot.config.to_dict()
            else:
                config = config or {}

            bot_user_check = BotUser.query.filter_by(
                bot_id=bot_id,
                telegram_user_id=telegram_user_id,
                archived=False
            ).first()

            if bot_user_check and bot_user_check.welcome_sent:
                logger.warning(f"welcome_sent ainda True apos reset - forcando reset novamente")
                bot_user_check.welcome_sent = False
                bot_user_check.welcome_sent_at = None
                db.session.commit()

            try:
                from tasks_async import task_queue, process_start_async
                if task_queue and bot_manager.user_id:
                    task_queue.enqueue(
                        process_start_async,
                        bot_manager.user_id,
                        bot_id=bot_id,
                        token=token,
                        config=config,
                        chat_id=chat_id,
                        message=message,
                        start_param=start_param
                    )
                elif task_queue:
                    task_queue.enqueue(
                        process_start_async,
                        0,
                        bot_id=bot_id,
                        token=token,
                        config=config,
                        chat_id=chat_id,
                        message=message,
                        start_param=start_param
                    )
            except Exception as e:
                logger.warning(f"Erro ao enfileirar task async: {e}")

        is_flow_active = checkActiveFlow(config)

        should_send_welcome = True

        logger.info(f"Verificacao de modo: is_flow_active={is_flow_active}, should_send_welcome={should_send_welcome}")

        if is_flow_active:
            logger.info(f"FLUXO VISUAL ATIVO - Executando fluxo visual")
            logger.info(f"BLOQUEANDO welcome_message, main_buttons, redirect_buttons, welcome_audio")

            should_send_welcome = False

            try:
                logger.info(f"Chamando _execute_flow...")
                logger.info(f"Config flow_enabled: {config.get('flow_enabled')}")
                logger.info(f"Config flow_steps count: {len(config.get('flow_steps', [])) if isinstance(config.get('flow_steps'), list) else 'N/A'}")
                logger.info(f"Config flow_start_step_id: {config.get('flow_start_step_id')}")

                bot_manager._execute_flow(bot_id, token, config, chat_id, telegram_user_id)
                logger.info(f"_execute_flow concluido sem excecoes")

                from flask import current_app
                from internal_logic.core.extensions import db
                from internal_logic.core.models import BotUser

                with current_app.app_context():
                    try:
                        bot_user_update = BotUser.query.filter_by(
                            bot_id=bot_id,
                            telegram_user_id=telegram_user_id
                        ).first()
                        if bot_user_update:
                            bot_user_update.welcome_sent = True
                            from internal_logic.core.models import get_brazil_time
                            bot_user_update.welcome_sent_at = get_brazil_time()
                            db.session.commit()
                            logger.info(f"Fluxo iniciado - welcome_sent=True")
                    except Exception as e:
                        logger.error(f"Erro ao marcar welcome_sent: {e}")

                logger.info(f"Fluxo visual executado com sucesso - should_send_welcome=False (confirmado)")

            except Exception as e:
                logger.error(f"Erro ao executar fluxo: {e}", exc_info=True)
                should_send_welcome = False
                logger.warning(f"Fluxo falhou mas welcome_message esta BLOQUEADO (flow_enabled=True)")
                logger.warning(f"Usuario nao recebera welcome_message nem mensagem do fluxo")
        else:
            logger.info(f"Fluxo visual desabilitado ou vazio - usando welcome_message normalmente")
            should_send_welcome = True
            logger.info(f"should_send_welcome confirmado como True (fluxo nao ativo)")

        logger.info(f"DECISAO FINAL: should_send_welcome={should_send_welcome} (is_flow_active={is_flow_active})")
        logger.info(f"Condicao para enviar welcome: should_send_welcome={should_send_welcome}")

        if should_send_welcome:
            logger.info(f"ENVIANDO welcome_message - fluxo visual NAO esta ativo ou esta vazio")
            welcome_message = config.get('welcome_message', 'Ola! Bem-vindo!')
            welcome_media_url = config.get('welcome_media_url')
            welcome_media_type = config.get('welcome_media_type', 'video')
            welcome_audio_enabled = config.get('welcome_audio_enabled', False)
            welcome_audio_url = config.get('welcome_audio_url', '')
            main_buttons = config.get('main_buttons', [])
            redirect_buttons = config.get('redirect_buttons', [])

            buttons = []
            for index, btn in enumerate(main_buttons):
                if btn.get('text') and btn.get('price'):
                    price = float(btn.get('price', 0))
                    button_text = bot_manager._format_button_text(btn['text'], price, btn.get('price_position'))
                    buttons.append({
                        'text': button_text,
                        'callback_data': f"buy_{index}"
                    })

            for btn in redirect_buttons:
                if btn.get('text') and btn.get('url'):
                    buttons.append({
                        'text': btn['text'],
                        'url': btn['url']
                    })

            valid_media = False
            if welcome_media_url:
                if '/c/' not in welcome_media_url and welcome_media_url.startswith('http'):
                    valid_media = True
                else:
                    logger.info(f"Midia de canal privado detectada - enviando so texto")

            result = bot_manager.send_funnel_step_sequential(
                token=token,
                chat_id=str(chat_id),
                text=welcome_message,
                media_url=welcome_media_url if valid_media else None,
                media_type=welcome_media_type if valid_media else None,
                buttons=buttons,
                delay_between=0.2
            )

            if result:
                logger.info(f"Mensagem /start enviada com {len(buttons)} botao(oes)")

                from flask import current_app
                from internal_logic.core.extensions import db
                from internal_logic.core.models import BotUser

                with current_app.app_context():
                    try:
                        bot_user_update = BotUser.query.filter_by(
                            bot_id=bot_id,
                            telegram_user_id=telegram_user_id
                        ).first()
                        if bot_user_update:
                            bot_user_update.welcome_sent = True
                            from internal_logic.core.models import get_brazil_time
                            bot_user_update.welcome_sent_at = get_brazil_time()
                            db.session.commit()
                            logger.info(f"Marcado como welcome_sent=True")
                    except Exception as e:
                        logger.error(f"Erro ao marcar welcome_sent: {e}")

                if welcome_audio_enabled and welcome_audio_url:
                    logger.info(f"Enviando audio complementar...")
                    audio_result = bot_manager.send_telegram_message(
                        token=token,
                        chat_id=str(chat_id),
                        message="",
                        media_url=welcome_audio_url,
                        media_type='audio',
                        buttons=None
                    )
                    if audio_result:
                        logger.info(f"Audio complementar enviado")
                    else:
                        logger.warning(f"Falha ao enviar audio complementar")
            else:
                logger.error(f"Falha ao enviar mensagem")
        else:
            logger.info(f"should_send_welcome=False - welcome_message BLOQUEADO (fluxo visual ativo)")
            logger.info(f"Apenas o fluxo visual sera executado, sem welcome_message tradicional")

        try:
            from flask import current_app
            from internal_logic.core.extensions import db
            from internal_logic.core.models import Bot
            with current_app.app_context():
                bot = db.session.get(Bot, bot_id)
                if bot:
                    try:
                        if bot_manager.socketio:
                            bot_manager.socketio.emit('bot_interaction', {
                                'bot_id': bot_id,
                                'type': 'start',
                                'chat_id': chat_id,
                                'user': message.get('from', {}).get('first_name', 'Usuario')
                            }, room=f'user_{bot.user_id}')
                    except Exception as ws_error:
                        logger.debug(f"Falha nao-critica na UI (WebSocket ignorado): {ws_error}")
                        pass
        except Exception as db_error:
            logger.warning(f"Erro ao buscar bot para WebSocket (nao critico): {db_error}")

        logger.info(f"{'='*60}\n")

    except Exception as e:
        logger.error(f"Erro ao processar /start: {e}")
        import traceback
        traceback.print_exc()
