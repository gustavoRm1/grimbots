# 🔍 VERIFICAR TRANSAÇÕES UMBRELLAPAY
## Como identificar transações no sistema

**Data:** 2025-11-13  
**Status:** Scripts Prontos

---

## ⚡ EXECUTAR NA VPS (COMANDOS RÁPIDOS)

### 1. **Executar Script Python**
```bash
cd ~/grimbots
source venv/bin/activate
python scripts/verificar_transacoes_umbrella.py
```

### 2. **Verificar Resultados**
```bash
# Verificar CSVs gerados
ls -la exports/transacoes_*

# Ver conteúdo dos CSVs
head -5 exports/transacoes_pagas_*.csv
head -5 exports/transacoes_pendentes_*.csv
head -5 exports/transacoes_nao_encontradas_*.csv
```

---

## 📊 O QUE O SCRIPT FAZ

### 1. **Busca Transações**
- Busca por `gateway_transaction_id` (ID do gateway)
- Busca por `gateway_transaction_hash` (fallback)
- Busca por CPF e valor (fallback)
- Busca por telefone e valor (fallback)

### 2. **Separa Transações**
- ✅ **PAGAS (PAID)** - Transações encontradas com status `paid`
- ⚠️  **PENDENTES (PENDING)** - Transações encontradas com status `pending`
- ❌ **NÃO ENCONTRADAS** - Transações que não foram encontradas no sistema

### 3. **Compara Valores**
- Compara valor do gateway com valor do payment
- Identifica diferenças de valor

### 4. **Gera Relatórios**
- Mostra resumo no terminal
- Gera CSVs separados:
  - `transacoes_pagas_YYYY-MM-DD_HH-MM-SS.csv`
  - `transacoes_pendentes_YYYY-MM-DD_HH-MM-SS.csv`
  - `transacoes_nao_encontradas_YYYY-MM-DD_HH-MM-SS.csv`

---

## 📋 RESULTADO ESPERADO

### Resumo:
```
Total no Gateway: 58 transações - R$ XXXX.XX
✅ Encontradas (PAID): XX transações - R$ XXXX.XX
⚠️  Encontradas (PENDING): XX transações - R$ XXXX.XX
❌ Não Encontradas: XX transações - R$ XXXX.XX
🔴 Valores Diferentes: XX transações
```

### Detalhes:
- Lista completa de transações pagas
- Lista completa de transações pendentes
- Lista completa de transações não encontradas
- Lista de valores diferentes

---

## 🔍 VERIFICAÇÃO MANUAL (SQL)

### Buscar uma transação específica:
```bash
export PGPASSWORD=123sefudeu
psql -U grimbots -d grimbots -c "
SELECT 
    payment_id,
    gateway_transaction_id,
    gateway_transaction_hash,
    status,
    amount,
    customer_user_id,
    customer_name,
    customer_username,
    created_at,
    paid_at
FROM payments
WHERE gateway_transaction_id = '454ae28b-fafe-4248-aae5-12fada764bf5'
  AND gateway_type = 'umbrellapag';
"
```

### Buscar por CPF:
```bash
export PGPASSWORD=123sefudeu
psql -U grimbots -d grimbots -c "
SELECT 
    payment_id,
    gateway_transaction_id,
    status,
    amount,
    customer_user_id,
    customer_name,
    created_at,
    paid_at
FROM payments
WHERE customer_user_id LIKE '%04986407953%'
  AND gateway_type = 'umbrellapag'
ORDER BY created_at DESC;
"
```

### Buscar todas as transações do UmbrellaPay:
```bash
export PGPASSWORD=123sefudeu
psql -U grimbots -d grimbots -c "
SELECT 
    payment_id,
    gateway_transaction_id,
    status,
    amount,
    customer_user_id,
    customer_name,
    created_at,
    paid_at
FROM payments
WHERE gateway_type = 'umbrellapag'
ORDER BY created_at DESC
LIMIT 100;
"
```

---

## 🚨 ANÁLISE DE DISCREPÂNCIAS

### Se houver transações não encontradas:
1. **Verificar se o webhook foi recebido**
   - Verificar logs do webhook
   - Verificar se o `gateway_transaction_id` foi salvo corretamente

2. **Verificar se há duplicatas**
   - Verificar se a mesma transação aparece múltiplas vezes
   - Verificar se há conflitos de ID

3. **Verificar se o valor está correto**
   - Comparar valor do gateway com valor do payment
   - Verificar se há taxas ou descontos

### Se houver valores diferentes:
1. **Verificar taxas do gateway**
   - Verificar se há taxas aplicadas
   - Verificar se há descontos aplicados

2. **Verificar arredondamentos**
   - Verificar se há diferenças de arredondamento
   - Verificar se há conversões de moeda

---

## 📊 EXPORTAR RESULTADOS

### CSVs Gerados:
- `exports/transacoes_pagas_YYYY-MM-DD_HH-MM-SS.csv`
- `exports/transacoes_pendentes_YYYY-MM-DD_HH-MM-SS.csv`
- `exports/transacoes_nao_encontradas_YYYY-MM-DD_HH-MM-SS.csv`

### Baixar CSVs:
- Acessar `/admin/exports`
- Baixar os arquivos CSV gerados

---

## ✅ CHECKLIST

- [ ] ✅ Script executado com sucesso
- [ ] ✅ Transações identificadas
- [ ] ✅ Transações pagas separadas
- [ ] ✅ Transações pendentes separadas
- [ ] ✅ Transações não encontradas identificadas
- [ ] ✅ Valores comparados
- [ ] ✅ CSVs gerados
- [ ] ✅ Relatório analisado

---

**Status:** ✅ **Scripts Prontos**  
**Próximo:** Executar script na VPS e analisar resultados

