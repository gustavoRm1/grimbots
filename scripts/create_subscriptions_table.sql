-- Script SQL para criar tabela subscriptions no PostgreSQL
-- Execute este script antes de iniciar os jobs de assinaturas

-- Criar tabela subscriptions
CREATE TABLE IF NOT EXISTS subscriptions (
    id SERIAL PRIMARY KEY,
    payment_id INTEGER NOT NULL UNIQUE,
    bot_id INTEGER NOT NULL,
    telegram_user_id VARCHAR(255) NOT NULL,
    customer_name VARCHAR(255),
    duration_type VARCHAR(20) NOT NULL,
    duration_value INTEGER NOT NULL,
    vip_chat_id VARCHAR(100) NOT NULL,
    vip_group_link VARCHAR(500),
    started_at TIMESTAMP WITH TIME ZONE,
    expires_at TIMESTAMP WITH TIME ZONE,
    removed_at TIMESTAMP WITH TIME ZONE,
    status VARCHAR(20) DEFAULT 'pending',
    removed_by VARCHAR(50) DEFAULT 'system',
    error_count INTEGER DEFAULT 0,
    last_error TEXT,
    created_at TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP,
    
    CONSTRAINT uq_subscription_payment UNIQUE (payment_id),
    CONSTRAINT fk_subscription_payment FOREIGN KEY (payment_id) REFERENCES payments(id) ON DELETE CASCADE,
    CONSTRAINT fk_subscription_bot FOREIGN KEY (bot_id) REFERENCES bots(id) ON DELETE CASCADE
);

-- Criar índices para performance
CREATE INDEX IF NOT EXISTS idx_subscription_status_expires ON subscriptions(status, expires_at);
CREATE INDEX IF NOT EXISTS idx_subscription_vip_chat ON subscriptions(vip_chat_id, status);
CREATE INDEX IF NOT EXISTS idx_subscription_payment_id ON subscriptions(payment_id);
CREATE INDEX IF NOT EXISTS idx_subscription_bot_id ON subscriptions(bot_id);
CREATE INDEX IF NOT EXISTS idx_subscription_telegram_user_id ON subscriptions(telegram_user_id);
CREATE INDEX IF NOT EXISTS idx_subscription_created_at ON subscriptions(created_at);
CREATE INDEX IF NOT EXISTS idx_subscription_status ON subscriptions(status);

-- Verificar se tabela foi criada
SELECT 
    table_name, 
    column_name, 
    data_type, 
    is_nullable,
    column_default
FROM information_schema.columns
WHERE table_name = 'subscriptions'
ORDER BY ordinal_position;

