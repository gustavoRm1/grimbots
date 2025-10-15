"""
Interface Base para Gateways de Pagamento
Implementa Pattern Strategy para isolamento completo entre gateways
"""

from abc import ABC, abstractmethod
from typing import Dict, Any, Optional
from datetime import datetime


class PaymentGateway(ABC):
    """
    Interface abstrata para todos os gateways de pagamento.
    
    Cada gateway deve implementar todos os métodos abstratos.
    Isso garante isolamento completo e facilita manutenção.
    """
    
    @abstractmethod
    def generate_pix(
        self, 
        amount: float, 
        description: str, 
        payment_id: str,
        customer_data: Optional[Dict[str, Any]] = None
    ) -> Optional[Dict[str, Any]]:
        """
        Gera um pagamento PIX no gateway
        
        Args:
            amount: Valor em reais (ex: 10.50)
            description: Descrição do produto/serviço
            payment_id: ID único do pagamento no sistema
            customer_data: Dados opcionais do cliente (nome, CPF, email, etc)
        
        Returns:
            Dict com dados do PIX gerado:
            {
                'pix_code': str,              # Código PIX copia e cola (obrigatório)
                'qr_code_url': str,           # URL da imagem QR Code (obrigatório)
                'transaction_id': str,        # ID da transação no gateway (obrigatório)
                'payment_id': str,            # ID do pagamento no sistema (obrigatório)
                'qr_code_base64': str,        # QR Code em base64 (opcional)
                'expires_at': datetime        # Data de expiração (opcional)
            }
            
            None em caso de erro
        """
        pass
    
    @abstractmethod
    def process_webhook(self, data: Dict[str, Any]) -> Optional[Dict[str, Any]]:
        """
        Processa webhook recebido do gateway
        
        Args:
            data: Dados brutos do webhook (JSON do gateway)
        
        Returns:
            Dict com dados processados:
            {
                'payment_id': str,              # ID único do pagamento
                'status': str,                  # 'pending', 'paid', 'failed'
                'amount': float,                # Valor em reais
                'gateway_transaction_id': str,  # ID no gateway
                'payer_name': str,              # Nome do pagador (opcional)
                'payer_document': str,          # CPF/CNPJ (opcional)
                'end_to_end_id': str            # E2E do BC (opcional)
            }
            
            None em caso de erro
        """
        pass
    
    @abstractmethod
    def verify_credentials(self) -> bool:
        """
        Verifica se as credenciais do gateway são válidas
        
        Returns:
            True se credenciais válidas, False caso contrário
        """
        pass
    
    @abstractmethod
    def get_payment_status(self, transaction_id: str) -> Optional[Dict[str, Any]]:
        """
        Consulta status de um pagamento no gateway
        
        Args:
            transaction_id: ID da transação no gateway
        
        Returns:
            Mesmo formato do process_webhook()
            None em caso de erro
        """
        pass
    
    @abstractmethod
    def get_webhook_url(self) -> str:
        """
        Retorna URL do webhook para este gateway
        
        Returns:
            URL completa do webhook (ex: https://domain.com/webhook/payment/syncpay)
        """
        pass
    
    @abstractmethod
    def get_gateway_name(self) -> str:
        """
        Retorna nome identificador do gateway
        
        Returns:
            Nome do gateway (ex: 'SyncPay', 'PushynPay')
        """
        pass
    
    @abstractmethod
    def get_gateway_type(self) -> str:
        """
        Retorna tipo do gateway (usado para roteamento)
        
        Returns:
            Tipo do gateway (ex: 'syncpay', 'pushynpay')
        """
        pass
    
    def validate_amount(self, amount: float) -> bool:
        """
        Valida se o valor é válido para pagamento
        
        Args:
            amount: Valor em reais
        
        Returns:
            True se válido, False caso contrário
        """
        return amount > 0 and isinstance(amount, (int, float))
    
    def format_currency(self, amount: float) -> str:
        """
        Formata valor em moeda brasileira
        
        Args:
            amount: Valor em reais
        
        Returns:
            String formatada (ex: 'R$ 10,50')
        """
        return f"R$ {amount:,.2f}".replace(",", "X").replace(".", ",").replace("X", ".")

