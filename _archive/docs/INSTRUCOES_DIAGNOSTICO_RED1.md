# 🔥 INSTRUÇÕES - DIAGNÓSTICO POOL "red1"

## 📋 EXECUTAR NA VPS

```bash
cd ~/grimbots

# Opção 1: Definir senha antes de executar
export PGPASSWORD="123sefudeu"
chmod +x diagnostico_pool_red1.sh
./diagnostico_pool_red1.sh > diagnostico_red1_output.txt 2>&1

# Opção 2: Executar e salvar em arquivo
chmod +x diagnostico_pool_red1.sh
./diagnostico_pool_red1.sh > diagnostico_red1_output.txt 2>&1
cat diagnostico_red1_output.txt
```

---

## 🔍 O QUE O SCRIPT VAI MOSTRAR

### **1. Configuração do Pool "red1"**
- Pool ID, User ID, Nome, Slug
- `meta_tracking_enabled`, `meta_pixel_id`, `meta_access_token`, `meta_events_purchase`
- Status da configuração (✅ OK ou ❌ PROBLEMA)

### **2. Bots Associados ao Pool "red1"**
- Lista todos os bots no pool
- Verifica se `bot.user_id` == `pool.user_id` (evita conflito)

### **3. Payments do Pool "red1" (HOJE)**
- Total de payments
- Quantos têm `delivery_token`
- Quantos têm `meta_purchase_sent = true`
- **Quantos têm problema** (delivery_token mas não têm purchase enviado)

### **4. Payments Problemáticos (TOP 50)**
- Lista detalhada dos payments com problema
- Pool usado para cada payment
- Configuração do pool usado
- **Possível causa** do problema

### **5. Bots em Múltiplos Pools**
- Identifica bots que estão em múltiplos pools
- **RISCO:** Se um bot está em múltiplos pools, `first()` pode retornar pool errado!

### **6. Tracking Token**
- Verifica se `tracking_token` está correto
- Token deve ser UUID (32 chars), NÃO "tracking_xxx"

### **7. Resumo Executivo**
- Estatísticas consolidadas
- Taxa de envio
- Número de bots em múltiplos pools (risco)

### **8. Logs Recentes**
- Erros relacionados a Purchase não enviado
- Warnings relacionados ao pool "red1"

---

## 🎯 COM ESSES DADOS VAMOS IDENTIFICAR

1. **Se o pool "red1" está configurado corretamente**
   - Se `meta_tracking_enabled = false` → essa é a causa!
   - Se falta `meta_pixel_id` ou `meta_access_token` → essa é a causa!
   - Se `meta_events_purchase = false` → essa é a causa!

2. **Se bots estão em múltiplos pools**
   - Se SIM → sistema pode estar usando pool errado!
   - Precisamos corrigir busca de pool para filtrar por `user_id`

3. **Se `tracking_token` está correto**
   - Se token é "tracking_xxx" → dados não foram salvos no Redis corretamente
   - Se token é UUID → dados devem estar no Redis

4. **Se há conflito de usuários**
   - Se `bot.user_id != pool.user_id` → BUG CRÍTICO!

---

## ✅ APÓS RECEBER OS DADOS

Vou analisar e identificar a **CAUSA RAIZ REAL** baseada nos dados específicos do pool "red1".

Então vou propor **SOLUÇÃO CIRÚRGICA** e **ROBUSTA**.

---

**Execute o script e me envie o resultado completo!**

