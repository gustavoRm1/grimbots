"""
PaymentService - Serviço de Pagamentos (Gateway Factory Pattern)
===============================================================
Scaffold do motor de pagamentos para integração com múltiplos gateways.

Este serviço implementa o Factory Pattern para suportar diferentes gateways
de pagamento (WiinPay, AguiaPags, SyncPay, Paradise, HooPay, etc).
"""

import logging
from abc import ABC, abstractmethod
from typing import Optional, Dict, Any
from dataclasses import dataclass

# Import real gateway implementations
import sys
import os
sys.path.append(os.path.join(os.path.dirname(__file__), '..', '..'))

from gateway_paradise import ParadisePaymentGateway
from gateways.gateway_aguia import AguiaGateway
from gateway_bolt import BoltGateway
from gateway_syncpay import SyncPayGateway
from gateway_wiinpay import WiinPayGateway
# from gateway_atomopay import AtomoGateway  # Commented out - requires encryption setup
# from gateway_orionpay import OrionPayGateway  # Commented out - requires encryption setup
# from gateway_pushyn import PushynGateway  # Commented out - requires encryption setup
# from gateway_umbrellapag import UmbrellaPagGateway  # Commented out - requires encryption setup

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
        # 'atomo': AtomoGateway,  # Commented out - requires encryption setup
        # 'orionpay': OrionPayGateway,  # Commented out - requires encryption setup
        # 'pushyn': PushynGateway,  # Commented out - requires encryption setup
        # 'umbrellapag': UmbrellaPagGateway,  # Commented out - requires encryption setup
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
            if gateway_type == 'paradise':
                gateway_instance = gateway_class(credentials)
            elif gateway_type == 'aguia' or gateway_type == 'aguiapags':
                api_key = credentials.get('api_key', '')
                gateway_instance = gateway_class(api_key=api_key, sandbox=True)
            elif gateway_type == 'bolt':
                api_key = credentials.get('api_key', '')
                company_id = credentials.get('company_id', '')
                gateway_instance = gateway_class(api_key=api_key, company_id=company_id)
            elif gateway_type == 'wiinpay':
                api_key = credentials.get('api_key', '')
                split_user_id = credentials.get('split_user_id')
                split_percentage = credentials.get('split_percentage')
                gateway_instance = gateway_class(api_key=api_key, split_user_id=split_user_id, split_percentage=split_percentage)
            else:
                # Para outros gateways, tentar passar apenas api_key
                api_key = credentials.get('api_key', '')
                gateway_instance = gateway_class(api_key=api_key)
            
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
        external_id: Optional[str] = None
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
                response = PixPaymentResponse(
                    success=True,
                    transaction_id=result.get('transaction_id'),
                    pix_code=result.get('pix_code'),
                    qr_code_url=result.get('qr_code_url'),
                    status=result.get('status', 'pending'),
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
                self._register_transaction(
                    bot_id=bot_id,
                    gateway_id=gateway_id,
                    transaction_id=response.transaction_id,
                    amount=amount,
                    status=response.status
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
        transaction_id: Optional[str],
        amount: float,
        status: str
    ):
        """Registra transação no banco de dados"""
        try:
            from internal_logic.core.models import Payment
            
            payment = Payment(
                bot_id=bot_id,
                gateway_id=gateway_id,
                amount=amount,
                status=status,
                external_id=transaction_id
            )
            self.db.add(payment)
            self.db.commit()
            
            self.logger.info(f"PaymentService: Transação registrada - ID {payment.id}")
            
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
