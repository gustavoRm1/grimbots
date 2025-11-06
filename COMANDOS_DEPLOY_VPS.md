# Comandos para Deploy na VPS

## Opção 1: Usar o script automatizado (recomendado)

```bash
cd ~/grimbots
chmod +x deploy_update.sh
./deploy_update.sh
```

## Opção 2: Executar comandos manualmente

### 1. Fazer commit das mudanças locais

```bash
cd ~/grimbots
git add -A
git commit -m "fix: QI 10000 - Lock específico para texto completo após mídia (anti-duplicação)"
```

**OU** se preferir fazer stash (salvar temporariamente sem commit):

```bash
git stash save "Mudanças locais antes do pull"
```

### 2. Fazer pull do repositório

```bash
git pull origin main
```

Se usou stash, aplicar as mudanças novamente:

```bash
git stash pop
```

### 3. Parar o Gunicorn atual

```bash
# Verificar processos rodando
ps aux | grep gunicorn

# Parar processos
pkill -f gunicorn

# Se não parar, forçar
pkill -9 -f gunicorn

# Aguardar 2 segundos
sleep 2

# Verificar se parou
ps aux | grep gunicorn
```

### 4. Remover arquivo PID antigo (se existir)

```bash
rm -f grimbots.pid
```

### 5. Ativar ambiente virtual e iniciar Gunicorn

```bash
# Ativar venv
source venv/bin/activate

# Iniciar Gunicorn em background
cd ~/grimbots
nohup gunicorn -c gunicorn_config.py wsgi:app > logs/gunicorn.log 2>&1 &

# OU se não tiver gunicorn_config.py:
nohup gunicorn --worker-class eventlet -w 1 --bind 127.0.0.1:5000 --timeout 120 --access-logfile logs/access.log --error-logfile logs/error.log wsgi:app > logs/gunicorn.log 2>&1 &
```

### 6. Verificar se está rodando

```bash
# Ver processos
ps aux | grep gunicorn

# Ver logs
tail -f logs/error.log
tail -f logs/gunicorn.log
```

## Verificação pós-deploy

### Verificar se o lock está funcionando

Após reiniciar, teste enviando `/start` e monitore os logs:

```bash
tail -f logs/error.log | grep -E "(🚀|⛔|🔒|🔓|✅ Texto completo)"
```

**Resultado esperado:**
- `🔒 Lock de texto completo adquirido` (1 vez)
- `🚀 REQUISIÇÃO ÚNICA: Enviando texto completo` (1 vez)
- `✅ Texto completo enviado` (1 vez)
- `🔓 Lock de texto completo liberado` (1 vez)

Se aparecer `⛔ TEXTO COMPLETO já está sendo enviado`, o lock está funcionando corretamente.

## Troubleshooting

### Se o Gunicorn não iniciar

```bash
# Verificar erros
cat logs/gunicorn.log
cat logs/error.log

# Verificar se a porta está em uso
netstat -tulpn | grep 5000

# Verificar dependências
pip list | grep gunicorn
pip list | grep eventlet
```

### Se houver conflitos no git

```bash
# Ver conflitos
git status

# Resolver manualmente ou descartar mudanças locais
git checkout -- .
git pull origin main
```

### Se precisar reiniciar apenas (sem pull)

```bash
pkill -f gunicorn
sleep 2
cd ~/grimbots
source venv/bin/activate
nohup gunicorn -c gunicorn_config.py wsgi:app > logs/gunicorn.log 2>&1 &
```

