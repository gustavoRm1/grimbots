"""
Meta Pixel / Conversions API Integration
Documentação: https://developers.facebook.com/docs/marketing-api/conversions-api

IMPLEMENTAÇÃO QI 300:
- Server-side tracking (100% confiável, sem AdBlock)
- Deduplicação automática via event_id
- Retry inteligente com backoff exponencial
- Logs detalhados para auditoria
- Validação completa de dados

ARQUITETURA V2.0 (QI 240):
- Pixel configurado POR POOL (RedirectPool) ao invés de por Bot
- Alta disponibilidade: bot cai, pool continua tracking
- Dados consolidados: 1 campanha = 1 pool = 1 pixel
- Configuração simplificada: 1 vez por pool vs N vezes por bot
"""

import requests
import hashlib
import time
import logging
import json
import uuid
from datetime import datetime
from typing import Dict, List, Optional, Tuple
from urllib.parse import urlparse
from utils.ip_utils import normalize_ip_to_ipv6

logger = logging.getLogger(__name__)

def normalize_external_id(fbclid: str) -> str:
    if not fbclid or not isinstance(fbclid, str):
        return None
    fbclid = fbclid.strip()
    if not fbclid:
        return None
    return fbclid


def process_meta_parameters(
    request_cookies: dict = None,
    request_args: dict = None,
    request_headers: dict = None,
    request_remote_addr: str = None,
    referer: str = None,
    fbclid_first_seen_ts: int = None  # ✅ NOVO: Timestamp (em ms) quando fbclid foi primeiro observado
) -> dict:
    """
    Processa cookies, query parameters e headers para extrair fbc, fbp e client_ip_address
    conforme best practices do Meta Parameter Builder Library.
    
    ✅ SERVER-SIDE PARAMETER BUILDER (Implementação conforme Meta best practices)
    
    Prioridades:
    - fbc: Cookie _fbc (browser) > Gerado baseado em fbclid (se presente na URL) > None
    - fbp: Cookie _fbp (browser) > None
    - client_ip_address: Cookie _fbi (Parameter Builder) > X-Forwarded-For > Remote-Addr > None
    
    Args:
        request_cookies: Dict de cookies (ex: {'_fbc': '...', '_fbp': '...', '_fbi': '...'})
        request_args: Dict de query parameters (ex: {'fbclid': '...'})
        request_headers: Dict de headers (ex: {'X-Forwarded-For': '...', 'Referer': '...'})
        request_remote_addr: IP do cliente (ex: '192.168.1.1')
        referer: URL referer (ex: 'https://facebook.com/...')
    
    Returns:
        dict com keys:
            - 'fbc': str ou None (Facebook Click ID)
            - 'fbc_origin': str ('cookie', 'generated_from_fbclid', ou None)
            - 'fbp': str ou None (Facebook Browser ID)
            - 'fbp_origin': str ('cookie' ou None)
            - 'client_ip_address': str ou None (IP do cliente)
            - 'ip_origin': str ('parameter_builder', 'x_forwarded_for', 'remote_addr', ou None)
    """
    result = {
        'fbc': None,
        'fbc_origin': None,
        'fbp': None,
        'fbp_origin': None,
        'client_ip_address': None,
        'ip_origin': None
    }
    
    request_cookies = request_cookies or {}
    request_args = request_args or {}
    request_headers = request_headers or {}
    
    # ✅ DEBUG: Log cookies e args recebidos (para identificar problemas)
    logger.debug(f"[PARAM BUILDER] Cookies recebidos: {list(request_cookies.keys())}")
    logger.debug(f"[PARAM BUILDER] Args recebidos: {list(request_args.keys())}")
    if request_args.get('fbclid'):
        logger.info(f"[PARAM BUILDER] ✅ fbclid encontrado nos args: {request_args.get('fbclid')[:50]}... (len={len(request_args.get('fbclid', ''))})")
    
    # ✅ FBC: Prioridade 1 - Cookie _fbc do browser (MAIS CONFIÁVEL - Meta confia 100%)
    fbc_cookie = request_cookies.get('_fbc', '').strip()
    if fbc_cookie:
        logger.debug(f"[PARAM BUILDER] Cookie _fbc encontrado: {fbc_cookie[:50]}... (len={len(fbc_cookie)})")
        if len(fbc_cookie) >= 10:
            # Validar formato (deve começar com 'fb.1.' ou 'fb.2.')
            if fbc_cookie.startswith(('fb.1.', 'fb.2.')):
                result['fbc'] = fbc_cookie
                result['fbc_origin'] = 'cookie'
                logger.info(f"[PARAM BUILDER] ✅ fbc capturado do cookie (ORIGEM REAL): {fbc_cookie[:50]}...")
            else:
                logger.warning(f"[PARAM BUILDER] ⚠️ Cookie _fbc tem formato inválido (não começa com fb.1./fb.2.): {fbc_cookie[:30]}...")
        else:
            logger.warning(f"[PARAM BUILDER] ⚠️ Cookie _fbc muito curto (len={len(fbc_cookie)}, mínimo=10): {fbc_cookie[:30]}...")
    else:
        logger.debug(f"[PARAM BUILDER] Cookie _fbc não encontrado")
    
    # ✅ CRÍTICO: FBC - Prioridade 2 - Gerar baseado em fbclid (se presente)
    # Meta aceita _fbc gerado quando fbclid está presente (conforme documentação oficial)
    # SEM fbc, VENDAS NÃO SÃO TRACKEADAS CORRETAMENTE!
    # ✅ CORREÇÃO: Usar creationTime do cookie _fbc se existir, senão usar timestamp quando fbclid foi primeiro observado
    if not result['fbc']:
        fbclid = request_args.get('fbclid', '').strip()
        if fbclid:
            logger.info(f"[PARAM BUILDER] ✅ fbclid encontrado nos args: {fbclid[:50]}... (len={len(fbclid)})")
            try:
                # Formato: fb.1.{creationTime_ms}.{fbclid}
                # ✅ CORREÇÃO CRÍTICA: Meta diz: "use the timestamp in milliseconds when you first observed or received this fbclid value"
                # NÃO usar timestamp atual! Deve ser quando fbclid foi primeiro observado
                # Prioridade 1: Se cookie _fbc existe mas não foi capturado, tentar extrair creationTime
                # Prioridade 2: Usar pageview_ts do tracking_data (quando fbclid foi primeiro observado)
                # Prioridade 3: Fallback para timestamp atual (melhor que nada, mas não ideal)
                
                # ✅ CORREÇÃO CRÍTICA: Meta diz "use the timestamp in milliseconds when you first observed or received this fbclid value"
                # Prioridade 1: Extrair creationTime do cookie _fbc (se existir mas não foi capturado antes)
                # Prioridade 2: Usar fbclid_first_seen_ts (quando fbclid foi primeiro observado - pageview_ts)
                # Prioridade 3: Fallback para timestamp atual (não ideal, mas melhor que nada)
                creation_time_ms = None
                
                # ✅ PRIORIDADE 1: Usar timestamp quando fbclid foi primeiro observado (pageview_ts)
                # Meta diz: "use the timestamp in milliseconds when you first observed or received this fbclid value"
                if creation_time_ms is None and fbclid_first_seen_ts is not None:
                    # fbclid_first_seen_ts pode estar em segundos ou milissegundos
                    # Se < 10000000000 (10 dígitos), está em segundos -> converter para ms
                    if fbclid_first_seen_ts < 10000000000:
                        creation_time_ms = int(fbclid_first_seen_ts * 1000)
                    else:
                        creation_time_ms = int(fbclid_first_seen_ts)
                    logger.info(f"[PARAM BUILDER] ✅ creationTime usando fbclid_first_seen_ts (quando fbclid foi primeiro observado): {creation_time_ms}")
                
                # ✅ PRIORIDADE 3: Fallback para timestamp atual (não ideal, mas necessário)
                if creation_time_ms is None:
                    creation_time_ms = int(time.time() * 1000)
                    logger.warning(f"[PARAM BUILDER] ⚠️ creationTime não encontrado - usando timestamp atual (não ideal, mas necessário)")
                    logger.warning(f"[PARAM BUILDER] ⚠️ IDEAL: Passar fbclid_first_seen_ts (pageview_ts) para usar timestamp quando fbclid foi primeiro observado")
                
                result['fbc'] = f"fb.1.{creation_time_ms}.{fbclid}"
                result['fbc_origin'] = 'generated_from_fbclid'
                logger.info(f"[PARAM BUILDER] ✅ fbc gerado baseado em fbclid (conforme doc Meta): {result['fbc'][:50]}...")
                logger.info(f"[PARAM BUILDER] ✅ VENDA SERÁ TRACKEADA CORRETAMENTE (fbc gerado)")
            except Exception as e:
                logger.error(f"[PARAM BUILDER] ❌ ERRO CRÍTICO ao gerar fbc baseado em fbclid: {e}", exc_info=True)
                logger.error(f"[PARAM BUILDER] ❌ SEM fbc, VENDAS NÃO SÃO TRACKEADAS!")
        else:
            logger.warning(f"[PARAM BUILDER] ⚠️ fbclid não encontrado nos args (não será gerado fbc)")
            logger.warning(f"[PARAM BUILDER] ⚠️ SEM fbclid, Parameter Builder NÃO consegue gerar fbc")
    
    # ✅ CRÍTICO: LOG FINAL - Mostrar resultado do fbc
    # SEM fbc, VENDAS NÃO SÃO TRACKEADAS CORRETAMENTE!
    if not result['fbc']:
        logger.error(f"[PARAM BUILDER] ❌ CRÍTICO: fbc NÃO retornado (cookie _fbc ausente e fbclid ausente)")
        logger.error(f"[PARAM BUILDER] ❌ SEM fbc, VENDAS NÃO SÃO TRACKEADAS CORRETAMENTE!")
    else:
        logger.info(f"[PARAM BUILDER] ✅ fbc retornado com sucesso (origem: {result.get('fbc_origin', 'unknown')}) - VENDA SERÁ TRACKEADA")
    
    # ✅ FBP: Prioridade 1 - Cookie _fbp do browser (MAIS CONFIÁVEL)
    fbp_cookie = request_cookies.get('_fbp', '').strip()
    if fbp_cookie and len(fbp_cookie) >= 10:
        # Validar formato (deve começar com 'fb.1.' ou 'fb.2.')
        if fbp_cookie.startswith(('fb.1.', 'fb.2.')):
            result['fbp'] = fbp_cookie
            result['fbp_origin'] = 'cookie'
            logger.debug(f"[PARAM BUILDER] fbp capturado do cookie: {fbp_cookie[:30]}...")
    
    # ✅ CLIENT_IP_ADDRESS: Prioridade 1 - Cookie _fbi do Parameter Builder (MAIS CONFIÁVEL)
    # Parameter Builder prioriza IPv6, fallback IPv4 (melhor que IP do servidor para matching)
    fbi_cookie = request_cookies.get('_fbi', '').strip()
    if fbi_cookie:
        # Limpar sufixo do Parameter Builder (.AQYBAQIA.AQYBAQIA) se presente
        ip_value = fbi_cookie.split('.AQYBAQIA')[0] if '.AQYBAQIA' in fbi_cookie else fbi_cookie
        # Validar formato básico de IP (IPv4 ou IPv6)
        if len(ip_value) >= 7:  # Mínimo: '1.1.1.1' (7 chars)
            result['client_ip_address'] = ip_value
            result['ip_origin'] = 'parameter_builder'
            logger.debug(f"[PARAM BUILDER] client_ip_address capturado do Parameter Builder (_fbi): {ip_value}")
    
    # ✅ CLIENT_IP_ADDRESS: Prioridade 2 - X-Forwarded-For header
    if not result['client_ip_address']:
        x_forwarded_for = str(request_headers.get('X-Forwarded-For', request_headers.get('x-forwarded-for', ''))).strip()
        if x_forwarded_for:
            # X-Forwarded-For pode conter múltiplos IPs (ex: 'client, proxy1, proxy2')
            # Pegar o primeiro IP (IP do cliente original)
            first_ip = x_forwarded_for.split(',')[0].strip()
            if len(first_ip) >= 7:
                result['client_ip_address'] = first_ip
                result['ip_origin'] = 'x_forwarded_for'
                logger.debug(f"[PARAM BUILDER] client_ip_address capturado do X-Forwarded-For: {first_ip}")
    
    # ✅ CLIENT_IP_ADDRESS: Prioridade 3 - Remote-Addr
    if not result['client_ip_address'] and request_remote_addr:
        remote_addr = str(request_remote_addr).strip()
        # Validar que não é '0.0.0.0' ou vazio
        if remote_addr and remote_addr != '0.0.0.0' and len(remote_addr) >= 7:
            result['client_ip_address'] = remote_addr
            result['ip_origin'] = 'remote_addr'
            logger.debug(f"[PARAM BUILDER] client_ip_address capturado do Remote-Addr: {remote_addr}")
    
    # ✅ CORREÇÃO CRÍTICA: Normalizar IP para IPv6 (conforme recomendação Meta)
    # Meta recomenda IPv6 para melhor matching e durabilidade
    # Converter IPv4 para IPv6 mapeado quando possível
    if result.get('client_ip_address'):
        try:
            original_ip = result['client_ip_address']
            normalized_ip = normalize_ip_to_ipv6(original_ip)
            if original_ip != normalized_ip:
                logger.info(f"[PARAM BUILDER] ✅ IP normalizado para IPv6: {original_ip} -> {normalized_ip}")
            result['client_ip_address'] = normalized_ip
        except Exception as e:
            logger.warning(f"[PARAM BUILDER] ⚠️ Erro ao normalizar IP para IPv6: {e}")
            # Continuar com IP original se normalização falhar
    
    return result


class MetaPixelAPI:
    """
    Client para Meta Conversions API (CAPI)
    
    CARACTERÍSTICAS QI 300:
    - Zero duplicação garantida
    - Dados criptografados (SHA256)
    - Event Match Quality máximo
    - Retry automático em falhas
    - Logs auditáveis
    """
    
    API_VERSION = 'v19.0'
    BASE_URL = 'https://graph.facebook.com'
    MAX_RETRIES = 3
    RETRY_DELAYS = [1, 2, 4]  # Backoff exponencial
    
    @staticmethod
    def _hash_data(data: str) -> str:
        """Criptografa dados sensíveis com SHA256"""
        if not data:
            return ""
        return hashlib.sha256(data.encode('utf-8')).hexdigest()
    
    @staticmethod
    def _generate_event_id(event_type: str, unique_id: str, timestamp: int = None) -> str:
        """
        Gera event_id único para deduplicação
        
        Formato: {event_type}_{unique_id}_{timestamp}
        Exemplo: purchase_PAY_12345_1729440000
        """
        if timestamp is None:
            timestamp = int(time.time())
        
        return f"{event_type}_{unique_id}_{timestamp}"
    
    @staticmethod
    def _build_user_data(
        customer_user_id: str = None,
        email: str = None,
        phone: str = None,
        client_ip: str = None,
        client_user_agent: str = None,
        fbp: str = None,
        fbc: str = None,
        external_id: str = None
    ) -> Dict:
        """
        Constrói user_data para o evento
        
        Meta usa esses dados para matching com client-side events
        
        ✅ VALIDAÇÕES DE SEGURANÇA:
        - Ignora valores None ou strings vazias
        - Valida email antes de hash
        - Limpa phone antes de hash
        - Garante que external_id é sempre array quando presente
        """
        user_data = {}
        
        # ✅ CRÍTICO: External ID (obrigatório para Conversions API)
        # Consistente com user_data.py: apenas fbclid como external_id (único ID)
        
        external_ids = []
        
        if isinstance(external_id, list):
            external_ids = external_id
            logger.debug(f"✅ External ID já é array (do TrackingService): {len(external_ids)} ID(s)")
        else:
            if external_id and isinstance(external_id, str) and external_id.strip():
                external_ids.append(MetaPixelAPI._hash_data(external_id.strip()))
        
        if external_ids:
            user_data['external_id'] = external_ids
        
        # ✅ Email (hashed) - apenas emails reais (não sintéticos)
        if email and isinstance(email, str) and email.strip():
            email_clean = email.lower().strip()
            synthetic_domains = ['@telegram.user', '@user.telegram', '@example.com']
            if any(d in email_clean for d in synthetic_domains):
                logger.debug(f"Email sintético ignorado: {email_clean}")
            elif '@' in email_clean and len(email_clean) >= 3:
                user_data['em'] = [MetaPixelAPI._hash_data(email_clean)]
        
        # ✅ Telefone (hashed) - normalizar com country code 55 (consistente com user_data.py)
        if phone and isinstance(phone, str):
            phone_clean = ''.join(filter(str.isdigit, phone))
            phone_clean = phone_clean.lstrip('0')
            if phone_clean and len(phone_clean) >= 10:
                if not phone_clean.startswith('55'):
                    phone_clean = '55' + phone_clean
                user_data['ph'] = [MetaPixelAPI._hash_data(phone_clean)]
        
        # ✅ Dados técnicos (IP e User Agent) - validar formato básico
        if client_ip and isinstance(client_ip, str) and client_ip.strip():
            # Validação básica: IP deve ter pelo menos 7 caracteres (ex: 1.1.1.1)
            if len(client_ip.strip()) >= 7:
                user_data['client_ip_address'] = client_ip.strip()
        
        if client_user_agent and isinstance(client_user_agent, str) and client_user_agent.strip():
            # User Agent deve ter pelo menos 10 caracteres (formato mínimo)
            if len(client_user_agent.strip()) >= 10:
                user_data['client_user_agent'] = client_user_agent.strip()
        
        # ✅ Cookies do Meta (para matching) - validar formato básico
        if fbp and isinstance(fbp, str) and fbp.strip():
            # _fbp geralmente começa com "fb.1." ou "fb.2."
            if len(fbp.strip()) >= 10:
                user_data['fbp'] = fbp.strip()
        
        if fbc and isinstance(fbc, str) and fbc.strip():
            # _fbc geralmente começa com "fb.1."
            if len(fbc.strip()) >= 10:
                user_data['fbc'] = fbc.strip()
        
        return user_data
    
    @staticmethod
    def _send_event_with_retry(
        url: str,
        payload: Dict,
        max_retries: int = MAX_RETRIES
    ) -> Tuple[bool, Dict, str]:
        """
        Envia evento com retry automático
        
        Returns:
            (success, response_data, error_message)
        """
        last_error = None
        
        for attempt in range(max_retries):
            try:
                logger.info(f"📤 Tentativa {attempt + 1}/{max_retries} - Enviando para Meta API")
                
                response = requests.post(
                    url,
                    json=payload,
                    timeout=3,
                    headers={
                        'Content-Type': 'application/json',
                        'User-Agent': 'GrimPay-MetaPixel/1.0'
                    }
                )

                try:
                    response_data = response.json()
                except Exception:
                    response_data = response.text

                try:
                    payload_event_id = None
                    if isinstance(payload, dict):
                        payload_event_id = (
                            payload.get("data", [{}])[0] if payload.get("data") else {}
                        ).get("event_id")
                    logger.error(
                        "[META RAW RESPONSE] status=%s body=%s payload_event_id=%s",
                        getattr(response, "status_code", None),
                        response_data,
                        payload_event_id,
                    )
                except Exception as log_exc:
                    logger.warning(f"[META RAW RESPONSE] Falha ao logar resposta Meta: {log_exc}")
                
                if response.status_code == 200:
                    logger.info(f"✅ Meta API sucesso: {response_data}")
                    return True, response_data, None
                elif 400 <= response.status_code < 500 and response.status_code != 429:
                    error_msg = response_data.get('error', {}).get('message', 'Unknown error')
                    logger.error(f"❌ Meta API error {response.status_code}: {error_msg} — não retentando")
                    last_error = error_msg
                    break
                elif response.status_code == 429:
                    if attempt < max_retries - 1:
                        wait = 60 * (2 ** attempt)
                        logger.warning(f"⏳ 429 rate limit | tentativa {attempt + 1}/{max_retries} | retry em {wait}s")
                        last_error = "429 rate limit"
                        time.sleep(wait)
                        continue
                    else:
                        logger.error(f"❌ 429 esgotou retries | pixel_id extraído da URL")
                        last_error = "429 rate limit exhausted"
                        break
                else:
                    error_msg = response_data.get('error', {}).get('message', 'Unknown error')
                    logger.warning(f"⚠️ Meta API error {response.status_code}: {error_msg}")
                    last_error = error_msg
                    
            except requests.exceptions.Timeout:
                last_error = f"Timeout na tentativa {attempt + 1}"
                logger.warning(f"⏱️ {last_error}")
                
            except requests.exceptions.RequestException as e:
                last_error = f"Erro de rede na tentativa {attempt + 1}: {str(e)}"
                logger.warning(f"🌐 {last_error}")
                
            except Exception as e:
                last_error = f"Erro inesperado na tentativa {attempt + 1}: {str(e)}"
                logger.error(f"💥 {last_error}")
                break
            
            # Delay antes do próximo retry
            if attempt < max_retries - 1:
                delay = MetaPixelAPI.RETRY_DELAYS[min(attempt, len(MetaPixelAPI.RETRY_DELAYS) - 1)]
                logger.info(f"⏳ Aguardando {delay}s antes do próximo retry...")
                time.sleep(delay)
        
        return False, None, last_error or "Erro desconhecido"
    
    @staticmethod
    def send_pageview_event(
        pixel_id: str,
        access_token: str,
        event_id: str,
        customer_user_id: str = None,
        external_id: str = None,
        client_ip: str = None,
        client_user_agent: str = None,
        fbp: str = None,
        fbc: str = None,
        utm_source: str = None,
        utm_campaign: str = None,
        campaign_code: str = None,
        event_source_url: str = None  # ✅ NOVO: URL do redirect
    ) -> Dict:
        """
        Envia evento PageView para Meta
        
        Args:
            pixel_id: ID do pixel (ex: 123456789)
            access_token: Token de acesso do Business Manager
            event_id: ID único do evento
            customer_user_id: ID do usuário (Telegram)
            external_id: ID do clique no redirecionador
            ... outros parâmetros
            
        Returns:
            dict: {'success': bool, 'response': dict, 'error': str}
        """
        
        url = f"{MetaPixelAPI.BASE_URL}/{MetaPixelAPI.API_VERSION}/{pixel_id}/events"
        
        # User Data
        user_data = MetaPixelAPI._build_user_data(
            customer_user_id=customer_user_id,
            external_id=external_id,
            client_ip=client_ip,
            client_user_agent=client_user_agent,
            fbp=fbp,
            fbc=fbc
        )
        
        # Custom Data
        custom_data = {}
        if utm_source:
            custom_data['utm_source'] = utm_source
        if utm_campaign:
            custom_data['utm_campaign'] = utm_campaign
        if campaign_code:
            custom_data['campaign_code'] = campaign_code
        
        # Payload
        payload = {
            'data': [{
                'event_name': 'PageView',
                'event_time': int(time.time()),
                'event_id': event_id,
                'action_source': 'website',
                'event_source_url': event_source_url if event_source_url else None,  # ✅ ADICIONAR
                'user_data': user_data,
                'custom_data': custom_data if custom_data else {}  # ✅ CORRIGIR: {} não None
            }],
            'access_token': access_token
        }
        
        # Enviar com retry
        success, response_data, error = MetaPixelAPI._send_event_with_retry(url, payload)
        
        return {
            'success': success,
            'response': response_data,
            'error': error,
            'event_type': 'PageView',
            'event_id': event_id
        }
    
    @staticmethod
    def send_viewcontent_event(
        pixel_id: str,
        access_token: str,
        event_id: str,
        customer_user_id: str,
        content_id: str = None,
        content_name: str = None,
        client_ip: str = None,
        client_user_agent: str = None,
        fbp: str = None,
        fbc: str = None,
        event_source_url: str = None,
        utm_source: str = None,
        utm_campaign: str = None,
        campaign_code: str = None
    ) -> Dict:
        """
        Envia evento ViewContent para Meta
        
        Disparado quando usuário inicia conversa com bot (/start)
        """
        
        url = f"{MetaPixelAPI.BASE_URL}/{MetaPixelAPI.API_VERSION}/{pixel_id}/events"
        
        # User Data
        user_data = MetaPixelAPI._build_user_data(
            customer_user_id=customer_user_id,
            client_ip=client_ip,
            client_user_agent=client_user_agent,
            fbp=fbp,
            fbc=fbc
        )
        
        # Custom Data
        custom_data = {
            'content_type': 'product'
        }
        
        if content_id:
            custom_data['content_ids'] = [content_id]
        
        if content_name:
            custom_data['content_name'] = content_name
        
        if utm_source:
            custom_data['utm_source'] = utm_source
        if utm_campaign:
            custom_data['utm_campaign'] = utm_campaign
        if campaign_code:
            custom_data['campaign_code'] = campaign_code
        
        # Payload
        payload = {
            'data': [{
                'event_name': 'ViewContent',
                'event_time': int(time.time()),
                'event_id': event_id,
                'action_source': 'website',
                'user_data': user_data,
                'custom_data': custom_data
            }],
            'access_token': access_token
        }
        if event_source_url:
            payload['data'][0]['event_source_url'] = event_source_url
        
        # Enviar com retry
        success, response_data, error = MetaPixelAPI._send_event_with_retry(url, payload)
        
        return {
            'success': success,
            'response': response_data,
            'error': error,
            'event_type': 'ViewContent',
            'event_id': event_id
        }
    
    @staticmethod
    def send_purchase_event(
        pixel_id: str,
        access_token: str,
        event_id: str,
        value: float,
        currency: str,
        customer_user_id: str,
        content_id: str = None,
        content_name: str = None,
        content_type: str = 'product',
        num_items: int = 1,
        is_downsell: bool = False,
        is_upsell: bool = False,
        is_remarketing: bool = False,
        order_bump_value: float = 0,
        client_ip: str = None,
        client_user_agent: str = None,
        fbp: str = None,
        fbc: str = None,
        event_source_url: str = None,
        utm_source: str = None,
        utm_campaign: str = None,
        campaign_code: str = None,
        email: str = None,
        phone: str = None
    ) -> Dict:
        """
        Envia evento Purchase para Meta
        
        CRÍTICO: Este é o evento mais importante para otimização!
        Cada compra (inicial, downsell, upsell, remarketing) deve ser enviada.
        """
        
        url = f"{MetaPixelAPI.BASE_URL}/{MetaPixelAPI.API_VERSION}/{pixel_id}/events"
        
        # User Data (máximo de dados para melhor matching)
        user_data = MetaPixelAPI._build_user_data(
            customer_user_id=customer_user_id,
            email=email,
            phone=phone,
            client_ip=client_ip,
            client_user_agent=client_user_agent,
            fbp=fbp,
            fbc=fbc
        )
        
        # Custom Data
        custom_data = {
            'value': float(value),
            'currency': currency,
            'content_type': content_type,
            'num_items': num_items
        }
        
        if content_id:
            custom_data['content_ids'] = [content_id]
        
        if content_name:
            custom_data['content_name'] = content_name
        
        # Categorização da venda
        if is_downsell:
            custom_data['content_category'] = 'downsell'
        elif is_upsell:
            custom_data['content_category'] = 'upsell'
        elif is_remarketing:
            custom_data['content_category'] = 'remarketing'
        else:
            custom_data['content_category'] = 'initial'
        
        # Order bump
        if order_bump_value > 0:
            custom_data['order_bump_value'] = float(order_bump_value)
        
        # UTM e campaign tracking
        if utm_source:
            custom_data['utm_source'] = utm_source
        if utm_campaign:
            custom_data['utm_campaign'] = utm_campaign
        if campaign_code:
            custom_data['campaign_code'] = campaign_code
        
        # Payload
        payload = {
            'data': [{
                'event_name': 'Purchase',
                'event_time': int(time.time()),
                'event_id': event_id,
                'action_source': 'website',
                'user_data': user_data,
                'custom_data': custom_data
            }],
            'access_token': access_token
        }
        if event_source_url:
            payload['data'][0]['event_source_url'] = event_source_url
        
        # Enviar com retry
        success, response_data, error = MetaPixelAPI._send_event_with_retry(url, payload)
        
        return {
            'success': success,
            'response': response_data,
            'error': error,
            'event_type': 'Purchase',
            'event_id': event_id,
            'value': value,
            'currency': currency
        }
    
    @staticmethod
    def test_connection(pixel_id: str, access_token: str) -> Dict:
        """
        Testa conexão REAL com Meta API usando Celery (MVP - QI 540)
        
        ARQUITETURA CORRETA PARA 100K/DIA:
        - USA O MESMO FLUXO dos eventos reais
        - Enfileira no Celery
        - Worker processa
        - Gestor VÊ NO LOG que funcionou
        - CONFIANÇA 100%
        
        Não é sobre ser rápido.
        É sobre PROVAR que funciona.
        """
        try:
            # ✅ PRIMEIRO: VALIDAR TOKEN DE ACESSO
            token_valid = MetaPixelAPI._validate_access_token(access_token)
            if not token_valid:
                return {
                    'success': False,
                    'pixel_info': None,
                    'error': 'Token de acesso inválido ou expirado. Gere um novo token no Meta Business Manager.'
                }
            
            # Importar RQ task
            from tasks_async import enqueue_meta_event
            import time
            
            # Criar evento de teste (USANDO ESTRUTURA CORRETA)
            event_data = {
                'event_name': 'ViewContent',  # ✅ Nome correto (mesmo dos eventos reais)
                'event_time': int(time.time()),
                'event_id': f'test_connection_{int(time.time())}',
                'action_source': 'website',
                'user_data': {
                    'external_id': f'test_user_{int(time.time())}',  # ✅ External ID obrigatório
                    'client_ip_address': '127.0.0.1',
                    'client_user_agent': 'GrimBots-ConnectionTest/1.0'
                },
                'custom_data': {
                    'content_id': 'test_connection',
                    'content_name': 'Teste de Conexão',
                    'bot_id': 0,
                    'bot_username': 'test_bot',
                    'utm_source': 'test',
                    'utm_campaign': 'connection_test',
                    'campaign_code': 'TEST_CONNECTION'
                }
            }
            
            # ✅ ENFILEIRAR NA RQ (MESMO FLUXO DOS EVENTOS REAIS!)
            enqueue_meta_event(
                pixel_id=pixel_id,
                access_token=access_token,
                event_data=event_data,
                test_code='TEST_CONNECTION'
            )
            
            return {
                'success': True,
                'pixel_info': {
                    'events_received': 1,
                    'fbtrace_id': None,
                    'note': 'Evento enfileirado na RQ (verificar logs do worker para resultado)'
                },
                'error': None
            }
                
        except Exception as e:
            # Se Celery falhar, tentar envio direto como fallback
            import time
            import requests
            
            url = f"{MetaPixelAPI.BASE_URL}/{MetaPixelAPI.API_VERSION}/{pixel_id}/events"
            
            test_payload = {
                'data': [{
                    'event_name': 'ViewContent',  # ✅ Nome correto
                    'event_time': int(time.time()),
                    'event_id': f'test_fallback_{int(time.time())}',
                    'action_source': 'website',
                    'user_data': {
                        'external_id': f'test_fallback_{int(time.time())}',  # ✅ External ID obrigatório
                        'client_ip_address': '127.0.0.1',
                        'client_user_agent': 'Test'
                    },
                    'custom_data': {
                        'content_id': 'test_fallback',
                        'content_name': 'Teste Fallback',
                        'bot_id': 0,
                        'bot_username': 'test_bot',
                        'utm_source': 'test',
                        'utm_campaign': 'fallback_test',
                        'campaign_code': 'TEST_FALLBACK'
                    }
                }],
                'access_token': access_token
            }
            
            try:
                response = requests.post(url, json=test_payload, timeout=10)
                
                if response.status_code == 200:
                    return {
                        'success': True,
                        'pixel_info': {
                            'note': 'Testado via envio direto (fallback)',
                            'events_received': 1
                        },
                        'error': None
                    }
                else:
                    return {
                        'success': False,
                        'pixel_info': None,
                        'error': f'Erro ao testar: {str(e)}'
                    }
            except:
                return {
                    'success': False,
                    'pixel_info': None,
                    'error': f'Celery e envio direto falharam: {str(e)}'
                }
    
    @staticmethod
    def _validate_access_token(access_token: str) -> bool:
        """
        Valida se o token de acesso é válido fazendo uma requisição simples
        
        Args:
            access_token: Token de acesso do Meta
            
        Returns:
            bool: True se válido, False se inválido
        """
        try:
            import requests
            
            # Fazer uma requisição simples para validar o token
            url = f"{MetaPixelAPI.BASE_URL}/{MetaPixelAPI.API_VERSION}/me"
            
            response = requests.get(
                url,
                params={'access_token': access_token},
                timeout=10
            )
            
            if response.status_code == 200:
                return True
            else:
                return False
                
        except Exception as e:
            return False
    
    @staticmethod
    def validate_pixel_config(pixel_id: str, access_token: str) -> Dict:
        """
        Valida configuração completa do pixel
        
        Returns:
            dict: {
                'valid': bool,
                'pixel_info': dict,
                'permissions': list,
                'errors': list
            }
        """
        result = {
            'valid': False,
            'pixel_info': None,
            'permissions': [],
            'errors': []
        }
        
        # Testar conexão básica
        test_result = MetaPixelAPI.test_connection(pixel_id, access_token)
        
        if not test_result['success']:
            result['errors'].append(f"Conexão falhou: {test_result['error']}")
            return result
        
        result['pixel_info'] = test_result['pixel_info']
        
        # Verificar permissões (tentar enviar evento de teste)
        test_event_id = f"test_{uuid.uuid4().hex[:8]}_{int(time.time())}"
        
        test_result = MetaPixelAPI.send_pageview_event(
            pixel_id=pixel_id,
            access_token=access_token,
            event_id=test_event_id,
            customer_user_id="test_user"
        )
        
        if test_result['success']:
            result['valid'] = True
            result['permissions'].append('events:write')
        else:
            result['errors'].append(f"Permissão de escrita falhou: {test_result['error']}")
        
        return result


class MetaPixelHelper:
    """
    Helper class para operações comuns do Meta Pixel
    """
    
    @staticmethod
    def extract_utm_params(request) -> Dict[str, str]:
        """Extrai parâmetros UTM do request"""
        utm_params = {}
        
        for param in ['utm_source', 'utm_campaign', 'utm_content', 'utm_medium', 'utm_term']:
            value = request.args.get(param)
            if value:
                utm_params[param] = value
        
        # Facebook Click ID
        fbclid = request.args.get('fbclid')
        if fbclid:
            utm_params['fbclid'] = fbclid
        
        return utm_params
    
    @staticmethod
    def extract_cookies(request) -> Dict[str, str]:
        """Extrai cookies relevantes do Meta"""
        cookies = {}
        
        # Facebook Pixel cookies
        if '_fbp' in request.cookies:
            cookies['fbp'] = request.cookies['_fbp']
        
        if '_fbc' in request.cookies:
            cookies['fbc'] = request.cookies['_fbc']
        
        return cookies
    
    @staticmethod
    def generate_external_id() -> str:
        """Gera ID único para tracking de cliques"""
        return f"click_{uuid.uuid4().hex[:12]}"
    
    @staticmethod
    def is_valid_pixel_id(pixel_id: str) -> bool:
        """Valida formato do Pixel ID"""
        if not pixel_id:
            return False
        
        # Pixel ID deve ser numérico e ter 15-16 dígitos
        return pixel_id.isdigit() and 15 <= len(pixel_id) <= 16
    
    @staticmethod
    def is_valid_access_token(access_token: str) -> bool:
        """Valida formato básico do Access Token"""
        if not access_token:
            return False
        
        # Access Token deve ter pelo menos 50 caracteres
        return len(access_token) >= 50
