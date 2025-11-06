"""
MODIFICAÇÕES NO bot_manager.py - ARQUITETO SÊNIOR QI 200

MODIFICAÇÕES CRÍTICAS:
1. Gerar webhook_token ao criar Payment
2. Corrigir payment_id para usar UUID completo
3. Salvar gateway_id no Payment
4. Salvar tracking_token no Payment e BotUser
5. Remover restrição de gateway único (multi-gateway)
"""

# ============================================================================
# MODIFICAÇÃO 1: _generate_pix_payment() - Gerar webhook_token e corrigir payment_id
# ============================================================================
# Localização: bot_manager.py, linha ~3636-3638

"""
# ANTES:
payment_id = f"BOT{bot_id}_{int(time.time())}_{uuid.uuid4().hex[:8]}"

# DEPOIS:
import uuid
import time

# ✅ CORREÇÃO QI 200: Gerar webhook_token único
webhook_token = str(uuid.uuid4())

# ✅ CORREÇÃO QI 200: Payment_id com UUID completo (garantido único)
payment_id = f"BOT{bot_id}_{uuid.uuid4().hex}"

logger.info(f"🔑 Payment ID gerado: {payment_id} | Webhook Token: {webhook_token}")
"""

# ============================================================================
# MODIFICAÇÃO 2: _generate_pix_payment() - Seleção de gateway (multi-gateway)
# ============================================================================
# Localização: bot_manager.py, linha ~3543-3551

"""
# ANTES:
gateway = Gateway.query.filter_by(
    user_id=bot.user_id,
    is_active=True,
    is_verified=True
).first()

# DEPOIS:
# ✅ CORREÇÃO QI 200: Permitir múltiplos gateways ativos
gateways = Gateway.query.filter_by(
    user_id=bot.user_id,
    is_active=True,
    is_verified=True
).order_by(
    Gateway.priority.desc(),  # Prioridade maior primeiro
    Gateway.weight.desc(),    # Peso maior primeiro
    Gateway.id.asc()          # ID menor primeiro (determinístico)
).all()

if not gateways:
    logger.error(f"Nenhum gateway ativo encontrado para usuário {bot.user_id}")
    return None

# ✅ ESTRATÉGIA: Usar gateway com maior priority
# Se mesma priority, usar weighted round-robin (futuro)
gateway = gateways[0]

logger.info(f"🔧 Gateway selecionado: {gateway.gateway_type} (priority={gateway.priority}, weight={gateway.weight})")
"""

# ============================================================================
# MODIFICAÇÃO 3: _generate_pix_payment() - Salvar gateway_id e webhook_token
# ============================================================================
# Localização: bot_manager.py, linha ~3785-3826

"""
# ANTES:
payment = Payment(
    bot_id=bot_id,
    payment_id=payment_id,
    gateway_type=gateway.gateway_type,
    gateway_transaction_id=gateway_transaction_id,
    # ... outros campos ...
)

# DEPOIS:
payment = Payment(
    bot_id=bot_id,
    payment_id=payment_id,
    gateway_id=gateway.id,  # ✅ NOVO - QI 200: Gateway FK
    gateway_type=gateway.gateway_type,  # Manter para compatibilidade
    gateway_transaction_id=gateway_transaction_id,
    webhook_token=webhook_token,  # ✅ NOVO - QI 200: Webhook token
    tracking_token=bot_user.tracking_token if bot_user else None,  # ✅ NOVO - QI 200: Tracking token
    # ... outros campos ...
)
"""

# ============================================================================
# MODIFICAÇÃO 4: _handle_start_command() - Salvar tracking_token no BotUser
# ============================================================================
# Localização: bot_manager.py, linha ~1570-1590 (após salvar tracking no Redis)

"""
# ADICIONAR após salvar tracking no Redis:

# ✅ CORREÇÃO QI 200: Gerar e salvar tracking_token no BotUser
from utils.tracking_service import TrackingService

if not bot_user.tracking_token:
    # Gerar tracking_token único
    tracking_token = TrackingService.generate_tracking_token()
    bot_user.tracking_token = tracking_token
    
    # Salvar tracking_token no Redis também
    try:
        TrackingService.save_tracking_token(
            tracking_token=tracking_token,
            tracking_data={
                'fbclid': fbclid_completo_redis or '',
                'fbp': tracking_elite.get('fbp', ''),
                'fbc': tracking_elite.get('fbc', ''),
                'ip_address': tracking_elite.get('ip', ''),
                'user_agent': tracking_elite.get('user_agent', ''),
                'grim': grim_from_redis or '',
                'telegram_user_id': str(chat_id),
                'utms': {
                    'utm_source': tracking_elite.get('utm_source', ''),
                    'utm_campaign': tracking_elite.get('utm_campaign', ''),
                    'utm_medium': tracking_elite.get('utm_medium', ''),
                    'utm_content': tracking_elite.get('utm_content', ''),
                    'utm_term': tracking_elite.get('utm_term', '')
                }
            }
        )
        logger.info(f"🔑 Tracking token gerado e salvo: {tracking_token}")
    except Exception as e:
        logger.warning(f"⚠️ Erro ao salvar tracking_token: {e}")
"""

# ============================================================================
# MODIFICAÇÃO 5: Modificar gateway para incluir webhook_token no payload
# ============================================================================
# Localização: bot_manager.py, linha ~3706-3716 (chamada generate_pix)

"""
# ANTES:
pix_result = payment_gateway.generate_pix(
    amount=amount,
    description=description,
    payment_id=payment_id,
    customer_data={...}
)

# DEPOIS:
# ✅ CORREÇÃO QI 200: Incluir webhook_token no payload
pix_result = payment_gateway.generate_pix(
    amount=amount,
    description=description,
    payment_id=payment_id,
    customer_data={...},
    webhook_token=webhook_token  # ✅ NOVO
)
"""

# ============================================================================
# MODIFICAÇÃO 6: Atualizar interface PaymentGateway para aceitar webhook_token
# ============================================================================
# Localização: gateway_interface.py, linha ~20-26

"""
# ANTES:
@abstractmethod
def generate_pix(
    self, 
    amount: float, 
    description: str, 
    payment_id: str,
    customer_data: Optional[Dict[str, Any]] = None
) -> Optional[Dict[str, Any]]:

# DEPOIS:
@abstractmethod
def generate_pix(
    self, 
    amount: float, 
    description: str, 
    payment_id: str,
    customer_data: Optional[Dict[str, Any]] = None,
    webhook_token: Optional[str] = None  # ✅ NOVO - QI 200
) -> Optional[Dict[str, Any]]:
"""

# ============================================================================
# MODIFICAÇÃO 7: Modificar cada gateway para incluir webhook_token
# ============================================================================
# Localização: Cada gateway (gateway_*.py)

"""
# Para cada gateway, modificar generate_pix():

def generate_pix(
    self, 
    amount: float, 
    description: str, 
    payment_id: str,
    customer_data: Optional[Dict[str, Any]] = None,
    webhook_token: Optional[str] = None  # ✅ NOVO
) -> Optional[Dict[str, Any]]:
    # ... código existente ...
    
    # ✅ Incluir webhook_token no payload
    payload = {
        # ... campos existentes ...
        'webhook_token': webhook_token,  # ✅ NOVO
        # OU 'reference': f"{payment_id}|{webhook_token}"  # Se gateway não suporta webhook_token diretamente
    }
    
    # ... resto do código ...
    
    # ✅ Retornar webhook_token no resultado
    return {
        # ... campos existentes ...
        'webhook_token': webhook_token,  # ✅ SEMPRE incluir
    }
"""

