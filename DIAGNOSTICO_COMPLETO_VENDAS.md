# 🔥 DIAGNÓSTICO COMPLETO: VENDAS NÃO MARCADAS NA CAMPANHA

## 🎯 ANÁLISE PROFUNDA - QI 500

### 📊 FLUXO COMPLETO DO TRACKING

```
1. REDIRECT (/go/{pool-slug})
   ├─ Captura UTMs da URL (linha 5565-5572)
   ├─ Salva tracking_payload no Redis (linha 5618)
   │  └─ Contém: fbclid, fbp, fbc, UTMs, grim, pageview_event_id
   ├─ Envia PageView para Meta (linha 5645)
   └─ Faz MERGE e atualiza Redis (linhas 5658-5729)

2. PURCHASE (quando pagamento é confirmado)
   ├─ Recupera tracking_data do Redis (linhas 9620-9719)
   ├─ Recupera UTMs do tracking_data (linha 10330-10339)
   ├─ Fallback: UTMs do payment (linha 10342-10361)
   ├─ Fallback: UTMs do bot_user (linha 10393-10402)
   └─ Envia Purchase para Meta (linha 10604-10612)
```

### ❌ PROBLEMAS IDENTIFICADOS

#### 1. **PROBLEMA CRÍTICO: UTMs Não Estão Sendo Salvos no Payment**

**LINHA:** Não encontrada - UTMs NÃO são salvos no Payment quando o pagamento é criado!

O código tenta recuperar UTMs do `payment.utm_source`, `payment.utm_campaign`, etc. (linha 10346-10361), mas **esses campos NUNCA são preenchidos** quando o pagamento é criado em `bot_manager._generate_pix_payment()`.

**SOLUÇÃO:** Salvar UTMs no Payment quando o pagamento é criado, recuperando do `tracking_token`.

#### 2. **PROBLEMA: UTMs Podem Estar Perdidos no Merge do PageView**

**LINHA:** 5658-5729

Se o PageView falhar ou o merge não preservar os UTMs, eles podem ser perdidos do `tracking_data`.

**SOLUÇÃO:** Garantir que o merge sempre preserve UTMs, mesmo quando `pageview_context` está vazio.

#### 3. **PROBLEMA: tracking_data Não Está Sendo Recuperado Corretamente**

**LINHAS:** 9620-9719

O Purchase tenta recuperar `tracking_data` do Redis usando várias prioridades, mas se o `tracking_token` estiver incorreto ou não existir no Redis, os UTMs serão perdidos.

**SOLUÇÃO:** Melhorar a recuperação de `tracking_data` e adicionar fallbacks robustos.

#### 4. **PROBLEMA: URL de Redirect Não Tem UTMs**

Se a URL de redirect não tiver UTMs, eles nunca serão salvos no `tracking_payload`.

**SOLUÇÃO:** Garantir que a URL de redirect sempre tenha UTMs quando for gerada.

## 🔧 CHECKLIST DE VERIFICAÇÃO

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

### ✅ **3. Verificar Tracking Token de uma Venda**

```sql
SELECT 
    p.id,
    p.payment_id,
    p.tracking_token,
    p.status,
    p.created_at,
    p.utm_source,
    p.utm_campaign,
    p.campaign_code
FROM payment p
WHERE p.id = [ID_DA_VENDA];
```

Verificar se `tracking_token` existe e se UTMs estão salvos no Payment.

### ✅ **4. Verificar tracking_data no Redis**

Usar o `tracking_token` do Payment e verificar no Redis:

```python
import redis
import json

redis_conn = redis.from_url('redis://localhost:6379/0')
tracking_token = '[TRACKING_TOKEN_DO_PAYMENT]'

tracking_data = redis_conn.get(f"tracking:{tracking_token}")
if tracking_data:
    data = json.loads(tracking_data)
    print(f"UTMs no Redis: utm_source={data.get('utm_source')}, utm_campaign={data.get('utm_campaign')}, grim={data.get('grim')}")
else:
    print("❌ tracking_data NÃO encontrado no Redis!")
```

## 🚨 PRÓXIMOS PASSOS

1. **Coletar logs de uma venda específica que não foi marcada**
2. **Verificar se o Purchase foi enviado (procurar nos logs)**
3. **Verificar se UTMs estão no Redis (usar script acima)**
4. **Implementar correção para salvar UTMs no Payment quando o pagamento é criado**

