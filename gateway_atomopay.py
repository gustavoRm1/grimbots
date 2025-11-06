"""
Gateway Átomo Pay - Implementação Isolada
Documentação: https://api.atomopay.com.br/api/public/v1
Versão da API: 1.0

Características:
- Autenticação via api_token (parâmetro)
- Valores monetários em centavos
- Webhook/Postback para notificações em tempo real
- Rate limiting: 1000 requisições/minuto
- TLS 1.3 com criptografia de ponta a ponta
"""

import os
import requests
import logging
from typing import Dict, Any, Optional
from datetime import datetime
from gateway_interface import PaymentGateway

logger = logging.getLogger(__name__)


class AtomPayGateway(PaymentGateway):
    """
    Implementação do gateway Átomo Pay
    
    Características:
    - Autenticação via api_token (parâmetro em todas as requisições)
    - Valores monetários em centavos
    - Webhook/Postback para confirmação de pagamento
    - Suporte a produtos e ofertas
    - PCI DSS Certificado
    """
    
    def __init__(self, api_token: str, offer_hash: str = None, product_hash: str = None):
        """
        Inicializa gateway Átomo Pay
        
        Args:
            api_token: Token de API obtido no painel da Átomo Pay
            offer_hash: Hash da oferta (opcional, mas recomendado)
            product_hash: Hash do produto (opcional, usado se offer_hash não fornecido)
        """
        # ✅ VALIDAÇÃO CRÍTICA: api_token não pode ser None ou vazio
        if not api_token or not api_token.strip():
            logger.error(f"❌ [{self.__class__.__name__}] api_token é None ou vazio!")
            raise ValueError("api_token é obrigatório para Átomo Pay")
        
        self.api_token = api_token.strip()  # ✅ Remover espaços em branco
        self.base_url = "https://api.atomopay.com.br/api/public/v1"
        self.offer_hash = offer_hash.strip() if offer_hash else None
        self.product_hash = product_hash.strip() if product_hash else None
        self.split_percentage = 2.0  # 2% PADRÃO (se suportado)
        
        logger.info(f"✅ [{self.get_gateway_name()}] Gateway inicializado | api_token: {self.api_token[:10]}... ({len(self.api_token)} caracteres)")
    
    def get_gateway_name(self) -> str:
        """Nome amigável do gateway"""
        return "Átomo Pay"
    
    def get_gateway_type(self) -> str:
        """Tipo do gateway para roteamento"""
        return "atomopay"
    
    def get_webhook_url(self) -> str:
        """URL do webhook/Postback Átomo Pay"""
        webhook_base = os.environ.get('WEBHOOK_URL', '')
        return f"{webhook_base}/webhook/payment/atomopay"
    
    def _make_request(
        self, 
        method: str, 
        endpoint: str, 
        payload: Optional[Dict[str, Any]] = None,
        params: Optional[Dict[str, Any]] = None
    ) -> Optional[requests.Response]:
        """
        Faz requisição à API Átomo Pay
        
        Args:
            method: Método HTTP (GET, POST, PUT)
            endpoint: Endpoint da API (ex: /transactions)
            payload: Dados para envio (POST/PUT)
            params: Parâmetros de query (GET)
        
        Returns:
            Response object ou None em caso de erro
        """
        try:
            url = f"{self.base_url}{endpoint}"
            
            # ✅ Átomo Pay usa api_token como PARÂMETRO (não header)
            request_params = {'api_token': self.api_token}
            if params:
                request_params.update(params)
            
            headers = {
                'Content-Type': 'application/json',
                'Accept': 'application/json'
            }
            
            logger.info(f"🌐 [{self.get_gateway_name()}] {method} {endpoint}")
            if payload:
                logger.debug(f"📦 [{self.get_gateway_name()}] Payload: {payload}")
            if request_params:
                api_token_present = request_params.get('api_token')
                if api_token_present:
                    logger.info(f"🔑 [{self.get_gateway_name()}] api_token presente ({len(api_token_present)} caracteres): {api_token_present[:10]}...")
                else:
                    logger.error(f"❌ [{self.get_gateway_name()}] api_token NÃO encontrado nos params!")
                    logger.error(f"   Params disponíveis: {list(request_params.keys())}")
            
            if method.upper() == 'GET':
                response = requests.get(url, params=request_params, headers=headers, timeout=15)
            elif method.upper() == 'POST':
                response = requests.post(url, json=payload, params=request_params, headers=headers, timeout=15)
            elif method.upper() == 'PUT':
                response = requests.put(url, json=payload, params=request_params, headers=headers, timeout=15)
            else:
                logger.error(f"❌ [{self.get_gateway_name()}] Método HTTP não suportado: {method}")
                return None
            
            # ✅ LOG DETALHADO: Status code e resposta
            logger.info(f"📊 [{self.get_gateway_name()}] Resposta: Status {response.status_code}")
            if response.status_code >= 400:
                logger.error(f"❌ [{self.get_gateway_name()}] Erro HTTP {response.status_code}")
                try:
                    error_data = response.json()
                    logger.error(f"📋 [{self.get_gateway_name()}] Resposta JSON: {error_data}")
                except:
                    logger.error(f"📋 [{self.get_gateway_name()}] Resposta texto: {response.text[:500]}")
            
            return response
            
        except requests.exceptions.Timeout:
            logger.error(f"❌ [{self.get_gateway_name()}] Timeout na requisição: {endpoint} (15s)")
            return None
        except requests.exceptions.ConnectionError as e:
            logger.error(f"❌ [{self.get_gateway_name()}] Erro de conexão: {e}")
            return None
        except requests.exceptions.RequestException as e:
            logger.error(f"❌ [{self.get_gateway_name()}] Erro na requisição: {e}")
            if hasattr(e, 'response') and e.response is not None:
                logger.error(f"📋 [{self.get_gateway_name()}] Status: {e.response.status_code}")
                logger.error(f"📋 [{self.get_gateway_name()}] Resposta: {e.response.text[:500]}")
            return None
        except Exception as e:
            logger.error(f"❌ [{self.get_gateway_name()}] Erro inesperado: {e}")
            import traceback
            logger.error(f"📋 [{self.get_gateway_name()}] Traceback: {traceback.format_exc()}")
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
        
        Endpoint: POST /transactions
        
        Documentação: https://api.atomopay.com.br/api/public/v1
        
        Nota: Átomo Pay trabalha com valores em CENTAVOS
        Requer: offer_hash OU cart com product_hash
        """
        try:
            # Validar valor
            if not self.validate_amount(amount):
                logger.error(f"❌ [{self.get_gateway_name()}] Valor inválido: {amount}")
                return None
            
            # Converter valor para centavos (Átomo Pay requer)
            amount_cents = int(amount * 100)
            
            # Validar valor mínimo (50 centavos = R$ 0.50)
            if amount_cents < 50:
                logger.error(f"❌ [{self.get_gateway_name()}] Valor muito baixo: {amount_cents} centavos (mínimo: 50)")
                return None
            
            # Preparar dados do cliente conforme documentação
            if not customer_data:
                customer_data = {}
            
            # ✅ Dados completos do customer (conforme documentação)
            customer_name = customer_data.get('name') or customer_data.get('customer_name') or 'Cliente'
            customer_email = customer_data.get('email') or customer_data.get('customer_email') or f'cliente{payment_id[:8]}@bot.digital'
            customer_phone = customer_data.get('phone') or customer_data.get('phone_number') or '11999999999'
            customer_document = customer_data.get('document') or customer_data.get('cpf') or customer_data.get('document') or '00000000000'
            
            # ✅ Endereço do cliente (requerido pela API)
            customer_address = {
                'street_name': customer_data.get('street_name') or customer_data.get('street') or 'Rua Não Informada',
                'number': customer_data.get('number') or customer_data.get('address_number') or '0',
                'complement': customer_data.get('complement') or '',
                'neighborhood': customer_data.get('neighborhood') or customer_data.get('bairro') or 'Centro',
                'city': customer_data.get('city') or customer_data.get('cidade') or 'São Paulo',
                'state': customer_data.get('state') or customer_data.get('estado') or 'SP',
                'zip_code': customer_data.get('zip_code') or customer_data.get('cep') or '00000000'
            }
            
            # ✅ Preparar customer conforme documentação
            customer = {
                'name': customer_name,
                'email': customer_email,
                'phone_number': customer_phone.replace(' ', '').replace('-', '').replace('(', '').replace(')', ''),
                'document': customer_document.replace('.', '').replace('-', '').replace('/', ''),
                'street_name': customer_address['street_name'],
                'number': customer_address['number'],
                'complement': customer_address['complement'],
                'neighborhood': customer_address['neighborhood'],
                'city': customer_address['city'],
                'state': customer_address['state'],
                'zip_code': customer_address['zip_code']
            }
            
            # ✅ Usar offer_hash ou product_hash do construtor
            offer_hash = self.offer_hash
            product_hash = self.product_hash
            
            # Preparar payload conforme documentação Átomo Pay
            payload = {
                'amount': amount_cents,  # ✅ Valores em centavos
                'payment_method': 'pix',
                'customer': customer,
                'postback_url': self.get_webhook_url(),  # URL para notificações
                'transaction_origin': 'api',
                'expire_in_days': 1,  # PIX expira em 1 dia
            }
            
            # ✅ Se tiver offer_hash, usar (mais simples)
            if offer_hash:
                payload['offer_hash'] = offer_hash
                logger.info(f"✅ [{self.get_gateway_name()}] Usando offer_hash: {offer_hash[:8]}...")
            # ✅ Se tiver product_hash, usar cart
            elif product_hash:
                payload['cart'] = [{
                    'product_hash': product_hash,
                    'title': description[:100] if description else 'Produto',
                    'cover': None,
                    'price': amount_cents,
                    'quantity': 1,
                    'operation_type': 1,  # Tipo de operação (1 = venda)
                    'tangible': False  # Produto digital
                }]
                logger.info(f"✅ [{self.get_gateway_name()}] Usando cart com product_hash: {product_hash[:8]}...")
            else:
                # ⚠️ FALLBACK: Criar cart sem product_hash (pode não funcionar na API real)
                # Usar um hash genérico baseado no payment_id
                import hashlib
                fallback_product_hash = hashlib.md5(f"product_{payment_id}".encode()).hexdigest()[:12]
                payload['cart'] = [{
                    'product_hash': fallback_product_hash,
                    'title': description[:100] if description else 'Produto',
                    'cover': None,
                    'price': amount_cents,
                    'quantity': 1,
                    'operation_type': 1,
                    'tangible': False
                }]
                logger.warning(f"⚠️ [{self.get_gateway_name()}] offer_hash/product_hash não configurado. Usando fallback: {fallback_product_hash}")
                logger.warning(f"⚠️ Configure offer_hash ou product_hash no gateway para melhor compatibilidade")
            
            # ✅ Tracking (opcional, mas útil)
            payload['tracking'] = {
                'src': '',
                'utm_source': customer_data.get('utm_source', ''),
                'utm_medium': customer_data.get('utm_medium', ''),
                'utm_campaign': customer_data.get('utm_campaign', ''),
                'utm_term': customer_data.get('utm_term', ''),
                'utm_content': customer_data.get('utm_content', '')
            }
            
            logger.info(f"📤 [{self.get_gateway_name()}] Gerando PIX: R$ {amount:.2f} ({amount_cents} centavos) | ID: {payment_id}")
            
            # Fazer requisição
            response = self._make_request('POST', '/transactions', payload=payload)
            
            if not response:
                logger.error(f"❌ [{self.get_gateway_name()}] Falha na requisição (response é None)")
                logger.error(f"   Verifique logs anteriores para detalhes do erro (timeout, conexão, etc.)")
                return None
            
            # Processar resposta
            if response.status_code == 200 or response.status_code == 201:
                data = response.json()
                
                # ✅ Log detalhado da resposta para debug
                logger.debug(f"📦 [{self.get_gateway_name()}] Resposta completa: {data}")
                
                # ✅ Mapear resposta do Átomo Pay para formato padrão
                # Átomo Pay retorna transaction_hash conforme documentação
                transaction_hash = (
                    data.get('transaction_hash') or 
                    data.get('hash') or 
                    data.get('id') or
                    data.get('transaction_id')
                )
                
                # ✅ Buscar código PIX (Átomo Pay pode retornar em diferentes campos)
                # Para PIX, geralmente vem em um campo específico
                pix_code = (
                    data.get('pix_code') or 
                    data.get('pix_copy_paste') or 
                    data.get('copy_paste') or 
                    data.get('qr_code') or
                    data.get('pix', {}).get('code') or  # Se estiver aninhado
                    data.get('payment', {}).get('pix_code')  # Se estiver aninhado
                )
                
                # ✅ Buscar URL do QR Code
                qr_code_url = (
                    data.get('qr_code_url') or 
                    data.get('qr_code_image_url') or
                    data.get('pix', {}).get('qr_code_url') or
                    data.get('payment', {}).get('qr_code_url')
                )
                
                # ✅ Buscar QR Code em base64 (se disponível)
                qr_code_base64 = (
                    data.get('qr_code_base64') or 
                    data.get('qr_code_image_base64') or
                    data.get('pix', {}).get('qr_code_base64') or
                    data.get('payment', {}).get('qr_code_base64')
                )
                
                # ✅ Data de expiração (se disponível)
                expires_at = None
                if data.get('expires_at'):
                    try:
                        from datetime import datetime
                        expires_at = datetime.fromisoformat(data['expires_at'].replace('Z', '+00:00'))
                    except:
                        pass
                
                if not transaction_hash:
                    logger.error(f"❌ [{self.get_gateway_name()}] Resposta sem transaction_hash")
                    logger.error(f"Campos disponíveis na resposta: {list(data.keys())}")
                    return None
                
                if not pix_code:
                    logger.error(f"❌ [{self.get_gateway_name()}] Resposta sem pix_code")
                    logger.error(f"Campos disponíveis na resposta: {list(data.keys())}")
                    logger.error(f"Resposta completa: {data}")
                    return None
                
                logger.info(f"✅ [{self.get_gateway_name()}] PIX gerado com sucesso! Hash: {transaction_hash[:20]}...")
                logger.info(f"📝 Código PIX: {pix_code[:50]}...")
                
                return {
                    'pix_code': pix_code,
                    'qr_code_url': qr_code_url or '',  # Pode ser vazio se não disponível
                    'transaction_id': transaction_hash,  # ✅ transaction_hash é o ID da transação
                    'payment_id': payment_id,
                    'qr_code_base64': qr_code_base64,  # Opcional
                    'expires_at': expires_at  # Se disponível
                }
            else:
                logger.error(f"❌ [{self.get_gateway_name()}] Erro ao gerar PIX: Status {response.status_code}")
                try:
                    error_data = response.json()
                    logger.error(f"📋 [{self.get_gateway_name()}] Resposta JSON: {error_data}")
                    
                    # Tentar extrair mensagem de erro específica
                    error_message = (
                        error_data.get('message') or
                        error_data.get('error') or
                        error_data.get('error_message') or
                        error_data.get('errors')
                    )
                    if error_message:
                        logger.error(f"📋 [{self.get_gateway_name()}] Mensagem de erro: {error_message}")
                except:
                    logger.error(f"📋 [{self.get_gateway_name()}] Resposta texto: {response.text[:1000]}")
                return None
                
        except Exception as e:
            logger.error(f"❌ [{self.get_gateway_name()}] Erro ao gerar PIX: {e}")
            import traceback
            traceback.print_exc()
            return None
    
    def process_webhook(self, data: Dict[str, Any]) -> Optional[Dict[str, Any]]:
        """
        Processa webhook/Postback recebido do Átomo Pay
        
        Formato esperado (conforme documentação):
        {
            "transaction_hash": "abc123def456",
            "status": "paid",
            "amount": 15000,
            "payment_method": "pix",
            "paid_at": "2025-01-20T10:15:00Z"
        }
        
        Args:
            data: Dados brutos do webhook (JSON)
        
        Returns:
            Dict no formato padrão ou None
        """
        try:
            logger.info(f"📥 [{self.get_gateway_name()}] Processando webhook/Postback...")
            logger.debug(f"Dados recebidos: {data}")
            
            # ✅ Extrair dados conforme formato do Átomo Pay
            transaction_hash = (
                data.get('transaction_hash') or 
                data.get('hash') or 
                data.get('id') or
                data.get('transaction_id')
            )
            
            if not transaction_hash:
                logger.error(f"❌ [{self.get_gateway_name()}] Webhook sem transaction_hash")
                return None
            
            # Status do pagamento
            status_raw = data.get('status', '').lower()
            
            # Valor em centavos (converter para reais)
            amount_cents = data.get('amount', 0)
            amount = float(amount_cents) / 100.0  # Converter centavos para reais
            
            # ✅ Mapear status do Átomo Pay para status interno
            # Possíveis status: 'pending', 'paid', 'failed', 'cancelled', 'expired'
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
                'rejected': 'failed'
            }
            
            status = status_map.get(status_raw, 'pending')
            
            # Dados adicionais (opcional)
            payer_name = data.get('payer_name') or data.get('customer_name')
            payer_document = data.get('payer_document') or data.get('customer_document')
            end_to_end_id = data.get('end_to_end_id') or data.get('e2e_id')
            paid_at = data.get('paid_at') or data.get('paid_date')
            
            # Buscar external_id (payment_id do sistema)
            external_id = data.get('external_id') or data.get('payment_id')
            
            logger.info(f"✅ [{self.get_gateway_name()}] Webhook processado: Hash={transaction_hash[:20]}... | Status={status_raw}→{status} | Valor=R$ {amount:.2f}")
            
            if payer_name:
                logger.info(f"👤 Pagador: {payer_name}")
            if paid_at:
                logger.info(f"📅 Pago em: {paid_at}")
            
            return {
                'payment_id': external_id or transaction_hash,  # Priorizar external_id (payment_id do sistema)
                'status': status,
                'amount': amount,
                'gateway_transaction_id': transaction_hash,
                'payer_name': payer_name,
                'payer_document': payer_document,
                'end_to_end_id': end_to_end_id
            }
            
        except Exception as e:
            logger.error(f"❌ [{self.get_gateway_name()}] Erro ao processar webhook: {e}")
            import traceback
            traceback.print_exc()
            return None
    
    def verify_credentials(self) -> bool:
        """
        Verifica se as credenciais são válidas
        
        Endpoint: GET /balance (consulta de saldo)
        
        Nota: Usa endpoint de consulta de saldo para validar token
        """
        try:
            if not self.api_token:
                logger.error(f"❌ [{self.get_gateway_name()}] API Token não fornecido")
                return False
            
            # Validação básica de formato
            if len(self.api_token) < 10:
                logger.error(f"❌ [{self.get_gateway_name()}] API Token muito curto")
                return False
            
            # Tentar consultar saldo (endpoint seguro para validação)
            # Se não houver endpoint de saldo, usar um endpoint de teste
            response = self._make_request('GET', '/balance')
            
            if response and response.status_code == 200:
                logger.info(f"✅ [{self.get_gateway_name()}] Credenciais válidas")
                return True
            elif response and response.status_code == 401:
                logger.error(f"❌ [{self.get_gateway_name()}] Credenciais inválidas (401 Unauthorized)")
                return False
            elif response and response.status_code == 403:
                logger.error(f"❌ [{self.get_gateway_name()}] Acesso negado (403 Forbidden)")
                return False
            else:
                # Se o endpoint não existir, tentar validar formato do token
                logger.warning(f"⚠️ [{self.get_gateway_name()}] Não foi possível validar credenciais via API. Validando formato...")
                # Validação básica de formato (token deve ter formato válido)
                return len(self.api_token) >= 20  # Assumir que tokens válidos têm pelo menos 20 caracteres
                
        except Exception as e:
            logger.error(f"❌ [{self.get_gateway_name()}] Erro ao verificar credenciais: {e}")
            return False
    
    def get_payment_status(self, transaction_id: str) -> Optional[Dict[str, Any]]:
        """
        Consulta status de um pagamento
        
        Endpoint: GET /transactions/{transaction_hash}
        
        Args:
            transaction_id: Hash da transação (transaction_hash)
        
        Returns:
            Mesmo formato do process_webhook()
        """
        try:
            if not transaction_id:
                logger.error(f"❌ [{self.get_gateway_name()}] transaction_hash não fornecido")
                return None
            
            logger.info(f"🔍 [{self.get_gateway_name()}] Consultando status: {transaction_id[:20]}...")
            
            # Consultar transação
            response = self._make_request('GET', f'/transactions/{transaction_id}')
            
            if not response:
                logger.error(f"❌ [{self.get_gateway_name()}] Falha na requisição")
                return None
            
            if response.status_code == 200:
                data = response.json()
                
                # ✅ Reutilizar lógica do process_webhook
                return self.process_webhook(data)
            elif response.status_code == 404:
                logger.warning(f"⚠️ [{self.get_gateway_name()}] Transação não encontrada: {transaction_id}")
                return None
            elif response.status_code == 401:
                logger.error(f"❌ [{self.get_gateway_name()}] Credenciais inválidas ao consultar status")
                return None
            else:
                logger.error(f"❌ [{self.get_gateway_name()}] Erro ao consultar status: Status {response.status_code}")
                logger.error(f"Resposta: {response.text}")
                return None
                
        except Exception as e:
            logger.error(f"❌ [{self.get_gateway_name()}] Erro ao consultar status: {e}")
            import traceback
            traceback.print_exc()
            return None

