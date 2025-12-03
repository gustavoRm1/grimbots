# 🔥 ANÁLISE REAL - DADOS DA VPS (QI 500)

## 📋 INSTRUÇÕES

1. **Execute o script na VPS:**
   ```bash
   ./diagnostico_meta_purchase.sh > diagnostico_output.txt 2>&1
   ```

2. **Envie o arquivo `diagnostico_output.txt` para análise**

3. **Alternativamente, ajuste as variáveis de ambiente se necessário:**
   ```bash
   export DB_NAME=grimbots
   export DB_USER=postgres
   export DB_HOST=localhost
   export LOG_FILE=/var/log/grimbots/app.log
   export REDIS_HOST=localhost
   export REDIS_PORT=6379
   ./diagnostico_meta_purchase.sh > diagnostico_output.txt 2>&1
   ```

---

## 🔍 O QUE O SCRIPT COLETA

### **1. Análise do Banco de Dados:**
- ✅ Total de payments 'paid' dos últimos 7 dias
- ✅ Quantos têm `delivery_token`
- ✅ Quantos têm `meta_purchase_sent = true`
- ✅ **CRÍTICO:** Quantos têm `delivery_token` mas `meta_purchase_sent = false`
- ✅ Análise por pool (configuração Meta Pixel)
- ✅ Payments problemáticos (TOP 20)

### **2. Análise de Logs:**
- ✅ Erros relacionados a Purchase não enviado
- ✅ Warnings relacionados a Purchase
- ✅ Logs de sucesso de Purchase
- ✅ Logs de `delivery_page` (acessos)

### **3. Análise do Celery:**
- ✅ Workers ativos
- ✅ Tasks falhadas relacionadas a `send_meta_event`

### **4. Análise do Redis:**
- ✅ Conexão e saúde
- ✅ Quantidade de tracking tokens
- ✅ Tamanho do Redis

### **5. Análise de Configuração dos Pools:**
- ✅ Pools totalmente configurados
- ✅ Pools com configuração incompleta
- ✅ Pools com `meta_events_purchase = false`

### **6. Bots Sem Pool:**
- ✅ Bots que têm payments mas não estão associados a pool

### **7. Análise de Webhooks:**
- ✅ Webhooks recebidos
- ✅ Chamadas de `send_payment_delivery`

### **8. Resumo Executivo:**
- ✅ Taxa de envio de Purchase
- ✅ Quantidade de payments problemáticos
- ✅ Pools configurados corretamente

---

## 🎯 COM OS DADOS COLETADOS, VAMOS IDENTIFICAR:

1. **Quantos payments têm `delivery_token` mas `meta_purchase_sent = false`**
   - Se for 97 → leads não estão acessando `/delivery`
   - Se for 0 → problema está em outro lugar

2. **Quantos pools têm `meta_events_purchase = false`**
   - Se for alto → esta é a causa raiz!

3. **Quantos bots não estão associados a pool**
   - Se for alto → purchases não podem ser enviados

4. **Padrões nos logs**
   - Erros recorrentes indicam causa raiz específica

5. **Celery está processando tasks?**
   - Se não → tasks estão sendo enfileiradas mas não processadas

---

## ✅ APÓS RECEBER OS DADOS

Vou analisar e identificar a **CAUSA RAIZ REAL** baseada em **DADOS CONCRETOS**, não suposições.

Então vou propor **SOLUÇÃO CIRÚRGICA** e **ROBUSTA** baseada nos fatos.

---

**STATUS:** Aguardando execução do script na VPS e envio dos dados

