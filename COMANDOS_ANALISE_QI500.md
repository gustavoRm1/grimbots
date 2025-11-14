# 🔍 ANÁLISE COMPLETA QI 500 - UMBRELLAPAY

## Objetivo
Análise rigorosa comparando TODOS os PIX gerados no sistema com as vendas pagas no gateway.

## Vendas Pagas no Gateway (Fonte da Verdade)
**Total: 5 transações - R$ 260,63**

1. `78366e3e-999b-4a5a-8232-3e442bd480eb` - R$ 32,86 - Samuel
2. `5561f532-9fc2-40f9-bdd6-132be6769bbc` - R$ 14,97 - Rodrigo
3. `1a71167d-62ea-4ac5-a088-925e5878d0c9` - R$ 32,86
4. `f0212d7f-269e-49dd-aeea-212a521d2fe1` - R$ 177,94 - CRÍTICA
5. `63a02dd9-1d70-48ac-8036-4eff20350d2b` - R$ 2,00 - Za Ya

---

## ✅ EXECUTAR ANÁLISE COMPLETA

### Versão V2 (Recomendada - Inclui TODAS as vendas)

```bash
cd ~/grimbots
source venv/bin/activate
export ENCRYPTION_KEY=$(grep ENCRYPTION_KEY .env | cut -d '=' -f2)
python3 scripts/analise_completa_umbrellapay_qi500_v2.py
```

### Versão Original (Apenas vendas pagas)

```bash
cd ~/grimbots
source venv/bin/activate
export ENCRYPTION_KEY=$(grep ENCRYPTION_KEY .env | cut -d '=' -f2)
python3 scripts/analise_completa_umbrellapay_qi500.py
```

---

## 📊 O QUE A ANÁLISE FAZ

### FASE 1: Buscar Todos os Pagamentos
- Busca TODOS os pagamentos UmbrellaPay no sistema (últimos 2 dias)
- Mapeia por `gateway_transaction_id` e CPF

### FASE 2: Comparar Cada Venda do Gateway
- Para cada venda paga no gateway:
  - Busca por `gateway_transaction_id` exato
  - Busca por `gateway_transaction_id` alternativo (para transação crítica)
  - Busca por CPF e valor aproximado
  - Busca por CPF parcial (caso truncado)

### FASE 3: Classificar Resultados
- ✅ **CORRETAS**: Gateway PAGO = Sistema PAGO
- ⚠️  **PENDENTES NO SISTEMA**: Gateway PAGO mas Sistema PENDENTE (BUG!)
- ❌ **NÃO ENCONTRADAS**: Gateway PAGO mas não existe no sistema
- ⚠️  **VALORES DIFERENTES**: Gateway PAGO mas valor diferente

### FASE 4: Análise Reversa
- Identifica pagamentos PAGOS no sistema que NÃO estão no gateway
- Pode indicar pagamentos que foram marcados como pagos incorretamente

### FASE 5: Relatório Final
- Estatísticas completas
- Taxa de acerto
- Conclusão e recomendações

---

## 🎯 RESULTADO ESPERADO

### Cenário Ideal:
- ✅ Todas as 5 transações encontradas
- ✅ Todas com status `paid`
- ✅ Valores corretos
- ✅ Taxa de acerto: 100%

### Possíveis Problemas:

#### 1. Transações PENDENTES no Sistema (BUG CRÍTICO)
**Causa:** Webhook não processou corretamente
**Solução:** 
- Verificar logs de webhook
- Reprocessar webhook manualmente
- Marcar como pago manualmente (se confirmado)

#### 2. Transações NÃO ENCONTRADAS
**Causa:** Webhook nunca foi recebido ou pagamento não foi criado
**Solução:**
- Verificar se webhook foi enviado pelo gateway
- Verificar logs de criação de pagamento
- Criar pagamento manualmente (se necessário)

#### 3. Valores Diferentes
**Causa:** Taxa ou arredondamento
**Solução:** Verificar se diferença é aceitável (< R$ 0,10)

---

## 🚨 AÇÕES SE HOUVER PROBLEMAS

### 1. Verificar Logs de Webhook

```bash
# Buscar por gateway_id específico
grep -i "78366e3e-999b-4a5a-8232-3e442bd480eb" logs/rq-webhook.log

# Ver todos os webhooks UmbrellaPay
tail -100 logs/rq-webhook.log | grep -i "umbrella"
```

### 2. Verificar Pagamentos Pendentes

```bash
export PGPASSWORD=123sefudeu
psql -U grimbots -d grimbots -c "
SELECT 
    payment_id,
    gateway_transaction_id,
    status,
    amount,
    customer_user_id,
    created_at
FROM payments
WHERE gateway_type = 'umbrellapag'
  AND status = 'pending'
  AND created_at >= NOW() - INTERVAL '2 days'
ORDER BY created_at DESC;
"
```

### 3. Marcar como Pago Manualmente (APENAS SE CONFIRMADO)

```bash
export PGPASSWORD=123sefudeu
psql -U grimbots -d grimbots -c "
UPDATE payments
SET status = 'paid',
    paid_at = NOW()
WHERE payment_id = 'PAYMENT_ID_AQUI'
  AND gateway_type = 'umbrellapag';
"
```

---

## 📋 CHECKLIST PÓS-ANÁLISE

- [ ] Executar análise completa
- [ ] Verificar transações CORRETAS
- [ ] Identificar transações PENDENTES (se houver)
- [ ] Identificar transações NÃO ENCONTRADAS (se houver)
- [ ] Verificar logs de webhook para problemas
- [ ] Reprocessar webhooks pendentes (se necessário)
- [ ] Marcar como pago manualmente (apenas se confirmado)

---

**Status:** 🔍 **Aguardando análise**  
**Próximo:** Executar script e identificar problemas

