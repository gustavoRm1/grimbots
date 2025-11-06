# 🚀 IMPLEMENTAÇÃO FASE 1 - CORREÇÕES CRÍTICAS

**Prazo:** 1 semana  
**Impacto:** +200% throughput, 99.9% uptime

---

## CHECKLIST DE IMPLEMENTAÇÃO

### ✅ Tarefa 1: Redis Connection Pool (Prioridade MÁXIMA)

**Tempo estimado:** 4 horas

#### Passo 1: Adicionar redis_manager.py
```bash
# Arquivo já criado: redis_manager.py
# Verificar se está correto:
python redis_manager.py
```

#### Passo 2: Refatorar bot_manager.py
Substituir todas as ocorrências de:
```python
# ❌ ANTES
redis_conn = redis.Redis(host='localhost', port=6379, db=0, decode_responses=True)
```

Por:
```python
# ✅ DEPOIS
from redis_manager import get_redis_connection
redis_conn = get_redis_connection()
```

**Arquivos a modificar:**
- `bot_manager.py` (9 ocorrências)
- `tasks_async.py` (2 ocorrências)
- `app.py` (4 ocorrências)
- `utils/tracking_service.py` (1 ocorrência)

#### Passo 3: Atualizar tasks_async.py e start_rq_worker.py
```python
# tasks_async.py
from redis_manager import get_redis_connection

# Substituir
redis_conn = Redis.from_url(...)

# Por
redis_conn = get_redis_connection(decode_responses=False)  # RQ precisa bytes
task_queue = Queue('tasks', connection=redis_conn)
```

#### Passo 4: Testar
```bash
# 1. Testar redis_manager
python redis_manager.py

# 2. Testar aplicação
python wsgi.py

# 3. Verificar logs
tail -f logs/error.log | grep -i redis
```

---

### ✅ Tarefa 2: Systemd Services (Prioridade ALTA)

**Tempo estimado:** 2 horas

#### Passo 1: Copiar arquivos
```bash
sudo cp deploy/systemd/grimbots.service /etc/systemd/system/
sudo cp deploy/systemd/rq-worker@.service /etc/systemd/system/
```

#### Passo 2: Editar configurações
```bash
# Editar grimbots.service
sudo nano /etc/systemd/system/grimbots.service

# Ajustar:
# - User (seu usuário)
# - WorkingDirectory (seu diretório)
# - DATABASE_URL (seu banco)
# - SECRET_KEY (sua chave)
```

#### Passo 3: Habilitar e iniciar
```bash
# Recarregar systemd
sudo systemctl daemon-reload

# Habilitar
sudo systemctl enable grimbots
sudo systemctl enable rq-worker@tasks-{1..5}
sudo systemctl enable rq-worker@gateway-{1..3}
sudo systemctl enable rq-worker@webhook-{1..3}

# Parar processos antigos (se houver)
pkill -f gunicorn
pkill -f start_rq_worker.py

# Iniciar via systemd
sudo systemctl start grimbots
sudo systemctl start rq-worker@tasks-{1..5}
sudo systemctl start rq-worker@gateway-{1..3}
sudo systemctl start rq-worker@webhook-{1..3}

# Verificar status
sudo systemctl status grimbots
sudo systemctl status 'rq-worker@*'
```

#### Passo 4: Testar auto-restart
```bash
# Matar processo
sudo kill -9 $(pgrep -f gunicorn | head -1)

# Aguardar 10s e verificar se reiniciou
sleep 15
sudo systemctl status grimbots
```

---

### ✅ Tarefa 3: Health Check Endpoint (Prioridade ALTA)

**Tempo estimado:** 2 horas

#### Passo 1: Adicionar endpoint no app.py
```python
# app.py
from redis_manager import redis_health_check

@app.route('/health', methods=['GET'])
@limiter.exempt  # Sem rate limit
def health_check():
    """Health check para load balancer"""
    checks = {
        'status': 'healthy',
        'timestamp': datetime.utcnow().isoformat(),
        'checks': {}
    }
    
    # Check 1: Banco de dados
    try:
        db.session.execute('SELECT 1')
        checks['checks']['database'] = 'ok'
    except Exception as e:
        checks['checks']['database'] = f'error: {str(e)}'
        checks['status'] = 'unhealthy'
    
    # Check 2: Redis
    redis_status = redis_health_check()
    checks['checks']['redis'] = redis_status
    if redis_status['status'] != 'healthy':
        checks['status'] = 'unhealthy'
    
    # Check 3: RQ Workers
    try:
        from redis_manager import get_redis_connection
        from rq import Queue
        redis_conn = get_redis_connection(decode_responses=False)
        
        tasks_queue = Queue('tasks', connection=redis_conn)
        gateway_queue = Queue('gateway', connection=redis_conn)
        webhook_queue = Queue('webhook', connection=redis_conn)
        
        workers_count = {
            'tasks': len(tasks_queue.workers),
            'gateway': len(gateway_queue.workers),
            'webhook': len(webhook_queue.workers)
        }
        
        checks['checks']['rq_workers'] = workers_count
        
        # Alertar se alguma fila sem workers
        if any(count == 0 for count in workers_count.values()):
            checks['status'] = 'degraded'
    except Exception as e:
        checks['checks']['rq_workers'] = f'error: {str(e)}'
        checks['status'] = 'unhealthy'
    
    # Status code
    if checks['status'] == 'healthy':
        status_code = 200
    elif checks['status'] == 'degraded':
        status_code = 200  # 200 mas com aviso
    else:
        status_code = 503  # Service Unavailable
    
    return jsonify(checks), status_code
```

#### Passo 2: Testar endpoint
```bash
curl http://localhost:5000/health
```

Resposta esperada:
```json
{
  "status": "healthy",
  "timestamp": "2025-11-06T23:30:00",
  "checks": {
    "database": "ok",
    "redis": {
      "status": "healthy",
      "connected_clients": 10,
      "used_memory_human": "1.5M",
      "pool_size": 50,
      "pool_available": 45
    },
    "rq_workers": {
      "tasks": 5,
      "gateway": 3,
      "webhook": 3
    }
  }
}
```

---

### ✅ Tarefa 4: Testes de Carga (Prioridade MÉDIA)

**Tempo estimado:** 2 horas

#### Passo 1: Instalar ferramentas
```bash
pip install locust
```

#### Passo 2: Criar script de teste
```python
# locustfile.py
from locust import HttpUser, task, between

class GrimbotsUser(HttpUser):
    wait_time = between(1, 3)
    
    @task(10)
    def health_check(self):
        self.client.get("/health")
    
    @task(5)
    def webhook(self):
        # Simular webhook Telegram
        self.client.post(
            "/webhook/telegram/1",
            json={
                "update_id": 123456,
                "message": {
                    "message_id": 789,
                    "from": {"id": 123, "first_name": "Test"},
                    "chat": {"id": 123},
                    "text": "/start"
                }
            }
        )
```

#### Passo 3: Executar teste
```bash
# Teste com 100 usuários simultâneos
locust -f locustfile.py --headless -u 100 -r 10 -t 60s --host http://localhost:5000
```

#### Passo 4: Analisar resultados
```bash
# Verificar logs
tail -f logs/error.log

# Verificar métricas
curl http://localhost:5000/health

# Verificar filas RQ
python -c "
from rq import Queue
from redis_manager import get_redis_connection
q = Queue('tasks', connection=get_redis_connection(False))
print(f'Queue size: {len(q)}')
print(f'Workers: {len(q.workers)}')
"
```

---

## VERIFICAÇÃO FINAL

### Checklist de Validação

- [ ] Redis Connection Pool funcionando
  - `python redis_manager.py` (sem erros)
  - Logs não mostram "nova conexão" a cada request
  
- [ ] Systemd services rodando
  - `sudo systemctl status grimbots` (active)
  - `sudo systemctl status 'rq-worker@*'` (11 workers ativos)
  
- [ ] Health check funcionando
  - `curl http://localhost:5000/health` (200 OK)
  - Todas as checks passando
  
- [ ] Auto-restart funcionando
  - Matar processo e verificar restart automático
  - Verificar logs: `sudo journalctl -u grimbots -f`

---

## ROLLBACK (Se necessário)

### Reverter para versão anterior

```bash
# 1. Parar serviços systemd
sudo systemctl stop grimbots
sudo systemctl stop 'rq-worker@*'

# 2. Restaurar código anterior
git stash
# ou
git checkout HEAD~1

# 3. Iniciar modo antigo
pkill -f gunicorn
pkill -f start_rq_worker
cd ~/grimbots
source venv/bin/activate
nohup gunicorn -c gunicorn_config.py wsgi:app > logs/gunicorn.log 2>&1 &
python start_rq_worker.py tasks &
python start_rq_worker.py gateway &
python start_rq_worker.py webhook &
```

---

## PRÓXIMOS PASSOS

Após concluir Fase 1 com sucesso:

1. ✅ Validar métricas (latência -50%, throughput +200%)
2. ✅ Monitorar por 24h
3. ✅ Iniciar Fase 2 (Migração PostgreSQL)

---

**Observações:**
- Fazer backup antes de cada mudança
- Testar em staging primeiro (se disponível)
- Monitorar logs durante deploy
- Ter plano de rollback pronto

