# Como Iniciar os Workers RQ (Redis Queue)

## Arquitetura Enterprise Restaurada

O sistema agora usa a arquitetura distribuída original com múltiplos workers RQ para processamento paralelo de campanhas remarketing.

## Iniciar Workers

### 1. Worker Marathon (Remarketing Massivo)
```bash
python start_rq_worker.py marathon
```
- Processa campanhas de remarketing com timeout de 12h
- Suporta 50K+ leads com Marathon Engine
- FloodWait handling e Network Timeout recovery

### 2. Worker Tasks (Telegram Urgente)
```bash
python start_rq_worker.py tasks
```
- Processa mensagens /start, tracking e operações urgentes
- Baixa latência para interações em tempo real

### 3. Worker Gateway (PIX/Pagamentos)
```bash
python start_rq_worker.py gateway
```
- Processa reconciliações, downsells, upsells
- Operações financeiras críticas

### 4. Worker Webhook
```bash
python start_rq_worker.py webhook
```
- Processa webhooks de pagamento
- Eventos assíncronos de gateways

## Iniciar Todos os Workers (Produção)
```bash
# Iniciar todos em background
python start_rq_worker.py marathon &
python start_rq_worker.py tasks &
python start_rq_worker.py gateway &
python start_rq_worker.py webhook &

# Ou iniciar todos de uma vez
python start_rq_worker.py
```

## Verificar Status dos Workers

### Monitorar Filas
```python
# Verificar jobs pendentes
from tasks_async import marathon_queue, task_queue, gateway_queue, webhook_queue

print(f"Marathon: {len(marathon_queue)} jobs")
print(f"Tasks: {len(task_queue)} jobs")
print(f"Gateway: {len(gateway_queue)} jobs")
print(f"Webhook: {len(webhook_queue)} jobs")
```

### Limpar Filas (se necessário)
```bash
python clear_rq_queues.py
```

## Configuração Redis

- **Broker:** `redis://localhost:6379/0`
- **Backend:** `redis://localhost:6379/1`
- **Connection Pool:** Ativado para performance
- **Timeout:** 12h para campanhas massivas

## Performance

- **Throughput:** 10K+ leads/hora por worker
- **Paralelismo:** Múltiplos workers simultâneos
- **Resiliência:** Auto-reconexão e retry automático
- **Escalabilidade:** Horizontal via múltiplos processos

## Troubleshooting

### Worker não inicia
```bash
# Verificar Redis
redis-cli ping

# Verificar logs
python start_rq_worker.py marathon 2>&1 | grep ERROR
```

### Jobs empilhados
```bash
# Limpar filas danificadas
python clear_rq_queues.py

# Reiniciar workers
pkill -f "start_rq_worker.py"
```

## Arquitetura vs Anterior

| Anterior (Single-thread) | Atual (RQ Distribuído) |
|------------------------|------------------------|
| 1 processo sequencial | Múltiplos workers paralelos |
| Gargalo de performance | Escalável horizontalmente |
| Sem resiliência | Auto-reconexão e retry |
| Timeout limitado | 12h para campanhas massivas |

A arquitetura enterprise foi **totalmente restaurada**!
