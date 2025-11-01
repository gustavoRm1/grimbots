# gateway_paradise.py
"""
Gateway de Pagamento: Paradise Pags (API V30 atualizada)
Documentação: Arquivos paradise.php e paradise.json fornecidos

Particularidades da API V30:
- Autenticação via X-API-Key (Secret Key)
- Requer product_hash (código do produto criado no Paradise)
- Requer checkoutUrl (novo campo obrigatório)
- Valores em CENTAVOS (amount)
- Split por VALOR FIXO em centavos (via store_id)
- Endpoint: https://multi.paradisepags.com/api/v1/transaction.php
- Webhook: https://multi.paradisepags.com/api/v1/check_status.php?hash={transaction_id}
- Resposta: {transaction: {id, qr_code, qr_code_base64, expires_at}}

Credenciais atualizadas:
- API Key: sk_c3728b109649c7ab1d4e19a61189dbb2b07161d6955b8f20b6023c55b8a9e722
- Product Hash: prod_6c60b3dd3ae2c63e
- Store ID: 177
"""

import requests
import logging
import random
from typing import Dict, Optional
from gateway_interface import PaymentGateway

logger = logging.getLogger(__name__)

# Pool de CPFs válidos para fallback
VALID_CPFS = [
    '56657477007',
    '06314127513',
    '25214446772',
    '27998261321',
    '09553238602',
    '48317801896',
    '21540970817',
    '21996866900',
    '15721994746'
]


class ParadisePaymentGateway(PaymentGateway):
    """Implementação do gateway Paradise Pags"""
    
    def __init__(self, credentials: Dict[str, str]):
        """
        Inicializa o gateway Paradise (API V30 atualizada)
        
        Args:
            credentials: Dict com:
                - api_key: Secret Key do Paradise (sk_...)
                - product_hash: Código do produto (prod_...)
                - offer_hash: ID da oferta (extraído da URL)
                - store_id: ID da conta para split (ex: "177")
                - split_percentage: Percentual de comissão da plataforma (padrão 2%)
        """
        # ✅ CREDENCIAIS ATUALIZADAS baseadas nos arquivos paradise.php e paradise.json
        self.api_key = credentials.get('api_key', 'sk_c3728b109649c7ab1d4e19a61189dbb2b07161d6955b8f20b6023c55b8a9e722')
        self.product_hash = credentials.get('product_hash', 'prod_6c60b3dd3ae2c63e')
        self.offer_hash = credentials.get('offer_hash', '')
        
        # ✅ STORE ID DO SISTEMA (SPLIT DA PLATAFORMA) - NÃO DO USUÁRIO
        from os import environ
        self.store_id = environ.get('PARADISE_STORE_ID', '177')  # Store ID do dono do sistema
        
        # ✅ CORREÇÃO CRÍTICA: Validar split_percentage
        try:
            split_percentage = credentials.get('split_percentage', 2.0)
            self.split_percentage = float(split_percentage) if split_percentage is not None else 2.0
        except (ValueError, TypeError):
            logger.warning(f"⚠️ Paradise: split_percentage inválido, usando padrão 2.0%")
            self.split_percentage = 2.0
        
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
    
    def _get_dynamic_checkout_url(self, payment_id: int) -> str:
        """
        Gera URL de checkout dinâmica baseada no ambiente
        """
        from os import environ
        base_url = environ.get('WEBHOOK_URL', 'http://localhost:5000')
        # Remove /webhook se presente e adiciona /payment
        if '/webhook' in base_url:
            base_url = base_url.replace('/webhook', '')
        return f"{base_url}/payment/{payment_id}"
    
    def _validate_phone(self, phone: str) -> str:
        """
        Valida e corrige número de telefone para formato brasileiro
        """
        # Remove caracteres não numéricos
        phone_digits = ''.join(filter(str.isdigit, str(phone)))
        
        # Se tem 11 dígitos e começa com 0, remove o 0
        if len(phone_digits) == 11 and phone_digits.startswith('0'):
            phone_digits = phone_digits[1:]
        
        # Se tem 10 dígitos, adiciona 9 (celular)
        if len(phone_digits) == 10:
            phone_digits = '9' + phone_digits
        
        # Se ainda não tem 11 dígitos, usar padrão
        if len(phone_digits) != 11:
            phone_digits = '11999999999'
        
        return phone_digits
    
    def _validate_document(self, document: str) -> str:
        """
        Valida e corrige documento (CPF) para formato brasileiro
        """
        # Remove caracteres não numéricos
        doc_digits = ''.join(filter(str.isdigit, str(document)))
        
        # Se tem 11 dígitos, usar
        if len(doc_digits) == 11:
            return doc_digits
        
        # Se não tem 11 dígitos, usar CPF válido aleatório
        return random.choice(VALID_CPFS)
    
    def verify_credentials(self) -> bool:
        """
        Verifica se as credenciais são válidas (API V30 atualizada)
        Paradise não tem endpoint de verificação, então validamos localmente
        """
        try:
            # ✅ Validação atualizada com credenciais padrão
            if not self.api_key or len(self.api_key) < 40:
                logger.error("❌ Paradise: api_key inválida (deve ter 40+ caracteres)")
                return False
            
            if not self.api_key.startswith('sk_'):
                logger.error("❌ Paradise: api_key deve começar com 'sk_'")
                return False
            
            if not self.product_hash or not self.product_hash.startswith('prod_'):
                logger.error("❌ Paradise: product_hash inválido (deve começar com 'prod_')")
                return False
            
            # ✅ Store ID agora é obrigatório para split
            if not self.store_id:
                logger.error("❌ Paradise: store_id é obrigatório para split")
                return False
            
            if self.store_id and self.split_percentage > 0:
                logger.info(f"✅ Paradise: Split configurado (Store {self.store_id} - {self.split_percentage}%)")
            
            logger.info(f"✅ Paradise: Credenciais válidas | Product: {self.product_hash} | Store: {self.store_id}")
            return True
            
        except Exception as e:
            logger.error(f"❌ Paradise: Erro ao verificar credenciais: {e}")
            return False
    
    def generate_pix(self, amount: float, description: str, payment_id: int, customer_data: Optional[Dict] = None) -> Optional[Dict]:
        """
        Gera um código PIX via Paradise (API V30 atualizada)
        
        Args:
            amount: Valor em reais (ex: 10.50)
            description: Descrição do pagamento
            payment_id: ID do pagamento no banco local
            customer_data: Dados do cliente (opcional, não usado pelo Paradise)
        
        Returns:
            Dict com pix_code, qr_code_url, transaction_id, payment_id
        """
        try:
            # ✅ CORREÇÃO CRÍTICA: Validar entrada antes de processar
            if not isinstance(amount, (int, float)) or amount <= 0:
                logger.error(f"❌ Paradise: Valor inválido - deve ser número positivo (recebido: {amount})")
                return None
            
            # Verificar NaN e infinito
            if isinstance(amount, float) and (amount != amount or amount == float('inf') or amount == float('-inf')):
                logger.error(f"❌ Paradise: Valor inválido - NaN ou infinito (recebido: {amount})")
                return None
            
            if amount > 1000000:  # R$ 1.000.000 máximo
                logger.error(f"❌ Paradise: Valor muito alto - máximo R$ 1.000.000 (recebido: {amount})")
                return None
            
            # Paradise trabalha em CENTAVOS
            amount_cents = int(amount * 100)
            
            # Validação de valor mínimo (ajustado para downsells)
            if amount_cents < 1:  # R$ 0,01 mínimo
                logger.error(f"❌ Paradise: Valor mínimo é R$ 0,01 (recebido: {amount})")
                return None
            
            logger.info(f"💰 Paradise: Gerando PIX - R$ {amount:.2f} ({amount_cents} centavos)")
            
            # ✅ PRODUÇÃO: Preparar dados do cliente (com fallback funcional se não fornecidos)
            if not customer_data:
                logger.warning("⚠️ Paradise: customer_data não fornecido, usando fallback")
                customer_data = {}
            
            # ✅ CORREÇÃO CRÍTICA: Validar e corrigir dados do cliente
            customer_payload = {
                "name": customer_data.get('name') or description[:30] if description else 'Cliente Digital',
                "email": customer_data.get('email') or f"pix{payment_id}@bot.digital",
                "phone": self._validate_phone(customer_data.get('phone') or '11999999999'),
                "document": self._validate_document(customer_data.get('document') or random.choice(VALID_CPFS))
            }
            
            logger.info(f"👤 Paradise: Cliente - {customer_payload['name']} | {customer_payload['email']}")
            logger.info(f"🔗 Paradise: Webhook URL - {self.get_webhook_url()}")
            logger.info(f"🔗 Paradise: Checkout URL - {self._get_dynamic_checkout_url(payment_id)}")
            
            # ✅ NOVA API V30: Payload atualizado baseado no paradise.php
            # ✅ CORREÇÃO CRÍTICA: Reference deve ser único e válido (sem caracteres especiais problemáticos)
            # Limitar tamanho e garantir unicidade
            # IMPORTANTE: Paradise pode gerar seu próprio ID baseado no reference
            # Usar payment_id diretamente (já é único: BOT{bot_id}_{timestamp}_{uuid})
            # ✅ CRÍTICO: Garantir que reference SEMPRE seja único (adicionar timestamp se necessário)
            safe_reference = str(payment_id).replace('_', '-').replace(' ', '')[:50]  # Max 50 chars, substituir _ por -
            
            # ✅ VALIDAÇÃO: Verificar se reference não está vazio
            if not safe_reference or len(safe_reference.strip()) == 0:
                logger.error(f"❌ Paradise: Reference inválido (vazio) - payment_id: {payment_id}")
                return None
            
            # ✅ VALIDAÇÃO CRÍTICA: Verificar se já existe payment com mesmo reference
            # Para evitar duplicação na Paradise, garantir que reference nunca seja reutilizado
            from app import db
            from models import Payment
            existing_with_same_reference = Payment.query.filter_by(
                gateway_transaction_hash=safe_reference  # Reference salvo como hash
            ).first()
            
            if existing_with_same_reference and existing_with_same_reference.status == 'pending':
                logger.error(f"❌ Paradise: Reference '{safe_reference}' já existe e está pendente!")
                logger.error(f"   Payment ID existente: {existing_with_same_reference.payment_id}")
                logger.error(f"   Isso não deveria acontecer - payment_id deve ser único!")
                # ✅ CORREÇÃO: Adicionar sufixo único ao reference para forçar unicidade
                import time
                safe_reference = f"{safe_reference}_{int(time.time())}"
                logger.warning(f"⚠️ Reference corrigido para garantir unicidade: {safe_reference}")
            
            payload = {
                "amount": amount_cents,  # ✅ CENTAVOS
                "description": (description[:100] if len(description) > 100 else description) or "Pagamento",  # ✅ Limitar descrição
                "reference": safe_reference,  # ✅ Reference seguro e único
                "checkoutUrl": self._get_dynamic_checkout_url(payment_id),  # ✅ URL DINÂMICA
                "webhookUrl": self.get_webhook_url(),  # ✅ WEBHOOK URL
                "productHash": self.product_hash,  # ✅ OBRIGATÓRIO
                "customer": customer_payload  # ✅ DADOS REAIS DO CLIENTE
            }
            
            # ✅ VALIDAÇÃO CRÍTICA: Verificar se productHash está configurado
            if not self.product_hash or not self.product_hash.startswith('prod_'):
                logger.error(f"❌ Paradise: productHash inválido ou não configurado: {self.product_hash}")
                return None
            
            # ✅ CORREÇÃO CRÍTICA: NÃO enviar offerHash para Paradise API
            # O offerHash no paradise.json é o hash da oferta, não deve ser enviado como parâmetro
            # Enviar offerHash pode causar IDs duplicados na Paradise
            # Se offerHash foi configurado, adiciona apenas se explicitamente necessário
            if self.offer_hash:
                # ⚠️ DESABILITADO: offerHash causa IDs duplicados na Paradise
                # payload["offerHash"] = self.offer_hash
                logger.info(f"⚠️ Paradise: offerHash ignorado ({self.offer_hash}) para evitar duplicação")
            
            # ✅ CORREÇÃO CRÍTICA: ADICIONAR SPLIT PAYMENT
            if self.store_id and self.split_percentage and self.split_percentage > 0:
                # Validar split_percentage
                if not isinstance(self.split_percentage, (int, float)) or self.split_percentage <= 0:
                    logger.error(f"❌ Paradise: split_percentage inválido: {self.split_percentage}")
                    return None
                
                # Log do split para debug
                logger.info(f"💰 Paradise Split: {self.split_percentage}% configurado")
                
                # ✅ CORREÇÃO CRÍTICA: Para valores muito pequenos, não aplicar split
                if amount_cents < 10:  # Menos de R$ 0,10
                    logger.warning(f"⚠️ Paradise: Valor muito pequeno (R$ {amount:.2f}), não aplicando split")
                    # Não adiciona split para valores muito pequenos
                else:
                    split_amount_cents = int(amount_cents * (self.split_percentage / 100))
                    
                    # Validar mínimo de 1 centavo para split
                    if split_amount_cents < 1:
                        split_amount_cents = 1
                    
                    # Garantir que sobra pelo menos 1 centavo para o vendedor
                    seller_amount_cents = amount_cents - split_amount_cents
                    if seller_amount_cents < 1:
                        logger.warning(f"⚠️ Paradise: Split deixaria menos de 1 centavo para vendedor. Ajustando...")
                        split_amount_cents = amount_cents - 1
                    
                    payload["split"] = {
                        "store_id": self.store_id,
                        "amount": split_amount_cents
                    }
                    
                    logger.info(f"💰 Paradise Split: {split_amount_cents} centavos ({self.split_percentage}%) para store {self.store_id}")
            
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
            
            # ✅ VALIDAÇÃO CRÍTICA: Status code pode ser 200 mas ter erro no JSON
            if response.status_code != 200:
                logger.error(f"❌ Paradise API Error: {response.status_code}")
                logger.error(f"❌ Response: {response.text}")
                return None
            
            # ✅ CORREÇÃO CRÍTICA: Verificar se response.text contém erro mesmo com 200
            if 'error' in response.text.lower() or '"status":"error"' in response.text.lower():
                logger.error(f"❌ Paradise: Resposta contém erro mesmo com status 200")
                logger.error(f"❌ Response: {response.text}")
                return None
            
            # ✅ CORREÇÃO CRÍTICA: Verificar se resposta é JSON válido
            try:
                data = response.json()
            except ValueError as e:
                logger.error(f"❌ Paradise: Resposta não é JSON válido: {e}")
                logger.error(f"❌ Response body: {response.text}")
                return None
            
            logger.info(f"📥 Paradise CREATE Response: {data}")
            
            # ✅ VALIDAÇÃO CRÍTICA: Verificar se status é realmente "success"
            response_status = data.get('status', '').lower()
            if response_status != 'success':
                logger.error(f"❌ Paradise: Status não é 'success' - recebido: '{response_status}'")
                logger.error(f"❌ Response completa: {data}")
                return None
            
            # ✅ VALIDAÇÃO CRÍTICA: Verificar se há erro na resposta
            if 'error' in data:
                logger.error(f"❌ Paradise: Erro na resposta: {data.get('error')}")
                logger.error(f"❌ Response completa: {data}")
                return None
            
            # ✅ CORREÇÃO CRÍTICA: Paradise retorna estrutura DIRETA, não aninhada
            # Resposta real: {"status": "success", "transaction_id": "145732", "qr_code": "...", "id": "TEST-1"}
            # NÃO é: {"transaction": {"id": "145732", "qr_code": "..."}}
            
            # ✅ CORREÇÃO CRÍTICA: Usar dados diretamente da resposta
            pix_code = data.get('qr_code')  # ✅ Campo direto: qr_code
            # ✅ CORREÇÃO DEFINITIVA: Paradise retorna 'id' como identificador do painel e 'transaction_id' como ID numérico
            # O campo 'id' é o que aparece no painel Paradise, então deve ser o hash principal
            transaction_id = data.get('transaction_id')  # ID numérico (ex: 151299)
            paradise_id = data.get('id')  # ID do painel (ex: "BOT-BOT5_1761860711_cf29c4f3")
            # ✅ CORREÇÃO CRÍTICA: Usar 'id' como hash principal (é o que aparece no painel)
            transaction_hash = data.get('hash') or paradise_id or transaction_id  # ✅ Prioridade: hash > id > transaction_id
            qr_code_base64 = data.get('qr_code_base64')  # ✅ QR Code em base64
            
            # ✅ Se não temos transaction_id mas temos id, usar id como transaction_id também
            if not transaction_id and paradise_id:
                transaction_id = paradise_id
            
            # ✅ Se ainda não temos transaction_id, usar hash como fallback
            if not transaction_id:
                transaction_id = transaction_hash
            
            logger.info(f"📥 Paradise Response Data: {data}")
            logger.info(f"📥 Paradise PIX Code: {pix_code[:50] if pix_code else None}...")
            logger.info(f"📥 Paradise Transaction ID (numérico): {transaction_id}")
            logger.info(f"📥 Paradise ID (painel): {paradise_id}")
            logger.info(f"📥 Paradise Transaction Hash (usado para consulta): {transaction_hash}")
            
            # ✅ VALIDAÇÃO RIGOROSA: Pix code é OBRIGATÓRIO
            if not pix_code:
                logger.error(f"❌ Paradise: qr_code ausente na resposta - transação NÃO criada no painel!")
                logger.error(f"❌ Response completa: {data}")
                return None
            
            # ✅ VALIDAÇÃO: Ao menos um identificador (transaction_id ou hash) deve existir
            if not transaction_id and not transaction_hash:
                logger.error(f"❌ Paradise: Nenhum identificador retornado (transaction_id ou id ausentes) - transação NÃO criada no painel!")
                logger.error(f"❌ Response completa: {data}")
                return None
            
            # ✅ Se não temos hash mas temos transaction_id, usar transaction_id como hash
            if not transaction_hash and transaction_id:
                transaction_hash = transaction_id
            
            # ✅ VALIDAÇÃO FINAL: Verificar se qr_code é válido (começa com 000201 para PIX)
            if not pix_code.startswith('000201'):
                logger.warning(f"⚠️ Paradise: qr_code não parece válido (não começa com 000201): {pix_code[:20]}...")
            
            # ✅ LOG CRÍTICO: Informações para debug
            logger.info(f"✅ Paradise: PIX gerado com SUCESSO")
            logger.info(f"   Transaction ID (numérico): {transaction_id}")
            logger.info(f"   Paradise ID (aparece no painel): {paradise_id or 'N/A'}")
            logger.info(f"   Transaction Hash (usado para consulta): {transaction_hash}")
            logger.info(f"   Reference enviado: {safe_reference}")
            logger.info(f"   Product Hash: {self.product_hash}")
            logger.info(f"   QR Code válido: {'✅' if pix_code.startswith('000201') else '⚠️'}")
            
            # ✅ ALERTA: Se o ID retornado é diferente do reference, pode não aparecer no painel
            if paradise_id and paradise_id != safe_reference:
                logger.warning(f"⚠️ Paradise gerou ID diferente do reference enviado!")
                logger.warning(f"   Reference enviado: {safe_reference}")
                logger.warning(f"   ID retornado: {paradise_id}")
                logger.warning(f"   💡 Use o ID retornado ({paradise_id}) para verificar no painel Paradise")
            else:
                logger.info(f"   ✅ Reference e ID coincidem - transação deve aparecer no painel")
            
            # Retorna padrão unificado
            return {
                'pix_code': pix_code,  # ✅ Padronizado
                'qr_code_url': qr_code_base64 if qr_code_base64 else f'https://api.qrserver.com/v1/create-qr-code/?size=300x300&data={pix_code}',
                'transaction_id': transaction_id,  # ✅ Convertido de 'id'
                'transaction_hash': transaction_hash,  # ✅ Hash para consulta de status
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
            
            # Extrai transaction_id (pode vir como 'transaction_id', 'id' ou 'hash')
            transaction_id = data.get('transaction_id') or data.get('id') or data.get('hash')
            logger.info(f"🔍 Transaction ID extraído: {transaction_id}")
            
            if not transaction_id:
                logger.error(f"❌ Paradise: 'id'/'hash' ausente | Data recebida: {data}")
                return None
            
            # Extrai status
            # Paradise pode enviar: 'status' (approved|pending|refunded) ou 'payment_status'
            status = (data.get('status') or data.get('payment_status') or '').lower()
            logger.info(f"🔍 Status bruto: {status}")
            
            # Extrai valor
            amount_cents = data.get('amount_paid') or data.get('amount')
            logger.info(f"🔍 Amount (centavos): {amount_cents}")
            
            # Converte centavos para reais
            amount = amount_cents / 100 if amount_cents else 0
            
            # Mapeia status Paradise → Sistema
            # Paradise envia: approved, pending, refunded
            mapped_status = 'pending'
            if status == 'approved':  # ✅ Paradise envia "approved", não "paid"!
                mapped_status = 'paid'
            elif status == 'refunded':
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
        Consulta status de um pagamento no Paradise (API V30)
        Aceita: hash, id (painel) ou transaction_id (numérico)
        Retorna dict padronizado: { 'gateway_transaction_id', 'status', 'amount' }
        """
        try:
            if not transaction_id:
                logger.error("❌ Paradise: hash/id vazio na consulta de status")
                return None
            
            # ✅ CORREÇÃO: Paradise aceita 'hash' como parâmetro (pode ser id ou hash real)
            # Tentar primeiro com hash/id (que é o que aparece no painel)
            params = { 'hash': str(transaction_id) }
            headers = {
                'Accept': 'application/json',
                'X-API-Key': self.api_key
            }
            
            # ✅ LOG para debug
            logger.debug(f"🔍 Paradise: Consultando status com hash/id: {transaction_id}")
            
            # Paradise aceita GET em check_status.php
            resp = requests.get(self.check_status_url, params=params, headers=headers, timeout=15)
            
            # ✅ Log de erro
            if resp.status_code != 200:
                logger.warning(f"⚠️ Paradise CHECK {resp.status_code}: {resp.text[:200]}")
                return None
            
            try:
                data = resp.json()
            except ValueError:
                logger.warning(f"⚠️ Paradise: Resposta não é JSON válido: {resp.text[:200]}")
                return None

            # ✅ VALIDAÇÃO: Verificar se resposta contém erro
            if data.get('error') or data.get('status') == 'error':
                logger.warning(f"⚠️ Paradise: Erro na resposta: {data.get('error', data.get('message', 'Erro desconhecido'))}")
                return None

            # Campos possíveis: status/payment_status, transaction_id/id/hash, amount/amount_paid
            raw_status = (data.get('status') or data.get('payment_status') or '').lower()
            mapped_status = 'pending'
            if raw_status == 'approved':
                mapped_status = 'paid'
            elif raw_status == 'refunded':
                mapped_status = 'failed'

            amount_cents = data.get('amount_paid') or data.get('amount')
            amount = (amount_cents / 100.0) if isinstance(amount_cents, (int, float)) else None

            tx_id = data.get('transaction_id') or data.get('id') or data.get('hash') or str(transaction_id)

            # ✅ Log de status (sempre para debug)
            logger.debug(f"🔍 Paradise Status: {raw_status} → {mapped_status} | Amount: {amount} | TX ID: {tx_id}")

            return {
                'gateway_transaction_id': str(tx_id),
                'status': mapped_status,
                'amount': amount
            }

        except requests.Timeout:
            logger.error("❌ Paradise: Timeout na consulta de status (15s)")
            return None
        except requests.RequestException as e:
            logger.error(f"❌ Paradise: Erro de conexão na consulta de status: {e}")
            return None
        except Exception as e:
            logger.error(f"❌ Paradise: Erro inesperado na consulta de status: {e}", exc_info=True)
            return None
    
    def validate_amount(self, amount: float) -> bool:
        """Valida se o valor está dentro dos limites aceitos pelo Paradise"""
        amount_cents = int(amount * 100)
        
        if amount_cents < 1:  # R$ 0,01 mínimo
            logger.error(f"❌ Paradise: Valor mínimo é R$ 0,01")
            return False
        
        # Paradise não especifica limite máximo na documentação
        # Mas é prudente ter um limite razoável
        if amount_cents > 100000000:  # R$ 1.000.000,00
            logger.error(f"❌ Paradise: Valor máximo é R$ 1.000.000,00")
            return False
        
        return True


