# ✅ CORREÇÃO - Duplicação de Purchase Events

## 🎯 PROBLEMA IDENTIFICADO

**Logs mostram Purchase sendo enviado duas vezes:**
```
2025-11-20 03:32:18 - Purchase - Iniciando para payment 9391
2025-11-20 03:32:25 - Purchase - Iniciando para payment 9391 (7 segundos depois)
```

**Causa:** Condição de corrida onde `payment.meta_purchase_sent` era marcado como `True` **DEPOIS** de enviar, permitindo duas chamadas simultâneas.

---

## ✅ CORREÇÃO APLICADA

### **1. Lock Pessimista - Marcar ANTES de Enviar**

**ANTES:**
```python
if has_meta_pixel and not payment.meta_purchase_sent:
    send_meta_pixel_purchase_event(payment, pageview_event_id=event_id_to_pass)
    # ❌ meta_purchase_sent só era marcado DEPOIS (condição de corrida)
```

**DEPOIS:**
```python
if has_meta_pixel and not payment.meta_purchase_sent:
    # ✅ CRÍTICO: Lock pessimista - marcar ANTES de enviar
    payment.meta_purchase_sent = True
    payment.meta_purchase_sent_at = get_brazil_time()
    db.session.commit()
    
    send_meta_pixel_purchase_event(payment, pageview_event_id=event_id_to_pass)
    # ✅ Agora qualquer segunda chamada verá meta_purchase_sent=True e não enviará
```

### **2. Rollback em Caso de Falha**

```python
except Exception as e:
    logger.error(f"❌ Erro ao enviar Purchase via Server: {e}", exc_info=True)
    # ✅ ROLLBACK: Se falhou, reverter meta_purchase_sent para permitir nova tentativa
    try:
        payment.meta_purchase_sent = False
        payment.meta_purchase_sent_at = None
        db.session.commit()
    except:
        pass
```

### **3. Atualização do meta_event_id**

**ANTES:**
```python
# ✅ SUCESSO: Marcar como enviado APÓS confirmação
payment.meta_purchase_sent = True  # ❌ Já foi marcado antes de enviar!
payment.meta_event_id = event_id
```

**DEPOIS:**
```python
# ✅ SUCESSO: Atualizar meta_event_id (meta_purchase_sent já foi marcado antes de enviar)
# ✅ CRÍTICO: Não marcar meta_purchase_sent novamente aqui
payment.meta_event_id = event_id
db.session.commit()
```

---

## 🔍 PROBLEMAS ADICIONAIS IDENTIFICADOS

### **1. pageview_event_id está None**

**Causa:** Usuário não passou pelo redirect (`bot_user.tracking_session_id` vazio, `payment.tracking_token` ausente).

**Solução:**
- ✅ Sistema já gera `event_id` no formato correto (`purchase_{payment.id}_{int(time.time())}`) quando `pageview_event_id` está ausente
- ✅ Mesmo formato do client-side garante deduplicação mesmo sem `pageview_event_id` original

### **2. fbclid ausente**

**Causa:** Usuário não passou pelo redirect ou dados expiraram no Redis.

**Impacto:**
- ⚠️ Match Quality reduzida (sem `external_id`)
- ⚠️ Cobertura FBC reduzida (sem `fbclid` para gerar `fbc`)
- ✅ Purchase ainda é enviado (mas com atribuição reduzida)

### **3. Duas Chamadas com 7 Segundos de Diferença**

**Causa:** Possivelmente:
- Usuário recarregou a página
- Ou dois requests simultâneos (browser + servidor)

**Solução:**
- ✅ Lock pessimista evita segunda chamada (verifica `meta_purchase_sent` antes de enviar)

---

## 📊 VERIFICAÇÃO

### **Comando para Verificar Duplicação:**

```bash
tail -f logs/gunicorn.log | grep -E "Purchase - Iniciando|Purchase ENVIADO|meta_purchase_sent"
```

### **O que Esperar:**

**✅ CORRETO (sem duplicação):**
```
[03:32:18] Purchase - Iniciando para payment 9391
[03:32:18] meta_purchase_sent marcado como True (ANTES de enviar)
[03:32:18] Purchase ENVIADO: payment 9391 | event_id: purchase_9391_1763609538
```

**❌ INCORRETO (com duplicação):**
```
[03:32:18] Purchase - Iniciando para payment 9391
[03:32:25] Purchase - Iniciando para payment 9391 (segunda chamada!)
```

---

## 🎯 PRÓXIMOS PASSOS

1. ✅ **Testar com nova venda** para confirmar que não há duplicação
2. ✅ **Verificar logs** para confirmar que `meta_purchase_sent` é marcado ANTES de enviar
3. ✅ **Verificar Meta Event Manager** para confirmar que eventos não estão duplicados

---

## ⚠️ NOTAS IMPORTANTES

1. **Lock Pessimista é Crítico:** Sem marcar `meta_purchase_sent` antes de enviar, duas chamadas simultâneas podem ver `meta_purchase_sent=False` e ambas enviarem o Purchase.

2. **Rollback é Essencial:** Se o envio falhar, devemos reverter `meta_purchase_sent` para permitir nova tentativa.

3. **event_id Consistente:** O `event_id` gerado no `send_payment_delivery` é o mesmo usado no client-side (`delivery.html`), garantindo deduplicação mesmo sem `pageview_event_id` original.

---

## ✅ STATUS

- ✅ Lock pessimista implementado
- ✅ Rollback em caso de falha implementado
- ✅ Atualização do `meta_event_id` corrigida
- ⚠️ **Aguardando teste com nova venda para confirmar correção**

