"""
Payment Generator Service
=========================
Servico responsavel pela geracao de pagamentos PIX via gateway.
Extraido do BotManager para isolamento e testabilidade.

Fluxo:
1. Tenta PaymentService.generate_pix() (nova arquitetura)
2. Se falha, executa logica legada completa (fallback)
"""

import json
import logging
import requests
from typing import Optional, Dict, Any

logger = logging.getLogger(__name__)


def generate_pix_payment(bot_id: int, amount: float, description: str,
                         customer_name: str, customer_username: str, customer_user_id: str,
                         order_bump_shown: bool = False, order_bump_accepted: bool = False,
                         order_bump_value: float = 0.0, is_downsell: bool = False,
                         downsell_index: int = None,
                         is_upsell: bool = False,
                         upsell_index: int = None,
                         is_remarketing: bool = False,
                         remarketing_campaign_id: int = None,
                         button_index: int = None,
                         button_config: dict = None) -> Optional[Dict[str, Any]]:
    """Gera pagamento PIX via gateway configurado

    Args:
        bot_id: ID do bot
        amount: Valor do pagamento
        description: Descricao do produto
        customer_name: Nome do cliente
        customer_username: Username do Telegram
        customer_user_id: ID do usuario no Telegram
    """
    try:
        from internal_logic.core.extensions import db
        from internal_logic.core.models import Bot, Gateway

        bot = Bot.query.get(bot_id)
        if not bot:
            logger.error(f"Bot {bot_id} nao encontrado para geracao de PIX")
            return None

        gateway = Gateway.query.filter_by(
            user_id=bot.user_id,
            is_active=True,
            is_verified=True
        ).first()

        if not gateway:
            logger.error(f"Nenhum gateway ativo encontrado para usuario {bot.user_id}")
            return None

        from internal_logic.services.payment_service import get_payment_service
        payment_service = get_payment_service(db.session)

        response = payment_service.generate_pix(
            bot_id=bot_id,
            gateway_id=gateway.id,
            amount=amount,
            description=description,
            customer_name=customer_name or 'Cliente',
            customer_email=f"{customer_username}@telegram.user" if customer_username else f"user{customer_user_id}@telegram.user",
            customer_cpf=customer_user_id,
            external_id=customer_user_id,
            order_bump_shown=order_bump_shown,
            order_bump_accepted=order_bump_accepted,
            order_bump_value=order_bump_value,
            is_downsell=is_downsell,
            downsell_index=downsell_index,
            is_upsell=is_upsell,
            upsell_index=upsell_index,
            is_remarketing=is_remarketing,
            remarketing_campaign_id=remarketing_campaign_id,
            button_index=button_index,
            button_config=json.dumps(button_config) if button_config else None
        )

        if response.success:
            logger.info(f"PIX gerado via PaymentService - Transaction ID: {response.transaction_id}")
            payment_ref = response.reference or str(customer_user_id)
            transaction_hash = None
            try:
                if isinstance(response.raw_response, dict):
                    transaction_hash = response.raw_response.get('transaction_hash') or response.raw_response.get('gateway_transaction_hash')
            except Exception:
                transaction_hash = None
            return {
                'pix_code': response.qr_code,
                'pix_code_base64': None,
                'qr_code_url': response.qr_code_url,
                'transaction_id': response.transaction_id,
                'transaction_hash': transaction_hash,
                'payment_id': payment_ref,
                'expires_at': None,
                'status': response.status
            }
        else:
            logger.error(f"Falha ao gerar PIX via PaymentService: {response.error_message}")
            return None  # Não cair no fallback legado — gateway já rejeitou os dados
    except Exception as e:
        logger.error(f"Erro na integracao PaymentService: {e}")
        logger.info("Fallback para logica legada de PIX...")

    if not customer_user_id or customer_user_id.strip() == "":
        logger.error(f"ERRO CRITICO: customer_user_id vazio ao gerar PIX! Bot: {bot_id}, Valor: R$ {amount:.2f}")
        logger.error(f"   Isso quebra tracking Meta Pixel - Purchase nao sera atribuido a campanha!")
        logger.error(f"   customer_name: {customer_name}, customer_username: {customer_username}")
        return None

    fbc = None
    fbp = None
    fbclid = None
    pageview_event_id = None
    redirect_id = None
    meta_pixel_id = None
    pool_id_from_tracking = None
    tracking_token = None

    lock_acquired = False
    lock_key = None
    redis_conn = None

    try:
        from internal_logic.core.models import Bot, Gateway, Payment
        from internal_logic.core.extensions import db
        from flask import current_app
        from sqlalchemy.exc import IntegrityError

        with current_app.app_context():
            bot = db.session.get(Bot, bot_id)
            if not bot:
                logger.error(f"Bot {bot_id} nao encontrado")
                return None
            bot = db.session.merge(bot)

            gateway = Gateway.query.filter_by(
                user_id=bot.user_id,
                is_active=True,
                is_verified=True
            ).first()

            if not gateway:
                logger.error(f"Nenhum gateway ativo encontrado para usuario {bot.user_id} | Bot: {bot_id}")
                logger.error(f"   Verifique se ha um gateway configurado e ativo em /settings")
                return None

            logger.info(f"Gateway: {gateway.gateway_type.upper()} | Gateway ID: {gateway.id} | User ID: {bot.user_id}")

            def normalize_product_name(name):
                if not name:
                    return ''
                import re
                normalized = re.sub(r'[^\w\s]', '', name)
                return normalized.lower().strip()

            normalized_description = normalize_product_name(description)

            all_pending = Payment.query.filter_by(
                bot_id=bot_id,
                customer_user_id=customer_user_id,
                status='pending'
            ).all()

            pending_same_product = None
            for p in all_pending:
                if normalize_product_name(p.product_name) == normalized_description:
                    pending_same_product = p
                    break

            if pending_same_product:
                try:
                    from internal_logic.core.models import get_brazil_time
                    age_seconds = (get_brazil_time() - pending_same_product.created_at).total_seconds() if pending_same_product.created_at else 999999
                except Exception:
                    age_seconds = 999999
                amount_matches = abs(float(pending_same_product.amount) - float(amount)) < 0.01
                if pending_same_product.status == 'pending' and age_seconds <= 300 and amount_matches:
                    if gateway.gateway_type == 'paradise':
                        logger.warning(f"Paradise nao permite reutilizar PIX - gerando NOVO para evitar IDs duplicados.")
                    else:
                        logger.warning(f"Ja existe PIX pendente (<=5min) e valor igual para {description}. Reutilizando.")
                        pix_result = {
                            'pix_code': pending_same_product.product_description,
                            'pix_code_base64': None,
                            'qr_code_url': None,
                            'transaction_id': pending_same_product.gateway_transaction_id,
                            'transaction_hash': pending_same_product.gateway_transaction_hash,
                            'payment_id': pending_same_product.payment_id,
                            'expires_at': None
                        }
                        logger.info(f"PIX reutilizado: {pending_same_product.payment_id} | idade={int(age_seconds)}s | valor_ok={amount_matches}")
                        return pix_result
                else:
                    logger.info(
                        f"NAO reutilizar PIX existente: status={pending_same_product.status}, idade={int(age_seconds)}s, valor_ok={amount_matches}. Gerando NOVO PIX."
                    )

            last_pix = Payment.query.filter_by(
                bot_id=bot_id,
                customer_user_id=customer_user_id
            ).order_by(Payment.id.desc()).first()

            if last_pix and last_pix.status == 'pending':
                from internal_logic.core.models import get_brazil_time
                time_since = (get_brazil_time() - last_pix.created_at).total_seconds()
                if time_since < 120:
                    wait_time = 120 - int(time_since)
                    wait_minutes = wait_time // 60
                    wait_seconds = wait_time % 60

                    if wait_minutes > 0:
                        time_msg = f"{wait_minutes} minuto{'s' if wait_minutes > 1 else ''} e {wait_seconds} segundo{'s' if wait_seconds > 1 else ''}"
                    else:
                        time_msg = f"{wait_seconds} segundo{'s' if wait_seconds > 1 else ''}"

                    logger.warning(f"Rate limit: cliente deve aguardar {time_msg} para gerar novo PIX")
                    return {'rate_limit': True, 'wait_time': time_msg}

            import uuid
            payment_id = f"BOT{bot_id}_{int(time.time())}_{uuid.uuid4().hex[:8]}"

            from internal_logic.core.models import User
            owner_commission = None
            if bot and getattr(bot, 'user_id', None):
                current_owner = db.session.get(User, bot.user_id)
                if current_owner:
                    owner_commission = current_owner.commission_percentage
            user_commission = owner_commission or gateway.split_percentage or 2.0

            try:
                api_key = gateway.api_key
                if gateway.gateway_type == 'wiinpay':
                    if api_key:
                        logger.info(f"[WiinPay] api_key descriptografada com sucesso (len={len(api_key)})")
                    else:
                        logger.warning(f"[WiinPay] api_key retornou None (campo interno existe: {bool(gateway._api_key)})")
            except Exception as decrypt_error:
                logger.error(f"ERRO CRITICO ao acessar gateway.api_key (gateway {gateway.id}): {decrypt_error}")
                logger.error(f"   Tipo do gateway: {gateway.gateway_type}")
                logger.error(f"   Isso indica que a descriptografia esta FALHANDO com excecao")
                api_key = None
                if gateway.gateway_type == 'wiinpay':
                    logger.error(f"[WiinPay] ERRO CRITICO na descriptografia da api_key!")
                    logger.error(f"   Gateway ID: {gateway.id} | User ID: {gateway.user_id}")
                    logger.error(f"   Campo interno existe: {bool(gateway._api_key)}")
                    logger.error(f"   Excecao: {decrypt_error}")
                    logger.error(f"   SOLUCAO: Reconfigure o gateway WiinPay com a api_key correta em /settings")

            try:
                client_secret = gateway.client_secret
            except Exception as decrypt_error:
                logger.error(f"ERRO CRITICO ao acessar gateway.client_secret (gateway {gateway.id}): {decrypt_error}")
                client_secret = None

            try:
                product_hash = gateway.product_hash
            except Exception as decrypt_error:
                logger.error(f"ERRO CRITICO ao acessar gateway.product_hash (gateway {gateway.id}): {decrypt_error}")
                product_hash = None

            try:
                split_user_id = gateway.split_user_id
            except Exception as decrypt_error:
                logger.error(f"ERRO CRITICO ao acessar gateway.split_user_id (gateway {gateway.id}): {decrypt_error}")
                split_user_id = None

            if gateway.gateway_type == 'wiinpay':
                platform_split_id = '68ffcc91e23263e0a01fffa4'
                old_id = '6877edeba3c39f8451ba5bdd'

                try:
                    import jwt
                    import json
                    decoded = jwt.decode(api_key, options={"verify_signature": False}) if api_key else {}
                    api_key_user_id = decoded.get('userId') or decoded.get('user_id') or ''
                    logger.info(f"[WiinPay] user_id da api_key (JWT): {api_key_user_id}")
                except Exception as jwt_error:
                    api_key_user_id = None
                    logger.warning(f"[WiinPay] Nao foi possivel extrair user_id do JWT: {jwt_error}")

                if not split_user_id or split_user_id == old_id or split_user_id.strip() == '':
                    logger.info(f"[WiinPay] split_user_id vazio/antigo, usando ID da plataforma: {platform_split_id}")
                    split_user_id = platform_split_id
                elif split_user_id == api_key_user_id:
                    logger.warning(f"[WiinPay] split_user_id e o mesmo da conta de recebimento ({api_key_user_id})!")
                    logger.warning(f"   Isso causara erro 422. Forcando ID da plataforma: {platform_split_id}")
                    split_user_id = platform_split_id
                elif split_user_id != platform_split_id:
                    logger.warning(f"[WiinPay] split_user_id diferente do ID da plataforma: {split_user_id}")
                    logger.warning(f"   Esperado: {platform_split_id} | Usando: {split_user_id}")
                    logger.warning(f"   Forcando ID da plataforma para garantir split correto")
                    split_user_id = platform_split_id
                else:
                    logger.info(f"[WiinPay] split_user_id correto (ID da plataforma): {split_user_id}")

            encryption_error_detected = False

            if gateway._api_key and not api_key:
                logger.error(f"CRITICO: Erro ao descriptografar api_key do gateway {gateway.id}")
                logger.error(f"   Campo interno existe: {gateway._api_key[:30] if gateway._api_key else 'None'}...")
                logger.error(f"   Property retornou: {api_key}")
                logger.error(f"   POSSIVEL CAUSA: ENCRYPTION_KEY foi alterada apos salvar credenciais")
                logger.error(f"   SOLUCAO: Reconfigure o gateway {gateway.gateway_type} com as credenciais corretas")
                logger.error(f"   Gateway ID: {gateway.id} | Tipo: {gateway.gateway_type} | User: {gateway.user_id}")
                encryption_error_detected = True

            if gateway._client_secret and not client_secret:
                logger.error(f"CRITICO: Erro ao descriptografar client_secret do gateway {gateway.id}")
                logger.error(f"   Campo interno existe: {gateway._client_secret[:30] if gateway._client_secret else 'None'}...")
                logger.error(f"   Property retornou: {client_secret}")
                logger.error(f"   POSSIVEL CAUSA: ENCRYPTION_KEY foi alterada apos salvar credenciais")
                encryption_error_detected = True

            if gateway._product_hash and not product_hash:
                logger.error(f"CRITICO: Erro ao descriptografar product_hash do gateway {gateway.id}")
                logger.error(f"   Campo interno existe: {gateway._product_hash[:30] if gateway._product_hash else 'None'}...")
                logger.error(f"   Property retornou: {product_hash}")
                logger.error(f"   POSSIVEL CAUSA: ENCRYPTION_KEY foi alterada apos salvar credenciais")
                encryption_error_detected = True

            if gateway._split_user_id and not split_user_id and gateway.gateway_type == 'wiinpay':
                logger.warning(f"WiinPay: split_user_id nao descriptografado (pode ser normal se nao configurado)")

            if encryption_error_detected:
                logger.error(f"ERRO DE DESCRIPTOGRAFIA DETECTADO - Payment NAO sera criado")
                logger.error(f"   ACAO NECESSARIA: Reconfigure o gateway {gateway.gateway_type} (ID: {gateway.id}) em /settings")
                return None

            credentials = {
                'client_id': gateway.client_id,
                'client_secret': client_secret,
                'api_key': api_key,
                'api_token': api_key if gateway.gateway_type == 'atomopay' else None,
                'company_id': gateway.client_id if gateway.gateway_type == 'babylon' else None,
                'product_hash': product_hash,
                'offer_hash': gateway.offer_hash,
                'store_id': gateway.store_id,
                'split_user_id': split_user_id,
                'split_percentage': user_commission
            }

            if gateway.gateway_type == 'paradise':
                if not api_key:
                    logger.error(f"Paradise: api_key ausente ou nao descriptografado")
                    return None
                if not product_hash:
                    logger.error(f"Paradise: product_hash ausente ou nao descriptografado")
                    return None
            elif gateway.gateway_type == 'atomopay':
                if not api_key:
                    logger.error(f"Atomo Pay: api_token (api_key) ausente ou nao descriptografado")
                    logger.error(f"   gateway.id: {gateway.id}")
                    return None
                else:
                    logger.debug(f"Atomo Pay: api_token presente ({len(api_key)} caracteres)")
            elif gateway.gateway_type == 'syncpay':
                if not client_secret:
                    logger.error(f"SyncPay: client_secret ausente ou nao descriptografado")
                    logger.error(f"   Gateway ID: {gateway.id} | User: {gateway.user_id}")
                    if gateway._client_secret:
                        logger.error(f"   Campo interno existe mas descriptografia falhou!")
                        logger.error(f"   POSSIVEL CAUSA: ENCRYPTION_KEY foi alterada apos salvar credenciais")
                    return None
                if not gateway.client_id:
                    logger.error(f"SyncPay: client_id ausente")
                    logger.error(f"   Gateway ID: {gateway.id} | User: {gateway.user_id}")
                    return None
            elif gateway.gateway_type in ['pushynpay', 'wiinpay']:
                if not api_key:
                    logger.error(f"{gateway.gateway_type.upper()}: api_key ausente ou nao descriptografado")
                    logger.error(f"   Gateway ID: {gateway.id} | User: {gateway.user_id} | Tipo: {gateway.gateway_type}")
                    if gateway._api_key:
                        logger.error(f"   Campo interno existe mas descriptografia falhou!")
                        logger.error(f"   Campo interno (primeiros 30 chars): {gateway._api_key[:30] if gateway._api_key else 'None'}...")
                        logger.error(f"   POSSIVEL CAUSA: ENCRYPTION_KEY foi alterada apos salvar credenciais")
                        logger.error(f"   SOLUCAO CRITICA: Reconfigure o gateway {gateway.gateway_type.upper()} (ID: {gateway.id}) em /settings")
                    else:
                        logger.error(f"   Campo interno (_api_key) tambem esta vazio - gateway nao foi configurado corretamente")
                        logger.error(f"   SOLUCAO: Configure o gateway {gateway.gateway_type.upper()} em /settings")
                    return None
            elif gateway.gateway_type == 'babylon':
                if not api_key:
                    logger.error(f"BABYLON: api_key (Secret Key) ausente ou nao descriptografado")
                    logger.error(f"   Gateway ID: {gateway.id} | User: {gateway.user_id}")
                    if gateway._api_key:
                        logger.error(f"   Campo interno existe mas descriptografia falhou!")
                        logger.error(f"   POSSIVEL CAUSA: ENCRYPTION_KEY foi alterada apos salvar credenciais")
                        logger.error(f"   SOLUCAO: Reconfigure o gateway Babylon (ID: {gateway.id}) em /settings")
                    return None
                if not gateway.client_id:
                    logger.error(f"BABYLON: client_id (Company ID) ausente")
                    logger.error(f"   Gateway ID: {gateway.id} | User: {gateway.user_id}")
                    logger.error(f"   SOLUCAO: Configure o Company ID no gateway Babylon em /settings")
                    return None

            if user_commission < 2.0:
                logger.info(f"TAXA PREMIUM aplicada: {user_commission}% (User ID {bot.user_id})")

            original_product_hash = gateway.product_hash

            logger.info(f"Criando gateway {gateway.gateway_type} com credenciais...")

            if gateway.gateway_type == 'wiinpay':
                logger.info(f"[WiinPay Debug] Criando gateway com:")
                logger.info(f"   - api_key presente: {bool(api_key)}")
                logger.info(f"   - api_key length: {len(api_key) if api_key else 0}")
                logger.info(f"   - split_user_id: {split_user_id}")
                logger.info(f"   - split_percentage: {user_commission}%")
                logger.info(f"   - credentials keys: {list(credentials.keys())}")

            from gateways import GatewayFactory
            payment_gateway = GatewayFactory.create_gateway(
                gateway_type=gateway.gateway_type,
                credentials=credentials
            )

            if not payment_gateway:
                logger.error(f"Erro ao criar gateway {gateway.gateway_type}")
                if gateway.gateway_type == 'wiinpay':
                    logger.error(f"   WIINPAY: Gateway nao foi criado - verifique:")
                    logger.error(f"   1. api_key foi descriptografada corretamente: {bool(api_key)}")
                    logger.error(f"   2. Gateway esta ativo e verificado: is_active={gateway.is_active}, is_verified={gateway.is_verified}")
                    logger.error(f"   3. Verifique logs anteriores para erros de descriptografia")
                return None

            logger.info(f"Gateway {gateway.gateway_type} criado com sucesso!")

            if gateway.gateway_type == 'wiinpay' and amount < 3.0:
                logger.error(f"WIINPAY: Valor minimo R$ 3,00 | Produto: R$ {amount:.2f}")
                logger.error(f"   SOLUCAO: Use Paradise, Pushyn ou SyncPay para valores < R$ 3,00")
                logger.error(f"   Ou aumente o preco do produto para minimo R$ 3,00")
                return None

            logger.info(f"Gerando PIX: R$ {amount:.2f} | Descricao: {description}")
            customer_data = {
                'name': customer_name or 'Cliente',
                'email': f"{customer_username}@telegram.user" if customer_username else f"user{customer_user_id}@telegram.user",
                'phone': customer_user_id,
            }
            # document NÃO é enviado — SigiloPayGateway já sorteia CPF do CSV KYC internamente
            pix_result = payment_gateway.generate_pix(
                amount=amount,
                description=description,
                payment_id=payment_id,
                customer_data=customer_data
            )

            logger.info(f"Resultado do PIX: {pix_result}")

            if not pix_result:
                if gateway.gateway_type == 'wiinpay':
                    logger.error(f"WIINPAY: generate_pix retornou None!")
                    logger.error(f"   Bot ID: {bot_id} | Gateway ID: {gateway.id} | User ID: {bot.user_id}")
                    logger.error(f"   Valor: R$ {amount:.2f} | Descricao: {description}")
                    logger.error(f"   api_key presente: {bool(api_key)}")
                    logger.error(f"   split_user_id: {split_user_id}")
                    logger.error(f"   split_percentage: {user_commission}%")

                if 'payment' in locals() and payment:
                    try:
                        logger.warning(f"[GATEWAY RETORNOU NONE] Gateway {gateway.gateway_type} retornou None")
                        logger.warning(f"   Bot: {bot_id}, Valor: R$ {amount:.2f}, Payment ID: {payment.payment_id}")
                        logger.warning(f"   Payment sera marcado como 'pending_verification' para nao perder venda")

                        payment.status = 'pending_verification'
                        payment.gateway_transaction_id = None
                        payment.product_description = None
                        db.session.commit()

                        logger.warning(f"Payment {payment.id} marcado como 'pending_verification' (gateway retornou None)")
                        return {'status': 'pending_verification', 'payment_id': payment.payment_id, 'error': 'Gateway retornou None'}
                    except Exception as commit_error:
                        logger.error(f"Erro ao commitar Payment apos gateway retornar None: {commit_error}", exc_info=True)
                        db.session.rollback()
                        return None
                else:
                    logger.error(f"Gateway retornou None e Payment nao foi criado")
                    return None

            if pix_result:
                transaction_status = pix_result.get('status')
                is_refused = transaction_status == 'refused' or pix_result.get('error')

                if is_refused:
                    logger.warning(f"Transacao RECUSADA pelo gateway - criando payment com status 'failed' para webhook")
                else:
                    logger.info(f"PIX gerado com sucesso pelo gateway!")

                from internal_logic.core.models import BotUser
                bot_user = BotUser.query.filter_by(
                    bot_id=bot_id,
                    telegram_user_id=customer_user_id
                ).first()
                if not bot_user:
                    try:
                        bot_user_int = int(customer_user_id)
                    except (TypeError, ValueError):
                        bot_user_int = None
                    if bot_user_int is not None:
                        bot_user = BotUser.query.filter_by(
                            bot_id=bot_id,
                            telegram_user_id=str(bot_user_int)
                        ).first()

                from utils.tracking_service import TrackingServiceV4
                tracking_service = TrackingServiceV4()

                fbclid = getattr(bot_user, 'fbclid', None) if bot_user else None
                utm_source = getattr(bot_user, 'utm_source', None) if bot_user else None
                utm_medium = getattr(bot_user, 'utm_medium', None) if bot_user else None
                utm_campaign = getattr(bot_user, 'utm_campaign', None) if bot_user else None
                utm_content = getattr(bot_user, 'utm_content', None) if bot_user else None
                utm_term = getattr(bot_user, 'utm_term', None) if bot_user else None

                redis_tracking_payload: Dict[str, Any] = {}
                tracking_token = None

                # ├─ PRIORIDADE 1: tracking_session_id do BotUser (vem do /go/<slug>)
                if bot_user and bot_user.tracking_session_id:
                    candidate = bot_user.tracking_session_id
                    norm = candidate.replace('-', '').lower()
                    if len(norm) == 32 and all(c in '0123456789abcdef' for c in norm):
                        tracking_token = candidate
                        logger.info(f"[TRACKING] Token do bot_user.tracking_session_id: {tracking_token[:20]}...")

                # ├─ PRIORIDADE 2: Redis indices (fallback para leads sem redirect)
                if not tracking_token and customer_user_id:
                    try:
                        cached_token = tracking_service.redis.get(f"tracking:last_token:user:{customer_user_id}")
                        if cached_token:
                            norm = cached_token.replace('-', '').lower()
                            if len(norm) == 32 and all(c in '0123456789abcdef' for c in norm):
                                tracking_token = cached_token
                                logger.info(f"[TRACKING] Token de tracking:last_token:user: {tracking_token[:20]}...")
                    except Exception:
                        logger.exception("[TRACKING] Erro tracking:last_token:user")

                if not tracking_token and customer_user_id:
                    try:
                        raw = tracking_service.redis.get(f"tracking:chat:{customer_user_id}")
                        if raw:
                            chat_data = json.loads(raw)
                            t = chat_data.get("tracking_token")
                            if t:
                                norm = t.replace('-', '').lower()
                                if len(norm) == 32 and all(c in '0123456789abcdef' for c in norm):
                                    tracking_token = t
                                    redis_tracking_payload = chat_data
                                    logger.info(f"[TRACKING] Token de tracking:chat: {tracking_token[:20]}...")
                    except Exception:
                        logger.exception("[TRACKING] Erro tracking:chat")

                # ├─ PRIORIDADE 3.5: Fallback token legado (tracking_xxx) — mesmo comportamento do código antigo
                if not tracking_token and bot_user and bot_user.tracking_session_id:
                    candidate = bot_user.tracking_session_id
                    if candidate.startswith('tracking_'):
                        tracking_token = candidate
                        logger.warning(f"[TOKEN LEGADO] Fallback para token legado: {candidate[:30]}...")

                # ├─ Se achou token novo e bot_user tem session_id diferente → atualizar
                if tracking_token and bot_user and bot_user.tracking_session_id != tracking_token:
                    bot_user.tracking_session_id = tracking_token
                    logger.info(f"[TRACKING] bot_user.tracking_session_id atualizado: {tracking_token[:20]}...")

                # ── Recuperar payload do Redis ─────────────────────────────
                tracking_data_v4: Dict[str, Any] = redis_tracking_payload if isinstance(redis_tracking_payload, dict) else {}
                if tracking_token and not tracking_data_v4:
                    recovered = tracking_service.recover_tracking_data(tracking_token) or {}
                    if recovered:
                        tracking_data_v4 = recovered
                        logger.info(f"[TRACKING] Payload Redis recuperado | "
                                     f"fbp={'ok' if recovered.get('fbp') else 'missing'} "
                                     f"fbc={'ok' if recovered.get('fbc') else 'missing'} "
                                     f"pageview_event_id={'ok' if recovered.get('pageview_event_id') else 'missing'}")

                # ── Extrair campos do tracking_data ────────────────────────
                if tracking_data_v4:
                    fbc = tracking_data_v4.get("fbc") or fbc
                    fbp = tracking_data_v4.get("fbp") or fbp
                    fbclid = tracking_data_v4.get("fbclid") or fbclid
                    pageview_event_id = tracking_data_v4.get("pageview_event_id") or pageview_event_id

                external_ids = tracking_service.build_external_id_array(
                    fbclid=fbclid,
                    telegram_user_id=str(customer_user_id),
                    email=getattr(bot_user, 'email', None) if bot_user else None,
                    phone=getattr(bot_user, 'phone', None) if bot_user else None
                )

                tracking_update_payload = {
                    "tracking_token": tracking_token,
                    "bot_id": bot_id,
                    "customer_user_id": customer_user_id,
                    "fbclid": fbclid,
                    "fbp": fbp,
                    **({"fbc": fbc} if fbc is not None else {}),
                    "pageview_event_id": pageview_event_id,
                    "pageview_ts": tracking_data_v4.get('pageview_ts'),
                    "grim": tracking_data_v4.get('grim'),
                    "utm_source": utm_source,
                    "utm_medium": utm_medium,
                    "utm_campaign": utm_campaign,
                    "utm_content": utm_content,
                    "utm_term": utm_term,
                    "external_ids": external_ids,
                    "updated_from": "generate_pix_payment",
                }
                tracking_service.save_tracking_token(tracking_token, {k: v for k, v in tracking_update_payload.items() if v})

                logger.info("Tracking token pronto: %s | fbp=%s | fbc=%s | pageview=%s", tracking_token, 'ok' if fbp else 'missing', 'ok' if fbc else 'missing', 'ok' if pageview_event_id else 'missing')

                payment_status = 'failed' if is_refused else 'pending'

                gateway_transaction_id = (
                    pix_result.get('transaction_id') or
                    pix_result.get('transaction_hash') or
                    None
                )

                gateway_hash = pix_result.get('gateway_hash') or pix_result.get('transaction_hash')

                reference = pix_result.get('reference')

                if gateway.gateway_type in ['atomopay', 'umbrellapag'] and payment_gateway:
                    current_product_hash = getattr(payment_gateway, 'product_hash', None)
                    if current_product_hash and current_product_hash != original_product_hash:
                        gateway.product_hash = current_product_hash
                        logger.info(f"Product Hash criado dinamicamente e salvo no Gateway: {current_product_hash[:12]}...")

                producer_hash = pix_result.get('producer_hash')
                if producer_hash and gateway.gateway_type == 'atomopay':
                    if not gateway.producer_hash:
                        gateway.producer_hash = producer_hash
                        logger.info(f"Producer Hash salvo no Gateway: {producer_hash[:12]}...")

                if gateway.gateway_type in ['atomopay', 'umbrellapag']:
                    db.session.commit()
                    if gateway.gateway_type == 'atomopay':
                        logger.info(f"Gateway atualizado (product_hash, producer_hash)")
                    else:
                        logger.info(f"Gateway atualizado (product_hash)")

                logger.info(f"Salvando Payment com dados do gateway:")
                logger.info(f"   payment_id: {payment_id}")
                logger.info(f"   gateway_transaction_id: {gateway_transaction_id}")
                logger.info(f"   gateway_hash: {gateway_hash}")
                logger.info(f"   producer_hash: {producer_hash}")
                logger.info(f"   reference: {reference}")

                if not tracking_token:
                    transaction_id_from_result = pix_result.get('transaction_id') if pix_result else None
                    if pix_result and transaction_id_from_result:
                        logger.warning(f"[TOKEN AUSENTE] tracking_token AUSENTE - PIX ja foi gerado (transaction_id: {transaction_id_from_result})")
                        logger.warning(f"   BotUser {bot_user.id if bot_user else 'N/A'} nao tem tracking_session_id")
                        logger.warning(f"   Payment sera criado mesmo sem tracking_token para evitar perder venda")
                        logger.warning(f"   Meta Pixel Purchase tera atribuicao reduzida (sem pageview_event_id)")
                    else:
                        error_msg = f"[TOKEN AUSENTE] tracking_token AUSENTE e PIX nao foi gerado - Payment NAO sera criado"
                        logger.error(error_msg)
                        logger.error(f"   BotUser {bot_user.id if bot_user else 'N/A'} nao tem tracking_session_id")
                        logger.error(f"   SOLUCAO: Usuario deve acessar link de redirect primeiro: /go/{slug}?grim=...&fbclid=...")
                        raise ValueError("tracking_token ausente e PIX nao gerado - Payment nao pode ser criado sem tracking_token valido e sem PIX")

                is_generated_token = False
                is_uuid_token = False

                if tracking_token:
                    is_generated_token = tracking_token.startswith('tracking_')

                    normalized_token = tracking_token.replace('-', '').lower()
                    is_uuid_token = len(normalized_token) == 32 and all(c in '0123456789abcdef' for c in normalized_token)

                    if is_generated_token:
                        logger.warning(f"[TOKEN LEGADO] tracking_token LEGADO detectado: {tracking_token[:30]}...")
                        logger.warning(f"   PIX foi gerado com sucesso (transaction_id: {gateway_transaction_id})")
                        logger.warning(f"   Payment sera criado mesmo com token legado para evitar perder venda")
                        logger.warning(f"   Meta Pixel Purchase pode ter atribuicao reduzida (sem pageview_event_id)")

                    if not is_uuid_token and not is_generated_token:
                        error_msg = f"[GENERATE PIX] tracking_token com formato invalido: {tracking_token[:30]}... (len={len(tracking_token)})"
                        logger.error(error_msg)
                        logger.error(f"   Payment NAO sera criado com token invalido")
                        logger.error(f"   tracking_token deve ser UUID (32 ou 36 chars, com ou sem hifens) ou gerado (tracking_*)")
                        raise ValueError(f"tracking_token com formato invalido - deve ser UUID (32 ou 36 chars) ou gerado (tracking_*)")

                    if is_uuid_token:
                        logger.info(f"[TOKEN UUID] tracking_token validado: {tracking_token[:20]}... (UUID do redirect, len={len(tracking_token)})")
                    else:
                        logger.info(f"[TOKEN LEGADO] tracking_token legado: {tracking_token[:20]}... (sera usado mesmo assim)")
                else:
                    logger.info(f"[TOKEN AUSENTE] Payment sera criado sem tracking_token (PIX ja foi gerado)")

                button_data_for_subscription = None
                has_subscription_flag = False

                if button_config:
                    button_data_for_subscription = button_config.copy()
                    has_subscription_flag = button_config.get('subscription', {}).get('enabled', False)
                elif button_index is not None:
                    if bot and bot.config:
                        config_dict = bot.config.to_dict()
                        main_buttons = config_dict.get('main_buttons', [])
                        if button_index < len(main_buttons):
                            button_data_for_subscription = main_buttons[button_index].copy()
                            has_subscription_flag = button_data_for_subscription.get('subscription', {}).get('enabled', False)

                import json as json_module

                is_downsell_final = is_downsell or False
                is_upsell_final = is_upsell or False

                bot_user_for_payment = None
                if customer_user_id:
                    bot_user_for_payment = BotUser.query.filter_by(
                        bot_id=bot_id,
                        telegram_user_id=str(customer_user_id),
                        archived=False
                    ).first()

                payment = Payment(
                    bot_id=bot_id,
                    payment_id=payment_id,
                    gateway_type=gateway.gateway_type if gateway else None,
                    gateway_transaction_id=gateway_transaction_id,
                    gateway_transaction_hash=gateway_hash,
                    payment_method=str(pix_result.get('payment_method') or pix_result.get('paymentMethod') or 'PIX')[:20] if pix_result else 'PIX',
                    amount=amount,
                    customer_name=customer_name,
                    customer_username=customer_username,
                    customer_user_id=customer_user_id,
                    customer_email=customer_data.get('email'),
                    customer_phone=customer_data.get('phone'),
                    customer_document=customer_data.get('document'),
                    product_name=description,
                    product_description=pix_result.get('pix_code'),
                    status=payment_status,
                    tracking_token=getattr(bot_user_for_payment, 'tracking_session_id', None) if bot_user_for_payment else (tracking_token if tracking_token else None),
                    meta_pixel_id=meta_pixel_id,
                    pool_id=pool_id_from_tracking if pool_id_from_tracking else None,
                    fbclid=getattr(bot_user_for_payment, 'fbclid', None) if bot_user_for_payment else None,
                    order_bump_shown=order_bump_shown,
                    order_bump_accepted=order_bump_accepted,
                    order_bump_value=order_bump_value,
                    is_downsell=is_downsell,
                    downsell_index=downsell_index,
                    is_upsell=is_upsell_final,
                    upsell_index=upsell_index,
                    is_remarketing=is_remarketing,
                    remarketing_campaign_id=remarketing_campaign_id,
                    customer_age=getattr(bot_user, 'customer_age', None) if bot_user else None,
                    customer_city=getattr(bot_user, 'customer_city', None) if bot_user else None,
                    customer_state=getattr(bot_user, 'customer_state', None) if bot_user else None,
                    customer_country=getattr(bot_user, 'customer_country', 'BR') if bot_user else 'BR',
                    customer_gender=getattr(bot_user, 'customer_gender', None) if bot_user else None,
                    device_type=getattr(bot_user, 'device_type', None) if bot_user else None,
                    os_type=getattr(bot_user, 'os_type', None) if bot_user else None,
                    browser=getattr(bot_user, 'browser', None) if bot_user else None,
                    device_model=getattr(bot_user, 'device_model', None) if bot_user else None,
                    utm_source=utm_source if utm_source is not None else (getattr(bot_user, 'utm_source', None) if bot_user else None),
                    utm_campaign=utm_campaign if utm_campaign is not None else (getattr(bot_user, 'utm_campaign', None) if bot_user else None),
                    utm_content=utm_content if utm_content is not None else (getattr(bot_user, 'utm_content', None) if bot_user else None),
                    utm_medium=utm_medium if utm_medium is not None else (getattr(bot_user, 'utm_medium', None) if bot_user else None),
                    utm_term=utm_term if utm_term is not None else (getattr(bot_user, 'utm_term', None) if bot_user else None),
                    campaign_code=tracking_data_v4.get('grim') if tracking_data_v4.get('grim') else (getattr(bot_user, 'campaign_code', None) if bot_user else None),
                    click_context_url=(
                        tracking_data_v4.get('event_source_url')
                        or getattr(bot_user, 'last_click_context_url', None)
                        or None
                    ),
                    button_index=button_index,
                    button_config=json_module.dumps(button_data_for_subscription, ensure_ascii=False) if button_data_for_subscription else None,
                    has_subscription=has_subscription_flag
                )
                db.session.add(payment)
                db.session.flush()

                if tracking_token:
                    try:
                        tracking_service.save_tracking_data(
                            tracking_token=tracking_token,
                            bot_id=bot_id,
                            customer_user_id=customer_user_id,
                            payment_id=payment.id,
                            fbclid=fbclid,
                            fbp=fbp,
                            fbc=fbc,
                            utm_source=utm_source,
                            utm_medium=utm_medium,
                            utm_campaign=utm_campaign,
                            external_ids=external_ids
                        )
                        logger.info(f"Tracking data salvo no Redis para payment {payment.id}")
                    except Exception as redis_error:
                        logger.warning(f"[REDIS INDISPONIVEL] Erro ao salvar tracking data no Redis: {redis_error}")
                        logger.warning(f"   Payment {payment.id} foi criado mesmo assim (tracking data e opcional)")
                else:
                    logger.warning(f"[TOKEN AUSENTE] Nao salvando tracking data no Redis (tracking_token e None)")

                gateway.total_transactions += 1

                try:
                    db.session.commit()
                    logger.info(f"Payment {payment.id} commitado com sucesso")
                except IntegrityError as integrity_error:
                    db.session.rollback()
                    logger.error(f"[ERRO DE INTEGRIDADE] Erro ao commitar Payment: {integrity_error}", exc_info=True)
                    logger.error(f"   Payment ID: {payment.id}, payment_id: {payment.payment_id}")
                    logger.error(f"   Gateway Transaction ID: {gateway_transaction_id}")
                    return None
                except Exception as commit_error:
                    db.session.rollback()
                    logger.error(f"[ERRO AO COMMITAR] Erro ao commitar Payment: {commit_error}", exc_info=True)
                    logger.error(f"   Payment ID: {payment.id}, payment_id: {payment.payment_id}")
                    return None

                try:
                    resolved_pageview_event_id = (
                        pageview_event_id
                        or getattr(payment, 'pageview_event_id', None)
                        or getattr(bot_user, 'pageview_event_id', None)
                    )

                    # Resolver pool_bot para o enrichment (mesma lógica do delivery)
                    from internal_logic.core.models import PoolBot
                    pool_bot = None
                    if bot_user and bot_user.tracking_session_id:
                        temp_tracking_data = tracking_service.recover_tracking_data(bot_user.tracking_session_id) or {}
                        pool_id_from_tracking = temp_tracking_data.get('pool_id')
                        if pool_id_from_tracking:
                            pool_bot = PoolBot.query.filter_by(bot_id=bot_id, pool_id=pool_id_from_tracking).first()
                    if not pool_bot:
                        pool_bot = PoolBot.query.filter_by(bot_id=bot_id).first()

                    logger.info(
                        "ENRICHMENT CHECK | PIX",
                        extra={
                            "payment_db_id": getattr(payment, 'id', None),
                            "payment_id": getattr(payment, 'payment_id', None),
                            "pageview_event_id": pageview_event_id,
                            "resolved_pageview_event_id": resolved_pageview_event_id,
                            "tracking_token": tracking_token,
                            "has_customer_email": bool(getattr(payment, 'customer_email', None)),
                            "has_customer_phone": bool(getattr(payment, 'customer_phone', None)),
                            "pool_bot": bool(pool_bot),
                            "meta_enabled": bool(pool_bot and pool_bot.pool and pool_bot.pool.meta_tracking_enabled),
                            "meta_pageview_enabled": bool(pool_bot and pool_bot.pool and pool_bot.pool.meta_events_pageview)
                        }
                    )
                    if resolved_pageview_event_id and pool_bot and pool_bot.pool and pool_bot.pool.meta_tracking_enabled and pool_bot.pool.meta_events_pageview:
                        pool_for_meta = pool_bot.pool

                        customer_email = getattr(payment, 'customer_email', None)
                        customer_phone = getattr(payment, 'customer_phone', None)

                        def _is_high_confidence_email(email_value: str) -> bool:
                            if not email_value or not isinstance(email_value, str):
                                return False
                            email_clean = email_value.strip().lower()
                            if '@' not in email_clean:
                                return False
                            if email_clean.endswith('@telegram.local'):
                                return False
                            if email_clean.startswith('user_') and email_clean.endswith('@telegram.local'):
                                return False
                            return len(email_clean) >= 6

                        def _is_high_confidence_phone(phone_value: str) -> bool:
                            if not phone_value or not isinstance(phone_value, str):
                                return False
                            digits = ''.join(filter(str.isdigit, phone_value))
                            if len(digits) < 10:
                                return False
                            if digits in ('11999999999', '00000000000'):
                                return False
                            return True

                        should_enrich = _is_high_confidence_email(customer_email) or _is_high_confidence_phone(customer_phone)
                        if should_enrich:
                            if not resolved_pageview_event_id:
                                logger.warning(
                                    "PAGEVIEW_EVENT_ID AUSENTE | Enrichment impossivel",
                                    extra={
                                        "payment_db_id": getattr(payment, 'id', None),
                                        "payment_id": getattr(payment, 'payment_id', None),
                                        "tracking_token": tracking_token,
                                        "bot_user_id": getattr(bot_user, 'id', None),
                                        "is_remarketing": bool(is_remarketing)
                                    }
                                )
                                return

                            enrichment_lock_key = f"meta:pageview_enriched:{resolved_pageview_event_id}"
                            lock_ttl_seconds = 60 * 60 * 24 * 30

                            lock_acquired = False
                            try:
                                lock_acquired = bool(tracking_service.redis.set(enrichment_lock_key, '1', nx=True, ex=lock_ttl_seconds))
                            except Exception as lock_error:
                                logger.warning(f"[META PAGEVIEW ENRICH] Falha ao criar lock Redis: {lock_error}")

                            logger.info(
                                "ENRICHMENT LOCK RESULT",
                                extra={
                                    "enrichment_lock_key": enrichment_lock_key,
                                    "lock_ttl_seconds": lock_ttl_seconds,
                                    "lock_acquired": bool(lock_acquired)
                                }
                            )

                            if lock_acquired:
                                from tasks_async import enqueue_meta_event
                                from utils.encryption import decrypt
                                from utils.meta_pixel import MetaPixelAPI

                                try:
                                    access_token = decrypt(pool_for_meta.meta_access_token)
                                except Exception as decrypt_error:
                                    logger.error(f"[META PAGEVIEW ENRICH] Erro ao descriptografar access_token do pool {pool_for_meta.id}: {decrypt_error}")
                                    access_token = None

                                if access_token:
                                    ip_value_for_enrich = tracking_data_v4.get('client_ip') or tracking_data_v4.get('ip') or tracking_data_v4.get('client_ip_address')
                                    if ip_value_for_enrich and isinstance(ip_value_for_enrich, str) and '.AQYBAQIA' in ip_value_for_enrich:
                                        ip_value_for_enrich = ip_value_for_enrich.split('.AQYBAQIA')[0]

                                    ua_value_for_enrich = tracking_data_v4.get('client_user_agent') or tracking_data_v4.get('ua') or tracking_data_v4.get('client_ua')
                                    fbp_value_for_enrich = tracking_data_v4.get('fbp') or getattr(payment, 'fbp', None)
                                    fbc_value_for_enrich = tracking_data_v4.get('fbc') or getattr(payment, 'fbc', None)

                                    fbclid_for_enrich = tracking_data_v4.get('fbclid') or getattr(payment, 'fbclid', None)

                                    telegram_user_id_for_enrich = None
                                    if bot_user and getattr(bot_user, 'telegram_user_id', None):
                                        telegram_user_id_for_enrich = str(bot_user.telegram_user_id)
                                    elif customer_user_id:
                                        telegram_user_id_for_enrich = str(customer_user_id).replace('user_', '')

                                    external_id_value = (fbclid_for_enrich or '').strip()

                                    user_data_enriched = MetaPixelAPI._build_user_data(
                                        customer_user_id=telegram_user_id_for_enrich,
                                        external_id=external_id_value or None,
                                        email=customer_email if _is_high_confidence_email(customer_email) else None,
                                        phone=customer_phone if _is_high_confidence_phone(customer_phone) else None,
                                        client_ip=ip_value_for_enrich,
                                        client_user_agent=ua_value_for_enrich,
                                        fbp=fbp_value_for_enrich,
                                        fbc=fbc_value_for_enrich
                                    )

                                    event_source_url_enrich = tracking_data_v4.get('event_source_url') or tracking_data_v4.get('first_page')

                                    pageview_enriched_event = {
                                        'event_name': 'PageView',
                                        'event_time': int(time.time()),
                                        'event_id': resolved_pageview_event_id,
                                        'action_source': 'website',
                                        'event_source_url': event_source_url_enrich,
                                        'user_data': user_data_enriched,
                                        'custom_data': {
                                            'source': 'pageview_enrichment',
                                            'payment_id': getattr(payment, 'payment_id', None),
                                            'payment_db_id': getattr(payment, 'id', None),
                                            'gateway_type': getattr(payment, 'gateway_type', None)
                                        }
                                    }

                                    enqueue_meta_event(
                                        pixel_id=pool_for_meta.meta_pixel_id,
                                        access_token=access_token,
                                        event_data=pageview_enriched_event,
                                        test_code=pool_for_meta.meta_test_event_code
                                    )

                                    logger.info(
                                        f"[META PAGEVIEW ENRICH] Enfileirado apos PIX | event_id={resolved_pageview_event_id} | "
                                        f"em={'ok' if user_data_enriched.get('em') else 'missing'} | ph={'ok' if user_data_enriched.get('ph') else 'missing'}"
                                    )
                            else:
                                logger.info(f"[META PAGEVIEW ENRICH] Lock ja existe (nao reenviar) | key={enrichment_lock_key} | ttl={lock_ttl_seconds}s | event_id={resolved_pageview_event_id}")
                except Exception as enrich_error:
                    logger.warning(f"[META PAGEVIEW ENRICH] Falha ao enriquecer PageView apos PIX (nao bloqueia PIX): {enrich_error}")

                return {
                    'payment_id': payment_id,
                    'pix_code': pix_result.get('pix_code'),
                    'qr_code_url': pix_result.get('qr_code_url'),
                    'qr_code_base64': pix_result.get('qr_code_base64')
                }
            else:
                logger.error(f"FALHA AO GERAR PIX NO GATEWAY {gateway.gateway_type.upper()}")
                logger.error(f"   Gateway Type: {gateway.gateway_type}")
                logger.error(f"   Valor: R$ {amount:.2f}")
                logger.error(f"   Descricao: {description}")

                if gateway.gateway_type == 'wiinpay' and amount < 3.0:
                    logger.error(f"WIINPAY: Valor minimo e R$ 3,00! Valor enviado: R$ {amount:.2f}")

                return None

    except requests.exceptions.Timeout as timeout_error:
        logger.warning(f"[GATEWAY TIMEOUT] Gateway timeout ao gerar PIX: {timeout_error}")
        try:
            from internal_logic.core.extensions import db
            from internal_logic.core.models import Payment
            from flask import current_app
            with current_app.app_context():
                payment = Payment.query.filter_by(
                    bot_id=bot_id,
                    customer_user_id=customer_user_id,
                    amount=amount,
                    status='pending'
                ).order_by(Payment.id.desc()).first()

                if payment:
                    payment.status = 'pending_verification'
                    db.session.commit()
                    return {'status': 'pending_verification', 'payment_id': payment.payment_id, 'error': 'Gateway timeout'}
        except Exception as db_err:
            logger.error(f"Erro ao tratar timeout no DB: {db_err}")
        return None

    finally:
        try:
            if lock_acquired and lock_key and redis_conn:
                redis_conn.delete(lock_key)
        except Exception as unlock_error:
            logger.warning(f"Erro ao liberar lock PIX: {unlock_error}")
