-- Script para extrair todas as vendas do UmbrellaPay de hoje
-- Data: 2025-11-13

-- 1. TODAS AS VENDAS DO UMBRELLAPAY HOJE (pendentes + paid + failed)
SELECT 
    id,
    payment_id,
    status,
    gateway_type,
    gateway_transaction_id,
    gateway_transaction_hash,
    amount,
    net_amount,
    customer_name,
    customer_username,
    customer_user_id,
    product_name,
    product_description,
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
    paid_at,
    updated_at
FROM payments
WHERE gateway_type = 'umbrellapag'
  AND created_at >= CURRENT_DATE
  AND created_at < CURRENT_DATE + INTERVAL '1 day'
ORDER BY created_at DESC;

-- 2. VENDAS PAGAS DO UMBRELLAPAY HOJE
SELECT 
    id,
    payment_id,
    status,
    gateway_type,
    gateway_transaction_id,
    gateway_transaction_hash,
    amount,
    net_amount,
    customer_name,
    customer_username,
    customer_user_id,
    product_name,
    product_description,
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
    meta_purchase_sent_at,
    created_at,
    paid_at,
    updated_at
FROM payments
WHERE gateway_type = 'umbrellapag'
  AND status = 'paid'
  AND paid_at >= CURRENT_DATE
  AND paid_at < CURRENT_DATE + INTERVAL '1 day'
ORDER BY paid_at DESC;

-- 3. RESUMO ESTATÍSTICO
SELECT 
    COUNT(*) as total_vendas,
    COUNT(CASE WHEN status = 'paid' THEN 1 END) as vendas_pagas,
    COUNT(CASE WHEN status = 'pending' THEN 1 END) as vendas_pendentes,
    COUNT(CASE WHEN status = 'failed' THEN 1 END) as vendas_falhadas,
    SUM(CASE WHEN status = 'paid' THEN amount ELSE 0 END) as valor_total_pago,
    SUM(amount) as valor_total_gerado,
    COUNT(CASE WHEN meta_purchase_sent = true THEN 1 END) as purchase_enviados,
    COUNT(CASE WHEN tracking_token IS NOT NULL THEN 1 END) as com_tracking_token,
    COUNT(CASE WHEN fbc IS NOT NULL THEN 1 END) as com_fbc,
    COUNT(CASE WHEN pageview_event_id IS NOT NULL THEN 1 END) as com_pageview_event_id
FROM payments
WHERE gateway_type = 'umbrellapag'
  AND created_at >= CURRENT_DATE
  AND created_at < CURRENT_DATE + INTERVAL '1 day';

-- 4. VENDAS PAGAS COM DETALHES DE TRACKING
SELECT 
    payment_id,
    status,
    amount,
    customer_user_id,
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
    created_at,
    paid_at
FROM payments
WHERE gateway_type = 'umbrellapag'
  AND status = 'paid'
  AND paid_at >= CURRENT_DATE
  AND paid_at < CURRENT_DATE + INTERVAL '1 day'
ORDER BY paid_at DESC;

