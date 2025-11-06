# Configuração Systemd - Grimbots

## Instalação

### 1. Copiar arquivos de service

```bash
sudo cp deploy/systemd/grimbots.service /etc/systemd/system/
sudo cp deploy/systemd/rq-worker@.service /etc/systemd/system/
```

### 2. Editar configurações

**grimbots.service:**
```bash
sudo nano /etc/systemd/system/grimbots.service
```

Ajustar:
- `User=grimbots` (seu usuário)
- `Group=grimbots` (seu grupo)
- `WorkingDirectory=/opt/grimbots` (seu diretório)
- `DATABASE_URL=postgresql://...` (sua URL do banco)
- `SECRET_KEY=...` (sua secret key)

**rq-worker@.service:**
```bash
sudo nano /etc/systemd/system/rq-worker@.service
```

Ajustar:
- `User=grimbots`
- `Group=grimbots`
- `WorkingDirectory=/opt/grimbots`
- `DATABASE_URL=postgresql://...`

### 3. Recarregar systemd

```bash
sudo systemctl daemon-reload
```

### 4. Habilitar serviços (auto-start)

```bash
# Gunicorn
sudo systemctl enable grimbots

# RQ Workers
# Criar 5 workers para 'tasks'
sudo systemctl enable rq-worker@tasks-1
sudo systemctl enable rq-worker@tasks-2
sudo systemctl enable rq-worker@tasks-3
sudo systemctl enable rq-worker@tasks-4
sudo systemctl enable rq-worker@tasks-5

# Criar 3 workers para 'gateway'
sudo systemctl enable rq-worker@gateway-1
sudo systemctl enable rq-worker@gateway-2
sudo systemctl enable rq-worker@gateway-3

# Criar 3 workers para 'webhook'
sudo systemctl enable rq-worker@webhook-1
sudo systemctl enable rq-worker@webhook-2
sudo systemctl enable rq-worker@webhook-3
```

### 5. Iniciar serviços

```bash
# Gunicorn
sudo systemctl start grimbots

# RQ Workers
sudo systemctl start rq-worker@tasks-{1..5}
sudo systemctl start rq-worker@gateway-{1..3}
sudo systemctl start rq-worker@webhook-{1..3}
```

## Comandos Úteis

### Status

```bash
# Gunicorn
sudo systemctl status grimbots

# Todos os RQ workers
sudo systemctl status 'rq-worker@*'

# Worker específico
sudo systemctl status rq-worker@tasks-1
```

### Logs

```bash
# Gunicorn (últimas 100 linhas)
sudo journalctl -u grimbots -n 100

# Gunicorn (tempo real)
sudo journalctl -u grimbots -f

# Todos os RQ workers
sudo journalctl -u 'rq-worker@*' -f

# Worker específico
sudo journalctl -u rq-worker@tasks-1 -f
```

### Restart

```bash
# Gunicorn
sudo systemctl restart grimbots

# Todos os RQ workers de uma fila
sudo systemctl restart rq-worker@tasks-{1..5}

# Worker específico
sudo systemctl restart rq-worker@tasks-1
```

### Stop/Start

```bash
# Parar
sudo systemctl stop grimbots
sudo systemctl stop 'rq-worker@*'

# Iniciar
sudo systemctl start grimbots
sudo systemctl start rq-worker@tasks-{1..5}
```

### Reload (graceful restart)

```bash
# Reload Gunicorn sem downtime
sudo systemctl reload grimbots
```

## Verificação

### Verificar se está rodando

```bash
# Ver processos
ps aux | grep gunicorn
ps aux | grep 'start_rq_worker'

# Ver portas
sudo lsof -i:5000
sudo netstat -tulpn | grep :5000
```

### Verificar logs de erro

```bash
# Gunicorn
sudo journalctl -u grimbots -p err

# RQ Workers
sudo journalctl -u 'rq-worker@*' -p err
```

## Troubleshooting

### Serviço não inicia

```bash
# Ver erro específico
sudo systemctl status grimbots -l

# Ver logs completos
sudo journalctl -xe
```

### Permissões

```bash
# Verificar se usuário existe
id grimbots

# Verificar permissões do diretório
ls -la /opt/grimbots

# Ajustar permissões se necessário
sudo chown -R grimbots:grimbots /opt/grimbots
sudo chmod -R 755 /opt/grimbots
```

### Porta em uso

```bash
# Ver o que está usando a porta 5000
sudo lsof -i:5000

# Matar processo
sudo kill -9 <PID>
```

## Auto-restart em caso de falha

Os serviços estão configurados com `Restart=always`, o que significa:
- Se o processo crashar, será reiniciado automaticamente em 10 segundos
- Restart infinito (sem limite de tentativas)
- Logs de restart no journalctl

## Logs Persistentes

Por padrão, os logs do systemd são persistentes. Para garantir:

```bash
# Habilitar persistência
sudo mkdir -p /var/log/journal
sudo systemctl restart systemd-journald

# Ver espaço usado
sudo journalctl --disk-usage

# Limpar logs antigos (manter últimos 7 dias)
sudo journalctl --vacuum-time=7d
```

## Health Check

Adicione um cronjob para verificar saúde:

```bash
# Criar script de health check
cat > /opt/grimbots/health_check.sh << 'EOF'
#!/bin/bash
if ! systemctl is-active --quiet grimbots; then
    echo "❌ Grimbots is down!"
    # Enviar alerta (email, Telegram, etc)
fi
EOF

chmod +x /opt/grimbots/health_check.sh

# Adicionar ao crontab (verificar a cada 5 minutos)
(crontab -l 2>/dev/null; echo "*/5 * * * * /opt/grimbots/health_check.sh") | crontab -
```

