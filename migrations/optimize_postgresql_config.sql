-- ============================================================================
-- PostgreSQL Performance Tuning para Grimbots
-- ============================================================================
-- SEGURO: ALTER SYSTEM SET não modifica dados, apenas parâmetros.
-- SEGURO: pg_reload_conf() aplica sem restart.
-- SEGURO: VACUUM ANALYZE não bloqueia writes.
-- ============================================================================

-- ── 1. MEMÓRIA ──
-- shared_buffers: cache do PostgreSQL em RAM (antes era 256MB — muito baixo)
ALTER SYSTEM SET shared_buffers = '2GB';

-- work_mem: memória para cada operação de sorting/aggregation (antes 4MB)
-- Essencial para GROUP BY / ORDER BY / DISTINCT do dashboard
ALTER SYSTEM SET work_mem = '32MB';

-- effective_cache_size: estimativa do OS cache (ajuda planner a escolher index scan)
ALTER SYSTEM SET effective_cache_size = '6GB';

-- maintenance_work_mem: memória para VACUUM, CREATE INDEX (antes 64MB)
ALTER SYSTEM SET maintenance_work_mem = '256MB';

-- ── 2. PLANEJADOR ──
-- default_statistics_target: amostragem para o planner (antes 100)
-- 500 = planner vê distribuição real dos dados, evita sequential scans errados
ALTER SYSTEM SET default_statistics_target = 500;

-- random_page_cost: custo de I/O aleatório vs sequencial (SSD = 1.1, HDD = 4.0)
-- Já configurado para SSD, mantendo
-- ALTER SYSTEM SET random_page_cost = 1.1;

-- ── 3. CONEXÕES ──
-- max_connections: limite de conexões simultâneas (antes 100, migration subiu pra 200)
-- Com 4 gunicorn workers + 11 RQ workers, precisamos de mais
ALTER SYSTEM SET max_connections = 300;

-- ── 4. CHECKPOINT ──
-- checkpoint_completion_target: distribui escrita no disco ao longo do intervalo
ALTER SYSTEM SET checkpoint_completion_target = 0.9;

-- wal_buffers: buffer de write-ahead log (antes 16MB)
ALTER SYSTEM SET wal_buffers = '16MB';

-- ============================================================================
-- APLICAR CONFIGURAÇÕES E VERIFICAR
-- ============================================================================
SELECT pg_reload_conf();

-- Verificar se as configurações foram aplicadas
SELECT name, setting, unit, context
FROM pg_settings
WHERE name IN (
    'shared_buffers', 'work_mem', 'effective_cache_size',
    'maintenance_work_mem', 'default_statistics_target',
    'max_connections', 'checkpoint_completion_target', 'wal_buffers'
)
ORDER BY name;

-- ============================================================================
-- VACUUM + ANALYZE NAS TABELAS MAIORES
-- ============================================================================
-- VACUUM: recupera espaço de tuplas mortas
-- ANALYZE: atualiza estatísticas (crucial depois de mudar default_statistics_target)
--
-- NOTA: Pode levar alguns minutos em tabelas grandes.
-- Não bloqueia writes (autovacuum já roda em background).
-- ============================================================================

-- Tabela de mensagens (maior do sistema)
VACUUM ANALYZE bot_messages;

-- Tabela de pagamentos
VACUUM ANALYZE payments;

-- Tabela de usuários dos bots
VACUUM ANALYZE bot_users;

-- Tabela de webhooks
VACUUM ANALYZE webhook_events;

-- ============================================================================
-- REINDEX (opcional, só se houver sinais de corrupção/bloat)
-- ============================================================================
-- REINDEX TABLE bot_messages;
-- REINDEX TABLE payments;

-- ============================================================================
-- VERIFICAR ÍNDICES MAIS USADOS (diagnóstico)
-- ============================================================================
SELECT
    schemaname,
    tablename,
    indexname,
    idx_scan,
    idx_tup_read,
    idx_tup_fetch
FROM pg_stat_user_indexes
WHERE schemaname = 'public'
ORDER BY idx_scan DESC
LIMIT 20;
