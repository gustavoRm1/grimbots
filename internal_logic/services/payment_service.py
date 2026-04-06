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


class WiinPayGateway(BaseGateway):
    """Gateway WiinPay - Split de pagamentos"""
    
    def generate_pix(self, payment_request: PixPaymentRequest) -> PixPaymentResponse:
        """
        Implementação WiinPay para geração de PIX.
        Endpoint: POST /api/v1/payments/pix
        """
        self.logger.info(f"Gerando PIX WiinPay - Amount: {payment_request.amount}")
        
        # TODO: Implementar chamada real à API WiinPay
        # Headers: Authorization: Bearer {config.api_key}
        # Body: { amount, description, customer, split_config }
        
        return PixPaymentResponse(
            success=False,
            error_message="WiinPay gateway não implementado (scaffold)"
        )
    
    def check_status(self, transaction_id: str) -> str:
        self.logger.info(f"Verificando status WiinPay: {transaction_id}")
        return "pending"
    
    def cancel_transaction(self, transaction_id: str) -> bool:
        self.logger.info(f"Cancelando transação WiinPay: {transaction_id}")
        return False


class AguiaPagsGateway(BaseGateway):
    """Gateway AguiarPags - Simplificado"""
    
    def generate_pix(self, payment_request: PixPaymentRequest) -> PixPaymentResponse:
        """
        Implementação AguiarPags para geração de PIX.
        """
        self.logger.info(f"Gerando PIX AguiarPags - Amount: {payment_request.amount}")
        
        # TODO: Implementar chamada real à API AguiarPags
        
        return PixPaymentResponse(
            success=False,
            error_message="AguiarPags gateway não implementado (scaffold)"
        )
    
    def check_status(self, transaction_id: str) -> str:
        return "pending"
    
    def cancel_transaction(self, transaction_id: str) -> bool:
        return False


class SyncPayGateway(BaseGateway):
    """Gateway SyncPay - Sincronização multi-gateway"""
    
    def generate_pix(self, payment_request: PixPaymentRequest) -> PixPaymentResponse:
        """
        Implementação SyncPay para geração de PIX.
        """
        self.logger.info(f"Gerando PIX SyncPay - Amount: {payment_request.amount}")
        
        # TODO: Implementar chamada real à API SyncPay
        
        return PixPaymentResponse(
            success=False,
            error_message="SyncPay gateway não implementado (scaffold)"
        )
    
    def check_status(self, transaction_id: str) -> str:
        return "pending"
    
    def cancel_transaction(self, transaction_id: str) -> bool:
        return False


class ParadiseGateway(BaseGateway):
    """Gateway Paradise Pay - Checkout completo"""
    
    def generate_pix(self, payment_request: PixPaymentRequest) -> PixPaymentResponse:
        """
        Implementação Paradise para geração de PIX.
        Usa product_hash e offer_hash para identificação.
        """
        self.logger.info(f"Gerando PIX Paradise - Amount: {payment_request.amount}")
        
        # TODO: Implementar chamada real à API Paradise
        # Usa: config._product_hash, config._offer_hash
        
        return PixPaymentResponse(
            success=False,
            error_message="Paradise gateway não implementado (scaffold)"
        )
    
    def check_status(self, transaction_id: str) -> str:
        return "pending"
    
    def cancel_transaction(self, transaction_id: str) -> bool:
        return False


class HooPayGateway(BaseGateway):
    """Gateway HooPay - Organizações e subcontas"""
    
    def generate_pix(self, payment_request: PixPaymentRequest) -> PixPaymentResponse:
        """
        Implementação HooPay para geração de PIX.
        Usa organization_id para identificação.
        """
        self.logger.info(f"Gerando PIX HooPay - Amount: {payment_request.amount}")
        
        # TODO: Implementar chamada real à API HooPay
        # Usa: config._organization_id
        
        return PixPaymentResponse(
            success=False,
            error_message="HooPay gateway não implementado (scaffold)"
        )
    
    def check_status(self, transaction_id: str) -> str:
        return "pending"
    
    def cancel_transaction(self, transaction_id: str) -> bool:
        return False


class AtomoGateway(BaseGateway):
    """Gateway Atomo - Producer hash based"""
    
    def generate_pix(self, payment_request: PixPaymentRequest) -> PixPaymentResponse:
        """
        Implementação Atomo para geração de PIX.
        Usa producer_hash para identificação.
        """
        self.logger.info(f"Gerando PIX Atomo - Amount: {payment_request.amount}")
        
        # TODO: Implementar chamada real à API Atomo
        # Usa: config.producer_hash
        
        return PixPaymentResponse(
            success=False,
            error_message="Atomo gateway não implementado (scaffold)"
        )
    
    def check_status(self, transaction_id: str) -> str:
        return "pending"
    
    def cancel_transaction(self, transaction_id: str) -> bool:
        return False


class GatewayFactory:
    """
    Factory para criação de gateways de pagamento.
    
    Uso:
        gateway = GatewayFactory.create(gateway_model)
        response = gateway.generate_pix(payment_request)
    """
    
    # Mapeamento de gateway_type para classe
    _GATEWAYS = {
        'wiinpay': WiinPayGateway,
        'aguiapags': AguiaPagsGateway,
        'aguia': AguiaPagsGateway,
        'syncpay': SyncPayGateway,
        'paradise': ParadiseGateway,
        'hoopay': HooPayGateway,
        'atomo': AtomoGateway,
    }
    
    @classmethod
    def create(cls, gateway_config: Any) -> Optional[BaseGateway]:
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
        gateway_instance = gateway_class(gateway_config)
        
        logger.info(f"GatewayFactory: Criado {gateway_class.__name__} para {gateway_type}")
        return gateway_instance
    
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
        self.logger.info(f"PaymentService: Gerando PIX - Bot {bot_id}, Gateway {gateway_id}, Amount {amount}")
        
        # 1. Buscar gateway no banco
        try:
            from internal_logic.core.models import Gateway
            gateway_config = Gateway.query.get(gateway_id) if self.db else None
            
            if not gateway_config:
                return PixPaymentResponse(
                    success=False,
                    error_message=f"Gateway {gateway_id} não encontrado"
                )
            
            if not gateway_config.is_active:
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
        
        # 2. Criar instância do gateway via Factory
        gateway = GatewayFactory.create(gateway_config)
        if not gateway:
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
            response = gateway.generate_pix(request)
            
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
            self.logger.error(f"PaymentService: Erro ao gerar PIX - {e}")
            return PixPaymentResponse(
                success=False,
                error_message=f"Erro ao comunicar com gateway: {str(e)}"
            )
    
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
