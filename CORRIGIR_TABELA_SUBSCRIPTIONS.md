# 🚨 CORREÇÃO URGENTE: Tabela subscriptions não existe

**Erro:** `relation "subscriptions" does not exist`

---

## ✅ SOLUÇÃO RÁPIDA

Execute na VPS:

```bash
# Criar tabela subscriptions
python3 scripts/create_subscriptions_table.py
```

---

## 📋 O QUE FAZER

### **PASSO 1: Criar Tabela subscriptions**

```bash
cd ~/grimbots
python3 scripts/create_subscriptions_table.py
```

**Deve mostrar:**
```
✅ Tabela subscriptions criada com sucesso!
✅ Índices criados com sucesso!
```

### **PASSO 2: Verificar se Foi Criada**

```bash
# Verificar no banco
psql -U seu_usuario -d nome_banco -c "SELECT COUNT(*) FROM subscriptions;"
```

Ou via Python:

```python
python3 -c "from app import app, db; from models import Subscription; app.app_context().push(); print(f'✅ {db.session.query(Subscription).count()} subscriptions')"
```

### **PASSO 3: Reiniciar (se necessário)**

Se o script não funcionar ou quiser aplicar via SQL:

```bash
# Executar SQL direto
psql -U seu_usuario -d nome_banco -f scripts/create_subscriptions_table.sql
```

---

## 🔧 SQL MANUAL (se scripts não funcionarem)

Conecte ao banco e execute:

```sql
-- PostgreSQL
CREATE TABLE subscriptions (
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

-- Criar índices
CREATE INDEX idx_subscription_status_expires ON subscriptions(status, expires_at);
CREATE INDEX idx_subscription_vip_chat ON subscriptions(vip_chat_id, status);
CREATE INDEX idx_subscription_payment_id ON subscriptions(payment_id);
CREATE INDEX idx_subscription_bot_id ON subscriptions(bot_id);
CREATE INDEX idx_subscription_telegram_user_id ON subscriptions(telegram_user_id);
CREATE INDEX idx_subscription_created_at ON subscriptions(created_at);
CREATE INDEX idx_subscription_status ON subscriptions(status);
```

---

## ✅ APÓS CRIAR A TABELA

Os jobs de assinaturas vão funcionar normalmente:
- `check_expired_subscriptions` ✅
- `check_pending_subscriptions_in_groups` ✅
- `retry_failed_subscription_removals` ✅

---

**Execute o script e me avise se funcionou!**

