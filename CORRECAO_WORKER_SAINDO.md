# Correção: Worker Saindo Imediatamente

## Problema
Worker inicia e sai com status 0 (SUCCESS) imediatamente, reiniciando constantemente.

## Causa
Jobs antigos/corrompidos na fila fazem o worker encontrar erro e sair.

## Solução

### Passo 1: Limpar Filas Antigas

```bash
cd /root/grimbots
source venv/bin/activate
python clear_rq_queues.py
```

### Passo 2: Verificar se Limpou

```bash
redis-cli
KEYS rq:*
# Se ainda houver chaves, DELETE manualmente
exit
```

### Passo 3: Reiniciar Workers

```bash
sudo systemctl restart rq-worker-tasks
sudo systemctl restart rq-worker-gateway
sudo systemctl restart rq-worker-webhook
```

### Passo 4: Verificar Logs

```bash
sudo journalctl -u rq-worker-tasks -f
```

Deve aparecer:
```
*** Listening on tasks...
```

E ficar rodando (não sair).

## Se Ainda Sair

### Opção 1: Limpar Redis Completamente (CUIDADO!)

```bash
redis-cli
FLUSHDB
exit
```

Isso apaga TUDO do Redis. Use apenas se necessário.

### Opção 2: Verificar se Worker Está Funcionando

```bash
# Testar manualmente
cd /root/grimbots
source venv/bin/activate
python start_rq_worker.py tasks
```

Se funcionar manualmente mas não no systemd, problema é na configuração do systemd.

### Opção 3: Usar Nohup (Temporário)

```bash
cd /root/grimbots
source venv/bin/activate
mkdir -p logs

# Parar systemd
sudo systemctl stop rq-worker-tasks rq-worker-gateway rq-worker-webhook

# Iniciar com nohup
nohup python start_rq_worker.py tasks > logs/rq-tasks.log 2>&1 &
nohup python start_rq_worker.py gateway > logs/rq-gateway.log 2>&1 &
nohup python start_rq_worker.py webhook > logs/rq-webhook.log 2>&1 &

# Verificar
ps aux | grep "start_rq_worker"
tail -f logs/rq-tasks.log
```

