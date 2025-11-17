"""
Tracking Service V4 - Universal e Definitivo
Sistema robusto de tracking para Meta Pixel com alta Match Quality (8-10/10)

Características V4:
- Tracking Token único por transação
- Recuperação multi-estratégia de fbp/fbc
- TTL de 30 dias (persistência)
- external_id imutável e ordenado
- Consistência total entre PageView e Purchase
- Compatibilidade com versão QI 300 (métodos estáticos mantidos)
"""

import os
import json
import logging
import random
import uuid
from datetime import datetime
from typing import Dict, Optional

import redis

logger = logging.getLogger(__name__)

REDIS_URL = os.environ.get("REDIS_URL", "redis://localhost:6379/0")
TRACKING_TOKEN_TTL_SECONDS = int(os.environ.get("TRACKING_TOKEN_TTL_SECONDS", 24 * 3600))


def _redis_client(decode_responses: bool = True) -> redis.Redis:
    return redis.from_url(REDIS_URL, decode_responses=decode_responses)


class TrackingServiceV4:
    """Persistência resiliente de tracking tokens com compatibilidade legada."""

    TRACKING_TOKEN_TTL_SECONDS = TRACKING_TOKEN_TTL_SECONDS

    def __init__(self) -> None:
        self.redis = _redis_client(decode_responses=True)

    def _key(self, token: str) -> str:
        return f"tracking:{token}"

    def _legacy_key(self, token: str) -> str:
        return f"tracking:token:{token}"

    def generate_tracking_token(
        self,
        bot_id: int,
        customer_user_id: str,
        payment_id: Optional[int] = None,
        fbclid: Optional[str] = None,
        utm_source: Optional[str] = None,
        utm_medium: Optional[str] = None,
        utm_campaign: Optional[str] = None,
    ) -> str:
        """
        ⚠️ DEPRECATED - NÃO USAR!
        
        Este método NÃO DEVE ser usado para gerar tracking_token.
        tracking_token DEVE ser criado APENAS em /go/{slug} (public_redirect).
        
        Se você está chamando este método, há um BUG no seu código.
        
        RAZÃO: tracking_token gerado aqui NÃO tem dados do redirect (client_ip, client_user_agent, pageview_event_id).
        Isso quebra o fluxo PageView → ViewContent → Purchase e impede Meta de atribuir vendas.
        """
        import traceback
        logger.error(f"❌ [DEPRECATED] generate_tracking_token() foi chamado - ISSO É UM BUG!")
        logger.error(f"   tracking_token DEVE ser criado APENAS em /go/{{slug}} (public_redirect)")
        logger.error(f"   Stack trace: {''.join(traceback.format_stack()[-5:-1])}")
        logger.error(f"   Parâmetros: bot_id={bot_id}, customer_user_id={customer_user_id}, payment_id={payment_id}")
        
        # ✅ Lançar exceção para forçar correção do bug
        raise DeprecationWarning(
            "generate_tracking_token() está DEPRECATED. "
            "tracking_token deve ser criado APENAS em /go/{slug} (public_redirect). "
            "Se você está chamando este método, há um BUG no seu código. "
            "SOLUÇÃO: Usar tracking_token do bot_user.tracking_session_id (vem do redirect)."
        )

    def generate_fbp(self, telegram_user_id: str) -> str:
        """
        Gera _fbp cookie conforme documentação Meta (TrackingServiceV4):
        Formato: fb.{subdomainIndex}.{creationTime}.{randomNumber}
        - subdomainIndex: 1 (para app.grimbots.online)
        - creationTime: tempo UNIX em MILISSEGUNDOS (não segundos!)
        - randomNumber: hash do telegram_user_id (garante unicidade)
        """
        import time
        timestamp = int(time.time() * 1000)  # ✅ CRÍTICO: MILISSEGUNDOS (não segundos!)
        random_part = abs(hash(telegram_user_id)) % 10_000_000_000
        return f"fb.1.{timestamp}.{random_part}"

    def generate_fbc(self, fbclid: Optional[str]) -> Optional[str]:
        return TrackingService.generate_fbc(fbclid)

    def build_external_id_array(
        self,
        fbclid: Optional[str] = None,
        telegram_user_id: Optional[str] = None,
        email: Optional[str] = None,
        phone: Optional[str] = None,
    ) -> list[str]:
        external_ids: list[str] = []
        if fbclid:
            external_ids.append(self._hash_data(fbclid))
        if telegram_user_id:
            external_ids.append(self._hash_data(str(telegram_user_id)))
        if email:
            external_ids.append(self._hash_data(email.lower().strip()))
        if phone:
            digits = "".join(filter(str.isdigit, phone))
            if digits:
                external_ids.append(self._hash_data(digits))
        return external_ids

    def _hash_data(self, value: str) -> str:
        import hashlib

        return hashlib.sha256(value.encode()).hexdigest()

    def save_tracking_token(self, tracking_token: str, payload: Dict, ttl: Optional[int] = None) -> bool:
        if not tracking_token:
            logger.warning("save_tracking_token chamado com token vazio")
            return False

        ttl = ttl or TRACKING_TOKEN_TTL_SECONDS
        key = self._key(tracking_token)
        legacy = self._legacy_key(tracking_token)

        try:
            current = self.redis.get(key)
            if current:
                try:
                    previous = json.loads(current)
                    if isinstance(previous, dict):
                        # ✅ CRÍTICO: Preservar pageview_event_id do payload anterior se o novo não tiver ou for None/vazio
                        preserved_pageview_event_id = previous.get('pageview_event_id')
                        new_pageview_event_id = payload.get('pageview_event_id')
                        if preserved_pageview_event_id and (not new_pageview_event_id or new_pageview_event_id == 'None' or new_pageview_event_id == ''):
                            payload['pageview_event_id'] = preserved_pageview_event_id
                            logger.debug(f"✅ Preservando pageview_event_id do payload anterior: {preserved_pageview_event_id}")
                        # ✅ CRÍTICO: Não sobrescrever pageview_event_id se o novo payload não tiver um valor válido
                        elif preserved_pageview_event_id and new_pageview_event_id:
                            # Se ambos têm valor, usar o novo (mais recente)
                            logger.debug(f"✅ Usando pageview_event_id do novo payload: {new_pageview_event_id}")
                        
                        # ✅ CRÍTICO V4.1: Preservar fbc APENAS se fbc_origin = 'cookie' (fbc real)
                        # Se novo payload tem fbc com fbc_origin = 'cookie', usar (substituir qualquer fbc anterior)
                        # Se novo payload não tem fbc mas anterior tem fbc com fbc_origin = 'cookie', preservar
                        # Se anterior tem fbc_origin = 'synthetic', NÃO preservar (ignorar fbc sintético)
                        preserved_fbc = previous.get('fbc')
                        preserved_fbc_origin = previous.get('fbc_origin')
                        new_fbc = payload.get('fbc')
                        new_fbc_origin = payload.get('fbc_origin')
                        
                        # ✅ PRIORIDADE 1: Novo payload tem fbc REAL (cookie) → usar
                        if new_fbc and new_fbc_origin == 'cookie':
                            # Manter fbc do novo payload (é real)
                            logger.debug(f"✅ Usando fbc REAL do novo payload: {new_fbc[:50]}...")
                        # ✅ PRIORIDADE 2: Novo não tem fbc, mas anterior tem fbc REAL → preservar
                        elif preserved_fbc and preserved_fbc_origin == 'cookie' and (not new_fbc or new_fbc_origin != 'cookie'):
                            payload['fbc'] = preserved_fbc
                            payload['fbc_origin'] = 'cookie'  # Preservar origem também
                            logger.debug(f"✅ Preservando fbc REAL do payload anterior: {preserved_fbc[:50]}...")
                        # ✅ PRIORIDADE 3: Novo não tem fbc e anterior não tem fbc real → deixar None
                        else:
                            # Não preservar fbc sintético ou ausente
                            if preserved_fbc_origin == 'synthetic':
                                logger.debug(f"⚠️ Ignorando fbc sintético do payload anterior (não será preservado)")
                            payload['fbc'] = None
                            payload['fbc_origin'] = None
                        
                        # ✅ CORREÇÃO V4.1: Não sobrescrever com None
                        for key, value in payload.items():
                            if value is not None:  # ✅ Só atualizar se não for None
                                previous[key] = value
                            # Se value é None, manter valor anterior (se existir)
                        payload = previous
                except Exception:
                    logger.exception("Falha ao mesclar payload existente; substituindo")

            payload["tracking_token"] = tracking_token
            now_iso = datetime.utcnow().isoformat()
            payload.setdefault("created_at", now_iso)
            payload["updated_at"] = now_iso

            json_payload = json.dumps(payload, ensure_ascii=False)
            self.redis.setex(key, ttl, json_payload)
            self.redis.setex(legacy, ttl, json_payload)

            fbclid = payload.get("fbclid")
            if fbclid:
                # ✅ CORREÇÃO CRÍTICA V16: Validar tracking_token ANTES de salvar em tracking:fbclid
                is_generated_token = tracking_token.startswith('tracking_')
                is_uuid_token = len(tracking_token) == 32 and all(c in '0123456789abcdef' for c in tracking_token.lower())
                
                if is_generated_token:
                    logger.error(f"❌ [TRACKING SERVICE] tracking_token é GERADO: {tracking_token[:30]}... - NÃO salvar em tracking:fbclid")
                    logger.error(f"   Token gerado não tem dados do redirect (client_ip, client_user_agent, pageview_event_id)")
                    # ✅ NÃO salvar token gerado em tracking:fbclid
                elif is_uuid_token:
                    # ✅ Token válido - pode salvar
                    try:
                        self.redis.setex(f"tracking:fbclid:{fbclid}", ttl, tracking_token)
                    except Exception:
                        logger.exception("Nao foi possivel indexar fbclid")
                else:
                    logger.warning(f"⚠️ [TRACKING SERVICE] tracking_token tem formato inválido: {tracking_token[:30]}... (len={len(tracking_token)}) - NÃO salvar em tracking:fbclid")

            customer_user_id = payload.get("customer_user_id")
            if customer_user_id:
                # ✅ CORREÇÃO CRÍTICA V16: Validar tracking_token ANTES de salvar em tracking:chat e tracking:last_token
                is_generated_token = tracking_token.startswith('tracking_')
                is_uuid_token = len(tracking_token) == 32 and all(c in '0123456789abcdef' for c in tracking_token.lower())
                
                if is_generated_token:
                    logger.error(f"❌ [TRACKING SERVICE] tracking_token é GERADO: {tracking_token[:30]}... - NÃO salvar em tracking:chat/tracking:last_token")
                    logger.error(f"   Token gerado não tem dados do redirect (client_ip, client_user_agent, pageview_event_id)")
                    # ✅ NÃO salvar token gerado em tracking:chat ou tracking:last_token
                elif is_uuid_token:
                    # ✅ Token válido - pode salvar
                    chat_key = f"tracking:chat:{customer_user_id}"
                    try:
                        chat_payload = payload.copy()
                        existing_chat = self.redis.get(chat_key)
                        if existing_chat:
                            try:
                                existing_data = json.loads(existing_chat)
                                if isinstance(existing_data, dict):
                                    existing_data.update(chat_payload)
                                    chat_payload = existing_data
                            except Exception:
                                logger.exception("Falha ao mesclar registro tracking:chat existente")
                        chat_payload["tracking_token"] = tracking_token
                        chat_payload_json = json.dumps(chat_payload, ensure_ascii=False)
                        self.redis.setex(chat_key, ttl, chat_payload_json)
                    except Exception:
                        logger.exception("Falha ao indexar tracking por chat_id")
                    try:
                        self.redis.setex(f"tracking:last_token:user:{customer_user_id}", ttl, tracking_token)
                    except Exception:
                        logger.exception("Falha ao indexar tracking last token por usuario")
                else:
                    logger.warning(f"⚠️ [TRACKING SERVICE] tracking_token tem formato inválido: {tracking_token[:30]}... (len={len(tracking_token)}) - NÃO salvar em tracking:chat/tracking:last_token")

            payment_id = payload.get("payment_id")
            if payment_id:
                try:
                    self.redis.setex(f"tracking:payment:{payment_id}", ttl, json_payload)
                except Exception:
                    logger.exception("Falha ao indexar tracking por payment_id")

            return True
        except Exception:
            logger.exception("Falha ao salvar tracking_token no Redis")
            return False
    
    def recover_tracking_data(self, tracking_token: str) -> Dict:
        if not tracking_token:
            return {}

        try:
            key = self._key(tracking_token)
            legacy = self._legacy_key(tracking_token)

            raw = self.redis.get(key)
            if not raw:
                raw = self.redis.get(legacy)

            if raw:
                try:
                    return json.loads(raw)
                except Exception:
                    logger.exception("Falha ao desserializar tracking payload")
                    return {}

            return {}
        except Exception:
            logger.exception("Erro ao recuperar tracking_token do Redis")
            return {}

    def save_tracking_data(
        self,
        tracking_token: str,
        bot_id: int,
        customer_user_id: str,
        payment_id: Optional[int] = None,
        fbclid: Optional[str] = None,
        fbp: Optional[str] = None,
        fbc: Optional[str] = None,
        utm_source: Optional[str] = None,
        utm_medium: Optional[str] = None,
        utm_campaign: Optional[str] = None,
        external_ids: Optional[list[str]] = None,
    ) -> bool:
        payload = {
            "tracking_token": tracking_token,
            "bot_id": bot_id,
            "customer_user_id": customer_user_id,
            "payment_id": payment_id,
            "fbclid": fbclid,
            "fbp": fbp,
            "fbc": fbc,
            "utm_source": utm_source,
            "utm_medium": utm_medium,
            "utm_campaign": utm_campaign,
            "external_ids": external_ids or [],
        }
        now_iso = datetime.utcnow().isoformat()
        payload.setdefault("created_at", now_iso)
        payload["updated_at"] = now_iso
        compact = {k: v for k, v in payload.items() if v not in (None, "", [])}
        ok = self.save_tracking_token(tracking_token, compact)
        if not ok:
            return False

        ttl = TRACKING_TOKEN_TTL_SECONDS
        try:
            if payment_id:
                self.redis.setex(
                    f"tracking:payment:{payment_id}",
                    ttl,
                    json.dumps(compact, ensure_ascii=False)
                )
        except Exception:
            logger.exception("Falha ao indexar tracking por payment_id")
        return True


class TrackingService:
    """Compat layer para utilitários legados de tracking."""

    TTL_DAYS = 30

    @staticmethod
    def generate_fbp() -> str:
        """
        Gera _fbp cookie conforme documentação Meta:
        Formato: fb.{subdomainIndex}.{creationTime}.{randomNumber}
        - subdomainIndex: 1 (para app.grimbots.online)
        - creationTime: tempo UNIX em MILISSEGUNDOS (não segundos!)
        - randomNumber: número aleatório de 10 dígitos
        """
        import time
        timestamp = int(time.time() * 1000)  # ✅ CRÍTICO: MILISSEGUNDOS (não segundos!)
        random_part = random.randint(1000000000, 9999999999)
        return f"fb.1.{timestamp}.{random_part}"

    @staticmethod
    def generate_fbc(fbclid: Optional[str]) -> Optional[str]:
        """
        Gera _fbc cookie conforme documentação Meta:
        Formato: fb.{subdomainIndex}.{creationTime}.{fbclid}
        - subdomainIndex: 1 (para app.grimbots.online)
        - creationTime: tempo UNIX em MILISSEGUNDOS (não segundos!)
        - fbclid: valor do parâmetro fbclid da URL (case-sensitive, não alterar)
        
        IMPORTANTE: Meta recomenda usar o valor do cookie _fbc do browser quando disponível.
        Este método deve ser usado apenas quando o cookie não existe e temos fbclid da URL.
        """
        if not fbclid:
            return None
        import time
        timestamp = int(time.time() * 1000)  # ✅ CRÍTICO: MILISSEGUNDOS (não segundos!)
        return f"fb.1.{timestamp}.{fbclid}"

    @staticmethod
    def save_tracking_data(
        fbclid: Optional[str] = None,
        fbp: Optional[str] = None,
        fbc: Optional[str] = None,
        ip_address: Optional[str] = None,
        user_agent: Optional[str] = None,
        grim: Optional[str] = None,
        telegram_user_id: Optional[str] = None,
        utms: Optional[Dict[str, str]] = None
    ) -> bool:
        redis_client = _redis_client(decode_responses=True)
        ttl = TrackingService.TTL_DAYS * 24 * 3600
        payload = {
            "fbclid": fbclid,
            "fbp": fbp or "",
            "fbc": fbc or "",
            "ip": ip_address or "",
            "ua": user_agent or "",
            "grim": grim or "",
            "telegram_user_id": telegram_user_id or "",
            "utms": utms or {},
            "timestamp": int(datetime.utcnow().timestamp()),
        }
        try:
            if fbclid:
                redis_client.setex(f"tracking:fbclid:{fbclid}", ttl, json.dumps(payload, ensure_ascii=False))
            if telegram_user_id:
                redis_client.setex(f"tracking:chat:{telegram_user_id}", ttl, json.dumps(payload, ensure_ascii=False))
            if grim:
                redis_client.setex(f"tracking_grim:{grim}", ttl, json.dumps(payload, ensure_ascii=False))
            return True
        except Exception:
            logger.exception("Erro ao salvar tracking legacy")
            return False

    @staticmethod
    def recover_tracking_data(
        fbclid: Optional[str] = None,
        telegram_user_id: Optional[str] = None,
        grim: Optional[str] = None
    ) -> Optional[Dict[str, str]]:
        redis_client = _redis_client(decode_responses=True)
        try:
            if fbclid:
                data = redis_client.get(f"tracking:fbclid:{fbclid}")
                if data:
                    return json.loads(data)
            if telegram_user_id:
                data = redis_client.get(f"tracking:chat:{telegram_user_id}")
                if data:
                    return json.loads(data)
            if grim:
                data = redis_client.get(f"tracking_grim:{grim}")
                if data:
                    return json.loads(data)
        except Exception:
            logger.exception("Erro ao recuperar tracking legacy")
        return None

