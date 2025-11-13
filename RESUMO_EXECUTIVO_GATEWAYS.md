# Resumo Executivo - Sistema Multi-Gateway

## 📊 Visão Geral

O sistema suporta **5 gateways de pagamento** simultaneamente, permitindo que cada usuário configure um ou mais gateways. A arquitetura foi projetada para **isolamento completo**, **extensibilidade** e **normalização** de dados.

---

## 🏗️ Arquitetura

### Componentes Principais

```
┌─────────────────────────────────────────────────────────────┐
│                    BotManager                                │
│  - Gerencia criação de pagamentos                           │
│  - Usa GatewayFactory para criar instâncias                 │
│  - Processa resultados e salva no banco                     │
└────────────────────┬────────────────────────────────────────┘
                     │
                     ▼
┌─────────────────────────────────────────────────────────────┐
│                  GatewayFactory                              │
│  - Registry de gateways disponíveis                         │
│  - Cria instâncias com credenciais específicas              │
│  - Envolve com GatewayAdapter (padrão)                      │
└────────────────────┬────────────────────────────────────────┘
                     │
                     ▼
┌─────────────────────────────────────────────────────────────┐
│                  GatewayAdapter                              │
│  - Normaliza entrada/saída de todos os gateways             │
│  - Tratamento de erros uniforme                             │
│  - Logging consistente                                       │
└────────────────────┬────────────────────────────────────────┘
                     │
        ┌────────────┼────────────┬────────────┬────────────┐
        ▼            ▼            ▼            ▼            ▼
   ┌────────┐  ┌─────────┐  ┌──────────┐  ┌──────────┐  ┌──────────┐
   │SyncPay │  │PushynPay│  │Paradise  │  │WiinPay   │  │AtomoPay  │
   │Gateway │  │Gateway  │  │Gateway   │  │Gateway   │  │Gateway   │
   └────────┘  └─────────┘  └──────────┘  └──────────┘  └──────────┘
```

### Padrões de Design

- **Strategy Pattern**: Interface `PaymentGateway` define o contrato
- **Factory Pattern**: `GatewayFactory` cria instâncias de gateways
- **Adapter Pattern**: `GatewayAdapter` normaliza dados entre gateways
- **Template Method Pattern**: Métodos abstratos definidos na interface

---

## 🔌 Gateways Disponíveis

### 1. SyncPay

**Características**:
- Autenticação: Bearer Token (client_id + client_secret)
- Valores: Reais (float)
- Split: Percentual (1-100%)
- Webhook: POST com dados em `data` wrapper

**Credenciais**:
- `client_id`: UUID do client ID
- `client_secret`: UUID do client secret
- `split_user_id`: UUID do usuário para split (opcional)
- `split_percentage`: Percentual de split (opcional)

**Endpoints**:
- `POST /api/partner/v1/cash-in`: Criar pagamento PIX
- `POST /api/partner/v1/auth-token`: Gerar Bearer Token

**Webhook**:
- Formato: `{data: {id, status, amount, external_reference}}`
- Status: `PAID_OUT`, `CANCELLED`, `EXPIRED`, `PENDING`

---

### 2. PushynPay

**Características**:
- Autenticação: Bearer Token (API Key)
- Valores: Centavos (int)
- Split: Valor fixo (máximo 50%)
- Webhook: POST com status direto

**Credenciais**:
- `api_key`: API Key da Pushyn
- `split_account_id`: Account ID para split (opcional)
- `split_percentage`: Percentual de split (opcional)

**Endpoints**:
- `POST /api/pix/cashIn`: Criar pagamento PIX
- `GET /api/transactions/{id}`: Consultar status

**Webhook**:
- Formato: `{id, status, value, payer_name, payer_national_registration}`
- Status: `paid`, `pending`, `expired`

---

### 3. Paradise

**Características**:
- Autenticação: X-API-Key (Secret Key)
- Valores: Centavos (int)
- Split: Valor fixo (via store_id)
- Webhook: POST com status direto

**Credenciais**:
- `api_key`: Secret Key (sk_...)
- `product_hash`: Código do produto (prod_...)
- `offer_hash`: ID da oferta (opcional - não enviado)
- `store_id`: ID da conta para split
- `split_percentage`: Percentual de split (padrão 2%)

**Endpoints**:
- `POST /api/v1/transaction.php`: Criar pagamento PIX
- `GET /api/v1/check_status.php?hash={id}`: Consultar status

**Webhook**:
- Formato: `{id, payment_status, amount}`
- Status: `approved`, `paid`, `pending`, `refunded`

**Observações**:
- ✅ Dados únicos por transação (email, CPF, telefone, nome)
- ✅ Reference único (timestamp + hash)
- ❌ Não enviar offerHash para evitar duplicação

---

### 4. WiinPay

**Características**:
- Autenticação: api_key no body
- Valores: Reais (float)
- Split: Percentual OU valor fixo
- Webhook: POST com status direto
- Valor mínimo: R$ 3,00

**Credenciais**:
- `api_key`: Chave API da WiinPay
- `split_user_id`: User ID para split (opcional)
- `split_percentage`: Percentual de split (opcional)

**Endpoints**:
- `POST /payment/create`: Criar pagamento PIX
- `GET /payment/{id}`: Consultar status

**Webhook**:
- Formato: `{id, status, value, payer_name, payer_document}`
- Status: `paid`, `pending`, `cancelled`

---

### 5. Átomo Pay

**Características**:
- Autenticação: api_token como query parameter
- Valores: Centavos (int)
- Multi-tenancy: Suporta producer_hash
- Webhook: POST com dados em múltiplos formatos

**Credenciais**:
- `api_token`: Token de API
- `product_hash`: Hash do produto (obrigatório para criar ofertas)
- `offer_hash`: Hash da oferta (opcional - criado dinamicamente)

**Endpoints**:
- `POST /api/public/v1/transactions`: Criar pagamento PIX
- `GET /api/public/v1/transactions/{id}`: Consultar status
- `GET /api/public/v1/products`: Listar produtos
- `POST /api/public/v1/products/{hash}/offers`: Criar oferta

**Webhook**:
- Formato: `{id, hash, payment_status, amount, producer, reference}`
- Status: `paid`, `pending`, `refused`, `failed`

**Observações**:
- ✅ Dados únicos por transação (email, CPF, telefone, nome)
- ✅ Reference único (timestamp + hash)
- ✅ Ofertas criadas dinamicamente (evita conflitos de valor)
- ✅ Multi-tenancy via producer_hash
- ✅ product_hash obrigatório (criado dinamicamente se não existir)

---

## 📋 Comparação de Gateways

| Gateway | Autenticação | Valores | Split | Webhook | Valor Mínimo | Multi-Tenancy |
|---------|-------------|---------|-------|---------|--------------|---------------|
| SyncPay | Bearer Token | Reais | % | `data` wrapper | N/A | ❌ |
| PushynPay | Bearer Token | Centavos | Valor fixo (50%) | Direto | R$ 0,50 | ❌ |
| Paradise | X-API-Key | Centavos | Valor fixo | Direto | R$ 0,01 | ❌ |
| WiinPay | api_key (body) | Reais | % ou fixo | Direto | R$ 3,00 | ❌ |
| Átomo Pay | api_token (query) | Centavos | N/A | Múltiplos formatos | R$ 0,50 | ✅ |

---

## 🔄 Fluxo de Criação de Pagamento

```
1. BotManager._generate_pix_payment()
   ↓
2. Busca Gateway no banco (models.Gateway)
   ↓
3. GatewayFactory.create_gateway(gateway_type, credentials)
   ↓
4. GatewayAdapter(gateway) - envolve o gateway
   ↓
5. gateway.generate_pix(amount, description, payment_id, customer_data)
   ↓
6. Retorna dict normalizado: {pix_code, qr_code_url, transaction_id, ...}
   ↓
7. BotManager salva Payment no banco
```

---

## 🔔 Fluxo de Processamento de Webhook

```
1. app.py: payment_webhook(gateway_type)
   ↓
2. GatewayFactory.create_gateway(gateway_type, dummy_credentials)
   ↓
3. gateway.process_webhook(data)
   ↓
4. Retorna dict normalizado: {gateway_transaction_id, status, amount, ...}
   ↓
5. Busca Payment no banco (por gateway_transaction_id, hash, reference)
   ↓
6. Atualiza status e processa entregável
```

---

## 🎯 Padrões de Retorno

### `generate_pix()` - Formato Padronizado:
```python
{
    'pix_code': str,              # OBRIGATÓRIO
    'qr_code_url': str,           # OBRIGATÓRIO
    'transaction_id': str,        # OBRIGATÓRIO
    'payment_id': str,            # OBRIGATÓRIO
    'gateway_hash': str,          # RECOMENDADO (para webhook matching)
    'reference': str,             # RECOMENDADO (para webhook matching)
    'producer_hash': str,         # OPCIONAL (multi-tenancy)
    'qr_code_base64': str,        # OPCIONAL
    'expires_at': datetime        # OPCIONAL
}
```

### `process_webhook()` - Formato Padronizado:
```python
{
    'gateway_transaction_id': str,  # OBRIGATÓRIO
    'status': str,                  # OBRIGATÓRIO ('pending', 'paid', 'failed')
    'amount': float,                # OBRIGATÓRIO
    'gateway_hash': str,            # RECOMENDADO (para webhook matching)
    'external_reference': str,      # RECOMENDADO (para webhook matching)
    'producer_hash': str,           # OPCIONAL (multi-tenancy)
    'payer_name': str,              # OPCIONAL
    'payer_document': str,          # OPCIONAL
    'end_to_end_id': str            # OPCIONAL
}
```

---

## 🔍 Busca de Payment no Webhook

O sistema busca o `Payment` por múltiplas chaves (prioridade):

1. **gateway_transaction_id**: ID da transação no gateway
2. **gateway_hash**: Hash da transação
3. **external_reference**: Reference externo (pode conter payment_id)
4. **amount + gateway_type + status pending**: Fallback (últimos 10 pagamentos)

---

## 🏢 Multi-Tenancy

Gateways que suportam multi-tenancy (ex: Átomo Pay) devem:

1. **Extrair producer_hash do webhook**:
   ```python
   def extract_producer_hash(self, webhook_data: Dict[str, Any]) -> Optional[str]:
       producer_data = webhook_data.get('producer', {})
       if isinstance(producer_data, dict):
           return producer_data.get('hash')
       return None
   ```

2. **Salvar producer_hash no Gateway**:
   ```python
   # No generate_pix(), salvar producer_hash no Gateway
   if pix_result.get('producer_hash'):
       gateway.producer_hash = pix_result.get('producer_hash')
       db.session.commit()
   ```

3. **Filtrar por producer_hash no webhook**:
   ```python
   # No payment_webhook(), filtrar por producer_hash
   if producer_hash:
       gateway = Gateway.query.filter_by(
           gateway_type=gateway_type,
           producer_hash=producer_hash
       ).first()
       if gateway:
           # Filtrar Payments do usuário correto
           user_bot_ids = [b.id for b in Bot.query.filter_by(user_id=gateway.user_id).all()]
           payment_query = payment_query.filter(Payment.bot_id.in_(user_bot_ids))
   ```

---

## 🔐 Segurança

### Criptografia de Credenciais

Credenciais sensíveis são criptografadas automaticamente no modelo `Gateway`:

```python
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

- ✅ Rate limiting: 500 webhooks/minuto
- ✅ CSRF exempt: Webhooks externos não enviam CSRF token
- ✅ Validação de gateway_type: Apenas gateways válidos
- ✅ Logging: Todos os webhooks são registrados

---

## 📊 Estatísticas

### Modelo `Gateway`:
- `total_transactions`: Total de transações
- `successful_transactions`: Transações bem-sucedidas
- `is_active`: Gateway ativo
- `is_verified`: Gateway verificado
- `last_error`: Último erro (se houver)

### Atualização de Estatísticas:
```python
# No webhook, quando status vira 'paid':
payment.bot.total_sales += 1
payment.bot.total_revenue += payment.amount
payment.bot.owner.total_sales += 1
payment.bot.owner.total_revenue += payment.amount
gateway.total_transactions += 1
gateway.successful_transactions += 1
```

---

## 🚀 Como Adicionar Novo Gateway

### Passos Básicos:

1. **Criar arquivo `gateway_novogateway.py`**
2. **Implementar interface `PaymentGateway`**
3. **Registrar no `GatewayFactory`**
4. **Adicionar ao middleware**
5. **Testar criação de pagamento e processamento de webhook**

### Documentação Completa:

Ver `REQUISITOS_GATEWAYS.md` para documentação completa.

### Guia Rápido:

Ver `GUIA_RAPIDO_GATEWAYS.md` para guia rápido de implementação.

---

## 📝 Observações Importantes

### 1. Dados Únicos por Transação

Alguns gateways (ex: Paradise, Átomo Pay) requerem dados únicos por transação:
- ✅ Email único (timestamp + hash)
- ✅ CPF único (timestamp + hash)
- ✅ Telefone único (timestamp + hash)
- ✅ Nome único (timestamp + hash)
- ✅ Reference único (timestamp + hash)

### 2. Validações Específicas

Alguns gateways têm validações específicas:
- ✅ WiinPay: Valor mínimo R$ 3,00
- ✅ PushynPay: Valor mínimo R$ 0,50
- ✅ Paradise: Valor mínimo R$ 0,01
- ✅ Átomo Pay: Valor mínimo R$ 0,50

### 3. Split Payment

Alguns gateways suportam split payment:
- ✅ SyncPay: Percentual (1-100%)
- ✅ PushynPay: Valor fixo (máximo 50%)
- ✅ Paradise: Valor fixo (via store_id)
- ✅ WiinPay: Percentual OU valor fixo
- ❌ Átomo Pay: Não suporta split

### 4. Multi-Tenancy

Apenas Átomo Pay suporta multi-tenancy:
- ✅ Extrai producer_hash do webhook
- ✅ Salva producer_hash no Gateway
- ✅ Filtra por producer_hash no webhook

---

## 🔧 Configuração

### Variáveis de Ambiente:

```bash
# Webhook URL (obrigatório)
WEBHOOK_URL=https://seu-dominio.com

# Split Payment (opcional)
PLATFORM_SPLIT_USER_ID=uuid-do-usuario
PUSHYN_SPLIT_ACCOUNT_ID=account-id
WIINPAY_PLATFORM_USER_ID=user-id
PARADISE_STORE_ID=store-id

# URLs dos gateways (opcional - usa padrão se não configurado)
SYNCPAY_API_URL=https://api.syncpayments.com.br
PUSHYN_API_URL=https://api.pushinpay.com.br
NOVOGATEWAY_API_URL=https://api.novogateway.com.br
```

---

## 📚 Documentação Adicional

- **REQUISITOS_GATEWAYS.md**: Documentação completa de requisitos
- **GUIA_RAPIDO_GATEWAYS.md**: Guia rápido de implementação
- **gateway_interface.py**: Interface obrigatória
- **gateway_factory.py**: Factory de gateways
- **gateway_adapter.py**: Adapter de normalização

---

**Última atualização**: 2024-11-12
**Versão**: 1.0
**Autor**: Sistema de Requisitos - Gateways

