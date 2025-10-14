#!/usr/bin/env python3
"""
Bot do Telegram - Sistema Multi-Bot para Alto Tráfego
"""

import logging
import os
import time
import requests
import uuid
import asyncio
import json
import threading
from datetime import datetime
from telegram import Update, Bot, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import Application, CommandHandler, MessageHandler, filters, ContextTypes, CallbackQueryHandler
from shared_data import (
    add_event, update_stats, set_bot_status, get_settings,
    add_user_session, update_user_session, get_user_session, remove_user_session,
    add_timer, remove_timer, get_expired_timers, get_downsell_config,
    increment_downsell_stats, add_unique_user, get_all_scheduled_downsells,
    update_downsell_schedule
)
import signal
import sys
from concurrent.futures import ThreadPoolExecutor
from contextlib import contextmanager
from typing import Dict, List, Tuple, Optional

# Configuração de logging otimizada para produção
logging.basicConfig(
    format='%(asctime)s - %(levelname)s - %(message)s',
    level=logging.WARNING,  # Apenas WARNING e ERROR em produção
    handlers=[
        logging.StreamHandler(),
        logging.FileHandler('bot.log', encoding='utf-8')
    ]
)
logger = logging.getLogger(__name__)

# Logger separado para eventos importantes
event_logger = logging.getLogger('events')
event_logger.setLevel(logging.INFO)
event_handler = logging.FileHandler('events.log', encoding='utf-8')
event_handler.setFormatter(logging.Formatter('%(asctime)s - %(message)s'))
event_logger.addHandler(event_handler)

# Configuração de tokens múltiplos
BOT_TOKENS = [
    '8306671959:AAHeqNjcC9C3MpAVrCXRyer62vOyfLm_0MM',  # Token 1
    '7562715822:AAEPe1Men2JZHLWl5hjtoHtFO7FN6tHnxyM',  # Token 2
    '8465360609:AAGQuceE1GceIDZftS0MuVVmTYT1ifoe3hY',  # Token 3
    '8225954437:AAFtdhf4_4r2EH3ydStFwRvhN1b4MVKxLgQ',  # Token 4
    '8376203049:AAHBw3rMvolNSuIfZ-Si1CRifyRyf6z6lCY',  # Token 5
    '8372884477:AAFl8GwuVNxWXXEumjwMbm63_l_DfdvvwqM',  # Token 6
    '8426700153:AAF3NtPQZaPelVRdos1h1QkhIvGRbeDi-jQ',  # Token 7
    '7344610657:AAH3_JTdnZH_0CkNxfhb0hAIptlfRseSaK8',  # Token 8
    '8300351452:AAEsDLhXi4Cf5WVqnQS2-7ZkjBExbn5Z17U',  # Token 9
    '8297063257:AAFFE3K8I6yycwZQ-fAGO6di0yr4n5jGh_w',  # Token 10
    '8443691990:AAFjgMtr38_rHw6HZlnIvf3cCKTpb7m4R7Q',  # Token 11
    '8339224972:AAEzCqgfTmPT3l6k2R9_-7L0En3c-bgOST0',  # Token 12
    '8316837637:AAFgDiXo4HvU9RVJJrcwlkAz8kHj2xlbSok',  # Token 13
    '8454123391:AAHfSpgEFB_9UXm66NuUmHhGGRE_TkuxiGk',  # Token 15 - @libereseuacesso006bot
    '8382560938:AAE4dlx7fz4VfYDZrNWqLjWn4T7hG9XTN5g',  # Token 17 - @liberaoseuacesso00011bot
    '8260047923:AAGM3bUwqVPXWwlnYgrWfFxmS8A3TUq3CI8',  # Token 18 - @acessoliberando001bot
]

# Configuração de links por bot - TODOS ENTREGAM acessoliberado2
BOT_LINKS = {
    '8306671959:AAHeqNjcC9C3MpAVrCXRyer62vOyfLm_0MM': 'https://oacessoliberado.shop/acessoliberado2',  # @libereiotestedos100kbot
    '7562715822:AAEPe1Men2JZHLWl5hjtoHtFO7FN6tHnxyM': 'https://oacessoliberado.shop/acessoliberado2',  # @botzinhoteste001bot
    '8465360609:AAGQuceE1GceIDZftS0MuVVmTYT1ifoe3hY': 'https://oacessoliberado.shop/acessoliberado2',  # @liberrarseuacesso004bot
    '8376203049:AAHBw3rMvolNSuIfZ-Si1CRifyRyf6z6lCY': 'https://oacessoliberado.shop/acessoliberado2',  # @liberrarseuacesso002bot
    '8372884477:AAFl8GwuVNxWXXEumjwMbm63_l_DfdvvwqM': 'https://oacessoliberado.shop/acessoliberado2',  # @liberrarseuacesso001bot
    '8426700153:AAF3NtPQZaPelVRdos1h1QkhIvGRbeDi-jQ': 'https://oacessoliberado.shop/acessoliberado2',  # @lliberaroseuacesso003bot
    '7344610657:AAH3_JTdnZH_0CkNxfhb0hAIptlfRseSaK8': 'https://oacessoliberado.shop/acessoliberado2',  # @lliberaroseuacesso002bot
    '8300351452:AAEsDLhXi4Cf5WVqnQS2-7ZkjBExbn5Z17U': 'https://oacessoliberado.shop/acessoliberado2',  # @lliberaroseuacesso001bot
    '8297063257:AAFFE3K8I6yycwZQ-fAGO6di0yr4n5jGh_w': 'https://oacessoliberado.shop/acessoliberado2',  # @liberaoseuacesso0009bot
    '8454123391:AAHfSpgEFB_9UXm66NuUmHhGGRE_TkuxiGk': 'https://oacessoliberado.shop/acessoliberado2',  # @libereseuacesso006bot
    '8382560938:AAE4dlx7fz4VfYDZrNWqLjWn4T7hG9XTN5g': 'https://oacessoliberado.shop/acessoliberado2',  # @liberaoseuacesso00011bot
    '8260047923:AAGM3bUwqVPXWwlnYgrWfFxmS8A3TUq3CI8': 'https://oacessoliberado.shop/acessoliberado2',  # @acessoliberando001bot
}

# Configurações PushynPay (URLs CORRETAS)
PUSHYNPAY_TOKEN = ''
PUSHYNPAY_BASE_URL_SANDBOX = 'https://api-sandbox.pushinpay.com.br'
PUSHYNPAY_BASE_URL_PRODUCTION = 'https://api.pushinpay.com.br'

# Endpoints PushynPay corretos
PUSHYNPAY_ENDPOINTS = [
    f"{PUSHYNPAY_BASE_URL_SANDBOX}/api/pix/cashIn",
    f"{PUSHYNPAY_BASE_URL_PRODUCTION}/api/pix/cashIn"
]

# Configurações SyncPay Original (mantido como backup)
SYNCPAY_CLIENT_ID = '54f3518a-1e5f-4f08-8c68-5a79df3bddf9'
SYNCPAY_CLIENT_SECRET = 'f49f4e62-d0c6-4c17-a8ac-e036a0fc69a2'
SYNCPAY_BASE_URL = 'https://api.syncpayments.com.br'

# Sistema de múltiplos gateways
GATEWAYS = {
    'syncpay_original': {
        'name': 'SyncPay Original',
        'base_url': SYNCPAY_BASE_URL,
        'client_id': SYNCPAY_CLIENT_ID,
        'client_secret': SYNCPAY_CLIENT_SECRET,
        'active': True,
        'priority': 1,
        'max_amount': 10000.00,
        'min_amount': 1.00
    },
    'pushynpay': {
        'name': 'PushynPay',
        'base_url': PUSHYNPAY_BASE_URL_SANDBOX,  # Usar sandbox para testes
        'token': PUSHYNPAY_TOKEN,
        'active': False,  # DESATIVADO - Apenas SyncPay ativo
        'priority': 2,  # Prioridade baixa
        'max_amount': 10000.00,
        'min_amount': 0.50,  # Valor mínimo R$ 0,50 (50 centavos)
        'endpoints': PUSHYNPAY_ENDPOINTS
    }
}

# Controle de rate limiting inteligente para vendas
user_requests = {}  # {user_id: {'last_request': timestamp, 'pending_request': bool, 'last_action': 'start'|'button'|'message'}}
RESPONSE_COOLDOWN = 5  # 5 segundos de cooldown após responder

# Armazenamento de pagamentos pendentes
pending_payments = {}  # {user_id: {'payment_id': str, 'amount': float, 'plan': str}}

# Rate limiting para verificação PushynPay (conforme documentação: 1 minuto entre consultas)
pushynpay_last_check = {}  # {payment_id: timestamp}

# Rate limiting para verificação de pagamento (evitar cliques muito rápidos)
payment_check_cooldown = {}  # {user_id: timestamp}
PAYMENT_CHECK_COOLDOWN = 3  # 3 segundos entre verificações

# Sistema multi-bot com controle de shutdown
active_bots = {}  # {token: {'application': app, 'bot': bot, 'status': 'active'|'failed'}}
bot_rotation_index = 0
shutdown_requested = False

# Sistema de gateways com failover
gateway_status = {}  # {gateway_id: {'status': 'active'|'failed', 'last_error': str, 'error_count': int}}
gateway_rotation_index = 0

# Sistema de comandos administrativos
ADMIN_USER_ID = 7676333385  # Seu ID do Telegram
ADMIN_COMMANDS = {
    '/admin': 'admin',
    '/gw': 'gateway',
    '/meuid': 'meu_id'
}

# Configuração de notificações de vendas
SALE_NOTIFICATIONS_ENABLED = True
ADMIN_NOTIFICATION_CHAT_ID = ADMIN_USER_ID  # ID do chat para receber notificações

def signal_handler(signum, frame):
    """Handler para sinais de interrupção"""
    global shutdown_requested
    if not shutdown_requested:
        event_logger.info(f"Shutdown iniciado - sinal {signum}")
        shutdown_requested = True
        # Forçar saída após 5 segundos
        import threading
        def force_exit():
            import time
            time.sleep(5)
            logger.error("Shutdown forçado após timeout")
            os._exit(1)
        threading.Thread(target=force_exit, daemon=True).start()
    else:
        logger.error("Segundo sinal recebido - forçando saída imediata")
        os._exit(1)

# Registrar handlers de sinal
signal.signal(signal.SIGINT, signal_handler)
signal.signal(signal.SIGTERM, signal_handler)

def initialize_gateways():
    """Inicializa o sistema de gateways"""
    global gateway_status
    
    for gateway_id, config in GATEWAYS.items():
        gateway_status[gateway_id] = {
            'status': 'active' if config['active'] else 'inactive',
            'last_error': None,
            'error_count': 0,
            'last_success': None,
            'total_requests': 0,
            'successful_requests': 0
        }
    
    event_logger.info(f"Gateways inicializados: {len(gateway_status)}")

def get_best_gateway(amount=None):
    """Retorna o melhor gateway disponível baseado na prioridade e status"""
    global gateway_rotation_index
    
    # Filtrar gateways ativos e válidos para o valor
    available_gateways = []
    for gateway_id, config in GATEWAYS.items():
        if (gateway_status[gateway_id]['status'] == 'active' and 
            config['active'] and
            (amount is None or (config['min_amount'] <= amount <= config['max_amount']))):
            available_gateways.append((gateway_id, config))
    
    if not available_gateways:
        logger.error("Nenhum gateway disponível")
        return None
    
    # Ordenar por prioridade
    available_gateways.sort(key=lambda x: x[1]['priority'])
    
    # Selecionar gateway com melhor taxa de sucesso
    best_gateway = None
    best_success_rate = 0
    
    for gateway_id, config in available_gateways:
        status = gateway_status[gateway_id]
        if status['total_requests'] > 0:
            success_rate = status['successful_requests'] / status['total_requests']
        else:
            success_rate = 1.0  # Gateway novo, assumir 100% de sucesso
        
        if success_rate > best_success_rate:
            best_success_rate = success_rate
            best_gateway = gateway_id
    
    if best_gateway:
        # Log apenas se taxa de sucesso baixa
        if best_success_rate < 0.8:
            logger.warning(f"Gateway {GATEWAYS[best_gateway]['name']} com baixa taxa de sucesso: {best_success_rate:.2%}")
        return best_gateway
    
    # Fallback para primeiro gateway disponível
    return available_gateways[0][0]

def mark_gateway_failed(gateway_id, error_msg):
    """Marca um gateway como falhado"""
    if gateway_id in gateway_status:
        gateway_status[gateway_id]['status'] = 'failed'
        gateway_status[gateway_id]['last_error'] = error_msg
        gateway_status[gateway_id]['error_count'] += 1
        
        logger.error(f"Gateway {GATEWAYS[gateway_id]['name']} falhou: {error_msg}")
        
        # Tentar reativar após 5 minutos
        asyncio.create_task(reactivate_gateway_after_delay(gateway_id, 300))

def mark_gateway_success(gateway_id):
    """Marca um gateway como bem-sucedido"""
    if gateway_id in gateway_status:
        gateway_status[gateway_id]['status'] = 'active'
        gateway_status[gateway_id]['last_success'] = datetime.now()
        gateway_status[gateway_id]['successful_requests'] += 1
        gateway_status[gateway_id]['total_requests'] += 1
        
        # Reset error count após sucesso
        if gateway_status[gateway_id]['error_count'] > 0:
            gateway_status[gateway_id]['error_count'] = max(0, gateway_status[gateway_id]['error_count'] - 1)

async def reactivate_gateway_after_delay(gateway_id, delay_seconds):
    """Reativa um gateway após um delay"""
    await asyncio.sleep(delay_seconds)
    if gateway_id in gateway_status:
        gateway_status[gateway_id]['status'] = 'active'
        event_logger.info(f"Gateway {GATEWAYS[gateway_id]['name']} reativado")

def is_admin(user_id):
    """Verifica se o usuário é administrador"""
    return user_id == ADMIN_USER_ID

def activate_gateway(gateway_id):
    """Ativa um gateway específico"""
    if gateway_id in GATEWAYS:
        GATEWAYS[gateway_id]['active'] = True
        gateway_status[gateway_id]['status'] = 'active'
        gateway_status[gateway_id]['error_count'] = 0
        event_logger.info(f"Gateway {GATEWAYS[gateway_id]['name']} ativado pelo admin")
        return True
    return False

def deactivate_gateway(gateway_id):
    """Desativa um gateway específico"""
    if gateway_id in GATEWAYS:
        GATEWAYS[gateway_id]['active'] = False
        gateway_status[gateway_id]['status'] = 'inactive'
        event_logger.info(f"Gateway {GATEWAYS[gateway_id]['name']} desativado pelo admin")
        return True
    return False

def set_gateway_priority(gateway_id, priority):
    """Define a prioridade de um gateway"""
    if gateway_id in GATEWAYS:
        GATEWAYS[gateway_id]['priority'] = priority
        event_logger.info(f"Prioridade do gateway {GATEWAYS[gateway_id]['name']} alterada para {priority}")
        return True
    return False

def get_gateway_status_text():
    """Retorna status dos gateways em formato de texto"""
    status_text = "💳 **STATUS DOS GATEWAYS**\n\n"
    
    for gateway_id, status in gateway_status.items():
        gateway_name = GATEWAYS[gateway_id]['name']
        priority = GATEWAYS[gateway_id]['priority']
        
        if status['status'] == 'active':
            status_icon = "✅"
        elif status['status'] == 'failed':
            status_icon = "❌"
        else:
            status_icon = "⏸️"
        
        success_rate = "N/A"
        if status['total_requests'] > 0:
            success_rate = f"{(status['successful_requests'] / status['total_requests'] * 100):.1f}%"
        
        status_text += f"{status_icon} **{gateway_name}**\n"
        status_text += f"   Prioridade: {priority}\n"
        status_text += f"   Taxa de Sucesso: {success_rate}\n"
        status_text += f"   Requisições: {status['total_requests']}\n"
        if status['last_error']:
            status_text += f"   Último Erro: {status['last_error'][:50]}...\n"
        status_text += "\n"
    
    return status_text

def check_rate_limit(user_id, action_type="start"):
    """Sistema inteligente de rate limiting que prioriza a última ação"""
    current_time = time.time()
    
    if user_id not in user_requests:
        user_requests[user_id] = {
            'last_response': 0,
            'pending_request': False,
            'last_action': action_type,
            'last_action_time': current_time
        }
        return True
    
    user_data = user_requests[user_id]
    time_since_last_response = current_time - user_data['last_response']
    
    # Se passou mais de 5 segundos desde a última resposta, pode responder
    if time_since_last_response >= RESPONSE_COOLDOWN:
        user_data['last_action'] = action_type
        user_data['last_action_time'] = current_time
        return True
    
    # Se ainda está no cooldown, verifica se a nova ação é mais importante
    time_since_last_action = current_time - user_data['last_action_time']
    
    # Se a nova ação é mais recente (últimos 2 segundos), substitui a anterior
    if time_since_last_action <= 2:
        # Log apenas para debug se necessário
        pass
        user_data['last_action'] = action_type
        user_data['last_action_time'] = current_time
        return True
    
    # Se ainda está no cooldown e não é uma ação recente
    user_data['pending_request'] = True
    # Log apenas se cooldown muito longo (possível problema)
    if time_since_last_response > RESPONSE_COOLDOWN * 2:
        logger.warning(f"Usuário {user_id} com cooldown excessivo: {time_since_last_response:.1f}s")
    return False

def mark_response_sent(user_id):
    """Marca que uma resposta foi enviada para o usuário"""
    current_time = time.time()
    if user_id not in user_requests:
        user_requests[user_id] = {'last_response': 0, 'pending_request': False, 'last_action': 'start', 'last_action_time': 0}
    
    user_requests[user_id]['last_response'] = current_time
    user_requests[user_id]['pending_request'] = False

class SyncPayIntegration:
    """Integração profissional com SyncPay"""
    
    def __init__(self):
        self.client_id = SYNCPAY_CLIENT_ID
        self.client_secret = SYNCPAY_CLIENT_SECRET
        self.base_url = SYNCPAY_BASE_URL
        self.access_token = None
        self.token_expires_at = 0
    
    def get_access_token(self):
        """Obtém token de acesso da SyncPay"""
        try:
            if self.access_token and time.time() < self.token_expires_at:
                return self.access_token
            
            url = f"{self.base_url}/api/partner/v1/auth-token"
            data = {
                'client_id': self.client_id,
                'client_secret': self.client_secret
            }
            
            response = requests.post(url, json=data, timeout=15)
            
            if response.status_code == 200:
                token_data = response.json()
                self.access_token = token_data['access_token']
                self.token_expires_at = time.time() + token_data['expires_in'] - 60  # 1 min de margem
                
                # Token obtido com sucesso
                return self.access_token
            else:
                logger.error(f"Erro ao obter token SyncPay: {response.status_code}")
                return None
                
        except Exception as e:
            logger.error(f"Erro ao obter token SyncPay: {e}")
            return None
    
    def create_payment(self, amount, description, user_id):
        """Cria pagamento PIX na SyncPay usando API Cash-in"""
        try:
            # Criando pagamento SyncPay
            
            # Obter token de acesso primeiro
            token = self.get_access_token()
            if not token:
                logger.error("Token SyncPay não obtido")
                return None
            
            url = f"{self.base_url}/api/partner/v1/cash-in"
            headers = {
                'Authorization': f'Bearer {token}',
                'Content-Type': 'application/json',
                'Accept': 'application/json'
            }
            
            # Dados do cliente (obrigatórios pela API)
            client_data = {
                'name': f'Usuário {user_id}',
                'cpf': '12345678900',  # CPF genérico para testes
                'email': f'user{user_id}@telegram.com',
                'phone': '11999999999'  # Telefone genérico
            }
            
            data = {
                'amount': amount,
                'description': description,
                'client': client_data,
                'webhook_url': 'https://webhook.site/your-webhook-url'  # Opcional
            }
            
            response = requests.post(url, json=data, headers=headers, timeout=15)
            
            if response.status_code == 200:
                payment_data = response.json()
                event_logger.info(f"Pagamento SyncPay criado: R$ {amount}")
                
                return {
                    'payment_id': payment_data.get('identifier'),
                    'pix_code': payment_data.get('pix_code'),
                    'status': 'pending'
                }
            else:
                logger.error(f"Erro HTTP SyncPay {response.status_code}")
                return None
                
        except requests.exceptions.RequestException as e:
            logger.error(f"Erro de conexão SyncPay: {e}")
            return None
        except Exception as e:
            logger.error(f"Erro ao criar pagamento SyncPay: {e}")
            return None
    
    def check_payment_status(self, payment_id):
        """Verifica status do pagamento usando endpoint CORRETO da documentação"""
        try:
            # Obter token de acesso primeiro
            token = self.get_access_token()
            if not token:
                logger.error("❌ Token não obtido")
                return None
            
            # ENDPOINT CORRETO DA DOCUMENTAÇÃO: /api/partner/v1/transaction/{identifier}
            url = f"{self.base_url}/api/partner/v1/transaction/{payment_id}"
            headers = {
                'Authorization': f'Bearer {token}',
                'Accept': 'application/json'
            }
            
            logger.info(f"🔍 Verificando pagamento: {url}")
            
            response = requests.get(url, headers=headers, timeout=10)
            
            logger.info(f"📥 Status HTTP: {response.status_code}")
            
            if response.status_code == 200:
                response_data = response.json()
                logger.info(f"📦 Resposta: {response_data}")
                
                # Extrair dados conforme documentação
                payment_data = response_data.get('data', {})
                status = payment_data.get('status', '').lower()
                
                logger.info(f"📊 Status do pagamento: {status}")
                
                # Mapear status conforme documentação SyncPay
                if status == 'completed':
                    logger.info("✅ Pagamento COMPLETADO")
                    return 'paid'
                elif status == 'pending':
                    logger.info("⏳ Pagamento PENDENTE")
                    return 'pending'
                elif status in ['failed', 'refunded']:
                    logger.warning(f"❌ Pagamento {status}")
                    return 'failed'
                else:
                    logger.warning(f"⚠️ Status desconhecido: {status}")
                    return None
                    
            elif response.status_code == 404:
                logger.warning(f"⚠️ Pagamento não encontrado: {payment_id}")
                return None
            else:
                logger.error(f"❌ Erro HTTP {response.status_code}: {response.text}")
                return None
                
        except Exception as e:
            logger.error(f"❌ Exceção ao verificar status: {e}")
            import traceback
            logger.error(traceback.format_exc())
            return None

async def check_pushynpay_payment_status(payment_id):
    """Verifica status do pagamento PushynPay usando a API oficial"""
    try:
        # Verificar rate limiting (conforme documentação: 1 minuto entre consultas)
        current_time = time.time()
        if payment_id in pushynpay_last_check:
            time_since_last_check = current_time - pushynpay_last_check[payment_id]
            if time_since_last_check < 60:  # 1 minuto
                logger.info(f"Rate limiting PushynPay: aguardando {60 - time_since_last_check:.0f}s para {payment_id}")
                return 'pending'  # Retornar pending para evitar bloqueio da conta
        
        # Registrar timestamp da consulta
        pushynpay_last_check[payment_id] = current_time
        
        # Headers para autenticação PushynPay (conforme documentação oficial)
        headers = {
            "Authorization": f"Bearer {PUSHYNPAY_TOKEN}",
            "Accept": "application/json",
            "Content-Type": "application/json"
        }
        
        # URLs de verificação conforme documentação oficial PushynPay
        verify_urls = [
            f"{PUSHYNPAY_BASE_URL_PRODUCTION}/api/transactions/{payment_id}",  # Produção primeiro
            f"{PUSHYNPAY_BASE_URL_SANDBOX}/api/transactions/{payment_id}"       # Sandbox como fallback
        ]
        
        # Tentar cada URL de verificação
        for verify_url in verify_urls:
            try:
                response = requests.get(
                    verify_url,
                    headers=headers,
                    timeout=15
                )
                
                if response.status_code == 200:
                    payment_data = response.json()
                    logger.info(f"Resposta PushynPay para {payment_id}: {payment_data}")
                    
                    # Verificar status baseado na resposta PushynPay
                    # Conforme documentação, o retorno é igual ao de criar PIX
                    status = payment_data.get('status', '').lower()
                    
                    if status in ['paid', 'completed', 'approved', 'success', 'confirmed']:
                        return 'paid'
                    elif status in ['pending', 'processing', 'waiting', 'created', 'open']:
                        return 'pending'
                    elif status in ['failed', 'cancelled', 'expired', 'rejected']:
                        return 'failed'
                    else:
                        logger.warning(f"Status PushynPay desconhecido: {status}")
                        # Se não reconhece o status, assumir pending para permitir nova verificação
                        return 'pending'
                        
                elif response.status_code == 404:
                    # Pagamento não encontrado - conforme documentação
                    logger.debug(f"Pagamento não encontrado em {verify_url}")
                    continue
                elif response.status_code == 401:
                    # Token inválido
                    logger.error(f"Token PushynPay inválido para verificação")
                    return None
                else:
                    logger.warning(f"Erro PushynPay verificação {response.status_code} em {verify_url}")
                    continue
                    
            except requests.exceptions.RequestException as e:
                logger.warning(f"Erro de conexão PushynPay em {verify_url}: {e}")
                continue
            except Exception as e:
                logger.warning(f"Erro PushynPay verificação em {verify_url}: {e}")
                continue
        
        # Se chegou aqui, todas as tentativas falharam
        logger.warning(f"Nenhuma URL de verificação PushynPay funcionou para {payment_id}")
        
        # Como fallback, assumir que o pagamento está pendente para permitir nova verificação
        # Isso evita que o usuário fique preso em um erro permanente
        return 'pending'
        
    except Exception as e:
        logger.error(f"Erro geral na verificação PushynPay: {e}")
        # Em caso de erro geral, retornar pending para permitir nova tentativa
        return 'pending'

async def create_pix_payment_pushynpay(user_id, amount, plan_name, customer_data):
    """Cria um pagamento PIX usando PushynPay com formato correto da API"""
    payment_id = str(uuid.uuid4())
    
    # Dados do pagamento para PushynPay (formato correto da API)
    payment_data = {
        "value": int(amount * 100),  # Converter para centavos (PushynPay exige)
        "webhook_url": "https://webhook.site/test",  # URL de teste temporária
        "split_rules": []  # Regras de split (vazio para pagamento simples)
    }
    
    # Headers para autenticação PushynPay
    headers = {
        "Authorization": f"Bearer {PUSHYNPAY_TOKEN}",
        "Accept": "application/json",
        "Content-Type": "application/json"
    }
    
    # Tentar endpoints PushynPay
    for i, endpoint in enumerate(PUSHYNPAY_ENDPOINTS):
        try:
            # Tentativa de pagamento PushynPay
            
            response = requests.post(
                endpoint,
                json=payment_data,
                headers=headers,
                timeout=30
            )
            
            # Processando resposta PushynPay
            
            # Verificar diferentes códigos de sucesso
            if response.status_code in [200, 201, 202]:
                try:
                    pix_data = response.json()
                    
                    # Verificar se tem código PIX (formato PushynPay)
                    pix_code = pix_data.get('pix_code') or pix_data.get('qr_code') or pix_data.get('code') or pix_data.get('pix')
                    
                    if pix_code:
                        # Armazenar pagamento pendente
                        pending_payments[user_id] = {
                            'payment_id': payment_id,
                            'amount': amount,
                            'plan': plan_name,
                            'pix_code': pix_code,
                            'expires_at': pix_data.get('expires_at'),
                            'gateway': 'pushynpay',
                            'gateway_payment_id': pix_data.get('id') or pix_data.get('payment_id')
                        }
                        
                        event_logger.info(f"PIX PushynPay criado: R$ {amount}")
                        return pix_data
                    else:
                        logger.warning(f"Resposta PushynPay sem código PIX")
                        continue
                        
                except json.JSONDecodeError:
                    logger.error(f"Resposta PushynPay não é JSON válido")
                    continue
            elif response.status_code == 401:
                logger.error(f"Token PushynPay inválido")
                continue
            elif response.status_code == 422:
                logger.error(f"Dados PushynPay inválidos")
                continue
            else:
                logger.warning(f"Status PushynPay {response.status_code}")
                continue
                
        except requests.exceptions.RequestException as e:
            logger.error(f"Erro de conexão PushynPay tentativa {i+1}")
            continue
        except Exception as e:
            logger.error(f"Erro PushynPay tentativa {i+1}: {e}")
            continue
    
    logger.error(f"Todas as tentativas PushynPay falharam")
    return None

async def create_pix_payment_syncpay_original(user_id, amount, plan_name, customer_data):
    """Cria um pagamento PIX usando SyncPay Original com API correta"""
    try:
        logger.info("🔵 Iniciando criação de pagamento SyncPay")
        
        # PASSO 1: Obter token de acesso
        token_url = f"{SYNCPAY_BASE_URL}/api/partner/v1/auth-token"
        token_payload = {
            "client_id": SYNCPAY_CLIENT_ID,
            "client_secret": SYNCPAY_CLIENT_SECRET
        }
        
        logger.info(f"📡 Obtendo token de acesso...")
        token_response = requests.post(token_url, json=token_payload, timeout=15)
        
        if token_response.status_code != 200:
            logger.error(f"❌ Erro ao obter token SyncPay: {token_response.status_code}")
            logger.error(f"Resposta: {token_response.text}")
            return None
        
        token_data = token_response.json()
        access_token = token_data.get('access_token')
        
        if not access_token:
            logger.error("❌ Token não retornado pela API")
            return None
        
        logger.info("✅ Token obtido com sucesso")
        
        # PASSO 2: Criar pagamento PIX
        payment_id = str(uuid.uuid4())
        
        # Dados do cliente no formato correto da API SyncPay
        client_info = {
            "name": customer_data.get("name", f"Cliente {user_id}"),
            "cpf": "12345678900",  # CPF genérico
            "email": customer_data.get("email", f"cliente{user_id}@example.com"),
            "phone": "11999999999"  # Telefone genérico
        }
        
        # Dados do pagamento no formato correto
        # IMPORTANTE: Configure a URL do webhook para seu domínio
        webhook_url = "https://seu-dominio.com/webhook_syncpay.php"  # ALTERAR PARA SUA URL REAL
        
        payment_payload = {
            "amount": float(amount),
            "description": f"Pagamento {plan_name}",
            "client": client_info,
            "webhook_url": webhook_url
        }
        
        # Headers com Bearer token
        headers = {
            "Authorization": f"Bearer {access_token}",
            "Content-Type": "application/json",
            "Accept": "application/json"
        }
        
        # Fazer requisição para criar PIX
        pix_url = f"{SYNCPAY_BASE_URL}/api/partner/v1/cash-in"
        
        logger.info(f"📡 Criando pagamento PIX...")
        logger.info(f"URL: {pix_url}")
        logger.info(f"Payload: {json.dumps(payment_payload, indent=2)}")
        logger.info(f"Headers: Authorization Bearer {access_token[:30]}...")
        
        response = requests.post(pix_url, json=payment_payload, headers=headers, timeout=30)
        
        logger.info(f"📥 Status Code: {response.status_code}")
        logger.info(f"📥 Response Headers: {dict(response.headers)}")
        logger.info(f"📥 Resposta Completa: {response.text}")
        
        if response.status_code == 200:
            pix_data = response.json()
            pix_code = pix_data.get('pix_code')
            identifier = pix_data.get('identifier')
            
            if not pix_code:
                logger.error("❌ PIX code não retornado pela SyncPay")
                logger.error(f"Resposta completa: {pix_data}")
                return None
            
            # Se não tem identifier, usar ID alternativo ou gerar
            if not identifier:
                identifier = pix_data.get('id') or str(uuid.uuid4())
                logger.warning(f"⚠️ Identifier não retornado, usando: {identifier}")
            
            logger.info(f"✅ PIX Code obtido: {pix_code[:50]}...")
            logger.info(f"✅ Identifier: {identifier}")
            
            # Armazenar pagamento pendente
            pending_payments[user_id] = {
                'payment_id': identifier,
                'amount': amount,
                'plan': plan_name,
                'pix_code': pix_code,
                'gateway': 'syncpay_original',
                'gateway_payment_id': identifier  # CRÍTICO para verificação
            }
            
            event_logger.info(f"✅ PIX SyncPay criado: R$ {amount} - Identifier: {identifier}")
            
            return pix_data
            
        else:
            logger.error(f"❌ Erro ao criar PIX SyncPay: {response.status_code}")
            logger.error(f"Resposta completa: {response.text}")
            return None
            
    except Exception as e:
        logger.error(f"❌ Exceção ao criar PIX SyncPay: {e}")
        import traceback
        logger.error(traceback.format_exc())
        return None

async def create_pix_payment_with_fallback(user_id, amount, plan_name, customer_data):
    """Cria um pagamento PIX usando APENAS SyncPay Original"""
    # FORÇAR USO APENAS DO SYNCPAY - PushynPay DESABILITADO
    current_gateway = 'syncpay_original'
    
    logger.info("🔒 Usando apenas SyncPay Original para pagamentos")
    
    try:
        # Criar pagamento usando SyncPay Original
        result = await create_pix_payment_syncpay_original(user_id, amount, plan_name, customer_data)
        
        if result:
            mark_gateway_success(current_gateway)
            logger.info("✅ Pagamento criado com sucesso via SyncPay")
            return result
        else:
            mark_gateway_failed(current_gateway, "Falha na criação do PIX")
            logger.error("❌ SyncPay falhou ao criar PIX")
            return None
            
    except Exception as e:
        mark_gateway_failed(current_gateway, str(e))
        logger.error(f"❌ Erro no SyncPay: {e}")
        return None

def get_next_bot():
    """Retorna o próximo bot disponível (round-robin)"""
    global bot_rotation_index
    
    if not active_bots:
        logger.error("Nenhum bot ativo disponível")
        return None
    
    # Filtrar apenas bots ativos
    active_tokens = [token for token, info in active_bots.items() if info['status'] == 'active']
    
    if not active_tokens:
        logger.error("Nenhum bot ativo encontrado")
        return None
    
    # Round-robin
    token = active_tokens[bot_rotation_index % len(active_tokens)]
    bot_rotation_index += 1
    
    return active_bots[token]

async def initialize_bot(token):
    """Inicializa um bot individual"""
    try:
        # Inicializando bot
        
        # Criar aplicação do bot
        application = Application.builder().token(token).build()
        
        # Configurar handlers
        await setup_bot_handlers(application, token)
        
        # Testar conexão
        bot = application.bot
        bot_info = await bot.get_me()
        
        event_logger.info(f"Bot inicializado: @{bot_info.username}")
        
        return {
            'application': application,
            'bot': bot,
            'token': token,
            'status': 'active',
            'last_heartbeat': datetime.now(),
            'retry_count': 0
        }
        
    except Exception as e:
        logger.error(f"Erro ao inicializar bot: {e}")
        return None

async def setup_bot_handlers(application, token):
    """Configura os handlers para cada bot"""
    
    # Handler para comando /start
    async def start_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
        """Comando /start"""
        user = update.effective_user
        user_id = user.id
        
        # Verificar rate limiting inteligente
        if not check_rate_limit(user_id, "start"):
            # Usuário em cooldown
            return
        
        event_logger.info(f"/start executado por {user.first_name} (ID: {user_id})")
        add_event('INFO', f'Comando /start executado por {user.first_name}', user_id)
        
        # Adicionar usuário único (só incrementa se for novo usuário)
        is_new_user = add_unique_user(user_id, user.first_name, user.username)
        if is_new_user:
            event_logger.info(f"Novo usuário: {user.first_name} (ID: {user_id})")
        # else: usuário existente
        
        # Adicionar sessão de usuário para downsell
        add_user_session(user_id)
        
        # Mensagem principal
        message_text = """🚷 𝗩𝗢𝗖Ê 𝗔𝗖𝗔𝗕𝗢𝗨 𝗗𝗘 𝗘𝗡𝗧𝗥𝗔𝗥 𝗡𝗢 𝗔𝗕𝗜𝗦𝗠𝗢 — 𝗘 𝗔𝗤𝗨𝗜 𝗡Ã𝗢 𝗘𝗫𝗜𝗦𝗧𝗘 𝗩𝗢𝗟𝗧𝗔.
💎 O maior e mais pr🔞curad🔞 Rateio de Grupos VIPs do Telegram está aberto… mas não por muito tempo.

🔞 OnlyF4ns, Privacy, Close Friends VAZADOS
🔞 Famosas, Nov!nhas +18, Amadoras & Milf's insaciáveis
🔞 L!ves completas, conteúdos escondidos e traições reais gravadas.

🎭 Casais abertos | 🎥 V!d3os de surub4s | 😈 Segredos de inc3sto | 🚨 Fet!ches 🔞cultos do c0rno moderno.

🔥 𝗔𝘁𝘂𝗮𝗹𝗶𝘇𝗮çõ𝗲𝘀 𝗗𝗶á𝗿𝗶𝗮𝘀 — 𝗡𝗮𝗱𝗮 𝗳𝗶𝗰𝗮 𝘃𝗲𝗹𝗵𝗼.
🔒 𝗖𝗼𝗺𝗽𝗿𝗮 𝟭𝟬𝟬% 𝗦𝗲𝗴𝘂𝗿𝗮 — 𝗡𝗶𝗻𝗴𝘂é𝗺 𝗱𝗲𝘀𝗰𝗼𝗯𝗿𝗲.
⚡️ 𝗔𝗰𝗲𝘀𝘀𝗼 𝗜𝗺𝗲𝗱𝗶𝗮𝘁𝗼 — 𝗘𝗺 𝗺𝗲𝗻𝗼𝘀 𝗱𝗲 𝟭 𝗺𝗶𝗻𝘂𝘁𝗼 𝘃𝗼𝗰ê 𝗷á 𝗲𝘀𝘁á 𝗱𝗲𝗻𝘁𝗿𝗼.

❌ Aqui não tem "achismos": são os vídeos que NINGUÉM teria coragem de postar publicamente.
👉 Se você sair agora, nunca mais encontra esse conteúdo.

🎁 𝗕ô𝗻𝘂𝘀 𝗦ó 𝗛𝗼𝗷𝗲: 𝗮𝗼 𝗮𝘀𝘀𝗶𝗻𝗮𝗿, 𝘃𝗼𝗰ê 𝗿𝗲𝗰𝗲𝗯𝗲 𝗮𝗰𝗲𝘀𝘀𝗼 𝘀𝗲𝗰𝗿𝗲𝘁𝗼 𝗮 +𝟰 𝗚𝗿𝘂𝗽𝗼𝘀 𝗩𝗜𝗣'𝘀 𝗼𝗰𝘂𝗹𝘁𝗼𝘀 (𝗻𝗼𝘃!𝗻𝗵𝟰𝘀 +𝟭𝟴, 𝗰𝗮𝘀𝗮𝗱𝗮𝘀 𝗿𝗲𝗮𝗶𝘀, 𝗳𝗹@𝗴𝗿@𝘀 & 𝗺í𝗱𝗶𝗮𝘀 𝗲𝘅𝗰𝗹𝘂í𝗱𝗮𝘀 𝗱𝗮 𝘄𝟯𝗯)."""
        
        # Botões
        keyboard = [
            [InlineKeyboardButton("❌🤫𝐕𝐈𝐓𝐀𝐋𝐈𝐂𝐈𝐎(𝐏𝐑𝐎𝐌𝐎)🤫❌ 𝐩𝐨𝐫 𝟏𝟗.𝟗𝟕", callback_data="vitalicio")],
            [InlineKeyboardButton("❌🤫𝟭 𝗺ê𝘀 🤫❌ 𝐩𝐨𝐫 𝟏𝟒.𝟗𝟕", callback_data="mensal")]
        ]
        reply_markup = InlineKeyboardMarkup(keyboard)
        
        # Enviar vídeo principal via link
        video_link = "https://t.me/MIDIASBOTIS/9"  # Link do vídeo principal
        
        try:
            await update.message.reply_video(
                video=video_link,
                caption=message_text,
                reply_markup=reply_markup,
                read_timeout=30,
                write_timeout=30,
                connect_timeout=30
            )
            # Vídeo enviado com sucesso
        except Exception as e:
            logger.error(f"Erro ao enviar vídeo: {e}")
            # Fallback: enviar apenas texto
            await update.message.reply_text(
                message_text,
                reply_markup=reply_markup
            )
            # Fallback para texto enviado
        
        # Marcar resposta como enviada
        mark_response_sent(user_id)
        
        # Iniciar timers de downsell se configurado
        start_downsell_timers(user_id)
    
    # Handler para botões
    async def button_callback(update: Update, context: ContextTypes.DEFAULT_TYPE):
        """Processa cliques nos botões"""
        query = update.callback_query
        await query.answer()
        
        user = update.effective_user
        user_id = user.id
        
        # CRÍTICO: Obter o token do bot atual que está processando a requisição
        current_bot_token = token  # Usar o token do bot atual
        
        # Verificar rate limiting inteligente
        if not check_rate_limit(user_id, "button"):
            # Usuário em cooldown
            return
        
        # Botão clicado
        
        if query.data == "vitalicio":
            # Order bump para vitalício
            await send_order_bump(query)
        elif query.data == "mensal":
            # Order bump para mensal
            await send_order_bump_mensal(query)
        elif query.data == "aceitar_bonus":
            await create_payment(query, 32.87, "VITALÍCIO + SALA VERMELHA", user_id, current_bot_token)
        elif query.data == "nao_quero_bonus":
            await create_payment(query, 19.97, "VITALÍCIO", user_id, current_bot_token)
        elif query.data == "aceitar_bonus_mensal":
            await create_payment(query, 27.87, "1 MÊS + PACOTE SOMBRIO", user_id, current_bot_token)
        elif query.data == "nao_quero_bonus_mensal":
            await create_payment(query, 14.97, "1 MÊS", user_id, current_bot_token)
        elif query.data.startswith("verificar_pagamento"):
            # Extrair user_id do callback_data
            if "_" in query.data:
                user_id = int(query.data.split("_")[-1])
            else:
                user_id = query.from_user.id
            
            await check_payment_status(query, user_id)
        elif query.data.startswith("contatar_suporte"):
            # Extrair user_id do callback_data
            if "_" in query.data:
                user_id = int(query.data.split("_")[-1])
            else:
                user_id = query.from_user.id
            
            await send_support_message(query, user_id)
        
        # Marcar resposta como enviada
        mark_response_sent(user_id)
    
    # Handler para mensagens
    async def handle_message(update: Update, context: ContextTypes.DEFAULT_TYPE):
        """Processa mensagens"""
        user = update.effective_user
        user_id = user.id
        text = update.message.text
        
        # Verificar rate limiting inteligente
        if not check_rate_limit(user_id, "message"):
            # Usuário em cooldown
            return
        
        # Mensagem recebida
        
        response = f"Você disse: {text}\nUse /help para comandos!"
        await update.message.reply_text(response)
        # Resposta enviada
        
        # Marcar resposta como enviada
        mark_response_sent(user_id)
    
    # Handler para /help
    async def help_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
        """Comando /help"""
        # Comando /help executado
        await update.message.reply_text("Comandos:\n/start - Iniciar\n/help - Ajuda\n/info - Info")
    
    # Handler para /info
    async def info_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
        """Comando /info"""
        user = update.effective_user
        # Comando /info executado
        await update.message.reply_text(f"Bot Info:\nUsuário: {user.first_name}\nID: {user.id}")
    
    # Adicionar handlers
    application.add_handler(CommandHandler("start", start_command))
    application.add_handler(CommandHandler("help", help_command))
    application.add_handler(CommandHandler("info", info_command))
    
    # Handlers para comandos administrativos
    application.add_handler(CommandHandler("admin", admin_with_args_handler))
    application.add_handler(CommandHandler("gw", gateway_command_handler))
    application.add_handler(CommandHandler("meuid", admin_command_handler))
    application.add_handler(CommandHandler("notificacoes", admin_command_handler))
    application.add_handler(CommandHandler("ativar_notificacoes", admin_command_handler))
    application.add_handler(CommandHandler("desativar_notificacoes", admin_command_handler))
    application.add_handler(CommandHandler("testar_notificacao", admin_command_handler))
    application.add_handler(CommandHandler("testar_notificacao_simples", admin_command_handler))
    application.add_handler(CommandHandler("testar_mensagem", admin_command_handler))
    application.add_handler(CommandHandler("teste_producao", admin_command_handler))
    application.add_handler(CommandHandler("verificar_notificacoes", admin_command_handler))
    application.add_handler(CommandHandler("teste_final_producao", admin_command_handler))
    application.add_handler(CommandHandler("testar_chat_privado", admin_command_handler))
    application.add_handler(CommandHandler("debug_notificacoes", admin_command_handler))
    application.add_handler(CommandHandler("iniciar_conversas", admin_command_handler))
    
    application.add_handler(CallbackQueryHandler(button_callback))
    application.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, handle_message))
    
    # Handlers configurados

async def admin_command_handler(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Handler para comandos administrativos usando argumentos"""
    global SALE_NOTIFICATIONS_ENABLED
    user_id = update.effective_user.id
    
    if not is_admin(user_id):
        await update.message.reply_text("❌ Acesso negado. Apenas administradores podem usar este comando.")
        return
    
    command = update.message.text.lower()
    
    if command == '/admin':
        help_text = """🔧 **COMANDOS ADMINISTRATIVOS**

**Comandos principais:**
• `/admin ativar <pushyn|sync>` - Ativa gateway
• `/admin desativar <pushyn|sync>` - Desativa gateway  
• `/admin status` - Status dos gateways
• `/admin prioridade <pushyn|sync> <1|2>` - Define prioridade
• `/admin testar <pushyn|sync>` - Testa gateway

**Comandos rápidos:**
• `/gw pushyn` - Ativa PushynPay
• `/gw sync` - Ativa SyncPay Original
• `/gw status` - Status dos gateways

**Notificações de vendas:**
• `/notificacoes` - Status das notificações
• `/ativar_notificacoes` - Ativa notificações
• `/desativar_notificacoes` - Desativa notificações
• `/testar_notificacao` - Testa sistema de notificações
• `/testar_notificacao_simples` - Teste simplificado
• `/testar_mensagem` - Testa envio de mensagem simples
• `/teste_producao` - Teste final de produção
• `/verificar_notificacoes` - Verifica se está recebendo no Telegram
• `/teste_final_producao` - Teste definitivo de produção
• `/testar_chat_privado` - Testa chat privado específico
• `/debug_notificacoes` - Debug detalhado do sistema

**Outros:**
• `/meuid` - Mostra seu ID"""
        await update.message.reply_text(help_text, parse_mode='Markdown')
    
    elif command == '/meuid':
        user = update.effective_user
        await update.message.reply_text(f"🆔 Seu ID: `{user.id}`\n\nNome: {user.first_name}\nUsername: @{user.username or 'N/A'}", parse_mode='Markdown')
    
    elif command == '/testar':
        await update.message.reply_text("🧪 Para testar PushynPay, use: `/admin testar pushyn`")
    
    elif command == '/notificacoes':
        status = "✅ ATIVADAS" if SALE_NOTIFICATIONS_ENABLED else "❌ DESATIVADAS"
        await update.message.reply_text(f"📢 **STATUS DAS NOTIFICAÇÕES DE VENDAS**\n\n{status}\n\nChat ID: `{ADMIN_NOTIFICATION_CHAT_ID}`", parse_mode='Markdown')
    
    elif command == '/ativar_notificacoes':
        SALE_NOTIFICATIONS_ENABLED = True
        await update.message.reply_text("✅ **NOTIFICAÇÕES DE VENDAS ATIVADAS!**\n\nAgora você receberá notificações detalhadas sempre que uma venda for confirmada.", parse_mode='Markdown')
        event_logger.info("Notificações de vendas ativadas pelo admin")
    
    elif command == '/desativar_notificacoes':
        SALE_NOTIFICATIONS_ENABLED = False
        await update.message.reply_text("❌ **NOTIFICAÇÕES DE VENDAS DESATIVADAS!**\n\nVocê não receberá mais notificações de vendas.", parse_mode='Markdown')
        event_logger.info("Notificações de vendas desativadas pelo admin")
    
    elif command == '/testar_notificacao':
        # Testar sistema de notificações - VERSÃO PRODUÇÃO
        await update.message.reply_text("🧪 **INICIANDO TESTE DE NOTIFICAÇÃO...**\n\nVerificando configurações...", parse_mode='Markdown')
        
        # Verificar configurações
        notifications_status = "✅ SIM" if SALE_NOTIFICATIONS_ENABLED else "❌ NÃO"
        debug_info = f"""🔍 **DEBUG - CONFIGURAÇÕES:**

📢 Notificações ativas: {notifications_status}
👤 Admin Chat ID: `{ADMIN_NOTIFICATION_CHAT_ID}`
🤖 Bots ativos: {len(active_bots)}

📋 **Dados do teste:**"""
        
        await update.message.reply_text(debug_info, parse_mode='Markdown')
        
        test_payment_info = {
            'payment_id': 'test_' + str(uuid.uuid4())[:8],
            'amount': 19.97,
            'plan': 'VITALÍCIO',
            'gateway': 'pushynpay',
            'gateway_payment_id': str(uuid.uuid4())
        }
        
        test_user_info = {
            'user_id': user_id,
            'first_name': update.effective_user.first_name or 'Teste',
            'last_name': update.effective_user.last_name or '',
            'username': update.effective_user.username or 'teste',
            'document': '123.456.789-00'
        }
        
        test_bot_info = {
            'username': 'teste_bot',
            'id': '12345',
            'first_name': 'Bot Teste'
        }
        
        # Tentar enviar notificação
        try:
            await update.message.reply_text("🔄 **ENVIANDO NOTIFICAÇÃO DE TESTE...**", parse_mode='Markdown')
            
            # Chamar função com timeout
            await asyncio.wait_for(
                send_sale_notification_to_admin(test_payment_info, test_user_info, test_bot_info),
                timeout=30.0
            )
            
            await update.message.reply_text("✅ **TESTE CONCLUÍDO COM SUCESSO!**\n\nVerifique se você recebeu a notificação de teste.\n\nSe não recebeu, verifique os logs do bot.", parse_mode='Markdown')
            
        except asyncio.TimeoutError:
            await update.message.reply_text("⏰ **TIMEOUT NO TESTE!**\n\nA função demorou mais de 30 segundos para responder.\n\nVerifique os logs para mais detalhes.", parse_mode='Markdown')
        except Exception as e:
            await update.message.reply_text(f"❌ **ERRO NO TESTE:**\n\n`{str(e)}`\n\nVerifique os logs para mais detalhes.", parse_mode='Markdown')
    
    elif command == '/testar_notificacao_simples':
        # Teste simplificado de notificação
        await update.message.reply_text("🧪 **TESTE SIMPLIFICADO DE NOTIFICAÇÃO...**", parse_mode='Markdown')
        
        try:
            # Mensagem de teste simplificada
            test_message = """🎉 **Pagamento Aprovado!**

🤖 **Bot:** @teste_bot
⚙️ **ID Bot:** 12345

👤 **ID Cliente:** 7676333385
🔗 **Username:** @robertinhaop1
👤 **Nome de Perfil:** Roberta
👤 **Nome Completo:** Roberta Teste
📄 **CPF/CNPJ:** 123.456.789-00

🌍 **Idioma:** pt-br
⭐ **Telegram Premium:** Não
📦 **Categoria:** Plano Normal
🎁 **Plano:** **VITALÍCIO**
📅 **Duração:** Vitalício

💰 **Valor:** R$19.97
💰 **Valor Líquido:** R$18.77

⏱️ **Tempo Conversão:** 0d 0h 2m 15s
🔑 **ID Transação Interna:** test_123
🏷️ **ID Transação Gateway:** `test-uuid-123`
💱 **Tipo Moeda:** BRL
💳 **Método Pagamento:** pix
🏢 **Plataforma Pagamento:** pushynpay"""
            
            # Tentar enviar diretamente
            message_sent = False
            
            for token, bot_data in active_bots.items():
                if bot_data['status'] == 'active':
                    try:
                        bot = bot_data['bot']
                        await bot.send_message(
                            chat_id=ADMIN_NOTIFICATION_CHAT_ID,
                            text=test_message,
                            parse_mode='Markdown'
                        )
                        message_sent = True
                        await update.message.reply_text(f"✅ **NOTIFICAÇÃO SIMPLES ENVIADA!**\n\nBot usado: {token[:20]}...\n\nVerifique se você recebeu a notificação.", parse_mode='Markdown')
                        break
                    except Exception as e:
                        logger.error(f"Erro ao enviar notificação simples: {e}")
                        continue
            
            if not message_sent:
                await update.message.reply_text("❌ **FALHA AO ENVIAR NOTIFICAÇÃO SIMPLES!**", parse_mode='Markdown')
                
        except Exception as e:
            await update.message.reply_text(f"❌ **ERRO NO TESTE SIMPLES:**\n\n`{str(e)}`", parse_mode='Markdown')
    
    elif command == '/testar_mensagem':
        # Teste simples de envio de mensagem
        await update.message.reply_text("🧪 **TESTANDO ENVIO DE MENSAGEM SIMPLES...**", parse_mode='Markdown')
        
        try:
            # Tentar enviar uma mensagem simples para o admin
            message_sent = False
            
            for token, bot_data in active_bots.items():
                if bot_data['status'] == 'active':
                    try:
                        bot = bot_data['bot']
                        await bot.send_message(
                            chat_id=ADMIN_NOTIFICATION_CHAT_ID,
                            text="🧪 **TESTE DE MENSAGEM SIMPLES**\n\nSe você recebeu esta mensagem, o bot consegue enviar notificações para você!",
                            parse_mode='Markdown'
                        )
                        message_sent = True
                        await update.message.reply_text(f"✅ **MENSAGEM SIMPLES ENVIADA!**\n\nBot usado: {token[:20]}...\n\nVerifique se você recebeu a mensagem de teste.", parse_mode='Markdown')
                        break
                    except Exception as e:
                        logger.error(f"Erro ao enviar mensagem simples: {e}")
                        continue
            
            if not message_sent:
                await update.message.reply_text("❌ **FALHA AO ENVIAR MENSAGEM SIMPLES!**\n\nNenhum bot conseguiu enviar a mensagem.", parse_mode='Markdown')
                
        except Exception as e:
            await update.message.reply_text(f"❌ **ERRO NO TESTE DE MENSAGEM:**\n\n`{str(e)}`", parse_mode='Markdown')
    
    elif command == '/teste_producao':
        # Teste final de produção - VERSÃO DEFINITIVA
        await update.message.reply_text("🚀 **TESTE FINAL DE PRODUÇÃO**\n\nExecutando teste completo do sistema de notificações...", parse_mode='Markdown')
        
        try:
            # Verificar se notificações estão ativas
            if not SALE_NOTIFICATIONS_ENABLED:
                await update.message.reply_text("❌ **NOTIFICAÇÕES DESATIVADAS!**\n\nExecute `/ativar_notificacoes` primeiro.", parse_mode='Markdown')
                return
            
            # Verificar se há bots ativos
            if not active_bots:
                await update.message.reply_text("❌ **NENHUM BOT ATIVO!**\n\nSistema não pode enviar notificações.", parse_mode='Markdown')
                return
            
            # Dados de teste realistas
            test_payment_info = {
                'payment_id': 'prod_' + str(uuid.uuid4())[:8],
                'amount': 19.97,
                'plan': 'VITALÍCIO',
                'gateway': 'pushynpay',
                'gateway_payment_id': str(uuid.uuid4())
            }
            
            test_user_info = {
                'user_id': user_id,
                'first_name': update.effective_user.first_name or 'Cliente',
                'last_name': update.effective_user.last_name or '',
                'username': update.effective_user.username or 'cliente',
                'document': '123.456.789-00'
            }
            
            test_bot_info = {
                'username': 'bot_producao',
                'id': '99999',
                'first_name': 'Bot Produção'
            }
            
            # Enviar notificação de teste
            await send_sale_notification_to_admin(test_payment_info, test_user_info, test_bot_info)
            
            await update.message.reply_text("✅ **TESTE DE PRODUÇÃO CONCLUÍDO!**\n\n🎯 Sistema de notificações funcionando perfeitamente!\n\n📱 Verifique se você recebeu a notificação de teste.\n\n🚀 Sistema pronto para produção!", parse_mode='Markdown')
            
        except Exception as e:
            await update.message.reply_text(f"❌ **ERRO NO TESTE DE PRODUÇÃO:**\n\n`{str(e)}`\n\nVerifique os logs para detalhes.", parse_mode='Markdown')
    
    elif command == '/verificar_notificacoes':
        # Verificar se você está recebendo notificações no Telegram
        await update.message.reply_text("🔍 **VERIFICANDO NOTIFICAÇÕES NO TELEGRAM...**\n\nEnviando notificação de teste diretamente para você...", parse_mode='Markdown')
        
        try:
            # Verificar configurações
            await update.message.reply_text(f"📋 **CONFIGURAÇÕES:**\n\nAdmin ID: `{ADMIN_USER_ID}`\nChat ID: `{ADMIN_NOTIFICATION_CHAT_ID}`\nNotificações: {'✅ ATIVAS' if SALE_NOTIFICATIONS_ENABLED else '❌ DESATIVAS'}", parse_mode='Markdown')
            
            # Enviar notificação de teste diretamente
            test_message = """🎉 Pagamento Aprovado!

🤖 Bot: @teste_bot
⚙️ ID Bot: 12345

👤 ID Cliente: 7676333385
🔗 Username: @robertinhaop1
👤 Nome de Perfil: Roberta
👤 Nome Completo: Roberta Teste
📄 CPF/CNPJ: 123.456.789-00

🌍 Idioma: pt-br
⭐ Telegram Premium: Não
📦 Categoria: Plano Normal
🎁 Plano: VITALÍCIO
📅 Duração: Vitalício

💰 Valor: R$19.97
💰 Valor Líquido: R$18.77

⏱️ Tempo Conversão: 0d 0h 2m 15s
🔑 ID Transação Interna: test123
🏷️ ID Transação Gateway: test-uuid-123
💱 Tipo Moeda: BRL
💳 Método Pagamento: pix
🏢 Plataforma Pagamento: pushynpay"""
            
            # Tentar enviar para todos os bots
            message_sent = False
            
            for token, bot_data in active_bots.items():
                if bot_data['status'] == 'active':
                    try:
                        bot = bot_data['bot']
                        await bot.send_message(
                            chat_id=ADMIN_NOTIFICATION_CHAT_ID,
                            text=test_message,
                            parse_mode=None
                        )
                        message_sent = True
                        await update.message.reply_text(f"✅ **NOTIFICAÇÃO ENVIADA COM SUCESSO!**\n\nBot usado: {token[:20]}...\n\n📱 Verifique se você recebeu a notificação acima no seu chat!", parse_mode='Markdown')
                        break
                    except Exception as e:
                        logger.error(f"Erro ao enviar notificação: {e}")
                        continue
            
            if not message_sent:
                await update.message.reply_text("❌ **FALHA AO ENVIAR NOTIFICAÇÃO!**\n\nNenhum bot conseguiu enviar a mensagem.", parse_mode='Markdown')
                
        except Exception as e:
            await update.message.reply_text(f"❌ **ERRO:**\n\n`{str(e)}`", parse_mode='Markdown')
    
    elif command == '/teste_final_producao':
        # Teste final de produção - VERSÃO DEFINITIVA ROBUSTA
        await update.message.reply_text("🚀 **TESTE FINAL DE PRODUÇÃO - VERSÃO DEFINITIVA**\n\nExecutando teste completo e robusto do sistema...", parse_mode='Markdown')
        
        try:
            # Verificar se notificações estão ativas
            if not SALE_NOTIFICATIONS_ENABLED:
                await update.message.reply_text("❌ **NOTIFICAÇÕES DESATIVADAS!**\n\nExecute `/ativar_notificacoes` primeiro.", parse_mode='Markdown')
                return
            
            # Verificar se há bots ativos
            if not active_bots:
                await update.message.reply_text("❌ **NENHUM BOT ATIVO!**\n\nSistema não pode enviar notificações.", parse_mode='Markdown')
                return
            
            # Verificar configurações críticas
            if ADMIN_NOTIFICATION_CHAT_ID != ADMIN_USER_ID:
                await update.message.reply_text("⚠️ **CONFIGURAÇÃO INCONSISTENTE!**\n\nAdmin Chat ID diferente do Admin User ID.", parse_mode='Markdown')
                return
            
            # Dados de teste realistas com validação
            test_payment_info = {
                'payment_id': 'prod_' + str(uuid.uuid4())[:8],
                'amount': 19.97,
                'plan': 'VITALÍCIO',
                'gateway': 'pushynpay',
                'gateway_payment_id': str(uuid.uuid4()),
                'created_at': datetime.now().isoformat()
            }
            
            test_user_info = {
                'user_id': user_id,
                'first_name': update.effective_user.first_name or 'Cliente',
                'last_name': update.effective_user.last_name or '',
                'username': update.effective_user.username or 'cliente',
                'document': '123.456.789-00'
            }
            
            test_bot_info = {
                'username': 'bot_producao_final',
                'id': '99999',
                'first_name': 'Bot Produção Final'
            }
            
            # Enviar notificação de teste com timeout
            await update.message.reply_text("🔄 **ENVIANDO NOTIFICAÇÃO DE TESTE...**", parse_mode='Markdown')
            
            try:
                await asyncio.wait_for(
                    send_sale_notification_to_admin(test_payment_info, test_user_info, test_bot_info),
                    timeout=30.0
                )
                
                # Mensagem de sucesso sem formatação problemática
                success_message = "✅ **TESTE FINAL CONCLUÍDO COM SUCESSO!**\n\n"
                success_message += "🎯 Sistema de notificações funcionando perfeitamente!\n"
                success_message += "📱 Verifique se você recebeu a notificação de teste.\n"
                success_message += "🚀 Sistema pronto para produção!\n\n"
                success_message += "📊 **RESUMO DO SISTEMA:**\n"
                success_message += "• Notificações: ✅ ATIVAS\n"
                success_message += f"• Bots ativos: ✅ {len(active_bots)}\n"
                success_message += "• Configurações: ✅ VÁLIDAS\n"
                success_message += "• Dados reais: ✅ IMPLEMENTADOS"
                
                await update.message.reply_text(success_message, parse_mode='Markdown')
                
            except asyncio.TimeoutError:
                await update.message.reply_text("⏰ **TIMEOUT NO TESTE!**\n\nA função demorou mais de 30 segundos.\nVerifique os logs para detalhes.", parse_mode='Markdown')
            
        except Exception as e:
            await update.message.reply_text(f"❌ **ERRO NO TESTE FINAL:**\n\n`{str(e)}`\n\nVerifique os logs para detalhes.", parse_mode='Markdown')
    
    elif command == '/testar_chat_privado':
        # Teste específico para chat privado
        await update.message.reply_text("🔍 **TESTANDO CHAT PRIVADO...**\n\nEnviando mensagem diretamente para você...", parse_mode='Markdown')
        
        try:
            # Verificar configurações
            await update.message.reply_text(f"📋 **CONFIGURAÇÕES:**\n\nAdmin ID: `{ADMIN_USER_ID}`\nChat ID: `{ADMIN_NOTIFICATION_CHAT_ID}`\nSeu ID atual: `{user_id}`", parse_mode='Markdown')
            
            # Tentar enviar mensagem simples para o chat privado
            message_sent = False
            error_details = []
            
            for token, bot_data in active_bots.items():
                if bot_data['status'] == 'active':
                    try:
                        bot = bot_data['bot']
                        
                        # Tentar enviar mensagem simples
                        await bot.send_message(
                            chat_id=ADMIN_NOTIFICATION_CHAT_ID,
                            text="🔔 **TESTE DE CHAT PRIVADO**\n\nSe você recebeu esta mensagem, o sistema está funcionando!\n\nBot: " + token[:20] + "...",
                            parse_mode='Markdown'
                        )
                        
                        message_sent = True
                        await update.message.reply_text(f"✅ **MENSAGEM ENVIADA COM SUCESSO!**\n\nBot usado: {token[:20]}...\n\n📱 Verifique se você recebeu a mensagem no seu chat privado!", parse_mode='Markdown')
                        break
                        
                    except Exception as e:
                        error_details.append(f"Bot {token[:20]}: {str(e)}")
                        continue
            
            if not message_sent:
                error_summary = "\n".join(error_details[:3])  # Mostrar apenas os primeiros 3 erros
                await update.message.reply_text(f"❌ **FALHA AO ENVIAR MENSAGEM!**\n\nErros encontrados:\n{error_summary}\n\n💡 **SOLUÇÃO:** Você precisa iniciar uma conversa com os bots primeiro!", parse_mode='Markdown')
                
        except Exception as e:
            await update.message.reply_text(f"❌ **ERRO:**\n\n`{str(e)}`", parse_mode='Markdown')
    
    elif command == '/debug_notificacoes':
        # Debug específico para notificações
        await update.message.reply_text("🔍 **DEBUG DETALHADO DAS NOTIFICAÇÕES**\n\nAnalisando sistema completo...", parse_mode='Markdown')
        
        try:
            # Verificar todas as configurações
            debug_info = f"""📋 **CONFIGURAÇÕES DETALHADAS:**

🔧 Admin User ID: `{ADMIN_USER_ID}`
🔧 Admin Chat ID: `{ADMIN_NOTIFICATION_CHAT_ID}`
🔧 Seu ID atual: `{user_id}`
🔧 Notificações ativas: {'✅ SIM' if SALE_NOTIFICATIONS_ENABLED else '❌ NÃO'}
🔧 Bots ativos: {len(active_bots)}

🤖 **LISTA DE BOTS ATIVOS:**"""
            
            bot_list = ""
            for i, (token, bot_data) in enumerate(active_bots.items(), 1):
                if bot_data['status'] == 'active':
                    try:
                        bot = bot_data['bot']
                        bot_me = await bot.get_me()
                        bot_list += f"\n{i}. @{bot_me.username} (ID: {bot_me.id})"
                    except Exception as e:
                        bot_list += f"\n{i}. Bot {token[:20]}... (Erro: {str(e)[:50]})"
            
            debug_info += bot_list
            
            await update.message.reply_text(debug_info, parse_mode='Markdown')
            
            # Testar envio real
            await update.message.reply_text("🧪 **TESTANDO ENVIO REAL...**", parse_mode='Markdown')
            
            test_message = "🔔 **TESTE DE DEBUG**\n\nEsta é uma mensagem de teste para verificar se o sistema está funcionando.\n\nSe você recebeu esta mensagem, o problema está resolvido!"
            
            message_sent = False
            error_log = []
            
            for token, bot_data in active_bots.items():
                if bot_data['status'] == 'active':
                    try:
                        bot = bot_data['bot']
                        bot_me = await bot.get_me()
                        
                        await bot.send_message(
                            chat_id=ADMIN_NOTIFICATION_CHAT_ID,
                            text=test_message,
                            parse_mode='Markdown'
                        )
                        
                        message_sent = True
                        await update.message.reply_text(f"✅ **MENSAGEM ENVIADA COM SUCESSO!**\n\nBot usado: @{bot_me.username}\n\n📱 Verifique se você recebeu a mensagem!", parse_mode='Markdown')
                        break
                        
                    except Exception as e:
                        error_log.append(f"@{bot_me.username if 'bot_me' in locals() else 'bot_desconhecido'}: {str(e)}")
                        continue
            
            if not message_sent:
                error_summary = "\n".join(error_log[:5])
                await update.message.reply_text(f"❌ **FALHA NO ENVIO!**\n\nErros encontrados:\n{error_summary}\n\n💡 **SOLUÇÃO:** Inicie uma conversa com os bots primeiro!", parse_mode='Markdown')
                
        except Exception as e:
            await update.message.reply_text(f"❌ **ERRO NO DEBUG:**\n\n`{str(e)}`", parse_mode='Markdown')
    
    elif command == '/iniciar_conversas':
        # Comando para iniciar conversas com todos os bots
        await update.message.reply_text("🤖 **INICIANDO CONVERSAS COM TODOS OS BOTS**\n\nEnviando mensagem inicial para cada bot...", parse_mode='Markdown')
        
        try:
            success_count = 0
            error_count = 0
            
            for token, bot_data in active_bots.items():
                if bot_data['status'] == 'active':
                    try:
                        bot = bot_data['bot']
                        bot_me = await bot.get_me()
                        
                        # Enviar mensagem inicial para iniciar a conversa
                        await bot.send_message(
                            chat_id=ADMIN_NOTIFICATION_CHAT_ID,
                            text=f"🤖 **Bot {bot_me.username} conectado!**\n\nAgora você receberá notificações de vendas deste bot.",
                            parse_mode='Markdown'
                        )
                        
                        success_count += 1
                        
                    except Exception as e:
                        error_count += 1
                        logger.error(f"Erro ao iniciar conversa com bot {token[:20]}: {e}")
                        continue
            
            # Resultado
            result_message = f"""✅ **CONVERSAS INICIADAS!**

📊 **RESULTADO:**
• ✅ Sucessos: {success_count}
• ❌ Erros: {error_count}
• 🤖 Total de bots: {len(active_bots)}

💡 **PRÓXIMO PASSO:**
Agora teste uma venda real para ver se as notificações chegam!"""
            
            await update.message.reply_text(result_message, parse_mode='Markdown')
            
        except Exception as e:
            await update.message.reply_text(f"❌ **ERRO:**\n\n`{str(e)}`", parse_mode='Markdown')
    
    else:
        await update.message.reply_text("❌ Comando administrativo não reconhecido")

async def admin_with_args_handler(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Handler para /admin com argumentos"""
    user_id = update.effective_user.id
    
    if not is_admin(user_id):
        await update.message.reply_text("❌ Acesso negado.")
        return
    
    if not context.args:
        await update.message.reply_text("Uso: /admin <acao> [gateway] [prioridade]")
        return
    
    action = context.args[0].lower()
    
    if action == "ativar":
        if len(context.args) < 2:
            await update.message.reply_text("Uso: /admin ativar <pushyn|sync>")
            return
        
        gateway = context.args[1].lower()
        if gateway == "pushyn":
            if activate_gateway('pushynpay'):
                await update.message.reply_text("✅ Gateway PushynPay ATIVADO!")
            else:
                await update.message.reply_text("❌ Erro ao ativar gateway PushynPay")
        elif gateway == "sync":
            if activate_gateway('syncpay_original'):
                await update.message.reply_text("✅ Gateway SyncPay Original ATIVADO!")
            else:
                await update.message.reply_text("❌ Erro ao ativar gateway SyncPay Original")
        else:
            await update.message.reply_text("❌ Gateway inválido. Use: pushyn ou sync")
    
    elif action == "desativar":
        if len(context.args) < 2:
            await update.message.reply_text("Uso: /admin desativar <pushyn|sync>")
            return
        
        gateway = context.args[1].lower()
        if gateway == "pushyn":
            if deactivate_gateway('pushynpay'):
                await update.message.reply_text("❌ Gateway PushynPay DESATIVADO!")
            else:
                await update.message.reply_text("❌ Erro ao desativar gateway PushynPay")
        elif gateway == "sync":
            if deactivate_gateway('syncpay_original'):
                await update.message.reply_text("❌ Gateway SyncPay Original DESATIVADO!")
            else:
                await update.message.reply_text("❌ Erro ao desativar gateway SyncPay Original")
        else:
            await update.message.reply_text("❌ Gateway inválido. Use: pushyn ou sync")
    
    elif action == "status":
        status_text = get_gateway_status_text()
        await update.message.reply_text(status_text, parse_mode='Markdown')
    
    elif action == "prioridade":
        if len(context.args) < 3:
            await update.message.reply_text("Uso: /admin prioridade <pushyn|sync> <1|2>")
            return
        
        gateway = context.args[1].lower()
        priority = int(context.args[2])
        
        if gateway == "pushyn":
            if set_gateway_priority('pushynpay', priority):
                await update.message.reply_text(f"🎯 PushynPay definido como PRIORIDADE {priority}!")
            else:
                await update.message.reply_text("❌ Erro ao alterar prioridade")
        elif gateway == "sync":
            if set_gateway_priority('syncpay_original', priority):
                await update.message.reply_text(f"🎯 SyncPay Original definido como PRIORIDADE {priority}!")
            else:
                await update.message.reply_text("❌ Erro ao alterar prioridade")
        else:
            await update.message.reply_text("❌ Gateway inválido. Use: pushyn ou sync")
    
    elif action == "testar":
        if len(context.args) < 2:
            await update.message.reply_text("Uso: /admin testar <pushyn|sync>")
            return
        
        gateway = context.args[1].lower()
        if gateway == "pushyn":
            await update.message.reply_text("🧪 Testando PushinPay...")
            
            # Dados de teste
            test_customer = {
                "name": "Teste PushynPay",
                "email": "teste@pushynpay.com",
                "document": "12345678900"
            }
            
            try:
                result = await create_pix_payment_pushynpay(
                    user_id, 0.50, "Teste PushynPay", test_customer  # R$ 0,50 = 50 centavos
                )
                
                if result:
                    pix_code = result.get('qr_code') or result.get('pix_code') or result.get('code')
                    if pix_code:
                        await update.message.reply_text(f"✅ PushynPay FUNCIONANDO!\n\n🎯 Código PIX: `{pix_code}`", parse_mode='Markdown')
                    else:
                        await update.message.reply_text(f"⚠️ PushinPay respondeu mas sem código PIX:\n```json\n{result}\n```", parse_mode='Markdown')
                else:
                    await update.message.reply_text(
                        "❌ **PUSHYNPAY FALHOU**\n\n"
                        "🔍 **POSSÍVEIS CAUSAS:**\n"
                        "• Token inválido ou expirado\n"
                        "• Valor mínimo: R$ 0,50\n"
                        "• Problemas de conectividade\n\n"
                        "🛠️ **SOLUÇÕES:**\n"
                        "• Verificar token PushynPay\n"
                        "• Usar valor mínimo R$ 0,50\n"
                        "• Contatar suporte PushynPay",
                        parse_mode='Markdown'
                    )
                    
            except Exception as e:
                await update.message.reply_text(f"❌ Erro no teste PushynPay: {e}")
                
        elif gateway == "sync":
            await update.message.reply_text("🧪 Testando SyncPay Original...")
            
            test_customer = {
                "name": "Teste SyncPay",
                "email": "teste@syncpay.com", 
                "document": "12345678900"
            }
            
            try:
                result = await create_pix_payment_syncpay_original(
                    user_id, 1.00, "Teste SyncPay", test_customer
                )
                
                if result:
                    pix_code = result.get('pix_code') or result.get('qr_code') or result.get('code')
                    if pix_code:
                        await update.message.reply_text(f"✅ SyncPay Original FUNCIONANDO!\n\n🎯 Código PIX: `{pix_code}`", parse_mode='Markdown')
                    else:
                        await update.message.reply_text(f"⚠️ SyncPay respondeu mas sem código PIX:\n```json\n{result}\n```", parse_mode='Markdown')
                else:
                    await update.message.reply_text("❌ SyncPay Original FALHOU - Verifique os logs para detalhes")
                    
            except Exception as e:
                await update.message.reply_text(f"❌ Erro no teste SyncPay: {e}")
        else:
            await update.message.reply_text("❌ Gateway inválido para teste. Use: pushyn ou sync")
    
    else:
        await update.message.reply_text("❌ Ação inválida. Use: ativar, desativar, status, prioridade, testar")

async def gateway_command_handler(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Handler para /gw com argumentos"""
    user_id = update.effective_user.id
    
    if not is_admin(user_id):
        await update.message.reply_text("❌ Acesso negado.")
        return
    
    if not context.args:
        await update.message.reply_text("Uso: /gw <pushyn|sync|status>")
        return
    
    action = context.args[0].lower()
    
    if action == "pushyn":
        if activate_gateway('pushynpay'):
            await update.message.reply_text("✅ Gateway PushynPay ATIVADO!")
        else:
            await update.message.reply_text("❌ Erro ao ativar gateway PushynPay")
    
    elif action == "sync":
        if activate_gateway('syncpay_original'):
            await update.message.reply_text("✅ Gateway SyncPay Original ATIVADO!")
        else:
            await update.message.reply_text("❌ Erro ao ativar gateway SyncPay Original")
    
    elif action == "status":
        status_text = get_gateway_status_text()
        await update.message.reply_text(status_text, parse_mode='Markdown')
    
    else:
        await update.message.reply_text("❌ Ação inválida. Use: pushyn, sync, status")

async def send_order_bump(query):
    """Envia order bump com vídeo e botões"""
    # Mensagem do order bump (SALA VERMELHA)
    order_bump_text = """📦 DESBLOQUEAR SALA VERMELHA 📦

🚷 Arquivos deletados do servidor principal e salvos só pra essa liberação.
✅ Amador das faveladas
✅ Amador com o pai depois do banho ⭐️🤫
✅ Vídeos que muitos procuram várias países.
✅ Conteúdo de cameras com áudio original.
💥 Ative agora e leva 1 grupo s3cr3to bônus."""
    
    # Botões do order bump
    keyboard = [
        [InlineKeyboardButton("✅ Aceitar Oportunidade", callback_data="aceitar_bonus")],
        [InlineKeyboardButton("❌ Não Quero Bônus", callback_data="nao_quero_bonus")]
    ]
    reply_markup = InlineKeyboardMarkup(keyboard)
    
    # Enviar vídeo do order bump via link
    video_link = "https://t.me/MIDIASBOTIS/4"  # Link do order bump vitalício
    
    try:
            await query.message.reply_video(
            video=video_link,
                caption=order_bump_text,
                reply_markup=reply_markup
            )
        # Order bump enviado
    except Exception as e:
        logger.error(f"Erro ao enviar vídeo do order bump: {e}")
        await query.edit_message_text(order_bump_text, reply_markup=reply_markup)
        # Fallback para texto

async def send_order_bump_mensal(query):
    """Envia order bump mensal com vídeo e botões"""
    # Mensagem do order bump mensal (PACOTE SOMBRIO)
    order_bump_text = """📦 DESBLOQUEAR PACOTE SOMBRIO 📦

🚷 Arquivos esquecidos e salvos só pra essa liberação.
✅ Amador das faveladas
✅ Amador com o pai depois do banho ⭐️🤫
✅ Vídeos que já foi esquecidos em vários países.
✅ Conteúdo de cameras com áudio original.
💥 Ative agora e leva 1 grupo s3cr3to bônus."""
    
    # Botões do order bump mensal
    keyboard = [
        [InlineKeyboardButton("✅ Aceitar Oportunidade", callback_data="aceitar_bonus_mensal")],
        [InlineKeyboardButton("❌ Não Quero Bônus", callback_data="nao_quero_bonus_mensal")]
    ]
    reply_markup = InlineKeyboardMarkup(keyboard)
    
    # Enviar vídeo do order bump mensal via link
    video_link = "https://t.me/MIDIASBOTIS/3"  # Link do order bump mensal
    
    try:
            await query.message.reply_video(
            video=video_link,
                caption=order_bump_text,
                reply_markup=reply_markup
            )
        # Order bump mensal enviado
    except Exception as e:
        logger.error(f"Erro ao enviar vídeo do order bump mensal: {e}")
        await query.edit_message_text(order_bump_text, reply_markup=reply_markup)
        # Fallback para texto

async def create_payment(query, amount, description, user_id, bot_token=None):
    """Cria pagamento PIX com fallback simples entre gateways"""
    try:
        logger.info("=" * 60)
        logger.info("🔵 INICIANDO CRIAÇÃO DE PAGAMENTO")
        logger.info(f"User ID: {user_id}")
        logger.info(f"Amount: R$ {amount}")
        logger.info(f"Description: {description}")
        logger.info(f"Bot Token Recebido: {bot_token}")
        logger.info(f"Bots Ativos: {list(active_bots.keys())}")
        
        # CRÍTICO: Garantir que bot_token seja capturado
        if bot_token is None:
            logger.warning("⚠️ Bot token não foi passado! Tentando recuperar de active_bots")
            if active_bots:
                bot_token = list(active_bots.keys())[0]
                logger.info(f"✅ Bot token recuperado: {bot_token}")
            else:
                logger.error("❌ Nenhum bot ativo disponível!")
                await query.message.reply_text("❌ Erro interno. Tente novamente.")
                return
        
        # Validar se o bot_token existe em BOT_LINKS
        if bot_token not in BOT_LINKS:
            logger.warning(f"⚠️ Bot token {bot_token} não tem link específico - usando padrão")
        else:
            logger.info(f"✅ Link específico encontrado: {BOT_LINKS[bot_token]}")
        
        # Dados do cliente
        customer_data = {
            "name": query.from_user.first_name or f"Cliente {user_id}",
            "email": f"cliente{user_id}@example.com",
            "document": "12345678900"
        }
        
        # USAR APENAS SYNCPAY - PUSHYNPAY DESABILITADO PERMANENTEMENTE
        logger.info("🔒 Usando APENAS SyncPay Original - PushynPay DESABILITADO")
        
        try:
            payment_data = await create_pix_payment_syncpay_original(user_id, amount, description, customer_data)
            if payment_data and payment_data.get('pix_code'):
                gateway_used = "syncpay_original"
                logger.info("✅ SyncPay Original funcionou")
            else:
                raise Exception("SyncPay retornou sem código PIX")
        except Exception as e:
            logger.error(f"❌ SyncPay Original falhou: {e}")
            payment_data = None
        
        # Se ambos falharam, usar fallback manual
        if not payment_data:
            logger.error("Ambos os gateways falharam, usando PIX manual")
            await create_fallback_payment(query, amount, description, user_id)
            return
        
        # Sucesso! Processar pagamento
        pix_code = payment_data.get('qr_code') or payment_data.get('pix_code')
        
        if not pix_code:
            logger.error(f"Código PIX não encontrado")
            await query.message.reply_text("❌ Erro ao gerar código PIX. Tente novamente.")
            return
        
        # CRÍTICO: Usar identifier retornado pela API SyncPay (ou gerar fallback)
        identifier = payment_data.get('identifier')
        
        if not identifier:
            # Se SyncPay não retornou identifier, usar o ID retornado ou gerar um
            identifier = payment_data.get('id') or str(uuid.uuid4())
            logger.warning(f"⚠️ SyncPay não retornou identifier, usando fallback: {identifier}")
        else:
            logger.info(f"✅ Identifier SyncPay: {identifier}")
        
        # Criar objeto de pagamento com bot_token
        payment_info = {
            'payment_id': identifier,  # Usar identifier da SyncPay
            'amount': amount,
            'plan': description,
            'gateway': gateway_used,
            'gateway_payment_id': identifier,  # CRÍTICO para webhook mapear
            'pix_code': pix_code,
            'status': 'pending',
            'created_at': datetime.now().isoformat(),
            'user_name': query.from_user.first_name or 'Usuário',
            'user_username': query.from_user.username or '',
            'bot_token': bot_token  # CRÍTICO: Armazenar bot_token
        }
        
        # Armazenar localmente
        pending_payments[user_id] = payment_info
        
        # Armazenar no sistema compartilhado
        try:
            from shared_data import add_pending_payment
            add_pending_payment(user_id, payment_info)
        except ImportError:
            logger.warning("Função add_pending_payment não disponível no shared_data")
        
        logger.info("=" * 60)
        logger.info("✅ PAGAMENTO CRIADO COM SUCESSO")
        logger.info(f"Identifier: {identifier}")
        logger.info(f"Bot Token Armazenado: {payment_info['bot_token']}")
        logger.info(f"Dados Completos: {payment_info}")
        logger.info("=" * 60)
        
        # Marcar usuário como comprador
        update_user_session(user_id, purchased=True)
        
        # Mensagem do PIX com bloco de código HTML
        pix_message = f"""💠 Pague via Pix Copia e Cola:

<pre>{pix_code}</pre>

👆 Toque no código acima para copiá-lo facilmente

‼️ Após o pagamento, clique no botão abaixo para verificar:"""
        
        # Botão para verificar pagamento
        keyboard = [
            [InlineKeyboardButton("✅ Verificar Pagamento", callback_data=f"verificar_pagamento_{user_id}")]
        ]
        reply_markup = InlineKeyboardMarkup(keyboard)
        
        # Enviar mensagem com parse_mode HTML
        await query.message.reply_text(pix_message, reply_markup=reply_markup, parse_mode='HTML')
        event_logger.info(f"PIX enviado via {gateway_used}")
        
    except Exception as e:
        logger.error(f"❌ ERRO na create_payment: {str(e)}", exc_info=True)
        try:
            await query.message.reply_text("❌ Erro ao processar pagamento. Tente novamente.")
        except:
            await query.answer("❌ Erro ao processar pagamento. Tente novamente.")

async def create_fallback_payment(query, amount, description, user_id):
    """Fallback: cria PIX manual quando SyncPay falha"""
    try:
        # Gerar PIX manual simples
        pix_code = f"00020126360014BR.GOV.BCB.PIX0114+5511999999999520400005303986540{amount:.2f}5802BR5925GRMPAY BOT TELEGRAM6009SAO PAULO62070503***6304"
        
        # Armazenar dados do pagamento (sem ID da SyncPay)
        pending_payments[user_id] = {
            'payment_id': f"manual_{user_id}_{int(time.time())}",
            'amount': amount,
            'plan': description,
            'manual': True
        }
        
        pix_message = f"""💠 PIX MANUAL - {description}

💰 Valor: R$ {amount:.2f}

📱 Para pagar:
1. Abra seu app de banco
2. Escaneie o QR Code ou copie o código PIX
3. Confirme o pagamento
4. Clique em "Verificar Pagamento"

‼️ Após o pagamento, clique no botão abaixo:"""
        
        keyboard = [
            [InlineKeyboardButton("✅ Verificar Pagamento", callback_data=f"verificar_pagamento_{user_id}")]
        ]
        reply_markup = InlineKeyboardMarkup(keyboard)
        
        # Enviar nova mensagem em vez de editar
        await query.message.reply_text(pix_message, reply_markup=reply_markup, parse_mode='HTML')
        event_logger.info(f"PIX manual criado")
        
    except Exception as e:
        logger.error(f"Erro no fallback: {e}")
        try:
            await query.message.reply_text("❌ Sistema temporariamente indisponível. Tente novamente em alguns minutos.")
        except:
            await query.answer("❌ Sistema temporariamente indisponível. Tente novamente em alguns minutos.")

async def check_payment_status(query, user_id):
    """Verifica status do pagamento e envia link específico"""
    try:
        # Verificar rate limiting para evitar cliques muito rápidos
        current_time = time.time()
        if user_id in payment_check_cooldown:
            time_since_last_check = current_time - payment_check_cooldown[user_id]
            if time_since_last_check < PAYMENT_CHECK_COOLDOWN:
                remaining_time = PAYMENT_CHECK_COOLDOWN - time_since_last_check
                await query.answer(f"⏳ Aguarde {remaining_time:.0f}s para verificar novamente")
                return
        
        # Registrar timestamp da verificação
        payment_check_cooldown[user_id] = current_time
        
        logger.info("=" * 60)
        logger.info("🔍 INICIANDO VERIFICAÇÃO DE PAGAMENTO")
        logger.info(f"User ID: {user_id}")
        
        # Recuperar informações do pagamento
        payment_info = pending_payments.get(user_id)
        
        if not payment_info:
            logger.warning(f"⚠️ Nenhum pagamento pendente para user {user_id}")
            # Tentar recuperar do sistema compartilhado
            try:
                from shared_data import get_pending_payments
                all_payments = get_pending_payments()
                payment_info = all_payments.get(str(user_id))
            except ImportError:
                logger.warning("Função get_pending_payments não disponível no shared_data")
                payment_info = None
            
        if not payment_info:
            logger.error(f"❌ Pagamento não encontrado em nenhum local!")
            await query.edit_message_text("❌ Nenhum pagamento pendente encontrado.")
            return
        
        logger.info(f"📦 Payment Info Recuperado: {payment_info}")
        
        # Extrair bot_token
        bot_token = payment_info.get('bot_token')
        logger.info(f"🤖 Bot Token: {bot_token}")
        
        if not bot_token:
            logger.error("❌ Bot token não encontrado no payment_info!")
            logger.error(f"Chaves disponíveis: {list(payment_info.keys())}")
            # Tentar recuperar de active_bots como fallback
            if active_bots:
                bot_token = list(active_bots.keys())[0]
                logger.warning(f"⚠️ Usando fallback bot_token: {bot_token}")
        
        payment_id = payment_info['payment_id']
        gateway = payment_info.get('gateway', 'pushynpay')
        
        # Se é pagamento manual, simular verificação
        if payment_info.get('manual'):
            await query.edit_message_text(f"""⏳ PAGAMENTO MANUAL

💰 Valor: R$ {payment_info['amount']:.2f}
📋 Plano: {payment_info['plan']}

🔄 Para pagamentos manuais, entre em contato com @seu_usuario após o pagamento para liberação imediata.

📱 Ou aguarde até 24h para liberação automática.""")
            return
        
        # Verificar status baseado no gateway usado
        status = None
        
        if gateway == 'pushynpay':
            # Verificar via PushynPay com múltiplas tentativas
            max_attempts = 3
            for attempt in range(max_attempts):
                status = await check_pushynpay_payment_status(payment_id)
                if status is not None:
                    break
                if attempt < max_attempts - 1:
                    logger.info(f"Tentativa {attempt + 1} de verificação PushynPay falhou, tentando novamente...")
                    await asyncio.sleep(2)  # Aguardar 2 segundos entre tentativas
        elif gateway == 'syncpay_original':
            # Verificar via SyncPay Original
            syncpay = SyncPayIntegration()
            status = syncpay.check_payment_status(payment_id)
        else:
            logger.error(f"Gateway desconhecido para verificação: {gateway}")
            status = None
        
        logger.info(f"📊 Status Retornado: {status}")
        
        # Se pagamento confirmado
        if status == 'paid':
            logger.info("=" * 60)
            logger.info("💰 PAGAMENTO CONFIRMADO!")
            logger.info(f"User ID: {user_id}")
            logger.info(f"Bot Token: {bot_token}")
            logger.info("=" * 60)
            
            # Exibir mensagem de confirmação
            await query.edit_message_text(f"""🎉 PAGAMENTO CONFIRMADO!

✅ {payment_info['plan']}
💰 Valor: R$ {payment_info['amount']:.2f}

🎁 Seu acesso será liberado em até 5 minutos!
📱 Entre em contato com @seu_usuario para receber os links dos grupos.

Obrigado pela compra! 🚀""")
            
            # Enviar link de acesso específico
            link_sent = await send_access_link(user_id, bot_token)
            
            if link_sent:
                logger.info("✅ Link de acesso enviado com sucesso!")
            else:
                logger.error("❌ Falha ao enviar link de acesso!")
            
            # ENVIAR NOTIFICAÇÃO DE VENDA PARA O ADMIN
            try:
                # Obter informações do usuário
                user_info = {
                    'user_id': user_id,
                    'first_name': query.from_user.first_name or 'N/A',
                    'last_name': query.from_user.last_name or '',
                    'username': query.from_user.username or 'N/A',
                    'document': '***.***.***-**'  # CPF mascarado por privacidade
                }
                
                # Obter informações do bot atual
                bot_info = {}
                if bot_token in active_bots:
                    try:
                        bot = active_bots[bot_token]['bot']
                        bot_me = await bot.get_me()
                        bot_info = {
                            'username': bot_me.username,
                            'id': bot_me.id,
                            'first_name': bot_me.first_name
                        }
                    except Exception as e:
                        logger.warning(f"Erro ao obter info do bot: {e}")
                        bot_info = {
                            'username': 'bot_desconhecido',
                            'id': 'N/A',
                            'first_name': 'Bot'
                        }
                
                # Enviar notificação para o admin
                await send_sale_notification_to_admin(payment_info, user_info, bot_info)
                
            except Exception as e:
                logger.error(f"❌ Erro ao enviar notificação de venda: {e}")
            
            # Limpar pagamento pendente
            if user_id in pending_payments:
                del pending_payments[user_id]
            try:
                from shared_data import remove_pending_payment, update_stats
                remove_pending_payment(user_id)
                update_stats('confirmed_payments')
            except ImportError:
                logger.warning("Funções do shared_data não disponíveis")
            
            # Adicionar evento de pagamento confirmado
            add_event('PAYMENT_CONFIRMED', f'Pagamento confirmado: R$ {payment_info["amount"]:.2f} - {payment_info["plan"]}', user_id)
            
        elif status == 'pending':
            # Pagamento pendente - permitir verificação novamente
            keyboard = [
                [InlineKeyboardButton("🔄 Verificar Novamente", callback_data=f"verificar_pagamento_{user_id}")]
            ]
            reply_markup = InlineKeyboardMarkup(keyboard)
            
            pending_message = f"""⏳ PAGAMENTO AINDA NÃO CONFIRMADO

🔄 Aguarde alguns minutos e clique em "Verificar Novamente"

💡 O PIX pode levar até 5 minutos para ser processado
⏰ Você pode verificar quantas vezes quiser até ser autorizado

💰 Valor: R$ {payment_info['amount']:.2f}
📋 Plano: {payment_info['plan']}"""
            
            try:
                await query.edit_message_text(pending_message, reply_markup=reply_markup)
            except Exception as edit_error:
                if "Message is not modified" in str(edit_error):
                    logger.info("Mensagem já está atualizada, ignorando erro de modificação")
                    await query.answer("⏳ Pagamento ainda pendente...")
                else:
                    logger.error(f"Erro ao editar mensagem: {edit_error}")
                    await query.answer("❌ Erro ao atualizar mensagem")
            
        else:
            # Pagamento não encontrado ou erro - permitir nova verificação
            keyboard = [
                [InlineKeyboardButton("🔄 Verificar Novamente", callback_data=f"verificar_pagamento_{user_id}")],
                [InlineKeyboardButton("📞 Contatar Suporte", callback_data=f"contatar_suporte_{user_id}")]
            ]
            reply_markup = InlineKeyboardMarkup(keyboard)
            
            not_found_message = f"""❌ PAGAMENTO NÃO IDENTIFICADO

🔄 Clique em "Verificar Novamente" para tentar mais uma vez

💡 Possíveis motivos:
• PIX ainda está sendo processado
• Aguarde alguns minutos após o pagamento
• Verifique se copiou o código PIX corretamente

📞 Se o problema persistir, clique em "Contatar Suporte"

💰 Valor: R$ {payment_info['amount']:.2f}
📋 Plano: {payment_info['plan']}"""
            
            try:
                await query.edit_message_text(not_found_message, reply_markup=reply_markup)
            except Exception as edit_error:
                if "Message is not modified" in str(edit_error):
                    logger.info("Mensagem já está atualizada, ignorando erro de modificação")
                    await query.answer("❌ Pagamento não identificado...")
                else:
                    logger.error(f"Erro ao editar mensagem: {edit_error}")
                    await query.answer("❌ Erro ao atualizar mensagem")
            
    except Exception as e:
        logger.error(f"❌ ERRO em check_payment_status: {str(e)}", exc_info=True)
        
        # Em caso de erro, também permitir nova verificação
        keyboard = [
            [InlineKeyboardButton("🔄 Verificar Novamente", callback_data=f"verificar_pagamento_{user_id}")]
        ]
        reply_markup = InlineKeyboardMarkup(keyboard)
        
        # Tentar obter payment_info para mostrar valores
        payment_info = pending_payments.get(user_id, {})
        
        error_message = f"""❌ ERRO AO VERIFICAR PAGAMENTO

🔄 Clique em "Verificar Novamente" para tentar mais uma vez

💡 Possíveis motivos:
• Problema temporário de conexão
• Aguarde alguns minutos e tente novamente
• Se persistir, entre em contato com @seu_usuario

💰 Valor: R$ {payment_info.get('amount', 0):.2f}
📋 Plano: {payment_info.get('plan', 'N/A')}"""
        
        try:
            await query.edit_message_text(error_message, reply_markup=reply_markup)
        except Exception as edit_error:
            if "Message is not modified" in str(edit_error):
                logger.info("Mensagem já está atualizada, ignorando erro de modificação")
                await query.answer("❌ Erro ao verificar pagamento...")
            else:
                logger.error(f"Erro ao editar mensagem de erro: {edit_error}")
                await query.answer("❌ Erro ao atualizar mensagem")

async def send_support_message(query, user_id):
    """Envia mensagem de suporte para problemas de pagamento"""
    try:
        # Obter informações do pagamento pendente
        payment_info = pending_payments.get(user_id, {})
        
        support_message = f"""📞 SUPORTE TÉCNICO

Olá! Identificamos um problema com a verificação do seu pagamento.

🔍 **INFORMAÇÕES DO PAGAMENTO:**
• ID: {payment_info.get('payment_id', 'N/A')}
• Valor: R$ {payment_info.get('amount', 0):.2f}
• Plano: {payment_info.get('plan', 'N/A')}
• Gateway: {payment_info.get('gateway', 'N/A')}

📱 **PRÓXIMOS PASSOS:**
1. Envie o comprovante de pagamento para @seu_usuario
2. Aguarde até 24h para liberação automática
3. Se urgente, entre em contato diretamente

⚠️ **IMPORTANTE:** Mantenha o comprovante do PIX para comprovação.

Obrigado pela paciência! 🙏"""

        await query.edit_message_text(support_message)
        
        # Log do evento de suporte
        event_logger.info(f"Usuário {user_id} solicitou suporte para pagamento {payment_info.get('payment_id')}")
        add_event('INFO', f'Suporte solicitado por usuário {user_id} para pagamento {payment_info.get("payment_id")}', user_id)
        
    except Exception as e:
        logger.error(f"Erro ao enviar mensagem de suporte: {e}")
        await query.edit_message_text("❌ Erro ao processar solicitação de suporte. Tente novamente.")

async def send_access_link(user_id, bot_token=None):
    """Envia link de acesso específico do bot"""
    try:
        logger.info("=" * 60)
        logger.info("🔗 INICIANDO ENVIO DE LINK DE ACESSO")
        logger.info(f"User ID: {user_id}")
        logger.info(f"Bot Token Recebido: {bot_token}")
        
        # Validar bot_token
        if not bot_token:
            logger.error("❌ Bot token não fornecido!")
            if active_bots:
                bot_token = list(active_bots.keys())[0]
                logger.warning(f"⚠️ Usando fallback: {bot_token}")
            else:
                logger.error("❌ Nenhum bot disponível!")
                return False
        
        # Buscar link específico do bot
        specific_link = BOT_LINKS.get(bot_token)
        
        if specific_link:
            logger.info(f"✅ Link específico encontrado: {specific_link}")
            access_link = specific_link
        else:
            logger.warning(f"⚠️ Bot {bot_token} sem link específico")
            logger.warning(f"Bots disponíveis: {list(BOT_LINKS.keys())}")
            access_link = "https://oacessoliberado.shop/vip2"  # Link padrão
            logger.info(f"📌 Usando link padrão: {access_link}")
        
        # Preparar mensagem
        message = (
            "✅ *PAGAMENTO CONFIRMADO!*\n\n"
            "🎉 Seu acesso foi liberado com sucesso!\n\n"
            f"🔗 *Link de Acesso:*\n{access_link}\n\n"
            "⚡ Acesse agora mesmo e aproveite!\n\n"
            "❓ Dúvidas? Entre em contato com o suporte."
        )
        
        # Tentar enviar por todos os bots ativos
        message_sent = False
        
        # Tentar primeiro com o bot específico
        if bot_token in active_bots:
            try:
                bot = active_bots[bot_token]['bot']
                await bot.send_message(
                    chat_id=user_id,
                    text=message,
                    parse_mode='Markdown'
                )
                message_sent = True
                logger.info(f"✅ Mensagem enviada pelo bot específico: {bot_token}")
            except Exception as e:
                logger.error(f"❌ Erro ao enviar pelo bot específico: {str(e)}")
        
        # Se não conseguiu, tentar com qualquer bot ativo
        if not message_sent:
            for token, bot_info in active_bots.items():
                try:
                    bot = bot_info['bot']
                    await bot.send_message(
                        chat_id=user_id,
                        text=message,
                        parse_mode='Markdown'
                    )
                    message_sent = True
                    logger.info(f"✅ Mensagem enviada pelo bot fallback: {token}")
                    break
                except Exception as e:
                    logger.error(f"❌ Erro ao enviar pelo bot {token}: {str(e)}")
                    continue
        
        if message_sent:
            logger.info("=" * 60)
            logger.info("✅ LINK DE ACESSO ENVIADO COM SUCESSO")
            logger.info(f"User ID: {user_id}")
            logger.info(f"Bot Token: {bot_token}")
            logger.info(f"Link Enviado: {access_link}")
            logger.info("=" * 60)
            return True
        else:
            logger.error("❌ FALHA TOTAL - Nenhum bot conseguiu enviar a mensagem")
            return False
        
    except Exception as e:
        logger.error(f"❌ ERRO CRÍTICO em send_access_link: {str(e)}", exc_info=True)
        return False

def debug_payment_state(user_id):
    """Função helper para debug do estado do pagamento"""
    logger.info("=" * 60)
    logger.info("🔍 DEBUG - ESTADO DO PAGAMENTO")
    logger.info(f"User ID: {user_id}")
    logger.info(f"Em pending_payments: {user_id in pending_payments}")
    if user_id in pending_payments:
        logger.info(f"Dados: {pending_payments[user_id]}")
    logger.info(f"Bots ativos: {list(active_bots.keys())}")
    logger.info(f"Links configurados: {list(BOT_LINKS.keys())}")
    logger.info("=" * 60)

async def send_sale_notification_to_admin(payment_info, user_info, bot_info):
    """Envia notificação detalhada de venda para o administrador - VERSÃO PRODUÇÃO COM DADOS REAIS"""
    try:
        logger.info("=" * 60)
        logger.info("📢 INICIANDO ENVIO DE NOTIFICAÇÃO DE VENDA")
        logger.info(f"SALE_NOTIFICATIONS_ENABLED: {SALE_NOTIFICATIONS_ENABLED}")
        logger.info(f"ADMIN_NOTIFICATION_CHAT_ID: {ADMIN_NOTIFICATION_CHAT_ID}")
        logger.info(f"Active bots: {len(active_bots)}")
        logger.info(f"Payment Info: {payment_info}")
        logger.info("=" * 60)
        
        # Validação robusta dos dados obrigatórios
        if not payment_info or 'amount' not in payment_info or 'plan' not in payment_info:
            logger.error("❌ Dados de pagamento inválidos ou incompletos")
            return
            
        if not user_info or 'user_id' not in user_info:
            logger.error("❌ Dados do usuário inválidos ou incompletos")
            return
            
        if not bot_info:
            logger.error("❌ Dados do bot inválidos ou incompletos")
            return
        
        if not SALE_NOTIFICATIONS_ENABLED:
            logger.warning("⚠️ Notificações de vendas estão DESATIVADAS!")
            return
        
        # Obter informações REAIS do bot
        bot_username = bot_info.get('username', 'bot_desconhecido')
        bot_id = bot_info.get('id', 'N/A')
        
        # Calcular tempo de conversão REAL (baseado na criação do pagamento)
        conversion_time = "0d 0h 0m 0s"  # Padrão
        if 'created_at' in payment_info:
            try:
                created_time = datetime.fromisoformat(payment_info['created_at'].replace('Z', '+00:00'))
                current_time = datetime.now()
                time_diff = current_time - created_time
                
                days = time_diff.days
                hours, remainder = divmod(time_diff.seconds, 3600)
                minutes, seconds = divmod(remainder, 60)
                
                conversion_time = f"{days}d {hours}h {minutes}m {seconds}s"
            except Exception as e:
                logger.warning(f"Erro ao calcular tempo de conversão: {e}")
                conversion_time = "0d 0h 2m 15s"  # Fallback
        
        # Calcular valor líquido REAL (assumindo taxa de 6% como nas imagens)
        gross_amount = payment_info['amount']
        net_amount = gross_amount * 0.94  # 6% de taxa
        
        # Gerar IDs únicos REAIS para a transação
        internal_transaction_id = payment_info['payment_id'][:8]  # Primeiros 8 caracteres do ID real
        gateway_transaction_id = payment_info.get('gateway_payment_id', payment_info.get('payment_id', str(uuid.uuid4())))
        
        # Determinar método de pagamento e plataforma REAIS
        payment_method = "pix"  # Sempre PIX no sistema atual
        payment_platform = payment_info.get('gateway', 'pushynpay')
        
        # Determinar categoria e plano REAIS
        plan_name = payment_info['plan']
        if 'VITALÍCIO' in plan_name.upper():
            category = "Plano Normal"
            duration = "Vitalício"
        elif 'MENSAL' in plan_name.upper():
            category = "Plano Normal"
            duration = "1 Mês"
        else:
            category = "Plano Normal"
            duration = "1 Mês"  # Padrão
        
        # Obter informações REAIS do usuário com sanitização
        user_id = user_info['user_id']
        username = user_info.get('username', 'N/A')
        first_name = user_info.get('first_name', 'N/A')
        last_name = user_info.get('last_name', '')
        document = user_info.get('document', '***.***.***-**')
        
        # Sanitizar dados para evitar problemas de parsing
        username = username.replace('@', '') if username != 'N/A' else 'N/A'
        first_name = first_name.replace('*', '').replace('_', ' ').strip() if first_name != 'N/A' else 'N/A'
        last_name = last_name.replace('*', '').replace('_', ' ').strip()
        
        # Criar mensagem de notificação com dados REAIS e sanitizados
        notification_message = f"""🎉 Pagamento Aprovado!

🤖 Bot: @{bot_username}
⚙️ ID Bot: {bot_id}

👤 ID Cliente: {user_id}
🔗 Username: @{username}
👤 Nome de Perfil: {first_name}
👤 Nome Completo: {first_name} {last_name}
📄 CPF/CNPJ: {document}

🌍 Idioma: pt-br
⭐ Telegram Premium: Não
📦 Categoria: {category}
🎁 Plano: {plan_name}
📅 Duração: {duration}

💰 Valor: R${gross_amount:.2f}
💰 Valor Líquido: R${net_amount:.2f}

⏱️ Tempo Conversão: {conversion_time}
🔑 ID Transação Interna: {internal_transaction_id}
🏷️ ID Transação Gateway: {gateway_transaction_id}
💱 Tipo Moeda: BRL
💳 Método Pagamento: {payment_method}
🏢 Plataforma Pagamento: {payment_platform}"""
        
        logger.info("📝 Mensagem de notificação criada com dados REAIS")
        logger.info(f"Tamanho da mensagem: {len(notification_message)} caracteres")
        
        # Tentar enviar notificação por todos os bots ativos
        notification_sent = False
        attempts = 0
        
        for token, bot_data in active_bots.items():
            if bot_data['status'] == 'active':
                attempts += 1
                logger.info(f"🔄 Tentativa {attempts}: Enviando via bot {token[:20]}...")
                
                try:
                    bot = bot_data['bot']
                    logger.info(f"📤 Enviando para chat_id: {ADMIN_NOTIFICATION_CHAT_ID}")
                    
                    # Tentar enviar com timeout para evitar travamentos
                    try:
                        await asyncio.wait_for(
                            bot.send_message(
                                chat_id=ADMIN_NOTIFICATION_CHAT_ID,
                                text=notification_message,
                                parse_mode=None
                            ),
                            timeout=10.0
                        )
                        
                        notification_sent = True
                        logger.info(f"✅ NOTIFICAÇÃO ENVIADA COM SUCESSO pelo bot {token[:20]}...")
                        break
                        
                    except Exception as send_error:
                        logger.error(f"❌ Erro específico ao enviar mensagem: {send_error}")
                        logger.error(f"Tipo do erro: {type(send_error).__name__}")
                        continue
                    
                except asyncio.TimeoutError:
                    logger.error(f"⏰ Timeout ao enviar notificação pelo bot {token[:20]}...")
                    continue
                except Exception as e:
                    logger.error(f"❌ Erro ao enviar notificação pelo bot {token[:20]}...: {e}")
                    logger.error(f"Tipo do erro: {type(e).__name__}")
                    continue
        
        if notification_sent:
            logger.info("=" * 60)
            logger.info("✅ NOTIFICAÇÃO DE VENDA ENVIADA COM SUCESSO!")
            logger.info(f"Valor: R$ {gross_amount:.2f}")
            logger.info(f"Plano: {plan_name}")
            logger.info(f"Cliente: {first_name} (@{username})")
            logger.info(f"Bot: @{bot_username}")
            logger.info("=" * 60)
            event_logger.info(f"Notificação de venda enviada: R$ {gross_amount:.2f} - {plan_name} - {first_name}")
        else:
            logger.error("=" * 60)
            logger.error("❌ FALHA TOTAL AO ENVIAR NOTIFICAÇÃO DE VENDA!")
            logger.error(f"Tentativas realizadas: {attempts}")
            logger.error(f"Bots ativos: {len(active_bots)}")
            logger.error("=" * 60)
            
    except Exception as e:
        logger.error("=" * 60)
        logger.error(f"❌ ERRO CRÍTICO ao enviar notificação de venda: {e}")
        logger.error(f"Tipo do erro: {type(e).__name__}")
        logger.error("=" * 60, exc_info=True)

def start_downsell_timers(user_id):
    """Inicia timers de downsell para um usuário"""
    downsell_config = get_downsell_config()
    
    if not downsell_config.get('enabled', False):
        return
    
    downsells = downsell_config.get('downsells', [])
    if not downsells:
        return
    
    event_logger.info(f"Iniciando {len(downsells)} timers de downsell")
    
    for i, downsell in enumerate(downsells):
        delay_minutes = downsell.get('sendTime', 5)  # Usar 'sendTime' em vez de 'delay_minutes'
        delay_seconds = delay_minutes * 60
        
        add_timer(user_id, i, delay_seconds)
        # Timer programado

async def start_downsell_scheduler():
    """Scheduler contínuo para gerenciar downsells"""
    event_logger.info("Scheduler de downsells iniciado")
    
    while True:
        try:
            # Obter todos os downsells agendados
            scheduled_downsells = get_all_scheduled_downsells()
            
            if scheduled_downsells:
                # Verificando downsells agendados
                current_time = datetime.now().timestamp()
            
            for ds in scheduled_downsells:
                # Verificar se é hora de enviar
                if ds["next_run"] <= current_time:
                    # Enviando downsell
                    
                    try:
                        # Enviar downsell
                        await send_downsell_to_user(ds["user_id"], ds["downsell"], ds["downsell_index"])
                        
                        # Marcar como enviado na sessão do usuário
                        user_session = get_user_session(ds["user_id"])
                        if user_session:
                            downsells_sent = user_session.get('downsell_sent', [])
                            downsells_sent.append(ds["downsell_index"])
                            update_user_session(ds["user_id"], downsell_sent=downsells_sent)
                        
                        # Remover timer (downsell enviado)
                        update_downsell_schedule(ds["id"])
                        
                        # Incrementar estatísticas
                        increment_downsell_stats('total_downsells_sent')
                        
                        event_logger.info(f"Downsell {ds['downsell_index']} enviado")
                        
                    except Exception as e:
                        logger.error(f"Erro ao enviar downsell {ds['downsell_index']}: {e}")
            
            # Aguardar 60 segundos antes da próxima verificação
            await asyncio.sleep(60)
            
        except Exception as e:
            logger.error(f"Erro no scheduler de downsells: {e}")
            await asyncio.sleep(60)  # Aguardar antes de tentar novamente

async def send_downsell_to_user(user_id, downsell, downsell_index):
    """Envia um downsell específico para um usuário"""
    try:
        # Obter bot disponível
        bot_info = get_next_bot()
        if not bot_info:
            logger.error("Nenhum bot disponível para enviar downsell")
            return
        
        bot = bot_info['bot']  # Obter o objeto Bot real
        
        # Texto do downsell
        downsell_text = downsell.get('text', '')
        
        # Criar botões de pagamento
        keyboard = []
        payment_buttons = downsell.get('paymentButtons', [])
        
        for button in payment_buttons:
            button_text = button.get('text', '')
            price = button.get('price', 0)
            description = button.get('description', '')
            
            # Criar callback_data para mostrar order bump primeiro
            if 'vitalício' in button_text.lower() or 'vitalicio' in button_text.lower():
                callback_data = "vitalicio"  # Vai mostrar order bump primeiro
            else:  # Mensal
                callback_data = "mensal"  # Vai mostrar order bump primeiro
            
            keyboard.append([InlineKeyboardButton(button_text, callback_data=callback_data)])
        
        reply_markup = InlineKeyboardMarkup(keyboard) if keyboard else None
        
        # Se tem mídia, enviar vídeo com caption
        media_file = downsell.get('mediaFile', '')
        if media_file:
            try:
                if media_file.startswith('https://t.me/'):
                    # É um link do Telegram - enviar como vídeo com caption
                    await bot.send_video(
                        chat_id=user_id,
                        video=media_file,
                        caption=downsell_text,
                        reply_markup=reply_markup,
                        parse_mode='HTML'
                    )
                else:
                    # É um arquivo local - enviar como vídeo
                    with open(media_file, 'rb') as f:
                        await bot.send_video(
                            chat_id=user_id,
                            video=f,
                            caption=downsell_text,
                            reply_markup=reply_markup,
                            parse_mode='HTML'
                        )
            except Exception as media_error:
                logger.warning(f"Erro ao enviar mídia do downsell: {media_error}")
                # Fallback: enviar apenas texto com botões
                await bot.send_message(
                    chat_id=user_id,
                    text=downsell_text,
                    reply_markup=reply_markup,
                    parse_mode='HTML'
                )
        else:
            # Sem mídia - enviar apenas texto com botões
            await bot.send_message(
                chat_id=user_id,
                text=downsell_text,
                reply_markup=reply_markup,
                parse_mode='HTML'
            )
        
        # Downsell enviado
        
    except Exception as e:
        logger.error(f"Erro ao enviar downsell para usuário {user_id}: {e}")

async def monitor_bots():
    """Monitora status dos bots"""
    while True:
        try:
            await asyncio.sleep(30)  # Verificar a cada 30 segundos
            
            # Verificar bots ativos
            for token, bot_info in list(active_bots.items()):
                try:
                    # Testar conexão com timeout
                    await asyncio.wait_for(
                        bot_info['bot'].get_me(),
                        timeout=10.0
                    )
                    bot_info['last_heartbeat'] = datetime.now()
                    
                except asyncio.TimeoutError:
                    logger.warning(f"Bot {token[:20]}... timeout na conexão")
                    bot_info['status'] = 'failed'
                except Exception as e:
                    logger.warning(f"Bot {token[:20]}... perdeu conexão")
                    bot_info['status'] = 'failed'
                    logger.error(f"Bot {token[:20]}... marcado como falhado")
            
            # Tentar reconectar bots falhados
            await retry_failed_bots()
            
            # Log de status
            active_count = sum(1 for info in active_bots.values() if info['status'] == 'active')
            failed_count = sum(1 for info in active_bots.values() if info['status'] == 'failed')
            # Status dos bots
            
        except Exception as e:
            logger.error(f"Erro no monitoramento: {e}")
            # Se houver erro crítico no monitoramento, aguardar antes de continuar
            await asyncio.sleep(60)

async def retry_failed_bots():
    """Tenta reconectar bots que falharam"""
    for token, bot_info in list(active_bots.items()):
        if bot_info['status'] == 'failed' and bot_info['retry_count'] < 3:
            # Tentando reconectar bot
            
            try:
                # Tentar inicializar novamente
                new_bot_info = await initialize_bot(token)
                
                if new_bot_info:
                    active_bots[token] = new_bot_info
                    event_logger.info(f"Bot reconectado: {token[:20]}...")
                    
                    # Registrar evento
                    add_event('INFO', f'Bot {token[:20]}... reconectado automaticamente', 'system')
                else:
                    bot_info['retry_count'] += 1
                    logger.error(f"Falha ao reconectar bot (tentativa {bot_info['retry_count']})")
                    
            except Exception as e:
                bot_info['retry_count'] += 1
                logger.error(f"Falha ao reconectar bot: {e}")

async def shutdown_all_bots():
    """Shutdown graceful de todos os bots"""
    event_logger.info("Iniciando shutdown graceful")
    
    try:
        # Cancelar todas as tasks ativas primeiro
        tasks = [task for task in asyncio.all_tasks() if not task.done()]
        if tasks:
            # Cancelando tasks ativas
            for task in tasks:
                task.cancel()
        
        # Shutdown das aplicações
        for token, bot_info in active_bots.items():
            if bot_info['status'] == 'active':
                try:
                    app = bot_info['application']
                    if hasattr(app, 'updater') and app.updater.running:
                        await app.updater.stop()
                    if hasattr(app, 'stop'):
                        await app.stop()
                    if hasattr(app, 'shutdown'):
                        await app.shutdown()
                except Exception as e:
                    logger.warning(f"Erro no shutdown do bot: {e}")
        
        event_logger.info("Shutdown graceful concluído")
        
    except Exception as e:
        logger.error(f"Erro durante shutdown: {e}")
    finally:
        active_bots.clear()
        # Lista de bots ativos limpa

async def shutdown_single_bot(bot_info):
    """Shutdown de um único bot"""
    try:
        token = bot_info['token']
        # Shutdown bot
        
        # Shutdown da aplicação
        await bot_info['application'].shutdown()
        
        # Bot shutdown concluído
        
    except Exception as e:
        logger.error(f"Erro no shutdown do bot: {e}")

async def start_all_bots():
    """Inicia todos os bots configurados"""
    event_logger.info("Iniciando sistema de múltiplos bots")
    
    # Filtrar apenas tokens válidos
    valid_tokens = [token for token in BOT_TOKENS if token and not token.startswith('SEU_TOKEN')]
    
    if not valid_tokens:
        logger.error("Nenhum token válido encontrado")
        return False
    
    # Inicializar bots em paralelo
    tasks = []
    for token in valid_tokens:
        task = initialize_bot(token)
        tasks.append(task)
    
    results = await asyncio.gather(*tasks, return_exceptions=True)
    
    # Processar resultados
    for i, result in enumerate(results):
        if isinstance(result, dict) and result:
            token = valid_tokens[i]
            active_bots[token] = result
            # Bot adicionado à lista ativa
        else:
            token = valid_tokens[i]
            logger.error(f"Bot falhou na inicialização: {result}")
    
    event_logger.info(f"Sistema iniciado: {len(active_bots)} bots ativos")
    return len(active_bots) > 0


async def run_single_bot(token: str, bot_info: Dict) -> None:
    """Executa um único bot de forma assíncrona"""
    try:
        logger.info(f"🤖 Executando bot {token[:20]}...")
        
        app = bot_info['application']
        
        # Inicializar o bot
        await app.initialize()
        await app.start()
        await app.updater.start_polling(drop_pending_updates=True)
        
        logger.info(f"✅ Bot {token[:20]}... iniciado com sucesso")
        
        # Manter o bot rodando até shutdown ser solicitado
        while not shutdown_requested:
            await asyncio.sleep(1)
        
    except Exception as e:
        logger.error(f"❌ Erro no bot {token[:20]}...: {e}")
        bot_info['status'] = 'failed'
        raise e
    finally:
        # Shutdown limpo
        try:
            await app.updater.stop()
            await app.stop()
            await app.shutdown()
            logger.info(f"🔄 Bot {token[:20]}... finalizado")
        except Exception as shutdown_error:
            logger.warning(f"⚠️ Erro no shutdown do bot {token[:20]}...: {shutdown_error}")

async def run_all_bots():
    """Executa todos os bots em paralelo usando um único event loop"""
    if not active_bots:
        logger.error("Nenhum bot ativo para executar!")
        return False
    
    logger.info(f"Executando {len(active_bots)} bots em paralelo...")
    
    # Criar tasks para cada bot ativo
    tasks = []
    for token, bot_info in active_bots.items():
        if bot_info['status'] == 'active':
            task = asyncio.create_task(
                run_single_bot(token, bot_info),
                name=f"bot_{token[:10]}"
            )
            tasks.append(task)
            logger.info(f"✅ Task criada para bot {token[:20]}...")
    
    if not tasks:
        logger.error("Nenhuma task criada!")
        return False
    
    try:
        # Executar todos os bots em paralelo
        logger.info(f"🚀 Iniciando {len(tasks)} bots simultaneamente...")
        
        # Aguardar até que shutdown seja solicitado ou todos os bots falhem
        while not shutdown_requested and any(not task.done() for task in tasks):
            await asyncio.sleep(1)
        
        if shutdown_requested:
            logger.info("🔄 Shutdown solicitado - cancelando tasks...")
        
    except KeyboardInterrupt:
        logger.info("🔄 Interrupção pelo usuário detectada")
    except Exception as e:
        logger.error(f"❌ Erro na execução dos bots: {e}")
    finally:
        # Cancelar todas as tasks pendentes
        for task in tasks:
            if not task.done():
                task.cancel()
                logger.info(f"🔄 Task {task.get_name()} cancelada")
    
    return True

async def supervise_bots():
    """Supervisiona os bots e reinicia em caso de falha"""
    while not shutdown_requested:
        try:
            event_logger.info("Iniciando supervisão dos bots")
            await run_all_bots()
            
        except Exception as e:
            if shutdown_requested:
                event_logger.info("Shutdown solicitado - parando supervisão")
                break
            logger.error(f"Erro na supervisão: {e}")
            event_logger.info("Reiniciando bots em 5 segundos")
            await asyncio.sleep(5)
    
    event_logger.info("Supervisão finalizada")

async def main():
    """Função principal - Sistema Multi-Bot Assíncrono"""
    print("="*70)
    print("🤖 SISTEMA MULTI-BOT TELEGRAM - ALTO TRÁFEGO")
    print("="*70)
    print("✅ Múltiplos bots rodando simultaneamente")
    print("✅ Troca automática quando um bot cai")
    print("✅ Distribuição de carga entre bots")
    print("✅ Monitoramento em tempo real")
    print("="*70)
    
    # Verificar se há tokens válidos
    valid_tokens = [token for token in BOT_TOKENS if token and not token.startswith('SEU_TOKEN')]
    
    if not valid_tokens:
        logger.error("❌ Nenhum token válido encontrado!")
        logger.info("💡 Adicione tokens válidos na lista BOT_TOKENS")
        return
    
    logger.info(f"📋 {len(valid_tokens)} token(s) válido(s) encontrado(s)")
    
    # Inicializar sistema de gateways
    initialize_gateways()
    
    # Inicializar todos os bots
    success = await start_all_bots()
    
    if not success:
        logger.error("❌ Nenhum bot pôde ser inicializado!")
        return
    
    logger.info(f"🚀 Sistema iniciado com {len(active_bots)} bot(s) ativo(s)")
    
    # Exibir status dos bots
    print("\n📊 STATUS DOS BOTS:")
    print("-" * 50)
    for token, bot_info in active_bots.items():
        status = "✅ Ativo" if bot_info['status'] == 'active' else "❌ Falhado"
        print(f"{status} - {token[:20]}...")
    
    # Exibir status dos gateways
    print("\n💳 STATUS DOS GATEWAYS:")
    print("-" * 50)
    for gateway_id, status in gateway_status.items():
        gateway_name = GATEWAYS[gateway_id]['name']
        
        if status['status'] == 'active':
            status_icon = "✅ Ativo"
            status_text = "Funcionando"
        else:
            status_icon = "❌ Falhado"
            status_text = status.get('last_error', 'Erro desconhecido')
        
        success_rate = "N/A"
        if status['total_requests'] > 0:
            success_rate = f"{(status['successful_requests'] / status['total_requests'] * 100):.1f}%"
        
        print(f"{status_icon} - {gateway_name}")
        print(f"    Status: {status_text}")
        print(f"    Sucesso: {success_rate}")
        print()
    
    print("\n🔄 Sistema rodando... Pressione Ctrl+C para parar")
    
    # Executar supervisão dos bots
    try:
        # Criar tasks para execução paralela
        tasks = []
        
        # Task 1: Supervisão dos bots
        supervise_task = asyncio.create_task(supervise_bots())
        tasks.append(supervise_task)
        
        # Task 2: Scheduler de downsells
        scheduler_task = asyncio.create_task(start_downsell_scheduler())
        tasks.append(scheduler_task)
        
        logger.info("🚀 Sistema iniciado com scheduler de downsells!")
        
        # Aguardar todas as tasks
        await asyncio.gather(*tasks, return_exceptions=True)
        
    except KeyboardInterrupt:
        logger.info("🔄 Interrupção pelo usuário detectada")
    except Exception as e:
        logger.error(f"❌ Erro na execução: {e}")
    finally:
        logger.info("🔄 Iniciando shutdown...")
        await shutdown_all_bots()

def run_system():
    """Função wrapper para executar o sistema"""
    try:
        asyncio.run(main())
    except KeyboardInterrupt:
        print("\n👋 Sistema interrompido pelo usuário")
    except Exception as e:
        logger.error(f"❌ Erro crítico: {e}")
        print(f"❌ Erro crítico: {e}")

if __name__ == '__main__':
    run_system()