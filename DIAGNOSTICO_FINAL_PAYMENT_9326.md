# 🔴 DIAGNÓSTICO FINAL - PAYMENT 9326

## 📊 **STATUS ATUAL**

**Payment 9326:**
- ❌ `tracking_token`: NONE
- ❌ `utm_source`: NONE
- ❌ `utm_campaign`: NONE
- ❌ `campaign_code`: NONE
- ❌ `pageview_event_id`: NONE
- ⚠️ `fbclid`: `7501115620...` (parece ser `telegram_user_id`, não `fbclid` real)

**BotUser 37950:**
- ⚠️ `fbclid`: `7501115620...` (parece ser `telegram_user_id`, não `fbclid` real)
- ❌ `tracking_session_id`: NONE

**Redis:**
- ❌ `tracking:fbclid:7501115620...`: NÃO encontrado
- ❌ `tracking_token`: NÃO encontrado

---

## 🔍 **CAUSA RAIZ**

1. **Usuário NÃO passou pelo redirect** antes de gerar o PIX
   - Sem passar pelo redirect, `tracking_token` não é gerado
   - Sem `tracking_token`, `tracking_data` não é salvo no Redis
   - Sem `tracking_data`, UTMs não são salvos no Payment

2. **`fbclid` parece estar incorreto**
   - `fbclid` = `7501115620...` (parece ser `telegram_user_id`)
   - `fbclid` real do Facebook seria algo como: `IwAR1...` ou similar
   - Isso indica que `fbclid` foi salvo incorretamente ou não foi capturado

---

## ❌ **CONCLUSÃO**

**Para este payment específico, NÃO há como recuperar o tracking** porque:
- `tracking_token` não existe no Redis
- `tracking_data` não existe no Redis
- `fbclid` parece estar incorreto (não é um `fbclid` real do Facebook)

**Purchase via CAPI será enviado SEM atribuição de campanha** porque:
- Não há UTMs
- Não há `campaign_code`
- Não há `pageview_event_id` (deduplicação pode falhar)

---

## ✅ **SOLUÇÃO PREVENTIVA**

### **1. Implementar validação de `fbclid`**

Garantir que `fbclid` seja um valor válido do Facebook antes de salvar:
- `fbclid` do Facebook geralmente começa com `IwAR...` ou similar
- Não deve ser `telegram_user_id`

### **2. Implementar salvamento de `tracking_session_id` no redirect**

Modificar `public_redirect` em `app.py` para:
- Buscar `bot_user` existente quando usuário passa pelo redirect
- Salvar `tracking_session_id` no `bot_user` mesmo se não enviar `/start`
- Garantir que `tracking_session_id` seja salvo **em múltiplos pontos**

### **3. Adicionar validação antes de gerar PIX**

Modificar `_generate_pix_payment` em `bot_manager.py` para:
- Verificar se `bot_user.tracking_session_id` existe
- Se não existir, tentar recuperar via `fbclid`
- Se não encontrar, **WARNING** mas não bloquear (evitar perder venda)
- Logar claramente que Purchase terá atribuição reduzida

---

## 📋 **PRÓXIMOS PASSOS**

1. ✅ **Aceitar que este payment não terá atribuição** (já perdido)
2. ✅ **Implementar soluções preventivas** para evitar problema futuro
3. ✅ **Adicionar logs detalhados** para identificar quando tracking está ausente
4. ✅ **Monitorar Meta Events Manager** para verificar se Purchase foi enviado mesmo sem UTMs

---

## ⚠️ **RECOMENDAÇÃO**

**Para este payment específico**: Não há como recuperar tracking. Purchase será enviado sem atribuição de campanha.

**Para futuros payments**: Implementar soluções preventivas para garantir que `tracking_session_id` seja salvo sempre que possível.

