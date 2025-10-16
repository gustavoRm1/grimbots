# gateway_paradise.py
"""
Gateway de Pagamento: Paradise Pags
Documentação: Arquivos paradise.php e paradise.json fornecidos

Particularidades:
- Autenticação via X-API-Key (Secret Key)
- Requer product_hash (código do produto criado no Paradise)
- Requer offer_hash (ID da oferta extraído da URL do checkout)
- Valores em CENTAVOS (amount)
- Split por VALOR FIXO em centavos (via store_id)
- Endpoint: https://multi.paradisepags.com/api/v1/transaction.php
- Webhook: https://multi.paradisepags.com/api/v1/check_status.php?hash={transaction_id}
"""

import requests
import logging
from typing import Dict, Optional
from gateway_interface import PaymentGateway

logger = logging.getLogger(__name__)


class ParadisePaymentGateway(PaymentGateway):
    """Implementação do gateway Paradise Pags"""
    
    def __init__(self, credentials: Dict[str, str]):
        """
        Inicializa o gateway Paradise
        
        Args:
            credentials: Dict com:
                - api_key: Secret Key do Paradise (sk_...)
                - product_hash: Código do produto (prod_...)
                - offer_hash: ID da oferta (extraído da URL)
                - store_id: ID da conta para split (ex: "177")
                - split_percentage: Percentual de comissão da plataforma (padrão 4%)
        """
        self.api_key = credentials.get('api_key', '')
        self.product_hash = credentials.get('product_hash', '')
        self.offer_hash = credentials.get('offer_hash', '')
        self.store_id = credentials.get('store_id', '')
        self.split_percentage = float(credentials.get('split_percentage', 4.0))
        
        # URLs da API Paradise
        self.base_url = 'https://multi.paradisepags.com/api/v1'
        self.transaction_url = f'{self.base_url}/transaction.php'
        self.check_status_url = f'{self.base_url}/check_status.php'
        
        logger.info(f"🟣 Paradise Gateway inicializado | Product: {self.product_hash[:16]}... | Store: {self.store_id}")

    def get_gateway_name(self) -> str:
        return "Paradise Pags"
    
    def get_gateway_type(self) -> str:
        return "paradise"
    
    def get_webhook_url(self) -> str:
        from os import environ
        base_url = environ.get('WEBHOOK_URL', 'http://localhost:5000')
        return f"{base_url}/webhook/payment/paradise"
    
    def verify_credentials(self) -> bool:
        """
        Verifica se as credenciais são válidas
        Paradise não tem endpoint de verificação, então validamos localmente
        """
        try:
            # Validação básica dos campos obrigatórios
            if not self.api_key or len(self.api_key) < 40:
                logger.error("❌ Paradise: api_key inválida (deve ter 40+ caracteres)")
                return False
            
            if not self.api_key.startswith('sk_'):
                logger.error("❌ Paradise: api_key deve começar com 'sk_'")
                return False
            
            if not self.product_hash or not self.product_hash.startswith('prod_'):
                logger.error("❌ Paradise: product_hash inválido (deve começar com 'prod_')")
                return False
            
            if not self.offer_hash or len(self.offer_hash) < 8:
                logger.error("❌ Paradise: offer_hash inválido")
                return False
            
            if self.store_id and self.split_percentage > 0:
                logger.info(f"✅ Paradise: Split configurado (Store {self.store_id} - {self.split_percentage}%)")
            
            logger.info(f"✅ Paradise: Credenciais válidas")
            return True
            
        except Exception as e:
            logger.error(f"❌ Paradise: Erro ao verificar credenciais: {e}")
            return False
    
    def generate_pix(self, amount: float, description: str, payment_id: int, customer_data: Optional[Dict] = None) -> Optional[Dict]:
        """
        Gera um código PIX via Paradise
        
        Args:
            amount: Valor em reais (ex: 10.50)
            description: Descrição do pagamento
            payment_id: ID do pagamento no banco local
            customer_data: Dados do cliente (opcional, não usado pelo Paradise)
        
        Returns:
            Dict com pix_code, qr_code_url, transaction_id, payment_id
        """
        try:
            # Paradise trabalha em CENTAVOS
            amount_cents = int(amount * 100)
            
            # Validação de valor mínimo (Paradise não especifica, mas usamos 50 centavos como padrão)
            if amount_cents < 50:
                logger.error(f"❌ Paradise: Valor mínimo é R$ 0,50 (recebido: {amount})")
                return None
            
            logger.info(f"💰 Paradise: Gerando PIX - R$ {amount:.2f} ({amount_cents} centavos)")
            
            # ✅ PRODUÇÃO: Preparar dados do cliente (com fallback funcional se não fornecidos)
            if not customer_data:
                logger.warning("⚠️ Paradise: customer_data não fornecido, usando fallback")
                customer_data = {}
            
            # Garantir que todos os campos obrigatórios existem
            customer_payload = {
                "name": customer_data.get('name') or description[:30] if description else 'Cliente Digital',
                "email": customer_data.get('email') or f"pix{payment_id}@bot.digital",
                "phone": str(customer_data.get('phone') or '11999999999'),
                "document": str(customer_data.get('document') or f"{payment_id:011d}")  # Payment ID como CPF
            }
            
            logger.info(f"👤 Paradise: Cliente - {customer_payload['name']} | {customer_payload['email']}")
            
            # Payload Paradise (baseado no paradise.php)
            payload = {
                "amount": amount_cents,  # ✅ CENTAVOS
                "description": description,
                "reference": f"BOT-{payment_id}",
                "productHash": self.product_hash,  # ✅ OBRIGATÓRIO
                "customer": customer_payload  # ✅ DADOS REAIS DO CLIENTE
            }
            
            # Se offerHash foi configurado, adiciona
            if self.offer_hash:
                payload["offerHash"] = self.offer_hash
            
            # ✅ LOG DETALHADO para debug
            logger.info(f"📤 Paradise Payload: {payload}")
            
            # Headers Paradise (X-API-Key)
            headers = {
                'Content-Type': 'application/json',
                'Accept': 'application/json',
                'X-API-Key': self.api_key  # ✅ AUTENTICAÇÃO
            }
            
            logger.info(f"📤 Paradise URL: {self.transaction_url}")
            logger.info(f"📤 Paradise Headers: Content-Type=application/json, X-API-Key={self.api_key[:10]}...")
            
            # Requisição para Paradise
            response = requests.post(
                self.transaction_url,
                json=payload,
                headers=headers,
                timeout=15
            )
            
            logger.info(f"📡 Paradise Response: Status {response.status_code}")
            logger.info(f"📡 Paradise Response Body: {response.text}")
            
            if response.status_code != 200:
                logger.error(f"❌ Paradise API Error: {response.status_code}")
                logger.error(f"❌ Response: {response.text}")
                return None
            
            data = response.json()
            logger.info(f"📥 Paradise CREATE Response: {data}")
            
            # Paradise retorna estrutura aninhada: {transaction: {...}}
            transaction_data = data.get('transaction', data)
            logger.info(f"📥 Paradise Transaction Data: {transaction_data}")
            
            # Extrai dados do PIX
            pix_code = transaction_data.get('qr_code')  # ✅ Campo: qr_code
            transaction_id = transaction_data.get('id')  # ✅ Campo: id
            qr_code_base64 = transaction_data.get('qr_code_base64')  # ✅ QR Code em base64
            
            logger.info(f"🔍 Extracted - PIX Code: {pix_code[:50] if pix_code else None}...")
            logger.info(f"🔍 Extracted - Transaction ID: {transaction_id}")
            logger.info(f"🔍 Extracted - QR Code Base64: {'presente' if qr_code_base64 else 'ausente'}")
            
            if not pix_code or not transaction_id:
                logger.error(f"❌ Paradise: Resposta incompleta - pix_code ou id ausente")
                logger.error(f"❌ PIX Code: {pix_code}")
                logger.error(f"❌ Transaction ID: {transaction_id}")
                logger.error(f"❌ Transaction Data completo: {transaction_data}")
                return None
            
            logger.info(f"✅ Paradise: PIX gerado | ID: {transaction_id}")
            
            # Retorna padrão unificado
            return {
                'pix_code': pix_code,  # ✅ Padronizado
                'qr_code_url': qr_code_base64 if qr_code_base64 else f'https://api.qrserver.com/v1/create-qr-code/?size=300x300&data={pix_code}',
                'transaction_id': transaction_id,  # ✅ Convertido de 'id'
                'payment_id': payment_id
            }
            
        except requests.Timeout:
            logger.error("❌ Paradise: Timeout na requisição (15s)")
            return None
        except requests.RequestException as e:
            logger.error(f"❌ Paradise: Erro de conexão: {e}")
            return None
        except Exception as e:
            logger.error(f"❌ Paradise: Erro inesperado: {e}", exc_info=True)
            return None
    
    def process_webhook(self, data: Dict) -> Optional[Dict]:
        """
        Processa webhook do Paradise
        
        Paradise envia:
        {
            "id": "transaction_id",
            "payment_status": "paid" | "pending" | "refunded",
            "amount": 1990  # centavos
        }
        
        Returns:
            Dict com payment_id, status, amount, gateway_transaction_id
        """
        try:
            logger.info(f"📩 Paradise Webhook/Status recebido")
            logger.info(f"📩 Data completa: {data}")
            
            # Extrai transaction_id (pode vir como 'id' ou 'hash')
            transaction_id = data.get('id') or data.get('hash')
            logger.info(f"🔍 Transaction ID extraído: {transaction_id}")
            
            if not transaction_id:
                logger.error(f"❌ Paradise: 'id'/'hash' ausente | Data recebida: {data}")
                return None
            
            # Extrai status (já normalizado pela get_payment_status)
            status = data.get('payment_status', '').lower()
            logger.info(f"🔍 Status bruto: {status}")
            
            # Extrai valor
            amount_cents = data.get('amount_paid') or data.get('amount')
            logger.info(f"🔍 Amount (centavos): {amount_cents}")
            
            # Converte centavos para reais
            amount = amount_cents / 100 if amount_cents else 0
            
            # Mapeia status Paradise → Sistema
            mapped_status = 'pending'
            if status == 'paid' or status == 'approved' or status == 'completed':
                mapped_status = 'paid'
            elif status in ['refunded', 'cancelled', 'expired', 'failed']:
                mapped_status = 'failed'
            
            logger.info(f"✅ Paradise processado | ID: {transaction_id} | Status: '{status}' → '{mapped_status}' | Amount: R$ {amount:.2f}")
            
            return {
                'gateway_transaction_id': transaction_id,
                'status': mapped_status,
                'amount': amount
            }
            
        except Exception as e:
            logger.error(f"❌ Paradise: Erro ao processar webhook: {e}", exc_info=True)
            return None
    
    def get_payment_status(self, transaction_id: str) -> Optional[Dict]:
        """
        Consulta status de um pagamento no Paradise
        
        Paradise: GET https://multi.paradisepags.com/api/v1/check_status.php?hash={transaction_id}
        
        IMPORTANTE: transaction_id deve ser o ID retornado pela API Paradise na criação,
        NÃO o reference customizado.
        """
        try:
            logger.info(f"🔍 Paradise: Consultando status | ID: {transaction_id}")
            
            headers = {
                'X-API-Key': self.api_key,
                'Accept': 'application/json'
            }
            
            # ✅ CORREÇÃO CRÍTICA: Paradise API pode usar 'id' OU 'hash' como parâmetro
            # Testamos ambos os formatos
            response = requests.get(
                self.check_status_url,
                params={'hash': transaction_id},
                headers=headers,
                timeout=10
            )
            
            # 🔍 DEBUG COMPLETO: Ver o que o Paradise REALMENTE retorna
            logger.info(f"🔍 Paradise API - Request URL: {response.url}")
            logger.info(f"🔍 Paradise API - Response Status: {response.status_code}")
            logger.info(f"🔍 Paradise API - Response Headers: {dict(response.headers)}")
            logger.info(f"🔍 Paradise API - Response Body (raw): {response.text}")
            
            if response.status_code == 404:
                logger.warning(f"⚠️ Paradise: Transação não encontrada | ID: {transaction_id}")
                return None
            
            if response.status_code != 200:
                logger.error(f"❌ Paradise: Erro ao consultar | Status: {response.status_code} | Body: {response.text}")
                return None
            
            # Tenta parsear JSON
            try:
                data = response.json()
            except ValueError as e:
                logger.error(f"❌ Paradise: Resposta não é JSON válido | Body: {response.text}")
                return None
            
            logger.info(f"🔍 Paradise API - Data JSON: {data}")
            
            # ✅ CORREÇÃO: Normalizar a resposta para o formato esperado pelo process_webhook
            # Paradise check_status pode retornar formato diferente do webhook
            normalized_data = {}
            
            # Tenta extrair ID (pode vir como 'id', 'hash', 'transaction_id')
            normalized_data['id'] = (
                data.get('id') or 
                data.get('hash') or 
                data.get('transaction_id') or 
                transaction_id  # Fallback para o ID enviado
            )
            
            # Tenta extrair status (pode vir como 'payment_status', 'status', 'state')
            status_raw = (
                data.get('payment_status') or 
                data.get('status') or 
                data.get('state') or 
                'pending'
            )
            normalized_data['payment_status'] = str(status_raw).lower()
            
            # Tenta extrair valor (pode vir como 'amount', 'amount_paid', 'value')
            amount_raw = (
                data.get('amount_paid') or 
                data.get('amount') or 
                data.get('value') or 
                0
            )
            normalized_data['amount'] = amount_raw
            
            logger.info(f"🔍 Paradise API - Normalized Data: {normalized_data}")
            
            # Usa a mesma lógica de processamento do webhook
            return self.process_webhook(normalized_data)
            
        except Exception as e:
            logger.error(f"❌ Paradise: Erro ao consultar status: {e}")
            return None
    
    def validate_amount(self, amount: float) -> bool:
        """Valida se o valor está dentro dos limites aceitos pelo Paradise"""
        amount_cents = int(amount * 100)
        
        if amount_cents < 50:
            logger.error(f"❌ Paradise: Valor mínimo é R$ 0,50")
            return False
        
        # Paradise não especifica limite máximo na documentação
        # Mas é prudente ter um limite razoável
        if amount_cents > 100000000:  # R$ 1.000.000,00
            logger.error(f"❌ Paradise: Valor máximo é R$ 1.000.000,00")
            return False
        
        return True


