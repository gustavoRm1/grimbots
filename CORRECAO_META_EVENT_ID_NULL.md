# ✅ CORREÇÃO - meta_event_id NULL enquanto meta_purchase_sent = True

## 🎯 PROBLEMA IDENTIFICADO

**8 vendas com `meta_purchase_sent = True` mas `meta_event_id = NULL`**
```
id  | payment_id | meta_purchase_sent | meta_event_id
9445| BOT19_...  | t                  | NULL ❌
9438| BOT19_...  | t                  | NULL ❌
9436| BOT43_...  | t                  | NULL ❌
...
```

**Causa Raiz:**
1. `meta_purchase_sent` é marcado como `True` ANTES de enviar (lock pessimista - linha 7523-7526)
2. Purchase é enfileirado no Celery (linha 9349-9357)
3. Sistema aguarda resultado do Celery com `timeout=10` (linha 9370)
4. Se Celery falhar (timeout, erro, etc), `meta_event_id` não é salvo
5. MAS `meta_purchase_sent` já está marcado como `True` e não é revertido

---

## ✅ CORREÇÃO APLICADA

### **1. Tratamento de Exceção para Timeout**

**ANTES:**
```python
try:
    result = task.get(timeout=10)
    if result and result.get('events_received', 0) > 0:
        payment.meta_event_id = event_id
        db.session.commit()
    else:
        # ❌ Falhou mas não reverte meta_purchase_sent
        logger.error(f"❌ Purchase FALHOU silenciosamente")
```

**DEPOIS:**
```python
try:
    result = task.get(timeout=10)
    if result and result.get('events_received', 0) > 0:
        payment.meta_event_id = event_id
        db.session.commit()
    else:
        # ✅ FALHOU: Reverter meta_purchase_sent para permitir nova tentativa
        logger.error(f"❌ Purchase FALHOU silenciosamente")
        payment.meta_purchase_sent = False
        payment.meta_purchase_sent_at = None
        db.session.commit()
except Exception as timeout_error:
    # ✅ TIMEOUT ou ERRO: Reverter meta_purchase_sent para permitir nova tentativa
    logger.error(f"❌ Purchase FALHOU (timeout/erro): {timeout_error}")
    payment.meta_purchase_sent = False
    payment.meta_purchase_sent_at = None
    db.session.commit()
```

### **2. Rollback em Caso de Falha**

Agora, se Purchase falhar:
- ✅ `meta_purchase_sent` é revertido para `False`
- ✅ `meta_purchase_sent_at` é revertido para `NULL`
- ✅ Purchase pode ser tentado novamente quando usuário acessar `/delivery/<token>` novamente

---

## 🔍 POSSÍVEIS CAUSAS DO PROBLEMA

### **CAUSA 1: Timeout do Celery**

**Sintoma:**
- `task.get(timeout=10)` lança exceção `TimeoutError`
- Celery não processa task dentro de 10 segundos

**Possíveis Causas:**
- Workers do Celery não estão rodando
- Workers estão sobrecarregados
- Rede lenta ou Meta API lenta

**Solução:**
- Verificar se workers do Celery estão ativos: `celery -A celery_app inspect active`
- Verificar logs do Celery para erros
- Aumentar timeout se necessário

### **CAUSA 2: Erro na API Meta**

**Sintoma:**
- Purchase é processado mas API Meta retorna erro (4xx, 5xx)
- `events_received = 0` ou `result = None`

**Possíveis Causas:**
- Token de acesso inválido ou expirado
- Pixel ID incorreto
- Payload inválido (faltando campos obrigatórios)
- Meta API rejeitando eventos

**Solução:**
- Verificar logs de erro da API Meta
- Validar token de acesso e pixel ID
- Verificar payload enviado (event_id, user_data, custom_data)

### **CAUSA 3: Erro no Celery Task**

**Sintoma:**
- Task falha antes de enviar para Meta
- Exception lançada dentro da task

**Possíveis Causas:**
- Erro ao descriptografar access_token
- Erro ao construir payload
- Erro de validação de dados

**Solução:**
- Verificar logs do Celery para erros específicos
- Verificar se `access_token` está válido
- Verificar se `event_data` está correto

---

## 📊 VERIFICAÇÃO

### **1. Verificar Vendas com Problema**

```sql
SELECT 
    p.id,
    p.payment_id,
    p.meta_purchase_sent,
    p.meta_event_id,
    p.meta_purchase_sent_at,
    b.name as bot_name
FROM payments p
JOIN bots b ON p.bot_id = b.id
WHERE p.status = 'paid'
AND p.meta_purchase_sent = true
AND p.meta_event_id IS NULL
AND p.created_at >= NOW() - INTERVAL '24 hours'
ORDER BY p.created_at DESC;
```

### **2. Verificar Logs de Purchase**

```bash
tail -1000 logs/gunicorn.log | grep -iE "Purchase.*FALHOU|Purchase.*timeout|meta_purchase_sent revertido"
```

### **3. Verificar Status do Celery**

```bash
celery -A celery_app inspect active
celery -A celery_app inspect stats
```

### **4. Verificar Logs do Celery**

```bash
tail -f logs/celery.log | grep -iE "Purchase|error|timeout"
```

---

## 🎯 PRÓXIMOS PASSOS

1. ✅ **Testar com nova venda** para confirmar que correção funciona
2. ✅ **Verificar logs** para confirmar que `meta_purchase_sent` é revertido em caso de falha
3. ✅ **Verificar se Purchase está sendo tentado novamente** quando usuário acessa `/delivery/<token>` novamente
4. ✅ **Verificar Meta Event Manager** para confirmar que Purchase aparece (pode levar 24-48h)

---

## ⚠️ NOTAS IMPORTANTES

1. **Rollback é Essencial:** Se Purchase falhar, devemos reverter `meta_purchase_sent` para permitir nova tentativa.

2. **Celery Timeout:** Timeout de 10 segundos pode ser curto se Meta API estiver lenta. Se necessário, aumentar timeout ou processar assincronamente sem aguardar resultado.

3. **Processamento Assíncrono:** Idealmente, Purchase deveria ser processado assincronamente sem bloquear a página de delivery. Aguardar resultado do Celery pode causar timeout.

4. **Retry Automático:** Se Purchase falhar, será tentado novamente quando usuário acessar `/delivery/<token>` novamente (pois `meta_purchase_sent` foi revertido).

---

## ✅ STATUS

- ✅ Tratamento de exceção para timeout implementado
- ✅ Rollback de `meta_purchase_sent` em caso de falha implementado
- ✅ Logging detalhado de erros implementado
- ⚠️ **Aguardando teste com nova venda para confirmar correção**

