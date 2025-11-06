"""
Gateway SyncPay - Implementação Isolada
Documentação: https://syncpay.apidog.io/
"""

import os
import requests
import logging
from typing import Dict, Any, Optional
from gateway_interface import PaymentGateway

logger = logging.getLogger(__name__)


class SyncPayGateway(PaymentGateway):
    """
    Implementação do gateway SyncPay
    
    Características:
    - Autenticação via Bearer Token (expires 1h)
    - Split payment por percentual
    - Webhook para confirmação de pagamento
    """
    
    def __init__(self, client_id: str, client_secret: str):
        """
        Inicializa gateway SyncPay
        
        Args:
            client_id: UUID do client ID da SyncPay
            client_secret: UUID do client secret da SyncPay
        """
        self.client_id = client_id
        self.client_secret = client_secret
        self.base_url = "https://api.syncpayments.com.br"
        self.split_user_id = os.environ.get('PLATFORM_SPLIT_USER_ID', '')
        self.split_percentage = 2  # 2% de comissão PADRÃO
        self._cached_token = None
        self._token_expires_at = None
    
    def get_gateway_name(self) -> str:
        """Nome amigável do gateway"""
        return "SyncPay"
    
    def get_gateway_type(self) -> str:
        """Tipo do gateway para roteamento"""
        return "syncpay"
    
    def get_webhook_url(self) -> str:
        """URL do webhook SyncPay"""
        webhook_base = os.environ.get('WEBHOOK_URL', '')
        return f"{webhook_base}/webhook/payment/syncpay"
    
    def _generate_bearer_token(self) -> Optional[str]:
        """
        Gera Bearer Token da SyncPay (válido por 1 hora)
        
        Returns:
            Access token ou None se falhar
        """
        try:
            auth_url = f"{self.base_url}/api/partner/v1/auth-token"
            
            payload = {
                "client_id": self.client_id,
                "client_secret": self.client_secret
            }
            
            headers = {
                'Content-Type': 'application/json'
            }
            
            logger.info(f"🔑 [{self.get_gateway_name()}] Gerando Bearer Token...")
            
            response = requests.post(auth_url, json=payload, headers=headers, timeout=10)
            
            if response.status_code == 200:
                data = response.json()
                access_token = data.get('access_token')
                expires_in = data.get('expires_in', 3600)
                logger.info(f"✅ [{self.get_gateway_name()}] Bearer Token gerado! Válido por {expires_in}s")
                return access_token
            else:
                logger.error(f"❌ [{self.get_gateway_name()}] Erro ao gerar token: Status {response.status_code}")
                logger.error(f"Resposta: {response.text}")
                return None
                
        except Exception as e:
            logger.error(f"❌ [{self.get_gateway_name()}] Erro ao gerar Bearer Token: {e}")
            return None
    
    def generate_pix(
        self, 
        amount: float, 
        description: str, 
        payment_id: str,
        customer_data: Optional[Dict[str, Any]] = None
    ) -> Optional[Dict[str, Any]]:
        """
        Gera PIX via SyncPay
        
        Endpoint: POST /api/partner/v1/cash-in
        """
        try:
            # Validar valor
            if not self.validate_amount(amount):
                logger.error(f"❌ [{self.get_gateway_name()}] Valor inválido: {amount}")
                return None
            
            # 1. Gerar Bearer Token
            bearer_token = self._generate_bearer_token()
            if not bearer_token:
                logger.error(f"❌ [{self.get_gateway_name()}] Falha ao obter Bearer Token")
                return None
            
            # 2. Preparar dados do cliente (formato EXATO da documentação SyncPay)
            if not customer_data:
                customer_data = {}
            
            # ✅ VALIDAÇÃO CRÍTICA: Formato EXATO conforme documentação SyncPay
            # name: string (obrigatório)
            client_name = customer_data.get('name') or (description[:100] if description else "Cliente") or "Cliente"
            
            # cpf: string, EXATAMENTE 11 dígitos (padrão: /^\d{11}$/)
            client_cpf = customer_data.get('cpf') or customer_data.get('document', '')
            # Remover caracteres não numéricos e garantir 11 dígitos
            client_cpf = ''.join(filter(str.isdigit, str(client_cpf)))
            if len(client_cpf) != 11:
                # Gerar CPF válido baseado no customer_user_id ou usar padrão
                if customer_data.get('document'):
                    # Usar últimos 11 dígitos do document
                    doc_str = ''.join(filter(str.isdigit, str(customer_data.get('document', ''))))
                    client_cpf = doc_str[-11:] if len(doc_str) >= 11 else doc_str.zfill(11)
                else:
                    # CPF padrão válido (formato: 00000000000)
                    client_cpf = "00000000000"
            
            # email: string <email> (obrigatório)
            client_email = customer_data.get('email') or "cliente@bot.com"
            if '@' not in client_email:
                client_email = f"user{payment_id}@bot.com"
            
            # phone: string, 10-11 dígitos (padrão: /^\d{10,11}$/)
            client_phone = customer_data.get('phone') or ''
            # Remover caracteres não numéricos
            client_phone = ''.join(filter(str.isdigit, str(client_phone)))
            if len(client_phone) < 10 or len(client_phone) > 11:
                # Gerar phone válido baseado no customer_user_id ou usar padrão
                if customer_data.get('phone') or customer_data.get('document'):
                    phone_source = str(customer_data.get('phone') or customer_data.get('document', ''))
                    phone_digits = ''.join(filter(str.isdigit, phone_source))
                    if len(phone_digits) >= 10:
                        client_phone = phone_digits[-11:] if len(phone_digits) >= 11 else phone_digits[-10:]
                    else:
                        client_phone = "11999999999"
                else:
                    client_phone = "11999999999"
            
            # ✅ Construir objeto client no formato EXATO da documentação
            client_data = {
                "name": client_name,
                "cpf": client_cpf,
                "email": client_email,
                "phone": client_phone
            }
            
            logger.debug(f"🔍 [{self.get_gateway_name()}] Client data formatado: {client_data}")
            
            # 3. Configurar split (formato EXATO da documentação SyncPay)
            # split: array [object], >= 1 items, <= 3 items
            # percentage: integer, >= 1, <= 100 (Porcentagem do amount)
            # user_id: string <uuid> (Client ID Público das chaves em API Keys)
            split_config = []
            if self.split_user_id:
                # ✅ Validar que split_percentage é integer entre 1 e 100
                split_percentage_int = int(self.split_percentage)
                if split_percentage_int < 1 or split_percentage_int > 100:
                    logger.error(f"❌ [{self.get_gateway_name()}] Split percentage inválido: {split_percentage_int} (deve ser entre 1 e 100)")
                    return None
                
                split_config.append({
                    "percentage": split_percentage_int,  # ✅ integer (não float!)
                    "user_id": self.split_user_id  # ✅ string <uuid>
                })
                logger.info(f"💰 [{self.get_gateway_name()}] Split configurado: {split_percentage_int}% para {self.split_user_id[:8]}...")
            else:
                logger.warning(f"⚠️ [{self.get_gateway_name()}] PLATFORM_SPLIT_USER_ID não configurado. Split desabilitado.")
            
            # 4. Criar payload (formato EXATO da documentação SyncPay)
            cashin_url = f"{self.base_url}/api/partner/v1/cash-in"
            
            # ✅ HEADERS OBRIGATÓRIOS conforme documentação
            headers = {
                'Accept': 'application/json',  # ✅ OBRIGATÓRIO pela documentação
                'Authorization': f'Bearer {bearer_token}',
                'Content-Type': 'application/json'
            }
            
            # ✅ Construir payload base (formato EXATO da documentação)
            payload = {
                "amount": float(amount),  # ✅ number <double>, >= 0
                "description": description or None,  # ✅ string | null (opcional)
                "webhook_url": self.get_webhook_url(),  # ✅ string <uri> (opcional)
                "client": client_data  # ✅ object (opcional, mas recomendado)
            }
            
            # ✅ Remover campos None do payload (API pode rejeitar)
            payload = {k: v for k, v in payload.items() if v is not None}
            
            # ✅ Adicionar split apenas se configurado (não enviar array vazio)
            if split_config:
                payload["split"] = split_config
            
            # ✅ Validação crítica: verificar se webhook_url está configurado
            if not payload.get("webhook_url"):
                logger.error(f"❌ [{self.get_gateway_name()}] WEBHOOK_URL não configurado!")
                return None
            
            logger.info(f"📤 [{self.get_gateway_name()}] Criando Cash-In (R$ {amount:.2f})...")
            
            # 5. Fazer requisição
            logger.debug(f"🔍 [{self.get_gateway_name()}] Payload enviado: {payload}")
            response = requests.post(cashin_url, json=payload, headers=headers, timeout=15)
            
            # 6. Processar resposta
            logger.info(f"📥 [{self.get_gateway_name()}] Status: {response.status_code}")
            logger.debug(f"🔍 [{self.get_gateway_name()}] Headers: {dict(response.headers)}")
            logger.debug(f"🔍 [{self.get_gateway_name()}] Resposta completa: {response.text}")
            
            if response.status_code == 200:
                try:
                    data = response.json()
                except ValueError as e:
                    logger.error(f"❌ [{self.get_gateway_name()}] Erro ao parsear JSON: {e}")
                    logger.error(f"Resposta raw: {response.text}")
                    return None
                
                # ✅ FORMATO DA RESPOSTA conforme documentação SyncPay:
                # {
                #     "message": "Cashin request successfully submitted",
                #     "pix_code": "00020126820014br.gov.bcb.pix...",
                #     "identifier": "3df0319d-ecf7-455a-84c4-070aee2779c1"
                # }
                # ✅ NÃO está em wrapper 'data', está direto no root!
                
                # ✅ Extrair campos conforme documentação
                pix_code = data.get('pix_code')
                identifier = data.get('identifier')
                message = data.get('message', '')
                
                # ✅ Log detalhado da resposta
                logger.info(f"🔍 [{self.get_gateway_name()}] Resposta parseada: {data}")
                logger.info(f"🔍 [{self.get_gateway_name()}] Message: {message}")
                logger.info(f"🔍 [{self.get_gateway_name()}] pix_code encontrado: {bool(pix_code)}")
                logger.info(f"🔍 [{self.get_gateway_name()}] identifier encontrado: {bool(identifier)}")
                
                if not pix_code:
                    logger.error(f"❌ [{self.get_gateway_name()}] Resposta não contém pix_code: {data}")
                    logger.error(f"❌ [{self.get_gateway_name()}] Chaves disponíveis: {list(data.keys()) if isinstance(data, dict) else 'N/A'}")
                    return None
                
                if not identifier:
                    logger.error(f"❌ [{self.get_gateway_name()}] Resposta não contém identifier: {data}")
                    return None
                
                logger.info(f"✅ [{self.get_gateway_name()}] PIX gerado com sucesso!")
                logger.info(f"📝 Transaction ID: {identifier}")
                
                # Gerar URL do QR Code
                import urllib.parse
                qr_code_url = f'https://api.qrserver.com/v1/create-qr-code/?size=400x400&data={urllib.parse.quote(pix_code)}'
                
                return {
                    'pix_code': pix_code,
                    'qr_code_url': qr_code_url,
                    'transaction_id': identifier,
                    'payment_id': payment_id,
                    'expires_at': None
                }
            else:
                logger.error(f"❌ [{self.get_gateway_name()}] Erro: Status {response.status_code}")
                try:
                    error_data = response.json()
                    logger.error(f"❌ [{self.get_gateway_name()}] Erro JSON: {error_data}")
                except:
                    logger.error(f"❌ [{self.get_gateway_name()}] Resposta texto: {response.text}")
                return None
                
        except Exception as e:
            logger.error(f"❌ [{self.get_gateway_name()}] Erro ao gerar PIX: {e}")
            import traceback
            traceback.print_exc()
            return None
    
    def process_webhook(self, data: Dict[str, Any]) -> Optional[Dict[str, Any]]:
        """
        Processa webhook SyncPay
        
        Estrutura real do webhook SyncPay:
        {
            "data": {
                "id": "eb4fe1b0-e928-4561-b4ac-7d2fcf712fbf",
                "status": "PAID_OUT",  // ou "CANCELLED", "EXPIRED", etc
                "amount": 33.8,
                "idtransaction": "...",
                "externalreference": "...",
                ...
            }
        }
        """
        try:
            logger.info(f"📥 [{self.get_gateway_name()}] Processando webhook...")
            logger.info(f"🔍 Estrutura recebida: {list(data.keys())}")
            
            # ✅ CORREÇÃO CRÍTICA: SyncPay envia dados dentro de 'data'
            webhook_data = data.get('data', {})
            if not webhook_data:
                # Fallback: tentar usar data diretamente (caso venha sem wrapper)
                webhook_data = data
                logger.warning(f"⚠️ [{self.get_gateway_name()}] Webhook sem wrapper 'data', usando root")
            
            # ✅ Extrair identifier (pode ser 'id' ou 'idtransaction')
            identifier = (
                webhook_data.get('id') or
                webhook_data.get('idtransaction') or
                webhook_data.get('identifier') or
                data.get('identifier') or
                data.get('id')
            )
            
            # ✅ Extrair status (pode vir em uppercase: PAID_OUT, CANCELLED, etc)
            status_raw = webhook_data.get('status', '').upper()
            
            # ✅ Extrair amount (pode vir como float ou int)
            amount = webhook_data.get('amount') or data.get('amount')
            if amount:
                try:
                    amount = float(amount)
                except (ValueError, TypeError):
                    logger.warning(f"⚠️ [{self.get_gateway_name()}] Valor inválido: {amount}")
                    amount = None
            
            # ✅ Extrair externalreference (pode conter payment_id)
            external_reference = webhook_data.get('externalreference') or webhook_data.get('external_reference')
            
            logger.info(f"🔍 [{self.get_gateway_name()}] Dados extraídos:")
            logger.info(f"   identifier: {identifier}")
            logger.info(f"   status_raw: {status_raw}")
            logger.info(f"   amount: {amount}")
            logger.info(f"   external_reference: {external_reference}")
            
            if not identifier:
                logger.error(f"❌ [{self.get_gateway_name()}] Webhook sem identifier")
                logger.error(f"   Estrutura recebida: {data}")
                logger.error(f"   webhook_data: {webhook_data}")
                return None
            
            # ✅ Mapear status da SyncPay (uppercase) para status interno
            # SyncPay usa: PAID_OUT, CANCELLED, EXPIRED, PENDING, etc
            mapped_status = 'pending'
            if status_raw in ['PAID_OUT', 'PAID', 'CONFIRMED', 'APPROVED']:
                mapped_status = 'paid'
            elif status_raw in ['CANCELLED', 'CANCELED', 'EXPIRED', 'FAILED']:
                mapped_status = 'failed'
            elif status_raw in ['PENDING', 'WAITING', 'PROCESSING']:
                mapped_status = 'pending'
            else:
                logger.warning(f"⚠️ [{self.get_gateway_name()}] Status desconhecido: {status_raw}, usando 'pending'")
            
            logger.info(f"✅ [{self.get_gateway_name()}] Webhook processado:")
            logger.info(f"   Identifier: {identifier}")
            logger.info(f"   Status: {status_raw} → {mapped_status}")
            logger.info(f"   Amount: R$ {amount:.2f}" if amount else "   Amount: N/A")
            logger.info(f"   External Reference: {external_reference}")
            
            return {
                'payment_id': identifier,  # Usar identifier como payment_id
                'status': mapped_status,
                'amount': amount,
                'gateway_transaction_id': identifier,  # ID da transação no gateway
                'external_reference': external_reference  # Referência externa (pode conter payment_id)
            }
            
        except Exception as e:
            logger.error(f"❌ [{self.get_gateway_name()}] Erro ao processar webhook: {e}")
            import traceback
            logger.error(f"📋 Traceback: {traceback.format_exc()}")
            logger.error(f"📋 Dados recebidos: {data}")
            return None
    
    def verify_credentials(self) -> bool:
        """
        Verifica se credenciais SyncPay são válidas
        
        Returns:
            True se conseguir gerar Bearer Token, False caso contrário
        """
        try:
            token = self._generate_bearer_token()
            return token is not None
        except Exception as e:
            logger.error(f"❌ [{self.get_gateway_name()}] Erro ao verificar credenciais: {e}")
            return False
    
    def get_payment_status(self, transaction_id: str) -> Optional[Dict[str, Any]]:
        """
        Consulta status de pagamento na SyncPay
        
        Nota: Endpoint de consulta não está documentado na SyncPay.
        Implementar quando disponível.
        """
        logger.warning(f"⚠️ [{self.get_gateway_name()}] Consulta de status não implementada (endpoint não documentado)")
        return None


