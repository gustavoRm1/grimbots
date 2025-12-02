# 🔥 DIAGNÓSTICO FINAL - BUG CRÍTICO DO TRACKING

## 🎯 LINHA EXATA QUE QUEBROU: LINHA 9538 de `app.py`

### **PROBLEMA IDENTIFICADO:**

A função `send_meta_pixel_purchase_event()` é chamada na linha 8791 APÓS marcar `payment.meta_purchase_sent = True` na linha 8777.

**FLUXO QUEBRADO:**

1. Linha 8777: `payment.meta_purchase_sent = True` (marcado ANTES)
2. Linha 8780: `db.session.commit()` (commitado no banco)
3. Linha 8791: `send_meta_pixel_purchase_event(payment, ...)` (chamada com objeto já commitado)
4. Linha 9538: Verifica `if payment.meta_purchase_sent and getattr(payment, 'meta_event_id', None):`

**PROBLEMA CRÍTICO:**

Quando `send_meta_pixel_purchase_event()` é chamada, o objeto `payment` já tem `meta_purchase_sent = True` mas `meta_event_id = None`. 

A verificação na linha 9538 deveria permitir o envio (porque `meta_event_id` é `None`), MAS se a função retornar silenciosamente ANTES de enfileirar o Purchase (por qualquer verificação que falhe), o `meta_purchase_sent` permanece `True` e bloqueia futuras tentativas.

## 🔧 SOLUÇÃO CIRÚRGICA

### **CORREÇÃO: Remover lock pessimista da linha 8777**

O lock pessimista está causando o problema. Devemos marcar `meta_purchase_sent = True` APENAS APÓS confirmar que o Purchase foi enfileirado com sucesso.

### **ALTERNATIVA: Verificar apenas `meta_event_id`**

Modificar a verificação na linha 9538 para verificar APENAS se `meta_event_id` existe (ignorando `meta_purchase_sent`).

