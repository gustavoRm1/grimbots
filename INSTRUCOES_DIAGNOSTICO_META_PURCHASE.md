# 🔥 INSTRUÇÕES: DIAGNÓSTICO META PURCHASE NÃO ENVIADO

## 📋 CONTEXTO

**Problema:** Webhooks estão funcionando, pagamentos estão sendo marcados como `paid`, entregáveis estão sendo enviados, PageView está sendo disparado normalmente, **MAS** o Meta Purchase **NÃO** está sendo enviado.

**Causa provável:** Validações estão bloqueando o Purchase silenciosamente (IP ou User-Agent ausentes).

**⚠️ CRÍTICO: Sistema usa Cloudflare** - Captura de IP estava usando apenas `X-Forwarded-For` (incorreto com Cloudflare). Correção aplicada para priorizar `CF-Connecting-IP`.

---

## 🛠️ CORREÇÕES APLICADAS

### **1. Fallbacks para IP e User-Agent** (`app.py`)

**Antes:**
- Se IP ou User-Agent ausentes → `return` (bloqueia Purchase)
- Erro é logado, mas Purchase nunca é enviado

**Depois:**
- Se IP ausente → Tentar recuperar do BotUser
- Se ainda ausente → Usar IP genérico como último recurso
- Se User-Agent ausente → Tentar recuperar do BotUser
- Se ainda ausente → Usar User-Agent genérico como último recurso
- **NÃO bloqueia** mais o Purchase por falta de IP/UA

### **2. Logs melhorados no Webhook** (`tasks_async.py`)

**Antes:**
- Erro capturado com `logger.warning` (silencioso)
- Webhook continua normalmente, mas Purchase não é enviado

**Depois:**
- Logs detalhados antes e depois do envio
- Erro capturado com `logger.error` e `exc_info=True` (mais visível)
- Logs mostram Payment ID, Status, Meta Purchase Sent

---

## 🔬 DIAGNÓSTICO

### **PASSO 1: Executar script de diagnóstico**

```bash
cd /root/grimbots
source venv/bin/activate
python scripts/diagnostico_meta_purchase_webhook.py
```

**O que o script faz:**
- Analisa pagamentos recentes (últimas 24 horas)
- Verifica todas as condições necessárias para envio do Purchase
- Identifica problemas e avisos
- Mostra resumo detalhado

**O que procurar:**
- ✅ **SUCESSOS:** Condições atendidas
- ⚠️ **AVISOS:** Condições que podem causar problemas
- ❌ **PROBLEMAS:** Condições que bloqueiam o Purchase

### **PASSO 2: Verificar logs do webhook**

```bash
# Buscar logs do webhook para pagamentos recentes
tail -1000 logs/gunicorn.log | grep -iE "\[WEBHOOK|Deve enviar Meta Purchase|Erro ao enviar Meta Pixel Purchase|Iniciando envio de Meta Purchase"
```

**O que procurar:**
- `Deve enviar Meta Purchase: True` → Webhook decidiu enviar
- `🚀 [WEBHOOK ...] Iniciando envio de Meta Purchase` → Purchase foi iniciado
- `✅ [WEBHOOK ...] Meta Purchase processado` → Purchase foi processado
- `❌ [WEBHOOK ...] Erro ao enviar Meta Pixel Purchase` → Erro foi capturado

### **PASSO 3: Verificar logs do Purchase**

```bash
# Buscar logs do Purchase para pagamentos recentes
tail -1000 logs/gunicorn.log | grep -iE "\[META PURCHASE\]|DEBUG Meta Pixel Purchase|Purchase -|client_ip_address|client_user_agent"
```

**O que procurar:**
- `🔍 DEBUG Meta Pixel Purchase - Iniciando` → Função foi chamada
- `🔍 DEBUG Meta Pixel Purchase - Pool Bot encontrado: True` → Pool Bot existe
- `🔍 DEBUG Meta Pixel Purchase - Tracking habilitado: True` → Tracking habilitado
- `🔍 DEBUG Meta Pixel Purchase - Evento Purchase habilitado: True` → Evento habilitado
- `🔍 DEBUG Meta Pixel Purchase - Já enviado: False` → Flag não está True
- `❌ Purchase - client_ip_address AUSENTE!` → IP ausente (AGORA TEM FALLBACK)
- `❌ Purchase - client_user_agent AUSENTE!` → User-Agent ausente (AGORA TEM FALLBACK)
- `✅ Purchase - IP recuperado do BotUser` → IP recuperado do BotUser
- `✅ Purchase - User Agent recuperado do BotUser` → User-Agent recuperado do BotUser
- `⚠️ Purchase - Usando IP genérico como fallback` → IP genérico usado (AVISO)
- `⚠️ Purchase - Usando User-Agent genérico como fallback` → User-Agent genérico usado (AVISO)

### **PASSO 4: Verificar dados no Redis**

```bash
# No Python:
python -c "
from app import app, db
from models import Payment
import redis
import json

redis_client = redis.Redis(host='localhost', port=6379, db=0, decode_responses=False)

with app.app_context():
    payment = Payment.query.filter_by(status='paid').order_by(Payment.id.desc()).first()
    if payment and payment.tracking_token:
        redis_key = f'tracking:{payment.tracking_token}'
        redis_data = redis_client.get(redis_key)
        if redis_data:
            tracking_data = json.loads(redis_data)
            print(f'Tracking Token: {payment.tracking_token}')
            print(f'Campos no Redis: {list(tracking_data.keys())}')
            print(f'IP: {tracking_data.get(\"client_ip\") or tracking_data.get(\"ip\")}')
            print(f'User-Agent: {tracking_data.get(\"client_user_agent\") or tracking_data.get(\"ua\") or tracking_data.get(\"user_agent\")}')
        else:
            print(f'❌ Tracking token NÃO encontrado no Redis: {redis_key}')
    else:
        print('❌ Nenhum pagamento encontrado ou tracking_token ausente')
"
```

---

## 🎯 VERIFICAÇÕES ESPECÍFICAS

### **1. Pool está configurado corretamente?**

```sql
-- Verificar Pool Bot
SELECT pb.id, pb.bot_id, pb.pool_id, p.name, p.meta_tracking_enabled, p.meta_events_purchase, p.meta_pixel_id, p.meta_access_token IS NOT NULL as has_access_token
FROM pool_bots pb
JOIN redirect_pools p ON pb.pool_id = p.id
WHERE pb.bot_id = (SELECT bot_id FROM payments WHERE status = 'paid' ORDER BY id DESC LIMIT 1);
```

**O que verificar:**
- `meta_tracking_enabled = true`
- `meta_events_purchase = true`
- `meta_pixel_id` não é NULL
- `has_access_token = true`

### **2. Flag meta_purchase_sent está False?**

```sql
-- Verificar flag meta_purchase_sent
SELECT id, payment_id, status, meta_purchase_sent, meta_purchase_sent_at, meta_event_id
FROM payments
WHERE status = 'paid'
ORDER BY id DESC
LIMIT 10;
```

**O que verificar:**
- `meta_purchase_sent = false` (para pagamentos recentes)
- Se `meta_purchase_sent = true`, verificar `meta_purchase_sent_at` (quando foi marcado)

### **3. Tracking token existe?**

```sql
-- Verificar tracking_token
SELECT id, payment_id, tracking_token, pageview_event_id, fbp, fbc, fbclid
FROM payments
WHERE status = 'paid'
ORDER BY id DESC
LIMIT 10;
```

**O que verificar:**
- `tracking_token` não é NULL
- `pageview_event_id` não é NULL (para deduplicação)
- `fbp`, `fbc`, `fbclid` presentes (para matching)

### **4. BotUser tem IP e User-Agent?**

```sql
-- Verificar BotUser
SELECT bu.id, bu.bot_id, bu.telegram_user_id, bu.ip_address, bu.user_agent, bu.fbp, bu.fbc
FROM bot_users bu
WHERE bu.bot_id = (SELECT bot_id FROM payments WHERE status = 'paid' ORDER BY id DESC LIMIT 1)
AND bu.telegram_user_id = (SELECT customer_user_id FROM payments WHERE status = 'paid' ORDER BY id DESC LIMIT 1);
```

**O que verificar:**
- `ip_address` não é NULL (fallback disponível)
- `user_agent` não é NULL (fallback disponível)
- `fbp`, `fbc` presentes (fallback disponível)

---

## 🚀 TESTE COM PAGAMENTO REAL

### **1. Fazer uma venda de teste**

1. Acessar o redirecionador com `fbclid` (ex: `https://app.grimbots.online/go/red1?grim=testecamu01&fbclid=test`)
2. Dar `/start` no bot
3. Gerar PIX
4. Pagar o PIX
5. Verificar se webhook chegou
6. Verificar se entregável foi enviado
7. **Verificar se Purchase foi enviado**

### **2. Monitorar logs em tempo real**

```bash
# Terminal 1: Logs do webhook
tail -f logs/gunicorn.log | grep -iE "\[WEBHOOK|Meta Purchase"

# Terminal 2: Logs do Purchase
tail -f logs/gunicorn.log | grep -iE "\[META PURCHASE\]|DEBUG Meta Pixel Purchase"

# Terminal 3: Logs do Celery (se disponível)
tail -f logs/celery.log | grep -iE "Meta Event|Purchase"
```

### **3. Verificar no Meta Events Manager**

1. Acessar Meta Events Manager
2. Buscar eventos de Purchase
3. Verificar se evento foi recebido
4. Verificar Match Quality (deve ser >= 7/10)

---

## 🐛 PROBLEMAS COMUNS E SOLUÇÕES

### **Problema 1: Pool não configurado**

**Sintoma:**
- Log: `❌ PROBLEMA RAIZ: Bot não está associado a nenhum pool`
- Log: `❌ PROBLEMA RAIZ: Meta tracking DESABILITADO`
- Log: `❌ PROBLEMA RAIZ: Evento Purchase DESABILITADO`

**Solução:**
1. Associar bot a um pool no dashboard
2. Ativar Meta Tracking no pool
3. Ativar Evento Purchase no pool
4. Configurar Meta Pixel ID e Access Token no pool

### **Problema 2: Flag meta_purchase_sent já está True**

**Sintoma:**
- Log: `⚠️ Purchase já enviado ao Meta, ignorando: {payment_id}`
- Purchase não é enviado mesmo com pagamento novo

**Solução:**
1. Verificar se Purchase foi realmente enviado (Meta Events Manager)
2. Se não foi enviado, resetar flag:
   ```sql
   UPDATE payments SET meta_purchase_sent = false, meta_purchase_sent_at = NULL WHERE payment_id = 'PAYMENT_ID';
   ```
3. Reenviar Purchase manualmente (se necessário)

### **Problema 3: Tracking token ausente**

**Sintoma:**
- Log: `⚠️ Purchase - payment.tracking_token AUSENTE!`
- Purchase não tem dados de tracking

**Solução:**
1. Verificar se usuário veio do redirect (deve ter `tracking_token`)
2. Verificar se `tracking_token` está sendo salvo no Payment
3. Verificar se `tracking_token` existe no Redis

### **Problema 4: IP ou User-Agent ausentes**

**Sintoma:**
- Log: `❌ Purchase - client_ip_address AUSENTE!`
- Log: `❌ Purchase - client_user_agent AUSENTE!`
- Purchase bloqueado (ANTES das correções)

**Solução (APÓS correções):**
- Fallbacks automáticos agora recuperam IP/UA do BotUser
- Se ainda ausentes, usam valores genéricos
- **AVISO:** Meta pode rejeitar eventos com IP/UA genéricos
- **CORREÇÃO DEFINITIVA:** Garantir que IP/UA sejam capturados no redirect

### **Problema 5: Timeout do Celery Task**

**Sintoma:**
- Log: `❌ Erro ao obter resultado do Celery: Timeout`
- Purchase não é marcado como enviado

**Solução:**
1. Verificar se Celery está rodando
2. Verificar se worker está processando tasks
3. Aumentar timeout (se necessário):
   ```python
   result = task.get(timeout=30)  # Aumentar de 10 para 30 segundos
   ```

---

## 📊 CHECKLIST FINAL

### **✅ Antes de testar:**

- [ ] Pool está configurado corretamente
- [ ] Meta Tracking está habilitado
- [ ] Evento Purchase está habilitado
- [ ] Meta Pixel ID está configurado
- [ ] Meta Access Token está configurado
- [ ] Celery está rodando
- [ ] Redis está rodando
- [ ] Logs estão sendo gerados

### **✅ Durante o teste:**

- [ ] Webhook está chegando
- [ ] Pagamento está sendo marcado como `paid`
- [ ] Entregável está sendo enviado
- [ ] Purchase está sendo iniciado (logs)
- [ ] Purchase está sendo processado (logs)
- [ ] Purchase está sendo enfileirado (logs)
- [ ] Purchase está sendo enviado (logs)
- [ ] Purchase está sendo confirmado (logs)

### **✅ Após o teste:**

- [ ] Flag `meta_purchase_sent` está `True`
- [ ] `meta_purchase_sent_at` está preenchido
- [ ] `meta_event_id` está preenchido
- [ ] Evento aparece no Meta Events Manager
- [ ] Match Quality >= 7/10
- [ ] Evento está sendo atribuído corretamente

---

## 🔥 PRÓXIMOS PASSOS

1. **Executar script de diagnóstico**
   ```bash
   python scripts/diagnostico_meta_purchase_webhook.py
   ```

2. **Verificar logs do webhook**
   ```bash
   tail -1000 logs/gunicorn.log | grep -iE "\[WEBHOOK|Meta Purchase"
   ```

3. **Verificar logs do Purchase**
   ```bash
   tail -1000 logs/gunicorn.log | grep -iE "\[META PURCHASE\]|DEBUG Meta Pixel Purchase"
   ```

4. **Testar com pagamento real**
   - Fazer uma venda de teste
   - Monitorar logs em tempo real
   - Verificar no Meta Events Manager

5. **Aplicar correções adicionais (se necessário)**
   - Baseado nos resultados do diagnóstico
   - Baseado nos logs do webhook e Purchase
   - Baseado nos problemas encontrados

---

## 📝 NOTAS IMPORTANTES

1. **Fallbacks não são ideais:**
   - IP genérico (`0.0.0.0`) pode ser rejeitado pela Meta
   - User-Agent genérico pode ser rejeitado pela Meta
   - **CORREÇÃO DEFINITIVA:** Garantir que IP/UA sejam capturados no redirect

2. **Logs são críticos:**
   - Sempre verificar logs antes de assumir que algo está funcionando
   - Logs mostram exatamente onde está falhando
   - Logs ajudam a identificar problemas rapidamente

3. **Validações são necessárias:**
   - Validações previnem envio de eventos inválidos
   - Validações ajudam a identificar problemas de configuração
   - **MAS** validações não devem bloquear silenciosamente (agora corrigido)

4. **Diagnóstico é essencial:**
   - Sem diagnóstico, é difícil identificar o problema
   - Script de diagnóstico ajuda a encontrar problemas rapidamente
   - Diagnóstico deve ser executado regularmente

---

## 🎯 CONCLUSÃO

**Correções aplicadas:**
- ✅ Fallbacks para IP e User-Agent
- ✅ Logs melhorados no webhook
- ✅ Validações não bloqueiam mais silenciosamente
- ✅ Script de diagnóstico criado

**Próximos passos:**
1. Executar script de diagnóstico
2. Verificar logs do webhook e Purchase
3. Testar com pagamento real
4. Aplicar correções adicionais (se necessário)

**Resultado esperado:**
- Purchase sendo enviado normalmente
- Logs mostrando sucesso
- Eventos aparecendo no Meta Events Manager
- Match Quality >= 7/10

