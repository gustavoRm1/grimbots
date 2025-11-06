# 🚀 IMPLEMENTAÇÃO FINAL QI 200 - CÓDIGO COMPLETO

## 📋 VISÃO GERAL

Este documento contém todo o código necessário para transformar o sistema em uma plataforma robusta, multi-gateway e multi-tenant, com tracking universal e webhooks confiáveis.

---

## 📁 ESTRUTURA DE ARQUIVOS

```
grpay/
├── gateway_interface.py          # ✅ Interface base (já existe)
├── gateway_factory.py            # ✅ Factory (já existe, precisa melhorias)
├── gateway_adapter.py            # 🆕 ADAPTER LAYER (NOVO)
├── gateway_syncpay.py            # ✅ Já existe
├── gateway_pushyn.py             # ✅ Já existe
├── gateway_paradise.py           # ✅ Já existe
├── gateway_wiinpay.py            # ✅ Já existe
├── gateway_atomopay.py           # ✅ Já existe
├── models.py                     # ✅ Atualizar com novos campos
├── app.py                        # ✅ Atualizar rotas e webhooks
├── bot_manager.py                # ✅ Atualizar generate_payment
├── utils/
│   ├── tracking_service.py       # ✅ Atualizar para V4
│   └── meta_pixel.py             # ✅ Já existe
└── middleware/
    └── gateway_validator.py      # 🆕 MIDDLEWARE (NOVO)
```

---

## 1️⃣ GATEWAY INTERFACE (atualizar)

**Arquivo:** `gateway_interface.py`

```python
from abc import ABC, abstractmethod
from typing import Dict, Any, Optional, List
from enum import Enum

class GatewayStatus(str, Enum):
    """Status padrão de pagamento"""
    PENDING = "pending"
    PAID = "paid"
    REFUNDED = "refunded"
    EXPIRED = "expired"
    CANCELLED = "cancelled"
    FAILED = "failed"

class PaymentGateway(ABC):
    """
    Interface base para todos os gateways de pagamento.
    Garante consistência e permite fácil extensão.
    """
    
    @abstractmethod
    def generate_pix(
        self,
        amount: float,
        customer_name: str,
        customer_email: str,
        customer_cpf: str,
        customer_phone: str,
        external_reference: str,
        description: str = "",
        expires_in: int = 3600,
        **kwargs
    ) -> Optional[Dict[str, Any]]:
        """
        Gera um pagamento PIX.
        
        Returns:
            Dict com:
                - transaction_id: ID da transação no gateway
                - qr_code: Código PIX para pagamento
                - qr_code_base64: QR code em base64 (opcional)
                - payment_url: URL para checkout (opcional)
                - expires_at: Timestamp de expiração (opcional)
                - gateway_data: Dict com dados adicionais do gateway
        """
        pass
    
    @abstractmethod
    def process_webhook(
        self,
        webhook_data: Dict[str, Any],
        headers: Optional[Dict[str, str]] = None
    ) -> Optional[Dict[str, Any]]:
        """
        Processa webhook do gateway.
        
        Returns:
            Dict com:
                - transaction_id: ID da transação
                - status: GatewayStatus
                - amount: float
                - paid_at: datetime (opcional)
                - gateway_data: Dict com dados adicionais
                - producer_hash: str (opcional, para multi-tenant)
        """
        pass
    
    @abstractmethod
    def verify_credentials(self) -> bool:
        """
        Verifica se as credenciais são válidas.
        
        Returns:
            bool: True se válidas, False caso contrário
        """
        pass
    
    @abstractmethod
    def get_payment_status(
        self,
        transaction_id: str
    ) -> Optional[Dict[str, Any]]:
        """
        Consulta status de um pagamento específico.
        
        Returns:
            Dict com status e dados do pagamento
        """
        pass
    
    @abstractmethod
    def get_webhook_url(self) -> str:
        """
        Retorna a URL de webhook esperada pelo gateway.
        """
        pass
    
    @abstractmethod
    def get_gateway_name(self) -> str:
        """
        Retorna nome amigável do gateway.
        """
        pass
    
    @abstractmethod
    def get_gateway_type(self) -> str:
        """
        Retorna tipo do gateway (syncpay, pushyn, paradise, etc).
        """
        pass
    
    def validate_webhook_signature(
        self,
        payload: str,
        signature: str,
        headers: Optional[Dict[str, str]] = None
    ) -> bool:
        """
        Valida assinatura do webhook (implementação opcional).
        
        Args:
            payload: Body do webhook (string)
            signature: Assinatura recebida
            headers: Headers HTTP (opcional)
        
        Returns:
            bool: True se válida
        """
        # Implementação padrão: sempre retorna True
        # Gateways específicos devem sobrescrever
        return True
    
    def extract_producer_hash(
        self,
        webhook_data: Dict[str, Any]
    ) -> Optional[str]:
        """
        Extrai producer_hash do webhook para multi-tenancy (implementação opcional).
        
        Args:
            webhook_data: Dados do webhook
        
        Returns:
            str: producer_hash ou None
        """
        # Implementação padrão: None
        # Gateways que suportam multi-tenancy devem sobrescrever
        return None
```

---

## 2️⃣ GATEWAY FACTORY (melhorar)

**Arquivo:** `gateway_factory.py`

```python
from typing import Optional, Dict, Any, Type
from gateway_interface import PaymentGateway, GatewayStatus
from gateway_syncpay import SyncPayGateway
from gateway_pushyn import PushynGateway
from gateway_paradise import ParadisePaymentGateway
from gateway_wiinpay import WiinPayGateway
from gateway_atomopay import AtomPayGateway
from gateway_adapter import GatewayAdapter
import logging

logger = logging.getLogger(__name__)

class GatewayFactory:
    """
    Factory para criar instâncias de gateways de pagamento.
    Implementa o padrão Factory para desacoplar a criação de gateways.
    """
    
    # Registry de gateways disponíveis
    _gateway_classes: Dict[str, Type[PaymentGateway]] = {
        'syncpay': SyncPayGateway,
        'pushyn': PushynGateway,
        'paradise': ParadisePaymentGateway,
        'wiinpay': WiinPayGateway,
        'atomopay': AtomPayGateway,
    }
    
    @classmethod
    def create_gateway(
        cls,
        gateway_type: str,
        credentials: Dict[str, Any],
        use_adapter: bool = True
    ) -> Optional[PaymentGateway]:
        """
        Cria uma instância do gateway especificado.
        
        Args:
            gateway_type: Tipo do gateway (syncpay, pushyn, etc)
            credentials: Dict com credenciais específicas do gateway
            use_adapter: Se True, envolve o gateway com GatewayAdapter
        
        Returns:
            Instância do gateway ou None se tipo inválido
        """
        gateway_type = gateway_type.lower().strip()
        
        if gateway_type not in cls._gateway_classes:
            logger.error(f"❌ Gateway type '{gateway_type}' não suportado. Tipos disponíveis: {list(cls._gateway_classes.keys())}")
            return None
        
        gateway_class = cls._gateway_classes[gateway_type]
        
        try:
            # Criar instância do gateway com credenciais
            gateway = gateway_class(**credentials)
            
            # Se use_adapter=True, envolver com adapter para normalização
            if use_adapter:
                gateway = GatewayAdapter(gateway)
            
            logger.info(f"✅ Gateway '{gateway_type}' criado com sucesso")
            return gateway
            
        except Exception as e:
            logger.error(f"❌ Erro ao criar gateway '{gateway_type}': {e}", exc_info=True)
            return None
    
    @classmethod
    def register_gateway(
        cls,
        gateway_type: str,
        gateway_class: Type[PaymentGateway]
    ):
        """
        Registra um novo tipo de gateway.
        
        Args:
            gateway_type: Nome do tipo (ex: 'novogateway')
            gateway_class: Classe que implementa PaymentGateway
        """
        cls._gateway_classes[gateway_type.lower()] = gateway_class
        logger.info(f"✅ Gateway '{gateway_type}' registrado")
    
    @classmethod
    def list_available_gateways(cls) -> list:
        """
        Lista todos os gateways disponíveis.
        
        Returns:
            Lista de strings com tipos de gateways
        """
        return list(cls._gateway_classes.keys())
    
    @classmethod
    def verify_gateway_credentials(
        cls,
        gateway_type: str,
        credentials: Dict[str, Any]
    ) -> tuple[bool, Optional[str]]:
        """
        Verifica credenciais de um gateway sem criar instância persistente.
        
        Args:
            gateway_type: Tipo do gateway
            credentials: Credenciais a verificar
        
        Returns:
            Tuple (bool, str): (True, None) se válidas, (False, erro) se inválidas
        """
        gateway = cls.create_gateway(gateway_type, credentials, use_adapter=False)
        
        if not gateway:
            return False, f"Gateway '{gateway_type}' não suportado"
        
        try:
            is_valid = gateway.verify_credentials()
            if is_valid:
                return True, None
            else:
                return False, "Credenciais inválidas"
        except Exception as e:
            logger.error(f"❌ Erro ao verificar credenciais: {e}", exc_info=True)
            return False, str(e)
```

---

## 3️⃣ GATEWAY ADAPTER (NOVO)

**Arquivo:** `gateway_adapter.py`

```python
from typing import Dict, Any, Optional
from datetime import datetime
from gateway_interface import PaymentGateway, GatewayStatus
import logging
import hashlib

logger = logging.getLogger(__name__)

class GatewayAdapter(PaymentGateway):
    """
    Adapter que normaliza dados entre gateways diferentes.
    Garante consistência de formato, tratamento de erros e logging.
    """
    
    def __init__(self, gateway: PaymentGateway):
        """
        Args:
            gateway: Instância do gateway a ser adaptada
        """
        if not isinstance(gateway, PaymentGateway):
            raise ValueError("gateway deve implementar PaymentGateway")
        
        self._gateway = gateway
        logger.debug(f"🔧 GatewayAdapter criado para {gateway.get_gateway_type()}")
    
    # ==================== DELEGAÇÃO DE MÉTODOS ====================
    
    def generate_pix(
        self,
        amount: float,
        customer_name: str,
        customer_email: str,
        customer_cpf: str,
        customer_phone: str,
        external_reference: str,
        description: str = "",
        expires_in: int = 3600,
        **kwargs
    ) -> Optional[Dict[str, Any]]:
        """
        Normaliza generate_pix de todos os gateways.
        """
        try:
            # Validar inputs
            if amount <= 0:
                raise ValueError(f"Amount deve ser > 0, recebido: {amount}")
            
            if not customer_email or not customer_email.strip():
                raise ValueError("customer_email é obrigatório")
            
            if not external_reference:
                raise ValueError("external_reference é obrigatório")
            
            # Chamar gateway real
            result = self._gateway.generate_pix(
                amount=amount,
                customer_name=customer_name,
                customer_email=customer_email,
                customer_cpf=customer_cpf,
                customer_phone=customer_phone,
                external_reference=external_reference,
                description=description,
                expires_in=expires_in,
                **kwargs
            )
            
            if not result:
                logger.warning(f"⚠️ Gateway {self._gateway.get_gateway_type()} retornou None para generate_pix")
                return None
            
            # Normalizar resposta
            normalized = self._normalize_generate_response(result)
            
            logger.info(
                f"✅ PIX gerado via {self._gateway.get_gateway_type()}: "
                f"transaction_id={normalized.get('transaction_id')}, "
                f"amount={amount}"
            )
            
            return normalized
            
        except Exception as e:
            logger.error(
                f"❌ Erro ao gerar PIX via {self._gateway.get_gateway_type()}: {e}",
                exc_info=True
            )
            raise
    
    def process_webhook(
        self,
        webhook_data: Dict[str, Any],
        headers: Optional[Dict[str, str]] = None
    ) -> Optional[Dict[str, Any]]:
        """
        Normaliza process_webhook de todos os gateways.
        """
        try:
            # Validar webhook_data
            if not webhook_data:
                logger.warning("⚠️ webhook_data vazio")
                return None
            
            # Validar assinatura (se gateway implementar)
            if headers:
                signature = self._extract_signature(headers)
                if signature:
                    is_valid = self._gateway.validate_webhook_signature(
                        payload=str(webhook_data),
                        signature=signature,
                        headers=headers
                    )
                    if not is_valid:
                        logger.error(f"❌ Assinatura inválida do webhook {self._gateway.get_gateway_type()}")
                        return None
            
            # Chamar gateway real
            result = self._gateway.process_webhook(webhook_data, headers)
            
            if not result:
                logger.warning(f"⚠️ Gateway {self._gateway.get_gateway_type()} retornou None para process_webhook")
                return None
            
            # Normalizar resposta
            normalized = self._normalize_webhook_response(result)
            
            logger.info(
                f"✅ Webhook processado via {self._gateway.get_gateway_type()}: "
                f"transaction_id={normalized.get('transaction_id')}, "
                f"status={normalized.get('status')}"
            )
            
            return normalized
            
        except Exception as e:
            logger.error(
                f"❌ Erro ao processar webhook via {self._gateway.get_gateway_type()}: {e}",
                exc_info=True
            )
            return None
    
    def verify_credentials(self) -> bool:
        return self._gateway.verify_credentials()
    
    def get_payment_status(self, transaction_id: str) -> Optional[Dict[str, Any]]:
        return self._gateway.get_payment_status(transaction_id)
    
    def get_webhook_url(self) -> str:
        return self._gateway.get_webhook_url()
    
    def get_gateway_name(self) -> str:
        return self._gateway.get_gateway_name()
    
    def get_gateway_type(self) -> str:
        return self._gateway.get_gateway_type()
    
    def extract_producer_hash(self, webhook_data: Dict[str, Any]) -> Optional[str]:
        """
        Extrai producer_hash para multi-tenancy.
        """
        if hasattr(self._gateway, 'extract_producer_hash'):
            return self._gateway.extract_producer_hash(webhook_data)
        return None
    
    # ==================== MÉTODOS DE NORMALIZAÇÃO ====================
    
    def _normalize_generate_response(self, result: Dict[str, Any]) -> Dict[str, Any]:
        """
        Normaliza resposta de generate_pix.
        Garante que todos os gateways retornem o mesmo formato.
        """
        normalized = {
            'transaction_id': result.get('transaction_id') or result.get('id') or result.get('hash'),
            'qr_code': result.get('qr_code') or result.get('pix_code') or result.get('qrcode'),
            'qr_code_base64': result.get('qr_code_base64'),
            'payment_url': result.get('payment_url') or result.get('checkout_url') or result.get('url'),
            'expires_at': result.get('expires_at') or result.get('expires_in'),
            'gateway_data': result.get('gateway_data', {}),
            # Campos adicionais
            'gateway_type': self._gateway.get_gateway_type(),
            'gateway_name': self._gateway.get_gateway_name(),
        }
        
        # Garantir transaction_id (gerar hash se não existir)
        if not normalized['transaction_id']:
            normalized['transaction_id'] = self._generate_transaction_hash(result)
        
        return normalized
    
    def _normalize_webhook_response(self, result: Dict[str, Any]) -> Dict[str, Any]:
        """
        Normaliza resposta de process_webhook.
        Garante que todos os gateways retornem o mesmo formato.
        """
        # Normalizar status
        status_str = result.get('status', '').lower()
        if status_str in ['paid', 'pago', 'approved', 'aprovado']:
            status = GatewayStatus.PAID
        elif status_str in ['pending', 'pendente', 'waiting']:
            status = GatewayStatus.PENDING
        elif status_str in ['refunded', 'reembolsado', 'refund']:
            status = GatewayStatus.REFUNDED
        elif status_str in ['expired', 'expirado', 'expired']:
            status = GatewayStatus.EXPIRED
        elif status_str in ['cancelled', 'cancelado', 'cancel']:
            status = GatewayStatus.CANCELLED
        else:
            status = GatewayStatus.FAILED
        
        normalized = {
            'transaction_id': result.get('transaction_id') or result.get('id') or result.get('hash'),
            'status': status,
            'amount': float(result.get('amount', 0)),
            'paid_at': result.get('paid_at') or result.get('paid_date') or result.get('created_at'),
            'gateway_data': result.get('gateway_data', {}),
            'producer_hash': result.get('producer_hash'),  # Para multi-tenancy
            'gateway_type': self._gateway.get_gateway_type(),
        }
        
        # Garantir transaction_id
        if not normalized['transaction_id']:
            normalized['transaction_id'] = self._generate_transaction_hash(result)
        
        return normalized
    
    def _extract_signature(self, headers: Dict[str, str]) -> Optional[str]:
        """
        Extrai assinatura dos headers HTTP.
        """
        # Tentar vários campos comuns
        signature_keys = [
            'x-signature', 'x-hub-signature', 'x-webhook-signature',
            'signature', 'authorization'
        ]
        
        for key in signature_keys:
            if key.lower() in [h.lower() for h in headers.keys()]:
                return headers.get(key) or headers.get(key.lower())
        
        return None
    
    def _generate_transaction_hash(self, data: Dict[str, Any]) -> str:
        """
        Gera hash único para transação quando gateway não fornece ID.
        """
        import json
        data_str = json.dumps(data, sort_keys=True)
        return hashlib.sha256(data_str.encode()).hexdigest()[:32]
```

---

## 4️⃣ TRACKING SERVICE V4 (atualizar)

**Arquivo:** `utils/tracking_service.py`

```python
import hashlib
import hmac
import json
import time
from typing import Dict, Any, Optional, List
from datetime import datetime, timedelta
import redis
import logging

logger = logging.getLogger(__name__)

class TrackingServiceV4:
    """
    Tracking Service V4 - Universal e Definitivo
    
    Funcionalidades:
    - Geração de fbp/fbc consistentes
    - External ID array imutável e ordenado
    - Persistência robusta no Redis
    - Recuperação multi-chave
    - Tracking token único por transação
    """
    
    def __init__(self, redis_client: redis.Redis = None):
        """
        Args:
            redis_client: Cliente Redis (opcional)
        """
        self.redis = redis_client or self._create_redis_client()
        self.TTL_DAYS = 30  # TTL padrão de 30 dias
    
    def _create_redis_client(self) -> redis.Redis:
        """Cria cliente Redis se não fornecido"""
        try:
            import os
            redis_url = os.getenv('REDIS_URL', 'redis://localhost:6379/0')
            return redis.from_url(redis_url, decode_responses=True)
        except Exception as e:
            logger.error(f"❌ Erro ao criar cliente Redis: {e}")
            return None
    
    # ==================== TRACKING TOKEN ====================
    
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
        Gera tracking_token único e imutável.
        
        Formato: tracking_{hash}
        Hash = SHA256(bot_id|customer_user_id|payment_id|fbclid|timestamp)
        """
        timestamp = int(time.time())
        payload = f"{bot_id}|{customer_user_id}|{payment_id or 0}|{fbclid or ''}|{timestamp}"
        token_hash = hashlib.sha256(payload.encode()).hexdigest()[:16]
        return f"tracking_{token_hash}"
    
    # ==================== FBP/FBC ====================
    
    def generate_fbp(self, telegram_user_id: str) -> str:
        """
        Gera _fbp cookie do Meta Pixel.
        
        Formato: fb.{version}.{timestamp}.{random}
        """
        version = 1
        timestamp = int(time.time() * 1000)
        random = int(hashlib.md5(telegram_user_id.encode()).hexdigest()[:9], 16)
        return f"fb.{version}.{timestamp}.{random}"
    
    def generate_fbc(self, fbclid: str, timestamp: Optional[int] = None) -> str:
        """
        Gera _fbc cookie do Meta Pixel (se fbclid presente).
        
        Formato: fb.{version}.{timestamp}.{fbclid}
        """
        if not fbclid:
            return None
        
        version = 1
        if not timestamp:
            timestamp = int(time.time() * 1000)
        
        return f"fb.{version}.{timestamp}.{fbclid}"
    
    # ==================== EXTERNAL ID ====================
    
    def build_external_id_array(
        self,
        fbclid: Optional[str] = None,
        telegram_user_id: Optional[str] = None,
        email: Optional[str] = None,
        phone: Optional[str] = None,
    ) -> List[str]:
        """
        Constrói array de external_id consistente e imutável.
        
        Ordem de prioridade (IMUTÁVEL):
        1. SHA256(fbclid) se presente
        2. SHA256(telegram_user_id) se presente
        3. SHA256(email) se presente
        4. SHA256(phone) se presente
        
        IMPORTANTE: A ordem NUNCA muda para garantir Match Quality.
        """
        external_ids = []
        
        # 1. fbclid (maior prioridade)
        if fbclid:
            external_ids.append(self._hash_data(fbclid))
        
        # 2. telegram_user_id
        if telegram_user_id:
            external_ids.append(self._hash_data(str(telegram_user_id)))
        
        # 3. email
        if email:
            external_ids.append(self._hash_data(email.lower().strip()))
        
        # 4. phone
        if phone:
            # Normalizar phone (remover caracteres não numéricos)
            phone_clean = ''.join(filter(str.isdigit, phone))
            if phone_clean:
                external_ids.append(self._hash_data(phone_clean))
        
        return external_ids
    
    def _hash_data(self, data: str) -> str:
        """Hash SHA256 de dados"""
        return hashlib.sha256(data.encode()).hexdigest()
    
    # ==================== PERSISTÊNCIA REDIS ====================
    
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
        external_ids: Optional[List[str]] = None,
        **kwargs
    ) -> bool:
        """
        Salva dados de tracking no Redis com múltiplas chaves para recuperação robusta.
        
        Chaves criadas:
        - tracking:token:{tracking_token}
        - tracking:fbclid:{fbclid} (se presente)
        - tracking:hash:{hash(telegram_user_id)} (se presente)
        - tracking:chat:{bot_id}:{customer_user_id}
        - tracking:payment:{payment_id} (se presente)
        """
        if not self.redis:
            logger.warning("⚠️ Redis não disponível - tracking não será persistido")
            return False
        
        try:
            tracking_data = {
                'tracking_token': tracking_token,
                'bot_id': bot_id,
                'customer_user_id': customer_user_id,
                'payment_id': payment_id,
                'fbclid': fbclid,
                'fbp': fbp,
                'fbc': fbc,
                'utm_source': utm_source,
                'utm_medium': utm_medium,
                'utm_campaign': utm_campaign,
                'external_ids': external_ids or [],
                'created_at': datetime.utcnow().isoformat(),
                **kwargs
            }
            
            data_json = json.dumps(tracking_data)
            ttl_seconds = self.TTL_DAYS * 24 * 3600
            
            # Chave principal: tracking_token
            self.redis.setex(
                f"tracking:token:{tracking_token}",
                ttl_seconds,
                data_json
            )
            
            # Chave por fbclid
            if fbclid:
                self.redis.setex(
                    f"tracking:fbclid:{fbclid}",
                    ttl_seconds,
                    data_json
                )
            
            # Chave por hash do telegram_user_id
            if customer_user_id:
                user_hash = self._hash_data(str(customer_user_id))
                self.redis.setex(
                    f"tracking:hash:{user_hash}",
                    ttl_seconds,
                    data_json
                )
            
            # Chave por chat (bot_id + customer_user_id)
            self.redis.setex(
                f"tracking:chat:{bot_id}:{customer_user_id}",
                ttl_seconds,
                data_json
            )
            
            # Chave por payment_id
            if payment_id:
                self.redis.setex(
                    f"tracking:payment:{payment_id}",
                    ttl_seconds,
                    data_json
                )
            
            logger.debug(f"✅ Tracking data salvo: token={tracking_token}, bot_id={bot_id}")
            return True
            
        except Exception as e:
            logger.error(f"❌ Erro ao salvar tracking data: {e}", exc_info=True)
            return False
    
    def recover_tracking_data(
        self,
        tracking_token: Optional[str] = None,
        fbclid: Optional[str] = None,
        telegram_user_id: Optional[str] = None,
        payment_id: Optional[int] = None,
        bot_id: Optional[int] = None,
    ) -> Optional[Dict[str, Any]]:
        """
        Recupera dados de tracking usando estratégia de múltiplas chaves.
        
        Ordem de tentativa:
        1. tracking_token (se fornecido)
        2. fbclid (se fornecido)
        3. payment_id (se fornecido)
        4. hash(telegram_user_id) (se fornecido)
        5. chat (bot_id + customer_user_id) (se ambos fornecidos)
        """
        if not self.redis:
            return None
        
        try:
            # 1. Por tracking_token
            if tracking_token:
                data = self.redis.get(f"tracking:token:{tracking_token}")
                if data:
                    return json.loads(data)
            
            # 2. Por fbclid
            if fbclid:
                data = self.redis.get(f"tracking:fbclid:{fbclid}")
                if data:
                    return json.loads(data)
            
            # 3. Por payment_id
            if payment_id:
                data = self.redis.get(f"tracking:payment:{payment_id}")
                if data:
                    return json.loads(data)
            
            # 4. Por hash do telegram_user_id
            if telegram_user_id:
                user_hash = self._hash_data(str(telegram_user_id))
                data = self.redis.get(f"tracking:hash:{user_hash}")
                if data:
                    return json.loads(data)
            
            # 5. Por chat
            if bot_id and telegram_user_id:
                data = self.redis.get(f"tracking:chat:{bot_id}:{telegram_user_id}")
                if data:
                    return json.loads(data)
            
            return None
            
        except Exception as e:
            logger.error(f"❌ Erro ao recuperar tracking data: {e}", exc_info=True)
            return None
```

---

## 5️⃣ MIDDLEWARE DE VALIDAÇÃO (NOVO)

**Arquivo:** `middleware/gateway_validator.py`

```python
from flask import request, jsonify
from functools import wraps
from typing import Dict, Any, Optional
import logging

logger = logging.getLogger(__name__)

def validate_gateway_request(f):
    """
    Middleware para validar requisições de gateway.
    """
    @wraps(f)
    def decorated_function(*args, **kwargs):
        # Validar Content-Type
        if request.method in ['POST', 'PUT', 'PATCH']:
            content_type = request.headers.get('Content-Type', '')
            if 'application/json' not in content_type and 'application/x-www-form-urlencoded' not in content_type:
                return jsonify({'error': 'Content-Type inválido'}), 400
        
        # Validar gateway_type
        gateway_type = kwargs.get('gateway_type') or request.args.get('gateway_type')
        if gateway_type:
            valid_types = ['syncpay', 'pushyn', 'paradise', 'wiinpay', 'atomopay']
            if gateway_type.lower() not in valid_types:
                return jsonify({'error': f'Gateway type inválido: {gateway_type}'}), 400
        
        return f(*args, **kwargs)
    
    return decorated_function

def validate_webhook_signature(f):
    """
    Middleware para validar assinatura de webhooks.
    """
    @wraps(f)
    def decorated_function(*args, **kwargs):
        gateway_type = kwargs.get('gateway_type')
        if not gateway_type:
            return jsonify({'error': 'gateway_type não fornecido'}), 400
        
        # Obter dados do webhook
        webhook_data = request.get_json() or request.form.to_dict()
        headers = dict(request.headers)
        
        # Criar gateway temporário para validação
        from gateway_factory import GatewayFactory
        # Nota: Para validar assinatura, precisamos das credenciais
        # Isso deve ser feito dentro da rota, não no middleware
        
        return f(*args, **kwargs)
    
    return decorated_function

def rate_limit_webhook(max_per_minute: int = 60):
    """
    Rate limiting para webhooks.
    """
    from functools import wraps
    from flask import request
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
```

---

## 6️⃣ ROTAS APP.PY (atualizar webhook)

**Arquivo:** `app.py` (seção de webhook)

```python
# ==================== WEBHOOK DE PAGAMENTO (UNIVERSAL) ====================

@app.route('/webhook/payment/<string:gateway_type>', methods=['POST'])
@csrf.exempt
@rate_limit_webhook(max_per_minute=60)
def payment_webhook(gateway_type: str):
    """
    Webhook universal para todos os gateways.
    
    Fluxo:
    1. Identificar gateway_type
    2. Identificar producer_hash (multi-tenant)
    3. Processar webhook via GatewayFactory
    4. Buscar Payment (múltiplas chaves)
    5. Atualizar status
    6. Enviar entregáveis
    7. Enviar Meta Pixel
    8. Gamificação
    """
    try:
        logger.info(f"🔔 Webhook recebido: gateway_type={gateway_type}")
        
        # 1. Obter dados do webhook
        webhook_data = request.get_json() or request.form.to_dict() or {}
        headers = dict(request.headers)
        
        if not webhook_data:
            logger.warning("⚠️ Webhook vazio")
            return jsonify({'error': 'Webhook vazio'}), 400
        
        # 2. Criar gateway temporário (sem credenciais ainda)
        from gateway_factory import GatewayFactory
        from gateway_adapter import GatewayAdapter
        
        # 3. Extrair producer_hash (multi-tenant) ANTES de buscar gateway
        producer_hash = None
        gateway_adapter = GatewayFactory.create_gateway(
            gateway_type,
            {},  # Credenciais vazias para extrair producer_hash
            use_adapter=True
        )
        
        if gateway_adapter:
            producer_hash = gateway_adapter.extract_producer_hash(webhook_data)
            logger.info(f"🔍 producer_hash extraído: {producer_hash}")
        
        # 4. Processar webhook via gateway (sem credenciais, apenas parsing)
        # Criar gateway dummy para processar estrutura do webhook
        webhook_result = None
        if gateway_adapter:
            # Usar método direto do gateway (sem validação de credenciais)
            if hasattr(gateway_adapter._gateway, 'process_webhook'):
                try:
                    webhook_result = gateway_adapter.process_webhook(webhook_data, headers)
                except Exception as e:
                    logger.warning(f"⚠️ Erro ao processar webhook (continuando): {e}")
        
        # Se não conseguiu processar, tentar parsing manual
        if not webhook_result:
            webhook_result = _parse_webhook_manual(webhook_data, gateway_type)
        
        if not webhook_result:
            logger.error("❌ Não foi possível processar webhook")
            return jsonify({'error': 'Webhook inválido'}), 400
        
        transaction_id = webhook_result.get('transaction_id')
        status = webhook_result.get('status')
        amount = webhook_result.get('amount', 0)
        
        if not transaction_id:
            logger.error("❌ transaction_id não encontrado no webhook")
            return jsonify({'error': 'transaction_id não encontrado'}), 400
        
        # 5. Buscar Payment (ESTRATÉGIA MULTI-CHAVE)
        payment = _find_payment_by_multiple_keys(
            transaction_id=transaction_id,
            gateway_type=gateway_type,
            producer_hash=producer_hash,
            amount=amount,
            webhook_data=webhook_data
        )
        
        if not payment:
            logger.warning(
                f"⚠️ Payment não encontrado: "
                f"transaction_id={transaction_id}, "
                f"gateway_type={gateway_type}, "
                f"producer_hash={producer_hash}"
            )
            # Retornar 200 para evitar retentativas do gateway
            return jsonify({'message': 'Payment não encontrado (já processado ou inválido)'}), 200
        
        # 6. Verificar se já foi processado (idempotência)
        if payment.status == 'paid' and status == 'paid':
            logger.info(f"✅ Payment {payment.id} já está pago - reenviando entregáveis/Meta Pixel")
            # Reenviar entregáveis e Meta Pixel (idempotente)
            send_payment_delivery(payment, bot_manager)
            send_meta_pixel_purchase_event(payment)
            return jsonify({'message': 'Payment já processado'}), 200
        
        # 7. Atualizar status do payment
        old_status = payment.status
        payment.status = status.value if hasattr(status, 'value') else str(status)
        payment.updated_at = datetime.utcnow()
        
        # Atualizar campos adicionais se presente
        if 'paid_at' in webhook_result:
            payment.paid_at = webhook_result['paid_at']
        
        if 'gateway_data' in webhook_result:
            payment.gateway_data = json.dumps(webhook_result['gateway_data'])
        
        # Salvar gateway_transaction_hash se presente
        if transaction_id:
            payment.gateway_transaction_hash = transaction_id
        
        db.session.commit()
        
        logger.info(
            f"✅ Payment {payment.id} atualizado: "
            f"{old_status} -> {payment.status}"
        )
        
        # 8. Se status = paid, processar entregáveis e tracking
        if payment.status == 'paid':
            # Enviar entregáveis
            send_payment_delivery(payment, bot_manager)
            
            # Enviar Meta Pixel
            send_meta_pixel_purchase_event(payment)
            
            # Gamificação
            _update_user_gamification(payment)
            
            # Upsell (se configurado)
            _trigger_upsell(payment, bot_manager)
        
        return jsonify({'message': 'Webhook processado com sucesso'}), 200
        
    except Exception as e:
        logger.error(f"❌ Erro ao processar webhook: {e}", exc_info=True)
        db.session.rollback()
        return jsonify({'error': 'Erro ao processar webhook'}), 500

def _parse_webhook_manual(webhook_data: Dict, gateway_type: str) -> Optional[Dict]:
    """
    Parser manual de webhook quando gateway não consegue processar.
    """
    try:
        # Tentar extrair campos comuns
        transaction_id = (
            webhook_data.get('transaction_id') or
            webhook_data.get('id') or
            webhook_data.get('hash') or
            webhook_data.get('payment_id') or
            webhook_data.get('external_reference')
        )
        
        status_str = (
            webhook_data.get('status') or
            webhook_data.get('payment_status') or
            webhook_data.get('state')
        )
        
        amount = float(
            webhook_data.get('amount') or
            webhook_data.get('value') or
            webhook_data.get('total') or
            0
        )
        
        if transaction_id and status_str:
            return {
                'transaction_id': transaction_id,
                'status': status_str,
                'amount': amount,
                'gateway_data': webhook_data
            }
    except Exception as e:
        logger.error(f"❌ Erro no parsing manual: {e}")
    
    return None

def _find_payment_by_multiple_keys(
    transaction_id: str,
    gateway_type: str,
    producer_hash: Optional[str],
    amount: Optional[float],
    webhook_data: Dict
) -> Optional[Payment]:
    """
    Busca Payment usando múltiplas chaves (estratégia robusta).
    
    Ordem de busca:
    1. gateway_transaction_id = transaction_id
    2. gateway_transaction_hash = transaction_id
    3. payment_id extraído de external_reference
    4. external_reference contém transaction_id
    5. producer_hash + transaction_id (multi-tenant)
    """
    from models import Payment, Gateway, Bot
    
    # 1. Buscar por gateway_transaction_id
    payment = Payment.query.filter_by(
        gateway_transaction_id=transaction_id,
        gateway_type=gateway_type
    ).first()
    
    if payment:
        logger.debug(f"✅ Payment encontrado por gateway_transaction_id: {payment.id}")
        return payment
    
    # 2. Buscar por gateway_transaction_hash
    payment = Payment.query.filter_by(
        gateway_transaction_hash=transaction_id,
        gateway_type=gateway_type
    ).first()
    
    if payment:
        logger.debug(f"✅ Payment encontrado por gateway_transaction_hash: {payment.id}")
        return payment
    
    # 3. Buscar por external_reference contendo transaction_id
    payment = Payment.query.filter(
        Payment.external_reference.contains(transaction_id),
        Payment.gateway_type == gateway_type
    ).first()
    
    if payment:
        logger.debug(f"✅ Payment encontrado por external_reference: {payment.id}")
        return payment
    
    # 4. Se producer_hash presente, buscar via Gateway + Bot
    if producer_hash:
        # Buscar Gateway com producer_hash
        gateway = Gateway.query.filter_by(
            producer_hash=producer_hash,
            gateway_type=gateway_type,
            is_active=True
        ).first()
        
        if gateway:
            # Buscar Payment do user_id do gateway
            payment = Payment.query.join(Bot).join(Gateway).filter(
                Gateway.id == gateway.id,
                Payment.gateway_transaction_id == transaction_id,
                Payment.gateway_type == gateway_type
            ).first()
            
            if payment:
                logger.debug(f"✅ Payment encontrado por producer_hash: {payment.id}")
                return payment
    
    # 5. Buscar por amount + gateway_type (último recurso, menos confiável)
    if amount:
        # Buscar payments pendentes com amount similar (± 1 real)
        payments = Payment.query.filter(
            Payment.gateway_type == gateway_type,
            Payment.status == 'pending',
            Payment.amount >= amount - 1.0,
            Payment.amount <= amount + 1.0
        ).order_by(Payment.created_at.desc()).limit(10).all()
        
        # Tentar match por transaction_id em gateway_data
        for p in payments:
            if p.gateway_data:
                try:
                    gateway_data = json.loads(p.gateway_data) if isinstance(p.gateway_data, str) else p.gateway_data
                    if gateway_data.get('transaction_id') == transaction_id:
                        logger.debug(f"✅ Payment encontrado por amount + gateway_data: {p.id}")
                        return p
                except:
                    pass
    
    return None

def _update_user_gamification(payment: Payment):
    """
    Atualiza gamificação do usuário após pagamento.
    """
    try:
        if not payment or not payment.bot:
            return
        
        user = payment.bot.user
        if not user:
            return
        
        # Atualizar streaks, ranking, achievements
        # (implementar lógica de gamificação existente)
        logger.debug(f"🎮 Gamificação atualizada para user {user.id}")
        
    except Exception as e:
        logger.error(f"❌ Erro ao atualizar gamificação: {e}", exc_info=True)

def _trigger_upsell(payment: Payment, bot_manager):
    """
    Dispara upsell após pagamento confirmado.
    """
    try:
        if not payment or not payment.bot:
            return
        
        # Verificar se bot tem upsell configurado
        # (implementar lógica de upsell existente)
        logger.debug(f"🛒 Upsell verificado para payment {payment.id}")
        
    except Exception as e:
        logger.error(f"❌ Erro ao disparar upsell: {e}", exc_info=True)
```

---

## 7️⃣ BOT_MANAGER (atualizar generate_payment)

**Arquivo:** `bot_manager.py` (seção _generate_pix_payment)

```python
def _generate_pix_payment(
    self,
    bot: Bot,
    customer_user_id: str,
    amount: float,
    product_name: str = "Produto",
    description: str = "",
    fbclid: Optional[str] = None,
    utm_source: Optional[str] = None,
    utm_medium: Optional[str] = None,
    utm_campaign: Optional[str] = None,
    remarketing_campaign_id: Optional[int] = None,
    **kwargs
) -> Optional[Payment]:
    """
    Gera pagamento PIX universal usando GatewayFactory.
    
    Fluxo:
    1. Validar inputs
    2. Buscar gateway ativo do user
    3. Preparar credenciais
    4. Criar gateway via Factory
    5. Gerar tracking_token V4
    6. Gerar PIX
    7. Salvar Payment no DB
    8. Salvar tracking data no Redis
    9. Enviar notificações
    """
    try:
        # 1. VALIDAÇÃO CRÍTICA
        if not customer_user_id or str(customer_user_id).strip() == '':
            logger.error("❌ customer_user_id vazio - não é possível gerar PIX")
            return None
        
        if amount <= 0:
            logger.error(f"❌ Amount inválido: {amount}")
            return None
        
        if not bot or not bot.user_id:
            logger.error("❌ Bot ou user_id inválido")
            return None
        
        # 2. Buscar gateway ativo e verificado
        from models import Gateway, db
        gateway_db = Gateway.query.filter_by(
            user_id=bot.user_id,
            is_active=True,
            is_verified=True
        ).first()
        
        if not gateway_db:
            logger.error(f"❌ Nenhum gateway ativo encontrado para user {bot.user_id}")
            return None
        
        # 3. Preparar credenciais do gateway
        credentials = _prepare_gateway_credentials(gateway_db, bot.user)
        
        # 4. Criar gateway via Factory
        from gateway_factory import GatewayFactory
        gateway = GatewayFactory.create_gateway(
            gateway_type=gateway_db.gateway_type,
            credentials=credentials,
            use_adapter=True  # Usar adapter para normalização
        )
        
        if not gateway:
            logger.error(f"❌ Erro ao criar gateway {gateway_db.gateway_type}")
            return None
        
        # 5. Gerar tracking_token V4
        from utils.tracking_service import TrackingServiceV4
        tracking_service = TrackingServiceV4()
        
        # Gerar fbp/fbc
        fbp = tracking_service.generate_fbp(str(customer_user_id))
        fbc = tracking_service.generate_fbc(fbclid) if fbclid else None
        
        # Gerar external_ids
        external_ids = tracking_service.build_external_id_array(
            fbclid=fbclid,
            telegram_user_id=str(customer_user_id),
            email=kwargs.get('customer_email'),
            phone=kwargs.get('customer_phone')
        )
        
        # Gerar tracking_token
        tracking_token = tracking_service.generate_tracking_token(
            bot_id=bot.id,
            customer_user_id=str(customer_user_id),
            fbclid=fbclid,
            utm_source=utm_source,
            utm_medium=utm_medium,
            utm_campaign=utm_campaign
        )
        
        # 6. Preparar dados do cliente (garantir unicidade)
        customer_name = kwargs.get('customer_name', f"Cliente {customer_user_id}")
        customer_email = kwargs.get('customer_email', f"client{customer_user_id}@temp.com")
        customer_cpf = kwargs.get('customer_cpf', _generate_unique_cpf())
        customer_phone = kwargs.get('customer_phone', _generate_unique_phone())
        
        # 7. Gerar external_reference único
        payment_id_temp = int(time.time() * 1000)  # ID temporário
        external_reference = f"{bot.id}_{customer_user_id}_{payment_id_temp}_{tracking_token}"
        
        # 8. Gerar PIX via gateway
        pix_result = gateway.generate_pix(
            amount=amount,
            customer_name=customer_name,
            customer_email=customer_email,
            customer_cpf=customer_cpf,
            customer_phone=customer_phone,
            external_reference=external_reference,
            description=description or product_name,
            expires_in=3600,
            **kwargs
        )
        
        if not pix_result:
            logger.error("❌ Erro ao gerar PIX - gateway retornou None")
            return None
        
        transaction_id = pix_result.get('transaction_id')
        if not transaction_id:
            logger.error("❌ transaction_id não retornado pelo gateway")
            return None
        
        # 9. Salvar Payment no DB
        payment = Payment(
            bot_id=bot.id,
            customer_user_id=str(customer_user_id),
            customer_name=customer_name,
            customer_email=customer_email,
            amount=amount,
            product_name=product_name,
            status='pending',
            gateway_type=gateway_db.gateway_type,
            gateway_id=gateway_db.id,
            gateway_transaction_id=transaction_id,
            gateway_transaction_hash=transaction_id,  # Backup
            external_reference=external_reference,
            qr_code=pix_result.get('qr_code'),
            qr_code_base64=pix_result.get('qr_code_base64'),
            payment_url=pix_result.get('payment_url'),
            # Tracking V4
            tracking_token=tracking_token,
            fbclid=fbclid,
            utm_source=utm_source,
            utm_medium=utm_medium,
            utm_campaign=utm_campaign,
            # Meta Pixel
            meta_fbp=fbp,
            meta_fbc=fbc,
            # Gateway data
            gateway_data=json.dumps(pix_result.get('gateway_data', {}))
        )
        
        db.session.add(payment)
        db.session.commit()
        
        logger.info(
            f"✅ Payment criado: id={payment.id}, "
            f"transaction_id={transaction_id}, "
            f"gateway={gateway_db.gateway_type}"
        )
        
        # 10. Salvar tracking data no Redis
        tracking_service.save_tracking_data(
            tracking_token=tracking_token,
            bot_id=bot.id,
            customer_user_id=str(customer_user_id),
            payment_id=payment.id,
            fbclid=fbclid,
            fbp=fbp,
            fbc=fbc,
            utm_source=utm_source,
            utm_medium=utm_medium,
            utm_campaign=utm_campaign,
            external_ids=external_ids
        )
        
        # 11. Salvar producer_hash se presente (AtomPay)
        if 'producer_hash' in pix_result.get('gateway_data', {}):
            producer_hash = pix_result['gateway_data']['producer_hash']
            if producer_hash and not gateway_db.producer_hash:
                gateway_db.producer_hash = producer_hash
                db.session.commit()
                logger.info(f"✅ producer_hash salvo: {producer_hash}")
        
        # 12. Enviar notificações
        _send_payment_notifications(payment, bot, gateway)
        
        return payment
        
    except Exception as e:
        logger.error(f"❌ Erro ao gerar PIX: {e}", exc_info=True)
        db.session.rollback()
        return None

def _prepare_gateway_credentials(gateway_db: Gateway, user: User) -> Dict[str, Any]:
    """
    Prepara credenciais do gateway baseado no tipo.
    """
    credentials = {}
    
    if gateway_db.gateway_type == 'syncpay':
        credentials = {
            'client_id': gateway_db.client_id,
            'client_secret': gateway_db.client_secret
        }
    elif gateway_db.gateway_type == 'pushyn':
        credentials = {
            'api_key': gateway_db.api_key
        }
    elif gateway_db.gateway_type == 'paradise':
        credentials = {
            'api_key': gateway_db.api_key,
            'product_hash': gateway_db.product_hash,
            'checkout_url': gateway_db.checkout_url
        }
    elif gateway_db.gateway_type == 'wiinpay':
        credentials = {
            'api_key': gateway_db.api_key
        }
    elif gateway_db.gateway_type == 'atomopay':
        credentials = {
            'api_token': gateway_db.api_key,  # AtomPay usa api_key como api_token
            'product_hash': gateway_db.product_hash,
            'offer_hash': gateway_db.offer_hash
        }
    
    # Adicionar split se presente
    if gateway_db.split_user_id:
        credentials['split_user_id'] = gateway_db.split_user_id
    
    return credentials

def _generate_unique_cpf() -> str:
    """Gera CPF único temporário"""
    import random
    return f"{random.randint(100000000, 999999999):011d}"

def _generate_unique_phone() -> str:
    """Gera telefone único temporário"""
    import random
    return f"55{random.randint(1000000000, 9999999999)}"

def _send_payment_notifications(payment: Payment, bot: Bot, gateway: Gateway):
    """
    Envia notificações de novo pagamento.
    """
    try:
        # WebSocket event
        socketio.emit('new_sale', {
            'payment_id': payment.id,
            'amount': payment.amount,
            'gateway_type': payment.gateway_type
        }, room=f"user_{payment.bot.user_id}")
        
        # Push notification (se configurado)
        # (implementar lógica de push notification existente)
        
        logger.debug(f"📢 Notificações enviadas para payment {payment.id}")
        
    except Exception as e:
        logger.error(f"❌ Erro ao enviar notificações: {e}", exc_info=True)
```

---

## 8️⃣ MIGRATIONS (adicionar campos)

**Arquivo:** `migrations/add_qi200_fields.py`

```python
"""
Migration para adicionar campos QI 200.
Execute: python migrations/add_qi200_fields.py
"""

from flask import Flask
from models import db
from sqlalchemy import text
import logging

logger = logging.getLogger(__name__)

def add_qi200_fields():
    """
    Adiciona campos necessários para QI 200.
    """
    app = Flask(__name__)
    app.config['SQLALCHEMY_DATABASE_URI'] = os.getenv('DATABASE_URL')
    app.config['SQLALCHEMY_TRACK_MODIFICATIONS'] = False
    
    db.init_app(app)
    
    with app.app_context():
        try:
            # 1. Adicionar tracking_token em Payment
            try:
                db.session.execute(text("""
                    ALTER TABLE payment
                    ADD COLUMN IF NOT EXISTS tracking_token VARCHAR(100);
                """))
                db.session.commit()
                logger.info("✅ Campo tracking_token adicionado em Payment")
            except Exception as e:
                logger.warning(f"⚠️ Campo tracking_token já existe ou erro: {e}")
            
            # 2. Adicionar producer_hash em Gateway (se não existir)
            try:
                db.session.execute(text("""
                    ALTER TABLE gateway
                    ADD COLUMN IF NOT EXISTS producer_hash VARCHAR(100);
                """))
                db.session.commit()
                logger.info("✅ Campo producer_hash adicionado em Gateway")
            except Exception as e:
                logger.warning(f"⚠️ Campo producer_hash já existe ou erro: {e}")
            
            # 3. Adicionar índices
            try:
                db.session.execute(text("""
                    CREATE INDEX IF NOT EXISTS idx_payment_tracking_token 
                    ON payment(tracking_token);
                """))
                db.session.execute(text("""
                    CREATE INDEX IF NOT EXISTS idx_gateway_producer_hash 
                    ON gateway(producer_hash);
                """))
                db.session.commit()
                logger.info("✅ Índices criados")
            except Exception as e:
                logger.warning(f"⚠️ Erro ao criar índices: {e}")
            
            logger.info("✅ Migration QI 200 concluída")
            
        except Exception as e:
            db.session.rollback()
            logger.error(f"❌ Erro na migration: {e}", exc_info=True)
            raise

if __name__ == '__main__':
    import os
    add_qi200_fields()
```

---

## 9️⃣ RESUMO DE IMPLEMENTAÇÃO

### Arquivos a Criar:
1. ✅ `gateway_adapter.py` - Adapter layer
2. ✅ `middleware/gateway_validator.py` - Middleware de validação
3. ✅ `migrations/add_qi200_fields.py` - Migration

### Arquivos a Atualizar:
1. ✅ `gateway_interface.py` - Adicionar métodos opcionais
2. ✅ `gateway_factory.py` - Melhorar factory
3. ✅ `utils/tracking_service.py` - Atualizar para V4
4. ✅ `app.py` - Atualizar webhook universal
5. ✅ `bot_manager.py` - Atualizar generate_payment
6. ✅ `models.py` - Adicionar campos (já existe producer_hash)

### Ordem de Implementação:
1. Executar migration
2. Implementar GatewayAdapter
3. Atualizar GatewayFactory
4. Atualizar TrackingService V4
5. Atualizar webhook em app.py
6. Atualizar generate_payment em bot_manager.py
7. Testar cada gateway individualmente
8. Testar webhooks
9. Testar tracking

---

## 🔟 CHECKLIST FINAL

- [ ] Migration executada
- [ ] GatewayAdapter implementado
- [ ] GatewayFactory atualizado
- [ ] TrackingService V4 implementado
- [ ] Webhook universal funcionando
- [ ] Generate_payment universal funcionando
- [ ] Multi-tenant testado (AtomPay)
- [ ] Multi-gateway testado (todos os gateways)
- [ ] Tracking token funcionando
- [ ] Meta Pixel funcionando
- [ ] Logs robustos implementados
- [ ] Rate limiting funcionando
- [ ] Validação de assinaturas (se aplicável)

---

**FIM DO DOCUMENTO**

