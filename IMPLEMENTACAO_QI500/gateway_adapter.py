"""
Gateway Adapter - Normaliza entrada/saída de todos os gateways
Implementado por: Engineer QI 500
"""

from typing import Dict, Any, Optional
from gateway_interface import PaymentGateway
import logging

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
        description: str,
        payment_id: str,
        customer_data: Optional[Dict[str, Any]] = None
    ) -> Optional[Dict[str, Any]]:
        """
        Normaliza generate_pix de todos os gateways.
        """
        try:
            # Validar inputs
            if amount <= 0:
                raise ValueError(f"Amount deve ser > 0, recebido: {amount}")
            
            # Chamar gateway real
            result = self._gateway.generate_pix(
                amount=amount,
                description=description,
                payment_id=payment_id,
                customer_data=customer_data
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
    
    def process_webhook(self, data: Dict[str, Any]) -> Optional[Dict[str, Any]]:
        """
        Normaliza process_webhook de todos os gateways.
        """
        try:
            # Validar webhook_data
            if not data:
                logger.warning("⚠️ webhook_data vazio")
                return None
            
            # Chamar gateway real
            result = self._gateway.process_webhook(data)
            
            if not result:
                logger.warning(f"⚠️ Gateway {self._gateway.get_gateway_type()} retornou None para process_webhook")
                return None
            
            # Normalizar resposta
            normalized = self._normalize_webhook_response(result)
            
            logger.info(
                f"✅ Webhook processado via {self._gateway.get_gateway_type()}: "
                f"transaction_id={normalized.get('gateway_transaction_id')}, "
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
            'pix_code': result.get('pix_code') or result.get('qr_code') or result.get('emv'),
            'qr_code_url': result.get('qr_code_url') or result.get('qr_code_base64') or '',
            'qr_code_base64': result.get('qr_code_base64'),
            'payment_id': result.get('payment_id'),
            'gateway_hash': result.get('gateway_hash') or result.get('hash') or result.get('transaction_hash'),
            'reference': result.get('reference') or result.get('external_reference'),
            'producer_hash': result.get('producer_hash'),
            'status': result.get('status', 'pending'),
            'error': result.get('error')
        }
        
        # Garantir transaction_id (gerar hash se não existir)
        if not normalized['transaction_id']:
            import hashlib
            import json
            data_str = json.dumps(result, sort_keys=True)
            normalized['transaction_id'] = hashlib.sha256(data_str.encode()).hexdigest()[:32]
        
        return normalized
    
    def _normalize_webhook_response(self, result: Dict[str, Any]) -> Dict[str, Any]:
        """
        Normaliza resposta de process_webhook.
        Garante que todos os gateways retornem o mesmo formato.
        """
        # Normalizar status
        status_str = result.get('status', '').lower()
        if status_str in ['paid', 'pago', 'approved', 'aprovado', 'confirmed']:
            status = 'paid'
        elif status_str in ['pending', 'pendente', 'waiting']:
            status = 'pending'
        elif status_str in ['refunded', 'reembolsado', 'failed', 'cancelled', 'canceled', 'expired', 'refused']:
            status = 'failed'
        else:
            status = 'pending'
        
        normalized = {
            'gateway_transaction_id': result.get('gateway_transaction_id') or result.get('transaction_id') or result.get('id'),
            'gateway_hash': result.get('gateway_hash') or result.get('hash') or result.get('transaction_hash'),
            'status': status,
            'amount': float(result.get('amount', 0)),
            'external_reference': result.get('external_reference') or result.get('reference'),
            'producer_hash': result.get('producer_hash'),
            'payer_name': result.get('payer_name'),
            'payer_document': result.get('payer_document'),
            'end_to_end_id': result.get('end_to_end_id')
        }
        
        # Garantir gateway_transaction_id
        if not normalized['gateway_transaction_id']:
            normalized['gateway_transaction_id'] = normalized['gateway_hash']
        
        return normalized

