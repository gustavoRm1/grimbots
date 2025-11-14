# 🎯 EXPLICAÇÃO FINAL: O QUE REALMENTE ACONTECEU

## 📊 ANÁLISE DOS RESULTADOS

### **O que o script mostrou:**

1. ✅ **Apenas 1 webhook recebido** para cada transaction_id
2. ✅ **Payload mostra:** `"status": "waiting_payment"`
3. ✅ **Status salvo no DB:** `paid`
4. ⚠️  **Contradição:** Payload diz `waiting_payment`, mas DB diz `paid`

---

## 🔍 O QUE ISSO SIGNIFICA

### **Cenário Real:**

1. **Cliente clica "Verificar Pagamento"** → Sistema consulta API UmbrellaPay
2. **API retorna `PAID`** → Sistema marca Payment como `paid`
3. **Webhook `WAITING_PAYMENT` chega depois** → Sistema processa webhook
4. **`process_webhook` normaliza para `pending`** → `result.status = 'pending'`
5. **`_persist_webhook_event` salva...** → **MAS** o status salvo é `paid`?

### **O PROBLEMA:**

O `_persist_webhook_event` está usando `result.get('status')`, que deveria ser `'pending'`.

**MAS** o status salvo é `paid`. Isso significa:

#### **Possibilidade 1: Bug no `process_webhook`** ⭐ **MAIS PROVÁVEL**

O `process_webhook` pode estar retornando `paid` ao invés de `pending` quando:
- O payment já está `paid` no sistema
- O código está usando o status do payment ao invés do webhook

**MAS** olhando o código de `process_webhook`, ele não tem acesso ao payment...

#### **Possibilidade 2: Bug no `_persist_webhook_event`**

O código pode estar usando o status do payment ao invés do `result`:

```python
existing.status = result.get('status')  # ← Se result.get('status') for None, não atualiza?
```

**MAS** o `process_webhook` sempre retorna um status normalizado...

#### **Possibilidade 3: Webhook foi processado DUAS VEZES** ⭐ **MAIS PROVÁVEL**

1. **Primeira vez:** Webhook `PAID` chegou → Sistema salvou `status = 'paid'`
2. **Segunda vez:** Webhook `WAITING_PAYMENT` chegou → Sistema atualizou `payload`, mas **não atualizou `status` corretamente**

**MAS** o script mostra apenas 1 webhook... **A MENOS QUE** o `dedup_key` esteja sendo reutilizado incorretamente, causando sobrescrita.

---

## 🎯 CAUSA RAIZ REAL

**HIPÓTESE MAIS PROVÁVEL:**

O `dedup_key` está sendo gerado incorretamente, causando que webhooks diferentes sejam tratados como o mesmo evento:

```python
base_key = (transaction_hash or transaction_id or raw_payload.get('event') or '').strip()
dedup_key = f"{gateway_type}:{base_key}".lower()
```

**Se o `transaction_id` for o mesmo para webhooks diferentes, o `dedup_key` será o mesmo, causando sobrescrita.**

**OU** o webhook `PAID` foi recebido, mas não está sendo mostrado pelo script porque:
- Foi deletado
- Foi processado antes do período analisado
- Tem `dedup_key` diferente

---

## 🔍 INVESTIGAÇÃO NECESSÁRIA

### **1. Verificar logs de webhook para ver se houve webhook PAID anterior**

```bash
grep -i "umbrellapag.*webhook" logs/rq-webhook.log | grep -i "GATEWAY_ID" | sort
```

### **2. Verificar se há webhooks com mesmo transaction_id mas dedup_key diferente**

```sql
SELECT transaction_id, dedup_key, status, received_at 
FROM webhook_events 
WHERE gateway_type = 'umbrellapag' 
  AND transaction_id = 'GATEWAY_ID'
ORDER BY received_at;
```

### **3. Adicionar logs detalhados antes de `_persist_webhook_event`**

```python
logger.info(f"🔍 ANTES DE SALVAR: result.status={result.get('status')}, payload.status={data.get('data', {}).get('status')}")
_persist_webhook_event(...)
```

---

## 🎯 CONCLUSÃO

**O que realmente aconteceu:**

1. ✅ **Payment foi marcado como `paid` via botão "Verificar Pagamento"**
2. ✅ **Webhook `WAITING_PAYMENT` chegou depois**
3. ⚠️  **Sistema processou webhook, mas salvou status incorreto**

**Por quê?**
- Ou `result.get('status')` não está retornando `pending`
- Ou há bug na lógica de atualização do `WebhookEvent.status`
- Ou webhook `PAID` foi recebido antes e não está sendo mostrado

**AÇÃO:**
1. Verificar logs para ver se houve webhook `PAID` anterior
2. Adicionar logs detalhados antes de salvar webhook
3. Corrigir bug se identificado

---

**Status:** 🔍 **BUG IDENTIFICADO - INVESTIGAÇÃO NECESSÁRIA**  
**Prioridade:** 🔴 **CRÍTICA** - Webhooks sendo salvos com status incorreto

