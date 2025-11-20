# ✅ RESUMO - Correção de Duplicação de Purchase Events

## 🎯 PROBLEMA IDENTIFICADO NOS LOGS

**Purchase sendo enviado duas vezes:**
```
2025-11-20 03:32:18 - Purchase - Iniciando para payment 9391
2025-11-20 03:32:25 - Purchase - Iniciando para payment 9391 (7 segundos depois)
```

**Causas:**
1. ❌ **Condição de corrida:** `payment.meta_purchase_sent` era marcado **DEPOIS** de enviar
2. ❌ **Duas chamadas simultâneas:** Duas requisições veem `meta_purchase_sent=False` antes que a primeira marque como `True`
3. ❌ **event_id diferente:** Timestamps diferentes geram `event_id`s diferentes (quebra deduplicação)

---

## ✅ CORREÇÕES APLICADAS

### **1. Lock Pessimista - Marcar ANTES de Enviar**

**ANTES (linha 7519-7528):**
```python
if has_meta_pixel and not payment.meta_purchase_sent:
    send_meta_pixel_purchase_event(payment, pageview_event_id=event_id_to_pass)
    # ❌ meta_purchase_sent só era marcado DEPOIS (dentro de send_meta_pixel_purchase_event)
```

**DEPOIS:**
```python
if has_meta_pixel and not payment.meta_purchase_sent:
    # ✅ CRÍTICO: Lock pessimista - marcar ANTES de enviar
    payment.meta_purchase_sent = True
    payment.meta_purchase_sent_at = get_brazil_time()
    db.session.commit()
    logger.info(f"[META DELIVERY] Delivery - payment.meta_purchase_sent marcado como True (ANTES de enviar)")
    
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

### **3. Atualização do meta_event_id (linha 9357-9362)**

**ANTES:**
```python
if result and result.get('events_received', 0) > 0:
    # ✅ SUCESSO: Marcar como enviado APÓS confirmação
    payment.meta_purchase_sent = True  # ❌ Já foi marcado antes de enviar!
    payment.meta_purchase_sent_at = get_brazil_time()
    payment.meta_event_id = event_id
```

**DEPOIS:**
```python
if result and result.get('events_received', 0) > 0:
    # ✅ SUCESSO: Atualizar meta_event_id (meta_purchase_sent já foi marcado antes de enviar)
    # ✅ CRÍTICO: Não marcar meta_purchase_sent novamente aqui
    payment.meta_event_id = event_id
    db.session.commit()
    logger.info(f"[META PURCHASE] Purchase - meta_event_id atualizado: {event_id[:50]}...")
```

---

## 🔍 VERIFICAÇÃO ADICIONAL

### **Verificação em `send_meta_pixel_purchase_event` (linha 8284-8288)**

```python
if payment.meta_purchase_sent and getattr(payment, 'meta_event_id', None):
    # ✅ CAPI já foi enviado com sucesso (tem meta_event_id) - bloquear para evitar duplicação
    logger.info(f"⚠️ Purchase já enviado via CAPI ao Meta, ignorando: {payment.payment_id}")
    return
```

**✅ Esta verificação está correta e funciona como camada adicional de proteção.**

---

## 📊 COMO VERIFICAR SE FUNCIONOU

### **1. Comando para Monitorar Logs:**

```bash
tail -f logs/gunicorn.log | grep -E "Purchase - Iniciando|meta_purchase_sent marcado|Purchase ENVIADO|meta_event_id atualizado"
```

### **2. O que Esperar (CORRETO):**

```
[03:32:18] [META DELIVERY] Delivery - payment.meta_purchase_sent marcado como True (ANTES de enviar)
[03:32:18] [META PURCHASE] Purchase - Iniciando send_meta_pixel_purchase_event para payment 9391
[03:32:18] Purchase ENVIADO: payment 9391 | event_id: purchase_9391_1763609538
[03:32:18] [META PURCHASE] Purchase - meta_event_id atualizado: purchase_9391_1763609538...
```

**✅ Se a página for recarregada ou houver segunda chamada:**
```
[03:32:25] [META DELIVERY] Delivery - Purchase já foi enviado (meta_purchase_sent=True), client-side NÃO enviará
```

### **3. O que NÃO Esperar (ERRO - antes da correção):**

```
[03:32:18] [META PURCHASE] Purchase - Iniciando send_meta_pixel_purchase_event para payment 9391
[03:32:25] [META PURCHASE] Purchase - Iniciando send_meta_pixel_purchase_event para payment 9391 (segunda chamada!)
```

---

## 🎯 OUTROS PROBLEMAS IDENTIFICADOS

### **1. pageview_event_id está None**

**Causa:** Usuário não passou pelo redirect (`bot_user.tracking_session_id` vazio, `payment.tracking_token` ausente).

**Impacto:**
- ⚠️ Cobertura reduzida (sem `pageview_event_id` para deduplicação perfeita)
- ✅ Mas `event_id` é gerado no formato correto (`purchase_{payment.id}_{int(time.time())}`), garantindo deduplicação mesmo sem `pageview_event_id` original

### **2. fbclid ausente**

**Causa:** Usuário não passou pelo redirect ou dados expiraram no Redis.

**Impacto:**
- ⚠️ Match Quality reduzida (sem `external_id`)
- ⚠️ Cobertura FBC reduzida (sem `fbclid` para gerar `fbc`)
- ✅ Purchase ainda é enviado (mas com atribuição reduzida)

---

## ✅ STATUS

- ✅ Lock pessimista implementado
- ✅ Rollback em caso de falha implementado
- ✅ Atualização do `meta_event_id` corrigida
- ✅ Verificação adicional em `send_meta_pixel_purchase_event` confirmada
- ⚠️ **Aguardando teste com nova venda para confirmar correção**

---

## 🎯 PRÓXIMOS PASSOS

1. ✅ **Testar com nova venda** para confirmar que não há duplicação
2. ✅ **Verificar logs** para confirmar que `meta_purchase_sent` é marcado ANTES de enviar
3. ✅ **Verificar Meta Event Manager** para confirmar que eventos não estão duplicados
4. ✅ **Verificar cobertura** no Meta Event Manager (deve aumentar com `event_id` consistente)

---

## ⚠️ NOTAS IMPORTANTES

1. **Lock Pessimista é Crítico:** Sem marcar `meta_purchase_sent` antes de enviar, duas chamadas simultâneas podem ver `meta_purchase_sent=False` e ambas enviarem o Purchase.

2. **Rollback é Essencial:** Se o envio falhar, devemos reverter `meta_purchase_sent` para permitir nova tentativa.

3. **event_id Consistente:** O `event_id` gerado no `send_payment_delivery` é o mesmo usado no client-side (`delivery.html`), garantindo deduplicação mesmo sem `pageview_event_id` original.

4. **Verificação Dupla:** Temos duas camadas de proteção:
   - ✅ Verificação em `send_payment_delivery` (linha 7519) - bloqueia ANTES de chamar
   - ✅ Verificação em `send_meta_pixel_purchase_event` (linha 8284) - bloqueia DENTRO da função

