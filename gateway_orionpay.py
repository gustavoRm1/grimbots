"""
Gateway OrionPay
Baseado na documentação oficial: https://payapi.orion.moe

Fluxo de criação de pagamento:
1. POST /api/v1/pix/generate → retorna dados do PIX

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
from gateway_interface import PaymentGateway

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
        base_url = os.environ.get('WEBHOOK_URL', 'http://localhost:5000')
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
        Gera PIX via OrionPay usando endpoint /api/v1/pix/generate
        
        Args:
            amount: Valor em reais (ex: 10.50)
            description: Descrição do produto/serviço
            payment_id: ID único do pagamento no sistema
            customer_data: Dados opcionais do cliente
        
        Returns:
            Dict com dados do PIX gerado ou None em caso de erro
        """
        try:
            # Validar valor
            if not isinstance(amount, (int, float)) or amount <= 0:
                logger.error(f"❌ [{self.get_gateway_name()}] Valor inválido: {amount}")
                return None
            
            if amount > 1000000:  # R$ 1.000.000 máximo
                logger.error(f"❌ [{self.get_gateway_name()}] Valor muito alto: R$ {amount:.2f}")
                return None
            
            logger.info(f"💰 [{self.get_gateway_name()}] Gerando PIX - R$ {amount:.2f}")
            logger.info(f"   Payment ID: {payment_id}")
            
            # Preparar payload conforme documentação
            # Formato esperado: { "amount": 100.00, "description": "Pagamento teste" }
            payload = {
                'amount': float(amount),
                'description': description[:200] if description else f'Pagamento {payment_id}'
            }
            
            # Adicionar dados do cliente se disponíveis (metadata opcional)
            if customer_data:
                customer_email = customer_data.get('email')
                if customer_email:
                    payload['userEmail'] = customer_email
            
            logger.info(f"💳 [{self.get_gateway_name()}] Criando PIX via /api/v1/pix/generate")
            logger.info(f"   Valor: R$ {amount:.2f}")
            logger.info(f"   Description: {payload['description']}")
            
            # Fazer requisição para gerar PIX
            response = self._make_request('POST', '/api/v1/pix/generate', payload=payload)
            
            if not response:
                logger.error(f"❌ [{self.get_gateway_name()}] Erro ao gerar PIX (sem resposta)")
                return None
            
            logger.info(f"📥 [{self.get_gateway_name()}] Resposta recebida: Status {response.status_code}")
            
            # Status 200 ou 201 = sucesso
            if response.status_code in [200, 201]:
                try:
                    data = response.json()
                    logger.debug(f"📥 [{self.get_gateway_name()}] Resposta completa: {json.dumps(data, indent=2)[:500]}")
                    
                    # Extrair dados do PIX conforme documentação
                    # Formato esperado: { "pixCode": "00020126...", "qrCode": "data:image/png;base64...", "expiresAt": "2025-09-30T23:00:00Z" }
                    pix_code = data.get('pixCode') or data.get('pix_code')
                    qr_code_base64 = data.get('qrCode') or data.get('qr_code') or data.get('qrCodeBase64') or data.get('qr_code_base64')
                    expires_at_str = data.get('expiresAt') or data.get('expires_at')
                    transaction_id = data.get('transactionId') or data.get('transaction_id') or data.get('id')
                    
                    if not pix_code:
                        logger.error(f"❌ [{self.get_gateway_name()}] pix_code não encontrado na resposta")
                        logger.error(f"   Resposta completa: {json.dumps(data, indent=2)}")
                        return None
                    
                    # Gerar QR Code URL se não fornecido
                    qr_code_url = None
                    if qr_code_base64:
                        # Se é base64, usar diretamente
                        if qr_code_base64.startswith('data:image'):
                            qr_code_url = qr_code_base64
                        else:
                            # Se não tem prefixo, adicionar
                            qr_code_url = f'data:image/png;base64,{qr_code_base64}'
                    else:
                        # Gerar URL externa como fallback
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
                    
                    return {
                        'pix_code': pix_code,
                        'qr_code_url': qr_code_url,
                        'qr_code_base64': qr_code_base64,
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
        
        Formato esperado do webhook OrionPay:
        {
            "event": "payment.success" | "purchase.created" | "access.granted" | "webhook.test",
            "data": {
                "purchaseId": 17,
                "transactionId": "0199a1b1a335713591928b06376b1c82",
                "productId": 8,
                "pixCode": "00020101...",
                "buyerEmail": "cliente@email.com",
                "buyerName": "Nome do Cliente",
                "accessToken": "token_de_acesso_unico",
                "price": 100.00,
                "netAmount": 90.00,
                "platformFee": 10.00,
                ...
            }
        }
        
        Args:
            data: Dados brutos do webhook (JSON do gateway)
        
        Returns:
            Dict com dados processados ou None em caso de erro
        """
        try:
            logger.info(f"📥 [{self.get_gateway_name()}] Processando webhook")
            logger.debug(f"   Estrutura recebida: {list(data.keys()) if isinstance(data, dict) else 'Não é dict'}")
            logger.debug(f"   Payload completo: {json.dumps(data, indent=2)[:1000]}")
            
            # Verificar formato da resposta
            if not isinstance(data, dict):
                logger.error(f"❌ [{self.get_gateway_name()}] Webhook com formato inválido (não é dict)")
                return None
            
            # Extrair evento e dados
            event = data.get('event', '')
            webhook_data = data.get('data', {})
            
            # Se não tem 'data', usar o próprio data como webhook_data
            if not webhook_data:
                webhook_data = data
                logger.info(f"🔍 [{self.get_gateway_name()}] Webhook sem wrapper 'data', usando root diretamente")
            else:
                logger.info(f"🔍 [{self.get_gateway_name()}] Webhook com wrapper 'data' encontrado")
                logger.debug(f"   Evento: {event}")
                logger.debug(f"   Dados dentro de 'data': {list(webhook_data.keys())}")
            
            # Ignorar eventos de teste
            if event == 'webhook.test':
                logger.info(f"ℹ️ [{self.get_gateway_name()}] Webhook de teste recebido (ignorado)")
                return {
                    'payment_id': None,
                    'status': 'pending',
                    'amount': 0.0,
                    'gateway_transaction_id': None,
                    'is_test': True
                }
            
            # Extrair transaction_id
            transaction_id = (
                webhook_data.get('transactionId') or 
                webhook_data.get('transaction_id') or 
                webhook_data.get('id') or
                webhook_data.get('purchaseId') or
                webhook_data.get('purchase_id')
            )
            
            # Extrair status baseado no evento
            # payment.success = pagamento concluído (paid)
            # purchase.created = compra criada (pending)
            # access.granted = acesso liberado (pode ser paid ou pending dependendo do contexto)
            status_map = {
                'payment.success': 'paid',
                'payment_success': 'paid',
                'purchase.completed': 'paid',
                'purchase_completed': 'paid',
                'access.granted': 'paid',  # Acesso liberado geralmente significa que foi pago
                'access_granted': 'paid',
                'purchase.created': 'pending',
                'purchase_created': 'pending'
            }
            
            normalized_status = status_map.get(event, 'pending')
            
            # Log detalhado do status
            logger.info(f"🔍 [{self.get_gateway_name()}] Evento: {event} → Status: {normalized_status}")
            
            # Extrair amount
            amount = (
                webhook_data.get('price') or 
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
            
            # Extrair payment_id (pode vir de vários campos)
            payment_id = (
                webhook_data.get('purchaseId') or 
                webhook_data.get('purchase_id') or
                webhook_data.get('externalRef') or
                webhook_data.get('external_ref') or
                webhook_data.get('reference') or
                transaction_id
            )
            
            # Extrair dados do pagador
            payer_name = webhook_data.get('buyerName') or webhook_data.get('buyer_name') or webhook_data.get('payer_name')
            payer_email = webhook_data.get('buyerEmail') or webhook_data.get('buyer_email') or webhook_data.get('payer_email')
            
            # Extrair end_to_end_id se disponível
            end_to_end_id = webhook_data.get('endToEndId') or webhook_data.get('end_to_end_id') or webhook_data.get('e2eId') or webhook_data.get('e2e_id')
            
            # VALIDAÇÃO: transaction_id é obrigatório
            if not transaction_id:
                logger.error(f"❌ [{self.get_gateway_name()}] transaction_id não encontrado no webhook")
                logger.error(f"   Estrutura recebida: {json.dumps(data, indent=2)[:500]}")
                return None
            
            # LOGS DETALHADOS: Webhook processado com sucesso
            logger.info(f"✅ [{self.get_gateway_name()}] Webhook processado com sucesso")
            logger.info(f"   Transaction ID: {transaction_id}")
            logger.info(f"   Evento: {event} → Status: {normalized_status}")
            logger.info(f"   Amount: R$ {amount:.2f}" if amount else "   Amount: N/A")
            logger.info(f"   Payment ID: {payment_id}")
            logger.info(f"   Payer Name: {payer_name}")
            logger.info(f"   Payer Email: {payer_email}")
            logger.info(f"   End-to-End ID: {end_to_end_id}")
            
            # LOG CRÍTICO: Status PAID deve disparar entregável e Meta Pixel
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
                'raw_data': webhook_data,
                'event': event
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
        
        Nota: OrionPay não fornece endpoint de consulta de status na documentação.
        Este método retorna None e deve ser usado apenas para compatibilidade.
        A recomendação é usar webhooks para atualizar status.
        
        Args:
            transaction_id: ID da transação no gateway
        
        Returns:
            None (endpoint não disponível)
        """
        logger.warning(f"⚠️ [{self.get_gateway_name()}] Consulta de status não disponível na API OrionPay")
        logger.info(f"   Recomendação: Use webhooks para atualizar status de pagamentos")
        logger.info(f"   Transaction ID: {transaction_id}")
        return None

