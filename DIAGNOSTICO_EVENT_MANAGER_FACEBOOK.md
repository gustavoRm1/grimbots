# 🔍 DIAGNÓSTICO - EVENT MANAGER DO FACEBOOK

## 📊 SITUAÇÃO ATUAL (BASEADO NO EVENT MANAGER)

### **O QUE ESTÁ FUNCIONANDO:**
- ✅ **57 conversões adicionais relatadas** da API de conversões (servidor)
- ✅ **Eventos estão chegando** (última mensagem há 2 horas)
- ✅ **Sistema está enviando Purchase events** (objetivo parcialmente alcançado)
- ✅ **Qualidade 7,4/10** (funcional, mas pode melhorar)

### **O QUE NÃO ESTÁ FUNCIONANDO:**
- ❌ **"Melhore a desduplicação para este evento"** - Desduplicação está abaixo do ideal
- ❌ **Qualidade pode melhorar** (7,4/10 - ideal seria 8,5+/10)
- ⚠️ **Match Quality pode melhorar** - Event match quality precisa melhorar

---

## 🎯 OBJETIVO FINAL: VENDAS TRACKEADAS CORRETAMENTE

### **STATUS ATUAL:**
- ✅ **PARCIALMENTE ALCANÇADO** - Vendas estão aparecendo, mas podem melhorar
- ⚠️ **Desduplicação está ruim** - Meta não consegue deduplicar eventos corretamente
- ⚠️ **Match Quality está baixa** - Meta não consegue fazer matching perfeito

---

## 🔍 PROBLEMAS IDENTIFICADOS PELO META

### **PROBLEMA 1: Desduplicação ruim**

**Meta diz:**
> "Melhore a desduplicação para este evento a fim de visualizar resultados adicionais de conversões"

**Causa provável:**
- ❌ **`event_id` não está sendo enviado** ou está inconsistente
- ❌ **`external_id` (fbclid) não está sendo enviado** ou está inconsistente
- ❌ **`fbp` não está sendo enviado** ou está inconsistente

**Impacto:**
- ⚠️ Meta não consegue deduplicar eventos (browser vs servidor)
- ⚠️ Pode estar contando eventos duplicados
- ⚠️ "Conversões adicionais relatadas" não aparece corretamente

---

### **PROBLEMA 2: Match Quality baixa**

**Meta diz:**
> "Your event match quality needs improvement"

**Causa provável:**
- ❌ **`fbc` não está sendo enviado** ou está inconsistente (PARAMETER BUILDER!)
- ❌ **`fbp` não está sendo enviado** ou está inconsistente
- ❌ **`external_id` (fbclid) não está sendo enviado** ou está inconsistente
- ❌ **Dados de cliente (email, telefone) podem estar faltando**

**Impacto:**
- ⚠️ Meta não consegue fazer matching perfeito entre PageView e Purchase
- ⚠️ Vendas podem não estar sendo atribuídas corretamente às campanhas
- ⚠️ Qualidade 7,4/10 (ideal seria 8,5+/10)

---

## ✅ SOLUÇÕES

### **SOLUÇÃO 1: Melhorar Desduplicação**

**O que fazer:**
1. ✅ **Garantir que `event_id` está sendo enviado** em todos os eventos (PageView e Purchase)
2. ✅ **Garantir que `event_id` é CONSISTENTE** entre browser e servidor
3. ✅ **Garantir que `external_id` (fbclid) está sendo enviado**
4. ✅ **Garantir que `fbp` está sendo enviado**

**Como verificar:**
```bash
# Ver se event_id está sendo enviado
tail -100 logs/gunicorn.log | grep -E "event_id|event-id" | tail -10

# Ver se external_id está sendo enviado
tail -100 logs/gunicorn.log | grep -E "external_id|external-id" | tail -10

# Ver se fbp está sendo enviado
tail -100 logs/gunicorn.log | grep -E "fbp|_fbp" | tail -10
```

---

### **SOLUÇÃO 2: Melhorar Match Quality (PARAMETER BUILDER!)**

**O que fazer:**
1. ✅ **Usar Parameter Builder para `fbc`** - Isso melhora MUITO o match quality
2. ✅ **Garantir que `fbc` está sendo enviado** em todos os eventos (PageView e Purchase)
3. ✅ **Garantir que `fbp` está sendo enviado** em todos os eventos
4. ✅ **Garantir que `external_id` (fbclid) está sendo enviado**

**Por que Parameter Builder é importante:**
- ✅ **Meta recomenda Parameter Builder** para melhorar match quality
- ✅ **`fbc` do Parameter Builder** tem melhor qualidade que `fbc` gerado manualmente
- ✅ **Match Quality pode melhorar de 7,4/10 para 8,5+/10**

**Impacto esperado:**
- ✅ **Match Quality melhora** (de 7,4/10 para 8,5+/10)
- ✅ **Desduplicação melhora** (overlap acima de 50%)
- ✅ **"Conversões adicionais relatadas" aparece corretamente**
- ✅ **Vendas são atribuídas corretamente às campanhas**

---

## 🔧 VERIFICAÇÃO DO CÓDIGO

### **VERIFICAR SE `event_id` ESTÁ SENDO ENVIADO:**

```bash
# Ver logs de Purchase events
tail -100 logs/gunicorn.log | grep "META PURCHASE.*Purchase -" | grep -E "event_id|event-id" | tail -5
```

**O que procurar:**
- ✅ `event_id: purchase_PAY_12345_1734567890` → `event_id` está sendo enviado
- ❌ Nenhuma menção a `event_id` → `event_id` não está sendo enviado

---

### **VERIFICAR SE `fbc` ESTÁ SENDO ENVIADO:**

```bash
# Ver logs de Purchase events com fbc
tail -100 logs/gunicorn.log | grep "META PURCHASE.*Purchase -" | grep -E "fbc|fbc REAL" | tail -5
```

**O que procurar:**
- ✅ `fbc REAL aplicado: fb.1.1734567890...` → `fbc` está sendo enviado
- ❌ `fbc ausente ou ignorado` → `fbc` não está sendo enviado

---

### **VERIFICAR SE `external_id` ESTÁ SENDO ENVIADO:**

```bash
# Ver logs de Purchase events com external_id
tail -100 logs/gunicorn.log | grep "META PURCHASE.*Purchase -" | grep -E "external_id|fbclid" | tail -5
```

**O que procurar:**
- ✅ `external_id: [hash]` → `external_id` está sendo enviado
- ❌ Nenhuma menção a `external_id` → `external_id` não está sendo enviado

---

## 📊 RESULTADO ESPERADO APÓS CORREÇÕES

### **ANTES (Situação atual):**
- ⚠️ Qualidade: 7,4/10
- ⚠️ Desduplicação: abaixo de 50% overlap
- ⚠️ Match Quality: baixa
- ⚠️ "Melhore a desduplicação para este evento"

### **DEPOIS (Com Parameter Builder e correções):**
- ✅ Qualidade: 8,5+/10
- ✅ Desduplicação: acima de 50% overlap
- ✅ Match Quality: alta
- ✅ "Conversões adicionais relatadas" aparece corretamente
- ✅ Vendas são atribuídas corretamente às campanhas

---

## 🎯 AÇÃO IMEDIATA

### **PASSO 1: Verificar se Parameter Builder está sendo usado**

```bash
bash testar_parameter_builder.sh
```

**Se mostrar 0 eventos com fbc do Parameter Builder:**
- ❌ Parameter Builder não está sendo usado
- ✅ Precisamos corrigir isso (isso vai melhorar match quality)

---

### **PASSO 2: Verificar se event_id está sendo enviado**

```bash
tail -100 logs/gunicorn.log | grep "META PURCHASE.*Purchase -" | grep -E "event_id" | tail -5
```

**Se não aparecer event_id:**
- ❌ `event_id` não está sendo enviado
- ✅ Precisamos adicionar `event_id` (isso vai melhorar desduplicação)

---

### **PASSO 3: Verificar logs de Purchase com fbc**

```bash
tail -100 logs/gunicorn.log | grep "META PURCHASE.*Purchase -" | grep -E "fbc" | tail -5
```

**O que procurar:**
- ✅ `fbc REAL aplicado` → fbc está sendo enviado (bom)
- ❌ `fbc ausente` → fbc não está sendo enviado (ruim)

---

## 🎯 CONCLUSÃO

### **OBJETIVO FINAL: PARCIALMENTE ALCANÇADO**

**Situação:**
- ✅ **Vendas estão aparecendo** (57 conversões adicionais relatadas)
- ⚠️ **Mas qualidade pode melhorar** (7,4/10 - ideal 8,5+/10)
- ⚠️ **Desduplicação está ruim** (abaixo de 50% overlap)
- ⚠️ **Match Quality está baixa** (pode melhorar)

**Problemas:**
1. ❌ **Parameter Builder não está sendo usado** (fbc não vem do Parameter Builder)
2. ❌ **Desduplicação está ruim** (event_id ou external_id pode estar faltando)

**Soluções:**
1. ✅ **Usar Parameter Builder para fbc** (melhora match quality)
2. ✅ **Garantir que event_id está sendo enviado** (melhora desduplicação)
3. ✅ **Garantir que external_id está sendo enviado** (melhora desduplicação e match quality)

**Próximo passo:**
- ✅ Verificar se event_id está sendo enviado
- ✅ Verificar se Parameter Builder está sendo usado
- ✅ Corrigir para melhorar qualidade de 7,4/10 para 8,5+/10

