# 🚀 GUIA COMPLETO DE DEPLOY NA VPS

**Projeto:** Bot Manager SaaS  
**Data:** Outubro 2025  
**Stack:** Python 3.11 + Flask + PostgreSQL/SQLite + PM2 + Nginx

---

## 📋 PRÉ-REQUISITOS

### Na sua VPS:
- Ubuntu 20.04+ / Debian 11+
- Mínimo 2GB RAM
- 20GB disco
- Acesso root/sudo
- IP público

### No seu computador:
- SSH configurado
- Git instalado
- Acesso à VPS via SSH

---

## 🎯 OPÇÕES DE DEPLOY

### **Opção 1: Deploy Rápido (SQLite + PM2)** ⚡
✅ Mais rápido (5 minutos)  
✅ Ideal para teste/MVP  
✅ Fácil de configurar  
❌ SQLite (não recomendado para produção em escala)

### **Opção 2: Deploy Completo (PostgreSQL + Docker + Nginx)** 🏢
✅ Produção profissional  
✅ Escalável  
✅ PostgreSQL  
✅ SSL automático  
❌ Mais complexo (30 minutos)

---

## ⚡ OPÇÃO 1: DEPLOY RÁPIDO (SQLite + PM2)

### 1️⃣ Preparar VPS

```bash
# Conectar na VPS
ssh root@SEU_IP_VPS

# Atualizar sistema
apt update && apt upgrade -y

# Instalar dependências
apt install -y python3.11 python3.11-venv python3-pip git curl

# Instalar Node.js e PM2
curl -fsSL https://deb.nodesource.com/setup_20.x | bash -
apt install -y nodejs
npm install -g pm2
```

### 2️⃣ Clonar Projeto

```bash
# Criar diretório
mkdir -p /var/www
cd /var/www

# Clonar projeto (ou fazer upload)
git clone https://github.com/SEU_USUARIO/grpay.git bot-manager
# OU fazer upload via SCP (veja comando abaixo)

cd bot-manager
```

### 3️⃣ Configurar Ambiente Python

```bash
# Criar ambiente virtual
python3.11 -m venv venv

# Ativar ambiente
source venv/bin/activate

# Instalar dependências
pip install --upgrade pip
pip install -r requirements.txt
pip install gunicorn
```

### 4️⃣ Configurar Variáveis de Ambiente

```bash
# Copiar exemplo
cp .env.example .env

# Editar configurações
nano .env
```

**Configurar no .env:**
```bash
# OBRIGATÓRIO: Gerar chave secreta forte
SECRET_KEY=cole_aqui_resultado_do_comando_abaixo

# Banco de dados (SQLite)
DATABASE_URL=sqlite:///instance/saas_bot_manager.db

# URL do webhook (seu domínio)
WEBHOOK_URL=https://seudominio.com

# Split IDs (seus IDs de comissão)
PLATFORM_SPLIT_USER_ID=seu_id_syncpay
PUSHYN_SPLIT_ACCOUNT_ID=seu_id_pushyn
WIINPAY_PLATFORM_USER_ID=seu_id_wiinpay

# Flask
FLASK_ENV=production
```

**Gerar SECRET_KEY:**
```bash
python3 -c "import secrets; print(secrets.token_hex(32))"
```

### 5️⃣ Inicializar Banco de Dados

```bash
# Criar diretório do banco
mkdir -p instance

# Inicializar banco
python init_db.py

# Executar migrações
python migrate_add_gateway_fields.py
python migrate_encrypt_credentials.py
python migration_gamification_v2.py
```

### 6️⃣ Testar Aplicação

```bash
# Testar localmente
gunicorn -b 127.0.0.1:5000 wsgi:app

# Em outro terminal, testar
curl http://127.0.0.1:5000

# Se funcionar, pressionar Ctrl+C para parar
```

### 7️⃣ Configurar PM2

```bash
# Criar arquivo ecosystem.config.js
nano ecosystem.config.js
```

**Conteúdo:**
```javascript
module.exports = {
  apps: [{
    name: 'bot-manager',
    script: 'venv/bin/gunicorn',
    args: '-w 4 -b 0.0.0.0:5000 --timeout 120 wsgi:app',
    cwd: '/var/www/bot-manager',
    instances: 1,
    autorestart: true,
    watch: false,
    max_memory_restart: '1G',
    env: {
      NODE_ENV: 'production',
      FLASK_ENV: 'production'
    }
  }]
}
```

**Iniciar com PM2:**
```bash
# Iniciar aplicação
pm2 start ecosystem.config.js

# Salvar configuração
pm2 save

# Configurar para iniciar no boot
pm2 startup
# Copiar e executar o comando que aparecer

# Ver logs
pm2 logs bot-manager

# Ver status
pm2 status
```

### 8️⃣ Configurar Nginx (Proxy Reverso)

```bash
# Instalar Nginx
apt install -y nginx

# Criar configuração
nano /etc/nginx/sites-available/bot-manager
```

**Conteúdo:**
```nginx
server {
    listen 80;
    server_name seudominio.com www.seudominio.com;

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

    client_max_body_size 50M;
}
```

**Ativar configuração:**
```bash
# Criar link simbólico
ln -s /etc/nginx/sites-available/bot-manager /etc/nginx/sites-enabled/

# Remover default
rm /etc/nginx/sites-enabled/default

# Testar configuração
nginx -t

# Reiniciar Nginx
systemctl restart nginx
```

### 9️⃣ Configurar SSL (Certbot)

```bash
# Instalar Certbot
apt install -y certbot python3-certbot-nginx

# Gerar certificado SSL
certbot --nginx -d seudominio.com -d www.seudominio.com

# Renovação automática já está configurada
```

### 🔟 Configurar Firewall

```bash
# Configurar UFW
ufw allow 22/tcp    # SSH
ufw allow 80/tcp    # HTTP
ufw allow 443/tcp   # HTTPS
ufw --force enable

# Verificar status
ufw status
```

---

## 🏢 OPÇÃO 2: DEPLOY COMPLETO (PostgreSQL + Docker)

### 1️⃣ Setup Automático

```bash
# Conectar na VPS
ssh root@SEU_IP_VPS

# Baixar script de setup
cd /tmp
wget https://raw.githubusercontent.com/SEU_USUARIO/grpay/main/deploy/setup-production.sh

# Executar (demora ~15 minutos)
chmod +x setup-production.sh
./setup-production.sh
```

Este script instala:
- ✅ Python 3.11
- ✅ Node.js 20 + PM2
- ✅ Docker + Docker Compose
- ✅ PostgreSQL (Docker)
- ✅ Nginx Proxy Manager
- ✅ Firewall (UFW)

### 2️⃣ Seguir Passos 2-6 da Opção 1

Com as seguintes diferenças:

**No .env, usar PostgreSQL:**
```bash
DATABASE_URL=postgresql://botmanager:SUA_SENHA@127.0.0.1:5432/botmanager_db
```

### 3️⃣ Configurar Nginx Proxy Manager

```bash
# Acessar interface web
http://SEU_IP_VPS:81

# Login padrão:
# Email: admin@example.com
# Senha: changeme

# IMPORTANTE: Trocar senha imediatamente!
```

**Criar Proxy Host:**
1. Proxy Hosts → Add Proxy Host
2. Domain Names: `seudominio.com`, `www.seudominio.com`
3. Scheme: `http`
4. Forward Hostname/IP: `127.0.0.1`
5. Forward Port: `5000`
6. Websockets Support: ✅ ON
7. SSL → Request New SSL Certificate
8. Force SSL: ✅ ON

**Após configurar, bloquear porta 81:**
```bash
ufw delete allow 81/tcp
ufw reload
```

---

## 📤 COMO FAZER UPLOAD DO PROJETO (SEM GIT)

### Da sua máquina local:

```bash
# Navegar até a pasta do projeto
cd C:\Users\grcon\Downloads\grpay

# Criar arquivo tar
tar -czf grpay.tar.gz \
    --exclude='venv' \
    --exclude='__pycache__' \
    --exclude='*.pyc' \
    --exclude='.git' \
    --exclude='instance/*.db' \
    --exclude='.env' \
    .

# Enviar para VPS
scp grpay.tar.gz root@SEU_IP_VPS:/tmp/

# Conectar na VPS e extrair
ssh root@SEU_IP_VPS
mkdir -p /var/www/bot-manager
cd /var/www/bot-manager
tar -xzf /tmp/grpay.tar.gz
rm /tmp/grpay.tar.gz
```

**Ou usar o script automático:**
```bash
# Da sua máquina local
chmod +x deploy/deploy_to_vps.sh
./deploy/deploy_to_vps.sh root@SEU_IP_VPS
```

---

## 🔄 COMANDOS ÚTEIS PM2

```bash
# Ver status
pm2 status

# Ver logs em tempo real
pm2 logs bot-manager

# Reiniciar aplicação
pm2 restart bot-manager

# Parar aplicação
pm2 stop bot-manager

# Iniciar aplicação
pm2 start bot-manager

# Ver uso de recursos
pm2 monit

# Ver logs de erro
pm2 logs bot-manager --err

# Limpar logs
pm2 flush
```

---

## 🔍 VERIFICAÇÃO PÓS-DEPLOY

### 1. Testar Aplicação
```bash
curl https://seudominio.com
# Deve retornar HTML da página de login
```

### 2. Testar Webhook
```bash
curl -X POST https://seudominio.com/webhook/payment/syncpay \
  -H "Content-Type: application/json" \
  -d '{"test": true}'
# Deve retornar 200 OK ou mensagem de erro
```

### 3. Testar Login
- Acessar: `https://seudominio.com`
- Criar conta
- Fazer login
- Criar bot de teste

### 4. Ver Logs
```bash
pm2 logs bot-manager --lines 100
```

---

## 🐛 TROUBLESHOOTING

### Aplicação não inicia
```bash
# Ver logs detalhados
pm2 logs bot-manager --err

# Testar manualmente
cd /var/www/bot-manager
source venv/bin/activate
python wsgi.py
```

### Erro de SECRET_KEY
```bash
# Gerar nova chave
python3 -c "import secrets; print(secrets.token_hex(32))"

# Adicionar no .env
nano .env
```

### Erro de banco de dados
```bash
# Recriar banco (CUIDADO: apaga dados!)
cd /var/www/bot-manager
source venv/bin/activate
rm -f instance/saas_bot_manager.db
python init_db.py
```

### Nginx não funciona
```bash
# Testar configuração
nginx -t

# Ver logs
tail -f /var/log/nginx/error.log

# Reiniciar
systemctl restart nginx
```

### SSL não funciona
```bash
# Verificar certificado
certbot certificates

# Renovar manualmente
certbot renew --force-renewal
```

---

## 🔒 SEGURANÇA PÓS-DEPLOY

### 1. Mudar Porta SSH (Opcional mas recomendado)
```bash
nano /etc/ssh/sshd_config
# Trocar Port 22 para Port 2222
systemctl restart sshd

# Atualizar firewall
ufw allow 2222/tcp
ufw delete allow 22/tcp
```

### 2. Desabilitar Login Root
```bash
nano /etc/ssh/sshd_config
# Adicionar: PermitRootLogin no
systemctl restart sshd
```

### 3. Configurar Fail2Ban
```bash
apt install -y fail2ban
systemctl enable fail2ban
systemctl start fail2ban
```

### 4. Backups Automáticos
```bash
# Criar script de backup
nano /root/backup-bot.sh
```

**Conteúdo:**
```bash
#!/bin/bash
DATE=$(date +%Y%m%d_%H%M%S)
BACKUP_DIR="/root/backups"
mkdir -p $BACKUP_DIR

# Backup do banco
cp /var/www/bot-manager/instance/saas_bot_manager.db \
   $BACKUP_DIR/db_$DATE.db

# Backup do .env
cp /var/www/bot-manager/.env \
   $BACKUP_DIR/env_$DATE.bak

# Manter apenas últimos 7 backups
find $BACKUP_DIR -name "db_*.db" -mtime +7 -delete
find $BACKUP_DIR -name "env_*.bak" -mtime +7 -delete

echo "Backup concluído: $DATE"
```

**Agendar com Cron:**
```bash
chmod +x /root/backup-bot.sh
crontab -e

# Adicionar linha (backup diário às 3h da manhã):
0 3 * * * /root/backup-bot.sh >> /var/log/backup-bot.log 2>&1
```

---

## 📊 MONITORAMENTO

### Logs do Sistema
```bash
# Logs da aplicação
pm2 logs bot-manager

# Logs do Nginx
tail -f /var/log/nginx/access.log
tail -f /var/log/nginx/error.log

# Uso de recursos
htop
```

### Métricas PM2
```bash
# Monitor interativo
pm2 monit

# Métricas web (opcional)
pm2 install pm2-server-monit
# Acessar: http://SEU_IP:9615
```

---

## ✅ CHECKLIST FINAL

- [ ] VPS configurada e acessível
- [ ] Projeto clonado/enviado para `/var/www/bot-manager`
- [ ] Python venv criado e dependências instaladas
- [ ] .env configurado com SECRET_KEY forte
- [ ] Banco de dados inicializado
- [ ] PM2 rodando a aplicação
- [ ] Nginx configurado como proxy reverso
- [ ] SSL configurado (HTTPS)
- [ ] Firewall ativo (UFW)
- [ ] Domínio apontando para o IP da VPS
- [ ] Aplicação acessível via HTTPS
- [ ] Login funcionando
- [ ] Criação de bot funcionando
- [ ] Webhooks configurados nos gateways
- [ ] Backups automáticos agendados

---

## 🎉 DEPLOY CONCLUÍDO!

Sua aplicação está rodando em: **https://seudominio.com**

**Próximos passos:**
1. Criar conta de admin
2. Configurar gateways de pagamento
3. Criar bot de teste
4. Monitorar logs por 24h
5. Configurar alertas (opcional)

---

## 📞 SUPORTE

Se tiver problemas:
1. Verificar logs: `pm2 logs bot-manager`
2. Verificar status: `pm2 status`
3. Reiniciar: `pm2 restart bot-manager`
4. Verificar .env: todas variáveis configuradas?
5. Verificar firewall: `ufw status`

---

**Documentação criada:** Outubro 2025  
**Versão:** 2.1.0  
**Stack:** Python 3.11 + Flask + SQLAlchemy + PostgreSQL/SQLite

