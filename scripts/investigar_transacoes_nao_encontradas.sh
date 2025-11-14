#!/bin/bash
# Script para investigar transações não encontradas do UmbrellaPay
# Data: 2025-11-14

echo "=========================================="
echo "  INVESTIGAÇÃO - TRANSAÇÕES NÃO ENCONTRADAS"
echo "=========================================="

export PGPASSWORD=123sefudeu

# IDs das transações não encontradas
IDS_NAO_ENCONTRADAS=(
    "722664db-384a-4342-94cf-603c0eea2702"
    "80211675-fdd4-4edc-9af2-f719278b08ad"
    "b425c8ba-accf-42a8-8bf7-734bbc6145f0"
    "358d6cb7-84eb-49f7-b9fe-0adbb67377f2"
    "df22dff0-388e-4a20-8161-a541fe72fd98"
    "f68dd1f7-700c-4de4-b626-d05c2136ffea"
    "62d3863f-e747-4b67-92de-a49689bd6bbe"
    "fd2ffd9e-ac58-44a0-b0d0-9cf28cf64b99"
    "f0212d7f-269e-49dd-aeea-212a521d2e1"
    "828b626d-b31e-4405-9607-303331b36ef0"
)

echo ""
echo "1. VERIFICANDO POR GATEWAY_TRANSACTION_ID:"
echo "---------------------------------------"
for id in "${IDS_NAO_ENCONTRADAS[@]}"; do
    echo ""
    echo "Gateway ID: $id"
    psql -U grimbots -d grimbots -c "
    SELECT 
        payment_id,
        gateway_transaction_id,
        gateway_transaction_hash,
        status,
        amount,
        customer_user_id,
        customer_name,
        created_at
    FROM payments
    WHERE gateway_transaction_id = '$id'
       OR gateway_transaction_hash = '$id'
       OR gateway_transaction_id LIKE '%$id%'
       OR gateway_transaction_hash LIKE '%$id%';
    " 2>/dev/null || echo "  Nenhum resultado encontrado"
done

echo ""
echo "2. VERIFICANDO POR CPF E VALOR:"
echo "---------------------------------------"
echo ""
echo "CPF: 72037508174 (Valor: R$ 14,97)"
psql -U grimbots -d grimbots -c "
SELECT 
    payment_id,
    gateway_transaction_id,
    status,
    amount,
    customer_user_id,
    customer_name,
    created_at
FROM payments
WHERE customer_user_id LIKE '%72037508174%'
  AND gateway_type = 'umbrellapag'
  AND amount BETWEEN 14.90 AND 15.00
ORDER BY created_at DESC;
"

echo ""
echo "CPF: 16147722140 (Valor: R$ 24,87)"
psql -U grimbots -d grimbots -c "
SELECT 
    payment_id,
    gateway_transaction_id,
    status,
    amount,
    customer_user_id,
    customer_name,
    created_at
FROM payments
WHERE customer_user_id LIKE '%16147722140%'
  AND gateway_type = 'umbrellapag'
  AND amount BETWEEN 24.80 AND 24.90
ORDER BY created_at DESC;
"

echo ""
echo "CPF: 21064388156 (Valores: R$ 14,97, R$ 19,97, R$ 32,86)"
psql -U grimbots -d grimbots -c "
SELECT 
    payment_id,
    gateway_transaction_id,
    status,
    amount,
    customer_user_id,
    customer_name,
    created_at
FROM payments
WHERE customer_user_id LIKE '%21064388156%'
  AND gateway_type = 'umbrellapag'
ORDER BY created_at DESC;
"

echo ""
echo "CPF: 76664441926 (Valor: R$ 177,94) - CRÍTICO"
psql -U grimbots -d grimbots -c "
SELECT 
    payment_id,
    gateway_transaction_id,
    status,
    amount,
    customer_user_id,
    customer_name,
    created_at
FROM payments
WHERE customer_user_id LIKE '%76664441926%'
  AND gateway_type = 'umbrellapag'
  AND amount BETWEEN 177.90 AND 178.00
ORDER BY created_at DESC;
"

echo ""
echo "CPF: 88008017570 (Valor: R$ 19,97)"
psql -U grimbots -d grimbots -c "
SELECT 
    payment_id,
    gateway_transaction_id,
    status,
    amount,
    customer_user_id,
    customer_name,
    created_at
FROM payments
WHERE customer_user_id LIKE '%88008017570%'
  AND gateway_type = 'umbrellapag'
  AND amount BETWEEN 19.90 AND 20.00
ORDER BY created_at DESC;
"

echo ""
echo "3. VERIFICANDO LOGS DE WEBHOOK:"
echo "---------------------------------------"
echo ""
echo "Buscando nos logs de webhook..."
for id in "${IDS_NAO_ENCONTRADAS[@]}"; do
    if grep -q "$id" logs/rq-webhook.log 2>/dev/null; then
        echo "✅ Gateway ID $id encontrado nos logs de webhook"
        grep "$id" logs/rq-webhook.log | tail -3
    else
        echo "❌ Gateway ID $id NÃO encontrado nos logs de webhook"
    fi
done

echo ""
echo "4. VERIFICANDO TODAS AS TRANSAÇÕES DO UMBRELLAPAY:"
echo "---------------------------------------"
psql -U grimbots -d grimbots -c "
SELECT 
    COUNT(*) as total_transacoes,
    COUNT(CASE WHEN gateway_transaction_id IS NOT NULL THEN 1 END) as com_gateway_id,
    COUNT(CASE WHEN gateway_transaction_hash IS NOT NULL THEN 1 END) as com_gateway_hash,
    COUNT(CASE WHEN status = 'paid' THEN 1 END) as pagas,
    COUNT(CASE WHEN status = 'pending' THEN 1 END) as pendentes
FROM payments
WHERE gateway_type = 'umbrellapag';
"

echo ""
echo "=========================================="
echo "  INVESTIGAÇÃO CONCLUÍDA"
echo "=========================================="

