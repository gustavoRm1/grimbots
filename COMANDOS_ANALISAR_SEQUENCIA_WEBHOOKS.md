# 🔍 ANALISAR SEQUÊNCIA DE WEBHOOKS

## Objetivo
Verificar se houve webhook `PAID` antes de `WAITING_PAYMENT` para cada transaction_id.

**Isso vai revelar se:**
- Gateway enviou `PAID` e depois `WAITING_PAYMENT` (reversão?)
- Ou apenas `WAITING_PAYMENT` foi recebido (mas sistema marcou como `paid`)

---

## ✅ EXECUTAR ANÁLISE

```bash
cd ~/grimbots
source venv/bin/activate
python3 scripts/analisar_sequencia_webhooks.py
```

---

## 📊 O QUE O SCRIPT FAZ

1. ✅ Busca **TODOS** os webhooks para cada transaction_id
2. ✅ Ordena por data de recebimento (cronológico)
3. ✅ Mostra status no payload vs status salvo no DB
4. ✅ Identifica contradições
5. ✅ Detecta se houve webhook `PAID` antes de `WAITING_PAYMENT`

---

## 🎯 RESULTADO ESPERADO

### **Cenário 1: Webhook PAID Antes de WAITING_PAYMENT** ✅

```
📨 Webhook 1 (recebido em 2025-11-13 09:30:00):
   Status no payload: PAID
   Status salvo no DB: paid

📨 Webhook 2 (recebido em 2025-11-13 09:35:00):
   Status no payload: WAITING_PAYMENT
   Status salvo no DB: paid
   ⚠️  CONTRADIÇÃO DETECTADA!
```

**Conclusão:** Gateway enviou `PAID` primeiro, depois `WAITING_PAYMENT`. Sistema processou o `PAID` corretamente.

### **Cenário 2: Apenas WAITING_PAYMENT** ❌

```
📨 Webhook 1 (recebido em 2025-11-13 09:30:00):
   Status no payload: WAITING_PAYMENT
   Status salvo no DB: paid
   ⚠️  CONTRADIÇÃO DETECTADA!
```

**Conclusão:** Apenas `WAITING_PAYMENT` foi recebido, mas sistema marcou como `paid`. Possível uso do botão "Verificar Pagamento".

---

## 📋 PRÓXIMOS PASSOS

1. ✅ Executar script de análise
2. ✅ Verificar se houve webhook `PAID` anterior
3. ✅ Se sim: Gateway confirmou via webhook (problema é do painel)
4. ✅ Se não: Investigar botão "Verificar Pagamento"

---

**Status:** 🔍 **Aguardando análise de sequência**  
**Próximo:** Executar script e verificar se gateway enviou `PAID` antes

