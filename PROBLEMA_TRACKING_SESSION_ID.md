# 🔴 PROBLEMA IDENTIFICADO - TRACKING_SESSION_ID AUSENTE

## 📊 **SITUAÇÃO ATUAL**

**Payment 9326:**
- ❌ `tracking_token`: NONE
- ❌ `utm_source`: NONE
- ❌ `utm_campaign`: NONE
- ❌ `campaign_code`: NONE
- ❌ `pageview_event_id`: NONE
- ❌ `bot_user.tracking_session_id`: NONE

**Resultado**: Purchase via CAPI não pode ser enviado com atribuição de campanha.

---

## 🔍 **CAUSA RAIZ**

O `tracking_session_id` é salvo no `bot_user` **APENAS** quando:
1. Usuário passa pelo redirect (`/go/{slug}`)
2. Usuário clica no botão "Abrir no Telegram" (que inclui `start_param` com `tracking_token`)
3. Usuário envia `/start` no bot (com `start_param`)

**Se o usuário acessar o bot diretamente** (sem passar pelo redirect), o `tracking_session_id` **NÃO será salvo**.

---

## ✅ **SOLUÇÃO PROPOSTA**

### **OPÇÃO 1: Salvar `tracking_session_id` no redirect (RECOMENDADO)**

Modificar `public_redirect` em `app.py` para salvar `tracking_session_id` no `bot_user` quando:
- Usuário passa pelo redirect
- `bot_user` já existe (criado anteriormente)
- `tracking_token` está disponível

**Vantagem**: Garante que `tracking_session_id` seja salvo mesmo se usuário não enviar `/start` com `start_param`.

### **OPÇÃO 2: Recuperar `tracking_token` via `fbclid` no `_generate_pix_payment`**

Já implementado, mas **não funciona** se:
- `tracking:fbclid:{fbclid}` não existe no Redis (token expirou ou não foi salvo)
- Usuário não passou pelo redirect

**Limitação**: Depende do Redis não expirar.

### **OPÇÃO 3: Salvar `tracking_session_id` quando `bot_user` é criado/atualizado**

Modificar `process_start_async` em `tasks_async.py` para:
- Sempre tentar recuperar `tracking_token` via `fbclid` do `bot_user`
- Salvar `tracking_session_id` mesmo se `start_param` não tiver `tracking_token`

**Vantagem**: Funciona mesmo se usuário acessar bot diretamente (mas só se `fbclid` estiver no `bot_user`).

---

## 🎯 **RECOMENDAÇÃO FINAL**

**Implementar OPÇÃO 1 + OPÇÃO 3**:

1. **OPÇÃO 1**: Salvar `tracking_session_id` no redirect quando `bot_user` já existe
2. **OPÇÃO 3**: Tentar recuperar `tracking_token` via `fbclid` quando `bot_user` é criado/atualizado

Isso garante que `tracking_session_id` seja salvo em **múltiplos pontos**, aumentando a chance de sucesso.

---

## 📋 **PRÓXIMOS PASSOS**

1. ✅ Verificar se `bot_user` tem `fbclid` salvo
2. ✅ Tentar recuperar `tracking_token` via `fbclid` do `bot_user`
3. ✅ Se encontrar, atualizar `bot_user.tracking_session_id` e `payment.tracking_token`
4. ✅ Implementar OPÇÃO 1 + OPÇÃO 3 para prevenir problema futuro

---

## ⚠️ **LIMITAÇÃO ATUAL**

**Se o usuário NÃO passou pelo redirect**, não há como recuperar `tracking_data` porque:
- `tracking_token` não foi gerado
- `tracking_data` não foi salvo no Redis
- `bot_user.tracking_session_id` não foi salvo

**Solução**: Garantir que usuários sempre passem pelo redirect antes de acessar o bot.

