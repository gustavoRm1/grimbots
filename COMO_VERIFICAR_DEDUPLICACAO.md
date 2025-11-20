# 🔍 COMO VERIFICAR DEDUPLICAÇÃO - Purchase Events

## 🎯 OBJETIVO

Verificar se:
1. ✅ Mesmo `event_id` está sendo usado no client-side e server-side
2. ✅ Não há duplicação de eventos (client-side + server-side)
3. ✅ Deduplicação está funcionando corretamente
4. ✅ Meta está deduplicando eventos automaticamente

---

## 📋 PASSO A PASSO

### **1. Gerar uma Nova Venda de Teste**

1. Acessar URL com `fbclid` (ex: `https://app.grimbots.online/go/{slug}?fbclid=TESTE123...`)
2. Interagir com bot
3. Gerar pagamento
4. Acessar página de entrega (`/delivery/<token>`)

---

### **2. Verificar Logs em Tempo Real**

**Execute no servidor Linux:**
```bash
tail -f logs/gunicorn.log | grep -E "Purchase.*event_id|Purchase.*eventID|Delivery.*event_id|META PURCHASE|META DELIVERY"
```

**O que procurar:**

#### **✅ Sucesso - Mesmo `event_id` no client-side e server-side:**
```
[META DELIVERY] Delivery - event_id que será usado (mesmo do client-side): purchase_9380_1763607037...
✅ Purchase - event_id recebido como parâmetro (mesmo do client-side): purchase_9380_1763607037...
✅ Deduplicação garantida (mesmo event_id no client-side e server-side)
```

#### **✅ Sucesso - `event_id` gerado com mesmo formato:**
```
⚠️ Purchase - event_id gerado novo: purchase_9380_1763607037 (mesmo formato do client-side: purchase_{payment.id}_{time.time()})
✅ Garantido: mesmo formato = deduplicação funcionará mesmo sem pageview_event_id original
```

#### **❌ Problema - `event_id` diferente:**
```
[META DELIVERY] Delivery - event_id que será usado: purchase_9380_1763607037...
⚠️ Purchase - event_id gerado novo: purchase_BOT43_1763607031_eabd7eaf_1763596296
❌ FORMATO DIFERENTE = deduplicação quebrada!
```

---

### **3. Verificar Logs Específicos Após Venda**

**Execute no servidor Linux:**
```bash
# Buscar último Purchase event gerado
tail -500 logs/gunicorn.log | grep -E "Purchase.*event_id|Purchase.*Event Data" | tail -5
```

**O que procurar:**

#### **✅ Sucesso:**
```
🚀 [META PURCHASE] Purchase - Event Data: event_name=Purchase, event_id=purchase_9380_1763607037, event_time=1763607037
✅ Purchase - event_id recebido como parâmetro (mesmo do client-side): purchase_9380_1763607037...
```

#### **❌ Problema:**
```
🚀 [META PURCHASE] Purchase - Event Data: event_name=Purchase, event_id=purchase_BOT43_1763607031_eabd7eaf_1763596296, event_time=1763596296
⚠️ Purchase - event_id gerado novo: purchase_BOT43_1763607031_eabd7eaf_1763596296
```

---

### **4. Verificar no Event Manager do Meta**

**Acesse:**
- Meta Events Manager: https://business.facebook.com/events_manager2/list/pixel/{pixel_id}/overview
- Ou: Meta Ads Manager → Eventos → Ver eventos

**O que verificar:**

#### **✅ Sucesso - Deduplicação funcionando:**
- **1 evento Purchase** (não 2)
- **Status:** "Received" ou "Deduplicated"
- **Source:** "Browser" ou "Server" (deve aparecer apenas 1)
- **Event ID:** Mesmo `event_id` usado no client-side e server-side

#### **❌ Problema - Duplicação detectada:**
- **2 eventos Purchase** (duplicado!)
- **Status:** Ambos "Received" (não deduplicados)
- **Source:** Um "Browser" e outro "Server"
- **Event ID:** Diferentes (não deduplicados)

---

### **5. Verificar no Test Events Tool (Meta)**

**Acesse:**
- Meta Events Manager → Test Events: https://business.facebook.com/events_manager2/list/pixel/{pixel_id}/test_events

**O que verificar:**

#### **✅ Sucesso:**
- **1 evento Purchase** aparece
- **Status:** "Deduplicated" ou "Received"
- **Event ID:** Mesmo usado no código
- **Source:** "Browser" ou "Server" (apenas 1)

#### **❌ Problema:**
- **2 eventos Purchase** aparecem
- **Status:** Ambos "Received" (não deduplicados)
- **Event ID:** Diferentes
- **Source:** Um "Browser" e outro "Server"

---

### **6. Verificar Cobertura de Eventos (Event Coverage)**

**Acesse:**
- Meta Events Manager → Event Coverage: https://business.facebook.com/events_manager2/list/pixel/{pixel_id}/event_coverage

**O que verificar:**

#### **✅ Sucesso:**
- **Event Coverage:** ≥ 75% (Meta recomenda)
- **Deduplication:** Funcionando (overlap ≥ 50%)

#### **❌ Problema:**
- **Event Coverage:** 0% (sem deduplicação)
- **Deduplication:** Não funcionando (overlap < 50%)

---

## 🔍 COMANDOS DE VERIFICAÇÃO COMPLETA

### **Comando 1: Verificar último Purchase event**

```bash
tail -500 logs/gunicorn.log | grep -E "Purchase.*Event Data|Purchase.*event_id|Purchase.*Event ID" | tail -3
```

### **Comando 2: Verificar se `event_id` está sendo passado como parâmetro**

```bash
tail -500 logs/gunicorn.log | grep -E "Delivery.*event_id|Purchase.*event_id recebido|Purchase.*event_id gerado" | tail -5
```

### **Comando 3: Verificar se há duplicação (mesmo `event_id` em client-side e server-side)**

```bash
tail -500 logs/gunicorn.log | grep -E "Delivery.*event_id|Purchase.*event_id" | tail -10 | grep -E "purchase_[0-9]+_[0-9]+"
```

### **Comando 4: Verificar todos os Purchase events recentes**

```bash
tail -1000 logs/gunicorn.log | grep -E "Purchase.*Event Data|Purchase.*ENVIADO" | tail -10
```

---

## 📊 CHECKLIST DE VERIFICAÇÃO

### **✅ Checklist - Logs**

- [ ] `event_id` está sendo passado como parâmetro (`✅ Purchase - event_id recebido como parâmetro`)
- [ ] `event_id` tem mesmo formato no client-side e server-side (`purchase_{payment.id}_{time.time()}`)
- [ ] Não há avisos de `event_id` gerado novo (ou se houver, formato está correto)
- [ ] `event_id` é o mesmo no log de Delivery e Purchase

### **✅ Checklist - Event Manager**

- [ ] Apenas 1 evento Purchase aparece (não 2)
- [ ] Status é "Received" ou "Deduplicated"
- [ ] Event ID corresponde ao usado no código
- [ ] Source é "Browser" ou "Server" (apenas 1)

### **✅ Checklist - Event Coverage**

- [ ] Event Coverage ≥ 75% (Meta recomenda)
- [ ] Deduplication overlap ≥ 50%
- [ ] Não há duplicação visível

---

## ⚠️ PROBLEMAS COMUNS

### **Problema 1: `event_id` diferente entre client-side e server-side**

**Sintoma:**
- Log mostra `event_id` diferente no Delivery e Purchase
- Event Manager mostra 2 eventos Purchase

**Causa:**
- `pageview_event_id` não está sendo passado como parâmetro
- `event_id` está sendo gerado com formato diferente

**Solução:**
- Verificar se `pixel_config['event_id']` está sendo passado corretamente
- Garantir que mesmo formato seja usado em ambos

### **Problema 2: Deduplicação não funcionando**

**Sintoma:**
- Event Manager mostra 2 eventos Purchase
- Event Coverage está em 0%

**Causa:**
- `event_id` diferente entre client-side e server-side
- Meta não consegue deduplicar eventos com `event_id` diferentes

**Solução:**
- Garantir que mesmo `event_id` seja usado em ambos
- Verificar se `pageview_event_id` está sendo passado como parâmetro

### **Problema 3: Cobertura de eventos 0%**

**Sintoma:**
- Event Coverage está em 0%
- Meta não está deduplicando eventos

**Causa:**
- `event_id` não está sendo usado corretamente
- `pageview_event_id` não está sendo recuperado

**Solução:**
- Garantir que `pageview_event_id` seja passado como parâmetro
- Verificar se `event_id` tem mesmo formato em ambos

---

## 🎯 RESULTADO ESPERADO

**Após verificação:**
- ✅ **Apenas 1 evento Purchase** no Event Manager (não 2)
- ✅ **Status:** "Deduplicated" ou "Received"
- ✅ **Event Coverage:** ≥ 75%
- ✅ **Deduplication overlap:** ≥ 50%
- ✅ **Logs mostram:** Mesmo `event_id` no client-side e server-side

---

## 📋 PRÓXIMOS PASSOS

1. ✅ Gerar uma nova venda de teste
2. ✅ Verificar logs em tempo real (comando acima)
3. ✅ Verificar Event Manager do Meta (Test Events)
4. ✅ Verificar Event Coverage (Event Coverage)
5. ✅ Confirmar que não há duplicação e deduplicação está funcionando

---

## 🔧 SCRIPTS DE VERIFICAÇÃO

### **Script 1: Verificar último Purchase event**

```bash
#!/bin/bash
echo "🔍 VERIFICANDO ÚLTIMO PURCHASE EVENT"
echo "===================================="
echo ""
echo "1️⃣ Último Purchase event gerado:"
tail -500 logs/gunicorn.log | grep -E "Purchase.*Event Data|Purchase.*event_id" | tail -3
echo ""
echo "2️⃣ Event ID usado:"
tail -500 logs/gunicorn.log | grep -E "Purchase.*event_id|Delivery.*event_id" | tail -5 | grep -oE "purchase_[0-9]+_[0-9]+" | tail -2
echo ""
echo "3️⃣ Verificando se há duplicação (mesmos event_ids):"
tail -500 logs/gunicorn.log | grep -E "Purchase.*event_id|Delivery.*event_id" | tail -10 | grep -oE "purchase_[0-9]+_[0-9]+" | sort | uniq -c | sort -rn
echo ""
echo "✅ Verificação concluída!"
```

### **Script 2: Verificar deduplicação completa**

```bash
#!/bin/bash
echo "🔍 VERIFICAÇÃO COMPLETA DE DEDUPLICAÇÃO"
echo "======================================="
echo ""
echo "1️⃣ Últimos Purchase events:"
tail -500 logs/gunicorn.log | grep -E "Purchase.*Event Data" | tail -5
echo ""
echo "2️⃣ Event IDs usados:"
tail -500 logs/gunicorn.log | grep -E "Purchase.*event_id|Delivery.*event_id" | tail -10 | grep -oE "purchase_[0-9]+_[0-9]+" | sort -u
echo ""
echo "3️⃣ Verificando formato (deve ser purchase_{id}_{timestamp}):"
tail -500 logs/gunicorn.log | grep -E "Purchase.*event_id gerado|Purchase.*event_id recebido" | tail -5
echo ""
echo "4️⃣ Verificando se pageview_event_id foi passado como parâmetro:"
tail -500 logs/gunicorn.log | grep -E "Purchase.*event_id recebido como parâmetro|pageview_event_id NÃO foi passado" | tail -3
echo ""
echo "✅ Verificação concluída!"
```

---

## ⚠️ IMPORTANTE

**Para garantir deduplicação:**
1. ✅ Mesmo `event_id` no client-side e server-side
2. ✅ Meta deduplica automaticamente se `event_id` for o mesmo
3. ✅ Flag `meta_purchase_sent` como backup
4. ✅ Formato consistente de `event_id` em ambos

**Se houver problemas:**
1. Verificar logs detalhados acima
2. Verificar Event Manager do Meta
3. Verificar Event Coverage
4. Aplicar correções específicas baseadas nos logs

