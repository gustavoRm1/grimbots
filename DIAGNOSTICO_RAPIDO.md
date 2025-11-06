# Diagnóstico Rápido - Workers RQ Falhando

## Passo 1: Ver Logs do Systemd

```bash
sudo journalctl -u rq-worker-tasks -n 50 --no-pager
```

Isso vai mostrar o erro exato. Os erros mais comuns são:

### Erro 1: "No module named 'rq'"
**Solução:**
```bash
source venv/bin/activate
pip install rq
```

### Erro 2: "Connection refused" (Redis)
**Solução:**
```bash
sudo systemctl start redis
redis-cli ping  # Deve retornar PONG
```

### Erro 3: "No such file or directory" (caminho)
**Solução:**
Verificar se o caminho no arquivo `.service` está correto:
```bash
cat /etc/systemd/system/rq-worker-tasks.service
```

Ajustar se necessário:
- `WorkingDirectory=/root/grimbots`
- `ExecStart=/root/grimbots/venv/bin/python start_rq_worker.py tasks`

## Passo 2: Testar Manualmente

```bash
cd /root/grimbots
source venv/bin/activate
python start_rq_worker.py tasks
```

Se funcionar manualmente, o problema é no systemd. Se não funcionar, ver o erro na tela.

## Passo 3: Usar Script de Diagnóstico

```bash
chmod +x fix_workers.sh
bash fix_workers.sh
```

O script vai:
1. Verificar logs
2. Verificar Redis
3. Verificar RQ instalado
4. Testar execução manual
5. Reiniciar serviços

## Passo 4: Solução Rápida (Nohup)

Se systemd continuar dando problema, use nohup:

```bash
cd /root/grimbots
source venv/bin/activate

# Criar diretório de logs
mkdir -p logs

# Iniciar workers
nohup python start_rq_worker.py tasks > logs/rq-tasks.log 2>&1 &
nohup python start_rq_worker.py gateway > logs/rq-gateway.log 2>&1 &
nohup python start_rq_worker.py webhook > logs/rq-webhook.log 2>&1 &

# Verificar se estão rodando
ps aux | grep "start_rq_worker"

# Ver logs
tail -f logs/rq-tasks.log
```

## Comandos Úteis

```bash
# Ver status
sudo systemctl status rq-worker-tasks

# Ver logs em tempo real
sudo journalctl -u rq-worker-tasks -f

# Reiniciar
sudo systemctl restart rq-worker-tasks

# Parar
sudo systemctl stop rq-worker-tasks

# Ver processos Python
ps aux | grep python
```

