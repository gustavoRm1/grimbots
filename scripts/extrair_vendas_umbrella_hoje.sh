#!/bin/bash
# Script para extrair todas as vendas do UmbrellaPay de hoje
# Data: 2025-11-13

echo "=========================================="
echo "  EXTRAÇÃO - VENDAS UMBRELLAPAY HOJE"
echo "=========================================="

export PGPASSWORD=123sefudeu

# Data de hoje
DATE_TODAY=$(date +%Y-%m-%d)
echo "Data: $DATE_TODAY"
echo ""

# 1. RESUMO ESTATÍSTICO
echo "1. RESUMO ESTATÍSTICO:"
echo "---------------------------------------"
psql -U grimbots -d grimbots -c "
SELECT 
    COUNT(*) as total_vendas,
    COUNT(CASE WHEN status = 'paid' THEN 1 END) as vendas_pagas,
    COUNT(CASE WHEN status = 'pending' THEN 1 END) as vendas_pendentes,
    COUNT(CASE WHEN status = 'failed' THEN 1 END) as vendas_falhadas,
    ROUND(SUM(CASE WHEN status = 'paid' THEN amount ELSE 0 END), 2) as valor_total_pago,
    ROUND(SUM(amount), 2) as valor_total_gerado,
    COUNT(CASE WHEN meta_purchase_sent = true THEN 1 END) as purchase_enviados,
    COUNT(CASE WHEN tracking_token IS NOT NULL THEN 1 END) as com_tracking_token,
    COUNT(CASE WHEN fbc IS NOT NULL THEN 1 END) as com_fbc,
    COUNT(CASE WHEN pageview_event_id IS NOT NULL THEN 1 END) as com_pageview_event_id
FROM payments
WHERE gateway_type = 'umbrellapag'
  AND created_at >= CURRENT_DATE
  AND created_at < CURRENT_DATE + INTERVAL '1 day';
"

echo ""
echo "2. TODAS AS VENDAS DO UMBRELLAPAY HOJE:"
echo "---------------------------------------"
psql -U grimbots -d grimbots -c "
SELECT 
    payment_id,
    status,
    amount,
    customer_user_id,
    tracking_token IS NOT NULL as has_token,
    pageview_event_id IS NOT NULL as has_pageview,
    fbp IS NOT NULL as has_fbp,
    fbc IS NOT NULL as has_fbc,
    meta_purchase_sent,
    created_at,
    paid_at
FROM payments
WHERE gateway_type = 'umbrellapag'
  AND created_at >= CURRENT_DATE
  AND created_at < CURRENT_DATE + INTERVAL '1 day'
ORDER BY created_at DESC;
"

echo ""
echo "3. VENDAS PAGAS DO UMBRELLAPAY HOJE:"
echo "---------------------------------------"
psql -U grimbots -d grimbots -c "
SELECT 
    payment_id,
    status,
    amount,
    customer_user_id,
    tracking_token,
    pageview_event_id,
    fbp IS NOT NULL as has_fbp,
    fbc IS NOT NULL as has_fbc,
    fbclid,
    utm_source,
    utm_campaign,
    campaign_code,
    meta_purchase_sent,
    meta_event_id,
    created_at,
    paid_at
FROM payments
WHERE gateway_type = 'umbrellapag'
  AND status = 'paid'
  AND paid_at >= CURRENT_DATE
  AND paid_at < CURRENT_DATE + INTERVAL '1 day'
ORDER BY paid_at DESC;
"

echo ""
echo "4. VENDAS PAGAS COM DETALHES COMPLETOS:"
echo "---------------------------------------"
psql -U grimbots -d grimbots -c "
SELECT 
    payment_id,
    status,
    amount,
    customer_name,
    customer_username,
    customer_user_id,
    product_name,
    tracking_token,
    pageview_event_id,
    fbp,
    fbc,
    fbclid,
    utm_source,
    utm_campaign,
    campaign_code,
    meta_purchase_sent,
    meta_event_id,
    meta_purchase_sent_at,
    created_at,
    paid_at
FROM payments
WHERE gateway_type = 'umbrellapag'
  AND status = 'paid'
  AND paid_at >= CURRENT_DATE
  AND paid_at < CURRENT_DATE + INTERVAL '1 day'
ORDER BY paid_at DESC;
"

echo ""
echo "5. EXPORTAR PARA CSV (opcional):"
echo "---------------------------------------"
echo "Para exportar para CSV, execute:"
echo "psql -U grimbots -d grimbots -c \"COPY (SELECT * FROM payments WHERE gateway_type = 'umbrellapag' AND created_at >= CURRENT_DATE) TO STDOUT WITH CSV HEADER;\" > vendas_umbrella_hoje.csv"

echo ""
echo "=========================================="
echo "  EXTRAÇÃO CONCLUÍDA"
echo "=========================================="

