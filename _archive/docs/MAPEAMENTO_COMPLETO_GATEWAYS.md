# Mapeamento Completo - Sistema Multi-Gateway

## 🎯 Objetivo

Este documento fornece um mapeamento completo e visual do sistema multi-gateway, incluindo:
- Arquitetura detalhada
- Fluxos de dados
- Gateways existentes
- Padrões de implementação
- Exemplos práticos

---

## 📊 Arquitetura Visual

### Componentes e Relacionamentos

```
┌─────────────────────────────────────────────────────────────────┐
│                         BotManager                               │
│  - _generate_pix_payment()                                      │
│  - Busca Gateway no banco                                       │
│  - Cria gateway via Factory                                     │
│  - Gera PIX                                                     │
│  - Salva Payment no banco                                       │
└────────────────────────────┬────────────────────────────────────┘
                             │
                             ▼
┌─────────────────────────────────────────────────────────────────┐
│                      GatewayFactory                              │
│  - Registry: _gateway_classes                                   │
│  - create_gateway(gateway_type, credentials, use_adapter=True)  │
│  - Valida credenciais                                           │
│  - Cria instância do gateway                                    │
│  - Envolve com GatewayAdapter (padrão)                          │
└────────────────────────────┬────────────────────────────────────┘
                             │
                             ▼
┌─────────────────────────────────────────────────────────────────┐
│                     GatewayAdapter                               │
│  - Normaliza generate_pix()                                     │
│  - Normaliza process_webhook()                                  │
│  - Normaliza status                                             │
│  - Normaliza valores                                            │
│  - Logging consistente                                          │
└────────────────────────────┬────────────────────────────────────┘
                             │
        ┌────────────────────┼────────────────────┬────────────────────┬────────────────────┐
        ▼                    ▼                    ▼                    ▼                    ▼
┌──────────────┐    ┌──────────────┐    ┌──────────────┐    ┌──────────────┐    ┌──────────────┐
│  SyncPay     │    │  PushynPay   │    │  Paradise    │    │  WiinPay     │    │  Átomo Pay   │
│  Gateway     │    │  Gateway     │    │  Gateway     │    │  Gateway     │    │  Gateway     │
│              │    │              │    │              │    │              │    │              │
│ Bearer Token │    │ Bearer Token │    │ X-API-Key    │    │ api_key body │    │ api_token qs │
│ Reais        │    │ Centavos     │    │ Centavos     │    │ Reais        │    │ Centavos     │
│ Split %      │    │ Split fixo   │    │ Split fixo   │    │ Split %/fixo │    │ Multi-tenant │
└──────────────┘    └──────────────┘    └──────────────┘    └──────────────┘    └──────────────┘
```

---

## 🔄 Fluxo de Criação de Pagamento

### Sequência Detalhada

```
1. Usuário inicia pagamento no bot
   ↓
2. BotManager._generate_pix_payment()
   ├─ Busca Bot no banco
   ├─ Busca Gateway ativo do usuário
   ├─ Valida gateway (is_active=True, is_verified=True)
   └─ Prepara credenciais específicas do gateway
   ↓
3. GatewayFactory.create_gateway(gateway_type, credentials)
   ├─ Valida gateway_type
   ├─ Busca classe do gateway no registry
   ├─ Valida credenciais obrigatórias
   ├─ Cria instância do gateway
   └─ Envolve com GatewayAdapter (use_adapter=True)
   ↓
4. GatewayAdapter(gateway)
   ├─ Normaliza generate_pix()
   ├─ Normaliza process_webhook()
   └─ Normaliza status e valores
   ↓
5. gateway.generate_pix(amount, description, payment_id, customer_data)
   ├─ Valida valor (amount > 0)
   ├─ Converte valor se necessário (reais ↔ centavos)
   ├─ Prepara payload específico do gateway
   ├─ Faz requisição à API do gateway
   ├─ Processa resposta
   └─ Retorna dict normalizado
   ↓
6. BotManager processa resultado
   ├─ Extrai pix_code, qr_code_url, transaction_id
   ├─ Cria Payment no banco
   ├─ Salva gateway_transaction_id, gateway_hash, reference
   └─ Retorna resultado para o bot
   ↓
7. Bot exibe PIX para o usuário
   ├─ Mostra código PIX
   ├─ Mostra QR Code
   └─ Aguarda pagamento
```

### Exemplo de Código

```python
# bot_manager.py
def _generate_pix_payment(self, bot_id, amount, description, ...):
    # 1. Buscar bot e gateway
    bot = db.session.get(Bot, bot_id)
    gateway = Gateway.query.filter_by(
        user_id=bot.user_id,
        is_active=True,
        is_verified=True
    ).first()
    
    # 2. Preparar credenciais
    credentials = {
        'api_key': gateway.api_key,
        'product_hash': gateway.product_hash,
        'split_percentage': user_commission
    }
    
    # 3. Criar gateway via Factory
    payment_gateway = GatewayFactory.create_gateway(
        gateway_type=gateway.gateway_type,
        credentials=credentials
    )
    
    # 4. Gerar PIX
    pix_result = payment_gateway.generate_pix(
        amount=amount,
        description=description,
        payment_id=payment_id,
        customer_data={
            'name': customer_name,
            'email': customer_email,
            'phone': customer_user_id,
            'document': customer_user_id
        }
    )
    
    # 5. Salvar Payment no banco
    payment = Payment(
        bot_id=bot_id,
        payment_id=payment_id,
        amount=amount,
        status='pending',
        gateway_type=gateway.gateway_type,
        gateway_transaction_id=pix_result.get('transaction_id'),
        gateway_transaction_hash=pix_result.get('gateway_hash'),
        product_description=pix_result.get('pix_code')
    )
    db.session.add(payment)
    db.session.commit()
    
    # 6. Retornar resultado
    return pix_result
```

---

## 🔔 Fluxo de Processamento de Webhook

### Sequência Detalhada

```
1. Gateway envia webhook para /webhook/payment/{gateway_type}
   ↓
2. app.py: payment_webhook(gateway_type)
   ├─ Recebe dados do webhook (JSON ou form)
   ├─ Cria gateway com credenciais dummy
   ├─ Extrai producer_hash (multi-tenancy)
   └─ Processa webhook via adapter
   ↓
3. GatewayAdapter.process_webhook(data)
   ├─ Normaliza dados do webhook
   ├─ Chama gateway.process_webhook(data)
   ├─ Normaliza resposta
   └─ Retorna dict normalizado
   ↓
4. gateway.process_webhook(data)
   ├─ Extrai gateway_transaction_id
   ├─ Extrai status
   ├─ Mapeia status para formato interno
   ├─ Extrai amount
   ├─ Converte valor se necessário (centavos → reais)
   └─ Retorna dict normalizado
   ↓
5. Buscar Payment no banco (múltiplas chaves)
   ├─ Prioridade 1: gateway_transaction_id
   ├─ Prioridade 2: gateway_hash
   ├─ Prioridade 3: external_reference
   └─ Prioridade 4: amount + gateway_type + status pending (fallback)
   ↓
6. Atualizar Payment
   ├─ Atualiza status
   ├─ Se status == 'paid':
   │   ├─ Processa entregável
   │   ├─ Atualiza estatísticas
   │   └─ Envia notificação
   └─ Salva no banco
   ↓
7. Retornar 200 OK
```

### Exemplo de Código

```python
# app.py
@app.route('/webhook/payment/<string:gateway_type>', methods=['POST'])
@csrf.exempt
def payment_webhook(gateway_type):
    # 1. Receber dados do webhook
    data = request.get_json(silent=True)
    
    # 2. Criar gateway com credenciais dummy
    dummy_credentials = {'api_key': 'dummy'}
    gateway_instance = GatewayFactory.create_gateway(
        gateway_type, 
        dummy_credentials, 
        use_adapter=True
    )
    
    # 3. Extrair producer_hash (multi-tenancy)
    producer_hash = None
    if hasattr(gateway_instance, 'extract_producer_hash'):
        producer_hash = gateway_instance.extract_producer_hash(data)
    
    # 4. Processar webhook
    result = gateway_instance.process_webhook(data)
    
    # 5. Buscar Payment no banco
    payment = None
    if result:
        # Prioridade 1: gateway_transaction_id
        payment = Payment.query.filter_by(
            gateway_transaction_id=str(result.get('gateway_transaction_id'))
        ).first()
        
        # Prioridade 2: gateway_hash
        if not payment and result.get('gateway_hash'):
            payment = Payment.query.filter_by(
                gateway_transaction_hash=str(result.get('gateway_hash'))
            ).first()
        
        # Prioridade 3: external_reference
        if not payment and result.get('external_reference'):
            # Extrair payment_id do reference
            # ...
            payment = Payment.query.filter_by(payment_id=extracted_payment_id).first()
    
    # 6. Atualizar Payment
    if payment:
        payment.status = result.get('status')
        if result.get('status') == 'paid':
            # Processar entregável
            send_payment_delivery(payment, bot_manager)
            # Atualizar estatísticas
            payment.bot.total_sales += 1
            payment.bot.total_revenue += payment.amount
        db.session.commit()
    
    # 7. Retornar 200 OK
    return jsonify({'status': 'ok'}), 200
```

---

## 🗂️ Estrutura de Arquivos

### Arquivos Principais

```
grpay/
├── gateway_interface.py          # Interface PaymentGateway
├── gateway_factory.py            # Factory de gateways
├── gateway_adapter.py            # Adapter de normalização
├── gateway_syncpay.py            # Gateway SyncPay
├── gateway_pushyn.py             # Gateway PushynPay
├── gateway_paradise.py           # Gateway Paradise
├── gateway_wiinpay.py            # Gateway WiinPay
├── gateway_atomopay.py           # Gateway Átomo Pay
├── bot_manager.py                # Gerencia criação de pagamentos
├── app.py                        # Rotas e webhooks
├── models.py                     # Modelo Gateway
└── middleware/
    └── gateway_validator.py      # Validação de gateways
```

### Dependências

```
gateway_interface.py
    └── PaymentGateway (ABC)
        ├── generate_pix()
        ├── process_webhook()
        ├── verify_credentials()
        ├── get_payment_status()
        ├── get_webhook_url()
        ├── get_gateway_name()
        ├── get_gateway_type()
        └── extract_producer_hash() (opcional)

gateway_factory.py
    └── GatewayFactory
        ├── _gateway_classes (registry)
        ├── create_gateway()
        ├── get_available_gateways()
        ├── register_gateway()
        └── unregister_gateway()

gateway_adapter.py
    └── GatewayAdapter(PaymentGateway)
        ├── __init__(gateway)
        ├── generate_pix()
        ├── process_webhook()
        ├── _normalize_generate_response()
        └── _normalize_webhook_response()

gateway_*.py
    └── *Gateway(PaymentGateway)
        ├── __init__(credentials)
        ├── generate_pix()
        ├── process_webhook()
        ├── verify_credentials()
        ├── get_payment_status()
        ├── get_webhook_url()
        ├── get_gateway_name()
        └── get_gateway_type()
```

---

## 📋 Tabela de Comparação de Gateways

### Características Técnicas

| Gateway | Autenticação | Valores | Split | Webhook | Valor Mínimo | Multi-Tenancy |
|---------|-------------|---------|-------|---------|--------------|---------------|
| SyncPay | Bearer Token | Reais | % | `data` wrapper | N/A | ❌ |
| PushynPay | Bearer Token | Centavos | Valor fixo (50%) | Direto | R$ 0,50 | ❌ |
| Paradise | X-API-Key | Centavos | Valor fixo | Direto | R$ 0,01 | ❌ |
| WiinPay | api_key (body) | Reais | % ou fixo | Direto | R$ 3,00 | ❌ |
| Átomo Pay | api_token (query) | Centavos | N/A | Múltiplos formatos | R$ 0,50 | ✅ |

### Credenciais Obrigatórias

| Gateway | Credenciais Obrigatórias | Credenciais Opcionais |
|---------|-------------------------|----------------------|
| SyncPay | `client_id`, `client_secret` | `split_user_id`, `split_percentage` |
| PushynPay | `api_key` | `split_account_id`, `split_percentage` |
| Paradise | `api_key`, `product_hash` | `offer_hash`, `store_id`, `split_percentage` |
| WiinPay | `api_key` | `split_user_id`, `split_percentage` |
| Átomo Pay | `api_token` | `product_hash`, `offer_hash` |

### Formato de Webhook

| Gateway | Formato do Webhook | Campos Principais |
|---------|-------------------|-------------------|
| SyncPay | `{data: {id, status, amount, external_reference}}` | `id`, `status`, `amount`, `external_reference` |
| PushynPay | `{id, status, value, payer_name, payer_national_registration}` | `id`, `status`, `value`, `payer_name` |
| Paradise | `{id, payment_status, amount}` | `id`, `payment_status`, `amount` |
| WiinPay | `{id, status, value, payer_name, payer_document}` | `id`, `status`, `value`, `payer_name` |
| Átomo Pay | `{id, hash, payment_status, amount, producer, reference}` | `id`, `hash`, `payment_status`, `amount`, `producer.hash`, `reference` |

---

## 🔍 Padrões de Implementação

### 1. Validação de Valores

```python
def generate_pix(self, amount: float, ...):
    # Validar valor
    if not isinstance(amount, (int, float)) or amount <= 0:
        logger.error(f"❌ Valor inválido: {amount}")
        return None
    
    # Verificar NaN e infinito
    if isinstance(amount, float) and (amount != amount or amount == float('inf')):
        logger.error(f"❌ Valor inválido: NaN ou infinito")
        return None
    
    # Validar valor mínimo/máximo (se aplicável)
    if amount < 3.0:  # Exemplo: WiinPay
        logger.error(f"❌ Valor mínimo é R$ 3,00")
        return None
```

### 2. Conversão de Valores

```python
def generate_pix(self, amount: float, ...):
    # Converter reais para centavos (se necessário)
    amount_cents = int(amount * 100)
    
    # Fazer requisição com centavos
    payload = {'amount': amount_cents}
    
    # ...

def process_webhook(self, data: Dict[str, Any]):
    # Converter centavos para reais (se necessário)
    amount_cents = data.get('amount', 0)
    amount = float(amount_cents) / 100.0
    
    return {
        'amount': amount  # Em reais
    }
```

### 3. Mapeamento de Status

```python
def process_webhook(self, data: Dict[str, Any]):
    status_raw = data.get('status', '').lower()
    
    # Mapear status para formato interno
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
    
    return {
        'status': status
    }
```

### 4. Dados Únicos por Transação

```python
def generate_pix(self, amount: float, description: str, payment_id: str, customer_data: Optional[Dict[str, Any]] = None):
    import time
    import hashlib
    
    # Gerar timestamp único
    timestamp_ms = int(time.time() * 1000)
    
    # Gerar hash único
    unique_hash = hashlib.md5(
        f"{payment_id}_{timestamp_ms}_{customer_user_id}".encode()
    ).hexdigest()[:8]
    
    # Gerar email único
    unique_email = f"pix{payment_id[:10]}{unique_hash}@bot.digital"
    
    # Gerar CPF único (se necessário)
    unique_cpf = f"{unique_hash}{payment_id[:6]}".zfill(11)
    
    # Gerar telefone único
    unique_phone = f"11{unique_hash[:9]}"
    
    # Gerar reference único
    reference_hash = hashlib.md5(
        f"{payment_id}_{timestamp_ms}_{unique_hash}".encode()
    ).hexdigest()[:8]
    safe_reference = f"{payment_id}-{timestamp_ms}-{reference_hash}"
    
    # Usar dados únicos no payload
    payload = {
        'customer': {
            'name': customer_data.get('name') or 'Cliente',
            'email': unique_email,
            'phone': unique_phone,
            'document': unique_cpf
        },
        'reference': safe_reference
    }
```

### 5. Multi-Tenancy (Átomo Pay)

```python
def extract_producer_hash(self, webhook_data: Dict[str, Any]) -> Optional[str]:
    # Formato 1: producer.hash direto
    if 'producer' in webhook_data and isinstance(webhook_data['producer'], dict):
        return webhook_data['producer'].get('hash')
    
    # Formato 2: offer.producer.hash
    if 'offer' in webhook_data and isinstance(webhook_data['offer'], dict):
        offer_producer = webhook_data['offer'].get('producer', {})
        if isinstance(offer_producer, dict):
            return offer_producer.get('hash')
    
    return None

def generate_pix(self, ...):
    # ...
    # Salvar producer_hash no Gateway
    if pix_result.get('producer_hash'):
        gateway.producer_hash = pix_result.get('producer_hash')
        db.session.commit()
```

---

## 🎯 Casos de Uso

### Caso 1: Criar Pagamento com SyncPay

```python
# 1. Buscar gateway
gateway = Gateway.query.filter_by(
    user_id=user_id,
    gateway_type='syncpay',
    is_active=True,
    is_verified=True
).first()

# 2. Preparar credenciais
credentials = {
    'client_id': gateway.client_id,
    'client_secret': gateway.client_secret,
    'split_user_id': gateway.split_user_id,
    'split_percentage': 2.0
}

# 3. Criar gateway
payment_gateway = GatewayFactory.create_gateway('syncpay', credentials)

# 4. Gerar PIX
pix_result = payment_gateway.generate_pix(
    amount=10.50,
    description='Produto de teste',
    payment_id='BOT1_1234567890_abc123',
    customer_data={
        'name': 'João Silva',
        'email': 'joao@example.com',
        'phone': '11999999999',
        'document': '12345678900'
    }
)

# 5. Resultado
# {
#     'pix_code': '00020126820014br.gov.bcb.pix...',
#     'qr_code_url': 'https://api.qrserver.com/v1/create-qr-code/...',
#     'transaction_id': '3df0319d-ecf7-455a-84c4-070aee2779c1',
#     'payment_id': 'BOT1_1234567890_abc123'
# }
```

### Caso 2: Processar Webhook do Paradise

```python
# 1. Receber webhook
data = {
    'id': 'BOT-BOT5_1761860711_cf29c4f3',
    'payment_status': 'approved',
    'amount': 1990  # centavos
}

# 2. Criar gateway
dummy_credentials = {'api_key': 'dummy', 'product_hash': 'dummy'}
gateway_instance = GatewayFactory.create_gateway('paradise', dummy_credentials)

# 3. Processar webhook
result = gateway_instance.process_webhook(data)

# 4. Resultado
# {
#     'gateway_transaction_id': 'BOT-BOT5_1761860711_cf29c4f3',
#     'status': 'paid',
#     'amount': 19.90  # convertido para reais
# }

# 5. Buscar Payment
payment = Payment.query.filter_by(
    gateway_transaction_id='BOT-BOT5_1761860711_cf29c4f3'
).first()

# 6. Atualizar Payment
payment.status = 'paid'
payment.paid_at = get_brazil_time()
db.session.commit()
```

### Caso 3: Multi-Tenancy com Átomo Pay

```python
# 1. Gerar PIX
pix_result = payment_gateway.generate_pix(...)

# 2. Resultado inclui producer_hash
# {
#     'pix_code': '...',
#     'transaction_id': '123',
#     'producer_hash': 'prod_abc123'
# }

# 3. Salvar producer_hash no Gateway
gateway.producer_hash = pix_result.get('producer_hash')
db.session.commit()

# 4. Webhook recebido
webhook_data = {
    'id': '123',
    'payment_status': 'paid',
    'amount': 1990,
    'producer': {
        'hash': 'prod_abc123'
    }
}

# 5. Extrair producer_hash
producer_hash = gateway_instance.extract_producer_hash(webhook_data)
# producer_hash = 'prod_abc123'

# 6. Buscar Gateway pelo producer_hash
gateway = Gateway.query.filter_by(
    gateway_type='atomopay',
    producer_hash=producer_hash
).first()

# 7. Filtrar Payments do usuário correto
user_bot_ids = [b.id for b in Bot.query.filter_by(user_id=gateway.user_id).all()]
payment = Payment.query.filter(
    Payment.bot_id.in_(user_bot_ids),
    Payment.gateway_transaction_id == '123'
).first()
```

---

## 📊 Estatísticas e Monitoramento

### Modelo `Gateway`

```python
class Gateway(db.Model):
    # Estatísticas
    total_transactions = db.Column(db.Integer, default=0)
    successful_transactions = db.Column(db.Integer, default=0)
    
    # Status
    is_active = db.Column(db.Boolean, default=True)
    is_verified = db.Column(db.Boolean, default=False)
    last_error = db.Column(db.Text)
```

### Atualização de Estatísticas

```python
# No webhook, quando status vira 'paid':
if payment.status != 'paid' and result.get('status') == 'paid':
    # Atualizar estatísticas do bot
    payment.bot.total_sales += 1
    payment.bot.total_revenue += payment.amount
    
    # Atualizar estatísticas do usuário
    payment.bot.owner.total_sales += 1
    payment.bot.owner.total_revenue += payment.amount
    
    # Atualizar estatísticas do gateway
    gateway.total_transactions += 1
    gateway.successful_transactions += 1
    
    db.session.commit()
```

---

## 🔐 Segurança

### Criptografia de Credenciais

```python
# models.py
@property
def api_key(self):
    """Descriptografa api_key ao acessar"""
    if not self._api_key:
        return None
    from utils.encryption import decrypt
    return decrypt(self._api_key)

@api_key.setter
def api_key(self, value):
    """Criptografa api_key ao armazenar"""
    if not value:
        self._api_key = None
    else:
        from utils.encryption import encrypt
        self._api_key = encrypt(value)
```

### Validação de Webhooks

```python
# app.py
@app.route('/webhook/payment/<string:gateway_type>', methods=['POST'])
@limiter.limit("500 per minute")  # Rate limiting
@csrf.exempt  # CSRF exempt para webhooks externos
def payment_webhook(gateway_type):
    # Validar gateway_type
    valid_types = ['syncpay', 'pushynpay', 'paradise', 'wiinpay', 'atomopay']
    if gateway_type not in valid_types:
        return jsonify({'error': 'Gateway inválido'}), 400
    
    # Processar webhook
    # ...
```

---

## 📚 Documentação Adicional

- **REQUISITOS_GATEWAYS.md**: Documentação completa de requisitos
- **GUIA_RAPIDO_GATEWAYS.md**: Guia rápido de implementação
- **RESUMO_EXECUTIVO_GATEWAYS.md**: Resumo executivo
- **gateway_interface.py**: Interface obrigatória
- **gateway_factory.py**: Factory de gateways
- **gateway_adapter.py**: Adapter de normalização

---

**Última atualização**: 2024-11-12
**Versão**: 1.0
**Autor**: Sistema de Requisitos - Gateways

