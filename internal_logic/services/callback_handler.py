"""
Callback Handler Service
=========================
Processa cliques em botoes do Telegram (callbacks).
Extraido do BotManager (Fase 10).
"""

import logging
import requests
from typing import Dict, Any

from internal_logic.core.redis_manager import get_redis_connection
from internal_logic.services.bot_messenger import checkActiveFlow

logger = logging.getLogger(__name__)


def handle_callback_query(bot_manager, bot_id: int, token: str, config: Dict[str, Any],
                          callback: Dict[str, Any]):
    try:
        callback_data = callback.get('data', '')
        chat_id = callback['message']['chat']['id']
        user_info = callback.get('from', {})

        logger.info(f"\n{'='*60}")
        logger.info(f"CLIQUE NO BOTAO: {callback_data}")
        logger.info(f"Cliente: {user_info.get('first_name')}")
        logger.info(f"{'='*60}")

        callback_id = callback['id']
        url = f"https://api.telegram.org/bot{token}/answerCallbackQuery"

        if callback_data.startswith('flow_') and not callback_data.startswith('flow_step_'):
            try:
                parts = callback_data.split('_', 2)
                if len(parts) == 3:
                    step_id = parts[1]
                    btn_index = int(parts[2])

                    requests.post(url, json={
                        'callback_query_id': callback_id,
                        'text': 'Processando...'
                    }, timeout=3)

                    telegram_user_id = str(user_info.get('id', ''))

                    import json
                    flow_steps_raw = config.get('flow_steps', [])
                    if isinstance(flow_steps_raw, str):
                        flow_steps = json.loads(flow_steps_raw)
                    else:
                        flow_steps = flow_steps_raw if isinstance(flow_steps_raw, list) else []

                    step = bot_manager._find_step_by_id(flow_steps, step_id)
                    if not step:
                        logger.warning(f"Step {step_id} nao encontrado no fluxo")
                        return

                    custom_buttons = step.get('config', {}).get('custom_buttons', [])
                    if btn_index >= len(custom_buttons):
                        logger.warning(f"Indice de botao invalido: {btn_index} (total: {len(custom_buttons)})")
                        return

                    target_step = custom_buttons[btn_index].get('target_step')
                    if not target_step:
                        logger.warning(f"Botao {btn_index} nao tem target_step definido")
                        return

                    logger.info(f"[FLOW] Callback customizado: step={step_id}, button={btn_index}, target={target_step}")

                    try:
                        redis_conn = get_redis_connection()
                        if redis_conn:
                            current_step_key = f"flow_current_step:{bot_id}:{telegram_user_id}"
                            redis_conn.delete(current_step_key)
                    except Exception as e:
                        logger.warning(f"Erro ao limpar step atual do Redis: {e}")

                    flow_snapshot = bot_manager._get_flow_snapshot_from_redis(bot_id, telegram_user_id)

                    bot_manager._execute_flow_recursive(
                        bot_id, token, config,
                        chat_id, telegram_user_id,
                        target_step,
                        recursion_depth=0,
                        visited_steps=set(),
                        flow_snapshot=flow_snapshot
                    )
                    return

            except ValueError as e:
                logger.error(f"[FLOW] Erro ao parsear callback flow_: {e}")
            except Exception as e:
                logger.error(f"[FLOW] Erro callback flow_: {e}", exc_info=True)
            return

        if callback_data.startswith('flow_step_'):
            requests.post(url, json={
                'callback_query_id': callback_id,
                'text': 'Processando...'
            }, timeout=3)

            callback_without_prefix = callback_data.replace('flow_step_', '')

            if '_btn_' in callback_without_prefix:
                parts = callback_without_prefix.rsplit('_btn_', 1)
                source_step_id = parts[0]
                action = 'btn_' + parts[1] if len(parts) > 1 else ''
            else:
                parts = callback_without_prefix.split('_', 1)
                source_step_id = parts[0]
                action = parts[1] if len(parts) > 1 else ''

            logger.info(f"Botao contextual clicado: step={source_step_id}, action={action}")

            flow_steps = config.get('flow_steps', [])
            source_step = bot_manager._find_step_by_id(flow_steps, source_step_id)

            if source_step:
                telegram_user_id = str(user_info.get('id', ''))

                conditions = source_step.get('conditions', [])
                if conditions and len(conditions) > 0:
                    try:
                        redis_conn = get_redis_connection()
                        current_step_key = f"flow_current_step:{bot_id}:{telegram_user_id}"

                        next_step_id = bot_manager._evaluate_conditions(
                            source_step,
                            user_input=callback_data,
                            context={},
                            bot_id=bot_id,
                            telegram_user_id=telegram_user_id,
                            step_id=source_step_id
                        )

                        if next_step_id:
                            logger.info(f"Condicao de button_click matchou! Continuando para step: {next_step_id}")
                            redis_conn.delete(current_step_key)
                            bot_manager._execute_flow_recursive(bot_id, token, config, chat_id, telegram_user_id, next_step_id)
                            return
                        else:
                            logger.info(f"Nenhuma condicao de button_click matchou para callback: {callback_data}")
                    except Exception as e:
                        logger.warning(f"Erro ao avaliar condicoes de button_click: {e} - usando target_step do botao")

                step_config = source_step.get('config', {})
                custom_buttons = step_config.get('custom_buttons', [])

                btn_idx = None
                if action.startswith('btn_'):
                    try:
                        btn_idx = int(action.replace('btn_', ''))
                    except:
                        pass

                if btn_idx is not None and btn_idx < len(custom_buttons):
                    target_step_id = custom_buttons[btn_idx].get('target_step')
                    if target_step_id:
                        logger.info(f"Continuando fluxo para step: {target_step_id} (target_step do botao)")
                        try:
                            redis_conn = get_redis_connection()
                            if redis_conn:
                                current_step_key = f"flow_current_step:{bot_id}:{telegram_user_id}"
                                redis_conn.delete(current_step_key)
                        except:
                            pass
                        flow_snapshot = bot_manager._get_flow_snapshot_from_redis(bot_id, telegram_user_id)
                        bot_manager._execute_flow_recursive(
                            bot_id, token, config, chat_id, telegram_user_id, target_step_id,
                            recursion_depth=0, visited_steps=set(), flow_snapshot=flow_snapshot
                        )
                        return
                    else:
                        logger.warning(f"Botao contextual sem target_step definido")
                else:
                    logger.warning(f"Indice de botao invalido: {btn_idx}")
            else:
                logger.warning(f"Step nao encontrado: {source_step_id}")

            return

        if callback_data.startswith('verify_'):
            requests.post(url, json={
                'callback_query_id': callback_id,
                'text': 'Verificando pagamento...'
            }, timeout=3)
            payment_id = callback_data.replace('verify_', '')
            logger.info(f"Verificando pagamento: {payment_id}")

            bot_manager._handle_verify_payment(bot_id, token, chat_id, payment_id, user_info)

        elif callback_data.startswith('rmkt_'):
            parts = callback_data.replace('rmkt_', '').split('_')
            campaign_id = int(parts[0])
            btn_idx = int(parts[1])

            requests.post(url, json={
                'callback_query_id': callback_id,
                'text': 'Gerando PIX da oferta...'
            }, timeout=3)

            from flask import current_app
            from internal_logic.core.extensions import db
            from internal_logic.core.models import RemarketingCampaign

            with current_app.app_context():
                campaign = db.session.get(RemarketingCampaign, campaign_id)
                if campaign and campaign.buttons:
                    buttons_list = campaign.buttons
                    if isinstance(campaign.buttons, str):
                        import json
                        try:
                            buttons_list = json.loads(campaign.buttons)
                        except:
                            buttons_list = []

                    if btn_idx < len(buttons_list):
                        btn = buttons_list[btn_idx]
                        price = float(btn.get('price', 0))
                        description = btn.get('description', 'Produto Remarketing')
                else:
                    price = 0
                    description = 'Produto Remarketing'

            logger.info(f"COMPRA VIA REMARKETING | Campanha: {campaign_id} | Produto: {description} | Valor: R$ {price:.2f}")

            pix_data = bot_manager._generate_pix_payment(
                bot_id=bot_id,
                amount=price,
                description=description,
                customer_name=user_info.get('first_name', ''),
                customer_username=user_info.get('username', ''),
                customer_user_id=str(user_info.get('id', '')),
                is_remarketing=True,
                remarketing_campaign_id=campaign_id
            )
            if pix_data and pix_data.get('rate_limit'):
                wait_time_msg = pix_data.get('wait_time', 'alguns segundos')
                bot_manager.send_telegram_message(
                    chat_id=chat_id,
                    message=f"Aguarde {wait_time_msg}...\n\nVoce ja gerou um PIX agora mesmo. Verifique se recebeu o QR Code acima antes de tentar novamente.",
                    token=token
                )
                return

            if pix_data and pix_data.get('pix_code'):
                payment_message = f"""Produto: {description}
Valor: R$ {price:.2f}

PIX Copia e Cola:
<code>{pix_data.get('pix_code')}</code>

Toque no codigo acima para copiar

Valido por: 30 minutos

Apos pagar, clique no botao abaixo para verificar e receber seu acesso!"""

                verify_button = [{
                    'text': 'Verificar Pagamento',
                    'callback_data': f"verify_{pix_data.get('payment_id')}"
                }]

                bot_manager.send_telegram_message(
                    token=token,
                    chat_id=str(chat_id),
                    message=payment_message,
                    buttons=verify_button
                )

                logger.info(f"PIX ENVIADO (Remarketing)! ID: {pix_data.get('payment_id')}")

                from flask import current_app
                from internal_logic.core.extensions import db
                from internal_logic.core.models import RemarketingCampaign
                with current_app.app_context():
                    campaign = RemarketingCampaign.query.get(campaign_id)
                    if campaign:
                        campaign.total_clicks += 1
                        db.session.commit()
            else:
                bot_manager.send_telegram_message(
                    token=token,
                    chat_id=str(chat_id),
                    message="Erro ao gerar PIX. Entre em contato com o suporte."
                )

        elif callback_data.startswith('bump_yes_'):
            requests.post(url, json={
                'callback_query_id': callback_id,
                'text': 'Order bump adicionado! Gerando PIX...'
            }, timeout=3)

            button_index = int(callback_data.replace('bump_yes_', ''))

            main_buttons = config.get('main_buttons', [])
            if button_index < len(main_buttons):
                button_data = main_buttons[button_index]
                original_price = float(button_data.get('price', 0))
                description = button_data.get('description', 'Produto')
                order_bump = button_data.get('order_bump', {})
                bump_price = float(order_bump.get('price', 0))
            else:
                original_price = 0
                bump_price = 0
                description = 'Produto'

            total_price = original_price + bump_price
            final_description = f"{description} + Bonus"

            logger.info(f"Cliente ACEITOU order bump! Total: R$ {total_price:.2f}")

            pix_data = bot_manager._generate_pix_payment(
                bot_id=bot_id,
                amount=total_price,
                description=final_description,
                customer_name=user_info.get('first_name', ''),
                customer_username=user_info.get('username', ''),
                customer_user_id=str(user_info.get('id', '')),
                order_bump_shown=True,
                order_bump_accepted=True,
                order_bump_value=bump_price
            )

            if pix_data and pix_data.get('pix_code'):
                payment_message = f"""Produto: {final_description}
Valor: R$ {total_price:.2f}

PIX Copia e Cola:
<code>{pix_data['pix_code']}</code>

Toque no codigo acima para copiar

Valido por: 30 minutos

Apos pagar, clique no botao abaixo para verificar e receber seu acesso!"""

                buttons = [{
                    'text': 'Verificar Pagamento',
                    'callback_data': f'verify_{pix_data.get("payment_id")}'
                }]

                bot_manager.send_telegram_message(
                    token=token,
                    chat_id=str(chat_id),
                    message=payment_message.strip(),
                    buttons=buttons
                )

                logger.info(f"PIX gerado COM order bump!")

                from flask import current_app
                from internal_logic.core.extensions import db
                from internal_logic.core.models import Bot as BotModel

                with current_app.app_context():
                    bot = db.session.get(BotModel, bot_id)
                    if bot and bot.config:
                        config = bot.config.to_dict()
                    else:
                        config = {}

                logger.info(f"DEBUG Downsells (Order Bump) - bot_id: {bot_id}")
                logger.info(f"DEBUG Downsells (Order Bump) - enabled: {config.get('downsells_enabled', False)}")
                logger.info(f"DEBUG Downsells (Order Bump) - list: {config.get('downsells', [])}")

                if config.get('downsells_enabled', False):
                    downsells = config.get('downsells', [])
                    logger.info(f"DEBUG Downsells (Order Bump) - downsells encontrados: {len(downsells)}")
                    if downsells and len(downsells) > 0:
                        bot_manager.schedule_downsells(
                            bot_id=bot_id,
                            payment_id=pix_data.get('payment_id'),
                            chat_id=chat_id,
                            downsells=downsells,
                            original_price=total_price,
                            original_button_index=button_index
                        )
                    else:
                        logger.warning(f"Downsells habilitados mas lista vazia! (Order Bump)")
                else:
                    logger.info(f"Downsells desabilitados ou nao configurados (Order Bump)")

        elif callback_data.startswith('bump_no_'):
            requests.post(url, json={
                'callback_query_id': callback_id,
                'text': 'Gerando PIX do valor original...'
            }, timeout=3)

            button_index = int(callback_data.replace('bump_no_', ''))

            main_buttons = config.get('main_buttons', [])
            if button_index < len(main_buttons):
                button_data = main_buttons[button_index]
                price = float(button_data.get('price', 0))
                description = button_data.get('description', 'Produto')
            else:
                price = 0
                description = 'Produto'

            logger.info(f"Cliente RECUSOU order bump. Gerando PIX do valor original...")

            pix_data = bot_manager._generate_pix_payment(
                bot_id=bot_id,
                amount=price,
                description=description,
                customer_name=user_info.get('first_name', ''),
                customer_username=user_info.get('username', ''),
                customer_user_id=str(user_info.get('id', '')),
                order_bump_shown=True,
                order_bump_accepted=False,
                order_bump_value=0.0
            )

            if pix_data and pix_data.get('pix_code'):
                payment_message = f"""Produto: {description}
Valor: R$ {price:.2f}

PIX Copia e Cola:
<code>{pix_data['pix_code']}</code>

Toque no codigo acima para copiar

Valido por: 30 minutos

Apos pagar, clique no botao abaixo para verificar e receber seu acesso!"""

                buttons = [{
                    'text': 'Verificar Pagamento',
                    'callback_data': f'verify_{pix_data.get("payment_id")}'
                }]

                bot_manager.send_telegram_message(
                    token=token,
                    chat_id=str(chat_id),
                    message=payment_message.strip(),
                    buttons=buttons
                )

                logger.info(f"PIX gerado SEM order bump!")

                from flask import current_app
                from internal_logic.core.extensions import db
                from internal_logic.core.models import Bot as BotModel

                with current_app.app_context():
                    bot = db.session.get(BotModel, bot_id)
                    if bot and bot.config:
                        config = bot.config.to_dict()
                    else:
                        config = {}

                logger.info(f"DEBUG Downsells (bump_no) - bot_id: {bot_id}")
                logger.info(f"DEBUG Downsells (bump_no) - enabled: {config.get('downsells_enabled', False)}")
                logger.info(f"DEBUG Downsells (bump_no) - list: {config.get('downsells', [])}")

                if config.get('downsells_enabled', False):
                    downsells = config.get('downsells', [])
                    logger.info(f"DEBUG Downsells (bump_no) - downsells encontrados: {len(downsells)}")
                    if downsells and len(downsells) > 0:
                        bot_manager.schedule_downsells(
                            bot_id=bot_id,
                            payment_id=pix_data.get('payment_id'),
                            chat_id=chat_id,
                            downsells=downsells,
                            original_price=price,
                            original_button_index=button_index
                        )
                    else:
                        logger.warning(f"Downsells habilitados mas lista vazia! (bump_no)")
                else:
                    logger.info(f"Downsells desabilitados ou nao configurados (bump_no)")

        elif callback_data.startswith('multi_bump_yes_'):
            import json as json_lib
            parts = callback_data.replace('multi_bump_yes_', '').split('_')
            chat_id_from_callback = int(parts[0])
            user_key = f"orderbump_{chat_id_from_callback}"
            bump_index = int(parts[1])
            total_price = float(parts[2]) / 100

            logger.info(f"Order Bump {bump_index + 1} ACEITO | User: {user_key} | Valor Total: R$ {total_price:.2f}")

            requests.post(url, json={
                'callback_query_id': callback_id,
                'text': 'Bonus adicionado!'
            }, timeout=3)

            redis_conn = get_redis_connection()
            session_key = f"gb:ob_session:{user_key}"
            pix_cache_key = f"gb:pix_cache:{user_key}"

            session_json = redis_conn.get(session_key)
            if session_json:
                session = json_lib.loads(session_json)

                session_chat_id = session.get('chat_id')
                if session_chat_id and session_chat_id != chat_id_from_callback:
                    logger.error(f"Chat ID mismatch: callback de chat {chat_id_from_callback}, mas sessao e do chat {session_chat_id}!")
                    return

                session_bot_id = session.get('bot_id', bot_id)

                if session_bot_id != bot_id:
                    logger.warning(f"Bot ID mismatch: callback de bot {bot_id}, mas sessao e do bot {session_bot_id}. Usando bot_id da sessao.")
                    session_bot_data = bot_manager.bot_state.get_bot_data(session_bot_id)
                    if session_bot_data:
                        token = session_bot_data['token']
                        bot_id = session_bot_id
                    else:
                        logger.error(f"Bot {session_bot_id} da sessao nao esta mais ativo no Redis!")
                        return

                chat_id = session.get('chat_id', chat_id)

                current_bump = session['order_bumps'][bump_index]
                bump_price = float(current_bump.get('price', 0))

                session['accepted_bumps'].append(current_bump)
                session['total_bump_value'] += bump_price
                session['current_index'] = bump_index + 1

                logger.info(f"Bump aceito: {current_bump.get('description', 'Bonus')} (+R$ {bump_price:.2f})")

                redis_conn.setex(session_key, 600, json_lib.dumps(session))

                bot_manager._show_next_order_bump(bot_id, token, chat_id, user_key)
            else:
                pix_cache_json = redis_conn.get(pix_cache_key)
                if pix_cache_json:
                    cached = json_lib.loads(pix_cache_json)
                    logger.info(f"Callback 'SIM' - Reenviando PIX do cache Redis: {cached['pix_data'].get('payment_id')}")
                    bot_manager._send_pix_message(token, chat_id, cached['pix_data'], "Reenviando seu PIX:")
                    return

                logger.warning(f"Sessao de order bump nao encontrada no Redis (ja finalizada): {user_key} | Callback ja processado")

        elif callback_data.startswith('multi_bump_no_'):
            import json as json_lib
            parts = callback_data.replace('multi_bump_no_', '').split('_')
            chat_id_from_callback = int(parts[0])
            user_key = f"orderbump_{chat_id_from_callback}"
            bump_index = int(parts[1])
            current_price = float(parts[2]) / 100

            logger.info(f"Order Bump {bump_index + 1} RECUSADO | User: {user_key} | Valor Atual: R$ {current_price:.2f}")

            requests.post(url, json={
                'callback_query_id': callback_id,
                'text': 'Bonus recusado'
            }, timeout=3)

            redis_conn = get_redis_connection()
            session_key = f"gb:ob_session:{user_key}"
            pix_cache_key = f"gb:pix_cache:{user_key}"

            session_json = redis_conn.get(session_key)
            if session_json:
                session = json_lib.loads(session_json)

                session_chat_id = session.get('chat_id')
                if session_chat_id and session_chat_id != chat_id_from_callback:
                    logger.error(f"Chat ID mismatch: callback de chat {chat_id_from_callback}, mas sessao e do chat {session_chat_id}!")
                    return

                session_bot_id = session.get('bot_id', bot_id)

                if session_bot_id != bot_id:
                    logger.warning(f"Bot ID mismatch: callback de bot {bot_id}, mas sessao e do bot {session_bot_id}. Usando bot_id da sessao.")
                    session_bot_data = bot_manager.bot_state.get_bot_data(session_bot_id)
                    if session_bot_data:
                        token = session_bot_data['token']
                        bot_id = session_bot_id
                    else:
                        logger.error(f"Bot {session_bot_id} da sessao nao esta mais ativo no Redis!")
                        return

                chat_id = session.get('chat_id', chat_id)

                session['current_index'] = bump_index + 1

                logger.info(f"Bump recusado: {session['order_bumps'][bump_index].get('description', 'Bonus')}")

                redis_conn.setex(session_key, 600, json_lib.dumps(session))

                bot_manager._show_next_order_bump(bot_id, token, chat_id, user_key)
            else:
                pix_cache_json = redis_conn.get(pix_cache_key)
                if pix_cache_json:
                    cached = json_lib.loads(pix_cache_json)
                    logger.info(f"Callback 'NAO' - Reenviando PIX do cache Redis: {cached['pix_data'].get('payment_id')}")
                    bot_manager._send_pix_message(token, chat_id_from_callback, cached['pix_data'], "Reenviando seu PIX:")
                    return

                logger.warning(f"Sessao de order bump nao encontrada no Redis (ja finalizada): {user_key} | Callback ja processado")

        elif callback_data.startswith('downsell_bump_yes_'):
            parts = callback_data.replace('downsell_bump_yes_', '').split('_')
            downsell_idx = int(parts[0])
            total_price = float(parts[1]) / 100

            logger.info(f"Order Bump Downsell ACEITO | Downsell: {downsell_idx} | Valor Total: R$ {total_price:.2f}")

            requests.post(url, json={
                'callback_query_id': callback_id,
                'text': 'Gerando pagamento PIX...'
            }, timeout=3)

            pix_data = bot_manager._generate_pix_payment(
                bot_id=bot_id,
                amount=total_price,
                description="Oferta Especial + Bonus",
                customer_name=user_info.get('first_name', ''),
                customer_username=user_info.get('username', ''),
                customer_user_id=str(user_info.get('id', '')),
                order_bump_shown=True,
                order_bump_accepted=True,
                order_bump_value=total_price - (total_price * 0.7),
                is_downsell=True,
                downsell_index=downsell_idx
            )

            if pix_data and pix_data.get('pix_code'):
                payment_message = f"""Produto: Oferta Especial + Bonus
Valor: R$ {total_price:.2f}

PIX Copia e Cola:
<code>{pix_data['pix_code']}</code>

Toque no codigo acima para copiar

Valido por: 30 minutos

Apos pagar, clique no botao abaixo para verificar e receber seu acesso!"""

                buttons = [{
                    'text': 'Verificar Pagamento',
                    'callback_data': f'verify_{pix_data.get("payment_id")}'
                }]

                bot_manager.send_telegram_message(
                    token=token,
                    chat_id=str(chat_id),
                    message=payment_message.strip(),
                    buttons=buttons
                )

                logger.info(f"PIX DOWNSELL COM ORDER BUMP ENVIADO! ID: {pix_data.get('payment_id')}")
            else:
                bot_manager.send_telegram_message(
                    token=token,
                    chat_id=str(chat_id),
                    message="Erro ao gerar PIX. Entre em contato com o suporte."
                )

        elif callback_data.startswith('downsell_bump_no_'):
            parts = callback_data.replace('downsell_bump_no_', '').split('_')
            downsell_idx = int(parts[0])
            downsell_price = float(parts[1]) / 100

            logger.info(f"Order Bump Downsell RECUSADO | Downsell: {downsell_idx} | Valor: R$ {downsell_price:.2f}")

            requests.post(url, json={
                'callback_query_id': callback_id,
                'text': 'Gerando pagamento PIX...'
            }, timeout=3)

            pix_data = bot_manager._generate_pix_payment(
                bot_id=bot_id,
                amount=downsell_price,
                description="Oferta Especial",
                customer_name=user_info.get('first_name', ''),
                customer_username=user_info.get('username', ''),
                customer_user_id=str(user_info.get('id', '')),
                order_bump_shown=True,
                order_bump_accepted=False,
                order_bump_value=0.0,
                is_downsell=True,
                downsell_index=downsell_idx
            )

            if pix_data and pix_data.get('pix_code'):
                payment_message = f"""Produto: Oferta Especial
Valor: R$ {downsell_price:.2f}

PIX Copia e Cola:
<code>{pix_data['pix_code']}</code>

Toque no codigo acima para copiar

Valido por: 30 minutos

Apos pagar, clique no botao abaixo para verificar e receber seu acesso!"""

                buttons = [{
                    'text': 'Verificar Pagamento',
                    'callback_data': f'verify_{pix_data.get("payment_id")}'
                }]

                bot_manager.send_telegram_message(
                    token=token,
                    chat_id=str(chat_id),
                    message=payment_message.strip(),
                    buttons=buttons
                )

                logger.info(f"PIX DOWNSELL SEM ORDER BUMP ENVIADO! ID: {pix_data.get('payment_id')}")
            else:
                bot_manager.send_telegram_message(
                    token=token,
                    chat_id=str(chat_id),
                    message="Erro ao gerar PIX. Entre em contato com o suporte."
                )

        elif callback_data.startswith('dwnsl_'):
            parts = callback_data.replace('dwnsl_', '').split('_')
            downsell_idx = int(parts[0])
            button_idx = int(parts[1])
            price = float(parts[2]) / 100

            from flask import current_app
            from internal_logic.core.extensions import db
            from internal_logic.core.models import Bot as BotModel

            product_name = f'Produto {button_idx + 1}'
            description = f"Downsell {downsell_idx + 1} - {product_name}"

            with current_app.app_context():
                bot = db.session.get(BotModel, bot_id)
                if bot and bot.config:
                    fresh_config = bot.config.to_dict()
                    main_buttons = fresh_config.get('main_buttons', [])
                    if button_idx < len(main_buttons):
                        product_name = main_buttons[button_idx].get('text', product_name)
                        description = f"{product_name} (Downsell {downsell_idx + 1})"

            logger.info(f"DOWNSELL PERCENTUAL CLICADO | Downsell: {downsell_idx} | Produto: {product_name} | Valor: R$ {price:.2f}")

            requests.post(url, json={
                'callback_query_id': callback_id,
                'text': 'Gerando pagamento PIX...'
            }, timeout=3)

            pix_data = bot_manager._generate_pix_payment(
                bot_id=bot_id,
                amount=price,
                description=description,
                customer_name=user_info.get('first_name', ''),
                customer_username=user_info.get('username', ''),
                customer_user_id=str(user_info.get('id', '')),
                is_downsell=True,
                downsell_index=downsell_idx
            )

            if pix_data and pix_data.get('pix_code'):
                payment_message = f"""Produto: {description}
Valor: R$ {price:.2f}

PIX Copia e Cola:
<code>{pix_data['pix_code']}</code>

Toque no codigo acima para copiar

Valido por: 30 minutos

Apos pagar, clique no botao abaixo para verificar e receber seu acesso!"""

                buttons = [{
                    'text': 'Verificar Pagamento',
                    'callback_data': f'verify_{pix_data.get("payment_id")}'
                }]

                bot_manager.send_telegram_message(
                    token=token,
                    chat_id=str(chat_id),
                    message=payment_message.strip(),
                    buttons=buttons
                )

                logger.info(f"PIX DOWNSELL PERCENTUAL ENVIADO! ID: {pix_data.get('payment_id')}")
            else:
                bot_manager.send_telegram_message(
                    token=token,
                    chat_id=str(chat_id),
                    message="Erro ao gerar PIX. Entre em contato com o suporte."
                )

        elif callback_data.startswith('downsell_'):
            parts = callback_data.replace('downsell_', '').split('_')
            logger.info(f"DEBUG downsell callback_data: {callback_data}")
            logger.info(f"DEBUG downsell parts: {parts}")

            downsell_idx = int(parts[0])

            if len(parts) == 4:
                original_button_idx = int(parts[1])
                price_cents = int(parts[2])
                logger.info(f"Formato ANTIGO detectado: idx={downsell_idx}, btn={original_button_idx}, price_cents={price_cents}")
            elif len(parts) == 3:
                price_cents = int(parts[1])
                original_button_idx = int(parts[2])
                logger.info(f"Formato NOVO detectado: idx={downsell_idx}, price_cents={price_cents}, btn={original_button_idx}")
            else:
                logger.error(f"Formato de callback_data invalido: {callback_data}")
                return

            price = float(price_cents) / 100

            logger.info(f"DEBUG downsell parsed: idx={downsell_idx}, price_cents={price_cents}, price={price:.2f}, original_button={original_button_idx}")

            if price <= 0:
                logger.error(f"Downsell com preco invalido: R$ {price:.2f} (centavos: {price_cents})")
                logger.error(f"CALLBACK_DATA PROBLEMATICO: {callback_data}")
                logger.error(f"PARTS PROBLEMATICAS: {parts}")
                return

            if price < 1.00:
                logger.warning(f"Downsell com preco muito baixo (R$ {price:.2f}), calculando valor real")

                from flask import current_app
                from internal_logic.core.extensions import db
                from internal_logic.core.models import Bot as BotModel

                with current_app.app_context():
                    bot = db.session.get(BotModel, bot_id)
                    if bot and bot.config:
                        config = bot.config.to_dict()
                        downsells = config.get('downsells', [])

                        if downsell_idx < len(downsells):
                            downsell_config = downsells[downsell_idx]
                            discount_percentage = float(downsell_config.get('discount_percentage', 50))

                            main_buttons = config.get('main_buttons', [])
                            if original_button_idx < len(main_buttons):
                                original_button = main_buttons[original_button_idx]
                                original_price = float(original_button.get('price', 0))

                                if original_price > 0:
                                    price = original_price * (1 - discount_percentage / 100)
                                    logger.info(f"Valor real calculado: R$ {original_price:.2f} com {discount_percentage}% OFF = R$ {price:.2f}")
                                else:
                                    price = 9.97
                                    logger.warning(f"Preco original nao encontrado, usando fallback R$ {price:.2f}")
                            else:
                                price = 9.97
                                logger.warning(f"Botao original nao encontrado, usando fallback R$ {price:.2f}")
                        else:
                            price = 9.97
                            logger.warning(f"Configuracao de downsell nao encontrada, usando fallback R$ {price:.2f}")
                    else:
                        price = 9.97
                        logger.warning(f"Configuracao do bot nao encontrada, usando fallback R$ {price:.2f}")

            from flask import current_app
            from internal_logic.core.extensions import db
            from internal_logic.core.models import Bot as BotModel

            description = "Oferta Especial"

            with current_app.app_context():
                bot = db.session.get(BotModel, bot_id)
                if bot and bot.config:
                    fresh_config = bot.config.to_dict()
                    main_buttons = fresh_config.get('main_buttons', [])

                    if original_button_idx >= 0 and original_button_idx < len(main_buttons):
                        button_data = main_buttons[original_button_idx]
                        product_name = button_data.get('description') or button_data.get('text') or f'Produto {original_button_idx + 1}'
                        description = f"{product_name} (Downsell)"
                        logger.info(f"Descricao do produto original encontrada: {product_name}")
                    else:
                        description = "Oferta Especial (Downsell)"
                        logger.warning(f"Botao original {original_button_idx} nao encontrado em {len(main_buttons)} botoes")

            button_index = -1

            logger.info(f"DOWNSELL FIXO CLICADO | Downsell: {downsell_idx} | Botao Original: {original_button_idx} | Produto: {description} | Valor: R$ {price:.2f}")

            from flask import current_app
            from internal_logic.core.extensions import db
            from internal_logic.core.models import Bot as BotModel

            order_bump = None
            with current_app.app_context():
                bot = db.session.get(BotModel, bot_id)
                if bot and bot.config:
                    config = bot.config.to_dict()
                    downsells = config.get('downsells', [])

                    if downsell_idx < len(downsells):
                        downsell_config = downsells[downsell_idx]
                        order_bump = downsell_config.get('order_bump', {})

            if order_bump and order_bump.get('enabled'):
                requests.post(url, json={
                    'callback_query_id': callback_id,
                    'text': 'Oferta especial para voce!'
                }, timeout=3)

                logger.info(f"Order Bump detectado para downsell {downsell_idx + 1}!")
                bot_manager._show_downsell_order_bump(bot_id, token, chat_id, user_info,
                                                     price, description, downsell_idx, order_bump)
                return

            requests.post(url, json={
                'callback_query_id': callback_id,
                'text': 'Gerando pagamento PIX...'
            }, timeout=3)

            pix_data = bot_manager._generate_pix_payment(
                bot_id=bot_id,
                amount=price,
                description=description,
                customer_name=user_info.get('first_name', ''),
                customer_username=user_info.get('username', ''),
                customer_user_id=str(user_info.get('id', '')),
                is_downsell=True,
                downsell_index=downsell_idx
            )

            if pix_data and pix_data.get('pix_code'):
                payment_message = f"""Produto: {description}
Valor: R$ {price:.2f}

PIX Copia e Cola:
<code>{pix_data['pix_code']}</code>

Toque no codigo acima para copiar

Valido por: 30 minutos

Apos pagar, clique no botao abaixo para verificar e receber seu acesso!"""

                buttons = [{
                    'text': 'Verificar Pagamento',
                    'callback_data': f'verify_{pix_data.get("payment_id")}'
                }]

                bot_manager.send_telegram_message(
                    token=token,
                    chat_id=str(chat_id),
                    message=payment_message.strip(),
                    buttons=buttons
                )

                logger.info(f"PIX DOWNSELL ENVIADO! ID: {pix_data.get('payment_id')}")
            else:
                bot_manager.send_telegram_message(
                    token=token,
                    chat_id=str(chat_id),
                    message="Erro ao gerar PIX. Entre em contato com o suporte."
                )

        elif callback_data.startswith('upsell_'):
            parts = callback_data.replace('upsell_', '').split('_')
            logger.info(f"DEBUG upsell callback_data: {callback_data}")
            logger.info(f"DEBUG upsell parts: {parts}")

            upsell_idx = int(parts[0])

            if len(parts) == 4:
                original_button_idx = int(parts[1])
                price_cents = int(parts[2])
                logger.info(f"Formato ANTIGO detectado: idx={upsell_idx}, btn={original_button_idx}, price_cents={price_cents}")
            elif len(parts) == 3:
                price_cents = int(parts[1])
                original_button_idx = int(parts[2])
                logger.info(f"Formato NOVO detectado: idx={upsell_idx}, price_cents={price_cents}, btn={original_button_idx}")
            else:
                logger.error(f"Formato de callback_data invalido: {callback_data}")
                return

            price = float(price_cents) / 100

            logger.info(f"DEBUG upsell parsed: idx={upsell_idx}, price_cents={price_cents}, price={price:.2f}, original_button={original_button_idx}")

            if price <= 0:
                logger.error(f"Upsell com preco invalido: R$ {price:.2f} (centavos: {price_cents})")
                logger.error(f"CALLBACK_DATA PROBLEMATICO: {callback_data}")
                logger.error(f"PARTS PROBLEMATICAS: {parts}")
                return

            if price < 1.00:
                logger.warning(f"Upsell com preco muito baixo (R$ {price:.2f}), calculando valor real")

                from flask import current_app
                from internal_logic.core.extensions import db
                from internal_logic.core.models import Bot as BotModel

                with current_app.app_context():
                    bot = db.session.get(BotModel, bot_id)
                    if bot and bot.config:
                        config = bot.config.to_dict()
                        upsells = config.get('upsells', [])

                        if upsell_idx < len(upsells):
                            upsell_config = upsells[upsell_idx]
                            discount_percentage = float(upsell_config.get('discount_percentage', 50))

                            main_buttons = config.get('main_buttons', [])
                            if original_button_idx < len(main_buttons):
                                original_button = main_buttons[original_button_idx]
                                original_price = float(original_button.get('price', 0))

                                if original_price > 0:
                                    price = original_price * (1 - discount_percentage / 100)
                                    logger.info(f"Valor real calculado: R$ {original_price:.2f} com {discount_percentage}% OFF = R$ {price:.2f}")
                                else:
                                    price = 97.00
                                    logger.warning(f"Preco original nao encontrado, usando fallback R$ {price:.2f}")
                            else:
                                price = 97.00
                                logger.warning(f"Botao original nao encontrado, usando fallback R$ {price:.2f}")
                        else:
                            price = 97.00
                            logger.warning(f"Configuracao de upsell nao encontrada, usando fallback R$ {price:.2f}")
                    else:
                        price = 97.00
                        logger.warning(f"Configuracao do bot nao encontrada, usando fallback R$ {price:.2f}")

            from flask import current_app
            from internal_logic.core.extensions import db
            from internal_logic.core.models import Bot as BotModel

            description = "Oferta Especial"

            with current_app.app_context():
                bot = db.session.get(BotModel, bot_id)
                if bot and bot.config:
                    fresh_config = bot.config.to_dict()
                    main_buttons = fresh_config.get('main_buttons', [])

                    if original_button_idx >= 0 and original_button_idx < len(main_buttons):
                        button_data = main_buttons[original_button_idx]
                        product_name = button_data.get('description') or button_data.get('text') or f'Produto {original_button_idx + 1}'
                        description = f"{product_name} (Upsell)"
                        logger.info(f"Descricao do produto original encontrada: {product_name}")
                    else:
                        description = "Oferta Especial (Upsell)"
                        logger.warning(f"Botao original {original_button_idx} nao encontrado em {len(main_buttons)} botoes")

            button_index = -1

            logger.info(f"UPSELL CLICADO | Upsell: {upsell_idx} | Botao Original: {original_button_idx} | Produto: {description} | Valor: R$ {price:.2f}")

            from flask import current_app
            from internal_logic.core.extensions import db
            from internal_logic.core.models import Bot as BotModel

            order_bump = None
            with current_app.app_context():
                bot = db.session.get(BotModel, bot_id)
                if bot and bot.config:
                    config = bot.config.to_dict()
                    upsells = config.get('upsells', [])

                    if upsell_idx < len(upsells):
                        upsell_config = upsells[upsell_idx]
                        order_bump = upsell_config.get('order_bump', {})

            if order_bump and order_bump.get('enabled'):
                requests.post(url, json={
                    'callback_query_id': callback_id,
                    'text': 'Oferta especial para voce!'
                }, timeout=3)

                logger.info(f"Order Bump detectado para upsell {upsell_idx + 1}!")
                logger.warning(f"Order bump para upsell ainda nao implementado, processando direto")

            requests.post(url, json={
                'callback_query_id': callback_id,
                'text': 'Gerando pagamento PIX...'
            }, timeout=3)

            pix_data = bot_manager._generate_pix_payment(
                bot_id=bot_id,
                amount=price,
                description=description,
                customer_name=user_info.get('first_name', ''),
                customer_username=user_info.get('username', ''),
                customer_user_id=str(user_info.get('id', '')),
                is_upsell=True,
                upsell_index=upsell_idx
            )
            if pix_data and pix_data.get('rate_limit'):
                wait_time_msg = pix_data.get('wait_time', 'alguns segundos')
                bot_manager.send_telegram_message(
                    chat_id=chat_id,
                    message=f"Aguarde {wait_time_msg}...\n\nVoce ja gerou um PIX agora mesmo. Verifique se recebeu o QR Code acima antes de tentar novamente.",
                    token=token
                )
                return

            if pix_data and pix_data.get('pix_code'):
                payment_message = f"""Produto: {description}
Valor: R$ {price:.2f}

PIX Copia e Cola:
<code>{pix_data['pix_code']}</code>

Toque no codigo acima para copiar

Valido por: 30 minutos

Apos pagar, clique no botao abaixo para verificar e receber seu acesso!"""

                buttons = [{
                    'text': 'Verificar Pagamento',
                    'callback_data': f'verify_{pix_data.get("payment_id")}'
                }]

                bot_manager.send_telegram_message(
                    token=token,
                    chat_id=str(chat_id),
                    message=payment_message.strip(),
                    buttons=buttons
                )

                logger.info(f"PIX UPSELL ENVIADO! ID: {pix_data.get('payment_id')}")
            else:
                bot_manager.send_telegram_message(
                    token=token,
                    chat_id=str(chat_id),
                    message="Erro ao gerar PIX. Entre em contato com o suporte."
                )

        elif callback_data.startswith('buy_'):
            button_index = int(callback_data.replace('buy_', ''))

            main_buttons = config.get('main_buttons', [])
            if button_index < len(main_buttons):
                button_data = main_buttons[button_index]
                price = float(button_data.get('price', 0))
                description = button_data.get('description', 'Produto')
            else:
                price = 0
                description = 'Produto'

            logger.info(f"Produto: {description} | Valor: R$ {price:.2f} | Botao: {button_index}")

            order_bumps = button_data.get('order_bumps', []) if button_index < len(main_buttons) else []
            enabled_order_bumps = [bump for bump in order_bumps if bump.get('enabled')]

            if enabled_order_bumps:
                import json as json_lib
                user_key = f"orderbump_{chat_id}"
                session_key = f"gb:ob_session:{user_key}"

                redis_conn = get_redis_connection()
                existing_session_json = redis_conn.get(session_key)

                if existing_session_json:
                    existing_session = json_lib.loads(existing_session_json)
                    existing_button_index = existing_session.get('button_index')
                    existing_description = existing_session.get('original_description', 'Produto')

                    logger.info(f"Nova intencao de compra detectada! Cancelando sessao anterior (botao {existing_button_index}) e iniciando nova (botao {button_index})")

                    redis_conn.delete(session_key)
                    pix_cache_key = f"gb:pix_cache:{user_key}"
                    redis_conn.delete(pix_cache_key)

                    logger.info(f"Sessao anterior cancelada automaticamente. Nova oferta iniciada para botao {button_index}")

                requests.post(url, json={
                    'callback_query_id': callback_id,
                    'text': 'Oferta especial para voce!'
                }, timeout=3)

                logger.info(f"{len(enabled_order_bumps)} Order Bumps detectados para este botao!")
                bot_manager._show_multiple_order_bumps(bot_id, token, chat_id, user_info,
                                                       price, description, button_index, enabled_order_bumps)
                return

            requests.post(url, json={
                'callback_query_id': callback_id,
                'text': 'Gerando pagamento PIX...'
            }, timeout=3)

            logger.info(f"Sem order bump - gerando PIX direto...")
            pix_data = bot_manager._generate_pix_payment(
                bot_id=bot_id,
                amount=price,
                description=description,
                customer_name=user_info.get('first_name', ''),
                customer_username=user_info.get('username', ''),
                customer_user_id=str(user_info.get('id', '')),
                button_index=button_index,
                button_config=button_data
            )
            if pix_data and pix_data.get('rate_limit'):
                wait_time_msg = pix_data.get('wait_time', 'alguns segundos')
                bot_manager.send_telegram_message(
                    chat_id=chat_id,
                    message=f"Aguarde {wait_time_msg}...\n\nVoce ja gerou um PIX agora mesmo. Verifique se recebeu o QR Code acima antes de tentar novamente.",
                    token=token
                )
                return

            if pix_data and pix_data.get('pix_code'):
                payment_message = f"""
Produto: {description}
Valor: R$ {price:.2f}

PIX Copia e Cola:
<code>{pix_data['pix_code']}</code>

Toque para copiar o codigo PIX

Valido por: 30 minutos

Apos pagar, clique no botao abaixo para verificar e receber seu acesso!
                """

                buttons = [{
                    'text': 'Verificar Pagamento',
                    'callback_data': f'verify_{pix_data.get("payment_id")}'
                }]

                bot_manager.send_telegram_message(
                    token=token,
                    chat_id=str(chat_id),
                    message=payment_message.strip(),
                    buttons=buttons
                )

                logger.info(f"PIX ENVIADO! ID: {pix_data.get('payment_id')}")

                from flask import current_app
                from internal_logic.core.extensions import db
                from internal_logic.core.models import Bot as BotModel

                with current_app.app_context():
                    bot = db.session.get(BotModel, bot_id)
                    if bot and bot.config:
                        config = bot.config.to_dict()
                    else:
                        config = {}

                logger.info(f"DEBUG Downsells - bot_id: {bot_id}")
                logger.info(f"DEBUG Downsells - enabled: {config.get('downsells_enabled', False)}")
                logger.info(f"DEBUG Downsells - list type: {type(config.get('downsells', []))}")
                logger.info(f"DEBUG Downsells - list content: {config.get('downsells', [])}")

                if config.get('downsells_enabled', False):
                    downsells = config.get('downsells', [])
                    logger.info(f"DEBUG Downsells - downsells encontrados: {len(downsells)}")
                    logger.info(f"DEBUG Downsells - is empty?: {len(downsells) == 0}")
                    if downsells and len(downsells) > 0:
                        bot_manager.schedule_downsells(
                            bot_id=bot_id,
                            payment_id=pix_data.get('payment_id'),
                            chat_id=chat_id,
                            downsells=downsells,
                            original_price=price,
                            original_button_index=button_index
                        )
                    else:
                        logger.warning(f"Downsells habilitados mas lista vazia!")
                else:
                    logger.info(f"Downsells desabilitados ou nao configurados")

                logger.info(f"{'='*60}\n")
            elif pix_data is not None and pix_data.get('rate_limit'):
                logger.warning(f"Rate limit: cliente precisa aguardar {pix_data.get('wait_time')}")

                rate_limit_message = f"""
AGUARDE PARA GERAR NOVO PIX

Voce ja tem um PIX pendente para outro produto.

Por favor, aguarde {pix_data.get('wait_time', 'alguns segundos')} para gerar um novo PIX para um produto diferente.

Ou: Pague o PIX atual e depois gere um novo PIX.

Voce pode verificar seu PIX atual em 'Verificar Pagamento'
                """
                bot_manager.send_telegram_message(
                    token=token,
                    chat_id=str(chat_id),
                    message=rate_limit_message.strip()
                )
            elif pix_data is None:
                logger.error(f"pix_data e None - erro no gateway")
                error_message = """
ERRO AO GERAR PAGAMENTO

Desculpe, nao foi possivel processar seu pagamento.

Entre em contato com o suporte.
                """
                bot_manager.send_telegram_message(
                    token=token,
                    chat_id=str(chat_id),
                    message=error_message.strip()
                )
            else:
                logger.error(f"FALHA CRITICA: Nao foi possivel gerar PIX!")
                logger.error(f"Verifique suas credenciais no painel!")

                error_message = """
ERRO AO GERAR PAGAMENTO

Desculpe, nao foi possivel processar seu pagamento.

Entre em contato com o suporte.
                """
                bot_manager.send_telegram_message(
                    token=token,
                    chat_id=str(chat_id),
                    message=error_message.strip()
                )

    except Exception as e:
        logger.error(f"Erro ao processar callback: {e}")
        import traceback
        traceback.print_exc()
