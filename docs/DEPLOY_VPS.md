# 🚀 GUIA COMPLETO DE DEPLOY NA VPS - GRIMBOTS

## 📋 **REQUISITOS DA VPS**

- **SO:** Ubuntu 20.04 LTS ou superior
- **RAM:** Mínimo 2GB (Recomendado: 4GB)
- **CPU:** 2 cores
- **Disco:** 20GB SSD
- **Acesso:** SSH root ou sudo

---

## 📦 **PASSO 1: PREPARAR A VPS**

### 1.1 Conectar via SSH
```bash
ssh root@SEU_IP_VPS
# ou
ssh seu_usuario@SEU_IP_VPS
```

### 1.2 Atualizar o Sistema
```bash
apt update && apt upgrade -y
```

### 1.3 Instalar Dependências Base
```bash
apt install -y python3 python3-pip python3-venv nginx certbot python3-certbot-nginx git curl wget ufw
```

### 1.4 Criar Usuário para a Aplicação (Segurança)
```bash
adduser grimbots
usermod -aG sudo grimbots
su - grimbots
```

---

## 🔧 **PASSO 2: CONFIGURAR O PROJETO**

### 2.1 Clonar/Upload do Projeto
```bash
cd /home/grimbots
git clone SEU_REPOSITORIO grimbots-app
# OU fazer upload via SCP/FTP para /home/grimbots/grimbots-app
```

### 2.2 Criar Ambiente Virtual
```bash
cd /home/grimbots/grimbots-app
python3 -m venv venv
source venv/bin/activate
```

### 2.3 Instalar Dependências
```bash
pip install --upgrade pip
pip install -r requirements.txt
pip install gunicorn  # Servidor WSGI para produção
```

### 2.4 Criar Arquivo .env de Produção
```bash
nano .env
```

**Conteúdo do `.env`:**
```env
FLASK_ENV=production
SECRET_KEY=GERE_UMA_CHAVE_SECRETA_FORTE_AQUI_64_CARACTERES_MINIMO
DATABASE_URL=sqlite:///instance/saas_bot_manager.db
DEBUG=False
HOST=0.0.0.0
PORT=5000
```

**Gerar SECRET_KEY segura:**
```bash
python3 -c "import secrets; print(secrets.token_hex(32))"
```

### 2.5 Inicializar Banco de Dados
```bash
python3 init_db.py
```

### 2.6 Testar Aplicação
```bash
gunicorn --bind 0.0.0.0:5000 wsgi:app
# Ctrl+C para parar
```

---

## 🔐 **PASSO 3: CONFIGURAR FIREWALL (UFW)**

```bash
# Habilitar UFW
ufw enable

# Permitir SSH (IMPORTANTE - não se tranque fora!)
ufw allow 22/tcp
ufw allow OpenSSH

# Permitir HTTP e HTTPS
ufw allow 80/tcp
ufw allow 443/tcp

# Verificar status
ufw status
```

---

## 🌐 **PASSO 4: CONFIGURAR NGINX**

### 4.1 Criar Arquivo de Configuração
```bash
sudo nano /etc/nginx/sites-available/grimbots
```

**Conteúdo do arquivo `grimbots`:**
```nginx
server {
    listen 80;
    server_name seudominio.com www.seudominio.com;

    # Tamanho máximo de upload (para mídias)
    client_max_body_size 50M;

    # Logs
    access_log /var/log/nginx/grimbots_access.log;
    error_log /var/log/nginx/grimbots_error.log;

    # Arquivos estáticos
    location /static {
        alias /home/grimbots/grimbots-app/static;
        expires 30d;
        add_header Cache-Control "public, immutable";
    }

    # Proxy para a aplicação Flask/Gunicorn
    location / {
        proxy_pass http://127.0.0.1:5000;
        proxy_set_header Host $host;
        proxy_set_header X-Real-IP $remote_addr;
        proxy_set_header X-Forwarded-For $proxy_add_x_forwarded_for;
        proxy_set_header X-Forwarded-Proto $scheme;
        
        # WebSocket support (para Socket.IO)
        proxy_http_version 1.1;
        proxy_set_header Upgrade $http_upgrade;
        proxy_set_header Connection "upgrade";
        
        # Timeouts
        proxy_connect_timeout 60s;
        proxy_send_timeout 60s;
        proxy_read_timeout 60s;
    }

    # Socket.IO específico
    location /socket.io {
        proxy_pass http://127.0.0.1:5000/socket.io;
        proxy_http_version 1.1;
        proxy_buffering off;
        proxy_set_header Upgrade $http_upgrade;
        proxy_set_header Connection "Upgrade";
        proxy_set_header Host $host;
        proxy_set_header X-Real-IP $remote_addr;
        proxy_set_header X-Forwarded-For $proxy_add_x_forwarded_for;
    }
}
```

### 4.2 Habilitar Site
```bash
sudo ln -s /etc/nginx/sites-available/grimbots /etc/nginx/sites-enabled/
sudo rm /etc/nginx/sites-enabled/default  # Remover site padrão
```

### 4.3 Testar e Reiniciar Nginx
```bash
sudo nginx -t
sudo systemctl restart nginx
sudo systemctl enable nginx
```

---

## 🔒 **PASSO 5: CONFIGURAR SSL/HTTPS (Certbot)**

### 5.1 Instalar Certificado SSL
```bash
sudo certbot --nginx -d seudominio.com -d www.seudominio.com
```

**Durante a instalação:**
- Digite seu email
- Aceite os termos
- Escolha opção 2: Redirecionar HTTP para HTTPS

### 5.2 Testar Renovação Automática
```bash
sudo certbot renew --dry-run
```

### 5.3 Configurar Auto-Renovação (já vem configurado)
```bash
sudo systemctl status certbot.timer
```

---

## ⚙️ **PASSO 6: CONFIGURAR SYSTEMD SERVICE**

### 6.1 Criar Service File
```bash
sudo nano /etc/systemd/system/grimbots.service
```

**Conteúdo do `grimbots.service`:**
```ini
[Unit]
Description=grimbots - Bot Manager SAAS
After=network.target

[Service]
Type=notify
User=grimbots
Group=grimbots
WorkingDirectory=/home/grimbots/grimbots-app
Environment="PATH=/home/grimbots/grimbots-app/venv/bin"
ExecStart=/home/grimbots/grimbots-app/venv/bin/gunicorn \
    --workers 4 \
    --worker-class eventlet \
    --bind 127.0.0.1:5000 \
    --timeout 120 \
    --access-logfile /var/log/grimbots/access.log \
    --error-logfile /var/log/grimbots/error.log \
    --log-level info \
    wsgi:app

Restart=always
RestartSec=10

[Install]
WantedBy=multi-user.target
```

### 6.2 Criar Diretório de Logs
```bash
sudo mkdir -p /var/log/grimbots
sudo chown grimbots:grimbots /var/log/grimbots
```

### 6.3 Habilitar e Iniciar Service
```bash
sudo systemctl daemon-reload
sudo systemctl enable grimbots
sudo systemctl start grimbots
```

### 6.4 Verificar Status
```bash
sudo systemctl status grimbots
```

---

## 📊 **PASSO 7: MONITORAMENTO E LOGS**

### 7.1 Ver Logs em Tempo Real
```bash
# Logs da aplicação
sudo journalctl -u grimbots -f

# Logs do Nginx
sudo tail -f /var/log/nginx/grimbots_access.log
sudo tail -f /var/log/nginx/grimbots_error.log

# Logs do Gunicorn
sudo tail -f /var/log/grimbots/error.log
```

### 7.2 Comandos de Controle
```bash
# Parar aplicação
sudo systemctl stop grimbots

# Iniciar aplicação
sudo systemctl start grimbots

# Reiniciar aplicação
sudo systemctl restart grimbots

# Recarregar configuração (sem downtime)
sudo systemctl reload grimbots

# Status
sudo systemctl status grimbots
```

---

## 🔄 **PASSO 8: SCRIPT DE DEPLOY/UPDATE**

### 8.1 Criar Script de Deploy
```bash
nano /home/grimbots/deploy.sh
```

**Conteúdo do `deploy.sh`:**
```bash
#!/bin/bash
set -e

echo "🚀 Iniciando deploy do grimbots..."

# Ir para diretório do projeto
cd /home/grimbots/grimbots-app

# Backup do banco de dados
echo "📦 Fazendo backup do banco..."
cp instance/saas_bot_manager.db instance/saas_bot_manager.db.backup.$(date +%Y%m%d_%H%M%S)

# Atualizar código (se usando Git)
# echo "📥 Atualizando código..."
# git pull origin main

# Ativar ambiente virtual
echo "🔧 Ativando ambiente virtual..."
source venv/bin/activate

# Atualizar dependências
echo "📦 Atualizando dependências..."
pip install -r requirements.txt --upgrade

# Migrar banco de dados (se necessário)
# python3 migrate.py

# Reiniciar aplicação
echo "🔄 Reiniciando aplicação..."
sudo systemctl restart grimbots

# Verificar status
echo "✅ Verificando status..."
sudo systemctl status grimbots --no-pager

echo "✨ Deploy concluído com sucesso!"
```

### 8.2 Tornar Executável
```bash
chmod +x /home/grimbots/deploy.sh
```

### 8.3 Usar o Script
```bash
/home/grimbots/deploy.sh
```

---

## 💾 **PASSO 9: BACKUP AUTOMÁTICO**

### 9.1 Criar Script de Backup
```bash
sudo nano /home/grimbots/backup.sh
```

**Conteúdo do `backup.sh`:**
```bash
#!/bin/bash
set -e

BACKUP_DIR="/home/grimbots/backups"
DATE=$(date +%Y%m%d_%H%M%S)
DB_FILE="/home/grimbots/grimbots-app/instance/saas_bot_manager.db"

# Criar diretório de backup
mkdir -p $BACKUP_DIR

# Backup do banco de dados
cp $DB_FILE $BACKUP_DIR/db_backup_$DATE.db

# Comprimir backups antigos (mais de 7 dias)
find $BACKUP_DIR -name "*.db" -mtime +7 -exec gzip {} \;

# Deletar backups muito antigos (mais de 30 dias)
find $BACKUP_DIR -name "*.db.gz" -mtime +30 -delete

echo "✅ Backup realizado: db_backup_$DATE.db"
```

### 9.2 Tornar Executável
```bash
chmod +x /home/grimbots/backup.sh
```

### 9.3 Adicionar ao Cron (Backup diário às 3h da manhã)
```bash
crontab -e
```

**Adicionar esta linha:**
```
0 3 * * * /home/grimbots/backup.sh >> /var/log/grimbots/backup.log 2>&1
```

---

## 🔍 **PASSO 10: TROUBLESHOOTING**

### Aplicação não inicia
```bash
# Ver logs detalhados
sudo journalctl -u grimbots -n 100 --no-pager

# Testar manualmente
cd /home/grimbots/grimbots-app
source venv/bin/activate
gunicorn --bind 127.0.0.1:5000 wsgi:app
```

### Nginx retorna 502 Bad Gateway
```bash
# Verificar se a aplicação está rodando
sudo systemctl status grimbots

# Verificar logs do Nginx
sudo tail -f /var/log/nginx/grimbots_error.log

# Reiniciar tudo
sudo systemctl restart grimbots
sudo systemctl restart nginx
```

### Socket.IO não conecta
```bash
# Verificar configuração do Nginx
sudo nginx -t

# Verificar logs
sudo journalctl -u grimbots -f | grep -i socket
```

### Banco de dados corrompido
```bash
# Restaurar último backup
cd /home/grimbots/grimbots-app/instance
cp saas_bot_manager.db saas_bot_manager.db.corrupted
cp /home/grimbots/backups/db_backup_YYYYMMDD_HHMMSS.db saas_bot_manager.db
sudo systemctl restart grimbots
```

### Alto uso de CPU/Memória
```bash
# Ver processos
htop
ps aux | grep gunicorn

# Ajustar workers no service
sudo nano /etc/systemd/system/grimbots.service
# Reduzir --workers de 4 para 2
sudo systemctl daemon-reload
sudo systemctl restart grimbots
```

---

## 📈 **PASSO 11: OTIMIZAÇÕES DE PRODUÇÃO**

### 11.1 Configurar Swap (se tiver pouca RAM)
```bash
sudo fallocate -l 2G /swapfile
sudo chmod 600 /swapfile
sudo mkswap /swapfile
sudo swapon /swapfile
echo '/swapfile none swap sw 0 0' | sudo tee -a /etc/fstab
```

### 11.2 Otimizar Nginx
```bash
sudo nano /etc/nginx/nginx.conf
```

**Adicionar/ajustar:**
```nginx
user www-data;
worker_processes auto;
worker_rlimit_nofile 65535;

events {
    worker_connections 4096;
    use epoll;
    multi_accept on;
}

http {
    # Gzip
    gzip on;
    gzip_vary on;
    gzip_proxied any;
    gzip_comp_level 6;
    gzip_types text/plain text/css text/xml text/javascript application/json application/javascript application/xml+rss;
    
    # Cache de arquivos estáticos
    open_file_cache max=1000 inactive=20s;
    open_file_cache_valid 30s;
    open_file_cache_min_uses 2;
    open_file_cache_errors on;
}
```

### 11.3 Configurar Fail2Ban (Segurança)
```bash
sudo apt install fail2ban -y
sudo systemctl enable fail2ban
sudo systemctl start fail2ban
```

---

## 🎯 **CHECKLIST FINAL**

- [ ] VPS atualizada e configurada
- [ ] Usuário `grimbots` criado
- [ ] Projeto instalado em `/home/grimbots/grimbots-app`
- [ ] Ambiente virtual criado e dependências instaladas
- [ ] Arquivo `.env` configurado com SECRET_KEY forte
- [ ] Banco de dados inicializado
- [ ] Firewall (UFW) configurado
- [ ] Nginx instalado e configurado
- [ ] SSL/HTTPS funcionando (Certbot)
- [ ] Systemd service criado e ativo
- [ ] Logs funcionando corretamente
- [ ] Backup automático configurado (cron)
- [ ] DNS apontando para o IP da VPS
- [ ] Aplicação acessível via HTTPS

---

## 🌐 **CONFIGURAR DNS (SEU PROVEDOR DE DOMÍNIO)**

**Exemplo para Cloudflare/Registro.br/GoDaddy:**

1. Acesse o painel do seu domínio
2. Adicione registros DNS:

```
Tipo: A
Nome: @
Valor: IP_DA_SUA_VPS
TTL: 3600

Tipo: A
Nome: www
Valor: IP_DA_SUA_VPS
TTL: 3600
```

3. Aguarde propagação (pode levar até 24h)
4. Teste: `ping seudominio.com`

---

## 📞 **COMANDOS RÁPIDOS ÚTEIS**

```bash
# Ver aplicação rodando
sudo systemctl status grimbots

# Reiniciar tudo
sudo systemctl restart grimbots nginx

# Ver logs em tempo real
sudo journalctl -u grimbots -f

# Atualizar aplicação
/home/grimbots/deploy.sh

# Backup manual
/home/grimbots/backup.sh

# Ver uso de recursos
htop
df -h
free -h

# Acessar banco de dados
cd /home/grimbots/grimbots-app
source venv/bin/activate
python3
>>> from app import db, app
>>> with app.app_context():
...     # Seus comandos aqui
```

---

## ✅ **PRONTO!**

Agora sua aplicação está rodando em **PRODUÇÃO** com:
- ✅ HTTPS/SSL
- ✅ Nginx como reverse proxy
- ✅ Systemd para auto-restart
- ✅ Firewall configurado
- ✅ Backup automático
- ✅ Logs organizados
- ✅ Deploy script pronto

**Acesse:** `https://seudominio.com` 🚀

---

## 📚 **REFERÊNCIAS**

- [Gunicorn Documentation](https://docs.gunicorn.org/)
- [Nginx Configuration](https://nginx.org/en/docs/)
- [Certbot SSL](https://certbot.eff.org/)
- [Flask Deployment](https://flask.palletsprojects.com/en/2.3.x/deploying/)
- [Ubuntu Server Guide](https://ubuntu.com/server/docs)

