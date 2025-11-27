# 📘 COMO FUNCIONA O SISTEMA DE ASSINATURAS

**Documento:** Explicação completa do funcionamento antes de subir na VPS  
**Data:** 2025-01-25  
**Objetivo:** Entender o fluxo completo do sistema de ponta a ponta

---

## 🎯 RESUMO RÁPIDO

O sistema de assinaturas permite que usuários configurem botões de pagamento que dão acesso temporário a grupos VIP do Telegram. Quando o acesso expira, o usuário é automaticamente removido do grupo.

**Principais Componentes:**
1. **Configuração no Frontend** (botão com assinatura)
2. **Criação de Subscription** (quando pagamento é confirmado)
3. **Ativação da Subscription** (quando usuário entra no grupo)
4. **Remoção Automática** (quando assinatura expira)

---

## 📋 ÍNDICE

1. [Visão Geral do Fluxo](#1-visão-geral-do-fluxo)
2. [Passo 1: Configuração do Botão](#2-passo-1-configuração-do-botão)
3. [Passo 2: Usuário Clica e Paga](#3-passo-2-usuário-clica-e-paga)
4. [Passo 3: Pagamento Confirmado](#4-passo-3-pagamento-confirmado)
5. [Passo 4: Usuário Entra no Grupo](#5-passo-4-usuário-entra-no-grupo)
6. [Passo 5: Contagem Inicia](#6-passo-5-contagem-inicia)
7. [Passo 6: Assinatura Expira](#7-passo-6-assinatura-expira)
8. [Jobs Automáticos (APScheduler)](#8-jobs-automáticos-apsscheduler)
9. [Edge Cases e Tratamento de Erros](#9-edge-cases-e-tratamento-de-erros)
10. [Estrutura de Dados](#10-estrutura-de-dados)

---

## 1. VISÃO GERAL DO FLUXO

```
┌─────────────────────────────────────────────────────────────────┐
│                    FLUXO COMPLETO DO SISTEMA                     │
└─────────────────────────────────────────────────────────────────┘

1. CONFIGURAÇÃO (Frontend)
   ↓
   Usuário configura botão com assinatura habilitada
   Define: duração (horas/dias/semanas/meses), grupo VIP, link do grupo
   
2. COMPRA (Botão + Payment Gateway)
   ↓
   Usuário clica no botão → PIX gerado → Pagamento confirmado
   
3. CRIAÇÃO DE SUBSCRIPTION (Backend)
   ↓
   Webhook confirma pagamento → Subscription criada com status 'pending'
   (Ainda não está ativa porque usuário ainda não entrou no grupo)
   
4. ENTREGA (Link de Acesso)
   ↓
   Usuário recebe link de acesso → Clica → Entra no grupo VIP
   
5. ATIVAÇÃO (Detecção de Entrada)
   ↓
   Bot detecta new_chat_member → Ativa subscription → Calcula expires_at
   Status muda: 'pending' → 'active'
   
6. EXPIRAÇÃO (Remoção Automática)
   ↓
   Job verifica subscriptions expiradas → Remove usuário do grupo
   Status muda: 'active' → 'expired' → 'removed'
```

---

## 2. PASSO 1: CONFIGURAÇÃO DO BOTÃO

### **Onde:** Frontend (`templates/bot_config.html`)

### **O que acontece:**

1. **Usuário acessa:** `https://app.grimbots.online/bots/{bot_id}/config`

2. **Ao criar/editar um botão:**
   - Há um toggle "Assinatura" no header do botão
   - Quando ativado, aparece seção de configuração de assinatura

3. **Campos configuráveis:**
   ```javascript
   {
     subscription: {
       enabled: true,
       duration_type: "days",     // hours, days, weeks, months
       duration_value: 30,         // Quantidade (ex: 30 dias)
       vip_group_link: "https://t.me/...",  // Link do grupo
       vip_chat_id: "-1001234567890"        // ID do grupo (preenchido automaticamente)
     }
   }
   ```

4. **Validação do Grupo:**
   - Botão "Validar Grupo" chama endpoint `/api/bots/{bot_id}/validate-subscription`
   - Sistema verifica:
     - Bot está no grupo
     - Bot é administrador
     - Grupo é válido
   - Se válido, `vip_chat_id` é preenchido automaticamente

5. **Salvamento:**
   - Configuração salva no `button_config` (JSON) do bot
   - Quando usuário clica no botão, essa config é lida

---

## 3. PASSO 2: USUÁRIO CLICA E PAGA

### **Onde:** Bot do Telegram + Gateway de Pagamento

### **O que acontece:**

1. **Usuário clica no botão no Telegram:**
   - Callback: `buy_{button_index}_{payment_id}`
   - Bot processa callback em `bot_manager.py:_handle_callback_query()`

2. **Sistema gera PIX:**
   ```python
   # bot_manager.py
   payment = _generate_pix_payment(
       bot_id=bot_id,
       amount=button_price,
       button_index=button_index,        # ✅ Salva índice do botão
       button_config=button_config,      # ✅ Salva config completa (inclui subscription)
       ...
   )
   ```

3. **Payment criado no banco:**
   ```python
   Payment(
       payment_id="BOT42_...",
       bot_id=42,
       amount=19.97,
       button_index=0,                   # ✅ Qual botão foi clicado
       button_config='{"subscription": {...}}',  # ✅ Config completa salva
       has_subscription=True,            # ✅ Flag para identificar
       status='pending'
   )
   ```

4. **Usuário paga o PIX**

5. **Gateway envia webhook de confirmação**

---

## 4. PASSO 3: PAGAMENTO CONFIRMADO

### **Onde:** `app.py:process_payment_webhook()`

### **O que acontece:**

1. **Webhook recebido:**
   ```
   POST /webhook/payment/{gateway_type}
   ```

2. **Sistema processa webhook:**
   ```python
   # app.py:10683-10697
   if status == 'paid' and payment.has_subscription:
       # ✅ CRIA SUBSCRIPTION
       subscription = create_subscription_for_payment(payment)
       if subscription:
           db.session.commit()  # Commit imediato
   ```

3. **Função `create_subscription_for_payment()` faz:**

   **a) Verifica se já existe:**
   ```python
   existing = Subscription.query.filter_by(payment_id=payment.id).first()
   if existing:
       return existing  # ✅ Idempotência
   ```

   **b) Valida configuração:**
   ```python
   button_config = json.loads(payment.button_config)
   subscription_config = button_config.get('subscription', {})
   
   # Valida se está habilitado
   if not subscription_config.get('enabled'):
       return None
   
   # Valida vip_chat_id
   vip_chat_id = subscription_config.get('vip_chat_id')
   if not vip_chat_id:
       return None
   
   # ✅ CORREÇÃO CRÍTICA: Normaliza e valida
   normalized_vip_chat_id = normalize_vip_chat_id(vip_chat_id)
   if not normalized_vip_chat_id:
       logger.error("vip_chat_id inválido")
       return None
   ```

   **c) Cria subscription:**
   ```python
   subscription = Subscription(
       payment_id=payment.id,            # ✅ Relacionamento
       bot_id=payment.bot_id,
       telegram_user_id=payment.customer_user_id,
       duration_type='days',
       duration_value=30,
       vip_chat_id=normalized_vip_chat_id,
       vip_group_link=subscription_config.get('vip_group_link'),
       status='pending',                 # ✅ AINDA NÃO ATIVA
       started_at=None,                  # ✅ NULL até entrar no grupo
       expires_at=None                   # ✅ NULL até ativar
   )
   db.session.add(subscription)
   db.session.commit()
   ```

4. **Status da Subscription:** `'pending'`

   **Por que 'pending'?**
   - Usuário ainda não entrou no grupo
   - Contagem só começa quando entrar
   - Isso previne que assinatura expire antes do usuário ter acesso

---

## 5. PASSO 4: USUÁRIO ENTRA NO GRUPO

### **Onde:** `bot_manager.py:_handle_new_chat_member()`

### **O que acontece:**

1. **Usuário clica no link de acesso:**
   - Link redireciona para `/delivery/{token}`
   - Meta Pixel é acionado (Purchase event)
   - Redirecionamento final para `bot.config.access_link`

2. **Usuário entra no grupo VIP via link:**
   - Telegram envia evento `new_chat_member` para o bot

3. **Bot detecta evento:**
   ```python
   # bot_manager.py:_process_telegram_update()
   if 'new_chat_member' in message:
       chat_id = message['chat']['id']
       member_id = str(new_member['id'])
       
       # ✅ Processa entrada
       self._handle_new_chat_member(bot_id, chat_id, member_id)
   ```

4. **Função `_handle_new_chat_member()` faz:**

   **a) Busca subscriptions pendentes:**
   ```python
   # bot_manager.py:9001-9007
   pending_subscriptions = Subscription.query.filter(
       Subscription.bot_id == bot_id,
       Subscription.telegram_user_id == member_id,
       Subscription.vip_chat_id == normalize_vip_chat_id(str(chat_id)),
       Subscription.status == 'pending'
   ).all()
   ```

   **b) Para cada subscription pendente, ativa:**
   ```python
   for subscription in pending_subscriptions:
       success = self._activate_subscription(subscription.id)
   ```

---

## 6. PASSO 5: CONTAGEM INICIA

### **Onde:** `bot_manager.py:_activate_subscription()`

### **O que acontece:**

1. **Função `_activate_subscription()` faz:**

   **a) Lock pessimista (previne race condition):**
   ```python
   # bot_manager.py:8918-8923
   subscription = db.session.execute(
       select(Subscription)
       .where(Subscription.id == subscription_id)
       .where(Subscription.status == 'pending')
       .with_for_update()  # ✅ Lock pessimista
   ).scalar_one_or_none()
   ```

   **b) Validação explícita:**
   ```python
   # bot_manager.py:8933-8946
   if subscription.status != 'pending':
       return False  # Já foi ativada
   
   if subscription.started_at is not None:
       return False  # Já foi ativada
   ```

   **c) Calcula expires_at:**
   ```python
   # bot_manager.py:8948-8962
   now_utc = datetime.now(timezone.utc)
   
   if duration_type == 'hours':
       expires_at = now_utc + relativedelta(hours=duration_value)
   elif duration_type == 'days':
       expires_at = now_utc + relativedelta(days=duration_value)
   elif duration_type == 'weeks':
       expires_at = now_utc + relativedelta(weeks=duration_value)
   elif duration_type == 'months':
       # ✅ Usa relativedelta para meses corretos (30 dias ≠ 1 mês)
       expires_at = now_utc + relativedelta(months=duration_value)
   ```

   **d) Ativa subscription:**
   ```python
   subscription.status = 'active'      # ✅ Muda status
   subscription.started_at = now_utc   # ✅ Marca início
   subscription.expires_at = expires_at # ✅ Marca expiração
   
   db.session.commit()
   ```

2. **Exemplo:**
   ```
   Subscription criada: 2025-01-01 10:00:00 UTC (status: 'pending')
   Usuário entra no grupo: 2025-01-01 15:00:00 UTC
   Ativada: 2025-01-01 15:00:00 UTC (status: 'active')
   Expira em: 2025-01-31 15:00:00 UTC (30 dias)
   ```

3. **Status da Subscription:** `'active'`

---

## 7. PASSO 6: ASSINATURA EXPIRA

### **Onde:** Job APScheduler `check_expired_subscriptions()`

### **O que acontece:**

1. **Job roda a cada 5 minutos:**
   ```python
   # app.py:11547-11648
   scheduler.add_job(
       check_expired_subscriptions,
       'interval',
       minutes=5,
       id='check_expired_subscriptions'
   )
   ```

2. **Função `check_expired_subscriptions()` faz:**

   **a) Lock distribuído (Redis):**
   ```python
   # Previne múltiplos workers processarem simultaneamente
   redis_conn.set('lock:check_expired_subscriptions', '1', ex=300, nx=True)
   ```

   **b) Busca subscriptions expiradas:**
   ```python
   # app.py:11584-11588
   expired = Subscription.query.filter(
       Subscription.status == 'active',
       Subscription.expires_at.isnot(None),
       Subscription.expires_at <= now_utc  # ✅ Já expirou
   ).limit(20).all()  # Processa apenas 20 por vez
   ```

   **c) Para cada subscription expirada:**

      **1) Verifica se ainda está no grupo:**
      ```python
      is_in_group = check_user_in_group(
          bot_token=bot.token,
          chat_id=subscription.vip_chat_id,
          telegram_user_id=subscription.telegram_user_id
      )
      
      if not is_in_group:
          # Usuário já saiu - apenas marca como removed
          subscription.status = 'removed'
          subscription.removed_at = datetime.now(timezone.utc)
          db.session.commit()
          continue
      ```

      **2) Marca como 'expired':**
      ```python
      subscription.status = 'expired'  # ✅ Indica que expirou
      db.session.commit()
      ```

      **3) Tenta remover do grupo:**
      ```python
      success = remove_user_from_vip_group(subscription, max_retries=3)
      ```

3. **Função `remove_user_from_vip_group()` faz:**

   **a) Verifica outras subscriptions ativas:**
   ```python
   # app.py:11858-11876
   # ✅ Lock pessimista previne race condition
   other_active = db.session.execute(
       select(Subscription)
       .where(Subscription.status == 'active')
       .where(Subscription.telegram_user_id == subscription.telegram_user_id)
       .where(Subscription.vip_chat_id == subscription.vip_chat_id)
       .with_for_update()
   ).scalar_one_or_none()
   
   if other_active:
       # ✅ Usuário tem outra subscription ativa - NÃO REMOVE
       subscription.status = 'removed'
       subscription.removed_by = 'system_skipped'
       return True
   ```

   **b) Remove do grupo via API do Telegram:**
   ```python
   # app.py:11890-11916
   url = f"https://api.telegram.org/bot{bot.token}/banChatMember"
   response = requests.post(url, json={
       'chat_id': subscription.vip_chat_id,
       'user_id': subscription.telegram_user_id,
       'until_date': int((subscription.expires_at + timedelta(days=1)).timestamp())
       # ✅ Ban temporário (permite reentrada após expiração)
   })
   ```

   **c) Se sucesso:**
   ```python
   subscription.status = 'removed'
   subscription.removed_at = datetime.now(timezone.utc)
   subscription.removed_by = 'system'
   subscription.error_count = 0  # ✅ Reset contador de erros
   db.session.commit()
   ```

   **d) Se falhar:**
   ```python
   subscription.status = 'error'
   subscription.error_count += 1
   subscription.last_error = str(error)
   db.session.commit()
   # ✅ Será retentado por job de retry
   ```

4. **Status final da Subscription:** `'removed'`

---

## 8. JOBS AUTOMÁTICOS (APScheduler)

### **8.1 Job: check_expired_subscriptions**

**Frequência:** A cada 5 minutos  
**O que faz:** Remove usuários de grupos quando subscription expira

**Fluxo:**
```
1. Lock distribuído (Redis) - previne processamento duplicado
2. Busca subscriptions ativas expiradas (limit 20)
3. Para cada uma:
   - Verifica se ainda está no grupo
   - Marca como 'expired'
   - Tenta remover via API Telegram
   - Se falhar, marca como 'error' (será retentado)
```

**Código:** `app.py:11547-11648`

---

### **8.2 Job: check_pending_subscriptions_in_groups**

**Frequência:** A cada 30 minutos  
**O que faz:** Fallback - ativa subscriptions se evento `new_chat_member` foi perdido

**Fluxo:**
```
1. Lock distribuído (Redis)
2. Busca subscriptions pendentes (limit 50)
3. Agrupa por (bot_id, vip_chat_id) para reduzir chamadas API
4. Para cada grupo:
   - Verifica usuários no grupo via API Telegram
   - Se usuário está no grupo mas subscription ainda está 'pending':
     - Ativa subscription automaticamente
5. Delay entre grupos (2s) para evitar rate limit
```

**Código:** `app.py:11650-11746`

**Por que é necessário?**
- Evento `new_chat_member` pode ser perdido (webhook offline, erro de rede, etc.)
- Este job garante que subscriptions sejam ativadas mesmo se evento for perdido

---

### **8.3 Job: retry_failed_subscription_removals**

**Frequência:** A cada 30 minutos  
**O que faz:** Retenta remoções que falharam anteriormente

**Fluxo:**
```
1. Lock distribuído (Redis)
2. Busca subscriptions com status 'error' e error_count < 5 (limit 20)
3. Para cada uma:
   - Tenta remover novamente
   - Se sucesso: status = 'removed', error_count = 0
   - Se falhar: error_count += 1
   - Se error_count >= 5: marca como erro permanente (não tenta mais)
```

**Código:** `app.py:11748-11820`

**Por que é necessário?**
- Remoção pode falhar por rate limit, timeout, bot removido do grupo, etc.
- Este job garante que remoções sejam tentadas novamente

---

## 9. EDGE CASES E TRATAMENTO DE ERROS

### **9.1 Pagamento Reembolsado**

**Onde:** `app.py:10814-10838`

**O que acontece:**
```python
if status in ['refunded', 'failed', 'cancelled']:
    subscription = Subscription.query.filter_by(payment_id=payment.id).first()
    if subscription and subscription.status in ['pending', 'active']:
        subscription.status = 'cancelled'
        subscription.removed_at = datetime.now(timezone.utc)
        
        # Se estava ativa, tenta remover do grupo
        if old_status == 'active' and subscription.vip_chat_id:
            remove_user_from_vip_group(subscription, max_retries=1)
```

**Resultado:** Subscription cancelada, usuário removido se estiver no grupo

---

### **9.2 Usuário Sai do Grupo Manualmente**

**Onde:** `bot_manager.py:1277-1313`

**O que acontece:**
```python
if 'left_chat_member' in message:
    active_subscriptions = Subscription.query.filter(
        Subscription.status == 'active'
    ).all()
    
    for sub in active_subscriptions:
        sub.status = 'cancelled'
        sub.removed_by = 'system_user_left'
```

**Resultado:** Subscription cancelada automaticamente

---

### **9.3 Múltiplas Subscriptions no Mesmo Grupo**

**Cenário:** Usuário tem subscription 1 ativa (expira em 10 dias) e compra subscription 2 (60 dias)

**O que acontece:**
```python
# remove_user_from_vip_group() verifica outras subscriptions
other_active = Subscription.query.filter(
    Subscription.status == 'active',
    Subscription.telegram_user_id == subscription.telegram_user_id,
    Subscription.vip_chat_id == subscription.vip_chat_id
).first()

if other_active:
    # ✅ NÃO REMOVE - usuário tem outra subscription ativa
    subscription.status = 'removed'
    subscription.removed_by = 'system_skipped'
    return True
```

**Resultado:** Usuário permanece no grupo enquanto tiver pelo menos uma subscription ativa

---

### **9.4 Bot Removido do Grupo**

**Onde:** `app.py:11919-11926`

**O que acontece:**
```python
if 'bot was kicked' in error_desc.lower():
    subscription.status = 'error'
    subscription.error_count = 999  # ✅ Marca como erro permanente
    subscription.last_error = "Bot removido do grupo"
```

**Resultado:** Subscription marcada como erro permanente (não tenta mais remover)

---

### **9.5 Rate Limit (429)**

**Onde:** `app.py:11929-11946`

**O que acontece:**
```python
elif response.status_code == 429:
    retry_after = int(response.headers.get('Retry-After', 60))
    
    # ✅ Atualiza expires_at para refletir o atraso
    subscription.expires_at = subscription.expires_at + timedelta(seconds=retry_after)
    db.session.commit()
    
    time.sleep(retry_after)  # Aguarda antes de retentar
```

**Resultado:** Expires_at é ajustado para compensar o delay

---

### **9.6 Subscription Criada Mas Usuário Nunca Entra**

**Cenário:** Payment confirmado, subscription criada ('pending'), mas usuário nunca entra no grupo

**O que acontece:**
- Subscription permanece 'pending' indefinidamente
- Job `check_pending_subscriptions_in_groups` tenta ativar a cada 30 minutos
- Se usuário nunca entrar, subscription nunca é ativada (comportamento correto)

**Resultado:** Subscription nunca expira (porque nunca foi ativada)

---

## 10. ESTRUTURA DE DADOS

### **10.1 Modelo Subscription**

```python
class Subscription(db.Model):
    # Relacionamentos
    payment_id = db.Integer (FK → Payment.id, CASCADE, UNIQUE)
    bot_id = db.Integer (FK → Bot.id, CASCADE)
    
    # Dados do usuário
    telegram_user_id = db.String(255)
    customer_name = db.String(255)
    
    # Configuração
    duration_type = db.String(20)  # 'hours', 'days', 'weeks', 'months'
    duration_value = db.Integer
    
    # Grupo VIP
    vip_chat_id = db.String(100)  # Chat ID normalizado
    vip_group_link = db.String(500)  # Link original
    
    # Datas (SEMPRE UTC)
    started_at = db.DateTime(timezone=True)  # NULL até entrar no grupo
    expires_at = db.DateTime(timezone=True)  # NULL até ativar
    removed_at = db.DateTime(timezone=True)  # NULL até remover
    
    # Status
    status = db.String(20)  # 'pending', 'active', 'expired', 'removed', 'cancelled', 'error'
    
    # Metadata
    removed_by = db.String(50)  # 'system', 'manual', 'user_left', etc.
    error_count = db.Integer  # Contador de tentativas de remoção falhadas
    last_error = db.Text  # Última mensagem de erro
    
    # Timestamps
    created_at = db.DateTime(timezone=True)
    updated_at = db.DateTime(timezone=True)
```

### **10.2 Status Possíveis**

| Status | Significado | Quando Acontece |
|--------|-------------|-----------------|
| `pending` | Aguardando entrada no grupo | Subscription criada, usuário ainda não entrou |
| `active` | Contagem iniciada | Usuário entrou no grupo, contagem de tempo ativa |
| `expired` | Tempo expirado (aguardando remoção) | `expires_at` passou, mas ainda não foi removido |
| `removed` | Removido do grupo | Usuário foi removido com sucesso |
| `cancelled` | Cancelada | Payment reembolsado ou usuário saiu manualmente |
| `error` | Erro ao remover | Falha na remoção (será retentado) |

### **10.3 Índices**

```python
# Performance
idx_subscription_status_expires (status, expires_at)
idx_subscription_vip_chat (vip_chat_id, status)

# Unicidade
uq_subscription_payment (payment_id)  # Uma subscription por payment
```

---

## 11. FLUXO COMPLETO - EXEMPLO PRÁTICO

### **Cenário:** Usuário compra acesso de 30 dias a um grupo VIP

**T=0: Configuração**
```
Botão configurado:
- subscription.enabled = true
- duration_type = "days"
- duration_value = 30
- vip_chat_id = "-1001234567890"
```

**T=1: Compra (10:00)**
```
Usuário clica no botão → PIX gerado
Payment criado: status='pending', has_subscription=True
```

**T=2: Pagamento Confirmado (10:05)**
```
Webhook recebido → Payment.status = 'paid'
Subscription criada:
- status = 'pending'
- started_at = NULL
- expires_at = NULL
```

**T=3: Entrega (10:10)**
```
Link de acesso enviado → Usuário clica → Entra no grupo
```

**T=4: Ativação (10:10)**
```
Evento new_chat_member → _activate_subscription()
Subscription atualizada:
- status = 'active'
- started_at = 2025-01-25 10:10:00 UTC
- expires_at = 2025-02-24 10:10:00 UTC (30 dias depois)
```

**T=5: Durante 30 dias**
```
Subscription permanece 'active'
Jobs verificam periodicamente mas não fazem nada
```

**T=6: Expiração (30 dias depois, 10:10)**
```
Job check_expired_subscriptions roda:
- Encontra subscription expirada (expires_at <= now)
- Marca como 'expired'
- Tenta remover via banChatMember
- Se sucesso: status = 'removed'
```

**T=7: Após Remoção**
```
Usuário removido do grupo
Subscription final: status='removed', removed_at=2025-02-24 10:10:05 UTC
```

---

## 12. PONTOS CRÍTICOS DE ATENÇÃO

### **12.1 Timezone**

- ✅ **TODAS as datas são UTC** (banco de dados e lógica)
- ✅ `started_at` e `expires_at` sempre em UTC
- ✅ Jobs APScheduler trabalham em UTC
- ⚠️ **CUIDADO:** Não usar `get_brazil_time()` para subscriptions (sempre UTC)

### **12.2 Normalização de Chat ID**

- ✅ Função `normalize_vip_chat_id()` centraliza normalização
- ✅ Remove espaços, garante consistência
- ✅ **Validação crítica:** Não criar subscription se normalização retornar `None`

### **12.3 Race Conditions**

- ✅ Lock pessimista em `_activate_subscription()` previne ativação duplicada
- ✅ Lock pessimista em `remove_user_from_vip_group()` previne remoção duplicada
- ✅ UniqueConstraint em `payment_id` previne subscription duplicada

### **12.4 Idempotência**

- ✅ Verifica subscription existente antes de criar
- ✅ Trata IntegrityError se outra thread criou entre verificação e criação
- ✅ Webhook pode ser chamado múltiplas vezes sem problemas

### **12.5 Performance**

- ✅ Jobs processam em batches (limit 20-50)
- ✅ Locks distribuídos (Redis) previne processamento duplicado
- ✅ Índices em campos críticos (status, expires_at, vip_chat_id)
- ✅ Delays entre chamadas API (evita rate limit)

---

## 13. VERIFICAÇÃO ANTES DE SUBIR NA VPS

### **Checklist:**

- [ ] **Banco de dados:**
  - [ ] Tabela `subscriptions` criada
  - [ ] Índices criados
  - [ ] Foreign keys com CASCADE configuradas
  - [ ] Migration SQL aplicada (se necessário)

- [ ] **Variáveis de ambiente:**
  - [ ] `REDIS_URL` configurado (para locks distribuídos)
  - [ ] `ENCRYPTION_KEY` configurado (para descriptografar credenciais)

- [ ] **Jobs APScheduler:**
  - [ ] `check_expired_subscriptions` agendado (5 minutos)
  - [ ] `check_pending_subscriptions_in_groups` agendado (30 minutos)
  - [ ] `retry_failed_subscription_removals` agendado (30 minutos)

- [ ] **Código:**
  - [ ] Função `normalize_vip_chat_id()` implementada
  - [ ] Validação de `normalize_vip_chat_id()` em `create_subscription_for_payment()`
  - [ ] Locks pessimistas implementados
  - [ ] Tratamento de erros robusto

- [ ] **Testes recomendados:**
  - [ ] Criar subscription → Verificar se foi criada como 'pending'
  - [ ] Entrar no grupo → Verificar se ativou (status='active', started_at preenchido)
  - [ ] Esperar expiração → Verificar se removeu do grupo
  - [ ] Reembolsar payment → Verificar se subscription foi cancelada
  - [ ] Múltiplas subscriptions → Verificar se não remove incorretamente

---

## 14. RESUMO EXECUTIVO

### **Como funciona em 7 passos:**

1. **Configuração:** Usuário configura botão com assinatura (duração, grupo VIP)
2. **Compra:** Usuário clica no botão → Paga → Subscription criada (`pending`)
3. **Entrega:** Usuário recebe link → Entra no grupo VIP
4. **Ativação:** Bot detecta entrada → Ativa subscription → Calcula `expires_at` (`active`)
5. **Contagem:** Tempo passa (30 dias, por exemplo)
6. **Expiração:** Job detecta expiração → Marca como `expired`
7. **Remoção:** Job remove usuário do grupo → Status `removed`

### **Jobs automáticos:**

- **A cada 5 minutos:** Remove usuários de grupos quando subscription expira
- **A cada 30 minutos:** Ativa subscriptions se evento `new_chat_member` foi perdido
- **A cada 30 minutos:** Retenta remoções que falharam anteriormente

### **Proteções:**

- ✅ Race conditions protegidas (locks pessimistas)
- ✅ Idempotência garantida (UniqueConstraint + verificações)
- ✅ Tratamento robusto de erros (retries, exponential backoff)
- ✅ Performance otimizada (batches, índices, locks distribuídos)

---

**FIM DA EXPLICAÇÃO COMPLETA**


