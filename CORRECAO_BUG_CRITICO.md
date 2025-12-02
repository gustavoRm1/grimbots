# 🔥 CORREÇÃO DO BUG CRÍTICO - LINHA EXATA

## 🎯 PROBLEMA IDENTIFICADO

### **LINHA QUE QUEBROU: LINHA 8777 de `app.py`**

**PROBLEMA:**
- `payment.meta_purchase_sent = True` é marcado ANTES de enviar o Purchase
- Se `send_meta_pixel_purchase_event()` retornar silenciosamente (por qualquer verificação), o flag permanece `True`
- Isso bloqueia todas as tentativas futuras de enviar o Purchase

### **PONTOS DE RETORNO SILENCIOSO:**

1. **Linha 9505:** Se bot não está associado ao pool → `return`
2. **Linha 9518:** Se tracking desabilitado → `return`
3. **Linha 9523:** Se sem pixel_id/access_token → `return`
4. **Linha 9530:** Se Purchase event desabilitado → `return`
5. **Linha 9542:** Se já enviado (com meta_event_id) → `return`

## 🔧 SOLUÇÃO CIRÚRGICA

### **OPÇÃO 1: NÃO MARCAR ANTES DE ENVIAR (RECOMENDADO)**

Remover o lock pessimista da linha 8777 e marcar APENAS após confirmação de sucesso.

### **OPÇÃO 2: FAZER ROLLBACK EM TODOS OS RETURNS**

Modificar todas as verificações para fazer rollback de `meta_purchase_sent` antes de retornar.

### **OPÇÃO 3: MARCAR APENAS DENTRO DA FUNÇÃO**

Mover a marcação de `meta_purchase_sent = True` para DENTRO de `send_meta_pixel_purchase_event`, APÓS todas as verificações passarem.

## 🚨 DECISÃO: OPÇÃO 3 (MAIS SEGURA)

Mover a marcação de `meta_purchase_sent = True` para DENTRO de `send_meta_pixel_purchase_event`, logo ANTES de enfileirar o Purchase no Celery, garantindo que todas as verificações já passaram.

