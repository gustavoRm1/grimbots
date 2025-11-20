# 📋 RESUMO - Logs Adicionados para Diagnóstico

## ✅ LOGS ADICIONADOS

### **1. Logs no início de `send_meta_pixel_purchase_event`**

**Adicionado em `app.py` (linhas 8273-8274):**
- ✅ `[META PURCHASE] Purchase - Iniciando send_meta_pixel_purchase_event para payment {payment.id}`
- ✅ `[META PURCHASE] Purchase - Iniciando recuperação de tracking_data para payment {payment.id}`
- ✅ `[META PURCHASE] Purchase - TrackingServiceV4 inicializado`
- ✅ `[META PURCHASE] Purchase - Dados iniciais: payment.tracking_token=..., bot_user=..., bot_user.tracking_session_id=...`

### **2. Logs detalhados para `event_id`**

**Adicionado em `app.py` (linhas 8816-8854):**
- ✅ Verifica se `tracking_data` existe
- ✅ Verifica se `tracking_data` tem `pageview_event_id`
- ✅ Verifica se `payment` tem `pageview_event_id`
- ✅ Mostra campos disponíveis no `tracking_data` se não tiver `pageview_event_id`
- ✅ Logs críticos quando `event_id` novo é gerado

### **3. Logs já existentes para UTMs**

**Já implementado em `app.py` (linhas 9016-9044):**
- ✅ Logs mostrando se `tracking_data` tem UTMs
- ✅ Logs mostrando se `payment` tem UTMs
- ✅ Logs mostrando se `bot_user` tem UTMs
- ✅ Logs mostrando `tracking_token` usado

---

## 🔍 COMANDO PARA VERIFICAR LOGS

**Execute no servidor Linux:**
```bash
tail -f logs/gunicorn.log | grep -E "META PURCHASE|Purchase.*event_id|Purchase.*pageview_event_id|tracking_data tem pageview_event_id|Purchase.*utm_source|Purchase.*campaign_code|Purchase SEM UTMs|Purchase - Iniciando"
```

---

## 📊 O QUE OS LOGS DEVEM MOSTRAR

### **Se a função está sendo chamada:**
```
[META PURCHASE] Purchase - Iniciando send_meta_pixel_purchase_event para payment 9372
[META PURCHASE] Purchase - Iniciando recuperação de tracking_data para payment 9372
[META PURCHASE] Purchase - TrackingServiceV4 inicializado
[META PURCHASE] Purchase - Dados iniciais: payment.tracking_token=✅, bot_user=✅, bot_user.tracking_session_id=✅
```

### **Se `pageview_event_id` não está sendo recuperado:**
```
[META PURCHASE] Purchase - Verificando pageview_event_id no tracking_data...
   tracking_data existe: False
   ⚠️ tracking_data NÃO tem pageview_event_id! Campos disponíveis: []
⚠️ [CRÍTICO] Purchase - event_id NÃO encontrado! Gerando novo event_id (desduplicação NÃO funcionará!)
   tracking_data existe: False
   tracking_data tem pageview_event_id: False
   payment tem pageview_event_id: False
   ⚠️ ATENÇÃO: Cobertura será 0% - Meta não conseguirá deduplicar eventos!
⚠️ Purchase - event_id gerado novo: purchase_9372_1763605039 (cobertura será 0% - desduplicação quebrada)
```

### **Se UTMs não estão sendo enviados:**
```
❌ [CRÍTICO] Purchase SEM UTMs e SEM campaign_code! Payment: 9372
   tracking_data existe: False
   tracking_data tem utm_source: False
   payment tem utm_source: False
   ⚠️ ATENÇÃO: Esta venda NÃO será atribuída à campanha no Meta Ads Manager!
```

---

## ⚠️ IMPORTANTE

**Se os logs não aparecerem:**
- ❌ A função `send_meta_pixel_purchase_event` não está sendo chamada
- ❌ Ou há um erro antes dos logs serem executados
- ✅ **Solução:** Verificar se há erros anteriores nos logs

**Se apenas o aviso "Meta Pixel Purchase terá atribuição reduzida (sem pageview_event_id)" aparecer:**
- ❌ Pode estar vindo de outro lugar (talvez do `send_payment_delivery`)
- ✅ **Solução:** Verificar de onde vem esse aviso

---

## 🎯 PRÓXIMOS PASSOS

1. **Gerar uma nova venda de teste**
2. **Executar o comando de verificação acima**
3. **Analisar os logs detalhados**
4. **Identificar causa raiz baseado nos logs**
5. **Aplicar correções específicas**

