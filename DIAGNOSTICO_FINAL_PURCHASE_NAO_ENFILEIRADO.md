# 🔍 DIAGNÓSTICO FINAL - Purchase não está sendo enfileirado no Celery

## 🎯 PROBLEMA IDENTIFICADO

**10 vendas com `meta_purchase_sent = True` mas `meta_event_id = NULL`**

**Diagnóstico do script:**
- ✅ `meta_purchase_sent` está sendo marcado
- ❌ **Purchase enfileirados: 0** - **PROBLEMA CRÍTICO!**
- ❌ Purchase não está sendo enfileirado no Celery
- ✅ Workers do Celery estão OK mas vazios

**Conclusão:** Purchase está sendo marcado como enviado, mas **NÃO está sendo enfileirado no Celery**.

---

## 🔍 ANÁLISE DO CÓDIGO

### **Fluxo de Purchase:**

1. **Linha 7519-7537:** `send_payment_delivery()` chama `send_meta_pixel_purchase_event()`
2. **Linha 8240:** `send_meta_pixel_purchase_event()` inicia
3. **Linha 8245-8294:** Verificações que podem bloquear:
   - Bot não associado a pool (linha 8248-8251)
   - Meta tracking desabilitado (linha 8261-8264)
   - Sem pixel_id ou access_token (linha 8266-8269)
   - Evento Purchase desabilitado (linha 8273-8276)
   - Purchase já enviado com meta_event_id (linha 8284-8288)
   - **✅ Purchase marcado mas sem meta_event_id (linha 8289-8294) - PERMITE ENVIO**
4. **Linha 9296:** Preparando envio Meta Purchase
5. **Linha 9349-9357:** Enfileirar no Celery
6. **Linha 9359:** Log "Purchase enfileirado"

**Se `Purchase enfileirados: 0`, significa que Purchase não está chegando na linha 9359.**

---

## 🎯 POSSÍVEIS CAUSAS

### **CAUSA 1: Purchase está sendo bloqueado por verificação ANTES de enfileirar**

**Verificações que podem bloquear:**
- Bot não associado a pool (linha 8248)
- Meta tracking desabilitado (linha 8261)
- Evento Purchase desabilitado (linha 8273)
- Sem pixel_id ou access_token (linha 8266)

**Verificação:**
```bash
tail -2000 logs/gunicorn.log | grep -iE "Bot.*não está associado|Meta tracking DESABILITADO|Evento Purchase DESABILITADO|SEM pixel_id ou access_token"
```

### **CAUSA 2: Erro ao enfileirar (não está sendo logado)**

**Verificação:**
```bash
tail -2000 logs/gunicorn.log | grep -iE "ERRO.*enfileirar Purchase|Erro.*Purchase.*Celery|Purchase.*exception|Purchase.*error"
```

### **CAUSA 3: `send_meta_pixel_purchase_event()` não está sendo chamado**

**Verificação:**
```bash
tail -2000 logs/gunicorn.log | grep -i "Purchase - Iniciando send_meta_pixel_purchase_event"
```

### **CAUSA 4: Purchase está sendo preparado mas não está sendo enfileirado**

**Verificação:**
```bash
tail -2000 logs/gunicorn.log | grep -iE "Preparando envio Meta Purchase|INICIANDO ENFILEIRAMENTO"
```

---

## 🔧 SCRIPT DE VERIFICAÇÃO

Execute o script `verificar_logs_purchase_nao_enfileirado.sh`:

```bash
chmod +x verificar_logs_purchase_nao_enfileirado.sh
bash verificar_logs_purchase_nao_enfileirado.sh
```

O script verifica:
1. ✅ Se `send_meta_pixel_purchase_event()` está sendo chamado
2. ✅ Se há erros bloqueando Purchase ANTES de enfileirar
3. ✅ Se Purchase está sendo preparado
4. ✅ Se Purchase está sendo enfileirado
5. ✅ Se há erros ao enfileirar
6. ✅ Logs de Purchase para venda específica
7. ✅ Últimos logs de Purchase
8. ✅ Logs de Delivery

---

## 📋 PRÓXIMOS PASSOS

1. ✅ **Execute o script** `verificar_logs_purchase_nao_enfileirado.sh`
2. ✅ **Identifique qual verificação está bloqueando** (seção 2 do script)
3. ✅ **Corrija o problema** (configuração do pool, etc)
4. ✅ **Teste com uma nova venda** para confirmar correção
5. ✅ **Verifique Meta Event Manager** para confirmar que Purchase aparece

---

## ⚠️ NOTAS IMPORTANTES

1. **Purchase só é enfileirado após passar todas as verificações** (linhas 8245-8294)
2. **Se Purchase não está sendo enfileirado, significa que está sendo bloqueado por alguma verificação**
3. **Logs devem mostrar qual verificação está bloqueando** (erros específicos)
4. **Workers do Celery estão OK, mas não há tasks para processar** (Purchase não está sendo enfileirado)

---

## ✅ STATUS

- ✅ Script de verificação criado
- ✅ Análise do código realizada
- ⚠️ **Aguardando execução do script para identificar causa raiz específica**

