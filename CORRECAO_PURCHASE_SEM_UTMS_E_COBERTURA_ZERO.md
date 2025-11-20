# 🔴 CORREÇÃO CRÍTICA - Purchase SEM UTMs e Cobertura 0%

## 🎯 PROBLEMAS IDENTIFICADOS

### **1. Purchase SEM UTMs e SEM campaign_code**
- ❌ Vendas NÃO estão sendo atribuídas às campanhas
- ❌ Meta não consegue rastrear de qual campanha veio a venda
- ❌ Log: `❌ [CRÍTICO] Purchase SEM UTMs e SEM campaign_code! Payment: 9363`

### **2. Cobertura de Eventos 0% (Meta recomenda ≥75%)**
- ❌ Desduplicação NÃO está funcionando entre Pixel (browser) e Conversions API (servidor)
- ❌ Meta não consegue deduplicar eventos do mesmo usuário
- ❌ Resultado: Eventos duplicados ou não reconhecidos

---

## 🔍 DIAGNÓSTICO

### **Problema 1: Purchase SEM UTMs**

**Causa:**
- `tracking_data` não está sendo recuperado corretamente no Purchase
- OU `tracking_data` não tem UTMs salvos (não foram salvos no redirect)
- OU `payment` não tem UTMs salvos (não foram salvos no `_generate_pix_payment`)

**Fluxo esperado:**
1. ✅ Redirect salva UTMs no Redis (`tracking_payload` linha 4484)
2. ❌ Purchase não recupera `tracking_data` do Redis (ou `tracking_data` está vazio)
3. ❌ Purchase não recupera UTMs do `payment` (ou `payment` não tem UTMs)

### **Problema 2: Cobertura de Eventos 0%**

**Causa:**
- `event_id` não está sendo recuperado corretamente do `pageview_event_id`
- OU `event_id` está sendo gerado novo em vez de reutilizar o `pageview_event_id`
- OU `event_id` do client-side (browser) não corresponde ao `event_id` do server-side (CAPI)

**Fluxo esperado:**
1. ✅ Redirect salva `pageview_event_id` no Redis (`tracking_payload` linha 4477)
2. ✅ Client-side Purchase usa `eventID` do `pixel_config.event_id` (delivery.html linha 32)
3. ✅ Server-side Purchase usa `event_id` do `pageview_event_id` (app.py linha 9098)
4. ❌ MAS `event_id` não está sendo recuperado corretamente → gerando novo `event_id` → desduplicação quebrada

---

## ✅ CORREÇÕES IMPLEMENTADAS

### **1. Logs mais detalhados para diagnosticar UTMs**

**Adicionado em `app.py`:**
- Logs mostrando UTMs salvos no redirect (linha 4507)
- Logs mostrando `tracking_token` usado no Purchase (linha 9034)
- Logs mostrando se `tracking_data` existe e tem UTMs

### **2. Logs mais detalhados para diagnosticar `event_id`**

**Adicionado em `app.py`:**
- Logs mostrando se `pageview_event_id` foi recuperado do `tracking_data` (linha 8821)
- Logs mostrando se `pageview_event_id` foi recuperado do `payment` (linha 8826)
- Logs mostrando se `event_id` foi gerado novo (linha 8830) - **CRÍTICO para desduplicação**

---

## 🎯 PRÓXIMOS PASSOS

### **1. Verificar logs para diagnosticar**

**Executar:**
```bash
tail -100 logs/gunicorn.log | grep -E "Purchase.*utm_source|Purchase.*campaign_code|Purchase.*event_id|Purchase SEM UTMs|tracking_token usado"
```

**Procurar:**
- ✅ `Purchase - utm_source do tracking_data (Redis): ...`
- ✅ `Purchase - event_id reutilizado do tracking_data (Redis): ...`
- ❌ `Purchase SEM UTMs e SEM campaign_code!`
- ❌ `event_id NÃO encontrado! Gerando novo event_id`

### **2. Verificar se UTMs estão sendo salvos no redirect**

**Executar:**
```bash
tail -100 logs/gunicorn.log | grep -E "Redirect.*UTMs|tracking_payload.*utm"
```

**Procurar:**
- ✅ `Redirect - UTMs no tracking_payload: utm_source=✅, utm_campaign=✅`
- ❌ `Redirect - UTMs no tracking_payload: utm_source=❌, utm_campaign=❌`

### **3. Verificar se `event_id` está sendo usado corretamente**

**Executar:**
```bash
tail -100 logs/gunicorn.log | grep -E "Purchase.*event_id|PageView.*event_id|delivery.*eventID"
```

**Procurar:**
- ✅ `Purchase - event_id reutilizado do tracking_data (Redis): ...`
- ✅ `PageView - event_id gerado: ...`
- ❌ `Purchase - event_id NÃO encontrado! Gerando novo event_id`

---

## 🔧 AÇÕES CORRETIVAS NECESSÁRIAS

### **Ação 1: Garantir que UTMs sejam salvos no Payment**

**Verificar `bot_manager.py` `_generate_pix_payment`:**
- ✅ UTMs devem ser salvos do `tracking_data_v4` para o `Payment`
- ✅ `campaign_code` deve ser salvo do `tracking_data_v4.get('grim')` para o `Payment`

### **Ação 2: Garantir que `event_id` seja recuperado corretamente**

**Verificar `app.py` `send_meta_pixel_purchase_event`:**
- ✅ `event_id` deve ser recuperado do `tracking_data.get('pageview_event_id')`
- ✅ Se não encontrar, usar `payment.pageview_event_id`
- ❌ **NUNCA gerar novo `event_id`** se `pageview_event_id` existir!

### **Ação 3: Garantir que `event_id` seja o mesmo no client-side e server-side**

**Verificar `delivery.html`:**
- ✅ `eventID: '{{ pixel_config.event_id }}'` deve usar o `pageview_event_id`
- ✅ `pixel_config.event_id` deve ser o mesmo `event_id` usado no server-side

---

## 📊 RESULTADO ESPERADO

**Após correções:**
- ✅ **UTMs presentes em 100% dos Purchases**
- ✅ **Cobertura de eventos ≥75%** (Meta recomenda)
- ✅ **Desduplicação funcionando corretamente**
- ✅ **Vendas atribuídas às campanhas corretamente**

---

## ⚠️ CRITICIDADE

**🔴 CRÍTICO:**
- Sem UTMs, **VENDAS NÃO SÃO ATRIBUÍDAS ÀS CAMPANHAS**
- Sem `event_id` correto, **DESDUPLICAÇÃO NÃO FUNCIONA**
- Cobertura 0% = **Meta não reconhece eventos como do mesmo usuário**

**Próximo passo:**
1. Executar comandos de diagnóstico acima
2. Analisar logs para identificar causa raiz
3. Aplicar correções específicas baseadas nos logs

