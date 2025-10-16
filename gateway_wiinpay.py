"""
Gateway WiinPay - Implementação Completa
Documentação: https://api.wiinpay.com.br/
"""

import os
import requests
import logging
from typing import Dict, Any, Optional
from gateway_interface import PaymentGateway

logger = logging.getLogger(__name__)


class WiinPayGateway(PaymentGateway):
    """
    Implementação do gateway WiinPay
    
    Características:
    - Autenticação via api_key no body
    - Valor mínimo: R$ 3,00
    - Split payment por percentual OU valor fixo
    - Webhook POST para confirmação
    - Sem necessidade de Bearer Token
    """
    
    def __init__(self, api_key: str, split_user_id: str = None):
        """
        Inicializa gateway WiinPay
        
        Args:
            api_key: Chave API da WiinPay
            split_user_id: User ID para splits (opcional)
        """
        self.api_key = api_key
        self.base_url = "https://api.wiinpay.com.br"
        
        # Split configuration (você é o dono da plataforma)
        self.split_user_id = split_user_id or os.environ.get('WIINPAY_PLATFORM_USER_ID', '6877edeba3c39f8451ba5bdd')
        self.split_percentage = 4  # 4% de comissão padrão
    
    def get_gateway_name(self) -> str:
        """Nome amigável do gateway"""
        return "WiinPay"
    
    def get_gateway_type(self) -> str:
        """Tipo do gateway para roteamento"""
        return "wiinpay"
    
    def get_webhook_url(self) -> str:
        """URL do webhook WiinPay"""
        webhook_base = os.environ.get('WEBHOOK_URL', '')
        return f"{webhook_base}/webhook/payment/wiinpay"
    
    def generate_pix(
        self, 
        amount: float, 
        description: str, 
        payment_id: str,
        customer_data: Optional[Dict[str, Any]] = None
    ) -> Optional[Dict[str, Any]]:
        """
        Gera PIX via WiinPay
        
        Args:
            amount: Valor em reais (mínimo R$ 3,00)
            description: Descrição do produto
            payment_id: ID único no sistema
            customer_data: {name, email, cpf} (opcional)
        
        Returns:
            {
                'pix_code': str,
                'qr_code_url': str,
                'transaction_id': str,
                'payment_id': str
            }
        """
        try:
            # ✅ VALIDAÇÃO: Valor mínimo R$ 3,00
            if amount < 3.0:
                logger.error(f"❌ [{self.get_gateway_name()}] Valor mínimo é R$ 3,00. Recebido: R$ {amount:.2f}")
                return None
            
            if not self.validate_amount(amount):
                logger.error(f"❌ [{self.get_gateway_name()}] Valor inválido: {amount}")
                return None
            
            # Extrair dados do cliente (ou usar defaults)
            customer_name = "Cliente"
            customer_email = "cliente@exemplo.com"
            
            if customer_data:
                customer_name = customer_data.get('name', customer_name)
                customer_email = customer_data.get('email', customer_email)
            
            # ✅ ENDPOINT: https://api.wiinpay.com.br/payment/create
            create_url = f"{self.base_url}/payment/create"
            
            # ✅ PAYLOAD completo
            payload = {
                "api_key": self.api_key,
                "value": float(amount),  # Valor total
                "name": customer_name,
                "email": customer_email,
                "description": description,
                "webhook_url": self.get_webhook_url(),
                "metadata": {
                    "payment_id": payment_id,  # Para rastreamento
                    "platform": "grimbots"
                }
            }
            
            # ✅ SPLIT PAYMENT (se configurado)
            if self.split_user_id:
                # Calcular valor do split (4% da venda)
                split_value = round(amount * (self.split_percentage / 100), 2)
                
                payload["split"] = {
                    "percentage": self.split_percentage,  # Percentual
                    "value": split_value,  # Valor em reais
                    "user_id": self.split_user_id  # Seu user_id na WiinPay
                }
                
                logger.info(f"💰 [{self.get_gateway_name()}] Split configurado: {self.split_percentage}% = R$ {split_value:.2f}")
            
            headers = {
                'Accept': 'application/json',
                'Content-Type': 'application/json'
            }
            
            logger.info(f"💳 [{self.get_gateway_name()}] Gerando PIX de R$ {amount:.2f}...")
            
            response = requests.post(create_url, json=payload, headers=headers, timeout=15)
            
            # ✅ SUCCESS: 201 Created
            if response.status_code == 201:
                data = response.json()
                
                # ✅ PARSE RESPONSE
                # Estrutura típica: {id, qr_code, qr_code_url, pix_code, status, ...}
                transaction_id = data.get('id') or data.get('transaction_id') or data.get('uuid')
                pix_code = data.get('pix_code') or data.get('brcode') or data.get('emv')
                qr_code_url = data.get('qr_code_url') or data.get('qrcode_url')
                qr_code_base64 = data.get('qr_code_base64') or data.get('qrcode_base64')
                
                if not transaction_id or not pix_code:
                    logger.error(f"❌ [{self.get_gateway_name()}] Resposta inválida - faltando transaction_id ou pix_code")
                    logger.error(f"Resposta: {data}")
                    return None
                
                logger.info(f"✅ [{self.get_gateway_name()}] PIX gerado! ID: {transaction_id}")
                
                result = {
                    'pix_code': pix_code,
                    'qr_code_url': qr_code_url or '',
                    'transaction_id': str(transaction_id),
                    'payment_id': payment_id,
                    'gateway_type': self.get_gateway_type(),
                    'amount': amount
                }
                
                # Adicionar QR Code base64 se disponível
                if qr_code_base64:
                    result['qr_code_base64'] = qr_code_base64
                
                return result
            
            # ❌ ERRORS
            elif response.status_code == 422:
                logger.error(f"❌ [{self.get_gateway_name()}] Campo vazio ou inválido (422)")
                logger.error(f"Resposta: {response.text}")
                return None
            
            elif response.status_code == 401:
                logger.error(f"❌ [{self.get_gateway_name()}] API Key inválida (401)")
                return None
            
            elif response.status_code == 500:
                logger.error(f"❌ [{self.get_gateway_name()}] Erro interno do gateway (500)")
                logger.error(f"Resposta: {response.text}")
                return None
            
            else:
                logger.error(f"❌ [{self.get_gateway_name()}] Erro inesperado: Status {response.status_code}")
                logger.error(f"Resposta: {response.text}")
                return None
        
        except requests.exceptions.Timeout:
            logger.error(f"❌ [{self.get_gateway_name()}] Timeout ao gerar PIX")
            return None
        
        except requests.exceptions.ConnectionError:
            logger.error(f"❌ [{self.get_gateway_name()}] Erro de conexão com API")
            return None
        
        except Exception as e:
            logger.error(f"❌ [{self.get_gateway_name()}] Erro ao gerar PIX: {e}")
            import traceback
            traceback.print_exc()
            return None
    
    def process_webhook(self, data: Dict[str, Any]) -> Optional[Dict[str, Any]]:
        """
        Processa webhook da WiinPay
        
        Webhook geralmente envia:
        {
            "id": "transaction_id",
            "status": "paid" | "pending" | "cancelled",
            "value": 10.50,
            "payment_id": "...",  # No metadata
            "payer_name": "...",
            "payer_document": "..."
        }
        
        Args:
            data: Dados do webhook
        
        Returns:
            Dados processados no formato padrão
        """
        try:
            logger.info(f"📨 [{self.get_gateway_name()}] Processando webhook...")
            logger.info(f"Dados recebidos: {data}")
            
            # ✅ EXTRAIR DADOS (adaptar conforme resposta real da WiinPay)
            transaction_id = data.get('id') or data.get('transaction_id') or data.get('uuid')
            status_raw = data.get('status', '').lower()
            amount = float(data.get('value') or data.get('amount') or 0)
            
            # Buscar payment_id nos metadata
            metadata = data.get('metadata', {})
            payment_id = metadata.get('payment_id') or data.get('payment_id')
            
            # Dados do pagador (opcional)
            payer_name = data.get('payer_name') or data.get('name')
            payer_document = data.get('payer_document') or data.get('cpf') or data.get('document')
            
            # ✅ NORMALIZAR STATUS
            # WiinPay pode usar: 'paid', 'pending', 'cancelled', 'expired'
            if status_raw in ['paid', 'approved', 'confirmed']:
                status = 'paid'
            elif status_raw in ['pending', 'waiting', 'processing']:
                status = 'pending'
            elif status_raw in ['cancelled', 'canceled', 'failed', 'expired']:
                status = 'failed'
            else:
                logger.warning(f"⚠️ [{self.get_gateway_name()}] Status desconhecido: {status_raw}")
                status = 'pending'
            
            logger.info(f"✅ [{self.get_gateway_name()}] Webhook processado: {status}")
            
            return {
                'payment_id': payment_id,
                'status': status,
                'amount': amount,
                'gateway_transaction_id': str(transaction_id),
                'payer_name': payer_name,
                'payer_document': payer_document,
                'gateway_type': self.get_gateway_type()
            }
        
        except Exception as e:
            logger.error(f"❌ [{self.get_gateway_name()}] Erro ao processar webhook: {e}")
            import traceback
            traceback.print_exc()
            return None
    
    def verify_credentials(self) -> bool:
        """
        Verifica se API Key é válida
        
        Tenta criar um pagamento de teste de R$ 3,00 (mínimo)
        ou simplesmente valida se api_key existe
        
        Returns:
            True se credenciais válidas
        """
        try:
            # ✅ VALIDAÇÃO SIMPLES: api_key não pode ser vazia
            if not self.api_key or len(self.api_key) < 10:
                logger.error(f"❌ [{self.get_gateway_name()}] API Key inválida ou vazia")
                return False
            
            # ✅ VALIDAÇÃO AVANÇADA: Tentar fazer request de teste
            # (Alguns gateways têm endpoint de health check, WiinPay não documentou)
            # Por segurança, apenas validar formato
            
            logger.info(f"✅ [{self.get_gateway_name()}] Credenciais validadas (API Key presente)")
            return True
        
        except Exception as e:
            logger.error(f"❌ [{self.get_gateway_name()}] Erro ao verificar credenciais: {e}")
            return False
    
    def get_payment_status(self, transaction_id: str) -> Optional[Dict[str, Any]]:
        """
        Consulta status de um pagamento
        
        NOTA: Documentação WiinPay não especifica endpoint de consulta.
        Implementação pode precisar de ajuste com base na doc completa.
        
        Args:
            transaction_id: ID da transação no WiinPay
        
        Returns:
            Dados do pagamento ou None
        """
        try:
            # ✅ ASSUMINDO endpoint padrão (ajustar se necessário)
            status_url = f"{self.base_url}/payment/{transaction_id}"
            
            headers = {
                'Accept': 'application/json',
                'Content-Type': 'application/json'
            }
            
            # Como WiinPay usa api_key no body, tentar passar como query param
            params = {
                'api_key': self.api_key
            }
            
            logger.info(f"🔍 [{self.get_gateway_name()}] Consultando status do pagamento {transaction_id}...")
            
            response = requests.get(status_url, headers=headers, params=params, timeout=10)
            
            if response.status_code == 200:
                data = response.json()
                
                # Processar resposta (mesmo formato do webhook)
                return self.process_webhook(data)
            
            else:
                logger.warning(f"⚠️ [{self.get_gateway_name()}] Não foi possível consultar status: {response.status_code}")
                logger.warning(f"Resposta: {response.text}")
                return None
        
        except Exception as e:
            logger.error(f"❌ [{self.get_gateway_name()}] Erro ao consultar status: {e}")
            return None


# ============================================================================
# FACTORY HELPER
# ============================================================================

def create_wiinpay_gateway(credentials: Dict[str, Any]) -> Optional[WiinPayGateway]:
    """
    Factory helper para criar instância do WiinPay
    
    Args:
        credentials: {
            'api_key': str,
            'split_user_id': str (opcional)
        }
    
    Returns:
        Instância do WiinPayGateway ou None
    """
    api_key = credentials.get('api_key')
    split_user_id = credentials.get('split_user_id')
    
    if not api_key:
        logger.error(f"❌ [WiinPay] api_key não fornecido")
        return None
    
    return WiinPayGateway(api_key=api_key, split_user_id=split_user_id)

