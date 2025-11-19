# 🔴 CORREÇÕES URGENTES - TRACKING META PIXEL

## 📊 PROBLEMAS IDENTIFICADOS

1. **FBC com baixa cobertura** - Meta reclamando que FBC não está sendo enviado
2. **Purchase apenas via Browser** - Não está sendo enviado via Server (Conversions API)
3. **Match Quality baixo** - PageView 6.1/10, ViewContent 4.4/10

## ✅ CORREÇÕES IMPLEMENTADAS

### 1. Purchase via Server (Conversions API)

**Problema:** Purchase estava sendo enviado apenas via Browser (client-side), não via Server.

**Solução:** Adicionado envio via Server na página de entrega (`app.py:7478-7487`)

```python
# ✅ CRÍTICO: ENVIAR PURCHASE VIA SERVER (Conversions API) TAMBÉM!
if has_meta_pixel and not payment.meta_purchase_sent:
    try:
        logger.info(f"[META DELIVERY] Delivery - Enviando Purchase via Server (Conversions API) para payment {payment.id}")
        send_meta_pixel_purchase_event(payment)
        logger.info(f"[META DELIVERY] Delivery - Purchase via Server enfileirado com sucesso")
    except Exception as e:
        logger.error(f"❌ Erro ao enviar Purchase via Server: {e}", exc_info=True)
```

**Status:** ✅ Implementado

---

### 2. FBP e FBC no pixel_config (delivery.html)

**Problema:** FBP e FBC não estavam sendo incluídos no `pixel_config` da página de entrega, então client-side não enviava esses dados.

**Solução:** Adicionado FBP e FBC ao `pixel_config` (`app.py:7461-7476`)

```python
# ✅ Renderizar página com Purchase tracking (INCLUINDO FBP E FBC!)
pixel_config = {
    'pixel_id': pool.meta_pixel_id if has_meta_pixel else None,
    'event_id': pageview_event_id or f"purchase_{payment.id}_{int(time.time())}",
    'external_id': external_id or '',
    'fbp': fbp_value or '',  # ✅ CRÍTICO: FBP para matching perfeito
    'fbc': fbc_value or '',  # ✅ CRÍTICO: FBC para matching perfeito (apenas se real)
    'value': float(payment.amount),
    # ... outros campos
}
```

**Status:** ✅ Implementado

---

### 3. FBP e FBC no client-side (delivery.html)

**Problema:** Client-side não estava enviando `_fbp` e `_fbc` no evento Purchase.

**Solução:** Adicionado `_fbp` e `_fbc` ao `fbq('track', 'Purchase', ...)` (`templates/delivery.html:22-34`)

```javascript
fbq('track', 'Purchase', {
    value: {{ pixel_config.value }},
    currency: '{{ pixel_config.currency }}',
    eventID: '{{ pixel_config.event_id }}',
    content_ids: ['{{ pixel_config.content_id }}'],
    content_name: '{{ pixel_config.content_name|replace("'", "\\'") }}',
    content_type: 'product',
    num_items: 1{% if pixel_config.fbp %},
    _fbp: '{{ pixel_config.fbp }}'  // ✅ CRÍTICO: FBP para matching perfeito
    {% endif %}{% if pixel_config.fbc %},
    _fbc: '{{ pixel_config.fbc }}'  // ✅ CRÍTICO: FBC para matching perfeito
    {% endif %}
});
```

**Status:** ✅ Implementado

---

## 🔍 VERIFICAÇÕES NECESSÁRIAS

### 1. Verificar se FBC está sendo gerado corretamente

**Onde verificar:**
- Logs: `[META REDIRECT] Redirect - fbc gerado baseado em fbclid`
- Redis: Verificar se `fbc_origin = 'generated_from_fbclid'` está sendo salvo
- Eventos: Verificar se FBC está sendo enviado no PageView

**Comando:**
```bash
tail -f logs/gunicorn.log | grep "fbc"
```

---

### 2. Verificar se Purchase está sendo enviado via Server

**Onde verificar:**
- Logs: `[META DELIVERY] Delivery - Purchase via Server enfileirado`
- Celery: Verificar tasks de Purchase no Redis
- Meta Events Manager: Verificar se Purchase aparece como "Browser • Server"

**Comando:**
```bash
tail -f logs/gunicorn.log | grep "META DELIVERY\|META PURCHASE"
```

---

### 3. Verificar Match Quality

**Onde verificar:**
- Meta Events Manager: Verificar Match Quality de cada evento
- Logs: Verificar quantidade de atributos enviados (7/7 = Match Quality máxima)

**Comando:**
```bash
tail -f logs/gunicorn.log | grep "User Data.*atributos"
```

---

## 🚀 PRÓXIMOS PASSOS

1. **Testar redirect** - Verificar se FBC está sendo gerado e salvo
2. **Testar Purchase** - Verificar se está sendo enviado via Server
3. **Monitorar Meta Events Manager** - Verificar Match Quality após 24-48h
4. **Verificar logs** - Identificar eventos sem FBC/FBP

---

## 📝 NOTAS IMPORTANTES

### FBC (Facebook Click ID)

**Formato correto:**
```
fb.1.{timestamp_ms}.{fbclid}
```

**Exemplo:**
```
fb.1.1729440000000.IwAR1234567890abcdef
```

**Validação:**
- ✅ FBC do cookie (browser) → `fbc_origin = 'cookie'` → SEMPRE enviar
- ✅ FBC gerado baseado em fbclid → `fbc_origin = 'generated_from_fbclid'` → SEMPRE enviar
- ❌ FBC sintético (gerado sem fbclid) → `fbc_origin = 'synthetic'` → NUNCA enviar

### FBP (Facebook Pixel)

**Formato correto:**
```
fb.1.{timestamp_ms}.{random}
```

**Exemplo:**
```
fb.1.1729440000000.1234567890
```

**Validação:**
- ✅ FBP do cookie (browser) → SEMPRE usar
- ✅ FBP gerado no servidor → Usar como fallback

---

## ✅ CHECKLIST DE VERIFICAÇÃO

- [ ] FBC está sendo gerado quando fbclid está presente?
- [ ] FBC está sendo salvo no Redis com `fbc_origin` correto?
- [ ] FBC está sendo enviado em todos os eventos (PageView, ViewContent, Purchase)?
- [ ] Purchase está sendo enviado via Server (Conversions API)?
- [ ] Purchase está sendo enviado via Browser (client-side) com FBP/FBC?
- [ ] Match Quality está melhorando (>= 8/10)?
- [ ] Meta Events Manager mostra "Browser • Server" para Purchase?

---

**Documentação criada em:** 2025-01-19  
**Versão:** 1.0  
**Status:** ✅ Correções implementadas - Aguardando validação

