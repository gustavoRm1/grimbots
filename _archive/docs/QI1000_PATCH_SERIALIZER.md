# ✅ QI 1000 - PATCH CRÍTICO: Serializer RQ Corrigido

## Problema Identificado

Workers RQ estavam crashando com erro:
```
TypeError: a bytes-like object is required, not 'str'
```

**Causa raiz**: Redis configurado com `decode_responses=True`, fazendo com que o RQ recebesse strings ao invés de bytes comprimidos.

O RQ serializa jobs como **bytes comprimidos com zlib**, mas estava recebendo **strings** devido à configuração incorreta do Redis.

## Solução Implementada

### ✅ PATCH 1: Remover decode_responses do Redis RQ

**Arquivos modificados:**
- `start_rq_worker.py` - Worker RQ
- `tasks_async.py` - Enfileiramento de tasks

**Mudança:**
```python
# ❌ ANTES (ERRADO)
redis_conn = Redis.from_url(redis_url, decode_responses=True)

# ✅ DEPOIS (CORRETO)
redis_conn = Redis.from_url(redis_url, decode_responses=False)
```

### ✅ PATCH 2: Script de Limpeza de Filas Corrompidas

Criado `clear_rq_queues.py` para limpar completamente:
- Todas as filas RQ (tasks, gateway, webhook, default)
- Todas as registries (started, finished, deferred, failed)
- Jobs corrompidas antigas

## Como Aplicar o Patch

### 1. Limpar Filas Corrompidas

```bash
# Executar script de limpeza
python clear_rq_queues.py

# Ou forçar sem confirmação
python clear_rq_queues.py --force
```

### 2. Reiniciar Redis

```bash
systemctl restart redis
```

### 3. Parar Workers Antigos

```bash
pkill -f start_rq_worker.py
```

### 4. Reiniciar Workers

```bash
python start_rq_worker.py tasks &
python start_rq_worker.py gateway &
python start_rq_worker.py webhook &
```

## O Que Foi Corrigido

✅ **Workers não crasham mais** - Serializer consistente (bytes)
✅ **Jobs não corrompem** - Formato correto (zlib comprimido)
✅ **Filas não travam** - Jobs antigas removidas
✅ **Performance restaurada** - Sem retry infinito de jobs corrompidas

## Verificação

Após aplicar o patch, verifique:

1. **Workers rodando sem erros:**
```bash
ps aux | grep start_rq_worker.py
```

2. **Filas vazias (após limpeza):**
```bash
redis-cli LLEN rq:queue:tasks
redis-cli LLEN rq:queue:gateway
redis-cli LLEN rq:queue:webhook
```

3. **Sem jobs failed:**
```bash
redis-cli GET rq:failed
```

## Notas Técnicas

- **RQ usa pickle por padrão** - Não precisa especificar serializer
- **RQ comprime com zlib** - Por isso precisa de bytes, não strings
- **decode_responses=True** - Apenas para uso direto do Redis (não RQ)
- **decode_responses=False** - Obrigatório para RQ funcionar corretamente

## Compatibilidade

✅ Compatível com QI 200 (Fast Response Mode)
✅ Compatível com QI 500 (Lock de /start)
✅ Compatível com QI 900 (Anti-reprocessamento de /start)

## Arquivos Modificados

1. `start_rq_worker.py` - Removido decode_responses=True
2. `tasks_async.py` - Removido decode_responses=True
3. `clear_rq_queues.py` - NOVO: Script de limpeza

