# 🧪 PLANO DE TESTE COMPLETO - PATCH V16

## 📋 OBJETIVO

Validar que TODAS as correções do PATCH V16 estão funcionando corretamente e que tokens gerados NUNCA são usados ou salvos.

---

## 🧪 TESTE 1: PageView → Start → PIX → Purchase (Fluxo Normal)

### **Passos:**
1. Acessar `/go/red1?grim=teste&fbclid=PAZXh0bgNhZW0BMABhZGlkAasqUTTZ2yRz...`
2. Verificar logs: `tracking_token` gerado (UUID 32 chars)
3. Verificar Redis: `tracking:{token}` salvo com todos os dados
4. Verificar logs: PageView enviado com `pageview_event_id`
5. Clicar em `/start` no Telegram
6. Verificar logs: `process_start_async` recupera `tracking_token` do `start_param`
7. Verificar DB: `bot_user.tracking_session_id` = token UUID
8. Clicar em "Gerar PIX"
9. Verificar logs: `_generate_pix_payment` recupera `tracking_token` de `bot_user.tracking_session_id`
10. Verificar DB: Payment criado com `tracking_token` UUID
11. Simular webhook confirmando pagamento
12. Verificar logs: Purchase enviado com `pageview_event_id` reutilizado

### **Validações:**
- ✅ `tracking_token` é UUID (não gerado)
- ✅ `pageview_event_id` presente no Purchase
- ✅ Meta atribui venda corretamente

### **Comandos de Validação:**
```bash
# Verificar tracking_token no Redis
redis-cli GET "tracking:71ab1909f5d44c969241..."

# Verificar bot_user.tracking_session_id
psql -c "SELECT id, tracking_session_id FROM bot_users WHERE telegram_user_id = '123456789'"

# Verificar Payment.tracking_token
psql -c "SELECT id, tracking_token, pageview_event_id FROM payments WHERE customer_user_id = '123456789' ORDER BY created_at DESC LIMIT 1"

# Verificar logs de Purchase
tail -f logs/gunicorn.log | grep -i "\[META PURCHASE\]"
```

---

## 🧪 TESTE 2: PageView → Direct Purchase (sem /start)

### **Passos:**
1. Acessar `/go/red1?grim=teste&fbclid=PAZ...`
2. Verificar logs: `tracking_token` gerado (UUID 32 chars)
3. Tentar gerar PIX diretamente (sem /start)
4. Verificar logs: Sistema FALHA com erro claro

### **Validações:**
- ✅ Sistema FALHA se `tracking_token` ausente
- ✅ NUNCA gera novo token
- ✅ Erro claro: "tracking_token ausente - usuário deve acessar link de redirect primeiro"

### **Comandos de Validação:**
```bash
# Verificar logs de erro
tail -f logs/gunicorn.log | grep -i "tracking_token ausente"
```

---

## 🧪 TESTE 3: Token Gerado Detectado em bot_user.tracking_session_id

### **Passos:**
1. Simular `bot_user.tracking_session_id` com token gerado (`tracking_27ae841d7d6...`)
2. Tentar gerar PIX
3. Verificar logs: Sistema detecta token gerado
4. Verificar logs: Sistema tenta recuperar token UUID via `fbclid`
5. Se encontrar, atualizar `bot_user.tracking_session_id` com token UUID
6. Se não encontrar, logar warning crítico

### **Validações:**
- ✅ Token gerado detectado
- ✅ Sistema tenta recuperar token UUID
- ✅ `bot_user.tracking_session_id` atualizado com token UUID (se encontrado)

### **Comandos de Validação:**
```bash
# Simular token gerado no bot_user
psql -c "UPDATE bot_users SET tracking_session_id = 'tracking_27ae841d7d67527d98521' WHERE telegram_user_id = '123456789'"

# Tentar gerar PIX e verificar logs
tail -f logs/gunicorn.log | grep -i "token GERADO"
```

---

## 🧪 TESTE 4: Token Gerado no Redis (tracking:last_token)

### **Passos:**
1. Simular token gerado em `tracking:last_token:user:{customer_user_id}`
2. Tentar gerar PIX
3. Verificar logs: Sistema detecta token gerado
4. Verificar logs: Sistema IGNORA token gerado
5. Verificar logs: Sistema FALHA com erro claro

### **Validações:**
- ✅ Token gerado detectado em `tracking:last_token`
- ✅ Sistema IGNORA token gerado
- ✅ Sistema FALHA com erro claro

### **Comandos de Validação:**
```bash
# Simular token gerado no Redis
redis-cli SET "tracking:last_token:user:123456789" "tracking_27ae841d7d67527d98521"

# Tentar gerar PIX e verificar logs
tail -f logs/gunicorn.log | grep -i "Token recuperado de tracking:last_token é GERADO"
```

---

## 🧪 TESTE 5: Token Gerado no Redis (tracking:chat)

### **Passos:**
1. Simular token gerado em `tracking:chat:{customer_user_id}`
2. Tentar gerar PIX
3. Verificar logs: Sistema detecta token gerado
4. Verificar logs: Sistema IGNORA token gerado
5. Verificar logs: Sistema FALHA com erro claro

### **Validações:**
- ✅ Token gerado detectado em `tracking:chat`
- ✅ Sistema IGNORA token gerado
- ✅ Sistema FALHA com erro claro

### **Comandos de Validação:**
```bash
# Simular token gerado no Redis
redis-cli SET "tracking:chat:123456789" '{"tracking_token": "tracking_27ae841d7d67527d98521", "fbclid": "PAZ..."}'

# Tentar gerar PIX e verificar logs
tail -f logs/gunicorn.log | grep -i "Token recuperado de tracking:chat é GERADO"
```

---

## 🧪 TESTE 6: Tentativa de Salvar Token Gerado no Redis

### **Passos:**
1. Simular tentativa de salvar token gerado via `save_tracking_token()`
2. Verificar logs: Sistema detecta token gerado
3. Verificar logs: Sistema NÃO salva token gerado
4. Verificar Redis: Token gerado NÃO está salvo

### **Validações:**
- ✅ Token gerado detectado antes de salvar
- ✅ Sistema NÃO salva token gerado em `tracking:fbclid`
- ✅ Sistema NÃO salva token gerado em `tracking:chat`
- ✅ Sistema NÃO salva token gerado em `tracking:last_token`

### **Comandos de Validação:**
```bash
# Verificar logs de erro
tail -f logs/gunicorn.log | grep -i "tracking_token é GERADO - NÃO salvar"

# Verificar Redis (não deve ter token gerado)
redis-cli GET "tracking:fbclid:PAZ..."
redis-cli GET "tracking:chat:123456789"
redis-cli GET "tracking:last_token:user:123456789"
```

---

## 🧪 TESTE 7: Fluxo Completo com Múltiplos Redirections

### **Passos:**
1. Acessar `/go/red1?grim=teste&fbclid=PAZ...` (primeira vez)
2. Verificar: `tracking_token_1` gerado
3. Acessar `/go/red1?grim=teste&fbclid=PAZ...` (segunda vez)
4. Verificar: `tracking_token_2` gerado (diferente)
5. Clicar em `/start` no Telegram
6. Verificar: `bot_user.tracking_session_id` = `tracking_token_2`
7. Gerar PIX
8. Verificar: Payment usa `tracking_token_2`

### **Validações:**
- ✅ Cada redirect gera novo token
- ✅ `bot_user.tracking_session_id` sempre atualizado com token mais recente
- ✅ Purchase usa token mais recente

---

## 🧪 TESTE 8: Webhook com Token UUID Válido

### **Passos:**
1. Payment criado com `tracking_token` UUID ✅
2. Simular webhook confirmando pagamento
3. Verificar logs: Purchase enviado com `tracking_token` UUID
4. Verificar logs: `pageview_event_id` reutilizado

### **Validações:**
- ✅ Purchase sempre usa `tracking_token` do Payment
- ✅ `pageview_event_id` sempre presente
- ✅ Meta atribui venda corretamente

---

## 📊 CHECKLIST DE VALIDAÇÃO

### **Geração:**
- [ ] ✅ `tracking_token` gerado APENAS em `/go/{slug}`
- [ ] ✅ Método `generate_tracking_token()` deprecated (lança exceção)
- [ ] ✅ Nenhum outro ponto gera token

### **Validação:**
- [ ] ✅ `tracking_elite.session_id` validado antes de salvar
- [ ] ✅ Tokens recuperados de `tracking:last_token` validados
- [ ] ✅ Tokens recuperados de `tracking:chat` validados
- [ ] ✅ Tokens recuperados de `tracking:fbclid` validados

### **Salvamento:**
- [ ] ✅ Tokens validados ANTES de salvar em `tracking:chat` (2 pontos)
- [ ] ✅ Tokens validados ANTES de salvar em `tracking:fbclid`
- [ ] ✅ Tokens validados ANTES de salvar em `tracking:last_token`
- [ ] ✅ Token gerado NUNCA é salvo no Redis

### **Uso:**
- [ ] ✅ Token gerado NUNCA é usado (mesmo se recuperado)
- [ ] ✅ Sistema FALHA se `tracking_token` ausente (não gera novo)
- [ ] ✅ Purchase sempre usa token UUID válido

---

## ✅ RESULTADO ESPERADO

**TODOS OS TESTES DEVEM PASSAR:**
- ✅ Token gerado NUNCA é usado
- ✅ Token gerado NUNCA é salvo no Redis
- ✅ Sistema 100% protegido contra tokens gerados
- ✅ Purchase sempre encontra dados completos
- ✅ Meta atribui vendas corretamente

---

**PLANO DE TESTE COMPLETO! ✅**

