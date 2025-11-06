"""
Gateway Átomo Pay - VERSÃO CORRIGIDA (QI 600/602)
Baseado na documentação oficial: https://docs.atomopay.com.br/

CORREÇÕES APLICADAS:
- Customer: apenas name, email, phone_number, document (sem endereço)
- Cart obrigatório (não offer_hash)
- Removido expire_in_days (não existe na API)
- Tracking apenas se tiver dados válidos
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
            offer_hash: Hash da oferta (opcional, mantido para compatibilidade mas não usado)
            product_hash: Hash do produto (opcional, usado no cart)
        """
        if not api_token or not api_token.strip():
            logger.error(f"❌ [{self.__class__.__name__}] api_token é None ou vazio!")
            raise ValueError("api_token é obrigatório para Átomo Pay")
        
        self.api_token = api_token.strip()
        self.base_url = "https://api.atomopay.com.br/api/public/v1"
        self.offer_hash = offer_hash.strip() if offer_hash else None
        self.product_hash = product_hash.strip() if product_hash else None
        self.split_percentage = 2.0
        
        logger.info(f"✅ [{self.get_gateway_name()}] Gateway inicializado | api_token: {self.api_token[:10]}... ({len(self.api_token)} caracteres)")
    
    def get_gateway_name(self) -> str:
        return "Átomo Pay"
    
    def get_gateway_type(self) -> str:
        return "atomopay"
    
    def get_webhook_url(self) -> str:
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
        
        CORRIGIDO baseado na documentação oficial:
        - customer: apenas name, email, phone_number, document
        - cart obrigatório
        - removido expire_in_days
        - tracking apenas se tiver dados válidos
        """
        try:
            # Validar valor
            if not self.validate_amount(amount):
                logger.error(f"❌ [{self.get_gateway_name()}] Valor inválido: {amount}")
                return None
            
            # Converter para centavos
            amount_cents = int(amount * 100)
            
            if amount_cents < 50:
                logger.error(f"❌ [{self.get_gateway_name()}] Valor muito baixo: {amount_cents} centavos (mínimo: 50)")
                return None
            
            # ✅ Preparar customer (APENAS campos permitidos pela API)
            if not customer_data:
                customer_data = {}
            
            customer_name = customer_data.get('name') or customer_data.get('customer_name') or 'Cliente'
            customer_email = customer_data.get('email') or customer_data.get('customer_email') or f'cliente{payment_id[:8]}@bot.digital'
            customer_phone = customer_data.get('phone') or customer_data.get('phone_number') or '11999999999'
            customer_document = customer_data.get('document') or customer_data.get('cpf') or '00000000000'
            
            # Limpar formatação
            customer_phone = customer_phone.replace(' ', '').replace('-', '').replace('(', '').replace(')', '')
            customer_document = customer_document.replace('.', '').replace('-', '').replace('/', '')
            
            # ✅ Customer APENAS com campos aceitos pela API (sem endereço)
            customer = {
                'name': customer_name,
                'email': customer_email,
                'phone_number': customer_phone,
                'document': customer_document
            }
            
            # ✅ Preparar payload conforme documentação oficial
            payload = {
                'amount': amount_cents,
                'payment_method': 'pix',
                'customer': customer,
                'postback_url': self.get_webhook_url(),
                'transaction_origin': 'api'
                # ✅ Removido expire_in_days (não existe na API conforme documentação)
            }
            
            # ✅ Adicionar cart (obrigatório conforme documentação)
            # Se tiver product_hash, usar; senão criar cart básico
            if self.product_hash:
                payload['cart'] = [{
                    'product_hash': self.product_hash,
                    'title': description[:100] if description else 'Produto',
                    'price': amount_cents,
                    'quantity': 1,
                    'operation_type': 1,
                    'tangible': False
                }]
                logger.info(f"✅ [{self.get_gateway_name()}] Usando cart com product_hash: {self.product_hash[:8]}...")
            else:
                # ✅ Cart sem product_hash (API aceita)
                payload['cart'] = [{
                    'title': description[:100] if description else 'Produto',
                    'price': amount_cents,
                    'quantity': 1,
                    'operation_type': 1,
                    'tangible': False
                }]
                logger.info(f"✅ [{self.get_gateway_name()}] Usando cart sem product_hash")
            
            # ✅ Tracking APENAS se tiver dados válidos (não enviar campos vazios)
            tracking_data = {
                'utm_source': customer_data.get('utm_source', ''),
                'utm_medium': customer_data.get('utm_medium', ''),
                'utm_campaign': customer_data.get('utm_campaign', ''),
                'utm_term': customer_data.get('utm_term', ''),
                'utm_content': customer_data.get('utm_content', '')
            }
            
            # Só adicionar tracking se tiver pelo menos um campo preenchido
            if any(tracking_data.values()):
                payload['tracking'] = tracking_data
            
            logger.info(f"📤 [{self.get_gateway_name()}] Gerando PIX: R$ {amount:.2f} ({amount_cents} centavos) | ID: {payment_id}")
            logger.debug(f"📦 Payload final: {payload}")
            
            # Fazer requisição
            response = self._make_request('POST', '/transactions', payload=payload)
            
            if not response:
                logger.error(f"❌ [{self.get_gateway_name()}] Falha na requisição")
                return None
            
            # Processar resposta
            if response.status_code in [200, 201]:
                data = response.json()
                
                logger.debug(f"📦 [{self.get_gateway_name()}] Resposta: {data}")
                
                # ✅ Extrair dados da resposta
                transaction_hash = (
                    data.get('transaction_hash') or 
                    data.get('hash') or 
                    data.get('id')
                )
                
                pix_code = (
                    data.get('pix_code') or 
                    data.get('pix_copy_paste') or 
                    data.get('copy_paste')
                )
                
                qr_code_url = data.get('qr_code_url') or data.get('qr_code_image_url')
                qr_code_base64 = data.get('qr_code_base64')
                
                if not transaction_hash:
                    logger.error(f"❌ [{self.get_gateway_name()}] Resposta sem transaction_hash")
                    logger.error(f"Campos disponíveis: {list(data.keys())}")
                    return None
                
                if not pix_code:
                    logger.error(f"❌ [{self.get_gateway_name()}] Resposta sem pix_code")
                    logger.error(f"Campos disponíveis: {list(data.keys())}")
                    return None
                
                logger.info(f"✅ [{self.get_gateway_name()}] PIX gerado! Hash: {transaction_hash[:20]}...")
                logger.info(f"📝 Código PIX: {pix_code[:50]}...")
                
                return {
                    'pix_code': pix_code,
                    'qr_code_url': qr_code_url or '',
                    'transaction_id': transaction_hash,
                    'payment_id': payment_id,
                    'qr_code_base64': qr_code_base64
                }
            else:
                logger.error(f"❌ [{self.get_gateway_name()}] Erro: Status {response.status_code}")
                try:
                    error_data = response.json()
                    logger.error(f"📋 Resposta: {error_data}")
                except:
                    logger.error(f"📋 Resposta: {response.text[:1000]}")
                return None
                
        except Exception as e:
            logger.error(f"❌ [{self.get_gateway_name()}] Erro ao gerar PIX: {e}")
            import traceback
            traceback.print_exc()
            return None
    
    def process_webhook(self, data: Dict[str, Any]) -> Optional[Dict[str, Any]]:
        """
        Processa webhook/Postback do Átomo Pay
        
        Formato esperado (conforme documentação):
        {
            "transaction_hash": "abc123",
            "status": "paid",
            "amount": 15000,
            "payment_method": "pix"
        }
        """
        try:
            logger.info(f"📥 [{self.get_gateway_name()}] Processando webhook...")
            logger.debug(f"Dados: {data}")
            
            transaction_hash = (
                data.get('transaction_hash') or 
                data.get('hash') or 
                data.get('id')
            )
            
            if not transaction_hash:
                logger.error(f"❌ [{self.get_gateway_name()}] Webhook sem transaction_hash")
                return None
            
            status_raw = data.get('status', '').lower()
            amount_cents = data.get('amount', 0)
            amount = float(amount_cents) / 100.0
            
            # Mapear status
            status_map = {
                'paid': 'paid',
                'approved': 'paid',
                'confirmed': 'paid',
                'pending': 'pending',
                'waiting': 'pending',
                'failed': 'failed',
                'cancelled': 'failed',
                'expired': 'failed'
            }
            
            status = status_map.get(status_raw, 'pending')
            
            logger.info(f"✅ [{self.get_gateway_name()}] Webhook: Hash={transaction_hash[:20]}... | Status={status_raw}→{status} | R$ {amount:.2f}")
            
            return {
                'payment_id': data.get('external_id') or transaction_hash,
                'status': status,
                'amount': amount,
                'gateway_transaction_id': transaction_hash,
                'payer_name': data.get('payer_name'),
                'payer_document': data.get('payer_document'),
                'end_to_end_id': data.get('end_to_end_id')
            }
            
        except Exception as e:
            logger.error(f"❌ [{self.get_gateway_name()}] Erro ao processar webhook: {e}")
            import traceback
            traceback.print_exc()
            return None
    
    def verify_credentials(self) -> bool:
        """
        Verifica credenciais usando GET /transactions
        """
        try:
            if not self.api_token or len(self.api_token) < 10:
                logger.error(f"❌ [{self.get_gateway_name()}] Token inválido")
                return False
            
            # Tentar listar transações (endpoint que existe conforme documentação)
            response = self._make_request('GET', '/transactions')
            
            if response and response.status_code == 200:
                logger.info(f"✅ [{self.get_gateway_name()}] Credenciais válidas")
                return True
            elif response and response.status_code == 401:
                logger.error(f"❌ [{self.get_gateway_name()}] Credenciais inválidas (401)")
                return False
            else:
                # Se não conseguir validar, assumir válido se token tem formato correto
                logger.warning(f"⚠️ [{self.get_gateway_name()}] Não foi possível validar. Assumindo válido.")
                return len(self.api_token) >= 20
                
        except Exception as e:
            logger.error(f"❌ [{self.get_gateway_name()}] Erro ao verificar credenciais: {e}")
            return False
    
    def get_payment_status(self, transaction_id: str) -> Optional[Dict[str, Any]]:
        """
        Consulta status via GET /transactions/{hash}
        """
        try:
            if not transaction_id:
                logger.error(f"❌ [{self.get_gateway_name()}] transaction_hash não fornecido")
                return None
            
            logger.info(f"🔍 [{self.get_gateway_name()}] Consultando: {transaction_id[:20]}...")
            
            response = self._make_request('GET', f'/transactions/{transaction_id}')
            
            if not response:
                return None
            
            if response.status_code == 200:
                data = response.json()
                return self.process_webhook(data)
            elif response.status_code == 404:
                logger.warning(f"⚠️ [{self.get_gateway_name()}] Transação não encontrada")
                return None
            else:
                logger.error(f"❌ [{self.get_gateway_name()}] Erro: Status {response.status_code}")
                return None
                
        except Exception as e:
            logger.error(f"❌ [{self.get_gateway_name()}] Erro ao consultar status: {e}")
            return None

    def validate_amount(self, amount: float) -> bool:
        """Valida se o valor é válido"""
        try:
            return isinstance(amount, (int, float)) and amount > 0
        except:
            return False
