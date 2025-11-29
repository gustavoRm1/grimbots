# 🔍 DIAGNÓSTICO: WEBHOOK RECEBIDO MAS SEM LOGS DE UPSELLS

## 📊 ANÁLISE DOS LOGS FORNECIDOS

### **Webhook Recebido:**
```
2025-11-29 17:40:04,246 - INFO - 🔔 [DIAGNÓSTICO] Webhook pushynpay recebido | content-type=application/x-www-form-urlencoded | source=form
2025-11-29 17:40:04,246 - INFO - 🔔 [DIAGNÓSTICO] Webhook pushynpay - URL: https://app.grimbots.online/webhook/payment/pushynpay | Method: POST
```

### **Logs Esperados (NÃO aparecem):**
```
🔍 [DIAGNÓSTICO] process_webhook_async INICIADO para gateway_type=pushynpay
💾 [WEBHOOK PUSHYNPAY] Pagamento {payment_id} atualizado para 'paid'
🔍 [UPSELLS ASYNC] Verificando condições...
✅ [UPSELLS ASYNC] Condições atendidas!
📅 [UPSELLS ASYNC] Upsells agendados com sucesso!
```

---

## 🚨 POSSÍVEIS CAUSAS

### **1. Webhook Enfileirado mas Worker RQ Não Está Processando**
**Sintoma:** Webhook recebido mas sem logs de `process_webhook_async`
**Causa:** Worker RQ (`rq worker webhook`) não está rodando ou travado
**Solução:** Verificar se worker RQ está rodando

**Comando para verificar:**
```bash
ps aux | grep "rq worker"
```

**Se não estiver rodando, iniciar:**
```bash
rq worker webhook --url redis://localhost:6379/0
```

---

### **2. Webhook Processado mas Payment Não Encontrado**
**Sintoma:** Webhook recebido mas payment não encontrado no banco
**Causa:** `transaction_id` do webhook não corresponde ao `gateway_transaction_id` salvo
**Solução:** Verificar logs para `❌ Payment não encontrado`

**Log esperado:**
```
❌ Payment não encontrado para webhook: {transaction_id}
⚠️ Payment não encontrado para webhook: {gateway_transaction_id}
```

---

### **3. Webhook Processado mas Status Não é 'paid'**
**Sintoma:** Webhook processado mas status é 'pending' ou outro
**Causa:** Gateway enviou webhook com status diferente de 'paid'
**Solução:** Verificar logs para status do webhook

**Log esperado:**
```
📥 [WEBHOOK PUSHYNPAY] Webhook recebido e processado
   Status normalizado: {status}  # ← Verificar se é 'paid'
```

---

### **4. Upsells Desabilitados ou Não Configurados**
**Sintoma:** Webhook processado, status='paid', mas upsells não são agendados
**Causa:** `upsells_enabled=False` ou lista de upsells vazia
**Solução:** Verificar logs para condições de upsells

**Log esperado:**
```
🔍 [UPSELLS ASYNC] Verificando condições: status='paid', has_config=True, upsells_enabled=False  # ← Verificar aqui
```

**Se `upsells_enabled=False` ou `has_config=False`:**
- Verificar configuração do bot no painel
- Habilitar upsells em Bot Config
- Adicionar upsells na configuração

---

### **5. Scheduler Não Está Rodando**
**Sintoma:** Upsells tentam ser agendados mas scheduler não está disponível
**Causa:** APScheduler não foi inicializado ou parou
**Solução:** Verificar logs para scheduler

**Log esperado:**
```
❌ CRÍTICO: Scheduler não está disponível! Upsells NÃO serão agendados!
❌ CRÍTICO: Scheduler existe mas NÃO está rodando!
```

**Se scheduler não está rodando:**
- Reiniciar aplicação
- Verificar se APScheduler foi inicializado corretamente

---

## 🔧 CHECKLIST DE DIAGNÓSTICO

### **Passo 1: Verificar Worker RQ**
```bash
# Verificar se worker está rodando
ps aux | grep "rq worker"

# Verificar jobs na fila
rq info webhook

# Verificar jobs falhados
rq failed
```

### **Passo 2: Verificar Logs Completos**
```bash
# Verificar logs do worker RQ (se estiver em arquivo separado)
tail -f /path/to/rq_worker.log

# Verificar logs da aplicação
tail -f /path/to/app.log | grep -E "(UPSELLS|WEBHOOK|process_webhook_async)"
```

### **Passo 3: Verificar Payment no Banco**
```sql
-- Verificar se payment existe e status
SELECT id, payment_id, gateway_transaction_id, status, created_at, paid_at
FROM payments
WHERE gateway_type = 'pushynpay'
ORDER BY created_at DESC
LIMIT 10;

-- Verificar se upsells estão habilitados para o bot
SELECT b.id, b.name, bc.upsells_enabled, bc.upsells
FROM bots b
JOIN bot_configs bc ON bc.bot_id = b.id
WHERE bc.upsells_enabled = true;
```

### **Passo 4: Verificar Scheduler**
```python
# Executar script Python para verificar scheduler
python3 -c "
from app import app, bot_manager
with app.app_context():
    print(f'Scheduler disponível: {bot_manager.scheduler is not None}')
    if bot_manager.scheduler:
        print(f'Scheduler rodando: {bot_manager.scheduler.running}')
        print(f'Jobs agendados: {len(bot_manager.scheduler.get_jobs())}')
"
```

---

## 📋 LOGS ESPERADOS PARA WEBHOOK COM UPSELLS

### **Cenário Ideal (Tudo Funcionando):**
```
17:40:04,246 - INFO - 🔔 [DIAGNÓSTICO] Webhook pushynpay recebido
17:40:04,247 - INFO - ✅ Webhook enfileirado na fila 'webhook'
17:40:04,250 - INFO - 🔍 [DIAGNÓSTICO] process_webhook_async INICIADO para gateway_type=pushynpay
17:40:04,255 - INFO - 📥 [WEBHOOK PUSHYNPAY] Webhook recebido e processado
17:40:04,256 - INFO -    Transaction ID: {transaction_id}
17:40:04,257 - INFO -    Status normalizado: paid
17:40:04,258 - INFO - 💾 [WEBHOOK PUSHYNPAY] Pagamento {payment_id} atualizado para 'paid'
17:40:04,259 - INFO - 📦 [WEBHOOK PUSHYNPAY] Enviando entregável...
17:40:04,260 - INFO - ✅ [WEBHOOK PUSHYNPAY] Entregável enviado com sucesso
17:40:04,261 - INFO - 🔍 [UPSELLS ASYNC] Verificando condições: status='paid', has_config=True, upsells_enabled=True
17:40:04,262 - INFO - ✅ [UPSELLS ASYNC] Condições atendidas! Processando upsells para payment {payment_id}
17:40:04,263 - INFO - 🎯 [UPSELLS ASYNC] Verificando upsells para produto: {product_name}
17:40:04,264 - INFO - ✅ [UPSELLS ASYNC] 1 upsell(s) encontrado(s) para '{product_name}'
17:40:04,265 - INFO - 🚨 ===== SCHEDULE_UPSELLS CHAMADO =====
17:40:04,266 - INFO - ✅ Upsell 1 AGENDADO COM SUCESSO
17:40:04,267 - INFO - 📅 [UPSELLS ASYNC] Upsells agendados com sucesso para payment {payment_id}!
```

---

## 🎯 AÇÕES IMEDIATAS

1. ✅ **Verificar se Worker RQ está rodando**
2. ✅ **Verificar logs completos (incluindo worker RQ)**
3. ✅ **Verificar se payment foi encontrado no banco**
4. ✅ **Verificar se status do webhook é 'paid'**
5. ✅ **Verificar se upsells estão habilitados no bot**
6. ✅ **Verificar se scheduler está rodando**

---

**DATA:** 2025-11-29
**STATUS:** ⚠️ **AGUARDANDO VERIFICAÇÃO DE WORKER RQ E LOGS COMPLETOS**

