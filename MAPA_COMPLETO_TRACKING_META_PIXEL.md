# 🗺️ MAPA COMPLETO DO SISTEMA DE TRACKING META PIXEL

**Data:** 2025-11-14  
**Versão:** V4.1  
**Objetivo:** Documentação completa do fluxo de tracking do redirect até o Purchase

---

## 📋 RESUMO EXECUTIVO

### **O QUE O SISTEMA FAZ:**

1. **Captura dados** no redirect (`/go/<slug>`): `fbclid`, `_fbp`, `_fbc`, `IP`, `User-Agent`, `UTMs`
2. **Salva no Redis** com `tracking_token` (UUID de 32 caracteres)
3. **Envia PageView** para Meta com 4/7 ou 5/7 atributos (sem email/phone - não temos)
4. **Atualiza BotUser** quando usuário clica em `/start` no Telegram
5. **Envia ViewContent** para Meta com 4/7 a 7/7 atributos (email/phone se disponível)
6. **Salva Payment** com `tracking_token` quando PIX é gerado
7. **Envia Purchase** para Meta com 2/7 a 7/7 atributos (email/phone se disponível)

### **DADOS ENVIADOS POR ETAPA:**

| Etapa | external_id | customer_user_id | email | phone | IP | UA | fbp | fbc |
|-------|-------------|------------------|-------|------|----|----|-----|-----|
| **PageView** | ✅ | ❌ | ❌ | ❌ | ✅ | ✅ | ✅ | ✅* |
| **ViewContent** | ✅ | ✅ | ⚠️ | ⚠️ | ✅ | ✅ | ✅ | ✅* |
| **Purchase** | ✅ | ✅ | ⚠️ | ⚠️ | ✅ | ✅ | ✅ | ✅* |

*✅ = Se cookie presente

### **ONDE OS DADOS SÃO ARMAZENADOS:**

- **Redis:** Fonte primária (TTL: 7 dias) - chave `tracking:{tracking_token}`
- **BotUser:** Fallback quando Redis expira - campos `tracking_session_id`, `fbclid`, `fbp`, `fbc`, `ip_address`, `user_agent`
- **Payment:** Fallback final - campos `tracking_token`, `fbclid`, `fbp`, `fbc`, `pageview_event_id`

### **CONCLUSÃO DO DEBATE:**

✅ **Sistema está CORRETO:**
- PageView **NÃO envia** email/phone (correto - não temos esses dados)
- Purchase **ENVIA** email/phone quando disponível (correto - se BotUser tiver)
- Logs mostram `email=❌, phone=❌` no PageView (correto)

---

## 📊 VISÃO GERAL DO FLUXO

```
┌─────────────────────────────────────────────────────────────────┐
│                    FLUXO COMPLETO DE TRACKING                    │
└─────────────────────────────────────────────────────────────────┘

1. REDIRECT (/go/<slug>)
   ↓
2. PAGEVIEW (Meta Pixel)
   ↓
3. /START (Telegram Bot)
   ↓
4. VIEWCONTENT (Meta Pixel)
   ↓
5. GENERATE PIX PAYMENT
   ↓
6. PURCHASE (Meta Pixel)
```

---

## 🎨 DIAGRAMA VISUAL DO FLUXO

```
┌─────────────────────────────────────────────────────────────────────────┐
│                         FLUXO COMPLETO DE TRACKING                        │
└─────────────────────────────────────────────────────────────────────────┘

┌──────────────┐
│  1. REDIRECT │
│  /go/<slug>  │
└──────┬───────┘
       │
       ├─► Captura: fbclid, _fbp, _fbc, IP, UA, UTMs
       ├─► Gera: tracking_token (UUID), pageview_event_id
       ├─► Salva: Redis (tracking:{token})
       │
       ▼
┌──────────────┐
│ 2. PAGEVIEW  │
│ (Meta Pixel) │
└──────┬───────┘
       │
       ├─► Envia: external_id (fbclid), IP, UA, fbp, fbc
       ├─► NÃO envia: email, phone, customer_user_id
       │   (4/7 ou 5/7 atributos)
       │
       ▼
┌──────────────┐
│ 3. /START    │
│ (Telegram)   │
└──────┬───────┘
       │
       ├─► Recupera: tracking_token do parâmetro start
       ├─► Recupera: dados do Redis
       ├─► Salva: BotUser (tracking_session_id, fbclid, fbp, fbc, IP, UA)
       │
       ▼
┌──────────────┐
│4. VIEWCONTENT│
│ (Meta Pixel) │
└──────┬───────┘
       │
       ├─► Envia: external_id, customer_user_id, IP, UA, fbp, fbc
       ├─► Envia: email, phone (se BotUser tiver)
       │   (4/7 a 7/7 atributos)
       │
       ▼
┌──────────────┐
│5. GENERATE   │
│  PIX PAYMENT │
└──────┬───────┘
       │
       ├─► Recupera: tracking_token (bot_user.tracking_session_id)
       ├─► Recupera: dados do Redis
       ├─► Gera: novo token se não encontrar (com seed_payload)
       ├─► Salva: Payment (tracking_token, fbclid, fbp, fbc, pageview_event_id)
       │
       ▼
┌──────────────┐
│ 6. PURCHASE  │
│ (Meta Pixel) │
└──────┬───────┘
       │
       ├─► Recupera: tracking_data (Redis → Payment → BotUser)
       ├─► Envia: external_id, customer_user_id, IP, UA, fbp, fbc
       ├─► Envia: email, phone (se BotUser tiver)
       ├─► Reutiliza: pageview_event_id (deduplicação)
       │   (2/7 a 7/7 atributos)
       │
       ▼
┌──────────────┐
│   META API   │
│  (Recebe)    │
└──────────────┘
```

---

## 📦 ARMAZENAMENTO DE DADOS

```
┌─────────────────────────────────────────────────────────────────┐
│                    ONDE OS DADOS SÃO ARMAZENADOS                 │
└─────────────────────────────────────────────────────────────────┘

┌─────────────┐
│   REDIS     │  TTL: 7 dias
│             │
│ tracking:   │  {fbclid, fbp, fbc, IP, UA, pageview_event_id, ...}
│ {token}     │
└─────────────┘
       │
       ├─► Fonte primária de dados de tracking
       ├─► Recuperado em: Purchase, ViewContent
       └─► Atualizado em: Redirect, Generate PIX

┌─────────────┐
│  BOTUSER    │  Database (permanente)
│             │
│ tracking_   │  {tracking_session_id, fbclid, fbp, fbc, IP, UA, ...}
│ session_id  │
└─────────────┘
       │
       ├─► Fallback quando Redis expira
       ├─► Atualizado em: /START
       └─► Usado em: Generate PIX, Purchase

┌─────────────┐
│  PAYMENT    │  Database (permanente)
│             │
│ tracking_   │  {tracking_token, fbclid, fbp, fbc, pageview_event_id, ...}
│ token       │
└─────────────┘
       │
       ├─► Fallback final quando Redis expira
       ├─► Criado em: Generate PIX
       └─► Usado em: Purchase
```

---

## 🔄 ETAPA 1: REDIRECT (`public_redirect`)

**Arquivo:** `app.py` (linhas 4133-4405)  
**Rota:** `/go/<slug>`

### **Dados Capturados:**

| Campo | Origem | Exemplo | Salvo em |
|-------|--------|---------|----------|
| `fbclid` | `request.args.get('fbclid')` | `PAZXh0bgNhZW0BMABhZGlkAasqUTTZ2yRz...` | Redis, Payment |
| `_fbp` | `request.cookies.get('_fbp')` | `fb.1.1763135268.7972483413...` | Redis, Payment |
| `_fbc` | `request.cookies.get('_fbc')` | `fb.1.1762423103.IwZXh0bgNhZW0BMABhZGlkAasqUTUOWKRz...` | Redis, Payment |
| `client_ip` | `X-Forwarded-For` ou `remote_addr` | `192.168.1.1` | Redis, BotUser |
| `client_user_agent` | `request.headers.get('User-Agent')` | `Mozilla/5.0...` | Redis, BotUser |
| `utm_source` | `request.args.get('utm_source')` | `facebook` | Redis, BotUser |
| `utm_campaign` | `request.args.get('utm_campaign')` | `campanha_01` | Redis, BotUser |
| `grim` | `request.args.get('grim')` | `testecamu01` | Redis, BotUser |

### **Ações Realizadas:**

1. ✅ **Gera `tracking_token`** (UUID de 32 caracteres)
2. ✅ **Gera `pageview_event_id`** (formato: `pageview_{uuid}`)
3. ✅ **Gera `fbp`** se cookie ausente (formato: `fb.1.{timestamp}.{random}`)
4. ✅ **Captura `fbc`** do cookie (NUNCA gera sintético)
5. ✅ **Salva no Redis** com chave `tracking:{tracking_token}` (TTL: 7 dias)
6. ✅ **Envia PageView** (assíncrono via Celery)
7. ✅ **Redireciona para Telegram** com `?start={tracking_token}`

### **Payload Salvo no Redis:**

```python
tracking_payload = {
    'tracking_token': '30d7839aa9194e9ca324...',  # UUID 32 chars
    'fbclid': 'PAZXh0bgNhZW0BMABhZGlkAasqUTTZ2yRz...',  # Completo (até 255 chars)
    'fbp': 'fb.1.1763135268.7972483413...',
    'fbc': 'fb.1.1762423103.IwZXh0bgNhZW0BMABhZGlkAasqUTUOWKRz...',  # Se cookie presente
    'fbc_origin': 'cookie',  # 'cookie' ou None
    'pageview_event_id': 'pageview_2796d78f76bc46dd822be80e084ddb5f',
    'pageview_ts': 1763135268,
    'client_ip': '192.168.1.1',
    'client_user_agent': 'Mozilla/5.0...',
    'event_source_url': 'https://app.grimbots.online/go/red1',
    'first_page': 'https://app.grimbots.online/go/red1',
    'utm_source': 'facebook',
    'utm_campaign': 'campanha_01',
    'grim': 'testecamu01'
}
```

---

## 📄 ETAPA 2: PAGEVIEW (Meta Pixel)

**Arquivo:** `app.py` (linhas 6939-7312)  
**Função:** `send_meta_pixel_pageview_event()`

### **Dados Enviados:**

| Campo | Origem | Hashado? | Enviado? |
|-------|--------|----------|----------|
| `external_id` | `fbclid` normalizado | ✅ SHA256 | ✅ SIM |
| `customer_user_id` | `None` (não temos ainda) | ❌ | ❌ NÃO |
| `email` | `None` | ❌ | ❌ NÃO |
| `phone` | `None` | ❌ | ❌ NÃO |
| `client_ip_address` | `X-Forwarded-For` ou `remote_addr` | ❌ | ✅ SIM |
| `client_user_agent` | `request.headers.get('User-Agent')` | ❌ | ✅ SIM |
| `fbp` | Cookie `_fbp` ou Redis | ❌ | ✅ SIM |
| `fbc` | Cookie `_fbc` ou Redis | ❌ | ✅ SIM |

### **Payload Enviado para Meta:**

```json
{
  "data": [{
    "event_name": "PageView",
    "event_time": 1763135268,
    "event_id": "pageview_2796d78f76bc46dd822be80e084ddb5f",
    "action_source": "website",
    "event_source_url": "https://app.grimbots.online/go/red1",
    "user_data": {
      "external_id": ["827682c84caf5aea..."],  // fbclid hasheado SHA256
      "client_ip_address": "192.168.1.1",
      "client_user_agent": "Mozilla/5.0...",
      "fbp": "fb.1.1763135268.7972483413...",
      "fbc": "fb.1.1762423103.IwZXh0bgNhZW0BMABhZGlkAasqUTUOWKRz..."  // Se presente
    },
    "custom_data": {
      "pool_id": 1,
      "pool_name": "ads",
      "utm_source": "facebook",
      "utm_campaign": "campanha_01",
      "fbclid": "PAZXh0bgNhZW0BMABhZGlkAasqUTTZ2yRz..."
    }
  }],
  "access_token": "..."
}
```

### **Atributos Enviados:**

- ✅ **4/7 atributos** (sem fbc) ou **5/7 atributos** (com fbc)
- ✅ `external_id` (fbclid)
- ✅ `fbp`
- ✅ `fbc` (se cookie presente)
- ✅ `client_ip_address`
- ✅ `client_user_agent`
- ❌ `email` (não temos)
- ❌ `phone` (não temos)
- ❌ `customer_user_id` (não temos ainda)

---

## 🤖 ETAPA 3: /START (Telegram Bot)

**Arquivo:** `tasks_async.py` (função `process_start_async`)  
**Trigger:** Usuário clica em `/start` no Telegram

### **Ações Realizadas:**

1. ✅ **Recupera `tracking_token`** do parâmetro `start`
2. ✅ **Recupera dados do Redis** usando `tracking_token`
3. ✅ **Cria/Atualiza `BotUser`** com:
   - `tracking_session_id` = `tracking_token`
   - `fbclid` = do Redis
   - `fbp` = do Redis
   - `fbc` = do Redis (se presente)
   - `ip_address` = do Redis
   - `user_agent` = do Redis
   - `utm_*` = do Redis
   - `campaign_code` = do Redis (grim)

### **Dados Salvos no BotUser:**

```python
bot_user.tracking_session_id = '30d7839aa9194e9ca324...'
bot_user.fbclid = 'PAZXh0bgNhZW0BMABhZGlkAasqUTTZ2yRz...'
bot_user.fbp = 'fb.1.1763135268.7972483413...'
bot_user.fbc = 'fb.1.1762423103.IwZXh0bgNhZW0BMABhZGlkAasqUTUOWKRz...'
bot_user.ip_address = '192.168.1.1'
bot_user.user_agent = 'Mozilla/5.0...'
bot_user.utm_source = 'facebook'
bot_user.utm_campaign = 'campanha_01'
bot_user.campaign_code = 'testecamu01'
```

---

## 👁️ ETAPA 4: VIEWCONTENT (Meta Pixel)

**Arquivo:** `bot_manager.py` (função `send_meta_pixel_viewcontent_event`)  
**Trigger:** Após `/start` ser processado

### **Dados Enviados:**

| Campo | Origem | Hashado? | Enviado? |
|-------|--------|----------|----------|
| `external_id` | `bot_user.fbclid` ou `tracking_data.fbclid` | ✅ SHA256 | ✅ SIM |
| `customer_user_id` | `bot_user.telegram_user_id` | ✅ SHA256 | ✅ SIM |
| `email` | `bot_user.email` | ✅ SHA256 | ⚠️ Se disponível |
| `phone` | `bot_user.phone` | ✅ SHA256 | ⚠️ Se disponível |
| `client_ip_address` | `bot_user.ip_address` ou `tracking_data.client_ip` | ❌ | ✅ SIM |
| `client_user_agent` | `bot_user.user_agent` ou `tracking_data.client_user_agent` | ❌ | ✅ SIM |
| `fbp` | `bot_user.fbp` ou `tracking_data.fbp` | ❌ | ✅ SIM |
| `fbc` | `bot_user.fbc` ou `tracking_data.fbc` | ❌ | ✅ SIM |

### **Atributos Enviados:**

- ✅ **4/7 a 7/7 atributos** (depende de email/phone)
- ✅ `external_id` (fbclid)
- ✅ `customer_user_id` (telegram_user_id)
- ⚠️ `email` (se BotUser tiver)
- ⚠️ `phone` (se BotUser tiver)
- ✅ `client_ip_address`
- ✅ `client_user_agent`
- ✅ `fbp`
- ✅ `fbc` (se presente)

---

## 💳 ETAPA 5: GENERATE PIX PAYMENT

**Arquivo:** `bot_manager.py` (função `_generate_pix_payment`)  
**Trigger:** Usuário clica em "Gerar PIX"

### **Ações Realizadas:**

1. ✅ **Recupera `tracking_token`** de:
   - `bot_user.tracking_session_id` (prioridade 1)
   - `tracking:last_token:user:{customer_user_id}` (prioridade 2)
   - `tracking:chat:{customer_user_id}` (prioridade 3)
   - Gera novo se não encontrar (prioridade 4)

2. ✅ **Recupera dados do Redis** usando `tracking_token`

3. ✅ **Se novo token gerado**, cria `seed_payload` com:
   - `fbp`, `fbc`, `client_ip`, `client_user_agent` do BotUser
   - `fbclid`, `utm_*` do contexto

4. ✅ **Cria Payment** com:
   - `tracking_token` = token recuperado ou gerado
   - `fbclid` = do Redis ou BotUser
   - `fbp` = do Redis ou BotUser
   - `fbc` = do Redis ou BotUser
   - `pageview_event_id` = do Redis ou BotUser
   - `utm_*` = do Redis ou BotUser

### **Dados Salvos no Payment:**

```python
payment.tracking_token = '30d7839aa9194e9ca324...'  # ou novo token se gerado
payment.fbclid = 'PAZXh0bgNhZW0BMABhZGlkAasqUTTZ2yRz...'
payment.fbp = 'fb.1.1763135268.7972483413...'
payment.fbc = 'fb.1.1762423103.IwZXh0bgNhZW0BMABhZGlkAasqUTUOWKRz...'
payment.pageview_event_id = 'pageview_2796d78f76bc46dd822be80e084ddb5f'
payment.utm_source = 'facebook'
payment.utm_campaign = 'campanha_01'
payment.campaign_code = 'testecamu01'
```

---

## 🛒 ETAPA 6: PURCHASE (Meta Pixel)

**Arquivo:** `app.py` (função `send_meta_pixel_purchase_event`)  
**Trigger:** Pagamento confirmado (webhook ou botão "Verificar Pagamento")

### **Dados Recuperados (Prioridade):**

1. **`tracking_data` do Redis** usando `payment.tracking_token`
2. **Fallback 1:** `tracking:payment:{payment_id}`
3. **Fallback 2:** `tracking:fbclid:{payment.fbclid}`
4. **Fallback 3:** Dados do Payment
5. **Fallback 4:** Dados do BotUser (IP, UA)

### **Dados Enviados:**

| Campo | Origem | Hashado? | Enviado? |
|-------|--------|----------|----------|
| `external_id` | `tracking_data.fbclid` → `payment.fbclid` → `bot_user.fbclid` | ✅ SHA256 | ✅ SIM |
| `customer_user_id` | `payment.customer_user_id` (telegram_user_id) | ✅ SHA256 | ✅ SIM |
| `email` | `bot_user.email` | ✅ SHA256 | ⚠️ Se disponível |
| `phone` | `bot_user.phone` | ✅ SHA256 | ⚠️ Se disponível |
| `client_ip_address` | `tracking_data.client_ip` → `bot_user.ip_address` | ❌ | ✅ SIM |
| `client_user_agent` | `tracking_data.client_user_agent` → `bot_user.user_agent` | ❌ | ✅ SIM |
| `fbp` | `tracking_data.fbp` → `payment.fbp` → `bot_user.fbp` | ❌ | ✅ SIM |
| `fbc` | `tracking_data.fbc` (se `fbc_origin='cookie'`) → `bot_user.fbc` → `payment.fbc` | ❌ | ✅ SIM |

### **Payload Enviado para Meta:**

```json
{
  "data": [{
    "event_name": "Purchase",
    "event_time": 1763135268,
    "event_id": "pageview_2796d78f76bc46dd822be80e084ddb5f",  // Reutiliza do PageView
    "action_source": "website",
    "user_data": {
      "external_id": [
        "827682c84caf5aea...",  // fbclid hasheado SHA256
        "a1b2c3d4e5f6..."  // telegram_user_id hasheado SHA256
      ],
      "em": ["abc123..."],  // email hasheado SHA256 (se disponível)
      "ph": ["def456..."],  // phone hasheado SHA256 (se disponível)
      "client_ip_address": "192.168.1.1",
      "client_user_agent": "Mozilla/5.0...",
      "fbp": "fb.1.1763135268.7972483413...",
      "fbc": "fb.1.1762423103.IwZXh0bgNhZW0BMABhZGlkAasqUTUOWKRz..."  // Se presente
    },
    "custom_data": {
      "currency": "BRL",
      "value": 14.97,
      "content_type": "product",
      "num_items": 1,
      "content_ids": ["1"],
      "content_name": "Acesso Imediato",
      "content_category": "initial"
    }
  }],
  "access_token": "..."
}
```

### **Atributos Enviados:**

- ✅ **2/7 a 7/7 atributos** (depende de dados disponíveis)
- ✅ `external_id` (fbclid + telegram_user_id)
- ✅ `fbp`
- ✅ `fbc` (se presente)
- ⚠️ `email` (se BotUser tiver)
- ⚠️ `phone` (se BotUser tiver)
- ✅ `client_ip_address`
- ✅ `client_user_agent`

---

## 📊 RESUMO: DADOS POR ETAPA

| Dado | Redirect | PageView | ViewContent | Purchase |
|------|----------|----------|-------------|----------|
| `external_id` (fbclid) | ✅ Capturado | ✅ Enviado | ✅ Enviado | ✅ Enviado |
| `customer_user_id` | ❌ Não temos | ❌ Não temos | ✅ Enviado | ✅ Enviado |
| `email` | ❌ Não temos | ❌ Não temos | ⚠️ Se tiver | ⚠️ Se tiver |
| `phone` | ❌ Não temos | ❌ Não temos | ⚠️ Se tiver | ⚠️ Se tiver |
| `client_ip_address` | ✅ Capturado | ✅ Enviado | ✅ Enviado | ✅ Enviado |
| `client_user_agent` | ✅ Capturado | ✅ Enviado | ✅ Enviado | ✅ Enviado |
| `fbp` | ✅ Capturado/Gerado | ✅ Enviado | ✅ Enviado | ✅ Enviado |
| `fbc` | ✅ Capturado (cookie) | ✅ Enviado (se presente) | ✅ Enviado (se presente) | ✅ Enviado (se presente) |

---

## 🗄️ ONDE OS DADOS SÃO ARMAZENADOS

### **Redis (TTL: 7 dias)**

**Chave:** `tracking:{tracking_token}`

```python
{
    'tracking_token': '30d7839aa9194e9ca324...',
    'fbclid': 'PAZXh0bgNhZW0BMABhZGlkAasqUTTZ2yRz...',
    'fbp': 'fb.1.1763135268.7972483413...',
    'fbc': 'fb.1.1762423103.IwZXh0bgNhZW0BMABhZGlkAasqUTUOWKRz...',
    'fbc_origin': 'cookie',
    'pageview_event_id': 'pageview_2796d78f76bc46dd822be80e084ddb5f',
    'pageview_ts': 1763135268,
    'client_ip': '192.168.1.1',
    'client_user_agent': 'Mozilla/5.0...',
    'event_source_url': 'https://app.grimbots.online/go/red1',
    'first_page': 'https://app.grimbots.online/go/red1',
    'utm_source': 'facebook',
    'utm_campaign': 'campanha_01',
    'grim': 'testecamu01'
}
```

### **BotUser (Database)**

```python
bot_user.tracking_session_id = '30d7839aa9194e9ca324...'
bot_user.fbclid = 'PAZXh0bgNhZW0BMABhZGlkAasqUTTZ2yRz...'
bot_user.fbp = 'fb.1.1763135268.7972483413...'
bot_user.fbc = 'fb.1.1762423103.IwZXh0bgNhZW0BMABhZGlkAasqUTUOWKRz...'
bot_user.ip_address = '192.168.1.1'
bot_user.user_agent = 'Mozilla/5.0...'
bot_user.utm_source = 'facebook'
bot_user.utm_campaign = 'campanha_01'
bot_user.campaign_code = 'testecamu01'
bot_user.email = 'user@example.com'  # Se coletado
bot_user.phone = '5511999999999'  # Se coletado
```

### **Payment (Database)**

```python
payment.tracking_token = '30d7839aa9194e9ca324...'
payment.fbclid = 'PAZXh0bgNhZW0BMABhZGlkAasqUTTZ2yRz...'
payment.fbp = 'fb.1.1763135268.7972483413...'
payment.fbc = 'fb.1.1762423103.IwZXh0bgNhZW0BMABhZGlkAasqUTUOWKRz...'
payment.pageview_event_id = 'pageview_2796d78f76bc46dd822be80e084ddb5f'
payment.utm_source = 'facebook'
payment.utm_campaign = 'campanha_01'
payment.campaign_code = 'testecamu01'
```

---

## ⚔️ DEBATE SÊNIOR: EMAIL/PHONE NO PAGEVIEW

### **POSIÇÃO A: NÃO DEVE ENVIAR EMAIL/PHONE NO PAGEVIEW**

**Argumentos:**
1. ❌ **Não temos esses dados:** No PageView, o usuário ainda não interagiu com o bot
2. ❌ **Não é coletado:** Não há formulário ou coleta de email/phone no redirect
3. ❌ **Pode confundir Meta:** Enviar `email=None` ou `phone=None` não adiciona valor
4. ✅ **Código atual está correto:** `email=None, phone=None` no PageView

**Veredito:**
- ✅ **CORRETO:** PageView não deve enviar email/phone (código atual está certo)

---

### **POSIÇÃO B: DEVERIA ENVIAR EMAIL/PHONE NO PAGEVIEW**

**Argumentos:**
1. ⚠️ **Se tiver dados:** Se o usuário já tiver email/phone em cookies ou localStorage
2. ⚠️ **Melhor matching:** Mais dados = melhor match quality
3. ❌ **Mas não temos:** Não há mecanismo para coletar esses dados no redirect

**Veredito:**
- ❌ **INVIÁVEL:** Não temos como coletar email/phone no redirect sem formulário

---

### **CONCLUSÃO DO DEBATE:**

**✅ CÓDIGO ATUAL ESTÁ CORRETO:**

1. **PageView:** `email=None, phone=None` ✅ (não temos esses dados)
2. **ViewContent:** `email=bot_user.email, phone=bot_user.phone` ✅ (se disponível)
3. **Purchase:** `email=bot_user.email, phone=bot_user.phone` ✅ (se disponível)

**✅ RECOMENDAÇÃO:**

- **PageView:** Manter `email=None, phone=None` (correto)
- **ViewContent/Purchase:** Enviar email/phone se BotUser tiver (correto)
- **Melhoria futura:** Coletar email/phone no bot e salvar no BotUser para melhor matching

---

## ✅ CHECKLIST DE VALIDAÇÃO

### **PageView:**
- ✅ `external_id` (fbclid) enviado
- ✅ `client_ip_address` enviado
- ✅ `client_user_agent` enviado
- ✅ `fbp` enviado
- ✅ `fbc` enviado (se cookie presente)
- ✅ `email` NÃO enviado (correto - não temos)
- ✅ `phone` NÃO enviado (correto - não temos)
- ✅ `customer_user_id` NÃO enviado (correto - não temos ainda)

### **Purchase:**
- ✅ `external_id` (fbclid + telegram_user_id) enviado
- ✅ `client_ip_address` enviado
- ✅ `client_user_agent` enviado
- ✅ `fbp` enviado
- ✅ `fbc` enviado (se presente)
- ⚠️ `email` enviado (se BotUser tiver)
- ⚠️ `phone` enviado (se BotUser tiver)
- ✅ `customer_user_id` (telegram_user_id) enviado

---

## 🎯 CONCLUSÃO

**✅ SISTEMA ESTÁ FUNCIONANDO CORRETAMENTE:**

1. **PageView:** Envia 4/7 ou 5/7 atributos (correto - não temos email/phone/customer_user_id)
2. **Purchase:** Envia 2/7 a 7/7 atributos (depende de dados disponíveis)
3. **Email/Phone:** Enviados apenas quando disponíveis (ViewContent/Purchase)
4. **Matching:** `external_id` (fbclid) garante matching PageView ↔ Purchase

**✅ MELHORIAS FUTURAS:**

1. Coletar email/phone no bot e salvar no BotUser
2. Adicionar email/phone ao `seed_payload` quando novo token é gerado
3. Melhorar fallback para recuperar email/phone de outras fontes

---

---

## ⚔️ DEBATE SÊNIOR COMPLETO: EMAIL/PHONE NO PAGEVIEW E PURCHASE

### **ENGENHEIRO A: "O sistema está correto - não devemos enviar email/phone no PageView"**

**Argumentos:**
1. ✅ **Dados não disponíveis:** No momento do PageView, o usuário ainda não interagiu com o bot. Não há como coletar email/phone sem formulário.
2. ✅ **Código atual está correto:** `email=None, phone=None` no PageView é o comportamento esperado.
3. ✅ **Meta aceita sem esses campos:** Meta não exige email/phone para PageView. O importante é `external_id` (fbclid) para matching.
4. ✅ **Purchase envia quando disponível:** Se BotUser tiver email/phone, Purchase envia. Isso é suficiente.

**Conclusão:**
- ✅ Sistema está funcionando corretamente
- ✅ Não há necessidade de mudança
- ✅ Email/phone são enviados quando disponíveis (ViewContent/Purchase)

---

### **ENGENHEIRO B: "Mas o usuário disse que estamos enviando email/phone no PageView"**

**Argumentos:**
1. ⚠️ **Verificação necessária:** Precisamos confirmar se realmente estamos enviando `email=None` ou se há algum bug.
2. ⚠️ **Logs mostram:** O log mostra `email=❌, phone=❌` no PageView, o que está correto.
3. ⚠️ **Mas pode haver edge case:** Se houver algum código que colete email/phone de cookies ou localStorage, deveríamos usar.

**Conclusão:**
- ⚠️ Verificar se há código que coleta email/phone de outras fontes
- ⚠️ Se não houver, manter como está (correto)
- ⚠️ Se houver, incluir no PageView

---

### **DEBATE FINAL: ANÁLISE DO CÓDIGO**

**Verificação do Código:**

```7172:7173:app.py
            email=None,
            phone=None,
```

**✅ CONFIRMADO:** Código envia `email=None, phone=None` no PageView.

**Verificação do `_build_user_data`:**

```125:130:utils/meta_pixel.py
        # ✅ Email (hashed) - validar antes de processar
        if email and isinstance(email, str) and email.strip():
            email_clean = email.lower().strip()
            # Validação básica de email (deve ter @ e pelo menos 3 caracteres)
            if '@' in email_clean and len(email_clean) >= 3:
                user_data['em'] = [MetaPixelAPI._hash_data(email_clean)]
```

**✅ CONFIRMADO:** Se `email=None`, `_build_user_data` não adiciona `em` ao `user_data`.

**Verificação do Purchase:**

```7713:7717:app.py
        email_value = getattr(bot_user, 'email', None)
        phone_value = getattr(bot_user, 'phone', None)
        if phone_value:
            digits_only = ''.join(filter(str.isdigit, str(phone_value)))
            phone_value = digits_only or None
```

**✅ CONFIRMADO:** Purchase recupera email/phone do BotUser e envia se disponível.

---

### **VEREDITO FINAL DO DEBATE:**

**✅ SISTEMA ESTÁ CORRETO:**

1. **PageView:** `email=None, phone=None` → Não envia email/phone ✅
2. **Purchase:** `email=bot_user.email, phone=bot_user.phone` → Envia se disponível ✅
3. **Logs confirmam:** `email=❌, phone=❌` no PageView ✅

**✅ CONCLUSÃO:**

- O sistema **NÃO está enviando** email/phone no PageView (correto)
- O sistema **ESTÁ enviando** email/phone no Purchase quando disponível (correto)
- O usuário pode estar confundindo PageView com Purchase, ou vendo logs de Purchase

**✅ RECOMENDAÇÃO:**

- Manter código atual (está correto)
- Adicionar log mais claro mostrando "email/phone não enviados no PageView (não temos dados)"
- Melhorar coleta de email/phone no bot para aumentar match quality no Purchase

---

**MAPA COMPLETO E DEBATE CONCLUÍDOS! ✅**

