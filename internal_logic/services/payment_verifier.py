"""
Payment Verifier Service
=======================
Verificacao de status de pagamento e liberacao de acesso.
Extraido do BotManager para isolamento e testabilidade.
"""

import logging
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
            payment_lookup = str(payment_id).strip() if payment_id is not None else ''
            payment = None
            if payment_lookup.isdigit():
                payment = Payment.query.get(int(payment_lookup))
            if not payment and payment_lookup:
                payment = Payment.query.filter_by(payment_id=payment_lookup).first()
            if not payment and payment_lookup:
                payment = Payment.query.filter_by(gateway_transaction_id=payment_lookup).first()

            if not payment:
                logger.warning(f"Pagamento nao encontrado: {payment_id}")
                bot_manager.send_telegram_message(
                    token=token,
                    chat_id=str(chat_id),
                    message="Pagamento nao encontrado. Entre em contato com o suporte."
                )
                return

            logger.info(f"Status do pagamento LOCAL: {payment.status}")

            if payment.status == 'pending':
                if payment.gateway_type == 'paradise':
                    logger.info(f"Paradise: Webhook sera processado automaticamente pelo job")
                    logger.info(f"Se pagamento ja esta aprovado no painel Paradise, aguarde ate 2 minutos")
                elif payment.gateway_type == 'umbrellapag':
                    logger.info(f"[VERIFY UMBRELLAPAY] Iniciando verificacao dupla para payment_id={payment.payment_id}")
                    logger.info(f"   Transaction ID: {payment.gateway_transaction_id}")
                    logger.info(f"   Status atual: {payment.status}")

                    if not payment.gateway_transaction_id or not payment.gateway_transaction_id.strip():
                        logger.error(f"[VERIFY UMBRELLAPAY] gateway_transaction_id nao encontrado para payment_id={payment.payment_id}")
                        return

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
                        logger.error(f"[VERIFY UMBRELLAPAY] Erro ao buscar webhook recente: {e}", exc_info=True)
                        webhook_recente = None

                    if webhook_recente:
                        logger.info(f"[VERIFY UMBRELLAPAY] Webhook recente encontrado (recebido em {webhook_recente.received_at})")
                        logger.info(f"   Transaction ID: {payment.gateway_transaction_id}")
                        logger.info(f"   Status do webhook: {webhook_recente.status}")
                        logger.info(f"   Aguardando processamento do webhook... Nao atualizando manualmente")

                        try:
                            db.session.refresh(payment)
                            if payment.status == 'paid':
                                logger.info(f"[VERIFY UMBRELLAPAY] Webhook ja atualizou o pagamento! Status: {payment.status}")
                            else:
                                logger.info(f"[VERIFY UMBRELLAPAY] Webhook ainda nao processou. Aguarde ate 2 minutos.")
                        except Exception as e:
                            logger.error(f"[VERIFY UMBRELLAPAY] Erro ao recarregar payment: {e}", exc_info=True)
                        return

                    try:
                        bot = payment.bot
                        if not bot:
                            logger.error(f"[VERIFY UMBRELLAPAY] Bot nao encontrado para payment_id={payment.payment_id}")
                            return

                        gateway = Gateway.query.filter_by(
                            user_id=bot.user_id,
                            gateway_type=payment.gateway_type,
                            is_verified=True
                        ).first()

                        if not gateway:
                            logger.warning(f"[VERIFY UMBRELLAPAY] Gateway nao encontrado para gateway_type={payment.gateway_type}, user_id={bot.user_id}")
                            return

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
                            logger.error(f"[VERIFY UMBRELLAPAY] Nao foi possivel criar instancia do gateway")
                            return

                        logger.info(f"[VERIFY UMBRELLAPAY] Consulta 1/2: Verificando status na API...")
                        logger.info(f"   Transaction ID: {payment.gateway_transaction_id}")

                        try:
                            api_status_1 = payment_gateway.get_payment_status(payment.gateway_transaction_id)
                            status_1 = api_status_1.get('status') if api_status_1 else None
                            logger.info(f"[VERIFY UMBRELLAPAY] Consulta 1 retornou: status={status_1}")
                        except Exception as e:
                            logger.error(f"[VERIFY UMBRELLAPAY] Erro na consulta 1: {e}", exc_info=True)
                            logger.error(f"   Transaction ID: {payment.gateway_transaction_id}")
                            return

                        try:
                            db.session.refresh(payment)
                            if not payment:
                                logger.warning(f"[VERIFY UMBRELLAPAY] Payment nao encontrado apos refresh")
                                return

                            if payment.status == 'paid':
                                logger.info(f"[VERIFY UMBRELLAPAY] Pagamento ja esta PAID no sistema. Nao atualizar.")
                                return
                        except Exception as e:
                            logger.error(f"[VERIFY UMBRELLAPAY] Erro ao recarregar payment: {e}", exc_info=True)
                            return

                        logger.info(f"[VERIFY UMBRELLAPAY] Aguardando 3 segundos antes da consulta 2...")
                        time.sleep(3)

                        logger.info(f"[VERIFY UMBRELLAPAY] Consulta 2/2: Verificando status na API novamente...")
                        logger.info(f"   Transaction ID: {payment.gateway_transaction_id}")

                        try:
                            api_status_2 = payment_gateway.get_payment_status(payment.gateway_transaction_id)
                            status_2 = api_status_2.get('status') if api_status_2 else None
                            logger.info(f"[VERIFY UMBRELLAPAY] Consulta 2 retornou: status={status_2}")
                        except Exception as e:
                            logger.error(f"[VERIFY UMBRELLAPAY] Erro na consulta 2: {e}", exc_info=True)
                            logger.error(f"   Transaction ID: {payment.gateway_transaction_id}")
                            return

                        if status_1 == 'paid' and status_2 == 'paid':
                            try:
                                db.session.refresh(payment)
                                if not payment:
                                    logger.warning(f"[VERIFY UMBRELLAPAY] Payment nao encontrado apos refresh final")
                                    return

                                if payment.status == 'paid':
                                    logger.info(f"[VERIFY UMBRELLAPAY] Pagamento ja foi atualizado por outro processo. Nao atualizar novamente.")
                                    return
                            except Exception as e:
                                logger.error(f"[VERIFY UMBRELLAPAY] Erro ao recarregar payment final: {e}", exc_info=True)
                                return

                            logger.info(f"[VERIFY UMBRELLAPAY] VERIFICACAO DUPLA CONFIRMADA: Ambas consultas retornaram 'paid'")
                            logger.info(f"   Payment ID: {payment.payment_id}")
                            logger.info(f"   Transaction ID: {payment.gateway_transaction_id}")
                            logger.info(f"   Atualizando pagamento para 'paid'...")

                            try:
                                payment.status = 'paid'
                                payment.paid_at = get_brazil_time()

                                db.session.commit()
                                logger.info(f"[VERIFY UMBRELLAPAY] Pagamento CONFIRMADO e COMMITADO - ID: {payment.payment_id}")

                            except Exception as commit_error:
                                db.session.rollback()
                                logger.error(f"[VERIFY UMBRELLAPAY] ERRO CRITICO ao confirmar pagamento: {commit_error}", exc_info=True)
                                return

                            try:
                                db.session.refresh(payment)

                                logger.info(f"[VERIFY UMBRELLAPAY] Purchase sera disparado apenas quando lead acessar link de entrega")

                                try:
                                    from internal_logic.services.achievements import check_and_unlock_achievements
                                    new_achievements = check_and_unlock_achievements(payment.bot.owner)
                                    if new_achievements:
                                        logger.info(f"[VERIFY UMBRELLAPAY] {len(new_achievements)} conquista(s) desbloqueada(s)!")
                                except Exception as e:
                                    logger.warning(f"[VERIFY UMBRELLAPAY] Erro ao verificar conquistas (nao critico): {e}")

                            except Exception as phase2_error:
                                logger.error(f"[VERIFY UMBRELLAPAY] Erro nao critico apos confirmacao: {phase2_error}", exc_info=True)

                            logger.info(f"[UPSELLS VERIFY] Verificando condicoes: status='{payment.status}', has_config={payment.bot.config is not None if payment.bot else False}, upsells_enabled={payment.bot.config.upsells_enabled if (payment.bot and payment.bot.config) else 'N/A'}")

                            if payment.status == 'paid' and payment.bot.config and payment.bot.config.upsells_enabled:
                                logger.info(f"[UPSELLS VERIFY] Condicoes atendidas! Processando upsells para payment {payment.payment_id}")
                                try:
                                    from internal_logic.core.models import Payment as PaymentModel
                                    payment_check = PaymentModel.query.filter_by(payment_id=payment.payment_id).first()

                                    if not bot_manager.scheduler:
                                        logger.error(f"CRITICO: Scheduler nao esta disponivel! Upsells NAO serao agendados!")
                                        logger.error(f"   Payment ID: {payment.payment_id}")
                                        logger.error(f"   Verificar se APScheduler foi inicializado corretamente")
                                    else:
                                        try:
                                            scheduler_running = bot_manager.scheduler.running
                                            if not scheduler_running:
                                                logger.error(f"CRITICO: Scheduler existe mas NAO esta rodando!")
                                                logger.error(f"   Payment ID: {payment.payment_id}")
                                                logger.error(f"   Upsells NAO serao executados se scheduler nao estiver rodando!")
                                        except Exception as scheduler_check_error:
                                            logger.warning(f"Nao foi possivel verificar se scheduler esta rodando: {scheduler_check_error}")

                                        upsells_already_scheduled = False
                                        try:
                                            for i in range(10):
                                                job_id = f"upsell_{payment.bot_id}_{payment.payment_id}_{i}"
                                                existing_job = bot_manager.scheduler.get_job(job_id)
                                                if existing_job:
                                                    upsells_already_scheduled = True
                                                    logger.info(f"Upsells ja foram agendados para payment {payment.payment_id} (job {job_id} existe)")
                                                    logger.info(f"   Job encontrado: {job_id}, proxima execucao: {existing_job.next_run_time}")
                                                    break
                                        except Exception as check_error:
                                            logger.error(f"ERRO ao verificar jobs existentes: {check_error}", exc_info=True)
                                            logger.warning(f"Continuando mesmo com erro na verificacao (pode causar duplicacao)")

                                        if bot_manager.scheduler and not upsells_already_scheduled:
                                            upsells = payment.bot.config.get_upsells()

                                            if upsells:
                                                logger.info(f"[UPSELLS VERIFY] Verificando upsells para produto: {payment.product_name}")

                                                matched_upsells = []
                                                for upsell in upsells:
                                                    trigger_product = upsell.get('trigger_product', '')
                                                    if not trigger_product or trigger_product == payment.product_name:
                                                        matched_upsells.append(upsell)

                                                if matched_upsells:
                                                    logger.info(f"[UPSELLS VERIFY] {len(matched_upsells)} upsell(s) encontrado(s) para '{payment.product_name}'")

                                                    bot_manager.schedule_upsells(
                                                        bot_id=payment.bot_id,
                                                        payment_id=payment.payment_id,
                                                        chat_id=int(payment.customer_user_id),
                                                        upsells=matched_upsells,
                                                        original_price=payment.amount,
                                                        original_button_index=payment.button_index if payment.button_index is not None else -1
                                                    )

                                                    logger.info(f"[UPSELLS VERIFY] Upsells agendados com sucesso para payment {payment.payment_id}!")
                                                else:
                                                    logger.info(f"[UPSELLS VERIFY] Nenhum upsell configurado para '{payment.product_name}' (trigger_product nao faz match)")
                                            else:
                                                logger.info(f"[UPSELLS VERIFY] Lista de upsells vazia no config do bot")
                                        else:
                                            if not bot_manager.scheduler:
                                                logger.error(f"[UPSELLS VERIFY] Scheduler nao disponivel - upsells nao serao agendados")
                                            else:
                                                logger.info(f"[UPSELLS VERIFY] Upsells ja foram agendados anteriormente para payment {payment.payment_id} (evitando duplicacao)")

                                except Exception as upsell_error:
                                    logger.error(f"[UPSELLS VERIFY] Erro ao processar upsells: {upsell_error}", exc_info=True)

                        elif status_1 == 'paid' and status_2 != 'paid':
                            logger.warning(f"[VERIFY UMBRELLAPAY] DISCREPANCIA DETECTADA: Consulta 1=paid, Consulta 2={status_2}")
                            logger.warning(f"   Transaction ID: {payment.gateway_transaction_id}")
                            logger.warning(f"   Nao atualizando - inconsistencia detectada. Aguardando webhook ou proxima verificacao.")

                        elif status_1 != 'paid' and status_2 == 'paid':
                            logger.warning(f"[VERIFY UMBRELLAPAY] DISCREPANCIA DETECTADA: Consulta 1={status_1}, Consulta 2=paid")
                            logger.warning(f"   Transaction ID: {payment.gateway_transaction_id}")
                            logger.warning(f"   Nao atualizando - inconsistencia detectada. Aguardando webhook ou proxima verificacao.")

                        else:
                            logger.info(f"[VERIFY UMBRELLAPAY] Ambas consultas retornaram: {status_1} e {status_2} (nao e 'paid')")
                            logger.info(f"   Transaction ID: {payment.gateway_transaction_id}")
                            logger.info(f"   Pagamento ainda pendente no gateway")

                    except Exception as e:
                        logger.error(f"[VERIFY UMBRELLAPAY] Erro critico na verificacao: {e}", exc_info=True)
                        logger.error(f"   Payment ID: {payment.payment_id}")
                        logger.error(f"   Transaction ID: {payment.gateway_transaction_id}")
                        return
                else:
                    logger.info(f"Gateway {payment.gateway_type}: Consultando status na API...")

                    bot = payment.bot
                    gateway = Gateway.query.filter_by(
                        user_id=bot.user_id,
                        gateway_type=payment.gateway_type,
                        is_verified=True
                    ).first()

                    if gateway:
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
                                    logger.info(f"API confirmou pagamento! Atualizando status...")

                                    try:
                                        payment.status = 'paid'
                                        from internal_logic.core.models import get_brazil_time
                                        payment.paid_at = get_brazil_time()

                                        db.session.commit()
                                        logger.info(f"Pagamento CONFIRMADO e COMMITADO - ID: {payment.payment_id}")

                                    except Exception as commit_error:
                                        db.session.rollback()
                                        logger.error(f"ERRO CRITICO ao confirmar pagamento: {commit_error}", exc_info=True)
                                        return

                                    try:
                                        db.session.refresh(payment)

                                        logger.info(f"Purchase sera disparado apenas quando lead acessar link de entrega")

                                        try:
                                            from internal_logic.services.achievements import check_and_unlock_achievements
                                            new_achievements = check_and_unlock_achievements(payment.bot.owner)
                                            if new_achievements:
                                                logger.info(f"{len(new_achievements)} conquista(s) desbloqueada(s)!")
                                        except Exception as e:
                                            logger.warning(f"Erro ao verificar conquistas (nao critico): {e}")

                                    except Exception as phase2_error:
                                        logger.error(f"Erro nao critico apos confirmacao de pagamento: {phase2_error}", exc_info=True)

                                    logger.info(f"[UPSELLS VERIFY OTHER] Verificando condicoes: status='paid', has_config={payment.bot.config is not None if payment.bot else False}, upsells_enabled={payment.bot.config.upsells_enabled if (payment.bot and payment.bot.config) else 'N/A'}")

                                    if payment.status == 'paid' and payment.bot.config and payment.bot.config.upsells_enabled:
                                        logger.info(f"[UPSELLS VERIFY OTHER] Condicoes atendidas! Processando upsells para payment {payment.payment_id}")
                                        try:
                                            from internal_logic.core.models import Payment as PaymentModel
                                            payment_check = PaymentModel.query.filter_by(payment_id=payment.payment_id).first()

                                            if not bot_manager.scheduler:
                                                logger.error(f"CRITICO: Scheduler nao esta disponivel! Upsells NAO serao agendados!")
                                                logger.error(f"   Payment ID: {payment.payment_id}")
                                                logger.error(f"   Verificar se APScheduler foi inicializado corretamente")
                                            else:
                                                try:
                                                    scheduler_running = bot_manager.scheduler.running
                                                    if not scheduler_running:
                                                        logger.error(f"CRITICO: Scheduler existe mas NAO esta rodando!")
                                                        logger.error(f"   Payment ID: {payment.payment_id}")
                                                        logger.error(f"   Upsells NAO serao executados se scheduler nao estiver rodando!")
                                                except Exception as scheduler_check_error:
                                                    logger.warning(f"Nao foi possivel verificar se scheduler esta rodando: {scheduler_check_error}")

                                                upsells_already_scheduled = False
                                                try:
                                                    for i in range(10):
                                                        job_id = f"upsell_{payment.bot_id}_{payment.payment_id}_{i}"
                                                        existing_job = bot_manager.scheduler.get_job(job_id)
                                                        if existing_job:
                                                            upsells_already_scheduled = True
                                                            logger.info(f"Upsells ja foram agendados para payment {payment.payment_id} (job {job_id} existe)")
                                                            logger.info(f"   Job encontrado: {job_id}, proxima execucao: {existing_job.next_run_time}")
                                                            break
                                                except Exception as check_error:
                                                    logger.error(f"ERRO ao verificar jobs existentes: {check_error}", exc_info=True)
                                                    logger.warning(f"Continuando mesmo com erro na verificacao (pode causar duplicacao)")

                                            if bot_manager.scheduler and not upsells_already_scheduled:
                                                upsells = payment.bot.config.get_upsells()

                                                if upsells:
                                                    logger.info(f"[UPSELLS VERIFY OTHER] Verificando upsells para produto: {payment.product_name}")

                                                    matched_upsells = []
                                                    for upsell in upsells:
                                                        trigger_product = upsell.get('trigger_product', '')
                                                        if not trigger_product or trigger_product == payment.product_name:
                                                            matched_upsells.append(upsell)

                                                    if matched_upsells:
                                                        logger.info(f"[UPSELLS VERIFY OTHER] {len(matched_upsells)} upsell(s) encontrado(s) para '{payment.product_name}'")

                                                        bot_manager.schedule_upsells(
                                                            bot_id=payment.bot_id,
                                                            payment_id=payment.payment_id,
                                                            chat_id=int(payment.customer_user_id),
                                                            upsells=matched_upsells,
                                                            original_price=payment.amount,
                                                            original_button_index=-1
                                                        )

                                                        logger.info(f"[UPSELLS VERIFY OTHER] Upsells agendados com sucesso para payment {payment.payment_id}!")
                                                    else:
                                                        logger.info(f"[UPSELLS VERIFY OTHER] Nenhum upsell configurado para '{payment.product_name}' (trigger_product nao faz match)")
                                                else:
                                                    logger.info(f"[UPSELLS VERIFY OTHER] Lista de upsells vazia no config do bot")
                                            else:
                                                if not bot_manager.scheduler:
                                                    logger.error(f"[UPSELLS VERIFY OTHER] Scheduler nao disponivel - upsells nao serao agendados")
                                                else:
                                                    logger.info(f"[UPSELLS VERIFY OTHER] Upsells ja foram agendados anteriormente para payment {payment.payment_id} (evitando duplicacao)")

                                        except Exception as e:
                                            logger.error(f"[UPSELLS VERIFY OTHER] Erro ao processar upsells: {e}", exc_info=True)
                                            import traceback
                                            traceback.print_exc()

                                    try:
                                        from internal_logic.services.payment_processor import send_payment_delivery
                                        logger.info(f"[VERIFY OTHER] Enviando entregavel via send_payment_delivery para {payment.payment_id}")

                                        db.session.refresh(payment)

                                        if payment.status == 'paid':
                                            resultado = send_payment_delivery(payment, bot_manager)
                                            if resultado:
                                                logger.info(f"[VERIFY OTHER] Entregavel enviado com sucesso via send_payment_delivery")
                                            else:
                                                logger.warning(f"[VERIFY OTHER] send_payment_delivery retornou False para {payment.payment_id}")
                                    except Exception as e:
                                        logger.error(f"[VERIFY OTHER] Erro ao enviar entregavel via send_payment_delivery: {e}", exc_info=True)
                            elif api_status:
                                logger.info(f"API retornou status: {api_status.get('status')}")

            db.session.refresh(payment)
            logger.info(f"Status FINAL do pagamento: {payment.status}")

            if payment.status == 'paid':
                db.session.refresh(payment)

                if payment.status != 'paid':
                    logger.error(
                        f"ERRO GRAVE: Status mudou apos refresh! Esperado: 'paid', Atual: {payment.status}"
                    )
                    logger.error(f"   Payment ID: {payment.payment_id}")
                    return

                logger.info(f"PAGAMENTO CONFIRMADO! Liberando acesso...")

                flow_processed = False
                if payment.flow_step_id:
                    bot_flow = Bot.query.get(bot_id)
                    if bot_flow and bot_flow.config:
                        flow_config = bot_flow.config.to_dict()
                        flow_enabled = flow_config.get('flow_enabled', False)

                        import json
                        flow_steps_raw = flow_config.get('flow_steps', [])
                        if isinstance(flow_steps_raw, str):
                            try:
                                flow_steps = json.loads(flow_steps_raw)
                            except:
                                flow_steps = []
                        else:
                            flow_steps = flow_steps_raw if isinstance(flow_steps_raw, list) else []

                        if flow_enabled and flow_steps:
                            current_step = bot_manager._find_step_by_id(flow_steps, payment.flow_step_id)

                            if current_step:
                                connections = current_step.get('connections', {})
                                telegram_user_id = str(user_info.get('id', ''))

                                if payment.status == 'paid':
                                    next_step_id = connections.get('next')
                                else:
                                    next_step_id = connections.get('pending')

                                if next_step_id:
                                    logger.info(f"[FLOW V] Payment {payment.status} - executando step: {next_step_id}")

                                    flow_snapshot = bot_manager._get_flow_snapshot_from_redis(bot_id, telegram_user_id)

                                    try:
                                        bot_manager._execute_flow_recursive(
                                            bot_id, token, flow_config,
                                            chat_id, telegram_user_id,
                                            next_step_id,
                                            recursion_depth=0,
                                            visited_steps=set(),
                                            flow_snapshot=flow_snapshot
                                        )
                                        flow_processed = True
                                        logger.info(f"[FLOW V] Proximo step executado: {next_step_id}")
                                        return
                                    except Exception as e:
                                        logger.error(f"[FLOW V] Erro ao executar proximo step: {e}", exc_info=True)
                            else:
                                logger.error(f"[FLOW V] Step {payment.flow_step_id} nao encontrado mais na config atual")

                if not flow_processed:
                    logger.info(f"Purchase sera disparado apenas quando lead acessar link de entrega: /delivery/<token>")

                    bot_manager.cancel_downsells(payment.payment_id)

                    try:
                        from internal_logic.services.payment_processor import send_payment_delivery
                        logger.info(f"[VERIFY] Enviando entregavel via send_payment_delivery para {payment.payment_id}")

                        db.session.refresh(payment)

                        if payment.status == 'paid':
                            resultado = send_payment_delivery(payment, bot_manager)
                            if resultado:
                                logger.info(f"[VERIFY] Entregavel enviado com sucesso via send_payment_delivery")

                                if payment.status == 'paid' and payment.bot.config and payment.bot.config.upsells_enabled:
                                    logger.info(f"[UPSELLS VERIFY] Condicoes atendidas! Processando upsells para payment {payment.payment_id}")
                                    try:
                                        from internal_logic.core.models import Payment as PaymentModel
                                        payment_check = PaymentModel.query.filter_by(payment_id=payment.payment_id).first()

                                        if not bot_manager.scheduler:
                                            logger.error(f"CRITICO: Scheduler nao esta disponivel! Upsells NAO serao agendados!")
                                            logger.error(f"   Payment ID: {payment.payment_id}")
                                            logger.error(f"   Verificar se APScheduler foi inicializado corretamente")
                                        else:
                                            try:
                                                scheduler_running = bot_manager.scheduler.running
                                                if not scheduler_running:
                                                    logger.error(f"CRITICO: Scheduler existe mas NAO esta rodando!")
                                                    logger.error(f"   Payment ID: {payment.payment_id}")
                                                    logger.error(f"   Upsells NAO serao executados se scheduler nao estiver rodando!")
                                            except Exception as scheduler_check_error:
                                                logger.warning(f"Nao foi possivel verificar se scheduler esta rodando: {scheduler_check_error}")

                                            upsells_already_scheduled = False
                                            try:
                                                for i in range(10):
                                                    job_id = f"upsell_{payment.bot_id}_{payment.payment_id}_{i}"
                                                    existing_job = bot_manager.scheduler.get_job(job_id)
                                                    if existing_job:
                                                        upsells_already_scheduled = True
                                                        logger.info(f"Upsells ja foram agendados para payment {payment.payment_id} (job {job_id} existe)")
                                                        logger.info(f"   Job encontrado: {job_id}, proxima execucao: {existing_job.next_run_time}")
                                                        break
                                            except Exception as check_error:
                                                logger.error(f"ERRO ao verificar jobs existentes: {check_error}", exc_info=True)
                                                logger.warning(f"Continuando mesmo com erro na verificacao (pode causar duplicacao)")

                                        if bot_manager.scheduler and not upsells_already_scheduled:
                                            upsells = payment.bot.config.get_upsells()

                                            if upsells:
                                                logger.info(f"[UPSELLS VERIFY] Verificando upsells para produto: {payment.product_name}")

                                                matched_upsells = []
                                                for upsell in upsells:
                                                    trigger_product = upsell.get('trigger_product', '')
                                                    if not trigger_product or trigger_product == payment.product_name:
                                                        matched_upsells.append(upsell)

                                                if matched_upsells:
                                                    logger.info(f"[UPSELLS VERIFY] {len(matched_upsells)} upsell(s) encontrado(s) para '{payment.product_name}'")

                                                    bot_manager.schedule_upsells(
                                                        bot_id=payment.bot_id,
                                                        payment_id=payment.payment_id,
                                                        chat_id=int(payment.customer_user_id),
                                                        upsells=matched_upsells,
                                                        original_price=payment.amount,
                                                        original_button_index=payment.button_index if payment.button_index is not None else -1
                                                    )

                                                    logger.info(f"[UPSELLS VERIFY] Upsells agendados com sucesso para payment {payment.payment_id}!")
                                                else:
                                                    logger.info(f"[UPSELLS VERIFY] Nenhum upsell configurado para '{payment.product_name}' (trigger_product nao faz match)")
                                            else:
                                                logger.info(f"[UPSELLS VERIFY] Lista de upsells vazia no config do bot")
                                        else:
                                            if not bot_manager.scheduler:
                                                logger.error(f"[UPSELLS VERIFY] Scheduler nao disponivel - upsells nao serao agendados")
                                            else:
                                                logger.info(f"[UPSELLS VERIFY] Upsells ja foram agendados anteriormente para payment {payment.payment_id} (evitando duplicacao)")

                                    except Exception as e:
                                        logger.error(f"[UPSELLS VERIFY] Erro ao processar upsells: {e}", exc_info=True)
                                        import traceback
                                        traceback.print_exc()
                            else:
                                logger.warning(f"[VERIFY] send_payment_delivery retornou False para {payment.payment_id}")
                        else:
                            logger.error(
                                f"ERRO GRAVE: Tentativa de enviar entregavel com status invalido "
                                f"(status: {payment.status}, payment_id: {payment.payment_id})"
                            )
                    except Exception as e:
                        logger.error(f"[VERIFY] Erro ao enviar entregavel via send_payment_delivery: {e}", exc_info=True)

                        logger.warning(f"[VERIFY] Usando fallback para envio de mensagem (send_payment_delivery falhou)")

                        bot = payment.bot
                        bot_data = bot_manager.bot_state.get_bot_data(bot_id)
                        bot_config = bot_data.get('config', {}) if bot_data else {}
                        access_link = bot_config.get('access_link', '')
                        custom_success_message = bot_config.get('success_message', '').strip()

                        if custom_success_message:
                            success_message = custom_success_message
                            success_message = success_message.replace('{produto}', payment.product_name or 'Produto')
                            success_message = success_message.replace('{valor}', f'R$ {payment.amount:.2f}')
                            success_message = success_message.replace('{link}', access_link or 'Link nao configurado')
                        elif access_link:
                            success_message = f"""
PAGAMENTO CONFIRMADO!

Parabens! Seu pagamento foi aprovado com sucesso!

Produto: {payment.product_name}
Valor pago: R$ {payment.amount:.2f}

Seu acesso:
{access_link}

Aproveite! 
                            """
                        else:
                            success_message = "Pagamento confirmado! Entre em contato com o suporte para receber seu acesso."

                        bot_manager.send_telegram_message(
                            token=token,
                            chat_id=str(chat_id),
                            message=success_message.strip()
                        )

                    logger.info(f"Acesso liberado para {user_info.get('first_name')}")
            else:
                logger.info(f"Pagamento ainda pendente...")

                flow_processed = False
                if payment.flow_step_id:
                    bot_flow = Bot.query.get(bot_id)
                    if bot_flow and bot_flow.config:
                        flow_config = bot_flow.config.to_dict()
                        flow_enabled = flow_config.get('flow_enabled', False)

                        import json
                        flow_steps_raw = flow_config.get('flow_steps', [])
                        if isinstance(flow_steps_raw, str):
                            try:
                                flow_steps = json.loads(flow_steps_raw)
                            except:
                                flow_steps = []
                        else:
                            flow_steps = flow_steps_raw if isinstance(flow_steps_raw, list) else []

                        if flow_enabled and flow_steps:
                            current_step = bot_manager._find_step_by_id(flow_steps, payment.flow_step_id)

                            if current_step:
                                connections = current_step.get('connections', {})
                                telegram_user_id = str(user_info.get('id', ''))

                                if payment.status == 'pending':
                                    pending_step_id = connections.get('pending')

                                    if pending_step_id:
                                        logger.info(f"[FLOW V] Payment pendente - executando step: {pending_step_id}")

                                        flow_snapshot = bot_manager._get_flow_snapshot_from_redis(bot_id, telegram_user_id)

                                        try:
                                            bot_manager._execute_flow_recursive(
                                                bot_id, token, flow_config,
                                                chat_id, telegram_user_id,
                                                pending_step_id,
                                                recursion_depth=0,
                                                visited_steps=set(),
                                                flow_snapshot=flow_snapshot
                                            )
                                            flow_processed = True
                                            logger.info(f"[FLOW V] Pending step executado: {pending_step_id}")
                                            return
                                        except Exception as e:
                                            logger.error(f"[FLOW V] Erro ao executar pending step: {e}", exc_info=True)

                if not flow_processed:
                    bot = payment.bot
                    bot_data = bot_manager.bot_state.get_bot_data(bot_id)
                    bot_config = bot_data.get('config', {}) if bot_data else {}
                    custom_pending_message = bot_config.get('pending_message', '').strip()

                    pix_code = payment.product_description or 'Aguardando...'

                    if (pix_code == 'Aguardando...' or not pix_code or len(pix_code) < 20) and payment.gateway_type == 'umbrellapag':
                        try:
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
                                    try:
                                        response = payment_gateway._make_request('GET', f'/user/transactions/{payment.gateway_transaction_id}')
                                        if response and response.status_code == 200:
                                            api_data = response.json()

                                            inner_data = api_data
                                            if isinstance(api_data, dict) and 'data' in api_data:
                                                inner_data = api_data.get('data', {})
                                                if isinstance(inner_data, dict) and 'data' in inner_data:
                                                    inner_data = inner_data.get('data', {})

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
                                                        logger.info(f"[VERIFY] PIX code recuperado do gateway via API para {payment.payment_id}")
                                    except Exception as api_error:
                                        logger.debug(f"[VERIFY] Nao foi possivel buscar PIX code via API (nao critico): {api_error}")
                        except Exception as e:
                            logger.warning(f"[VERIFY] Erro ao buscar PIX code do gateway (fallback): {e}")

                    if custom_pending_message:
                        pending_message = custom_pending_message
                        pending_message = pending_message.replace('{pix_code}', f'<code>{pix_code}</code>')
                        pending_message = pending_message.replace('{produto}', payment.product_name or 'Produto')
                        pending_message = pending_message.replace('{valor}', f'R$ {payment.amount:.2f}')
                    else:
                        if payment.gateway_type == 'paradise':
                            pending_message = f"""Aguardando confirmacao

Seu pagamento esta sendo processado.

PIX Copia e Cola:
<code>{pix_code}</code>

Toque no codigo acima para copiar

Confirmacao automatica:
Se voce ja pagou, o sistema confirmara automaticamente em ate 2 minutos via webhook.

Voce sera notificado assim que o pagamento for confirmado!"""
                        elif payment.gateway_type == 'umbrellapag':
                            pending_message = f"""Aguardando confirmacao

Seu pagamento esta sendo processado.

PIX Copia e Cola:
<code>{pix_code}</code>

Toque no codigo acima para copiar

Confirmacao automatica:
Se voce ja pagou, o sistema confirmara automaticamente em ate 5 minutos via webhook ou job de sincronizacao.

Dica: Voce pode clicar novamente em "Verificar Pagamento" para consultar o status manualmente.

Voce sera notificado assim que o pagamento for confirmado!"""
                        else:
                            pending_message = f"""Pagamento ainda nao identificado

Seu pagamento ainda nao foi confirmado.

PIX Copia e Cola:
<code>{pix_code}</code>

Toque no codigo acima para copiar

O que fazer:
1. Verifique se voce realmente pagou o PIX
2. Aguarde alguns minutos (pode levar ate 5 min)
3. Clique novamente em "Verificar Pagamento"

Se ja pagou, aguarde a confirmacao automatica!"""

                    buttons = [{
                        'text': 'Verificar Pagamento',
                        'callback_data': f'verify_{payment_id}'
                    }]

                    bot_manager.send_telegram_message(
                        token=token,
                        chat_id=str(chat_id),
                        message=pending_message.strip(),
                        buttons=buttons
                    )

                    logger.info(f"Cliente avisado que pagamento ainda esta pendente")

    except Exception as e:
        logger.error(f"Erro ao verificar pagamento: {e}")
        import traceback
        traceback.print_exc()
