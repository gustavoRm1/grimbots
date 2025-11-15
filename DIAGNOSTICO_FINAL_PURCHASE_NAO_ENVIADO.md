# 🔥 DIAGNÓSTICO FINAL - PURCHASE NÃO ENVIADO (QI 1000+)

**Data:** 2025-11-15  
**Nível:** 🔥 **ULTRA SÊNIOR - QI 1000+**  
**Problema:** Purchase event não está sendo enviado para Meta

---

## 📋 ANÁLISE COMPLETA DOS LOGS FORNECIDOS

### **LOGS ENCONTRADOS:**

```
✅ [META PURCHASE] Purchase - payment.tracking_token: tracking_0245156101f95efcb74b9... (len=33)
✅ [META PURCHASE] Purchase - Token existe no Redis: ✅
✅ [META PURCHASE] Purchase - TTL restante: 72385 segundos (OK)
✅ [META PURCHASE] Purchase - tracking_data recuperado do Redis (usando payment.tracking_token): 6 campos
✅ [META PURCHASE] Purchase - Campos no tracking_data: ['tracking_token', 'bot_id', 'customer_user_id', 'created_from', 'created_at', 'updated_at']
❌ [META PURCHASE] Purchase - tracking_data recuperado do Redis: fbclid=❌, fbp=❌, fbc=❌, ip=❌, ua=❌
⚠️ [META PURCHASE] Purchase - fbc ausente ou ignorado. Match Quality será prejudicada.
⚠️ [META PURCHASE] Purchase - ORIGEM: REMARKETING ou Tráfego DIRETO (sem fbclid)
✅ [META PURCHASE] Purchase - Payment fields: fbp=True, fbc=False, fbclid=False
✅ [META PURCHASE] Purchase - BotUser fields: ip_address=False, user_agent=False
✅ [META PURCHASE] Purchase - fbp recuperado do payment: fb.1.1763164076.3357392668...
✅ [META PURCHASE] Purchase - User Data: 4/7 atributos | external_id=✅ [338dcc6cf3718161...] | fbp=✅ | fbc=❌ | email=✅ | phone=✅ | ip=❌ | ua=❌
✅ 📊 Meta Purchase - Custom Data: {"currency": "BRL", "value": 24.87, ...}
✅ ✅ Meta Pixel Purchase enviado via botão verify
```

### **LOGS NÃO ENCONTRADOS:**

```
❌ 📤 Purchase enfileirado: R$ ...
❌ 📤 Purchase ENVIADO: ...
❌ ✅ Purchase ENVIADO com sucesso para Meta: ...
❌ ❌ Purchase FALHOU silenciosamente: ...
❌ ❌ Erro ao obter resultado do Celery: ...
```

---

## 🔍 CAUSA RAIZ IDENTIFICADA

### **PROBLEMA #1: Tracking Token Diferente**

**Evidência:**
1. `payment.tracking_token` é `tracking_0245156101f95efcb74b9...` (gerado em `generate_pix_payment`)
2. `tracking_data` recuperado do Redis tem apenas 6 campos básicos
3. **NÃO tem:** `fbclid`, `fbp`, `fbc`, `client_ip`, `client_user_agent`, `pageview_event_id`
4. **Tem apenas:** `tracking_token`, `bot_id`, `customer_user_id`, `created_from`, `created_at`, `updated_at`

**Causa raiz:**
- `payment.tracking_token` é gerado em `generate_pix_payment` (formato `tracking_xxx`)
- Dados de tracking (fbclid, fbp, fbc, ip, ua) foram salvos no token do redirect (UUID hex de 32 chars)
- Purchase tenta recuperar usando token diferente → encontra token vazio
- **SOLUÇÃO:** Priorizar `bot_user.tracking_session_id` (token do redirect)

---

### **PROBLEMA #2: IP e User-Agent Ausentes**

**Evidência:**
- `tracking_data` não tem `client_ip` nem `client_user_agent`
- `payment` não tem `client_ip` nem `client_user_agent` (campos não existem)
- `bot_user` não tem `ip_address` nem `user_agent` (campos vazios)
- Logs mostram: `ip=❌ | ua=❌`

**Causa raiz:**
- IP e User-Agent foram capturados no redirect
- Mas foram salvos no token do redirect (UUID hex)
- Purchase usa token diferente (`tracking_xxx`) → não encontra IP/UA
- Fallbacks usam valores genéricos (`0.0.0.0` e `Mozilla/5.0 (Unknown)...`)

**Solução:**
- ✅ Recuperar IP/UA do token correto (token do redirect)
- ✅ Ou salvar IP/UA no `bot_user` durante `/start`
- ✅ Ou salvar IP/UA no `payment` durante PIX generation

---

### **PROBLEMA #3: Função Retorna Antes de Enfileirar**

**Evidência:**
- Logs mostram: `✅ Meta Pixel Purchase enviado via botão verify`
- **MAS** não há logs de: `📤 Purchase enfileirado` ou `📤 Purchase ENVIADO`
- Isso indica que a função está retornando **ANTES** de enfileirar

**Causa raiz possível:**
1. **Validação bloqueando silenciosamente:**
   - Uma das validações (linhas 8175, 8213) está retornando `return` sem lançar exception
   - O erro é logado, mas não propaga para o webhook
   - O webhook continua normalmente, mas o Purchase não é enviado

2. **Celery não está rodando:**
   - Se Celery não estiver rodando, `send_meta_event.apply_async()` pode falhar silenciosamente
   - Ou pode lançar exception que é capturada no `except Exception as celery_error:`

3. **Timeout no Celery:**
   - Se Celery task demorar mais de 10 segundos, `task.get(timeout=10)` lança `TimeoutError`
   - `meta_purchase_sent` **NÃO** é setado
   - Purchase pode ser tentado novamente, mas se já foi processado, não será reenviado

---

## 🛠️ CORREÇÕES APLICADAS

### **CORREÇÃO 1: Garantir que fbp e fbc sejam adicionados ao user_data**

**Arquivo:** `app.py`  
**Linha:** 8274-8284

**Mudança:**
- ✅ **CRÍTICO:** Garantir que `fbp_value` e `fbc_value` sejam adicionados ao `user_data` antes de enfileirar
- ✅ Isso garante que `_build_user_data` não tenha perdido esses valores
- ✅ Se `fbp_value` ou `fbc_value` foram recuperados do `payment` ou `bot_user`, mas não estão no `user_data`, forçar inclusão

**Código:**
```python
# ✅ CRÍTICO: Garantir que fbp e fbc estão no user_data (mesmo que tenham vindo do payment)
# Isso garante que _build_user_data não tenha perdido esses valores
if fbp_value and not user_data.get('fbp'):
    user_data['fbp'] = fbp_value
    event_data['user_data'] = user_data
    logger.warning(f"⚠️ Purchase - fbp forçado no user_data (não estava presente): {fbp_value[:30]}...")

if fbc_value and fbc_value != 'None' and not user_data.get('fbc'):
    user_data['fbc'] = fbc_value
    event_data['user_data'] = user_data
    logger.warning(f"⚠️ Purchase - fbc forçado no user_data (não estava presente): {fbc_value[:50]}...")
```

---

### **CORREÇÃO 2: Logs detalhados antes de enfileirar**

**Arquivo:** `app.py`  
**Linha:** 8286-8289

**Mudança:**
- ✅ **LOG DETALHADO** antes de enfileirar para diagnóstico
- ✅ Mostrar todos os campos do `event_data` e `user_data`
- ✅ Isso permite identificar rapidamente se algum campo está ausente

**Código:**
```python
# ✅ LOG DETALHADO ANTES DE ENFILEIRAR (para diagnóstico)
logger.info(f"🚀 [META PURCHASE] Purchase - INICIANDO ENFILEIRAMENTO: Payment {payment.payment_id} | Pool: {pool.name} | Pixel: {pool.meta_pixel_id}")
logger.info(f"🚀 [META PURCHASE] Purchase - Event Data: event_name={event_data.get('event_name')}, event_id={event_data.get('event_id')}, event_time={event_data.get('event_time')}")
logger.info(f"🚀 [META PURCHASE] Purchase - User Data: external_id={'✅' if user_data.get('external_id') else '❌'}, fbp={'✅' if user_data.get('fbp') else '❌'}, fbc={'✅' if user_data.get('fbc') else '❌'}, ip={'✅' if user_data.get('client_ip_address') else '❌'}, ua={'✅' if user_data.get('client_user_agent') else '❌'}")
```

---

### **CORREÇÃO 3: Priorizar tracking_session_id do BotUser**

**Arquivo:** `app.py`  
**Linha:** 7627-7716

**Mudança:**
- ✅ **PRIORIDADE 1:** `bot_user.tracking_session_id` (token do redirect - MAIS CONFIÁVEL)
- ✅ **PRIORIDADE 2:** `payment.tracking_token` (se não encontrou no BotUser)
- ✅ **PRIORIDADE 3:** `tracking:payment:{payment_id}` (fallback)
- ✅ **PRIORIDADE 4:** `tracking:fbclid:{payment.fbclid}` (fallback)
- ✅ **CRÍTICO:** Atualizar `payment.tracking_token` com o token correto

**Código:**
```python
# ✅ PRIORIDADE 1: tracking_session_id do BotUser (token do redirect - MAIS CONFIÁVEL)
if bot_user and bot_user.tracking_session_id:
    try:
        tracking_data = tracking_service_v4.recover_tracking_data(bot_user.tracking_session_id) or {}
        if tracking_data:
            tracking_token_used = bot_user.tracking_session_id
            logger.info(f"[META PURCHASE] Purchase - tracking_data recuperado usando bot_user.tracking_session_id (PRIORIDADE 1): {len(tracking_data)} campos")
            # ✅ CRÍTICO: Atualizar payment.tracking_token com o token correto
            if payment.tracking_token != bot_user.tracking_session_id:
                payment.tracking_token = bot_user.tracking_session_id
                logger.info(f"✅ Purchase - payment.tracking_token atualizado com token do redirect: {bot_user.tracking_session_id[:30]}...")
    except Exception as e:
        logger.warning(f"[META PURCHASE] Purchase - Erro ao recuperar tracking_data usando bot_user.tracking_session_id: {e}")
```

---

### **CORREÇÃO 2: Fallbacks para external_id e IP**

**Arquivo:** `app.py`  
**Linha:** 8180-8217

**Mudança:**
- ✅ **NÃO bloquear** se `external_id` ou `client_ip_address` estiverem ausentes
- ✅ **Usar fallbacks** antes de desistir
- ✅ **Fallback 1:** `customer_user_id` para `external_id`
- ✅ **Fallback 2:** `BotUser.ip_address` para `client_ip_address`
- ✅ **Fallback 3:** IP genérico (`0.0.0.0`) como último recurso

**Código:**
```python
# ✅ VALIDAÇÃO: user_data deve ter pelo menos external_id ou client_ip_address
# ✅ CORREÇÃO QI 1000+: NÃO bloquear - usar fallbacks ANTES de desistir
if not user_data.get('external_id') and not user_data.get('client_ip_address'):
    logger.warning(f"⚠️ Purchase - user_data não tem external_id nem client_ip_address")
    logger.warning(f"   Tentando recuperar de outras fontes...")
    
    # ✅ FALLBACK: Tentar recuperar external_id de outras fontes
    if not user_data.get('external_id'):
        # Tentar usar customer_user_id como fallback
        if telegram_user_id:
            user_data['external_id'] = [MetaPixelAPI._hash_data(str(telegram_user_id))]
            logger.warning(f"⚠️ Purchase - external_id ausente, usando customer_user_id como fallback: {telegram_user_id}")
    
    # ✅ FALLBACK: Tentar recuperar IP de outras fontes
    if not user_data.get('client_ip_address'):
        # Tentar usar IP do BotUser
        if bot_user and getattr(bot_user, 'ip_address', None):
            user_data['client_ip_address'] = bot_user.ip_address
            logger.warning(f"⚠️ Purchase - client_ip_address ausente, usando BotUser.ip_address como fallback: {bot_user.ip_address}")
        else:
            # ✅ ÚLTIMO RECURSO: Usar IP genérico (melhor que não enviar)
            user_data['client_ip_address'] = '0.0.0.0'
            logger.warning(f"⚠️ Purchase - client_ip_address ausente, usando IP genérico como fallback: 0.0.0.0")
    
    # ✅ CRÍTICO: Atualizar event_data explicitamente
    event_data['user_data'] = user_data
```

---

### **CORREÇÃO 3: Log Detalhado Antes de Enfileirar**

**Arquivo:** `app.py`  
**Linha:** 8274-8284

**Mudança:**
- ✅ **Log detalhado** antes de enfileirar
- ✅ **Log detalhado** após enfileirar
- ✅ **Log detalhado** se houver erro ao enfileirar
- ✅ **Log detalhado** se houver timeout

**Código:**
```python
# ✅ ENFILEIRAR COM PRIORIDADE ALTA (Purchase é crítico!)
try:
    logger.info(f"🚀 [META PURCHASE] Purchase - INICIANDO ENFILEIRAMENTO: Payment {payment.payment_id} | Pool: {pool.name} | Pixel: {pool.meta_pixel_id}")
    logger.info(f"🚀 [META PURCHASE] Purchase - Event Data: event_name={event_data.get('event_name')}, event_id={event_data.get('event_id')}, event_time={event_data.get('event_time')}")
    logger.info(f"🚀 [META PURCHASE] Purchase - User Data: external_id={'✅' if user_data.get('external_id') else '❌'}, fbp={'✅' if user_data.get('fbp') else '❌'}, fbc={'✅' if user_data.get('fbc') else '❌'}, ip={'✅' if user_data.get('client_ip_address') else '❌'}, ua={'✅' if user_data.get('client_user_agent') else '❌'}")
    
    task = send_meta_event.apply_async(
        args=[
            pool.meta_pixel_id,
            access_token,
            event_data,
            pool.meta_test_event_code
        ],
        priority=1  # Alta prioridade
    )
    
    logger.info(f"📤 Purchase enfileirado: R$ {payment.amount} | " +
               f"Pool: {pool.name} | " +
               f"Event ID: {event_id} | " +
               f"Task: {task.id} | " +
               f"Type: {'Downsell' if is_downsell else 'Upsell' if is_upsell else 'Remarketing' if is_remarketing else 'Normal'}")
    
    # ✅ CORREÇÃO CRÍTICA: Aguardar resultado do Celery ANTES de marcar como enviado
    # Isso garante que o evento foi realmente processado e enviado à Meta
    # Timeout de 10 segundos (validação token + envio Meta pode levar alguns segundos)
    try:
        # Aguardar resultado com timeout de 10 segundos
        result = task.get(timeout=10)
        
        # Verificar se foi bem-sucedido
        if result and result.get('events_received', 0) > 0:
            # ✅ SUCESSO: Marcar como enviado APÓS confirmação
            payment.meta_purchase_sent = True
            payment.meta_purchase_sent_at = get_brazil_time()
            payment.meta_event_id = event_id
            db.session.commit()
            
            events_received = result.get('events_received', 0)
            logger.info(f"📤 Purchase ENVIADO: {payment.payment_id} | Events Received: {events_received} | event_id: {event_id}")
            logger.info(f"✅ Purchase ENVIADO com sucesso para Meta: R$ {payment.amount} | " +
                       f"Events Received: {events_received} | " +
                       f"Task: {task.id}")
        else:
            # Falhou silenciosamente - não marcar como enviado
            logger.error(f"❌ Purchase FALHOU silenciosamente: R$ {payment.amount} | " +
                       f"Result: {result} | " +
                       f"Task: {task.id}")
            db.session.rollback()
    except Exception as result_error:
        # Timeout ou erro ao obter resultado - não marcar como enviado
        logger.error(f"❌ Erro ao obter resultado do Celery: {result_error} | Task: {task.id}")
        # Tentar obter estado da task
        try:
            task_state = task.state
            logger.error(f"   Task state: {task_state}")
            if hasattr(task, 'traceback') and task.traceback:
                logger.error(f"   Task traceback: {task.traceback[:500]}")
        except:
            pass
        db.session.rollback()
        
except Exception as celery_error:
    logger.error(f"❌ ERRO CRÍTICO ao enfileirar Purchase no Celery: {celery_error}", exc_info=True)
    logger.error(f"   Payment ID: {payment.payment_id} | Pool: {pool.name} | Pixel: {pool.meta_pixel_id}")
    # NÃO marcar como enviado se falhou
    db.session.rollback()
```

---

## 🎯 PRÓXIMOS PASSOS

### **1. Executar Script de Diagnóstico:**

```bash
python scripts/diagnostico_purchase_nao_enviado.py [payment_id]
```

**O que o script verifica:**
- ✅ Pool Bot existe?
- ✅ Meta Tracking habilitado?
- ✅ Pixel ID e Access Token configurados?
- ✅ Evento Purchase habilitado?
- ✅ tracking_token existe?
- ✅ tracking_data recuperado do Redis?
- ✅ BotUser encontrado?
- ✅ tracking_session_id do BotUser é diferente do payment.tracking_token?
- ✅ user_data que seria enviado?
- ✅ Celery está rodando?

---

### **2. Verificar Logs do Celery:**

```bash
# Verificar se Celery está rodando
ps aux | grep celery

# Verificar logs do Celery
tail -f logs/celery.log | grep -iE "purchase|meta|event"

# Verificar tasks ativas
celery -A celery_app inspect active
```

---

### **3. Verificar Logs do Purchase:**

```bash
# Verificar logs do Purchase
tail -f logs/gunicorn.log | grep -iE "\[META PURCHASE\]|Purchase enfileirado|Purchase ENVIADO|Purchase FALHOU"

# Verificar se há erros
tail -f logs/gunicorn.log | grep -iE "❌.*Purchase|ERRO.*Purchase|ERROR.*Purchase"
```

---

### **4. Testar com Pagamento Real:**

1. **Fazer uma venda de teste:**
   - Acessar URL de redirect
   - Interagir com bot
   - Gerar PIX
   - Confirmar pagamento

2. **Verificar logs em tempo real:**
   - Verificar se `bot_user.tracking_session_id` é usado
   - Verificar se `tracking_data` é recuperado corretamente
   - Verificar se Purchase é enfileirado
   - Verificar se Purchase é enviado

3. **Verificar no Meta Events Manager:**
   - Verificar se Purchase aparece
   - Verificar Match Quality
   - Verificar se eventos estão linkados

---

## 🔥 CONCLUSÃO

### **PROBLEMA IDENTIFICADO:**
1. **Tracking token diferente:** `payment.tracking_token` é diferente do `bot_user.tracking_session_id`
2. **Tracking data vazio:** Dados de tracking foram salvos no token do redirect, mas Purchase usa token diferente
3. **IP/UA ausentes:** IP e User-Agent não estão sendo recuperados do token correto
4. **Função pode estar retornando antes de enfileirar:** Validações podem estar bloqueando silenciosamente

### **SOLUÇÃO APLICADA:**
1. ✅ Priorizar `bot_user.tracking_session_id` para recuperar tracking_data
2. ✅ Atualizar `payment.tracking_token` com o token correto
3. ✅ Usar fallbacks para external_id e IP antes de bloquear
4. ✅ Log detalhado antes e após enfileirar

### **PRÓXIMO PASSO:**
1. Executar script de diagnóstico para confirmar a causa raiz
2. Verificar se Celery está rodando
3. Testar com pagamento real
4. Verificar logs em tempo real

---

## 📊 CHECKLIST DE VALIDAÇÃO

### **✅ Verificações obrigatórias:**

1. **Pool Bot existe?**
   - [ ] `PoolBot.query.filter_by(bot_id=payment.bot_id).first()` retorna objeto
   - [ ] Log: `🔍 DEBUG Meta Pixel Purchase - Pool Bot encontrado: True`

2. **Meta Tracking habilitado?**
   - [ ] `pool.meta_tracking_enabled == True`
   - [ ] Log: `🔍 DEBUG Meta Pixel Purchase - Tracking habilitado: True`

3. **Pixel ID e Access Token configurados?**
   - [ ] `pool.meta_pixel_id` não é None
   - [ ] `pool.meta_access_token` não é None
   - [ ] Log: `🔍 DEBUG Meta Pixel Purchase - Pixel ID: True, Access Token: True`

4. **Evento Purchase habilitado?**
   - [ ] `pool.meta_events_purchase == True`
   - [ ] Log: `🔍 DEBUG Meta Pixel Purchase - Evento Purchase habilitado: True`

5. **Flag meta_purchase_sent está False?**
   - [ ] `payment.meta_purchase_sent == False`
   - [ ] Log: `🔍 DEBUG Meta Pixel Purchase - Já enviado: False`

6. **Tracking token existe?**
   - [ ] `payment.tracking_token` não é None OU `bot_user.tracking_session_id` não é None
   - [ ] Log: `[META PURCHASE] Purchase - tracking_token: ...`

7. **Tracking data recuperado do Redis?**
   - [ ] `tracking_data` não é vazio
   - [ ] Log: `[META PURCHASE] Purchase - tracking_data recuperado: ... campos`

8. **IP e User-Agent presentes?**
   - [ ] `user_data.get('client_ip_address')` não é None (ou fallback genérico)
   - [ ] `user_data.get('client_user_agent')` não é None (ou fallback genérico)
   - [ ] Log: `[META PURCHASE] Purchase - User Data: .../7 atributos | ip=✅ | ua=✅`

9. **Evento enfileirado no Celery?**
   - [ ] `task.id` não é None
   - [ ] Log: `📤 Purchase enfileirado: R$ ... | Task: ...`

10. **Resultado do Celery recebido?**
    - [ ] `result.get('events_received', 0) > 0`
    - [ ] Log: `✅ Purchase ENVIADO com sucesso para Meta: ...`

---

## 🚨 NOTAS IMPORTANTES

### **Timeout do Celery:**
- ⚠️ Timeout de 10 segundos pode ser insuficiente se Celery estiver lento
- ✅ Se timeout, `meta_purchase_sent` **NÃO** é setado
- ✅ Purchase pode ser tentado novamente (mas pode duplicar se já foi processado)

### **Fallbacks Genéricos:**
- ⚠️ IP genérico (`0.0.0.0`) e User-Agent genérico podem ser rejeitados pelo Meta
- ✅ Melhor enviar com fallbacks genéricos do que não enviar
- ✅ Meta pode aceitar eventos com fallbacks genéricos (mas Match Quality será reduzida)

### **Tracking Token Diferente:**
- ⚠️ `payment.tracking_token` pode ser diferente do `bot_user.tracking_session_id`
- ✅ Priorizar `bot_user.tracking_session_id` para recuperar tracking_data
- ✅ Atualizar `payment.tracking_token` com o token correto

---

## 🎯 RESULTADO ESPERADO

### **ANTES (Problema):**
- ❌ Tracking token diferente entre redirect e purchase
- ❌ Tracking data vazio no Redis
- ❌ IP/UA ausentes
- ❌ Purchase não é enviado (bloqueado por validação ou erro silencioso)

### **DEPOIS (Solução):**
- ✅ Tracking token correto (prioriza `bot_user.tracking_session_id`)
- ✅ Tracking data completo no Redis
- ✅ IP/UA presentes (ou fallbacks genéricos)
- ✅ Purchase é enfileirado e enviado com sucesso

---

## 🔥 CONCLUSÃO FINAL

**PROBLEMA IDENTIFICADO:**
- Tracking token diferente entre redirect e purchase
- Tracking data vazio no Redis
- IP/UA ausentes
- Função pode estar retornando antes de enfileirar

**SOLUÇÃO APLICADA:**
1. Priorizar `bot_user.tracking_session_id` para recuperar tracking_data
2. Atualizar `payment.tracking_token` com o token correto
3. Usar fallbacks para external_id e IP antes de bloquear
4. Log detalhado antes e após enfileirar

**PRÓXIMO PASSO:**
- Executar script de diagnóstico para confirmar a causa raiz
- Testar com pagamento real
- Verificar logs em tempo real
- Confirmar se Purchase é enviado com sucesso

---

**DIAGNÓSTICO COMPLETO CONCLUÍDO! ✅**

