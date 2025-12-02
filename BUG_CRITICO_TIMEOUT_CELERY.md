# 🔥 BUG CRÍTICO IDENTIFICADO - TIMEOUT DO CELERY

## 🎯 LINHA EXATA QUE ESTÁ QUEBRANDO: LINHA 10627

### **PROBLEMA CRÍTICO:**

```python
# Linha 10627
result = task.get(timeout=10)
```

**O QUE ESTÁ ACONTECENDO:**

1. **Linha 10606:** Task é enfileirada no Celery com sucesso ✅
2. **Linha 10627:** Código aguarda resultado com timeout de 10 segundos ⏱️
3. **PROBLEMA:** Se o Celery worker estiver lento, ocupado ou não responder em 10s:
   - `task.get(timeout=10)` lança exceção `TimeoutError`
   - Código entra no `except Exception as timeout_error:` (linha 10662)
   - Faz rollback de `meta_purchase_sent = False` (linha 10679)
   - Retorna `False` (linha 10687)
   - **MAS A TASK CONTINUA SENDO PROCESSADA PELO CELERY EM BACKGROUND!**

4. **RESULTADO:**
   - Se Celery processar a task depois do timeout → Purchase é enviado ✅
   - Mas se Celery não processar (worker parado, erro, etc.) → Purchase nunca é enviado ❌
   - E o código já fez rollback, então próxima tentativa vai tentar enviar novamente

## 🔍 CAUSA RAIZ DO PROBLEMA DE HOJE

**HIPÓTESE #1: Celery Worker Não Está Rodando**
- Task é enfileirada mas nunca processada
- Timeout ocorre após 10s
- Rollback é feito
- Purchase nunca é enviado

**HIPÓTESE #2: Celery Worker Está Lento**
- Task é enfileirada
- Worker está ocupado processando outras tasks
- Timeout ocorre antes de processar
- Rollback é feito
- Task pode ser processada depois, mas pode haver duplicação

**HIPÓTESE #3: Verificação de Resultado Está Incorreta**
- Linha 10630: `if result and result.get('events_received', 0) > 0:`
- Se `result` for `None` ou `events_received` for `0`, entra no `else` (linha 10648)
- Faz rollback mesmo que task tenha sido processada

## 🔧 CORREÇÃO NECESSÁRIA

### **OPÇÃO 1: Não Aguardar Resultado (Fire and Forget)**
- Enfileirar task e retornar `True` imediatamente
- Confiar que Celery vai processar
- Não fazer rollback se timeout ocorrer

### **OPÇÃO 2: Aumentar Timeout e Verificar Estado da Task**
- Aumentar timeout para 30-60 segundos
- Verificar estado da task antes de fazer rollback
- Se task está `PENDING` ou `STARTED`, não fazer rollback

### **OPÇÃO 3: Verificar Se Task Foi Enfileirada (Não Aguardar Resultado)**
- Verificar se `task.id` existe (confirma que foi enfileirada)
- Retornar `True` se enfileirada com sucesso
- Não aguardar resultado (fire and forget)

## 🚨 DECISÃO: OPÇÃO 3 (MAIS ROBUSTA)

A correção mais robusta é **NÃO aguardar o resultado do Celery** na função `send_meta_pixel_purchase_event`. Em vez disso:

1. Enfileirar task
2. Verificar se foi enfileirada com sucesso (`task.id` existe)
3. Retornar `True` se enfileirada
4. Confiar que Celery vai processar em background
5. Se falhar, Celery tem retry automático

Isso evita:
- Timeouts bloqueando o fluxo
- Rollbacks prematuros
- Dependência de resposta síncrona do Celery

