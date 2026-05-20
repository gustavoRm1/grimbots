"""
Gateway OrionPay
Baseado na documentação oficial: https://payapi.orion.moe

Fluxo de criação de pagamento:
1. POST /api/v1/pix/personal → retorna dados do PIX

Autenticação:
- Header: X-API-Key (API Key)

Webhook:
- Header: X-Webhook-Secret (validação de assinatura)
- Eventos: payment.success, purchase.created, access.granted, webhook.test
"""

import os
import requests
import logging
import json
from typing import Dict, Any, Optional
from datetime import datetime
try:
    from .gateway_interface import PaymentGateway, resolve_public_base_url
except ImportError:
    from .gateway_interface import PaymentGateway
    def resolve_public_base_url() -> str:
        from os import environ
        base_url = (environ.get('WEBHOOK_URL') or environ.get('PUBLIC_BASE_URL') or '').strip()
        if not base_url:
            domain = (environ.get('SESSION_COOKIE_DOMAIN') or '').strip()
            if domain:
                scheme = (environ.get('PREFERRED_URL_SCHEME') or 'https').strip()
                base_url = f"{scheme}://{domain}"
        if not base_url:
            base_url = 'https://app.grimbots.online'
        return base_url.rstrip('/')

logger = logging.getLogger(__name__)


class OrionPayGateway(PaymentGateway):
    """
    Implementação do gateway OrionPay
    
    Baseado na documentação oficial:
    - Base URL: https://payapi.orion.moe (production) ou https://sandbox.orion.moe (sandbox)
    - Autenticação: X-API-Key header
    - Webhook: X-Webhook-Secret header para validação
    """
    
    def __init__(self, api_key: str, environment: str = 'production', webhook_secret: str = None):
        """
        Inicializa gateway OrionPay
        
        Args:
            api_key: API Key obtido no painel da OrionPay
            environment: 'production' ou 'sandbox' (padrão: 'production')
            webhook_secret: Secret para validação de webhooks (opcional)
        """
        if not api_key or not api_key.strip():
            logger.error(f"❌ [{self.__class__.__name__}] api_key é None ou vazio!")
            raise ValueError("api_key é obrigatório para OrionPay")
        
        self.api_key = api_key.strip()
        self.environment = environment.lower().strip()
        
        # Definir base URL baseado no ambiente
        if self.environment == 'sandbox':
            self.base_url = "https://sandbox.orion.moe"
        else:
            self.base_url = "https://payapi.orion.moe"
        
        self.webhook_secret = webhook_secret.strip() if webhook_secret else None
        
        logger.info(f"✅ [{self.get_gateway_name()}] Gateway inicializado")
        logger.info(f"   Environment: {self.environment}")
        logger.info(f"   Base URL: {self.base_url}")
        logger.info(f"   api_key: {self.api_key[:15]}... ({len(self.api_key)} chars)")
        if self.webhook_secret:
            logger.info(f"   webhook_secret: configurado")
    
    def get_gateway_name(self) -> str:
        return "OrionPay"
    
    def get_gateway_type(self) -> str:
        return "orionpay"
    
    def get_webhook_url(self) -> str:
        base_url = resolve_public_base_url()
        return f"{base_url}/webhook/payment/orionpay"
    
    def _make_request(
        self, 
        method: str, 
        endpoint: str, 
        payload: Optional[Dict[str, Any]] = None,
        headers: Optional[Dict[str, str]] = None
    ) -> Optional[requests.Response]:
        """
        Faz requisição à API OrionPay
        
        Autenticação: X-API-Key header
        """
        try:
            # Garantir que endpoint começa com /
            if not endpoint.startswith('/'):
                endpoint = '/' + endpoint
            
            url = f"{self.base_url}{endpoint}"
            
            # Headers padrão
            request_headers = {
                'X-API-Key': self.api_key,
                'Content-Type': 'application/json',
                'Accept': 'application/json'
            }
            
            if headers:
                request_headers.update(headers)
            
            logger.info(f"🌐 [{self.get_gateway_name()}] {method} {url}")
            logger.debug(f"🔑 [{self.get_gateway_name()}] Headers: X-API-Key={self.api_key[:15]}...")
            
            if payload is not None:
                logger.debug(f"📦 [{self.get_gateway_name()}] Payload: {json.dumps(payload)}")
            
            # Fazer requisição
            try:
                if method.upper() == 'GET':
                    response = requests.get(url, headers=request_headers, timeout=30)
                elif method.upper() == 'POST':
                    response = requests.post(url, headers=request_headers, json=payload, timeout=30)
                elif method.upper() == 'PUT':
                    response = requests.put(url, headers=request_headers, json=payload, timeout=30)
                elif method.upper() == 'DELETE':
                    response = requests.delete(url, headers=request_headers, timeout=30)
                else:
                    logger.error(f"❌ [{self.get_gateway_name()}] Método HTTP não suportado: {method}")
                    return None
                
                logger.info(f"📥 [{self.get_gateway_name()}] Status: {response.status_code}")
                if response.text:
                    logger.debug(f"📥 [{self.get_gateway_name()}] Resposta: {response.text[:500]}")
                
                return response
            except requests.exceptions.Timeout as e:
                logger.error(f"❌ [{self.get_gateway_name()}] Timeout na requisição: {endpoint}")
                logger.error(f"   URL: {url}")
                logger.error(f"   Erro: {str(e)}")
                return None
            except requests.exceptions.ConnectionError as e:
                logger.error(f"❌ [{self.get_gateway_name()}] Erro de conexão: {endpoint}")
                logger.error(f"   URL: {url}")
                logger.error(f"   Erro: {str(e)}")
                return None
            except requests.exceptions.RequestException as e:
                logger.error(f"❌ [{self.get_gateway_name()}] Erro na requisição: {endpoint}")
                logger.error(f"   URL: {url}")
                logger.error(f"   Erro: {str(e)}")
                return None
            
        except Exception as e:
            logger.error(f"❌ [{self.get_gateway_name()}] Erro inesperado na requisição: {e}")
            import traceback
            logger.error(f"📋 Traceback: {traceback.format_exc()}")
            return None
    
    def verify_credentials(self) -> bool:
        """
        Verifica se as credenciais são válidas
        
        Nota: OrionPay não fornece endpoint de verificação de credenciais na documentação.
        Validamos apenas o formato da API Key (deve começar com 'opay_' e ter tamanho adequado).
        A validação real será feita na primeira tentativa de gerar PIX.
        """
        try:
            # ✅ VALIDAÇÃO SIMPLES: api_key não pode ser vazia e deve ter formato válido
            if not self.api_key:
                logger.error(f"❌ [{self.get_gateway_name()}] API Key não configurada")
                return False
            
            # Validar formato da API Key (deve começar com 'opay_' conforme documentação)
            api_key_clean = self.api_key.strip()
            if len(api_key_clean) < 20:
                logger.error(f"❌ [{self.get_gateway_name()}] API Key muito curta (mínimo 20 caracteres)")
                return False
            
            # Verificar se começa com 'opay_' (formato esperado conforme documentação)
            if not api_key_clean.startswith('opay_'):
                logger.warning(f"⚠️ [{self.get_gateway_name()}] API Key não começa com 'opay_' - pode estar em formato incorreto")
                # Não rejeitar automaticamente, pois pode ser um formato válido não documentado
            
            logger.info(f"✅ [{self.get_gateway_name()}] Credenciais validadas (API Key presente e formato OK)")
            logger.info(f"   API Key: {api_key_clean[:15]}... ({len(api_key_clean)} chars)")
            return True
                
        except Exception as e:
            logger.error(f"❌ [{self.get_gateway_name()}] Erro ao verificar credenciais: {e}")
            import traceback
            logger.error(f"📋 Traceback: {traceback.format_exc()}")
            return False
    
    def generate_pix(
        self, 
        amount: float, 
        description: str, 
        payment_id: str,
        customer_data: Optional[Dict[str, Any]] = None
    ) -> Optional[Dict[str, Any]]:
        """
        Gera PIX via OrionPay usando endpoint /api/v1/pix/personal
        
        Baseado na documentação oficial:
        - Endpoint: POST https://payapi.orion.moe/api/v1/pix/personal
        - Headers: X-API-Key (obrigatório), Content-Type: application/json
        - Parâmetros obrigatórios: amount, name, email
        - Parâmetros opcionais: description, cpf, phone
        
        Args:
            amount: Valor em reais (mínimo R$ 5,00)
            description: Descrição do produto/serviço
            payment_id: ID único do pagamento no sistema
            customer_data: Dados do cliente (name, email, cpf, phone)
        
        Returns:
            Dict com dados do PIX gerado ou None em caso de erro
        """
        try:
            # Validar valor (mínimo R$ 5,00 conforme documentação)
            if not isinstance(amount, (int, float)) or amount < 5.0:
                logger.error(f"❌ [{self.get_gateway_name()}] Valor inválido: R$ {amount:.2f} (mínimo R$ 5,00)")
                return None
            
            if amount > 1000000:  # R$ 1.000.000 máximo
                logger.error(f"❌ [{self.get_gateway_name()}] Valor muito alto: R$ {amount:.2f}")
                return None
            
            logger.info(f"💰 [{self.get_gateway_name()}] Gerando PIX - R$ {amount:.2f}")
            logger.info(f"   Payment ID: {payment_id}")
            
            # Preparar dados do cliente
            if not customer_data:
                customer_data = {}
            
            # ✅ Nome (obrigatório conforme documentação)
            customer_name = customer_data.get('name') or customer_data.get('customer_name') or 'Cliente'
            if not customer_name or customer_name.strip() == '':
                customer_name = 'Cliente'
            
            # ✅ Email (obrigatório conforme documentação)
            customer_email = customer_data.get('email') or customer_data.get('customer_email')
            if not customer_email:
                # Gerar email temporário baseado no payment_id
                customer_email = f'pix{payment_id.replace("-", "").replace("_", "")[:10]}@telegram.user'
                logger.warning(f"⚠️ [{self.get_gateway_name()}] Email não fornecido, usando temporário: {customer_email}")
            
            # ✅ CPF (opcional)
            customer_cpf = customer_data.get('cpf') or customer_data.get('document') or customer_data.get('customer_document')
            if customer_cpf:
                # Remover caracteres não numéricos
                customer_cpf = ''.join(filter(str.isdigit, str(customer_cpf)))
                if len(customer_cpf) != 11:
                    customer_cpf = None  # CPF inválido, não enviar
            
            # ✅ Telefone (opcional)
            customer_phone = customer_data.get('phone') or customer_data.get('telephone') or customer_data.get('customer_phone')
            
            # ✅ Preparar payload conforme documentação EXATA
            # Documentação: { "amount": 5, "name": "João da Silva", "email": "teste@example.com", "description": "Depósito pessoal", "cpf": "103.188.066-65", "phone": "(32) 99966-1111" }
            payload = {
                'amount': float(amount),
                'name': customer_name,
                'email': customer_email
            }
            
            # Adicionar campos opcionais
            if description:
                payload['description'] = description[:200]
            
            if customer_cpf:
                # Formatar CPF: 103.188.066-65
                formatted_cpf = f"{customer_cpf[:3]}.{customer_cpf[3:6]}.{customer_cpf[6:9]}-{customer_cpf[9:11]}"
                payload['cpf'] = formatted_cpf
            
            if customer_phone:
                payload['phone'] = customer_phone
            
            logger.info(f"💳 [{self.get_gateway_name()}] Criando PIX via /api/v1/pix/personal")
            logger.info(f"   Valor: R$ {amount:.2f}")
            logger.info(f"   Nome: {customer_name}")
            logger.info(f"   Email: {customer_email}")
            logger.debug(f"   Payload: {json.dumps(payload, indent=2)}")
            
            # ✅ Fazer requisição para gerar PIX (endpoint correto)
            response = self._make_request('POST', '/api/v1/pix/personal', payload=payload)
            
            if not response:
                logger.error(f"❌ [{self.get_gateway_name()}] Erro ao gerar PIX (sem resposta)")
                return None
            
            logger.info(f"📥 [{self.get_gateway_name()}] Resposta recebida: Status {response.status_code}")
            
            # Status 200 = sucesso (conforme documentação)
            if response.status_code == 200:
                try:
                    response_data = response.json()
                    logger.debug(f"📥 [{self.get_gateway_name()}] Resposta completa: {json.dumps(response_data, indent=2)[:500]}")
                    
                    # ✅ Verificar se success = true
                    if not response_data.get('success', False):
                        logger.error(f"❌ [{self.get_gateway_name()}] Resposta com success=false")
                        logger.error(f"   Resposta: {json.dumps(response_data, indent=2)}")
                        return None
                    
                    # ✅ Extrair dados do PIX conforme documentação EXATA
                    # Formato: { "success": true, "data": { "transactionId": 2531, "id": "019a9383781b759c9be83e9cb2ad91df", "pixCode": "...", "qrCode": "...", "amount": 5, "description": "...", "expiresAt": "2025-11-17T21:30:59.063Z", "status": "created" } }
                    data = response_data.get('data', {})
                    
                    pix_code = data.get('pixCode') or data.get('pix_code')
                    qr_code_url = data.get('qrCode') or data.get('qr_code')
                    expires_at_str = data.get('expiresAt') or data.get('expires_at')
                    transaction_id = data.get('transactionId') or data.get('transaction_id') or data.get('id')
                    
                    if not pix_code:
                        logger.error(f"❌ [{self.get_gateway_name()}] pixCode não encontrado na resposta")
                        logger.error(f"   Resposta completa: {json.dumps(response_data, indent=2)}")
                        return None
                    
                    # Se não tem qrCode, gerar URL externa como fallback
                    if not qr_code_url:
                        import urllib.parse
                        qr_code_url = f'https://api.qrserver.com/v1/create-qr-code/?size=300x300&data={urllib.parse.quote(pix_code)}'
                    
                    # Converter expires_at para datetime se fornecido
                    expires_at = None
                    if expires_at_str:
                        try:
                            from dateutil.parser import parse as parse_date
                            expires_at = parse_date(expires_at_str)
                        except:
                            logger.warning(f"⚠️ [{self.get_gateway_name()}] Erro ao parsear expiresAt: {expires_at_str}")
                    
                    # Se não tem transaction_id, usar payment_id como fallback
                    if not transaction_id:
                        transaction_id = payment_id
                    
                    logger.info(f"✅ [{self.get_gateway_name()}] PIX gerado com sucesso")
                    logger.info(f"   Transaction ID: {transaction_id}")
                    logger.info(f"   PIX Code: {pix_code[:50]}...")
                    logger.info(f"   Status: {data.get('status', 'N/A')}")
                    
                    return {
                        'pix_code': pix_code,
                        'qr_code_url': qr_code_url,
                        'qr_code_base64': None,  # OrionPay retorna URL, não base64
                        'transaction_id': str(transaction_id),
                        'payment_id': payment_id,
                        'gateway_transaction_id': str(transaction_id),
                        'expires_at': expires_at
                    }
                except json.JSONDecodeError as e:
                    logger.error(f"❌ [{self.get_gateway_name()}] Erro ao decodificar JSON: {e}")
                    logger.error(f"   Resposta: {response.text[:500]}")
                    return None
            else:
                logger.error(f"❌ [{self.get_gateway_name()}] Falha ao gerar PIX (status {response.status_code})")
                if response.text:
                    logger.error(f"   Resposta completa: {response.text[:1000]}")
                    try:
                        error_data = response.json()
                        error_message = error_data.get('message') or error_data.get('error') or error_data.get('error_message')
                        if error_message:
                            logger.error(f"   Mensagem de erro: {error_message}")
                    except:
                        pass
                return None
                
        except Exception as e:
            logger.error(f"❌ [{self.get_gateway_name()}] Erro ao gerar PIX: {e}")
            import traceback
            logger.error(f"📋 Traceback: {traceback.format_exc()}")
            return None
    
    def process_webhook(self, data: Dict[str, Any]) -> Optional[Dict[str, Any]]:
        """
        Processa webhook recebido do OrionPay
        
        Baseado na documentação oficial:
        Formato do webhook OrionPay:
        {
            "event": "payment.success" | "purchase.created" | "access.granted" | "webhook.test",
            "productId": null,
            "productTitle": "...",
            "webhookName": "GRIM",
            "timestamp": "2025-10-01T...",
            "data": {
                "purchaseId": 999,
                "transactionId": "mock_...",
                "productId": null,
                "pixCode": "00020101...",
                "buyerEmail": "teste@exemplo.com",
                "buyerName": "Cliente Teste",
                "accessToken": "mock_token_...",
                "price": 100.00,
                "netAmount": 90.00,
                "platformFee": 10.00,
                "distributions": [...]
            }
        }
        
        Eventos:
        - payment.success: Pagamento confirmado (compra paga) → status: 'paid'
        - purchase.created: Nova compra criada (antes do pagamento) → status: 'pending'
        - access.granted: Acesso liberado ao comprador → status: 'paid'
        - webhook.test: Teste genérico de webhook → ignorado
        
        Args:
            data: Dados brutos do webhook (JSON do gateway)
        
        Returns:
            Dict com dados processados ou None em caso de erro
        """
        try:
            logger.info(f"📥 [{self.get_gateway_name()}] Processando webhook")
            logger.debug(f"   Estrutura recebida: {list(data.keys()) if isinstance(data, dict) else 'Não é dict'}")
            logger.debug(f"   Payload completo: {json.dumps(data, indent=2)[:1000]}")
            
            # ✅ Verificar formato da resposta
            if not isinstance(data, dict):
                logger.error(f"❌ [{self.get_gateway_name()}] Webhook com formato inválido (não é dict)")
                return None
            
            # ✅ Extrair evento e dados conforme documentação EXATA
            event = data.get('event', '')
            webhook_data = data.get('data', {})
            
            # ✅ Extrair campos adicionais do root (conforme documentação)
            product_id = data.get('productId')
            product_title = data.get('productTitle')
            webhook_name = data.get('webhookName')
            timestamp = data.get('timestamp')
            
            # Se não tem 'data', usar o próprio data como webhook_data
            if not webhook_data:
                webhook_data = data
                logger.info(f"🔍 [{self.get_gateway_name()}] Webhook sem wrapper 'data', usando root diretamente")
            else:
                logger.info(f"🔍 [{self.get_gateway_name()}] Webhook com wrapper 'data' encontrado")
                logger.debug(f"   Evento: {event}")
                logger.debug(f"   Webhook Name: {webhook_name}")
                logger.debug(f"   Timestamp: {timestamp}")
                logger.debug(f"   Product ID: {product_id}")
                logger.debug(f"   Product Title: {product_title}")
                logger.debug(f"   Dados dentro de 'data': {list(webhook_data.keys())}")
            
            # ✅ Ignorar eventos de teste
            if event == 'webhook.test':
                logger.info(f"ℹ️ [{self.get_gateway_name()}] Webhook de teste recebido (ignorado)")
                logger.info(f"   Webhook Name: {webhook_name}")
                return {
                    'payment_id': None,
                    'status': 'pending',
                    'amount': 0.0,
                    'gateway_transaction_id': None,
                    'is_test': True
                }
            
            # ✅ Extrair transaction_id (prioridade conforme documentação)
            transaction_id = (
                webhook_data.get('transactionId') or 
                webhook_data.get('transaction_id') or 
                webhook_data.get('id') or
                webhook_data.get('purchaseId') or
                webhook_data.get('purchase_id')
            )
            
            # ✅ Extrair status baseado no evento (conforme documentação)
            # payment.success = Pagamento confirmado (compra paga) → paid
            # purchase.created = Nova compra criada (antes do pagamento) → pending
            # access.granted = Acesso liberado ao comprador → paid
            status_map = {
                'payment.success': 'paid',  # ✅ Pagamento confirmado
                'payment_success': 'paid',
                'purchase.completed': 'paid',
                'purchase_completed': 'paid',
                'access.granted': 'paid',  # ✅ Acesso liberado = pago
                'access_granted': 'paid',
                'purchase.created': 'pending',  # ✅ Nova compra criada (antes do pagamento)
                'purchase_created': 'pending'
            }
            
            normalized_status = status_map.get(event, 'pending')
            
            # ✅ Log detalhado do status
            logger.info(f"🔍 [{self.get_gateway_name()}] Evento: {event} → Status: {normalized_status}")
            logger.info(f"   Webhook Name: {webhook_name}")
            logger.info(f"   Timestamp: {timestamp}")
            
            # ✅ Extrair amount (prioridade: price > amount > netAmount)
            amount = (
                webhook_data.get('price') or  # ✅ Campo principal conforme documentação
                webhook_data.get('amount') or 
                webhook_data.get('netAmount') or
                webhook_data.get('net_amount') or
                webhook_data.get('value') or
                webhook_data.get('total')
            )
            
            # Converter amount para float
            if amount:
                try:
                    amount = float(amount)
                except (ValueError, TypeError):
                    amount = None
                    logger.warning(f"⚠️ [{self.get_gateway_name()}] Valor inválido no webhook: {amount}")
            else:
                amount = None
            
            # ✅ Extrair payment_id (pode vir de purchaseId conforme documentação)
            payment_id = (
                webhook_data.get('purchaseId') or  # ✅ Campo principal conforme documentação
                webhook_data.get('purchase_id') or
                webhook_data.get('externalRef') or
                webhook_data.get('external_ref') or
                webhook_data.get('reference') or
                transaction_id
            )
            
            # ✅ Extrair dados do pagador (conforme documentação)
            payer_name = webhook_data.get('buyerName') or webhook_data.get('buyer_name') or webhook_data.get('payer_name')
            payer_email = webhook_data.get('buyerEmail') or webhook_data.get('buyer_email') or webhook_data.get('payer_email')
            access_token = webhook_data.get('accessToken') or webhook_data.get('access_token')
            
            # ✅ Extrair dados financeiros (conforme documentação)
            net_amount = webhook_data.get('netAmount') or webhook_data.get('net_amount')
            platform_fee = webhook_data.get('platformFee') or webhook_data.get('platform_fee')
            distributions = webhook_data.get('distributions', [])
            
            # ✅ Extrair pixCode (conforme documentação)
            pix_code = webhook_data.get('pixCode') or webhook_data.get('pix_code')
            
            # ✅ Extrair end_to_end_id se disponível
            end_to_end_id = webhook_data.get('endToEndId') or webhook_data.get('end_to_end_id') or webhook_data.get('e2eId') or webhook_data.get('e2e_id')
            
            # ✅ VALIDAÇÃO: transaction_id é obrigatório
            if not transaction_id:
                logger.error(f"❌ [{self.get_gateway_name()}] transaction_id não encontrado no webhook")
                logger.error(f"   Estrutura recebida: {json.dumps(data, indent=2)[:500]}")
                return None
            
            # ✅ LOGS DETALHADOS: Webhook processado com sucesso
            logger.info(f"✅ [{self.get_gateway_name()}] Webhook processado com sucesso")
            logger.info(f"   Evento: {event}")
            logger.info(f"   Webhook Name: {webhook_name}")
            logger.info(f"   Timestamp: {timestamp}")
            logger.info(f"   Transaction ID: {transaction_id}")
            logger.info(f"   Purchase ID: {payment_id}")
            logger.info(f"   Status: {normalized_status}")
            logger.info(f"   Amount: R$ {amount:.2f}" if amount else "   Amount: N/A")
            logger.info(f"   Net Amount: R$ {net_amount:.2f}" if net_amount else "   Net Amount: N/A")
            logger.info(f"   Platform Fee: R$ {platform_fee:.2f}" if platform_fee else "   Platform Fee: N/A")
            logger.info(f"   Payer Name: {payer_name}")
            logger.info(f"   Payer Email: {payer_email}")
            logger.info(f"   Product ID: {product_id}")
            logger.info(f"   Product Title: {product_title}")
            logger.info(f"   PIX Code: {pix_code[:50] + '...' if pix_code else 'N/A'}")
            logger.info(f"   End-to-End ID: {end_to_end_id}")
            
            # ✅ LOG CRÍTICO: Status PAID deve disparar entregável e Meta Pixel
            if normalized_status == 'paid':
                logger.info(f"💰 [{self.get_gateway_name()}] ⚠️ STATUS PAID CONFIRMADO - Sistema vai:")
                logger.info(f"   1️⃣ Atualizar pagamento para 'paid'")
                logger.info(f"   2️⃣ Enviar entregável ao cliente")
                logger.info(f"   3️⃣ Disparar evento Meta Pixel Purchase")
                logger.info(f"   4️⃣ Atualizar estatísticas do bot e usuário")
            elif normalized_status == 'pending':
                logger.info(f"⏳ [{self.get_gateway_name()}] Status PENDING - Pagamento ainda aguardando confirmação")
            else:
                logger.warning(f"⚠️ [{self.get_gateway_name()}] Status {normalized_status} - Não será processado como pago")
            
            return {
                'payment_id': str(payment_id) if payment_id else None,
                'status': normalized_status,
                'amount': amount,
                'gateway_transaction_id': str(transaction_id),
                'gateway_transaction_hash': str(transaction_id),
                'payer_name': payer_name,
                'payer_email': payer_email,
                'payer_document': None,  # OrionPay não fornece documento no webhook
                'end_to_end_id': end_to_end_id,
                'external_reference': str(payment_id) if payment_id else None,
                'pix_code': pix_code,
                'access_token': access_token,
                'net_amount': float(net_amount) if net_amount else None,
                'platform_fee': float(platform_fee) if platform_fee else None,
                'product_id': product_id,
                'product_title': product_title,
                'raw_data': webhook_data,
                'event': event,
                'webhook_name': webhook_name,
                'timestamp': timestamp
            }
            
        except Exception as e:
            logger.error(f"❌ [{self.get_gateway_name()}] Erro ao processar webhook: {e}")
            import traceback
            logger.error(f"📋 Traceback: {traceback.format_exc()}")
            return None
    
    def validate_webhook_signature(self, payload: Dict[str, Any], signature: str) -> bool:
        """
        Valida assinatura do webhook usando X-Webhook-Secret
        
        Args:
            payload: Dados do webhook (dict)
            signature: Assinatura recebida no header X-Webhook-Secret
        
        Returns:
            True se assinatura válida, False caso contrário
        """
        if not self.webhook_secret:
            logger.warning(f"⚠️ [{self.get_gateway_name()}] webhook_secret não configurado, validação de assinatura desabilitada")
            return True  # Se não tem secret configurado, aceitar (mas logar aviso)
        
        try:
            # OrionPay usa comparação simples do secret (conforme documentação)
            # Se o secret recebido for igual ao configurado, é válido
            if signature == self.webhook_secret:
                logger.info(f"✅ [{self.get_gateway_name()}] Assinatura do webhook válida")
                return True
            else:
                logger.error(f"❌ [{self.get_gateway_name()}] Assinatura do webhook inválida")
                logger.error(f"   Esperado: {self.webhook_secret[:10]}...")
                logger.error(f"   Recebido: {signature[:10]}...")
                return False
        except Exception as e:
            logger.error(f"❌ [{self.get_gateway_name()}] Erro ao validar assinatura: {e}")
            return False
    
    def get_payment_status(self, transaction_id: str) -> Optional[Dict[str, Any]]:
        """
        Consulta status de um pagamento no OrionPay
        
        Baseado na documentação oficial:
        - Endpoint: GET https://payapi.orion.moe/api/v1/card/status/:paymentId
        - Para PIX, pode usar o mesmo endpoint ou /api/v1/pix/status/:paymentId
        - Headers: X-API-Key (obrigatório), Content-Type: application/json
        
        Args:
            transaction_id: ID da transação no gateway (transactionId ou id retornado na criação)
        
        Returns:
            Dict com dados do pagamento ou None em caso de erro
        """
        try:
            if not transaction_id:
                logger.error(f"❌ [{self.get_gateway_name()}] transaction_id vazio na consulta de status")
                return None
            
            logger.info(f"🔍 [{self.get_gateway_name()}] Consultando status do pagamento {transaction_id}...")
            
            # ✅ Tentar primeiro endpoint para PIX (se disponível)
            # Se não funcionar, tentar endpoint de cartão (genérico)
            endpoints_to_try = [
                f'/api/v1/pix/status/{transaction_id}',
                f'/api/v1/card/status/{transaction_id}',
                f'/api/v1/payment/status/{transaction_id}'
            ]
            
            for endpoint in endpoints_to_try:
                logger.debug(f"🔍 [{self.get_gateway_name()}] Tentando endpoint: {endpoint}")
                
                # Fazer requisição GET
                response = self._make_request('GET', endpoint)
                
                if not response:
                    logger.debug(f"⚠️ [{self.get_gateway_name()}] Sem resposta do endpoint: {endpoint}")
                    continue
                
                # Status 200 = sucesso
                if response.status_code == 200:
                    try:
                        response_data = response.json()
                        logger.debug(f"📥 [{self.get_gateway_name()}] Resposta completa: {json.dumps(response_data, indent=2)[:500]}")
                        
                        # ✅ Verificar se success = true
                        if not response_data.get('success', False):
                            logger.warning(f"⚠️ [{self.get_gateway_name()}] Resposta com success=false")
                            logger.warning(f"   Resposta: {json.dumps(response_data, indent=2)}")
                            continue
                        
                        # ✅ Extrair dados conforme documentação EXATA
                        # Formato: { "success": true, "data": { "id": "12345", "status": "pending", "amount": 5.00, "pixCode": "...", "qrCode": "...", "expiresAt": "2025-11-17T12:00:00Z" } }
                        data = response_data.get('data', {})
                        
                        # Extrair status
                        status_raw = data.get('status', '').lower()
                        
                        # Mapear status do OrionPay para status padrão
                        status_map = {
                            'paid': 'paid',
                            'pago': 'paid',
                            'approved': 'paid',
                            'aprovado': 'paid',
                            'completed': 'paid',
                            'concluido': 'paid',
                            'pending': 'pending',
                            'pendente': 'pending',
                            'waiting': 'pending',
                            'aguardando': 'pending',
                            'created': 'pending',
                            'criado': 'pending',
                            'failed': 'failed',
                            'falhou': 'failed',
                            'refused': 'failed',
                            'recusado': 'failed',
                            'expired': 'failed',
                            'expirado': 'failed',
                            'cancelled': 'failed',
                            'cancelado': 'failed'
                        }
                        
                        normalized_status = status_map.get(status_raw, 'pending')
                        
                        # Extrair outros dados
                        amount = data.get('amount')
                        if amount:
                            try:
                                amount = float(amount)
                            except (ValueError, TypeError):
                                amount = None
                        
                        pix_code = data.get('pixCode') or data.get('pix_code')
                        qr_code = data.get('qrCode') or data.get('qr_code')
                        expires_at_str = data.get('expiresAt') or data.get('expires_at')
                        transaction_id_from_response = data.get('id') or data.get('transactionId') or transaction_id
                        
                        # Converter expires_at para datetime se fornecido
                        expires_at = None
                        if expires_at_str:
                            try:
                                from dateutil.parser import parse as parse_date
                                expires_at = parse_date(expires_at_str)
                            except:
                                logger.warning(f"⚠️ [{self.get_gateway_name()}] Erro ao parsear expiresAt: {expires_at_str}")
                        
                        logger.info(f"✅ [{self.get_gateway_name()}] Status consultado com sucesso")
                        logger.info(f"   Transaction ID: {transaction_id_from_response}")
                        logger.info(f"   Status: {status_raw} → {normalized_status}")
                        logger.info(f"   Amount: R$ {amount:.2f}" if amount else "   Amount: N/A")
                        
                        return {
                            'gateway_transaction_id': str(transaction_id_from_response),
                            'status': normalized_status,
                            'amount': amount,
                            'pix_code': pix_code,
                            'qr_code': qr_code,
                            'expires_at': expires_at,
                            'raw_status': status_raw,
                            'raw_data': data
                        }
                        
                    except json.JSONDecodeError as e:
                        logger.error(f"❌ [{self.get_gateway_name()}] Erro ao decodificar JSON: {e}")
                        logger.error(f"   Resposta: {response.text[:500]}")
                        continue
                elif response.status_code == 404:
                    # Endpoint não encontrado, tentar próximo
                    logger.debug(f"⚠️ [{self.get_gateway_name()}] Endpoint não encontrado (404): {endpoint}")
                    continue
                elif response.status_code == 401:
                    # Não autorizado - credenciais inválidas
                    logger.error(f"❌ [{self.get_gateway_name()}] Credenciais inválidas (401)")
                    return None
                else:
                    # Outro erro, tentar próximo endpoint
                    logger.debug(f"⚠️ [{self.get_gateway_name()}] Status {response.status_code} no endpoint: {endpoint}")
                    if response.text:
                        logger.debug(f"   Resposta: {response.text[:200]}")
                    continue
            
            # Se nenhum endpoint funcionou
            logger.warning(f"⚠️ [{self.get_gateway_name()}] Nenhum endpoint de consulta funcionou para transaction_id: {transaction_id}")
            logger.info(f"   Recomendação: Use webhooks para atualizar status de pagamentos")
            return None
            
        except Exception as e:
            logger.error(f"❌ [{self.get_gateway_name()}] Erro ao consultar status: {e}")
            import traceback
            logger.error(f"📋 Traceback: {traceback.format_exc()}")
            return None
