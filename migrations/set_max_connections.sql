-- ============================================================================
-- PostgreSQL: Aumentar max_connections para suportar pool_size=10 por processo
-- ============================================================================
-- Contexto: Temos ~15 processos (4 gunicorn + 4 tasks + 3 gateway + 3 webhook
-- + 1 marathon) × pool_size=10 = 150 conexões simultâneas potenciais.
-- O default do PostgreSQL é 100. Precisamos de pelo menos 200.
--
-- Como executar (como superusuário PostgreSQL):
--   psql -U postgres -d saas_bot_manager -f set_max_connections.sql
--
-- Ou diretamente:
--   psql -U postgres -c "ALTER SYSTEM SET max_connections = 200;"
--   sudo systemctl restart postgresql   # ou brew services restart postgresql@16
-- ============================================================================

ALTER SYSTEM SET max_connections = 200;

SELECT pg_reload_conf();

-- Verificar o novo valor:
SHOW max_connections;
