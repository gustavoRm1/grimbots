# 🔥 TRECHOS CRÍTICOS - BUG DE LIBERAÇÃO ANTECIPADA

**Data:** 2025-11-14  
**Problema:** Acesso sendo liberado ANTES do pagamento ser confirmado

---

## 📌 1️⃣ `_generate_pix_payment()` COMPLETO

```python:4017:4616:bot_manager.py
    def _generate_pix_payment(self, bot_id: int, amount: float, description: str,
                             customer_name: str, customer_username: str, customer_user_id: str,
                             order_bump_shown: bool = False, order_bump_accepted: bool = False, 
                             order_bump_value: float = 0.0, is_downsell: bool = False, 
                             downsell_index: int = None) -> Optional[Dict[str, Any]]:
        """
        Gera pagamento PIX via gateway configurado
        
        Args:
            bot_id: ID do bot
            amount: Valor do pagamento
            description: Descrição do produto
            customer_name: Nome do cliente
            customer_username: Username do Telegram
            customer_user_id: ID do usuário no Telegram
            
        ✅ VALIDAÇÃO CRÍTICA: customer_user_id não pode ser vazio (destrói tracking Meta Pixel)
        """
        # ✅ VALIDAÇÃO CRÍTICA: customer_user_id obrigatório para tracking
        if not customer_user_id or customer_user_id.strip() == "":
            logger.error(f"❌ ERRO CRÍTICO: customer_user_id vazio ao gerar PIX! Bot: {bot_id}, Valor: R$ {amount:.2f}")
            logger.error(f"   Isso quebra tracking Meta Pixel - Purchase não será atribuído à campanha!")
            logger.error(f"   customer_name: {customer_name}, customer_username: {customer_username}")
            return None
        try:
            # Importar models dentro da função para evitar circular import
            from models import Bot, Gateway, Payment, db
            from app import app
            
            with app.app_context():
                # Buscar bot e gateway
                bot = db.session.get(Bot, bot_id)
                if not bot:
                    logger.error(f"Bot {bot_id} não encontrado")
                    return None
                
                # Buscar gateway ativo e verificado do usuário
                gateway = Gateway.query.filter_by(
                    user_id=bot.user_id,
                    is_active=True,
                    is_verified=True
                ).first()
                
                if not gateway:
                    logger.error(f"Nenhum gateway ativo encontrado para usuário {bot.user_id}")
                    return None
                
                logger.info(f"💳 Gateway: {gateway.gateway_type.upper()}")
                
                # ✅ PROTEÇÃO CONTRA MÚLTIPLOS PIX (SOLUÇÃO HÍBRIDA - SENIOR QI 500 + QI 502)
                
                # 1. Verificar se cliente tem PIX pendente para MESMO PRODUTO
                # ✅ CORREÇÃO: Normalizar descrição para comparação precisa
                def normalize_product_name(name):
                    """Remove emojis e normaliza para comparação"""
                    if not name:
                        return ''
                    import re
                    # Remove emojis e caracteres especiais
                    normalized = re.sub(r'[^\w\s]', '', name)
                    return normalized.lower().strip()
                
                normalized_description = normalize_product_name(description)
                
                # Buscar todos os PIX pendentes do cliente
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
                
                # ✅ REGRA DE NEGÓCIO: Reutilizar APENAS se foi gerado há <= 5 minutos E o valor bater exatamente
                if pending_same_product:
                    try:
                        from models import get_brazil_time
                        age_seconds = (get_brazil_time() - pending_same_product.created_at).total_seconds() if pending_same_product.created_at else 999999
                    except Exception:
                        age_seconds = 999999
                    amount_matches = abs(float(pending_same_product.amount) - float(amount)) < 0.01
                    if pending_same_product.status == 'pending' and age_seconds <= 300 and amount_matches:
                        # ✅ CORREÇÃO CRÍTICA: Paradise NÃO REUTILIZA PIX (evita duplicação de IDs)
                        # Paradise gera IDs únicos e não aceita reutilização
                        if gateway.gateway_type == 'paradise':
                            logger.warning(f"⚠️ Paradise não permite reutilizar PIX - gerando NOVO para evitar IDs duplicados.")
                        else:
                            logger.warning(f"⚠️ Já existe PIX pendente (<=5min) e valor igual para {description}. Reutilizando.")
                            pix_result = {
                                'pix_code': pending_same_product.product_description,
                                'pix_code_base64': None,
                                'qr_code_url': None,
                                'transaction_id': pending_same_product.gateway_transaction_id,
                                'transaction_hash': pending_same_product.gateway_transaction_hash,  # ✅ Incluir hash também
                                'payment_id': pending_same_product.payment_id,
                                'expires_at': None
                            }
                            logger.info(f"✅ PIX reutilizado: {pending_same_product.payment_id} | idade={int(age_seconds)}s | valor_ok={amount_matches}")
                            return pix_result
                    else:
                        logger.info(
                            f"♻️ NÃO reutilizar PIX existente: status={pending_same_product.status}, idade={int(age_seconds)}s, valor_ok={amount_matches}. Gerando NOVO PIX."
                        )
                
                # 2. Verificar rate limiting para OUTRO PRODUTO (2 minutos)
                last_pix = Payment.query.filter_by(
                    bot_id=bot_id,
                    customer_user_id=customer_user_id
                ).order_by(Payment.id.desc()).first()
                
                if last_pix and last_pix.status == 'pending':
                    from models import get_brazil_time
                    time_since = (get_brazil_time() - last_pix.created_at).total_seconds()
                    if time_since < 120:  # 2 minutos
                        wait_time = 120 - int(time_since)
                        wait_minutes = wait_time // 60
                        wait_seconds = wait_time % 60
                        
                        if wait_minutes > 0:
                            time_msg = f"{wait_minutes} minuto{'s' if wait_minutes > 1 else ''} e {wait_seconds} segundo{'s' if wait_seconds > 1 else ''}"
                        else:
                            time_msg = f"{wait_seconds} segundo{'s' if wait_seconds > 1 else ''}"
                        
                        logger.warning(f"⚠️ Rate limit: cliente deve aguardar {time_msg} para gerar novo PIX")
                        return {'rate_limit': True, 'wait_time': time_msg}  # Retorna tempo para frontend
                
                # Gerar ID único do pagamento (só se não houver PIX pendente)
                import uuid
                payment_id = f"BOT{bot_id}_{int(time.time())}_{uuid.uuid4().hex[:8]}"
                
                # ✅ PREPARAR CREDENCIAIS ESPECÍFICAS PARA CADA GATEWAY
                # ✅ RANKING V2.0: Usar commission_percentage do USUÁRIO diretamente
                # Isso garante que taxas premium do Top 3 sejam aplicadas em tempo real
                # Prioridade: user.commission_percentage > gateway.split_percentage > 2.0 (padrão)
                user_commission = bot.owner.commission_percentage or gateway.split_percentage or 2.0
                
                credentials = {
                    # SyncPay usa client_id/client_secret
                    'client_id': gateway.client_id,
                    'client_secret': gateway.client_secret,
                    # Outros gateways usam api_key
                    'api_key': gateway.api_key,
                    # ✅ Átomo Pay: api_token é salvo em api_key no banco, mas precisa ser passado como api_token
                    'api_token': gateway.api_key if gateway.gateway_type == 'atomopay' else None,
                    # Paradise
                    'product_hash': gateway.product_hash,
                    'offer_hash': gateway.offer_hash,
                    'store_id': gateway.store_id,
                    # WiinPay
                    'split_user_id': gateway.split_user_id,
                    # ✅ RANKING V2.0: Usar taxa do usuário (pode ser premium)
                    'split_percentage': user_commission
                }
                
                # ✅ LOG: Verificar se api_token está presente para Átomo Pay
                if gateway.gateway_type == 'atomopay':
                    if not credentials.get('api_token'):
                        logger.error(f"❌ Átomo Pay: api_token (api_key) não encontrado no gateway!")
                        logger.error(f"   gateway.api_key: {gateway.api_key}")
                        logger.error(f"   gateway.id: {gateway.id}")
                        return None
                    else:
                        logger.debug(f"🔑 Átomo Pay: api_token presente ({len(credentials['api_token'])} caracteres)")
                
                # Log para auditoria (apenas se for premium)
                if user_commission < 2.0:
                    logger.info(f"🏆 TAXA PREMIUM aplicada: {user_commission}% (User {bot.owner.id})")
                
                # ✅ PATCH 2 QI 200: Garantir que product_hash existe antes de usar
                # Se gateway não tem product_hash, será criado dinamicamente no generate_pix
                # Mas precisamos garantir que será salvo no banco após criação
                original_product_hash = gateway.product_hash
                
                # Gerar PIX via gateway (usando Factory Pattern)
                logger.info(f"🔧 Criando gateway {gateway.gateway_type} com credenciais...")
                
                payment_gateway = GatewayFactory.create_gateway(
                    gateway_type=gateway.gateway_type,
                    credentials=credentials
                )
                
                if not payment_gateway:
                    logger.error(f"❌ Erro ao criar gateway {gateway.gateway_type}")
                    return None
                
                logger.info(f"✅ Gateway {gateway.gateway_type} criado com sucesso!")
                
                # ✅ VALIDAÇÃO ESPECÍFICA: WiinPay valor mínimo R$ 3,00
                if gateway.gateway_type == 'wiinpay' and amount < 3.0:
                    logger.error(f"❌ WIINPAY: Valor mínimo R$ 3,00 | Produto: R$ {amount:.2f}")
                    logger.error(f"   SOLUÇÃO: Use Paradise, Pushyn ou SyncPay para valores < R$ 3,00")
                    logger.error(f"   Ou aumente o preço do produto para mínimo R$ 3,00")
                    return None
                
                # Gerar PIX usando gateway isolado com DADOS REAIS DO CLIENTE
                logger.info(f"💰 Gerando PIX: R$ {amount:.2f} | Descrição: {description}")
                pix_result = payment_gateway.generate_pix(
                    amount=amount,
                    description=description,
                    payment_id=payment_id,
                    customer_data={
                        'name': customer_name or 'Cliente',
                        'email': f"{customer_username}@telegram.user" if customer_username else f"user{customer_user_id}@telegram.user",
                        'phone': customer_user_id,  # ✅ User ID do Telegram como identificador único
                        'document': customer_user_id  # ✅ User ID do Telegram (gateways aceitam)
                    }
                )
                
                logger.info(f"📊 Resultado do PIX: {pix_result}")
                
                if pix_result:
                    # ✅ CRÍTICO: Verificar se transação foi recusada
                    transaction_status = pix_result.get('status')
                    is_refused = transaction_status == 'refused' or pix_result.get('error')
                    
                    if is_refused:
                        logger.warning(f"⚠️ Transação RECUSADA pelo gateway - criando payment com status 'failed' para webhook")
                    else:
                        logger.info(f"✅ PIX gerado com sucesso pelo gateway!")
                    
                    # ✅ BUSCAR BOT_USER PARA COPIAR DADOS DEMOGRÁFICOS
                    from models import BotUser
                    bot_user = BotUser.query.filter_by(
                        bot_id=bot_id,
                        telegram_user_id=customer_user_id
                    ).first()
                    
                    # ✅ QI 500: GERAR/REUTILIZAR TRACKING_TOKEN V4 (mantém vínculo PageView → Purchase)
                    from utils.tracking_service import TrackingServiceV4
                    tracking_service = TrackingServiceV4()
                    
                    # Recuperar dados de tracking do bot_user
                    fbclid = getattr(bot_user, 'fbclid', None) if bot_user else None
                    utm_source = getattr(bot_user, 'utm_source', None) if bot_user else None
                    utm_medium = getattr(bot_user, 'utm_medium', None) if bot_user else None
                    utm_campaign = getattr(bot_user, 'utm_campaign', None) if bot_user else None
                    utm_content = getattr(bot_user, 'utm_content', None) if bot_user else None
                    utm_term = getattr(bot_user, 'utm_term', None) if bot_user else None
                    
                    redis_tracking_payload: Dict[str, Any] = {}
                    tracking_token = None

                    # ✅ CORREÇÃO: Recuperar tracking_token ANTES de gerar valores sintéticos
                    # Prioridade: tracking:last_token > tracking:chat > bot_user.tracking_session_id
                    if customer_user_id:
                        try:
                            cached_token = tracking_service.redis.get(f"tracking:last_token:user:{customer_user_id}")
                            if cached_token:
                                tracking_token = cached_token
                                logger.info(f"✅ Tracking token recuperado de tracking:last_token:user:{customer_user_id}: {tracking_token[:20]}...")
                        except Exception:
                            logger.exception("Falha ao recuperar tracking:last_token do Redis")
                        if not tracking_token:
                            try:
                                cached_payload = tracking_service.redis.get(f"tracking:chat:{customer_user_id}")
                                if cached_payload:
                                    redis_tracking_payload = json.loads(cached_payload)
                                    tracking_token = redis_tracking_payload.get("tracking_token") or tracking_token
                                    if tracking_token:
                                        logger.info(f"✅ Tracking token recuperado de tracking:chat:{customer_user_id}: {tracking_token[:20]}...")
                            except Exception:
                                logger.exception("Falha ao recuperar tracking:chat do Redis")

                    # ✅ CRÍTICO: Verificar bot_user.tracking_session_id ANTES de tentar Redis
                    # Isso garante que o token do public_redirect seja sempre usado
                    if not tracking_token and bot_user:
                        tracking_token = getattr(bot_user, 'tracking_session_id', None)
                        if tracking_token:
                            logger.info(f"✅ Tracking token recuperado de bot_user.tracking_session_id: {tracking_token[:20]}...")
                        else:
                            logger.warning(f"⚠️ BotUser {bot_user.id} encontrado mas tracking_session_id está vazio (telegram_user_id: {customer_user_id})")

                    tracking_data_v4: Dict[str, Any] = redis_tracking_payload if isinstance(redis_tracking_payload, dict) else {}

                    # ✅ CRÍTICO: Recuperar payload completo do Redis ANTES de gerar valores sintéticos
                    if tracking_token:
                        recovered_payload = tracking_service.recover_tracking_data(tracking_token) or {}
                        if recovered_payload:
                            tracking_data_v4 = recovered_payload
                            logger.info(f"✅ Tracking payload recuperado do Redis para token {tracking_token[:20]}... | fbp={'ok' if recovered_payload.get('fbp') else 'missing'} | fbc={'ok' if recovered_payload.get('fbc') else 'missing'} | pageview_event_id={'ok' if recovered_payload.get('pageview_event_id') else 'missing'}")
                        elif not tracking_data_v4:
                            logger.warning("⚠️ Tracking token %s sem payload no Redis - tentando reconstruir via BotUser", tracking_token)
                        if bot_user and getattr(bot_user, 'tracking_session_id', None) != tracking_token:
                            bot_user.tracking_session_id = tracking_token

                    # ✅ CRÍTICO: NUNCA gerar novo token se bot_user.tracking_session_id existir
                    # Isso garante que o token do public_redirect seja sempre reutilizado
                    if not tracking_token and bot_user and bot_user.tracking_session_id:
                        tracking_token = bot_user.tracking_session_id
                        logger.info(f"✅ Tracking token recuperado de bot_user.tracking_session_id (fallback final): {tracking_token[:20]}...")
                        # Tentar recuperar payload do Redis com este token
                        try:
                            recovered_payload = tracking_service.recover_tracking_data(tracking_token) or {}
                            if recovered_payload:
                                tracking_data_v4 = recovered_payload
                                logger.info(f"✅ Tracking payload recuperado do bot_user.tracking_session_id: {tracking_token[:20]}... | fbp={'ok' if recovered_payload.get('fbp') else 'missing'} | fbc={'ok' if recovered_payload.get('fbc') else 'missing'} | pageview_event_id={'ok' if recovered_payload.get('pageview_event_id') else 'missing'}")
                        except Exception as e:
                            logger.warning(f"⚠️ Erro ao recuperar payload do bot_user.tracking_session_id: {e}")
                    
                    if not tracking_token:
                        # ✅ ÚLTIMA TENTATIVA: Verificar se bot_user foi encontrado mas tracking_session_id está vazio
                        if bot_user:
                            logger.warning(f"⚠️ Tracking token não encontrado para BotUser {bot_user.id} (telegram_user_id: {customer_user_id})")
                            logger.warning(f"   bot_user.tracking_session_id: {getattr(bot_user, 'tracking_session_id', None)}")
                            logger.warning(f"   Tentando recuperar de tracking:last_token:user:{customer_user_id} e tracking:chat:{customer_user_id}")
                        else:
                            logger.warning(f"⚠️ BotUser não encontrado para customer_user_id: {customer_user_id}, bot_id: {bot_id}")
                        
                        tracking_token = tracking_service.generate_tracking_token(
                            bot_id=bot_id,
                            customer_user_id=customer_user_id,
                            payment_id=None,
                            fbclid=fbclid,
                            utm_source=utm_source,
                            utm_medium=utm_medium,
                            utm_campaign=utm_campaign
                        )
                        logger.warning("⚠️ Token de tracking ausente - gerado novo %s para BotUser %s (customer_user_id: %s)", tracking_token, bot_user.id if bot_user else 'N/A', customer_user_id)
                        seed_payload = {
                            "tracking_token": tracking_token,
                            "bot_id": bot_id,
                            "customer_user_id": customer_user_id,
                            "fbclid": fbclid,
                            "utm_source": utm_source,
                            "utm_medium": utm_medium,
                            "utm_campaign": utm_campaign,
                            "utm_content": utm_content,
                            "utm_term": utm_term,
                            "pageview_ts": tracking_data_v4.get('pageview_ts'),
                            "created_from": "generate_pix_payment",
                        }
                        tracking_service.save_tracking_token(tracking_token, {k: v for k, v in seed_payload.items() if v})
                        if bot_user:
                            bot_user.tracking_session_id = tracking_token
                    if not tracking_data_v4:
                        tracking_data_v4 = tracking_service.recover_tracking_data(tracking_token) or {}
                    
                    # Enriquecer com dados do BotUser quando faltarem no payload
                    enrichment_source = {
                        "fbclid": fbclid,
                        "utm_source": utm_source,
                        "utm_medium": utm_medium,
                        "utm_campaign": utm_campaign,
                        "utm_content": utm_content,
                        "utm_term": utm_term,
                        "grim": getattr(bot_user, 'campaign_code', None) if bot_user else None,
                    }
                    for key, value in enrichment_source.items():
                        if value and key not in tracking_data_v4:
                            tracking_data_v4[key] = value
                    
                    if tracking_data_v4.get('fbclid'):
                        fbclid = tracking_data_v4['fbclid']
                    if tracking_data_v4.get('utm_source'):
                        utm_source = tracking_data_v4['utm_source']
                    if tracking_data_v4.get('utm_medium'):
                        utm_medium = tracking_data_v4['utm_medium']
                    if tracking_data_v4.get('utm_campaign'):
                        utm_campaign = tracking_data_v4['utm_campaign']
                    if tracking_data_v4.get('utm_content'):
                        utm_content = tracking_data_v4['utm_content']
                    if tracking_data_v4.get('utm_term'):
                        utm_term = tracking_data_v4['utm_term']
                    
                    # ✅ CRÍTICO: Usar valores do Redis se disponíveis, só gerar sintéticos se faltar
                    fbp = tracking_data_v4.get('fbp')
                    fbc = tracking_data_v4.get('fbc')
                    pageview_event_id = tracking_data_v4.get('pageview_event_id')
                    
                    if not fbp:
                        fbp = tracking_service.generate_fbp(str(customer_user_id))
                        logger.warning(f"⚠️ fbp não encontrado no tracking_data_v4 - gerado sintético: {fbp[:30]}...")
                    else:
                        logger.info(f"✅ fbp recuperado do tracking_data_v4: {fbp[:30]}...")
                    
                    # ✅ CRÍTICO: NUNCA gerar fbc sintético em generate_pix_payment
                    # O fbc deve vir EXATAMENTE do redirect (cookie do browser)
                    # Gerar sintético aqui quebra a atribuição porque o timestamp não corresponde ao clique original
                    if fbc:
                        logger.info(f"✅ fbc recuperado do tracking_data_v4: {fbc[:30]}...")
                    else:
                        logger.warning(f"⚠️ fbc não encontrado no tracking_data_v4 - NÃO gerando sintético (preservando atribuição)")
                        # ✅ NÃO gerar fbc sintético - deixar None e confiar no fallback do Purchase
                    
                    if pageview_event_id:
                        logger.info(f"✅ pageview_event_id recuperado do tracking_data_v4: {pageview_event_id}")
                    else:
                        # ✅ FALLBACK: Tentar recuperar do bot_user (se houver tracking_session_id)
                        if bot_user and bot_user.tracking_session_id:
                            try:
                                # ✅ CORREÇÃO: Usar tracking_service (já instanciado acima) ao invés de tracking_service_v4
                                fallback_tracking = tracking_service.recover_tracking_data(bot_user.tracking_session_id)
                                pageview_event_id = fallback_tracking.get('pageview_event_id')
                                if pageview_event_id:
                                    logger.info(f"✅ pageview_event_id recuperado do bot_user.tracking_session_id: {pageview_event_id}")
                            except Exception as e:
                                logger.warning(f"⚠️ Erro ao recuperar pageview_event_id do bot_user: {e}")
                        
                        if not pageview_event_id:
                            logger.warning(f"⚠️ pageview_event_id não encontrado no tracking_data_v4 nem no bot_user - Purchase pode não fazer dedup perfeito")
                    
                    # Gerar external_ids com dados reais recuperados
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
                        # ✅ CRÍTICO: Só incluir fbc se for válido (não None)
                        # Não sobrescrever fbc válido do Redis com None
                        **({"fbc": fbc} if fbc else {}),
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
                    # ✅ CRÍTICO: Filtrar None/vazios para não sobrescrever dados válidos no Redis
                    tracking_service.save_tracking_token(tracking_token, {k: v for k, v in tracking_update_payload.items() if v})
                    
                    logger.info("Tracking token pronto: %s | fbp=%s | fbc=%s | pageview=%s", tracking_token, 'ok' if fbp else 'missing', 'ok' if fbc else 'missing', 'ok' if pageview_event_id else 'missing')
                    
                    # ✅ CRÍTICO: Determinar status do payment
                    # Se recusado, usar 'failed' para que webhook possa atualizar
                    # Se não recusado, usar 'pending' normalmente
                    payment_status = 'failed' if is_refused else 'pending'
                    
                    # ✅ CRÍTICO: Extrair transaction_id/hash (prioridade: transaction_id > transaction_hash)
                    gateway_transaction_id = (
                        pix_result.get('transaction_id') or 
                        pix_result.get('transaction_hash') or 
                        None
                    )
                    
                    # ✅ CRÍTICO: Extrair gateway_hash (campo 'hash' da resposta) para webhook matching
                    gateway_hash = pix_result.get('gateway_hash') or pix_result.get('transaction_hash')
                    
                    # ✅ CRÍTICO: Extrair reference para matching no webhook
                    reference = pix_result.get('reference')
                    
                    # ✅ PATCH 2 QI 200: Salvar product_hash se foi criado dinamicamente
                    if gateway.gateway_type in ['atomopay', 'umbrellapag'] and payment_gateway:
                        # Verificar se product_hash foi criado dinamicamente
                        current_product_hash = getattr(payment_gateway, 'product_hash', None)
                        if current_product_hash and current_product_hash != original_product_hash:
                            gateway.product_hash = current_product_hash
                            logger.info(f"💾 Product Hash criado dinamicamente e salvo no Gateway: {current_product_hash[:12]}...")
                    
                    # ✅ CRÍTICO: Extrair producer_hash para identificar conta do usuário (multi-tenant)
                    # Salvar no Gateway para que webhook possa identificar qual usuário enviou
                    producer_hash = pix_result.get('producer_hash')
                    if producer_hash and gateway.gateway_type == 'atomopay':
                        # ✅ Salvar producer_hash no Gateway (se ainda não tiver)
                        if not gateway.producer_hash:
                            gateway.producer_hash = producer_hash
                            logger.info(f"💾 Producer Hash salvo no Gateway: {producer_hash[:12]}...")
                    
                    # ✅ PATCH 2 & 3 QI 200: Commit de todas as alterações do Gateway
                    if gateway.gateway_type in ['atomopay', 'umbrellapag']:
                        db.session.commit()
                        if gateway.gateway_type == 'atomopay':
                            logger.info(f"💾 Gateway atualizado (product_hash, producer_hash)")
                        else:
                            logger.info(f"💾 Gateway atualizado (product_hash)")
                    
                    logger.info(f"💾 Salvando Payment com dados do gateway:")
                    logger.info(f"   payment_id: {payment_id}")
                    logger.info(f"   gateway_transaction_id: {gateway_transaction_id}")
                    logger.info(f"   gateway_hash: {gateway_hash}")
                    logger.info(f"   producer_hash: {producer_hash}")  # ✅ Para identificar conta do usuário
                    logger.info(f"   reference: {reference}")
                    
                    # Salvar pagamento no banco (incluindo código PIX para reenvio + analytics)
                    payment = Payment(
                        bot_id=bot_id,
                        payment_id=payment_id,
                        gateway_type=gateway.gateway_type,
                        gateway_transaction_id=gateway_transaction_id,  # ✅ Salvar mesmo quando recusado
                        gateway_transaction_hash=gateway_hash,  # ✅ CRÍTICO: gateway_hash (campo 'hash' da resposta) para webhook matching
                        amount=amount,
                        customer_name=customer_name,
                        customer_username=customer_username,
                        customer_user_id=customer_user_id,
                        product_name=description,
                        product_description=pix_result.get('pix_code'),  # Salvar código PIX para reenvio (None se recusado)
                        status=payment_status,  # ✅ 'failed' se recusado, 'pending' se não
                        # Analytics tracking
                        order_bump_shown=order_bump_shown,
                        order_bump_accepted=order_bump_accepted,
                        order_bump_value=order_bump_value,
                        is_downsell=is_downsell,
                        downsell_index=downsell_index,
                        # ✅ DEMOGRAPHIC DATA (Copiar de bot_user se disponível, com fallback seguro)
                        customer_age=getattr(bot_user, 'customer_age', None) if bot_user else None,
                        customer_city=getattr(bot_user, 'customer_city', None) if bot_user else None,
                        customer_state=getattr(bot_user, 'customer_state', None) if bot_user else None,
                        customer_country=getattr(bot_user, 'customer_country', 'BR') if bot_user else 'BR',
                        customer_gender=getattr(bot_user, 'customer_gender', None) if bot_user else None,
                        # ✅ DEVICE DATA (Copiar de bot_user se disponível, com fallback seguro)
                        device_type=getattr(bot_user, 'device_type', None) if bot_user else None,
                        os_type=getattr(bot_user, 'os_type', None) if bot_user else None,
                        browser=getattr(bot_user, 'browser', None) if bot_user else None,
                        device_model=getattr(bot_user, 'device_model', None) if bot_user else None,
                        # ✅ CRÍTICO: UTM TRACKING E CAMPAIGN CODE (grim) - Copiar de bot_user para matching com campanha Meta
                        utm_source=getattr(bot_user, 'utm_source', None) if bot_user else None,
                        utm_campaign=getattr(bot_user, 'utm_campaign', None) if bot_user else None,
                        utm_content=getattr(bot_user, 'utm_content', None) if bot_user else None,
                        utm_medium=getattr(bot_user, 'utm_medium', None) if bot_user else None,
                        utm_term=getattr(bot_user, 'utm_term', None) if bot_user else None,
                        # ✅ CRÍTICO QI 600+: fbclid para external_id (matching Meta Pixel)
                        fbclid=fbclid,  # ✅ Usar fbclid já extraído
                        # ✅ CRÍTICO QI 600+: campaign_code (grim) para atribuição de campanha
                        # Usar campaign_code do bot_user (grim), não external_id (que agora é fbclid)
                        campaign_code=getattr(bot_user, 'campaign_code', None) if bot_user else None,
                        # ✅ QI 500: TRACKING_TOKEN V4
                        tracking_token=tracking_token,
                        # ✅ CRÍTICO: pageview_event_id para deduplicação Meta Pixel (fallback se Redis expirar)
                        pageview_event_id=pageview_event_id if pageview_event_id else None,
                        # ✅ CRÍTICO: fbp e fbc para fallback no Purchase se Redis expirar
                        fbp=fbp if fbp else None,
                        fbc=fbc if fbc else None
                    )
                    db.session.add(payment)
                    db.session.flush()  # ✅ Flush para obter payment.id antes do commit
                    
                    # ✅ QI 500: Salvar tracking data no Redis (após criar payment para ter payment.id)
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
                    
                    # ✅ ATUALIZAR CONTADOR DE TRANSAÇÕES DO GATEWAY
                    gateway.total_transactions += 1
                    
                    db.session.commit()
                    
                    logger.info(f"✅ Pagamento registrado | Nosso ID: {payment_id} | SyncPay ID: {pix_result.get('transaction_id')}")
                    
                    # NOTIFICAR VIA WEBSOCKET (tempo real - BROADCAST para todos do usuário)
                    try:
                        from app import socketio, app, send_sale_notification
                        from models import Bot
                        
                        with app.app_context():
                            bot = db.session.get(Bot, bot_id)
                            if bot:
                                # Emitir evento 'new_sale' (BROADCAST - sem room)
                                socketio.emit('new_sale', {
                                    'id': payment.id,
                                    'customer_name': customer_name,
                                    'product_name': description,
                                    'amount': float(amount),
                                    'status': 'pending',
                                    'created_at': payment.created_at.isoformat()
                                })
                                logger.info(f"📡 Evento 'new_sale' emitido - R$ {amount}")
                                
                                # ✅ NOTIFICAR VENDA PENDENTE (Push Notification - respeita configurações)
                                send_sale_notification(
                                    user_id=bot.user_id,
                                    payment=payment,
                                    status='pending'
                                )
                    except Exception as ws_error:
                        logger.warning(f"⚠️ Erro ao emitir WebSocket: {ws_error}")
                    
                    return {
                        'payment_id': payment_id,
                        'pix_code': pix_result.get('pix_code'),
                        'qr_code_url': pix_result.get('qr_code_url'),
                        'qr_code_base64': pix_result.get('qr_code_base64')
                    }
                else:
                    logger.error(f"❌ FALHA AO GERAR PIX NO GATEWAY {gateway.gateway_type.upper()}")
                    logger.error(f"   Gateway Type: {gateway.gateway_type}")
                    return None
                    
        except Exception as e:
            logger.error(f"❌ Erro ao gerar PIX: {e}")
            import traceback
            traceback.print_exc()
            return None
```

**✅ ANÁLISE:** 
- Linha 4458: `payment_status = 'failed' if is_refused else 'pending'` → ✅ **CORRETO: Status é 'pending' por padrão**
- Linha 4518: `status=payment_status` → ✅ **CORRETO: Payment é salvo como 'pending'**
- **NÃO há liberação de acesso nesta função**

---

## 📌 2️⃣ `_handle_verify_payment()` COMPLETO

```python:3051:3500:bot_manager.py
    def _handle_verify_payment(self, bot_id: int, token: str, chat_id: int, 
                               payment_id: str, user_info: Dict[str, Any]):
        """
        Verifica status do pagamento e libera acesso se pago
        
        Args:
            bot_id: ID do bot
            token: Token do bot
            chat_id: ID do chat
            payment_id: ID do pagamento
            user_info: Informações do usuário
        """
        try:
            from models import Payment, Bot, Gateway, db
            from app import app
            
            with app.app_context():
                # Buscar pagamento no banco
                payment = Payment.query.filter_by(payment_id=payment_id).first()
                
                if not payment:
                    logger.warning(f"⚠️ Pagamento não encontrado: {payment_id}")
                    self.send_telegram_message(
                        token=token,
                        chat_id=str(chat_id),
                        message="❌ Pagamento não encontrado. Entre em contato com o suporte."
                    )
                    return
                
                logger.info(f"📊 Status do pagamento LOCAL: {payment.status}")
                
                # ✅ PARADISE: Consulta manual DESATIVADA (usa apenas webhooks)
                # O job automático (check_paradise_pending_sales.py) processa pagamentos a cada 2 minutos
                # Se Paradise enviar webhook, o sistema marca automaticamente
                # Ao clicar em "Verificar Pagamento", apenas verifica o status NO BANCO
                if payment.status == 'pending':
                    # ... (código de verificação UmbrellaPay e outros gateways) ...
                
                # ✅ CRÍTICO: Recarregar objeto do banco antes de verificar status final
                db.session.refresh(payment)
                logger.info(f"📊 Status FINAL do pagamento: {payment.status}")
                
                if payment.status == 'paid':
                    # PAGAMENTO CONFIRMADO! Liberar acesso
                    logger.info(f"✅ PAGAMENTO CONFIRMADO! Liberando acesso...")
                    
                    # ============================================================================
                    # ✅ META PIXEL PURCHASE: Disparar se ainda não foi enviado
                    # ============================================================================
                    # CRÍTICO: Se pagamento foi confirmado via webhook ANTES do botão verify,
                    # o Meta Pixel pode não ter sido disparado. Verificar e disparar se necessário.
                    if not payment.meta_purchase_sent:
                        try:
                            from app import send_meta_pixel_purchase_event
                            logger.info(f"📊 Disparando Meta Pixel Purchase para {payment.payment_id} (via botão verify)")
                            send_meta_pixel_purchase_event(payment)
                            logger.info(f"✅ Meta Pixel Purchase enviado via botão verify")
                        except Exception as e:
                            logger.error(f"❌ Erro ao enviar Meta Purchase via botão verify: {e}", exc_info=True)
                    else:
                        logger.info(f"ℹ️ Meta Pixel Purchase já foi enviado anteriormente (meta_purchase_sent=True)")
                    
                    # Cancelar downsells agendados
                    self.cancel_downsells(payment.payment_id)
                    
                    bot = payment.bot
                    bot_config = self.active_bots.get(bot_id, {}).get('config', {})
                    access_link = bot_config.get('access_link', '')
                    custom_success_message = bot_config.get('success_message', '').strip()
                    
                    # Usar mensagem personalizada ou padrão
                    if custom_success_message:
                        # Substituir variáveis
                        success_message = custom_success_message
                        success_message = success_message.replace('{produto}', payment.product_name or 'Produto')
                        success_message = success_message.replace('{valor}', f'R$ {payment.amount:.2f}')
                        success_message = success_message.replace('{link}', access_link or 'Link não configurado')
                    elif access_link:
                        success_message = f"""
✅ <b>PAGAMENTO CONFIRMADO!</b>

🎉 <b>Parabéns!</b> Seu pagamento foi aprovado com sucesso!

🎯 <b>Produto:</b> {payment.product_name}
💰 <b>Valor pago:</b> R$ {payment.amount:.2f}

🔗 <b>Seu acesso:</b>
{access_link}

<b>Aproveite!</b> 🚀
                        """
                    else:
                        success_message = "✅ Pagamento confirmado! Entre em contato com o suporte para receber seu acesso."
                    
                    self.send_telegram_message(
                        token=token,
                        chat_id=str(chat_id),
                        message=success_message.strip()
                    )
                    
                    logger.info(f"✅ Acesso liberado para {user_info.get('first_name')}")
                else:
                    # PAGAMENTO AINDA PENDENTE
                    logger.info(f"⏳ Pagamento ainda pendente...")
                    # ... (código de mensagem pendente) ...
        
        except Exception as e:
            logger.error(f"❌ Erro ao verificar pagamento: {e}")
            import traceback
            traceback.print_exc()
```

**✅ ANÁLISE:**
- Linha 3373: `if payment.status == 'paid':` → ✅ **CORRETO: Só libera se status for 'paid'**
- **NÃO há problema aqui**

---

## 📌 3️⃣ Função que Envia "Pagamento Confirmado!"

**Localização:** `_handle_verify_payment()` linhas 3373-3429

```python:3373:3429:bot_manager.py
                if payment.status == 'paid':
                    # PAGAMENTO CONFIRMADO! Liberar acesso
                    logger.info(f"✅ PAGAMENTO CONFIRMADO! Liberando acesso...")
                    
                    # ============================================================================
                    # ✅ META PIXEL PURCHASE: Disparar se ainda não foi enviado
                    # ============================================================================
                    # CRÍTICO: Se pagamento foi confirmado via webhook ANTES do botão verify,
                    # o Meta Pixel pode não ter sido disparado. Verificar e disparar se necessário.
                    if not payment.meta_purchase_sent:
                        try:
                            from app import send_meta_pixel_purchase_event
                            logger.info(f"📊 Disparando Meta Pixel Purchase para {payment.payment_id} (via botão verify)")
                            send_meta_pixel_purchase_event(payment)
                            logger.info(f"✅ Meta Pixel Purchase enviado via botão verify")
                        except Exception as e:
                            logger.error(f"❌ Erro ao enviar Meta Purchase via botão verify: {e}", exc_info=True)
                    else:
                        logger.info(f"ℹ️ Meta Pixel Purchase já foi enviado anteriormente (meta_purchase_sent=True)")
                    
                    # Cancelar downsells agendados
                    self.cancel_downsells(payment.payment_id)
                    
                    bot = payment.bot
                    bot_config = self.active_bots.get(bot_id, {}).get('config', {})
                    access_link = bot_config.get('access_link', '')
                    custom_success_message = bot_config.get('success_message', '').strip()
                    
                    # Usar mensagem personalizada ou padrão
                    if custom_success_message:
                        # Substituir variáveis
                        success_message = custom_success_message
                        success_message = success_message.replace('{produto}', payment.product_name or 'Produto')
                        success_message = success_message.replace('{valor}', f'R$ {payment.amount:.2f}')
                        success_message = success_message.replace('{link}', access_link or 'Link não configurado')
                    elif access_link:
                        success_message = f"""
✅ <b>PAGAMENTO CONFIRMADO!</b>

🎉 <b>Parabéns!</b> Seu pagamento foi aprovado com sucesso!

🎯 <b>Produto:</b> {payment.product_name}
💰 <b>Valor pago:</b> R$ {payment.amount:.2f}

🔗 <b>Seu acesso:</b>
{access_link}

<b>Aproveite!</b> 🚀
                        """
                    else:
                        success_message = "✅ Pagamento confirmado! Entre em contato com o suporte para receber seu acesso."
                    
                    self.send_telegram_message(
                        token=token,
                        chat_id=str(chat_id),
                        message=success_message.strip()
                    )
                    
                    logger.info(f"✅ Acesso liberado para {user_info.get('first_name')}")
```

**✅ ANÁLISE:**
- Linha 3373: `if payment.status == 'paid':` → ✅ **CORRETO: Só envia se status for 'paid'**
- **NÃO há problema aqui**

---

## 📌 4️⃣ Função que Libera Entregável/Acesso

**Localização:** `app.py` linhas 320-394

```python:320:394:app.py
# ==================== FUNÇÃO CENTRALIZADA: ENVIO DE ENTREGÁVEL ====================
def send_payment_delivery(payment, bot_manager):
    """
    Envia entregável (link de acesso ou confirmação) ao cliente após pagamento confirmado
    
    Args:
        payment: Objeto Payment com status='paid'
        bot_manager: Instância do BotManager para enviar mensagem
    
    Returns:
        bool: True se enviado com sucesso, False se houve erro
    """
    try:
        if not payment or not payment.bot:
            logger.warning(f"⚠️ Payment ou bot inválido para envio de entregável: payment={payment}")
            return False
        
        if not payment.bot.token:
            logger.error(f"❌ Bot {payment.bot_id} não tem token configurado - não é possível enviar entregável")
            return False
        
        # ✅ VALIDAÇÃO CRÍTICA: Verificar se customer_user_id é válido
        if not payment.customer_user_id or str(payment.customer_user_id).strip() == '':
            logger.error(f"❌ Payment {payment.id} não tem customer_user_id válido ({payment.customer_user_id}) - não é possível enviar")
            return False
        
        # Verificar se bot tem config e access_link
        has_access_link = payment.bot.config and payment.bot.config.access_link
        
        if has_access_link:
            access_link = payment.bot.config.access_link
            # Mensagem completa com link
            access_message = f"""
✅ <b>Pagamento Confirmado!</b>

🎉 Parabéns! Seu pagamento foi aprovado!

🎯 <b>Produto:</b> {payment.product_name}
💰 <b>Valor:</b> R$ {payment.amount:.2f}

🔗 <b>Seu acesso:</b>
{access_link}

Aproveite! 🚀
            """
        else:
            # Mensagem genérica sem link (bot não configurou access_link)
            access_message = f"""
✅ <b>Pagamento Confirmado!</b>

🎉 Parabéns! Seu pagamento foi aprovado!

🎯 <b>Produto:</b> {payment.product_name}
💰 <b>Valor:</b> R$ {payment.amount:.2f}

📧 Entre em contato com o suporte para receber seu acesso.
            """
            logger.warning(f"⚠️ Bot {payment.bot_id} não tem access_link configurado - enviando mensagem genérica")
        
        # Enviar via bot manager e capturar exceção se falhar
        try:
            bot_manager.send_telegram_message(
                token=payment.bot.token,
                chat_id=str(payment.customer_user_id),
                message=access_message.strip()
            )
            logger.info(f"✅ Entregável enviado para {payment.customer_name} (payment_id: {payment.id}, bot_id: {payment.bot_id})")
            return True
        except Exception as send_error:
            # Erro ao enviar mensagem (bot bloqueado, chat_id inválido, etc)
            logger.error(f"❌ Erro ao enviar mensagem Telegram para payment {payment.id}: {send_error}")
            return False
        
    except Exception as e:
        logger.error(f"❌ Erro ao enviar entregável para payment {payment.id if payment else 'None'}: {e}", exc_info=True)
        return False
```

**✅ ANÁLISE:**
- **NÃO há validação de `payment.status == 'paid'` nesta função!**
- **🚨 PROBLEMA IDENTIFICADO:** A função `send_payment_delivery` não verifica se `payment.status == 'paid'` antes de enviar!

---

## 🔍 ONDE `send_payment_delivery` É CHAMADA?

**Localizações encontradas:**
1. `tasks_async.py` linha 814 e 907 - No processamento de webhooks
2. `app.py` linha 518 e 629 - Nos reconciliadores de pagamentos
3. `app.py` linha 8115 e 8228 - Em outras rotas

**🚨 PROBLEMA CRÍTICO IDENTIFICADO:**

A função `send_payment_delivery` **NÃO VALIDA** se `payment.status == 'paid'` antes de enviar o entregável!

**Código atual (app.py linha 320-394):**
```python
def send_payment_delivery(payment, bot_manager):
    """
    Envia entregável (link de acesso ou confirmação) ao cliente após pagamento confirmado
    
    Args:
        payment: Objeto Payment com status='paid'  # ⚠️ DOCUMENTAÇÃO DIZ 'paid', MAS NÃO VALIDA!
        bot_manager: Instância do BotManager para enviar mensagem
    """
    try:
        if not payment or not payment.bot:
            logger.warning(f"⚠️ Payment ou bot inválido para envio de entregável: payment={payment}")
            return False
        
        # ❌ FALTA: if payment.status != 'paid': return False
        
        # ... resto do código envia mensagem SEM VALIDAR STATUS ...
```

**🔥 CAUSA RAIZ DO BUG:**

Se `send_payment_delivery` for chamada com um `payment` que tem `status='pending'` (por exemplo, se houver um bug no webhook ou se o payment for passado incorretamente), ela **VAI ENVIAR O ACESSO MESMO ASSIM**!

**✅ CORREÇÃO NECESSÁRIA:**

Adicionar validação de status no início de `send_payment_delivery`:

```python
def send_payment_delivery(payment, bot_manager):
    """
    Envia entregável (link de acesso ou confirmação) ao cliente após pagamento confirmado
    
    Args:
        payment: Objeto Payment com status='paid'
        bot_manager: Instância do BotManager para enviar mensagem
    """
    try:
        if not payment or not payment.bot:
            logger.warning(f"⚠️ Payment ou bot inválido para envio de entregável: payment={payment}")
            return False
        
        # ✅ CRÍTICO: Validar status ANTES de enviar
        if payment.status != 'paid':
            logger.warning(f"⚠️ Tentativa de enviar entregável para payment {payment.id} com status '{payment.status}' (esperado: 'paid')")
            logger.warning(f"   Payment ID: {payment.payment_id}")
            logger.warning(f"   Status atual: {payment.status}")
            return False
        
        # ... resto do código ...
```

---

## 📊 RESUMO DA ANÁLISE

### ✅ O QUE ESTÁ CORRETO:

1. **`_generate_pix_payment()`** - ✅ Salva payment com `status='pending'` (linha 4458, 4518)
2. **`_handle_verify_payment()`** - ✅ Só libera acesso se `payment.status == 'paid'` (linha 3373)
3. **Fluxo após gerar PIX** - ✅ Apenas envia mensagem com código PIX, não libera acesso

### 🚨 O QUE ESTÁ ERRADO:

1. **`send_payment_delivery()`** - ❌ **NÃO VALIDA** se `payment.status == 'paid'` antes de enviar!
2. **Risco:** Se esta função for chamada com `payment.status='pending'`, ela **VAI ENVIAR O ACESSO MESMO ASSIM**!

### 🔥 CONCLUSÃO:

O bug está na função `send_payment_delivery()` que não valida o status do pagamento antes de enviar o entregável. Se ela for chamada incorretamente (por exemplo, se houver um bug no webhook que passa um payment pendente), o acesso será liberado indevidamente.
<｜tool▁calls▁begin｜><｜tool▁call▁begin｜>
grep
