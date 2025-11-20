# 🔍 DIAGNÓSTICO - event_id e UTMs não estão sendo recuperados

## 🎯 PROBLEMAS IDENTIFICADOS

### **1. `event_id` está sendo gerado novo em vez de reutilizar `pageview_event_id`**

**Log mostra:**
```
⚠️ Purchase - event_id gerado novo: purchase_BOT43_1763604996_719fe4c8_1763594239 (cobertura será 0% - desduplicação quebrada)
```

**Causa:**
- `pageview_event_id` não está sendo recuperado do `tracking_data` (Redis)
- `pageview_event_id` não está sendo recuperado do `payment` (banco)
- Resultado: `event_id` novo é gerado, quebrando desduplicação

### **2. UTMs não estão sendo enviados no Purchase**

**Log mostra:**
- ❌ Nenhum log de `Purchase - utm_source do tracking_data (Redis): ...`
- ❌ Nenhum log de `Purchase - campaign_code do tracking_data (Redis): ...`
- ❌ Resultado: Purchase enviado sem UTMs

### **3. `event_id` diferente entre server-side e client-side**

**Server-side:** `purchase_BOT43_1763604996_719fe4c8_1763594239`
**Client-side:** `purchase_9372_1763605039...` (diferente!)

---

## ✅ CORREÇÕES IMPLEMENTADAS

### **1. Logs mais detalhados para diagnosticar `event_id`**

**Adicionado em `app.py` (linhas 8816-8847):**
- ✅ Logs mostrando se `tracking_data` existe
- ✅ Logs mostrando se `tracking_data` tem `pageview_event_id`
- ✅ Logs mostrando se `payment` tem `pageview_event_id`
- ✅ Logs mostrando campos disponíveis no `tracking_data` se não tiver `pageview_event_id`
- ✅ Logs críticos quando `event_id` novo é gerado

### **2. Logs já existentes para diagnosticar UTMs**

**Já implementado em `app.py` (linhas 9016-9044):**
- ✅ Logs mostrando se `tracking_data` tem UTMs
- ✅ Logs mostrando se `payment` tem UTMs
- ✅ Logs mostrando se `bot_user` tem UTMs
- ✅ Logs mostrando `tracking_token` usado

---

## 🎯 PRÓXIMOS PASSOS

### **1. Gerar uma nova venda de teste**

**Para ver os logs detalhados:**
1. Acessar URL com `fbclid` (ex: `https://app.grimbots.online/go/{slug}?fbclid=...`)
2. Interagir com bot
3. Gerar pagamento
4. Monitorar logs

### **2. Verificar logs detalhados**

**Execute no servidor Linux:**
```bash
tail -f logs/gunicorn.log | grep -E "Purchase.*event_id|Purchase.*pageview_event_id|tracking_data tem pageview_event_id|Purchase.*utm_source|Purchase.*campaign_code|Purchase SEM UTMs"
```

**O que procurar:**

#### **Se `pageview_event_id` não está sendo recuperado:**
- ❌ `tracking_data existe: False` → `tracking_data` não foi recuperado do Redis
- ❌ `tracking_data tem pageview_event_id: False` → `tracking_data` não tem `pageview_event_id`
- ❌ `payment tem pageview_event_id: False` → `payment` não tem `pageview_event_id` salvo

#### **Se UTMs não estão sendo enviados:**
- ❌ `tracking_data tem utm_source: False` → `tracking_data` não tem UTMs
- ❌ `payment tem utm_source: False` → `payment` não tem UTMs salvos

---

## 🔧 AÇÕES CORRETIVAS NECESSÁRIAS

### **Ação 1: Garantir que `pageview_event_id` seja salvo no `payment`**

**Verificar `bot_manager.py` `_generate_pix_payment`:**
- ✅ `pageview_event_id` deve ser salvo do `tracking_data_v4` para o `Payment`
- ✅ Se `tracking_data_v4` não tiver `pageview_event_id`, salvar `None` (não gerar novo)

### **Ação 2: Garantir que UTMs sejam salvos no `payment`**

**Verificar `bot_manager.py` `_generate_pix_payment`:**
- ✅ UTMs devem ser salvos do `tracking_data_v4` para o `Payment`
- ✅ `campaign_code` deve ser salvo do `tracking_data_v4.get('grim')` para o `Payment`

### **Ação 3: Garantir que `event_id` seja o mesmo no client-side e server-side**

**Verificar `app.py` `send_payment_delivery`:**
- ✅ `pixel_config.event_id` deve usar o mesmo `pageview_event_id` recuperado no Purchase
- ✅ Se não tiver `pageview_event_id`, **NÃO** gerar novo no client-side (usar o mesmo do server-side)

---

## 📊 RESULTADO ESPERADO

**Após correções:**
- ✅ **`event_id` reutilizado do `pageview_event_id`** (logs mostrarão: `✅ Purchase - event_id reutilizado do tracking_data (Redis): ...`)
- ✅ **UTMs presentes em 100% dos Purchases** (logs mostrarão: `✅ Purchase - utm_source do tracking_data (Redis): ...`)
- ✅ **Cobertura de eventos ≥75%** (Meta recomenda)
- ✅ **Desduplicação funcionando corretamente**
- ✅ **Vendas atribuídas às campanhas corretamente**

---

## ⚠️ CRITICIDADE

**🔴 CRÍTICO:**
- Sem `pageview_event_id` correto, **DESDUPLICAÇÃO NÃO FUNCIONA** (cobertura 0%)
- Sem UTMs, **VENDAS NÃO SÃO ATRIBUÍDAS ÀS CAMPANHAS**
- Sem desduplicação, **Meta não reconhece eventos como do mesmo usuário**

**Próximo passo:**
1. Gerar uma nova venda de teste
2. Verificar logs detalhados acima
3. Analisar logs para identificar causa raiz
4. Aplicar correções específicas baseadas nos logs

