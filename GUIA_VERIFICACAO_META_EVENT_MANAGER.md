# 📊 GUIA - Verificar Deduplicação no Meta Event Manager

## 🎯 OBJETIVO

Verificar se a deduplicação está funcionando corretamente no Meta Event Manager após uma nova venda.

---

## 📋 PASSO A PASSO NO META EVENT MANAGER

### **1. Acessar Event Manager**

**URL:**
```
https://business.facebook.com/events_manager2/list/pixel/{pixel_id}/overview
```

**Ou:**
1. Acessar Meta Business Suite
2. Ir em **Eventos** (Events Manager)
3. Selecionar seu Pixel ID
4. Ir em **Visão Geral** (Overview)

---

### **2. Verificar Test Events (Eventos de Teste)**

**Acesse:**
- Event Manager → **Test Events** (Eventos de Teste)

**O que verificar:**

#### **✅ Sucesso - Deduplicação funcionando:**
- **1 evento Purchase** aparece (não 2)
- **Status:** "Deduplicated" ou "Received"
- **Event ID:** Mesmo `event_id` usado no código
- **Source:** "Browser" ou "Server" (apenas 1)
- **Event Time:** Mesmo timestamp

#### **❌ Problema - Duplicação detectada:**
- **2 eventos Purchase** aparecem (duplicado!)
- **Status:** Ambos "Received" (não deduplicados)
- **Event ID:** Diferentes (não deduplicados)
- **Source:** Um "Browser" e outro "Server"
- **Event Time:** Timestamps diferentes ou muito próximos

---

### **3. Verificar Event Details (Detalhes do Evento)**

**Acesse:**
- Event Manager → **Test Events** → Clicar no evento Purchase

**O que verificar:**

#### **✅ Sucesso:**
- **Event ID:** `purchase_{payment.id}_{timestamp}` (formato correto)
- **Event Name:** "Purchase"
- **Source:** "Browser" ou "Server" (apenas 1)
- **Status:** "Deduplicated" ou "Received"
- **User Data:** `external_id`, `fbp`, `fbc` presentes

#### **❌ Problema:**
- **Event ID:** Formato diferente (`purchase_BOT43_...` em vez de `purchase_{id}_{timestamp}`)
- **Status:** "Received" (não deduplicado)
- **User Data:** Faltando `external_id`, `fbp`, ou `fbc`

---

### **4. Verificar Event Coverage (Cobertura de Eventos)**

**Acesse:**
- Event Manager → **Event Coverage** (Cobertura de Eventos)

**O que verificar:**

#### **✅ Sucesso:**
- **Event Coverage:** ≥ 75% (Meta recomenda)
- **Deduplication Overlap:** ≥ 50%
- **Browser Events:** Presentes
- **Server Events:** Presentes
- **Deduplicated Events:** Presentes

#### **❌ Problema:**
- **Event Coverage:** 0% (sem deduplicação)
- **Deduplication Overlap:** < 50%
- **Browser Events:** Presentes mas não deduplicados
- **Server Events:** Presentes mas não deduplicados
- **Deduplicated Events:** Ausentes

---

### **5. Verificar Event Diagnostics (Diagnóstico de Eventos)**

**Acesse:**
- Event Manager → **Diagnostics** (Diagnósticos)

**O que verificar:**

#### **✅ Sucesso:**
- **Event Quality:** Alta (High)
- **Match Quality:** Alta (High)
- **Deduplication:** Funcionando
- **Warnings:** Nenhum warning crítico

#### **❌ Problema:**
- **Event Quality:** Baixa (Low)
- **Match Quality:** Baixa (Low)
- **Deduplication:** Não funcionando
- **Warnings:** "Event ID mismatch" ou "Duplicate events detected"

---

## 🔍 COMO IDENTIFICAR DUPLICAÇÃO

### **Método 1: Verificar Test Events**

1. Acessar **Test Events**
2. Filtrar por **Event Name:** "Purchase"
3. Verificar se há **2 eventos** com mesmo timestamp
4. Verificar se **Event ID** é o mesmo ou diferente

**Se Event ID for o mesmo:**
- ✅ **Deduplicação funcionando** (Meta deve mostrar apenas 1 evento ou status "Deduplicated")

**Se Event ID for diferente:**
- ❌ **Deduplicação quebrada** (Meta mostrará 2 eventos separados)

### **Método 2: Verificar Event Coverage**

1. Acessar **Event Coverage**
2. Selecionar **Event:** "Purchase"
3. Verificar **Event Coverage** (deve ser ≥ 75%)
4. Verificar **Deduplication Overlap** (deve ser ≥ 50%)

**Se Event Coverage ≥ 75% e Overlap ≥ 50%:**
- ✅ **Deduplicação funcionando**

**Se Event Coverage = 0% ou Overlap < 50%:**
- ❌ **Deduplicação não funcionando**

### **Método 3: Verificar Event Details**

1. Acessar **Test Events**
2. Clicar no evento Purchase
3. Verificar **Event ID**
4. Verificar **Status** (deve ser "Deduplicated" se deduplicado)

**Se Status = "Deduplicated":**
- ✅ **Deduplicação funcionando**

**Se Status = "Received" (e há 2 eventos):**
- ❌ **Deduplicação não funcionando**

---

## 📊 CHECKLIST DE VERIFICAÇÃO

### **✅ Checklist - Test Events**

- [ ] Apenas 1 evento Purchase aparece (não 2)
- [ ] Status é "Deduplicated" ou "Received"
- [ ] Event ID corresponde ao usado no código
- [ ] Source é "Browser" ou "Server" (apenas 1)

### **✅ Checklist - Event Coverage**

- [ ] Event Coverage ≥ 75% (Meta recomenda)
- [ ] Deduplication Overlap ≥ 50%
- [ ] Browser Events e Server Events estão presentes
- [ ] Deduplicated Events estão presentes

### **✅ Checklist - Event Details**

- [ ] Event ID tem formato correto (`purchase_{id}_{timestamp}`)
- [ ] User Data tem `external_id`, `fbp`, `fbc`
- [ ] Custom Data tem UTMs e `campaign_code` (se disponíveis)
- [ ] Status é "Deduplicated" ou "Received"

---

## ⚠️ PROBLEMAS COMUNS E SOLUÇÕES

### **Problema 1: 2 Eventos Purchase no Test Events**

**Causa:**
- `event_id` diferente entre client-side e server-side
- Meta não consegue deduplicar eventos com `event_id` diferentes

**Solução:**
- Verificar logs para confirmar que `event_id` está sendo passado corretamente
- Garantir que mesmo `event_id` seja usado em ambos

### **Problema 2: Event Coverage 0%**

**Causa:**
- `event_id` não está sendo usado corretamente
- `pageview_event_id` não está sendo recuperado

**Solução:**
- Verificar se `pageview_event_id` está sendo passado como parâmetro
- Garantir que `event_id` tenha mesmo formato em ambos

### **Problema 3: Status "Received" em vez de "Deduplicated"**

**Causa:**
- Eventos têm `event_id` diferentes
- Meta não consegue deduplicar eventos com `event_id` diferentes

**Solução:**
- Garantir que mesmo `event_id` seja usado em ambos
- Verificar se `pageview_event_id` está sendo passado corretamente

---

## 🎯 RESULTADO ESPERADO

**Após verificação:**
- ✅ **Apenas 1 evento Purchase** no Test Events (não 2)
- ✅ **Status:** "Deduplicated" ou "Received"
- ✅ **Event Coverage:** ≥ 75%
- ✅ **Deduplication Overlap:** ≥ 50%
- ✅ **Event ID:** Mesmo usado no código (`purchase_{id}_{timestamp}`)

---

## 📋 PRÓXIMOS PASSOS

1. ✅ Gerar uma nova venda de teste
2. ✅ Executar script `verificar_deduplicacao.sh` no servidor
3. ✅ Verificar Event Manager do Meta (Test Events)
4. ✅ Verificar Event Coverage
5. ✅ Confirmar que não há duplicação e deduplicação está funcionando

