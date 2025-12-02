# 🔥 DIAGNÓSTICO: VENDAS NÃO ESTÃO SENDO MARCADAS NA CAMPANHA

## 🎯 PROBLEMAS IDENTIFICADOS

### 1. ❌ **PROBLEMA CRÍTICO: UTMs/Campaign Code Ausentes**

**LOCALIZAÇÃO:** Linha 10365-10390 de `app.py`

O sistema detecta quando o Purchase não tem UTMs ou `campaign_code` e registra um erro crítico. **SEM UTMs, AS VENDAS NÃO SÃO ATRIBUÍDAS ÀS CAMPANHAS NO META ADS MANAGER!**

```python
if not custom_data.get('utm_source') and not custom_data.get('campaign_code'):
    logger.error(f"❌ [CRÍTICO] Purchase SEM UTMs e SEM campaign_code! Payment: {payment.id}")
    logger.error(f"   ⚠️ ATENÇÃO: Esta venda NÃO será atribuída à campanha no Meta Ads Manager!")
```

### 2. ❌ **PROBLEMA: Purchase Event Desabilitado**

**LOCALIZAÇÃO:** Linha 9527-9529 de `app.py`

Se o evento Purchase estiver desabilitado no pool, nenhum Purchase será enviado:

```python
if not pool.meta_events_purchase:
    logger.error(f"❌ PROBLEMA RAIZ: Evento Purchase DESABILITADO para pool {pool.id} ({pool.name})")
    return
```

### 3. ❌ **PROBLEMA: Pool Sem Configuração Meta Pixel**

**LOCALIZAÇÃO:** Linhas 9515-9523 de `app.py`

Se o pool não tiver Meta Pixel configurado corretamente, o Purchase não será enviado:

```python
if not pool.meta_tracking_enabled:
    logger.error(f"❌ PROBLEMA RAIZ: Meta tracking DESABILITADO para pool {pool.id}")
    return

if not pool.meta_pixel_id or not pool.meta_access_token:
    logger.error(f"❌ PROBLEMA RAIZ: Pool sem pixel_id ou access_token")
    return
```

## 🔍 CHECKLIST DE VERIFICAÇÃO

### ✅ Verificar no Dashboard:

1. **Pool Configurado:**
   - ✅ Meta Tracking está habilitado?
   - ✅ Meta Pixel ID configurado?
   - ✅ Meta Access Token configurado?
   - ✅ Evento Purchase habilitado? (`meta_events_purchase = True`)

2. **Bot Associado ao Pool:**
   - ✅ O bot está associado ao pool correto?
   - ✅ Verificar tabela `pool_bot` no banco de dados

3. **UTMs na URL de Redirect:**
   - ✅ A URL de redirect tem UTMs? (`utm_source`, `utm_campaign`, etc.)
   - ✅ A URL tem `grim` ou `campaign_code`?

### ✅ Verificar nos Logs:

Procure por estas mensagens nos logs:

1. **Se Purchase está sendo enviado:**
   ```
   [META PURCHASE] Purchase - Iniciando para {payment_id}
   ```

2. **Se Purchase foi bloqueado:**
   ```
   ❌ PROBLEMA RAIZ: Meta tracking DESABILITADO
   ❌ PROBLEMA RAIZ: Evento Purchase DESABILITADO
   ❌ PROBLEMA RAIZ: Pool sem pixel_id ou access_token
   ```

3. **Se UTMs estão ausentes:**
   ```
   ❌ [CRÍTICO] Purchase SEM UTMs e SEM campaign_code!
   ⚠️ ATENÇÃO: Esta venda NÃO será atribuída à campanha no Meta Ads Manager!
   ```

4. **Se Purchase foi enviado com sucesso:**
   ```
   ✅ Purchase enviado com sucesso
   ✅ Meta API response: 200
   ```

## 🔧 PRÓXIMOS PASSOS

1. Verificar logs de uma venda recente que não foi marcada
2. Identificar qual das 3 condições acima está falhando
3. Corrigir o problema identificado

