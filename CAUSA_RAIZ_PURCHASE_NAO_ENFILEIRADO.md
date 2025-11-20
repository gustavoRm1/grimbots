# 🔍 CAUSA RAIZ - Purchase não está sendo enfileirado

## 🎯 PROBLEMA IDENTIFICADO

**10 vendas com `meta_purchase_sent = True` mas `meta_event_id = NULL`**

**Diagnóstico:**
- ✅ `meta_purchase_sent` está sendo marcado
- ❌ **Chamadas a send_meta_pixel_purchase_event: 0** - **FUNÇÃO NÃO ESTÁ SENDO CHAMADA!**
- ❌ Purchase não está sendo enfileirado no Celery

**Conclusão:** `send_meta_pixel_purchase_event()` **NÃO está sendo chamado**.

---

## 🔍 ANÁLISE DO CÓDIGO

### **Linha 7519 - Condição para chamar `send_meta_pixel_purchase_event()`:**

```python
if has_meta_pixel and not payment.meta_purchase_sent:
```

**Problema:** Se `meta_purchase_sent = True`, a condição `not payment.meta_purchase_sent` é `False`, e `send_meta_pixel_purchase_event()` **NÃO será chamado**.

### **Linha 7448 - Verificação de `has_meta_pixel`:**

```python
has_meta_pixel = pool and pool.meta_tracking_enabled and pool.meta_pixel_id and pool.meta_access_token
```

**Problema:** Se `has_meta_pixel = False`, a condição da linha 7519 não será atendida, e `send_meta_pixel_purchase_event()` **NÃO será chamado**.

---

## 🎯 POSSÍVEIS CAUSAS

### **CAUSA 1: has_meta_pixel é False**

**Sintoma:**
- `has_meta_pixel = False` na linha 7448
- Condição da linha 7519 não é atendida
- `send_meta_pixel_purchase_event()` não é chamado

**Possíveis Causas:**
- Pool não tem `meta_tracking_enabled = True`
- Pool não tem `meta_pixel_id`
- Pool não tem `meta_access_token`

**Verificação:**
```bash
psql -U postgres -d grimbots -c "
SELECT 
    p.id,
    p.payment_id,
    pool.meta_tracking_enabled,
    pool.meta_events_purchase,
    CASE WHEN pool.meta_pixel_id IS NOT NULL THEN '✅' ELSE '❌' END as has_pixel_id,
    CASE WHEN pool.meta_access_token IS NOT NULL THEN '✅' ELSE '❌' END as has_access_token
FROM payments p
JOIN bots b ON p.bot_id = b.id
JOIN pool_bots pb ON p.bot_id = pb.bot_id
JOIN pools pool ON pb.pool_id = pool.id
WHERE p.status = 'paid'
AND p.meta_purchase_sent = true
AND p.meta_event_id IS NULL
ORDER BY p.created_at DESC
LIMIT 10;
"
```

**Solução:**
- Ativar `meta_tracking_enabled = True` no pool
- Configurar `meta_pixel_id` no pool
- Configurar `meta_access_token` no pool

---

### **CAUSA 2: meta_purchase_sent já está True quando delivery é acessado**

**Sintoma:**
- `meta_purchase_sent = True` quando usuário acessa `/delivery/<token>`
- Condição `not payment.meta_purchase_sent` é `False`
- `send_meta_pixel_purchase_event()` não é chamado

**Possíveis Causas:**
- `meta_purchase_sent` foi marcado anteriormente mas `send_meta_pixel_purchase_event()` não foi chamado (ou falhou)
- `meta_purchase_sent` foi marcado mas houve erro ao chamar `send_meta_pixel_purchase_event()` que não foi capturado

**Verificação:**
```bash
tail -2000 logs/gunicorn.log | grep -iE "meta_purchase_sent marcado|Enviando Purchase via Server|Erro ao enviar Purchase"
```

**Solução:**
- Verificar se `send_meta_pixel_purchase_event()` está sendo chamado após marcar `meta_purchase_sent`
- Verificar se há erro ao chamar `send_meta_pixel_purchase_event()` que está sendo capturado silenciosamente

---

### **CAUSA 3: Erro ao chamar send_meta_pixel_purchase_event() está sendo capturado silenciosamente**

**Sintoma:**
- `meta_purchase_sent` está sendo marcado (linha 7527)
- Mas `send_meta_pixel_purchase_event()` não está sendo chamado (ou está falhando silenciosamente)
- Logs não mostram "Enviando Purchase via Server"

**Possíveis Causas:**
- Exceção sendo capturada antes de chamar `send_meta_pixel_purchase_event()`
- Erro ao gerar `event_id_to_pass` (linha 7532)
- Erro ao chamar `send_meta_pixel_purchase_event()` que está sendo capturado no `except` (linha 7539)

**Verificação:**
```bash
tail -2000 logs/gunicorn.log | grep -iE "Erro ao enviar Purchase|Delivery.*erro|Purchase.*exception"
```

**Solução:**
- Verificar logs de erro ao enviar Purchase
- Verificar se há exceção sendo capturada silenciosamente

---

## 🔧 SCRIPT DE VERIFICAÇÃO

Execute o script `verificar_logs_delivery.sh`:

```bash
chmod +x verificar_logs_delivery.sh
bash verificar_logs_delivery.sh
```

O script verifica:
1. ✅ Se delivery está sendo acessado
2. ✅ Logs de Delivery
3. ✅ Se has_meta_pixel é True
4. ✅ Se meta_purchase_sent está sendo marcado
5. ✅ Se send_meta_pixel_purchase_event está sendo chamado
6. ✅ Erros ao enviar Purchase
7. ✅ Logs de Delivery para venda específica
8. ✅ Configuração do pool para essas vendas

---

## 📋 PRÓXIMOS PASSOS

1. ✅ **Execute o script** `verificar_logs_delivery.sh`
2. ✅ **Verifique configuração do pool** (seção 8 do script)
3. ✅ **Identifique qual causa está bloqueando** (has_meta_pixel, meta_purchase_sent, ou erro)
4. ✅ **Corrija o problema** (configuração do pool, resetar meta_purchase_sent, etc)
5. ✅ **Teste com uma nova venda** para confirmar correção

---

## ⚠️ NOTAS IMPORTANTES

1. **has_meta_pixel é verificado na linha 7448** e deve ser `True` para chamar `send_meta_pixel_purchase_event()`
2. **meta_purchase_sent é marcado ANTES de chamar** `send_meta_pixel_purchase_event()` (lock pessimista)
3. **Se meta_purchase_sent já está True**, `send_meta_pixel_purchase_event()` não será chamado novamente
4. **Se há erro ao chamar**, pode estar sendo capturado silenciosamente no `except` (linha 7539)

---

## ✅ STATUS

- ✅ Script de verificação criado
- ✅ Análise do código realizada
- ✅ Causas possíveis identificadas
- ⚠️ **Aguardando execução do script para identificar causa raiz específica**

