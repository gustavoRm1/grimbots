"""
Gateway UmbrellaPag
Baseado na documentação oficial: https://docs.umbrellapag.com/

Fluxo de criação de pagamento:
1. Criar produto (POST /api/user/products) → retorna uniqueProductLinkId
2. Criar pedido (POST /api/public/checkout/create-order/{uniqueProductLinkId}) → retorna id do pedido
3. Criar pagamento PIX (POST /api/public/checkout/payment/{id}) → retorna dados do PIX

Autenticação:
- Header: x-api-key (token de API)
- Header: User-Agent: UMBRELLAB2B/1.0
"""

import os
import requests
import logging
import hashlib
import time
import json
from typing import Dict, Any, Optional
from datetime import datetime
from gateway_interface import PaymentGateway
from utils.validators import cpf_valido

logger = logging.getLogger(__name__)


class UmbrellaPagGateway(PaymentGateway):
    """
    Implementação do gateway UmbrellaPag
    
    Baseado na documentação oficial:
    - Base URL: https://api-gateway.umbrellapag.com/api
    - Autenticação: x-api-key header + User-Agent: UMBRELLAB2B/1.0
    - Fluxo: Produto → Pedido → Pagamento
    """
    
    def __init__(self, api_key: str, product_hash: str = None):
        """
        Inicializa gateway UmbrellaPag
        
        Args:
            api_key: Token de API obtido no painel da UmbrellaPag
            product_hash: uniqueProductLinkId do produto (opcional, será criado dinamicamente se não informado)
        """
        if not api_key or not api_key.strip():
            logger.error(f"❌ [{self.__class__.__name__}] api_key é None ou vazio!")
            raise ValueError("api_key é obrigatório para UmbrellaPag")
        
        self.api_key = api_key.strip()
        self.base_url = "https://api-gateway.umbrellapag.com/api"
        self.product_hash = product_hash.strip() if product_hash else None
        self.split_percentage = 2.0
        
        logger.info(f"✅ [{self.get_gateway_name()}] Gateway inicializado")
        logger.info(f"   api_key: {self.api_key[:15]}... ({len(self.api_key)} chars)")
        if self.product_hash:
            logger.info(f"   product_hash: {self.product_hash[:20]}...")
        else:
            logger.info(f"   product_hash: não configurado (será criado dinamicamente)")
    
    def get_gateway_name(self) -> str:
        return "UmbrellaPag"
    
    def get_gateway_type(self) -> str:
        return "umbrellapag"
    
    def get_webhook_url(self) -> str:
        base_url = os.environ.get('WEBHOOK_URL', 'http://localhost:5000')
        return f"{base_url}/webhook/payment/umbrellapag"
    
    def _get_dynamic_checkout_url(self, payment_id: str) -> str:
        """
        Gera URL de checkout dinâmica baseada no ambiente
        """
        base_url = os.environ.get('WEBHOOK_URL', 'http://localhost:5000')
        # Remove /webhook se presente e adiciona /payment
        if '/webhook' in base_url:
            base_url = base_url.replace('/webhook', '')
        return f"{base_url}/payment/{payment_id}"
    
    def _validate_phone(self, phone: str) -> str:
        """
        Valida e formata telefone (apenas números, 10-11 dígitos)
        """
        phone_clean = ''.join(c for c in phone if c.isdigit())
        
        if len(phone_clean) < 10:
            phone_clean = phone_clean.ljust(10, '0')
        elif len(phone_clean) > 11:
            phone_clean = phone_clean[:11]
        
        return phone_clean
    
    def _validate_document(self, document: str) -> str:
        """
        Valida e formata documento (CPF) - apenas números, 11 dígitos
        """
        doc_clean = ''.join(c for c in document if c.isdigit())
        
        if len(doc_clean) == 11:
            if cpf_valido(doc_clean):
                return doc_clean
            else:
                logger.warning(f"⚠️ [{self.get_gateway_name()}] CPF inválido: {doc_clean[:3]}***")
                return None
        
        if len(doc_clean) > 0:
            return doc_clean.ljust(11, '0')[:11]
        
        return None
    
    def _make_request(
        self, 
        method: str, 
        endpoint: str, 
        payload: Optional[Dict[str, Any]] = None,
        headers: Optional[Dict[str, str]] = None
    ) -> Optional[requests.Response]:
        """
        Faz requisição à API UmbrellaPag
        
        Autenticação: x-api-key header + User-Agent: UMBRELLAB2B/1.0
        """
        try:
            url = f"{self.base_url}{endpoint}"
            
            # Headers padrão
            request_headers = {
                'x-api-key': self.api_key,
                'User-Agent': 'UMBRELLAB2B/1.0',
                'Content-Type': 'application/json',
                'Accept': 'application/json'
            }
            
            if headers:
                request_headers.update(headers)
            
            logger.info(f"🌐 [{self.get_gateway_name()}] {method} {url}")
            logger.info(f"🔑 [{self.get_gateway_name()}] Headers: x-api-key={self.api_key[:15]}..., User-Agent=UMBRELLAB2B/1.0")
            
            # Log headers adicionais se houver
            if headers:
                logger.info(f"🔑 [{self.get_gateway_name()}] Headers adicionais: {', '.join(headers.keys())}")
                for key, value in headers.items():
                    if key.lower() in ['origin', 'referer']:
                        logger.info(f"   {key}: {value}")
                    elif 'key' in key.lower() or 'token' in key.lower():
                        logger.info(f"   {key}: {value[:15]}...")
            
            if payload is not None:
                logger.info(f"📦 [{self.get_gateway_name()}] Payload: {json.dumps(payload)}")
            else:
                logger.info(f"📦 [{self.get_gateway_name()}] Payload: None")
            
            # Fazer requisição
            try:
                if method.upper() == 'GET':
                    logger.info(f"📤 [{self.get_gateway_name()}] Enviando GET...")
                    response = requests.get(url, headers=request_headers, timeout=30)
                elif method.upper() == 'POST':
                    # Sempre passar json=payload, mesmo se for None ou {}
                    if payload is None:
                        payload = {}
                    logger.info(f"📤 [{self.get_gateway_name()}] Enviando POST com payload: {json.dumps(payload)}")
                    response = requests.post(url, headers=request_headers, json=payload, timeout=30)
                elif method.upper() == 'PUT':
                    if payload is None:
                        payload = {}
                    logger.info(f"📤 [{self.get_gateway_name()}] Enviando PUT com payload: {json.dumps(payload)}")
                    response = requests.put(url, headers=request_headers, json=payload, timeout=30)
                elif method.upper() == 'DELETE':
                    logger.info(f"📤 [{self.get_gateway_name()}] Enviando DELETE...")
                    response = requests.delete(url, headers=request_headers, timeout=30)
                else:
                    logger.error(f"❌ [{self.get_gateway_name()}] Método HTTP não suportado: {method}")
                    return None
                
                logger.info(f"📥 [{self.get_gateway_name()}] Status: {response.status_code}")
                if response.text:
                    logger.info(f"📥 [{self.get_gateway_name()}] Resposta: {response.text[:500]}")
                else:
                    logger.info(f"📥 [{self.get_gateway_name()}] Resposta: (vazia)")
                
                return response
            except requests.exceptions.Timeout as e:
                logger.error(f"❌ [{self.get_gateway_name()}] Timeout na requisição: {endpoint}")
                logger.error(f"   URL: {url}")
                logger.error(f"   Erro: {str(e)}")
                import traceback
                logger.error(f"📋 Traceback: {traceback.format_exc()}")
                return None
            except requests.exceptions.ConnectionError as e:
                logger.error(f"❌ [{self.get_gateway_name()}] Erro de conexão: {endpoint}")
                logger.error(f"   URL: {url}")
                logger.error(f"   Erro: {str(e)}")
                import traceback
                logger.error(f"📋 Traceback: {traceback.format_exc()}")
                return None
            except requests.exceptions.RequestException as e:
                logger.error(f"❌ [{self.get_gateway_name()}] Erro na requisição: {endpoint}")
                logger.error(f"   URL: {url}")
                logger.error(f"   Erro: {str(e)}")
                import traceback
                logger.error(f"📋 Traceback: {traceback.format_exc()}")
                return None
            
        except Exception as e:
            logger.error(f"❌ [{self.get_gateway_name()}] Erro inesperado na requisição: {e}")
            import traceback
            logger.error(f"📋 Traceback: {traceback.format_exc()}")
            return None
    
    def verify_credentials(self) -> bool:
        """
        Verifica se as credenciais são válidas
        Tenta fazer uma requisição simples à API para buscar dados da empresa
        """
        try:
            # Tentar buscar dados da empresa (endpoint mais simples e confiável)
            # Se conseguir buscar dados, as credenciais são válidas
            response = self._make_request('GET', '/user/sellers')
            
            # Verificar resposta
            if not response:
                logger.error(f"❌ [{self.get_gateway_name()}] Erro ao verificar credenciais (sem resposta)")
                return False
            
            status_code = response.status_code
            logger.debug(f"🔍 [{self.get_gateway_name()}] Status da resposta: {status_code}")
            
            # Status 200 ou 201 = sucesso (credenciais válidas) - SIMPLIFICADO
            if status_code in [200, 201]:
                logger.info(f"✅ [{self.get_gateway_name()}] Credenciais válidas (status {status_code})")
                # Tentar parsear resposta para log detalhado
                try:
                    response_data = response.json()
                    if isinstance(response_data, dict):
                        message = response_data.get('message', '')
                        logger.debug(f"   Mensagem: {message}")
                        if 'data' in response_data:
                            logger.debug(f"   Dados encontrados: {list(response_data.get('data', {}).keys())}")
                except:
                    pass
                return True
            
            # Status 401 ou 403 = credenciais inválidas
            elif status_code in [401, 403]:
                logger.error(f"❌ [{self.get_gateway_name()}] Credenciais inválidas (status {status_code})")
                if response.text:
                    logger.error(f"   Resposta: {response.text[:200]}")
                return False
            
            # Outros status = verificar mensagem de sucesso na resposta
            else:
                logger.warning(f"⚠️ [{self.get_gateway_name()}] Status inesperado {status_code}")
                # Verificar se a resposta indica sucesso mesmo com status diferente
                try:
                    response_data = response.json()
                    if isinstance(response_data, dict):
                        message = response_data.get('message', '').lower()
                        # Se tiver mensagem de sucesso ou dados válidos, considerar válido
                        if 'sucesso' in message or 'encontrada' in message or 'data' in response_data:
                            logger.info(f"✅ [{self.get_gateway_name()}] Credenciais válidas (mensagem de sucesso, status {status_code})")
                            return True
                except Exception as e:
                    logger.debug(f"   Erro ao parsear resposta: {e}")
                
                # Se não conseguir verificar, considerar credenciais inválidas
                logger.error(f"❌ [{self.get_gateway_name()}] Credenciais inválidas (status {status_code} não reconhecido)")
                if response.text:
                    logger.error(f"   Resposta: {response.text[:200]}")
                return False
                
        except Exception as e:
            logger.error(f"❌ [{self.get_gateway_name()}] Erro ao verificar credenciais: {e}")
            import traceback
            logger.error(f"📋 Traceback: {traceback.format_exc()}")
            return False
    
    def _create_product(self, amount: float, description: str, payment_id: str) -> Optional[str]:
        """
        Cria produto dinamicamente na UmbrellaPag
        
        Args:
            amount: Valor em reais
            description: Descrição do produto
            payment_id: ID único do pagamento
        
        Returns:
            uniqueProductLinkId ou None em caso de erro
        """
        try:
            # Converter para centavos (se necessário)
            amount_cents = int(amount * 100) if amount > 0 else 0
            
            # Payload para criar produto
            payload = {
                'title': description[:100] if description else f'Produto {payment_id}',
                'description': description[:500] if description else f'Produto digital - Pagamento {payment_id}',
                'shippingType': 'DIGITAL',
                'status': 'ACTIVE',
                'unitPrice': amount,  # Valor em reais (não centavos)
                'maxInstallments': 1,  # PIX sempre 1 parcela
                'paymentMethod': {
                    'creditCard': False,
                    'pix': True,
                    'boleto': False
                }
            }
            
            logger.info(f"📦 [{self.get_gateway_name()}] Criando produto: {payload['title']}")
            
            response = self._make_request('POST', '/user/products', payload=payload)
            
            if not response:
                logger.error(f"❌ [{self.get_gateway_name()}] Erro ao criar produto (sem resposta)")
                return None
            
            if response.status_code == 201:
                try:
                    data = response.json()
                    
                    # Verificar formato da resposta
                    if isinstance(data, dict) and 'data' in data:
                        product_data = data.get('data', {})
                        unique_product_link_id = product_data.get('uniqueProductLinkId')
                        
                        if unique_product_link_id:
                            logger.info(f"✅ [{self.get_gateway_name()}] Produto criado: {unique_product_link_id}")
                            return unique_product_link_id
                        else:
                            logger.error(f"❌ [{self.get_gateway_name()}] uniqueProductLinkId não encontrado na resposta")
                            logger.error(f"   Resposta: {json.dumps(data, indent=2)}")
                            return None
                    else:
                        logger.error(f"❌ [{self.get_gateway_name()}] Formato de resposta inválido")
                        logger.error(f"   Resposta: {response.text[:500]}")
                        return None
                        
                except json.JSONDecodeError as e:
                    logger.error(f"❌ [{self.get_gateway_name()}] Erro ao decodificar JSON: {e}")
                    logger.error(f"   Resposta: {response.text[:500]}")
                    return None
            else:
                logger.error(f"❌ [{self.get_gateway_name()}] Falha ao criar produto (status {response.status_code})")
                if response.text:
                    logger.error(f"   Resposta: {response.text[:500]}")
                return None
                
        except Exception as e:
            logger.error(f"❌ [{self.get_gateway_name()}] Erro ao criar produto: {e}")
            import traceback
            logger.error(f"📋 Traceback: {traceback.format_exc()}")
            return None
    
    def _create_order(self, unique_product_link_id: str) -> Optional[str]:
        """
        Cria pedido de checkout na UmbrellaPag
        
        Args:
            unique_product_link_id: ID único do produto
        
        Returns:
            id do pedido ou None em caso de erro
        """
        try:
            logger.info(f"🛒 [{self.get_gateway_name()}] Criando pedido para produto: {unique_product_link_id}")
            
            # Endpoint: /api/public/checkout/create-order/{uniqueProductLinkId}
            endpoint = f'/public/checkout/create-order/{unique_product_link_id}'
            
            # Passar body vazio {} conforme documentação
            payload = {}
            
            # Adicionar headers adicionais para endpoints /public/
            # O erro "Hostname não identificado" pode exigir Origin ou Referer
            additional_headers = {}
            try:
                webhook_url = os.environ.get('WEBHOOK_URL', '')
                if webhook_url:
                    # Extrair domínio do WEBHOOK_URL
                    from urllib.parse import urlparse
                    parsed = urlparse(webhook_url)
                    domain = f"{parsed.scheme}://{parsed.netloc}"
                    additional_headers['Origin'] = domain
                    additional_headers['Referer'] = domain
                    logger.info(f"🌐 [{self.get_gateway_name()}] Adicionando headers Origin/Referer: {domain}")
                else:
                    logger.warning(f"⚠️ [{self.get_gateway_name()}] WEBHOOK_URL não configurado - headers Origin/Referer não serão enviados")
            except Exception as e:
                logger.warning(f"⚠️ [{self.get_gateway_name()}] Erro ao extrair domínio: {e}")
            
            logger.info(f"🌐 [{self.get_gateway_name()}] POST {endpoint}")
            logger.info(f"📦 [{self.get_gateway_name()}] Payload: {json.dumps(payload)}")
            logger.info(f"📦 [{self.get_gateway_name()}] Product Link ID: {unique_product_link_id}")
            
            response = self._make_request('POST', endpoint, payload=payload, headers=additional_headers)
            
            if not response:
                logger.error(f"❌ [{self.get_gateway_name()}] Erro ao criar pedido (sem resposta)")
                logger.error(f"   Endpoint: {endpoint}")
                logger.error(f"   URL completa: {self.base_url}{endpoint}")
                logger.error(f"   Payload: {payload}")
                logger.error(f"   API Key: {self.api_key[:15]}... ({len(self.api_key)} chars)")
                logger.error(f"   Isso indica que a requisição falhou antes de receber resposta")
                logger.error(f"   Possíveis causas: timeout, erro de conexão, ou erro de autenticação")
                return None
            
            logger.info(f"📥 [{self.get_gateway_name()}] Resposta recebida: Status {response.status_code}")
            
            if response.status_code == 201:
                try:
                    data = response.json()
                    
                    # Verificar formato da resposta
                    if isinstance(data, dict) and 'data' in data:
                        order_data = data.get('data', {})
                        order_id = order_data.get('id')
                        
                        if order_id:
                            logger.info(f"✅ [{self.get_gateway_name()}] Pedido criado: {order_id}")
                            return order_id
                        else:
                            logger.error(f"❌ [{self.get_gateway_name()}] id do pedido não encontrado na resposta")
                            logger.error(f"   Resposta: {json.dumps(data, indent=2)}")
                            return None
                    else:
                        logger.error(f"❌ [{self.get_gateway_name()}] Formato de resposta inválido")
                        logger.error(f"   Resposta: {response.text[:500]}")
                        return None
                        
                except json.JSONDecodeError as e:
                    logger.error(f"❌ [{self.get_gateway_name()}] Erro ao decodificar JSON: {e}")
                    logger.error(f"   Resposta: {response.text[:500]}")
                    return None
            else:
                logger.error(f"❌ [{self.get_gateway_name()}] Falha ao criar pedido (status {response.status_code})")
                logger.error(f"   Endpoint: {endpoint}")
                logger.error(f"   URL completa: {self.base_url}{endpoint}")
                logger.error(f"   Product Link ID: {unique_product_link_id}")
                logger.error(f"   API Key: {self.api_key[:15]}... ({len(self.api_key)} chars)")
                
                # Log detalhado do erro
                if response.text:
                    logger.error(f"   Resposta: {response.text[:500]}")
                    try:
                        error_data = response.json()
                        error_message = error_data.get('message', '')
                        error_status_code = error_data.get('statusCode', response.status_code)
                        
                        logger.error(f"   Erro JSON: {json.dumps(error_data, indent=2)}")
                        logger.error(f"   Mensagem de erro: {error_message}")
                        logger.error(f"   Status Code: {error_status_code}")
                        
                        # Se o erro for "Hostname não identificado", pode precisar de header adicional
                        if 'hostname' in error_message.lower() or 'hostname' in str(error_data).lower():
                            logger.warning(f"⚠️ [{self.get_gateway_name()}] Erro relacionado a hostname!")
                            logger.warning(f"   Possível causa: endpoint /public/ pode precisar de header ou payload adicional")
                            logger.warning(f"   Verifique a documentação do endpoint /api/public/checkout/create-order/{{id}}")
                    except Exception as e:
                        logger.error(f"   Erro ao parsear resposta: {e}")
                else:
                    logger.error(f"   Resposta: (vazia)")
                return None
                
        except Exception as e:
            logger.error(f"❌ [{self.get_gateway_name()}] Erro ao criar pedido: {e}")
            import traceback
            logger.error(f"📋 Traceback: {traceback.format_exc()}")
            return None
    
    def generate_pix(
        self, 
        amount: float, 
        description: str, 
        payment_id: str,
        customer_data: Optional[Dict[str, Any]] = None
    ) -> Optional[Dict[str, Any]]:
        """
        Gera PIX via UmbrellaPag
        
        Fluxo:
        1. Criar produto (se não existir product_hash)
        2. Criar pedido
        3. Criar pagamento PIX
        
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
            
            # 1. Criar ou usar produto existente
            unique_product_link_id = self.product_hash
            
            if not unique_product_link_id:
                logger.info(f"📦 [{self.get_gateway_name()}] Criando produto dinamicamente...")
                unique_product_link_id = self._create_product(amount, description, payment_id)
                
                if not unique_product_link_id:
                    logger.error(f"❌ [{self.get_gateway_name()}] Falha ao criar produto")
                    return None
                
                # Salvar product_hash para uso futuro
                self.product_hash = unique_product_link_id
            else:
                logger.info(f"✅ [{self.get_gateway_name()}] Usando produto existente: {unique_product_link_id}")
            
            # 2. Criar pedido
            order_id = self._create_order(unique_product_link_id)
            
            if not order_id:
                logger.error(f"❌ [{self.get_gateway_name()}] Falha ao criar pedido")
                return None
            
            # 3. Criar pagamento PIX
            logger.info(f"💳 [{self.get_gateway_name()}] Criando pagamento PIX para pedido: {order_id}")
            
            # Preparar dados do cliente
            if not customer_data:
                customer_data = {}
            
            customer_name = customer_data.get('name', 'Cliente')
            customer_email = customer_data.get('email', f'pix{payment_id}@bot.digital')
            customer_phone = customer_data.get('phone', '11999999999')
            customer_document = customer_data.get('document')
            
            # Validar e formatar telefone
            customer_phone = self._validate_phone(customer_phone)
            
            # Validar documento (se fornecido)
            if customer_document:
                customer_document = self._validate_document(customer_document)
            
            # Payload para criar pagamento PIX
            payment_payload = {
                'paymentMethod': 'pix',
                'customer': {
                    'name': customer_name[:100],
                    'email': customer_email[:100],
                    'phone': customer_phone
                }
            }
            
            # Adicionar documento se válido
            if customer_document:
                payment_payload['customer']['document'] = customer_document
            
            # Adicionar webhook URL
            webhook_url = self.get_webhook_url()
            if webhook_url:
                payment_payload['webhookUrl'] = webhook_url
            
            # Adicionar metadata com payment_id
            payment_payload['metadata'] = {
                'payment_id': payment_id,
                'platform': 'grimbots'
            }
            
            response = self._make_request('POST', f'/public/checkout/payment/{order_id}', payload=payment_payload)
            
            if not response:
                logger.error(f"❌ [{self.get_gateway_name()}] Erro ao criar pagamento (sem resposta)")
                return None
            
            if response.status_code == 201:
                try:
                    data = response.json()
                    
                    # Verificar formato da resposta
                    if isinstance(data, dict) and 'data' in data:
                        payment_data = data.get('data', {})
                        
                        # Extrair dados do PIX
                        pix_code = payment_data.get('pixCode') or payment_data.get('pix_code') or payment_data.get('qrCode') or payment_data.get('qr_code')
                        qr_code_url = payment_data.get('qrCodeUrl') or payment_data.get('qr_code_url') or payment_data.get('qrCodeImage') or payment_data.get('qr_code_image')
                        transaction_id = payment_data.get('id') or payment_data.get('transactionId') or payment_data.get('transaction_id') or order_id
                        
                        if not pix_code:
                            logger.error(f"❌ [{self.get_gateway_name()}] pix_code não encontrado na resposta")
                            logger.error(f"   Resposta: {json.dumps(data, indent=2)}")
                            return None
                        
                        # Gerar QR Code URL se não fornecido
                        if not qr_code_url:
                            qr_code_url = f'https://api.qrserver.com/v1/create-qr-code/?size=300x300&data={pix_code}'
                        
                        logger.info(f"✅ [{self.get_gateway_name()}] PIX gerado com sucesso")
                        logger.info(f"   Transaction ID: {transaction_id}")
                        logger.info(f"   PIX Code: {pix_code[:50]}...")
                        
                        return {
                            'pix_code': pix_code,
                            'qr_code_url': qr_code_url,
                            'transaction_id': str(transaction_id),
                            'payment_id': payment_id,
                            'gateway_transaction_id': str(transaction_id),
                            'gateway_transaction_hash': str(transaction_id),  # Usar transaction_id como hash
                            'order_id': order_id,
                            'product_hash': unique_product_link_id
                        }
                    else:
                        logger.error(f"❌ [{self.get_gateway_name()}] Formato de resposta inválido")
                        logger.error(f"   Resposta: {response.text[:500]}")
                        return None
                        
                except json.JSONDecodeError as e:
                    logger.error(f"❌ [{self.get_gateway_name()}] Erro ao decodificar JSON: {e}")
                    logger.error(f"   Resposta: {response.text[:500]}")
                    return None
            else:
                logger.error(f"❌ [{self.get_gateway_name()}] Falha ao criar pagamento (status {response.status_code})")
                if response.text:
                    logger.error(f"   Resposta: {response.text[:500]}")
                return None
                
        except Exception as e:
            logger.error(f"❌ [{self.get_gateway_name()}] Erro ao gerar PIX: {e}")
            import traceback
            logger.error(f"📋 Traceback: {traceback.format_exc()}")
            return None
    
    def process_webhook(self, data: Dict[str, Any]) -> Optional[Dict[str, Any]]:
        """
        Processa webhook recebido do UmbrellaPag
        
        Args:
            data: Dados brutos do webhook (JSON do gateway)
        
        Returns:
            Dict com dados processados ou None em caso de erro
        """
        try:
            logger.info(f"📥 [{self.get_gateway_name()}] Processando webhook")
            logger.debug(f"   Dados: {json.dumps(data, indent=2)}")
            
            # Verificar formato da resposta
            if not isinstance(data, dict):
                logger.error(f"❌ [{self.get_gateway_name()}] Webhook com formato inválido")
                return None
            
            # Extrair dados do webhook
            # Formato pode variar, tentar múltiplos campos
            transaction_id = (
                data.get('id') or 
                data.get('transactionId') or 
                data.get('transaction_id') or
                data.get('orderId') or
                data.get('order_id')
            )
            
            status = data.get('status') or data.get('paymentStatus') or data.get('payment_status')
            amount = data.get('amount') or data.get('value') or data.get('total')
            
            # Mapear status
            status_map = {
                'PAID': 'paid',
                'paid': 'paid',
                'PENDING': 'pending',
                'pending': 'pending',
                'FAILED': 'failed',
                'failed': 'failed',
                'CANCELLED': 'failed',
                'cancelled': 'failed',
                'REFUNDED': 'failed',
                'refunded': 'failed'
            }
            
            normalized_status = status_map.get(status, 'pending') if status else 'pending'
            
            # Extrair payment_id do metadata
            payment_id = None
            if isinstance(data.get('metadata'), dict):
                payment_id = data.get('metadata', {}).get('payment_id')
            
            # Se não encontrou no metadata, tentar outros campos
            if not payment_id:
                payment_id = data.get('paymentId') or data.get('payment_id') or data.get('reference')
            
            # Extrair dados do pagador
            payer_name = None
            payer_document = None
            
            if isinstance(data.get('customer'), dict):
                customer = data.get('customer', {})
                payer_name = customer.get('name')
                payer_document = customer.get('document') or customer.get('cpf') or customer.get('cnpj')
            
            # Extrair end_to_end_id (E2E do BC)
            end_to_end_id = data.get('endToEndId') or data.get('end_to_end_id') or data.get('e2eId') or data.get('e2e_id')
            
            if not transaction_id:
                logger.error(f"❌ [{self.get_gateway_name()}] transaction_id não encontrado no webhook")
                return None
            
            logger.info(f"✅ [{self.get_gateway_name()}] Webhook processado")
            logger.info(f"   Transaction ID: {transaction_id}")
            logger.info(f"   Status: {normalized_status}")
            logger.info(f"   Amount: {amount}")
            
            return {
                'payment_id': payment_id,
                'status': normalized_status,
                'amount': float(amount) if amount else None,
                'gateway_transaction_id': str(transaction_id),
                'gateway_transaction_hash': str(transaction_id),
                'payer_name': payer_name,
                'payer_document': payer_document,
                'end_to_end_id': end_to_end_id
            }
            
        except Exception as e:
            logger.error(f"❌ [{self.get_gateway_name()}] Erro ao processar webhook: {e}")
            import traceback
            logger.error(f"📋 Traceback: {traceback.format_exc()}")
            return None
    
    def get_payment_status(self, transaction_id: str) -> Optional[Dict[str, Any]]:
        """
        Consulta status de um pagamento no UmbrellaPag
        
        Args:
            transaction_id: ID da transação no gateway
        
        Returns:
            Mesmo formato do process_webhook() ou None em caso de erro
        """
        try:
            logger.info(f"🔍 [{self.get_gateway_name()}] Consultando status: {transaction_id}")
            
            # Tentar buscar transação por ID
            response = self._make_request('GET', f'/user/transactions/{transaction_id}')
            
            if not response:
                logger.error(f"❌ [{self.get_gateway_name()}] Erro ao consultar status (sem resposta)")
                return None
            
            if response.status_code == 200:
                try:
                    data = response.json()
                    
                    # Processar como webhook
                    return self.process_webhook(data)
                    
                except json.JSONDecodeError as e:
                    logger.error(f"❌ [{self.get_gateway_name()}] Erro ao decodificar JSON: {e}")
                    return None
            else:
                logger.error(f"❌ [{self.get_gateway_name()}] Falha ao consultar status (status {response.status_code})")
                return None
                
        except Exception as e:
            logger.error(f"❌ [{self.get_gateway_name()}] Erro ao consultar status: {e}")
            return None

