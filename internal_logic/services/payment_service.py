"""
PaymentService - Serviço de Pagamentos (Gateway Factory Pattern)
===============================================================
Scaffold do motor de pagamentos para integração com múltiplos gateways.

Este serviço implementa o Factory Pattern para suportar diferentes gateways
de pagamento (WiinPay, AguiaPags, SyncPay, Paradise, HooPay, etc).
"""

import logging
import uuid
from abc import ABC, abstractmethod
from typing import Optional, Dict, Any
from dataclasses import dataclass

# Import real gateway implementations
from gateways.gateway_paradise import ParadisePaymentGateway
from gateways.gateway_aguia import AguiaGateway
from gateways.gateway_bolt import BoltGateway
from gateways.gateway_syncpay import SyncPayGateway
from gateways.gateway_wiinpay import WiinPayGateway
from gateways.gateway_atomopay import AtomPayGateway
from gateways.gateway_orionpay import OrionPayGateway
from gateways.gateway_pushyn import PushynGateway
from gateways.gateway_umbrellapag import UmbrellaPagGateway
from gateways.gateway_babylon import BabylonGateway
from gateways.gateway_sigilopay import SigiloPayGateway

logger = logging.getLogger(__name__)


@dataclass
class PixPaymentRequest:
    """DTO para requisição de pagamento PIX"""
    amount: float
    description: str
    customer_name: str
    customer_email: str
    customer_cpf: Optional[str] = None
    expires_in: int = 3600  # segundos
    external_id: Optional[str] = None


@dataclass
class PixPaymentResponse:
    """DTO para resposta de pagamento PIX"""
    success: bool
    qr_code: Optional[str] = None
    qr_code_url: Optional[str] = None
    transaction_id: Optional[str] = None
    reference: Optional[str] = None  # ✅ NOVO: Reference oficial do gateway
    status: str = "pending"
    error_message: Optional[str] = None
    raw_response: Optional[Dict] = None


class BaseGateway(ABC):
    """Interface base para todos os gateways de pagamento"""
    
    def __init__(self, gateway_config: Any):
        self.config = gateway_config
        self.logger = logging.getLogger(f"{__name__}.{self.__class__.__name__}")
    
    @abstractmethod
    def generate_pix(self, payment_request: PixPaymentRequest) -> PixPaymentResponse:
        """Gera um pagamento PIX e retorna QR code ou link"""
        pass
    
    @abstractmethod
    def check_status(self, transaction_id: str) -> str:
        """Verifica status de uma transação"""
        pass
    
    @abstractmethod
    def cancel_transaction(self, transaction_id: str) -> bool:
        """Cancela uma transação pendente"""
        pass
    
    def _mask_key(self, key: str) -> str:
        """Helper para mascarar chaves sensíveis nos logs"""
        if not key:
            return "None"
        return f"****{key[-4:]}" if len(key) > 4 else "****"




class GatewayFactory:
    """
    Factory para criação de gateways de pagamento.
    
    Uso:
        gateway = GatewayFactory.create(gateway_model)
        response = gateway.generate_pix(payment_request)
    """
    
    # Mapeamento de gateway_type para classe real
    _GATEWAYS = {
        'wiinpay': WiinPayGateway,
        'aguia': AguiaGateway,
        'aguiapags': AguiaGateway,
        'syncpay': SyncPayGateway,
        'paradise': ParadisePaymentGateway,
        'bolt': BoltGateway,
        'atomopay': AtomPayGateway,  # ✅ Adicionado
        'orionpay': OrionPayGateway,
        'pushyn': PushynGateway,
        'umbrellapag': UmbrellaPagGateway,
        'babylon': BabylonGateway,
        'sigilopay': SigiloPayGateway,
    }
    
    @classmethod
    def create(cls, gateway_config: Any) -> Optional[Any]:
        """
        Cria instância do gateway apropriado baseado no gateway_type.
        
        Args:
            gateway_config: Instância do modelo Gateway (com type, api_key, etc)
            
        Returns:
            Instância do gateway ou None se tipo não suportado
        """
        if not gateway_config:
            logger.warning("GatewayFactory: gateway_config é None")
            return None
        
        gateway_type = getattr(gateway_config, 'gateway_type', '').lower()
        
        if gateway_type not in cls._GATEWAYS:
            logger.error(f"GatewayFactory: Tipo '{gateway_type}' não suportado")
            logger.info(f"Tipos suportados: {list(cls._GATEWAYS.keys())}")
            return None
        
        gateway_class = cls._GATEWAYS[gateway_type]
        
        try:
            # Extrair credenciais do gateway_config
            credentials = {}
            if hasattr(gateway_config, 'api_key') and gateway_config.api_key:
                credentials['api_key'] = gateway_config.api_key
            if hasattr(gateway_config, 'secret_key') and gateway_config.secret_key:
                credentials['secret_key'] = gateway_config.secret_key
            if hasattr(gateway_config, 'client_id') and gateway_config.client_id:
                credentials['client_id'] = gateway_config.client_id
            if hasattr(gateway_config, 'client_secret') and gateway_config.client_secret:
                credentials['client_secret'] = gateway_config.client_secret
            if hasattr(gateway_config, 'product_hash') and gateway_config.product_hash:
                credentials['product_hash'] = gateway_config.product_hash
            if hasattr(gateway_config, 'offer_hash') and gateway_config.offer_hash:
                credentials['offer_hash'] = gateway_config.offer_hash
            if hasattr(gateway_config, 'store_id') and gateway_config.store_id:
                credentials['store_id'] = gateway_config.store_id
            if hasattr(gateway_config, 'company_id') and gateway_config.company_id:
                credentials['company_id'] = gateway_config.company_id
            if hasattr(gateway_config, 'split_user_id') and gateway_config.split_user_id:
                credentials['split_user_id'] = gateway_config.split_user_id
            if hasattr(gateway_config, 'split_percentage') and gateway_config.split_percentage:
                credentials['split_percentage'] = gateway_config.split_percentage
            
            # Instanciar gateway baseado no tipo
            if gateway_type == 'syncpay':
                gateway_instance = gateway_class(
                    client_id=credentials.get('client_id'),
                    client_secret=credentials.get('client_secret')
                )
            elif gateway_type == 'atomopay':
                gateway_instance = gateway_class(
                    api_token=credentials.get('api_key'),
                    product_hash=credentials.get('product_hash')
                )
            elif gateway_type == 'babylon':
                gateway_instance = gateway_class(
                    api_key=credentials.get('api_key'),
                    company_id=credentials.get('client_id')
                )
            elif gateway_type == 'bolt':
                gateway_instance = gateway_class(
                    api_key=credentials.get('api_key'),
                    company_id=credentials.get('company_id')
                )
            elif gateway_type == 'paradise':
                gateway_instance = gateway_class(credentials)
            elif gateway_type in ['aguia', 'aguiapags']:
                gateway_instance = gateway_class(api_key=credentials.get('api_key', ''), sandbox=False)
            elif gateway_type == 'wiinpay':
                gateway_instance = gateway_class(
                    api_key=credentials.get('api_key', ''), 
                    split_user_id=credentials.get('split_user_id'), 
                    split_percentage=credentials.get('split_percentage')
                )
            elif gateway_type == 'sigilopay':
                gateway_instance = gateway_class(
                    api_key=credentials.get('api_key', ''),
                    secret_key=credentials.get('client_secret', '')
                )
            else:
                # Para outros (OrionPay, Pushyn, UmbrellaPag)
                gateway_instance = gateway_class(api_key=credentials.get('api_key', ''))
            
            logger.info(f"GatewayFactory: Criado {gateway_class.__name__} para {gateway_type}")
            return gateway_instance
            
        except Exception as e:
            logger.error(f"GatewayFactory: Erro ao criar gateway {gateway_type}: {e}")
            return None
    
    @classmethod
    def register_gateway(cls, gateway_type: str, gateway_class: type):
        """Registra um novo tipo de gateway dinamicamente"""
        cls._GATEWAYS[gateway_type.lower()] = gateway_class
        logger.info(f"GatewayFactory: Registrado {gateway_class.__name__} para '{gateway_type}'")


class PaymentService:
    """
    Serviço principal de pagamentos.
    
    Responsabilidades:
    - Orquestrar a criação de pagamentos via gateways
    - Gerenciar transações no banco de dados
    - Fornecer interface unificada para o BotManager
    
    Uso:
        service = PaymentService(db_session)
        response = service.generate_pix(bot_id, amount, description, customer_data)
    """
    
    def __init__(self, db_session=None):
        self.db = db_session
        self.logger = logging.getLogger(f"{__name__}.PaymentService")
    
    def generate_pix(
        self,
        bot_id: int,
        gateway_id: int,
        amount: float,
        description: str,
        customer_name: str,
        customer_email: str,
        customer_cpf: Optional[str] = None,
        external_id: Optional[str] = None,
        order_bump_shown: bool = False,
        order_bump_accepted: bool = False,
        order_bump_value: float = 0.0,
        is_downsell: bool = False,
        downsell_index: int = None,
        is_upsell: bool = False,
        upsell_index: int = None,
        is_remarketing: bool = False,
        remarketing_campaign_id: int = None,
        button_index: int = None,
        button_config: str = None
    ) -> PixPaymentResponse:
        # Initialize distributed lock variables - MUST be first line
        lock_key = None
        lock_acquired = False
        redis_conn = None
        
        """
        Gera um pagamento PIX através do gateway configurado.
        
        Args:
            bot_id: ID do bot solicitante
            gateway_id: ID do gateway a ser usado
            amount: Valor do pagamento
            description: Descrição do produto/serviço
            customer_name: Nome do cliente
            customer_email: Email do cliente
            customer_cpf: CPF do cliente (opcional)
            external_id: ID externo para rastreamento (opcional)
            
        Returns:
            PixPaymentResponse com QR code ou erro
        """
        # 1. Log de início da requisição
        self.logger.info(f"Gerando PIX - BotID: {bot_id} | Valor: {amount} | UserID: {external_id}")
        
        # 1. Buscar gateway no banco
        try:
            from internal_logic.core.models import Gateway
            gateway_config = Gateway.query.get(gateway_id) if self.db else None
            
            # 2. Log da busca do Gateway
            if gateway_config:
                self.logger.info(f"Gateway ativo encontrado: {gateway_config.gateway_type}")
            else:
                self.logger.error(f"Nenhum gateway verificado e ativo para o dono do bot {bot_id}")
                return PixPaymentResponse(
                    success=False,
                    error_message=f"Gateway {gateway_id} não encontrado"
                )
            
            if not gateway_config.is_active:
                self.logger.warning(f"Gateway {gateway_id} está inativo")
                return PixPaymentResponse(
                    success=False,
                    error_message=f"Gateway {gateway_id} está inativo"
                )
        
        except Exception as e:
            self.logger.error(f"PaymentService: Erro ao buscar gateway - {e}")
            return PixPaymentResponse(
                success=False,
                error_message="Erro interno ao buscar gateway"
            )
        
        # 3. Verificar criptografia das chaves
        try:
            # Testar se conseguimos acessar as chaves (desencriptação automática via @property)
            api_key = gateway_config.api_key
            client_secret = gateway_config.client_secret
            
            if api_key is None and client_secret is None:
                # 3. Log de falha na descriptografia
                self.logger.error("Falha ao descriptografar chaves do gateway. A ENCRYPTION_KEY mudou?")
                return PixPaymentResponse(
                    success=False,
                    error_message="Falha ao descriptografar credenciais do gateway"
                )
        except Exception as e:
            self.logger.error(f"Falha ao descriptografar chaves do gateway. A ENCRYPTION_KEY mudou? - {e}")
            return PixPaymentResponse(
                success=False,
                error_message="Erro ao acessar credenciais do gateway"
            )
        
        # 2. Criar instância do gateway via Factory
        gateway = GatewayFactory.create(gateway_config)
        if not gateway:
            self.logger.error(f"Tipo de gateway '{gateway_config.gateway_type}' não suportado")
            return PixPaymentResponse(
                success=False,
                error_message=f"Tipo de gateway '{gateway_config.gateway_type}' não suportado"
            )
        
        # 3. Montar requisição
        request = PixPaymentRequest(
            amount=amount,
            description=description,
            customer_name=customer_name,
            customer_email=customer_email,
            customer_cpf=customer_cpf,
            external_id=external_id or f"bot_{bot_id}_{int(__import__('time').time())}"
        )
        
        # 4. Chamar gateway
        try:
            # Garanta que payment_id e description existam no escopo antes dessa chamada
            payment_id = external_id or f"bot_{bot_id}_{int(__import__('time').time())}"
            customer_user_id = external_id or bot_id
            
            result = gateway.generate_pix(
                amount=amount,
                description=description,
                payment_id=payment_id,
                customer_data={
                    'name': customer_name,
                    'email': f"{customer_user_id}@telegram.user",
                    'phone': str(customer_user_id),
                    'document': str(customer_user_id)
                }
            )
            
            # 4. Log do resultado da API externa
            if result and result.get('status') != 'error':
                self.logger.info(f"PIX gerado com sucesso via {gateway_config.gateway_type}")
                # O gateway legado retorna um dict com 'pix_code'. O DTO espera 'qr_code'.
                if isinstance(result, dict):
                    response = PixPaymentResponse(
                        success=True,
                        qr_code=result.get('pix_code') or result.get('qr_code'),
                        qr_code_url=result.get('qr_code_url'),
                        transaction_id=result.get('transaction_id') or result.get('payment_id'),
                        reference=result.get('reference') or result.get('external_reference'), # ✅ Capturar reference
                        status="pending",
                        raw_response=result
                    )
                else:
                    response = PixPaymentResponse(
                        success=True,
                        qr_code=None,
                        qr_code_url=None,
                        transaction_id=None,
                        status="pending",
                        raw_response=result
                    )
            else:
                self.logger.error(f"Erro na API do Gateway {gateway_config.gateway_type}: {result.get('error', 'Unknown error')}")
                response = PixPaymentResponse(
                    success=False,
                    error_message=result.get('error', 'Erro desconhecido no gateway'),
                    raw_response=result
                )
            
            # 5. Registrar transação no banco (se sucesso)
            if response.success and self.db:
                # Priorizar o reference retornado pelo gateway, senão usa o payment_id original
                final_payment_id = response.reference or payment_id
                transaction_hash = None
                try:
                    if isinstance(response.raw_response, dict):
                        transaction_hash = response.raw_response.get('transaction_hash') or response.raw_response.get('gateway_transaction_hash')
                except Exception:
                    transaction_hash = None
                
                self._register_transaction(
                    bot_id=bot_id,
                    gateway_id=gateway_id,
                    gateway_type=gateway_config.gateway_type,
                    payment_id=final_payment_id,
                    transaction_id=response.transaction_id,
                    transaction_hash=transaction_hash,
                    amount=amount,
                    status=response.status,
                    customer_user_id=customer_user_id,
                    customer_name=customer_name,
                    product_name=description,
                    product_description=response.qr_code,
                    order_bump_shown=order_bump_shown,
                    order_bump_accepted=order_bump_accepted,
                    order_bump_value=order_bump_value,
                    is_downsell=is_downsell,
                    downsell_index=downsell_index,
                    is_upsell=is_upsell,
                    upsell_index=upsell_index,
                    is_remarketing=is_remarketing,
                    remarketing_campaign_id=remarketing_campaign_id,
                    button_index=button_index,
                    button_config=button_config,
                )
            
            return response
            
        except Exception as e:
            self.logger.error(f"Erro na API do Gateway {gateway_config.gateway_type}: {str(e)}")
            return PixPaymentResponse(
                success=False,
                error_message=f"Erro ao comunicar com gateway: {str(e)}"
            )
        finally:
            try:
                if lock_acquired and lock_key and redis_conn:
                    redis_conn.delete(lock_key)
            except Exception as e:
                self.logger.warning(f"Erro ao liberar lock PIX: {e}")
    
    def _register_transaction(
        self,
        bot_id: int,
        gateway_id: int,
        gateway_type: str,
        payment_id: str,
        transaction_id: Optional[str],
        transaction_hash: Optional[str],
        amount: float,
        status: str,
        customer_user_id: Optional[str] = None,
        customer_name: Optional[str] = None,
        product_name: Optional[str] = None,
        product_description: Optional[str] = None,
        device_type: Optional[str] = None,
        os_type: Optional[str] = None,
        browser: Optional[str] = None,
        device_model: Optional[str] = None,
        order_bump_shown: bool = False,
        order_bump_accepted: bool = False,
        order_bump_value: float = 0.0,
        is_downsell: bool = False,
        downsell_index: int = None,
        is_upsell: bool = False,
        upsell_index: int = None,
        is_remarketing: bool = False,
        remarketing_campaign_id: int = None,
        button_index: int = None,
        button_config: str = None
    ):
        """Registra transação no banco de dados"""
        try:
            from internal_logic.core.models import Payment
            
            # 🚀 ARQUITETURA SENIOR: Usar dados REAIS do gateway, não fallbacks fixos
            payment = Payment(
                bot_id=bot_id,
                payment_id=payment_id,                # ✅ ID Real (Reference)
                gateway_type=(gateway_type or '').strip().lower(),           # ✅ Tipo Real (atomopay, etc)
                amount=amount,
                status=status,
                gateway_transaction_id=str(transaction_id) if transaction_id else payment_id,
                gateway_transaction_hash=str(transaction_hash) if transaction_hash else None,
                customer_user_id=str(customer_user_id) if customer_user_id else None,
                customer_name=customer_name,
                product_name=product_name,
                product_description=product_description,
                device_type=device_type,
                os_type=os_type,
                browser=browser,
                device_model=device_model,
                order_bump_shown=order_bump_shown,
                order_bump_accepted=order_bump_accepted,
                order_bump_value=order_bump_value,
                is_downsell=is_downsell,
                downsell_index=downsell_index,
                is_upsell=is_upsell,
                upsell_index=upsell_index,
                is_remarketing=is_remarketing,
                remarketing_campaign_id=remarketing_campaign_id,
                button_index=button_index,
                button_config=button_config
            )
            self.db.add(payment)
            self.db.commit()
            
            self.logger.info(f"PaymentService: Transação registrada - ID {payment.id} | Type: {gateway_type}")
            
        except Exception as e:
            self.logger.error(f"PaymentService: Erro ao registrar transação - {e}")
            self.db.rollback()
    
    def check_payment_status(self, transaction_id: str, gateway_id: int) -> str:
        """Verifica status de um pagamento existente"""
        try:
            from internal_logic.core.models import Gateway
            gateway_config = Gateway.query.get(gateway_id) if self.db else None
            
            if not gateway_config:
                return "unknown"
            
            gateway = GatewayFactory.create(gateway_config)
            if gateway:
                return gateway.check_status(transaction_id)
            
            return "unknown"
            
        except Exception as e:
            self.logger.error(f"PaymentService: Erro ao verificar status - {e}")
            return "error"
    
    def get_active_gateway_for_user(self, user_id: int) -> Optional[Any]:
        """Retorna o gateway ativo para um usuário"""
        try:
            from internal_logic.core.models import Gateway
            return Gateway.query.filter_by(
                user_id=user_id,
                is_active=True
            ).first()
        except Exception as e:
            self.logger.error(f"PaymentService: Erro ao buscar gateway ativo - {e}")
            return None


# Singleton para uso global
_payment_service_instance: Optional[PaymentService] = None


def get_payment_service(db_session=None) -> PaymentService:
    """Retorna instância singleton do PaymentService"""
    global _payment_service_instance
    if _payment_service_instance is None:
        _payment_service_instance = PaymentService(db_session)
    elif db_session:
        _payment_service_instance.db = db_session
    return _payment_service_instance
