"""
Gateway Adapter - Normaliza entrada/saída de todos os gateways
Implementado por: Arquiteto Sênior QI 200

OBJETIVO:
- Normalizar dados entre gateways
- Garantir formato consistente de retorno
- Facilitar adição de novos gateways
"""

from typing import Dict, Any, Optional, List
import logging

logger = logging.getLogger(__name__)


class GatewayAdapter:
    """
    Adapter que normaliza dados entre gateways
    
    Garante que todos os gateways retornam o mesmo formato,
    independente de como implementam internamente.
    """
    
    @staticmethod
    def normalize_generate_request(
        gateway_type: str,
        amount: float,
        description: str,
        payment_id: str,
        customer_data: Dict[str, Any],
        webhook_token: str,
        **kwargs
    ) -> Dict[str, Any]:
        """
        Normaliza requisição de geração de PIX
        
        Todos os gateways recebem mesmo formato de entrada
        
        Args:
            gateway_type: Tipo do gateway
            amount: Valor em reais
            description: Descrição do produto
            payment_id: ID único do pagamento
            customer_data: Dados do cliente
            webhook_token: Token único para matching no webhook
            **kwargs: Parâmetros específicos do gateway
        
        Returns:
            Dict normalizado para o gateway
        """
        base_request = {
            'amount': amount,
            'description': description,
            'payment_id': payment_id,
            'customer_data': customer_data,
            'webhook_token': webhook_token  # ✅ SEMPRE incluir
        }
        
        # Adicionar parâmetros específicos do gateway
        base_request.update(kwargs)
        
        return base_request
    
    @staticmethod
    def normalize_generate_response(
        gateway_type: str,
        response: Optional[Dict[str, Any]],
        payment_id: str,
        webhook_token: str
    ) -> Optional[Dict[str, Any]]:
        """
        Normaliza resposta de geração de PIX
        
        Todos os gateways retornam mesmo formato
        
        Args:
            gateway_type: Tipo do gateway
            response: Resposta bruta do gateway
            payment_id: ID do pagamento
            webhook_token: Token para webhook
        
        Returns:
            Dict normalizado no formato padrão
        """
        if not response:
            return None
        
        # Normalizar campos comuns
        normalized = {
            # ✅ PIX Code (prioridade: pix_code > qr_code > emv)
            'pix_code': (
                response.get('pix_code') or
                response.get('qr_code') or
                response.get('emv') or
                response.get('pix_copy_paste') or
                None
            ),
            
            # ✅ QR Code URL (prioridade: qr_code_url > qr_code_base64)
            'qr_code_url': (
                response.get('qr_code_url') or
                response.get('qr_code_base64') or
                ''
            ),
            
            # ✅ Transaction ID (varia por gateway)
            'transaction_id': (
                response.get('transaction_id') or
                response.get('identifier') or
                response.get('id') or
                response.get('hash') or
                None
            ),
            
            # ✅ Transaction Hash (para matching)
            'transaction_hash': (
                response.get('gateway_hash') or
                response.get('transaction_hash') or
                response.get('hash') or
                response.get('transaction_id') or
                None
            ),
            
            # ✅ Webhook Token (sempre incluir)
            'webhook_token': webhook_token,
            
            # ✅ Producer Hash (Átomo Pay)
            'producer_hash': response.get('producer_hash'),
            
            # ✅ Reference (para matching)
            'reference': response.get('reference') or response.get('external_reference'),
            
            # ✅ Payment ID (sempre incluir)
            'payment_id': payment_id,
            
            # ✅ Status (se disponível)
            'status': response.get('status', 'pending'),
            
            # ✅ Erro (se disponível)
            'error': response.get('error')
        }
        
        # ✅ VALIDAÇÃO: pix_code é obrigatório
        if not normalized['pix_code']:
            logger.error(f"❌ [Adapter] Gateway {gateway_type} retornou sem pix_code")
            # Se status é 'refused', retornar mesmo assim (para webhook)
            if normalized['status'] == 'refused':
                logger.warning(f"⚠️ [Adapter] Transação recusada - retornando sem pix_code")
            else:
                return None
        
        # ✅ VALIDAÇÃO: transaction_id é obrigatório
        if not normalized['transaction_id']:
            logger.error(f"❌ [Adapter] Gateway {gateway_type} retornou sem transaction_id")
            return None
        
        return normalized
    
    @staticmethod
    def normalize_webhook_response(
        gateway_type: str,
        data: Dict[str, Any]
    ) -> Dict[str, Any]:
        """
        Normaliza resposta de webhook
        
        Todos os gateways retornam mesmo formato no webhook
        
        Args:
            gateway_type: Tipo do gateway
            data: Dados brutos do webhook
        
        Returns:
            Dict normalizado no formato padrão
        """
        # ✅ Extrair dados comuns (normalizar nomes de campos)
        normalized = {
            # ✅ Gateway Transaction ID
            'gateway_transaction_id': (
                data.get('gateway_transaction_id') or
                data.get('transaction_id') or
                data.get('id') or
                data.get('identifier') or
                data.get('uuid') or
                None
            ),
            
            # ✅ Gateway Hash
            'gateway_hash': (
                data.get('gateway_hash') or
                data.get('transaction_hash') or
                data.get('hash') or
                data.get('transaction_id') or
                None
            ),
            
            # ✅ Webhook Token (prioridade máxima)
            'webhook_token': (
                data.get('webhook_token') or
                data.get('webhook_id') or
                data.get('token') or
                None
            ),
            
            # ✅ External Reference
            'external_reference': (
                data.get('external_reference') or
                data.get('reference') or
                data.get('payment_id') or
                data.get('external_id') or
                None
            ),
            
            # ✅ Status (normalizar)
            'status': GatewayAdapter._normalize_status(
                gateway_type,
                data.get('status') or data.get('payment_status') or 'pending'
            ),
            
            # ✅ Amount (normalizar para float)
            'amount': GatewayAdapter._normalize_amount(
                data.get('amount') or data.get('value') or data.get('amount_paid') or 0
            ),
            
            # ✅ Producer Hash (Átomo Pay)
            'producer_hash': (
                data.get('producer_hash') or
                (data.get('producer', {}).get('hash') if isinstance(data.get('producer'), dict) else None) or
                None
            ),
            
            # ✅ Dados do pagador (opcional)
            'payer_name': data.get('payer_name') or data.get('name'),
            'payer_document': (
                data.get('payer_document') or
                data.get('payer_national_registration') or
                data.get('cpf') or
                data.get('document')
            ),
            'end_to_end_id': data.get('end_to_end_id') or data.get('e2e_id')
        }
        
        return normalized
    
    @staticmethod
    def _normalize_status(gateway_type: str, status: str) -> str:
        """
        Normaliza status do gateway para status interno
        
        Mapeia status específicos de cada gateway para:
        - 'paid': Pagamento confirmado
        - 'pending': Aguardando pagamento
        - 'failed': Falhou/cancelado/expirado
        """
        status_lower = str(status).lower()
        
        # Mapeamento por gateway
        if gateway_type == 'syncpay':
            if status_lower in ['paid_out', 'paid', 'confirmed', 'approved']:
                return 'paid'
            elif status_lower in ['cancelled', 'expired', 'failed']:
                return 'failed'
            else:
                return 'pending'
        
        elif gateway_type == 'pushynpay':
            if status_lower == 'paid':
                return 'paid'
            elif status_lower == 'expired':
                return 'failed'
            else:
                return 'pending'
        
        elif gateway_type == 'paradise':
            if status_lower in ['approved', 'paid', 'confirmed']:
                return 'paid'
            elif status_lower == 'refunded':
                return 'failed'
            else:
                return 'pending'
        
        elif gateway_type == 'wiinpay':
            if status_lower in ['paid', 'approved', 'confirmed']:
                return 'paid'
            elif status_lower in ['cancelled', 'canceled', 'failed', 'expired']:
                return 'failed'
            else:
                return 'pending'
        
        elif gateway_type == 'atomopay':
            if status_lower in ['paid', 'approved', 'confirmed']:
                return 'paid'
            elif status_lower in ['refused', 'failed', 'cancelled', 'canceled', 'expired']:
                return 'failed'
            else:
                return 'pending'
        
        # Fallback genérico
        if status_lower in ['paid', 'approved', 'confirmed', 'completed']:
            return 'paid'
        elif status_lower in ['failed', 'cancelled', 'canceled', 'expired', 'refunded', 'refused']:
            return 'failed'
        else:
            return 'pending'
    
    @staticmethod
    def _normalize_amount(amount: Any) -> float:
        """
        Normaliza valor para float (reais)
        
        Gateways podem retornar em centavos (int) ou reais (float)
        """
        try:
            amount_float = float(amount)
            # Se valor > 1000, provavelmente está em centavos
            if amount_float > 1000:
                return amount_float / 100.0
            return amount_float
        except (ValueError, TypeError):
            return 0.0
    
    @staticmethod
    def prepare_gateway_credentials(
        gateway_type: str,
        gateway: Any  # Gateway model
    ) -> Dict[str, Any]:
        """
        Prepara credenciais normalizadas para o gateway
        
        Args:
            gateway_type: Tipo do gateway
            gateway: Instância do modelo Gateway
        
        Returns:
            Dict com credenciais normalizadas
        """
        credentials = {}
        
        if gateway_type == 'syncpay':
            credentials = {
                'client_id': gateway.client_id,
                'client_secret': gateway.client_secret
            }
        
        elif gateway_type == 'pushynpay':
            credentials = {
                'api_key': gateway.api_key
            }
        
        elif gateway_type == 'paradise':
            credentials = {
                'api_key': gateway.api_key,
                'product_hash': gateway.product_hash,
                'offer_hash': gateway.offer_hash,
                'store_id': gateway.store_id,
                'split_percentage': gateway.split_percentage or 2.0
            }
        
        elif gateway_type == 'wiinpay':
            credentials = {
                'api_key': gateway.api_key,
                'split_user_id': gateway.split_user_id
            }
        
        elif gateway_type == 'atomopay':
            credentials = {
                'api_token': gateway.api_key,  # Átomo Pay usa api_token (salvo em api_key)
                'product_hash': gateway.product_hash
            }
        
        return credentials

