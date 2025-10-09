# 🚀 DEPLOY COMPLETO: PM2 + NGINX PROXY MANAGER

## 📋 ÍNDICE

1. [Visão Geral](#visão-geral)
2. [Pré-requisitos](#pré-requisitos)
3. [Preparação do Servidor](#preparação-do-servidor)
4. [Instalação do PostgreSQL](#instalação-do-postgresql)
5. [Configuração do Projeto](#configuração-do-projeto)
6. [Instalação do PM2](#instalação-do-pm2)
7. [Instalação do Nginx Proxy Manager](#instalação-do-nginx-proxy-manager)
8. [Configuração Final](#configuração-final)
9. [Monitoramento](#monitoramento)
10. [Troubleshooting](#troubleshooting)

---

## 🎯 VISÃO GERAL

### Arquitetura do Deploy

```
Internet
   ↓
Nginx Proxy Manager (Docker)
:80 (HTTP) → :443 (HTTPS + SSL)
   ↓
PM2 + Gunicorn + Eventlet
127.0.0.1:5000
   ↓
Flask + SocketIO + APScheduler
   ↓
PostgreSQL (Docker)
:5432
```

### Por que PM2 + Nginx Proxy Manager?

✅ **PM2:**
- Gerenciamento de processos Python
- Auto-restart em caso de crash
- Monitoramento em tempo real
- Logs centralizados
- Zero-downtime reload

✅ **Nginx Proxy Manager:**
- Interface web visual
- SSL automático (Let's Encrypt)
- Configuração sem editar arquivos
- Múltiplos domínios/subdomínios
- Access Lists e Rate Limiting

---

## 📦 PRÉ-REQUISITOS

### Servidor

- **OS:** Ubuntu 20.04 LTS ou superior
- **RAM:** Mínimo 2GB, Recomendado 4GB
- **CPU:** Mínimo 1 vCPU, Recomendado 2 vCPU
- **Disco:** Mínimo 20GB, Recomendado 40GB
- **Acesso:** SSH com sudo

### Domínio

- **Domínio configurado** apontando para o IP do servidor
- **DNS Tipo A:** `@` e `www` → IP do servidor
- **Propagação:** Aguardar 5-30 minutos

### Credenciais

- **SyncPay:** Client ID e Client Secret
- **Platform Split User ID:** Para comissões
- **Email:** Para SSL Let's Encrypt

---

## 🔧 PREPARAÇÃO DO SERVIDOR

### 1. Conectar ao Servidor

```bash
ssh root@SEU_IP_DO_SERVIDOR
# ou
ssh usuario@SEU_IP_DO_SERVIDOR
```

### 2. Atualizar Sistema

```bash
# Atualizar repositórios
apt update && apt upgrade -y

# Instalar utilitários essenciais
apt install -y \
  curl \
  wget \
  git \
  nano \
  htop \
  build-essential \
  software-properties-common \
  ca-certificates \
  gnupg \
  lsb-release
```

### 3. Instalar Python 3.11

```bash
# Adicionar repositório deadsnakes
add-apt-repository ppa:deadsnakes/ppa -y
apt update

# Instalar Python 3.11 e ferramentas
apt install -y \
  python3.11 \
  python3.11-venv \
  python3.11-dev \
  python3-pip

# Verificar instalação
python3.11 --version
# Deve mostrar: Python 3.11.x
```

### 4. Instalar Node.js e NPM (para PM2)

```bash
# Instalar NodeSource repository (Node 20 LTS)
curl -fsSL https://deb.nodesource.com/setup_20.x | bash -

# Instalar Node.js e NPM
apt install -y nodejs

# Verificar instalação
node --version   # Deve mostrar: v20.x.x
npm --version    # Deve mostrar: 10.x.x
```

### 5. Instalar Docker e Docker Compose

```bash
# Instalar Docker
curl -fsSL https://get.docker.com -o get-docker.sh
sh get-docker.sh

# Instalar Docker Compose
apt install -y docker-compose

# Verificar instalação
docker --version
docker-compose --version

# Adicionar usuário ao grupo docker (opcional)
usermod -aG docker $USER
```

---

## 🗄️ INSTALAÇÃO DO POSTGRESQL

### Opção A: Docker (RECOMENDADO)

```bash
# Criar diretório para PostgreSQL
mkdir -p /var/lib/postgresql/data

# Criar docker-compose.yml para PostgreSQL
cat > /opt/postgresql-docker-compose.yml <<'EOF'
version: '3.8'

services:
  postgres:
    image: postgres:15-alpine
    container_name: postgres-botmanager
    restart: always
    environment:
      POSTGRES_DB: botmanager_db
      POSTGRES_USER: botmanager
      POSTGRES_PASSWORD: SENHA_SUPER_SEGURA_AQUI_MIN_16_CHARS
    ports:
      - "127.0.0.1:5432:5432"
    volumes:
      - /var/lib/postgresql/data:/var/lib/postgresql/data
    networks:
      - bot-network

networks:
  bot-network:
    driver: bridge
EOF

# ⚠️ IMPORTANTE: Editar a senha antes de continuar
nano /opt/postgresql-docker-compose.yml
# Trocar: SENHA_SUPER_SEGURA_AQUI_MIN_16_CHARS

# Iniciar PostgreSQL
cd /opt
docker-compose -f postgresql-docker-compose.yml up -d

# Verificar se está rodando
docker ps | grep postgres

# Testar conexão
docker exec -it postgres-botmanager psql -U botmanager -d botmanager_db -c "SELECT version();"
```

### Opção B: Instalação Nativa

```bash
# Instalar PostgreSQL 15
apt install -y postgresql-15 postgresql-contrib-15

# Iniciar serviço
systemctl start postgresql
systemctl enable postgresql

# Criar database e usuário
sudo -u postgres psql <<EOF
CREATE DATABASE botmanager_db;
CREATE USER botmanager WITH ENCRYPTED PASSWORD 'SENHA_SUPER_SEGURA_AQUI';
GRANT ALL PRIVILEGES ON DATABASE botmanager_db TO botmanager;
\q
EOF

# Verificar
sudo -u postgres psql -c "SELECT version();"
```

---

## 📂 CONFIGURAÇÃO DO PROJETO

### 1. Clonar Projeto

```bash
# Criar diretório
mkdir -p /var/www
cd /var/www

# Clonar do GitHub
git clone https://github.com/gustavoRm1/grimbots.git bot-manager
cd bot-manager

# OU enviar via SCP
# No seu PC: scp -r C:\Users\grcon\Downloads\grpay root@SEU_IP:/var/www/bot-manager
```

### 2. Criar Ambiente Virtual

```bash
cd /var/www/bot-manager

# Criar venv com Python 3.11
python3.11 -m venv venv

# Ativar venv
source venv/bin/activate

# Atualizar pip
pip install --upgrade pip setuptools wheel
```

### 3. Instalar Dependências

```bash
# Garantir que está no venv
source venv/bin/activate

# Instalar requirements
pip install -r requirements.txt

# Verificar instalação
pip list | grep -E "Flask|gunicorn|eventlet"
```

### 4. Configurar Variáveis de Ambiente

```bash
# Criar arquivo .env
nano /var/www/bot-manager/.env
```

**Conteúdo do `.env`:**

```env
# Flask
SECRET_KEY=SUA_CHAVE_SECRETA_SUPER_SEGURA_MIN_32_CARACTERES
FLASK_ENV=production

# Database (ajustar senha que você definiu)
DATABASE_URL=postgresql://botmanager:SENHA_SUPER_SEGURA_AQUI@127.0.0.1:5432/botmanager_db

# SyncPay
SYNCPAY_CLIENT_ID=seu-client-id-syncpay
SYNCPAY_CLIENT_SECRET=seu-client-secret-syncpay

# Platform Split Payment
PLATFORM_SPLIT_USER_ID=seu-split-user-id

# Webhook URL (seu domínio)
WEBHOOK_URL=https://seu-dominio.com.br

# Server
PORT=5000
```

**Salvar:** `CTRL+O`, `Enter`, `CTRL+X`

**Gerar SECRET_KEY segura:**

```bash
python3 -c "import secrets; print(secrets.token_urlsafe(32))"
# Copiar o resultado e colar no SECRET_KEY
```

### 5. Inicializar Banco de Dados

```bash
# Garantir que está no venv
source venv/bin/activate

# Ir para diretório do projeto
cd /var/www/bot-manager

# Inicializar banco
python init_db.py

# Verificar se funcionou
echo "SELECT * FROM users;" | docker exec -i postgres-botmanager psql -U botmanager -d botmanager_db
```

### 6. Criar Diretório de Logs

```bash
mkdir -p /var/www/bot-manager/logs
touch /var/www/bot-manager/logs/access.log
touch /var/www/bot-manager/logs/error.log
touch /var/www/bot-manager/logs/pm2-out.log
touch /var/www/bot-manager/logs/pm2-error.log
touch /var/www/bot-manager/logs/pm2-combined.log
```

### 7. Ajustar Permissões

```bash
# Proprietário (ajustar se necessário)
chown -R root:root /var/www/bot-manager

# Permissões
chmod -R 755 /var/www/bot-manager
chmod 600 /var/www/bot-manager/.env
chmod 755 /var/www/bot-manager/logs
```

---

## 🔄 INSTALAÇÃO DO PM2

### 1. Instalar PM2 Globalmente

```bash
# Instalar PM2
npm install -g pm2

# Verificar instalação
pm2 --version
```

### 2. Configurar PM2 para Iniciar com o Sistema

```bash
# Gerar script de startup
pm2 startup systemd

# ⚠️ O comando acima mostrará um comando para copiar/colar
# Execute o comando mostrado, será algo como:
# sudo env PATH=$PATH:/usr/bin pm2 startup systemd -u root --hp /root
```

### 3. Ajustar ecosystem.config.js

```bash
cd /var/www/bot-manager

# Verificar se arquivo existe
ls -la ecosystem.config.js

# Ajustar caminho do interpreter (se necessário)
nano ecosystem.config.js
```

**Verificar estas linhas:**

```javascript
interpreter: 'python3',  // ← Trocar para caminho completo se der erro
cwd: '/var/www/bot-manager',  // ← Confirmar caminho
```

**Para encontrar caminho do Python no venv:**

```bash
source /var/www/bot-manager/venv/bin/activate
which python
# Resultado: /var/www/bot-manager/venv/bin/python
# Usar este caminho no interpreter
```

### 4. Testar Configuração

```bash
cd /var/www/bot-manager

# Ativar venv
source venv/bin/activate

# Testar Gunicorn manualmente
gunicorn --worker-class eventlet --workers 1 --bind 127.0.0.1:5000 wsgi:app

# Se funcionar (acesse http://SEU_IP:5000), pressione CTRL+C
# Se der erro, veja seção Troubleshooting
```

### 5. Iniciar com PM2

```bash
cd /var/www/bot-manager

# Iniciar aplicação
pm2 start ecosystem.config.js

# Verificar status
pm2 status

# Ver logs em tempo real
pm2 logs bot-manager

# Se tudo estiver OK, salvar configuração
pm2 save
```

### 6. Verificar se Está Rodando

```bash
# Ver processos PM2
pm2 list

# Ver logs
pm2 logs bot-manager --lines 50

# Ver monitoramento
pm2 monit

# Testar endpoint
curl http://127.0.0.1:5000
# Deve retornar o HTML da página de login
```

---

## 🌐 INSTALAÇÃO DO NGINX PROXY MANAGER

### 1. Criar Docker Compose para NPM

```bash
# Criar diretório
mkdir -p /opt/nginx-proxy-manager
cd /opt/nginx-proxy-manager

# Criar docker-compose.yml
cat > docker-compose.yml <<'EOF'
version: '3.8'

services:
  app:
    image: 'jc21/nginx-proxy-manager:latest'
    container_name: nginx-proxy-manager
    restart: unless-stopped
    ports:
      - '80:80'     # HTTP
      - '443:443'   # HTTPS
      - '81:81'     # Admin UI
    environment:
      DB_SQLITE_FILE: "/data/database.sqlite"
      DISABLE_IPV6: 'true'
    volumes:
      - ./data:/data
      - ./letsencrypt:/etc/letsencrypt
    networks:
      - npm-network

networks:
  npm-network:
    driver: bridge
EOF
```

### 2. Iniciar Nginx Proxy Manager

```bash
cd /opt/nginx-proxy-manager

# Iniciar container
docker-compose up -d

# Verificar se está rodando
docker ps | grep nginx-proxy-manager

# Ver logs
docker logs -f nginx-proxy-manager
```

### 3. Acessar Interface Web

**URL:** `http://SEU_IP:81`

**Login Padrão:**
- **Email:** `admin@example.com`
- **Senha:** `changeme`

**⚠️ TROCAR SENHA IMEDIATAMENTE!**

1. Fazer login
2. Clicar no avatar (canto superior direito)
3. **"Edit Details"**
4. Trocar nome, email e senha
5. Salvar

---

## ⚙️ CONFIGURAÇÃO FINAL

### 1. Configurar Proxy Host no Nginx Proxy Manager

#### Passo 1: Criar Proxy Host

1. Acesse: `http://SEU_IP:81`
2. Login com suas credenciais
3. Clique: **"Proxy Hosts"** → **"Add Proxy Host"**

#### Passo 2: Aba "Details"

```
Domain Names:
  seu-dominio.com.br
  www.seu-dominio.com.br

Scheme: http
Forward Hostname / IP: 127.0.0.1
Forward Port: 5000

✅ Cache Assets
✅ Block Common Exploits
✅ Websockets Support  ← IMPORTANTE para SocketIO!

Access List: Publicly Accessible
```

#### Passo 3: Aba "SSL"

```
SSL Certificate: Request a new SSL Certificate

✅ Force SSL
✅ HTTP/2 Support
✅ HSTS Enabled

Email Address for Let's Encrypt: seu@email.com

✅ I Agree to the Let's Encrypt Terms of Service
```

#### Passo 4: Aba "Advanced" (Opcional)

```nginx
# Adicionar estas configurações para melhor performance

# Timeouts maiores para WebSocket
proxy_read_timeout 300;
proxy_connect_timeout 300;
proxy_send_timeout 300;

# Headers para WebSocket
proxy_set_header Upgrade $http_upgrade;
proxy_set_header Connection "upgrade";
proxy_set_header X-Forwarded-Proto $scheme;

# Buffer para performance
proxy_buffering off;
```

#### Passo 5: Salvar

Clicar: **"Save"**

O Nginx Proxy Manager vai:
1. Configurar o proxy reverso
2. Solicitar certificado SSL ao Let's Encrypt
3. Configurar renovação automática

### 2. Testar Configuração

```bash
# Testar HTTP → HTTPS redirect
curl -I http://seu-dominio.com.br
# Deve retornar: 301 Moved Permanently

# Testar HTTPS
curl -I https://seu-dominio.com.br
# Deve retornar: 200 OK

# Testar no navegador
# https://seu-dominio.com.br
# Deve carregar a página de login
```

### 3. Configurar Firewall

```bash
# Instalar UFW (se não tiver)
apt install -y ufw

# Configurar regras
ufw default deny incoming
ufw default allow outgoing

# Permitir SSH
ufw allow 22/tcp

# Permitir HTTP/HTTPS (Nginx Proxy Manager)
ufw allow 80/tcp
ufw allow 443/tcp

# Permitir Admin do NPM (TEMPORÁRIO - remover depois)
ufw allow 81/tcp

# Ativar firewall
ufw enable

# Verificar status
ufw status verbose
```

**⚠️ DEPOIS de configurar tudo, BLOQUEAR porta 81:**

```bash
ufw delete allow 81/tcp
ufw reload
```

### 4. Configurar Webhook da SyncPay

1. Acesse o painel da SyncPay
2. Configurações → Webhooks
3. **URL do Webhook:** `https://seu-dominio.com.br/webhook/payment/syncpay`
4. **Eventos:** Marcar "Pagamento Confirmado"
5. Salvar

---

## 📊 MONITORAMENTO

### PM2 Monitoring

```bash
# Lista de processos
pm2 list

# Status detalhado
pm2 show bot-manager

# Monitoramento em tempo real
pm2 monit

# Logs ao vivo
pm2 logs bot-manager

# Logs com filtro
pm2 logs bot-manager --lines 100 --err

# Limpar logs
pm2 flush

# Informações do sistema
pm2 info bot-manager
```

### PM2 Plus (Dashboard Web - Opcional)

```bash
# Criar conta em: https://pm2.io

# Conectar PM2 ao PM2 Plus
pm2 link CHAVE_SECRETA CHAVE_PUBLICA

# Agora você tem dashboard web com:
# - Monitoramento em tempo real
# - Alertas por email
# - Histórico de performance
```

### Logs do Sistema

```bash
# Logs do PM2
tail -f /var/www/bot-manager/logs/pm2-combined.log

# Logs do Gunicorn
tail -f /var/www/bot-manager/logs/access.log
tail -f /var/www/bot-manager/logs/error.log

# Logs do PostgreSQL (Docker)
docker logs -f postgres-botmanager

# Logs do Nginx Proxy Manager
docker logs -f nginx-proxy-manager

# Logs do sistema
journalctl -u pm2-root -f
```

### Comandos Úteis PM2

```bash
# Reiniciar aplicação
pm2 restart bot-manager

# Reload (zero-downtime)
pm2 reload bot-manager

# Parar aplicação
pm2 stop bot-manager

# Deletar do PM2
pm2 delete bot-manager

# Resetar restart count
pm2 reset bot-manager

# Ver uso de memória/CPU
pm2 describe bot-manager
```

---

## 🔄 ATUALIZAR SISTEMA

### Deploy de Nova Versão

```bash
cd /var/www/bot-manager

# 1. Fazer backup do banco
docker exec postgres-botmanager pg_dump -U botmanager botmanager_db > backup_$(date +%Y%m%d_%H%M%S).sql

# 2. Puxar código novo
git pull origin main

# 3. Ativar venv
source venv/bin/activate

# 4. Atualizar dependências (se mudou requirements.txt)
pip install -r requirements.txt --upgrade

# 5. Aplicar migrações (se houver)
# python migrate.py

# 6. Reload PM2 (zero-downtime)
pm2 reload bot-manager

# 7. Verificar logs
pm2 logs bot-manager --lines 50
```

### Rollback

```bash
cd /var/www/bot-manager

# Voltar para commit anterior
git log --oneline -n 5  # Ver últimos 5 commits
git reset --hard COMMIT_HASH

# Reload PM2
pm2 reload bot-manager
```

---

## 🛡️ SEGURANÇA

### 1. Fail2Ban (Proteção contra Força Bruta)

```bash
# Instalar
apt install -y fail2ban

# Configurar
cat > /etc/fail2ban/jail.local <<'EOF'
[sshd]
enabled = true
port = 22
maxretry = 3
bantime = 3600

[nginx-limit-req]
enabled = true
filter = nginx-limit-req
logpath = /opt/nginx-proxy-manager/data/logs/*.log
maxretry = 5
bantime = 3600
EOF

# Reiniciar
systemctl restart fail2ban
systemctl enable fail2ban

# Verificar
fail2ban-client status
```

### 2. Backup Automático

```bash
# Criar script de backup
cat > /root/backup-bot-manager.sh <<'EOF'
#!/bin/bash
BACKUP_DIR="/root/backups"
DATE=$(date +%Y%m%d_%H%M%S)

mkdir -p $BACKUP_DIR

# Backup do banco
docker exec postgres-botmanager pg_dump -U botmanager botmanager_db | gzip > $BACKUP_DIR/db_$DATE.sql.gz

# Backup dos uploads (se houver)
tar -czf $BACKUP_DIR/instance_$DATE.tar.gz /var/www/bot-manager/instance

# Manter apenas últimos 7 dias
find $BACKUP_DIR -type f -mtime +7 -delete

echo "Backup concluído: $DATE"
EOF

chmod +x /root/backup-bot-manager.sh

# Testar
/root/backup-bot-manager.sh

# Agendar backup diário (3h da manhã)
crontab -e
# Adicionar:
0 3 * * * /root/backup-bot-manager.sh >> /var/log/backup.log 2>&1
```

---

## ❓ TROUBLESHOOTING

### Problema: PM2 não inicia

**Sintomas:**
```bash
pm2 list
# Status: errored
```

**Solução:**

```bash
# 1. Ver logs detalhados
pm2 logs bot-manager --err

# 2. Testar Gunicorn manualmente
cd /var/www/bot-manager
source venv/bin/activate
gunicorn --worker-class eventlet --workers 1 --bind 127.0.0.1:5000 wsgi:app

# 3. Verificar .env
cat .env | grep -v "^#"

# 4. Verificar imports
python -c "from app import app; print('OK')"

# 5. Verificar PostgreSQL
docker ps | grep postgres
```

### Problema: Erro 502 Bad Gateway

**Sintomas:**
Página mostra "502 Bad Gateway"

**Solução:**

```bash
# 1. Verificar se PM2 está rodando
pm2 list

# 2. Verificar se porta 5000 está escutando
netstat -tlnp | grep 5000
# ou
ss -tlnp | grep 5000

# 3. Testar conexão local
curl http://127.0.0.1:5000

# 4. Ver logs do Nginx Proxy Manager
docker logs nginx-proxy-manager | tail -50

# 5. Verificar configuração do Proxy Host
# - Forward IP: 127.0.0.1
# - Forward Port: 5000
# - WebSockets: HABILITADO
```

### Problema: WebSocket não funciona

**Sintomas:**
Dashboard não atualiza em tempo real

**Solução:**

```bash
# 1. Verificar configuração do NPM
# Proxy Host → Edit → Details
# ✅ WebSockets Support DEVE estar marcado

# 2. Verificar Advanced Config
# Deve ter: proxy_set_header Upgrade $http_upgrade;

# 3. Ver logs do navegador (F12 → Console)
# Procurar erros de WebSocket

# 4. Testar WebSocket
curl -i -N \
  -H "Connection: Upgrade" \
  -H "Upgrade: websocket" \
  http://127.0.0.1:5000/socket.io/
```

### Problema: Banco de dados não conecta

**Sintomas:**
```
sqlalchemy.exc.OperationalError: could not connect
```

**Solução:**

```bash
# 1. Verificar se PostgreSQL está rodando
docker ps | grep postgres

# 2. Testar conexão
docker exec -it postgres-botmanager psql -U botmanager -d botmanager_db -c "SELECT 1;"

# 3. Verificar DATABASE_URL no .env
cat .env | grep DATABASE_URL

# 4. Formato correto:
# postgresql://botmanager:SENHA@127.0.0.1:5432/botmanager_db

# 5. Reiniciar PostgreSQL
docker restart postgres-botmanager
```

### Problema: SSL não funciona

**Sintomas:**
"Your connection is not private" ou certificado inválido

**Solução:**

```bash
# 1. Verificar DNS
nslookup seu-dominio.com.br
# Deve retornar o IP do seu servidor

# 2. Verificar portas abertas
netstat -tlnp | grep -E "80|443"

# 3. Ver logs do NPM
docker logs nginx-proxy-manager | grep -i "let's encrypt"

# 4. Forçar renovação do certificado
# No NPM: SSL Certificates → View → Renew

# 5. Verificar email no Let's Encrypt
# Deve ser um email válido
```

### Problema: PM2 reinicia constantemente

**Sintomas:**
```bash
pm2 list
# restart: 10+ (muitos restarts)
```

**Solução:**

```bash
# 1. Ver logs de erro
pm2 logs bot-manager --err --lines 100

# 2. Verificar uso de memória
pm2 monit
# Se usar > 500MB, ajustar no ecosystem.config.js

# 3. Verificar se APScheduler está duplicando jobs
pm2 describe bot-manager
# Se tiver múltiplas instâncias, garantir instances: 1

# 4. Limpar e reiniciar
pm2 delete bot-manager
pm2 start ecosystem.config.js
pm2 save
```

---

## ✅ CHECKLIST FINAL

Antes de considerar deploy completo:

- [ ] Servidor atualizado e configurado
- [ ] Python 3.11 instalado
- [ ] PostgreSQL rodando (Docker ou nativo)
- [ ] Projeto clonado em `/var/www/bot-manager`
- [ ] Venv criado e dependências instaladas
- [ ] `.env` configurado com credenciais reais
- [ ] Banco inicializado (`init_db.py`)
- [ ] PM2 instalado globalmente
- [ ] `ecosystem.config.js` ajustado
- [ ] PM2 iniciado e rodando (`pm2 list`)
- [ ] PM2 configurado para startup (`pm2 startup`)
- [ ] Nginx Proxy Manager rodando (Docker)
- [ ] NPM configurado no `:81`
- [ ] Proxy Host criado com SSL
- [ ] Domínio apontando para servidor
- [ ] SSL Let's Encrypt ativo
- [ ] WebSockets habilitados
- [ ] Firewall configurado (UFW)
- [ ] Webhook SyncPay configurado
- [ ] Backups automáticos agendados
- [ ] Fail2Ban instalado e ativo
- [ ] Sistema testado (login, bot, pagamento)
- [ ] Monitoramento configurado (logs, PM2)

---

## 🎉 DEPLOY COMPLETO!

Seu sistema está 100% operacional em produção com:

✅ **Alta disponibilidade** (PM2 auto-restart)  
✅ **SSL automático** (Let's Encrypt)  
✅ **Interface visual** (Nginx Proxy Manager)  
✅ **Backups automáticos**  
✅ **Monitoramento em tempo real**  
✅ **WebSocket funcionando**  
✅ **Segurança reforçada** (Firewall + Fail2Ban)  

**URL:** https://seu-dominio.com.br  
**Admin NPM:** http://SEU_IP:81 (bloquear depois!)  

---

## 📞 SUPORTE

- **Logs PM2:** `pm2 logs bot-manager`
- **Status PM2:** `pm2 monit`
- **Logs NPM:** `docker logs nginx-proxy-manager`
- **Logs PostgreSQL:** `docker logs postgres-botmanager`

---

**Documentação criada com ❤️ para deploy perfeito!** 🚀

