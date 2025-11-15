"""
Middleware de Validação para Gateways
QI 500 - Engineer Sênior

Funcionalidades:
- Validação de Content-Type
- Validação de gateway_type
- Rate limiting para webhooks
- Sanitização de logs
"""

from flask import request, jsonify
from functools import wraps
from typing import Dict, Any, Optional
import logging

logger = logging.getLogger(__name__)


def validate_gateway_request(f):
    """
    Middleware para validar requisições de gateway.
    
    Valida:
    - Content-Type (application/json ou application/x-www-form-urlencoded)
    - gateway_type (deve ser um tipo válido)
    
    Example:
        @app.route('/webhook/payment/<string:gateway_type>', methods=['POST'])
        @validate_gateway_request
        def payment_webhook(gateway_type):
            ...
    """
    @wraps(f)
    def decorated_function(*args, **kwargs):
        # Validar Content-Type
        if request.method in ['POST', 'PUT', 'PATCH']:
            content_type = request.headers.get('Content-Type', '')
            if 'application/json' not in content_type and 'application/x-www-form-urlencoded' not in content_type:
                logger.warning(f"⚠️ Content-Type inválido: {content_type}")
                return jsonify({'error': 'Content-Type inválido. Use application/json'}), 400
        
        # Validar gateway_type
        gateway_type = kwargs.get('gateway_type') or request.args.get('gateway_type')
        if gateway_type:
            valid_types = ['syncpay', 'pushynpay', 'paradise', 'wiinpay', 'atomopay', 'umbrellapag', 'orionpay']
            if gateway_type.lower() not in valid_types:
                logger.warning(f"⚠️ Gateway type inválido: {gateway_type}")
                return jsonify({'error': f'Gateway type inválido: {gateway_type}'}), 400
        
        return f(*args, **kwargs)
    
    return decorated_function


def rate_limit_webhook(max_per_minute: int = 60):
    """
    Rate limiting para webhooks.
    
    Args:
        max_per_minute: Número máximo de requisições por minuto
    
    Example:
        @app.route('/webhook/payment/<string:gateway_type>', methods=['POST'])
        @rate_limit_webhook(max_per_minute=100)
        def payment_webhook(gateway_type):
            ...
    
    Note:
        Em produção, usar Redis para armazenar contadores (não usar dicionário em memória)
    """
    from functools import wraps
    import time
    
    # Armazenar timestamps de requisições (em produção, usar Redis)
    request_times = {}
    
    def decorator(f):
        @wraps(f)
        def decorated_function(*args, **kwargs):
            # Identificar origem (IP + gateway_type)
            gateway_type = kwargs.get('gateway_type', 'unknown')
            client_ip = request.remote_addr
            key = f"{client_ip}:{gateway_type}"
            
            now = time.time()
            
            # Limpar timestamps antigos (> 1 minuto)
            if key in request_times:
                request_times[key] = [t for t in request_times[key] if now - t < 60]
            else:
                request_times[key] = []
            
            # Verificar rate limit
            if len(request_times[key]) >= max_per_minute:
                logger.warning(f"⚠️ Rate limit excedido para {key}")
                return jsonify({'error': 'Rate limit excedido'}), 429
            
            # Adicionar timestamp atual
            request_times[key].append(now)
            
            return f(*args, **kwargs)
        
        return decorated_function
    return decorator


def sanitize_log_data(data: Dict[str, Any], sensitive_fields: list = None) -> Dict[str, Any]:
    """
    Sanitiza dados para logs, mascarando campos sensíveis.
    
    Args:
        data: Dicionário com dados a serem sanitizados
        sensitive_fields: Lista de campos sensíveis (padrão: ['api_key', 'api_token', 'client_secret', 'password'])
    
    Returns:
        Dict com dados sanitizados
    
    Example:
        sanitized = sanitize_log_data(request.json)
        logger.info(f"Webhook data: {sanitized}")
    """
    if sensitive_fields is None:
        sensitive_fields = ['api_key', 'api_token', 'client_secret', 'client_id', 'password', 'token']
    
    sanitized = {}
    for key, value in data.items():
        if key.lower() in sensitive_fields:
            if isinstance(value, str) and len(value) > 6:
                # Mostrar apenas últimos 6 caracteres
                sanitized[key] = f"{'*' * (len(value) - 6)}{value[-6:]}"
            else:
                sanitized[key] = '***'
        elif isinstance(value, dict):
            # Recursivo para objetos aninhados
            sanitized[key] = sanitize_log_data(value, sensitive_fields)
        else:
            sanitized[key] = value
    
    return sanitized

