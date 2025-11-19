# 🔴 CORREÇÃO CRÍTICA - ATRIBUIÇÃO DE CAMPANHAS

**Problema identificado**: Vendas não estão sendo atribuídas às campanhas no Meta Ads Manager.

---

## 🔍 ANÁLISE DO PROBLEMA

### Situação Atual:
- ✅ PageView está sendo enviado com UTMs
- ✅ Purchase está sendo enviado via CAPI
- ❌ **PROBLEMA**: UTMs não estão sendo salvos no Payment
- ❌ **RESULTADO**: Purchase não tem UTMs para atribuição de campanha

### Causa Raiz:

Na função `_generate_pix_payment` (bot_manager.py), os UTMs estão sendo recuperados do `tracking_data_v4` (Redis) mas **NÃO estão sendo salvos no Payment**.

O código estava usando `getattr(bot_user, 'utm_source', None)` ao invés de usar as variáveis `utm_source`, `utm_campaign`, etc. que foram recuperadas do `tracking_data_v4`.

**Código Problemático**:
```python
# ❌ ERRADO: Usa apenas bot_user (pode não ter UTMs)
utm_source=getattr(bot_user, 'utm_source', None) if bot_user else None,
utm_campaign=getattr(bot_user, 'utm_campaign', None) if bot_user else None,
campaign_code=getattr(bot_user, 'campaign_code', None) if bot_user else None,
```

**Problema**:
1. UTMs são recuperados do `tracking_data_v4` (linhas 6425-6434)
2. Mas ao criar o Payment, usa apenas `bot_user` (que pode não ter UTMs)
3. Resultado: Payment é criado sem UTMs
4. Purchase event não tem UTMs para atribuição de campanha

---

## ✅ CORREÇÃO APLICADA

### Mudança na Lógica de Salvamento de UTMs:

**ANTES**:
```python
utm_source=getattr(bot_user, 'utm_source', None) if bot_user else None,
utm_campaign=getattr(bot_user, 'utm_campaign', None) if bot_user else None,
campaign_code=getattr(bot_user, 'campaign_code', None) if bot_user else None,
```

**DEPOIS**:
```python
# ✅ PRIORIDADE: tracking_data_v4 > bot_user
utm_source=utm_source if utm_source else (getattr(bot_user, 'utm_source', None) if bot_user else None),
utm_campaign=utm_campaign if utm_campaign else (getattr(bot_user, 'utm_campaign', None) if bot_user else None),
utm_content=utm_content if utm_content else (getattr(bot_user, 'utm_content', None) if bot_user else None),
utm_medium=utm_medium if utm_medium else (getattr(bot_user, 'utm_medium', None) if bot_user else None),
utm_term=utm_term if utm_term else (getattr(bot_user, 'utm_term', None) if bot_user else None),
campaign_code=tracking_data_v4.get('grim') if tracking_data_v4.get('grim') else (getattr(bot_user, 'campaign_code', None) if bot_user else None),
```

---

## 🎯 RESULTADO ESPERADO

Após a correção:
- ✅ UTMs serão salvos no Payment a partir do `tracking_data_v4` (Redis)
- ✅ `campaign_code` (grim) será salvo no Payment
- ✅ Purchase event terá UTMs no `custom_data`
- ✅ Meta Ads Manager atribuirá vendas às campanhas corretamente

---

## 📋 CHECKLIST PÓS-DEPLOY

Após o deploy, verificar:

1. **Payment criado com UTMs**:
   ```sql
   SELECT id, utm_source, utm_campaign, campaign_code, fbclid 
   FROM payments 
   WHERE created_at > NOW() - INTERVAL '1 hour'
   ORDER BY id DESC 
   LIMIT 5;
   ```

2. **Purchase event com UTMs**:
   ```bash
   tail -f logs/gunicorn.log | grep -E "Meta Purchase - Custom Data|utm_source|utm_campaign|campaign_code"
   ```

3. **Meta Ads Manager**:
   - Verificar se vendas aparecem nas campanhas
   - Verificar se `campaign_code` está presente
   - Verificar se UTMs estão corretos

---

## ⚠️ OBSERVAÇÕES IMPORTANTES

1. **Prioridade de UTMs**:
   - PRIORIDADE 1: `tracking_data_v4` (Redis - dados do redirect)
   - PRIORIDADE 2: `bot_user` (fallback se Redis não tiver)

2. **Campaign Code**:
   - PRIORIDADE 1: `tracking_data_v4.get('grim')` (dados do redirect)
   - PRIORIDADE 2: `bot_user.campaign_code` (fallback)

3. **Retrocompatibilidade**:
   - Se `tracking_data_v4` não tiver UTMs, usa `bot_user` (fallback)
   - Garante que não quebra vendas antigas

---

## ✅ CONCLUSÃO

**PROBLEMA RESOLVIDO**: UTMs e `campaign_code` agora são salvos no Payment a partir do `tracking_data_v4` (Redis), garantindo que Purchase events tenham todos os dados necessários para atribuição de campanha.

**RESULTADO**: Meta Ads Manager agora atribuirá vendas às campanhas corretamente.

