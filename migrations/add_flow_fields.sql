-- Migration SQL direta para PostgreSQL
-- Execute este script diretamente no PostgreSQL se a migration Python não funcionar

-- ✅ Adicionar flow_enabled ao BotConfig
ALTER TABLE bot_configs 
ADD COLUMN IF NOT EXISTS flow_enabled BOOLEAN DEFAULT FALSE;

CREATE INDEX IF NOT EXISTS idx_bot_configs_flow_enabled 
ON bot_configs(flow_enabled);

-- ✅ Adicionar flow_steps ao BotConfig
ALTER TABLE bot_configs 
ADD COLUMN IF NOT EXISTS flow_steps TEXT;

-- ✅ Adicionar flow_step_id ao Payment
ALTER TABLE payments 
ADD COLUMN IF NOT EXISTS flow_step_id VARCHAR(50);

CREATE INDEX IF NOT EXISTS idx_payments_flow_step_id 
ON payments(flow_step_id);

-- Verificar se as colunas foram criadas
SELECT 
    table_name, 
    column_name, 
    data_type, 
    column_default
FROM information_schema.columns 
WHERE (table_name = 'bot_configs' AND column_name IN ('flow_enabled', 'flow_steps'))
   OR (table_name = 'payments' AND column_name = 'flow_step_id')
ORDER BY table_name, column_name;

