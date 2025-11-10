"""
Gateway Pushyn - Implementação Isolada
Documentação: https://api.pushinpay.com.br/docs
"""

import os
import requests
import logging
from typing import Dict, Any, Optional, List
from gateway_interface import PaymentGateway

logger = logging.getLogger(__name__)


class PushynGateway(PaymentGateway):
    """
    Implementação do gateway Pushyn
    
    Características:
    - Autenticação via Bearer Token (API Key)
    - Valores em centavos
    - Split payment por valor fixo
    - Webhook para confirmação de pagamento
    - Limite mínimo: 50 centavos
    - Limite split: 50% do valor total
    """
    
    def __init__(self, api_key: str):
        """
        Inicializa gateway Pushyn
        
        Args:
            api_key: API Key (Token) da Pushyn
        """
        self.api_key = api_key
        self.base_url = os.environ.get('PUSHYN_API_URL', 'https://api.pushinpay.com.br')
        # ⚠️ SPLIT DESABILITADO - Account ID fornecido não existe no PushynPay
        # Configure o Account ID correto no .env: PUSHYN_SPLIT_ACCOUNT_ID
        self.split_account_id = os.environ.get('PUSHYN_SPLIT_ACCOUNT_ID', None)
        self.split_percentage = 2  # 2% (quando habilitado)
    
    def get_gateway_name(self) -> str:
        """Nome amigável do gateway"""
        return "PushynPay"
    
    def get_gateway_type(self) -> str:
        """Tipo do gateway para roteamento"""
        return "pushynpay"
    
    def get_webhook_url(self) -> str:
        """URL do webhook Pushyn"""
        webhook_base = os.environ.get('WEBHOOK_URL', '')
        return f"{webhook_base}/webhook/payment/pushynpay"
    
    def generate_pix(
        self, 
        amount: float, 
        description: str, 
        payment_id: str,
        customer_data: Optional[Dict[str, Any]] = None
    ) -> Optional[Dict[str, Any]]:
        """
        Gera PIX via Pushyn
        
        Endpoint: POST /api/pix/cashIn
        
        Nota: Pushyn trabalha com valores em CENTAVOS
        """
        try:
            # Validar valor
            if not self.validate_amount(amount):
                logger.error(f"❌ [{self.get_gateway_name()}] Valor inválido: {amount}")
                return None
            
            # 1. Converter valor para centavos
            value_cents = int(amount * 100)
            
            # 2. Validar valor mínimo (50 centavos = R$ 0.50)
            if value_cents < 50:
                logger.error(f"❌ [{self.get_gateway_name()}] Valor muito baixo: {value_cents} centavos (mínimo: 50)")
                return None
            
            # 3. Configurar split rules
            split_rules = []
            if self.split_account_id:
                # Calcular valor do split em centavos
                split_value_cents = int(value_cents * (self.split_percentage / 100))
                
                # Validações do split
                # a) Mínimo de 1 centavo
                if split_value_cents < 1:
                    split_value_cents = 1
                
                # b) Máximo de 50% (limite Pushyn)
                max_split_cents = int(value_cents * 0.5)
                if split_value_cents > max_split_cents:
                    logger.warning(f"⚠️ [{self.get_gateway_name()}] Split de {split_value_cents} centavos ultrapassa 50%. Ajustando para {max_split_cents}")
                    split_value_cents = max_split_cents
                
                # c) Garantir que sobra pelo menos 1 centavo para o vendedor
                seller_value_cents = value_cents - split_value_cents
                if seller_value_cents < 1:
                    logger.warning(f"⚠️ [{self.get_gateway_name()}] Split deixaria menos de 1 centavo para vendedor. Ajustando...")
                    split_value_cents = value_cents - 1
                
                split_rules.append({
                    "value": split_value_cents,
                    "account_id": self.split_account_id
                })
                
                logger.info(f"💰 [{self.get_gateway_name()}] Split configurado: {split_value_cents} centavos ({self.split_percentage}%) para conta {self.split_account_id}")
            else:
                logger.warning(f"⚠️ [{self.get_gateway_name()}] PUSHYN_SPLIT_ACCOUNT_ID não configurado. Split desabilitado.")
            
            # 4. Criar payload
            cashin_url = f"{self.base_url}/api/pix/cashIn"
            
            headers = {
                'Authorization': f'Bearer {self.api_key}',
                'Accept': 'application/json',
                'Content-Type': 'application/json'
            }
            
            payload = {
                "value": value_cents,
                "webhook_url": self.get_webhook_url(),
                "split_rules": split_rules
            }
            
            logger.info(f"📤 [{self.get_gateway_name()}] Criando Cash-In (R$ {amount:.2f} = {value_cents} centavos)...")
            
            # 5. Fazer requisição
            response = requests.post(cashin_url, json=payload, headers=headers, timeout=15)
            
            # 6. Processar resposta
            if response.status_code == 200:
                data = response.json()
                pix_code = data.get('qr_code')  # Pushyn retorna como 'qr_code'
                transaction_id = data.get('id')
                qr_code_base64 = data.get('qr_code_base64')
                
                if not pix_code:
                    logger.error(f"❌ [{self.get_gateway_name()}] Resposta não contém qr_code: {data}")
                    return None
                
                logger.info(f"✅ [{self.get_gateway_name()}] PIX gerado com sucesso!")
                logger.info(f"📝 Transaction ID: {transaction_id}")
                
                # Gerar URL do QR Code
                # Pushyn já retorna base64, mas também gerar URL como fallback
                qr_code_url = qr_code_base64
                if not qr_code_url:
                    import urllib.parse
                    qr_code_url = f'https://api.qrserver.com/v1/create-qr-code/?size=400x400&data={urllib.parse.quote(pix_code)}'
                
                return {
                    'pix_code': pix_code,
                    'qr_code_url': qr_code_url,
                    'qr_code_base64': qr_code_base64,
                    'transaction_id': transaction_id,
                    'payment_id': payment_id,
                    'expires_at': None  # Pushyn não retorna expiração
                }
            else:
                error_data = response.json() if response.text else {}
                logger.error(f"❌ [{self.get_gateway_name()}] Erro: Status {response.status_code}")
                logger.error(f"Resposta: {error_data}")
                return None
                
        except Exception as e:
            logger.error(f"❌ [{self.get_gateway_name()}] Erro ao gerar PIX: {e}")
            import traceback
            traceback.print_exc()
            return None
    
    def process_webhook(self, data: Dict[str, Any]) -> Optional[Dict[str, Any]]:
        """
        Processa webhook Pushyn
        
        Campos esperados:
        - id: ID da transação
        - status: Status (created, paid, expired)
        - value: Valor em centavos
        - payer_name: Nome do pagador (após pagamento)
        - payer_national_registration: CPF/CNPJ (após pagamento)
        - end_to_end_id: ID do Banco Central (após pagamento)
        """
        try:
            payload = data or {}
            identifier = payload.get('id')

            if not identifier:
                logger.error(f"❌ [{self.get_gateway_name()}] Webhook sem ID")
                return None

            normalized_identifier = str(identifier).strip()
            identifier_lower = normalized_identifier.replace('-', '').replace('_', '').lower()

            # Normalizar status e coletar todos os campos relacionados
            raw_statuses: List[str] = []

            def _normalize_status(value) -> Optional[str]:
                if value is None:
                    return None
                status_str = str(value).strip().lower()
                if status_str:
                    raw_statuses.append(status_str)
                    return status_str
                return None

            primary_status = _normalize_status(payload.get('status'))
            for key in (
                'status_description', 'status_detail', 'status_label', 'status_name',
                'transaction_status', 'payment_status', 'paymentStatus', 'statusHistory',
            ):
                alt_value = payload.get(key)
                if isinstance(alt_value, dict):
                    for inner_value in alt_value.values():
                        _normalize_status(inner_value)
                elif isinstance(alt_value, list):
                    for inner_value in alt_value:
                        _normalize_status(inner_value)
                else:
                    _normalize_status(alt_value)

            # Valores monetários
            value_cents = payload.get('value', 0)
            try:
                value_cents = int(value_cents) if value_cents else 0
            except (ValueError, TypeError):
                logger.warning(f"⚠️ [{self.get_gateway_name()}] Valor inválido: {value_cents}, usando 0")
                value_cents = 0
            amount = value_cents / 100 if value_cents else 0.0

            # Indicadores de pagamento
            payer_name = payload.get('payer_name') or payload.get('customer_name')
            payer_cpf = payload.get('payer_national_registration') or payload.get('payer_document')
            end_to_end = payload.get('end_to_end_id') or payload.get('end_to_end') or payload.get('endToEndId')

            paid_timestamps = []
            for key in ('paid_at', 'confirmed_at', 'completed_at', 'settled_at', 'paidAt', 'completedAt'):
                if payload.get(key):
                    paid_timestamps.append(payload.get(key))

            paid_amount_fields = 0.0
            for key in ('paid_value', 'value_paid', 'paidAmount', 'paid_amount', 'received_value'):
                paid_amount_fields = max(
                    paid_amount_fields,
                    float(payload.get(key) or 0) if payload.get(key) not in (None, '') else 0.0
                )

            truthy_values = {'true', '1', 'yes', 'sim', 'paid'}
            has_paid_flag = str(payload.get('is_paid', '')).strip().lower() in truthy_values

            paid_keywords = {
                'paid', 'completed', 'concluded', 'confirmed', 'success', 'succeeded',
                'received', 'settled', 'finished', 'done', 'approved', 'captured',
                'pagamento_confirmado', 'pagamento aprovado', 'pagamento_concluido',
                'payment_confirmed', 'payment_completed'
            }
            failed_keywords = {
                'failed', 'cancelled', 'canceled', 'refused', 'rejected', 'expired',
                'chargeback', 'charged_back', 'reversed', 'denied'
            }

            is_paid_keyword = any(status in paid_keywords for status in raw_statuses)
            is_failed_keyword = any(status in failed_keywords for status in raw_statuses)

            if not is_paid_keyword:
                paid_substrings = ['confirm', 'aprov', 'conclu', 'receb', 'settled', 'success', 'feito']
                for status in raw_statuses:
                    if status and any(substr in status for substr in paid_substrings):
                        is_paid_keyword = True
                        break

            has_paid_indicator = any([
                is_paid_keyword,
                has_paid_flag,
                bool(end_to_end),
                bool(payer_name),
                paid_amount_fields > 0,
                bool(paid_timestamps),
            ])

            if is_failed_keyword:
                mapped_status = 'failed'
                status_reason = 'keyword_failed'
            elif has_paid_indicator:
                mapped_status = 'paid'
                status_reason = 'paid_indicator'
            else:
                mapped_status = 'pending'
                status_reason = 'default_pending'

            logger.info(
                f"📥 [{self.get_gateway_name()}] Webhook recebido: {identifier} - "
                f"Status bruto: {primary_status or 'n/a'} → {mapped_status} - Valor: R$ {amount:.2f} "
                f"| Indicador: {status_reason}"
            )

            if mapped_status == 'paid':
                logger.debug(f"🧾 [{self.get_gateway_name()}] Dados de confirmação: end_to_end={end_to_end}, "
                             f"payer={payer_name}, paid_value={paid_amount_fields}, timestamps={paid_timestamps}")

            if payer_name:
                logger.info(f"👤 Pagador: {payer_name} (CPF: {payer_cpf})")
            if end_to_end:
                logger.info(f"🔑 End-to-End ID: {end_to_end}")

            return {
                'payment_id': normalized_identifier,
                'status': mapped_status,
                'amount': amount,
                'gateway_transaction_id': identifier_lower,
                'payer_name': payer_name,
                'payer_document': payer_cpf,
                'end_to_end_id': end_to_end,
                'raw_status': primary_status,
                'raw_statuses': raw_statuses,
                'raw_data': payload,
                'status_reason': status_reason,
                'paid_value': paid_amount_fields,
                'paid_timestamps': paid_timestamps,
            }

        except Exception as e:
            logger.error(f"❌ [{self.get_gateway_name()}] Erro ao processar webhook: {e}", exc_info=True)
            return None
    
    def verify_credentials(self) -> bool:
        """
        Verifica se credenciais Pushyn são válidas
        
        Validação básica: API Key deve ter mais de 20 caracteres
        """
        try:
            if not self.api_key:
                return False
            
            # Validação simples de formato
            if len(self.api_key) < 20:
                logger.error(f"❌ [{self.get_gateway_name()}] API Key muito curta")
                return False
            
            # Tentativa de teste real seria fazer uma requisição à API
            # mas evitamos para não gerar transação de teste
            logger.info(f"✅ [{self.get_gateway_name()}] API Key parece válida (formato correto)")
            return True
            
        except Exception as e:
            logger.error(f"❌ [{self.get_gateway_name()}] Erro ao verificar credenciais: {e}")
            return False
    
    def get_payment_status(self, transaction_id: str) -> Optional[Dict[str, Any]]:
        """
        Consulta status de pagamento na Pushyn
        
        Endpoint: GET /api/transactions/{transaction_id}
        """
        try:
            query_url = f"{self.base_url}/api/transactions/{transaction_id}"
            
            headers = {
                'Authorization': f'Bearer {self.api_key}',
                'Accept': 'application/json',
                'Content-Type': 'application/json'
            }
            
            logger.info(f"🔍 [{self.get_gateway_name()}] Consultando status: {transaction_id}")
            
            response = requests.get(query_url, headers=headers, timeout=10)
            
            if response.status_code == 200:
                data = response.json()
                # Processar usando a mesma lógica do webhook
                return self.process_webhook(data)
            elif response.status_code == 404:
                logger.warning(f"⚠️ [{self.get_gateway_name()}] Transação não encontrada: {transaction_id}")
                return None
            else:
                logger.error(f"❌ [{self.get_gateway_name()}] Erro ao consultar: Status {response.status_code}")
                return None
                
        except Exception as e:
            logger.error(f"❌ [{self.get_gateway_name()}] Erro ao consultar status: {e}")
            return None


