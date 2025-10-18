"""
Gateway SyncPay - Implementação Isolada
Documentação: https://syncpay.apidog.io/
"""

import os
import requests
import logging
from typing import Dict, Any, Optional
from gateway_interface import PaymentGateway

logger = logging.getLogger(__name__)


class SyncPayGateway(PaymentGateway):
    """
    Implementação do gateway SyncPay
    
    Características:
    - Autenticação via Bearer Token (expires 1h)
    - Split payment por percentual
    - Webhook para confirmação de pagamento
    """
    
    def __init__(self, client_id: str, client_secret: str):
        """
        Inicializa gateway SyncPay
        
        Args:
            client_id: UUID do client ID da SyncPay
            client_secret: UUID do client secret da SyncPay
        """
        self.client_id = client_id
        self.client_secret = client_secret
        self.base_url = "https://api.syncpayments.com.br"
        self.split_user_id = os.environ.get('PLATFORM_SPLIT_USER_ID', '')
        self.split_percentage = 2  # 2% de comissão PADRÃO
        self._cached_token = None
        self._token_expires_at = None
    
    def get_gateway_name(self) -> str:
        """Nome amigável do gateway"""
        return "SyncPay"
    
    def get_gateway_type(self) -> str:
        """Tipo do gateway para roteamento"""
        return "syncpay"
    
    def get_webhook_url(self) -> str:
        """URL do webhook SyncPay"""
        webhook_base = os.environ.get('WEBHOOK_URL', '')
        return f"{webhook_base}/webhook/payment/syncpay"
    
    def _generate_bearer_token(self) -> Optional[str]:
        """
        Gera Bearer Token da SyncPay (válido por 1 hora)
        
        Returns:
            Access token ou None se falhar
        """
        try:
            auth_url = f"{self.base_url}/api/partner/v1/auth-token"
            
            payload = {
                "client_id": self.client_id,
                "client_secret": self.client_secret
            }
            
            headers = {
                'Content-Type': 'application/json'
            }
            
            logger.info(f"🔑 [{self.get_gateway_name()}] Gerando Bearer Token...")
            
            response = requests.post(auth_url, json=payload, headers=headers, timeout=10)
            
            if response.status_code == 200:
                data = response.json()
                access_token = data.get('access_token')
                expires_in = data.get('expires_in', 3600)
                logger.info(f"✅ [{self.get_gateway_name()}] Bearer Token gerado! Válido por {expires_in}s")
                return access_token
            else:
                logger.error(f"❌ [{self.get_gateway_name()}] Erro ao gerar token: Status {response.status_code}")
                logger.error(f"Resposta: {response.text}")
                return None
                
        except Exception as e:
            logger.error(f"❌ [{self.get_gateway_name()}] Erro ao gerar Bearer Token: {e}")
            return None
    
    def generate_pix(
        self, 
        amount: float, 
        description: str, 
        payment_id: str,
        customer_data: Optional[Dict[str, Any]] = None
    ) -> Optional[Dict[str, Any]]:
        """
        Gera PIX via SyncPay
        
        Endpoint: POST /api/partner/v1/cash-in
        """
        try:
            # Validar valor
            if not self.validate_amount(amount):
                logger.error(f"❌ [{self.get_gateway_name()}] Valor inválido: {amount}")
                return None
            
            # 1. Gerar Bearer Token
            bearer_token = self._generate_bearer_token()
            if not bearer_token:
                logger.error(f"❌ [{self.get_gateway_name()}] Falha ao obter Bearer Token")
                return None
            
            # 2. Preparar dados do cliente
            if not customer_data:
                customer_data = {
                    "name": description,
                    "cpf": "00000000000",
                    "email": "cliente@bot.com",
                    "phone": "11999999999"
                }
            
            # 3. Configurar split
            split_config = []
            if self.split_user_id:
                split_config.append({
                    "percentage": self.split_percentage,
                    "user_id": self.split_user_id
                })
                logger.info(f"💰 [{self.get_gateway_name()}] Split configurado: {self.split_percentage}% para {self.split_user_id[:8]}...")
            else:
                logger.warning(f"⚠️ [{self.get_gateway_name()}] PLATFORM_SPLIT_USER_ID não configurado. Split desabilitado.")
            
            # 4. Criar payload
            cashin_url = f"{self.base_url}/api/partner/v1/cash-in"
            
            headers = {
                'Authorization': f'Bearer {bearer_token}',
                'Content-Type': 'application/json'
            }
            
            payload = {
                "amount": float(amount),
                "description": description,
                "webhook_url": self.get_webhook_url(),
                "client": customer_data,
                "split": split_config
            }
            
            logger.info(f"📤 [{self.get_gateway_name()}] Criando Cash-In (R$ {amount:.2f})...")
            
            # 5. Fazer requisição
            response = requests.post(cashin_url, json=payload, headers=headers, timeout=15)
            
            # 6. Processar resposta
            if response.status_code == 200:
                data = response.json()
                pix_code = data.get('pix_code')
                identifier = data.get('identifier')
                
                if not pix_code:
                    logger.error(f"❌ [{self.get_gateway_name()}] Resposta não contém pix_code: {data}")
                    return None
                
                logger.info(f"✅ [{self.get_gateway_name()}] PIX gerado com sucesso!")
                logger.info(f"📝 Transaction ID: {identifier}")
                
                # Gerar URL do QR Code
                import urllib.parse
                qr_code_url = f'https://api.qrserver.com/v1/create-qr-code/?size=400x400&data={urllib.parse.quote(pix_code)}'
                
                return {
                    'pix_code': pix_code,
                    'qr_code_url': qr_code_url,
                    'transaction_id': identifier,
                    'payment_id': payment_id,
                    'expires_at': None
                }
            else:
                logger.error(f"❌ [{self.get_gateway_name()}] Erro: Status {response.status_code}")
                logger.error(f"Resposta: {response.text}")
                return None
                
        except Exception as e:
            logger.error(f"❌ [{self.get_gateway_name()}] Erro ao gerar PIX: {e}")
            import traceback
            traceback.print_exc()
            return None
    
    def process_webhook(self, data: Dict[str, Any]) -> Optional[Dict[str, Any]]:
        """
        Processa webhook SyncPay
        
        Campos esperados:
        - identifier: ID da transação
        - status: Status do pagamento (paid, cancelled, expired, etc)
        - amount: Valor do pagamento
        """
        try:
            identifier = data.get('identifier') or data.get('id')
            status = data.get('status', '').lower()
            amount = data.get('amount')
            
            if not identifier:
                logger.error(f"❌ [{self.get_gateway_name()}] Webhook sem identifier")
                return None
            
            # Mapear status da SyncPay para status interno
            mapped_status = 'pending'
            if status in ['paid', 'confirmed', 'approved']:
                mapped_status = 'paid'
            elif status in ['cancelled', 'expired', 'failed']:
                mapped_status = 'failed'
            
            logger.info(f"📥 [{self.get_gateway_name()}] Webhook recebido: {identifier} - Status: {status} → {mapped_status}")
            
            return {
                'payment_id': identifier,
                'status': mapped_status,
                'amount': amount,
                'gateway_transaction_id': identifier
            }
            
        except Exception as e:
            logger.error(f"❌ [{self.get_gateway_name()}] Erro ao processar webhook: {e}")
            return None
    
    def verify_credentials(self) -> bool:
        """
        Verifica se credenciais SyncPay são válidas
        
        Returns:
            True se conseguir gerar Bearer Token, False caso contrário
        """
        try:
            token = self._generate_bearer_token()
            return token is not None
        except Exception as e:
            logger.error(f"❌ [{self.get_gateway_name()}] Erro ao verificar credenciais: {e}")
            return False
    
    def get_payment_status(self, transaction_id: str) -> Optional[Dict[str, Any]]:
        """
        Consulta status de pagamento na SyncPay
        
        Nota: Endpoint de consulta não está documentado na SyncPay.
        Implementar quando disponível.
        """
        logger.warning(f"⚠️ [{self.get_gateway_name()}] Consulta de status não implementada (endpoint não documentado)")
        return None


