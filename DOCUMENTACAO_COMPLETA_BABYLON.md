# 📚 DOCUMENTAÇÃO COMPLETA - GATEWAY BABYLON

**Data:** 2025-01-27  
**Status:** ✅ Implementado e Funcional  
**Gateway Type:** `babylon`

---

## 📋 SUMÁRIO

1. [Visão Geral](#visão-geral)
2. [Arquitetura e Implementação](#arquitetura-e-implementação)
3. [Configuração e Credenciais](#configuração-e-credenciais)
4. [API e Endpoints](#api-e-endpoints)
5. [Geração de PIX](#geração-de-pix)
6. [Processamento de Webhook](#processamento-de-webhook)
7. [Consulta de Status](#consulta-de-status)
8. [Integração no Sistema](#integração-no-sistema)
9. [Interface do Usuário](#interface-do-usuário)
10. [Características Técnicas](#características-técnicas)

---

## 🎯 VISÃO GERAL

O **Babylon Gateway** é um gateway de pagamento PIX integrado ao sistema GRPay. Implementa a interface `PaymentGateway` e utiliza o padrão Adapter para normalização de dados.

**Características Principais:**
- ✅ Autenticação via Bearer Token (API Key)
- ✅ Geração de PIX com QR Code
- ✅ Webhook para confirmação de pagamento
- ✅ Suporte a Split Payment (opcional)
- ✅ Valores em centavos
- ✅ Expiração configurável (1-7 dias)

---

## 🏗️ ARQUITETURA E IMPLEMENTAÇÃO

### Arquivo Principal
**Localização:** `gateway_babylon.py`

### Classe Principal
```python
class BabylonGateway(PaymentGateway):
    """Implementação do gateway Babylon"""
```

### Factory Pattern
**Localização:** `gateway_factory.py`

```38:38:gateway_factory.py
        'babylon': BabylonGateway,  # ✅ Babylon
```

### Adapter Pattern
O gateway é envolvido pelo `GatewayAdapter` para normalização de dados:

```211:225:gateway_factory.py
            elif gateway_type == 'babylon':
                # ✅ Babylon requer: api_key
                api_key = credentials.get('api_key')
                split_percentage = credentials.get('split_percentage', 2.0)
                split_user_id = credentials.get('split_user_id', '')
                
                if not api_key:
                    logger.error(f"❌ [Factory] Babylon requer api_key")
                    return None
                
                gateway = gateway_class(
                    api_key=api_key,
                    split_percentage=split_percentage,
                    split_user_id=split_user_id if split_user_id else None
                )
```

---

## ⚙️ CONFIGURAÇÃO E CREDENCIAIS

### Credenciais Obrigatórias

| Campo | Tipo | Obrigatório | Descrição |
|-------|------|-------------|-----------|
| `api_key` | string | ✅ Sim | API Key do Babylon (Bearer Token) |

### Credenciais Opcionais

| Campo | Tipo | Padrão | Descrição |
|-------|------|--------|-----------|
| `split_percentage` | float | 2.0 | Percentual de split (comissão da plataforma) |
| `split_user_id` | string | None | ID do recipient para split payment |

### Variáveis de Ambiente

| Variável | Padrão | Descrição |
|----------|--------|-----------|
| `BABYLON_API_URL` | `https://api.bancobabylon.com/functions/v1` | URL base da API |
| `WEBHOOK_URL` | (vazio) | URL base para webhooks |

### Validação de Credenciais

```409:430:gateway_babylon.py
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
```

**⚠️ Nota:** A validação atual é apenas de formato. Se a API fornecer endpoint de verificação, deve ser implementado.

---

## 🌐 API E ENDPOINTS

### Base URL
```
https://api.bancobabylon.com/functions/v1
```

### Endpoints Utilizados

#### 1. Gerar PIX
- **Método:** `POST`
- **Endpoint:** `/transactions`
- **Status Esperado:** `201 Created`
- **Autenticação:** `Bearer {api_key}`

#### 2. Consultar Status
- **Método:** `GET`
- **Endpoint:** `/transactions/{id}`
- **Status Esperado:** `200 OK`
- **Autenticação:** `Bearer {api_key}`

#### 3. Webhook
- **Método:** `POST`
- **URL:** `{WEBHOOK_URL}/webhook/payment/babylon`
- **Content-Type:** `application/json`

---

## 💰 GERAÇÃO DE PIX

### Método: `generate_pix()`

**Assinatura:**
```python
def generate_pix(
    self, 
    amount: float, 
    description: str, 
    payment_id: str,
    customer_data: Optional[Dict[str, Any]] = None
) -> Optional[Dict[str, Any]]
```

### Validações

1. **Valor Mínimo:** R$ 1,00 (100 centavos)
2. **Valor em Centavos:** Conversão automática
3. **Expiração:** 1 a 7 dias (padrão: 1 dia)

### Payload da Requisição

```json
{
  "customer": {
    "name": "Nome do Cliente",
    "email": "cliente@email.com",
    "phone": "11999999999",
    "document": {
      "number": "00000000000",
      "type": "CPF"  // ou "CNPJ" se 14 dígitos
    }
  },
  "paymentMethod": "PIX",
  "amount": 10000,  // em centavos
  "items": [
    {
      "title": "Descrição do Produto",
      "unitPrice": 10000,
      "quantity": 1,
      "externalRef": "payment_id_123"  // opcional
    }
  ],
  "pix": {
    "expiresInDays": 1  // 1 a 7 dias
  },
  "postbackUrl": "https://.../webhook/payment/babylon",
  "description": "Descrição completa"  // opcional
}
```

### Split Payment (Opcional)

Se `split_user_id` e `split_percentage > 0` estiverem configurados:

```json
{
  "split": [
    {
      "recipientId": "user_id_123",
      "amount": 200  // em centavos (2% de R$ 100,00)
    }
  ]
}
```

**Regras de Split:**
- Mínimo: 1 centavo
- Máximo: valor total - 1 centavo (garante que sobra pelo menos 1 centavo para o vendedor)

### Resposta de Sucesso (201 Created)

```json
{
  "id": "28a65292-6c74-4368-924d-f52a653706be",
  "status": "pending",
  "pix": {
    "copyPaste": "00020126...",  // Código PIX copia e cola
    "emv": "00020126...",         // Código EMV
    "qrcode": "https://...",      // URL do QR Code (pode ser URL ou código)
    "expirationDate": "2025-04-03T16:19:43-03:00",
    "end2EndId": "E12345678202009091221abcdef12345"
  }
}
```

### Extração do Código PIX

O sistema tenta extrair o código PIX na seguinte ordem de prioridade:

1. `pix.copyPaste` (código copia e cola)
2. `pix.emv` (código EMV)
3. `pix.qrcode` (pode ser URL ou código)

**⚠️ Tratamento Especial:** Se `qrcode` for uma URL, o sistema tenta extrair de campos alternativos. Se não encontrar, usa a URL como fallback.

### Resposta Normalizada

```python
{
    'pix_code': '00020126...',  # Código PIX ou URL
    'qr_code_url': 'https://api.qrserver.com/v1/create-qr-code/?size=400x400&data=...',
    'qr_code_base64': None,  # Não implementado
    'transaction_id': '28a65292-6c74-4368-924d-f52a653706be',
    'payment_id': 'payment_id_123',
    'expires_at': datetime(2025, 4, 3, 16, 19, 43)  # datetime object
}
```

### Tratamento de Erros

- **400 Bad Request:** Payload inválido
- **401 Unauthorized:** API Key inválida
- **500 Internal Server Error:** Erro no servidor Babylon
- **Timeout:** 15 segundos

---

## 📥 PROCESSAMENTO DE WEBHOOK

### Método: `process_webhook()`

**Assinatura:**
```python
def process_webhook(self, data: Dict[str, Any]) -> Optional[Dict[str, Any]]
```

### Estrutura do Webhook

```json
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
```

### Mapeamento de Status

| Status Babylon | Status Interno | Descrição |
|----------------|----------------|-----------|
| `paid` | `paid` | Pagamento confirmado |
| `waiting_payment` | `pending` | Aguardando pagamento |
| `refused` | `failed` | Recusado |
| `canceled` | `failed` | Cancelado |
| `refused` | `failed` | Recusado |
| `refunded` | `failed` | Estornado |
| `chargedback` | `failed` | Chargeback |
| `failed` | `failed` | Falhou |
| `expired` | `failed` | Expirado |
| `in_analisys` | `pending` | Em análise |
| `in_protest` | `pending` | Em protesto |

### Identificação da Transação

O sistema tenta identificar a transação na seguinte ordem:

1. `payload.objectId`
2. `payload.data.id`
3. `payload.id` (fallback)

### Busca de Payment no Banco de Dados

Após processar o webhook, o sistema busca o Payment no banco usando múltiplas estratégias (prioridade):

1. **PRIORIDADE 1:** `gateway_transaction_id` (campo `gateway_transaction_id` do Payment)
2. **PRIORIDADE 2:** `gateway_hash` (campo `gateway_transaction_hash` do Payment)
3. **PRIORIDADE 3:** `payment_id` (usando `gateway_transaction_id` como fallback)
4. **PRIORIDADE 4:** `external_reference` (busca parcial e completa)

**Nota:** Para gateways com `producer_hash`, o sistema filtra Payments apenas do usuário correto para evitar conflitos.

### Dados Extraídos

```python
{
    'payment_id': '28a65292-6c74-4368-924d-f52a653706be',
    'status': 'paid',  # mapeado
    'amount': 100.00,  # convertido de centavos para reais
    'gateway_transaction_id': '28a65292-6c74-4368-924d-f52a653706be',
    'payer_name': 'TESTE PIX',
    'payer_document': '01234567890',
    'end_to_end_id': 'E12345678202009091221abcdef12345',
    'raw_status': 'paid',
    'raw_data': {...},  # payload completo
    'paid_at': '2025-04-03T15:59:43.56-03:00'
}
```

---

## 🔍 CONSULTA DE STATUS

### Método: `get_payment_status()`

**Assinatura:**
```python
def get_payment_status(self, transaction_id: str) -> Optional[Dict[str, Any]]
```

### Endpoint
```
GET https://api.bancobabylon.com/functions/v1/transactions/{transaction_id}
```

### Processamento

A resposta do GET `/transactions/{id}` tem a mesma estrutura do webhook. O sistema reutiliza `process_webhook()` para manter consistência.

### Códigos de Status HTTP

| Status | Descrição | Ação |
|--------|-----------|------|
| `200 OK` | Transação encontrada | Processa resposta |
| `401 Unauthorized` | Credenciais inválidas | Retorna None |
| `404 Not Found` | Transação não encontrada | Retorna None |
| `500 Internal Server Error` | Erro no servidor | Retorna None |

### Timeout
- **10 segundos**

---

## 🔗 INTEGRAÇÃO NO SISTEMA

### 1. Bot Manager

**Localização:** `bot_manager.py`

Validação de credenciais:

```6816:6821:bot_manager.py
                elif gateway.gateway_type in ['pushynpay', 'wiinpay', 'babylon']:
                    if not api_key:
                        logger.error(f"❌ {gateway.gateway_type.upper()}: api_key ausente ou não descriptografado")
                        logger.error(f"   Gateway ID: {gateway.id} | User: {gateway.user_id} | Tipo: {gateway.gateway_type}")
                        if gateway._api_key:
                            logger.error(f"   ❌ Campo interno existe mas descriptografia falhou!")
```

### 2. App Routes

**Localização:** `app.py`

Criação de gateway com credenciais dummy para verificação:

```11471:11472:app.py
        elif gateway_type == 'babylon':
            dummy_credentials = {'api_key': 'dummy'}
```

### 3. Gateway Factory

**Localização:** `gateway_factory.py`

Registro e criação:

```38:38:gateway_factory.py
        'babylon': BabylonGateway,  # ✅ Babylon
```

### 4. Rota de Webhook

**Localização:** `app.py` (linha 11394)

**Rota:**
```python
@app.route('/webhook/payment/<string:gateway_type>', methods=['POST'])
@limiter.limit("500 per minute")
@csrf.exempt
def payment_webhook(gateway_type):
```

**Processamento:**
1. Recebe webhook via POST
2. Cria gateway com credenciais dummy (webhook não precisa de credenciais reais)
3. Processa via `GatewayAdapter.process_webhook()`
4. Busca Payment por múltiplas chaves (gateway_transaction_id, gateway_hash, payment_id, external_reference)
5. Atualiza status do pagamento

**Credenciais Dummy para Webhook:**

```11471:11472:app.py
        elif gateway_type == 'babylon':
            dummy_credentials = {'api_key': 'dummy'}
```

### 5. Middleware de Validação

**Localização:** `middleware/gateway_validator.py`

**⚠️ ATENÇÃO:** O middleware atual **NÃO inclui** `babylon` na lista de gateways válidos:

```46:46:middleware/gateway_validator.py
            valid_types = ['syncpay', 'pushynpay', 'paradise', 'wiinpay', 'atomopay', 'umbrellapag', 'orionpay']
```

**🔧 CORREÇÃO NECESSÁRIA:** Adicionar `'babylon'` à lista `valid_types`.

---

## 🎨 INTERFACE DO USUÁRIO

### Templates HTML

**Localização:** `templates/settings.html`

#### 1. Seleção de Gateway (Wizard de Criação)

```264:268:templates/bot_create_wizard.html
                <!-- Babylon -->
                <label>
                    <input type="radio" x-model="formData.gateway_type" value="babylon" class="hidden peer">
                    <div class="gateway-option peer-checked:border-primary peer-checked:bg-primary/10">
                        <h3 class="text-lg font-bold text-txt-primary mb-3">Babylon</h3>
```

#### 2. Formulário de Configuração

```857:859:templates/settings.html
                            <!-- Babylon -->
                            <template x-if="gateway.gateway_type === 'babylon'">
                                <form @submit.prevent="updateGateway(gateway.id, 'babylon')" class="space-y-3">
```

#### 3. Card de Gateway (Adicionar Novo)

```1316:1338:templates/settings.html
                <!-- Babylon -->
                <div class="gateway-card" x-show="!getGatewayStatus('babylon')?.is_verified">
                    <div class="flex items-center gap-3 mb-3">
                        <div class="w-12 h-12 rounded-lg bg-gradient-to-br from-purple-500 to-pink-500 flex items-center justify-center">
                            <img src="{{ url_for('static', filename='img/babylon.png') }}" 
                                 alt="Babylon" 
                                 class="w-8 h-8 object-contain">
                        </div>
                        <div>
                            <h3 class="text-xs sm:text-sm font-bold text-white truncate">Babylon</h3>
                        </div>
                    </div>
                    <form @submit.prevent="saveGateway('babylon')" class="space-y-3">
                        <div>
                            <label class="block text-xs text-gray-300 mb-1">API Key</label>
                            <input type="text" 
                                   class="w-full px-3 py-2 bg-gray-800 border border-gray-700 rounded text-white text-sm"
                                   x-model="gateways.babylon.api_key" 
                                   placeholder="Digite sua API Key do Babylon"
                                   required>
                        </div>
```

#### 4. Logo do Gateway

```583:585:templates/settings.html
                                    <template x-if="gateway.gateway_type === 'babylon'">
                                        <img src="{{ url_for('static', filename='img/babylon.png') }}" 
                                             alt="Babylon" 
```

**Localização do Logo:** `static/img/babylon.png`

### Estado JavaScript

```1764:1764:templates/settings.html
            babylon: { api_key: '' }
```

### Validação no Frontend

```1916:1916:templates/settings.html
                    } else if (type === 'babylon') {
```

---

## 🔧 CARACTERÍSTICAS TÉCNICAS

### Validação de Valor

- **Mínimo:** R$ 1,00 (100 centavos)
- **Conversão:** Automática para centavos (int)

### Validação de Documento

- **CPF:** 11 dígitos → `type: "CPF"`
- **CNPJ:** 14 dígitos → `type: "CNPJ"`
- **Fallback:** `00000000000` (CPF)

### Validação de Telefone

- Remove formatação (apenas números)
- Fallback: `11999999999`

### Expiração do PIX

- **Range:** 1 a 7 dias
- **Padrão:** 1 dia
- **Configurável:** Via `customer_data.pix_expires_in_days` (futuro)

### Geração de QR Code

- **URL:** `https://api.qrserver.com/v1/create-qr-code/?size=400x400&data={pix_code}`
- **Tamanho:** 400x400 pixels
- **Base64:** Não implementado

### Timeouts

- **Geração de PIX:** 15 segundos
- **Consulta de Status:** 10 segundos

### Logging

Todos os métodos incluem logging detalhado:
- ✅ Informações de requisição
- ✅ Respostas de sucesso
- ✅ Erros e exceções
- ✅ Dados de webhook

---

## 📊 STATUS DE IMPLEMENTAÇÃO

### ✅ Funcionalidades Implementadas

- [x] Geração de PIX
- [x] Processamento de Webhook
- [x] Consulta de Status
- [x] Validação de Credenciais (formato)
- [x] Split Payment (opcional)
- [x] Interface do Usuário
- [x] Integração com Bot Manager
- [x] Integração com Gateway Factory
- [x] Integração com Gateway Adapter

### ⚠️ Melhorias Pendentes

1. **Middleware de Validação:** Adicionar `'babylon'` à lista de gateways válidos
2. **Validação de Credenciais:** Implementar validação real via API (se disponível)
3. **QR Code Base64:** Implementar geração de QR Code em base64
4. **Expiração Configurável:** Permitir configuração via gateway config

### 📝 Documentação de Garantias

Conforme documentos de garantia:

- ✅ **GARANTIA_FINAL_100_PORCENTO_TODOS_GATEWAYS.md:** Babylon listado como suportado
- ✅ **GARANTIA_FINAL_100_UPSELLS_COMPLETA.md:** Babylon com cobertura completa
- ✅ **DEBATE_FINAL_GARANTIA_100_UPSELLS.md:** Babylon com webhooks + verificação manual

---

## 🐛 PROBLEMAS CONHECIDOS

### 1. Middleware de Validação

**Problema:** `babylon` não está na lista de gateways válidos no middleware.

**Impacto:** Webhooks podem ser rejeitados se o middleware for aplicado.

**Solução:** Adicionar `'babylon'` à lista em `middleware/gateway_validator.py`.

### 2. Validação de Credenciais

**Problema:** Validação apenas verifica formato, não autentica com a API.

**Impacto:** Credenciais inválidas podem ser aceitas.

**Solução:** Implementar validação real se a API fornecer endpoint.

---

## 📚 REFERÊNCIAS

### Arquivos Relacionados

- `gateway_babylon.py` - Implementação principal
- `gateway_factory.py` - Factory pattern
- `gateway_adapter.py` - Adapter pattern
- `gateway_interface.py` - Interface base
- `bot_manager.py` - Integração com bots
- `app.py` - Rotas da API
- `templates/settings.html` - Interface do usuário
- `templates/bot_create_wizard.html` - Wizard de criação

### Documentação Externa

- **API Base URL:** `https://api.bancobabylon.com/functions/v1`
- **Documentação:** (Não encontrada no codebase)

---

## ✅ CONCLUSÃO

O gateway Babylon está **totalmente implementado e funcional**, com suporte completo a:
- Geração de PIX
- Webhooks
- Consulta de status
- Split payment
- Interface do usuário

**Atenção necessária:**
- Adicionar `'babylon'` ao middleware de validação
- Considerar implementar validação real de credenciais

---

**Última Atualização:** 2025-01-27  
**Versão do Documento:** 1.0

