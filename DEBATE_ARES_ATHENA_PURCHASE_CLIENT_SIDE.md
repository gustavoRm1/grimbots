# 🔥 DEBATE ARES & ATHENA - PURCHASE APENAS SERVER-SIDE

## 📊 PROBLEMA REPORTADO

**Meta Events Manager:**
- PageView: "Múltiplos" ✅ (browser + server)
- Purchase: "API de conversões" ❌ (apenas server)

**Meta mostra que Purchase está sendo enviado APENAS via servidor, não pelo browser!**

---

## 🔍 ANÁLISE ARES (Arquiteto Perfeccionista)

### **Causa Raiz Identificada:**

**1. Template `delivery.html` (linha 24):**
```html
{% if not payment.meta_purchase_sent %}
// ✅ Purchase ainda NÃO foi enviado - pode disparar client-side
fbq('track', 'Purchase', {...});
{% else %}
// ✅ Purchase JÁ foi enviado anteriormente - NÃO disparar novamente
{% endif %}
```

**2. Fluxo Atual (ERRADO):**
1. Payment é confirmado
2. `delivery_page()` é chamado
3. `purchase_already_sent = payment.meta_purchase_sent` (linha 9336)
4. `send_meta_pixel_purchase_event()` é chamado DEPOIS de renderizar (linha 9365)
5. `meta_purchase_sent = True` é marcado DEPOIS de enfileirar (linha 11213-11216)
6. Template renderiza com `meta_purchase_sent = False` ✅
7. Client-side deveria disparar ✅

**MAS...**

---

## 🔍 ANÁLISE ATHENA (Engenheira Cirúrgica)

### **Problema Específico:**

**Verificar se `meta_purchase_sent` está sendo marcado ANTES de renderizar:**

**Linha 11179-11184 (dentro de `send_meta_pixel_purchase_event`):**
```python
# ✅ CORREÇÃO CRÍTICA V3: NÃO marcar meta_purchase_sent ANTES de enfileirar
purchase_was_pending = payment.meta_purchase_sent
logger.info(f"[META PURCHASE] Purchase - meta_purchase_sent atual: {purchase_was_pending}")
```

**Linha 11213-11216 (DEPOIS de enfileirar):**
```python
if not payment.meta_purchase_sent or not getattr(payment, 'meta_event_id', None):
    payment.meta_purchase_sent = True
    payment.meta_purchase_sent_at = get_brazil_time()
```

**Linha 11219-11220 (COMMIT):**
```python
payment.meta_event_id = event_id
db.session.commit()
```

**PROBLEMA:** O commit acontece DEPOIS de renderizar, então `meta_purchase_sent` deveria estar `False` quando o template renderiza.

**MAS... pode haver outra chamada antes!**

---

## 🎯 DEBATE FINAL

**ARES:** O problema pode ser que `send_meta_pixel_purchase_event()` está sendo chamado de OUTRO lugar ANTES do `delivery_page()`.

**ATHENA:** Ou o payment já tem `meta_purchase_sent = True` de uma tentativa anterior.

**ARES:** Precisamos garantir que `meta_purchase_sent` seja `False` quando o template renderiza.

**ATHENA:** E garantir que o client-side dispare ANTES de marcar como `True`.

---

## ✅ SOLUÇÃO PROPOSTA

**1. NÃO marcar `meta_purchase_sent = True` até que:**
   - Template foi renderizado ✅
   - Client-side teve chance de disparar ✅
   - Server-side foi enfileirado ✅

**2. Usar flag temporária `meta_purchase_pending` em vez de `meta_purchase_sent`:**
   - `meta_purchase_pending = True` quando enfileirar
   - Template verifica `meta_purchase_pending` (não bloqueia)
   - `meta_purchase_sent = True` apenas quando ambos enviarem

**3. OU: Remover verificação de `meta_purchase_sent` no template:**
   - Sempre disparar client-side
   - Meta deduplica usando eventID
   - Server-side também dispara (deduplicação automática)

---

**STATUS:** Aguardando validação do fluxo atual.

