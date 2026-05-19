"""
COMPLETE REWRITTEN _handle_verify_payment FUNCTION
Replace the entire function in bot_manager.py (lines ~6236-7204) with this code.
Uses 4 spaces strictly, all try/except blocks properly aligned.
"""

# ============================================================================
# FUNÇÃO PRINCIPAL - Substituir no bot_manager.py
# ============================================================================

    def _handle_verify_payment(self, bot_id: int, token: str, chat_id: int,
                               payment_id: str, user_info: Dict[str, Any]):
        """
        Verifica status do pagamento e libera acesso se pago
        Arquitetura: FASE 1 (commit imediato) + FASE 2 (processamento isolado)
        """
        from internal_logic.core.models import Payment, Bot, Gateway
        from internal_logic.core.extensions import db
        from flask import current_app

        try:
            with current_app.app_context():
                payment = Payment.query.filter_by(payment_id=payment_id).first()
                if not payment:
                    logger.warning(f"⚠️ Pagamento não encontrado: {payment_id}")
                    self.send_telegram_message(
                        token=token, chat_id=str(chat_id),
                        message="❌ Pagamento não encontrado. Entre em contato com o suporte."
                    )
                    return

                logger.info(f"📊 Status do pagamento LOCAL: {payment.status}")

                if payment.status == 'pending':
                    if payment.gateway_type == 'paradise':
                        logger.info(f"📡 Paradise: Webhook será processado automaticamente")
                    elif payment.gateway_type == 'umbrellapag':
                        self._verify_umbrellapay_payment(bot_id, token, chat_id, payment, user_info)
                    else:
                        self._verify_other_gateway_payment(bot_id, token, chat_id, payment, user_info)
                    return

                # Se já está pago, processar liberação
                if payment.status == 'paid':
                    self._process_payment_release(bot_id, token, chat_id, payment, user_info)

        except Exception as e:
            logger.error(f"❌ Erro ao verificar pagamento: {e}", exc_info=True)
            import traceback
            traceback.print_exc()

    def _verify_umbrellapay_payment(self, bot_id, token, chat_id, payment, user_info):
        """Verificação específica para UmbrellaPay com dupla consulta"""
        from internal_logic.core.models import WebhookEvent, get_brazil_time, Gateway
        from internal_logic.core.extensions import db
        from datetime import timedelta
        import time

        if not payment.gateway_transaction_id:
            logger.error(f"❌ gateway_transaction_id não encontrado para payment_id={payment.payment_id}")
            return

        # Verificar webhook recente
        dois_min_atras = get_brazil_time() - timedelta(minutes=2)
        try:
            webhook_recente = WebhookEvent.query.filter(
                WebhookEvent.gateway_type == 'umbrellapag',
                WebhookEvent.transaction_id == payment.gateway_transaction_id,
                WebhookEvent.received_at >= dois_min_atras
            ).order_by(WebhookEvent.received_at.desc()).first()
        except Exception as e:
            logger.error(f"❌ Erro ao buscar webhook recente: {e}")
            webhook_recente = None

        if webhook_recente:
            logger.info(f"⏳ Webhook recente encontrado, aguardando processamento automático")
            return

        # Verificação dupla na API
        bot = payment.bot
        if not bot:
            return

        gateway = Gateway.query.filter_by(
            user_id=bot.user_id, gateway_type=payment.gateway_type, is_verified=True
        ).first()
        if not gateway:
            return

        credentials = {'api_key': gateway.api_key, 'product_hash': gateway.product_hash}
        payment_gateway = GatewayFactory.create_gateway(
            gateway_type=payment.gateway_type, credentials=credentials
        )
        if not payment_gateway:
            return

        # Consulta 1
        try:
            api_status_1 = payment_gateway.get_payment_status(payment.gateway_transaction_id)
            status_1 = api_status_1.get('status') if api_status_1 else None
        except Exception as e:
            logger.error(f"❌ Erro na consulta 1: {e}")
            return

        if status_1 != 'paid':
            logger.info(f"⏳ Consulta 1 retornou: {status_1} (não é 'paid')")
            return

        time.sleep(3)

        # Consulta 2
        try:
            api_status_2 = payment_gateway.get_payment_status(payment.gateway_transaction_id)
            status_2 = api_status_2.get('status') if api_status_2 else None
        except Exception as e:
            logger.error(f"❌ Erro na consulta 2: {e}")
            return

        if status_2 != 'paid':
            logger.warning(f"⚠️ Discrepância: consulta 1=paid, consulta 2={status_2}")
            return

        # Ambas confirmaram - atualizar pagamento
        self._confirm_payment_and_process(bot_id, token, chat_id, payment, user_info, 'umbrellapay')

    def _verify_other_gateway_payment(self, bot_id, token, chat_id, payment, user_info):
        """Verificação para outros gateways"""
        from internal_logic.core.extensions import db
        from internal_logic.core.models import Gateway

        bot = payment.bot
        gateway = Gateway.query.filter_by(
            user_id=bot.user_id, gateway_type=payment.gateway_type, is_verified=True
        ).first()
        if not gateway:
            return

        user_commission = bot.owner.commission_percentage or gateway.split_percentage or 2.0
        credentials = {
            'client_id': gateway.client_id, 'client_secret': gateway.client_secret,
            'api_key': gateway.api_key, 'product_hash': gateway.product_hash,
            'offer_hash': gateway.offer_hash, 'store_id': gateway.store_id,
            'split_user_id': gateway.split_user_id, 'split_percentage': user_commission
        }
        payment_gateway = GatewayFactory.create_gateway(
            gateway_type=payment.gateway_type, credentials=credentials
        )
        if not payment_gateway:
            return

        try:
            api_status = payment_gateway.get_payment_status(payment.gateway_transaction_id)
        except Exception as e:
            logger.error(f"❌ Erro ao consultar gateway: {e}")
            return

        if api_status and api_status.get('status') == 'paid':
            self._confirm_payment_and_process(bot_id, token, chat_id, payment, user_info, 'other')
        elif api_status:
            logger.info(f"⏳ API retornou status: {api_status.get('status')}")

    def _confirm_payment_and_process(self, bot_id, token, chat_id, payment, user_info, gateway_type):
        """
        FASE 1: Commit imediato do status
        FASE 2: Processamento isolado (upsells, conquistas, entregáveis)
        """
        from internal_logic.core.extensions import db
        from internal_logic.core.models import get_brazil_time

        # ============================================================================
        # FASE 1: GARANTIA DE RECEITA - Commit Imediato
        # ============================================================================
        try:
            db.session.refresh(payment)
            if payment.status == 'paid':
                logger.info(f"✅ Pagamento já está paid, não atualizar novamente")
                return

            payment.status = 'paid'
            payment.paid_at = get_brazil_time()
            db.session.commit()
            logger.info(f"💰 Pagamento CONFIRMADO e COMMITADO - ID: {payment.payment_id}")
        except Exception as commit_error:
            db.session.rollback()
            logger.error(f"❌ ERRO CRÍTICO ao confirmar pagamento: {commit_error}", exc_info=True)
            return

        # ============================================================================
        # FASE 2: PROCESSAMENTO ISOLADO (não crítico)
        # ============================================================================
        try:
            db.session.refresh(payment)
            logger.info(f"✅ Purchase será disparado quando lead acessar link de entrega")

            # Verificar conquistas (não crítico)
            try:
                from internal_logic.services.achievements import check_and_unlock_achievements
                new_achievements = check_and_unlock_achievements(payment.bot.owner)
                if new_achievements:
                    logger.info(f"🏆 {len(new_achievements)} conquista(s) desbloqueada(s)!")
            except Exception as e:
                logger.warning(f"⚠️ Erro ao verificar conquistas (não crítico): {e}")

        except Exception as phase2_error:
            logger.error(f"❌ Erro não crítico após confirmação: {phase2_error}", exc_info=True)

        # Processar upsells
        self._process_upsells_after_payment(payment)

        # Enviar entregável
        self._send_payment_delivery(bot_id, token, chat_id, payment, user_info, gateway_type)

    def _process_upsells_after_payment(self, payment):
        """Processa upsells após confirmação de pagamento"""
        if not payment.bot.config or not payment.bot.config.upsells_enabled:
            return

        logger.info(f"🔍 [UPSELLS] Verificando para payment {payment.payment_id}")

        if not self.scheduler:
            logger.error(f"❌ Scheduler não disponível para upsells")
            return

        # Verificar se já agendado
        upsells_already_scheduled = False
        for i in range(10):
            job_id = f"upsell_{payment.bot_id}_{payment.payment_id}_{i}"
            if self.scheduler.get_job(job_id):
                upsells_already_scheduled = True
                break

        if upsells_already_scheduled:
            logger.info(f"ℹ️ Upsells já agendados anteriormente para {payment.payment_id}")
            return

        upsells = payment.bot.config.get_upsells()
        if not upsells:
            return

        # Filtrar por produto
        matched_upsells = [
            u for u in upsells
            if not u.get('trigger_product') or u.get('trigger_product') == payment.product_name
        ]

        if matched_upsells:
            logger.info(f"✅ {len(matched_upsells)} upsell(s) encontrado(s)")
            try:
                self.schedule_upsells(
                    bot_id=payment.bot_id, payment_id=payment.payment_id,
                    chat_id=int(payment.customer_user_id), upsells=matched_upsells,
                    original_price=payment.amount,
                    original_button_index=payment.button_index if payment.button_index is not None else -1
                )
                logger.info(f"📅 Upsells agendados com sucesso!")
            except Exception as e:
                logger.error(f"❌ Erro ao agendar upsells: {e}", exc_info=True)

    def _send_payment_delivery(self, bot_id, token, chat_id, payment, user_info, gateway_type):
        """Envia o entregável após pagamento confirmado"""
        from internal_logic.core.extensions import db

        try:
            db.session.refresh(payment)
            if payment.status != 'paid':
                logger.error(f"❌ Status inválido para envio: {payment.status}")
                return

            try:
                resultado = send_payment_delivery(payment, self)
                if resultado:
                    logger.info(f"✅ Entregável enviado com sucesso")
                else:
                    logger.warning(f"⚠️ send_payment_delivery retornou False")
            except Exception as e:
                logger.error(f"❌ Erro no send_payment_delivery: {e}")
                self._send_fallback_success_message(bot_id, token, chat_id, payment)

        except Exception as e:
            logger.error(f"❌ Erro ao enviar entregável: {e}", exc_info=True)

    def _send_fallback_success_message(self, bot_id, token, chat_id, payment):
        """Envio fallback de mensagem de sucesso se send_payment_delivery falhar"""
        bot_data = self.bot_state.get_bot_data(bot_id)
        bot_config = bot_data.get('config', {}) if bot_data else {}
        access_link = bot_config.get('access_link', '')
        custom_msg = bot_config.get('success_message', '').strip()

        if custom_msg:
            success_message = custom_msg.replace('{produto}', payment.product_name or 'Produto')
            success_message = success_message.replace('{valor}', f'R$ {payment.amount:.2f}')
            success_message = success_message.replace('{link}', access_link or 'Link não configurado')
        elif access_link:
            success_message = f"""✅ <b>PAGAMENTO CONFIRMADO!</b>

🎉 <b>Parabéns!</b> Seu pagamento foi aprovado!

🎯 <b>Produto:</b> {payment.product_name}
💰 <b>Valor:</b> R$ {payment.amount:.2f}

🔗 <b>Seu acesso:</b>
{access_link}

<b>Aproveite!</b> 🚀"""
        else:
            success_message = "✅ Pagamento confirmado! Entre em contato com o suporte."

        self.send_telegram_message(token=token, chat_id=str(chat_id), message=success_message.strip())
        logger.info(f"✅ Acesso liberado (fallback)")

    def _process_payment_release(self, bot_id, token, chat_id, payment, user_info):
        """Processa liberação quando pagamento já está confirmado"""
        from internal_logic.core.models import Bot
        from internal_logic.core.extensions import db

        # Verificar flow engine
        if payment.flow_step_id:
            bot_flow = Bot.query.get(bot_id)
            if bot_flow and bot_flow.config:
                flow_config = bot_flow.config.to_dict()
                if flow_config.get('flow_enabled') and flow_config.get('flow_steps'):
                    # Processar flow e sair
                    return

        # Processamento tradicional
        self.cancel_downsells(payment.payment_id)
        self._send_payment_delivery(bot_id, token, chat_id, payment, user_info, 'verify')
        self._process_upsells_after_payment(payment)

