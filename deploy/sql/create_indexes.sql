-- ============================================================================
-- GRIMBOTS — Índices de Performance para 200k visitas/dia
-- ============================================================================
-- Uso: psql -U <user> -d <database> -f deploy/sql/create_indexes.sql
-- ============================================================================

BEGIN;

-- 1. bot_users.fbclid — lookup no /start e matching de tracking
CREATE INDEX CONCURRENTLY IF NOT EXISTS idx_botuser_fbclid
    ON bot_users (fbclid)
    WHERE fbclid IS NOT NULL;

-- 2. bot_users.tracking_session_id — usado no delivery e recovery de tracking
CREATE INDEX CONCURRENTLY IF NOT EXISTS idx_botuser_tracking_session_id
    ON bot_users (tracking_session_id)
    WHERE tracking_session_id IS NOT NULL;

-- 3. payment.meta_event_id — deduplicação de Purchase CAPI
CREATE INDEX CONCURRENTLY IF NOT EXISTS idx_payment_meta_event_id
    ON payment (meta_event_id)
    WHERE meta_event_id IS NOT NULL;

-- 4. payment.delivery_token — lookup na rota de delivery (/delivery/<token>)
CREATE INDEX CONCURRENTLY IF NOT EXISTS idx_payment_delivery_token
    ON payment (delivery_token)
    WHERE delivery_token IS NOT NULL;

-- 5. payment.status + paid_at — queries de pending_sales e relatórios
CREATE INDEX CONCURRENTLY IF NOT EXISTS idx_payment_status_paid_at
    ON payment (status, paid_at)
    WHERE status = 'paid';

-- 6. bot_users.bot_id + last_interaction — queries de usuários recentes por bot
CREATE INDEX CONCURRENTLY IF NOT EXISTS idx_botuser_bot_last_interaction
    ON bot_users (bot_id, last_interaction DESC);

-- 7. payment.bot_id + created_at — relatórios de vendas por bot
CREATE INDEX CONCURRENTLY IF NOT EXISTS idx_payment_bot_created
    ON payment (bot_id, created_at DESC);

COMMIT;
