"""
User Data Builder — Meta CAPI
=============================
Normalização e hashing de PII conforme documentação Meta:
- em: SHA-256, lowercase, trimmed → NUNCA sintético
- ph: SHA-256, remove símbolos/letras, lstrip zeros, country code
- client_ip_address: RAW (NUNCA hash)
- client_user_agent: RAW (NUNCA hash)
- fbp: RAW
- fbc: RAW (só se real, não synthetic)
- external_id: SHA-256
"""

import hashlib
import re
import logging
from typing import Dict, Optional, Any

logger = logging.getLogger(__name__)


def sha256(data: str) -> str:
    """SHA-256 hex digest (padrão Meta CAPI)."""
    return hashlib.sha256(data.encode('utf-8')).hexdigest()


def normalize_email(email: Optional[str]) -> Optional[str]:
    """Normaliza email conforme Meta: trim + lowercase.

    Retorna None se vazio ou inválido.
    """
    if not email:
        return None
    return email.strip().lower()


def is_synthetic_email(email: Optional[str]) -> bool:
    """Email sintético (gerado pelo sistema) não serve para matching.

    O sistema gera emails como 'usuario@telegram.user' quando
    o lead não fornece email real. Meta não consegue match.
    """
    if not email:
        return True
    return any(
        domain in email.lower()
        for domain in ['@telegram.user', '@user.telegram', '@example.com']
    )


def normalize_phone(phone: Optional[str]) -> Optional[str]:
    """Normaliza telefone conforme Meta.

    - Remove símbolos e letras
    - Remove zeros à esquerda
    - Adiciona country code 55 (Brasil) se ausente
    - Retorna None se vazio após limpeza
    """
    if not phone:
        return None
    phone = re.sub(r'[^\d]', '', phone)
    if not phone:
        return None
    phone = phone.lstrip('0')
    if not phone.startswith('55'):
        phone = '55' + phone
    return phone


def build_user_data(
    payment,
    bot_user,
    tracking_data: Optional[Dict] = None
) -> Dict[str, Any]:
    """Constrói dicionário user_data para Meta CAPI.

    Regras:
    - em (email): só inclui se NÃO for sintético
    - ph (phone): só inclui se existir e for válido
    - client_ip_address: RAW (nunca hash), fallback tracking_data
    - client_user_agent: RAW, fallback tracking_data
    - fbp: RAW do Payment ou BotUser
    - fbc: RAW, só se origem REAL (não synthetic)
    - external_id: SHA-256 do fbclid
    """
    user_data: Dict[str, Any] = {}

    # ── EMAIL (em) ──────────────────────────────────────────
    email_raw = normalize_email(getattr(payment, 'customer_email', None))
    if email_raw and not is_synthetic_email(email_raw):
        user_data['em'] = [sha256(email_raw)]

    # ── PHONE (ph) ──────────────────────────────────────────
    phone_raw = normalize_phone(getattr(payment, 'customer_phone', None))
    if phone_raw:
        user_data['ph'] = [sha256(phone_raw)]

    # ── CLIENT IP (RAW, NUNCA hash) ─────────────────────────
    ip = None
    if bot_user and getattr(bot_user, 'ip_address', None):
        ip = bot_user.ip_address
    if not ip and tracking_data:
        ip = tracking_data.get('client_ip')
    if ip:
        user_data['client_ip_address'] = ip

    # ── USER AGENT (RAW, NUNCA hash) ────────────────────────
    # Meta: REQUIRED para website events
    ua = None
    if bot_user and getattr(bot_user, 'user_agent', None):
        ua = bot_user.user_agent
    if not ua and tracking_data:
        ua = tracking_data.get('client_user_agent')
    if ua:
        user_data['client_user_agent'] = ua

    # ── FBP (RAW) ───────────────────────────────────────────
    fbp = getattr(payment, 'fbp', None)
    if not fbp and bot_user:
        fbp = getattr(bot_user, 'fbp', None)
    if fbp:
        user_data['fbp'] = fbp

    # ── FBC (RAW, só se REAL) ──────────────────────────────
    fbc = getattr(payment, 'fbc', None)
    if not fbc and bot_user:
        fbc = getattr(bot_user, 'fbc', None)
    fbc_origin = (tracking_data or {}).get('fbc_origin')
    if fbc and fbc_origin != 'synthetic':
        user_data['fbc'] = fbc

    # ── EXTERNAL_ID (SHA-256) ──────────────────────────────
    fbclid = getattr(payment, 'fbclid', None)
    if not fbclid and bot_user:
        fbclid = getattr(bot_user, 'fbclid', None)
    if fbclid:
        user_data['external_id'] = [sha256(str(fbclid))]

    # ── DEMOGRAPHIC DATA ───────────────────────────────────
    if payment:
        if getattr(payment, 'customer_city', None):
            user_data['ct'] = payment.customer_city
        if getattr(payment, 'customer_state', None):
            user_data['st'] = payment.customer_state
        if getattr(payment, 'customer_country', None):
            user_data['country'] = payment.customer_country
        if getattr(payment, 'customer_gender', None):
            user_data['ge'] = payment.customer_gender

    # Fallback para BotUser se Payment não tiver
    if bot_user:
        if 'ct' not in user_data and getattr(bot_user, 'customer_city', None):
            user_data['ct'] = bot_user.customer_city
        if 'st' not in user_data and getattr(bot_user, 'customer_state', None):
            user_data['st'] = bot_user.customer_state
        if 'country' not in user_data and getattr(bot_user, 'customer_country', None):
            user_data['country'] = bot_user.customer_country
        if 'ge' not in user_data and getattr(bot_user, 'customer_gender', None):
            user_data['ge'] = bot_user.customer_gender

    return user_data
