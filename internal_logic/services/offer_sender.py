"""
Offer Sender Service
====================
Servico unificado para envio de ofertas agendadas (downsell/upsell).
Extraido do BotManager para isolamento e testabilidade.

Modos:
- 'downsell': enviado quando payment.status == 'pending'
- 'upsell': enviado quando payment.status == 'paid'
"""

import logging
import traceback
import re
from datetime import datetime, timedelta
from typing import Optional, Dict, Any, List, Callable

logger = logging.getLogger(__name__)


def send_offer(
    mode: str,
    bot_state,
    send_message_func: Callable,
    bot_id: int,
    payment_id: str,
    chat_id: int,
    offer_config: dict,
    index: int,
    original_price: float = 0,
    original_button_index: int = -1,
) -> bool:
    """Envia oferta agendada (downsell ou upsell)

    Args:
        mode: 'downsell' ou 'upsell'
        bot_state: BotState com get_bot_data()
        send_message_func: Funcao para enviar mensagem Telegram
        bot_id: ID do bot
        payment_id: ID do pagamento
        chat_id: ID do chat
        offer_config: Configuracao da oferta
        index: Indice da oferta
        original_price: Preco original
        original_button_index: Indice do botao original
    """
    if mode not in ('downsell', 'upsell'):
        logger.error(f"Modo invalido: {mode}")
        return False

    is_downsell = mode == 'downsell'
    mode_label = 'downsell' if is_downsell else 'upsell'
    status_expected = 'pending' if is_downsell else 'paid'
    config_enabled_key = 'downsells_enabled' if is_downsell else 'upsells_enabled'
    callback_prefix = 'downsell_' if is_downsell else 'upsell_'

    logger.info(f"SEND_{mode_label.upper()} EXECUTADO")
    logger.info(f"   Timestamp: {datetime.now()}")
    logger.info(f"   bot_id: {bot_id}")
    logger.info(f"   payment_id: {payment_id}")
    logger.info(f"   chat_id: {chat_id}")
    logger.info(f"   index: {index}")
    logger.info(f"   original_price: {original_price}")
    logger.info(f"   original_button_index: {original_button_index}")
    logger.info(f"   {mode_label} config: {offer_config}")

    try:
        payment_status = _check_payment_status(payment_id)
        if payment_status is None:
            return False
        if payment_status != status_expected:
            logger.warning(
                f"Pagamento {payment_id} status='{payment_status}', "
                f"cancelando {mode_label} {index+1}"
            )
            return False

        logger.info(f"Pagamento ok ({payment_status}) - prosseguindo com {mode_label}")

        bot_info = bot_state.get_bot_data(bot_id)
        if not bot_info:
            logger.warning(f"Bot {bot_id} nao ativo no Redis, cancelando {mode_label} {index+1}")
            return False
        logger.info(f"Bot ativo no Redis")

        token = bot_info['token']

        config = _load_bot_config(bot_id, bot_info)
        if not config.get(config_enabled_key, False):
            logger.info(f"{mode_label.capitalize()}s desabilitados, cancelando {mode_label} {index+1}")
            return False
        logger.info(f"{mode_label.capitalize()}s habilitados")

        message = offer_config.get('message', '')
        media_url = offer_config.get('media_url', '')
        media_type = offer_config.get('media_type', 'video')
        audio_enabled = offer_config.get('audio_enabled', False)
        audio_url = offer_config.get('audio_url', '')

        buttons = _build_offer_buttons(
            offer_config=offer_config,
            config=config,
            index=index,
            original_price=original_price,
            original_button_index=original_button_index,
            callback_prefix=callback_prefix,
            mode_label=mode_label,
        )
        if buttons is None:
            return False

        order_bump = offer_config.get('order_bump', {})

        logger.info(f"Enviando {mode_label} {index+1} para chat {chat_id}")
        logger.info(f"   Botoes: {len(buttons)}")

        try:
            if media_url and '/c/' not in media_url and media_url.startswith('http'):
                result = send_message_func(
                    token=token,
                    chat_id=str(chat_id),
                    message=message,
                    media_url=media_url,
                    media_type=media_type,
                    buttons=buttons,
                )
                if not result:
                    result = send_message_func(
                        token=token,
                        chat_id=str(chat_id),
                        message=message,
                        buttons=buttons,
                    )
            else:
                result = send_message_func(
                    token=token,
                    chat_id=str(chat_id),
                    message=message,
                    buttons=buttons,
                )

            if result:
                logger.info(f"{mode_label.capitalize()} {index+1} ENVIADO para chat {chat_id}")
            else:
                logger.error(f"Falha ao enviar {mode_label} {index+1}")
        except Exception as send_error:
            logger.error(f"Erro ao enviar mensagem {mode_label} {index+1}: {send_error}")

        if audio_enabled and audio_url:
            logger.info(f"Enviando audio complementar do {mode_label} {index+1}...")
            try:
                send_message_func(
                    token=token,
                    chat_id=str(chat_id),
                    message="",
                    media_url=audio_url,
                    media_type='audio',
                    buttons=None,
                )
            except Exception as audio_error:
                logger.error(f"Erro ao enviar audio: {audio_error}")

        logger.info(f"FIM SEND_{mode_label.upper()}")
        return True

    except Exception as e:
        logger.error(f"Erro CRITICO ao enviar {mode_label} {index+1}: {e}")
        logger.error(traceback.format_exc())
        return False


def _check_payment_status(payment_id: str) -> Optional[str]:
    """Verifica status do pagamento no banco"""
    from flask import current_app
    from internal_logic.core.extensions import db
    from internal_logic.core.models import Payment

    try:
        with current_app.app_context():
            payment_lookup = str(payment_id).strip() if payment_id else ''
            payment = None
            if payment_lookup.isdigit():
                payment = Payment.query.get(int(payment_lookup))
            if not payment and payment_lookup:
                payment = Payment.query.filter_by(payment_id=payment_lookup).first()
            if not payment and payment_lookup:
                payment = Payment.query.filter_by(
                    gateway_transaction_id=payment_lookup
                ).first()
            if payment:
                logger.info(f"Status do pagamento: {payment.status}")
                return payment.status
            else:
                logger.error(f"Pagamento {payment_id} nao encontrado")
                return None
    except Exception as e:
        logger.error(f"Erro ao verificar pagamento: {e}")
        return None


def _load_bot_config(bot_id: int, bot_info: dict) -> dict:
    """Carrega config atualizada do banco (fallback para memoria)"""
    from flask import current_app
    from internal_logic.core.extensions import db
    from internal_logic.core.models import Bot as BotModel

    try:
        with current_app.app_context():
            bot = BotModel.query.get(bot_id)
            if bot and bot.config:
                config = bot.config.to_dict()
                logger.info("Config recarregada do banco")
                return config
    except Exception:
        pass

    config = bot_info.get('config', {})
    logger.warning("Usando config da memoria")
    return config


def _build_offer_buttons(
    offer_config: dict,
    config: dict,
    index: int,
    original_price: float = 0,
    original_button_index: int = -1,
    callback_prefix: str = 'downsell_',
    mode_label: str = 'downsell',
) -> Optional[List[Dict[str, Any]]]:
    """Constroi botoes para a oferta (modo fixo ou percentual)"""
    pricing_mode = offer_config.get('pricing_mode', 'fixed')
    logger.info(f"pricing_mode: {pricing_mode}")

    if pricing_mode == 'percentage':
        discount_percentage = float(offer_config.get('discount_percentage', 50))
        discount_percentage = max(1, min(95, discount_percentage))

        main_buttons = config.get('main_buttons', [])

        if main_buttons:
            buttons = []
            logger.info(f"MODO PERCENTUAL: {discount_percentage}% OFF em TODOS os produtos!")

            for btn_index, btn in enumerate(main_buttons):
                original_btn_price = float(btn.get('price', 0))
                if original_btn_price <= 0:
                    continue

                discounted_price = original_btn_price * (1 - discount_percentage / 100)
                if discounted_price < 0.50:
                    continue

                original_btn_text = btn.get('text', 'Produto')
                has_por = 'por' in original_btn_text.lower()
                product_name = re.sub(
                    r'\s*(por\s+)?(R\$\s*)?\d+[.,]\d+',
                    '',
                    original_btn_text,
                    flags=re.IGNORECASE,
                ).strip()
                product_name = re.sub(r'\s+por\s*$', '', product_name, flags=re.IGNORECASE).strip()
                if not product_name:
                    product_name = 'Produto'

                if has_por:
                    btn_text = f"{product_name} por R${discounted_price:.2f} ({int(discount_percentage)}% OFF)"
                else:
                    btn_text = f"{product_name} R${discounted_price:.2f} ({int(discount_percentage)}% OFF)"

                buttons.append({
                    'text': btn_text,
                    'callback_data': f'{callback_prefix}{index}_{int(discounted_price * 100)}_{btn_index}',
                })

            if not buttons:
                logger.error("Nenhum botao valido apos aplicar desconto percentual")
                return None

            logger.info(f"Total de {len(buttons)} opcoes de compra com desconto")

        else:
            if original_price > 0:
                price = original_price * (1 - discount_percentage / 100)
            else:
                logger.warning(f"original_price=0, usando preco padrao para {mode_label}")
                price = 9.97 if mode_label == 'downsell' else 97.00

            if price < 0.50:
                logger.error(f"Preco muito baixo (R$ {price:.2f})")
                return None

            custom_button_text = offer_config.get('button_text', '').strip()
            has_por = False
            if custom_button_text:
                has_por = 'por' in custom_button_text.lower()
                product_name = re.sub(
                    r'\s*(por\s+)?(R\$\s*)?\d+[.,]\d+',
                    '',
                    custom_button_text,
                    flags=re.IGNORECASE,
                ).strip()
                product_name = re.sub(r'\s+por\s*$', '', product_name, flags=re.IGNORECASE).strip()
                if not product_name:
                    product_name = offer_config.get('product_name', 'Produto') or 'Produto'
            else:
                product_name = offer_config.get('product_name', 'Produto') or 'Produto'

            if has_por:
                button_text = f'{product_name} por R${price:.2f} ({int(discount_percentage)}% OFF)'
            else:
                button_text = f'{product_name} R${price:.2f} ({int(discount_percentage)}% OFF)'

            buttons = [{
                'text': button_text,
                'callback_data': f'{callback_prefix}{index}_{int(price * 100)}_{0}',
            }]
    else:
        price = float(offer_config.get('price', 0))
        logger.info(f"MODO FIXO: R$ {price:.2f}")

        if price < 0.50:
            logger.error(f"Preco muito baixo (R$ {price:.2f})")
            return None

        button_text = offer_config.get('button_text', '').strip()
        if not button_text:
            button_text = f'Comprar por R$ {price:.2f}'

        buttons = [{
            'text': button_text,
            'callback_data': f'{callback_prefix}{index}_{int(price * 100)}_{original_button_index if original_button_index >= 0 else 0}',
        }]

    # Um botao por linha para ofertas (texto longo fica ileivel lado a lado)
    return [[b] for b in buttons]


def schedule_offers(
    mode: str,
    marathon_queue,
    bot_id: int,
    payment_id: str,
    chat_id: int,
    offers: list,
    original_price: float = 0,
    original_button_index: int = -1,
    user_id: Optional[int] = None,
) -> list:
    """Agenda ofertas (downsell/upsell) via RQ (Redis Queue)

    Args:
        mode: 'downsell' ou 'upsell'
        marathon_queue: Fila RQ para agendamento
        bot_id: ID do bot
        payment_id: ID do pagamento
        chat_id: ID do chat
        offers: Lista de ofertas configuradas
        original_price: Preco do botao original
        original_button_index: Indice do botao original clicado
        user_id: ID do usuario (necessario para send_downsell_async)

    Returns:
        Lista de job_ids agendados
    """
    if mode not in ('downsell', 'upsell'):
        logger.error(f"Modo invalido: {mode}")
        return []

    is_downsell = mode == 'downsell'
    mode_label = 'downsell' if is_downsell else 'upsell'
    job_prefix = mode_label

    logger.info(f"🚨 ===== SCHEDULE_{mode_label.upper()}S (RQ) =====")
    logger.info(f"   bot_id: {bot_id}")
    logger.info(f"   payment_id: {payment_id}")
    logger.info(f"   chat_id: {chat_id}")
    logger.info(f"   {mode_label}s count: {len(offers) if offers else 0}")

    try:
        if not offers:
            logger.warning(f"⚠️ Lista de {mode_label}s esta vazia!")
            return []

        if not marathon_queue:
            logger.error(f"❌ CRITICO: Fila RQ 'marathon' nao disponivel!")
            return []

        logger.info(f"📅 Agendando {len(offers)} {mode_label}(s) via RQ para payment {payment_id}")

        jobs_agendados = []
        for i, offer in enumerate(offers):
            delay_minutes = int(offer.get('delay_minutes', 5))
            logger.info(f"📅 {mode_label.capitalize()} {i+1}: delay={delay_minutes}min")

            try:
                if is_downsell and user_id:
                    from tasks_async import send_downsell_async
                    job = marathon_queue.enqueue_in(
                        timedelta(minutes=delay_minutes),
                        send_downsell_async,
                        user_id,
                        bot_id,
                        payment_id,
                        chat_id,
                        offer,
                        i,
                        original_price,
                        original_button_index,
                        job_id=f"{job_prefix}_{bot_id}_{payment_id}_{i}",
                        job_timeout=300,
                    )
                elif is_downsell:
                    from tasks_async import send_downsell_job
                    job = marathon_queue.enqueue_in(
                        timedelta(minutes=delay_minutes),
                        send_downsell_job,
                        bot_id=bot_id,
                        payment_id=payment_id,
                        chat_id=chat_id,
                        downsell=offer,
                        index=i,
                        original_price=original_price,
                        original_button_index=original_button_index,
                        job_id=f"{job_prefix}_{bot_id}_{payment_id}_{i}",
                        job_timeout=300,
                    )
                else:
                    from tasks_async import send_upsell_job
                    job = marathon_queue.enqueue_in(
                        timedelta(minutes=delay_minutes),
                        send_upsell_job,
                        bot_id=bot_id,
                        payment_id=payment_id,
                        chat_id=chat_id,
                        upsell=offer,
                        index=i,
                        original_price=original_price,
                        original_button_index=original_button_index,
                        job_id=f"{job_prefix}_{bot_id}_{payment_id}_{i}",
                        job_timeout=300,
                    )

                logger.info(f"✅ {mode_label.capitalize()} {i+1} AGENDADO via RQ: job_id={job.id if job else 'N/A'}")
                if job:
                    jobs_agendados.append(job.id)
                    if is_downsell:
                        try:
                            from internal_logic.core.redis_manager import get_redis_connection
                            r = get_redis_connection()
                            r.sadd(f"gb:downsell:jobs:{payment_id}", job.id)
                            r.expire(f"gb:downsell:jobs:{payment_id}", 86400)
                        except Exception:
                            pass

            except Exception as e:
                logger.error(f"❌ Erro ao agendar {mode_label} {i+1} no RQ: {e}", exc_info=True)

        logger.info(f"✅ Total de {len(jobs_agendados)} {mode_label}(s) agendado(s) via RQ")
        logger.info(f"🚨 ===== FIM SCHEDULE_{mode_label.upper()}S (RQ) =====")
        return jobs_agendados

    except Exception as e:
        logger.error(f"❌ Erro ao agendar {mode_label}s via RQ: {e}", exc_info=True)
        return []
