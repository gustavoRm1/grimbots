"""
Funções Utilitárias - Sistema de Assinaturas
Validações e utilitários para gerenciamento de assinaturas VIP
"""

import re
import requests
import logging
from typing import Optional, Tuple
from models import Bot

logger = logging.getLogger(__name__)


def extract_or_validate_chat_id(link_or_id: str, bot_token: str) -> Tuple[Optional[str], bool]:
    """
    Extrai ou valida chat_id de link ou chat_id direto
    
    Suporta:
    - Chat ID direto: -1001234567890
    - Link t.me/c/: t.me/c/1234567890
    - Username: @username
    
    Retorna: (chat_id, is_valid)
    """
    if not link_or_id or not bot_token:
        logger.error("❌ extract_or_validate_chat_id: link_or_id ou bot_token vazio")
        return None, False
    
    # ✅ CASO 1: Já é chat_id (formato: -1001234567890)
    if isinstance(link_or_id, str) and link_or_id.startswith('-'):
        chat_id = link_or_id.strip()
        # Validar via API
        if validate_chat_id_via_api(chat_id, bot_token):
            logger.info(f"✅ Chat ID direto válido: {chat_id[:20]}...")
            return chat_id, True
        logger.warning(f"⚠️ Chat ID direto inválido: {chat_id[:20]}...")
        return None, False
    
    # ✅ CASO 2: Link t.me/c/1234567890
    match = re.search(r't\.me/c/(-?\d+)', link_or_id)
    if match:
        base_id = match.group(1)
        # Converter para chat_id completo: -100 + base_id
        if not base_id.startswith('-100'):
            chat_id = f"-100{base_id}"
        else:
            chat_id = base_id
        
        if validate_chat_id_via_api(chat_id, bot_token):
            logger.info(f"✅ Chat ID extraído de link t.me válido: {chat_id[:20]}...")
            return chat_id, True
        logger.warning(f"⚠️ Chat ID extraído de link t.me inválido: {chat_id[:20]}...")
    
    # ✅ CASO 3: @username
    match = re.search(r'@(\w+)', link_or_id)
    if match:
        username = match.group(1)
        chat_id = f"@{username}"
        if validate_chat_id_via_api(chat_id, bot_token):
            logger.info(f"✅ Chat ID (username) válido: {chat_id}")
            return chat_id, True
        logger.warning(f"⚠️ Chat ID (username) inválido: {chat_id}")
    
    # ✅ CASO 4: Link joinchat (não dá para extrair facilmente)
    if 'joinchat' in link_or_id.lower():
        logger.warning(f"⚠️ Link joinchat não suportado: {link_or_id}")
        return None, False
    
    logger.error(f"❌ Não foi possível extrair/validar chat_id de: {link_or_id[:50]}...")
    return None, False


def validate_chat_id_via_api(chat_id: str, bot_token: str) -> bool:
    """
    Valida chat_id via Telegram API (getChat)
    
    Retorna: True se chat_id é válido, False caso contrário
    """
    try:
        url = f"https://api.telegram.org/bot{bot_token}/getChat"
        response = requests.post(url, json={'chat_id': chat_id}, timeout=10)
        
        if response.status_code == 200:
            data = response.json()
            if data.get('ok', False):
                chat_type = data.get('result', {}).get('type', '')
                if chat_type in ['group', 'supergroup']:
                    logger.info(f"✅ Chat ID válido: {chat_id[:20]}... (tipo: {chat_type})")
                    return True
                else:
                    logger.warning(f"⚠️ Chat ID não é grupo/supergrupo (tipo: {chat_type})")
                    return False
            else:
                logger.warning(f"⚠️ Telegram API retornou ok=False para chat_id: {chat_id[:20]}...")
                return False
        
        logger.warning(f"⚠️ HTTP {response.status_code} ao validar chat_id: {chat_id[:20]}...")
        return False
    except requests.exceptions.Timeout:
        logger.error(f"❌ Timeout ao validar chat_id via API: {chat_id[:20]}...")
        return False
    except Exception as e:
        logger.error(f"❌ Erro ao validar chat_id via API: {e}")
        return False


def validate_bot_is_admin_and_in_group(bot: Bot, chat_id: str) -> Tuple[bool, Optional[str]]:
    """
    Valida se bot é admin do grupo com permissão 'Ban Members'
    
    Retorna: (is_admin, error_message)
    """
    try:
        # Primeiro, obter informações do bot via getMe
        url_get_me = f"https://api.telegram.org/bot{bot.token}/getMe"
        response = requests.post(url_get_me, timeout=10)
        
        if response.status_code != 200:
            error_msg = f"Erro ao obter informações do bot: HTTP {response.status_code}"
            logger.error(f"❌ {error_msg}")
            return False, error_msg
        
        bot_info = response.json()
        if not bot_info.get('ok'):
            error_msg = "Erro ao obter informações do bot: API retornou ok=False"
            logger.error(f"❌ {error_msg}")
            return False, error_msg
        
        bot_user_id = bot_info.get('result', {}).get('id')
        if not bot_user_id:
            error_msg = "Não foi possível obter ID do bot"
            logger.error(f"❌ {error_msg}")
            return False, error_msg
        
        # Agora verificar se bot é admin do grupo
        url_get_member = f"https://api.telegram.org/bot{bot.token}/getChatMember"
        response = requests.post(url_get_member, json={
            'chat_id': chat_id,
            'user_id': bot_user_id
        }, timeout=10)
        
        if response.status_code != 200:
            error_msg = f"Erro ao verificar permissões: HTTP {response.status_code}"
            logger.error(f"❌ {error_msg}")
            return False, error_msg
        
        data = response.json()
        if not data.get('ok'):
            error_msg = f"Erro ao verificar permissões: API retornou ok=False"
            logger.error(f"❌ {error_msg}")
            return False, error_msg
        
        member = data.get('result', {})
        status = member.get('status', '')
        can_restrict_members = member.get('can_restrict_members', False)
        
        if status in ['administrator', 'creator']:
            if can_restrict_members:
                logger.info(f"✅ Bot é admin e tem permissão 'Ban Members' no grupo: {chat_id[:20]}...")
                return True, None
            else:
                error_msg = "Bot é admin mas não tem permissão 'Ban Members'"
                logger.warning(f"⚠️ {error_msg}")
                return False, error_msg
        elif status == 'member':
            error_msg = "Bot é membro do grupo mas não é administrador"
            logger.warning(f"⚠️ {error_msg}")
            return False, error_msg
        elif status in ['left', 'kicked']:
            error_msg = f"Bot não está no grupo (status: {status})"
            logger.warning(f"⚠️ {error_msg}")
            return False, error_msg
        else:
            error_msg = f"Status desconhecido: {status}"
            logger.warning(f"⚠️ {error_msg}")
            return False, error_msg
            
    except requests.exceptions.Timeout:
        error_msg = "Timeout ao verificar permissões do bot"
        logger.error(f"❌ {error_msg}")
        return False, error_msg
    except Exception as e:
        error_msg = f"Erro ao verificar permissões: {str(e)}"
        logger.error(f"❌ {error_msg}")
        return False, error_msg


def normalize_vip_chat_id(chat_id_or_link: str) -> str:
    """
    ✅ CORREÇÃO 4 (ROBUSTA): Centraliza normalização de vip_chat_id
    
    Normaliza chat_id para formato padrão usado no sistema:
    - Remove espaços em branco
    - Converte para string
    - Remove caracteres especiais desnecessários
    - Garante consistência em todo o sistema
    
    Args:
        chat_id_or_link: Chat ID (ex: -1001234567890) ou link do Telegram
        
    Returns:
        str: Chat ID normalizado (string, sem espaços, pronto para uso)
    """
    if not chat_id_or_link:
        logger.warning("⚠️ normalize_vip_chat_id: chat_id_or_link vazio ou None")
        return None
    
    # Converter para string e remover espaços
    normalized = str(chat_id_or_link).strip()
    
    # Remover caracteres de controle e espaços extras
    normalized = ' '.join(normalized.split())
    
    # Se estiver vazio após normalização, retornar None
    if not normalized:
        logger.warning("⚠️ normalize_vip_chat_id: chat_id vazio após normalização")
        return None
    
    logger.debug(f"✅ vip_chat_id normalizado: '{chat_id_or_link}' → '{normalized}'")
    return normalized


def check_user_in_group(bot_token: str, chat_id: str, telegram_user_id: str) -> bool:
    """
    Verifica se usuário está no grupo via getChatMember
    
    Retorna: True se usuário está no grupo (member/admin/creator), False caso contrário
    """
    try:
        url = f"https://api.telegram.org/bot{bot_token}/getChatMember"
        response = requests.post(url, json={
            'chat_id': chat_id,
            'user_id': telegram_user_id
        }, timeout=10)
        
        if response.status_code == 200:
            data = response.json()
            if data.get('ok'):
                member = data.get('result', {})
                status = member.get('status', '')
                
                if status in ['member', 'administrator', 'creator']:
                    logger.info(f"✅ Usuário {telegram_user_id} está no grupo {chat_id[:20]}... (status: {status})")
                    return True
                else:
                    logger.info(f"ℹ️ Usuário {telegram_user_id} não está no grupo {chat_id[:20]}... (status: {status})")
                    return False
            else:
                logger.warning(f"⚠️ API retornou ok=False ao verificar usuário no grupo")
                return False
        
        logger.warning(f"⚠️ HTTP {response.status_code} ao verificar usuário no grupo")
        return False
    except requests.exceptions.Timeout:
        logger.error(f"❌ Timeout ao verificar usuário no grupo")
        return False
    except Exception as e:
        logger.error(f"❌ Erro ao verificar usuário no grupo: {e}")
        return False

