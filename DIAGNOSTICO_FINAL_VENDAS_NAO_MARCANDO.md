# 🔥 DIAGNÓSTICO FINAL: VENDAS NÃO ESTÃO SENDO MARCADAS NA CAMPANHA

## 🎯 ANÁLISE PROFUNDA - QI 500

Analisamos o código completo do sistema de tracking e identificamos os pontos críticos que podem impedir as vendas de serem marcadas na campanha do Meta Ads.

## 📊 FLUXO COMPLETO DO TRACKING

```
1. REDIRECT (/go/{pool-slug})
   ├─ Captura UTMs da URL (app.py:5565-5572)
   ├─ Salva tracking_payload no Redis (app.py:5618)
   │  └─ Contém: fbclid, fbp, fbc, UTMs, grim, pageview_event_id
   ├─ Envia PageView para Meta (app.py:5645)
   └─ Faz MERGE e atualiza Redis (app.py:5658-5729)

2. PURCHASE (quando pagamento é confirmado)
   ├─ Recupera tracking_data do Redis (app.py:9620-9719)
   ├─ Recupera UTMs do tracking_data (app.py:10330-10339)
   ├─ Fallback: UTMs do payment (app.py:10342-10361) ✅
   ├─ Fallback: UTMs do bot_user (app.py:10393-10402) ✅
   └─ Envia Purchase para Meta (app.py:10604-10612)
```

## ✅ O QUE JÁ ESTÁ FUNCIONANDO

1. **UTMs são salvos no Payment:** `bot_manager.py:7484-7493` - UTMs são salvos corretamente quando o Payment é criado
2. **Fallbacks robustos:** `app.py:10330-10402` - O sistema tenta recuperar UTMs de múltiplas fontes (Redis, Payment, BotUser)
3. **Logging detalhado:** O sistema loga quando UTMs estão ausentes (linha 10365-10409)

## ❌ POSSÍVEIS PROBLEMAS

### **PROBLEMA #1: UTMs Não Estão na URL de Redirect**

**CAUSA:** Se o link do Meta Ads não incluir UTMs na query string, eles nunca serão capturados.

**VERIFICAÇÃO:** 
- Verificar se o link do Meta Ads inclui `?utm_source=facebook&utm_campaign=...&grim=...`
- Verificar se o link do redirector (se houver) preserva os UTMs

**SOLUÇÃO:** 
- Garantir que todos os links do Meta Ads incluam UTMs
- Configurar o redirector para preservar UTMs

### **PROBLEMA #2: Purchase Event Desabilitado**

**CAUSA:** Se `meta_events_purchase = False` no pool, o Purchase não será enviado.

**VERIFICAÇÃO:**
```sql
SELECT meta_events_purchase FROM redirect_pool WHERE id = [POOL_ID];
```

**SOLUÇÃO:** Ativar `meta_events_purchase = True` nas configurações do pool.

### **PROBLEMA #3: Pool Sem Meta Pixel Configurado**

**CAUSA:** Se o pool não tiver `meta_pixel_id` ou `meta_access_token`, o Purchase não será enviado.

**VERIFICAÇÃO:**
```sql
SELECT 
    meta_tracking_enabled,
    meta_pixel_id,
    meta_access_token IS NOT NULL as has_token
FROM redirect_pool 
WHERE id = [POOL_ID];
```

**SOLUÇÃO:** Configurar Meta Pixel ID e Access Token no pool.

### **PROBLEMA #4: Bot Não Associado ao Pool**

**CAUSA:** Se o bot não estiver associado ao pool, o Purchase não será enviado.

**VERIFICAÇÃO:**
```sql
SELECT * FROM pool_bot WHERE bot_id = [BOT_ID];
```

**SOLUÇÃO:** Associar o bot ao pool no dashboard.

### **PROBLEMA #5: UTMs Estão Vazios no Redis**

**CAUSA:** Se UTMs não forem salvos no Redis durante o redirect, o Purchase pode não recuperá-los.

**VERIFICAÇÃO:**
- Usar o `tracking_token` do Payment e verificar no Redis
- Verificar logs do redirect para ver se UTMs foram capturados

**SOLUÇÃO:** Garantir que UTMs sejam sempre salvos no Redis durante o redirect.

## 🔧 CHECKLIST DE DIAGNÓSTICO

### ✅ **1. Verificar Configuração do Pool**

```sql
SELECT 
    id, 
    name, 
    meta_tracking_enabled, 
    meta_pixel_id, 
    meta_access_token IS NOT NULL as has_access_token,
    meta_events_purchase
FROM redirect_pool 
WHERE id = [SEU_POOL_ID];
```

**Requisitos:**
- ✅ `meta_tracking_enabled = True`
- ✅ `meta_pixel_id IS NOT NULL`
- ✅ `has_access_token = True`
- ✅ `meta_events_purchase = True`

### ✅ **2. Verificar Bot Associado ao Pool**

```sql
SELECT 
    pb.bot_id,
    pb.pool_id,
    b.username
FROM pool_bot pb
JOIN bot b ON b.id = pb.bot_id
WHERE pb.bot_id = [SEU_BOT_ID];
```

**Requisito:** Bot deve estar associado ao pool!

### ✅ **3. Verificar Payment de uma Venda**

```sql
SELECT 
    p.id,
    p.payment_id,
    p.tracking_token,
    p.status,
    p.created_at,
    p.utm_source,
    p.utm_campaign,
    p.campaign_code,
    p.meta_purchase_sent,
    p.meta_event_id
FROM payment p
WHERE p.id = [ID_DA_VENDA];
```

**Verificar:**
- ✅ `tracking_token` existe?
- ✅ UTMs estão salvos no Payment?
- ✅ `meta_purchase_sent = True`?
- ✅ `meta_event_id` existe?

### ✅ **4. Verificar tracking_data no Redis**

Usar o `tracking_token` do Payment:

```python
import redis
import json

redis_conn = redis.from_url('redis://localhost:6379/0')
tracking_token = '[TRACKING_TOKEN_DO_PAYMENT]'

tracking_data = redis_conn.get(f"tracking:{tracking_token}")
if tracking_data:
    data = json.loads(tracking_data)
    print(f"UTMs no Redis:")
    print(f"  utm_source: {data.get('utm_source')}")
    print(f"  utm_campaign: {data.get('utm_campaign')}")
    print(f"  grim: {data.get('grim')}")
    print(f"  campaign_code: {data.get('campaign_code')}")
else:
    print("❌ tracking_data NÃO encontrado no Redis!")
```

### ✅ **5. Verificar Logs do Purchase**

Procurar nos logs por estas mensagens:

**Se Purchase foi enviado:**
```
[META PURCHASE] Purchase - Iniciando send_meta_pixel_purchase_event
📤 Purchase ENVIADO: {payment_id} | Events Received: {count}
```

**Se Purchase foi bloqueado:**
```
❌ PROBLEMA RAIZ: Meta tracking DESABILITADO
❌ PROBLEMA RAIZ: Evento Purchase DESABILITADO
❌ PROBLEMA RAIZ: Pool sem pixel_id ou access_token
❌ PROBLEMA RAIZ: Bot não está associado a nenhum pool
```

**Se UTMs estão ausentes:**
```
❌ [CRÍTICO] Purchase SEM UTMs e SEM campaign_code!
⚠️ ATENÇÃO: Esta venda NÃO será atribuída à campanha no Meta Ads Manager!
```

## 🚨 PRÓXIMOS PASSOS

1. **Coletar dados de uma venda específica que não foi marcada:**
   - Payment ID
   - Pool ID
   - Bot ID
   - Tracking Token

2. **Verificar cada item do checklist acima**

3. **Analisar logs do redirect e do Purchase**

4. **Implementar correções baseadas nos problemas encontrados**

## 📝 NOTA IMPORTANTE

O código já tem fallbacks robustos para recuperar UTMs. Se ainda assim as vendas não estão sendo marcadas, o problema provavelmente está em uma das seguintes áreas:

1. **Configuração do Pool:** Meta Pixel não configurado ou Purchase desabilitado
2. **URL de Redirect:** UTMs não estão na URL original
3. **Timing:** Redis pode ter expirado antes do Purchase ser enviado

**RECOMENDAÇÃO:** Use os logs detalhados para identificar exatamente onde os UTMs estão sendo perdidos.

