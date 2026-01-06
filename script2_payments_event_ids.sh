#!/bin/bash

echo "=============================================="
echo " PAYMENTS × EVENT_ID (META TRACKING)"
echo "=============================================="

echo "" 
psql -d sua_database <<'EOF'
SELECT
  id,
  created_at,
  meta_event_id,
  pageview_event_id,
  utm_source,
  campaign_code
FROM payments
ORDER BY created_at DESC
LIMIT 15;
EOF
