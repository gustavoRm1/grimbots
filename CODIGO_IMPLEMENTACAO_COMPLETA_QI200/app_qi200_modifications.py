"""
MODIFICAÇÕES NO app.py - ARQUITETO SÊNIOR QI 200

MODIFICAÇÕES CRÍTICAS:
1. Validar webhook_secret no webhook handler
2. Buscar Payment por webhook_token (prioridade 0)
3. Filtrar por gateway_id no webhook
4. Gerar tracking_token no redirect
5. Recuperar tracking via tracking_token no Purchase
6. Remover código que desativa outros gateways
7. Gerar webhook_secret ao criar Gateway
"""

# ============================================================================
# MODIFICAÇÃO 1: payment_webhook() - Validar webhook_secret
# ============================================================================
# Localização: app.py, linha ~7226-7232

"""
# ANTES:
@app.route('/webhook/payment/<string:gateway_type>', methods=['POST'])
@csrf.exempt
def payment_webhook(gateway_type):
    data = request.json
    logger.info(f"🔔 WEBHOOK RECEBIDO de {gateway_type}")

# DEPOIS:
@app.route('/webhook/payment/<string:gateway_type>', methods=['POST'])
@csrf.exempt
def payment_webhook(gateway_type):
    data = request.json
    logger.info(f"🔔 WEBHOOK RECEBIDO de {gateway_type}")
    
    # ✅ CORREÇÃO QI 200: Validar webhook_secret (multi-tenant)
    webhook_secret = request.args.get('secret')
    if not webhook_secret:
        logger.error(f"❌ Webhook sem secret: {gateway_type}")
        return jsonify({'error': 'Unauthorized'}), 401
    
    # Buscar gateway pelo secret
    gateway = Gateway.query.filter_by(
        gateway_type=gateway_type,
        webhook_secret=webhook_secret
    ).first()
    
    if not gateway:
        logger.error(f"❌ Gateway não encontrado para secret: {webhook_secret[:20]}...")
        return jsonify({'error': 'Unauthorized'}), 401
    
    logger.info(f"✅ Gateway identificado via webhook_secret: {gateway.id} (User: {gateway.user_id})")
"""

# ============================================================================
# MODIFICAÇÃO 2: payment_webhook() - Buscar Payment por webhook_token (prioridade 0)
# ============================================================================
# Localização: app.py, linha ~7326-7341

"""
# ANTES:
# ✅ PRIORIDADE 0 (QI 200): Filtrar por gateway se identificado via producer_hash
payment_query = Payment.query
if gateway:
    payment_query = payment_query.filter_by(gateway_type='atomopay')
    # ...

# DEPOIS:
# ✅ PRIORIDADE 0: Filtrar por gateway_id (mais preciso que gateway_type)
payment_query = Payment.query
if gateway:
    # ✅ CORREÇÃO QI 200: Filtrar por gateway_id (integridade referencial)
    payment_query = payment_query.filter_by(gateway_id=gateway.id)
    
    # ✅ CORREÇÃO QI 200: Filtrar por bot_id do usuário correto (via relacionamento)
    from models import Bot
    user_bot_ids = [b.id for b in Bot.query.filter_by(user_id=gateway.user_id).all()]
    if user_bot_ids:
        payment_query = payment_query.filter(Payment.bot_id.in_(user_bot_ids))
        logger.info(f"🔍 Filtrando Payments do usuário {gateway.user_id} ({len(user_bot_ids)} bots)")

# ✅ PRIORIDADE 0 (QI 200): webhook_token (único, garantido)
webhook_token = data.get('webhook_token') or result.get('webhook_token')
if webhook_token:
    payment = payment_query.filter_by(webhook_token=webhook_token).first()
    if payment:
        logger.info(f"✅ Payment encontrado por webhook_token: {webhook_token}")
        # ✅ USAR ESTE PAYMENT (não continuar para outras prioridades)
    else:
        logger.warning(f"⚠️ Webhook token não encontrado: {webhook_token}")

# PRIORIDADE 1: gateway_transaction_id (manter código existente)
# PRIORIDADE 2: gateway_transaction_hash (manter código existente)
# ... resto das prioridades ...
"""

# ============================================================================
# MODIFICAÇÃO 3: create_gateway() - Gerar webhook_secret e remover restrição
# ============================================================================
# Localização: app.py, linha ~4537 e ~4594-4600

"""
# MODIFICAÇÃO 3.1: Gerar webhook_secret ao criar Gateway
# Localização: app.py, linha ~4537

# ANTES:
if not gateway:
    gateway = Gateway(
        user_id=current_user.id,
        gateway_type=gateway_type
    )

# DEPOIS:
if not gateway:
    import uuid
    gateway = Gateway(
        user_id=current_user.id,
        gateway_type=gateway_type,
        webhook_secret=str(uuid.uuid4())  # ✅ NOVO - QI 200: Gerar webhook_secret único
    )
else:
    # ✅ Se gateway já existe mas não tem webhook_secret, gerar
    if not gateway.webhook_secret:
        import uuid
        gateway.webhook_secret = str(uuid.uuid4())

# MODIFICAÇÃO 3.2: Remover código que desativa outros gateways
# Localização: app.py, linha ~4594-4600

# ANTES:
if data.get('is_active', True):
    Gateway.query.filter(
        Gateway.user_id == current_user.id,
        Gateway.id != gateway.id
    ).update({'is_active': False})
    gateway.is_active = True

# DEPOIS:
# ✅ CORREÇÃO QI 200: REMOVIDO - Permitir múltiplos gateways ativos
# Sistema selecionará gateway baseado em priority/weight
gateway.is_active = data.get('is_active', True)
"""

# ============================================================================
# MODIFICAÇÃO 4: Redirect handler - Gerar tracking_token
# ============================================================================
# Localização: app.py, handler de redirect (precisa localizar)

"""
# ADICIONAR após capturar dados de tracking:

from utils.tracking_service import TrackingService
import uuid

# ✅ CORREÇÃO QI 200: Gerar tracking_token único
tracking_token = TrackingService.generate_tracking_token()

# Salvar tracking_token no Redis
TrackingService.save_tracking_token(
    tracking_token=tracking_token,
    tracking_data={
        'fbclid': fbclid,
        'fbp': fbp,
        'fbc': fbc,
        'ip_address': request.remote_addr,
        'user_agent': request.headers.get('User-Agent', ''),
        'grim': grim,
        'telegram_user_id': None,  # Será atualizado no /start
        'utms': {
            'utm_source': utm_source,
            'utm_campaign': utm_campaign,
            'utm_medium': utm_medium,
            'utm_content': utm_content,
            'utm_term': utm_term
        }
    }
)

# Incluir tracking_token no redirect URL
redirect_url = f"{bot_url}?start={tracking_token}"
"""

# ============================================================================
# MODIFICAÇÃO 5: send_meta_pixel_purchase_event() - Recuperar tracking via tracking_token
# ============================================================================
# Localização: app.py, função send_meta_pixel_purchase_event (precisa localizar)

"""
# ANTES:
def send_meta_pixel_purchase_event(payment):
    # Usa dados salvos no Payment (pode estar incompleto)

# DEPOIS:
def send_meta_pixel_purchase_event(payment):
    from utils.tracking_service import TrackingService
    from utils.meta_pixel import MetaPixelAPI
    
    # ✅ CORREÇÃO QI 200: PRIORIDADE 1 - Recuperar tracking via tracking_token
    tracking_data = None
    if payment.tracking_token:
        tracking_data = TrackingService.recover_by_tracking_token(payment.tracking_token)
        logger.info(f"🔑 Tracking recuperado via tracking_token: {payment.tracking_token}")
    
    # ✅ PRIORIDADE 2 - Recuperar via telegram_user_id
    if not tracking_data and payment.customer_user_id:
        tracking_data = TrackingService.recover_tracking_data(
            telegram_user_id=payment.customer_user_id
        )
        logger.info(f"🔑 Tracking recuperado via telegram_user_id: {payment.customer_user_id}")
    
    # ✅ PRIORIDADE 3 - Usar dados salvos no Payment (fallback)
    if not tracking_data:
        tracking_data = {
            'fbclid': payment.fbclid or '',
            'fbp': '',
            'fbc': '',
            'ip': '',
            'ua': '',
            'telegram_user_id': payment.customer_user_id or '',
            'utms': {
                'utm_source': payment.utm_source or '',
                'utm_campaign': payment.utm_campaign or '',
                'utm_medium': payment.utm_medium or '',
                'utm_content': payment.utm_content or '',
                'utm_term': payment.utm_term or ''
            }
        }
        logger.warning(f"⚠️ Tracking não encontrado no Redis, usando dados do Payment (fallback)")
    
    # ✅ SEMPRE construir external_id array com ordem fixa
    external_ids = TrackingService.build_external_id_array(
        fbclid=tracking_data.get('fbclid') or payment.fbclid,
        telegram_user_id=payment.customer_user_id
    )
    
    # ... resto do código para enviar evento ...
"""

# ============================================================================
# MODIFICAÇÃO 6: Modificar cada gateway para incluir webhook_secret na URL
# ============================================================================
# Localização: Cada gateway (gateway_*.py), método get_webhook_url()

"""
# Para cada gateway, modificar get_webhook_url():

# ANTES:
def get_webhook_url(self) -> str:
    base_url = os.environ.get('WEBHOOK_URL', 'http://localhost:5000')
    return f"{base_url}/webhook/payment/{self.get_gateway_type()}"

# DEPOIS:
def get_webhook_url(self) -> str:
    base_url = os.environ.get('WEBHOOK_URL', 'http://localhost:5000')
    # ✅ CORREÇÃO QI 200: Incluir webhook_secret na URL
    # NOTA: webhook_secret deve ser passado ao criar gateway
    # Por enquanto, retornar sem secret (será adicionado depois)
    webhook_secret = getattr(self, 'webhook_secret', None)
    if webhook_secret:
        return f"{base_url}/webhook/payment/{self.get_gateway_type()}?secret={webhook_secret}"
    else:
        # Fallback: retornar sem secret (compatibilidade)
        return f"{base_url}/webhook/payment/{self.get_gateway_type()}"
"""

# ============================================================================
# NOTA: Gateway precisa receber webhook_secret no __init__
# ============================================================================
# Localização: Cada gateway (gateway_*.py), método __init__()

"""
# Adicionar webhook_secret como parâmetro opcional:

def __init__(self, api_key: str, webhook_secret: str = None, ...):
    self.api_key = api_key
    self.webhook_secret = webhook_secret  # ✅ NOVO
    # ... resto do código ...
"""

