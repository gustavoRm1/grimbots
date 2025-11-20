# 🚨 DIAGNÓSTICO - Webhooks não estão sendo enviados pelos gateways

## 🎯 PROBLEMA IDENTIFICADO

**Diagnóstico do script `verificar_webhook_venda_recente.sh`:**

- ❌ **Nenhum webhook real recebido** - apenas reconciliação (polling UmbrellaPag)
- ❌ **Nenhum log de "🔔 Webhook {gateway_type} recebido"** - POST não está chegando
- ❌ **Nenhuma venda nos últimos 90 minutos** - se houve venda, não foi salva ou foi antes

**Conclusão:** Gateways **NÃO estão enviando webhooks** ou não há vendas recentes.

---

## 🔍 ANÁLISE

### **Rota de Webhook (linha 9479):**

```python
@app.route('/webhook/payment/<string:gateway_type>', methods=['POST'])
def payment_webhook(gateway_type):
    """
    Webhook para confirmação de pagamento - QI 200 FAST MODE
    ✅ Retorna 200 IMEDIATAMENTE e processa em background
    """
    # ✅ QI 200: Log mínimo (reduzir 80% dos logs)
    logger.info(f"🔔 Webhook {gateway_type} recebido | content-type={request.content_type} | source={payload_source}")
```

**Problema:** Não há nenhum log com esse padrão ("🔔 Webhook {gateway_type} recebido"), o que significa que:
- ❌ Gateways **NÃO estão enviando webhooks**
- ❌ POST não está chegando em `/webhook/payment/<gateway_type>`

### **Gateway Types Identificados (do diagnóstico anterior):**

- `atomopay`: 2462 total, 304 paid
- `umbrellapag`: 138 total, 43 paid
- `paradise`: 45 total, 0 paid
- `pushynpay`: 1 total, 0 paid
- `orionpay`: 2 total, 0 paid

**Problema:** A maioria das vendas são via `atomopay` e `umbrellapag`, mas nenhum webhook está sendo recebido.

---

## 🔍 POSSÍVEIS CAUSAS

### **CAUSA 1: Gateways não estão configurados para enviar webhooks**

**Sintoma:**
- Webhook URL não está configurada no gateway
- Gateway não envia webhook quando payment é confirmado
- Apenas reconciliação (polling) processa pagamentos

**Verificação:**
- Verificar configuração do webhook no gateway (URL, método, formato)
- Verificar se gateway suporta webhooks

**Solução:**
- Configurar webhook URL no gateway: `https://app.grimbots.online/webhook/payment/{gateway_type}`
- Verificar se gateway está enviando webhooks

---

### **CAUSA 2: Webhook está sendo bloqueado/filtrado**

**Sintoma:**
- Gateway está enviando webhook mas não está chegando
- Firewall/reverso proxy bloqueando requisições
- Rate limiting bloqueando webhooks

**Verificação:**
- Verificar logs de acesso (nginx/apache)
- Verificar firewall/reverso proxy
- Verificar rate limiting

**Solução:**
- Verificar configuração do firewall/reverso proxy
- Verificar rate limiting (linha 9480: `@limiter.limit("500 per minute")`)

---

### **CAUSA 3: Não há vendas recentes**

**Sintoma:**
- Nenhuma venda encontrada nos últimos 90 minutos
- Mas usuário disse que "acabou de sair uma venda"

**Verificação:**
- Verificar vendas mais recentes (últimas 24h)
- Verificar se venda foi realmente criada
- Verificar se venda foi salva no banco

**Solução:**
- Verificar se venda foi realmente criada
- Verificar se venda está no banco
- Verificar gateway_type da venda

---

### **CAUSA 4: Webhook está sendo enviado mas falhando silenciosamente**

**Sintoma:**
- Webhook é recebido mas não é logado
- Erro está sendo capturado silenciosamente
- Webhook está falhando antes de logar

**Verificação:**
- Verificar logs de erro (nginx/apache)
- Verificar exception handlers
- Verificar se há erros silenciosos

**Solução:**
- Adicionar logging mais detalhado na rota de webhook
- Verificar exception handlers

---

## ✅ VERIFICAÇÃO NECESSÁRIA

Execute o script `verificar_venda_especifica.sh` para verificar:

1. ✅ Se há vendas recentes (últimas 24h)
2. ✅ Gateway_type das vendas
3. ✅ Se webhooks estão sendo enviados pelos gateways
4. ✅ Se há webhooks pendentes na fila RQ

---

## 📋 PRÓXIMOS PASSOS

1. ✅ **Execute o script** `verificar_venda_especifica.sh`:
   ```bash
   chmod +x verificar_venda_especifica.sh
   bash verificar_venda_especifica.sh
   ```

2. ✅ **Verifique se há vendas recentes** (seção 1 do script)

3. ✅ **Verifique gateway_type das vendas** (seção 4 do script)

4. ✅ **Verifique se gateways estão enviando webhooks**:
   - Verificar configuração do webhook no gateway
   - Verificar se webhook URL está correta: `https://app.grimbots.online/webhook/payment/{gateway_type}`

5. ✅ **Verifique se há webhooks pendentes na fila** (seção 5 do script)

---

## ⚠️ NOTAS IMPORTANTES

1. **Nenhum webhook real recebido:**
   - Apenas reconciliação (polling) está processando pagamentos
   - Gateways podem não estar configurados para enviar webhooks

2. **Reconciliação funciona mas é mais lenta:**
   - Reconciliação processa pagamentos via polling (consultas periódicas)
   - Webhooks são mais rápidos (confirmação imediata)

3. **Webhook URL esperada:**
   - `https://app.grimbots.online/webhook/payment/atomopay`
   - `https://app.grimbots.online/webhook/payment/umbrellapag`
   - `https://app.grimbots.online/webhook/payment/paradise`
   - etc.

---

## ✅ STATUS

- ✅ Problema identificado: Gateways não estão enviando webhooks
- ✅ Script de verificação criado
- ⚠️ **Aguardando execução do script e verificação de configuração dos gateways**

