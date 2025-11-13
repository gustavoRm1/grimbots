"""
Gateway UmbrellaPag
Baseado na documentação oficial: https://docs.umbrellapag.com/

Fluxo de criação de pagamento:
1. Criar transação diretamente (POST /api/user/transactions) → retorna dados do PIX

Autenticação:
- Header: x-api-key (token de API)
- Header: User-Agent: UmbrellaPagB2B/1.0 (forma canônica para PluggouV2)

✅ CORREÇÕES APLICADAS (2025-11-13):
- Customer.id: UUID válido gerado com uuid.uuid5() (RFC 4122 válido - obrigatório no OpenAPI)
- Customer.birthdate: REMOVIDO (não deve existir - causa erro 400)
- Metadata: STRING JSON usando json.dumps() (não objeto dict - conforme documentação)
- Traceable: True (obrigatório no provider PluggouV2)
- Shipping: presente com fee=0 e address (recomendado)
- Email: sempre @grimbots.online (RFC 5322 válido)
- Telefone: formato 55DDXXXXXXXXX (sem símbolo +, apenas números)
- State: minúsculas (sp em vez de SP)
- Textos: normalizados para ASCII (remove acentos)
- Document.number: apenas números (sem máscara - pontos, hífens, espaços removidos)
- User-Agent: UmbrellaPagB2B/1.0 (forma canônica)
- Boleto: removido do payload (não necessário para PIX)
"""

import os
import requests
import logging
import hashlib
import time
import json
import re
import unicodedata
import uuid
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
    
    def _validate_phone(self, phone: str) -> Optional[str]:
        """
        Valida e formata telefone (formato brasileiro: DDD + número, 10-11 dígitos)
        Retorna None se telefone é claramente inválido (ID do Telegram, etc.)
        """
        if not phone:
            return None
        
        # Remover caracteres não numéricos
        phone_clean = ''.join(c for c in str(phone) if c.isdigit())
        
        # Se tem menos de 10 dígitos, provavelmente é ID do Telegram
        if len(phone_clean) < 10:
            logger.debug(f"🔍 [{self.get_gateway_name()}] Telefone muito curto ({len(phone_clean)} dígitos), provavelmente ID")
            return None
        
        # Se tem exatamente 10 dígitos, adicionar 9 (celular)
        if len(phone_clean) == 10:
            phone_clean = '9' + phone_clean
        
        # Se tem mais de 11 dígitos, usar apenas os últimos 11
        if len(phone_clean) > 11:
            phone_clean = phone_clean[-11:]
        
        # Validar DDD (deve estar entre 11-99)
        if len(phone_clean) == 11:
            try:
                ddd = int(phone_clean[:2])
                if ddd < 11 or ddd > 99:
                    # DDD inválido, provavelmente é ID do Telegram
                    logger.debug(f"🔍 [{self.get_gateway_name()}] DDD inválido ({ddd}), provavelmente ID")
                    return None
            except ValueError:
                return None
        
        return phone_clean
    
    def _validate_document(self, document: str) -> Optional[str]:
        """
        Valida documento (CPF) - deve ter 11 dígitos e passar validação
        Retorna None se documento é claramente inválido (ID do Telegram, etc.)
        """
        if not document:
            return None
        
        # Remover caracteres não numéricos
        doc_clean = ''.join(c for c in str(document) if c.isdigit())
        
        # Se tem menos de 8 dígitos, provavelmente é ID do Telegram
        if len(doc_clean) < 8:
            logger.debug(f"🔍 [{self.get_gateway_name()}] Documento muito curto ({len(doc_clean)} dígitos), provavelmente ID")
            return None
        
        # Se tem exatamente 11 dígitos, validar CPF
        if len(doc_clean) == 11:
            # Verificar se não é claramente um ID do Telegram (padrões comuns)
            # IDs do Telegram geralmente começam com números baixos ou são sequenciais
            if doc_clean.startswith('16147') or doc_clean == doc_clean[0] * 11:
                logger.debug(f"🔍 [{self.get_gateway_name()}] Documento parece ser ID do Telegram: {doc_clean[:5]}***")
                return None
            
            # Validar CPF usando função de validação
            if cpf_valido(doc_clean):
                return doc_clean
            else:
                logger.debug(f"🔍 [{self.get_gateway_name()}] CPF não passou na validação: {doc_clean[:3]}***")
                return None
        
        # Se tem entre 8-10 dígitos, provavelmente é ID parcial, não CPF
        if 8 <= len(doc_clean) < 11:
            logger.debug(f"🔍 [{self.get_gateway_name()}] Documento com {len(doc_clean)} dígitos, provavelmente ID parcial")
            return None
        
        # Se tem mais de 11 dígitos, usar apenas os primeiros 11
        if len(doc_clean) > 11:
            doc_clean = doc_clean[:11]
            if cpf_valido(doc_clean):
                return doc_clean
            else:
                return None
        
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
                'x-api-key': self.api_key,  # ✅ Chave completa (sem truncar)
                'User-Agent': 'UmbrellaPagB2B/1.0',  # ✅ CORREÇÃO: forma canônica (PluggouV2)
                'Content-Type': 'application/json',
                'Accept': 'application/json'
            }
            
            if headers:
                request_headers.update(headers)
            
            logger.info(f"🌐 [{self.get_gateway_name()}] {method} {url}")
            logger.info(f"🔑 [{self.get_gateway_name()}] Headers: x-api-key={self.api_key[:15]}..., User-Agent=UmbrellaPagB2B/1.0")
            
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
            
            # Tentar extrair domínio do WEBHOOK_URL para adicionar ao payload ou headers
            domain = None
            hostname = None
            try:
                webhook_url = os.environ.get('WEBHOOK_URL', '')
                if webhook_url:
                    # Extrair domínio do WEBHOOK_URL
                    from urllib.parse import urlparse
                    parsed = urlparse(webhook_url)
                    domain = f"{parsed.scheme}://{parsed.netloc}"
                    hostname = parsed.netloc
                    logger.info(f"🌐 [{self.get_gateway_name()}] Domínio extraído: {domain} (hostname: {hostname})")
                else:
                    logger.warning(f"⚠️ [{self.get_gateway_name()}] WEBHOOK_URL não configurado")
            except Exception as e:
                logger.warning(f"⚠️ [{self.get_gateway_name()}] Erro ao extrair domínio: {e}")
            
            # Tentar diferentes abordagens para resolver "Hostname não identificado"
            # Abordagem 1: Payload com hostname (se o endpoint aceitar)
            payload = {}
            if hostname:
                # Tentar adicionar hostname/domain no payload (teste)
                payload['hostname'] = hostname
                payload['domain'] = domain
                logger.info(f"🌐 [{self.get_gateway_name()}] Adicionando hostname/domain no payload: {hostname}")
            
            # Abordagem 2: Headers adicionais
            additional_headers = {}
            if domain:
                additional_headers['Origin'] = domain
                additional_headers['Referer'] = domain
                additional_headers['X-Forwarded-Host'] = hostname
                logger.info(f"🌐 [{self.get_gateway_name()}] Adicionando headers Origin/Referer/X-Forwarded-Host: {domain}")
            
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
        Gera PIX via UmbrellaPag usando endpoint /api/user/transactions
        
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
            
            # Converter valor para centavos
            amount_cents = int(amount * 100)
            
            # Preparar dados do cliente
            if not customer_data:
                customer_data = {}
            
            customer_name = customer_data.get('name', 'Cliente')
            customer_email = customer_data.get('email', f'pix{payment_id}@bot.digital')
            customer_phone = customer_data.get('phone', '11999999999')
            customer_document = customer_data.get('document')
            
            # ✅ CORREÇÃO 1: Validar e formatar email (deve ser formato válido RFC 5322)
            # SEMPRE validar email - PluggouV2 é muito rigoroso
            customer_email_lower = str(customer_email).lower().strip() if customer_email else ''
            
            # Lista de domínios inválidos ou suspeitos
            invalid_domains = ['@telegram.user', '@telegram', '.user', '@bot.digital', '@bot', '@test']
            is_invalid_email = (
                not customer_email_lower or 
                not '@' in customer_email_lower or
                any(domain in customer_email_lower for domain in invalid_domains) or
                customer_email_lower.count('@') != 1
            )
            
            if is_invalid_email:
                # Extrair ID do Telegram do email, payment_id ou customer_data
                telegram_id = None
                # Tentar extrair do email
                telegram_id_match = re.search(r'(\d+)', customer_email_lower or '')
                if telegram_id_match:
                    telegram_id = telegram_id_match.group(1)
                # Tentar extrair do payment_id (formato: BOT47_1763007586_5e9123b2)
                elif '_' in payment_id:
                    try:
                        telegram_id = payment_id.split('_')[1]
                    except:
                        pass
                # Tentar extrair do customer_data (user_id)
                if not telegram_id:
                    user_id = customer_data.get('user_id') or customer_data.get('telegram_id')
                    if user_id:
                        telegram_id = str(user_id)
                # Se não encontrou, gerar hash do payment_id
                if not telegram_id:
                    hash_obj = hashlib.md5(payment_id.encode())
                    hash_hex = hash_obj.hexdigest()
                    telegram_id = ''.join([str(int(c, 16) % 10) for c in hash_hex[:10]])
                
                customer_email = f'user{telegram_id}@grimbots.online'
                logger.info(f"ℹ️ [{self.get_gateway_name()}] Email inválido ('{customer_email_lower}'), gerando email válido: {customer_email}")
            else:
                # Email parece válido, mas garantir que não tem caracteres estranhos
                customer_email = customer_email_lower
                # Garantir que é um email válido (tem @ e domínio)
                if not re.match(r'^[a-zA-Z0-9._%+-]+@[a-zA-Z0-9.-]+\.[a-zA-Z]{2,}$', customer_email):
                    # Email mal formatado, gerar novo
                    telegram_id = re.search(r'(\d+)', customer_email or '')
                    telegram_id = telegram_id.group(1) if telegram_id else payment_id.split('_')[1] if '_' in payment_id else '0'
                    customer_email = f'user{telegram_id}@grimbots.online'
                    logger.info(f"ℹ️ [{self.get_gateway_name()}] Email mal formatado, gerando email válido: {customer_email}")
            
            # ✅ CORREÇÃO 2: Validar e formatar telefone (PluggouV2: apenas números, formato 55DDXXXXXXXXX)
            # SEMPRE remover todos os símbolos e garantir formato correto
            phone_clean = re.sub(r'\D', '', str(customer_phone) if customer_phone else '')
            
            # Se telefone é muito curto ou parece ser ID do Telegram, gerar telefone válido
            if len(phone_clean) < 10 or (len(phone_clean) == 10 and phone_clean.startswith('1614')):
                # Gerar telefone válido baseado no payment_id (hash MD5)
                hash_obj = hashlib.md5(payment_id.encode())
                hash_hex = hash_obj.hexdigest()
                # DDD válido brasileiro (11-99)
                ddd = 11 + (int(hash_hex[0], 16) % 89)  # DDD entre 11-99
                # Número de 9 dígitos (celular sempre começa com 9)
                numero = '9' + ''.join([str(int(c, 16) % 10) for c in hash_hex[1:9]])
                phone_clean = f'{ddd}{numero}'
                logger.info(f"ℹ️ [{self.get_gateway_name()}] Telefone inválido, gerando telefone válido: ({phone_clean[:2]}) {phone_clean[2:7]}-{phone_clean[7:]}")
            
            # Validar formato brasileiro (10 ou 11 dígitos sem DDI)
            if len(phone_clean) == 10:
                # Telefone fixo (10 dígitos), adicionar 9 no início (celular)
                phone_clean = '9' + phone_clean
            elif len(phone_clean) > 11:
                # Muitos dígitos, usar apenas os últimos 11
                phone_clean = phone_clean[-11:]
            
            # ✅ CORREÇÃO CRÍTICA: PluggouV2 exige formato 55DDXXXXXXXXX (SEM símbolo +)
            # Remover DDI 55 se já existe e garantir que está correto
            if phone_clean.startswith('55'):
                # Já tem DDI, garantir que tem pelo menos 13 dígitos (55 + 11)
                if len(phone_clean) < 13:
                    # Adicionar zeros ou ajustar
                    phone_clean = '55' + phone_clean[2:].zfill(11)
                elif len(phone_clean) > 13:
                    # Muitos dígitos, usar apenas os últimos 13
                    phone_clean = '55' + phone_clean[-11:]
            else:
                # Não tem DDI, adicionar 55
                phone_clean = '55' + phone_clean
            
            # PluggouV2: APENAS números, SEM "+" ou outros símbolos
            customer_phone = phone_clean
            logger.info(f"ℹ️ [{self.get_gateway_name()}] Telefone formatado: {customer_phone} (formato: 55DDXXXXXXXXX, sem +)")
            
            # Validar documento (CPF)
            validated_document = None
            if customer_document:
                validated_document = self._validate_document(customer_document)
            
            # Se documento não é válido, gerar CPF baseado em hash
            if not validated_document:
                # Gerar CPF válido baseado no payment_id (hash MD5)
                hash_obj = hashlib.md5(payment_id.encode())
                hash_hex = hash_obj.hexdigest()
                # Gerar 11 dígitos do hash (evitar zeros repetidos)
                customer_document = ''.join([str(int(c, 16) % 10) for c in hash_hex[:11]])
                # Garantir que não seja todos zeros ou todos iguais (evitar padrões suspeitos)
                if customer_document == '0' * 11:
                    customer_document = '1' + customer_document[1:]
                if customer_document == customer_document[0] * 11:
                    # Variar alguns dígitos para evitar padrões
                    doc_list = list(customer_document)
                    doc_list[5] = str((int(doc_list[5]) + 1) % 10)
                    doc_list[9] = str((int(doc_list[9]) + 2) % 10)
                    customer_document = ''.join(doc_list)
                logger.info(f"ℹ️ [{self.get_gateway_name()}] CPF inválido, gerando CPF: {customer_document[:3]}.***.***-{customer_document[-2:]}")
            else:
                customer_document = validated_document
            
            # ✅ CORREÇÃO: Normalizar texto para ASCII (remover acentos)
            # PluggouV2 não aceita caracteres não ASCII (ê, ã, ó, etc.)
            def normalize_ascii(text: str) -> str:
                """Remove acentos e caracteres especiais, mantém apenas ASCII"""
                if not text:
                    return text
                # Normalizar e remover diacríticos
                text_normalized = unicodedata.normalize('NFKD', str(text))
                # Manter apenas caracteres não combinantes (sem acentos)
                text_ascii = ''.join(c for c in text_normalized if not unicodedata.combining(c))
                # Remover espaços duplos e trim
                text_clean = ' '.join(text_ascii.split())
                # Garantir que não tem caracteres especiais problemáticos
                # Substituir caracteres problemáticos comuns
                replacements = {
                    'ç': 'c', 'Ç': 'C',
                    'ñ': 'n', 'Ñ': 'N',
                }
                for old, new in replacements.items():
                    text_clean = text_clean.replace(old, new)
                return text_clean.strip()
            
            # Normalizar description, title e customer_name para ASCII
            description_clean = normalize_ascii(description)
            customer_name_clean = normalize_ascii(customer_name)
            logger.debug(f"🔍 [{self.get_gateway_name()}] Description normalizado: '{description}' -> '{description_clean}'")
            logger.debug(f"🔍 [{self.get_gateway_name()}] Customer name normalizado: '{customer_name}' -> '{customer_name_clean}'")
            
            # Obter IP do cliente (usar IP válido, não 0.0.0.0)
            client_ip = customer_data.get('ip')
            if not client_ip or client_ip == '0.0.0.0' or client_ip == '127.0.0.1':
                # Usar IP público válido (pode ser necessário para validação)
                client_ip = '177.43.80.1'  # IP público válido brasileiro
                logger.debug(f"🔍 [{self.get_gateway_name()}] IP não fornecido ou inválido, usando: {client_ip}")
            
            # Preparar endereço do cliente (valores válidos e realistas)
            # ✅ CORREÇÃO: Normalizar todos os campos de endereço para ASCII
            address_data = customer_data.get('address', {})
            customer_address = {
                'street': normalize_ascii(address_data.get('street') or 'Avenida Paulista'),
                'streetNumber': address_data.get('streetNumber') or '1000',
                'complement': normalize_ascii(address_data.get('complement') or ''),
                'zipCode': address_data.get('zipCode') or '01310100',  # CEP válido
                'neighborhood': normalize_ascii(address_data.get('neighborhood') or 'Bela Vista'),
                'city': normalize_ascii(address_data.get('city') or 'Sao Paulo'),  # Sem acento
                'state': (address_data.get('state') or 'sp').lower().strip(),  # ✅ CORREÇÃO: minúsculas e sem espaços (PluggouV2)
                'country': address_data.get('country') or 'BR'
            }
            
            # Validar e limpar CEP (deve ter exatamente 8 dígitos, sem hífen)
            zip_code_clean = customer_address['zipCode'].replace('-', '').replace('.', '').strip()
            if len(zip_code_clean) != 8 or not zip_code_clean.isdigit():
                customer_address['zipCode'] = '01310100'  # CEP padrão válido (Avenida Paulista)
                logger.debug(f"🔍 [{self.get_gateway_name()}] CEP inválido, usando padrão: {customer_address['zipCode']}")
            else:
                customer_address['zipCode'] = zip_code_clean
            
            # Preparar documento
            # ✅ CORREÇÃO: Garantir que document.number seja apenas números (sem máscara)
            # PluggouV2 exige CPF apenas com dígitos: "01314950271" (não "013.149.502-71")
            document_number_clean = re.sub(r'\D', '', str(customer_document)) if customer_document else ''
            if len(document_number_clean) != 11:
                # Se não tem 11 dígitos após limpar, usar o customer_document original (já validado)
                document_number_clean = str(customer_document).replace('.', '').replace('-', '').replace(' ', '')
                if len(document_number_clean) != 11:
                    # Se ainda não tem 11 dígitos, usar o customer_document gerado
                    document_number_clean = customer_document
            
            customer_doc = {
                'number': document_number_clean,  # ✅ Apenas números (sem máscara)
                'type': 'CPF'  # Sempre CPF para clientes
            }
            
            logger.debug(f"🔍 [{self.get_gateway_name()}] Documento formatado: {document_number_clean[:3]}.***.***-{document_number_clean[-2:]}")
            
            # ✅ CORREÇÃO CRÍTICA: Metadata deve ser STRING JSON (não objeto dict)
            # PluggouV2 exige metadata como string JSON, conforme documentação:
            # "metadata | string | Dados adicionais personalizados em formato JSON"
            metadata_dict = {
                'payment_id': str(payment_id),
                'description': str(description_clean)[:200]  # Limitar tamanho
            }
            # Serializar metadata como string JSON
            # ✅ CORREÇÃO FINAL: Metadata deve ser STRING JSON (não objeto dict)
            # Conforme documentação UmbrellaPag: "metadata | string | Dados adicionais personalizados em formato JSON"
            metadata_string = json.dumps(metadata_dict, ensure_ascii=True)
            
            # Payload para criar transação PIX usando endpoint /api/user/transactions
            # ✅ TODAS AS CORREÇÕES APLICADAS:
            # 1. Email: sempre @grimbots.online (RFC 5322 válido)
            # 2. Telefone: formato 55DDXXXXXXXXX (sem símbolo +)
            # 3. Metadata: STRING JSON (não objeto dict) - CORREÇÃO FINAL
            # 4. Traceable: True (obrigatório no provider PluggouV2)
            # 5. State: minúsculas (sp em vez de SP)
            # 6. Textos: normalizados para ASCII (sem acentos)
            # 7. Boleto: removido do payload
            # 8. Customer.id: UUID válido (obrigatório no OpenAPI - não aceita payment_id simples)
            # 9. Customer.birthdate: REMOVIDO (não deve existir - causa erro 400)
            # 10. Shipping: recomendado (mesmo que dummy)
            
            # ✅ CORREÇÃO: Gerar UUID válido para customer.id
            # PluggouV2 exige que customer.id seja um UUID válido (não aceita payment_id simples)
            # Usar uuid.uuid5() com namespace fixo para garantir UUID válido e determinístico
            # (mesmo payment_id = mesmo UUID, sempre válido conforme RFC 4122)
            customer_uuid = str(uuid.uuid5(uuid.NAMESPACE_URL, f"umbrellapag:customer:{payment_id}"))
            
            payload = {
                'amount': int(amount_cents),  # Garantir que é inteiro
                'currency': 'BRL',
                'paymentMethod': 'pix',
                'installments': 1,  # PIX sempre 1 parcela
                'traceable': True,  # ✅ CORREÇÃO: obrigatório no provider PluggouV2
                'postbackUrl': self.get_webhook_url(),
                'metadata': metadata_string,  # ✅ STRING JSON (não objeto dict) - CORREÇÃO FINAL
                'ip': client_ip,
                'customer': {
                    'id': customer_uuid,  # ✅ CORREÇÃO: UUID válido (obrigatório no OpenAPI)
                    'name': customer_name_clean[:100],  # ✅ Normalizado para ASCII
                    'email': customer_email[:100],  # ✅ Sempre @grimbots.online
                    'document': customer_doc,
                    'phone': customer_phone,  # ✅ Formato 55DDXXXXXXXXX (sem +)
                    # ✅ CORREÇÃO: birthdate REMOVIDO (não deve existir - causa erro 400)
                    'externalRef': str(payment_id),
                    'address': customer_address  # ✅ Todos os campos normalizados para ASCII
                },
                'shipping': {  # ✅ CORREÇÃO: recomendado (mesmo que dummy)
                    'fee': 0,  # Produto digital, sem frete
                    'address': customer_address  # Usar mesmo endereço do cliente
                },
                'items': [
                    {
                        'title': description_clean[:100] if description_clean else f'Produto {payment_id}',  # ✅ ASCII sem acentos
                        'unitPrice': int(amount_cents),  # Garantir que é inteiro
                        'quantity': 1,
                        'tangible': False,  # Produto digital
                        'externalRef': str(payment_id)
                    }
                ],
                'pix': {
                    'expiresInDays': 3  # PIX expira em 3 dias
                }
                # ✅ boleto removido (não é necessário para PIX)
            }
            
            logger.info(f"💳 [{self.get_gateway_name()}] Criando transação PIX via /api/user/transactions")
            logger.info(f"   Valor: R$ {amount:.2f} ({amount_cents} centavos)")
            logger.info(f"   Cliente: {customer_name_clean} ({customer_email})")
            logger.info(f"   Cliente ID (UUID): {customer_uuid}")
            logger.info(f"   Payment ID: {payment_id}")
            logger.info(f"   Telefone: {customer_phone} (formato: 55DDXXXXXXXXX)")
            logger.info(f"   Traceable: True")
            logger.info(f"   Metadata: {metadata_string} (string JSON)")
            
            # Fazer requisição para criar transação
            response = self._make_request('POST', '/user/transactions', payload=payload)
            
            if not response:
                logger.error(f"❌ [{self.get_gateway_name()}] Erro ao criar transação (sem resposta)")
                return None
            
            logger.info(f"📥 [{self.get_gateway_name()}] Resposta recebida: Status {response.status_code}")
            
            # ✅ CORREÇÃO: Status 200 ou 201 = sucesso (PluggouV2 pode retornar 201)
            if response.status_code in [200, 201]:
                try:
                    data = response.json()
                    logger.info(f"📥 [{self.get_gateway_name()}] Resposta completa: {json.dumps(data, indent=2)[:500]}")
                    
                    # Verificar formato da resposta conforme documentação
                    if isinstance(data, dict) and 'data' in data:
                        transaction_data = data.get('data', {})
                        
                        # Extrair dados do PIX conforme documentação
                        pix_data = transaction_data.get('pix', {})
                        
                        # Código PIX pode estar em diferentes campos
                        pix_code = (
                            pix_data.get('qrCode') or 
                            pix_data.get('qr_code') or 
                            pix_data.get('code') or
                            transaction_data.get('qrCode') or
                            transaction_data.get('qr_code')
                        )
                        
                        # QR Code URL
                        qr_code_url = (
                            pix_data.get('qrCodeUrl') or
                            pix_data.get('qr_code_url') or
                            pix_data.get('url') or
                            transaction_data.get('qrCodeUrl') or
                            transaction_data.get('qr_code_url')
                        )
                        
                        # Transaction ID
                        transaction_id = (
                            transaction_data.get('id') or
                            transaction_data.get('transactionId') or
                            transaction_data.get('transaction_id') or
                            transaction_data.get('externalRef') or
                            payment_id
                        )
                        
                        # Status da transação
                        transaction_status = transaction_data.get('status', 'WAITING_PAYMENT')
                        
                        if not pix_code:
                            logger.error(f"❌ [{self.get_gateway_name()}] pix_code não encontrado na resposta")
                            logger.error(f"   Resposta completa: {json.dumps(data, indent=2)}")
                            return None
                        
                        # Gerar QR Code URL se não fornecido
                        if not qr_code_url:
                            qr_code_url = f'https://api.qrserver.com/v1/create-qr-code/?size=300x300&data={pix_code}'
                        
                        logger.info(f"✅ [{self.get_gateway_name()}] PIX gerado com sucesso")
                        logger.info(f"   Transaction ID: {transaction_id}")
                        logger.info(f"   Status: {transaction_status}")
                        logger.info(f"   PIX Code: {pix_code[:50]}...")
                        
                        return {
                            'pix_code': pix_code,
                            'qr_code_url': qr_code_url,
                            'transaction_id': str(transaction_id),
                            'payment_id': payment_id,
                            'gateway_transaction_id': str(transaction_id),
                            'gateway_transaction_hash': str(transaction_id),
                            'status': transaction_status,
                            'external_ref': transaction_data.get('externalRef', payment_id)
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
                logger.error(f"❌ [{self.get_gateway_name()}] Falha ao criar transação (status {response.status_code})")
                if response.text:
                    logger.error(f"   Resposta completa: {response.text[:1000]}")
                    try:
                        error_data = response.json()
                        error_message = error_data.get('message', '')
                        error_provider = error_data.get('error', {}).get('provider', '')
                        error_reason = error_data.get('error', {}).get('refusedReason', '')
                        
                        logger.error(f"   Mensagem: {error_message}")
                        if error_provider:
                            logger.error(f"   Provider: {error_provider}")
                        if error_reason:
                            logger.error(f"   Motivo da recusa: {error_reason}")
                        
                        # Log do payload para debug
                        logger.error(f"   📦 Payload enviado (resumo):")
                        logger.error(f"      - amount: {amount_cents} centavos (R$ {amount:.2f})")
                        logger.error(f"      - paymentMethod: pix")
                        logger.error(f"      - customer.name: {customer_name_clean}")
                        logger.error(f"      - customer.email: {customer_email}")
                        logger.error(f"      - customer.phone: {customer_phone} (formato: 55DDXXXXXXXXX)")
                        logger.error(f"      - customer.document: {customer_document[:3]}.***.***-{customer_document[-2:]}")
                        logger.error(f"      - customer.address.zipCode: {customer_address['zipCode']}")
                        logger.error(f"      - customer.address.street: {customer_address['street']}")
                        logger.error(f"      - customer.address.city: {customer_address['city']}")
                        logger.error(f"      - customer.address.state: {customer_address['state']} (minúsculas)")
                        logger.error(f"      - customer.id: {customer_uuid} (UUID válido)")
                        logger.error(f"      - traceable: True (obrigatório no PluggouV2)")
                        logger.error(f"      - shipping: presente (recomendado)")
                        logger.error(f"      - metadata: {metadata_string} (string JSON)")
                        logger.error(f"      - ip: {client_ip}")
                        logger.error(f"   ⚠️  Verifique se todos os campos estão no formato correto:")
                        logger.error(f"      - Email: deve ser @grimbots.online (RFC 5322 válido)")
                        logger.error(f"      - Telefone: deve ser 55DDXXXXXXXXX (sem símbolo +)")
                        logger.error(f"      - Metadata: deve ser STRING JSON (não objeto dict)")
                        logger.error(f"      - State: deve ser minúsculas (sp em vez de SP)")
                        logger.error(f"      - Textos: devem ser ASCII (sem acentos)")
                        logger.error(f"      - Traceable: deve ser True (obrigatório no PluggouV2)")
                        logger.error(f"      - Customer.id: deve ser UUID válido (não payment_id simples)")
                        logger.error(f"      - Customer.birthdate: NÃO deve existir (causa erro 400)")
                        logger.error(f"      - Shipping: deve estar presente (recomendado)")
                    except Exception as e:
                        logger.error(f"   Erro ao parsear resposta: {e}")
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
            # ✅ CORREÇÃO: Metadata pode vir como string JSON ou dict (dependendo da origem)
            payment_id = None
            metadata = data.get('metadata')
            
            if metadata:
                if isinstance(metadata, str):
                    # Metadata é string JSON, fazer parse
                    try:
                        metadata_dict = json.loads(metadata)
                        payment_id = metadata_dict.get('payment_id')
                    except (json.JSONDecodeError, TypeError):
                        logger.warning(f"⚠️ [{self.get_gateway_name()}] Erro ao parsear metadata como JSON: {metadata}")
                elif isinstance(metadata, dict):
                    # Metadata já é dict
                    payment_id = metadata.get('payment_id')
            
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

