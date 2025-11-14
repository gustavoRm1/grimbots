# ⚔️ DEBATE SÊNIOR - TRACKING_TOKEN DESVINCULADO (6 CAMPOS MAS TODOS VAZIOS)

**Data:** 2025-11-14  
**Problema Crítico:** Token existe no Redis com 6 campos, mas TODOS os campos importantes estão ausentes  
**Log Analisado:** Purchase com `tracking_token` diferente do redirect

---

## 📋 ANÁLISE DO LOG CRÍTICO

```
[META PURCHASE] Purchase - payment.tracking_token: tracking_bf83ba1dcdbf5007befd1... (len=33)
[META PURCHASE] Purchase - Token existe no Redis: ✅
[META PURCHASE] Purchase - TTL restante: 86220 segundos (OK)
[META PURCHASE] Purchase - tracking_data recuperado do Redis (usando payment.tracking_token): 6 campos
[META PURCHASE] Purchase - tracking_data recuperado do Redis: fbclid=❌, fbp=❌, fbc=❌, ip=❌, ua=❌
[META PURCHASE] Purchase - ORIGEM: REMARKETING ou Tráfego DIRETO (sem fbclid)
[META PURCHASE] Purchase - User Data: 2/7 atributos
```

**Observações Críticas:**
1. ✅ **Token existe no Redis:** TTL OK (86220 segundos = ~24 horas)
2. ✅ **6 campos recuperados:** Token tem dados no Redis
3. ❌ **TODOS os campos importantes ausentes:** fbclid, fbp, fbc, ip, ua = todos ❌
4. ⚠️ **Token diferente:** `tracking_bf83ba1dcdbf5007befd1...` (len=33) vs tokens do redirect (32 chars UUID)

---

## 🔍 COMPARAÇÃO: TOKENS DO REDIRECT vs TOKEN DO PAYMENT

### **Tokens do Redirect (PageView):**
```
tracking_token salvo: 30d7839aa9194e9ca324... (32 chars - UUID)
tracking_token salvo: 33cc3fcff3aa4397a7a1... (32 chars - UUID)
tracking_token salvo: 0da3616cd5da49b894bb... (32 chars - UUID)
```

**Formato:** UUID hexadecimal (32 caracteres)  
**Exemplo:** `30d7839aa9194e9ca324...`

### **Token do Payment (Purchase):**
```
payment.tracking_token: tracking_bf83ba1dcdbf5007befd1... (len=33)
```

**Formato:** `tracking_` + hash (33 caracteres)  
**Exemplo:** `tracking_bf83ba1dcdbf5007befd1...`

---

## ⚔️ DEBATE: POR QUE TOKEN É DIFERENTE?

### **HIPÓTESE 1: Token foi gerado novo em `_generate_pix_payment`**

**Posição A (Código Atual):**
- Se `bot_user.tracking_session_id` está vazio, novo token é gerado
- Novo token usa formato `tracking_` + hash
- Token gerado não tem dados no Redis (não foi salvo no redirect)

**Posição B (Problema Real):**
- Token do redirect é UUID (32 chars)
- Token do Payment é `tracking_` + hash (33 chars)
- **São tokens DIFERENTES!** O token do Payment não corresponde ao do redirect

**Veredito:**
- ❌ **CONFIRMADO:** Token do Payment é diferente do token do redirect
- ✅ **CAUSA:** Novo token foi gerado em `_generate_pix_payment()` porque `bot_user.tracking_session_id` estava vazio
- ⚠️ **PROBLEMA:** Token gerado tem 6 campos no Redis, mas todos estão vazios (por quê?)

---

### **HIPÓTESE 2: Token gerado tem dados vazios no Redis**

**Posição A (Código Atual):**
- Quando novo token é gerado, um `seed_payload` é criado
- `seed_payload` deve ter `fbclid`, `fbp`, etc.
- Dados são salvos no Redis com o novo token

**Posição B (Problema Real):**
- Token existe no Redis com 6 campos
- Mas TODOS os campos importantes estão ausentes
- **O que são esses 6 campos se não são fbclid, fbp, fbc, ip, ua?**

**Veredito:**
- ⚠️ **MISTÉRIO:** Token tem 6 campos, mas nenhum é útil
- ✅ **POSSÍVEL:** Campos são metadados (bot_id, customer_user_id, etc.) mas não dados de tracking
- ❌ **PROBLEMA:** Dados de tracking não foram salvos no token gerado

---

### **HIPÓTESE 3: `bot_user.tracking_session_id` não foi atualizado**

**Posição A (Código Atual):**
- `process_start_async` deve atualizar `bot_user.tracking_session_id` com o token do redirect
- Se atualizado, `_generate_pix_payment` usa o token do redirect
- Se não atualizado, novo token é gerado

**Posição B (Problema Real):**
- `bot_user.tracking_session_id` estava vazio quando `_generate_pix_payment` foi chamado
- Novo token foi gerado
- Token do redirect foi perdido

**Veredito:**
- ⚠️ **PROVÁVEL:** `process_start_async` não atualizou `bot_user.tracking_session_id`
- ✅ **CAUSA POSSÍVEL:** Usuário não veio do redirect (remarketing) ou `/start` não foi processado corretamente
- ❌ **PROBLEMA:** Token do redirect foi perdido

---

## 🔍 INVESTIGAÇÃO NECESSÁRIA

### **1. Verificar o que são os 6 campos no Redis**

**Adicionar log para mostrar TODOS os campos:**
```python
if tracking_data:
    logger.info(f"[META PURCHASE] Purchase - tracking_data completo: {list(tracking_data.keys())}")
    for key, value in tracking_data.items():
        logger.info(f"[META PURCHASE] Purchase - {key}: {value if value else 'None/Empty'}")
```

**Pergunta:** Quais são os 6 campos? São metadados ou dados de tracking?

---

### **2. Verificar se `bot_user.tracking_session_id` foi atualizado**

**Adicionar log em `process_start_async`:**
```python
logger.info(f"[PROCESS START] bot_user.tracking_session_id ANTES: {bot_user.tracking_session_id}")
logger.info(f"[PROCESS START] tracking_token recebido: {tracking_token}")
logger.info(f"[PROCESS START] bot_user.tracking_session_id DEPOIS: {bot_user.tracking_session_id}")
```

**Pergunta:** `bot_user.tracking_session_id` foi atualizado corretamente?

---

### **3. Verificar quando novo token é gerado**

**Adicionar log em `_generate_pix_payment`:**
```python
if not tracking_token:
    logger.warning(f"[GENERATE PIX] Gerando NOVO token - bot_user.tracking_session_id: {bot_user.tracking_session_id if bot_user else 'N/A'}")
    logger.warning(f"[GENERATE PIX] Token gerado: {tracking_token}")
    logger.warning(f"[GENERATE PIX] seed_payload: {seed_payload}")
```

**Pergunta:** Quando e por que novo token foi gerado?

---

## ✅ CONCLUSÕES DO DEBATE

### **PROBLEMA IDENTIFICADO:**

1. ❌ **Token Desvinculado:** `payment.tracking_token` não corresponde ao token do redirect
2. ❌ **Token Gerado Novo:** Formato diferente (`tracking_` + hash vs UUID)
3. ⚠️ **Dados Vazios:** Token tem 6 campos no Redis, mas todos importantes estão ausentes
4. ❌ **ORIGEM REMARKETING:** Usuário não veio do redirect (sem fbclid)

### **CAUSA RAIZ:**

**Cenário Mais Provável:**
1. Usuário veio de remarketing (sem `fbclid` no redirect)
2. Redirect criou token UUID e salvou no Redis (com fbclid, fbp, ip, ua)
3. Usuário clicou em `/start` mas `process_start_async` não atualizou `bot_user.tracking_session_id`
4. `_generate_pix_payment` não encontrou `bot_user.tracking_session_id`
5. Novo token foi gerado (`tracking_` + hash)
6. Novo token foi salvo no Redis com `seed_payload` (metadados, mas sem dados de tracking)
7. Purchase tenta recuperar dados do novo token, mas só encontra metadados vazios

**OU:**

1. Usuário veio de remarketing (sem `fbclid`)
2. Redirect criou token UUID, mas não salvou dados corretamente
3. `bot_user.tracking_session_id` não foi atualizado
4. Novo token foi gerado e salvo com dados vazios

### **SOLUÇÕES PROPOSTAS:**

1. ✅ **CRÍTICO: Logar TODOS os campos do tracking_data** para identificar o que são os 6 campos
2. ✅ **Verificar `process_start_async`** para garantir que `bot_user.tracking_session_id` é atualizado
3. ✅ **Melhorar `seed_payload`** para incluir dados de tracking quando novo token é gerado
4. ✅ **Adicionar fallback** para recuperar token do redirect mesmo quando novo token é gerado

---

## 🎯 PRÓXIMOS PASSOS

1. ✅ **CORREÇÃO APLICADA:** Logs detalhados para mostrar TODOS os campos do `tracking_data`
2. ✅ **CORREÇÃO APLICADA:** `seed_payload` agora inclui `fbp`, `fbc`, `ip`, `ua` do BotUser
3. ⚠️ **PENDENTE:** Verificar `process_start_async` para garantir atualização de `tracking_session_id`
4. ⚠️ **PENDENTE:** Melhorar recuperação para tentar encontrar token do redirect mesmo quando novo token é gerado

---

## ✅ CORREÇÕES APLICADAS

### **1. Logs Detalhados do tracking_data**

**Arquivo:** `app.py` (linhas 7446-7452)  
**Mudança:**
```python
# ✅ LOG CRÍTICO: Mostrar TODOS os campos para identificar o problema
logger.info(f"[META PURCHASE] Purchase - Campos no tracking_data: {list(tracking_data.keys())}")
for key, value in tracking_data.items():
    if value:
        logger.info(f"[META PURCHASE] Purchase - {key}: {str(value)[:50]}...")
    else:
        logger.warning(f"[META PURCHASE] Purchase - {key}: None/Empty")
```

**Resultado:** Logs agora mostram exatamente quais campos existem e seus valores.

---

### **2. seed_payload Inclui Dados de Tracking**

**Arquivo:** `bot_manager.py` (linhas 4525-4538)  
**Mudança:**
```python
# ✅ CRÍTICO: Incluir fbp, fbc, ip, ua do BotUser no seed_payload
fbp_from_botuser = getattr(bot_user, 'fbp', None) if bot_user else None
fbc_from_botuser = getattr(bot_user, 'fbc', None) if bot_user else None
ip_from_botuser = getattr(bot_user, 'ip_address', None) if bot_user else None
ua_from_botuser = getattr(bot_user, 'user_agent', None) if bot_user else None

seed_payload = {
    # ... campos existentes ...
    "fbp": fbp_from_botuser,  # ✅ CRÍTICO: Incluir fbp do BotUser
    "fbc": fbc_from_botuser,  # ✅ CRÍTICO: Incluir fbc do BotUser
    "client_ip": ip_from_botuser,  # ✅ CRÍTICO: Incluir IP do BotUser
    "client_user_agent": ua_from_botuser,  # ✅ CRÍTICO: Incluir UA do BotUser
    # ...
}
```

**Resultado:** Quando novo token é gerado, dados de tracking do BotUser são incluídos no Redis.

---

**DEBATE CONCLUÍDO E CORREÇÕES APLICADAS! ✅**

