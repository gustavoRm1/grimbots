"""
Gateway WiinPay - Implementação Completa
Documentação: https://api-v2.wiinpay.com.br/
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
    
    def __init__(self, api_key: str, split_user_id: str = None, split_percentage: float = None):
        """
        Inicializa gateway WiinPay
        
        Args:
            api_key: Chave API da WiinPay
            split_user_id: User ID para splits (opcional)
            split_percentage: Percentual de split (opcional, padrão 2%). ✅ RANKING: Pode ser taxa premium do Top 3
        """
        self.api_key = api_key
        self.base_url = "https://api-v2.wiinpay.com.br"
        
        # ✅ SPLIT CONFIGURATION - Plataforma recebe split de todas as vendas
        # Prioridade: split_user_id fornecido > env > padrão da plataforma
        # ID da plataforma na WiinPay: 68ffcc91e23263e0a01fffa4
        # ✅ CORREÇÃO: Se ID antigo foi fornecido, usar novo ID
        old_split_id = '6877edeba3c39f8451ba5bdd'
        new_split_id = '68ffcc91e23263e0a01fffa4'
        
        if split_user_id and split_user_id.strip() and split_user_id != old_split_id:
            self.split_user_id = split_user_id.strip()
        else:
            # Usar novo ID se split_user_id é None, vazio ou antigo
            self.split_user_id = os.environ.get('WIINPAY_PLATFORM_USER_ID', new_split_id)
            if split_user_id == old_split_id:
                logger.warning(f"⚠️ [{self.get_gateway_name()}] split_user_id antigo detectado ({old_split_id}), usando novo ID: {new_split_id}")
        
        # ✅ RANKING V2.0: split_percentage pode ser taxa premium do Top 3
        # Prioridade: split_percentage fornecido > padrão 2%
        if split_percentage is not None:
            self.split_percentage = float(split_percentage)
            logger.info(f"✅ [{self.get_gateway_name()}] Taxa premium aplicada: {self.split_percentage}% (pode ser do ranking)")
        else:
            self.split_percentage = 2.0  # 2% de comissão PADRÃO para a plataforma
        
        # ✅ GARANTIR: Split sempre configurado para plataforma receber comissão
        if not self.split_user_id or len(self.split_user_id.strip()) == 0:
            logger.warning(f"⚠️ [{self.get_gateway_name()}] split_user_id não configurado, usando padrão da plataforma")
            self.split_user_id = '68ffcc91e23263e0a01fffa4'
        
        logger.info(f"✅ [{self.get_gateway_name()}] Split configurado: {self.split_percentage}% para user_id {self.split_user_id}")
    
    def get_gateway_name(self) -> str:
        """Nome amigável do gateway"""
        return "WiinPay"
    
    def get_gateway_type(self) -> str:
        """Tipo do gateway para roteamento"""
        return "wiinpay"
    
    def get_webhook_url(self) -> str:
        """URL do webhook WiinPay"""
        webhook_base = os.environ.get('WEBHOOK_URL', 'https://app.grimbots.online')
        # Garantir que não tem barra dupla
        if webhook_base.endswith('/'):
            webhook_base = webhook_base[:-1]
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
            # ✅ VALIDAÇÃO: Valor mínimo R$ 3,00 (conforme documentação)
            if amount < 3.0:
                logger.error(f"❌ [{self.get_gateway_name()}] Valor mínimo é R$ 3,00. Recebido: R$ {amount:.2f}")
                return None
            
            if not self.validate_amount(amount):
                logger.error(f"❌ [{self.get_gateway_name()}] Valor inválido: {amount}")
                return None
            
            # ✅ VALIDAÇÃO: API Key obrigatória
            if not self.api_key or len(self.api_key.strip()) == 0:
                logger.error(f"❌ [{self.get_gateway_name()}] API Key não configurada")
                return None
            
            # Extrair dados do cliente (ou usar defaults)
            customer_name = "Cliente"
            customer_email = "cliente@exemplo.com"
            
            if customer_data:
                customer_name = customer_data.get('name', customer_name) or "Cliente"
                customer_email = customer_data.get('email', customer_email) or "cliente@exemplo.com"
            
            # ✅ VALIDAÇÃO: Campos obrigatórios
            if not customer_name or not customer_email:
                logger.error(f"❌ [{self.get_gateway_name()}] Nome ou email do cliente não fornecido")
                return None
            
            if not description:
                description = "Pagamento via Telegram Bot"
            
            # ✅ VALIDAÇÃO: Webhook URL
            webhook_url = self.get_webhook_url()
            if not webhook_url or not webhook_url.startswith('http'):
                logger.error(f"❌ [{self.get_gateway_name()}] Webhook URL inválida: {webhook_url}")
                return None
            
            # ✅ ENDPOINT: https://api-v2.wiinpay.com.br/payment/create (conforme documentação)
            create_url = f"{self.base_url}/payment/create"
            
            # ✅ PAYLOAD completo (conforme documentação WiinPay)
            payload = {
                "api_key": self.api_key.strip(),  # Chave API no body (não no header)
                "value": float(amount),  # Valor em reais (mínimo R$ 3,00)
                "name": customer_name,  # Nome do pagador
                "email": customer_email,  # Email do pagador
                "description": description,  # Descrição do pagamento
                "webhook_url": webhook_url  # URL do webhook (POST)
            }
            
            # ✅ METADATA (opcional conforme documentação)
            metadata = {
                "payment_id": payment_id,  # Para rastreamento
                "platform": "grimbots"
            }
            payload["metadata"] = metadata
            
            # ✅ SPLIT PAYMENT - SEMPRE configurado para plataforma receber comissão
            # ✅ RANKING V2.0: split_percentage pode ser taxa premium do Top 3 (ex: 1.5%, 1%, 0.5%)
            # Split é obrigatório: plataforma recebe comissão de todas as vendas dos usuários
            # ✅ CORREÇÃO: Garantir que split_user_id está usando o ID correto (não o antigo)
            old_split_id = '6877edeba3c39f8451ba5bdd'
            new_split_id = '68ffcc91e23263e0a01fffa4'
            
            if not self.split_user_id or len(self.split_user_id.strip()) == 0 or self.split_user_id == old_split_id:
                if self.split_user_id == old_split_id:
                    logger.warning(f"⚠️ [{self.get_gateway_name()}] split_user_id antigo detectado ({old_split_id}), atualizando para: {new_split_id}")
                else:
                    logger.warning(f"⚠️ [{self.get_gateway_name()}] split_user_id não configurado, usando padrão: {new_split_id}")
                self.split_user_id = new_split_id
            
            # ✅ RANKING: Calcular valor do split usando split_percentage (pode ser taxa premium)
            split_value = round(amount * (self.split_percentage / 100), 2)
            
            # ✅ Garantir que split_value é no mínimo 0.01 (centavo mínimo)
            if split_value < 0.01:
                split_value = 0.01
            
            # ✅ SEMPRE adicionar split ao payload (conforme documentação WiinPay)
            payload["split"] = {
                "percentage": self.split_percentage,  # ✅ RANKING: Percentual (pode ser premium: 1.5%, 1%, 0.5%, ou padrão 2%)
                "value": split_value,  # Valor em reais
                "user_id": self.split_user_id  # ID da plataforma na WiinPay: 68ffcc91e23263e0a01fffa4
            }
            
            # ✅ LOG: Indicar se é taxa premium (diferente de 2%)
            if self.split_percentage != 2.0:
                logger.info(f"💰 [{self.get_gateway_name()}] Split PREMIUM configurado: {self.split_percentage}% = R$ {split_value:.2f} (user_id: {self.split_user_id}) - TAXA DO RANKING")
            else:
                logger.info(f"💰 [{self.get_gateway_name()}] Split configurado para plataforma: {self.split_percentage}% = R$ {split_value:.2f} (user_id: {self.split_user_id})")
            
            headers = {
                'Accept': 'application/json',
                'Content-Type': 'application/json'
            }
            
            logger.info(f"💳 [{self.get_gateway_name()}] Gerando PIX de R$ {amount:.2f}...")
            logger.info(f"📤 [{self.get_gateway_name()}] URL: {create_url}")
            logger.info(f"📤 [{self.get_gateway_name()}] Payload: {payload}")
            logger.info(f"📤 [{self.get_gateway_name()}] Headers: {headers}")
            
            response = requests.post(create_url, json=payload, headers=headers, timeout=15)
            
            logger.info(f"📡 [{self.get_gateway_name()}] Status: {response.status_code}")
            logger.info(f"📡 [{self.get_gateway_name()}] Response Headers: {dict(response.headers)}")
            logger.info(f"📡 [{self.get_gateway_name()}] Response Body: {response.text}")
            
            # ✅ SUCCESS: 201 Created (conforme documentação)
            if response.status_code == 201:
                try:
                    response_data = response.json()
                    logger.info(f"📥 [{self.get_gateway_name()}] Response JSON: {response_data}")
                except Exception as e:
                    logger.error(f"❌ [{self.get_gateway_name()}] Erro ao parsear JSON: {e}")
                    logger.error(f"Response text: {response.text}")
                    return None
                
                # ✅ CORREÇÃO: WiinPay pode retornar dentro de 'data' wrapper ou diretamente
                if 'data' in response_data:
                    data = response_data['data']
                    logger.info(f"📥 [{self.get_gateway_name()}] Dados extraídos de 'data' wrapper: {data}")
                else:
                    data = response_data
                    logger.info(f"📥 [{self.get_gateway_name()}] Dados diretos da resposta: {data}")
                
                # ✅ PARSE RESPONSE - conforme documentação WiinPay
                # WiinPay retorna: {qr_code, paymentId} ou formato similar
                transaction_id = data.get('paymentId') or data.get('id') or data.get('transaction_id') or data.get('uuid') or data.get('payment_id')
                pix_code = data.get('qr_code') or data.get('pix_code') or data.get('brcode') or data.get('emv') or data.get('qrCode') or data.get('qrcode')
                qr_code_url = data.get('qr_code_url') or data.get('qrcode_url') or data.get('qrCodeUrl')
                qr_code_base64 = data.get('qr_code_base64') or data.get('qrcode_base64') or data.get('qrCodeBase64')
                
                logger.info(f"🔍 [{self.get_gateway_name()}] transaction_id: {transaction_id}")
                logger.info(f"🔍 [{self.get_gateway_name()}] pix_code: {pix_code[:50] + '...' if pix_code and len(pix_code) > 50 else pix_code}")
                
                if not transaction_id:
                    logger.error(f"❌ [{self.get_gateway_name()}] Resposta inválida - faltando transaction_id/paymentId")
                    logger.error(f"Resposta completa: {response_data}")
                    return None
                
                if not pix_code:
                    logger.error(f"❌ [{self.get_gateway_name()}] Resposta inválida - faltando qr_code/pix_code")
                    logger.error(f"Resposta completa: {response_data}")
                    return None
                
                logger.info(f"✅ [{self.get_gateway_name()}] PIX gerado! ID: {transaction_id}")
                
                # Gerar URL do QR Code se não fornecido
                if not qr_code_url:
                    import urllib.parse
                    qr_code_url = f'https://api.qrserver.com/v1/create-qr-code/?size=300x300&data={urllib.parse.quote(pix_code)}'
                
                result = {
                    'pix_code': pix_code,
                    'qr_code_url': qr_code_url,
                    'transaction_id': str(transaction_id),
                    'payment_id': payment_id,
                    'gateway_type': self.get_gateway_type(),
                    'amount': amount,
                    'status': 'pending'
                }
                
                # Adicionar QR Code base64 se disponível
                if qr_code_base64:
                    result['qr_code_base64'] = qr_code_base64
                
                return result
            
            # ✅ TAMBÉM ACEITAR 200 OK (alguns gateways retornam 200)
            elif response.status_code == 200:
                try:
                    response_data = response.json()
                    logger.info(f"📥 [{self.get_gateway_name()}] Response JSON (200): {response_data}")
                except Exception as e:
                    logger.error(f"❌ [{self.get_gateway_name()}] Erro ao parsear JSON: {e}")
                    logger.error(f"Response text: {response.text}")
                    return None
                
                # ✅ CORREÇÃO: WiinPay pode retornar dentro de 'data' wrapper ou diretamente
                if 'data' in response_data:
                    data = response_data['data']
                else:
                    data = response_data
                
                # ✅ PARSE RESPONSE
                transaction_id = data.get('paymentId') or data.get('id') or data.get('transaction_id') or data.get('uuid') or data.get('payment_id')
                pix_code = data.get('qr_code') or data.get('pix_code') or data.get('brcode') or data.get('emv') or data.get('qrCode') or data.get('qrcode')
                qr_code_url = data.get('qr_code_url') or data.get('qrcode_url') or data.get('qrCodeUrl')
                qr_code_base64 = data.get('qr_code_base64') or data.get('qrcode_base64') or data.get('qrCodeBase64')
                
                if not transaction_id or not pix_code:
                    logger.error(f"❌ [{self.get_gateway_name()}] Resposta inválida (200) - faltando transaction_id ou pix_code")
                    logger.error(f"Resposta: {response_data}")
                    return None
                
                logger.info(f"✅ [{self.get_gateway_name()}] PIX gerado! ID: {transaction_id}")
                
                # Gerar URL do QR Code se não fornecido
                if not qr_code_url:
                    import urllib.parse
                    qr_code_url = f'https://api.qrserver.com/v1/create-qr-code/?size=300x300&data={urllib.parse.quote(pix_code)}'
                
                result = {
                    'pix_code': pix_code,
                    'qr_code_url': qr_code_url,
                    'transaction_id': str(transaction_id),
                    'payment_id': payment_id,
                    'gateway_type': self.get_gateway_type(),
                    'amount': amount,
                    'status': 'pending'
                }
                
                if qr_code_base64:
                    result['qr_code_base64'] = qr_code_base64
                
                return result
            
            # ❌ ERRORS - conforme documentação WiinPay
            elif response.status_code == 422:
                try:
                    error_data = response.json()
                    error_message = error_data.get('message') or error_data.get('error') or 'Campo vazio ou inválido'
                    logger.error(f"❌ [{self.get_gateway_name()}] Campo vazio ou inválido (422): {error_message}")
                    logger.error(f"📋 Payload enviado: {payload}")
                    logger.error(f"📋 Resposta: {response.text}")
                except:
                    logger.error(f"❌ [{self.get_gateway_name()}] Campo vazio ou inválido (422)")
                    logger.error(f"📋 Payload enviado: {payload}")
                    logger.error(f"📋 Resposta: {response.text}")
                return None
            
            elif response.status_code == 401:
                logger.error(f"❌ [{self.get_gateway_name()}] Não autorizado - Chave API inválida (401)")
                logger.error(f"📋 API Key usada: {self.api_key[:10]}...{self.api_key[-5:] if len(self.api_key) > 15 else '***'}")
                logger.error(f"📋 Resposta: {response.text}")
                return None
            
            elif response.status_code == 500:
                logger.error(f"❌ [{self.get_gateway_name()}] Erro interno do servidor (500)")
                logger.error(f"📋 Payload enviado: {payload}")
                logger.error(f"📋 Resposta: {response.text}")
                return None
            
            else:
                logger.error(f"❌ [{self.get_gateway_name()}] Erro inesperado: Status {response.status_code}")
                logger.error(f"📋 Payload enviado: {payload}")
                logger.error(f"📋 Headers enviados: {headers}")
                logger.error(f"📋 Resposta: {response.text}")
                try:
                    error_data = response.json()
                    logger.error(f"📋 Resposta JSON: {error_data}")
                except:
                    pass
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

