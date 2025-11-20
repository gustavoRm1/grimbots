# 🚨 CAUSA RAIZ - Link de Delivery não está sendo enviado via Telegram

## 🎯 PROBLEMA CONFIRMADO

**Diagnóstico do script `verificar_porque_nao_enviando_telegram.sh`:**

- ❌ **Chamadas a `send_payment_delivery()`: 0** - Função NÃO está sendo chamada
- ⚠️ **Sem bot.token: 2** - Há 2 casos de bot sem token (problema secundário)
- ❌ **delivery_token gerados: 0** - Nenhum token sendo gerado via logs
- ❌ **Mensagens enviadas via Telegram: 0** - Nenhuma mensagem sendo enviada

**Conclusão:** `send_payment_delivery()` **NÃO está sendo chamado** quando payment é confirmado.

---

## 🔍 POSSÍVEIS CAUSAS

### **CAUSA 1: Webhook não está sendo recebido**

**Sintoma:**
- Payment fica `pending` indefinidamente
- Webhook não é recebido do gateway
- `send_payment_delivery()` nunca é chamado

**Verificação:**
```bash
tail -5000 logs/gunicorn.log | grep -iE "webhook|POST.*webhook|webhook.*POST"
```

**Solução:**
- Verificar configuração do webhook no gateway
- Verificar se gateway está enviando webhook
- Verificar se URL do webhook está correta

---

### **CAUSA 2: Payment não está sendo encontrado no webhook**

**Sintoma:**
- Webhook é recebido mas payment não é encontrado
- Logs mostram "Payment NÃO encontrado" ou "CRÍTICO: Payment NÃO encontrado"
- `send_payment_delivery()` nunca é chamado (pois payment não foi encontrado)

**Verificação:**
```bash
tail -5000 logs/gunicorn.log | grep -iE "Payment.*não encontrado|Payment NÃO encontrado|CRÍTICO.*Payment NÃO"
```

**Solução:**
- Verificar se `gateway_transaction_id` ou `gateway_transaction_hash` está correto
- Verificar se payment existe no banco de dados
- Verificar se `payment_id` está sendo salvo corretamente

---

### **CAUSA 3: Payment não está sendo atualizado para 'paid'**

**Sintoma:**
- Webhook é recebido e payment é encontrado
- MAS payment não é atualizado para `paid`
- `deve_enviar_entregavel` fica `False` (pois `status != 'paid'`)
- `send_payment_delivery()` nunca é chamado

**Verificação:**
```bash
tail -5000 logs/gunicorn.log | grep -iE "payment.*atualizado.*paid|atualizado para paid|Webhook.*payment.*paid"
```

**Solução:**
- Verificar se `status` do webhook está sendo processado corretamente
- Verificar se `payment.status = 'paid'` está sendo executado
- Verificar se há erro ao fazer commit

---

### **CAUSA 4: `deve_enviar_entregavel` está False quando deveria ser True**

**Sintoma:**
- Webhook é recebido, payment é encontrado e atualizado para `paid`
- MAS `deve_enviar_entregavel` está `False` (mas deveria ser `True` se `status == 'paid'`)
- `send_payment_delivery()` nunca é chamado (pois `if deve_enviar_entregavel:` é `False`)

**Verificação:**
```bash
tail -5000 logs/gunicorn.log | grep -iE "Enviando entregável|📦 Enviando entregável|deve_enviar_entregavel"
```

**Código (linha 9807):**
```python
deve_enviar_entregavel = (status == 'paid')  # SEMPRE envia se status é 'paid'
```

**Solução:**
- Verificar se `status` do webhook está sendo recebido como `'paid'`
- Verificar se `deve_enviar_entregavel` está sendo calculado corretamente
- Adicionar logging para rastrear `deve_enviar_entregavel`

---

### **CAUSA 5: Reconciliação não está funcionando**

**Sintoma:**
- Webhook não é recebido (gateway não envia webhook)
- Reconciliação (polling) deveria processar payments `pending`
- MAS reconciliação não está funcionando ou não está chamando `send_payment_delivery()`

**Verificação:**
```bash
tail -5000 logs/gunicorn.log | grep -iE "reconcili|Reconciliador"
```

**Solução:**
- Verificar se reconciliação está sendo executada (job agendado)
- Verificar se reconciliação está encontrando payments `pending`
- Verificar se reconciliação está chamando `send_payment_delivery()`

---

## ✅ VERIFICAÇÃO NECESSÁRIA

Execute o script `verificar_webhooks_e_reconciliacao.sh` para identificar a causa raiz:

```bash
chmod +x verificar_webhooks_e_reconciliacao.sh
bash verificar_webhooks_e_reconciliacao.sh
```

O script verifica:
1. ✅ Se webhooks estão sendo recebidos
2. ✅ Se payments estão sendo encontrados no webhook
3. ✅ Se payments estão sendo atualizados para `paid`
4. ✅ Se reconciliação está funcionando
5. ✅ Se `deve_enviar_entregavel` está sendo calculado
6. ✅ Gateway_type das vendas recentes

---

## 📋 PRÓXIMOS PASSOS

1. ✅ **Execute o script** `verificar_webhooks_e_reconciliacao.sh`
2. ✅ **Analise os resultados** para identificar a causa específica
3. ✅ **Corrija o problema** identificado
4. ✅ **Teste com uma nova venda** para confirmar correção

---

## ⚠️ NOTAS IMPORTANTES

1. **42 vendas têm `delivery_token`:**
   - Token está sendo gerado (pode ser manualmente ou via código antigo)
   - MAS link não está sendo enviado via Telegram

2. **2 casos de bot sem token:**
   - Problema secundário (não é a causa principal)
   - MAS pode estar bloqueando envio em alguns casos

3. **0 logs de "Entregável enviado":**
   - `send_payment_delivery()` não está sendo chamado com sucesso
   - Ou está sendo chamado mas falhando antes de logar sucesso

---

## ✅ STATUS

- ✅ Problema identificado: `send_payment_delivery()` não está sendo chamado
- ✅ Script de verificação criado
- ✅ Análise das possíveis causas realizada
- ⚠️ **Aguardando execução do script `verificar_webhooks_e_reconciliacao.sh` para identificar causa raiz específica**

