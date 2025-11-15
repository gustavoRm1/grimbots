# 🔥 CORREÇÃO ERRO 415 — BEACON API (QI 500)

## 📋 PROBLEMA IDENTIFICADO

### **Erro 415: Unsupported Media Type**
```
ERROR - [META TRACKING] Erro ao capturar cookies: 415 Unsupported Media Type: Did not attempt to load JSON data because the request Content-Type was not 'application/json'.
```

### **Causa Raiz:**
1. **`navigator.sendBeacon()` não envia header `Content-Type: application/json`**
   - Beacon API envia dados como `text/plain` por padrão
   - Flask não consegue parsear JSON automaticamente sem o header `Content-Type`
   - Endpoint retorna erro 415 (Unsupported Media Type)

2. **Cookies não estão sendo salvos no Redis**
   - Erro 415 impede que cookies sejam processados
   - Tracking data não é atualizado com cookies do browser
   - Purchase event não encontra FBC no Redis

3. **Tracking token diferente entre redirect e purchase**
   - Redirect gera `tracking_token = uuid.uuid4().hex` (32 chars)
   - Purchase usa `payment.tracking_token` que pode ser `tracking_xxx` (formato diferente)
   - Dados de tracking salvos no redirect não são encontrados no purchase

---

## ✅ CORREÇÕES APLICADAS

### **1. Endpoint `/api/tracking/cookies` - Aceitar dados sem Content-Type**

**ANTES:**
```python
data = request.json  # ❌ Falha se Content-Type não estiver presente
if not data:
    return jsonify({'success': False, 'error': 'Invalid JSON'}), 400
```

**DEPOIS:**
```python
# ✅ CORREÇÃO CRÍTICA: Beacon API não envia Content-Type: application/json
# Precisamos parsear manualmente usando request.get_data()
import json as json_lib

# ✅ Tentar parsear como JSON primeiro (se Content-Type estiver presente)
data = None
if request.is_json:
    data = request.json
else:
    # ✅ Fallback: Parsear manualmente do body (Beacon API envia como text/plain)
    try:
        raw_data = request.get_data(as_text=True)
        if raw_data:
            data = json_lib.loads(raw_data)
    except (json_lib.JSONDecodeError, ValueError) as e:
        logger.warning(f"[META TRACKING] Erro ao parsear JSON do body: {e}")
        # ✅ Último fallback: Tentar parsear como form data
        if request.form:
            data = {
                'tracking_token': request.form.get('tracking_token'),
                '_fbp': request.form.get('_fbp'),
                '_fbc': request.form.get('_fbc')
            }
```

### **2. Validação de tracking_token - Aceitar múltiplos formatos**

**ANTES:**
```python
# ✅ Validar formato do tracking_token (deve ser UUID hex de 32 chars)
if len(tracking_token) != 32 or not all(c in '0123456789abcdef' for c in tracking_token):
    return jsonify({'success': False, 'error': 'Invalid tracking_token format'}), 400
```

**DEPOIS:**
```python
# ✅ Validar formato do tracking_token (pode ser UUID hex de 32 chars ou tracking_xxx)
# Formato 1: UUID hex de 32 chars (ex: 71ab1909f5d44c969241...)
# Formato 2: tracking_xxx (ex: tracking_0245156101f95efcb74b9...)
is_valid_uuid = len(tracking_token) == 32 and all(c in '0123456789abcdef' for c in tracking_token)
is_valid_tracking = tracking_token.startswith('tracking_') and len(tracking_token) > 9

if not (is_valid_uuid or is_valid_tracking):
    logger.warning(f"[META TRACKING] tracking_token inválido: {tracking_token[:30]}... (len={len(tracking_token)})")
    return jsonify({'success': False, 'error': 'Invalid tracking_token format'}), 400
```

### **3. HTML Bridge - Usar Blob com sendBeacon**

**ANTES:**
```javascript
const sent = navigator.sendBeacon('/api/tracking/cookies', payload);
// ❌ Beacon API não envia Content-Type: application/json
```

**DEPOIS:**
```javascript
// ✅ CORREÇÃO: Usar Blob com sendBeacon para garantir Content-Type correto
// Beacon API não envia Content-Type automaticamente, então precisamos usar Blob
if (navigator.sendBeacon) {
    try {
        // ✅ Criar Blob com Content-Type: application/json
        const blob = new Blob([payload], { type: 'application/json' });
        const sent = navigator.sendBeacon('/api/tracking/cookies', blob);
        if (sent) {
            cookiesSent = true;
            console.log('[META PIXEL] Cookies enviados para servidor via Beacon API');
        } else {
            // ✅ Fallback para fetch se Beacon falhar
            sendCookiesViaFetch(payload);
        }
    } catch (e) {
        // ✅ Fallback para fetch se Beacon lançar exceção
        sendCookiesViaFetch(payload);
    }
} else {
    // ✅ Fallback para fetch (não bloqueia, keepalive garante envio mesmo após redirect)
    sendCookiesViaFetch(payload);
}
```

---

## 🧪 TESTE DA CORREÇÃO

### **1. Testar endpoint manualmente:**
```bash
# Teste 1: Com Content-Type header (deve funcionar)
curl -X POST https://app.grimbots.online/api/tracking/cookies \
  -H "Content-Type: application/json" \
  -d '{
    "tracking_token": "71ab1909f5d44c969241...",
    "_fbp": "fb.1.1763175459.7915916332",
    "_fbc": "fb.1.1762696947.IwZXh0bgNhZW0BMABhZGlkAFS9OzsVXAhz"
  }'

# Teste 2: Sem Content-Type header (Beacon API - deve funcionar agora)
curl -X POST https://app.grimbots.online/api/tracking/cookies \
  -d '{
    "tracking_token": "71ab1909f5d44c969241...",
    "_fbp": "fb.1.1763175459.7915916332",
    "_fbc": "fb.1.1762696947.IwZXh0bgNhZW0BMABhZGlkAFS9OzsVXAhz"
  }'
```

### **2. Verificar logs após correção:**
```bash
tail -f logs/gunicorn.log | grep -iE "\[META TRACKING\]"
```

**Logs esperados (SUCESSO):**
```
[META TRACKING] Cookie _fbp capturado do browser: fb.1.1763175459...
[META TRACKING] Cookie _fbc capturado do browser: fb.1.1762696947...
[META TRACKING] Tracking token atualizado com cookies: 71ab1909f5d44c969241... | fbp=✅, fbc=✅
```

**Logs esperados (ERRO - não deve mais aparecer):**
```
ERROR - [META TRACKING] Erro ao capturar cookies: 415 Unsupported Media Type
```

### **3. Verificar Redis após correção:**
```bash
# Conectar ao Redis
redis-cli

# Buscar tracking_token (substituir pelo token do log)
GET tracking:71ab1909f5d44c969241...

# Verificar se fbp e fbc estão presentes
# Resultado esperado: JSON com fbp, fbc, fbc_origin='cookie'
```

---

## 📊 RESULTADO ESPERADO

### **ANTES (Problema):**
- ❌ Erro 415 em 100% dos casos
- ❌ Cookies não são salvos no Redis
- ❌ FBC ausente no Purchase event
- ❌ Match Quality: 4-5/10

### **DEPOIS (Solução):**
- ✅ Erro 415 corrigido (0% de erros)
- ✅ Cookies são salvos no Redis via Beacon API
- ✅ FBC presente no Purchase event (quando disponível)
- ✅ Match Quality: 7-8/10 (com FBC)

---

## 🔍 DIAGNÓSTICO ADICIONAL

### **Problema #2: Tracking Token Diferente**

**Logs mostram:**
```
[META PURCHASE] Purchase - payment.tracking_token: tracking_0245156101f95efcb74b9... (len=33)
[META PURCHASE] Purchase - Campos no tracking_data: ['tracking_token', 'bot_id', 'customer_user_id', 'created_from', 'created_at', 'updated_at']
[META PURCHASE] Purchase - tracking_data recuperado do Redis: fbclid=❌, fbp=❌, fbc=❌, ip=❌, ua=❌
```

**Causa:**
- `payment.tracking_token` é `tracking_xxx` (gerado em `generate_pix_payment`)
- Dados de tracking (fbclid, fbp, fbc, ip, ua) foram salvos em `tracking_token` diferente (gerado no redirect)
- Purchase não encontra dados de tracking porque usa token diferente

**Solução:**
- ✅ Já corrigido: Endpoint aceita ambos os formatos (UUID hex e `tracking_xxx`)
- ⚠️ **PROBLEMA RESTANTE**: Garantir que mesmo `tracking_token` seja usado no redirect e no purchase
- 🔧 **PRÓXIMO PASSO**: Verificar se `bot_user.tracking_session_id` está sendo salvo corretamente

---

## 🎯 PRÓXIMOS PASSOS

1. ✅ **Testar correção do erro 415:**
   - Acessar URL de redirect
   - Verificar se cookies são enviados via Beacon API
   - Verificar se endpoint aceita dados sem Content-Type
   - Verificar se cookies são salvos no Redis

2. ⚠️ **Resolver problema de tracking_token diferente:**
   - Garantir que mesmo `tracking_token` seja usado no redirect e no purchase
   - Verificar se `bot_user.tracking_session_id` está sendo salvo corretamente
   - Verificar se `payment.tracking_token` está sendo salvo corretamente

3. 📊 **Validar Match Quality:**
   - Verificar se FBC está presente no Purchase event
   - Verificar Match Quality no Meta Events Manager
   - Monitorar atribuição de vendas no Meta Ads Manager

---

## 🚨 NOTAS IMPORTANTES

### **Beacon API Limitations:**
- ✅ Beacon API funciona mesmo após página fechar (ideal para redirects)
- ❌ Beacon API não envia Content-Type header automaticamente
- ✅ Solução: Usar Blob com `type: 'application/json'` OU parsear manualmente no servidor

### **Fallback Strategy:**
- ✅ Se Beacon API falhar, usar `fetch` com `keepalive: true`
- ✅ Se `fetch` falhar, usar `XMLHttpRequest` com `async: false` (último recurso)
- ✅ Endpoint aceita dados sem Content-Type (parsear manualmente)

---

## 📝 CONCLUSÃO

**Correção aplicada:** Endpoint `/api/tracking/cookies` agora aceita dados sem header `Content-Type: application/json`, parseando manualmente do body quando necessário.

**Resultado esperado:** Erro 415 corrigido, cookies sendo salvos no Redis via Beacon API, FBC presente no Purchase event quando disponível.

**Próximo passo:** Resolver problema de tracking_token diferente entre redirect e purchase para garantir que dados de tracking sejam encontrados corretamente.

