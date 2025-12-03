# ✅ CORREÇÃO APLICADA - META PURCHASE SENT

## 🔍 PROBLEMA IDENTIFICADO

**Causa:** `meta_purchase_sent = True` estava sendo marcado **ANTES** de renderizar o template, bloqueando client-side Purchase.

**Fluxo anterior (ERRADO):**
1. `send_meta_pixel_purchase_event()` é chamado
2. `meta_purchase_sent = True` é marcado **ANTES** de enfileirar
3. Template renderiza com `meta_purchase_sent = True`
4. Client-side Purchase **NÃO dispara** ❌ (`{% if not payment.meta_purchase_sent %}`)
5. Apenas server-side Purchase é enviado

---

## ✅ CORREÇÃO APLICADA

**Fluxo novo (CORRETO):**
1. Template renderiza **PRIMEIRO** (`meta_purchase_sent = False`)
2. Client-side Purchase **dispara** ✅
3. `send_meta_pixel_purchase_event()` enfileira task
4. `meta_purchase_sent = True` é marcado **DEPOIS** de enfileirar
5. Server-side Purchase é enviado (Meta deduplica usando eventID)

---

## 📝 MUDANÇAS NO CÓDIGO

### **ANTES (linha 11179-11184):**
```python
# ❌ PROBLEMA: Marca ANTES de enfileirar
if not payment.meta_purchase_sent or not getattr(payment, 'meta_event_id', None):
    payment.meta_purchase_sent = True
    payment.meta_purchase_sent_at = get_brazil_time()
    db.session.commit()
```

### **DEPOIS (linhas 11179-11184 e 11213-11214):**
```python
# ✅ CORREÇÃO: NÃO marca antes, apenas salva estado
purchase_was_pending = payment.meta_purchase_sent
logger.info(f"[META PURCHASE] Purchase - meta_purchase_sent atual: {purchase_was_pending}")

# ... enfileirar task ...

# ✅ CORREÇÃO: Marca DEPOIS de enfileirar
if not payment.meta_purchase_sent or not getattr(payment, 'meta_event_id', None):
    payment.meta_purchase_sent = True
    payment.meta_purchase_sent_at = get_brazil_time()
```

---

## 🎯 RESULTADO ESPERADO

1. ✅ Client-side Purchase dispara (browser)
2. ✅ Server-side Purchase é enviado (CAPI)
3. ✅ Meta deduplica usando eventID (mesmo eventID em ambos)
4. ✅ Meta mostra Purchase no Events Manager
5. ✅ Cobertura >= 75% (browser + server)

---

## ⚠️ RISCOS

**Condição de corrida:** Se múltiplas requisições chegarem simultaneamente:
- Ambas podem renderizar template com `meta_purchase_sent = False`
- Ambas podem enfileirar task
- Meta deduplica usando eventID (deve funcionar)

**Mitigação:** Lock pessimista ainda funciona (linha 11213-11214), mas apenas DEPOIS de enfileirar.

---

**STATUS:** ✅ Correção aplicada. Client-side Purchase agora deve disparar corretamente.

