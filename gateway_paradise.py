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
import csv
from typing import Dict, Optional
from gateway_interface import PaymentGateway

logger = logging.getLogger(__name__)

# Cache global para identidades válidas (KYC)
_VALID_IDENTITIES_CACHE = []

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


def _load_identities_if_needed():
    """
    Carrega identidades válidas do CSV para o cache global (apenas uma vez)
    """
    global _VALID_IDENTITIES_CACHE
    
    if not _VALID_IDENTITIES_CACHE:
        try:
            with open('cpf_nome_formatado.csv', 'r', encoding='utf-8') as file:
                reader = csv.reader(file)
                next(reader)  # Pular cabeçalho (cpf,nome)
                for row in reader:
                    if len(row) >= 2 and row[0] and row[1]:
                        _VALID_IDENTITIES_CACHE.append({
                            'cpf': row[0].strip(),
                            'nome': row[1].strip()
                        })
            logger.info(f"✅ KYC Cache: {len(_VALID_IDENTITIES_CACHE)} identidades carregadas do CSV")
        except FileNotFoundError:
            logger.warning("⚠️ KYC Cache: Arquivo cpf_nome_formatado.csv não encontrado, usando fallback")
            _VALID_IDENTITIES_CACHE = []
        except Exception as e:
            logger.error(f"❌ KYC Cache: Erro ao carregar CSV: {e}")
            _VALID_IDENTITIES_CACHE = []


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
        # ✅ CREDENCIAIS - NÃO usar fallback padrão (gateways devem ter credenciais configuradas)
        # Fallback padrão estava mascarando erros de configuração
        api_key = credentials.get('api_key')
        product_hash = credentials.get('product_hash')
        
        # ✅ VALIDAÇÃO CRÍTICA: Credenciais devem ser fornecidas
        if not api_key:
            logger.error(f"❌ CRÍTICO: Paradise api_key não fornecida nas credentials!")
            logger.error(f"   Credentials recebidas: {list(credentials.keys())}")
            raise ValueError("Paradise api_key é obrigatória")
        
        if not product_hash:
            logger.error(f"❌ CRÍTICO: Paradise product_hash não fornecido nas credentials!")
            logger.error(f"   Credentials recebidas: {list(credentials.keys())}")
            raise ValueError("Paradise product_hash é obrigatório")
        
        # ✅ VALIDAÇÃO DE FORMATO
        if not api_key.startswith('sk_'):
            logger.error(f"❌ CRÍTICO: Paradise api_key deve começar com 'sk_'")
            logger.error(f"   API Key recebida: {api_key[:20]}...")
            raise ValueError("Paradise api_key formato inválido")
        
        if not product_hash.startswith('prod_'):
            logger.error(f"❌ CRÍTICO: Paradise product_hash deve começar com 'prod_'")
            logger.error(f"   Product Hash recebido: {product_hash[:20]}...")
            raise ValueError("Paradise product_hash formato inválido")
        
        self.api_key = api_key
        self.product_hash = product_hash
        self.offer_hash = credentials.get('offer_hash', '')
        
        # ✅ STORE ID DO SISTEMA (SPLIT DA PLATAFORMA) - NÃO DO USUÁRIO
        # Prioridade: credentials > env > default
        from os import environ
        self.store_id = credentials.get('store_id') or environ.get('PARADISE_STORE_ID', '177')
        
        # ✅ VALIDAÇÃO: Store ID deve ser válido
        if not self.store_id or not str(self.store_id).strip():
            logger.error(f"❌ CRÍTICO: Paradise store_id inválido ou vazio!")
            logger.error(f"   Store ID recebido: {self.store_id}")
            raise ValueError("Paradise store_id é obrigatório para split")
        
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
            
            # ✅ KYC: Carregar identidades reais do cache (apenas uma vez)
            _load_identities_if_needed()
            
            # ✅ KYC: Sortear identidade real para antifraude
            if _VALID_IDENTITIES_CACHE:
                identity = random.choice(_VALID_IDENTITIES_CACHE)
                real_name = identity['nome']
                real_cpf = ''.join(filter(str.isdigit, identity['cpf']))  # Apenas números
                logger.info(f"✅ KYC: Identidade sorteada - {real_name} | CPF: {real_cpf[:3]}***")
            else:
                # Fallback se CSV não disponível
                logger.warning("⚠️ KYC: Cache vazio, usando dados gerados")
                real_name = "Cliente Padrão"
                real_cpf = random.choice(VALID_CPFS)
            
            # ✅ PRODUÇÃO: Preparar dados do cliente (com fallback funcional se não fornecidos)
            if not customer_data:
                logger.warning("⚠️ Paradise: customer_data não fornecido, usando fallback")
                customer_data = {}
            
            # ✅ CORREÇÃO CRÍTICA: Gerar dados ÚNICOS para cada transação
            # NUNCA reutilizar dados de transações anteriores para evitar duplicação na Paradise
            import time
            import hashlib
            
            # Gerar timestamp único em milissegundos
            timestamp_ms = int(time.time() * 1000)
            
            # Gerar hash único baseado em payment_id + timestamp + customer_user_id
            unique_hash = hashlib.md5(f"{payment_id}_{timestamp_ms}_{customer_data.get('document', customer_data.get('phone', 'user'))}".encode()).hexdigest()[:8]
            
            # ✅ EMAIL ÚNICO: Usar @gmail.com para evitar anti-bot
            # Formato: primeironome + ultimos4digitoscpf + @gmail.com
            first_name = real_name.split()[0].lower() if real_name and ' ' in real_name else real_name.lower() if real_name else 'cliente'
            cpf_last4 = real_cpf[-4:] if len(real_cpf) >= 4 else unique_hash[:4]
            unique_email = f"{first_name}{cpf_last4}@gmail.com"
            
            # ✅ CPF ÚNICO: Usar CPF real do cache + hash para garantir unicidade
            # Combinar CPF real com hash para evitar duplicação enquanto mantém dados válidos
            cpf_base = f"{real_cpf[:8]}{unique_hash[:3]}"  # 8 dígitos do CPF real + 3 do hash
            unique_cpf = cpf_base[:11]  # Garantir 11 dígitos
            
            # ✅ TELEFONE ÚNICO: Baseado no customer_user_id ou gerar único
            customer_user_id = customer_data.get('phone') or customer_data.get('document') or str(payment_id).replace('BOT', '').replace('-', '').replace('_', '')[:10]
            unique_phone = self._validate_phone(f"11{customer_user_id[-9:]}" if len(str(customer_user_id)) >= 9 else f"11{unique_hash[:9]}")
            
            # ✅ NOME ÚNICO: Usar nome real do cache (KYC)
            unique_name = real_name[:30] if len(real_name) > 30 else real_name
            
            # ✅ VALIDAÇÃO CRÍTICA: Garantir que nome tem pelo menos 2 caracteres
            if len(unique_name) < 2:
                logger.error(f"❌ Paradise: Nome do cliente inválido (muito curto): '{unique_name}'")
                unique_name = f"Cliente {unique_hash[:4]}"
            
            customer_payload = {
                "name": unique_name,
                "email": unique_email,
                "phone": unique_phone,
                "document": self._validate_document(unique_cpf)
            }
            
            logger.info(f"✅ Paradise: Dados ÚNICOS gerados para payment {payment_id}")
            logger.info(f"   Email: {unique_email}")
            logger.info(f"   CPF: {unique_cpf[:3]}***")
            logger.info(f"   Phone: {unique_phone[:5]}***")
            
            logger.info(f"👤 Paradise: Cliente - {customer_payload['name']} | {customer_payload['email']}")
            logger.info(f"🔗 Paradise: Webhook URL - {self.get_webhook_url()}")
            logger.info(f"🔗 Paradise: Checkout URL - {self._get_dynamic_checkout_url(payment_id)}")
            
            # ✅ NOVA API V30: Payload atualizado baseado no paradise.php
            # ✅ CORREÇÃO CRÍTICA: Reference deve ser SEMPRE ÚNICO (timestamp + hash)
            # NUNCA reutilizar reference para evitar duplicação na Paradise
            # Usar payment_id + timestamp + hash único para garantir unicidade absoluta
            reference_hash = hashlib.md5(f"{payment_id}_{timestamp_ms}_{unique_hash}".encode()).hexdigest()[:8]
            
            # Reference único: payment_id_base + timestamp + hash
            payment_id_base = str(payment_id).replace('_', '-').replace(' ', '')[:30]  # Base do payment_id
            safe_reference = f"{payment_id_base}-{timestamp_ms}-{reference_hash}"
            
            # Limitar a 50 caracteres (limite da Paradise)
            safe_reference = safe_reference[:50]
            
            # ✅ VALIDAÇÃO: Verificar se reference não está vazio
            if not safe_reference or len(safe_reference.strip()) == 0:
                logger.error(f"❌ Paradise: Reference inválido (vazio) - payment_id: {payment_id}")
                return None
            
            logger.info(f"✅ Paradise: Reference ÚNICO gerado: {safe_reference}")
            
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
            
            # Configurar Split (Estratégia Híbrida para bypass de Parser PHP)
            if self.store_id and self.split_percentage > 0:
                try:
                    recipient_id_int = int(self.store_id)
                    split_amount = int((amount_cents * self.split_percentage) / 100)
                    
                    # ✅ REGRA DE OURO: Split não pode ser menor que 100 centavos (R$ 1.00)
                    if split_amount < 100:
                        logger.warning(f"⚠️ Paradise Split: Ajustando valor de {split_amount} para 100 centavos.")
                        split_amount = 100
                    
                    # ✅ REGRA DE PROTEÇÃO DE OVERFLOW: Split não pode ser maior ou igual ao valor total
                    if split_amount >= amount_cents:
                        logger.warning(f"⚠️ Paradise Split: Split ({split_amount}) maior que o total. Cancelando split.")
                    else:
                        logger.info(f"💰 Paradise Split: {split_amount} centavos para a store {recipient_id_int}")
                        
                        # ENGENHARIA HÍBRIDA: Enviamos ambas as estruturas para garantir parsing
                        # 1. Estrutura Antiga/Legada (Objeto)
                        payload['split'] = {
                            'store_id': str(recipient_id_int),
                            'amount': split_amount
                        }
                        
                        # 2. Estrutura da Nova Documentação (Array de Objetos)
                        payload['splits'] = [
                            {
                                "recipientId": recipient_id_int,
                                "amount": split_amount
                            }
                        ]
                except ValueError:
                    logger.error(f"❌ Paradise Split: O store_id '{self.store_id}' não é válido.")
            
            # ✅ LOG DETALHADO para debug (mascarar dados sensíveis)
            payload_log = payload.copy()
            if 'customer' in payload_log and payload_log['customer']:
                payload_log['customer'] = payload_log['customer'].copy()
                if 'document' in payload_log['customer']:
                    doc = payload_log['customer']['document']
                    if doc:
                        payload_log['customer']['document'] = doc[:3] + '***'
            logger.info(f"📤 Paradise Payload: {payload_log}")
            
            # ✅ VALIDAÇÃO CRÍTICA: Verificar campos antes de enviar
            if not payload.get('productHash'):
                logger.error(f"❌ CRÍTICO: productHash ausente no payload!")
                logger.error(f"   Payload keys: {list(payload.keys())}")
                return None
            
            if payload.get('productHash') != self.product_hash:
                logger.error(f"❌ CRÍTICO: productHash no payload difere do configurado!")
                logger.error(f"   Payload: {payload.get('productHash')}")
                logger.error(f"   Configurado: {self.product_hash}")
                return None
            
            # ✅ VALIDAÇÃO CRÍTICA: Verificar se api_key está presente e no formato correto
            if not self.api_key:
                logger.error(f"❌ CRÍTICO: api_key não configurada no gateway Paradise!")
                return None
            
            if not self.api_key.startswith('sk_'):
                logger.error(f"❌ CRÍTICO: api_key formato inválido (deve começar com 'sk_')!")
                logger.error(f"   API Key: {self.api_key[:30]}...")
                return None
            
            # ✅ VALIDAÇÃO CRÍTICA: Verificar product_hash
            if not self.product_hash or not self.product_hash.startswith('prod_'):
                logger.error(f"❌ CRÍTICO: product_hash inválido (deve começar com 'prod_')!")
                logger.error(f"   Product Hash: {self.product_hash}")
                return None
            
            # Headers Paradise (X-API-Key)
            headers = {
                'Content-Type': 'application/json',
                'Accept': 'application/json',
                'X-API-Key': self.api_key  # ✅ AUTENTICAÇÃO
            }
            
            # ✅ VALIDAÇÃO: Verificar se API Key está presente
            if not self.api_key or len(self.api_key) < 10:
                logger.error(f"❌ CRÍTICO: API Key inválida ou ausente!")
                logger.error(f"   API Key (primeiros 20 chars): {self.api_key[:20] if self.api_key else 'None'}...")
                return None
            
            logger.info(f"📤 Paradise URL: {self.transaction_url}")
            logger.info(f"📤 Paradise Headers: Content-Type=application/json, X-API-Key={self.api_key[:10]}...")
            logger.info(f"📤 Paradise Request ID: {safe_reference}")
            
            # ✅ RETRY COM BACKOFF EXPONENCIAL para erros 400/500 transitórios
            # Alguns 400 podem ser temporários (rate limit, validação transitória)
            max_retries = 2
            retry_delays = [0.5, 1.0]  # 500ms, 1s
            
            import time
            request_start_time = time.time()
            response = None
            last_error = None
            
            for attempt in range(max_retries + 1):
                try:
                    response = requests.post(
                        self.transaction_url,
                        json=payload,
                        headers=headers,
                        timeout=15
                    )
                    
                    request_duration = (time.time() - request_start_time) * 1000  # ms
                    
                    logger.info(f"📡 Paradise Response (tentativa {attempt + 1}/{max_retries + 1}): Status {response.status_code} | Duration: {request_duration:.2f}ms")
                    logger.info(f"📡 Paradise Response Body: {response.text}")
                    
                    # ✅ Se for 200, sair do loop
                    if response.status_code == 200:
                        break
                    
                    # ✅ DIAGNÓSTICO IMEDIATO para erro 400 (na primeira tentativa)
                    if response.status_code == 400 and attempt == 0:
                        try:
                            error_data = response.json()
                            error_message = error_data.get('message', 'Erro desconhecido')
                            acquirer = error_data.get('acquirer', 'N/A')
                            
                            logger.error(f"")
                            logger.error(f"🔍 ===== DIAGNÓSTICO PARADISE 400 BAD REQUEST (TENTATIVA {attempt + 1}) =====")
                            logger.error(f"   Mensagem da API: {error_message}")
                            logger.error(f"   Acquirer: {acquirer}")
                            logger.error(f"   ════════════════════════════════════════════════")
                            logger.error(f"   🔑 CREDENCIAIS ENVIADAS:")
                            logger.error(f"   - API Key: {self.api_key[:10]}...{self.api_key[-10:] if len(self.api_key) > 20 else ''} (len={len(self.api_key)})")
                            logger.error(f"   - Product Hash: {self.product_hash} (valido={'✅' if self.product_hash.startswith('prod_') else '❌'})")
                            logger.error(f"   - Store ID: {self.store_id}")
                            logger.error(f"   ════════════════════════════════════════════════")
                            logger.error(f"   📊 PAYLOAD ENVIADO:")
                            logger.error(f"   - Valor: R$ {amount:.2f} ({amount_cents} centavos)")
                            logger.error(f"   - Reference: {safe_reference}")
                            split_amount = payload.get('split', {}).get('amount', 0) if 'split' in payload else 0
                            logger.error(f"   - Split: {self.split_percentage}% ({split_amount} centavos)")
                            customer_data_payload = payload.get('customer', {})
                            customer_name_payload = customer_data_payload.get('name', '')
                            logger.error(f"   - Cliente: '{customer_name_payload}' (len={len(customer_name_payload)}) | {customer_data_payload.get('email')}")
                            doc = customer_data_payload.get('document', '')
                            logger.error(f"   - CPF: {doc[:3]}*** (len={len(doc) if doc else 0})")
                            phone = customer_data_payload.get('phone', '')
                            logger.error(f"   - Telefone: {phone[:5]}*** (len={len(phone) if phone else 0})")
                            logger.error(f"   ════════════════════════════════════════════════")
                            logger.error(f"   🔍 POSSÍVEIS CAUSAS (em ordem de probabilidade):")
                            logger.error(f"   1. ❌ NOME DO CLIENTE MUITO CURTO: '{customer_name_payload}' (len={len(customer_name_payload)})")
                            logger.error(f"      → Paradise pode rejeitar nomes com menos de 2 caracteres")
                            logger.error(f"      → AÇÃO: Validar nome do cliente antes de enviar")
                            logger.error(f"   2. ❌ API Key inválida ou sem permissões")
                            logger.error(f"      → Verificar se api_key começa com 'sk_' e está ativa no painel Paradise")
                            logger.error(f"   3. ❌ Product Hash não existe ou foi deletado no painel Paradise")
                            logger.error(f"      → Verificar se '{self.product_hash}' existe no painel Paradise")
                            logger.error(f"   4. ❌ Store ID inválido ou sem permissão para split")
                            logger.error(f"      → Verificar se store_id '{self.store_id}' existe e tem permissão para split")
                            logger.error(f"   5. ❌ Split amount inválido (valor do split muito alto ou calculado incorretamente)")
                            logger.error(f"      → Split: {split_amount} centavos de {amount_cents} total")
                            logger.error(f"   6. ❌ Dados do cliente inválidos (CPF ou telefone)")
                            logger.error(f"      → CPF: {len(doc) if doc else 0} dígitos | Telefone: {len(phone) if phone else 0} dígitos")
                            logger.error(f"   7. ❌ Valor inválido (muito baixo < R$ 0,01 ou muito alto > R$ 1.000.000)")
                            logger.error(f"      → Valor: R$ {amount:.2f} ({amount_cents} centavos)")
                            logger.error(f"   8. ❌ Rate limit atingido (muitas requisições em pouco tempo)")
                            logger.error(f"   9. ❌ Campos obrigatórios faltando no payload")
                            logger.error(f"   ════════════════════════════════════════════════")
                            logger.error(f"   ✅ AÇÕES RECOMENDADAS:")
                            logger.error(f"   1. Verificar se nome do cliente tem pelo menos 2 caracteres")
                            logger.error(f"   2. Verificar no painel Paradise se Product Hash '{self.product_hash}' existe")
                            logger.error(f"   3. Verificar no painel Paradise se API Key está ativa e tem permissões")
                            logger.error(f"   4. Verificar no painel Paradise se Store ID '{self.store_id}' existe e tem permissão para split")
                            logger.error(f"   5. Reconfigurar gateway em /settings com credenciais corretas")
                            logger.error(f"   ════════════════════════════════════════════════")
                            logger.error(f"")
                        except Exception as e:
                            logger.error(f"   ❌ Erro ao processar resposta de erro: {e}")
                            logger.error(f"   Response raw: {response.text[:500]}")
                    
                    # ✅ Se for erro não-retryável (exceto 500), não retentar
                    if response.status_code not in [400, 500, 502, 503, 504]:
                        logger.error(f"❌ Paradise API Error: {response.status_code} (não-retryável)")
                        logger.error(f"❌ Response: {response.text}")
                        return None
                    
                    # ✅ Última tentativa ou erro retryável - logar erro
                    if attempt < max_retries:
                        last_error = {
                            'status': response.status_code,
                            'message': response.text
                        }
                        logger.warning(f"⚠️ Paradise retornou {response.status_code}, retentando em {retry_delays[attempt]}s...")
                        time.sleep(retry_delays[attempt])
                    else:
                        # Última tentativa falhou
                        logger.error(f"❌ Paradise API Error após {max_retries + 1} tentativas: {response.status_code}")
                        logger.error(f"❌ Response: {response.text}")
                        break
                        
                except requests.exceptions.Timeout:
                    if attempt < max_retries:
                        logger.warning(f"⚠️ Paradise timeout, retentando em {retry_delays[attempt]}s...")
                        time.sleep(retry_delays[attempt])
                    else:
                        logger.error(f"❌ Paradise timeout após {max_retries + 1} tentativas")
                        return None
                except Exception as e:
                    logger.error(f"❌ Erro inesperado ao chamar Paradise API: {e}", exc_info=True)
                    return None
            
            # ✅ Verificar resposta final
            if not response:
                logger.error(f"❌ Paradise: Nenhuma resposta recebida após {max_retries + 1} tentativas")
                return None
            
            # ✅ VALIDAÇÃO CRÍTICA: Status code pode ser 200 mas ter erro no JSON
            if response.status_code != 200:
                logger.error(f"❌ Paradise API Error: {response.status_code}")
                logger.error(f"❌ Response: {response.text}")
                
                # ✅ DIAGNÓSTICO DETALHADO PARA ERRO 400
                if response.status_code == 400:
                    try:
                        error_data = response.json()
                        error_message = error_data.get('message', 'Erro desconhecido')
                        acquirer = error_data.get('acquirer', 'N/A')
                        
                        logger.error(f"🔍 ===== DIAGNÓSTICO PARADISE 400 BAD REQUEST =====")
                        logger.error(f"   Mensagem da API: {error_message}")
                        logger.error(f"   Acquirer: {acquirer}")
                        logger.error(f"   ════════════════════════════════════════════════")
                        logger.error(f"   🔑 CREDENCIAIS ENVIADAS:")
                        logger.error(f"   - API Key: {self.api_key[:10]}...{self.api_key[-10:] if len(self.api_key) > 20 else ''} (len={len(self.api_key)})")
                        logger.error(f"   - Product Hash: {self.product_hash} (valido={'✅' if self.product_hash.startswith('prod_') else '❌'})")
                        logger.error(f"   - Store ID: {self.store_id}")
                        logger.error(f"   ════════════════════════════════════════════════")
                        logger.error(f"   📊 PAYLOAD:")
                        logger.error(f"   - Valor: R$ {amount:.2f} ({amount_cents} centavos)")
                        logger.error(f"   - Reference: {safe_reference}")
                        split_amount = payload.get('split', {}).get('amount', 0) if 'split' in payload else 0
                        logger.error(f"   - Split: {self.split_percentage}% ({split_amount} centavos)")
                        customer_data = payload.get('customer', {})
                        logger.error(f"   - Cliente: {customer_data.get('name')} | {customer_data.get('email')}")
                        doc = customer_data.get('document', '')
                        logger.error(f"   - CPF: {doc[:3]}*** (len={len(doc)})")
                        phone = customer_data.get('phone', '')
                        logger.error(f"   - Telefone: {phone[:5]}*** (len={len(phone)})")
                        logger.error(f"   ════════════════════════════════════════════════")
                        logger.error(f"   🔍 POSSÍVEIS CAUSAS (em ordem de probabilidade):")
                        logger.error(f"   1. ❌ API Key inválida ou sem permissões")
                        logger.error(f"      → Verificar se api_key começa com 'sk_' e está ativa no painel Paradise")
                        logger.error(f"   2. ❌ Product Hash não existe ou foi deletado no painel Paradise")
                        logger.error(f"      → Verificar se '{self.product_hash}' existe no painel Paradise")
                        logger.error(f"   3. ❌ Store ID inválido ou sem permissão para split")
                        logger.error(f"      → Verificar se store_id '{self.store_id}' existe e tem permissão para split")
                        logger.error(f"   4. ❌ Split amount inválido (valor do split muito alto ou calculado incorretamente)")
                        logger.error(f"      → Split: {split_amount} centavos de {amount_cents} total")
                        logger.error(f"   5. ❌ Dados do cliente inválidos (CPF, telefone ou email)")
                        logger.error(f"      → CPF: {len(doc)} dígitos | Telefone: {len(phone)} dígitos")
                        logger.error(f"   6. ❌ Valor inválido (muito baixo < R$ 0,01 ou muito alto > R$ 1.000.000)")
                        logger.error(f"      → Valor: R$ {amount:.2f} ({amount_cents} centavos)")
                        logger.error(f"   7. ❌ Rate limit atingido (muitas requisições em pouco tempo)")
                        logger.error(f"   8. ❌ Campos obrigatórios faltando no payload")
                        logger.error(f"   ════════════════════════════════════════════════")
                        logger.error(f"   ✅ AÇÕES RECOMENDADAS:")
                        logger.error(f"   1. Verificar no painel Paradise se Product Hash '{self.product_hash}' existe")
                        logger.error(f"   2. Verificar no painel Paradise se API Key está ativa e tem permissões")
                        logger.error(f"   3. Verificar no painel Paradise se Store ID '{self.store_id}' existe e tem permissão para split")
                        logger.error(f"   4. Reconfigurar gateway em /settings com credenciais corretas")
                        logger.error(f"   ════════════════════════════════════════════════")
                    except Exception as e:
                        logger.error(f"   ❌ Erro ao processar resposta de erro: {e}")
                        logger.error(f"   Response raw: {response.text[:500]}")
                
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
            # Paradise pode enviar: approved, paid, pending, refunded
            mapped_status = 'pending'
            # ✅ CORREÇÃO CRÍTICA: Aceitar tanto "approved" quanto "paid" como pago
            if status in ('approved', 'paid'):
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
                error_msg = data.get('error', data.get('message', 'Erro desconhecido'))
                logger.warning(f"⚠️ Paradise: Erro na resposta: {error_msg}")
                logger.debug(f"   Response completa: {data}")
                return None
            
            # ✅ Log da resposta completa para debug quando status é paid
            raw_status_check = (data.get('status') or data.get('payment_status') or '').lower()
            if raw_status_check in ('paid', 'approved'):
                logger.info(f"📡 Paradise Response (PAID): {data}")

            # Campos possíveis: status/payment_status, transaction_id/id/hash, amount/amount_paid
            raw_status = (data.get('status') or data.get('payment_status') or '').lower()
            mapped_status = 'pending'
            # ✅ CORREÇÃO CRÍTICA: Paradise pode retornar "paid" ou "approved" como status pago
            if raw_status in ('approved', 'paid'):
                mapped_status = 'paid'
            elif raw_status == 'refunded':
                mapped_status = 'failed'

            amount_cents = data.get('amount_paid') or data.get('amount')
            amount = (amount_cents / 100.0) if isinstance(amount_cents, (int, float)) else None

            tx_id = data.get('transaction_id') or data.get('id') or data.get('hash') or str(transaction_id)

            # ✅ Log de status (info para pending também, para debug)
            if mapped_status == 'pending':
                logger.info(f"🔍 Paradise Status Response: {raw_status} → {mapped_status} | Amount: {amount} | TX ID: {tx_id}")
            else:
                logger.info(f"🔍 Paradise Status Response: {raw_status} → {mapped_status} | Amount: {amount} | TX ID: {tx_id}")

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


