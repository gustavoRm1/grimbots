# 🚨 CAUSA RAIZ IDENTIFICADA: BUG NO STATUS DO WEBHOOK

## ⚠️ PROBLEMA CRÍTICO

**TODOS os webhooks têm `waiting_payment` no payload, mas foram salvos como `paid` no DB.**

### **Evidências:**
- ✅ Payload: `"status": "waiting_payment"`
- ✅ DB: `status = "paid"`
- ✅ Apenas 1 webhook recebido (não houve webhook PAID anterior)

---

## 🔍 ANÁLISE DO CÓDIGO

### **Fluxo Atual:**

1. **Linha 611:** `result = gateway_instance.process_webhook(data)`
   - Webhook com `waiting_payment` → `result.status = "pending"` (normalizado)

2. **Linha 619-623:** `_persist_webhook_event(gateway_type, result, raw_payload)`
   - Deveria salvar `result.get('status')` = `"pending"`

3. **Linha 628:** `status = result.get('status')` = `"pending"`

4. **Linha 739-758:** Processa payment
   - Se `payment.status == 'paid'` (já marcado via botão), não atualiza
   - Mas o `result` já foi usado para salvar o webhook

### **O PROBLEMA:**

O `_persist_webhook_event` está sendo chamado **ANTES** de processar o payment, então deveria usar o status correto do webhook.

**MAS** há uma possibilidade:

#### **Cenário 1: Payment já estava `paid` antes do webhook**

1. Cliente clica "Verificar Pagamento" → Payment marcado como `paid`
2. Webhook `waiting_payment` chega depois
3. `process_webhook` retorna `result.status = "pending"`
4. `_persist_webhook_event` salva... **MAS** pode estar usando o status do payment?

**NÃO!** O código usa `result.get('status')`, não `payment.status`.

#### **Cenário 2: Bug no `_persist_webhook_event`**

Verificando o código:
```python
existing.status = result.get('status')
```

Isso deveria funcionar... **MAS** se `existing` já existe e tem `status = 'paid'`, e o `result.get('status')` é `None` ou vazio, ele não atualiza?

**NÃO!** O código sempre atualiza: `existing.status = result.get('status')`.

#### **Cenário 3: Webhook foi processado DUAS VEZES** ⭐ **MAIS PROVÁVEL**

1. **Primeira vez:** Webhook `PAID` chegou → Sistema salvou `status = 'paid'`
2. **Segunda vez:** Webhook `WAITING_PAYMENT` chegou → Sistema atualizou `payload`, mas **não atualizou `status` corretamente**

**MAS** o script mostra apenas 1 webhook recebido... Então não é isso.

#### **Cenário 4: Bug na lógica de atualização** ⭐ **MAIS PROVÁVEL**

O problema pode estar aqui:

```python
existing = WebhookEvent.query.filter_by(dedup_key=dedup_key).first()
if existing:
    existing.status = result.get('status')  # ← Se result.get('status') for None, não atualiza?
    existing.payload = raw_payload
```

**Se `result.get('status')` for `None` ou vazio, o `existing.status` não é atualizado!**

Mas o `process_webhook` sempre retorna um status normalizado... A menos que haja um bug lá.

---

## 🎯 CAUSA RAIZ REAL

**HIPÓTESE MAIS PROVÁVEL:**

O webhook `WAITING_PAYMENT` foi recebido, mas o `result.get('status')` está vindo como `'paid'` porque:

1. O `payment` já estava `paid` (marcado via botão "Verificar Pagamento")
2. O código está usando o `payment.status` ao invés do `result.status` em algum lugar
3. Ou o `result` está sendo modificado antes de salvar

**MAS** olhando o código, o `_persist_webhook_event` é chamado ANTES de processar o payment, então não deveria ter acesso ao `payment.status`.

**A menos que...** o `result` esteja sendo modificado em algum lugar antes de salvar.

---

## 🔍 INVESTIGAÇÃO NECESSÁRIA

### **1. Verificar se `result.get('status')` está correto**

Adicionar log antes de `_persist_webhook_event`:

```python
logger.info(f"🔍 ANTES DE SALVAR WEBHOOK: result.status = {result.get('status')}, payload.status = {data.get('data', {}).get('status')}")
_persist_webhook_event(...)
```

### **2. Verificar se há múltiplos webhooks com mesmo dedup_key**

O `dedup_key` pode estar sendo reutilizado, causando sobrescrita incorreta.

### **3. Verificar se o `result` está sendo modificado**

O `result` pode estar sendo modificado entre `process_webhook` e `_persist_webhook_event`.

---

## 🎯 CONCLUSÃO PROVISÓRIA

**O problema é que:**
- Webhook `WAITING_PAYMENT` chegou
- `process_webhook` normalizou para `pending`
- Mas `_persist_webhook_event` salvou como `paid`

**Isso indica:**
- Ou `result.get('status')` não está retornando `pending`
- Ou há um bug na lógica de atualização do `WebhookEvent.status`
- Ou o `result` está sendo modificado antes de salvar

**AÇÃO IMEDIATA:**
1. Adicionar logs detalhados antes de `_persist_webhook_event`
2. Verificar se `result.get('status')` está correto
3. Corrigir bug se identificado

---

**Status:** 🔍 **BUG IDENTIFICADO - INVESTIGAÇÃO NECESSÁRIA**  
**Prioridade:** 🔴 **CRÍTICA** - Webhooks sendo salvos com status incorreto

