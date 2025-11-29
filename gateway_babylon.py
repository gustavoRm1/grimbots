"""
Gateway Babylon - Implementação Isolada
"""

import os
import requests
import logging
from typing import Dict, Any, Optional, List
from gateway_interface import PaymentGateway

logger = logging.getLogger(__name__)


class BabylonGateway(PaymentGateway):
    """
    Implementação do gateway Babylon
    
    Características:
    - Autenticação via API Key
    - Geração de PIX
    - Webhook para confirmação de pagamento
    """
    
    def __init__(self, api_key: str, split_percentage: float = 2.0, split_user_id: str = None):
        """
        Inicializa gateway Babylon
        
        Args:
            api_key: API Key do Babylon
            split_percentage: Percentual de split (padrão: 2%)
            split_user_id: ID do usuário para split (opcional)
        """
        self.api_key = api_key
        self.split_percentage = split_percentage
        self.split_user_id = split_user_id
        self.base_url = os.environ.get('BABYLON_API_URL', 'https://api.bancobabylon.com/functions/v1')
    
    def get_gateway_name(self) -> str:
        """Nome amigável do gateway"""
        return "Babylon"
    
    def get_gateway_type(self) -> str:
        """Tipo do gateway para roteamento"""
        return "babylon"
    
    def get_webhook_url(self) -> str:
        """URL do webhook Babylon"""
        webhook_base = os.environ.get('WEBHOOK_URL', '')
        return f"{webhook_base}/webhook/payment/babylon"
    
    def generate_pix(
        self, 
        amount: float, 
        description: str, 
        payment_id: str,
        customer_data: Optional[Dict[str, Any]] = None
    ) -> Optional[Dict[str, Any]]:
        """
        Gera PIX via Babylon
        
        Endpoint: POST https://api.bancobabylon.com/functions/v1/transactions
        
        Documentação: Valor em centavos, customer obrigatório, items obrigatório
        """
        try:
            # Validar valor (mínimo R$ 1,00 = 100 centavos)
            if not self.validate_amount(amount):
                logger.error(f"❌ [{self.get_gateway_name()}] Valor inválido: {amount}")
                return None
            
            if amount < 1.0:
                logger.error(f"❌ [{self.get_gateway_name()}] Valor mínimo é R$ 1,00. Recebido: R$ {amount:.2f}")
                return None
            
            # Converter valor para centavos
            amount_cents = int(amount * 100)
            
            # Preparar headers
            headers = {
                'Authorization': f'Bearer {self.api_key}',
                'Accept': 'application/json',
                'Content-Type': 'application/json'
            }
            
            # ✅ Preparar customer (obrigatório)
            customer_name = 'Cliente'
            customer_email = 'cliente@email.com'
            customer_phone = '11999999999'
            customer_document = '00000000000'
            
            if customer_data:
                customer_name = customer_data.get('name', customer_name)
                customer_email = customer_data.get('email', customer_email)
                customer_phone = customer_data.get('phone', customer_phone)
                customer_document = customer_data.get('cpf') or customer_data.get('document', customer_document)
            
            # Remover formatação do telefone e documento (apenas números)
            customer_phone = ''.join(filter(str.isdigit, customer_phone))
            customer_document = ''.join(filter(str.isdigit, customer_document))
            
            # ✅ Validar expiresInDays (obrigatório: 1 a 7 dias conforme documentação)
            # Por padrão, usar 1 dia. No futuro, pode ser configurável via customer_data ou gateway config
            expires_in_days = 1
            if customer_data and 'pix_expires_in_days' in customer_data:
                # Permitir configuração via customer_data (futuro)
                try:
                    custom_expires = int(customer_data['pix_expires_in_days'])
                    if 1 <= custom_expires <= 7:
                        expires_in_days = custom_expires
                    else:
                        logger.warning(f"⚠️ [{self.get_gateway_name()}] expiresInDays fora do range (1-7), usando padrão: 1")
                except (ValueError, TypeError):
                    logger.warning(f"⚠️ [{self.get_gateway_name()}] expiresInDays inválido, usando padrão: 1")
            
            # Preparar payload conforme documentação
            payload = {
                'customer': {
                    'name': customer_name,
                    'email': customer_email,
                    'phone': customer_phone,
                    'document': {
                        'number': customer_document,
                        'type': 'CPF'  # Assumir CPF por padrão (pode ser CNPJ se tiver 14 dígitos)
                    }
                },
                'paymentMethod': 'PIX',
                'amount': amount_cents,  # Valor em centavos
                'items': [
                    {
                        'title': description[:100] if description else 'Produto',
                        'unitPrice': amount_cents,
                        'quantity': 1,
                        'externalRef': payment_id[:50] if payment_id else None
                    }
                ],
                'pix': {
                    'expiresInDays': expires_in_days  # ✅ Obrigatório: 1 a 7 dias (conforme documentação)
                },
                'postbackUrl': self.get_webhook_url(),
                'description': description[:500] if description else None
            }
            
            # ✅ Remover campos None do payload
            if not payload['description']:
                del payload['description']
            if not payload['items'][0]['externalRef']:
                del payload['items'][0]['externalRef']
            
            # ✅ Adicionar split se configurado (formato Babylon: recipientId + amount em centavos)
            if self.split_user_id and self.split_percentage > 0:
                split_amount_cents = int(amount_cents * (self.split_percentage / 100))
                
                # Garantir mínimo de 1 centavo
                if split_amount_cents < 1:
                    split_amount_cents = 1
                
                # Garantir que sobra pelo menos 1 centavo para o vendedor
                if split_amount_cents >= amount_cents:
                    split_amount_cents = amount_cents - 1
                
                payload['split'] = [
                    {
                        'recipientId': self.split_user_id,
                        'amount': split_amount_cents
                    }
                ]
                logger.info(f"💰 [{self.get_gateway_name()}] Split configurado: {split_amount_cents} centavos ({self.split_percentage}%) para recipientId {self.split_user_id}")
            
            # ✅ Ajustar tipo de documento se for CNPJ (14 dígitos)
            if len(customer_document) == 14:
                payload['customer']['document']['type'] = 'CNPJ'
            
            # Endpoint conforme documentação
            pix_url = f"{self.base_url}/transactions"
            
            logger.info(f"📤 [{self.get_gateway_name()}] Gerando PIX de R$ {amount:.2f} ({amount_cents} centavos)...")
            logger.debug(f"📋 [{self.get_gateway_name()}] URL: {pix_url}")
            logger.debug(f"📋 [{self.get_gateway_name()}] Payload (resumido): paymentMethod=PIX, amount={amount_cents}, customer.name={customer_name}")
            
            # Fazer requisição
            response = requests.post(pix_url, json=payload, headers=headers, timeout=15)
            
            # Processar resposta
            if response.status_code == 201:  # 201 Created conforme documentação
                data = response.json()
                
                # ✅ Extrair dados conforme formato da resposta
                transaction_id = data.get('id')
                status = data.get('status', 'pending')
                
                # ✅ Extrair dados do PIX
                pix_info = data.get('pix', {})
                
                # ✅ Tentar extrair código PIX de múltiplos campos possíveis
                # Prioridade: copyPaste > emv > qrcode (pode ser URL)
                pix_code = None
                if isinstance(pix_info, dict):
                    pix_code = (
                        pix_info.get('copyPaste') or      # Código PIX copia e cola
                        pix_info.get('emv') or           # Código EMV
                        pix_info.get('qrcode')           # Pode ser URL ou código
                    )
                
                # ✅ Se qrcode for URL, tentar fazer requisição para obter código PIX
                # Ou usar outros campos da resposta
                if pix_code and pix_code.startswith('http'):
                    logger.warning(f"⚠️ [{self.get_gateway_name()}] qrcode é uma URL, tentando obter código PIX...")
                    
                    # Tentar extrair de outros campos da resposta
                    pix_code_alt = (
                        data.get('copyPaste') or
                        data.get('emv') or
                        data.get('pix_copy_paste') or
                        data.get('pix_emv')
                    )
                    
                    if pix_code_alt and not pix_code_alt.startswith('http'):
                        logger.info(f"✅ [{self.get_gateway_name()}] Código PIX encontrado em campo alternativo")
                        pix_code = pix_code_alt
                    else:
                        # Se não encontrar, manter URL como fallback (será tratado no bot_manager)
                        logger.warning(f"⚠️ [{self.get_gateway_name()}] Código PIX não encontrado, usando URL como fallback")
                        # pix_code permanece como URL
                
                expiration_date = pix_info.get('expirationDate') if isinstance(pix_info, dict) else None
                end_to_end_id = pix_info.get('end2EndId') if isinstance(pix_info, dict) else None
                
                if not transaction_id:
                    logger.error(f"❌ [{self.get_gateway_name()}] Resposta não contém ID da transação: {data}")
                    return None
                
                if not pix_code:
                    logger.error(f"❌ [{self.get_gateway_name()}] Resposta não contém código PIX: {data}")
                    logger.error(f"📋 Estrutura da resposta: {list(data.keys())}")
                    if isinstance(pix_info, dict):
                        logger.error(f"📋 Campos do objeto pix: {list(pix_info.keys())}")
                    return None
                
                logger.info(f"✅ [{self.get_gateway_name()}] PIX gerado com sucesso!")
                logger.info(f"📝 Transaction ID: {transaction_id}")
                logger.info(f"📝 Status: {status}")
                if expiration_date:
                    logger.info(f"⏰ Expira em: {expiration_date}")
                
                # ✅ Gerar URL do QR Code
                # Se pix_code já for uma URL, usar diretamente como qr_code_url
                # Se for código PIX em texto, gerar URL do QR Code
                import urllib.parse
                
                if pix_code.startswith('http'):
                    # Se for URL, usar como qr_code_url
                    # Mas avisar que não temos código PIX copia e cola
                    qr_code_url = pix_code
                    qr_code_base64 = None
                    logger.warning(f"⚠️ [{self.get_gateway_name()}] Código PIX é uma URL. Sistema usará URL como fallback.")
                else:
                    # Código PIX em texto - gerar URL do QR Code
                    qr_code_url = f'https://api.qrserver.com/v1/create-qr-code/?size=400x400&data={urllib.parse.quote(pix_code)}'
                    qr_code_base64 = None
                    logger.info(f"✅ [{self.get_gateway_name()}] Código PIX em texto extraído com sucesso")
                
                # ✅ Converter expiration_date para datetime se necessário
                expires_at = None
                if expiration_date:
                    try:
                        from datetime import datetime
                        # Formato: "2025-04-03T16:19:43-03:00"
                        expires_at = datetime.fromisoformat(expiration_date.replace('Z', '+00:00'))
                    except Exception as e:
                        logger.warning(f"⚠️ [{self.get_gateway_name()}] Erro ao converter expirationDate: {e}")
                
                return {
                    'pix_code': pix_code,  # Pode ser URL ou código PIX
                    'qr_code_url': qr_code_url,
                    'qr_code_base64': qr_code_base64,
                    'transaction_id': transaction_id,
                    'payment_id': payment_id,
                    'expires_at': expires_at
                }
            else:
                error_data = response.json() if response.text else {}
                logger.error(f"❌ [{self.get_gateway_name()}] Erro: Status {response.status_code}")
                logger.error(f"📋 Resposta: {error_data}")
                
                # Log detalhado do erro
                if isinstance(error_data, dict):
                    error_message = error_data.get('message') or error_data.get('error') or str(error_data)
                    logger.error(f"📋 Mensagem de erro: {error_message}")
                
                return None
                
        except Exception as e:
            logger.error(f"❌ [{self.get_gateway_name()}] Erro ao gerar PIX: {e}", exc_info=True)
            return None
    
    def process_webhook(self, data: Dict[str, Any]) -> Optional[Dict[str, Any]]:
        """
        Processa webhook Babylon
        
        Estrutura do webhook:
        {
            "id": "F92XRTVSGB2B",
            "type": "transaction",
            "objectId": "28a65292-6c74-4368-924d-f52a653706be",
            "data": {
                "id": "28a65292-6c74-4368-924d-f52a653706be",
                "amount": 10000,  // em centavos
                "status": "paid",
                "pix": {
                    "end2EndId": "E12345678202009091221abcdef12345"
                },
                "customer": {
                    "name": "TESTE PIX",
                    "document": "01234567890"
                },
                "paidAt": "2025-04-03T15:59:43.56-03:00"
            }
        }
        """
        try:
            payload = data or {}
            
            # ✅ Babylon estrutura: data dentro de 'data'
            transaction_data = payload.get('data', payload)  # Fallback: se não tiver 'data', usar payload direto
            
            # Identificadores
            object_id = payload.get('objectId') or transaction_data.get('id')
            transaction_id = transaction_data.get('id')
            
            identifier = object_id or transaction_id
            
            if not identifier:
                logger.error(f"❌ [{self.get_gateway_name()}] Webhook sem identificador")
                return None

            normalized_identifier = str(identifier).strip()
            identifier_lower = normalized_identifier.lower()

            # Status do webhook
            raw_status = str(transaction_data.get('status', '')).strip().lower()
            
            # ✅ Mapear status conforme documentação Babylon
            status_map = {
                'paid': 'paid',
                'waiting_payment': 'pending',
                'refused': 'failed',
                'canceled': 'failed',
                'refunded': 'failed',
                'chargedback': 'failed',
                'failed': 'failed',
                'expired': 'failed',
                'in_analisys': 'pending',
                'in_protest': 'pending'
            }
            
            mapped_status = status_map.get(raw_status, 'pending')
            
            # ✅ Valor vem em CENTAVOS (amount: 10000 = R$ 100,00)
            amount_cents = transaction_data.get('amount', 0)
            try:
                amount_cents = int(amount_cents) if amount_cents else 0
            except (ValueError, TypeError):
                logger.warning(f"⚠️ [{self.get_gateway_name()}] Valor inválido: {amount_cents}, usando 0")
                amount_cents = 0
            
            amount = amount_cents / 100  # Converter centavos para reais
            
            # ✅ Extrair dados do cliente
            customer = transaction_data.get('customer', {})
            payer_name = customer.get('name') if isinstance(customer, dict) else None
            payer_cpf = customer.get('document') if isinstance(customer, dict) else None
            
            # ✅ Extrair end2EndId do PIX
            pix_data = transaction_data.get('pix', {})
            end_to_end = pix_data.get('end2EndId') if isinstance(pix_data, dict) else None
            
            # ✅ Timestamp de pagamento
            paid_at = transaction_data.get('paidAt')
            
            logger.info(
                f"📥 [{self.get_gateway_name()}] Webhook recebido: {identifier} - "
                f"Status: {raw_status} → {mapped_status} - Valor: R$ {amount:.2f}"
            )

            if payer_name:
                logger.info(f"👤 Pagador: {payer_name} (CPF: {payer_cpf})")
            if end_to_end:
                logger.info(f"🔑 End-to-End ID: {end_to_end}")
            if paid_at:
                logger.info(f"⏰ Pago em: {paid_at}")

            return {
                'payment_id': normalized_identifier,
                'status': mapped_status,
                'amount': amount,
                'gateway_transaction_id': identifier_lower,
                'payer_name': payer_name,
                'payer_document': payer_cpf,
                'end_to_end_id': end_to_end,
                'raw_status': raw_status,
                'raw_data': payload,
                'paid_at': paid_at
            }

        except Exception as e:
            logger.error(f"❌ [{self.get_gateway_name()}] Erro ao processar webhook: {e}", exc_info=True)
            return None
    
    def verify_credentials(self) -> bool:
        """
        Verifica se credenciais Babylon são válidas
        
        TODO: Implementar validação real se a API fornecer endpoint de verificação
        """
        try:
            if not self.api_key:
                return False
            
            # Validação básica de formato
            if len(self.api_key) < 10:
                logger.error(f"❌ [{self.get_gateway_name()}] API Key muito curta")
                return False
            
            # TODO: Se API tiver endpoint de verificação, fazer requisição real
            logger.info(f"✅ [{self.get_gateway_name()}] API Key parece válida (formato correto)")
            return True
            
        except Exception as e:
            logger.error(f"❌ [{self.get_gateway_name()}] Erro ao verificar credenciais: {e}")
            return False
    
    def get_payment_status(self, transaction_id: str) -> Optional[Dict[str, Any]]:
        """
        Consulta status de pagamento no Babylon
        
        Endpoint: GET https://api.bancobabylon.com/functions/v1/transactions/{id}
        
        Documentação: Retorna detalhes completos da transação pelo ID
        """
        try:
            # ✅ Endpoint conforme documentação
            query_url = f"{self.base_url}/transactions/{transaction_id}"
            
            headers = {
                'Authorization': f'Bearer {self.api_key}',
                'Accept': 'application/json'
            }
            
            logger.info(f"🔍 [{self.get_gateway_name()}] Consultando status da transação: {transaction_id}")
            
            response = requests.get(query_url, headers=headers, timeout=10)
            
            if response.status_code == 200:
                data = response.json()
                
                # ✅ A resposta do GET /transactions/{id} tem a mesma estrutura que o webhook
                # Processar usando a mesma lógica do webhook para manter consistência
                logger.info(f"✅ [{self.get_gateway_name()}] Status consultado com sucesso")
                return self.process_webhook(data)
                
            elif response.status_code == 401:
                logger.error(f"❌ [{self.get_gateway_name()}] Não autorizado - credenciais inválidas")
                return None
                
            elif response.status_code == 404:
                logger.warning(f"⚠️ [{self.get_gateway_name()}] Transação não encontrada: {transaction_id}")
                return None
                
            elif response.status_code == 500:
                logger.error(f"❌ [{self.get_gateway_name()}] Erro interno do servidor Babylon")
                logger.error(f"📋 Resposta: {response.text[:500]}")
                return None
                
            else:
                logger.error(f"❌ [{self.get_gateway_name()}] Erro ao consultar status: {response.status_code}")
                logger.error(f"📋 Resposta: {response.text[:500]}")
                return None
                
        except requests.exceptions.Timeout:
            logger.error(f"❌ [{self.get_gateway_name()}] Timeout ao consultar status: {transaction_id}")
            return None
            
        except requests.exceptions.RequestException as e:
            logger.error(f"❌ [{self.get_gateway_name()}] Erro de conexão ao consultar status: {e}")
            return None
            
        except Exception as e:
            logger.error(f"❌ [{self.get_gateway_name()}] Erro ao consultar status: {e}", exc_info=True)
            return None

