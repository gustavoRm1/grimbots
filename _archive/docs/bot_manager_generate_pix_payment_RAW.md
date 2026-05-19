```python
def _generate_pix_payment(self, bot_id: int, amount: float, description: str,
                         customer_name: str, customer_username: str, customer_user_id: str,
                         order_bump_shown: bool = False, order_bump_accepted: bool = False, 
                         order_bump_value: float = 0.0, is_downsell: bool = False, 
                         downsell_index: int = None,
                         is_upsell: bool = False,  # ✅ NOVO - UPSELLS
                         upsell_index: int = None,  # ✅ NOVO - UPSELLS
                         is_remarketing: bool = False,  # ✅ NOVO - REMARKETING
                         remarketing_campaign_id: int = None,  # ✅ NOVO - REMARKETING
                         button_index: int = None,  # ✅ NOVO - SISTEMA DE ASSINATURAS
                         button_config: dict = None) -> Optional[Dict[str, Any]]:  # ✅ NOVO - SISTEMA DE ASSINATURAS
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
        from sqlalchemy.exc import IntegrityError
        
        with app.app_context():
            # Buscar bot e gateway
            bot = db.session.get(Bot, bot_id)
            if not bot:
                logger.error(f"Bot {bot_id} não encontrado")
                return None
            
            # Buscar gateway ativo e verificado do usuário
            # ✅ CORREÇÃO: Filtrar também por gateway_type se necessário, mas permitir qualquer gateway ativo
            gateway = Gateway.query.filter_by(
                user_id=bot.user_id,
                is_active=True,
                is_verified=True
            ).first()
            
            if not gateway:
                logger.error(f"❌ Nenhum gateway ativo encontrado para usuário {bot.user_id} | Bot: {bot_id}")
                logger.error(f"   Verifique se há um gateway configurado e ativo em /settings")
                return None
            
            logger.info(f"💳 Gateway: {gateway.gateway_type.upper()} | Gateway ID: {gateway.id} | User ID: {bot.user_id}")
            
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
            
            # ✅ CRÍTICO: Extrair credenciais e validar ANTES de criar gateway
            # Se descriptografia falhar, properties retornam None
            # IMPORTANTE: Acessar properties explicitamente para forçar descriptografia e capturar exceções
            try:
                api_key = gateway.api_key
                # ✅ LOG ESPECÍFICO PARA WIINPAY
                if gateway.gateway_type == 'wiinpay':
                    if api_key:
                        logger.info(f"✅ [WiinPay] api_key descriptografada com sucesso (len={len(api_key)})")
                    else:
                        logger.warning(f"⚠️ [WiinPay] api_key retornou None (campo interno existe: {bool(gateway._api_key)})")
            except Exception as decrypt_error:
                logger.error(f"❌ ERRO CRÍTICO ao acessar gateway.api_key (gateway {gateway.id}): {decrypt_error}")
                logger.error(f"   Tipo do gateway: {gateway.gateway_type}")
                logger.error(f"   Isso indica que a descriptografia está FALHANDO com exceção")
                api_key = None
                # ✅ LOG ESPECÍFICO PARA WIINPAY
                if gateway.gateway_type == 'wiinpay':
                    logger.error(f"❌ [WiinPay] ERRO CRÍTICO na descriptografia da api_key!")
                    logger.error(f"   Gateway ID: {gateway.id} | User ID: {gateway.user_id}")
                    logger.error(f"   Campo interno existe: {bool(gateway._api_key)}")
                    logger.error(f"   Exceção: {decrypt_error}")
                    logger.error(f"   SOLUÇÃO: Reconfigure o gateway WiinPay com a api_key correta em /settings")
            
            try:
                client_secret = gateway.client_secret
            except Exception as decrypt_error:
                logger.error(f"❌ ERRO CRÍTICO ao acessar gateway.client_secret (gateway {gateway.id}): {decrypt_error}")
                client_secret = None
            
            try:
                product_hash = gateway.product_hash
            except Exception as decrypt_error:
                logger.error(f"❌ ERRO CRÍTICO ao acessar gateway.product_hash (gateway {gateway.id}): {decrypt_error}")
                product_hash = None
            
            try:
                split_user_id = gateway.split_user_id
            except Exception as decrypt_error:
                logger.error(f"❌ ERRO CRÍTICO ao acessar gateway.split_user_id (gateway {gateway.id}): {decrypt_error}")
                split_user_id = None
            
            # ✅ CORREÇÃO CRÍTICA: WiinPay - SEMPRE usar ID da plataforma para split
            # O split_user_id NUNCA deve ser o mesmo user_id da api_key (conta de recebimento)
            # Isso causa erro 422: "A conta de split não pode ser a mesma conta de recebimento"
            if gateway.gateway_type == 'wiinpay':
                platform_split_id = '68ffcc91e23263e0a01fffa4'  # ID da plataforma
                old_id = '6877edeba3c39f8451ba5bdd'  # ID antigo (também inválido)
                
                # ✅ Extrair user_id da api_key (JWT) para validar
                try:
                    import jwt
                    import json
                    # Decodificar JWT sem verificar assinatura (apenas para ler payload)
                    decoded = jwt.decode(api_key, options={"verify_signature": False}) if api_key else {}
                    api_key_user_id = decoded.get('userId') or decoded.get('user_id') or ''
                    logger.info(f"🔍 [WiinPay] user_id da api_key (JWT): {api_key_user_id}")
                except Exception as jwt_error:
                    api_key_user_id = None
                    logger.warning(f"⚠️ [WiinPay] Não foi possível extrair user_id do JWT: {jwt_error}")
                
                # ✅ FORÇAR: Sempre usar ID da plataforma, nunca o user_id do usuário
                if not split_user_id or split_user_id == old_id or split_user_id.strip() == '':
                    logger.info(f"✅ [WiinPay] split_user_id vazio/antigo, usando ID da plataforma: {platform_split_id}")
                    split_user_id = platform_split_id
                elif split_user_id == api_key_user_id:
                    logger.warning(f"⚠️ [WiinPay] split_user_id é o mesmo da conta de recebimento ({api_key_user_id})!")
                    logger.warning(f"   Isso causará erro 422. Forçando ID da plataforma: {platform_split_id}")
                    split_user_id = platform_split_id
                elif split_user_id != platform_split_id:
                    logger.warning(f"⚠️ [WiinPay] split_user_id diferente do ID da plataforma: {split_user_id}")
                    logger.warning(f"   Esperado: {platform_split_id} | Usando: {split_user_id}")
                    logger.warning(f"   Forçando ID da plataforma para garantir split correto")
                    split_user_id = platform_split_id
                else:
                    logger.info(f"✅ [WiinPay] split_user_id correto (ID da plataforma): {split_user_id}")
            
            # ✅ VALIDAÇÃO: Verificar se credenciais foram descriptografadas corretamente
            # Se alguma propriedade retornar None mas o campo interno existir, significa erro de descriptografia
            encryption_error_detected = False
            
            if gateway._api_key and not api_key:
                logger.error(f"❌ CRÍTICO: Erro ao descriptografar api_key do gateway {gateway.id}")
                logger.error(f"   Campo interno existe: {gateway._api_key[:30] if gateway._api_key else 'None'}...")
                logger.error(f"   Property retornou: {api_key}")
                logger.error(f"   POSSÍVEL CAUSA: ENCRYPTION_KEY foi alterada após salvar credenciais")
                logger.error(f"   SOLUÇÃO: Reconfigure o gateway {gateway.gateway_type} com as credenciais corretas")
                logger.error(f"   Gateway ID: {gateway.id} | Tipo: {gateway.gateway_type} | User: {gateway.user_id}")
                encryption_error_detected = True
            
            if gateway._client_secret and not client_secret:
                logger.error(f"❌ CRÍTICO: Erro ao descriptografar client_secret do gateway {gateway.id}")
                logger.error(f"   Campo interno existe: {gateway._client_secret[:30] if gateway._client_secret else 'None'}...")
                logger.error(f"   Property retornou: {client_secret}")
                logger.error(f"   POSSÍVEL CAUSA: ENCRYPTION_KEY foi alterada após salvar credenciais")
                logger.error(f"   SOLUÇÃO: Reconfigure o gateway {gateway.gateway_type} com as credenciais corretas")
                logger.error(f"   Gateway ID: {gateway.id} | Tipo: {gateway.gateway_type} | User: {gateway.user_id}")
                encryption_error_detected = True
            
            if gateway._product_hash and not product_hash:
                logger.error(f"❌ CRÍTICO: Erro ao descriptografar product_hash do gateway {gateway.id}")
                logger.error(f"   Campo interno existe: {gateway._product_hash[:30] if gateway._product_hash else 'None'}...")
                logger.error(f"   Property retornou: {product_hash}")
                logger.error(f"   POSSÍVEL CAUSA: ENCRYPTION_KEY foi alterada após salvar credenciais")
                logger.error(f"   SOLUÇÃO: Reconfigure o gateway {gateway.gateway_type} com as credenciais corretas")
                encryption_error_detected = True
            
            if gateway._split_user_id and not split_user_id and gateway.gateway_type == 'wiinpay':
                logger.warning(f"⚠️ WiinPay: split_user_id não descriptografado (pode ser normal se não configurado)")
            
            # ✅ Se detectou erro de descriptografia, retornar None imediatamente
            if encryption_error_detected:
                logger.error(f"❌ ERRO DE DESCRIPTOGRAFIA DETECTADO - Payment NÃO será criado")
                logger.error(f"   ACÃO NECESSÁRIA: Reconfigure o gateway {gateway.gateway_type} (ID: {gateway.id}) em /settings")
                return None
            
            credentials = {
                # SyncPay usa client_id/client_secret
                'client_id': gateway.client_id,
                'client_secret': client_secret,
                # Outros gateways usam api_key
                'api_key': api_key,
                # ✅ Átomo Pay: api_token é salvo em api_key no banco, mas precisa ser passado como api_token
                'api_token': api_key if gateway.gateway_type == 'atomopay' else None,
                # ✅ Babylon: company_id é salvo em client_id no banco
                'company_id': gateway.client_id if gateway.gateway_type == 'babylon' else None,
                # Paradise
                'product_hash': product_hash,
                'offer_hash': gateway.offer_hash,
                'store_id': gateway.store_id,
                # WiinPay
                'split_user_id': split_user_id,
                # ✅ RANKING V2.0: Usar taxa do usuário (pode ser premium)
                'split_percentage': user_commission
            }
            
            # ✅ VALIDAÇÃO ESPECÍFICA POR GATEWAY: Verificar credenciais obrigatórias
            if gateway.gateway_type == 'paradise':
                if not api_key:
                    logger.error(f"❌ Paradise: api_key ausente ou não descriptografado")
                    return None
                if not product_hash:
                    logger.error(f"❌ Paradise: product_hash ausente ou não descriptografado")
                    return None
            elif gateway.gateway_type == 'atomopay':
                if not api_key:
                    logger.error(f"❌ Átomo Pay: api_token (api_key) ausente ou não descriptografado")
                    logger.error(f"   gateway.id: {gateway.id}")
                    return None
                else:
                    logger.debug(f"🔑 Átomo Pay: api_token presente ({len(api_key)} caracteres)")
            elif gateway.gateway_type == 'syncpay':
                # ✅ SyncPay usa client_id/client_secret, NÃO api_key
                if not client_secret:
                    logger.error(f"❌ SyncPay: client_secret ausente ou não descriptografado")
                    logger.error(f"   Gateway ID: {gateway.id} | User: {gateway.user_id}")
                    if gateway._client_secret:
                        logger.error(f"   Campo interno existe mas descriptografia falhou!")
                        logger.error(f"   POSSÍVEL CAUSA: ENCRYPTION_KEY foi alterada após salvar credenciais")
                    return None
                if not gateway.client_id:
                    logger.error(f"❌ SyncPay: client_id ausente")
                    logger.error(f"   Gateway ID: {gateway.id} | User: {gateway.user_id}")
                    return None
            elif gateway.gateway_type in ['pushynpay', 'wiinpay']:
                if not api_key:
                    logger.error(f"❌ {gateway.gateway_type.upper()}: api_key ausente ou não descriptografado")
                    logger.error(f"   Gateway ID: {gateway.id} | User: {gateway.user_id} | Tipo: {gateway.gateway_type}")
                    if gateway._api_key:
                        logger.error(f"   ❌ Campo interno existe mas descriptografia falhou!")
                        logger.error(f"   Campo interno (primeiros 30 chars): {gateway._api_key[:30] if gateway._api_key else 'None'}...")
                        logger.error(f"   POSSÍVEL CAUSA: ENCRYPTION_KEY foi alterada após salvar credenciais")
                        logger.error(f"   SOLUÇÃO CRÍTICA: Reconfigure o gateway {gateway.gateway_type.upper()} (ID: {gateway.id}) em /settings")
                        logger.error(f"   Passo a passo:")
                        logger.error(f"   1. Acesse /settings")
                        logger.error(f"   2. Encontre o gateway {gateway.gateway_type.upper()} (ID: {gateway.id})")
                        logger.error(f"   3. Reinsira a api_key do gateway")
                        logger.error(f"   4. Salve as configurações")
                    else:
                        logger.error(f"   Campo interno (_api_key) também está vazio - gateway não foi configurado corretamente")
                        logger.error(f"   SOLUÇÃO: Configure o gateway {gateway.gateway_type.upper()} em /settings")
                    return None
            elif gateway.gateway_type == 'babylon':
                # ✅ BABYLON requer: api_key (Secret Key) + client_id (Company ID)
                if not api_key:
                    logger.error(f"❌ BABYLON: api_key (Secret Key) ausente ou não descriptografado")
                    logger.error(f"   Gateway ID: {gateway.id} | User: {gateway.user_id}")
                    if gateway._api_key:
                        logger.error(f"   ❌ Campo interno existe mas descriptografia falhou!")
                        logger.error(f"   POSSÍVEL CAUSA: ENCRYPTION_KEY foi alterada após salvar credenciais")
                        logger.error(f"   SOLUÇÃO: Reconfigure o gateway Babylon (ID: {gateway.id}) em /settings")
                    return None
                if not gateway.client_id:
                    logger.error(f"❌ BABYLON: client_id (Company ID) ausente")
                    logger.error(f"   Gateway ID: {gateway.id} | User: {gateway.user_id}")
                    logger.error(f"   SOLUÇÃO: Configure o Company ID no gateway Babylon em /settings")
                    return None
            
            # Log para auditoria (apenas se for premium)
            if user_commission < 2.0:
                logger.info(f"🏆 TAXA PREMIUM aplicada: {user_commission}% (User {bot.owner.id})")
            
            # ✅ PATCH 2 QI 200: Garantir que product_hash existe antes de usar
            # Se gateway não tem product_hash, será criado dinamicamente no generate_pix
            # Mas precisamos garantir que será salvo no banco após criação
            original_product_hash = gateway.product_hash
            
            # Gerar PIX via gateway (usando Factory Pattern)
            logger.info(f"🔧 Criando gateway {gateway.gateway_type} com credenciais...")
            
            # ✅ LOG DETALHADO PARA WIINPAY
            if gateway.gateway_type == 'wiinpay':
                logger.info(f"🔍 [WiinPay Debug] Criando gateway com:")
                logger.info(f"   - api_key presente: {bool(api_key)}")
                logger.info(f"   - api_key length: {len(api_key) if api_key else 0}")
                logger.info(f"   - split_user_id: {split_user_id}")
                logger.info(f"   - split_percentage: {user_commission}%")
                logger.info(f"   - credentials keys: {list(credentials.keys())}")
            
            payment_gateway = GatewayFactory.create_gateway(
                gateway_type=gateway.gateway_type,
                credentials=credentials
            )
            
            if not payment_gateway:
                logger.error(f"❌ Erro ao criar gateway {gateway.gateway_type}")
                if gateway.gateway_type == 'wiinpay':
                    logger.error(f"   WIINPAY: Gateway não foi criado - verifique:")
                    logger.error(f"   1. api_key foi descriptografada corretamente: {bool(api_key)}")
                    logger.error(f"   2. Gateway está ativo e verificado: is_active={gateway.is_active}, is_verified={gateway.is_verified}")
                    logger.error(f"   3. Verifique logs anteriores para erros de descriptografia")
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
            # ✅ CRÍTICO: Preparar customer_data ANTES de gerar PIX (para usar depois ao salvar Payment)
            customer_data = {
                'name': customer_name or 'Cliente',
                'email': f"{customer_username}@telegram.user" if customer_username else f"user{customer_user_id}@telegram.user",
                'phone': customer_user_id,  # ✅ User ID do Telegram como identificador único
                'document': customer_user_id  # ✅ User ID do Telegram (gateways aceitam)
            }
            pix_result = payment_gateway.generate_pix(
                amount=amount,
                description=description,
                payment_id=payment_id,
                customer_data=customer_data
            )
            
            logger.info(f"📊 Resultado do PIX: {pix_result}")
            
            # ✅ CORREÇÃO ROBUSTA: Se Payment foi criado mas gateway retornou None, marcar como 'pending_verification'
            if not pix_result:
                # ✅ Log detalhado para WiinPay especificamente
                if gateway.gateway_type == 'wiinpay':
                    logger.error(f"❌ WIINPAY: generate_pix retornou None!")
                    logger.error(f"   Bot ID: {bot_id} | Gateway ID: {gateway.id} | User ID: {bot.user_id}")
                    logger.error(f"   Valor: R$ {amount:.2f} | Descrição: {description}")
                    logger.error(f"   api_key presente: {bool(api_key)}")
                    logger.error(f"   split_user_id: {split_user_id}")
                    logger.error(f"   split_percentage: {user_commission}%")
                    logger.error(f"   Verifique os logs acima para ver se a API da WiinPay retornou algum erro")
                
                # ✅ Verificar se Payment foi criado antes de retornar None
                if 'payment' in locals() and payment:
                    try:
                        logger.warning(f"⚠️ [GATEWAY RETORNOU NONE] Gateway {gateway.gateway_type} retornou None")
                        logger.warning(f"   Bot: {bot_id}, Valor: R$ {amount:.2f}, Payment ID: {payment.payment_id}")
                        logger.warning(f"   Payment será marcado como 'pending_verification' para não perder venda")
                        
                        payment.status = 'pending_verification'
                        payment.gateway_transaction_id = None
                        payment.product_description = None
                        db.session.commit()
                        
                        logger.warning(f"⚠️ Payment {payment.id} marcado como 'pending_verification' (gateway retornou None)")
                        return {'status': 'pending_verification', 'payment_id': payment.payment_id, 'error': 'Gateway retornou None'}
                    except Exception as commit_error:
                        logger.error(f"❌ Erro ao commitar Payment após gateway retornar None: {commit_error}", exc_info=True)
                        db.session.rollback()
                        return None
                else:
                    # ✅ Payment não foi criado - retornar None normalmente
                    logger.error(f"❌ Gateway retornou None e Payment não foi criado")
                    return None
            
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
                if not is_remarketing:
                    tracking_token = None

                # ✅ CORREÇÃO CRÍTICA QI 1000+: PRIORIDADE MÁXIMA para bot_user.tracking_session_id
                # Isso garante que o token do public_redirect seja SEMPRE usado (tem todos os dados: client_ip, client_user_agent, pageview_event_id)
                # PROBLEMA IDENTIFICADO: Verificação estava DEPOIS de tracking:last_token e tracking:chat
                # SOLUÇÃO: Verificar bot_user.tracking_session_id PRIMEIRO (antes de tudo)
                # ✅ CORREÇÃO CRÍTICA V15: Se token gerado detectado, tentar recuperar token UUID correto via fbclid
                if is_remarketing:
                    if bot_user and bot_user.tracking_session_id:
                        tracking_token = bot_user.tracking_session_id
                        logger.info(f"✅ [REMARKETING] Forçando tracking_token do BotUser.tracking_session_id: {tracking_token[:20]}...")
                    else:
                        tracking_token = None
                        logger.error(f"❌ [REMARKETING] BotUser sem tracking_session_id - Payment será criado sem tracking_token (atribuição prejudicada)")
                elif bot_user and bot_user.tracking_session_id and not is_remarketing:
                    tracking_token = bot_user.tracking_session_id
                    logger.info(f"✅ Tracking token recuperado de bot_user.tracking_session_id (PRIORIDADE MÁXIMA): {tracking_token[:20]}...")
                    
                    # ✅ CORREÇÃO CRÍTICA V15: Validar se token é gerado e tentar recuperar token UUID correto
                    is_generated_token = tracking_token.startswith('tracking_')
                    if is_generated_token:
                        logger.error(f"❌ [GENERATE PIX] bot_user.tracking_session_id contém token GERADO: {tracking_token[:30]}...")
                        logger.error(f"   Token gerado não tem dados do redirect (client_ip, client_user_agent, pageview_event_id)")
                        logger.error(f"   Tentando recuperar token UUID correto via fbclid...")
                        
                        # ✅ ESTRATÉGIA DE RECUPERAÇÃO: Tentar recuperar token UUID via fbclid
                        if bot_user and getattr(bot_user, 'fbclid', None):
                            try:
                                fbclid_from_botuser = bot_user.fbclid
                                tracking_token_key = f"tracking:fbclid:{fbclid_from_botuser}"
                                recovered_token_from_fbclid = tracking_service.redis.get(tracking_token_key)
                                if recovered_token_from_fbclid:
                                    # ✅ Validar que token recuperado é UUID (não gerado)
                                    # ✅ CORREÇÃO: Aceitar UUID com ou sem hífens
                                    normalized_recovered = recovered_token_from_fbclid.replace('-', '').lower()
                                    is_recovered_uuid = len(normalized_recovered) == 32 and all(c in '0123456789abcdef' for c in normalized_recovered)
                                    if is_recovered_uuid:
                                        tracking_token = recovered_token_from_fbclid
                                        logger.info(f"✅ [GENERATE PIX] Token UUID correto recuperado via fbclid: {tracking_token[:20]}...")
                                        logger.info(f"   Atualizando bot_user.tracking_session_id com token UUID correto")
                                        bot_user.tracking_session_id = tracking_token
                                    else:
                                        logger.warning(f"⚠️ [GENERATE PIX] Token recuperado via fbclid tem formato inválido: {recovered_token_from_fbclid[:30]}... (len={len(recovered_token_from_fbclid)}) - IGNORANDO")
                            except Exception as e:
                                logger.warning(f"⚠️ Erro ao recuperar token UUID via fbclid: {e}")
                        else:
                            logger.warning(f"⚠️ [GENERATE PIX] bot_user.fbclid ausente - não é possível recuperar token UUID correto")
                    
                    # ✅ Tentar recuperar payload completo do Redis
                    try:
                        recovered_payload = tracking_service.recover_tracking_data(tracking_token) or {}
                        if recovered_payload:
                            redis_tracking_payload = recovered_payload
                            logger.info(f"✅ Tracking payload recuperado do bot_user.tracking_session_id: fbp={'✅' if recovered_payload.get('fbp') else '❌'}, fbc={'✅' if recovered_payload.get('fbc') else '❌'}, ip={'✅' if recovered_payload.get('client_ip') else '❌'}, ua={'✅' if recovered_payload.get('client_user_agent') else '❌'}, pageview_event_id={'✅' if recovered_payload.get('pageview_event_id') else '❌'}")
                    except Exception as e:
                        logger.warning(f"⚠️ Erro ao recuperar payload do bot_user.tracking_session_id: {e}")
                elif bot_user:
                    logger.warning(f"⚠️ BotUser {bot_user.id} encontrado mas tracking_session_id está vazio (telegram_user_id: {customer_user_id})")

                # ✅ FALLBACK 1: tracking:last_token (se bot_user.tracking_session_id não existir)
                # ✅ CORREÇÃO CRÍTICA V16: Validar token ANTES de usar
                if not is_remarketing and not tracking_token and customer_user_id:
                    try:
                        cached_token = tracking_service.redis.get(f"tracking:last_token:user:{customer_user_id}")
                        if cached_token:
                            # ✅ CORREÇÃO V16: Validar token antes de usar
                            is_generated_token = cached_token.startswith('tracking_')
                            # ✅ CORREÇÃO: Aceitar UUID com ou sem hífens
                            normalized_cached = cached_token.replace('-', '').lower()
                            is_uuid_token = len(normalized_cached) == 32 and all(c in '0123456789abcdef' for c in normalized_cached)
                            
                            if is_generated_token:
                                logger.error(f"❌ [GENERATE PIX] Token recuperado de tracking:last_token é GERADO: {cached_token[:30]}... - IGNORANDO")
                                logger.error(f"   Token gerado não tem dados do redirect (client_ip, client_user_agent, pageview_event_id)")
                                # ✅ NÃO usar token gerado
                            elif is_uuid_token:
                                tracking_token = cached_token
                                logger.info(f"✅ Tracking token recuperado de tracking:last_token:user:{customer_user_id}: {tracking_token[:20]}...")
                            else:
                                logger.warning(f"⚠️ [GENERATE PIX] Token recuperado de tracking:last_token tem formato inválido: {cached_token[:30]}... (len={len(cached_token)}) - IGNORANDO")
                    except Exception:
                        logger.exception("Falha ao recuperar tracking:last_token do Redis")
                
                # ✅ FALLBACK 2: tracking:chat (se bot_user.tracking_session_id não existir)
                # ✅ CORREÇÃO CRÍTICA V16: Validar token ANTES de usar
                # ✅ REGRA: Remarketing NÃO pode gerar/substituir tracking_token aqui
                if not is_remarketing and not tracking_token and customer_user_id:
                    try:
                        cached_payload = tracking_service.redis.get(f"tracking:chat:{customer_user_id}")
                        if cached_payload:
                            redis_tracking_payload = json.loads(cached_payload)
                            recovered_token_from_chat = redis_tracking_payload.get("tracking_token")
                            if recovered_token_from_chat:
                                # ✅ CORREÇÃO V16: Validar token antes de usar
                                is_generated_token = recovered_token_from_chat.startswith('tracking_')
                                # ✅ CORREÇÃO: Aceitar UUID com ou sem hífens
                                normalized_chat = recovered_token_from_chat.replace('-', '').lower()
                                is_uuid_token = len(normalized_chat) == 32 and all(c in '0123456789abcdef' for c in normalized_chat)
                                
                                if is_generated_token:
                                    logger.error(f"❌ [GENERATE PIX] Token recuperado de tracking:chat é GERADO: {recovered_token_from_chat[:30]}... - IGNORANDO")
                                    logger.error(f"   Token gerado não tem dados do redirect (client_ip, client_user_agent, pageview_event_id)")
                                    # ✅ NÃO usar token gerado
                                elif is_uuid_token:
                                    tracking_token = recovered_token_from_chat
                                    logger.info(f"✅ Tracking token recuperado de tracking:chat:{customer_user_id}: {tracking_token[:20]}...")
                                else:
                                    logger.warning(f"⚠️ [GENERATE PIX] Token recuperado de tracking:chat tem formato inválido: {recovered_token_from_chat[:30]}... (len={len(recovered_token_from_chat)}) - IGNORANDO")
                    except Exception:
                        logger.exception("Falha ao recuperar tracking:chat do Redis")

                tracking_data_v4: Dict[str, Any] = redis_tracking_payload if isinstance(redis_tracking_payload, dict) else {}

                # ✅ CRÍTICO: Recuperar payload completo do Redis ANTES de gerar valores sintéticos
                if tracking_token:
                    recovered_payload = tracking_service.recover_tracking_data(tracking_token) or {}
                    if recovered_payload:
                        tracking_data_v4 = recovered_payload
                        logger.info(f"✅ Tracking payload recuperado do Redis para token {tracking_token[:20]}... | fbp={'ok' if recovered_payload.get('fbp') else 'missing'} | fbc={'ok' if recovered_payload.get('fbc') else 'missing'} | pageview_event_id={'ok' if recovered_payload.get('pageview_event_id') else 'missing'}")
                    elif not tracking_data_v4:
                        logger.warning("⚠️ Tracking token %s sem payload no Redis - tentando reconstruir via BotUser", tracking_token)
                    # ✅ CORREÇÃO CRÍTICA V12: VALIDAR antes de atualizar bot_user.tracking_session_id
                    # NUNCA atualizar com token gerado (deve ser UUID de 32 chars do redirect)
                    if bot_user and tracking_token:
                        # ✅ VALIDAÇÃO: tracking_token deve ser UUID (32 ou 36 chars, com ou sem hífens)
                        is_generated_token = tracking_token.startswith('tracking_')
                        # ✅ CORREÇÃO: Aceitar UUID com ou sem hífens
                        normalized_token_check = tracking_token.replace('-', '').lower()
                        is_uuid_token = len(normalized_token_check) == 32 and all(c in '0123456789abcdef' for c in normalized_token_check)
                        
                        if is_generated_token:
                            logger.error(f"❌ [GENERATE PIX] Tentativa de atualizar bot_user.tracking_session_id com token GERADO: {tracking_token[:30]}...")
                            logger.error(f"   Isso é um BUG - token gerado não deve ser salvo em bot_user.tracking_session_id")
                            # ✅ NÃO atualizar - manter token original do redirect
                        elif is_uuid_token:
                            # ✅ Token é UUID (vem do redirect) - pode atualizar
                            if bot_user.tracking_session_id != tracking_token:
                                bot_user.tracking_session_id = tracking_token
                                logger.info(f"✅ bot_user.tracking_session_id atualizado com token do redirect: {tracking_token[:20]}...")
                        else:
                            logger.warning(f"⚠️ [GENERATE PIX] tracking_token com formato inválido: {tracking_token[:30]}... (len={len(tracking_token)})")
                            # ✅ NÃO atualizar - formato inválido

                # ✅ NOTA: bot_user.tracking_session_id já foi verificado no início (prioridade máxima)
                # Não precisa verificar novamente aqui
                
                if not tracking_token:
                    # ✅ ESTRATÉGIA 1: Tentar recuperar tracking_token do Redis usando fbclid do BotUser
                    # Isso recupera o token original do redirect mesmo se bot_user.tracking_session_id estiver vazio
                    recovered_token_from_fbclid = None
                    if bot_user and getattr(bot_user, 'fbclid', None):
                        try:
                            # ✅ CRÍTICO: Buscar tracking_token no Redis via fbclid (chave: tracking:fbclid:{fbclid})
                            fbclid_from_botuser = bot_user.fbclid
                            tracking_token_key = f"tracking:fbclid:{fbclid_from_botuser}"
                            recovered_token_from_fbclid = tracking_service.redis.get(tracking_token_key)
                            if recovered_token_from_fbclid:
                                # ✅ Token encontrado via fbclid - recuperar payload completo
                                tracking_token = recovered_token_from_fbclid
                                logger.info(f"✅ Tracking token recuperado do Redis via fbclid do BotUser: {tracking_token[:20]}...")
                                recovered_payload_from_fbclid = tracking_service.recover_tracking_data(tracking_token) or {}
                                if recovered_payload_from_fbclid:
                                    tracking_data_v4 = recovered_payload_from_fbclid
                                    logger.info(f"✅ Tracking payload recuperado via fbclid: fbp={'✅' if recovered_payload_from_fbclid.get('fbp') else '❌'}, fbc={'✅' if recovered_payload_from_fbclid.get('fbc') else '❌'}, ip={'✅' if recovered_payload_from_fbclid.get('client_ip') else '❌'}, ua={'✅' if recovered_payload_from_fbclid.get('client_user_agent') else '❌'}, pageview_event_id={'✅' if recovered_payload_from_fbclid.get('pageview_event_id') else '❌'}")
                                    # ✅ CORREÇÃO CRÍTICA V12: VALIDAR antes de atualizar bot_user.tracking_session_id
                                    # Token recuperado via fbclid deve ser UUID (vem do redirect)
                                    if bot_user and tracking_token:
                                        is_generated_token = tracking_token.startswith('tracking_')
                                        # ✅ CORREÇÃO: Aceitar UUID com ou sem hífens
                                        normalized_token_check2 = tracking_token.replace('-', '').lower()
                                        is_uuid_token = len(normalized_token_check2) == 32 and all(c in '0123456789abcdef' for c in normalized_token_check2)
                                        
                                        if is_generated_token:
                                            logger.error(f"❌ [GENERATE PIX] Token recuperado via fbclid é GERADO: {tracking_token[:30]}... - NÃO atualizar bot_user.tracking_session_id")
                                        elif is_uuid_token:
                                            if bot_user.tracking_session_id != tracking_token:
                                                bot_user.tracking_session_id = tracking_token
                                                logger.info(f"✅ bot_user.tracking_session_id atualizado com token recuperado via fbclid: {tracking_token[:20]}...")
                                        else:
                                            logger.warning(f"⚠️ [GENERATE PIX] Token recuperado via fbclid tem formato inválido: {tracking_token[:30]}... (len={len(tracking_token)})")
                        except Exception as e:
                            logger.warning(f"⚠️ Erro ao recuperar tracking_token via fbclid do BotUser: {e}")
                    
                    # ✅ ESTRATÉGIA 2: Tentar recuperar de tracking:chat:{customer_user_id}
                    if not tracking_token and bot_user:
                        try:
                            chat_key = f"tracking:chat:{customer_user_id}"
                            chat_payload_raw = tracking_service.redis.get(chat_key)
                            if chat_payload_raw:
                                try:
                                    chat_payload = json.loads(chat_payload_raw)
                                    recovered_token_from_chat = chat_payload.get('tracking_token')
                                    if recovered_token_from_chat:
                                        tracking_token = recovered_token_from_chat
                                        logger.info(f"✅ Tracking token recuperado de tracking:chat:{customer_user_id}: {tracking_token[:20]}...")
                                        recovered_payload_from_chat = tracking_service.recover_tracking_data(tracking_token) or {}
                                        if recovered_payload_from_chat:
                                            tracking_data_v4 = recovered_payload_from_chat
                                            logger.info(f"✅ Tracking payload recuperado via chat: fbp={'✅' if recovered_payload_from_chat.get('fbp') else '❌'}, fbc={'✅' if recovered_payload_from_chat.get('fbc') else '❌'}, ip={'✅' if recovered_payload_from_chat.get('client_ip') else '❌'}, ua={'✅' if recovered_payload_from_chat.get('client_user_agent') else '❌'}, pageview_event_id={'✅' if recovered_payload_from_chat.get('pageview_event_id') else '❌'}")
                                            # ✅ CORREÇÃO CRÍTICA V12: VALIDAR antes de atualizar bot_user.tracking_session_id
                                            # Token recuperado via chat deve ser UUID (vem do redirect)
                                            if bot_user and tracking_token:
                                                is_generated_token = tracking_token.startswith('tracking_')
                                                # ✅ CORREÇÃO: Aceitar UUID com ou sem hífens
                                                normalized_token_check3 = tracking_token.replace('-', '').lower()
                                                is_uuid_token = len(normalized_token_check3) == 32 and all(c in '0123456789abcdef' for c in normalized_token_check3)
                                                
                                                if is_generated_token:
                                                    logger.error(f"❌ [GENERATE PIX] Token recuperado via chat é GERADO: {tracking_token[:30]}... - NÃO atualizar bot_user.tracking_session_id")
                                                elif is_uuid_token:
                                                    if bot_user.tracking_session_id != tracking_token:
                                                        bot_user.tracking_session_id = tracking_token
                                                        logger.info(f"✅ bot_user.tracking_session_id atualizado com token recuperado via chat: {tracking_token[:20]}...")
                                                else:
                                                    logger.warning(f"⚠️ [GENERATE PIX] Token recuperado via chat tem formato inválido: {tracking_token[:30]}... (len={len(tracking_token)})")
                                except Exception as e:
                                    logger.warning(f"⚠️ Erro ao parsear chat_payload: {e}")
                        except Exception as e:
                            logger.warning(f"⚠️ Erro ao recuperar tracking_token de tracking:chat: {e}")
                    
                    # ✅ CORREÇÃO CRÍTICA V17: Se PIX foi gerado com sucesso, SEMPRE criar Payment
                    # tracking_token ausente não deve bloquear criação de Payment se PIX já foi gerado
                    # Isso evita perder vendas quando gateway gera PIX mas tracking_token não está disponível
                    if not tracking_token:
                        # ✅ Verificar se PIX foi gerado com sucesso (pix_result existe e tem transaction_id)
                        if pix_result and pix_result.get('transaction_id'):
                            gateway_transaction_id_temp = pix_result.get('transaction_id')
                            logger.warning(f"⚠️ [TOKEN AUSENTE] tracking_token AUSENTE - PIX já foi gerado (transaction_id: {gateway_transaction_id_temp})")
                            logger.warning(f"   Isso indica que o usuário NÃO passou pelo redirect ou tracking_session_id não foi salvo")
                            logger.warning(f"   bot_user.tracking_session_id: {getattr(bot_user, 'tracking_session_id', None) if bot_user else 'N/A'}")
                            logger.warning(f"   bot_user.fbclid: {getattr(bot_user, 'fbclid', None) if bot_user else 'N/A'}")
                            logger.warning(f"   Payment será criado mesmo sem tracking_token para evitar perder venda")
                            logger.warning(f"   Meta Pixel Purchase terá atribuição reduzida (sem pageview_event_id)")
                            # ✅ NÃO bloquear - permitir criar Payment para que webhook possa processar
                            # tracking_token será None no Payment
                        else:
                            # ✅ PIX não foi gerado - pode falhar normalmente
                            error_msg = f"❌ [TOKEN AUSENTE] tracking_token AUSENTE e PIX não foi gerado para BotUser {bot_user.id if bot_user else 'N/A'} (customer_user_id: {customer_user_id})"
                            logger.error(error_msg)
                            logger.error(f"   Isso indica que o usuário NÃO passou pelo redirect ou tracking_session_id não foi salvo")
                            logger.error(f"   bot_user.tracking_session_id: {getattr(bot_user, 'tracking_session_id', None) if bot_user else 'N/A'}")
                            logger.error(f"   bot_user.fbclid: {getattr(bot_user, 'fbclid', None) if bot_user else 'N/A'}")
                            logger.error(f"   SOLUÇÃO: Usuário deve acessar link de redirect primeiro: /go/{{slug}}?grim=...&fbclid=...")
                            logger.error(f"   Payment NÃO será criado sem tracking_token válido e sem PIX gerado")
                            
                            # ✅ FALHAR: Não gerar token, não criar Payment sem tracking_token válido E sem PIX
                            raise ValueError(
                                f"tracking_token ausente e PIX não gerado - usuário deve acessar link de redirect primeiro. "
                                f"BotUser {bot_user.id if bot_user else 'N/A'} não tem tracking_session_id. "
                                f"SOLUÇÃO: Acessar /go/{{slug}}?grim=...&fbclid=... antes de gerar PIX"
                            )
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
                
                # ✅ CORREÇÃO CRÍTICA V17: VALIDAR tracking_token antes de criar Payment
                # Se PIX foi gerado com sucesso, SEMPRE criar Payment (mesmo sem tracking_token)
                # Isso evita perder vendas quando gateway gera PIX mas tracking_token não está disponível
                if not tracking_token:
                    # ✅ Verificar se PIX foi gerado com sucesso (pix_result existe e tem transaction_id)
                    transaction_id_from_result = pix_result.get('transaction_id') if pix_result else None
                    if pix_result and transaction_id_from_result:
                        logger.warning(f"⚠️ [TOKEN AUSENTE] tracking_token AUSENTE - PIX já foi gerado (transaction_id: {transaction_id_from_result})")
                        logger.warning(f"   BotUser {bot_user.id if bot_user else 'N/A'} não tem tracking_session_id")
                        logger.warning(f"   Payment será criado mesmo sem tracking_token para evitar perder venda")
                        logger.warning(f"   Meta Pixel Purchase terá atribuição reduzida (sem pageview_event_id)")
                        # ✅ NÃO bloquear - permitir criar Payment para que webhook possa processar
                        # tracking_token será None no Payment
                    else:
                        # ✅ PIX não foi gerado - pode falhar normalmente
                        error_msg = f"❌ [TOKEN AUSENTE] tracking_token AUSENTE e PIX não foi gerado - Payment NÃO será criado"
                        logger.error(error_msg)
                        logger.error(f"   BotUser {bot_user.id if bot_user else 'N/A'} não tem tracking_session_id")
                        logger.error(f"   SOLUÇÃO: Usuário deve acessar link de redirect primeiro: /go/{{slug}}?grim=...&fbclid=...")
                        raise ValueError("tracking_token ausente e PIX não gerado - Payment não pode ser criado sem tracking_token válido e sem PIX")
                
                # ✅ CORREÇÃO V17: Validar tracking_token apenas se não for None
                # ✅ CORREÇÃO CRÍTICA: Aceitar UUID com hífens (36 chars) OU sem hífens (32 chars)
                is_generated_token = False
                is_uuid_token = False
                
                if tracking_token:
                    is_generated_token = tracking_token.startswith('tracking_')
                    
                    # ✅ CORREÇÃO: Normalizar UUID removendo hífens para validação
                    # UUIDs podem vir em dois formatos:
                    # 1. Com hífens: faeac7b2-d4eb-4968-bf3b-87cad1b2bd5a (36 chars)
                    # 2. Sem hífens: faeac7b2d4eb4968bf3b87cad1b2bd5a (32 chars)
                    normalized_token = tracking_token.replace('-', '').lower()
                    is_uuid_token = len(normalized_token) == 32 and all(c in '0123456789abcdef' for c in normalized_token)
                    
                    # ✅ CORREÇÃO V14: Se PIX foi gerado com sucesso, permitir criar Payment mesmo com token gerado
                    # Isso evita perder vendas quando o gateway gera PIX mas o tracking_token não é ideal
                    # O warning será logado mas o Payment será criado para que o webhook possa processar
                    if is_generated_token:
                        logger.warning(f"⚠️ [TOKEN LEGADO] tracking_token LEGADO detectado: {tracking_token[:30]}...")
                        logger.warning(f"   PIX foi gerado com sucesso (transaction_id: {gateway_transaction_id})")
                        logger.warning(f"   Payment será criado mesmo com token legado para evitar perder venda")
                        logger.warning(f"   Meta Pixel Purchase pode ter atribuição reduzida (sem pageview_event_id)")
                        # ✅ NÃO bloquear - permitir criar Payment para que webhook possa processar
                    
                    if not is_uuid_token and not is_generated_token:
                        error_msg = f"❌ [GENERATE PIX] tracking_token com formato inválido: {tracking_token[:30]}... (len={len(tracking_token)})"
                        logger.error(error_msg)
                        logger.error(f"   Payment NÃO será criado com token inválido")
                        logger.error(f"   tracking_token deve ser UUID (32 ou 36 chars, com ou sem hífens) ou gerado (tracking_*)")
                        raise ValueError(f"tracking_token com formato inválido - deve ser UUID (32 ou 36 chars) ou gerado (tracking_*)")
                    
                    # ✅ VALIDAÇÃO PASSOU - criar Payment
                    if is_uuid_token:
                        logger.info(f"✅ [TOKEN UUID] tracking_token validado: {tracking_token[:20]}... (UUID do redirect, len={len(tracking_token)})")
                    else:
                        logger.info(f"⚠️ [TOKEN LEGADO] tracking_token legado: {tracking_token[:20]}... (será usado mesmo assim)")
                else:
                    # ✅ tracking_token é None - já foi logado como warning acima
                    logger.info(f"⚠️ [TOKEN AUSENTE] Payment será criado sem tracking_token (PIX já foi gerado)")
                
                # ✅ SISTEMA DE ASSINATURAS - Preparar dados de subscription
                button_data_for_subscription = None
                has_subscription_flag = False
                
                if button_config:
                    # Se button_config foi fornecido diretamente, usar
                    button_data_for_subscription = button_config.copy()
                    has_subscription_flag = button_config.get('subscription', {}).get('enabled', False)
                elif button_index is not None:
                    # Se button_index foi fornecido, buscar do config do bot
                    if bot and bot.config:
                        config_dict = bot.config.to_dict()
                        main_buttons = config_dict.get('main_buttons', [])
                        if button_index < len(main_buttons):
                            button_data_for_subscription = main_buttons[button_index].copy()
                            has_subscription_flag = button_data_for_subscription.get('subscription', {}).get('enabled', False)
                
                # ✅ CORREÇÃO: Importar json localmente para evitar UnboundLocalError
                import json as json_module
                
                # Salvar pagamento no banco (incluindo código PIX para reenvio + analytics)
                # ✅ CRÍTICO: Preparar dados para Payment
                # Determinar se é downsell, upsell ou normal
                is_downsell_final = is_downsell or False
                is_upsell_final = is_upsell or False
                
                payment = Payment(
                    bot_id=bot_id,  # ✅ OBRIGATÓRIO: ID do bot
                    payment_id=payment_id,  # ✅ OBRIGATÓRIO: ID único do pagamento
                    gateway_type=gateway.gateway_type if gateway else None,  # ✅ OBRIGATÓRIO: tipo do gateway
                    gateway_transaction_id=gateway_transaction_id,  # ✅ OBRIGATÓRIO: ID da transação
                    gateway_transaction_hash=gateway_hash,  # ✅ CRÍTICO: gateway_hash (campo 'hash' da resposta) para webhook matching
                    payment_method=str(pix_result.get('payment_method') or pix_result.get('paymentMethod') or 'PIX')[:20] if pix_result else 'PIX',
                    amount=amount,
                    customer_name=customer_name,
                    customer_username=customer_username,
                    customer_user_id=customer_user_id,
                    # ✅ CRÍTICO: Salvar email, phone e document do customer_data (para Meta Pixel Purchase)
                    customer_email=customer_data.get('email'),
                    customer_phone=customer_data.get('phone'),
                    customer_document=customer_data.get('document'),
                    product_name=description,
                    product_description=pix_result.get('pix_code'),  # Salvar código PIX para reenvio (None se recusado)
                    status=payment_status,  # ✅ 'failed' se recusado, 'pending' se não
                    # Analytics tracking
                    order_bump_shown=order_bump_shown,
                    order_bump_accepted=order_bump_accepted,
                    order_bump_value=order_bump_value,
                    is_downsell=is_downsell,
                    downsell_index=downsell_index,
                    is_upsell=is_upsell_final,  # ✅ NOVO - UPSELLS
                    upsell_index=upsell_index,  # ✅ NOVO - UPSELLS
                    is_remarketing=is_remarketing,  # ✅ NOVO - REMARKETING
                    remarketing_campaign_id=remarketing_campaign_id,  # ✅ NOVO - REMARKETING
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
                    # ✅ CRÍTICO: UTM TRACKING E CAMPAIGN CODE (grim) - PRIORIDADE: tracking_data_v4 > bot_user
                    # ✅ CORREÇÃO CRÍTICA: Usar UTMs do tracking_data_v4 (mais atualizados do redirect) ao invés de bot_user
                    utm_source=utm_source if utm_source else (getattr(bot_user, 'utm_source', None) if bot_user else None),
                    utm_campaign=utm_campaign if utm_campaign else (getattr(bot_user, 'utm_campaign', None) if bot_user else None),
                    utm_content=utm_content if utm_content else (getattr(bot_user, 'utm_content', None) if bot_user else None),
                    utm_medium=utm_medium if utm_medium else (getattr(bot_user, 'utm_medium', None) if bot_user else None),
                    utm_term=utm_term if utm_term else (getattr(bot_user, 'utm_term', None) if bot_user else None),
                    # ✅ CRÍTICO QI 600+: campaign_code (grim) para atribuição de campanha
                    # PRIORIDADE: tracking_data_v4.grim > bot_user.campaign_code
                    campaign_code=tracking_data_v4.get('grim') if tracking_data_v4.get('grim') else (getattr(bot_user, 'campaign_code', None) if bot_user else None),
                    # ✅ CRÍTICO: TRACKING_TOKEN V4 (pode ser None se PIX gerado sem tracking)
                    tracking_token=tracking_token,  # ✅ Token válido (UUID do redirect) ou None se ausente
                    # ✅ CRÍTICO: pageview_event_id para deduplicação Meta Pixel (fallback se Redis expirar)
                    # PRIORIDADE: tracking_data_v4.pageview_event_id > bot_user.pageview_event_id
                    pageview_event_id=pageview_event_id if pageview_event_id else (getattr(bot_user, 'pageview_event_id', None) if bot_user else None),
                    # ✅ CRÍTICO: fbclid para matching perfeito (persistente no banco)
                    # PRIORIDADE: tracking_data_v4.fbclid > bot_user.fbclid
                    fbclid=fbclid if fbclid else (getattr(bot_user, 'fbclid', None) if bot_user else None),
                    # ✅ CRÍTICO: fbp e fbc para fallback no Purchase (se Redis expirar)
                    # PRIORIDADE: tracking_data_v4 > bot_user
                    fbp=fbp if fbp else (getattr(bot_user, 'fbp', None) if bot_user else None),
                    fbc=fbc if fbc else (getattr(bot_user, 'fbc', None) if bot_user else None),
                    # ✅ CONTEXTO ORIGINAL DO CLIQUE (persistente para remarketing)
                    click_context_url=(
                        tracking_data_v4.get('event_source_url')
                        or getattr(bot_user, 'last_click_context_url', None)
                        or None
                    ),
                    # ✅ SISTEMA DE ASSINATURAS - Campos de subscription
                    button_index=button_index,
                    button_config=json_module.dumps(button_data_for_subscription, ensure_ascii=False) if button_data_for_subscription else None,
                    has_subscription=has_subscription_flag
                )
                db.session.add(payment)
                db.session.flush()  # ✅ Flush para obter payment.id antes do commit
                
                # ✅ QI 500: Salvar tracking data no Redis (após criar payment para ter payment.id)
                # ✅ CORREÇÃO V17: Só salvar se tracking_token não for None
                # ✅ CORREÇÃO ROBUSTA: Não bloquear se Redis falhar
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
                        logger.info(f"✅ Tracking data salvo no Redis para payment {payment.id}")
                    except Exception as redis_error:
                        logger.warning(f"⚠️ [REDIS INDISPONÍVEL] Erro ao salvar tracking data no Redis: {redis_error}")
                        logger.warning(f"   Payment {payment.id} foi criado mesmo assim (tracking data é opcional)")
                        # ✅ NÃO bloquear - continuar mesmo se Redis falhar
                else:
                    logger.warning(f"⚠️ [TOKEN AUSENTE] Não salvando tracking data no Redis (tracking_token é None)")
                
                # ✅ ATUALIZAR CONTADOR DE TRANSAÇÕES DO GATEWAY
                gateway.total_transactions += 1
                
                # ✅ CORREÇÃO ROBUSTA: Validação de integridade antes de commit
                try:
                    db.session.commit()
                    logger.info(f"✅ Payment {payment.id} commitado com sucesso")
                except IntegrityError as integrity_error:
                    db.session.rollback()
                    logger.error(f"❌ [ERRO DE INTEGRIDADE] Erro ao commitar Payment: {integrity_error}", exc_info=True)
                    logger.error(f"   Payment ID: {payment.id}, payment_id: {payment.payment_id}")
                    logger.error(f"   Gateway Transaction ID: {gateway_transaction_id}")
                    return None
                except Exception as commit_error:
                    db.session.rollback()
                    logger.error(f"❌ [ERRO AO COMMITAR] Erro ao commitar Payment: {commit_error}", exc_info=True)
                    logger.error(f"   Payment ID: {payment.id}, payment_id: {payment.payment_id}")
                    return None

                # ✅ QI 500: PAGEVIEW ENRICHMENT NO MOMENTO DO PIX (FONTE DE VERDADE = PAYMENT)
                # Re-enviar o MESMO PageView (mesmo event_id) com em/ph quando houver alta confiança.
                # Meta fará merge por event_id (não duplica PageView).
                try:
                    resolved_pageview_event_id = (
                        pageview_event_id
                        or getattr(payment, 'pageview_event_id', None)
                        or getattr(bot_user, 'pageview_event_id', None)
                    )
                    logger.info(
                        "🔎 ENRICHMENT CHECK | PIX",
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
                                    "🚨 PAGEVIEW_EVENT_ID AUSENTE | Enrichment impossível",
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
                            lock_ttl_seconds = 60 * 60 * 24 * 30  # 30 dias

                            lock_acquired = False
                            try:
                                lock_acquired = bool(tracking_service.redis.set(enrichment_lock_key, '1', nx=True, ex=lock_ttl_seconds))
                            except Exception as lock_error:
                                logger.warning(f"⚠️ [META PAGEVIEW ENRICH] Falha ao criar lock Redis: {lock_error}")

                            logger.info(
                                "🔎 ENRICHMENT LOCK RESULT",
                                extra={
                                    "enrichment_lock_key": enrichment_lock_key,
                                    "lock_ttl_seconds": lock_ttl_seconds,
                                    "lock_acquired": bool(lock_acquired)
                                }
                            )

                            if lock_acquired:
                                from celery_app import send_meta_event
                                from utils.encryption import decrypt
                                from utils.meta_pixel import MetaPixelAPI

                                try:
                                    access_token = decrypt(pool_for_meta.meta_access_token)
                                except Exception as decrypt_error:
                                    logger.error(f"❌ [META PAGEVIEW ENRICH] Erro ao descriptografar access_token do pool {pool_for_meta.id}: {decrypt_error}")
                                    access_token = None

                                if access_token:
                                    # IP/UA/FBP/FBC: pegar do tracking_data_v4, com fallback em Payment
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

                                    external_id_list = []
                                    if fbclid_for_enrich and isinstance(fbclid_for_enrich, str) and fbclid_for_enrich.strip():
                                        external_id_list.append(fbclid_for_enrich.strip())
                                    if telegram_user_id_for_enrich and telegram_user_id_for_enrich.strip():
                                        external_id_list.append(telegram_user_id_for_enrich.strip())

                                    user_data_enriched = MetaPixelAPI._build_user_data(
                                        customer_user_id=telegram_user_id_for_enrich,
                    
                                        external_id=external_id_list,
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

                                    send_meta_event.delay(
                                        pixel_id=pool_for_meta.meta_pixel_id,
                                        access_token=access_token,
                                        event_data=pageview_enriched_event,
                                        test_code=pool_for_meta.meta_test_event_code
                                    )

                                    logger.info(
                                        f"✅ [META PAGEVIEW ENRICH] Enfileirado após PIX | event_id={resolved_pageview_event_id} | "
                                        f"em={'✅' if user_data_enriched.get('em') else '❌'} | ph={'✅' if user_data_enriched.get('ph') else '❌'}"
                                    )
                            else:
                                logger.info(f"ℹ️ [META PAGEVIEW ENRICH] Lock já existe (não reenviar) | key={enrichment_lock_key} | ttl={lock_ttl_seconds}s | event_id={resolved_pageview_event_id}")
                except Exception as enrich_error:
                    logger.warning(f"⚠️ [META PAGEVIEW ENRICH] Falha ao enriquecer PageView após PIX (não bloqueia PIX): {enrich_error}")
                
                logger.info(f"✅ Pagamento registrado | Nosso ID: {payment_id} | SyncPay ID: {pix_result.get('transaction_id')}")
                
                # NOTIFICAR VIA WEBSOCKET (tempo real - BROADCAST para todos do usuário)
                try:
                    from app import socketio, app, send_sale_notification
                    from models import Bot
                    
                    with app.app_context():
                        bot = db.session.get(Bot, bot_id)
                        if bot:
                            # ✅ CORREÇÃO CRÍTICA: Emitir evento 'new_sale' APENAS para o usuário dono do bot
                            socketio.emit('new_sale', {
                                'id': payment.id,
                                'customer_name': customer_name,
                                'product_name': description,
                                'amount': float(amount),
                                'status': 'pending',
                                'created_at': payment.created_at.isoformat(),
                                'bot_id': bot_id
                            }, room=f'user_{bot.user_id}')
                            logger.info(f"📡 Evento 'new_sale' emitido para user_{bot.user_id} - R$ {amount}")
                            
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
                logger.error(f"   Valor: R$ {amount:.2f}")
                logger.error(f"   Descrição: {description}")
                logger.error(f"   API Key presente: {bool(gateway.api_key)}")
                
                # ✅ VALIDAÇÃO ESPECÍFICA WIINPAY
                if gateway.gateway_type == 'wiinpay' and amount < 3.0:
                    logger.error(f"⚠️ WIINPAY: Valor mínimo é R$ 3,00! Valor enviado: R$ {amount:.2f}")
                    logger.error(f"   SOLUÇÃO: Use outro gateway (Paradise, Pushyn ou SyncPay) para valores < R$ 3,00")
                
                return None
                
    except requests.exceptions.Timeout as timeout_error:
        # ✅ CORREÇÃO ROBUSTA: Gateway timeout - verificar se PIX foi gerado
        logger.warning(f"⚠️ [GATEWAY TIMEOUT] Gateway timeout ao gerar PIX")
        logger.warning(f"   Bot: {bot_id}, Valor: R$ {amount:.2f}")
        
        # ✅ Tentar encontrar Payment criado antes do timeout
        try:
            from models import db, Payment
            from app import app
            with app.app_context():
                # Tentar encontrar Payment criado antes do timeout
                payment = Payment.query.filter_by(
                    bot_id=bot_id,
                    customer_user_id=customer_user_id,
                    amount=amount,
                    status='pending'
                ).order_by(Payment.id.desc()).first()
                
                if payment:
                    payment.status = 'pending_verification'
                    payment.gateway_transaction_id = None
                    db.session.commit()
                    logger.warning(f"⚠️ Payment {payment.id} marcado como 'pending_verification' (timeout)")
                    return {'status': 'pending_verification', 'payment_id': payment.payment_id, 'error': 'Gateway timeout'}
        except Exception as commit_error:
            logger.error(f"❌ Erro ao processar timeout: {commit_error}", exc_info=True)
        
        logger.error(f"❌ Payment não foi criado antes do timeout - venda não iniciada")
        return None
            
    except Exception as e:
        # ✅ CORREÇÃO ROBUSTA: Verificar se gateway gerou PIX antes de fazer rollback
        logger.error(f"❌ [ERRO GATEWAY] Erro ao gerar PIX: {e}", exc_info=True)
        import traceback
        traceback.print_exc()
        
        # ✅ Verificar se gateway gerou PIX (pode estar em exception ou response)
        gateway_may_have_generated_pix = False
        transaction_id_from_error = None
        
        # ✅ ESTRATÉGIA 1: Verificar se exception tem transaction_id
        if hasattr(e, 'transaction_id') and e.transaction_id:
            gateway_may_have_generated_pix = True
            transaction_id_from_error = e.transaction_id
            logger.warning(f"⚠️ Exception contém transaction_id: {transaction_id_from_error}")
        
        # ✅ ESTRATÉGIA 2: Verificar se mensagem de erro contém transaction_id
        error_message = str(e).lower()
        if 'transaction_id' in error_message or 'transaction' in error_message:
            # Tentar extrair transaction_id da mensagem
            import re
            tx_match = re.search(r'transaction[_\s]?id[:\s]+([a-z0-9\-]+)', error_message, re.IGNORECASE)
            if tx_match:
                gateway_may_have_generated_pix = True
                transaction_id_from_error = tx_match.group(1)
                logger.warning(f"⚠️ transaction_id extraído da mensagem de erro: {transaction_id_from_error}")
        
        # ✅ Se gateway pode ter gerado PIX, tentar encontrar Payment e marcar como 'pending_verification'
        if gateway_may_have_generated_pix:
            try:
                from models import db, Payment
                from app import app
                with app.app_context():
                    # Tentar encontrar Payment criado antes do erro
                    payment = Payment.query.filter_by(
                        bot_id=bot_id,
                        customer_user_id=customer_user_id,
                        amount=amount
                    ).order_by(Payment.id.desc()).first()
                    
                    if payment:
                        payment.status = 'pending_verification'
                        if transaction_id_from_error:
                            payment.gateway_transaction_id = transaction_id_from_error
                        db.session.commit()
                        logger.warning(f"⚠️ Payment {payment.id} marcado como 'pending_verification' (gateway pode ter gerado PIX)")
                        return {'status': 'pending_verification', 'payment_id': payment.payment_id, 'error': str(e)}
            except Exception as commit_error:
                logger.error(f"❌ Erro ao processar erro do gateway: {commit_error}", exc_info=True)
        
        return None
```
