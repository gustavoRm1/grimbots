# 🔥 CAUSA RAIZ IDENTIFICADA - PURCHASE NÃO APARECE NO META

## 📊 SITUAÇÃO ATUAL

**Logs do Celery:**
- ✅ Purchase está sendo enviado via server-side (CAPI)
- ✅ Meta confirma recebimento: `events_received: 1`
- ⚠️ Mas apenas **1 Purchase** foi enviado (vs muitos PageView)

**Problema:** Meta não mostra Purchase no Events Manager (apenas PageView)

---

## 🔍 CAUSA RAIZ

### **1. Client-side Purchase não está disparando**

**Código em `delivery.html` (linha 24):**
```html
{% if not payment.meta_purchase_sent %}
// ✅ Purchase ainda NÃO foi enviado - pode disparar client-side
fbq('track', 'Purchase', {...});
{% else %}
// ✅ Purchase JÁ foi enviado anteriormente - NÃO disparar novamente
{% endif %}
```

**Problema:** Se `payment.meta_purchase_sent = True` quando renderiza o template, client-side Purchase **NÃO dispara**!

---

### **2. Quando `meta_purchase_sent` é marcado?**

**Fluxo atual:**
1. Payment é confirmado
2. `send_meta_pixel_purchase_event()` é chamado
3. `meta_purchase_sent = True` é marcado **ANTES** de renderizar template (linha 10598 de app.py)
4. Template renderiza com `meta_purchase_sent = True`
5. Client-side Purchase **NÃO dispara** ❌
6. Server-side Purchase é enfileirado e enviado ✅

---

### **3. Por que Meta não mostra Purchase?**

Meta prefere **browser events** (client-side) sobre server-side events. Se apenas server-side é enviado:
- Meta pode não mostrar no Events Manager
- Atribuição pode ser inferior
- Deduplicação pode falhar se eventID não for consistente

---

## ✅ SOLUÇÃO

### **OPÇÃO 1: NÃO marcar `meta_purchase_sent` antes de renderizar**

**Antes:**
```python
# ❌ PROBLEMA: Marca ANTES de renderizar
payment.meta_purchase_sent = True
db.session.commit()
response = render_template('delivery.html', ...)  # Client-side NÃO dispara!
```

**Depois:**
```python
# ✅ CORREÇÃO: Renderizar PRIMEIRO, depois marcar
response = render_template('delivery.html', ...)  # Client-side dispara!
# Marcar apenas DEPOIS de renderizar (para evitar duplicação)
```

**Mas isso pode causar duplicação se:**
- Client-side dispara
- Server-side também dispara
- Meta deduplica usando eventID (deve funcionar)

---

### **OPÇÃO 2: Marcar `meta_purchase_sent` DEPOIS de renderizar**

**Modificar `send_meta_pixel_purchase_event()`:**
- NÃO marcar `meta_purchase_sent = True` antes de renderizar
- Marcar apenas DEPOIS que template foi renderizado
- Isso permite client-side disparar primeiro

---

### **OPÇÃO 3: Usar flag temporária**

**Criar flag `meta_purchase_pending` em vez de `meta_purchase_sent`:**
- `meta_purchase_pending = True` quando enfileirar
- Template verifica `meta_purchase_pending` (não bloqueia client-side)
- Marcar `meta_purchase_sent = True` apenas quando ambos (client + server) enviarem

---

## 🎯 RECOMENDAÇÃO

**Usar OPÇÃO 1 + deduplicação por eventID:**

1. Renderizar template **PRIMEIRO** (client-side dispara)
2. Enfileirar server-side **DEPOIS** (usando mesmo eventID)
3. Meta deduplica automaticamente usando eventID
4. Marcar `meta_purchase_sent = True` apenas quando ambos enviarem (ou após timeout)

---

**STATUS:** Identificada causa raiz. Client-side Purchase não dispara porque `meta_purchase_sent = True` antes de renderizar.

