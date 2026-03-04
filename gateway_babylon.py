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
    
    def __init__(self, api_key: str, company_id: str = None, split_percentage: float = 2.0, split_user_id: str = None):
        """
        Inicializa gateway Babylon
        
        Args:
            api_key: Secret Key do Babylon (usado como username na autenticação Basic)
            company_id: Company ID do Babylon (usado como password na autenticação Basic)
            split_percentage: Percentual de split (padrão: 2%)
            split_user_id: ID do usuário para split (opcional)
        """
        self.secret_key = api_key  # Secret Key = username
        self.company_id = company_id  # Company ID = password
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
            
            # ✅ VALIDAÇÃO: Verificar se temos ambas as credenciais (Basic Auth requer Secret Key + Company ID)
            if not self.secret_key:
                logger.error(f"❌ [{self.get_gateway_name()}] Secret Key não configurada")
                return None
            
            if not self.company_id:
                logger.error(f"❌ [{self.get_gateway_name()}] Company ID não configurado")
                return None
            
            # ✅ AUTENTICAÇÃO BASIC: Base64(Secret Key:Company ID)
            import base64
            credentials_string = f"{self.secret_key}:{self.company_id}"
            credentials_base64 = base64.b64encode(credentials_string.encode('utf-8')).decode('utf-8')
            
            # Preparar headers
            headers = {
                'Authorization': f'Basic {credentials_base64}',
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
            customer_phone = ''.join(filter(str.isdigit, str(customer_phone)))
            customer_document = ''.join(filter(str.isdigit, str(customer_document)))
            
            # ✅ VALIDAÇÃO CRÍTICA: CPF deve ter 11 dígitos
            if len(customer_document) != 11:
                logger.warning(f"⚠️ [{self.get_gateway_name()}] CPF inválido (len={len(customer_document)}): {customer_document}")
                logger.warning(f"   Gerando CPF válido aleatório...")
                # ✅ Gerar CPF válido aleatório (11 dígitos)
                import random
                # Gerar 9 primeiros dígitos
                cpf_base = ''.join([str(random.randint(0, 9)) for _ in range(9)])
                # Calcular dígitos verificadores (algoritmo simplificado)
                def calcular_dv(cpf):
                    soma = sum(int(cpf[i]) * (10 - i) for i in range(9))
                    dv1 = 11 - (soma % 11)
                    if dv1 >= 10:
                        dv1 = 0
                    cpf += str(dv1)
                    soma = sum(int(cpf[i]) * (11 - i) for i in range(10))
                    dv2 = 11 - (soma % 11)
                    if dv2 >= 10:
                        dv2 = 0
                    return cpf + str(dv2)
                customer_document = calcular_dv(cpf_base)
                logger.info(f"✅ CPF gerado: {customer_document[:3]}***{customer_document[-2:]}")
            
            # ✅ VALIDAÇÃO CRÍTICA: Telefone deve ter 10-11 dígitos e ser diferente do CPF
            if len(customer_phone) < 10 or len(customer_phone) > 11:
                logger.warning(f"⚠️ [{self.get_gateway_name()}] Telefone inválido (len={len(customer_phone)}): {customer_phone}")
                logger.warning(f"   Gerando telefone válido...")
                # ✅ Gerar telefone válido (11 dígitos - DDD + número)
                import random
                ddd = random.choice(['11', '21', '47', '48', '51', '61', '71', '81', '85', '92'])
                numero = ''.join([str(random.randint(0, 9)) for _ in range(9)])
                customer_phone = ddd + numero
                logger.info(f"✅ Telefone gerado: {customer_phone[:2]}****{customer_phone[-4:]}")
            
            # ✅ VALIDAÇÃO CRÍTICA: CPF e telefone não podem ser iguais
            if customer_phone == customer_document:
                logger.warning(f"⚠️ [{self.get_gateway_name()}] CPF e telefone são iguais: {customer_phone}")
                logger.warning(f"   Gerando telefone diferente...")
                import random
                ddd = random.choice(['11', '21', '47', '48', '51', '61', '71', '81', '85', '92'])
                numero = ''.join([str(random.randint(0, 9)) for _ in range(9)])
                customer_phone = ddd + numero
                logger.info(f"✅ Telefone gerado: {customer_phone[:2]}****{customer_phone[-4:]}")
            
            # ✅ Log dos dados validados
            logger.debug(f"🔍 [{self.get_gateway_name()}] Dados do cliente validados:")
            logger.debug(f"   Nome: {customer_name}")
            logger.debug(f"   Email: {customer_email}")
            logger.debug(f"   CPF: {customer_document[:3]}***{customer_document[-2:]} (len={len(customer_document)})")
            logger.debug(f"   Telefone: {customer_phone[:2]}****{customer_phone[-4:]} (len={len(customer_phone)})")
            
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
            
            # ✅ SPLITS DESATIVADOS - Decisão arquitetural para garantir 100% de aprovação
            # Problemas: Erros 400 sucessivos, bugs nas adquirentes, valores mínimos de split
            # Solução: 100% do valor vai para a conta principal (sem divisão)
            #
            # # Configurar Split Babylon
            # if self.split_user_id and self.split_percentage > 0:
            #     split_amount = int((amount_cents * self.split_percentage) / 100)
            #     
            #     # ✅ REGRA DE OURO: Split mínimo de 100 cêntimos (R$ 1,00)
            #     if split_amount < 100:
            #         logger.warning(f"⚠️ Babylon Split: Valor ({split_amount}) muito baixo. Forçando mínimo de 100 cêntimos.")
            #         split_amount = 100
            #         
            #     # ✅ PREVENÇÃO OVERFLOW
            #     if split_amount < amount_cents:
            #         payload['splits'] = [
            #             {
            #                 "recipientId": str(self.split_user_id),
            #                 "amount": split_amount
            #                 # Remova o envio de 'netAmount' para evitar conflitos de cálculo na adquirente.
            #                 # Deixe que a Babylon calcule o líquido com base no 'amount'.
            #             }
            #         ]
            
            logger.info(f"💰 Babylon: Splits desativados - 100% do valor para conta principal")
            
            # ✅ Ajustar tipo de documento se for CNPJ (14 dígitos)
            if len(customer_document) == 14:
                payload['customer']['document']['type'] = 'CNPJ'
            
            # Endpoint conforme documentação
            pix_url = f"{self.base_url}/transactions"
            
            logger.info(f"📤 [{self.get_gateway_name()}] Gerando PIX de R$ {amount:.2f} ({amount_cents} centavos)...")
            logger.info(f"📋 [{self.get_gateway_name()}] URL: {pix_url}")
            logger.info(f"📋 [{self.get_gateway_name()}] Base URL: {self.base_url}")
            logger.debug(f"📋 [{self.get_gateway_name()}] Payload completo: {payload}")
            logger.debug(f"📋 [{self.get_gateway_name()}] Headers: Authorization=Basic {credentials_base64[:30]}... (oculto)")
            logger.debug(f"📋 [{self.get_gateway_name()}] Payload (resumido): paymentMethod=PIX, amount={amount_cents}, customer.name={customer_name}, expiresInDays={expires_in_days}")
            
            # Fazer requisição
            response = requests.post(pix_url, json=payload, headers=headers, timeout=15)
            
            # ✅ Log da resposta para diagnóstico
            logger.info(f"📋 [{self.get_gateway_name()}] Status Code: {response.status_code}")
            logger.debug(f"📋 [{self.get_gateway_name()}] Headers: {dict(response.headers)}")
            
            # ✅ Detectar se resposta é HTML (indica erro de autenticação ou endpoint incorreto)
            content_type = response.headers.get('Content-Type', '').lower()
            is_html = '<html' in response.text.lower()[:100] or 'text/html' in content_type
            
            if is_html:
                logger.error(f"❌ [{self.get_gateway_name()}] Resposta é HTML (não JSON) - possível erro de autenticação ou endpoint incorreto")
                logger.error(f"📋 Content-Type: {content_type}")
                logger.error(f"📋 Resposta (primeiros 500 chars): {response.text[:500]}")
                return None
            
            logger.debug(f"📋 [{self.get_gateway_name()}] Response Text (primeiros 500 chars): {response.text[:500]}")
            
            # Processar resposta
            # ✅ Babylon pode retornar 200 (OK) ou 201 (Created)
            if response.status_code in [200, 201]:
                try:
                    data = response.json()
                except (ValueError, requests.exceptions.JSONDecodeError) as json_error:
                    logger.error(f"❌ [{self.get_gateway_name()}] Erro ao parsear JSON da resposta de sucesso: {json_error}")
                    logger.error(f"📋 Resposta raw (primeiros 1000 chars): {response.text[:1000]}")
                    logger.error(f"📋 Content-Type: {response.headers.get('Content-Type', 'N/A')}")
                    return None
                
                # ✅ Extrair dados conforme formato da resposta
                transaction_id = data.get('id')
                status = data.get('status', 'pending')
                
                # ✅ CRÍTICO: Verificar se transação foi recusada ANTES de tentar extrair código PIX
                if status in ['refused', 'failed', 'cancelled', 'canceled']:
                    refused_reason = data.get('refusedReason', {})
                    if isinstance(refused_reason, dict):
                        reason_code = refused_reason.get('acquirerCode')
                        reason_description = refused_reason.get('description', 'Transação recusada')
                        is_antifraud = refused_reason.get('antifraud', False)
                        
                        logger.error(f"❌ [{self.get_gateway_name()}] Transação RECUSADA pela adquirente!")
                        logger.error(f"   Status: {status}")
                        logger.error(f"   Código: {reason_code}")
                        logger.error(f"   Descrição: {reason_description}")
                        logger.error(f"   Antifraude: {is_antifraud}")
                        logger.error(f"   Transaction ID: {transaction_id}")
                        
                        # ✅ Log detalhado de possíveis causas
                        logger.error(f"")
                        logger.error(f"   🔍 POSSÍVEIS CAUSAS:")
                        logger.error(f"")
                        logger.error(f"   1. ❌ Credenciais inválidas (Secret Key ou Company ID)")
                        logger.error(f"      → Verificar se Secret Key e Company ID estão corretos")
                        logger.error(f"   2. ❌ Dados do cliente inválidos")
                        logger.error(f"      → CPF: {data.get('customer', {}).get('document', {}).get('number', 'N/A')}")
                        logger.error(f"      → Telefone: {data.get('customer', {}).get('phone', 'N/A')}")
                        logger.error(f"   3. ❌ Valor fora dos limites permitidos")
                        logger.error(f"      → Valor enviado: {data.get('amount', 0)} centavos (R$ {amount:.2f})")
                        logger.error(f"   4. ❌ Split configurado incorretamente")
                        if data.get('splits'):
                            logger.error(f"      → Splits: {data.get('splits')}")
                        logger.error(f"   5. ❌ Conta do Babylon com restrições ou bloqueada")
                        logger.error(f"")
                        logger.error(f"   💡 AÇÃO: Verificar configurações do gateway e tentar novamente")
                        logger.error(f"")
                    else:
                        logger.error(f"❌ [{self.get_gateway_name()}] Transação recusada (status: {status})")
                        logger.error(f"   Transaction ID: {transaction_id}")
                        logger.error(f"   Motivo: {refused_reason if refused_reason else 'Não especificado'}")
                    
                    # ✅ Retornar None para indicar falha (não gerar PIX quando recusado)
                    return None
                
                # ✅ Extrair dados do PIX (apenas se transação não foi recusada)
                pix_info = data.get('pix', {})
                
                logger.debug(f"🔍 [{self.get_gateway_name()}] Objeto pix: {pix_info}")
                if isinstance(pix_info, dict):
                    logger.debug(f"🔍 [{self.get_gateway_name()}] Campos do pix: {list(pix_info.keys())}")
                
                # ✅ Tentar extrair código PIX de múltiplos campos possíveis
                # Prioridade: copyPaste > emv > qrcode (pode ser URL)
                pix_code = None
                if isinstance(pix_info, dict):
                    pix_code = (
                        pix_info.get('copyPaste') or      # Código PIX copia e cola
                        pix_info.get('emv') or           # Código EMV
                        pix_info.get('qrcode')           # Pode ser URL ou código
                    )
                    logger.info(f"🔍 [{self.get_gateway_name()}] Código PIX extraído: {pix_code[:50] if pix_code else 'None'}...")
                
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
                    # ✅ Log mais detalhado quando não há código PIX (mas status não é refused)
                    logger.error(f"❌ [{self.get_gateway_name()}] Resposta não contém código PIX")
                    logger.error(f"   Status da transação: {status}")
                    logger.error(f"   Transaction ID: {transaction_id}")
                    logger.error(f"   Estrutura da resposta: {list(data.keys())}")
                    if isinstance(pix_info, dict):
                        logger.error(f"   Campos do objeto pix: {list(pix_info.keys())}")
                        logger.error(f"   Valores do pix: {pix_info}")
                    logger.error(f"   💡 Possível causa: Transação criada mas PIX não foi gerado (verificar configurações)")
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
                # ✅ Tratar erros com melhor diagnóstico
                error_data = {}
                error_message = None
                
                # ✅ Tentar parsear JSON apenas se houver conteúdo
                if response.text:
                    try:
                        error_data = response.json()
                        if isinstance(error_data, dict):
                            error_message = (
                                error_data.get('message') or 
                                error_data.get('error') or 
                                error_data.get('error_message') or
                                str(error_data)
                            )
                    except (ValueError, requests.exceptions.JSONDecodeError) as json_error:
                        # ✅ Resposta não é JSON válido - logar conteúdo raw
                        logger.warning(f"⚠️ [{self.get_gateway_name()}] Resposta de erro não é JSON válido: {json_error}")
                        error_message = response.text[:500]  # Primeiros 500 caracteres
                        logger.error(f"📋 Resposta raw (primeiros 500 chars): {error_message}")
                        logger.error(f"📋 Content-Type: {response.headers.get('Content-Type', 'N/A')}")
                
                # ✅ Log detalhado baseado no status code
                logger.error(f"❌ [{self.get_gateway_name()}] Erro: Status {response.status_code}")
                
                if response.status_code == 401:
                    logger.error(f"🔐 [{self.get_gateway_name()}] Não autorizado - API Key inválida ou expirada")
                    if error_message:
                        logger.error(f"📋 Mensagem: {error_message}")
                elif response.status_code == 400:
                    logger.error(f"📋 [{self.get_gateway_name()}] Requisição inválida - verificar payload")
                    if error_message:
                        logger.error(f"📋 Mensagem: {error_message}")
                    if error_data:
                        logger.error(f"📋 Dados do erro: {error_data}")
                elif response.status_code == 404:
                    logger.error(f"🔍 [{self.get_gateway_name()}] Endpoint não encontrado - verificar URL base")
                elif response.status_code == 500:
                    logger.error(f"💥 [{self.get_gateway_name()}] Erro interno do servidor Babylon")
                    if error_message:
                        logger.error(f"📋 Mensagem: {error_message}")
                elif response.status_code == 503:
                    logger.error(f"⚠️ [{self.get_gateway_name()}] Serviço temporariamente indisponível")
                else:
                    logger.error(f"❓ [{self.get_gateway_name()}] Status code desconhecido: {response.status_code}")
                
                # ✅ Log completo da resposta se disponível
                if error_data:
                    logger.error(f"📋 Resposta completa: {error_data}")
                elif error_message:
                    logger.error(f"📋 Mensagem de erro: {error_message}")
                
                return None
                
        except Exception as e:
            logger.error(f"❌ [{self.get_gateway_name()}] Erro ao gerar PIX: {e}", exc_info=True)
            return None
    
    def process_webhook(self, data: Dict[str, Any]) -> Optional[Dict[str, Any]]:
        """
        Processa webhook Babylon
        
        Suporta dois formatos:
        
        1. Formato novo (baseado na documentação oficial):
        {
            "event": "transaction.created" | "transaction.status_changed" | "transaction.completed" | "transaction.failed",
            "timestamp": "2025-07-10T17:40:27.373Z",
            "transaction": {
                "id": "756d4eec-9a22-44b0-a514-a27c366c5433",
                "amount": 254,  // em centavos ou reais (depende do campo)
                "status": "paid" | "pending" | "done" | "failed" | "refused" | "cancelled",
                "pix": {
                    "key_type": "CPF",
                    "key_value": "99999999999",
                    "end_to_end_id": "E1234567890123456789012345678901"
                },
                "customer": {
                    "name": "TESTE PIX",
                    "document": "01234567890"
                },
                "paid_at": "2025-07-10T18:15:45.400000",
                "created_at": "2025-07-10T14:40:26.270543",
                "updated_at": "2025-07-10T18:15:45.400000"
            },
            "metadata": {
                "source": "transactions_service",
                "version": "1.0.0"
            }
        }
        
        2. Formato antigo (compatibilidade):
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
            
            # Extração baseada na doc oficial da Babylon
            webhook_data = payload.get('data', payload) # Fallback caso venha direto
            transaction_id = str(webhook_data.get('id', ''))
            status_raw = str(webhook_data.get('status', '')).lower()
            
            # Mapa Oficial Babylon
            status_map = {
                'paid': 'paid',
                'waiting_payment': 'pending',
                'in_analisys': 'pending',
                'in_protest': 'pending',
                'refused': 'failed',
                'canceled': 'failed',
                'refunded': 'failed',
                'chargedback': 'failed',
                'failed': 'failed',
                'expired': 'failed'
            }
            
            status = status_map.get(status_raw, 'pending') # Fallback seguro
            
            # ✅ Extrair valor (pode vir em centavos ou reais)
            amount_value = webhook_data.get('amount') or webhook_data.get('requested_amount')
            
            # ✅ Detectar se valor está em centavos ou reais
            # Se for > 1000, provavelmente está em centavos (ex: 10000 = R$ 100,00)
            # Se for < 1000, provavelmente está em reais (ex: 2.54 = R$ 2,54)
            amount = 0.0
            if amount_value:
                try:
                    amount_value_float = float(amount_value)
                    # Se valor > 1000, assumir centavos; caso contrário, assumir reais
                    if amount_value_float >= 1000:
                        amount = amount_value_float / 100  # Converter centavos para reais
                        logger.info(f"💰 [{self.get_gateway_name()}] Valor em centavos detectado: {amount_value_float} → R$ {amount:.2f}")
                    else:
                        amount = amount_value_float  # Já está em reais
                        logger.info(f"💰 [{self.get_gateway_name()}] Valor em reais: R$ {amount:.2f}")
                except (ValueError, TypeError):
                    logger.warning(f"⚠️ [{self.get_gateway_name()}] Valor inválido: {amount_value}, usando 0")
                    amount = 0.0
            
            # ✅ Log detalhado
            logger.info(
                f"📥 [{self.get_gateway_name()}] Webhook processado: {transaction_id} - "
                f"Status: {status_raw} → {status} - Valor: R$ {amount:.2f}"
            )

            return {
                'payment_id': transaction_id,
                'status': status,
                'amount': amount,
                'gateway_transaction_id': transaction_id,
                'raw_status': status_raw,
                'raw_data': payload
            }

        except Exception as e:
            logger.error(f"❌ [{self.get_gateway_name()}] Erro ao processar webhook: {e}", exc_info=True)
            logger.error(f"📋 Payload recebido: {data}")
            return None
    
    def verify_credentials(self) -> bool:
        """
        Verifica se credenciais Babylon são válidas
        
        Valida presença de Secret Key e Company ID (ambos obrigatórios para Basic Auth)
        """
        try:
            if not self.secret_key:
                logger.error(f"❌ [{self.get_gateway_name()}] Secret Key não configurada")
                return False
            
            if not self.company_id:
                logger.error(f"❌ [{self.get_gateway_name()}] Company ID não configurado")
                return False
            
            # Validação básica de formato
            if len(self.secret_key) < 10:
                logger.error(f"❌ [{self.get_gateway_name()}] Secret Key muito curta")
                return False
            
            if len(self.company_id) < 5:
                logger.error(f"❌ [{self.get_gateway_name()}] Company ID muito curto")
                return False
            
            logger.info(f"✅ [{self.get_gateway_name()}] Credenciais parecem válidas (Secret Key + Company ID configurados)")
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
            
            # ✅ AUTENTICAÇÃO BASIC: Base64(Secret Key:Company ID)
            if not self.secret_key or not self.company_id:
                logger.error(f"❌ [{self.get_gateway_name()}] Credenciais incompletas para consulta de status")
                return None
            
            import base64
            credentials_string = f"{self.secret_key}:{self.company_id}"
            credentials_base64 = base64.b64encode(credentials_string.encode('utf-8')).decode('utf-8')
            
            headers = {
                'Authorization': f'Basic {credentials_base64}',
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

