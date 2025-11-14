# 🚨 ANÁLISE CRÍTICA: CONTRADIÇÃO NOS WEBHOOKS

## ⚠️ PROBLEMA IDENTIFICADO

**CONTRADIÇÃO CRÍTICA DETECTADA:**

Todos os webhooks mostram `"status": "waiting_payment"` no **payload**, mas o sistema processou como `paid`.

### **Evidências:**

1. ✅ **Payload do webhook:** `"status": "waiting_payment"`
2. ✅ **Status salvo no DB:** `paid`
3. ✅ **Sistema processou como:** `paid`

---

## 🔍 POSSÍVEIS CAUSAS

### **Cenário 1: Múltiplos Webhooks (MAIS PROVÁVEL)** ⭐

1. **Webhook 1:** Gateway envia `PAID` → Sistema salva `status=paid`
2. **Webhook 2:** Gateway envia `WAITING_PAYMENT` → Sistema atualiza `payload`, mas **não atualiza `status` corretamente**

**Problema:** O `_persist_webhook_event` pode estar atualizando o `payload` mas mantendo o `status` antigo.

### **Cenário 2: Botão "Verificar Pagamento"**

1. Cliente clica em "Verificar Pagamento"
2. Sistema consulta API e recebe `PAID`
3. Sistema marca como `paid` no Payment
4. Webhook `WAITING_PAYMENT` chega depois
5. Sistema salva webhook com `status=paid` (do Payment) ao invés de `pending` (do webhook)

**Problema:** O `status` salvo pode estar vindo do Payment ao invés do webhook.

### **Cenário 3: Bug no `_persist_webhook_event`**

O código em `tasks_async.py` linha 93:
```python
existing.status = result.get('status')
```

Se `result.get('status')` vier como `paid` (do Payment anterior), ele sobrescreve o status correto do webhook.

---

## 🔍 INVESTIGAÇÃO NECESSÁRIA

### **1. Analisar Sequência de Webhooks**

Execute o script para ver TODOS os webhooks recebidos para cada transaction_id:

```bash
cd ~/grimbots
source venv/bin/activate
python3 scripts/analisar_sequencia_webhooks.py
```

**Este script irá:**
- Buscar TODOS os webhooks para cada transaction_id
- Mostrar a sequência cronológica
- Identificar se houve webhook `PAID` antes de `WAITING_PAYMENT`
- Detectar contradições entre `payload` e `status` salvo

### **2. Verificar Logs de Processamento**

```bash
# Verificar logs de webhook para os transaction_ids problemáticos
grep -i "umbrellapag.*webhook" logs/rq-webhook.log | grep -i "GATEWAY_ID"

# Verificar se houve múltiplos webhooks
grep -i "transaction_id.*GATEWAY_ID" logs/rq-webhook.log
```

### **3. Verificar Código de Persistência**

Verificar se `_persist_webhook_event` está atualizando o `status` corretamente quando um webhook subsequente chega.

---

## 🎯 CONCLUSÃO PROVISÓRIA

**Baseado nos payloads mostrados:**

1. ✅ **Gateway enviou webhook com `waiting_payment`**
2. ✅ **Sistema processou como `paid`**
3. ⚠️  **Contradição:** Payload diz `waiting_payment`, mas sistema marcou como `paid`

**Isso indica que:**
- Ou houve webhook `PAID` anterior que não está sendo mostrado
- Ou o sistema está usando status do Payment ao invés do webhook
- Ou há bug no `_persist_webhook_event`

---

## 📋 PRÓXIMOS PASSOS

1. ✅ **Executar `analisar_sequencia_webhooks.py`** para ver TODOS os webhooks
2. ✅ **Verificar logs** para identificar se houve webhook `PAID` anterior
3. ✅ **Corrigir `_persist_webhook_event`** se necessário
4. ✅ **Validar com gateway** se realmente enviou `PAID` ou apenas `WAITING_PAYMENT`

---

**Status:** 🔍 **INVESTIGAÇÃO EM ANDAMENTO**  
**Prioridade:** 🔴 **CRÍTICA** - Contradição entre payload e status processado

