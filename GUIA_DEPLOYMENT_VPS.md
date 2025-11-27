# 🚀 GUIA DE DEPLOYMENT NA VPS - SISTEMA DE ASSINATURAS

**Data:** 2025-01-25  
**Objetivo:** Checklist completo para subir o sistema de assinaturas na VPS

---

## 📋 ÍNDICE

1. [Preparação](#1-preparação)
2. [Deployment](#2-deployment)
3. [Configuração do Banco de Dados](#3-configuração-do-banco-de-dados)
4. [Configuração de Variáveis de Ambiente](#4-configuração-de-variáveis-de-ambiente)
5. [Verificação dos Jobs APScheduler](#5-verificação-dos-jobs-apsscheduler)
6. [Testes Funcionais](#6-testes-funcionais)
7. [Monitoramento](#7-monitoramento)

---

## 1. PREPARAÇÃO

### **1.1 Backup do Banco de Dados**

```bash
# Fazer backup ANTES de fazer qualquer alteração
pg_dump -U seu_usuario -d nome_banco > backup_antes_assinaturas_$(date +%Y%m%d_%H%M%S).sql

# Ou se usar SQLite
cp seu_banco.db backup_antes_assinaturas_$(date +%Y%m%d_%H%M%S).db
```

### **1.2 Verificar Arquivos Modificados**

```bash
# Verificar se todos os arquivos foram commitados
git status

# Verificar se não há arquivos não commitados relacionados a assinaturas
git diff app.py models.py bot_manager.py utils/subscriptions.py
```

---

## 2. DEPLOYMENT

### **2.1 Fazer Pull do Código**

```bash
# Se usar Git
cd /caminho/do/seu/projeto
git pull origin main  # ou master, dependendo da branch

# Verificar se arquivos novos foram baixados
ls -la utils/subscriptions.py  # Deve existir
```

### **2.2 Instalar Dependências (se necessário)**

```bash
# Se usar pip
pip install -r requirements.txt

# Verificar se dateutil está instalado (necessário para relativedelta)
pip list | grep python-dateutil

# Se não estiver, instalar:
pip install python-dateutil
```

---

## 3. CONFIGURAÇÃO DO BANCO DE DADOS

### **3.1 Criar Tabela de Subscriptions**

**Opção A: Migration Python (Recomendado)**

```bash
# Criar script de migration (se ainda não existir)
python scripts/create_subscriptions_table.py

# OU executar SQL diretamente:
```

**Opção B: SQL Direto (PostgreSQL)**

```sql
-- Conectar ao banco
\c nome_do_banco

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
```

**Opção C: SQL Direto (SQLite)**

```sql
-- Criar tabela subscriptions
CREATE TABLE IF NOT EXISTS subscriptions (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    payment_id INTEGER NOT NULL UNIQUE,
    bot_id INTEGER NOT NULL,
    telegram_user_id VARCHAR(255) NOT NULL,
    customer_name VARCHAR(255),
    duration_type VARCHAR(20) NOT NULL,
    duration_value INTEGER NOT NULL,
    vip_chat_id VARCHAR(100) NOT NULL,
    vip_group_link VARCHAR(500),
    started_at TIMESTAMP,
    expires_at TIMESTAMP,
    removed_at TIMESTAMP,
    status VARCHAR(20) DEFAULT 'pending',
    removed_by VARCHAR(50) DEFAULT 'system',
    error_count INTEGER DEFAULT 0,
    last_error TEXT,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    
    FOREIGN KEY (payment_id) REFERENCES payments(id) ON DELETE CASCADE,
    FOREIGN KEY (bot_id) REFERENCES bots(id) ON DELETE CASCADE
);

-- Criar índices
CREATE INDEX IF NOT EXISTS idx_subscription_status_expires ON subscriptions(status, expires_at);
CREATE INDEX IF NOT EXISTS idx_subscription_vip_chat ON subscriptions(vip_chat_id, status);
CREATE INDEX IF NOT EXISTS idx_subscription_payment_id ON subscriptions(payment_id);
CREATE INDEX IF NOT EXISTS idx_subscription_bot_id ON subscriptions(bot_id);
```

### **3.2 Adicionar Colunas ao Modelo Payment (se necessário)**

```sql
-- PostgreSQL
ALTER TABLE payments 
ADD COLUMN IF NOT EXISTS button_index INTEGER,
ADD COLUMN IF NOT EXISTS button_config TEXT,
ADD COLUMN IF NOT EXISTS has_subscription BOOLEAN DEFAULT FALSE;

-- Criar índice para performance
CREATE INDEX IF NOT EXISTS idx_payment_has_subscription ON payments(has_subscription) WHERE has_subscription = TRUE;

-- SQLite (não suporta IF NOT EXISTS, verificar antes)
-- Verificar se colunas existem antes de adicionar
```

**Script Python para verificar e adicionar:**

```python
# scripts/add_payment_subscription_columns.py
from app import app, db
from sqlalchemy import inspect

with app.app_context():
    inspector = inspect(db.engine)
    columns = [col['name'] for col in inspector.get_columns('payments')]
    
    if 'button_index' not in columns:
        db.engine.execute("ALTER TABLE payments ADD COLUMN button_index INTEGER")
        print("✅ Coluna button_index adicionada")
    
    if 'button_config' not in columns:
        db.engine.execute("ALTER TABLE payments ADD COLUMN button_config TEXT")
        print("✅ Coluna button_config adicionada")
    
    if 'has_subscription' not in columns:
        db.engine.execute("ALTER TABLE payments ADD COLUMN has_subscription BOOLEAN DEFAULT FALSE")
        print("✅ Coluna has_subscription adicionada")
    
    print("✅ Verificação concluída!")
```

### **3.3 Verificar Constraints CASCADE**

```sql
-- PostgreSQL: Verificar se constraints CASCADE estão configuradas
SELECT 
    tc.constraint_name, 
    tc.table_name, 
    kcu.column_name,
    ccu.table_name AS foreign_table_name,
    rc.delete_rule
FROM information_schema.table_constraints AS tc
JOIN information_schema.key_column_usage AS kcu
    ON tc.constraint_name = kcu.constraint_name
JOIN information_schema.constraint_column_usage AS ccu
    ON ccu.constraint_name = tc.constraint_name
JOIN information_schema.referential_constraints AS rc
    ON rc.constraint_name = tc.constraint_name
WHERE tc.table_name = 'subscriptions'
    AND tc.constraint_type = 'FOREIGN KEY';

-- Se delete_rule não for CASCADE, aplicar migration:
ALTER TABLE subscriptions 
DROP CONSTRAINT IF EXISTS subscriptions_bot_id_fkey,
ADD CONSTRAINT subscriptions_bot_id_fkey 
FOREIGN KEY (bot_id) REFERENCES bots(id) ON DELETE CASCADE;
```

---

## 4. CONFIGURAÇÃO DE VARIÁVEIS DE AMBIENTE

### **4.1 Verificar Variáveis Críticas**

```bash
# Verificar arquivo .env
cat .env | grep -E "REDIS_URL|ENCRYPTION_KEY|DATABASE_URL"

# Ou se usar variáveis de sistema
env | grep -E "REDIS_URL|ENCRYPTION_KEY|DATABASE_URL"
```

### **4.2 Configurar Redis (para Locks Distribuídos)**

```bash
# Verificar se Redis está rodando
redis-cli ping
# Deve retornar: PONG

# Se não estiver rodando:
# Ubuntu/Debian
sudo systemctl start redis
sudo systemctl enable redis

# Verificar conexão
redis-cli -h localhost -p 6379 ping
```

**Adicionar ao .env:**

```env
REDIS_URL=redis://localhost:6379/0
```

### **4.3 Verificar ENCRYPTION_KEY**

```bash
# Verificar se ENCRYPTION_KEY está configurada
echo $ENCRYPTION_KEY

# Se não estiver, gerar uma nova (CUIDADO: Isso pode invalidar dados criptografados existentes!)
python -c "from cryptography.fernet import Fernet; print(Fernet.generate_key().decode())"

# Adicionar ao .env (NÃO gerar nova se já tem dados criptografados!)
# ENCRYPTION_KEY=sua_chave_aqui
```

---

## 5. VERIFICAÇÃO DOS JOBS APSCHEDULER

### **5.1 Verificar se Jobs Estão Agendados**

```python
# Criar script de verificação
# scripts/verificar_jobs_assinaturas.py
from app import app, scheduler

with app.app_context():
    jobs = scheduler.get_jobs()
    subscription_jobs = [j for j in jobs if 'subscription' in j.id.lower() or 'expired' in j.id.lower()]
    
    print("📋 Jobs de Assinaturas:")
    for job in subscription_jobs:
        print(f"  ✅ {job.id}")
        print(f"     Próxima execução: {job.next_run_time}")
        print(f"     Trigger: {job.trigger}")
        print()
    
    if not subscription_jobs:
        print("⚠️ Nenhum job de assinatura encontrado!")
        print("Verifique se os jobs foram adicionados em app.py")
```

**Executar:**

```bash
python scripts/verificar_jobs_assinaturas.py
```

### **5.2 Adicionar Jobs Manualmente (se necessário)**

Os jobs devem ser adicionados automaticamente quando o app inicia, mas se não estiverem, verificar em `app.py`:

```python
# app.py deve conter:
if _scheduler_owner:
    scheduler.add_job(
        check_expired_subscriptions,
        'interval',
        minutes=5,
        id='check_expired_subscriptions'
    )
    
    scheduler.add_job(
        check_pending_subscriptions_in_groups,
        'interval',
        minutes=30,
        id='check_pending_subscriptions_in_groups'
    )
    
    scheduler.add_job(
        retry_failed_subscription_removals,
        'interval',
        minutes=30,
        id='retry_failed_subscription_removals'
    )
```

### **5.3 Testar Jobs Manualmente**

```python
# scripts/testar_jobs_assinaturas.py
from app import app
from app import check_expired_subscriptions, check_pending_subscriptions_in_groups, retry_failed_subscription_removals

with app.app_context():
    print("🔍 Testando check_expired_subscriptions...")
    try:
        check_expired_subscriptions()
        print("✅ Sucesso!")
    except Exception as e:
        print(f"❌ Erro: {e}")
    
    print("\n🔍 Testando check_pending_subscriptions_in_groups...")
    try:
        check_pending_subscriptions_in_groups()
        print("✅ Sucesso!")
    except Exception as e:
        print(f"❌ Erro: {e}")
    
    print("\n🔍 Testando retry_failed_subscription_removals...")
    try:
        retry_failed_subscription_removals()
        print("✅ Sucesso!")
    except Exception as e:
        print(f"❌ Erro: {e}")
```

---

## 6. TESTES FUNCIONAIS

### **6.1 Verificar Criação de Subscription**

```python
# scripts/testar_criar_subscription.py
from app import app, db
from models import Payment, Subscription

with app.app_context():
    # Buscar um payment recente para teste
    payment = Payment.query.filter_by(status='paid').order_by(Payment.id.desc()).first()
    
    if not payment:
        print("❌ Nenhum payment pago encontrado")
    else:
        print(f"📋 Payment encontrado: {payment.id}")
        print(f"   has_subscription: {payment.has_subscription}")
        
        if payment.has_subscription:
            subscription = Subscription.query.filter_by(payment_id=payment.id).first()
            if subscription:
                print(f"✅ Subscription existe: {subscription.id}")
                print(f"   Status: {subscription.status}")
                print(f"   VIP Chat ID: {subscription.vip_chat_id}")
            else:
                print("⚠️ Payment tem has_subscription=True mas subscription não existe")
```

### **6.2 Verificar Função de Normalização**

```python
# scripts/testar_normalize_vip_chat_id.py
from utils.subscriptions import normalize_vip_chat_id

test_cases = [
    "-1001234567890",
    "  -1001234567890  ",
    "",
    None,
    "https://t.me/+abc123",
]

print("🔍 Testando normalize_vip_chat_id...")
for test in test_cases:
    result = normalize_vip_chat_id(test)
    print(f"  Input: {test}")
    print(f"  Output: {result}")
    print()
```

### **6.3 Verificar Endpoint de Validação**

```bash
# Testar endpoint de validação de subscription
curl -X POST http://localhost:5000/api/bots/1/validate-subscription \
  -H "Content-Type: application/json" \
  -d '{
    "vip_chat_id": "-1001234567890",
    "vip_group_link": "https://t.me/+abc123"
  }'

# Deve retornar JSON com valid: true/false
```

---

## 7. MONITORAMENTO

### **7.1 Verificar Logs**

```bash
# Ver logs em tempo real
tail -f logs/app.log | grep -i subscription

# Ou se usar systemd
journalctl -u seu_servico -f | grep -i subscription
```

### **7.2 Verificar Status das Subscriptions**

```sql
-- Verificar subscriptions por status
SELECT status, COUNT(*) 
FROM subscriptions 
GROUP BY status;

-- Verificar subscriptions ativas
SELECT id, payment_id, telegram_user_id, started_at, expires_at, status
FROM subscriptions
WHERE status = 'active'
ORDER BY expires_at ASC
LIMIT 10;

-- Verificar subscriptions com erro
SELECT id, payment_id, error_count, last_error, status
FROM subscriptions
WHERE status = 'error'
ORDER BY error_count DESC
LIMIT 10;

-- Verificar subscriptions pendentes (aguardando entrada no grupo)
SELECT id, payment_id, telegram_user_id, created_at, status
FROM subscriptions
WHERE status = 'pending'
ORDER BY created_at DESC
LIMIT 10;
```

### **7.3 Monitorar Jobs APScheduler**

```bash
# Ver logs dos jobs
grep -i "check_expired_subscriptions\|check_pending_subscriptions\|retry_failed_subscription" logs/app.log | tail -20

# Verificar última execução dos jobs
python scripts/verificar_jobs_assinaturas.py
```

### **7.4 Alertas (Opcional)**

```python
# scripts/monitorar_subscriptions.py
from app import app, db
from models import Subscription
from datetime import datetime, timezone, timedelta

with app.app_context():
    now = datetime.now(timezone.utc)
    
    # Subscriptions com muitos erros
    high_error_count = Subscription.query.filter(
        Subscription.error_count >= 5,
        Subscription.status == 'error'
    ).count()
    
    if high_error_count > 0:
        print(f"⚠️ ALERTA: {high_error_count} subscriptions com muitos erros!")
    
    # Subscriptions pendentes há muito tempo (mais de 1 hora)
    old_pending = Subscription.query.filter(
        Subscription.status == 'pending',
        Subscription.created_at < now - timedelta(hours=1)
    ).count()
    
    if old_pending > 0:
        print(f"⚠️ ALERTA: {old_pending} subscriptions pendentes há mais de 1 hora")
    
    # Subscriptions expiradas mas não removidas
    expired_not_removed = Subscription.query.filter(
        Subscription.status == 'expired',
        Subscription.expires_at < now - timedelta(minutes=10)
    ).count()
    
    if expired_not_removed > 0:
        print(f"⚠️ ALERTA: {expired_not_removed} subscriptions expiradas há mais de 10 minutos sem remoção")
```

---

## 8. CHECKLIST FINAL

### **Antes de Subir:**

- [ ] Backup do banco de dados feito
- [ ] Código atualizado (git pull)
- [ ] Dependências instaladas (python-dateutil)
- [ ] Tabela `subscriptions` criada
- [ ] Colunas em `payments` adicionadas (button_index, button_config, has_subscription)
- [ ] Índices criados
- [ ] Constraints CASCADE configuradas
- [ ] Redis configurado e rodando
- [ ] ENCRYPTION_KEY configurada
- [ ] REDIS_URL no .env

### **Após Subir:**

- [ ] Jobs APScheduler rodando (3 jobs)
- [ ] Logs sem erros críticos
- [ ] Endpoint de validação funcionando
- [ ] Função normalize_vip_chat_id funcionando
- [ ] Teste de criação de subscription funcionando
- [ ] Monitoramento configurado

### **Verificações de Segurança:**

- [ ] Redis acessível apenas localmente (bind 127.0.0.1)
- [ ] ENCRYPTION_KEY não exposta em logs
- [ ] Backup automático configurado
- [ ] Logs rotacionados (logrotate)

---

## 9. COMANDOS RÁPIDOS

```bash
# 1. Backup
pg_dump -U usuario -d banco > backup.sql

# 2. Pull código
cd /caminho/projeto && git pull

# 3. Instalar dependências
pip install python-dateutil

# 4. Verificar Redis
redis-cli ping

# 5. Reiniciar serviço
sudo systemctl restart seu_servico
# ou
sudo supervisorctl restart seu_servico
# ou
pm2 restart seu_servico

# 6. Ver logs
tail -f logs/app.log

# 7. Verificar jobs
python scripts/verificar_jobs_assinaturas.py

# 8. Testar criação
python scripts/testar_criar_subscription.py
```

---

## 10. TROUBLESHOOTING

### **Problema: Jobs não estão rodando**

```bash
# Verificar se scheduler foi iniciado
grep "APScheduler iniciado" logs/app.log

# Verificar se há lock de scheduler
ls -la /tmp/scheduler.lock

# Remover lock se necessário (CUIDADO: apenas se tiver certeza)
rm /tmp/scheduler.lock
```

### **Problema: Redis não conecta**

```bash
# Verificar se Redis está rodando
sudo systemctl status redis

# Verificar porta
netstat -tlnp | grep 6379

# Testar conexão
redis-cli -h localhost -p 6379 ping
```

### **Problema: Subscription não é criada**

```bash
# Verificar logs de criação
grep "create_subscription_for_payment" logs/app.log | tail -20

# Verificar se payment tem has_subscription=True
# Verificar se button_config tem subscription configurado
```

### **Problema: Subscription não ativa**

```bash
# Verificar se evento new_chat_member está sendo recebido
grep "new_chat_member" logs/app.log | tail -20

# Verificar job de fallback
grep "check_pending_subscriptions_in_groups" logs/app.log | tail -20
```

---

**FIM DO GUIA DE DEPLOYMENT**

