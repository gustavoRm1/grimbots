#!/bin/bash
# Script para extrair vendas do UmbrellaPay de hoje e exportar para CSV
# Data: 2025-11-13

echo "=========================================="
echo "  EXPORTAÇÃO - VENDAS UMBRELLAPAY HOJE (CSV)"
echo "=========================================="

export PGPASSWORD=123sefudeu

# Data de hoje
DATE_TODAY=$(date +%Y-%m-%d)
echo "Data: $DATE_TODAY"
echo ""

# Diretório de saída
OUTPUT_DIR="./exports"
mkdir -p "$OUTPUT_DIR"

# 1. TODAS AS VENDAS DO UMBRELLAPAY HOJE
echo "1. Exportando TODAS as vendas do UmbrellaPay de hoje..."
psql -U grimbots -d grimbots -c "
COPY (
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
        fbp,
        fbc,
        fbclid,
        utm_source,
        utm_campaign,
        utm_medium,
        utm_content,
        utm_term,
        campaign_code,
        meta_purchase_sent,
        meta_event_id,
        meta_purchase_sent_at,
        created_at,
        paid_at,
        updated_at
    FROM payments
    WHERE gateway_type = 'umbrellapag'
      AND created_at >= CURRENT_DATE
      AND created_at < CURRENT_DATE + INTERVAL '1 day'
    ORDER BY created_at DESC
) TO STDOUT WITH CSV HEADER;
" > "$OUTPUT_DIR/vendas_umbrella_todas_$DATE_TODAY.csv"

echo "✅ Arquivo criado: $OUTPUT_DIR/vendas_umbrella_todas_$DATE_TODAY.csv"
echo ""

# 2. VENDAS PAGAS DO UMBRELLAPAY HOJE
echo "2. Exportando VENDAS PAGAS do UmbrellaPay de hoje..."
psql -U grimbots -d grimbots -c "
COPY (
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
        fbp,
        fbc,
        fbclid,
        utm_source,
        utm_campaign,
        utm_medium,
        utm_content,
        utm_term,
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
    ORDER BY paid_at DESC
) TO STDOUT WITH CSV HEADER;
" > "$OUTPUT_DIR/vendas_umbrella_pagas_$DATE_TODAY.csv"

echo "✅ Arquivo criado: $OUTPUT_DIR/vendas_umbrella_pagas_$DATE_TODAY.csv"
echo ""

# 3. RESUMO ESTATÍSTICO
echo "3. Gerando RESUMO ESTATÍSTICO..."
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
" > "$OUTPUT_DIR/resumo_umbrella_$DATE_TODAY.txt"

echo "✅ Arquivo criado: $OUTPUT_DIR/resumo_umbrella_$DATE_TODAY.txt"
echo ""

# 4. Listar arquivos criados
echo "=========================================="
echo "  ARQUIVOS CRIADOS"
echo "=========================================="
ls -lh "$OUTPUT_DIR"/*"$DATE_TODAY"* 2>/dev/null || echo "Nenhum arquivo encontrado"
echo ""

# 5. Estatísticas dos arquivos
echo "=========================================="
echo "  ESTATÍSTICAS DOS ARQUIVOS"
echo "=========================================="
if [ -f "$OUTPUT_DIR/vendas_umbrella_todas_$DATE_TODAY.csv" ]; then
    TOTAL_LINES=$(wc -l < "$OUTPUT_DIR/vendas_umbrella_todas_$DATE_TODAY.csv")
    TOTAL_VENDAS=$((TOTAL_LINES - 1))  # Subtrai 1 para remover header
    echo "Total de vendas (todas): $TOTAL_VENDAS"
fi

if [ -f "$OUTPUT_DIR/vendas_umbrella_pagas_$DATE_TODAY.csv" ]; then
    PAID_LINES=$(wc -l < "$OUTPUT_DIR/vendas_umbrella_pagas_$DATE_TODAY.csv")
    PAID_VENDAS=$((PAID_LINES - 1))  # Subtrai 1 para remover header
    echo "Total de vendas pagas: $PAID_VENDAS"
fi

echo ""
echo "=========================================="
echo "  EXPORTAÇÃO CONCLUÍDA"
echo "=========================================="
echo "Arquivos salvos em: $OUTPUT_DIR"
echo ""

