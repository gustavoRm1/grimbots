-- ============================================================================
-- GRIMBOTS — Tabelas de Archive para Cleanup Seguro
-- ============================================================================
-- Uso: psql -U <user> -d <database> -f deploy/sql/create_archive_tables.sql
-- ============================================================================

BEGIN;

-- 1. bot_messages_archive — mensagens > 90 dias
CREATE TABLE IF NOT EXISTS bot_messages_archive (
    LIKE bot_messages INCLUDING ALL,
    archived_at TIMESTAMP NOT NULL DEFAULT NOW()
);

ALTER TABLE bot_messages_archive ADD COLUMN IF NOT EXISTS archived_at TIMESTAMP NOT NULL DEFAULT NOW();
CREATE INDEX IF NOT EXISTS idx_bot_messages_archive_archived_at
    ON bot_messages_archive (archived_at);
CREATE INDEX IF NOT EXISTS idx_bot_messages_archive_bot_id
    ON bot_messages_archive (bot_id);

-- 2. webhook_events_archive — webhooks > 30 dias
CREATE TABLE IF NOT EXISTS webhook_events_archive (
    LIKE webhook_events INCLUDING ALL,
    archived_at TIMESTAMP NOT NULL DEFAULT NOW()
);

ALTER TABLE webhook_events_archive ADD COLUMN IF NOT EXISTS archived_at TIMESTAMP NOT NULL DEFAULT NOW();
CREATE INDEX IF NOT EXISTS idx_webhook_events_archive_archived_at
    ON webhook_events_archive (archived_at);
CREATE INDEX IF NOT EXISTS idx_webhook_events_archive_bot_id
    ON webhook_events_archive (bot_id);

COMMIT;
