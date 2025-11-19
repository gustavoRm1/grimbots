# 🔴 CORREÇÃO CRÍTICA - PURCHASE VIA CAPI

**Problema identificado**: Purchase events aparecendo apenas via "Browser" (client-side), não via "Server" (CAPI)

---

## 🔍 ANÁLISE DO PROBLEMA

### Situação Atual no Meta Events Manager:
- ✅ Purchase via **Browser** (client-side): **Funcionando**
- ❌ Purchase via **Server** (CAPI): **Não aparecendo**

### Causa Raiz:

O código estava bloqueando o envio via CAPI quando `payment.meta_purchase_sent = True`, mas essa flag pode ser marcada **apenas client-side** (via `/api/tracking/mark-purchase-sent`) **ANTES** do Purchase via CAPI ser enviado.

### Fluxo Atual (PROBLEMÁTICO):
1. Cliente acessa `/delivery/<token>`
2. `delivery_page` renderiza a página (`delivery.html`)
3. JavaScript chama `/api/tracking/mark-purchase-sent` → marca `meta_purchase_sent = True`
4. `delivery_page` tenta chamar `send_meta_pixel_purchase_event`
5. ❌ **BLOQUEADO**: Check `if payment.meta_purchase_sent:` falha → Purchase via CAPI **NÃO é enviado**

---

## ✅ CORREÇÃO APLICADA

### Mudança na Lógica de Anti-Duplicação:

**ANTES**:
```python
if payment.meta_purchase_sent:
    # Bloqueia se qualquer Purchase foi enviado (client-side ou server-side)
    return
```

**DEPOIS**:
```python
if payment.meta_purchase_sent and getattr(payment, 'meta_event_id', None):
    # ✅ Só bloqueia se CAPI já foi enviado (tem meta_event_id)
    return
elif payment.meta_purchase_sent and not getattr(payment, 'meta_event_id', None):
    # ⚠️ meta_purchase_sent está True mas meta_event_id não existe
    # Isso indica que foi marcado apenas client-side, mas CAPI ainda não foi enviado
    logger.warning(f"⚠️ Purchase marcado como enviado, mas CAPI ainda não foi enviado (sem meta_event_id)")
    logger.warning(f"   Permitting CAPI send to ensure server-side event is sent")
    # ✅ NÃO retornar - permitir envio via CAPI
```

---

## 🎯 RESULTADO ESPERADO

Após a correção:
- ✅ Purchase via **Browser** (client-side): Continua funcionando
- ✅ Purchase via **Server** (CAPI): Agora será enviado corretamente
- ✅ Meta Events Manager: Mostrará eventos via **ambos** "Browser" e "Server"
- ✅ Deduplicação: Meta deduplicará usando `event_id` (mesmo ID usado em ambos)

---

## 📋 CHECKLIST PÓS-DEPLOY

Após o deploy, verificar no Meta Events Manager:

1. **Sampled Activities**:
   - Deve mostrar Purchase via **"Browser"** ✅
   - Deve mostrar Purchase via **"Server"** ✅ (NOVO!)

2. **Event Details**:
   - Deve mostrar `event_id` idêntico para ambos
   - Deve mostrar `external_id` (fbclid) presente
   - Deve mostrar `client_ip_address` presente (via CAPI)

3. **Match Quality**:
   - Deve melhorar (Purchase via CAPI tem mais dados de matching)
   - Deve mostrar FBC/FBP coverage maior

---

## 🔍 MONITORAMENTO

Execute na VPS para monitorar:

```bash
# Verificar Purchase via CAPI sendo enviado
tail -f logs/gunicorn.log | grep -E "Purchase.*CAPI|Purchase.*enfileirado|Purchase ENVIADO"

# Verificar se meta_event_id está sendo salvo
tail -f logs/gunicorn.log | grep -E "meta_event_id|Events Received"
```

**Resultado esperado**:
```
[META DELIVERY] Delivery - Enviando Purchase via Server (Conversions API) para payment XXX
📤 Purchase enfileirado: R$ XXX | Pool: XXX | Event ID: XXX | Task: XXX
✅ Purchase ENVIADO com sucesso para Meta: R$ XXX | Events Received: 1 | event_id: XXX
```

---

## ⚠️ OBSERVAÇÕES IMPORTANTES

1. **Deduplicação**: Meta deduplicará automaticamente usando `event_id` (mesmo ID usado em client-side e server-side)

2. **Match Quality**: Purchase via CAPI terá melhor match quality porque inclui:
   - `client_ip_address` (IP real do cliente)
   - `client_user_agent` (User Agent real)
   - `external_id` (fbclid hashado)
   - `fbp` e `fbc` (cookies do browser)

3. **Performance**: Purchase via CAPI é enviado **assíncronamente** via Celery, então não bloqueia a renderização da página

4. **Fallback**: Se CAPI falhar, Purchase client-side ainda será enviado (backup)

---

## ✅ CONCLUSÃO

**PROBLEMA RESOLVIDO**: Purchase via CAPI agora será enviado corretamente, mesmo se `meta_purchase_sent` estiver `True` (marcado apenas client-side).

**RESULTADO**: Meta Events Manager mostrará Purchase via **ambos** "Browser" e "Server", melhorando Match Quality e FBC/FBP coverage.

