# 🔥 DIAGNÓSTICO COMPLETO - PURCHASE NÃO ENVIADO (QI 1000+)

**Data:** 2025-11-15  
**Nível:** 🔥 **ULTRA SÊNIOR - QI 1000+**  
**Problema:** Purchase event não está sendo enviado para Meta

---

## 📋 ANÁLISE COMPLETA DO CÓDIGO

### **1. ONDE `send_meta_pixel_purchase_event` É CHAMADO:**

1. **Webhook (`tasks_async.py:8786`):**
   ```python
   send_meta_pixel_purchase_event(payment)
   ```
   - Chamado quando webhook recebe status `paid`
   - Condição: `deve_enviar_meta_purchase = status_is_paid and not payment.meta_purchase_sent`

2. **Botão Verify (`bot_manager.py:3499`):**
   ```python
   if not payment.meta_purchase_sent:
       send_meta_pixel_purchase_event(payment)
   ```
   - Chamado quando usuário clica em "Verificar Pagamento"
   - Condição: `payment.meta_purchase_sent == False`

3. **Reconciliadores (`app.py:482, 619`):**
   ```python
   send_meta_pixel_purchase_event(p)
   ```
   - Chamado quando reconciliador encontra pagamento pago
   - Sem condições (sempre tenta enviar)

---

### **2. VALIDAÇÕES QUE PODEM BLOQUEAR O ENVIO:**

#### **Validação 1: Pool Bot não existe (linha 7538-7541)**
```python
if not pool_bot:
    logger.error(f"❌ PROBLEMA RAIZ: Bot {payment.bot_id} não está associado a nenhum pool")
    return  # ❌ BLOQUEIA
```
**Causa possível:** Bot não associado a pool → Purchase não é enviado

#### **Validação 2: Meta Tracking desabilitado (linha 7551-7554)**
```python
if not pool.meta_tracking_enabled:
    logger.error(f"❌ PROBLEMA RAIZ: Meta tracking DESABILITADO")
    return  # ❌ BLOQUEIA
```
**Causa possível:** Meta tracking desabilitado no pool → Purchase não é enviado

#### **Validação 3: Pixel ID ou Access Token ausentes (linha 7556-7559)**
```python
if not pool.meta_pixel_id or not pool.meta_access_token:
    logger.error(f"❌ PROBLEMA RAIZ: Pool tem tracking ativo mas SEM pixel_id ou access_token")
    return  # ❌ BLOQUEIA
```
**Causa possível:** Pixel ID ou Access Token ausentes → Purchase não é enviado

#### **Validação 4: Evento Purchase desabilitado (linha 7563-7566)**
```python
if not pool.meta_events_purchase:
    logger.error(f"❌ PROBLEMA RAIZ: Evento Purchase DESABILITADO")
    return  # ❌ BLOQUEIA
```
**Causa possível:** Evento Purchase desabilitado no pool → Purchase não é enviado

#### **Validação 5: Já foi enviado (linha 7571-7577)**
```python
if payment.meta_purchase_sent:
    logger.info(f"⚠️ Purchase já enviado ao Meta, ignorando")
    return  # ❌ BLOQUEIA
```
**Causa possível:** Flag `meta_purchase_sent` já está `True` → Purchase não é enviado

#### **Validação 6: Erro ao descriptografar Access Token (linha 7590-7594)**
```python
try:
    access_token = decrypt(pool.meta_access_token)
except Exception as decrypt_error:
    logger.error(f"❌ Erro ao descriptografar access_token")
    return  # ❌ BLOQUEIA
```
**Causa possível:** Erro ao descriptografar Access Token → Purchase não é enviado

#### **Validação 7: Campos críticos ausentes (linha 8133-8136)**
```python
if critical_missing:
    logger.error(f"❌ Purchase - Campos críticos ausentes: {critical_missing}")
    return  # ❌ BLOQUEIA
```
**Causa possível:** Campos críticos ausentes (`event_name`, `event_time`, `event_id`, `action_source`, `user_data`) → Purchase não é enviado

#### **Validação 8: user_data inválido (linha 8142-8147)**
```python
if not user_data.get('external_id') and not user_data.get('client_ip_address'):
    logger.error(f"❌ Purchase - user_data deve ter pelo menos external_id ou client_ip_address")
    return  # ❌ BLOQUEIA
```
**Causa possível:** Sem `external_id` E sem `client_ip_address` → Purchase não é enviado

#### **Validação 9: Nenhum identificador presente (linha 8150-8154)**
```python
if not user_data.get('external_id') and not user_data.get('fbp') and not user_data.get('fbc'):
    logger.error(f"❌ Purchase - Nenhum identificador presente (external_id, fbp, fbc)")
    return  # ❌ BLOQUEIA
```
**Causa possível:** Sem nenhum identificador (`external_id`, `fbp`, `fbc`) → Purchase não é enviado

#### **Validação 10: IP ou User-Agent ausentes (linhas 8161-8202)**
```python
if event_data.get('action_source') == 'website':
    if not user_data.get('client_ip_address'):
        # ✅ FALLBACK: Usar IP genérico como último recurso
        user_data['client_ip_address'] = '0.0.0.0'
    if not user_data.get('client_user_agent'):
        # ✅ FALLBACK: Usar User-Agent genérico como último recurso
        user_data['client_user_agent'] = 'Mozilla/5.0 (Unknown)...'
```
**Causa possível:** ⚠️ **NÃO BLOQUEIA MAIS** - Usa fallbacks genéricos

---

### **3. FLUXO DE ENVIO:**

1. **Enfileirar no Celery (linha 8215-8223):**
   ```python
   task = send_meta_event.apply_async(
       args=[pool.meta_pixel_id, access_token, event_data, pool.meta_test_event_code],
       priority=1
   )
   ```

2. **Aguardar resultado (linha 8234-8244):**
   ```python
   try:
       result = task.get(timeout=10)  # ⚠️ TIMEOUT DE 10 SEGUNDOS
       if result and result.get('events_received', 0) > 0:
           payment.meta_purchase_sent = True
           db.session.commit()
   except Exception as result_error:
       logger.error(f"❌ Erro ao obter resultado do Celery: {result_error}")
       db.session.rollback()  # ❌ NÃO marca como enviado
   ```

3. **Problema identificado:**
   - Se Celery task demorar mais de 10 segundos → `TimeoutError`
   - Se Celery task falhar silenciosamente → `result.get('events_received', 0) == 0`
   - Se Celery não estiver rodando → `Exception`
   - **Resultado:** `meta_purchase_sent` **NÃO** é setado → Purchase pode ser tentado novamente

---

## 🔍 ANÁLISE DOS LOGS FORNECIDOS

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

## 🎯 DIAGNÓSTICO DEFINITIVO

### **PROBLEMA IDENTIFICADO #1: Tracking Data Vazio no Redis**

**Evidência:**
- `tracking_data` recuperado do Redis tem apenas 6 campos básicos
- **NÃO tem:** `fbclid`, `fbp`, `fbc`, `client_ip`, `client_user_agent`, `pageview_event_id`
- **Tem apenas:** `tracking_token`, `bot_id`, `customer_user_id`, `created_from`, `created_at`, `updated_at`

**Causa raiz:**
- `payment.tracking_token` é `tracking_0245156101f95efcb74b9...` (formato `tracking_xxx`)
- Este token foi gerado em `generate_pix_payment` (quando PIX foi criado)
- **NÃO** é o mesmo token usado no redirect (que seria UUID hex de 32 chars)
- Dados de tracking (fbclid, fbp, fbc, ip, ua) foram salvos no token do redirect
- Purchase tenta recuperar usando token diferente → encontra token vazio

**Solução:**
- ✅ Garantir que `payment.tracking_token` seja o mesmo usado no redirect
- ✅ Ou recuperar token do redirect via `bot_user.tracking_session_id`
- ✅ Ou recuperar token via `fbclid` do Payment

---

### **PROBLEMA IDENTIFICADO #2: IP e User-Agent Ausentes**

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

### **PROBLEMA IDENTIFICADO #3: Celery Task Pode Não Estar Processando**

**Evidência:**
- Logs mostram: `✅ Meta Pixel Purchase enviado via botão verify`
- **MAS** não há logs de: `📤 Purchase enfileirado` ou `📤 Purchase ENVIADO`
- Isso indica que a função pode estar retornando **ANTES** de enfileirar

**Causa raiz possível:**
1. **Validação bloqueando silenciosamente:**
   - Uma das validações (linhas 8136, 8147, 8154) está retornando `return` sem lançar exception
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

## 🛠️ SCRIPT DE DIAGNÓSTICO

### **Script para identificar a causa raiz:**

```python
# scripts/diagnostico_purchase_nao_enviado.py
"""
Script de diagnóstico completo para identificar por que Purchase não está sendo enviado
"""

import sys
import os
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from app import app, db
from models import Payment, PoolBot, BotUser
from utils.tracking_service import TrackingServiceV4
import json

def diagnostico_purchase_nao_enviado(payment_id=None):
    """
    Diagnóstico completo de por que Purchase não está sendo enviado
    """
    with app.app_context():
        # 1. Buscar payment recente
        if payment_id:
            payment = Payment.query.filter_by(payment_id=payment_id).first()
        else:
            payment = Payment.query.filter_by(status='paid').order_by(Payment.id.desc()).first()
        
        if not payment:
            print("❌ Nenhum payment encontrado")
            return
        
        print(f"🔍 DIAGNÓSTICO PARA PAYMENT: {payment.payment_id}")
        print(f"   Status: {payment.status}")
        print(f"   Meta Purchase Sent: {payment.meta_purchase_sent}")
        print(f"   Created At: {payment.created_at}")
        print(f"   Paid At: {payment.paid_at}")
        print()
        
        # 2. Verificar Pool Bot
        pool_bot = PoolBot.query.filter_by(bot_id=payment.bot_id).first()
        if not pool_bot:
            print("❌ PROBLEMA 1: Pool Bot não encontrado")
            print(f"   Bot ID: {payment.bot_id}")
            print(f"   SOLUÇÃO: Associe o bot a um pool no dashboard")
            return
        else:
            print("✅ Pool Bot encontrado")
            pool = pool_bot.pool
            print(f"   Pool ID: {pool.id}")
            print(f"   Pool Name: {pool.name}")
            print()
        
        # 3. Verificar Meta Tracking
        if not pool.meta_tracking_enabled:
            print("❌ PROBLEMA 2: Meta Tracking desabilitado")
            print(f"   SOLUÇÃO: Ative 'Meta Tracking' nas configurações do pool {pool.name}")
            return
        else:
            print("✅ Meta Tracking habilitado")
            print()
        
        # 4. Verificar Pixel ID e Access Token
        if not pool.meta_pixel_id:
            print("❌ PROBLEMA 3: Pixel ID ausente")
            print(f"   SOLUÇÃO: Configure Meta Pixel ID nas configurações do pool {pool.name}")
            return
        else:
            print("✅ Pixel ID configurado")
            print(f"   Pixel ID: {pool.meta_pixel_id}")
        
        if not pool.meta_access_token:
            print("❌ PROBLEMA 4: Access Token ausente")
            print(f"   SOLUÇÃO: Configure Meta Access Token nas configurações do pool {pool.name}")
            return
        else:
            print("✅ Access Token configurado")
            print()
        
        # 5. Verificar Evento Purchase
        if not pool.meta_events_purchase:
            print("❌ PROBLEMA 5: Evento Purchase desabilitado")
            print(f"   SOLUÇÃO: Ative 'Purchase Event' nas configurações do pool {pool.name}")
            return
        else:
            print("✅ Evento Purchase habilitado")
            print()
        
        # 6. Verificar tracking_token
        tracking_token = getattr(payment, 'tracking_token', None)
        if not tracking_token:
            print("❌ PROBLEMA 6: tracking_token ausente no Payment")
            print(f"   SOLUÇÃO: Verifique se usuário veio do redirect")
            return
        else:
            print("✅ tracking_token encontrado no Payment")
            print(f"   Tracking Token: {tracking_token[:30]}... (len={len(tracking_token)})")
            print()
        
        # 7. Verificar tracking_data no Redis
        tracking_service_v4 = TrackingServiceV4()
        tracking_data = tracking_service_v4.recover_tracking_data(tracking_token) or {}
        
        if not tracking_data:
            print("❌ PROBLEMA 7: tracking_data vazio no Redis")
            print(f"   Tracking Token: {tracking_token[:30]}...")
            print(f"   SOLUÇÃO: Verifique se token existe no Redis")
        else:
            print("✅ tracking_data encontrado no Redis")
            print(f"   Campos: {list(tracking_data.keys())}")
            print(f"   fbclid: {'✅' if tracking_data.get('fbclid') else '❌'}")
            print(f"   fbp: {'✅' if tracking_data.get('fbp') else '❌'}")
            print(f"   fbc: {'✅' if tracking_data.get('fbc') else '❌'}")
            print(f"   client_ip: {'✅' if tracking_data.get('client_ip') else '❌'}")
            print(f"   client_user_agent: {'✅' if tracking_data.get('client_user_agent') else '❌'}")
            print(f"   pageview_event_id: {'✅' if tracking_data.get('pageview_event_id') else '❌'}")
            print()
        
        # 8. Verificar BotUser
        telegram_user_id = str(payment.customer_user_id).replace('user_', '')
        bot_user = BotUser.query.filter_by(
            bot_id=payment.bot_id,
            telegram_user_id=telegram_user_id
        ).first()
        
        if not bot_user:
            print("❌ PROBLEMA 8: BotUser não encontrado")
            print(f"   Telegram User ID: {telegram_user_id}")
        else:
            print("✅ BotUser encontrado")
            print(f"   tracking_session_id: {bot_user.tracking_session_id[:30] if bot_user.tracking_session_id else 'None'}...")
            print(f"   fbclid: {'✅' if bot_user.fbclid else '❌'}")
            print(f"   fbp: {'✅' if bot_user.fbp else '❌'}")
            print(f"   fbc: {'✅' if bot_user.fbc else '❌'}")
            print(f"   ip_address: {'✅' if bot_user.ip_address else '❌'}")
            print(f"   user_agent: {'✅' if bot_user.user_agent else '❌'}")
            print()
            
            # ✅ CRÍTICO: Verificar se tracking_session_id é diferente do payment.tracking_token
            if bot_user.tracking_session_id and bot_user.tracking_session_id != tracking_token:
                print("⚠️ PROBLEMA 9: tracking_session_id do BotUser é diferente do payment.tracking_token")
                print(f"   BotUser tracking_session_id: {bot_user.tracking_session_id[:30]}...")
                print(f"   Payment tracking_token: {tracking_token[:30]}...")
                print(f"   SOLUÇÃO: Usar tracking_session_id do BotUser para recuperar tracking_data")
                print()
                
                # Tentar recuperar usando tracking_session_id do BotUser
                tracking_data_botuser = tracking_service_v4.recover_tracking_data(bot_user.tracking_session_id) or {}
                if tracking_data_botuser:
                    print("✅ tracking_data encontrado usando tracking_session_id do BotUser")
                    print(f"   Campos: {list(tracking_data_botuser.keys())}")
                    print(f"   fbclid: {'✅' if tracking_data_botuser.get('fbclid') else '❌'}")
                    print(f"   fbp: {'✅' if tracking_data_botuser.get('fbp') else '❌'}")
                    print(f"   fbc: {'✅' if tracking_data_botuser.get('fbc') else '❌'}")
                    print(f"   client_ip: {'✅' if tracking_data_botuser.get('client_ip') else '❌'}")
                    print(f"   client_user_agent: {'✅' if tracking_data_botuser.get('client_user_agent') else '❌'}")
                    print(f"   pageview_event_id: {'✅' if tracking_data_botuser.get('pageview_event_id') else '❌'}")
                else:
                    print("❌ tracking_data vazio mesmo usando tracking_session_id do BotUser")
                print()
        
        # 9. Verificar user_data que seria enviado
        from utils.meta_pixel import MetaPixelAPI
        
        external_id_value = tracking_data.get('fbclid') or payment.fbclid or (bot_user.fbclid if bot_user else None)
        fbp_value = tracking_data.get('fbp') or payment.fbp or (bot_user.fbp if bot_user else None)
        fbc_value = tracking_data.get('fbc') or payment.fbc or (bot_user.fbc if bot_user else None)
        ip_value = tracking_data.get('client_ip') or (bot_user.ip_address if bot_user else None)
        user_agent_value = tracking_data.get('client_user_agent') or (bot_user.user_agent if bot_user else None)
        
        print("🔍 USER_DATA QUE SERIA ENVIADO:")
        print(f"   external_id: {'✅' if external_id_value else '❌'}")
        print(f"   fbp: {'✅' if fbp_value else '❌'}")
        print(f"   fbc: {'✅' if fbc_value else '❌'}")
        print(f"   client_ip_address: {'✅' if ip_value else '❌'}")
        print(f"   client_user_agent: {'✅' if user_agent_value else '❌'}")
        print()
        
        # 10. Verificar validações que podem bloquear
        if not external_id_value and not ip_value:
            print("❌ PROBLEMA 10: user_data não tem external_id nem client_ip_address")
            print(f"   SOLUÇÃO: Meta rejeita eventos sem user_data válido")
            return
        
        if not external_id_value and not fbp_value and not fbc_value:
            print("❌ PROBLEMA 11: Nenhum identificador presente (external_id, fbp, fbc)")
            print(f"   SOLUÇÃO: Meta rejeita eventos sem identificadores")
            return
        
        # 11. Verificar Celery
        from celery_app import celery_app
        try:
            # Verificar se Celery está rodando
            inspect = celery_app.control.inspect()
            active_workers = inspect.active()
            if active_workers:
                print("✅ Celery está rodando")
                print(f"   Workers ativos: {len(active_workers)}")
            else:
                print("❌ PROBLEMA 12: Celery não está rodando")
                print(f"   SOLUÇÃO: Inicie o Celery worker")
                return
        except Exception as e:
            print(f"❌ PROBLEMA 12: Erro ao verificar Celery: {e}")
            print(f"   SOLUÇÃO: Verifique se Celery está configurado corretamente")
            return
        
        print()
        print("✅ TODAS AS VALIDAÇÕES PASSARAM!")
        print("   Purchase DEVERIA estar sendo enviado")
        print("   Verifique logs do Celery para identificar problemas no processamento")

if __name__ == '__main__':
    import sys
    payment_id = sys.argv[1] if len(sys.argv) > 1 else None
    diagnostico_purchase_nao_enviado(payment_id)
```

---

## 🎯 CAUSA RAIZ IDENTIFICADA

### **PROBLEMA PRINCIPAL: Tracking Token Diferente**

**Evidência:**
1. `payment.tracking_token` é `tracking_0245156101f95efcb74b9...` (gerado em `generate_pix_payment`)
2. `bot_user.tracking_session_id` é `30d7839aa9194e9ca324...` (gerado no redirect)
3. Dados de tracking (fbclid, fbp, fbc, ip, ua) foram salvos no token do redirect
4. Purchase tenta recuperar usando token diferente → encontra token vazio

**Solução:**
1. ✅ Usar `bot_user.tracking_session_id` como prioridade 1
2. ✅ Se não encontrar, tentar recuperar via `fbclid` do Payment
3. ✅ Se ainda não encontrar, usar dados do Payment/BotUser como fallback

---

## 🛠️ CORREÇÃO PROPOSTA

### **CORREÇÃO 1: Priorizar tracking_session_id do BotUser**

**Arquivo:** `app.py`  
**Linha:** 7628-7677

```python
# ✅ CORREÇÃO CRÍTICA: Priorizar tracking_session_id do BotUser
tracking_data = {}
payment_tracking_token = getattr(payment, "tracking_token", None)

# ✅ PRIORIDADE 1: tracking_session_id do BotUser (token do redirect)
if bot_user and bot_user.tracking_session_id:
    try:
        tracking_data = tracking_service_v4.recover_tracking_data(bot_user.tracking_session_id) or {}
        if tracking_data:
            logger.info(f"✅ Purchase - tracking_data recuperado usando bot_user.tracking_session_id: {len(tracking_data)} campos")
            # ✅ Atualizar payment.tracking_token com o token correto
            if payment.tracking_token != bot_user.tracking_session_id:
                payment.tracking_token = bot_user.tracking_session_id
                logger.info(f"✅ Purchase - payment.tracking_token atualizado: {bot_user.tracking_session_id[:30]}...")
    except Exception as e:
        logger.warning(f"⚠️ Purchase - Erro ao recuperar tracking_data usando bot_user.tracking_session_id: {e}")

# ✅ PRIORIDADE 2: payment.tracking_token (se não encontrou no BotUser)
if not tracking_data and payment_tracking_token:
    try:
        tracking_data = tracking_service_v4.recover_tracking_data(payment_tracking_token) or {}
        if tracking_data:
            logger.info(f"✅ Purchase - tracking_data recuperado usando payment.tracking_token: {len(tracking_data)} campos")
    except Exception as e:
        logger.warning(f"⚠️ Purchase - Erro ao recuperar tracking_data usando payment.tracking_token: {e}")

# ✅ PRIORIDADE 3: Recuperar via fbclid do Payment
if not tracking_data and getattr(payment, "fbclid", None):
    try:
        token = tracking_service_v4.redis.get(f"tracking:fbclid:{payment.fbclid}")
        if token:
            tracking_data = tracking_service_v4.recover_tracking_data(token) or {}
            if tracking_data:
                logger.info(f"✅ Purchase - tracking_data recuperado via fbclid do Payment: {len(tracking_data)} campos")
                # ✅ Atualizar payment.tracking_token com o token correto
                payment.tracking_token = token
                logger.info(f"✅ Purchase - payment.tracking_token atualizado via fbclid: {token[:30]}...")
    except Exception as e:
        logger.warning(f"⚠️ Purchase - Erro ao recuperar tracking_data via fbclid: {e}")
```

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

## 🚨 PRÓXIMOS PASSOS

1. **Executar script de diagnóstico:**
   ```bash
   python scripts/diagnostico_purchase_nao_enviado.py [payment_id]
   ```

2. **Verificar logs do Celery:**
   ```bash
   tail -f logs/celery.log | grep -iE "purchase|meta|event"
   ```

3. **Verificar se Celery está rodando:**
   ```bash
   ps aux | grep celery
   ```

4. **Aplicar correção proposta:**
   - Priorizar `bot_user.tracking_session_id` para recuperar tracking_data
   - Atualizar `payment.tracking_token` com o token correto
   - Garantir que IP/UA sejam recuperados do token correto

5. **Testar com pagamento real:**
   - Fazer uma venda de teste
   - Verificar logs em tempo real
   - Confirmar se Purchase foi enviado

---

## 🔥 CONCLUSÃO

**PROBLEMA IDENTIFICADO:**
- Tracking token diferente entre redirect e purchase
- Dados de tracking salvos no token do redirect
- Purchase tenta recuperar usando token diferente → encontra token vazio
- IP/UA ausentes → usa fallbacks genéricos
- Purchase pode estar sendo bloqueado por validação ou falhando no Celery

**SOLUÇÃO:**
1. Priorizar `bot_user.tracking_session_id` para recuperar tracking_data
2. Atualizar `payment.tracking_token` com o token correto
3. Garantir que IP/UA sejam recuperados do token correto
4. Verificar se Celery está processando tasks corretamente
5. Verificar se há timeout no Celery (10 segundos pode ser insuficiente)

**PRÓXIMO PASSO:**
- Executar script de diagnóstico para confirmar a causa raiz
- Aplicar correção proposta
- Testar com pagamento real

