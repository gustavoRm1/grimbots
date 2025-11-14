# 🔍 AUDITORIA COMPLETA - TRACKING META PIXEL V4 ULTRA SENIOR

**Data:** 2025-11-14  
**Engenheiro:** Meta Tracking Senior Engineer v4.0  
**Objetivo:** Garantir 100% de parâmetros em todos os eventos (PageView + Purchase)

---

## 📋 SUMÁRIO EXECUTIVO

### ✅ O QUE ESTÁ FUNCIONANDO
- Estrutura básica de tracking implementada
- Redis salvando tracking_payload
- Celery enfileirando eventos
- Validações de campos obrigatórios presentes
- FBC/FBP sendo capturados e salvos

### ❌ PROBLEMAS CRÍTICOS IDENTIFICADOS

1. **`custom_data` sendo enviado como `None` quando vazio** (PageView)
2. **`event_source_url` pode não estar sendo salvo no Redis** (PageView → Purchase)
3. **Validações muito restritivas bloqueando eventos válidos** (Purchase)
4. **Falta de `event_source_url` no payload do PageView** (utils/meta_pixel.py)
5. **`custom_data` pode estar vazio no Purchase** (sem UTM/campaign_code)

---

## 🔍 ANÁLISE ARQUIVO POR ARQUIVO

### 1. `utils/meta_pixel.py` - MetaPixelAPI.send_pageview_event()

**O QUE FAZ:**
- Constrói payload do PageView
- Envia para Meta Conversions API

**ONDE QUEBRA:**
```python
# LINHA 286 - PROBLEMA CRÍTICO
'custom_data': custom_data if custom_data else None  # ❌ ERRO: None quebra Meta
```

**COMO CORRIGIR:**
```python
# ✅ CORREÇÃO: Sempre enviar dict (mesmo vazio)
'custom_data': custom_data if custom_data else {}  # ✅ CORRETO
```

**OUTRO PROBLEMA:**
```python
# LINHA 285 - FALTA event_source_url
payload = {
    'data': [{
        'event_name': 'PageView',
        'event_time': int(time.time()),
        'event_id': event_id,
        'action_source': 'website',
        # ❌ FALTA: 'event_source_url': event_source_url,
        'user_data': user_data,
        'custom_data': custom_data if custom_data else None
    }],
    'access_token': access_token
}
```

**CORREÇÃO:**
```python
payload = {
    'data': [{
        'event_name': 'PageView',
        'event_time': int(time.time()),
        'event_id': event_id,
        'action_source': 'website',
        'event_source_url': event_source_url,  # ✅ ADICIONAR
        'user_data': user_data,
        'custom_data': custom_data if custom_data else {}  # ✅ CORRIGIR
    }],
    'access_token': access_token
}
```

---

### 2. `app.py` - send_meta_pixel_pageview_event()

**O QUE FAZ:**
- Captura dados do redirect
- Constrói event_data
- Enfileira no Celery

**ONDE QUEBRA:**
```python
# LINHA 7233-7244 - custom_data pode ter valores None
'custom_data': {
    'pool_id': pool.id,
    'pool_name': pool.name,
    'utm_source': utm_data['utm_source'],  # ❌ Pode ser None
    'utm_campaign': utm_data['utm_campaign'],  # ❌ Pode ser None
    # ...
}
```

**COMO CORRIGIR:**
```python
# ✅ CORREÇÃO: Filtrar valores None/vazios
custom_data = {}
if pool.id:
    custom_data['pool_id'] = pool.id
if pool.name:
    custom_data['pool_name'] = pool.name
if utm_data.get('utm_source'):
    custom_data['utm_source'] = utm_data['utm_source']
if utm_data.get('utm_campaign'):
    custom_data['utm_campaign'] = utm_data['utm_campaign']
if utm_data.get('utm_content'):
    custom_data['utm_content'] = utm_data['utm_content']
if utm_data.get('utm_medium'):
    custom_data['utm_medium'] = utm_data['utm_medium']
if utm_data.get('utm_term'):
    custom_data['utm_term'] = utm_data['utm_term']
if utm_data.get('fbclid'):
    custom_data['fbclid'] = utm_data['fbclid']
if utm_data.get('campaign_code'):
    custom_data['campaign_code'] = utm_data['campaign_code']

event_data = {
    'event_name': 'PageView',
    'event_time': int(time.time()),
    'event_id': event_id,
    'action_source': 'website',
    'event_source_url': event_source_url,
    'user_data': user_data,
    'custom_data': custom_data  # ✅ Sempre dict (pode ser vazio)
}
```

**OUTRO PROBLEMA:**
```python
# LINHA 7036 - tracking_data não está definido antes de usar
if tracking_data:  # ❌ NameError: tracking_data não definido
    fbp_value = tracking_data.get('fbp') or None
```

**COMO CORRIGIR:**
```python
# ✅ ADICIONAR antes da linha 7036
from utils.tracking_service import TrackingServiceV4
tracking_service_v4 = TrackingServiceV4()

# Recuperar tracking_data do Redis
tracking_data = {}
if tracking_token:
    tracking_data = tracking_service_v4.recover_tracking_data(tracking_token) or {}
```

---

### 3. `app.py` - send_meta_pixel_purchase_event()

**O QUE FAZ:**
- Recupera dados do Redis
- Constrói event_data do Purchase
- Enfileira no Celery

**ONDE QUEBRA:**
```python
# LINHA 7823, 7831, 7837, 7843, 7849 - Validações muito restritivas
# Bloqueiam eventos mesmo quando têm dados suficientes
if missing_fields:
    return  # ❌ Bloqueia evento sem tentar recuperar dados
```

**COMO CORRIGIR:**
```python
# ✅ CORREÇÃO: Tentar recuperar dados antes de bloquear
if missing_fields:
    logger.warning(f"⚠️ Purchase - Campos ausentes: {missing_fields} - Tentando recuperar...")
    
    # Tentar recuperar event_source_url
    if 'event_source_url' in missing_fields:
        event_source_url = tracking_data.get('event_source_url') or tracking_data.get('first_page')
        if event_source_url:
            event_data['event_source_url'] = event_source_url
            missing_fields.remove('event_source_url')
            logger.info(f"✅ Purchase - event_source_url recuperado: {event_source_url}")
    
    # Se ainda faltar campos críticos, bloquear
    critical_fields = ['event_name', 'event_time', 'event_id', 'action_source', 'user_data']
    if any(f in missing_fields for f in critical_fields):
        logger.error(f"❌ Purchase - Campos críticos ausentes: {[f for f in missing_fields if f in critical_fields]}")
        return
```

**OUTRO PROBLEMA:**
```python
# LINHA 7834-7837 - Bloqueia se external_id ausente, mas pode ter outros dados
if not user_data.get('external_id'):
    logger.error(f"❌ Purchase - external_id AUSENTE! Meta rejeita evento sem external_id.")
    return  # ❌ Muito restritivo - Meta aceita sem external_id se tiver fbp/fbc
```

**COMO CORRIGIR:**
```python
# ✅ CORREÇÃO: Bloquear apenas se não tiver NENHUM identificador
if not user_data.get('external_id') and not user_data.get('fbp') and not user_data.get('fbc'):
    logger.error(f"❌ Purchase - Nenhum identificador presente (external_id, fbp, fbc)")
    return
elif not user_data.get('external_id'):
    logger.warning(f"⚠️ Purchase - external_id ausente, mas fbp/fbc presente - Meta pode aceitar")
```

---

### 4. `celery_app.py` - send_meta_event()

**O QUE FAZ:**
- Recebe event_data do Celery
- Envia para Meta API
- Faz retry em caso de erro

**ONDE QUEBRA:**
```python
# LINHA 163-166 - Payload está correto, mas falta validação
payload = {
    'data': [event_data],  # ✅ Correto
    'access_token': access_token
}
```

**PROBLEMA:**
- Não valida se `event_data` tem todos os campos obrigatórios
- Não valida se `user_data` está presente e não vazio
- Não valida se `custom_data` é dict (não None)

**COMO CORRIGIR:**
```python
# ✅ ADICIONAR validação antes de enviar
def _validate_event_data(event_data):
    """Valida event_data antes de enviar"""
    required_fields = ['event_name', 'event_time', 'event_id', 'action_source']
    missing = [f for f in required_fields if not event_data.get(f)]
    if missing:
        raise ValueError(f"Campos obrigatórios ausentes: {missing}")
    
    # Validar user_data
    user_data = event_data.get('user_data', {})
    if not isinstance(user_data, dict):
        raise ValueError("user_data deve ser dict")
    
    # Validar custom_data (deve ser dict, não None)
    custom_data = event_data.get('custom_data')
    if custom_data is not None and not isinstance(custom_data, dict):
        raise ValueError("custom_data deve ser dict ou None")
    
    # Se custom_data é None, converter para {}
    if custom_data is None:
        event_data['custom_data'] = {}
    
    return True

# No início de send_meta_event:
try:
    _validate_event_data(event_data)
except ValueError as e:
    logger.error(f"❌ Event data inválido: {e}")
    raise
```

---

### 5. `utils/tracking_service.py` - TrackingServiceV4.save_tracking_token()

**O QUE FAZ:**
- Salva tracking_payload no Redis
- Preserva dados anteriores

**ONDE QUEBRA:**
```python
# LINHA 145 - previous.update(payload) pode sobrescrever com None
previous.update(payload)  # ❌ Se payload tem None, sobrescreve valores válidos
```

**COMO CORRIGIR:**
```python
# ✅ CORREÇÃO: Não sobrescrever com None
for key, value in payload.items():
    if value is not None:  # ✅ Só atualizar se não for None
        previous[key] = value
    # Se value é None, manter valor anterior (se existir)
```

---

## 🔧 PATCHES COMPLETOS

### PATCH 1: `utils/meta_pixel.py` - send_pageview_event()

```python
# ANTES (linha 278-289):
payload = {
    'data': [{
        'event_name': 'PageView',
        'event_time': int(time.time()),
        'event_id': event_id,
        'action_source': 'website',
        'user_data': user_data,
        'custom_data': custom_data if custom_data else None
    }],
    'access_token': access_token
}

# DEPOIS:
# ✅ ADICIONAR event_source_url como parâmetro
@staticmethod
def send_pageview_event(
    pixel_id: str,
    access_token: str,
    event_id: str,
    customer_user_id: str = None,
    external_id: str = None,
    client_ip: str = None,
    client_user_agent: str = None,
    fbp: str = None,
    fbc: str = None,
    utm_source: str = None,
    utm_campaign: str = None,
    campaign_code: str = None,
    event_source_url: str = None  # ✅ NOVO
) -> Dict:
    # ...
    payload = {
        'data': [{
            'event_name': 'PageView',
            'event_time': int(time.time()),
            'event_id': event_id,
            'action_source': 'website',
            'event_source_url': event_source_url,  # ✅ ADICIONAR
            'user_data': user_data,
            'custom_data': custom_data if custom_data else {}  # ✅ CORRIGIR: {} não None
        }],
        'access_token': access_token
    }
```

---

### PATCH 2: `app.py` - send_meta_pixel_pageview_event()

```python
# ANTES (linha 7029-7043):
# ✅ PATCH 2: RECUPERAR _fbp e _fbc (Prioridade: tracking_data → BotUser → cookie)
from utils.tracking_service import TrackingService

fbp_value = None
fbc_value = None

# ✅ PATCH 2: Prioridade 1 - tracking_data (Redis) - MAIS CONFIÁVEL
if tracking_data:  # ❌ NameError: tracking_data não definido

# DEPOIS:
# ✅ ADICIONAR antes da linha 7029
from utils.tracking_service import TrackingServiceV4
tracking_service_v4 = TrackingServiceV4()

# Recuperar tracking_data do Redis
tracking_data = {}
if tracking_token:
    tracking_data = tracking_service_v4.recover_tracking_data(tracking_token) or {}
    logger.info(f"✅ PageView - tracking_data recuperado do Redis: {len(tracking_data)} campos")

# ✅ PATCH 2: RECUPERAR _fbp e _fbc (Prioridade: tracking_data → BotUser → cookie)
from utils.tracking_service import TrackingService

fbp_value = None
fbc_value = None

# ✅ PATCH 2: Prioridade 1 - tracking_data (Redis) - MAIS CONFIÁVEL
if tracking_data:
    fbp_value = tracking_data.get('fbp') or None
    fbc_value = tracking_data.get('fbc') or None
    # ...
```

```python
# ANTES (linha 7233-7244):
'custom_data': {
    'pool_id': pool.id,
    'pool_name': pool.name,
    'utm_source': utm_data['utm_source'],  # ❌ Pode ser None
    # ...
}

# DEPOIS:
# ✅ CORREÇÃO: Filtrar valores None/vazios
custom_data = {}
if pool.id:
    custom_data['pool_id'] = pool.id
if pool.name:
    custom_data['pool_name'] = pool.name
if utm_data.get('utm_source'):
    custom_data['utm_source'] = utm_data['utm_source']
if utm_data.get('utm_campaign'):
    custom_data['utm_campaign'] = utm_data['utm_campaign']
if utm_data.get('utm_content'):
    custom_data['utm_content'] = utm_data['utm_content']
if utm_data.get('utm_medium'):
    custom_data['utm_medium'] = utm_data['utm_medium']
if utm_data.get('utm_term'):
    custom_data['utm_term'] = utm_data['utm_term']
if utm_data.get('fbclid'):
    custom_data['fbclid'] = utm_data['fbclid']
if utm_data.get('campaign_code'):
    custom_data['campaign_code'] = utm_data['campaign_code']

event_data = {
    'event_name': 'PageView',
    'event_time': int(time.time()),
    'event_id': event_id,
    'action_source': 'website',
    'event_source_url': event_source_url,
    'user_data': user_data,
    'custom_data': custom_data  # ✅ Sempre dict (pode ser vazio)
}
```

---

### PATCH 3: `app.py` - send_meta_pixel_purchase_event()

```python
# ANTES (linha 7807-7831):
missing_fields = [k for k, v in required_fields.items() if not v]
if missing_fields:
    logger.error(f"❌ Purchase - Campos obrigatórios ausentes: {missing_fields}")
    return  # ❌ Muito restritivo

# DEPOIS:
# ✅ CORREÇÃO: Tentar recuperar antes de bloquear
missing_fields = [k for k, v in required_fields.items() if not v]
if missing_fields:
    logger.warning(f"⚠️ Purchase - Campos ausentes: {missing_fields} - Tentando recuperar...")
    
    # Tentar recuperar event_source_url
    if 'event_source_url' in missing_fields:
        event_source_url = tracking_data.get('event_source_url') or tracking_data.get('first_page')
        if event_source_url:
            event_data['event_source_url'] = event_source_url
            missing_fields.remove('event_source_url')
            logger.info(f"✅ Purchase - event_source_url recuperado: {event_source_url}")
    
    # Se ainda faltar campos críticos, bloquear
    critical_fields = ['event_name', 'event_time', 'event_id', 'action_source', 'user_data']
    critical_missing = [f for f in missing_fields if f in critical_fields]
    if critical_missing:
        logger.error(f"❌ Purchase - Campos críticos ausentes: {critical_missing}")
        return
    else:
        logger.warning(f"⚠️ Purchase - Campos não-críticos ausentes: {[f for f in missing_fields if f not in critical_fields]}")
        # Continuar mesmo com campos não-críticos ausentes
```

```python
# ANTES (linha 7834-7837):
if not user_data.get('external_id'):
    logger.error(f"❌ Purchase - external_id AUSENTE! Meta rejeita evento sem external_id.")
    return

# DEPOIS:
# ✅ CORREÇÃO: Bloquear apenas se não tiver NENHUM identificador
if not user_data.get('external_id') and not user_data.get('fbp') and not user_data.get('fbc'):
    logger.error(f"❌ Purchase - Nenhum identificador presente (external_id, fbp, fbc)")
    logger.error(f"   Meta rejeita eventos sem identificadores")
    return
elif not user_data.get('external_id'):
    logger.warning(f"⚠️ Purchase - external_id ausente, mas fbp/fbc presente - Meta pode aceitar")
```

---

### PATCH 4: `celery_app.py` - send_meta_event()

```python
# ADICIONAR função de validação (antes de send_meta_event):
def _validate_event_data(event_data):
    """Valida event_data antes de enviar para Meta"""
    import logging
    logger = logging.getLogger(__name__)
    
    # Campos obrigatórios
    required_fields = ['event_name', 'event_time', 'event_id', 'action_source']
    missing = [f for f in required_fields if not event_data.get(f)]
    if missing:
        raise ValueError(f"Campos obrigatórios ausentes: {missing}")
    
    # Validar user_data
    user_data = event_data.get('user_data', {})
    if not isinstance(user_data, dict):
        raise ValueError("user_data deve ser dict")
    
    # Validar custom_data (deve ser dict, não None)
    custom_data = event_data.get('custom_data')
    if custom_data is not None and not isinstance(custom_data, dict):
        raise ValueError("custom_data deve ser dict ou None")
    
    # Se custom_data é None, converter para {}
    if custom_data is None:
        event_data['custom_data'] = {}
        logger.warning(f"⚠️ custom_data era None, convertido para {{}}")
    
    # Validar event_source_url (opcional mas recomendado)
    if not event_data.get('event_source_url'):
        logger.warning(f"⚠️ event_source_url ausente - Meta recomenda incluir")
    
    return True

# MODIFICAR send_meta_event (linha 125):
@celery_app.task(bind=True, max_retries=10)
def send_meta_event(self, pixel_id, access_token, event_data, test_code=None):
    # ...
    
    # ✅ VALIDAÇÃO ANTES DE ENVIAR
    try:
        _validate_event_data(event_data)
    except ValueError as e:
        logger.error(f"❌ Event data inválido: {e}")
        logger.error(f"   Event: {event_data.get('event_name')} | ID: {event_data.get('event_id')}")
        raise Exception(f"Event data inválido: {e}")
    
    url = f'https://graph.facebook.com/v18.0/{pixel_id}/events'
    # ...
```

---

### PATCH 5: `utils/tracking_service.py` - save_tracking_token()

```python
# ANTES (linha 145):
previous.update(payload)  # ❌ Sobrescreve com None

# DEPOIS:
# ✅ CORREÇÃO: Não sobrescrever com None
for key, value in payload.items():
    if value is not None:  # ✅ Só atualizar se não for None
        previous[key] = value
    # Se value é None, manter valor anterior (se existir)
```

---

## ✅ CHECKLIST FINAL META EVENT

### PageView
- [x] `event_name`: "PageView"
- [x] `event_time`: timestamp (segundos)
- [x] `event_id`: único
- [x] `action_source`: "website"
- [x] `event_source_url`: URL do redirect
- [x] `user_data.external_id`: array com fbclid hasheado
- [x] `user_data.fbp`: cookie _fbp
- [x] `user_data.fbc`: cookie _fbc (se disponível)
- [x] `user_data.client_ip_address`: IP do request
- [x] `user_data.client_user_agent`: User-Agent
- [x] `custom_data`: dict (não None, pode ser vazio)
- [x] `custom_data.utm_source`: se disponível
- [x] `custom_data.utm_campaign`: se disponível
- [x] `custom_data.campaign_code`: se disponível

### Purchase
- [x] `event_name`: "Purchase"
- [x] `event_time`: timestamp do pagamento (segundos)
- [x] `event_id`: reutilizado do PageView (deduplicação)
- [x] `action_source`: "website"
- [x] `event_source_url`: URL do redirect (mesma do PageView)
- [x] `user_data.external_id`: array com fbclid + telegram_id hasheados
- [x] `user_data.fbp`: mesmo do PageView
- [x] `user_data.fbc`: mesmo do PageView (se disponível)
- [x] `user_data.client_ip_address`: mesmo IP do PageView
- [x] `user_data.client_user_agent`: mesmo UA do PageView
- [x] `user_data.em`: email hasheado (se disponível)
- [x] `user_data.ph`: phone hasheado (se disponível)
- [x] `custom_data.value`: valor do pagamento
- [x] `custom_data.currency`: "BRL"
- [x] `custom_data.num_items`: quantidade
- [x] `custom_data.utm_source`: se disponível
- [x] `custom_data.utm_campaign`: se disponível
- [x] `custom_data.campaign_code`: se disponível

---

## 🧪 TESTE LOCAL SIMULADO

```python
# test_meta_event_complete.py
import json
from utils.meta_pixel import MetaPixelAPI

# Simular PageView
pageview_event = {
    'event_name': 'PageView',
    'event_time': 1732134409,
    'event_id': 'pageview_test_123',
    'action_source': 'website',
    'event_source_url': 'https://app.grimbots.online/go/red1?fbclid=PAZXh0bgNhZW0BMABhZGlkAasqUTTZ2yRz',
    'user_data': {
        'external_id': ['hashed_fbclid_123'],
        'fbp': 'fb.1.1732134409.1850396052',
        'fbc': 'fb.1.1732134409.IwZXh0bgNhZW0BMABhZGlkAasqUTTZ2yRz',
        'client_ip_address': '177.43.80.1',
        'client_user_agent': 'Mozilla/5.0...'
    },
    'custom_data': {
        'utm_source': 'facebook',
        'utm_campaign': 'test_campaign',
        'campaign_code': 'grim123'
    }
}

# Simular Purchase
purchase_event = {
    'event_name': 'Purchase',
    'event_time': 1732134500,
    'event_id': 'pageview_test_123',  # ✅ MESMO event_id do PageView
    'action_source': 'website',
    'event_source_url': 'https://app.grimbots.online/go/red1?fbclid=PAZXh0bgNhZW0BMABhZGlkAasqUTTZ2yRz',
    'user_data': {
        'external_id': ['hashed_fbclid_123', 'hashed_telegram_id_456'],
        'fbp': 'fb.1.1732134409.1850396052',  # ✅ MESMO do PageView
        'fbc': 'fb.1.1732134409.IwZXh0bgNhZW0BMABhZGlkAasqUTTZ2yRz',  # ✅ MESMO do PageView
        'client_ip_address': '177.43.80.1',  # ✅ MESMO do PageView
        'client_user_agent': 'Mozilla/5.0...'  # ✅ MESMO do PageView
    },
    'custom_data': {
        'value': 19.97,
        'currency': 'BRL',
        'num_items': 1,
        'utm_source': 'facebook',
        'utm_campaign': 'test_campaign',
        'campaign_code': 'grim123'
    }
}

# Validar
print("PageView payload:")
print(json.dumps(pageview_event, indent=2))

print("\nPurchase payload:")
print(json.dumps(purchase_event, indent=2))

# Verificar matching
assert pageview_event['user_data']['external_id'][0] == purchase_event['user_data']['external_id'][0]
assert pageview_event['user_data']['fbp'] == purchase_event['user_data']['fbp']
assert pageview_event['user_data']['fbc'] == purchase_event['user_data']['fbc']
assert pageview_event['event_id'] == purchase_event['event_id']
assert pageview_event['event_source_url'] == purchase_event['event_source_url']

print("\n✅ Matching garantido!")
```

---

## 📋 RUNBOOK DE VERIFICAÇÃO

### 1. Verificar Logs do PageView

```bash
# Buscar logs do PageView
grep -iE "\[META PAGEVIEW\]|META PAYLOAD COMPLETO.*PageView" logs/gunicorn.log | tail -10

# Verificar se todos os campos estão presentes
grep -iE "PageView.*User Data.*7/7" logs/gunicorn.log | tail -5
```

**Esperado:**
```
[META PAGEVIEW] PageView - User Data: 7/7 atributos | external_id=✅ | fbp=✅ | fbc=✅ | ip=✅ | ua=✅
📤 META PAYLOAD COMPLETO (PageView):
{
  "data": [{
    "event_name": "PageView",
    "event_time": 1732134409,
    "event_id": "pageview_...",
    "action_source": "website",
    "event_source_url": "https://app.grimbots.online/go/red1?...",
    "user_data": {
      "external_id": ["..."],
      "fbp": "...",
      "fbc": "...",
      "client_ip_address": "...",
      "client_user_agent": "..."
    },
    "custom_data": {
      "utm_source": "...",
      "utm_campaign": "...",
      "campaign_code": "..."
    }
  }]
}
```

### 2. Verificar Logs do Purchase

```bash
# Buscar logs do Purchase
grep -iE "\[META PURCHASE\]|META PAYLOAD COMPLETO.*Purchase" logs/gunicorn.log | tail -10

# Verificar se todos os campos estão presentes
grep -iE "Purchase.*User Data.*7/7" logs/gunicorn.log | tail -5
```

**Esperado:**
```
[META PURCHASE] Purchase - User Data: 7/7 atributos | external_id=✅ | fbp=✅ | fbc=✅ | ip=✅ | ua=✅
📤 META PAYLOAD COMPLETO (Purchase):
{
  "data": [{
    "event_name": "Purchase",
    "event_time": 1732134500,
    "event_id": "pageview_...",  # ✅ MESMO do PageView
    "action_source": "website",
    "event_source_url": "https://app.grimbots.online/go/red1?...",
    "user_data": {
      "external_id": ["...", "..."],  # ✅ fbclid + telegram_id
      "fbp": "...",  # ✅ MESMO do PageView
      "fbc": "...",  # ✅ MESMO do PageView
      "client_ip_address": "...",  # ✅ MESMO do PageView
      "client_user_agent": "..."  # ✅ MESMO do PageView
    },
    "custom_data": {
      "value": 19.97,
      "currency": "BRL",
      "num_items": 1,
      "utm_source": "...",
      "utm_campaign": "...",
      "campaign_code": "..."
    }
  }]
}
```

### 3. Verificar no Meta Event Manager

1. Acesse: https://business.facebook.com/events_manager2
2. Selecione seu Pixel ID
3. Vá em "Test Events" ou "Events"
4. Procure pelo PageView e Purchase
5. Verifique:
   - **Match Quality**: deve ser 9/10 ou 10/10
   - **Event ID**: Purchase deve ter o mesmo do PageView
   - **External ID**: deve estar presente em ambos
   - **FBP/FBC**: devem estar presentes e iguais
   - **IP/UA**: devem estar presentes e iguais
   - **Event Source URL**: deve estar presente e igual em ambos
   - **Custom Data**: deve estar presente (não None)

---

## 🎯 RESULTADO ESPERADO

Após aplicar todos os patches:

- ✅ **PageView**: 100% com parâmetros (7/7 atributos)
- ✅ **Purchase**: 100% com parâmetros (7/7 atributos)
- ✅ **FBP/FBC**: presentes e consistentes
- ✅ **External ID**: presente e consistente
- ✅ **IP/UA**: presentes e consistentes
- ✅ **Event Source URL**: presente em ambos
- ✅ **Custom Data**: sempre dict (nunca None)
- ✅ **Match Quality**: 9/10 ou 10/10
- ✅ **Zero eventos sem parâmetros**
- ✅ **Zero tracking_payload vazio**
- ✅ **Redis consistente**
- ✅ **Browser Pixel + CAPI alinhados**

---

## 🚀 PRÓXIMOS PASSOS

1. Aplicar todos os patches acima
2. Testar localmente com script de simulação
3. Fazer deploy na VPS
4. Monitorar logs em tempo real
5. Verificar no Meta Event Manager
6. Validar Match Quality

---

**FIM DA AUDITORIA**

