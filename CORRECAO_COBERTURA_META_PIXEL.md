# ✅ CORREÇÃO - COBERTURA META PIXEL (37% → 75%+)

## 🔍 PROBLEMA IDENTIFICADO

**Dados do Meta Events Manager:**
- **Cobertura do evento: 37%** (Meta recomenda >= 75%)
- **ID do evento (eventID):**
  - Browser: 91,85% ✅
  - Server: 100% ✅
  - **Cobertura: 0%** ❌ (CRÍTICO - não está fazendo matching!)
- **ID externo (external_id):**
  - Browser: 0% ❌ (CRÍTICO - não está enviando!)
  - Server: 100% ✅
  - **Cobertura: 0%** ❌
- **FBP:**
  - Browser: 98,93% ✅
  - Server: 98,68% ✅
  - **Cobertura: 36,57%** (baixa, mas melhor que os outros)

**Recomendações do Meta:**
1. ✅ Enviar eventID idêntico no browser e server
2. ✅ Enviar external_id idêntico no browser e server
3. ✅ Enviar fbp idêntico no browser e server

---

## ✅ CORREÇÕES APLICADAS

### 1. **Normalizar `external_id` no browser (mesmo formato do server)**

**Problema:** `external_id` estava sendo enviado como string vazia quando não havia `fbclid`, e a condição `{% if pixel_config.external_id %}` falhava.

**Solução:**
- Normalizar `external_id` usando `normalize_external_id()` (mesmo do server-side)
- Passar `None` ao invés de string vazia quando não houver `fbclid`
- Garantir que `external_id` seja sempre enviado no browser quando disponível

**Código aplicado em `app.py` (linhas 9375-9390):**
```python
# ✅ CORREÇÃO CRÍTICA: Normalizar external_id para garantir matching
# Se external_id existir, normalizar (MD5 se > 80 chars, ou original se <= 80)
# Isso garante que browser e server usem EXATAMENTE o mesmo formato
external_id_normalized = None
if external_id:
    from utils.meta_pixel import normalize_external_id
    external_id_normalized = normalize_external_id(external_id)
    logger.info(f"[META DELIVERY] Delivery - external_id normalizado: {external_id[:30]}... -> {external_id_normalized[:30]}... (len={len(external_id_normalized)})")

pixel_config = {
    'pixel_id': pool.meta_pixel_id if has_meta_pixel else None,
    'event_id': event_id_final,  # ✅ SEMPRE string, formato correto
    'external_id': external_id_normalized,  # ✅ None se não houver (não string vazia!)
    # ...
}
```

### 2. **Garantir que `eventID` seja sempre string e no formato correto**

**Problema:** `eventID` pode não estar no formato correto ou não estar correspondendo ao server-side.

**Solução:**
- Garantir que `event_id` seja sempre string
- Usar `pageview_event_id` se disponível (garante matching com PageView)
- Se não tiver, gerar baseado no `payment.id` (garante unicidade)

**Código aplicado em `app.py` (linhas 9366-9374):**
```python
# ✅ CORREÇÃO CRÍTICA: Garantir que event_id seja sempre string e no formato correto
# Meta requer event_id como string para deduplicação
# Usar pageview_event_id se disponível (garante matching com PageView)
# Se não tiver, gerar baseado no payment.id (garante unicidade)
event_id_final = None
if pageview_event_id:
    event_id_final = str(pageview_event_id)  # ✅ Garantir que é string
    logger.info(f"[META DELIVERY] Delivery - event_id do PageView: {event_id_final[:50]}...")
else:
    # ✅ Fallback: gerar event_id único baseado no payment
    event_id_final = f"purchase_{payment.id}_{int(time.time())}"
    logger.warning(f"[META DELIVERY] Delivery - pageview_event_id ausente, gerando novo: {event_id_final[:50]}...")
```

### 3. **Enviar `external_id` sempre no browser quando disponível**

**Problema:** Condição `{% if pixel_config.external_id %}` falhava quando `external_id` era string vazia.

**Solução:**
- Usar JavaScript para construir objeto dinamicamente
- Adicionar `external_id` apenas se existir (não enviar string vazia)

**Código aplicado em `templates/delivery.html` (linhas 31-45):**
```javascript
// ✅ CORREÇÃO: Sempre enviar eventID e external_id (se disponível) para garantir deduplicação
var purchaseParams = {
    value: {{ pixel_config.value }},
    currency: '{{ pixel_config.currency }}',
    eventID: '{{ pixel_config.event_id }}',  // ✅ MESMO event_id do server-side (deduplicação garantida)
    content_ids: ['{{ pixel_config.content_id }}'],
    content_name: '{{ pixel_config.content_name|replace("'", "\\'") }}',
    content_type: 'product',
    num_items: 1
};

// ✅ CRÍTICO: Adicionar external_id APENAS se existir (não enviar string vazia)
{% if pixel_config.external_id %}
purchaseParams.external_id = '{{ pixel_config.external_id }}';  // ✅ CRÍTICO: Enviar fbclid normalizado no browser para matching perfeito
{% endif %}

fbq('track', 'Purchase', purchaseParams);
```

---

## 📝 ARQUIVOS MODIFICADOS

1. **`app.py` - Linhas 9366-9390** (função `delivery_page`)
   - Normalização de `external_id`
   - Garantia de `event_id` como string
   - Logs detalhados para debug

2. **`templates/delivery.html` - Linhas 31-45** (client-side Purchase event)
   - Construção dinâmica do objeto `purchaseParams`
   - Envio condicional de `external_id` (apenas se existir)

---

## 🎯 RESULTADOS ESPERADOS

Após as correções, esperamos:

1. **ID do evento (eventID):**
   - Browser: 100% ✅
   - Server: 100% ✅
   - **Cobertura: 100%** ✅ (matching perfeito)

2. **ID externo (external_id):**
   - Browser: 100% ✅ (quando `fbclid` disponível)
   - Server: 100% ✅
   - **Cobertura: 100%** ✅ (matching perfeito)

3. **Cobertura do evento geral:**
   - **Antes: 37%** ❌
   - **Depois: 75%+** ✅ (meta do Meta)

---

## ⚠️ OBSERVAÇÕES

1. **`external_id` só será enviado quando `fbclid` estiver disponível:**
   - Se o lead não vier de um clique no Meta Ads, não haverá `fbclid`
   - Isso é normal e não afeta a deduplicação (Meta usa `eventID` e `fbp` como fallback)

2. **`eventID` sempre será enviado:**
   - Garante deduplicação mesmo sem `external_id`
   - Formato: `pageview_{uuid}` ou `purchase_{payment.id}_{timestamp}`

3. **Logs detalhados:**
   - Todos os valores são logados para facilitar debug
   - Verificar logs para confirmar que `external_id` está sendo normalizado corretamente

---

**STATUS:** ✅ Correções aplicadas. Sistema deve alcançar 75%+ de cobertura de eventos.

