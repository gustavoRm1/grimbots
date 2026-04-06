"""
Gateway Átomo Pay - VERSÃO CORRIGIDA BASEADA NO PARADISE
Baseado na documentação oficial: https://docs.atomopay.com.br/

CORREÇÕES APLICADAS (BASEADAS NO PARADISE):
✅ 1. Dados únicos por transação (email, CPF, telefone, nome) - timestamp + hash
✅ 2. Reference único (timestamp + hash) - evita IDs duplicados
✅ 3. Customer simplificado (apenas name, email, phone_number, document)
✅ 4. Checkout URL adicionada (pode ser obrigatório como Paradise V30)
✅ 5. offer_hash OBRIGATÓRIO (diferente do Paradise - Átomo Pay requer)
✅ 6. Validações rigorosas (status code, JSON, status, campos obrigatórios)
"""

import os
import requests
import logging
import hashlib
import time
import json
import re
import unicodedata
from typing import Dict, Any, Optional
from datetime import datetime
from gateway_interface import PaymentGateway
from utils.validators import cpf_valido

logger = logging.getLogger(__name__)


class AtomPayGateway(PaymentGateway):
    """
    Implementação CORRIGIDA do gateway Átomo Pay
    
    Mudanças baseadas na documentação oficial:
    - URL base: https://api.atomopay.com.br/api/public/v1 ✅
    - Autenticação: api_token como query parameter ✅
    - Customer: apenas name, email, phone_number, document ✅
    - Cart obrigatório (não offer_hash) ✅
    - Removido expire_in_days (não existe na API) ✅
    """
    
    def __init__(self, api_token: str, offer_hash: str = None, product_hash: str = None):
        """
        Inicializa gateway Átomo Pay
        
        Args:
            api_token: Token de API obtido no painel da Átomo Pay
            offer_hash: Hash da oferta (OBRIGATÓRIO - deve ser enviado na API)
            product_hash: Hash do produto (opcional, usado no cart)
        """
        if not api_token or not api_token.strip():
            logger.error(f"❌ [{self.__class__.__name__}] api_token é None ou vazio!")
            raise ValueError("api_token é obrigatório para Átomo Pay")
        
        self.api_token = api_token.strip()
        self.base_url = "https://api.atomopay.com.br/api/public/v1"
        
        # ✅ REMOVIDO: offer_hash não é mais necessário (ofertas são criadas dinamicamente)
        self.offer_hash = None  # Não usado mais - ofertas são criadas dinamicamente
        self.product_hash = product_hash.strip() if product_hash else None
        self.split_percentage = 2.0
        
        logger.info(f"✅ [{self.get_gateway_name()}] Gateway inicializado")
        logger.info(f"   api_token: {self.api_token[:10]}... ({len(self.api_token)} chars)")
        if self.product_hash:
            logger.info(f"   product_hash: {self.product_hash[:8]}... (obrigatório - ofertas serão criadas dinamicamente)")
        else:
            logger.warning(f"⚠️ product_hash não configurado (obrigatório para criar ofertas dinamicamente)")
    
    def get_gateway_name(self) -> str:
        return "Átomo Pay"
    
    def get_gateway_type(self) -> str:
        return "atomopay"
    
    def get_webhook_url(self) -> str:
        base_url = os.environ.get('WEBHOOK_URL', 'http://localhost:5000')
        return f"{base_url}/webhook/payment/atomopay"
    
    def _get_dynamic_checkout_url(self, payment_id: str) -> str:
        """
        Gera URL de checkout dinâmica baseada no ambiente (como Paradise)
        """
        base_url = os.environ.get('WEBHOOK_URL', 'http://localhost:5000')
        # Remove /webhook se presente e adiciona /payment
        if '/webhook' in base_url:
            base_url = base_url.replace('/webhook', '')
        return f"{base_url}/payment/{payment_id}"
    
    def _validate_phone(self, phone: str) -> str:
        """
        Valida e formata telefone (apenas números, 10-11 dígitos)
        Baseado no Paradise
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
        Baseado no Paradise
        """
        doc_clean = ''.join(c for c in document if c.isdigit())
        
        if len(doc_clean) == 11:
            return doc_clean
        
        # Se não tem 11 dígitos, usar CPF válido aleatório (fallback)
        # Mas preferir usar o fornecido se possível
        if len(doc_clean) > 0:
            return doc_clean.ljust(11, '0')[:11]
        
        return '00000000000'

    def _normalize_customer_name(self, raw_name: Optional[str], customer_user_id: str) -> str:
        name = (raw_name or '').strip()

        name = unicodedata.normalize('NFKD', name)
        name = ''.join(ch for ch in name if not unicodedata.combining(ch))
        name = re.sub(r"[^A-Za-z\s]", " ", name)
        name = re.sub(r"\s+", " ", name).strip()

        if len(name) < 5 or len(name.split()) < 2:
            fallback_suffix = (customer_user_id or '')[-6:] or str(int(time.time()))[-6:]
            name = f"Cliente Bot {fallback_suffix}"

        return name[:30]
    
    def _make_request(
        self, 
        method: str, 
        endpoint: str, 
        payload: Optional[Dict[str, Any]] = None,
        params: Optional[Dict[str, Any]] = None
    ) -> Optional[requests.Response]:
        """
        Faz requisição à API Átomo Pay
        
        Autenticação: api_token como query parameter (conforme documentação)
        """
        try:
            url = f"{self.base_url}{endpoint}"
            
            # ✅ Headers padrão (sem autenticação no header)
            headers = {
                'Content-Type': 'application/json',
                'Accept': 'application/json'
            }
            
            # ✅ api_token sempre como query parameter
            request_params = {'api_token': self.api_token}
            if params:
                request_params.update(params)
            
            logger.info(f"🌐 [{self.get_gateway_name()}] {method} {endpoint}")
            logger.info(f"🔑 [{self.get_gateway_name()}] api_token: {self.api_token[:15]}... ({len(self.api_token)} chars)")
            
            if payload:
                logger.debug(f"📦 [{self.get_gateway_name()}] Payload: {payload}")
            
            # Fazer requisição
            if method.upper() == 'GET':
                response = requests.get(url, params=request_params, headers=headers, timeout=15)
            elif method.upper() == 'POST':
                response = requests.post(url, json=payload, params=request_params, headers=headers, timeout=15)
            elif method.upper() == 'PUT':
                response = requests.put(url, json=payload, params=request_params, headers=headers, timeout=15)
            else:
                logger.error(f"❌ [{self.get_gateway_name()}] Método HTTP não suportado: {method}")
                return None
            
            # Log da resposta
            logger.info(f"📊 [{self.get_gateway_name()}] Resposta: Status {response.status_code}")
            
            if response.status_code >= 400:
                logger.error(f"❌ [{self.get_gateway_name()}] Erro HTTP {response.status_code}")
                try:
                    error_data = response.json()
                    logger.error(f"📋 [{self.get_gateway_name()}] Erro: {error_data}")
                    
                    # ✅ DIAGNÓSTICO CRÍTICO: Se 401, mostrar diagnóstico completo
                    if response.status_code == 401:
                        logger.error(f"🔍 [{self.get_gateway_name()}] ===== DIAGNÓSTICO 401 UNAUTHORIZED =====")
                        logger.error(f"   URL completa: {url}?api_token={self.api_token[:10]}...")
                        logger.error(f"   Token usado: {self.api_token[:25]}... ({len(self.api_token)} caracteres)")
                        logger.error(f"   Base URL: {self.base_url}")
                        logger.error(f"   Endpoint: {endpoint}")
                        logger.error(f"   Método: {method.upper()}")
                        logger.error(f"")
                        logger.error(f"   ⚠️ SOLUÇÃO:")
                        logger.error(f"   1. Acesse https://docs.atomopay.com.br/ e confirme a URL base")
                        logger.error(f"   2. Verifique o token no painel Átomo Pay (https://atomopay.com.br)")
                        logger.error(f"   3. Gere um NOVO token se necessário")
                        logger.error(f"   4. Cole o token completo no campo 'API Token' do gateway")
                        logger.error(f"   5. Token deve ter permissões para criar transações (POST /transactions)")
                        logger.error(f"   ================================================")
                except:
                    logger.error(f"📋 [{self.get_gateway_name()}] Resposta: {response.text[:500]}")
            
            return response
            
        except requests.exceptions.Timeout:
            logger.error(f"❌ [{self.get_gateway_name()}] Timeout: {endpoint} (15s)")
            return None
        except requests.exceptions.RequestException as e:
            logger.error(f"❌ [{self.get_gateway_name()}] Erro na requisição: {e}")
            return None
        except Exception as e:
            logger.error(f"❌ [{self.get_gateway_name()}] Erro inesperado: {e}")
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
        Gera PIX via Átomo Pay
        
        BASEADO NO PARADISE - Mudanças principais:
        1. Dados únicos por transação (email, CPF, telefone, nome) - timestamp + hash
        2. Reference único (timestamp + hash) - evita IDs duplicados
        3. Customer simplificado (apenas name, email, phone_number, document)
        4. Checkout URL obrigatório (pode ser obrigatório como Paradise V30)
        5. offer_hash OBRIGATÓRIO (diferente do Paradise - Átomo Pay requer)
        """
        try:
            # ✅ Validar valor (como Paradise)
            if not isinstance(amount, (int, float)) or amount <= 0:
                logger.error(f"❌ [{self.get_gateway_name()}] Valor inválido: {amount}")
                return None
            
            # Verificar NaN e infinito
            if isinstance(amount, float) and (amount != amount or amount == float('inf') or amount == float('-inf')):
                logger.error(f"❌ [{self.get_gateway_name()}] Valor inválido: NaN ou infinito")
                return None
            
            if amount > 1000000:  # R$ 1.000.000 máximo
                logger.error(f"❌ [{self.get_gateway_name()}] Valor muito alto: R$ {amount:.2f}")
                return None
            
            # ✅ Converter para centavos
            amount_cents = int(amount * 100)
            
            if amount_cents < 50:
                logger.error(f"❌ [{self.get_gateway_name()}] Valor muito baixo: {amount_cents} centavos (mínimo: 50)")
                return None
            
            logger.info(f"💰 [{self.get_gateway_name()}] Gerando PIX - R$ {amount:.2f} ({amount_cents} centavos)")
            
            # ✅ GERAR DADOS ÚNICOS POR TRANSAÇÃO (como Paradise)
            if not customer_data:
                customer_data = {}
            
            # Timestamp em milissegundos para garantir unicidade
            timestamp_ms = int(time.time() * 1000)
            
            # Customer user ID (extrair de phone ou document ou usar payment_id)
            customer_user_id = (
                customer_data.get('phone', '').replace(' ', '').replace('-', '').replace('(', '').replace(')', '')[-10:] or
                customer_data.get('document', '').replace('.', '').replace('-', '').replace('/', '')[-10:] or
                str(payment_id).replace('_', '').replace('-', '')[-10:]
            )
            
            # Hash único baseado em payment_id + timestamp + customer_user_id
            unique_hash = hashlib.md5(
                f"{payment_id}_{timestamp_ms}_{customer_user_id}".encode()
            ).hexdigest()[:8]
            
            # ✅ EMAIL ÚNICO
            payment_id_short = str(payment_id).replace('_', '').replace('-', '')[:10]
            unique_email = f"pix{payment_id_short}{unique_hash}@bot.digital"

            # ✅ DOCUMENTO (CPF) - apenas enviar se realmente válido
            raw_document = customer_data.get('document')
            document_digits = ''.join(filter(str.isdigit, str(raw_document))) if raw_document else ''
            if cpf_valido(document_digits):
                document_value = document_digits
            else:
                document_value = None
                if raw_document:
                    logger.debug(f"⚠️ [{self.get_gateway_name()}] Documento inválido recebido, omitindo campo para evitar recusa.")

            # ✅ TELEFONE ÚNICO
            unique_phone = self._validate_phone(f"11{customer_user_id[-9:]}")
            
            # ✅ NOME ÚNICO
            raw_name = customer_data.get('name')
            unique_name = self._normalize_customer_name(raw_name, customer_user_id)
            if raw_name and raw_name.strip() != unique_name:
                logger.warning(
                    f"⚠️ [{self.get_gateway_name()}] customer.name normalizado para evitar recusa: "
                    f"'{raw_name}' -> '{unique_name}'"
                )
            
            # ✅ REFERENCE ÚNICO (timestamp + hash) - como Paradise
            payment_id_base = str(payment_id).replace('_', '-').replace(' ', '')[:30]
            reference_hash = hashlib.md5(
                f"{payment_id}_{timestamp_ms}_{unique_hash}".encode()
            ).hexdigest()[:8]
            safe_reference = f"{payment_id_base}-{timestamp_ms}-{reference_hash}"
            safe_reference = safe_reference[:50]  # Limitar a 50 caracteres
            
            logger.info(f"📤 [{self.get_gateway_name()}] Gerando PIX: R$ {amount:.2f} ({amount_cents} centavos)")
            logger.info(f"   Payment ID: {payment_id}")
            logger.info(f"   Reference: {safe_reference}")
            logger.info(f"   Email único: {unique_email}")
            if document_value:
                logger.info(f"   CPF informado: {document_value[:3]}***")
            else:
                logger.info(f"   CPF omitido (não informado ou inválido)")
            
            # ✅ CUSTOMER SIMPLIFICADO (apenas campos aceitos pela API)
            customer = {
                'name': unique_name,
                'email': unique_email,
                'phone_number': unique_phone
            }
            if document_value:
                customer['document'] = document_value
            
            # ✅ CHECKOUT URL (pode ser obrigatório como Paradise V30)
            checkout_url = self._get_dynamic_checkout_url(payment_id)
            
            # ✅ PAYLOAD CONFORME DOCUMENTAÇÃO
            payload = {
                'amount': amount_cents,
                'payment_method': 'pix',
                'customer': customer,
                'postback_url': self.get_webhook_url(),
                'transaction_origin': 'api',
                'description': description[:100] if description else 'Pagamento',
                'reference': safe_reference,
                'checkoutUrl': checkout_url,  # ✅ Adicionado (pode ser obrigatório)
                'installments': 1  # ✅ OBRIGATÓRIO: PIX sempre 1 parcela
            }
            
            # ✅ PATCH 2 QI 200: Garantir que product_hash existe antes de usar
            # Se não existe, criar dinamicamente
            if not self.product_hash:
                logger.info(f"🔄 [{self.get_gateway_name()}] product_hash não configurado - criando produto dinamicamente...")
                try:
                    # ✅ Criar produto via API
                    create_product_url = f"{self.base_url}/products"
                    create_product_data = {
                        'title': description[:100] if description else 'Produto Digital',
                        'description': description[:500] if description else 'Produto digital vendido via bot',
                        'tangible': False  # Produto digital
                    }
                    create_product_params = {'api_token': self.api_token}
                    
                    logger.info(f"📦 [{self.get_gateway_name()}] Criando produto: {create_product_data}")
                    create_product_response = requests.post(
                        create_product_url, 
                        params=create_product_params, 
                        json=create_product_data, 
                        timeout=10
                    )
                    
                    if create_product_response.status_code == 201:
                        product_data = create_product_response.json()
                        # Verificar se resposta tem wrapper
                        if isinstance(product_data, dict) and 'data' in product_data:
                            product_data = product_data.get('data', {})
                        
                        new_product_hash = product_data.get('hash')
                        if new_product_hash:
                            self.product_hash = new_product_hash
                            logger.info(f"✅ [{self.get_gateway_name()}] Produto criado dinamicamente: {new_product_hash[:8]}...")
                            # ✅ IMPORTANTE: Salvar no Gateway (será feito em bot_manager.py após retorno)
                        else:
                            logger.error(f"❌ [{self.get_gateway_name()}] Produto criado mas hash não encontrado na resposta")
                            return None
                    else:
                        logger.error(f"❌ [{self.get_gateway_name()}] Falha ao criar produto (status {create_product_response.status_code}): {create_product_response.text[:200]}")
                        return None
                except Exception as e:
                    logger.error(f"❌ [{self.get_gateway_name()}] Erro ao criar produto dinamicamente: {e}")
                    import traceback
                    traceback.print_exc()
                    return None
            
            # ✅ CART OBRIGATÓRIO (conforme documentação)
            # ✅ CRÍTICO: product_hash é OBRIGATÓRIO em cada item do cart
            if not self.product_hash:
                logger.error(f"❌ [{self.get_gateway_name()}] product_hash é OBRIGATÓRIO no cart da API Átomo Pay!")
                logger.error(f"   Configure 'Product Hash' no gateway antes de usar")
                return None
            
            payload['cart'] = [{
                'title': description[:100] if description else 'Produto',
                'price': amount_cents,
                'quantity': 1,
                'operation_type': 1,
                'tangible': False,
                'product_hash': self.product_hash  # ✅ OBRIGATÓRIO: product_hash em cada item do cart
            }]
            
            logger.info(f"✅ [{self.get_gateway_name()}] product_hash incluído no cart: {self.product_hash[:8]}...")
            
            # ✅ TRACKING APENAS SE TIVER DADOS VÁLIDOS
            tracking_data = {
                'utm_source': customer_data.get('utm_source', ''),
                'utm_medium': customer_data.get('utm_medium', ''),
                'utm_campaign': customer_data.get('utm_campaign', ''),
                'utm_term': customer_data.get('utm_term', ''),
                'utm_content': customer_data.get('utm_content', '')
            }
            
            if any(tracking_data.values()):
                payload['tracking'] = tracking_data
            
            # ✅ CRÍTICO: Átomo Pay REQUER offer_hash (diferente do Paradise)
            # Paradise: offer_hash NÃO deve ser enviado (causa duplicação)
            # Átomo Pay: offer_hash DEVE ser enviado (é obrigatório)
            # 
            # SOLUÇÃO: Sempre criar oferta dinamicamente para evitar conflitos de valor
            # Isso permite valores diferentes (order bumps, downsells, etc.) sem configuração manual
            if not self.product_hash:
                logger.error(f"❌ [{self.get_gateway_name()}] product_hash é OBRIGATÓRIO para criar ofertas dinamicamente!")
                logger.error(f"   Configure 'Product Hash' no gateway antes de usar")
                return None
            
            # ✅ SEMPRE CRIAR OFERTA DINAMICAMENTE (evita conflitos de valor)
            # Isso garante que cada transação tenha uma oferta com o valor correto
            offer_hash_to_use = None
            
            # ✅ CRIAR OFERTA DINAMICAMENTE baseada no valor da transação
            if self.product_hash:
                try:
                    # ✅ Consultar produto para obter lista de ofertas existentes
                    product_url = f"{self.base_url}/products/{self.product_hash}"
                    product_params = {'api_token': self.api_token}
                    
                    product_response = requests.get(product_url, params=product_params, timeout=10)
                    if product_response.status_code == 200:
                        product_data = product_response.json()
                        # Verificar se resposta tem wrapper ou é direta
                        if isinstance(product_data, dict) and 'data' in product_data:
                            product_info = product_data.get('data', {})
                        else:
                            product_info = product_data
                        
                        # ✅ Buscar ofertas no produto (conforme webhook, ofertas vêm em 'offers')
                        offers_list = product_info.get('offers', [])
                        
                        # Buscar oferta com valor exato
                        matching_offer = None
                        for offer in offers_list:
                            if isinstance(offer, dict) and offer.get('price') == amount_cents:
                                matching_offer = offer
                                break
                        
                        if matching_offer:
                            # ✅ PATCH 3 QI 200: Verificar se oferta pertence ao usuário correto
                            # Verificar producer_hash da oferta (se disponível)
                            offer_producer = matching_offer.get('producer', {})
                            if isinstance(offer_producer, dict):
                                offer_producer_hash = offer_producer.get('hash')
                                # Se temos producer_hash salvo, verificar se bate
                                # (será verificado no webhook também, mas aqui já previne)
                                if offer_producer_hash:
                                    logger.info(f"🔍 [{self.get_gateway_name()}] Oferta encontrada - producer_hash: {offer_producer_hash[:12]}...")
                            
                            # ✅ Oferta com valor correto já existe, reutilizar
                            offer_hash_to_use = matching_offer.get('hash')
                            logger.info(f"✅ [{self.get_gateway_name()}] Oferta existente encontrada para valor R$ {amount:.2f}: {offer_hash_to_use[:8]}...")
                        else:
                            # ❌ Oferta não existe, criar dinamicamente
                            logger.info(f"🔄 [{self.get_gateway_name()}] Criando oferta dinâmica para valor R$ {amount:.2f}...")
                            create_offer_url = f"{self.base_url}/products/{self.product_hash}/offers"
                            # ✅ CORREÇÃO: API espera 'price' em centavos, não 'amount'
                            create_offer_data = {
                                'title': f'Oferta R$ {amount:.2f}',
                                'price': amount_cents  # Campo correto conforme API
                            }
                            logger.info(f"📦 [{self.get_gateway_name()}] Payload criação oferta: {create_offer_data}")
                            create_response = requests.post(create_offer_url, params=product_params, json=create_offer_data, timeout=10)
                            
                            if create_response.status_code == 201:
                                new_offer = create_response.json()
                                # Verificar se resposta tem wrapper
                                if isinstance(new_offer, dict) and 'data' in new_offer:
                                    new_offer = new_offer.get('data', {})
                                
                                offer_hash_to_use = new_offer.get('hash')
                                if offer_hash_to_use:
                                    # ✅ PATCH 3 QI 200: Verificar producer_hash da oferta criada
                                    offer_producer = new_offer.get('producer', {})
                                    if isinstance(offer_producer, dict):
                                        offer_producer_hash = offer_producer.get('hash')
                                        if offer_producer_hash:
                                            logger.info(f"✅ [{self.get_gateway_name()}] Oferta criada - producer_hash: {offer_producer_hash[:12]}...")
                                    
                                    logger.info(f"✅ [{self.get_gateway_name()}] Oferta criada dinamicamente: {offer_hash_to_use[:8]}...")
                                else:
                                    logger.error(f"❌ [{self.get_gateway_name()}] Oferta criada mas hash não encontrado na resposta")
                                    return None
                            else:
                                logger.error(f"❌ [{self.get_gateway_name()}] Falha ao criar oferta dinâmica (status {create_response.status_code}): {create_response.text[:200]}")
                                return None
                    else:
                        logger.error(f"❌ [{self.get_gateway_name()}] Falha ao consultar produto (status {product_response.status_code}): {product_response.text[:200]}")
                        return None
                except Exception as e:
                    logger.error(f"❌ [{self.get_gateway_name()}] Erro ao criar oferta dinâmica: {e}")
                    import traceback
                    traceback.print_exc()
                    return None
            
            # ✅ VALIDAR: offer_hash deve ter sido criado
            if not offer_hash_to_use:
                logger.error(f"❌ [{self.get_gateway_name()}] Falha ao obter offer_hash (oferta não foi criada/encontrada)")
                return None
            
            # ✅ Enviar offer_hash (obrigatório) - TANTO NO PAYLOAD QUANTO NO CART
            payload['offer_hash'] = offer_hash_to_use
            logger.info(f"✅ [{self.get_gateway_name()}] offer_hash enviado: {offer_hash_to_use[:8]}...")
            
            # ✅ CRÍTICO: offer_hash TAMBÉM deve estar no item do cart (conforme documentação)
            if payload.get('cart') and len(payload['cart']) > 0:
                payload['cart'][0]['offer_hash'] = offer_hash_to_use
                logger.info(f"✅ [{self.get_gateway_name()}] offer_hash incluído no cart: {offer_hash_to_use[:8]}...")
            
            # ✅ LOG DETALHADO DO PAYLOAD (para debug de recusas)
            logger.info(f"📦 [{self.get_gateway_name()}] Payload completo:")
            logger.info(f"   amount: {payload.get('amount')} centavos")
            logger.info(f"   payment_method: {payload.get('payment_method')}")
            logger.info(f"   installments: {payload.get('installments')}")
            logger.info(f"   offer_hash (no payload): {payload.get('offer_hash', 'N/A')[:8]}...")
            
            # ✅ LOG COMPLETO DO CART (verificar se product_hash e offer_hash estão presentes)
            if payload.get('cart') and len(payload['cart']) > 0:
                cart_item = payload['cart'][0]
                logger.info(f"   📦 Cart item completo:")
                logger.info(f"      title: {cart_item.get('title', 'N/A')}")
                logger.info(f"      price: {cart_item.get('price', 'N/A')}")
                logger.info(f"      quantity: {cart_item.get('quantity', 'N/A')}")
                logger.info(f"      operation_type: {cart_item.get('operation_type', 'N/A')}")
                logger.info(f"      tangible: {cart_item.get('tangible', 'N/A')}")
                logger.info(f"      product_hash: {cart_item.get('product_hash', '❌ NÃO ENCONTRADO')[:8]}...")
                logger.info(f"      offer_hash: {cart_item.get('offer_hash', '❌ NÃO ENCONTRADO')[:8]}...")
                
                # ✅ VALIDAÇÃO CRÍTICA: Se product_hash ou offer_hash não estão no cart, ERRO FATAL
                if not cart_item.get('product_hash'):
                    logger.error(f"❌ [{self.get_gateway_name()}] ERRO CRÍTICO: product_hash NÃO está no cart!")
                    return None
                if not cart_item.get('offer_hash'):
                    logger.error(f"❌ [{self.get_gateway_name()}] ERRO CRÍTICO: offer_hash NÃO está no cart!")
                    return None
            logger.info(f"   customer.name: {payload.get('customer', {}).get('name', 'N/A')}")
            logger.info(f"   customer.email: {payload.get('customer', {}).get('email', 'N/A')}")
            logger.info(f"   customer.phone_number: {payload.get('customer', {}).get('phone_number', 'N/A')}")
            logger.info(f"   customer.document: {payload.get('customer', {}).get('document', 'N/A')[:3]}***")
            logger.info(f"   reference: {payload.get('reference', 'N/A')}")
            
            # ✅ LOG COMPLETO DO PAYLOAD JSON (antes de enviar)
            import json
            payload_json = json.dumps(payload, indent=2, ensure_ascii=False)
            logger.info(f"📋 [{self.get_gateway_name()}] Payload JSON completo (antes de enviar):")
            logger.info(f"{payload_json[:2000]}...")  # Primeiros 2000 caracteres
            
            # ✅ VALIDAÇÃO FINAL: Verificar se cart tem product_hash e offer_hash
            if payload.get('cart') and len(payload['cart']) > 0:
                cart_item = payload['cart'][0]
                if not cart_item.get('product_hash'):
                    logger.error(f"❌ [{self.get_gateway_name()}] ERRO FATAL: product_hash ausente no cart antes de enviar!")
                    return None
                if not cart_item.get('offer_hash'):
                    logger.error(f"❌ [{self.get_gateway_name()}] ERRO FATAL: offer_hash ausente no cart antes de enviar!")
                    return None
                logger.info(f"✅ [{self.get_gateway_name()}] Validação final: cart contém product_hash e offer_hash")
            
            # ✅ FAZER REQUISIÇÃO
            response = self._make_request('POST', '/transactions', payload=payload)
            
            if not response:
                logger.error(f"❌ [{self.get_gateway_name()}] Falha na requisição")
                return None
            
            # ✅ VALIDAÇÕES DE RESPOSTA (conforme documentação Átomo Pay)
            # Status code 201 = Transação criada com sucesso (não 200!)
            if response.status_code != 201:
                logger.error(f"❌ [{self.get_gateway_name()}] Status code não é 201: {response.status_code}")
                logger.error(f"   Resposta: {response.text[:1000]}")
                
                # ✅ DIAGNÓSTICO ESPECÍFICO POR STATUS CODE
                if response.status_code == 400:
                    logger.error(f"🔍 [{self.get_gateway_name()}] ===== DIAGNÓSTICO 400 BAD REQUEST =====")
                    logger.error(f"   Possíveis causas:")
                    logger.error(f"   1. product_hash inválido ou não existe")
                    logger.error(f"   2. offer_hash inválido ou não existe")
                    logger.error(f"   3. Dados do cliente inválidos (CPF, telefone, email)")
                    logger.error(f"   4. Valor inválido (muito baixo ou muito alto)")
                    logger.error(f"   5. Campos obrigatórios faltando")
                    logger.error(f"   ================================================")
                elif response.status_code == 401:
                    logger.error(f"🔍 [{self.get_gateway_name()}] ===== DIAGNÓSTICO 401 UNAUTHORIZED =====")
                    logger.error(f"   Token de API inválido ou sem permissões")
                    logger.error(f"   ================================================")
                elif response.status_code == 422:
                    logger.error(f"🔍 [{self.get_gateway_name()}] ===== DIAGNÓSTICO 422 UNPROCESSABLE ENTITY =====")
                    logger.error(f"   Dados válidos mas não processáveis")
                    logger.error(f"   Verificar: product_hash, offer_hash, installments")
                    logger.error(f"   ================================================")
                
                return None
            
            # Verificar se resposta contém erro
            response_text = response.text.lower()
            if 'error' in response_text and 'success' not in response_text:
                logger.error(f"❌ [{self.get_gateway_name()}] Resposta contém erro: {response.text[:500]}")
                return None
            
            try:
                response_data = response.json()
            except:
                logger.error(f"❌ [{self.get_gateway_name()}] Resposta não é JSON válido: {response.text[:500]}")
                return None
            
            # ✅ CORREÇÃO CRÍTICA: A resposta pode vir de duas formas:
            # 1. Com wrapper: {success: true, data: {...}} (conforme documentação)
            # 2. Direta: {...} (resposta real da API quando cria transação)
            # Vamos tratar ambos os casos
            
            if response_data.get('success', False) and 'data' in response_data:
                # Formato com wrapper (conforme documentação)
                data = response_data.get('data', {})
            else:
                # Formato direto (resposta real da API)
                data = response_data
            
            if not data:
                logger.error(f"❌ [{self.get_gateway_name()}] Resposta vazia: {response_data}")
                return None
            
            # ✅ CRÍTICO: Verificar payment_status (pode ser 'refused', 'pending', 'paid', etc.)
            # ✅ NÃO RETORNAR None AQUI - Deixar extrair dados primeiro para que Payment seja criado
            payment_status = data.get('payment_status', '').lower()
            
            # ✅ LOG DETALHADO: Estrutura completa da resposta para debug
            logger.info(f"🔍 [{self.get_gateway_name()}] Estrutura da resposta:")
            logger.info(f"   Keys disponíveis: {list(data.keys())}")
            logger.info(f"   payment_status: {data.get('payment_status', 'N/A')}")
            logger.info(f"   status: {data.get('status', 'N/A')}")
            logger.info(f"   hash: {data.get('hash', 'N/A')}")
            logger.info(f"   id: {data.get('id', 'N/A')}")
            
            # ✅ EXTRAIR DADOS (priorizar campos mais importantes) - conforme documentação
            # ✅ CRÍTICO: Extrair transaction_id (prioridade: id > hash > transaction_id)
            # O webhook busca pelo 'id', então devemos usar 'id' como gateway_transaction_id
            transaction_id = (
                data.get('id') or           # 1ª prioridade (webhook busca por este)
                data.get('hash') or         # 2ª prioridade (fallback)
                data.get('transaction_id') or
                data.get('transaction_hash')
            )
            
            # ✅ CRÍTICO: Converter para string SEMPRE (id pode ser int, hash é string)
            transaction_id_str = str(transaction_id) if transaction_id else None
            
            # ✅ Hash para consulta de status (usar hash se disponível, senão id)
            # ✅ CRÍTICO: gateway_hash é o campo 'hash' da resposta (diferente de gateway_transaction_id que é 'id')
            gateway_hash = data.get('hash')  # Hash da transação (para webhook matching)
            transaction_hash_str = str(gateway_hash) if gateway_hash else transaction_id_str
            
            # ✅ CRÍTICO: Extrair producer.hash para identificar conta do usuário (multi-tenant)
            # Cada conta do Átomo Pay tem um producer.hash único
            producer_data = data.get('producer', {})
            producer_hash = producer_data.get('hash') if isinstance(producer_data, dict) else None
            
            # ✅ LOG CRÍTICO: Dados extraídos para salvar no Payment
            logger.info(f"💾 [{self.get_gateway_name()}] Dados extraídos para salvar no Payment:")
            logger.info(f"   gateway_transaction_id (id): {transaction_id_str}")
            logger.info(f"   gateway_hash (hash): {gateway_hash}")
            logger.info(f"   producer_hash: {producer_hash}")  # ✅ Para identificar conta do usuário
            logger.info(f"   reference: {payload.get('reference', 'N/A')}")
            
            # ✅ LOG: Verificar estrutura do objeto pix
            pix_data = data.get('pix', {})
            logger.info(f"🔍 [{self.get_gateway_name()}] Objeto 'pix': {pix_data}")
            if pix_data:
                logger.info(f"   pix keys: {list(pix_data.keys())}")
                logger.info(f"   pix_url: {pix_data.get('pix_url', 'N/A')}")
                logger.info(f"   pix_qr_code: {pix_data.get('pix_qr_code', 'N/A')[:50] if pix_data.get('pix_qr_code') else 'N/A'}...")
                logger.info(f"   pix_base64: {pix_data.get('pix_base64', 'N/A')[:50] if pix_data.get('pix_base64') else 'N/A'}...")
            
            # ✅ PIX_CODE: Extrair do objeto 'pix' ou do root
            # A resposta real tem: pix: {pix_url, pix_qr_code, pix_base64}
            # Conforme documentação, pode vir como 'pix_code' no root ou 'pix_qr_code' no objeto pix
            pix_code = (
                data.get('pix_code') or           # 1ª prioridade (se existir no root)
                pix_data.get('pix_qr_code') or    # 2ª prioridade (código PIX no objeto pix)
                pix_data.get('pix_base64') or     # 3ª prioridade (base64 pode conter código)
                data.get('pix_copy_paste') or
                data.get('copy_paste')
            )
            
            logger.info(f"🔍 [{self.get_gateway_name()}] pix_code extraído: {pix_code[:50] if pix_code else 'N/A'}...")
            
            # ✅ QR_CODE: URL ou base64 da imagem
            qr_code_url = pix_data.get('pix_url')
            qr_code_base64 = None
            
            # Se pix_base64 existe e não é o código PIX, usar como imagem
            if pix_data.get('pix_base64') and not pix_code:
                qr_code_base64 = pix_data.get('pix_base64')
            
            # Fallback: tentar do root
            if not qr_code_url and not qr_code_base64:
                qr_code_raw = data.get('qr_code', '')
                if qr_code_raw and qr_code_raw.startswith('data:image'):
                    qr_code_base64 = qr_code_raw.split(',', 1)[1] if ',' in qr_code_raw else qr_code_raw
                elif qr_code_raw and qr_code_raw.startswith('http'):
                    qr_code_url = qr_code_raw
                else:
                    qr_code_url = data.get('qr_code_url') or data.get('qr_code_image_url')
            
            # ✅ VALIDAÇÕES OBRIGATÓRIAS
            if not gateway_hash and not transaction_id_str:
                logger.error(f"❌ [{self.get_gateway_name()}] Resposta sem hash/transaction_hash/id")
                logger.error(f"Campos disponíveis: {list(data.keys())}")
                logger.error(f"Resposta completa: {response_data}")
                return None
            
            # ✅ VALIDAÇÃO: Se não tem pix_code, verificar payment_status
            if not pix_code:
                if payment_status == 'refused':
                    logger.error(f"❌ [{self.get_gateway_name()}] ===== TRANSAÇÃO RECUSADA PELO GATEWAY =====")
                    logger.error(f"   Hash: {gateway_hash or transaction_id_str} | Status: {payment_status}")
                    logger.error(f"   ID: {transaction_id_str}")
                    logger.error(f"   Motivo: Gateway recusou a transação (verificar configurações)")
                    logger.error(f"")
                    logger.error(f"   🔍 POSSÍVEIS CAUSAS (baseado na documentação Átomo Pay):")
                    logger.error(f"")
                    logger.error(f"   1. ❌ product_hash inválido ou não existe")
                    logger.error(f"      → product_hash usado: {self.product_hash[:12] if self.product_hash else 'NÃO CONFIGURADO'}...")
                    logger.error(f"   2. ❌ offer_hash inválido ou não existe")
                    # offer_hash_to_use pode não estar definido neste ponto, usar payload
                    offer_hash_used = payload.get('offer_hash') or payload.get('cart', [{}])[0].get('offer_hash') if payload.get('cart') else None
                    logger.error(f"      → offer_hash usado: {offer_hash_used[:12] if offer_hash_used else 'NÃO CONFIGURADO'}...")
                    logger.error(f"   3. ❌ Dados do cliente inválidos")
                    logger.error(f"      → CPF: {customer.get('document', 'N/A')[:3]}*** (deve ter 11 dígitos)")
                    logger.error(f"      → Telefone: {customer.get('phone_number', 'N/A')} (deve ter 10-11 dígitos)")
                    logger.error(f"   4. ❌ Valor inválido ou fora dos limites")
                    logger.error(f"      → Valor enviado: {amount_cents} centavos (R$ {amount:.2f})")
                    logger.error(f"   ================================================")
                    # ✅ CRÍTICO: Retornar dados da transação mesmo quando recusada
                    # Isso permite que o payment seja criado e o webhook possa encontrá-lo
                    # ✅ CRÍTICO: Extrair producer_hash para identificar conta do usuário
                    producer_data = data.get('producer', {})
                    producer_hash = producer_data.get('hash') if isinstance(producer_data, dict) else None
                    
                    return {
                        'pix_code': None,  # Não tem PIX porque foi recusado
                        'qr_code_url': None,
                        'transaction_id': transaction_id_str,  # ✅ Usar id (webhook busca por este)
                        'transaction_hash': transaction_hash_str,  # Hash para consulta de status (fallback)
                        'gateway_hash': gateway_hash,  # ✅ CRÍTICO: Hash da transação (para webhook matching)
                        'producer_hash': producer_hash,  # ✅ CRÍTICO: Hash do producer (identifica conta do usuário)
                        'payment_id': payment_id,
                        'reference': payload.get('reference'),  # ✅ CRÍTICO: Reference para matching
                        'status': 'refused',  # ✅ Status da transação
                        'error': 'Transação recusada pelo gateway'
                    }
                elif payment_status in ['pending', 'processing', 'waiting', '']:
                    # ✅ Transação criada, mas PIX ainda não disponível.
                    logger.warning(f"⚠️ [{self.get_gateway_name()}] PIX ainda não disponível na resposta (status: {payment_status or 'N/A'})")
                    logger.warning(f"   Transação criada com sucesso (hash: {gateway_hash or transaction_id_str}), aguardando webhook para código PIX")
                    return {
                        'pix_code': None,
                        'qr_code_url': None,
                        'transaction_id': transaction_id_str,
                        'transaction_hash': transaction_hash_str,
                        'gateway_hash': gateway_hash,
                        'producer_hash': producer_hash,
                        'payment_id': payment_id,
                        'reference': payload.get('reference'),
                        'status': 'pending'
                    }
                else:
                    logger.error(f"❌ [{self.get_gateway_name()}] Resposta sem pix_code/qr_code")
                    logger.error(f"   Status: {payment_status} | Hash: {gateway_hash or transaction_id_str}")
                    logger.error(f"   Campos disponíveis: {list(data.keys())}")
                    logger.error(f"   Objeto pix: {pix_data}")
                    logger.error(f"   Resposta completa: {response_data}")
                    return None
            
            logger.info(f"✅ [{self.get_gateway_name()}] PIX gerado com sucesso!")
            logger.info(f"   Transaction ID: {transaction_id_str} (webhook busca por este)")
            logger.info(f"   Gateway Hash: {gateway_hash[:20] if gateway_hash and len(gateway_hash) > 20 else gateway_hash}...")
            logger.info(f"   PIX Code: {pix_code[:50]}...")
            
            # ✅ RETORNO PADRONIZADO (como Paradise)
            # ✅ CRÍTICO: Incluir gateway_hash separado para webhook matching
            # ✅ CRÍTICO: Incluir producer_hash para identificar conta do usuário (multi-tenant)
            producer_data = data.get('producer', {})
            producer_hash = producer_data.get('hash') if isinstance(producer_data, dict) else None
            
            return {
                'pix_code': pix_code,
                'qr_code_url': qr_code_url or qr_code_base64 or '',
                'transaction_id': transaction_id_str,  # ✅ Usar id (webhook busca por este)
                'transaction_hash': transaction_hash_str,  # Hash para consulta de status (fallback)
                'gateway_hash': gateway_hash,  # ✅ CRÍTICO: Hash da transação (para webhook matching)
                'producer_hash': producer_hash,  # ✅ CRÍTICO: Hash do producer (identifica conta do usuário)
                'payment_id': payment_id,
                'reference': payload.get('reference')  # ✅ CRÍTICO: Reference para matching
            }
                
        except Exception as e:
            logger.error(f"❌ [{self.get_gateway_name()}] Erro ao gerar PIX: {e}")
            import traceback
            traceback.print_exc()
            return None
    
    def process_webhook(self, data: Dict[str, Any]) -> Optional[Dict[str, Any]]:
        """
        Processa webhook/Postback do Átomo Pay
        
        Baseado no Paradise
        """
        try:
            logger.info(f"📥 [{self.get_gateway_name()}] Processando webhook...")
            logger.debug(f"Dados: {data}")

            # ✅ NORMALIZAÇÃO: alguns webhooks chegam encapsulados em data/payload/transaction
            normalized = data if isinstance(data, dict) else {}
            if isinstance(normalized.get('data'), dict):
                candidate = normalized['data']
                if any(candidate.get(k) for k in ('id', 'hash', 'transaction_id', 'transaction_hash')):
                    normalized = candidate
            elif isinstance(normalized.get('payload'), dict):
                candidate = normalized['payload']
                if any(candidate.get(k) for k in ('id', 'hash', 'transaction_id', 'transaction_hash')):
                    normalized = candidate
            elif isinstance(normalized.get('transaction'), dict):
                candidate = normalized['transaction']
                if any(candidate.get(k) for k in ('id', 'hash', 'transaction_id', 'transaction_hash')):
                    # Propagar reference/producer para o nível interno se necessário
                    if normalized.get('reference') and 'reference' not in candidate:
                        candidate['reference'] = normalized['reference']
                    if normalized.get('producer') and 'producer' not in candidate:
                        candidate['producer'] = normalized['producer']
                    normalized = candidate

            # ✅ CRÍTICO: Extrair transaction_id (prioridade: id > hash > transaction_id)
            transaction_id = (
                normalized.get('id') or
                normalized.get('hash') or
                normalized.get('transaction_id') or
                normalized.get('transaction_hash') or
                data.get('token')  # fallback extremo para webhooks simplificados
            )

            if not transaction_id:
                logger.error(f"❌ [{self.get_gateway_name()}] Webhook sem identificador | payload normalizado: {normalized}")
                return None
            
            # ✅ CRÍTICO: Converter para string SEMPRE (id pode ser int, hash é string)
            transaction_id_str = str(transaction_id)
            
            # ✅ Hash para consulta de status (usar hash se disponível, senão id)
            transaction_hash = normalized.get('hash') or data.get('hash') or transaction_id_str
            transaction_hash_str = str(transaction_hash)
            
            # ✅ Extrair status (priorizar payment_status, depois status)
            status_raw = (
                normalized.get('payment_status') or
                normalized.get('status') or
                data.get('payment_status') or
                data.get('status') or
                ''
            ).lower()
            
            # ✅ Mapear status (como Paradise)
            status_map = {
                'paid': 'paid',
                'approved': 'paid',
                'confirmed': 'paid',
                'completed': 'paid',
                'pending': 'pending',
                'waiting': 'pending',
                'processing': 'pending',
                'failed': 'failed',
                'cancelled': 'failed',
                'canceled': 'failed',
                'expired': 'failed',
                'rejected': 'failed',
                'refused': 'failed',  # ✅ Átomo Pay: transação recusada
                'refunded': 'failed'
            }
            
            status = status_map.get(status_raw, 'pending')
            
            # ✅ Extrair valor (converter de centavos para reais)
            amount_cents = (
                normalized.get('amount') or
                normalized.get('amount_paid') or
                data.get('amount') or
                data.get('amount_paid') or
                0
            )
            amount = float(amount_cents) / 100.0
            
            # ✅ CRÍTICO: Extrair reference (pode conter payment_id para matching)
            external_reference = (
                normalized.get('reference') or
                normalized.get('external_reference') or
                normalized.get('reference_id') or
                data.get('reference') or
                data.get('external_reference') or
                data.get('reference_id')
            )
            
            # ✅ CRÍTICO: Extrair producer.hash para identificar conta do usuário (multi-tenant)
            producer_data = normalized.get('producer')
            if not isinstance(producer_data, dict):
                producer_data = data.get('producer', {})
            producer_hash = producer_data.get('hash') if isinstance(producer_data, dict) else None
            
            logger.info(f"✅ [{self.get_gateway_name()}] Webhook processado: Hash={transaction_hash_str[:20] if len(transaction_hash_str) > 20 else transaction_hash_str}... | Status={status_raw}→{status} | R$ {amount:.2f}")
            if external_reference:
                logger.info(f"   Reference: {external_reference}")
            if producer_hash:
                logger.info(f"   Producer Hash: {producer_hash} (identifica conta do usuário)")
            
            return {
                'gateway_transaction_id': transaction_id_str,  # ✅ Usar id (webhook busca por este)
                'gateway_hash': transaction_hash_str,  # ✅ CRÍTICO: Hash da transação (para webhook matching)
                'producer_hash': producer_hash,  # ✅ CRÍTICO: Hash do producer (identifica conta do usuário)
                'status': status,
                'amount': amount,
                'external_reference': external_reference  # ✅ CRÍTICO: Para matching do payment
            }
            
        except Exception as e:
            logger.error(f"❌ [{self.get_gateway_name()}] Erro ao processar webhook: {e}")
            import traceback
            traceback.print_exc()
            return None
    
    def verify_credentials(self) -> bool:
        """
        Verifica credenciais usando GET /products (conforme documentação)
        Status 200 = credenciais válidas
        Status 401 = token inválido
        
        NOTA: Usamos /products em vez de /transactions porque é mais simples e não requer product_hash
        """
        try:
            if not self.api_token or len(self.api_token) < 10:
                logger.error(f"❌ [{self.get_gateway_name()}] Token inválido (mínimo 10 caracteres)")
                return False
            
            # ✅ Listar produtos (endpoint mais simples para verificação)
            # GET /products?api_token=...&page=1&per_page=1
            # Isso não requer product_hash e valida apenas o token
            logger.info(f"🔍 [{self.get_gateway_name()}] Verificando credenciais via GET /products...")
            response = self._make_request('GET', '/products', params={'page': 1, 'per_page': 1})
            
            if not response:
                logger.error(f"❌ [{self.get_gateway_name()}] Falha na requisição de verificação (sem resposta)")
                return False
            
            logger.info(f"📊 [{self.get_gateway_name()}] Status da verificação: {response.status_code}")
            
            if response.status_code == 200:
                # ✅ Validar estrutura da resposta
                try:
                    response_data = response.json()
                    # A resposta pode vir como {success: true, data: [...]} ou diretamente como lista
                    if isinstance(response_data, dict):
                        if response_data.get('success', False) and 'data' in response_data:
                            logger.info(f"✅ [{self.get_gateway_name()}] Credenciais válidas (formato wrapper)")
                            return True
                        elif 'data' in response_data:
                            logger.info(f"✅ [{self.get_gateway_name()}] Credenciais válidas (formato data)")
                            return True
                    elif isinstance(response_data, list):
                        logger.info(f"✅ [{self.get_gateway_name()}] Credenciais válidas (formato lista)")
                        return True
                    else:
                        # Se retornou 200, mesmo que formato inesperado, token é válido
                        logger.info(f"✅ [{self.get_gateway_name()}] Credenciais válidas (status 200)")
                        return True
                except Exception as e:
                    logger.warning(f"⚠️ [{self.get_gateway_name()}] Erro ao parsear resposta, mas status 200: {e}")
                    # Status 200 geralmente significa token válido
                    return True
            elif response.status_code == 401:
                logger.error(f"❌ [{self.get_gateway_name()}] Credenciais inválidas (401 Unauthorized)")
                return False
            else:
                logger.warning(f"⚠️ [{self.get_gateway_name()}] Status inesperado: {response.status_code}")
                logger.warning(f"   Resposta: {response.text[:200]}")
                return False
                
        except Exception as e:
            logger.error(f"❌ [{self.get_gateway_name()}] Erro ao verificar credenciais: {e}")
            import traceback
            traceback.print_exc()
            return False
    
    def get_payment_status(self, transaction_id: str) -> Optional[Dict[str, Any]]:
        """
        Consulta status via GET /transactions/{hash} (conforme documentação)
        Endpoint específico para consultar detalhes completos de uma transação
        """
        try:
            if not transaction_id:
                logger.error(f"❌ [{self.get_gateway_name()}] transaction_hash não fornecido")
                return None
            
            # ✅ CRÍTICO: Converter para string SEMPRE
            transaction_id_str = str(transaction_id)
            
            logger.info(f"🔍 [{self.get_gateway_name()}] Consultando transação: {transaction_id_str[:20] if len(transaction_id_str) > 20 else transaction_id_str}...")
            
            # ✅ Endpoint específico conforme documentação: GET /transactions/{hash}
            response = self._make_request('GET', f'/transactions/{transaction_id_str}')
            
            if not response:
                logger.error(f"❌ [{self.get_gateway_name()}] Falha na requisição")
                return None
            
            if response.status_code == 200:
                # ✅ Resposta bem-sucedida (conforme documentação)
                try:
                    response_data = response.json()
                    
                    if not response_data.get('success', False):
                        logger.error(f"❌ [{self.get_gateway_name()}] Resposta não tem success=true: {response_data}")
                        return None
                    
                    # ✅ Dados vêm dentro de 'data' (conforme documentação)
                    data = response_data.get('data', {})
                    if not data:
                        logger.error(f"❌ [{self.get_gateway_name()}] Resposta não contém 'data': {response_data}")
                        return None
                    
                    hash_value = data.get('hash') or transaction_id_str
                    hash_str = str(hash_value) if hash_value else transaction_id_str
                    logger.info(f"✅ [{self.get_gateway_name()}] Transação encontrada: {hash_str[:20] if len(hash_str) > 20 else hash_str}...")
                    logger.info(f"   Status: {data.get('status', 'N/A')} | Valor: R$ {data.get('amount', 0) / 100:.2f}")
                    
                    # Processar transação (mesma estrutura do webhook)
                    return self.process_webhook(data)
                    
                except Exception as e:
                    logger.error(f"❌ [{self.get_gateway_name()}] Erro ao processar resposta: {e}")
                    import traceback
                    traceback.print_exc()
                    return None
                    
            elif response.status_code == 404:
                logger.warning(f"⚠️ [{self.get_gateway_name()}] Transação não encontrada (404): {transaction_id_str[:20] if len(transaction_id_str) > 20 else transaction_id_str}...")
                return None
            elif response.status_code == 401:
                logger.error(f"❌ [{self.get_gateway_name()}] Token inválido (401)")
                return None
            else:
                logger.error(f"❌ [{self.get_gateway_name()}] Erro HTTP {response.status_code}")
                try:
                    error_data = response.json()
                    logger.error(f"📋 [{self.get_gateway_name()}] Erro: {error_data}")
                except:
                    logger.error(f"📋 [{self.get_gateway_name()}] Resposta: {response.text[:500]}")
                return None
                
        except Exception as e:
            logger.error(f"❌ [{self.get_gateway_name()}] Erro ao consultar status: {e}")
            import traceback
            traceback.print_exc()
            return None

    def validate_amount(self, amount: float) -> bool:
        """Valida se o valor é válido"""
        try:
            return isinstance(amount, (int, float)) and amount > 0
        except:
            return False
    
    def extract_producer_hash(self, webhook_data: Dict[str, Any]) -> Optional[str]:
        """
        Extrai producer_hash do webhook AtomPay para multi-tenancy.
        
        Suporta múltiplos formatos de webhook:
        - producer.hash (direto)
        - offer.producer.hash
        - product_hash → gateway → producer_hash
        - transaction.token → payment → gateway → producer_hash
        - customer.document → payment recente → gateway → producer_hash
        
        Args:
            webhook_data: Dados brutos do webhook
        
        Returns:
            str: producer_hash ou None se não encontrado
        """
        try:
            # Formato 1: producer.hash direto (webhook de /transactions)
            if 'producer' in webhook_data and isinstance(webhook_data['producer'], dict):
                h = webhook_data['producer'].get('hash')
                if h:
                    logger.debug(f"🔍 [{self.get_gateway_name()}] Producer hash encontrado (formato 1 - producer.hash): {h[:12]}...")
                    return h
            
            # Formato 2: offer.producer.hash (webhook de /webhook integrador)
            if 'offer' in webhook_data and isinstance(webhook_data['offer'], dict):
                offer_producer = webhook_data['offer'].get('producer', {})
                if isinstance(offer_producer, dict):
                    h = offer_producer.get('hash')
                    if h:
                        logger.debug(f"🔍 [{self.get_gateway_name()}] Producer hash encontrado (formato 2 - offer.producer.hash): {h[:12]}...")
                        return h
            
            # Formato 3: product_hash → buscar gateway → producer_hash
            if 'items' in webhook_data and webhook_data['items']:
                prod_hash = webhook_data['items'][0].get('product_hash')
                if prod_hash:
                    from internal_logic.core.models import Gateway
                    g = Gateway.query.filter_by(
                        gateway_type='atomopay',
                        product_hash=prod_hash
                    ).first()
                    if g and g.producer_hash:
                        logger.debug(f"🔍 [{self.get_gateway_name()}] Producer hash encontrado (formato 3 - product_hash → gateway): {g.producer_hash[:12]}...")
                        return g.producer_hash
            
            # Formato 4: transaction.token → buscar payment → gateway → producer_hash
            if 'transaction' in webhook_data and isinstance(webhook_data['transaction'], dict):
                token = webhook_data['transaction'].get('token')
                if token:
                    from internal_logic.core.models import Payment
                    payment = Payment.query.filter_by(
                        gateway_transaction_id=str(token)
                    ).first()
                    if payment and payment.gateway and payment.gateway.producer_hash:
                        logger.debug(f"🔍 [{self.get_gateway_name()}] Producer hash encontrado (formato 4 - transaction.token → payment): {payment.gateway.producer_hash[:12]}...")
                        return payment.gateway.producer_hash
            
            # Formato 5: customer.document → buscar payment recente → gateway → producer_hash
            if 'customer' in webhook_data and isinstance(webhook_data['customer'], dict):
                customer_doc = webhook_data['customer'].get('document')
                if customer_doc:
                    from internal_logic.core.models import Payment
                    from datetime import timedelta
                    from internal_logic.core.models import get_brazil_time
                    # Buscar payment recente (últimas 24h) com mesmo documento
                    recent_payment = Payment.query.filter(
                        Payment.customer_user_id == customer_doc,
                        Payment.gateway_type == 'atomopay',
                        Payment.created_at >= get_brazil_time() - timedelta(hours=24)
                    ).order_by(Payment.created_at.desc()).first()
                    if recent_payment and recent_payment.gateway and recent_payment.gateway.producer_hash:
                        logger.debug(f"🔍 [{self.get_gateway_name()}] Producer hash encontrado (formato 5 - customer.document → payment): {recent_payment.gateway.producer_hash[:12]}...")
                        return recent_payment.gateway.producer_hash
            
            logger.debug(f"⚠️ [{self.get_gateway_name()}] Producer hash não encontrado em nenhum formato conhecido")
            return None
            
        except Exception as e:
            logger.error(f"❌ [{self.get_gateway_name()}] Erro ao extrair producer_hash: {e}", exc_info=True)
            return None