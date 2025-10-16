# 🚀 DEPLOY VPS - GRIMBOTS v2.1.0

**Versão:** 2.1.0  
**Data:** 16/10/2025  
**Atualizações:** Upsells + WiinPay + Correções Críticas

---

## 📋 PRÉ-REQUISITOS NA VPS

```bash
# Sistema
Ubuntu 20.04+ ou Debian 11+

# Software
Python 3.11+
Git
Nginx
PostgreSQL 14+ (recomendado) ou MySQL 8+

# Portas
80 (HTTP)
443 (HTTPS)
5000 (App - interno)
```

---

## 🔧 DEPLOY COMPLETO (PASSO A PASSO)

### 1. Conectar na VPS

```bash
ssh root@seu-ip-vps
```

### 2. Atualizar Sistema

```bash
apt update && apt upgrade -y
apt install -y python3.11 python3.11-venv python3-pip git nginx postgresql postgresql-contrib
```

### 3. Criar Usuário Dedicado

```bash
adduser grimbots
usermod -aG sudo grimbots
su - grimbots
```

### 4. Clonar Repositório

```bash
cd ~
git clone <seu-repositorio-git> grimbots
cd grimbots
```

### 5. Criar Virtual Environment

```bash
python3.11 -m venv venv
source venv/bin/activate
```

### 6. Instalar Dependências

```bash
pip install --upgrade pip
pip install -r requirements.txt
pip install gunicorn psycopg2-binary
```

### 7. Configurar .env

```bash
cp env.example .env
nano .env
```

**Editar .env:**
```bash
# OBRIGATÓRIAS
SECRET_KEY=<gerar: python -c "import secrets; print(secrets.token_hex(32))">
ENCRYPTION_KEY=<gerar: python -c "from cryptography.fernet import Fernet; print(Fernet.generate_key().decode())">

# Database (PostgreSQL recomendado)
DATABASE_URL=postgresql://grimbots:senha_forte@localhost/grimbots_db

# CORS (seu domínio)
ALLOWED_ORIGINS=https://seudominio.com,https://www.seudominio.com

# Webhook (para Telegram)
WEBHOOK_URL=https://seudominio.com

# WiinPay Split
WIINPAY_PLATFORM_USER_ID=6877edeba3c39f8451ba5bdd

# Flask
FLASK_ENV=production
PORT=5000
```

### 8. Configurar PostgreSQL

```bash
sudo -u postgres psql

CREATE DATABASE grimbots_db;
CREATE USER grimbots WITH PASSWORD 'senha_forte_aqui';
GRANT ALL PRIVILEGES ON DATABASE grimbots_db TO grimbots;
\q
```

### 9. Executar Migrations

```bash
# Inicializar banco
python init_db.py

# Migrations das novas features
python migrate_add_upsells.py
python migrate_add_wiinpay.py
python migrate_encrypt_credentials.py  # Se já tem gateways cadastrados

# Senha admin gerada em .admin_password
cat .admin_password
```

### 10. Configurar Gunicorn

```bash
nano gunicorn_config.py
```

**gunicorn_config.py:**
```python
import multiprocessing

# Server socket
bind = "127.0.0.1:5000"
backlog = 2048

# Worker processes
workers = multiprocessing.cpu_count() * 2 + 1
worker_class = "eventlet"  # Para Socket.IO
worker_connections = 1000
timeout = 120
keepalive = 5

# Logging
accesslog = "logs/access.log"
errorlog = "logs/error.log"
loglevel = "info"

# Process naming
proc_name = "grimbots"

# Server mechanics
daemon = False
pidfile = "grimbots.pid"
```

### 11. Criar Diretório de Logs

```bash
mkdir -p logs
touch logs/access.log logs/error.log
```

### 12. Configurar Systemd Service

```bash
sudo nano /etc/systemd/system/grimbots.service
```

**grimbots.service:**
```ini
[Unit]
Description=Grimbots v2.1.0 - Bot Manager SaaS
After=network.target postgresql.service

[Service]
Type=notify
User=grimbots
Group=grimbots
WorkingDirectory=/home/grimbots/grimbots
Environment="PATH=/home/grimbots/grimbots/venv/bin"
EnvironmentFile=/home/grimbots/grimbots/.env
ExecStart=/home/grimbots/grimbots/venv/bin/gunicorn -c gunicorn_config.py wsgi:app
ExecReload=/bin/kill -s HUP $MAINPID
KillMode=mixed
TimeoutStopSec=5
PrivateTmp=true
Restart=always
RestartSec=10

[Install]
WantedBy=multi-user.target
```

### 13. Configurar Nginx

```bash
sudo nano /etc/nginx/sites-available/grimbots
```

**nginx config:**
```nginx
upstream grimbots_app {
    server 127.0.0.1:5000 fail_timeout=0;
}

server {
    listen 80;
    server_name seudominio.com www.seudominio.com;
    
    client_max_body_size 20M;
    
    # Redirecionar para HTTPS
    return 301 https://$server_name$request_uri;
}

server {
    listen 443 ssl http2;
    server_name seudominio.com www.seudominio.com;
    
    # SSL (Certbot vai configurar)
    # ssl_certificate /etc/letsencrypt/live/seudominio.com/fullchain.pem;
    # ssl_certificate_key /etc/letsencrypt/live/seudominio.com/privkey.pem;
    
    client_max_body_size 20M;
    
    # Logs
    access_log /var/log/nginx/grimbots_access.log;
    error_log /var/log/nginx/grimbots_error.log;
    
    # Static files
    location /static {
        alias /home/grimbots/grimbots/static;
        expires 30d;
        add_header Cache-Control "public, immutable";
    }
    
    # WebSocket (Socket.IO)
    location /socket.io {
        proxy_pass http://grimbots_app/socket.io;
        proxy_http_version 1.1;
        proxy_buffering off;
        proxy_set_header Upgrade $http_upgrade;
        proxy_set_header Connection "Upgrade";
        proxy_set_header Host $host;
        proxy_set_header X-Real-IP $remote_addr;
        proxy_set_header X-Forwarded-For $proxy_add_x_forwarded_for;
        proxy_set_header X-Forwarded-Proto $scheme;
    }
    
    # Application
    location / {
        proxy_pass http://grimbots_app;
        proxy_set_header Host $host;
        proxy_set_header X-Real-IP $remote_addr;
        proxy_set_header X-Forwarded-For $proxy_add_x_forwarded_for;
        proxy_set_header X-Forwarded-Proto $scheme;
        proxy_redirect off;
        
        # Timeouts
        proxy_connect_timeout 60s;
        proxy_send_timeout 60s;
        proxy_read_timeout 60s;
    }
}
```

**Ativar site:**
```bash
sudo ln -s /etc/nginx/sites-available/grimbots /etc/nginx/sites-enabled/
sudo nginx -t
sudo systemctl reload nginx
```

### 14. Configurar SSL (HTTPS)

```bash
# Instalar Certbot
sudo apt install -y certbot python3-certbot-nginx

# Gerar certificado
sudo certbot --nginx -d seudominio.com -d www.seudominio.com

# Auto-renewal (já configurado)
sudo systemctl status certbot.timer
```

### 15. Iniciar Serviço

```bash
# Habilitar e iniciar
sudo systemctl enable grimbots
sudo systemctl start grimbots

# Verificar status
sudo systemctl status grimbots

# Ver logs
sudo journalctl -u grimbots -f
```

---

## 🔄 ATUALIZAR DEPLOY EXISTENTE

Se já tem v2.0 rodando:

```bash
# 1. Conectar na VPS
ssh grimbots@seu-ip

# 2. Ir para pasta
cd ~/grimbots

# 3. Backup do banco (IMPORTANTE)
cp instance/grpay.db instance/grpay.db.backup.$(date +%Y%m%d)

# 4. Pull das mudanças
git pull origin main

# 5. Ativar venv
source venv/bin/activate

# 6. Atualizar deps (se necessário)
pip install -r requirements.txt

# 7. Executar migrations
python migrate_add_upsells.py
python migrate_add_wiinpay.py

# 8. Reiniciar serviço
sudo systemctl restart grimbots

# 9. Verificar
sudo systemctl status grimbots
curl http://localhost:5000/api/health  # Se tiver endpoint
```

---

## ✅ VERIFICAÇÃO PÓS-DEPLOY

### 1. Testar Site
```bash
curl https://seudominio.com
# Deve retornar HTML da página de login
```

### 2. Testar WebSocket
```
Abrir navegador → https://seudominio.com
Abrir DevTools → Network → WS
Verificar conexão Socket.IO
```

### 3. Testar Login
```
1. Acessar https://seudominio.com
2. Login: admin@grimbots.com
3. Senha: (ver .admin_password)
4. Deve entrar no dashboard
```

### 4. Testar Gateway
```
1. Settings → Gateways
2. Configurar WiinPay:
   - API Key: sua_key
   - Split User ID: 6877edeba3c39f8451ba5bdd (já preenchido)
3. Salvar
4. Badge deve mudar para "ATIVO"
```

### 5. Testar Bot
```
1. Criar bot de teste
2. Iniciar bot
3. Enviar /start no Telegram
4. Verificar mensagem de boas-vindas
```

### 6. Testar Upsell
```
1. Configurar upsell em /bots/{id}/config
2. Fazer compra de teste
3. Simular pagamento
4. Verificar se upsell foi enviado
```

---

## 📁 ARQUIVOS ESSENCIAIS PARA VPS

### Devem estar no repositório:
```
✅ app.py, models.py, bot_manager.py
✅ gateway_*.py (todos os 7 arquivos)
✅ ranking_engine_v2.py
✅ achievement_checker_v2.py
✅ gamification_websocket.py
✅ utils/encryption.py
✅ migrate_*.py (todos)
✅ init_db.py
✅ wsgi.py
✅ requirements.txt
✅ env.example
✅ templates/ (todos)
✅ static/ (todos)
✅ docs/ (8 arquivos essenciais)
```

### NÃO commitar:
```
❌ .env (criar manualmente na VPS)
❌ .admin_password (gerado automaticamente)
❌ instance/ (banco de dados)
❌ venv/ (criar na VPS)
❌ __pycache__/
❌ *.pyc
❌ logs/
❌ .DS_Store
```

---

## 🔐 VARIÁVEIS DE AMBIENTE OBRIGATÓRIAS

```bash
# .env na VPS
SECRET_KEY=<64+ caracteres hex>
ENCRYPTION_KEY=<Fernet key base64>
DATABASE_URL=postgresql://user:pass@localhost/grimbots_db
ALLOWED_ORIGINS=https://seudominio.com
WEBHOOK_URL=https://seudominio.com
WIINPAY_PLATFORM_USER_ID=6877edeba3c39f8451ba5bdd
FLASK_ENV=production
```

---

## 🐛 TROUBLESHOOTING

### Erro: "ModuleNotFoundError"
```bash
# Ativar venv
source venv/bin/activate
pip install -r requirements.txt
```

### Erro: "ENCRYPTION_KEY não configurado"
```bash
python -c "from cryptography.fernet import Fernet; print(Fernet.generate_key().decode())"
# Copiar output para .env
```

### Erro: "Port 5000 already in use"
```bash
# Parar processo antigo
sudo systemctl stop grimbots
sudo lsof -ti:5000 | xargs kill -9
sudo systemctl start grimbots
```

### Nginx 502 Bad Gateway
```bash
# Verificar se app está rodando
sudo systemctl status grimbots

# Ver logs
sudo journalctl -u grimbots -n 50

# Reiniciar
sudo systemctl restart grimbots
```

---

## 📊 MONITORAMENTO

### Logs em Tempo Real
```bash
# App logs
tail -f logs/error.log

# Systemd logs
sudo journalctl -u grimbots -f

# Nginx logs
tail -f /var/log/nginx/grimbots_error.log
```

### Verificar Processos
```bash
# Workers Gunicorn
ps aux | grep gunicorn

# Uso de memória
free -h

# Uso de disco
df -h
```

---

## 🔄 ROLLBACK (Se Der Problema)

```bash
# 1. Parar serviço
sudo systemctl stop grimbots

# 2. Voltar commit anterior
git log --oneline  # Ver commits
git checkout <hash-anterior>

# 3. Restaurar banco
cp instance/grpay.db.backup.20251016 instance/grpay.db

# 4. Reiniciar
sudo systemctl start grimbots
```

---

## ✅ CHECKLIST PÓS-DEPLOY

- [ ] Site acessível via HTTPS
- [ ] Login funciona
- [ ] Dashboard carrega
- [ ] WebSocket conecta (verificar DevTools)
- [ ] Bot cria e inicia
- [ ] PIX gera corretamente
- [ ] Webhook recebe confirmações
- [ ] Upsells funcionam
- [ ] WiinPay ativo
- [ ] Split de 4% configurado
- [ ] Logs sem erros
- [ ] SSL válido (cadeado verde)

---

## 🎯 COMANDOS ÚTEIS

```bash
# Reiniciar app
sudo systemctl restart grimbots

# Ver status
sudo systemctl status grimbots

# Ver logs (últimas 100 linhas)
sudo journalctl -u grimbots -n 100

# Recarregar Nginx
sudo systemctl reload nginx

# Testar Nginx config
sudo nginx -t

# Atualizar código
git pull origin main
sudo systemctl restart grimbots
```

---

## 📞 SUPORTE

**Documentação:** `docs/DOCUMENTACAO_COMPLETA.md`  
**Changelog:** `CHANGELOG_v2.1.0.md`  
**Gateways:** `docs/GATEWAYS_README.md`

---

**Versão:** 2.1.0  
**Status:** ✅ Production-Ready  
**Score:** 10/10

