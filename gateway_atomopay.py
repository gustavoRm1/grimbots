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
from typing import Dict, Any, Optional
from datetime import datetime
from gateway_interface import PaymentGateway

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
        
        # ✅ offer_hash é OBRIGATÓRIO na Átomo Pay (diferente do Paradise)
        self.offer_hash = offer_hash.strip() if offer_hash else None
        self.product_hash = product_hash.strip() if product_hash else None
        self.split_percentage = 2.0
        
        logger.info(f"✅ [{self.get_gateway_name()}] Gateway inicializado")
        logger.info(f"   api_token: {self.api_token[:10]}... ({len(self.api_token)} chars)")
        if self.offer_hash:
            logger.info(f"   offer_hash: {self.offer_hash[:8]}... (obrigatório - será enviado)")
        else:
            logger.warning(f"⚠️ offer_hash não configurado (será obrigatório na geração de PIX)")
        if self.product_hash:
            logger.info(f"   product_hash: {self.product_hash[:8]}... (obrigatório no cart - será enviado)")
        else:
            logger.warning(f"⚠️ product_hash não configurado (será obrigatório no cart)")
    
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
            
            # ✅ CPF ÚNICO
            cpf_base = f"{unique_hash}{str(payment_id).replace('_', '').replace('-', '')[:6]}"
            unique_cpf = cpf_base[:11] if len(cpf_base) >= 11 else cpf_base.ljust(11, '0')
            
            # Validação: CPF não pode começar com 0
            if unique_cpf[0] == '0':
                unique_cpf = '1' + unique_cpf[1:]
            
            # ✅ TELEFONE ÚNICO
            unique_phone = self._validate_phone(f"11{customer_user_id[-9:]}")
            
            # ✅ NOME ÚNICO
            unique_name = customer_data.get('name') or f"Cliente {customer_user_id[-6:]}"
            unique_name = unique_name[:30]  # Limitar a 30 caracteres
            
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
            logger.info(f"   CPF único: {unique_cpf[:3]}***")
            
            # ✅ CUSTOMER SIMPLIFICADO (apenas campos aceitos pela API)
            customer = {
                'name': unique_name,
                'email': unique_email,
                'phone_number': unique_phone,
                'document': unique_cpf
            }
            
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
            if not self.offer_hash:
                logger.error(f"❌ [{self.get_gateway_name()}] offer_hash é OBRIGATÓRIO na API Átomo Pay!")
                logger.error(f"   Configure 'Offer Hash' no gateway antes de usar")
                return None
            
            # ✅ Enviar offer_hash (obrigatório)
            payload['offer_hash'] = self.offer_hash
            logger.info(f"✅ [{self.get_gateway_name()}] offer_hash enviado: {self.offer_hash[:8]}...")
            
            logger.debug(f"📦 Payload final: {payload}")
            
            # ✅ FAZER REQUISIÇÃO
            response = self._make_request('POST', '/transactions', payload=payload)
            
            if not response:
                logger.error(f"❌ [{self.get_gateway_name()}] Falha na requisição")
                return None
            
            # ✅ VALIDAÇÕES DE RESPOSTA (conforme documentação Átomo Pay)
            # Status code 201 = Transação criada com sucesso (não 200!)
            if response.status_code != 201:
                logger.error(f"❌ [{self.get_gateway_name()}] Status code não é 201: {response.status_code}")
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
            
            # ✅ Validar success no root (conforme documentação)
            if not response_data.get('success', False):
                logger.error(f"❌ [{self.get_gateway_name()}] Resposta não tem success=true: {response_data}")
                return None
            
            # ✅ CRÍTICO: Dados vêm dentro de 'data' (conforme documentação)
            data = response_data.get('data', {})
            if not data:
                logger.error(f"❌ [{self.get_gateway_name()}] Resposta não contém 'data': {response_data}")
                return None
            
            # ✅ EXTRAIR DADOS (priorizar campos mais importantes) - conforme documentação
            transaction_hash = (
                data.get('hash') or         # 1ª prioridade (conforme documentação)
                data.get('id') or           # 2ª prioridade
                data.get('transaction_hash') or
                data.get('transaction_id')  # 3ª prioridade (ID numérico)
            )
            
            transaction_id = data.get('transaction_id') or transaction_hash
            
            # ✅ PIX_CODE: Conforme documentação, vem como 'pix_code' (código copia-e-cola)
            # qr_code é a imagem base64, NÃO o código PIX
            pix_code = (
                data.get('pix_code') or     # 1ª prioridade (código PIX copia-e-cola)
                data.get('pix_copy_paste') or
                data.get('copy_paste')
            )
            
            # ✅ QR_CODE: Imagem base64 (data:image/png;base64,...) ou URL
            qr_code_raw = data.get('qr_code', '')
            if qr_code_raw and qr_code_raw.startswith('data:image'):
                # É base64 com prefixo, extrair apenas a parte base64
                qr_code_base64 = qr_code_raw.split(',', 1)[1] if ',' in qr_code_raw else qr_code_raw
                qr_code_url = None
            elif qr_code_raw and qr_code_raw.startswith('http'):
                # É URL
                qr_code_url = qr_code_raw
                qr_code_base64 = None
            else:
                # Tentar URL alternativa
                qr_code_url = data.get('qr_code_url') or data.get('qr_code_image_url')
                qr_code_base64 = qr_code_raw if qr_code_raw else None
            
            # ✅ VALIDAÇÕES OBRIGATÓRIAS
            if not transaction_hash:
                logger.error(f"❌ [{self.get_gateway_name()}] Resposta sem hash/transaction_hash/id")
                logger.error(f"Campos disponíveis em 'data': {list(data.keys())}")
                logger.error(f"Resposta completa: {response_data}")
                return None
            
            if not pix_code:
                logger.error(f"❌ [{self.get_gateway_name()}] Resposta sem pix_code/qr_code")
                logger.error(f"Campos disponíveis em 'data': {list(data.keys())}")
                logger.error(f"Resposta completa: {response_data}")
                return None
            
            logger.info(f"✅ [{self.get_gateway_name()}] PIX gerado com sucesso!")
            logger.info(f"   Transaction Hash: {transaction_hash[:20]}...")
            logger.info(f"   Transaction ID: {transaction_id}")
            logger.info(f"   PIX Code: {pix_code[:50]}...")
            
            # ✅ RETORNO PADRONIZADO (como Paradise)
            return {
                'pix_code': pix_code,
                'qr_code_url': qr_code_url or qr_code_base64 or '',
                'transaction_id': transaction_id,
                'transaction_hash': transaction_hash,  # Hash principal para consulta
                'payment_id': payment_id
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
            
            # ✅ Extrair transaction_hash (prioridade: id > hash > transaction_id) - como Paradise
            transaction_hash = (
                data.get('id') or
                data.get('hash') or
                data.get('transaction_hash') or
                data.get('transaction_id')
            )
            
            if not transaction_hash:
                logger.error(f"❌ [{self.get_gateway_name()}] Webhook sem identificador")
                return None
            
            # ✅ Extrair status
            status_raw = (
                data.get('status') or
                data.get('payment_status') or
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
                'refunded': 'failed'
            }
            
            status = status_map.get(status_raw, 'pending')
            
            # ✅ Extrair valor (converter de centavos para reais)
            amount_cents = data.get('amount') or data.get('amount_paid') or 0
            amount = float(amount_cents) / 100.0
            
            logger.info(f"✅ [{self.get_gateway_name()}] Webhook processado: Hash={transaction_hash[:20]}... | Status={status_raw}→{status} | R$ {amount:.2f}")
            
            return {
                'gateway_transaction_id': transaction_hash,
                'status': status,
                'amount': amount
            }
            
        except Exception as e:
            logger.error(f"❌ [{self.get_gateway_name()}] Erro ao processar webhook: {e}")
            import traceback
            traceback.print_exc()
            return None
    
    def verify_credentials(self) -> bool:
        """
        Verifica credenciais usando GET /transactions (conforme documentação)
        Status 200 = credenciais válidas
        Status 401 = token inválido
        """
        try:
            if not self.api_token or len(self.api_token) < 10:
                logger.error(f"❌ [{self.get_gateway_name()}] Token inválido")
                return False
            
            # ✅ Listar transações (endpoint conforme documentação)
            # GET /transactions?api_token=...&page=1&per_page=1
            response = self._make_request('GET', '/transactions', params={'page': 1, 'per_page': 1})
            
            if not response:
                logger.error(f"❌ [{self.get_gateway_name()}] Falha na requisição de verificação")
                return False
            
            if response.status_code == 200:
                # ✅ Validar estrutura da resposta (success: true, data: [...])
                try:
                    response_data = response.json()
                    if response_data.get('success', False) and 'data' in response_data:
                        logger.info(f"✅ [{self.get_gateway_name()}] Credenciais válidas")
                        return True
                    else:
                        logger.warning(f"⚠️ [{self.get_gateway_name()}] Resposta inesperada: {response_data}")
                        return False
                except:
                    logger.warning(f"⚠️ [{self.get_gateway_name()}] Resposta não é JSON válido")
                    return False
            elif response.status_code == 401:
                logger.error(f"❌ [{self.get_gateway_name()}] Credenciais inválidas (401)")
                return False
            else:
                logger.warning(f"⚠️ [{self.get_gateway_name()}] Status inesperado: {response.status_code}")
                return False
                
        except Exception as e:
            logger.error(f"❌ [{self.get_gateway_name()}] Erro ao verificar credenciais: {e}")
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
            
            logger.info(f"🔍 [{self.get_gateway_name()}] Consultando transação: {transaction_id[:20]}...")
            
            # ✅ Endpoint específico conforme documentação: GET /transactions/{hash}
            response = self._make_request('GET', f'/transactions/{transaction_id}')
            
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
                    
                    logger.info(f"✅ [{self.get_gateway_name()}] Transação encontrada: {data.get('hash', transaction_id)[:20]}...")
                    logger.info(f"   Status: {data.get('status', 'N/A')} | Valor: R$ {data.get('amount', 0) / 100:.2f}")
                    
                    # Processar transação (mesma estrutura do webhook)
                    return self.process_webhook(data)
                    
                except Exception as e:
                    logger.error(f"❌ [{self.get_gateway_name()}] Erro ao processar resposta: {e}")
                    import traceback
                    traceback.print_exc()
                    return None
                    
            elif response.status_code == 404:
                logger.warning(f"⚠️ [{self.get_gateway_name()}] Transação não encontrada (404): {transaction_id[:20]}...")
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
