# 🚀 GUIA COMPLETO DE DEPLOY - BOT MANAGER SAAS

## 📋 PRÉ-REQUISITOS

Antes de fazer deploy, você precisa ter:

1. **Servidor VPS/Cloud** (Ubuntu 20.04+ recomendado)
   - Mínimo: 2GB RAM, 1 vCPU, 20GB disco
   - Recomendado: 4GB RAM, 2 vCPU, 40GB disco

2. **Domínio** configurado apontando para o IP do servidor
   - Exemplo: `botmanager.com.br`

3. **Acesso SSH** ao servidor
   - Usuário com permissões sudo

4. **Credenciais SyncPay**
   - Client ID
   - Client Secret
   - Platform Split User ID (para comissões)

---

## 🎯 OPÇÃO 1: DEPLOY COM DOCKER (RECOMENDADO)

### Passo 1: Preparar o Servidor

```bash
# Conectar via SSH
ssh root@seu-ip-do-servidor

# Atualizar sistema
apt update && apt upgrade -y

# Instalar Docker e Docker Compose
curl -fsSL https://get.docker.com -o get-docker.sh
sh get-docker.sh

# Instalar Docker Compose
apt install docker-compose -y

# Verificar instalação
docker --version
docker-compose --version
```

### Passo 2: Enviar o Projeto para o Servidor

**Opção A: Via Git (RECOMENDADO)**

```bash
# No seu computador local
cd c:\Users\grcon\Downloads\grpay
git init
git add .
git commit -m "Initial commit"

# Criar repositório no GitHub/GitLab (privado)
# Seguir instruções do GitHub para conectar

# No servidor
cd /var/www
git clone https://github.com/seu-usuario/bot-manager.git
cd bot-manager
```

**Opção B: Via SCP/FTP**

```bash
# No seu computador local (PowerShell)
scp -r C:\Users\grcon\Downloads\grpay root@seu-ip:/var/www/bot-manager

# No servidor
cd /var/www/bot-manager
```

### Passo 3: Configurar Variáveis de Ambiente

```bash
# Criar arquivo .env
nano .env
```

**Conteúdo do `.env`:**

```env
# Flask
SECRET_KEY=sua-chave-secreta-super-segura-aqui-min-32-caracteres
FLASK_ENV=production

# Database (PostgreSQL em produção)
DATABASE_URL=postgresql://botmanager:senha-forte-aqui@localhost:5432/botmanager_db

# SyncPay
SYNCPAY_CLIENT_ID=seu-client-id-aqui
SYNCPAY_CLIENT_SECRET=seu-client-secret-aqui
PLATFORM_SPLIT_USER_ID=d0157d18-c0bb-4f0c-8569-de7d181b3e46

# Webhook URL (seu domínio)
WEBHOOK_URL=https://botmanager.com.br

# Opcional
PORT=5000
```

**Salvar:** `CTRL+O`, `Enter`, `CTRL+X`

### Passo 4: Ajustar `docker-compose.yml`

Verifique se o arquivo está assim:

```yaml
version: '3.8'

services:
  web:
    build: .
    ports:
      - "5000:5000"
    volumes:
      - ./instance:/app/instance
    env_file:
      - .env
    restart: always
    depends_on:
      - db

  db:
    image: postgres:15
    environment:
      POSTGRES_USER: botmanager
      POSTGRES_PASSWORD: senha-forte-aqui
      POSTGRES_DB: botmanager_db
    volumes:
      - postgres_data:/var/lib/postgresql/data
    restart: always

volumes:
  postgres_data:
```

### Passo 5: Buildar e Iniciar

```bash
# Buildar imagens
docker-compose build

# Iniciar containers
docker-compose up -d

# Verificar logs
docker-compose logs -f web

# Verificar se está rodando
docker-compose ps
```

### Passo 6: Inicializar Banco de Dados

```bash
# Entrar no container
docker-compose exec web python init_db.py

# Verificar se funcionou
docker-compose logs web
```

### Passo 7: Configurar Nginx como Proxy Reverso

```bash
# Instalar Nginx
apt install nginx -y

# Criar configuração
nano /etc/nginx/sites-available/botmanager
```

**Conteúdo do Nginx:**

```nginx
server {
    listen 80;
    server_name botmanager.com.br www.botmanager.com.br;

    location / {
        proxy_pass http://127.0.0.1:5000;
        proxy_set_header Host $host;
        proxy_set_header X-Real-IP $remote_addr;
        proxy_set_header X-Forwarded-For $proxy_add_x_forwarded_for;
        proxy_set_header X-Forwarded-Proto $scheme;
        
        # WebSocket support
        proxy_http_version 1.1;
        proxy_set_header Upgrade $http_upgrade;
        proxy_set_header Connection "upgrade";
    }

    client_max_body_size 20M;
}
```

```bash
# Ativar site
ln -s /etc/nginx/sites-available/botmanager /etc/nginx/sites-enabled/

# Remover default (opcional)
rm /etc/nginx/sites-enabled/default

# Testar configuração
nginx -t

# Reiniciar Nginx
systemctl restart nginx
```

### Passo 8: Instalar SSL (HTTPS)

```bash
# Instalar Certbot
apt install certbot python3-certbot-nginx -y

# Gerar certificado SSL
certbot --nginx -d botmanager.com.br -d www.botmanager.com.br

# Seguir instruções interativas
# Email: seu@email.com
# Aceitar termos: Y
# Compartilhar email: N
# Redirecionar HTTP -> HTTPS: 2 (Sim)

# Testar renovação automática
certbot renew --dry-run
```

---

## 🎯 OPÇÃO 2: DEPLOY MANUAL (Sem Docker)

### Passo 1: Preparar Servidor

```bash
# Conectar via SSH
ssh root@seu-ip

# Atualizar sistema
apt update && apt upgrade -y

# Instalar dependências
apt install python3.11 python3.11-venv python3-pip postgresql nginx git -y
```

### Passo 2: Configurar PostgreSQL

```bash
# Entrar no PostgreSQL
sudo -u postgres psql

# Criar database e usuário
CREATE DATABASE botmanager_db;
CREATE USER botmanager WITH PASSWORD 'senha-forte-aqui';
GRANT ALL PRIVILEGES ON DATABASE botmanager_db TO botmanager;
\q
```

### Passo 3: Clonar Projeto

```bash
cd /var/www
git clone https://github.com/seu-usuario/bot-manager.git
cd bot-manager
```

### Passo 4: Configurar Python

```bash
# Criar ambiente virtual
python3.11 -m venv venv

# Ativar
source venv/bin/activate

# Instalar dependências
pip install -r requirements.txt
pip install gunicorn
```

### Passo 5: Configurar .env

```bash
nano .env
```

(Mesmo conteúdo do Passo 3 da Opção 1)

### Passo 6: Inicializar Banco

```bash
python init_db.py
```

### Passo 7: Configurar Systemd (Autostart)

```bash
nano /etc/systemd/system/botmanager.service
```

**Conteúdo:**

```ini
[Unit]
Description=Bot Manager SaaS
After=network.target

[Service]
Type=notify
User=root
WorkingDirectory=/var/www/bot-manager
Environment="PATH=/var/www/bot-manager/venv/bin"
ExecStart=/var/www/bot-manager/venv/bin/gunicorn --worker-class eventlet -w 1 --bind 127.0.0.1:5000 wsgi:app
Restart=always

[Install]
WantedBy=multi-user.target
```

```bash
# Ativar serviço
systemctl daemon-reload
systemctl enable botmanager
systemctl start botmanager

# Verificar status
systemctl status botmanager
```

### Passo 8: Configurar Nginx

(Mesmo processo do Passo 7 da Opção 1)

### Passo 9: SSL

(Mesmo processo do Passo 8 da Opção 1)

---

## 🔧 PÓS-DEPLOY: CONFIGURAÇÕES FINAIS

### 1. Configurar Webhook da SyncPay

Acesse o painel da SyncPay e configure:

**Webhook URL:** `https://botmanager.com.br/webhook/payment/syncpay`

### 2. Criar Primeiro Admin

```bash
# Via Docker
docker-compose exec web python -c "
from app import app, db
from models import User
with app.app_context():
    admin = User(email='admin@botmanager.com', username='admin', full_name='Admin')
    admin.set_password('senha-segura-aqui')
    admin.is_admin = True
    db.session.add(admin)
    db.session.commit()
    print('Admin criado!')
"

# Via Manual
source venv/bin/activate
python -c "
from app import app, db
from models import User
with app.app_context():
    admin = User(email='admin@botmanager.com', username='admin', full_name='Admin')
    admin.set_password('senha-segura-aqui')
    admin.is_admin = True
    db.session.add(admin)
    db.session.commit()
    print('Admin criado!')
"
```

### 3. Testar Sistema

Acesse: `https://botmanager.com.br`

- Login com admin
- Adicionar gateway SyncPay
- Criar bot de teste
- Verificar logs

---

## 📊 MONITORAMENTO

### Ver Logs

**Docker:**
```bash
docker-compose logs -f web
docker-compose logs -f db
```

**Manual:**
```bash
journalctl -u botmanager -f
tail -f /var/log/nginx/access.log
tail -f /var/log/nginx/error.log
```

### Reiniciar Serviços

**Docker:**
```bash
docker-compose restart web
docker-compose restart
```

**Manual:**
```bash
systemctl restart botmanager
systemctl restart nginx
```

---

## 🔄 ATUALIZAR SISTEMA

### Docker

```bash
cd /var/www/bot-manager
git pull origin main
docker-compose build
docker-compose up -d
```

### Manual

```bash
cd /var/www/bot-manager
git pull origin main
source venv/bin/activate
pip install -r requirements.txt --upgrade
systemctl restart botmanager
```

---

## 🛡️ SEGURANÇA

### 1. Firewall

```bash
# Permitir apenas portas necessárias
ufw allow 22/tcp    # SSH
ufw allow 80/tcp    # HTTP
ufw allow 443/tcp   # HTTPS
ufw enable
```

### 2. Fail2Ban (Proteção contra força bruta)

```bash
apt install fail2ban -y
systemctl enable fail2ban
systemctl start fail2ban
```

### 3. Backups Automáticos

```bash
# Criar script de backup
nano /root/backup.sh
```

```bash
#!/bin/bash
DATE=$(date +%Y%m%d_%H%M%S)
BACKUP_DIR="/root/backups"
mkdir -p $BACKUP_DIR

# Backup do banco
docker exec bot-manager-db-1 pg_dump -U botmanager botmanager_db > $BACKUP_DIR/db_$DATE.sql

# Backup dos uploads (se houver)
tar -czf $BACKUP_DIR/instance_$DATE.tar.gz /var/www/bot-manager/instance

# Manter apenas últimos 7 dias
find $BACKUP_DIR -type f -mtime +7 -delete

echo "Backup concluído: $DATE"
```

```bash
chmod +x /root/backup.sh

# Agendar backup diário (3h da manhã)
crontab -e
# Adicionar linha:
0 3 * * * /root/backup.sh >> /var/log/backup.log 2>&1
```

---

## ❓ TROUBLESHOOTING

### Problema: Site não carrega

```bash
# Verificar se o serviço está rodando
docker-compose ps
# ou
systemctl status botmanager

# Verificar logs
docker-compose logs web
# ou
journalctl -u botmanager -n 100
```

### Problema: Erro 502 Bad Gateway

```bash
# Verificar se Flask está rodando
curl http://127.0.0.1:5000

# Verificar Nginx
nginx -t
systemctl status nginx
```

### Problema: Banco de dados não conecta

```bash
# Verificar PostgreSQL
docker-compose ps db
# ou
systemctl status postgresql

# Verificar conexão
psql -U botmanager -d botmanager_db -h localhost
```

---

## 📞 SUPORTE

- **Documentação:** `/docs/README.md`
- **Logs:** Sempre verificar logs primeiro
- **Backup:** Sempre fazer backup antes de mudanças

---

## ✅ CHECKLIST DE DEPLOY

- [ ] Servidor provisionado
- [ ] Domínio configurado
- [ ] Docker/Python instalado
- [ ] Projeto clonado
- [ ] `.env` configurado
- [ ] Banco inicializado
- [ ] Nginx configurado
- [ ] SSL instalado
- [ ] Webhook SyncPay configurado
- [ ] Admin criado
- [ ] Sistema testado
- [ ] Backups configurados
- [ ] Monitoramento ativo

---

**🎉 DEPLOY COMPLETO! Seu sistema está no ar!** 🚀

