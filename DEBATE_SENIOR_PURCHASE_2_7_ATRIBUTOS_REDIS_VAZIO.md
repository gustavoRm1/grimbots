# ⚔️ DEBATE SÊNIOR - PURCHASE COM REDIS VAZIO (2/7 ATRIBUTOS)

**Data:** 2025-11-14  
**Log Analisado:** Purchase event com `tracking_data` vazio do Redis  
**Problema:** Apenas 2/7 atributos (external_id + fbp), todos os outros ausentes

---

## 📋 ANÁLISE DO LOG

```
[META PURCHASE] Purchase - tracking_data recuperado do Redis: fbclid=❌, fbp=❌, fbc=❌, ip=❌, ua=❌
[META PURCHASE] Purchase - tracking_data recuperado: fbp=❌, fbc=❌, fbclid=❌
[META PURCHASE] Purchase - fbp recuperado do payment: fb.1.1763134459.2147734365...
[META PURCHASE] Purchase - User Data: 2/7 atributos | external_id=✅ | fbp=✅ | fbc=❌ | email=❌ | phone=❌ | ip=❌ | ua=❌
```

**Observações:**
1. ❌ **Redis vazio:** Nenhum dado foi recuperado do Redis usando `payment.tracking_token`
2. ✅ **FBP recuperado:** Apenas do Payment (fallback final)
3. ❌ **IP e UA ausentes:** Nem no Redis, nem no Payment
4. ✅ **External_id presente:** Provavelmente gerado do `payment.fbclid` ou `payment.customer_user_id`

---

## 🔍 FLUXO DE RECUPERAÇÃO (Código Atual)

### **Prioridade 1: `payment.tracking_token` → Redis**

```7423:7427:app.py
        if getattr(payment, "tracking_token", None):
            try:
                tracking_data = tracking_service_v4.recover_tracking_data(payment.tracking_token) or {}
            except Exception:
                logger.exception("Erro recovering tracking token")
```

**Resultado no log:** `tracking_data` vazio ❌

**Possíveis causas:**
1. `payment.tracking_token` é `None` ou vazio
2. `payment.tracking_token` existe mas não há dados no Redis (expirou ou nunca foi salvo)
3. `payment.tracking_token` não corresponde ao token salvo no redirect

---

### **Prioridade 2: `tracking:payment:{payment_id}` → Redis**

```7429:7435:app.py
        if not tracking_data:
            try:
                raw = tracking_service_v4.redis.get(f"tracking:payment:{payment.payment_id}")
                if raw:
                    tracking_data = json.loads(raw)
            except Exception:
                pass
```

**Resultado no log:** Não mencionado (provavelmente também vazio)

**Possíveis causas:**
1. Chave `tracking:payment:{payment_id}` nunca foi criada
2. Chave expirou no Redis
3. `payment.payment_id` não corresponde

---

### **Prioridade 3: `tracking:fbclid:{fbclid}` → Redis**

```7437:7443:app.py
        if not tracking_data and getattr(payment, "fbclid", None):
            try:
                token = tracking_service_v4.redis.get(f"tracking:fbclid:{payment.fbclid}")
                if token:
                    tracking_data = tracking_service_v4.recover_tracking_data(token) or {}
            except Exception:
                pass
```

**Resultado no log:** Não mencionado (provavelmente também vazio)

**Possíveis causas:**
1. `payment.fbclid` é `None` ou vazio
2. Chave `tracking:fbclid:{fbclid}` nunca foi criada
3. Chave expirou no Redis

---

### **Prioridade 4: Fallback do Payment**

```7445:7457:app.py
        if not tracking_data:
            tracking_data = {
                "fbp": getattr(payment, "fbp", None),
                "fbc": getattr(payment, "fbc", None),
                "fbclid": getattr(payment, "fbclid", None),
                "client_ip": getattr(payment, "client_ip", None),
                "client_user_agent": getattr(payment, "client_user_agent", None),
                "pageview_ts": getattr(payment, "pageview_ts", None),
                "pageview_event_id": getattr(payment, "pageview_event_id", None),
            }
```

**Resultado no log:** Apenas `fbp` foi recuperado ✅

**Problema:** `client_ip` e `client_user_agent` não estão no Payment!

---

## ⚔️ DEBATE: POR QUE REDIS ESTÁ VAZIO?

### **HIPÓTESE 1: `tracking_token` não foi salvo no Payment**

**Posição A (Código Atual):**
- `tracking_token` é salvo no Payment em `_generate_pix_payment()` (linha 4734)
- Deve estar presente se o usuário veio do redirect

**Posição B (Problema Real):**
- Se o usuário NÃO veio do redirect (remarketing, tráfego direto), `tracking_token` pode ser gerado novo
- Novo `tracking_token` não tem dados no Redis (não foi salvo no redirect)

**Veredito:**
- ⚠️ **PROVÁVEL:** Usuário pode ter vindo de remarketing ou tráfego direto
- ✅ **CONFIRMAÇÃO NECESSÁRIA:** Verificar se `payment.tracking_token` existe e qual é o valor

---

### **HIPÓTESE 2: `tracking_token` existe mas Redis expirou**

**Posição A (Código Atual):**
- TTL padrão: `TRACKING_TOKEN_TTL` (provavelmente 7 dias)
- Dados devem estar disponíveis por tempo suficiente

**Posição B (Problema Real):**
- Se o usuário demorou muito entre redirect e pagamento, Redis pode ter expirado
- TTL pode estar configurado muito curto

**Veredito:**
- ⚠️ **POSSÍVEL:** Mas improvável se TTL é 7 dias
- ✅ **CONFIRMAÇÃO NECESSÁRIA:** Verificar TTL configurado e tempo entre redirect e pagamento

---

### **HIPÓTESE 3: `tracking_token` do Payment não corresponde ao do Redis**

**Posição A (Código Atual):**
- `tracking_token` é salvo no `public_redirect` e depois usado no `/start`
- `bot_user.tracking_session_id` é atualizado no `process_start_async`
- `payment.tracking_token` vem de `bot_user.tracking_session_id` ou é gerado novo

**Posição B (Problema Real):**
- Se `bot_user.tracking_session_id` não foi atualizado corretamente, `payment.tracking_token` pode ser diferente
- Se novo token foi gerado em `_generate_pix_payment()`, não terá dados no Redis

**Veredito:**
- ⚠️ **MUITO PROVÁVEL:** Novo token gerado não tem dados no Redis
- ✅ **CONFIRMAÇÃO NECESSÁRIA:** Verificar logs de `_generate_pix_payment` para ver se token foi gerado novo

---

### **HIPÓTESE 4: IP e UA não foram salvos no Payment**

**Posição A (Código Atual):**
- `client_ip` e `client_user_agent` devem ser salvos no Payment em `_generate_pix_payment()`
- Mas o código atual não mostra isso claramente

**Posição B (Problema Real):**
- ❌ **CONFIRMADO:** `Payment` model **NÃO TEM** campos `client_ip` e `client_user_agent`!
- ✅ **VERIFICAÇÃO:** Payment model tem apenas `fbp`, `fbc`, `tracking_token`, `pageview_event_id`
- ✅ **DESCOBERTA:** `BotUser` tem `ip_address` e `user_agent`, mas `Payment` não!

**Veredito:**
- ❌ **CRÍTICO CONFIRMADO:** Payment não tem esses campos, então fallback nunca funcionará
- ✅ **SOLUÇÃO:** Recuperar IP e UA do `BotUser` ou adicionar campos ao Payment

---

## 🔍 INVESTIGAÇÃO NECESSÁRIA

### **1. Verificar `payment.tracking_token`**

```python
# Adicionar log antes de recuperar do Redis
logger.info(f"[META PURCHASE] Purchase - payment.tracking_token: {payment.tracking_token}")
logger.info(f"[META PURCHASE] Purchase - payment.tracking_token existe: {bool(payment.tracking_token)}")
```

**Pergunta:** O token existe? Qual é o valor?

---

### **2. Verificar se token existe no Redis**

```python
# Adicionar verificação direta
if payment.tracking_token:
    exists = tracking_service_v4.redis.exists(f"tracking:{payment.tracking_token}")
    logger.info(f"[META PURCHASE] Purchase - Token existe no Redis: {exists}")
    if exists:
        ttl = tracking_service_v4.redis.ttl(f"tracking:{payment.tracking_token}")
        logger.info(f"[META PURCHASE] Purchase - TTL restante: {ttl} segundos")
```

**Pergunta:** O token existe no Redis? Qual é o TTL?

---

### **3. Verificar campos do Payment**

```python
# Adicionar log dos campos do Payment
logger.info(f"[META PURCHASE] Purchase - Payment fields: fbp={bool(payment.fbp)}, fbc={bool(payment.fbc)}, fbclid={bool(payment.fbclid)}, client_ip={bool(getattr(payment, 'client_ip', None))}, client_user_agent={bool(getattr(payment, 'client_user_agent', None))}")
```

**Pergunta:** Quais campos existem no Payment?

---

### **4. Verificar origem do usuário**

```python
# Adicionar log para identificar se veio do redirect
if payment.fbclid:
    logger.info(f"[META PURCHASE] Purchase - ORIGEM: Campanha NOVA (fbclid presente)")
else:
    logger.warning(f"[META PURCHASE] Purchase - ORIGEM: REMARKETING ou Tráfego DIRETO (sem fbclid)")
```

**Pergunta:** O usuário veio de campanha nova ou remarketing?

---

## ✅ CONCLUSÕES DO DEBATE

### **PROBLEMA IDENTIFICADO:**

1. ❌ **Redis vazio:** `tracking_token` do Payment não encontrou dados no Redis
2. ❌ **Fallbacks falharam:** `tracking:payment` e `tracking:fbclid` também vazios
3. ⚠️ **FBP recuperado:** Apenas do Payment (fallback final funcionou parcialmente)
4. ❌ **IP e UA ausentes:** Nem no Redis, nem no Payment

### **CAUSA MAIS PROVÁVEL:**

**Cenário 1: Usuário de Remarketing (Sem fbclid)**
- Usuário não veio do redirect (sem `fbclid`)
- Novo `tracking_token` foi gerado em `_generate_pix_payment()`
- Novo token não tem dados no Redis (não foi salvo no redirect)
- Payment não tem `client_ip` e `client_user_agent` (não foram capturados)

**Cenário 2: Token Desvinculado**
- `payment.tracking_token` existe mas não corresponde ao token do redirect
- Token do redirect expirou ou foi sobrescrito
- Payment não tem `client_ip` e `client_user_agent`

### **SOLUÇÕES PROPOSTAS:**

1. ✅ **CRÍTICO: Recuperar IP e UA do BotUser** (campos existem: `ip_address` e `user_agent`)
2. **Adicionar logs detalhados** para rastrear `tracking_token` e campos do Payment
3. ❌ **NÃO POSSÍVEL:** Payment não tem campos `client_ip` e `client_user_agent` (requer migration)
4. ✅ **SOLUÇÃO IMEDIATA:** Usar `bot_user.ip_address` e `bot_user.user_agent` no fallback

---

## 🎯 PRÓXIMOS PASSOS

1. ✅ **CORREÇÃO APLICADA:** Fallback para recuperar IP e UA do BotUser
2. ✅ **CORREÇÃO APLICADA:** Logs detalhados para rastrear `tracking_token` e campos
3. ✅ **VERIFICAÇÃO CONCLUÍDA:** Payment não tem campos `client_ip` e `client_user_agent`
4. ✅ **SOLUÇÃO IMPLEMENTADA:** Usar `bot_user.ip_address` e `bot_user.user_agent` no fallback

---

## ✅ CORREÇÕES APLICADAS

### **1. Fallback para BotUser (IP e UA)**

**Arquivo:** `app.py` (linhas 7521-7527)  
**Mudança:**
```python
# ✅ FALLBACK CRÍTICO: Recuperar IP e UA do BotUser (campos existem: ip_address e user_agent)
if not ip_value and bot_user and getattr(bot_user, 'ip_address', None):
    ip_value = bot_user.ip_address
    logger.info(f"[META PURCHASE] Purchase - IP recuperado do BotUser (fallback): {ip_value}")
if not user_agent_value and bot_user and getattr(bot_user, 'user_agent', None):
    user_agent_value = bot_user.user_agent
    logger.info(f"[META PURCHASE] Purchase - User Agent recuperado do BotUser (fallback): {user_agent_value[:50]}...")
```

**Resultado:** Purchase agora recupera IP e UA do BotUser quando Redis está vazio.

---

### **2. Logs Detalhados**

**Arquivo:** `app.py` (linhas 7422-7435, 7513-7527)  
**Mudanças:**
- Log mostrando `payment.tracking_token` e se existe no Redis
- Log mostrando TTL restante do token
- Log mostrando origem (Campanha NOVA vs REMARKETING)
- Log mostrando campos do Payment e BotUser

**Resultado:** Logs agora mostram exatamente onde os dados estão sendo recuperados.

---

**DEBATE CONCLUÍDO E CORREÇÕES APLICADAS! ✅**

