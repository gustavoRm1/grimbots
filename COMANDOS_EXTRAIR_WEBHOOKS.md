# 📥 EXTRAIR WEBHOOKS - PAGAMENTOS DESINCRONIZADOS

## Objetivo
Extrair os webhooks recebidos dos 10 pagamentos desincronizados para verificar se o **GATEWAY retornou 'paid'**.

**Se o webhook retornou 'paid', então o GATEWAY confirmou o pagamento**, mesmo que o painel mostre 'WAITING_PAYMENT'.

---

## ✅ EXECUTAR EXTRAÇÃO

```bash
cd ~/grimbots
source venv/bin/activate
python3 scripts/extrair_webhooks_pagamentos_desincronizados.py
```

---

## 📊 O QUE O SCRIPT FAZ

1. ✅ Busca os 10 pagamentos desincronizados (PAGOS no sistema, mas não na lista de pagos do gateway)
2. ✅ Para cada pagamento, busca webhooks recebidos
3. ✅ Mostra o payload completo do webhook
4. ✅ Verifica se o webhook retornou `paid`
5. ✅ Exporta dados para JSON (para conversar com o gateway)

---

## 🎯 RESULTADO ESPERADO

### Cenário 1: Webhook Retornou 'paid' ✅
```
✅ GATEWAY RETORNOU 'PAID' NO WEBHOOK!
🎯 CONCLUSÃO: Gateway CONFIRMOU o pagamento via webhook
⚠️  Se o painel mostra 'WAITING_PAYMENT', é problema de delay/sincronização do painel
```

**Ação:** Usar o payload do webhook como evidência para o gateway.

### Cenário 2: Sem Webhook ❌
```
❌ NENHUM webhook encontrado para este pagamento!
🚨 Isso indica que:
   - Webhook não foi enviado pelo gateway
   - OU webhook foi enviado mas não foi processado
   - OU pagamento foi marcado como pago via botão 'Verificar Pagamento'
```

**Ação:** Investigar se botão "Verificar Pagamento" foi usado.

---

## 📋 ARQUIVO JSON GERADO

O script gera um arquivo JSON em `exports/webhooks_desincronizados_TIMESTAMP.json` com:
- Payload completo de cada webhook
- Status retornado pelo gateway
- Dados do pagamento
- Timestamp do webhook

**Use este arquivo para conversar com o gateway UmbrellaPay!**

---

## 🔍 ANÁLISE DA SUA IDEIA

### ✅ **VOCÊ ESTÁ CORRETO!**

**Se o webhook retornou 'paid', então:**
1. ✅ O gateway **CONFIRMOU** o pagamento
2. ✅ O pagamento está **REALMENTE PAGO** no gateway
3. ⚠️  Se o painel mostra 'WAITING_PAYMENT', é problema de:
   - Delay na atualização do painel
   - Cache do painel
   - Sincronização entre API e painel

**Isso muda completamente a análise!**

### **Cenário Real:**

1. Cliente paga PIX
2. Gateway processa pagamento
3. Gateway envia webhook com `status: "PAID"`
4. Sistema recebe webhook e marca como `paid`
5. **Painel do gateway ainda mostra 'WAITING_PAYMENT'** (delay/cache)
6. **Resultado:** Pagamento está PAGO, mas painel não atualizou

**Conclusão:** O problema é do **painel do gateway**, não do nosso sistema!

---

## 📋 PRÓXIMOS PASSOS

1. ✅ Executar script de extração
2. ✅ Verificar quantos webhooks retornaram 'paid'
3. ✅ Usar payloads como evidência para o gateway
4. ✅ Solicitar correção do delay no painel

---

**Status:** 🔍 **Aguardando extração de webhooks**  
**Próximo:** Executar script e verificar se gateway confirmou via webhook

