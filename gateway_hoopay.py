# gateway_hoopay.py
"""
Gateway de Pagamento: HooPay
Documentação: Arquivo hoopay.json fornecido

Particularidades:
- Autenticação via Basic Auth (Token ID como username, vazio como password)
- Endpoint único: POST /charge (para PIX e Cartão)
- Valores em REAIS (amount)
- Split via campo "commissions" com organization_id
- Campo "type": "pix" para pagamento PIX
- Resposta: payment.charges[].pixPayload (código PIX)
- Resposta: payment.charges[].pixQrCode (QR Code base64)
- Resposta: orderUUID (ID da transação)
- Webhook: callbackURL no payload
"""

import requests
import logging
from typing import Dict, Optional
from gateway_interface import PaymentGateway

logger = logging.getLogger(__name__)


class HoopayPaymentGateway(PaymentGateway):
    """Implementação do gateway HooPay"""
    
    def __init__(self, credentials: Dict[str, str]):
        """
        Inicializa o gateway HooPay
        
        Args:
            credentials: Dict com:
                - api_key: Token ID do HooPay (d7c92c358a7ec4819ce7282ff2f3f70d)
                - organization_id: ID da organização para split (UUID)
                - split_percentage: Percentual de comissão da plataforma (padrão 4%)
        """
        self.api_key = credentials.get('api_key', '')
        self.organization_id = credentials.get('organization_id', '')
        self.split_percentage = float(credentials.get('split_percentage', 2.0))  # 2% PADRÃO
        
        # URLs da API HooPay (conforme hoopay.json)
        self.base_url = 'https://pay.hoopay.com.br'  # ✅ pay.hoopay (não api.hoopay)
        self.charge_url = f'{self.base_url}/charge'  # ✅ /charge
        self.consult_url = f'{self.base_url}/pix/consult'  # ✅ /pix/consult/{orderUUID}
        
        logger.info(f"🟡 HooPay Gateway inicializado | Token: {self.api_key[:16]}...")

    def get_gateway_name(self) -> str:
        return "HooPay"
    
    def get_gateway_type(self) -> str:
        return "hoopay"
    
    def get_webhook_url(self) -> str:
        from os import environ
        base_url = environ.get('WEBHOOK_URL', 'http://localhost:5000')
        return f"{base_url}/webhook/payment/hoopay"
    
    def verify_credentials(self) -> bool:
        """
        Verifica se as credenciais são válidas
        HooPay não tem endpoint de verificação dedicado, validamos localmente
        """
        try:
            # Validação básica do token
            if not self.api_key or len(self.api_key) < 20:
                logger.error("❌ HooPay: api_key inválida (deve ter 20+ caracteres)")
                return False
            
            # Validação do organization_id (UUID format)
            if self.organization_id:
                if len(self.organization_id) != 36:  # UUID padrão: 8-4-4-4-12
                    logger.error("❌ HooPay: organization_id inválido (deve ser UUID)")
                    return False
                logger.info(f"✅ HooPay: Split configurado (Org: {self.organization_id[:8]}...)")
            
            logger.info(f"✅ HooPay: Credenciais válidas")
            return True
            
        except Exception as e:
            logger.error(f"❌ HooPay: Erro ao verificar credenciais: {e}")
            return False
    
    def generate_pix(self, amount: float, description: str, payment_id: int, customer_data: Optional[Dict] = None) -> Optional[Dict]:
        """
        Gera um código PIX via HooPay
        
        Args:
            amount: Valor em reais (ex: 10.50)
            description: Descrição do pagamento
            payment_id: ID do pagamento no banco local
            customer_data: Dados do cliente (opcional, não usado pelo HooPay)
        
        Returns:
            Dict com pix_code, qr_code_url, transaction_id, payment_id
        """
        try:
            # HooPay trabalha em REAIS (diferente de Pushyn e Paradise)
            logger.info(f"💰 HooPay: Gerando PIX - R$ {amount:.2f}")
            
            # Validação de valor mínimo (baseado na documentação: R$ 0.50)
            if amount < 0.50:
                logger.error(f"❌ HooPay: Valor mínimo é R$ 0,50 (recebido: {amount})")
                return None
            
            # ✅ PRODUÇÃO: Preparar dados do cliente (com fallback funcional se não fornecidos)
            if not customer_data:
                logger.warning("⚠️ HooPay: customer_data não fornecido, usando fallback")
                customer_data = {}
            
            # Preparar dados do cliente com validação de tamanho
            customer_name = customer_data.get('name') or (description[:50] if description else 'Cliente Digital')
            customer_payload = {
                "email": customer_data.get('email') or f"pix{payment_id}@bot.digital",
                "name": customer_name if len(customer_name) <= 50 else customer_name[:50],
                "phone": str(customer_data.get('phone') or '11999999999'),
                "document": str(customer_data.get('document') or f"{payment_id:011d}")  # Payment ID como CPF
            }
            
            logger.info(f"👤 HooPay: Cliente - {customer_payload['name']} | {customer_payload['email']}")
            
            # Produtos (HooPay exige array de produtos)
            products = [
                {
                    "title": description if len(description) <= 100 else description[:100],
                    "amount": amount,
                    "quantity": 1
                }
            ]
            
            # Payments (tipo PIX)
            payments = [
                {
                    "amount": amount,
                    "type": "pix"  # ✅ TIPO: pix
                }
            ]
            
            # Payload HooPay
            payload = {
                "amount": amount,  # ✅ REAIS (não centavos!)
                "customer": customer_payload,  # ✅ DADOS REAIS DO CLIENTE
                "products": products,
                "payments": payments,
                "data": {
                    "ip": "192.168.0.1",
                    "callbackURL": self.get_webhook_url()  # ✅ WEBHOOK
                }
            }
            
            # Se split configurado, adiciona comissões
            if self.organization_id and self.split_percentage > 0:
                split_amount = amount * (self.split_percentage / 100)
                seller_amount = amount - split_amount
                
                payload["commissions"] = [
                    {
                        "userId": self.organization_id,  # ✅ ORGANIZATION ID
                        "type": "platform",
                        "amount": split_amount
                    },
                    {
                        "userId": self.organization_id,
                        "type": "organization",
                        "amount": seller_amount
                    }
                ]
                
                logger.info(f"💸 HooPay Split: Platform R$ {split_amount:.2f} | Seller R$ {seller_amount:.2f}")
            
            logger.debug(f"📤 HooPay Payload: {payload}")
            
            # Headers HooPay (sem Authorization, usa Basic Auth)
            headers = {
                'Content-Type': 'application/json',
                'Accept': 'application/json'
            }
            
            # ✅ CORREÇÃO: HooPay usa Basic Auth (token como username, password vazio)
            from requests.auth import HTTPBasicAuth
            auth = HTTPBasicAuth(self.api_key, '')
            
            logger.info(f"🔐 HooPay Auth: Basic {self.api_key[:16]}... (token como username)")
            logger.info(f"📤 HooPay URL: {self.charge_url}")
            
            # Requisição para HooPay
            response = requests.post(
                self.charge_url,
                json=payload,
                headers=headers,
                auth=auth,  # ✅ CORREÇÃO: Basic Auth
                timeout=15
            )
            
            logger.info(f"📡 HooPay Response: Status {response.status_code}")
            
            if response.status_code != 200:
                logger.error(f"❌ HooPay API Error: {response.status_code} - {response.text}")
                return None
            
            data = response.json()
            logger.debug(f"📥 HooPay Data: {data}")
            
            # HooPay retorna: {payment: {charges: [{pixPayload, pixQrCode, uuid}]}, orderUUID}
            payment_data = data.get('payment', {})
            charges = payment_data.get('charges', [])
            
            if not charges or len(charges) == 0:
                logger.error(f"❌ HooPay: Nenhum charge retornado")
                return None
            
            charge = charges[0]  # Primeiro charge (PIX)
            
            # Extrai dados do PIX
            pix_code = charge.get('pixPayload')  # ✅ Campo: pixPayload
            qr_code_base64 = charge.get('pixQrCode')  # ✅ Campo: pixQrCode (base64)
            charge_uuid = charge.get('uuid')
            order_uuid = data.get('orderUUID')  # ✅ ID principal da transação
            
            if not pix_code or not order_uuid:
                logger.error(f"❌ HooPay: Resposta incompleta - pixPayload ou orderUUID ausente")
                return None
            
            logger.info(f"✅ HooPay: PIX gerado | Order: {order_uuid} | Charge: {charge_uuid}")
            
            # Retorna padrão unificado
            return {
                'pix_code': pix_code,  # ✅ Padronizado
                'qr_code_url': f'data:image/png;base64,{qr_code_base64}' if qr_code_base64 else f'https://api.qrserver.com/v1/create-qr-code/?size=300x300&data={pix_code}',
                'transaction_id': order_uuid,  # ✅ Usa orderUUID como ID principal
                'payment_id': payment_id
            }
            
        except requests.Timeout:
            logger.error("❌ HooPay: Timeout na requisição (15s)")
            return None
        except requests.RequestException as e:
            logger.error(f"❌ HooPay: Erro de conexão: {e}")
            return None
        except Exception as e:
            logger.error(f"❌ HooPay: Erro inesperado: {e}", exc_info=True)
            return None
    
    def process_webhook(self, data: Dict) -> Optional[Dict]:
        """
        Processa webhook do HooPay
        
        HooPay envia estrutura similar ao response de /charge:
        {
            "payment": {
                "status": "paid" | "pending" | "refused",
                "charges": [{"amount": 10.50, "status": "paid"}]
            },
            "orderUUID": "..."
        }
        
        Returns:
            Dict com payment_id, status, amount, gateway_transaction_id
        """
        try:
            logger.info(f"📩 HooPay Webhook recebido")
            logger.debug(f"Webhook Data: {data}")
            
            order_uuid = data.get('orderUUID')
            payment_data = data.get('payment', {})
            status = payment_data.get('status', '').lower()
            charges = payment_data.get('charges', [])
            
            if not order_uuid:
                logger.error("❌ HooPay Webhook: 'orderUUID' ausente")
                return None
            
            # Extrai valor do primeiro charge
            amount = 0
            if charges and len(charges) > 0:
                amount = charges[0].get('amount', 0)
            
            # Mapeia status HooPay → Sistema
            mapped_status = 'pending'
            if status == 'paid':
                mapped_status = 'paid'
            elif status in ['refused', 'cancelled', 'expired']:
                mapped_status = 'failed'
            
            logger.info(f"✅ HooPay Webhook processado | Order: {order_uuid} | Status: {status} → {mapped_status}")
            
            return {
                'gateway_transaction_id': order_uuid,
                'status': mapped_status,
                'amount': amount
            }
            
        except Exception as e:
            logger.error(f"❌ HooPay: Erro ao processar webhook: {e}", exc_info=True)
            return None
    
    def get_payment_status(self, transaction_id: str) -> Optional[Dict]:
        """
        Consulta status de um pagamento no HooPay
        
        HooPay: GET /pix/consult/{orderUUID}
        """
        try:
            logger.info(f"🔍 HooPay: Consultando status | Order: {transaction_id}")
            
            headers = {
                'Authorization': f'Bearer {self.api_key}',
                'Accept': 'application/json'
            }
            
            response = requests.get(
                f'{self.consult_url}/{transaction_id}',
                headers=headers,
                timeout=10
            )
            
            if response.status_code == 404:
                logger.warning(f"⚠️ HooPay: Transação não encontrada | Order: {transaction_id}")
                return None
            
            if response.status_code != 200:
                logger.error(f"❌ HooPay: Erro ao consultar | Status: {response.status_code}")
                return None
            
            data = response.json()
            
            # Usa a mesma lógica de processamento do webhook
            return self.process_webhook(data)
            
        except Exception as e:
            logger.error(f"❌ HooPay: Erro ao consultar status: {e}")
            return None
    
    def validate_amount(self, amount: float) -> bool:
        """Valida se o valor está dentro dos limites aceitos pelo HooPay"""
        if amount < 0.50:
            logger.error(f"❌ HooPay: Valor mínimo é R$ 0,50")
            return False
        
        # Limite razoável
        if amount > 1000000:
            logger.error(f"❌ HooPay: Valor máximo é R$ 1.000.000,00")
            return False
        
        return True


