"""
Callback Handler Service
=========================
Processa cliques em botoes do Telegram (callbacks).
Extraido do BotManager (Fase 10).
"""

import logging
import json
import requests
from typing import Dict, Any, List

from internal_logic.core.redis_manager import get_redis_connection

logger = logging.getLogger(__name__)


def handle_callback_query(bot_manager, bot_id: int, token: str, config: Dict[str, Any],
                          callback: Dict[str, Any]):
    try:
        callback_data = callback.get('data', '')
        chat_id = callback['message']['chat']['id']
        user_info = callback.get('from', {})
        
        logger.info(f"\n{'='*60}")
        logger.info(f"🔘 CLIQUE NO BOTÃO: {callback_data}")
        logger.info(f"👤 Cliente: {user_info.get('first_name')}")
        logger.info(f"{'='*60}")
        
        callback_id = callback['id']
        url = f"https://api.telegram.org/bot{token}/answerCallbackQuery"
        
        # ✅ V∞: Callback de Botão Customizado do Flow (formato: flow_{stepId}_{index})
        if callback_data.startswith('flow_') and not callback_data.startswith('flow_step_'):
            try:
                # Parse: flow_{stepId}_{index}
                parts = callback_data.split('_', 2)  # ['flow', '{stepId}', '{index}']
                if len(parts) == 3:
                    step_id = parts[1]
                    btn_index = int(parts[2])
                    
                    # Responder callback
                    requests.post(url, json={
                        'callback_query_id': callback_id,
                        'text': '⏳ Processando...'
                    }, timeout=3)
                    
                    telegram_user_id = str(user_info.get('id', ''))
                    
                    # Buscar config e steps
                    import json
                    flow_steps_raw = config.get('flow_steps', [])
                    if isinstance(flow_steps_raw, str):
                        flow_steps = json.loads(flow_steps_raw)
                    else:
                        flow_steps = flow_steps_raw if isinstance(flow_steps_raw, list) else []
                    
                    # Encontrar step
                    step = bot_manager._find_step_by_id(flow_steps, step_id)
                    if not step:
                        logger.warning(f"⚠️ Step {step_id} não encontrado no fluxo")
                        return
                    
                    custom_buttons = step.get('config', {}).get('custom_buttons', [])
                    if btn_index >= len(custom_buttons):
                        logger.warning(f"⚠️ Índice de botão inválido: {btn_index} (total: {len(custom_buttons)})")
                        return
                    
                    target_step = custom_buttons[btn_index].get('target_step')
                    if not target_step:
                        logger.warning(f"⚠️ Botão {btn_index} não tem target_step definido")
                        return
                    
                    logger.info(f"✅ [FLOW V∞] Callback customizado: step={step_id}, button={btn_index}, target={target_step}")
                    
                    # Limpar step atual do Redis
                    try:
                        redis_conn = get_redis_connection()
                        if redis_conn:
                            current_step_key = f"gb:{bot_manager.user_id}:flow_current_step:{bot_id}:{telegram_user_id}"
                            redis_conn.delete(current_step_key)
                    except Exception as e:
                        logger.warning(f"⚠️ Erro ao limpar step atual do Redis: {e}")
                    
                    # Buscar snapshot do Redis
                    flow_snapshot = bot_manager._get_flow_snapshot_from_redis(bot_id, telegram_user_id)
                    
                    # Executar step destino
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
                logger.error(f"❌ [FLOW V∞] Erro ao parsear callback flow_: {e}")
            except Exception as e:
                logger.error(f"❌ [FLOW V∞] Erro callback flow_: {e}", exc_info=True)
            return
        
        # ✅ NOVO: Botão contextual do fluxo (formato: flow_step_{step_id}_{action}) - COMPATIBILIDADE
        if callback_data.startswith('flow_step_'):
            # Responder callback
            requests.post(url, json={
                'callback_query_id': callback_id,
                'text': '⏳ Processando...'
            }, timeout=3)
            
            # Extrair step_id e action do callback_data
            # Formato: flow_step_{step_id}_btn_{idx}
            # ✅ CORREÇÃO: step_id pode conter underscores, então usar rsplit para pegar action corretamente
            callback_without_prefix = callback_data.replace('flow_step_', '')
            
            # Buscar pelo padrão _btn_ para dividir corretamente (action sempre é btn_{idx})
            if '_btn_' in callback_without_prefix:
                # Dividir no último _btn_ para pegar step_id completo
                parts = callback_without_prefix.rsplit('_btn_', 1)
                source_step_id = parts[0]
                action = 'btn_' + parts[1] if len(parts) > 1 else ''
            else:
                # Fallback: usar split tradicional (compatibilidade com formato antigo)
                parts = callback_without_prefix.split('_', 1)
                source_step_id = parts[0]
                action = parts[1] if len(parts) > 1 else ''
            
            logger.info(f"🔘 Botão contextual clicado: step={source_step_id}, action={action}")
            
            # Buscar step no fluxo
            flow_steps = config.get('flow_steps', [])
            source_step = bot_manager._find_step_by_id(flow_steps, source_step_id)
            
            if source_step:
                telegram_user_id = str(user_info.get('id', ''))
                
                # ✅ QI 500: Avaliar condições de button_click ANTES de usar target_step do botão
                conditions = source_step.get('conditions', [])
                if conditions and len(conditions) > 0:
                    try:
                        redis_conn = get_redis_connection()
                        current_step_key = f"gb:{bot_manager.user_id}:flow_current_step:{bot_id}:{telegram_user_id}"
                        
                        # Avaliar condições com parâmetros completos
                        next_step_id = bot_manager._evaluate_conditions(
                            source_step,
                            user_input=callback_data,
                            context={},
                            bot_id=bot_id,
                            telegram_user_id=telegram_user_id,
                            step_id=source_step_id
                        )
                        
                        if next_step_id:
                            logger.info(f"✅ Condição de button_click matchou! Continuando para step: {next_step_id}")
                            # Limpar step atual do Redis
                            redis_conn.delete(current_step_key)
                            # Continuar fluxo no step da condição (sobrescreve target_step do botão)
                            bot_manager._execute_flow_recursive(bot_id, token, config, chat_id, telegram_user_id, next_step_id)
                            return
                        else:
                            logger.info(f"⚠️ Nenhuma condição de button_click matchou para callback: {callback_data}")
                            # Fallback: usar target_step do botão (comportamento antigo)
                    except Exception as e:
                        logger.warning(f"⚠️ Erro ao avaliar condições de button_click: {e} - usando target_step do botão")
                
                # ✅ Fallback: Buscar botão correspondente no step (comportamento antigo)
                step_config = source_step.get('config', {})
                custom_buttons = step_config.get('custom_buttons', [])
                
                # Extrair índice do botão do action (formato: btn_{idx})
                btn_idx = None
                if action.startswith('btn_'):
                    try:
                        btn_idx = int(action.replace('btn_', ''))
                    except:
                        pass
                
                if btn_idx is not None and btn_idx < len(custom_buttons):
                    target_step_id = custom_buttons[btn_idx].get('target_step')
                    if target_step_id:
                        logger.info(f"✅ Continuando fluxo para step: {target_step_id} (target_step do botão)")
                        # ✅ NOVO: Limpar step atual atomicamente
                        try:
                            redis_conn = get_redis_connection()
                            if redis_conn:
                                current_step_key = f"gb:{bot_manager.user_id}:flow_current_step:{bot_id}:{telegram_user_id}"
                                redis_conn.delete(current_step_key)
                        except:
                            pass
                        # ✅ NOVO: Buscar snapshot do Redis
                        flow_snapshot = bot_manager._get_flow_snapshot_from_redis(bot_id, telegram_user_id)
                        
                        # Continuar fluxo no step de destino
                        bot_manager._execute_flow_recursive(
                            bot_id, token, config, chat_id, telegram_user_id, target_step_id,
                            recursion_depth=0, visited_steps=set(), flow_snapshot=flow_snapshot
                        )
                        return
                    else:
                        logger.warning(f"⚠️ Botão contextual sem target_step definido")
                else:
                    logger.warning(f"⚠️ Índice de botão inválido: {btn_idx}")
            else:
                logger.warning(f"⚠️ Step não encontrado: {source_step_id}")
            
            return
        
        # Botão de VERIFICAR PAGAMENTO
        if callback_data.startswith('verify_'):
            # Responder callback
            requests.post(url, json={
                'callback_query_id': callback_id,
                'text': '🔍 Verificando pagamento...'
            }, timeout=3)
            payment_id = callback_data.replace('verify_', '')
            logger.info(f"🔍 Verificando pagamento: {payment_id}")
            
            bot_manager._handle_verify_payment(bot_id, token, chat_id, payment_id, user_info)
        
        # ✅ NOVO: Botão de REMARKETING (formato simplificado)
        elif callback_data.startswith('rmkt_'):
            # Formato: rmkt_CAMPAIGN_ID_BUTTON_INDEX
            parts = callback_data.replace('rmkt_', '').split('_')
            campaign_id = int(parts[0])
            btn_idx = int(parts[1])
            
            # Responder callback
            requests.post(url, json={
                'callback_query_id': callback_id,
                'text': '🔄 Gerando PIX da oferta...'
            }, timeout=3)
            
            # Buscar dados da campanha e botão
            from flask import current_app
            from internal_logic.core.extensions import db
            from internal_logic.core.models import RemarketingCampaign
            
            with current_app.app_context():
                campaign = db.session.get(RemarketingCampaign, campaign_id)
                if campaign and campaign.buttons:
                    # ✅ CORREÇÃO: Parsear JSON se for string
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
                else:
                    price = 0
                    description = 'Produto Remarketing'
            
            logger.info(f"📢 COMPRA VIA REMARKETING | Campanha: {campaign_id} | Produto: {description} | Valor: R$ {price:.2f}")
            
            # Gerar PIX direto (sem order bump em remarketing)
            pix_data = bot_manager._generate_pix_payment(
                bot_id=bot_id,
                amount=price,
                description=description,
                customer_name=user_info.get('first_name', ''),
                customer_username=user_info.get('username', ''),
                customer_user_id=str(user_info.get('id', '')),
                is_remarketing=True,  # ✅ CORREÇÃO CRÍTICA: Marcar como remarketing
                remarketing_campaign_id=campaign_id  # ✅ Salvar ID da campanha
            )
            # ✅ UX FIX: Tratamento Amigável de Rate Limit
            if pix_data and pix_data.get('rate_limit'):
                wait_time_msg = pix_data.get('wait_time', 'alguns segundos')
                bot_manager.send_telegram_message(
                    chat_id=chat_id,
                    message=f"⏳ <b>Aguarde {wait_time_msg}...</b>\n\nVocê já gerou um PIX agora mesmo. Verifique se recebeu o QR Code acima antes de tentar novamente.",
                    token=token
                )
                return
            
            if pix_data and pix_data.get('pix_code'):
                # ✅ PIX em linha única dentro de <code> para copiar com um toque
                payment_message = f"""🎯 <b>Produto:</b> {description}
💰 <b>Valor:</b> R$ {price:.2f}

📱 <b>PIX Copia e Cola:</b>
<code>{pix_data.get('pix_code')}</code>

<i>👆 Toque no código acima para copiar</i>

⏰ <b>Válido por:</b> 30 minutos

💡 <b>Após pagar, clique no botão abaixo para verificar e receber seu acesso!</b>"""
                
                verify_button = [{
                    'text': '✅ Verificar Pagamento',
                    'callback_data': f"verify_{pix_data.get('payment_id')}"
                }]
                
                bot_manager.send_telegram_message(
                    token=token,
                    chat_id=str(chat_id),
                    message=payment_message,
                    buttons=verify_button
                )
                
                logger.info(f"✅ PIX ENVIADO (Remarketing)! ID: {pix_data.get('payment_id')}")
                
                # Atualizar stats da campanha
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
                    message="❌ Erro ao gerar PIX. Entre em contato com o suporte."
                )
        
        # Resposta do ORDER BUMP - SIM
        elif callback_data.startswith('bump_yes_'):
            # Responder callback
            requests.post(url, json={
                'callback_query_id': callback_id,
                'text': '✅ Order bump adicionado! Gerando PIX...'
            }, timeout=3)
            
            # ✅ NOVO FORMATO: bump_yes_INDEX
            button_index = int(callback_data.replace('bump_yes_', ''))
            
            # Buscar dados do botão e order bump pela configuração
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
            final_description = f"{description} + Bônus"
            
            logger.info(f"✅ Cliente ACEITOU order bump! Total: R$ {total_price:.2f}")
            
            # Gerar PIX com valor TOTAL (produto + order bump) + ANALYTICS
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
                # ✅ PIX em linha única dentro de <code> para copiar com um toque
                payment_message = f"""🎯 <b>Produto:</b> {final_description}
💰 <b>Valor:</b> R$ {total_price:.2f}

📱 <b>PIX Copia e Cola:</b>
<code>{pix_data['pix_code']}</code>

<i>👆 Toque no código acima para copiar</i>

⏰ <b>Válido por:</b> 30 minutos

💡 <b>Após pagar, clique no botão abaixo para verificar e receber seu acesso!</b>"""
                
                buttons = [{
                    'text': '✅ Verificar Pagamento',
                    'callback_data': f'verify_{pix_data.get("payment_id")}'
                }]
                
                bot_manager.send_telegram_message(
                    token=token,
                    chat_id=str(chat_id),
                    message=payment_message.strip(),
                    buttons=buttons
                )
                
                logger.info(f"✅ PIX gerado COM order bump!")
                
                # ✅ CORREÇÃO: Buscar config atualizada do BANCO (não da memória)
                from flask import current_app
                from internal_logic.core.extensions import db
                from internal_logic.core.models import Bot as BotModel
                
                with current_app.app_context():
                    bot = db.session.get(BotModel, bot_id)
                    if bot and bot.config:
                        config = bot.config.to_dict()
                    else:
                        config = {}
                
                logger.info(f"🔍 DEBUG Downsells (Order Bump) - bot_id: {bot_id}")
                logger.info(f"🔍 DEBUG Downsells (Order Bump) - enabled: {config.get('downsells_enabled', False)}")
                logger.info(f"🔍 DEBUG Downsells (Order Bump) - list: {config.get('downsells', [])}")
                
                if config.get('downsells_enabled', False):
                    downsells = config.get('downsells', [])
                    logger.info(f"🔍 DEBUG Downsells (Order Bump) - downsells encontrados: {len(downsells)}")
                    if downsells and len(downsells) > 0:
                        bot_manager.schedule_downsells(
                            bot_id=bot_id,
                            payment_id=pix_data.get('payment_id'),
                            chat_id=chat_id,
                            downsells=downsells,
                            original_price=total_price,  # ✅ Preço com order bump
                            original_button_index=button_index
                        )
                    else:
                        logger.warning(f"⚠️ Downsells habilitados mas lista vazia! (Order Bump)")
                else:
                    logger.info(f"ℹ️ Downsells desabilitados ou não configurados (Order Bump)")
        
        # Resposta do ORDER BUMP - NÃO
        elif callback_data.startswith('bump_no_'):
            # Responder callback
            requests.post(url, json={
                'callback_query_id': callback_id,
                'text': '🔄 Gerando PIX do valor original...'
            }, timeout=3)
            
            # ✅ NOVO FORMATO: bump_no_INDEX
            button_index = int(callback_data.replace('bump_no_', ''))
            
            # Buscar dados do botão pela configuração
            main_buttons = config.get('main_buttons', [])
            if button_index < len(main_buttons):
                button_data = main_buttons[button_index]
                price = float(button_data.get('price', 0))
                description = button_data.get('description', 'Produto')
            else:
                price = 0
                description = 'Produto'
            
            logger.info(f"❌ Cliente RECUSOU order bump. Gerando PIX do valor original...")
            
            # Gerar PIX com valor ORIGINAL (sem order bump) + ANALYTICS
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
                # ✅ PIX em linha única dentro de <code> para copiar com um toque
                payment_message = f"""🎯 <b>Produto:</b> {description}
💰 <b>Valor:</b> R$ {price:.2f}

📱 <b>PIX Copia e Cola:</b>
<code>{pix_data['pix_code']}</code>

<i>👆 Toque no código acima para copiar</i>

⏰ <b>Válido por:</b> 30 minutos

💡 <b>Após pagar, clique no botão abaixo para verificar e receber seu acesso!</b>"""
                
                buttons = [{
                    'text': '✅ Verificar Pagamento',
                    'callback_data': f'verify_{pix_data.get("payment_id")}'
                }]
                
                bot_manager.send_telegram_message(
                    token=token,
                    chat_id=str(chat_id),
                    message=payment_message.strip(),
                    buttons=buttons
                )
                
                logger.info(f"✅ PIX gerado SEM order bump!")
                
                # ✅ CORREÇÃO: Buscar config atualizada do BANCO (não da memória)
                from flask import current_app
                from internal_logic.core.extensions import db
                from internal_logic.core.models import Bot as BotModel
                
                with current_app.app_context():
                    bot = db.session.get(BotModel, bot_id)
                    if bot and bot.config:
                        config = bot.config.to_dict()
                    else:
                        config = {}
                
                logger.info(f"🔍 DEBUG Downsells (bump_no) - bot_id: {bot_id}")
                logger.info(f"🔍 DEBUG Downsells (bump_no) - enabled: {config.get('downsells_enabled', False)}")
                logger.info(f"🔍 DEBUG Downsells (bump_no) - list: {config.get('downsells', [])}")
                
                if config.get('downsells_enabled', False):
                    downsells = config.get('downsells', [])
                    logger.info(f"🔍 DEBUG Downsells (bump_no) - downsells encontrados: {len(downsells)}")
                    if downsells and len(downsells) > 0:
                        bot_manager.schedule_downsells(
                            bot_id=bot_id,
                            payment_id=pix_data.get('payment_id'),
                            chat_id=chat_id,
                            downsells=downsells,
                            original_price=price,  # ✅ Preço original (sem order bump)
                            original_button_index=button_index
                        )
                    else:
                        logger.warning(f"⚠️ Downsells habilitados mas lista vazia! (bump_no)")
                else:
                    logger.info(f"ℹ️ Downsells desabilitados ou não configurados (bump_no)")
        
        # ✅ NOVO: Múltiplos Order Bumps - Aceitar
        elif callback_data.startswith('multi_bump_yes_'):
            # ✅ REDIS MIGRATION: Formato: multi_bump_yes_CHAT_ID_BUMP_INDEX_TOTAL_PRICE_CENTAVOS
            import json as json_lib  # ✅ Proteção contra shadowing do módulo json
            parts = callback_data.replace('multi_bump_yes_', '').split('_')
            chat_id_from_callback = int(parts[0])
            user_key = f"orderbump_{chat_id_from_callback}"
            bump_index = int(parts[1])
            total_price = float(parts[2]) / 100  # Converter centavos para reais
            
            logger.info(f"🎁 Order Bump {bump_index + 1} ACEITO | User: {user_key} | Valor Total: R$ {total_price:.2f}")
            
            # Responder callback
            requests.post(url, json={
                'callback_query_id': callback_id,
                'text': '✅ Bônus adicionado!'
            }, timeout=3)
            
            # ✅ REDIS MIGRATION: Buscar sessão do Redis
            redis_conn = get_redis_connection()
            session_key = f"gb:ob_session:{user_key}"
            pix_cache_key = f"gb:pix_cache:{user_key}"
            
            session_json = redis_conn.get(session_key)
            if session_json:
                session = json_lib.loads(session_json)
                
                # ✅ VALIDAÇÃO: Verificar se chat_id do callback corresponde ao chat_id da sessão
                session_chat_id = session.get('chat_id')
                if session_chat_id and session_chat_id != chat_id_from_callback:
                    logger.error(f"❌ Chat ID mismatch: callback de chat {chat_id_from_callback}, mas sessão é do chat {session_chat_id}!")
                    return
                
                session_bot_id = session.get('bot_id', bot_id)
                
                # ✅ VALIDAÇÃO: Verificar se bot_id do callback corresponde ao bot_id da sessão
                if session_bot_id != bot_id:
                    logger.warning(f"⚠️ Bot ID mismatch: callback de bot {bot_id}, mas sessão é do bot {session_bot_id}. Usando bot_id da sessão.")
                    session_bot_data = bot_manager.bot_state.get_bot_data(session_bot_id)
                    if session_bot_data:
                        token = session_bot_data['token']
                        bot_id = session_bot_id
                    else:
                        logger.error(f"❌ Bot {session_bot_id} da sessão não está mais ativo no Redis!")
                        return
                
                # ✅ CORREÇÃO: Usar chat_id da sessão (mais confiável)
                chat_id = session.get('chat_id', chat_id)
                
                current_bump = session['order_bumps'][bump_index]
                bump_price = float(current_bump.get('price', 0))
                
                # Adicionar bump aceito
                session['accepted_bumps'].append(current_bump)
                session['total_bump_value'] += bump_price
                session['current_index'] = bump_index + 1
                
                logger.info(f"🎁 Bump aceito: {current_bump.get('description', 'Bônus')} (+R$ {bump_price:.2f})")
                
                # ✅ REDIS MIGRATION: Salvar sessão atualizada no Redis (TTL 10 min renovado)
                redis_conn.setex(session_key, 600, json_lib.dumps(session))
                
                # Exibir próximo order bump ou finalizar (usar bot_id correto)
                bot_manager._show_next_order_bump(bot_id, token, chat_id, user_key)
            else:
                # ✅ REDIS MIGRATION: Verificar cache de PIX no Redis antes de mostrar erro
                pix_cache_json = redis_conn.get(pix_cache_key)
                if pix_cache_json:
                    cached = json_lib.loads(pix_cache_json)
                    logger.info(f"🔄 Callback 'SIM' - Reenviando PIX do cache Redis: {cached['pix_data'].get('payment_id')}")
                    bot_manager._send_pix_message(token, chat_id, cached['pix_data'], "🔄 Reenviando seu PIX:")
                    return  # ✅ Sucesso - não é erro
                
                # ✅ PROTEÇÃO: Sessão já foi finalizada (usuário clicou em botão antigo)
                logger.warning(f"⚠️ Sessão de order bump não encontrada no Redis (já finalizada): {user_key} | Callback já processado")
        
        # ✅ NOVO: Múltiplos Order Bumps - Recusar
        elif callback_data.startswith('multi_bump_no_'):
            # ✅ REDIS MIGRATION: Formato: multi_bump_no_CHAT_ID_BUMP_INDEX_CURRENT_PRICE_CENTAVOS
            import json as json_lib  # ✅ Proteção contra shadowing do módulo json
            parts = callback_data.replace('multi_bump_no_', '').split('_')
            chat_id_from_callback = int(parts[0])
            user_key = f"orderbump_{chat_id_from_callback}"
            bump_index = int(parts[1])
            current_price = float(parts[2]) / 100  # Converter centavos para reais
            
            logger.info(f"🎁 Order Bump {bump_index + 1} RECUSADO | User: {user_key} | Valor Atual: R$ {current_price:.2f}")
            
            # Responder callback
            requests.post(url, json={
                'callback_query_id': callback_id,
                'text': '❌ Bônus recusado'
            }, timeout=3)
            
            # ✅ REDIS MIGRATION: Buscar sessão do Redis
            redis_conn = get_redis_connection()
            session_key = f"gb:ob_session:{user_key}"
            pix_cache_key = f"gb:pix_cache:{user_key}"
            
            session_json = redis_conn.get(session_key)
            if session_json:
                session = json_lib.loads(session_json)
                
                # ✅ VALIDAÇÃO: Verificar se chat_id do callback corresponde ao chat_id da sessão
                session_chat_id = session.get('chat_id')
                if session_chat_id and session_chat_id != chat_id_from_callback:
                    logger.error(f"❌ Chat ID mismatch: callback de chat {chat_id_from_callback}, mas sessão é do chat {session_chat_id}!")
                    return
                
                session_bot_id = session.get('bot_id', bot_id)
                
                # ✅ VALIDAÇÃO: Verificar se bot_id do callback corresponde ao bot_id da sessão
                if session_bot_id != bot_id:
                    logger.warning(f"⚠️ Bot ID mismatch: callback de bot {bot_id}, mas sessão é do bot {session_bot_id}. Usando bot_id da sessão.")
                    session_bot_data = bot_manager.bot_state.get_bot_data(session_bot_id)
                    if session_bot_data:
                        token = session_bot_data['token']
                        bot_id = session_bot_id
                    else:
                        logger.error(f"❌ Bot {session_bot_id} da sessão não está mais ativo no Redis!")
                        return
                
                # ✅ CORREÇÃO: Usar chat_id da sessão (mais confiável)
                chat_id = session.get('chat_id', chat_id)
                
                session['current_index'] = bump_index + 1
                
                logger.info(f"🎁 Bump recusado: {session['order_bumps'][bump_index].get('description', 'Bônus')}")
                
                # ✅ REDIS MIGRATION: Salvar sessão atualizada no Redis (TTL 10 min renovado)
                redis_conn.setex(session_key, 600, json_lib.dumps(session))
                
                # Exibir próximo order bump ou finalizar (usar bot_id correto)
                bot_manager._show_next_order_bump(bot_id, token, chat_id, user_key)
            else:
                # ✅ REDIS MIGRATION: Verificar cache de PIX no Redis antes de mostrar erro
                pix_cache_json = redis_conn.get(pix_cache_key)
                if pix_cache_json:
                    cached = json_lib.loads(pix_cache_json)
                    logger.info(f"🔄 Callback 'NÃO' - Reenviando PIX do cache Redis: {cached['pix_data'].get('payment_id')}")
                    bot_manager._send_pix_message(token, chat_id_from_callback, cached['pix_data'], "🔄 Reenviando seu PIX:")
                    return  # ✅ Sucesso - não é erro
                
                # ✅ PROTEÇÃO: Sessão já foi finalizada (usuário clicou em botão antigo)
                logger.warning(f"⚠️ Sessão de order bump não encontrada no Redis (já finalizada): {user_key} | Callback já processado")
        
        # ✅ NOVO: Order Bump Downsell - Aceitar
        elif callback_data.startswith('downsell_bump_yes_'):
            # Formato: downsell_bump_yes_DOWNSELL_INDEX_TOTAL_PRICE_CENTAVOS
            parts = callback_data.replace('downsell_bump_yes_', '').split('_')
            downsell_idx = int(parts[0])
            total_price = float(parts[1]) / 100  # Converter centavos para reais
            
            logger.info(f"🎁 Order Bump Downsell ACEITO | Downsell: {downsell_idx} | Valor Total: R$ {total_price:.2f}")
            
            # Responder callback
            requests.post(url, json={
                'callback_query_id': callback_id,
                'text': '🔄 Gerando pagamento PIX...'
            }, timeout=3)
            
            # Gerar PIX com valor total (downsell + order bump)
            pix_data = bot_manager._generate_pix_payment(
                bot_id=bot_id,
                amount=total_price,
                description=f"Oferta Especial + Bônus",
                customer_name=user_info.get('first_name', ''),
                customer_username=user_info.get('username', ''),
                customer_user_id=str(user_info.get('id', '')),
                order_bump_shown=True,
                order_bump_accepted=True,
                order_bump_value=total_price - (total_price * 0.7),  # Estimativa do bump
                is_downsell=True,
                downsell_index=downsell_idx
            )
            
            if pix_data and pix_data.get('pix_code'):
                payment_message = f"""🎯 <b>Produto:</b> Oferta Especial + Bônus
💰 <b>Valor:</b> R$ {total_price:.2f}

📱 <b>PIX Copia e Cola:</b>
<code>{pix_data['pix_code']}</code>

<i>👆 Toque no código acima para copiar</i>

⏰ <b>Válido por:</b> 30 minutos

💡 <b>Após pagar, clique no botão abaixo para verificar e receber seu acesso!</b>"""
                
                buttons = [{
                    'text': '✅ Verificar Pagamento',
                    'callback_data': f'verify_{pix_data.get("payment_id")}'
                }]
                
                bot_manager.send_telegram_message(
                    token=token,
                    chat_id=str(chat_id),
                    message=payment_message.strip(),
                    buttons=buttons
                )
                
                logger.info(f"✅ PIX DOWNSELL COM ORDER BUMP ENVIADO! ID: {pix_data.get('payment_id')}")
            else:
                bot_manager.send_telegram_message(
                    token=token,
                    chat_id=str(chat_id),
                    message="❌ Erro ao gerar PIX. Entre em contato com o suporte."
                )
        
        # ✅ NOVO: Order Bump Downsell - Recusar
        elif callback_data.startswith('downsell_bump_no_'):
            # Formato: downsell_bump_no_DOWNSELL_INDEX_DOWNSELL_PRICE_CENTAVOS
            parts = callback_data.replace('downsell_bump_no_', '').split('_')
            downsell_idx = int(parts[0])
            downsell_price = float(parts[1]) / 100  # Converter centavos para reais
            
            logger.info(f"🎁 Order Bump Downsell RECUSADO | Downsell: {downsell_idx} | Valor: R$ {downsell_price:.2f}")
            
            # Responder callback
            requests.post(url, json={
                'callback_query_id': callback_id,
                'text': '🔄 Gerando pagamento PIX...'
            }, timeout=3)
            
            # Gerar PIX apenas com valor do downsell (sem order bump)
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
                payment_message = f"""🎯 <b>Produto:</b> Oferta Especial
💰 <b>Valor:</b> R$ {downsell_price:.2f}

📱 <b>PIX Copia e Cola:</b>
<code>{pix_data['pix_code']}</code>

<i>👆 Toque no código acima para copiar</i>

⏰ <b>Válido por:</b> 30 minutos

💡 <b>Após pagar, clique no botão abaixo para verificar e receber seu acesso!</b>"""
                
                buttons = [{
                    'text': '✅ Verificar Pagamento',
                    'callback_data': f'verify_{pix_data.get("payment_id")}'
                }]
                
                bot_manager.send_telegram_message(
                    token=token,
                    chat_id=str(chat_id),
                    message=payment_message.strip(),
                    buttons=buttons
                )
                
                logger.info(f"✅ PIX DOWNSELL SEM ORDER BUMP ENVIADO! ID: {pix_data.get('payment_id')}")
            else:
                bot_manager.send_telegram_message(
                    token=token,
                    chat_id=str(chat_id),
                    message="❌ Erro ao gerar PIX. Entre em contato com o suporte."
                )
        
        # ✅ NOVO: Downsell com formato simplificado
        elif callback_data.startswith('dwnsl_'):
            # ✅ NOVO FORMATO PERCENTUAL: dwnsl_DOWNSELL_IDX_BUTTON_IDX_PRICE_CENTAVOS
            # Este formato é usado quando o downsell tem modo percentual e mostra múltiplos botões
            parts = callback_data.replace('dwnsl_', '').split('_')
            downsell_idx = int(parts[0])
            button_idx = int(parts[1])
            price = float(parts[2]) / 100  # Converter centavos para reais
            
            # Buscar configuração para pegar nome do produto
            # ✅ Recarregar config do banco (pode ter sido alterada)
            from flask import current_app
            from internal_logic.core.extensions import db
            from internal_logic.core.models import Bot as BotModel
            
            product_name = f'Produto {button_idx + 1}'  # Default
            description = f"Downsell {downsell_idx + 1} - {product_name}"
            
            with current_app.app_context():
                bot = db.session.get(BotModel, bot_id)
                if bot and bot.config:
                    fresh_config = bot.config.to_dict()
                    main_buttons = fresh_config.get('main_buttons', [])
                    if button_idx < len(main_buttons):
                        product_name = main_buttons[button_idx].get('text', product_name)
                        description = f"{product_name} (Downsell {downsell_idx + 1})"
            
            logger.info(f"💜 DOWNSELL PERCENTUAL CLICADO | Downsell: {downsell_idx} | Produto: {product_name} | Valor: R$ {price:.2f}")
            
            # Responder callback
            requests.post(url, json={
                'callback_query_id': callback_id,
                'text': '🔄 Gerando pagamento PIX...'
            }, timeout=3)
            
            # Gerar PIX do downsell
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
                payment_message = f"""🎯 <b>Produto:</b> {description}
💰 <b>Valor:</b> R$ {price:.2f}

📱 <b>PIX Copia e Cola:</b>
<code>{pix_data['pix_code']}</code>

<i>👆 Toque no código acima para copiar</i>

⏰ <b>Válido por:</b> 30 minutos

💡 <b>Após pagar, clique no botão abaixo para verificar e receber seu acesso!</b>"""
                
                buttons = [{
                    'text': '✅ Verificar Pagamento',
                    'callback_data': f'verify_{pix_data.get("payment_id")}'
                }]
                
                bot_manager.send_telegram_message(
                    token=token,
                    chat_id=str(chat_id),
                    message=payment_message.strip(),
                    buttons=buttons
                )
                
                logger.info(f"✅ PIX DOWNSELL PERCENTUAL ENVIADO! ID: {pix_data.get('payment_id')}")
            else:
                bot_manager.send_telegram_message(
                    token=token,
                    chat_id=str(chat_id),
                    message="❌ Erro ao gerar PIX. Entre em contato com o suporte."
                )
        
        elif callback_data.startswith('downsell_'):
            # Formato: downsell_INDEX_PRICE_CENTAVOS_BUTTON_INDEX
            parts = callback_data.replace('downsell_', '').split('_')
            logger.info(f"🔍 DEBUG downsell callback_data: {callback_data}")
            logger.info(f"🔍 DEBUG downsell parts: {parts}")
            
            downsell_idx = int(parts[0])
            
            # ✅ CORREÇÃO: Detectar formato antigo vs novo
            if len(parts) == 4:
                # Formato antigo: downsell_INDEX_BUTTON_PRICE_BUTTON
                original_button_idx = int(parts[1])
                price_cents = int(parts[2])
                logger.info(f"🔍 Formato ANTIGO detectado: idx={downsell_idx}, btn={original_button_idx}, price_cents={price_cents}")
            elif len(parts) == 3:
                # Formato novo: downsell_INDEX_PRICE_BUTTON
                price_cents = int(parts[1])
                original_button_idx = int(parts[2])
                logger.info(f"🔍 Formato NOVO detectado: idx={downsell_idx}, price_cents={price_cents}, btn={original_button_idx}")
            else:
                logger.error(f"❌ Formato de callback_data inválido: {callback_data}")
                return
            
            price = float(price_cents) / 100  # Converter centavos para reais
            
            logger.info(f"🔍 DEBUG downsell parsed: idx={downsell_idx}, price_cents={price_cents}, price={price:.2f}, original_button={original_button_idx}")
            
            # ✅ VALIDAÇÃO: Preço deve ser > 0
            if price <= 0:
                logger.error(f"❌ Downsell com preço inválido: R$ {price:.2f} (centavos: {price_cents})")
                logger.error(f"❌ CALLBACK_DATA PROBLEMÁTICO: {callback_data}")
                logger.error(f"❌ PARTS PROBLEMÁTICAS: {parts}")
                return
            
            # ✅ CORREÇÃO CRÍTICA: Se preço for muito baixo, calcular valor real do downsell
            if price < 1.00:  # Menos de R$ 1,00
                logger.warning(f"⚠️ Downsell com preço muito baixo (R$ {price:.2f}), calculando valor real")
                
                # ✅ CORREÇÃO: Buscar configuração do downsell para calcular valor real
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
                            
                            # ✅ CORREÇÃO: Usar preço original do botão clicado
                            main_buttons = config.get('main_buttons', [])
                            if original_button_idx < len(main_buttons):
                                original_button = main_buttons[original_button_idx]
                                original_price = float(original_button.get('price', 0))
                                
                                if original_price > 0:
                                    price = original_price * (1 - discount_percentage / 100)
                                    logger.info(f"✅ Valor real calculado: R$ {original_price:.2f} com {discount_percentage}% OFF = R$ {price:.2f}")
                                else:
                                    price = 9.97  # Fallback
                                    logger.warning(f"⚠️ Preço original não encontrado, usando fallback R$ {price:.2f}")
                            else:
                                price = 9.97  # Fallback
                                logger.warning(f"⚠️ Botão original não encontrado, usando fallback R$ {price:.2f}")
                        else:
                            price = 9.97  # Fallback
                            logger.warning(f"⚠️ Configuração de downsell não encontrada, usando fallback R$ {price:.2f}")
                    else:
                        price = 9.97  # Fallback
                        logger.warning(f"⚠️ Configuração do bot não encontrada, usando fallback R$ {price:.2f}")
            
            # ✅ QI 500 FIX V2: Buscar descrição do BOTÃO ORIGINAL que gerou o downsell
            from flask import current_app
            from internal_logic.core.extensions import db
            from internal_logic.core.models import Bot as BotModel
            
            # Default seguro (sem índice de downsell)
            description = "Oferta Especial"
            
            with current_app.app_context():
                bot = db.session.get(BotModel, bot_id)
                if bot and bot.config:
                    fresh_config = bot.config.to_dict()
                    main_buttons = fresh_config.get('main_buttons', [])
                    
                    # Buscar o botão ORIGINAL (não o índice do downsell)
                    if original_button_idx >= 0 and original_button_idx < len(main_buttons):
                        button_data = main_buttons[original_button_idx]
                        product_name = button_data.get('description') or button_data.get('text') or f'Produto {original_button_idx + 1}'
                        description = f"{product_name} (Downsell)"
                        logger.info(f"✅ Descrição do produto original encontrada: {product_name}")
                    else:
                        # Fallback: Se não encontrar o botão, usar genérico
                        description = "Oferta Especial (Downsell)"
                        logger.warning(f"⚠️ Botão original {original_button_idx} não encontrado em {len(main_buttons)} botões")
            
            button_index = -1  # Sinalizar que é downsell
            
            logger.info(f"💙 DOWNSELL FIXO CLICADO | Downsell: {downsell_idx} | Botão Original: {original_button_idx} | Produto: {description} | Valor: R$ {price:.2f}")
            
            # ✅ VERIFICAR SE TEM ORDER BUMP PARA ESTE DOWNSELL
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
                # Responder callback - AGUARDANDO order bump
                requests.post(url, json={
                    'callback_query_id': callback_id,
                    'text': '🎁 Oferta especial para você!'
                }, timeout=3)
                
                logger.info(f"🎁 Order Bump detectado para downsell {downsell_idx + 1}!")
                bot_manager._show_downsell_order_bump(bot_id, token, chat_id, user_info, 
                                             price, description, downsell_idx, order_bump)
                return  # Aguarda resposta do order bump
            
            # SEM ORDER BUMP - Gerar PIX direto
            # Responder callback
            requests.post(url, json={
                'callback_query_id': callback_id,
                'text': '🔄 Gerando pagamento PIX...'
            }, timeout=3)
            
            # Gerar PIX do downsell
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
                # ✅ PIX em linha única dentro de <code> para copiar com um toque
                payment_message = f"""🎯 <b>Produto:</b> {description}
💰 <b>Valor:</b> R$ {price:.2f}

📱 <b>PIX Copia e Cola:</b>
<code>{pix_data['pix_code']}</code>

<i>👆 Toque no código acima para copiar</i>

⏰ <b>Válido por:</b> 30 minutos

💡 <b>Após pagar, clique no botão abaixo para verificar e receber seu acesso!</b>"""
                
                buttons = [{
                    'text': '✅ Verificar Pagamento',
                    'callback_data': f'verify_{pix_data.get("payment_id")}'
                }]
                
                bot_manager.send_telegram_message(
                    token=token,
                    chat_id=str(chat_id),
                    message=payment_message.strip(),
                    buttons=buttons
                )
                
                logger.info(f"✅ PIX DOWNSELL ENVIADO! ID: {pix_data.get('payment_id')}")
            else:
                bot_manager.send_telegram_message(
                    token=token,
                    chat_id=str(chat_id),
                    message="❌ Erro ao gerar PIX. Entre em contato com o suporte."
                )
        
        elif callback_data.startswith('upsell_'):
            # ✅ UPSELL: Formato idêntico ao downsell: upsell_INDEX_PRICE_CENTAVOS_BUTTON_INDEX
            parts = callback_data.replace('upsell_', '').split('_')
            logger.info(f"🔍 DEBUG upsell callback_data: {callback_data}")
            logger.info(f"🔍 DEBUG upsell parts: {parts}")
            
            upsell_idx = int(parts[0])
            
            # ✅ CORREÇÃO: Detectar formato antigo vs novo (similar ao downsell)
            if len(parts) == 4:
                # Formato antigo: upsell_INDEX_BUTTON_PRICE_BUTTON
                original_button_idx = int(parts[1])
                price_cents = int(parts[2])
                logger.info(f"🔍 Formato ANTIGO detectado: idx={upsell_idx}, btn={original_button_idx}, price_cents={price_cents}")
            elif len(parts) == 3:
                # Formato novo: upsell_INDEX_PRICE_BUTTON
                price_cents = int(parts[1])
                original_button_idx = int(parts[2])
                logger.info(f"🔍 Formato NOVO detectado: idx={upsell_idx}, price_cents={price_cents}, btn={original_button_idx}")
            else:
                logger.error(f"❌ Formato de callback_data inválido: {callback_data}")
                return
            
            price = float(price_cents) / 100  # Converter centavos para reais
            
            logger.info(f"🔍 DEBUG upsell parsed: idx={upsell_idx}, price_cents={price_cents}, price={price:.2f}, original_button={original_button_idx}")
            
            # ✅ VALIDAÇÃO: Preço deve ser > 0
            if price <= 0:
                logger.error(f"❌ Upsell com preço inválido: R$ {price:.2f} (centavos: {price_cents})")
                logger.error(f"❌ CALLBACK_DATA PROBLEMÁTICO: {callback_data}")
                logger.error(f"❌ PARTS PROBLEMÁTICAS: {parts}")
                return
            
            # ✅ CORREÇÃO CRÍTICA: Se preço for muito baixo, calcular valor real do upsell
            if price < 1.00:  # Menos de R$ 1,00
                logger.warning(f"⚠️ Upsell com preço muito baixo (R$ {price:.2f}), calculando valor real")
                
                # ✅ CORREÇÃO: Buscar configuração do upsell para calcular valor real
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
                            
                            # ✅ CORREÇÃO: Usar preço original do botão clicado
                            main_buttons = config.get('main_buttons', [])
                            if original_button_idx < len(main_buttons):
                                original_button = main_buttons[original_button_idx]
                                original_price = float(original_button.get('price', 0))
                                
                                if original_price > 0:
                                    price = original_price * (1 - discount_percentage / 100)
                                    logger.info(f"✅ Valor real calculado: R$ {original_price:.2f} com {discount_percentage}% OFF = R$ {price:.2f}")
                                else:
                                    price = 97.00  # Fallback para upsell
                                    logger.warning(f"⚠️ Preço original não encontrado, usando fallback R$ {price:.2f}")
                            else:
                                price = 97.00  # Fallback para upsell
                                logger.warning(f"⚠️ Botão original não encontrado, usando fallback R$ {price:.2f}")
                        else:
                            price = 97.00  # Fallback para upsell
                            logger.warning(f"⚠️ Configuração de upsell não encontrada, usando fallback R$ {price:.2f}")
                    else:
                        price = 97.00  # Fallback para upsell
                        logger.warning(f"⚠️ Configuração do bot não encontrada, usando fallback R$ {price:.2f}")
            
            # ✅ QI 500 FIX V2: Buscar descrição do BOTÃO ORIGINAL que gerou o upsell
            from flask import current_app
            from internal_logic.core.extensions import db
            from internal_logic.core.models import Bot as BotModel
            
            # Default seguro (sem índice de upsell)
            description = "Oferta Especial"
            
            with current_app.app_context():
                bot = db.session.get(BotModel, bot_id)
                if bot and bot.config:
                    fresh_config = bot.config.to_dict()
                    main_buttons = fresh_config.get('main_buttons', [])
                    
                    # Buscar o botão ORIGINAL (não o índice do upsell)
                    if original_button_idx >= 0 and original_button_idx < len(main_buttons):
                        button_data = main_buttons[original_button_idx]
                        product_name = button_data.get('description') or button_data.get('text') or f'Produto {original_button_idx + 1}'
                        description = f"{product_name} (Upsell)"
                        logger.info(f"✅ Descrição do produto original encontrada: {product_name}")
                    else:
                        # Fallback: Se não encontrar o botão, usar genérico
                        description = "Oferta Especial (Upsell)"
                        logger.warning(f"⚠️ Botão original {original_button_idx} não encontrado em {len(main_buttons)} botões")
            
            button_index = -1  # Sinalizar que é upsell
            
            logger.info(f"💙 UPSELL CLICADO | Upsell: {upsell_idx} | Botão Original: {original_button_idx} | Produto: {description} | Valor: R$ {price:.2f}")
            
            # ✅ VERIFICAR SE TEM ORDER BUMP PARA ESTE UPSELL
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
                # Responder callback - AGUARDANDO order bump
                requests.post(url, json={
                    'callback_query_id': callback_id,
                    'text': '🎁 Oferta especial para você!'
                }, timeout=3)
                
                logger.info(f"🎁 Order Bump detectado para upsell {upsell_idx + 1}!")
                # ✅ TODO: Criar função _show_upsell_order_bump similar ao _show_downsell_order_bump
                # Por ora, processar sem order bump
                logger.warning(f"⚠️ Order bump para upsell ainda não implementado, processando direto")
            
            # SEM ORDER BUMP - Gerar PIX direto
            # Responder callback
            requests.post(url, json={
                'callback_query_id': callback_id,
                'text': '🔄 Gerando pagamento PIX...'
            }, timeout=3)
            
            # Gerar PIX do upsell
            pix_data = bot_manager._generate_pix_payment(
                bot_id=bot_id,
                amount=price,
                description=description,
                customer_name=user_info.get('first_name', ''),
                customer_username=user_info.get('username', ''),
                customer_user_id=str(user_info.get('id', '')),
                is_upsell=True,  # ✅ Marcar como upsell
                upsell_index=upsell_idx  # ✅ Passar índice do upsell
            )
            # ✅ UX FIX: Tratamento Amigável de Rate Limit
            if pix_data and pix_data.get('rate_limit'):
                wait_time_msg = pix_data.get('wait_time', 'alguns segundos')
                bot_manager.send_telegram_message(
                    chat_id=chat_id,
                    message=f"⏳ <b>Aguarde {wait_time_msg}...</b>\n\nVocê já gerou um PIX agora mesmo. Verifique se recebeu o QR Code acima antes de tentar novamente.",
                    token=token
                )
                return
            
            if pix_data and pix_data.get('pix_code'):
                # ✅ PIX em linha única dentro de <code> para copiar com um toque
                payment_message = f"""🎯 <b>Produto:</b> {description}
💰 <b>Valor:</b> R$ {price:.2f}

📱 <b>PIX Copia e Cola:</b>
<code>{pix_data['pix_code']}</code>

<i>👆 Toque no código acima para copiar</i>

⏰ <b>Válido por:</b> 30 minutos

💡 <b>Após pagar, clique no botão abaixo para verificar e receber seu acesso!</b>"""
                
                buttons = [{
                    'text': '✅ Verificar Pagamento',
                    'callback_data': f'verify_{pix_data.get("payment_id")}'
                }]
                
                bot_manager.send_telegram_message(
                    token=token,
                    chat_id=str(chat_id),
                    message=payment_message.strip(),
                    buttons=buttons
                )
                
                logger.info(f"✅ PIX UPSELL ENVIADO! ID: {pix_data.get('payment_id')}")
            else:
                bot_manager.send_telegram_message(
                    token=token,
                    chat_id=str(chat_id),
                    message="❌ Erro ao gerar PIX. Entre em contato com o suporte."
                )
        
        # Botão de compra (VERIFICAR SE TEM ORDER BUMP)
        elif callback_data.startswith('buy_'):
            # ✅ NOVO FORMATO: buy_INDEX (mais simples, evita BUTTON_DATA_INVALID)
            # Extrair índice do botão
            button_index = int(callback_data.replace('buy_', ''))
            
            # Buscar dados do botão pela configuração
            main_buttons = config.get('main_buttons', [])
            if button_index < len(main_buttons):
                button_data = main_buttons[button_index]
                price = float(button_data.get('price', 0))
                description = button_data.get('description', 'Produto')
            else:
                price = 0
                description = 'Produto'
                button_data = None
            
            logger.info(f"💰 Produto: {description} | Valor: R$ {price:.2f} | Botão: {button_index}")
            
            # ✅ VERIFICAR SE TEM ORDER BUMPS PARA ESTE BOTÃO
            order_bumps = button_data.get('order_bumps', []) if button_index < len(main_buttons) else []
            enabled_order_bumps = [bump for bump in order_bumps if bump.get('enabled')]
            
            if enabled_order_bumps:
                # ✅ REDIS MIGRATION: Permitir que usuário escolha dentro do funil
                # Se já existe sessão ativa no Redis, CANCELAR automaticamente e iniciar nova
                import json as json_lib  # ✅ Proteção contra shadowing do módulo json
                user_key = f"orderbump_{chat_id}"
                session_key = f"gb:ob_session:{user_key}"
                
                redis_conn = get_redis_connection()
                existing_session_json = redis_conn.get(session_key)
                
                if existing_session_json:
                    existing_session = json_lib.loads(existing_session_json)
                    existing_button_index = existing_session.get('button_index')
                    existing_description = existing_session.get('original_description', 'Produto')
                    
                    # ✅ SOLUÇÃO: Cancelar sessão anterior automaticamente
                    logger.info(f"🔄 Nova intenção de compra detectada! Cancelando sessão anterior (botão {existing_button_index}) e iniciando nova (botão {button_index})")
                    
                    # Remover sessão anterior do Redis
                    redis_conn.delete(session_key)
                    # Também limpar cache de PIX associado
                    pix_cache_key = f"gb:pix_cache:{user_key}"
                    redis_conn.delete(pix_cache_key)
                    
                    logger.info(f"✅ Sessão anterior cancelada automaticamente. Nova oferta iniciada para botão {button_index}")
                
                # Responder callback - AGUARDANDO order bump
                requests.post(url, json={
                    'callback_query_id': callback_id,
                    'text': '🎁 Oferta especial para você!'
                }, timeout=3)
                
                logger.info(f"🎁 {len(enabled_order_bumps)} Order Bumps detectados para este botão!")
                # ✅ CORREÇÃO: Chamar _show_multiple_order_bumps (função correta restaurada)
                bot_manager._show_multiple_order_bumps(bot_id, token, chat_id, user_info, 
                                               price, description, button_index, enabled_order_bumps)
                return  # Aguarda resposta dos order bumps
            
            # SEM ORDER BUMP - Gerar PIX direto
            # Responder callback (não crítico — não pode travar o PIX)
            try:
                requests.post(url, json={
                    'callback_query_id': callback_id,
                    'text': '🔄 Gerando pagamento PIX...'
                }, timeout=3)
            except Exception:
                logger.warning("⚠️ Não foi possível responder callback (não crítico)")

            logger.info(f"🔘 [BUY FLOW] Iniciando geração PIX...")
            logger.info(f"📝 Sem order bump - gerando PIX direto...")
            pix_data = bot_manager._generate_pix_payment(
                bot_id=bot_id,
                amount=price,
                description=description,
                customer_name=user_info.get('first_name', ''),
                customer_username=user_info.get('username', ''),
                customer_user_id=str(user_info.get('id', '')),
                button_index=button_index,  # ✅ SISTEMA DE ASSINATURAS
                button_config=button_data   # ✅ SISTEMA DE ASSINATURAS
            )
            # ✅ UX FIX: Tratamento Amigável de Rate Limit
            if pix_data and pix_data.get('rate_limit'):
                wait_time_msg = pix_data.get('wait_time', 'alguns segundos')
                try:
                    bot_manager.send_telegram_message(
                        chat_id=chat_id,
                        message=f"⏳ <b>Aguarde {wait_time_msg}...</b>\n\nVocê já gerou um PIX agora mesmo. Verifique se recebeu o QR Code acima antes de tentar novamente.",
                        token=token
                    )
                except Exception:
                    logger.warning("⚠️ Falha ao enviar rate limit (não crítico)")
                return
            
            if pix_data and pix_data.get('pix_code'):
                # Enviar PIX para o cliente
                payment_message = f"""
🎯 <b>Produto:</b> {description}
💰 <b>Valor:</b> R$ {price:.2f}

📱 <b>PIX Copia e Cola:</b>
<code>{pix_data['pix_code']}</code>

<i>👆 Toque para copiar o código PIX</i>

⏰ <b>Válido por:</b> 30 minutos

💡 <b>Após pagar, clique no botão abaixo para verificar e receber seu acesso!</b>
                """
                
                # Botão para VERIFICAR PAGAMENTO
                buttons = [{
                    'text': '✅ Verificar Pagamento',
                    'callback_data': f'verify_{pix_data.get("payment_id")}'
                }]
                
                try:
                    bot_manager.send_telegram_message(
                        token=token,
                        chat_id=str(chat_id),
                        message=payment_message.strip(),
                        buttons=buttons
                    )
                except Exception:
                    logger.warning("⚠️ Falha ao enviar PIX para o cliente (não crítico)")
                
                logger.info(f"✅ PIX ENVIADO! ID: {pix_data.get('payment_id')}")
                
                # ✅ CORREÇÃO: Buscar config atualizada do BANCO (não da memória)
                from flask import current_app
                from internal_logic.core.extensions import db
                from internal_logic.core.models import Bot as BotModel
                
                with current_app.app_context():
                    bot = db.session.get(BotModel, bot_id)
                    if bot and bot.config:
                        config = bot.config.to_dict()
                    else:
                        config = {}
                
                logger.info(f"🔍 DEBUG Downsells - bot_id: {bot_id}")
                logger.info(f"🔍 DEBUG Downsells - enabled: {config.get('downsells_enabled', False)}")
                logger.info(f"🔍 DEBUG Downsells - list type: {type(config.get('downsells', []))}")
                logger.info(f"🔍 DEBUG Downsells - list content: {config.get('downsells', [])}")
                
                if config.get('downsells_enabled', False):
                    downsells = config.get('downsells', [])
                    logger.info(f"🔍 DEBUG Downsells - downsells encontrados: {len(downsells)}")
                    logger.info(f"🔍 DEBUG Downsells - is empty?: {len(downsells) == 0}")
                    if downsells and len(downsells) > 0:
                        bot_manager.schedule_downsells(
                            bot_id=bot_id,
                            payment_id=pix_data.get('payment_id'),
                            chat_id=chat_id,
                            downsells=downsells,
                            original_price=price,  # ✅ Preço do botão clicado
                            original_button_index=button_index
                        )
                    else:
                        logger.warning(f"⚠️ Downsells habilitados mas lista vazia!")
                else:
                    logger.info(f"ℹ️ Downsells desabilitados ou não configurados")
                
                logger.info(f"{'='*60}\n")
            elif pix_data is not None and pix_data.get('rate_limit'):
                # Rate limit ativado: cliente já tem PIX pendente e quer gerar outro
                logger.warning(f"⚠️ Rate limit: cliente precisa aguardar {pix_data.get('wait_time')}")
                
                rate_limit_message = f"""
⏳ <b>AGUARDE PARA GERAR NOVO PIX</b>

Você já tem um PIX pendente para outro produto.

⏰ <b>Por favor, aguarde {pix_data.get('wait_time', 'alguns segundos')}</b> para gerar um novo PIX para um produto diferente.

💡 <b>Ou:</b> Pague o PIX atual e depois gere um novo PIX.

<i>Você pode verificar seu PIX atual em "Verificar Pagamento"</i>
                """
                try:
                    bot_manager.send_telegram_message(
                        token=token,
                        chat_id=str(chat_id),
                        message=rate_limit_message.strip()
                    )
                except Exception:
                    logger.warning("⚠️ Falha ao enviar rate limit (não crítico)")
            elif pix_data is None:
                # PIX não foi gerado (erro no gateway)
                logger.error(f"❌ pix_data é None - erro no gateway")
                error_message = """
❌ <b>ERRO AO GERAR PAGAMENTO</b>

Desculpe, não foi possível processar seu pagamento.

<b>Entre em contato com o suporte.</b>
                """
                try:
                    bot_manager.send_telegram_message(
                        token=token,
                        chat_id=str(chat_id),
                        message=error_message.strip()
                    )
                except Exception:
                    logger.warning("⚠️ Falha ao enviar mensagem de erro (não crítico)")
            else:
                # Erro CRÍTICO ao gerar PIX
                logger.error(f"❌ FALHA CRÍTICA: Não foi possível gerar PIX!")
                logger.error(f"Verifique suas credenciais no painel!")
                
                error_message = """
❌ <b>ERRO AO GERAR PAGAMENTO</b>

Desculpe, não foi possível processar seu pagamento.

<b>Entre em contato com o suporte.</b>
                """
                try:
                    bot_manager.send_telegram_message(
                        token=token,
                        chat_id=str(chat_id),
                        message=error_message.strip()
                    )
                except Exception:
                    logger.warning("⚠️ Falha ao enviar mensagem de erro (não crítico)")
        
    except Exception as e:
        logger.error(f"❌ Erro ao processar callback: {e}")
        import traceback
        traceback.print_exc()
        raise  # ✅ RQ marca como failed + salva exc_info

