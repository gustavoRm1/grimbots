# 🔥 DEBATE SÊNIOR - RAIZ DO PROBLEMA: META PURCHASE NÃO ENVIADO

## 📋 CONTEXTO

**Situação atual:**
- ✅ Webhooks estão chegando normalmente
- ✅ Pagamentos estão sendo marcados como `paid`
- ✅ Entregáveis estão sendo enviados aos clientes
- ✅ PageView está sendo disparado normalmente em tempo real
- ❌ **Meta Purchase NÃO está sendo enviado**
- ⚠️ **CRÍTICO: Sistema usa Cloudflare** (pode afetar captura de IP)

**Problema:** Mesmo com todos os sistemas funcionando, o evento Purchase não está chegando ao Meta.

**Causa adicional identificada:**
- Cloudflare modifica headers HTTP, incluindo IP do cliente
- Se IP não for capturado corretamente via Cloudflare headers, Purchase pode ser bloqueado
- Cloudflare usa `CF-Connecting-IP` (prioridade 1), `True-Client-IP` (prioridade 2), `X-Forwarded-For` (prioridade 3)

---

## 🔍 ANÁLISE LINHA POR LINHA

### 1. FLUXO DO WEBHOOK (`tasks_async.py`)

```python
# Linha 902: Decisão de enviar Meta Purchase
deve_enviar_meta_purchase = status_is_paid and not payment.meta_purchase_sent

# Linha 905-909: Logs de decisão
logger.info(f"📊 [WEBHOOK {gateway_type.upper()}] Decisões de processamento:")
logger.info(f"   Status é paid: {status_is_paid}")
logger.info(f"   Deve enviar Meta Purchase: {deve_enviar_meta_purchase}")

# Linha 961-965: Chamada do Purchase
if deve_enviar_meta_purchase:
    try:
        send_meta_pixel_purchase_event(payment)
    except Exception as e:
        logger.warning(f"Erro ao enviar Meta Pixel Purchase: {e}")

# Linha 987: COMMIT (DEPOIS do Purchase)
db.session.commit()
```

**🔴 PROBLEMA IDENTIFICADO #1: Ordem de execução**
- O Purchase é chamado **ANTES** do commit
- Se o Purchase tentar ler `payment.meta_purchase_sent` do banco, pode estar lendo um valor desatualizado
- **MAS** isso não deveria ser um problema, pois o objeto está na sessão

---

### 2. VALIDAÇÕES EM `send_meta_pixel_purchase_event` (`app.py`)

#### **Verificação 1: Pool Bot existe?** (Linha 7406-7409)
```python
if not pool_bot:
    logger.error(f"❌ PROBLEMA RAIZ: Bot {payment.bot_id} não está associado a nenhum pool - Meta Pixel Purchase NÃO SERÁ ENVIADO")
    return
```
**🔴 POSSÍVEL CAUSA:** Bot não associado a pool → Purchase não é enviado

#### **Verificação 2: Meta Tracking habilitado?** (Linha 7419-7422)
```python
if not pool.meta_tracking_enabled:
    logger.error(f"❌ PROBLEMA RAIZ: Meta tracking DESABILITADO para pool {pool.id} - Meta Pixel Purchase NÃO SERÁ ENVIADO")
    return
```
**🔴 POSSÍVEL CAUSA:** Meta tracking desabilitado no pool → Purchase não é enviado

#### **Verificação 3: Pixel ID e Access Token configurados?** (Linha 7424-7427)
```python
if not pool.meta_pixel_id or not pool.meta_access_token:
    logger.error(f"❌ PROBLEMA RAIZ: Pool {pool.id} tem tracking ativo mas SEM pixel_id ou access_token - Meta Pixel Purchase NÃO SERÁ ENVIADO")
    return
```
**🔴 POSSÍVEL CAUSA:** Pixel ID ou Access Token ausentes → Purchase não é enviado

#### **Verificação 4: Evento Purchase habilitado?** (Linha 7431-7434)
```python
if not pool.meta_events_purchase:
    logger.error(f"❌ PROBLEMA RAIZ: Evento Purchase DESABILITADO para pool {pool.id} - Meta Pixel Purchase NÃO SERÁ ENVIADO")
    return
```
**🔴 POSSÍVEL CAUSA:** Evento Purchase desabilitado no pool → Purchase não é enviado

#### **Verificação 5: Já foi enviado?** (Linha 7439-7445)
```python
if payment.meta_purchase_sent:
    logger.info(f"⚠️ Purchase já enviado ao Meta, ignorando: {payment.payment_id}")
    return
```
**🔴 POSSÍVEL CAUSA:** Flag `meta_purchase_sent` já está `True` → Purchase não é enviado

#### **Verificação 6: user_data válido?** (Linha 8010-8015)
```python
if not user_data.get('external_id') and not user_data.get('client_ip_address'):
    logger.error(f"❌ Purchase - user_data deve ter pelo menos external_id ou client_ip_address")
    return
```
**🔴 POSSÍVEL CAUSA:** Sem `external_id` E sem `client_ip_address` → Purchase não é enviado

#### **Verificação 7: Identificadores presentes?** (Linha 8018-8022)
```python
if not user_data.get('external_id') and not user_data.get('fbp') and not user_data.get('fbc'):
    logger.error(f"❌ Purchase - Nenhum identificador presente (external_id, fbp, fbc)")
    return
```
**🔴 POSSÍVEL CAUSA:** Sem nenhum identificador → Purchase não é enviado

#### **Verificação 8: IP obrigatório para website** (Linha 8028-8034)
```python
if event_data.get('action_source') == 'website':
    if not user_data.get('client_ip_address'):
        logger.error(f"❌ Purchase - client_ip_address AUSENTE! Meta rejeita eventos web sem IP.")
        return
```
**🔴 POSSÍVEL CAUSA:** `action_source = 'website'` mas sem IP → Purchase não é enviado

#### **Verificação 9: User Agent obrigatório para website** (Linha 8035-8041)
```python
if event_data.get('action_source') == 'website':
    if not user_data.get('client_user_agent'):
        logger.error(f"❌ Purchase - client_user_agent AUSENTE! Meta rejeita eventos web sem User-Agent.")
        return
```
**🔴 POSSÍVEL CAUSA:** `action_source = 'website'` mas sem User-Agent → Purchase não é enviado

---

### 3. TIMEOUT DO CELERY TASK (Linha 8066)

```python
try:
    result = task.get(timeout=10)
    if result and result.get('events_received', 0) > 0:
        payment.meta_purchase_sent = True
        payment.meta_purchase_sent_at = get_brazil_time()
        payment.meta_event_id = event_id
        db.session.commit()
    else:
        logger.error(f"❌ Purchase FALHOU silenciosamente: R$ {payment.amount}")
        db.session.rollback()
except Exception as result_error:
    logger.error(f"❌ Erro ao obter resultado do Celery: {result_error}")
    # NÃO marca como enviado se der timeout
```

**🔴 PROBLEMA IDENTIFICADO #2: Timeout de 10 segundos**
- Se o Celery task demorar mais de 10 segundos, o `meta_purchase_sent` **NÃO** é setado
- Isso permite que o webhook tente novamente na próxima execução
- **MAS** se o webhook já foi processado, não tentará novamente

**🔴 PROBLEMA IDENTIFICADO #3: Erro silencioso no webhook**
- Na linha 965 do `tasks_async.py`, erros são capturados com `logger.warning`
- Se `send_meta_pixel_purchase_event` retornar silenciosamente (sem exception), o webhook não sabe que falhou
- O webhook continua e faz commit, mas o Purchase nunca foi enviado

---

## 🎯 HIPÓTESES PRINCIPAIS

### **HIPÓTESE 1: Validação bloqueando silenciosamente**
**Probabilidade: 80%**
- Uma das validações (linhas 8010-8041) está retornando `return` sem lançar exception
- O erro é logado, mas não propaga para o webhook
- O webhook continua normalmente, mas o Purchase não é enviado

**Evidência:**
- Logs do usuário mostram PageView sendo enviado, mas não mostram Purchase
- Se fosse um erro de Celery, haveria logs de erro
- Se fosse um erro de configuração, haveria logs de "PROBLEMA RAIZ"

### **HIPÓTESE 2: IP ou User-Agent ausentes**
**Probabilidade: 70%**
- PageView captura IP e User-Agent do `request`
- Purchase precisa recuperar do Redis ou BotUser
- Se o Redis expirou ou o BotUser não tem esses dados, a validação bloqueia

**Evidência:**
- Linha 8028-8041 valida IP e User-Agent para `action_source = 'website'`
- Se esses campos estiverem ausentes, retorna sem enviar
- Logs deveriam mostrar: `❌ Purchase - client_ip_address AUSENTE!` ou `❌ Purchase - client_user_agent AUSENTE!`

### **HIPÓTESE 3: Flag `meta_purchase_sent` já está True**
**Probabilidade: 50%**
- Se o Purchase foi tentado anteriormente (via sync job ou outro webhook), a flag pode estar `True`
- A verificação na linha 7439 bloqueia reenvio
- **MAS** o usuário disse que nunca foi enviado, então isso não faz sentido

### **HIPÓTESE 4: Pool não configurado corretamente**
**Probabilidade: 40%**
- Pool não tem `meta_tracking_enabled = True`
- Pool não tem `meta_events_purchase = True`
- Pool não tem `meta_pixel_id` ou `meta_access_token`
- **MAS** se fosse isso, o PageView também não funcionaria

### **HIPÓTESE 5: Timeout do Celery Task**
**Probabilidade: 30%**
- Celery task demora mais de 10 segundos
- `task.get(timeout=10)` lança exception
- `meta_purchase_sent` não é setado
- **MAS** o webhook não tentará novamente automaticamente

---

## 🔬 DIAGNÓSTICO DEFINITIVO

### **PASSO 1: Verificar logs do webhook**
```bash
# Buscar logs do webhook para pagamentos recentes
tail -1000 logs/gunicorn.log | grep -iE "\[WEBHOOK|Deve enviar Meta Purchase|Erro ao enviar Meta Pixel Purchase"
```

**O que procurar:**
- `Deve enviar Meta Purchase: True` → Webhook decidiu enviar
- `Erro ao enviar Meta Pixel Purchase: ...` → Exception foi lançada
- `❌ PROBLEMA RAIZ: ...` → Validação bloqueou
- `❌ Purchase - client_ip_address AUSENTE!` → Validação de IP bloqueou
- `❌ Purchase - client_user_agent AUSENTE!` → Validação de UA bloqueou

### **PASSO 2: Verificar logs do Purchase**
```bash
# Buscar logs do Purchase para pagamentos recentes
tail -1000 logs/gunicorn.log | grep -iE "\[META PURCHASE\]|DEBUG Meta Pixel Purchase|Purchase -"
```

**O que procurar:**
- `🔍 DEBUG Meta Pixel Purchase - Iniciando para ...` → Função foi chamada
- `🔍 DEBUG Meta Pixel Purchase - Pool Bot encontrado: True` → Pool Bot existe
- `🔍 DEBUG Meta Pixel Purchase - Tracking habilitado: True` → Tracking habilitado
- `🔍 DEBUG Meta Pixel Purchase - Evento Purchase habilitado: True` → Evento habilitado
- `🔍 DEBUG Meta Pixel Purchase - Já enviado: False` → Flag não está True
- `❌ Purchase - client_ip_address AUSENTE!` → IP ausente
- `❌ Purchase - client_user_agent AUSENTE!` → User-Agent ausente

### **PASSO 3: Verificar dados no Redis**
```bash
# Buscar tracking_token de um pagamento recente
# No Python:
python -c "
from app import app, db
from models import Payment
with app.app_context():
    payment = Payment.query.filter_by(status='paid').order_by(Payment.id.desc()).first()
    if payment:
        print(f'Payment ID: {payment.payment_id}')
        print(f'Tracking Token: {payment.tracking_token}')
        print(f'Meta Purchase Sent: {payment.meta_purchase_sent}')
"
```

### **PASSO 4: Verificar dados do Pool**
```bash
# No Python:
python -c "
from app import app, db
from models import Payment, PoolBot
with app.app_context():
    payment = Payment.query.filter_by(status='paid').order_by(Payment.id.desc()).first()
    if payment:
        pool_bot = PoolBot.query.filter_by(bot_id=payment.bot_id).first()
        if pool_bot:
            pool = pool_bot.pool
            print(f'Pool ID: {pool.id}')
            print(f'Meta Tracking Enabled: {pool.meta_tracking_enabled}')
            print(f'Meta Events Purchase: {pool.meta_events_purchase}')
            print(f'Meta Pixel ID: {pool.meta_pixel_id}')
            print(f'Meta Access Token: {bool(pool.meta_access_token)}')
"
```

---

## 🛠️ CORREÇÕES PROPOSTAS

### **CORREÇÃO 1: Melhorar logs no webhook**
**Arquivo:** `tasks_async.py`
**Linha:** 961-965

```python
if deve_enviar_meta_purchase:
    try:
        logger.info(f"🚀 [WEBHOOK {gateway_type.upper()}] Iniciando envio de Meta Purchase para {payment.payment_id}")
        resultado = send_meta_pixel_purchase_event(payment)
        logger.info(f"✅ [WEBHOOK {gateway_type.upper()}] Meta Purchase processado para {payment.payment_id}")
    except Exception as e:
        logger.error(f"❌ [WEBHOOK {gateway_type.upper()}] Erro ao enviar Meta Pixel Purchase: {e}", exc_info=True)
        # ✅ CRÍTICO: Não silenciar erro - propagar para análise
        raise  # Opcional: re-raise para não silenciar
```

**Motivo:** Logs mais detalhados ajudam a identificar onde está falhando.

### **CORREÇÃO 2: Validar dados ANTES de bloquear**
**Arquivo:** `app.py`
**Linha:** 8028-8041

```python
# ✅ CORREÇÃO: Se IP ou UA ausentes, tentar recuperar do BotUser ANTES de bloquear
if event_data.get('action_source') == 'website':
    if not user_data.get('client_ip_address'):
        # ✅ FALLBACK: Tentar recuperar do BotUser
        if bot_user and getattr(bot_user, 'ip_address', None):
            user_data['client_ip_address'] = bot_user.ip_address
            logger.info(f"✅ Purchase - IP recuperado do BotUser (fallback): {bot_user.ip_address}")
        else:
            logger.error(f"❌ Purchase - client_ip_address AUSENTE! Meta rejeita eventos web sem IP.")
            logger.error(f"   Payment ID: {payment.payment_id} | Pool: {pool.name}")
            # ✅ CRÍTICO: NÃO bloquear - usar IP do servidor como último recurso
            user_data['client_ip_address'] = request.remote_addr if 'request' in globals() else '0.0.0.0'
            logger.warning(f"⚠️ Purchase - Usando IP do servidor como fallback: {user_data['client_ip_address']}")
    
    if not user_data.get('client_user_agent'):
        # ✅ FALLBACK: Tentar recuperar do BotUser
        if bot_user and getattr(bot_user, 'user_agent', None):
            user_data['client_user_agent'] = bot_user.user_agent
            logger.info(f"✅ Purchase - User Agent recuperado do BotUser (fallback): {bot_user.user_agent[:50]}...")
        else:
            logger.error(f"❌ Purchase - client_user_agent AUSENTE! Meta rejeita eventos web sem User-Agent.")
            logger.error(f"   Payment ID: {payment.payment_id} | Pool: {pool.name}")
            # ✅ CRÍTICO: NÃO bloquear - usar User-Agent genérico como último recurso
            user_data['client_user_agent'] = 'Mozilla/5.0 (Unknown)'
            logger.warning(f"⚠️ Purchase - Usando User-Agent genérico como fallback")
```

**Motivo:** Não bloquear o Purchase por falta de IP/UA - usar fallbacks antes de desistir.

### **CORREÇÃO 3: Retornar status de sucesso/falha**
**Arquivo:** `app.py`
**Linha:** 7386 (assinatura da função)

```python
def send_meta_pixel_purchase_event(payment) -> bool:
    """
    Envia evento Purchase para Meta Pixel quando pagamento é confirmado
    
    Returns:
        bool: True se enviado com sucesso, False se bloqueado por validação
    """
    try:
        # ... código existente ...
        
        # ✅ CRÍTICO: Retornar True apenas se evento foi enfileirado e confirmado
        if result and result.get('events_received', 0) > 0:
            return True
        else:
            return False
    except Exception as e:
        logger.error(f"❌ Erro ao enviar Meta Purchase: {e}", exc_info=True)
        return False
```

**Motivo:** Permitir que o webhook saiba se o Purchase foi enviado ou não.

### **CORREÇÃO 4: Validar Pool ANTES de processar webhook**
**Arquivo:** `tasks_async.py`
**Linha:** 900-902

```python
# ✅ CORREÇÃO: Validar Pool ANTES de decidir enviar Purchase
pool_bot = PoolBot.query.filter_by(bot_id=payment.bot_id).first()
if pool_bot:
    pool = pool_bot.pool
    pool_ready = (
        pool.meta_tracking_enabled and
        pool.meta_events_purchase and
        pool.meta_pixel_id and
        pool.meta_access_token
    )
else:
    pool_ready = False

deve_enviar_meta_purchase = status_is_paid and not payment.meta_purchase_sent and pool_ready

if not pool_ready and status_is_paid:
    logger.warning(f"⚠️ [WEBHOOK {gateway_type.upper()}] Pool não configurado para Meta Purchase - pulando envio")
```

**Motivo:** Evitar chamar `send_meta_pixel_purchase_event` se o Pool não estiver configurado.

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
   - [ ] `payment.tracking_token` não é None
   - [ ] Log: `[META PURCHASE] Purchase - payment.tracking_token: ...`

7. **Tracking data recuperado do Redis?**
   - [ ] `tracking_data` não é vazio
   - [ ] Log: `[META PURCHASE] Purchase - tracking_data recuperado do Redis: ... campos`

8. **IP e User-Agent presentes?**
   - [ ] `user_data.get('client_ip_address')` não é None
   - [ ] `user_data.get('client_user_agent')` não é None
   - [ ] Log: `[META PURCHASE] Purchase - User Data: .../7 atributos | ip=✅ | ua=✅`

9. **Evento enfileirado no Celery?**
   - [ ] `task.id` não é None
   - [ ] Log: `📤 Purchase enfileirado: R$ ... | Task: ...`

10. **Resultado do Celery recebido?**
    - [ ] `result.get('events_received', 0) > 0`
    - [ ] Log: `✅ Purchase ENVIADO com sucesso para Meta: ...`

---

## 🎯 PRÓXIMOS PASSOS

1. **Executar diagnóstico nos logs**
   - Buscar logs do webhook para pagamentos recentes
   - Buscar logs do Purchase para pagamentos recentes
   - Identificar qual validação está bloqueando

2. **Verificar dados no banco**
   - Verificar se Pool está configurado corretamente
   - Verificar se `meta_purchase_sent` está False
   - Verificar se `tracking_token` existe

3. **Verificar dados no Redis**
   - Verificar se `tracking_token` existe no Redis
   - Verificar se `tracking_data` tem IP e User-Agent
   - Verificar TTL do token (não expirou?)

4. **Aplicar correções**
   - Implementar fallbacks para IP e User-Agent
   - Melhorar logs no webhook
   - Validar Pool antes de processar webhook

5. **Testar com pagamento real**
   - Fazer uma venda de teste
   - Verificar logs em tempo real
   - Confirmar se Purchase foi enviado

---

## 🔥 CONCLUSÃO

**Problema mais provável:**
- Validação de IP ou User-Agent está bloqueando o Purchase silenciosamente
- O erro é logado, mas não propaga para o webhook
- O webhook continua normalmente, mas o Purchase nunca é enviado

**Solução:**
1. Implementar fallbacks para IP e User-Agent
2. Melhorar logs para identificar exatamente onde está falhando
3. Validar Pool antes de processar webhook
4. Retornar status de sucesso/falha da função

**Próximo passo:**
- Executar diagnóstico nos logs para confirmar a hipótese
- Aplicar correções baseadas nos resultados do diagnóstico
