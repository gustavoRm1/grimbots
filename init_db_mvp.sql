-- ============================================================================
-- INIT DB MVP - Meta Pixel Async System
-- ============================================================================

-- Tabela de eventos enfileirados
CREATE TABLE IF NOT EXISTS event_queue (
    id SERIAL PRIMARY KEY,
    event_id VARCHAR(100) UNIQUE NOT NULL,
    event_name VARCHAR(50) NOT NULL,
    pixel_id VARCHAR(50) NOT NULL,
    event_data JSONB NOT NULL,
    status VARCHAR(20) DEFAULT 'pending', -- pending, processing, sent, failed
    attempts INTEGER DEFAULT 0,
    max_attempts INTEGER DEFAULT 10,
    last_attempt_at TIMESTAMP,
    last_error TEXT,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    sent_at TIMESTAMP,
    priority INTEGER DEFAULT 5 -- 1=alta (Purchase), 5=média, 10=baixa (PageView)
);

-- Índices para performance
CREATE INDEX IF NOT EXISTS idx_event_queue_status ON event_queue(status);
CREATE INDEX IF NOT EXISTS idx_event_queue_event_id ON event_queue(event_id);
CREATE INDEX IF NOT EXISTS idx_event_queue_pixel_id ON event_queue(pixel_id);
CREATE INDEX IF NOT EXISTS idx_event_queue_priority ON event_queue(priority, status);
CREATE INDEX IF NOT EXISTS idx_event_queue_created_at ON event_queue(created_at);

-- Tabela de log de eventos (histórico)
CREATE TABLE IF NOT EXISTS event_log (
    id SERIAL PRIMARY KEY,
    event_id VARCHAR(100) NOT NULL,
    event_name VARCHAR(50) NOT NULL,
    pixel_id VARCHAR(50) NOT NULL,
    status VARCHAR(20) NOT NULL, -- sent, failed
    response_code INTEGER,
    response_body TEXT,
    request_body JSONB,
    latency_ms INTEGER,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

-- Índices para análise
CREATE INDEX IF NOT EXISTS idx_event_log_event_id ON event_log(event_id);
CREATE INDEX IF NOT EXISTS idx_event_log_pixel_id ON event_log(pixel_id);
CREATE INDEX IF NOT EXISTS idx_event_log_created_at ON event_log(created_at);
CREATE INDEX IF NOT EXISTS idx_event_log_status ON event_log(status);

-- Tabela de métricas agregadas (para dashboard rápido)
CREATE TABLE IF NOT EXISTS event_metrics (
    id SERIAL PRIMARY KEY,
    pixel_id VARCHAR(50) NOT NULL,
    event_name VARCHAR(50) NOT NULL,
    hour TIMESTAMP NOT NULL, -- truncado por hora
    events_sent INTEGER DEFAULT 0,
    events_failed INTEGER DEFAULT 0,
    avg_latency_ms INTEGER DEFAULT 0,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    UNIQUE(pixel_id, event_name, hour)
);

CREATE INDEX IF NOT EXISTS idx_event_metrics_pixel_hour ON event_metrics(pixel_id, hour);

-- Função para atualizar updated_at
CREATE OR REPLACE FUNCTION update_updated_at_column()
RETURNS TRIGGER AS $$
BEGIN
    NEW.updated_at = CURRENT_TIMESTAMP;
    RETURN NEW;
END;
$$ language 'plpgsql';

CREATE TRIGGER update_event_metrics_updated_at 
    BEFORE UPDATE ON event_metrics 
    FOR EACH ROW 
    EXECUTE FUNCTION update_updated_at_column();

-- Comentários
COMMENT ON TABLE event_queue IS 'Fila de eventos pendentes para envio';
COMMENT ON TABLE event_log IS 'Histórico de todos eventos enviados ou falhados';
COMMENT ON TABLE event_metrics IS 'Métricas agregadas por hora para dashboard';

