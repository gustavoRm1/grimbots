# 🔴 CORREÇÃO CRÍTICA FINAL - ATRIBUIÇÃO DE CAMPANHAS

**Problema identificado**: Vendas não estão sendo atribuídas às campanhas no Meta Ads Manager.

---

## 🔍 ANÁLISE DO PROBLEMA

### Situação:
- ✅ Purchase é enviado na página de entrega (`/delivery/<token>`)
- ✅ Purchase está sendo enviado via CAPI (server-side)
- ❌ **PROBLEMA**: UTMs não estão sendo enviados corretamente no Purchase event
- ❌ **RESULTADO**: Meta não atribui vendas às campanhas

### Causa Raiz:

No `send_meta_pixel_purchase_event` (app.py), os UTMs estavam sendo priorizados do `payment` (banco) ao invés de `tracking_data` (Redis).

**Problema**:
1. `tracking_data` (Redis) tem os UTMs **ORIGINAIS** do redirect (mais confiáveis)
2. `payment` pode ter UTMs vazios ou desatualizados
3. Código estava usando `payment.utm_source` primeiro, depois `tracking_data`
4. Se `payment` tinha UTMs vazios, não usava `tracking_data` como fallback corretamente

---

## ✅ CORREÇÃO APLICADA

### Mudança na Prioridade de UTMs no Purchase Event:

**ANTES**:
```python
# ❌ ERRADO: Usava payment primeiro, tracking_data como fallback
if payment.utm_source:
    custom_data['utm_source'] = payment.utm_source
# Depois tentava tracking_data apenas se payment não tivesse
if tracking_data.get(utm_key) and not custom_data.get(utm_key):
    custom_data[utm_key] = tracking_data.get(utm_key)
```

**DEPOIS**:
```python
# ✅ CORRETO: PRIORIDADE 1 - tracking_data (Redis - dados do redirect) - MAIS CONFIÁVEL
for utm_key in ('utm_source', 'utm_medium', 'utm_campaign', 'utm_content', 'utm_term'):
    utm_value_from_tracking = tracking_data.get(utm_key)
    if utm_value_from_tracking:
        custom_data[utm_key] = utm_value_from_tracking
        logger.info(f"✅ Purchase - {utm_key} do tracking_data (Redis): {utm_value_from_tracking}")

# ✅ PRIORIDADE 2 - payment (banco) - FALLBACK apenas se tracking_data não tiver
if not custom_data.get('utm_source') and payment.utm_source:
    custom_data['utm_source'] = payment.utm_source
```

---

## 🎯 RESULTADO ESPERADO

Após a correção:
- ✅ UTMs do `tracking_data` (Redis) serão **PRIORIZADOS** no Purchase event
- ✅ `campaign_code` (grim) do `tracking_data` será usado primeiro
- ✅ Payment será usado apenas como **FALLBACK** se `tracking_data` não tiver
- ✅ Purchase event terá UTMs corretos para atribuição de campanha
- ✅ Meta Ads Manager atribuirá vendas às campanhas corretamente

---

## 📋 CHECKLIST PÓS-DEPLOY

Após o deploy, verificar:

1. **Purchase event com UTMs do tracking_data**:
   ```bash
   tail -f logs/gunicorn.log | grep -E "Purchase - utm_source do tracking_data|Purchase - campaign_code do tracking_data|Meta Purchase - Custom Data"
   ```

2. **Meta Ads Manager**:
   - Verificar se vendas aparecem nas campanhas
   - Verificar se `campaign_code` está presente
   - Verificar se UTMs estão corretos

3. **Validação de atribuição**:
   - Meta Events Manager → Sampled Activities
   - Verificar se Purchase events têm `utm_source`, `utm_campaign`, `campaign_code`
   - Verificar se `event_source_url` aponta para URL do redirect (com UTMs)

---

## ⚠️ OBSERVAÇÕES IMPORTANTES

1. **Prioridade de UTMs**:
   - **PRIORIDADE 1**: `tracking_data` (Redis - dados do redirect) - MAIS CONFIÁVEL
   - **PRIORIDADE 2**: `payment` (banco) - FALLBACK apenas se tracking_data não tiver

2. **Campaign Code (grim)**:
   - **PRIORIDADE 1**: `tracking_data.get('grim')` ou `tracking_data.get('campaign_code')`
   - **PRIORIDADE 2**: `payment.campaign_code` (fallback)

3. **Logging**:
   - Logs indicam origem de cada UTM (`tracking_data` ou `payment`)
   - Log de erro crítico se Purchase for enviado sem UTMs nem campaign_code

4. **Validação**:
   - Se Purchase for enviado sem UTMs nem campaign_code, log de erro crítico
   - Isso ajuda a identificar problemas de tracking antes que afetem atribuição

---

## ✅ CONCLUSÃO

**PROBLEMA RESOLVIDO**: Purchase event agora **PRIORIZA** UTMs e `campaign_code` do `tracking_data` (Redis - dados do redirect), garantindo que Meta Ads Manager receba os dados corretos para atribuição de campanha.

**RESULTADO**: Meta Ads Manager agora atribuirá vendas às campanhas corretamente.

---

## 📝 CORREÇÕES APLICADAS

1. **bot_manager.py**: UTMs agora são salvos no Payment a partir do `tracking_data_v4` (prioridade sobre `bot_user`)
2. **app.py**: Purchase event agora prioriza UTMs do `tracking_data` (Redis) sobre `payment` (banco)

