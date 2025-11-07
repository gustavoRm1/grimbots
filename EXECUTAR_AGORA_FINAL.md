# 🚀 EXECUTAR AGORA - SOLUÇÃO FINAL DEFINITIVA

**Tempo:** 20 minutos  
**Resolve:** Git + SQLite → PostgreSQL + DNS + Deploy completo

---

## ⚡ COMANDO ÚNICO - COPIE E COLE

```bash
cd ~/grimbots && \
git stash && \
git pull origin main && \
chmod +x MIGRACAO_POSTGRESQL_AGORA.sh FIX_DNS_TELEGRAM.sh && \
./FIX_DNS_TELEGRAM.sh && \
./MIGRACAO_POSTGRESQL_AGORA.sh
```

**Este comando:**
1. ✅ Resolve Git (stash)
2. ✅ Faz pull do código
3. ✅ Corrige DNS Telegram
4. ✅ Migra SQLite → PostgreSQL
5. ✅ Inicia sistema com PostgreSQL

---

## 📋 OU PASSO A PASSO (SE PREFERIR)

### 1. Resolver Git (1 min)

```bash
cd ~/grimbots
git stash
git pull origin main
```

### 2. Corrigir DNS (2 min)

```bash
chmod +x FIX_DNS_TELEGRAM.sh
./FIX_DNS_TELEGRAM.sh
```

OU manualmente:

```bash
# Backup
sudo cp /etc/resolv.conf /etc/resolv.conf.backup

# Configurar DNS
sudo bash -c 'cat > /etc/resolv.conf << EOF
nameserver 8.8.8.8
nameserver 8.8.4.4
nameserver 1.1.1.1
EOF'

# Testar
nslookup api.telegram.org
ping -c 3 api.telegram.org
```

### 3. Migrar para PostgreSQL (15 min)

```bash
chmod +x MIGRACAO_POSTGRESQL_AGORA.sh
./MIGRACAO_POSTGRESQL_AGORA.sh
```

OU manualmente:

```bash
# Parar aplicação
pkill -9 python; pkill -9 gunicorn
sudo systemctl stop grimbots 2>/dev/null || true

# Backup SQLite
cp instance/saas_bot_manager.db instance/saas_bot_manager.db.backup_$(date +%Y%m%d_%H%M%S)

# Instalar PostgreSQL
sudo apt update
sudo apt install -y postgresql postgresql-contrib python3-psycopg2

# Iniciar PostgreSQL
sudo systemctl start postgresql
sudo systemctl enable postgresql

# Criar banco
sudo -u postgres psql << EOF
DROP DATABASE IF EXISTS grimbots;
CREATE DATABASE grimbots;
DROP USER IF EXISTS grimbots;
CREATE USER grimbots WITH PASSWORD 'MUDE_ESTA_SENHA_123';
GRANT ALL PRIVILEGES ON DATABASE grimbots TO grimbots;
ALTER DATABASE grimbots OWNER TO grimbots;
EOF

# Criar schema
cd ~/grimbots
source venv/bin/activate
export DATABASE_URL="postgresql://grimbots:MUDE_ESTA_SENHA_123@localhost:5432/grimbots"

python << EOF
from app import app, db
import logging
logging.basicConfig(level=logging.ERROR)
with app.app_context():
    db.create_all()
    print('✅ Schema criado')
EOF

# Migrar dados
export PG_PASSWORD='MUDE_ESTA_SENHA_123'
python migrate_to_postgres.py

# Atualizar .env
sed -i '/^DATABASE_URL=/d' .env 2>/dev/null || true
echo "DATABASE_URL=postgresql://grimbots:MUDE_ESTA_SENHA_123@localhost:5432/grimbots" >> .env

echo "✅ Migração concluída"
```

### 4. Iniciar Sistema (2 min)

```bash
# Reduzir workers para 1 (PostgreSQL aguenta mais, mas começar seguro)
cd ~/grimbots
source venv/bin/activate
sed -i 's/workers = max(3, min(cpu_count \* 2 + 1, 8))/workers = 1/' gunicorn_config.py

# Iniciar Gunicorn
sudo systemctl daemon-reload
sudo systemctl start grimbots

# Aguardar
sleep 10

# Verificar
sudo systemctl status grimbots

# Iniciar RQ Workers (nohup)
for i in {1..5}; do nohup python start_rq_worker.py tasks > logs/rq-tasks-$i.log 2>&1 & done
for i in {1..3}; do nohup python start_rq_worker.py gateway > logs/rq-gateway-$i.log 2>&1 & done
for i in {1..3}; do nohup python start_rq_worker.py webhook > logs/rq-webhook-$i.log 2>&1 & done

# Aguardar
sleep 5

# Contar
ps aux | grep start_rq_worker | grep -v grep | wc -l
# Deve mostrar: 11
```

### 5. Validar (2 min)

```bash
# Processos
ps aux | grep -E "gunicorn|start_rq_worker" | grep -v grep

# Health check
curl http://localhost:5000/health | python3 -m json.tool

# Deve retornar:
{
  "status": "healthy",
  "checks": {
    "database": "ok",
    "redis": {
      "status": "healthy"
    },
    "rq_workers": {
      "workers": {
        "tasks": 5,
        "gateway": 3,
        "webhook": 3
      }
    }
  }
}
```

---

## ✅ VALIDAÇÃO FINAL

### Testar Bot

```bash
# Monitorar logs
tail -f logs/error.log | grep -E "(🚀|⛔|database|Telegram)"

# Enviar /start no bot
# Verificar:
# ✅ Texto aparece APENAS 1 VEZ (não 2)
# ✅ SEM erro "database is locked"
# ✅ SEM erro "Failed to resolve api.telegram.org"
```

### Verificar Database

```bash
# Verificar que está usando PostgreSQL
psql -U grimbots -d grimbots -c "SELECT COUNT(*) FROM users;"
psql -U grimbots -d grimbots -c "SELECT COUNT(*) FROM bot_messages;"

# Logs não devem mostrar "database is locked"
grep "database is locked" logs/error.log
# Deve estar vazio
```

---

## 🎯 RESULTADO ESPERADO

Após executar:

✅ **Git:** Atualizado  
✅ **PostgreSQL:** Rodando com dados migrados  
✅ **DNS:** Resolvendo api.telegram.org  
✅ **Gunicorn:** Rodando (1 worker)  
✅ **RQ Workers:** 11 ativos  
✅ **Health Check:** HTTP 200 (healthy)  
✅ **Duplicação:** ZERO  
✅ **Database Locks:** ZERO  

---

## 🔧 TROUBLESHOOTING

### Se PostgreSQL falhar:

```bash
# Ver logs
sudo journalctl -u postgresql -n 50

# Verificar se está rodando
sudo systemctl status postgresql

# Reiniciar
sudo systemctl restart postgresql
```

### Se Gunicorn não iniciar:

```bash
# Ver erro
sudo journalctl -u grimbots -n 50

# Testar manualmente
source venv/bin/activate
gunicorn -c gunicorn_config.py wsgi:app
# Ver erro que aparece
```

### Se DNS ainda falhar:

```bash
# Verificar /etc/resolv.conf
cat /etc/resolv.conf

# Deve ter:
# nameserver 8.8.8.8
# nameserver 8.8.4.4

# Testar
nslookup api.telegram.org
```

---

## 📊 APÓS 24H

Se tudo estiver OK por 24h:

```bash
# Aumentar workers (PostgreSQL aguenta)
nano gunicorn_config.py
# Mudar: workers = 1
# Para: workers = 3

# Reiniciar
sudo systemctl restart grimbots
```

---

**EXECUTE AGORA:** Comando único acima ou passo a passo! 🚀

**Arquivo:** `EXECUTAR_AGORA_FINAL.md`

