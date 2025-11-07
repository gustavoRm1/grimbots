# 🔧 SOLUÇÃO: Porta 5000 em Uso / Systemd Não Inicia

## Problema Identificado

```
Process: 815234 ExecStart=... (code=exited, status=217/USER)
```

**Erro 217/USER:** Usuário "grimbots" não existe, mas o service está configurado para rodar como esse usuário.

---

## ✅ SOLUÇÃO AUTOMÁTICA (RECOMENDADO)

Execute o script que detecta automaticamente suas configurações:

```bash
cd ~/grimbots
chmod +x setup_systemd.sh start_system.sh
./setup_systemd.sh
./start_system.sh
```

**O que faz:**
1. Detecta usuário atual (root)
2. Detecta diretório atual (/root/grimbots)
3. Lê .env (DATABASE_URL, SECRET_KEY, REDIS_URL)
4. Gera services corretos automaticamente
5. Instala e inicia tudo

---

## ✅ SOLUÇÃO MANUAL

### Passo 1: Editar grimbots.service

```bash
sudo nano /etc/systemd/system/grimbots.service
```

**Ajustar estas linhas:**
```ini
# ANTES:
User=grimbots
Group=grimbots
WorkingDirectory=/opt/grimbots
Environment="PATH=/opt/grimbots/venv/bin:..."
ExecStart=/opt/grimbots/venv/bin/gunicorn -c /opt/grimbots/gunicorn_config.py wsgi:app

# DEPOIS:
User=root
Group=root
WorkingDirectory=/root/grimbots
Environment="PATH=/root/grimbots/venv/bin:/usr/local/bin:/usr/bin:/bin"
ExecStart=/root/grimbots/venv/bin/gunicorn -c /root/grimbots/gunicorn_config.py wsgi:app
```

**Salvar:** Ctrl+O, Enter, Ctrl+X

### Passo 2: Editar rq-worker@.service

```bash
sudo nano /etc/systemd/system/rq-worker@.service
```

**Ajustar as mesmas linhas** (User, Group, WorkingDirectory, PATH, ExecStart)

**Salvar:** Ctrl+O, Enter, Ctrl+X

### Passo 3: Recarregar e iniciar

```bash
# Recarregar
sudo systemctl daemon-reload

# Parar processos antigos
pkill -9 python
pkill -9 gunicorn
fuser -k 5000/tcp
sleep 3

# Iniciar
sudo systemctl start grimbots

# Verificar
sudo systemctl status grimbots

# Se estiver rodando, iniciar workers
for i in {1..5}; do sudo systemctl start rq-worker@tasks-$i; done
for i in {1..3}; do sudo systemctl start rq-worker@gateway-$i; done
for i in {1..3}; do sudo systemctl start rq-worker@webhook-$i; done

# Verificar tudo
sudo systemctl status grimbots 'rq-worker@*' | grep -E "Loaded|Active"
```

---

## 🔍 DEBUG: Ver Logs de Erro

```bash
# Ver erro específico do systemd
sudo journalctl -u grimbots -n 50

# Ver apenas erros
sudo journalctl -u grimbots -p err -n 20

# Ver em tempo real
sudo journalctl -u grimbots -f
```

---

## ⚡ ALTERNATIVA: Rodar SEM Systemd (Temporário)

Se systemd não funcionar, use este método temporário:

```bash
cd ~/grimbots
source venv/bin/activate

# Matar tudo
pkill -9 python; pkill -9 gunicorn; fuser -k 5000/tcp
sleep 3

# Iniciar Gunicorn
nohup gunicorn -c gunicorn_config.py wsgi:app > logs/gunicorn.log 2>&1 &

# Aguardar
sleep 5

# Verificar
ps aux | grep gunicorn
lsof -i:5000

# Iniciar RQ Workers
for i in {1..5}; do 
    nohup python start_rq_worker.py tasks > logs/rq-tasks-$i.log 2>&1 &
done

for i in {1..3}; do 
    nohup python start_rq_worker.py gateway > logs/rq-gateway-$i.log 2>&1 &
done

for i in {1..3}; do 
    nohup python start_rq_worker.py webhook > logs/rq-webhook-$i.log 2>&1 &
done

# Verificar
ps aux | grep start_rq_worker | wc -l
# Deve mostrar 11
```

**Desvantagem:** Sem auto-restart, precisa configurar systemd depois

---

## 🎯 VALIDAÇÃO FINAL

Após iniciar, verifique:

```bash
# 1. Gunicorn rodando
sudo systemctl status grimbots
# Deve mostrar: Active: active (running)

# 2. RQ Workers rodando
sudo systemctl status 'rq-worker@*' | grep "active (running)" | wc -l
# Deve mostrar: 11

# 3. Porta 5000 em uso
lsof -i:5000
# Deve mostrar processo Gunicorn

# 4. Health check
curl http://localhost:5000/health
# Deve retornar JSON com "status": "healthy"

# 5. Teste completo
chmod +x verificar_sistema.sh
./verificar_sistema.sh
# Deve mostrar: ✅ SISTEMA TOTALMENTE OPERACIONAL
```

---

## 🚨 TROUBLESHOOTING COMUM

### Erro: "User grimbots not found"
**Solução:** Editar service para usar `User=root` (seu usuário atual)

### Erro: "No such file or directory: /opt/grimbots"
**Solução:** Editar service para usar `WorkingDirectory=/root/grimbots` (seu diretório)

### Erro: "Connection in use: ('127.0.0.1', 5000)"
**Solução:** Matar processo usando a porta
```bash
fuser -k 5000/tcp
lsof -ti:5000 | xargs kill -9
```

### Erro: "ModuleNotFoundError: No module named 'redis_manager'"
**Solução:** Verificar se arquivo existe e PYTHONPATH está correto
```bash
ls -la redis_manager.py
export PYTHONPATH=$(pwd)
python -c "from redis_manager import get_redis_connection"
```

---

## ✅ SCRIPTS DISPONÍVEIS

1. **`setup_systemd.sh`** - Configura systemd automaticamente
2. **`start_system.sh`** - Inicia sistema completo
3. **`verificar_sistema.sh`** - Valida tudo

**Uso:**
```bash
chmod +x setup_systemd.sh start_system.sh verificar_sistema.sh
./setup_systemd.sh  # Configurar
./start_system.sh   # Iniciar
./verificar_sistema.sh  # Validar
```

---

**Resultado esperado:** Sistema rodando com systemd, 11 workers, health check ativo

