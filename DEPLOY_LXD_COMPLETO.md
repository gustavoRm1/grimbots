# 🚀 GUIA COMPLETO: DEPLOY COM LXD + NAMECHEAP

**Deploy do grpay em Container LXD na sua VPS**

---

## 📋 **SITUAÇÃO ATUAL**

Você já tem:
- ✅ VPS configurada
- ✅ LXD instalado e funcionando
- ✅ 5 containers rodando:
  - `api` (Api do Sistema)
  - `bot-telegram-lista`
  - `bot-telegram-supremos`
  - `s3-minio`
  - `site`

**Agora vamos criar um novo container para o grpay!**

---

## 🎯 **O QUE VOCÊ VAI PRECISAR**

Antes de começar, tenha em mãos:

1. ✅ **IP da sua VPS** (você já tem acesso)
2. ✅ **Seu domínio** (ex: `grpay.meusite.com.br` ou `meusite.com.br`)
3. ✅ **Acesso ao painel do Namecheap**
4. ✅ **Token do bot do Telegram** (pegue com o @BotFather)
5. ✅ **Credenciais da SyncPay** (Client ID e Secret)

---

## 📁 **PARTE 1: PREPARAR O PROJETO LOCALMENTE**

### **1.1 - Criar arquivo `.env` com suas configurações**

Na pasta do projeto (`C:\Users\grcon\Downloads\grpay`), crie um arquivo chamado `.env`:

```bash
# Flask Configuration
SECRET_KEY=minha-chave-super-segura-aleatoria-min-32-caracteres-2024
FLASK_ENV=production

# Database (PostgreSQL dentro do container)
DATABASE_URL=postgresql://botmanager:senha-forte-db-2024@localhost:5432/botmanager_db

# SyncPay API
SYNCPAY_CLIENT_ID=seu-client-id-aqui
SYNCPAY_CLIENT_SECRET=seu-client-secret-aqui

# Platform Split (seu ID para receber comissões)
PLATFORM_SPLIT_USER_ID=seu-client-id-syncpay

# Webhook URL (seu domínio - pode usar subdomínio)
WEBHOOK_URL=https://grpay.seudominio.com.br

# Server Port
PORT=5000
```

**⚠️ IMPORTANTE:**
- Troque `grpay.seudominio.com.br` pelo seu domínio ou subdomínio
- Troque as credenciais da SyncPay
- Guarde a senha do banco (`senha-forte-db-2024`)

---

### **1.2 - Compactar o projeto**

No Windows:
1. Vá até `C:\Users\grcon\Downloads\`
2. Clique com botão direito na pasta `grpay`
3. **"Enviar para" > "Pasta compactada (zipada)"**
4. Vai criar `grpay.zip`

**Arquivos importantes que DEVEM estar:**
- `app.py`, `bot_manager.py`, `models.py`, `wsgi.py`
- `requirements.txt`
- `Dockerfile`, `docker-compose.yml`
- `.env` (o arquivo que você criou)
- Pastas `templates/` e `static/`

**NÃO incluir:**
- `venv/` (pasta virtual env)
- `instance/` (banco local)
- `__pycache__/`

---

## 🌐 **PARTE 2: CONFIGURAR O DOMÍNIO NO NAMECHEAP**

### **2.1 - Decidir: Domínio ou Subdomínio?**

**Opção 1: Usar domínio principal** (ex: `meusite.com.br`)
- Use se não tiver nada no domínio ainda

**Opção 2: Usar subdomínio** (ex: `grpay.meusite.com.br`) ⭐ **RECOMENDADO**
- Use se já tiver outras coisas no domínio principal

Vou usar **subdomínio** como exemplo. Se quiser usar o domínio principal, troque `grpay` por `@` nas configurações.

---

### **2.2 - Configurar DNS no Namecheap**

1. **Entre no Namecheap:**
   - https://www.namecheap.com/
   - Faça login
   - Clique em **"Domain List"**
   - Clique em **"Manage"** no seu domínio

2. **Vá na aba "Advanced DNS"**

3. **Adicione 1 registro A:**

   ```
   Type: A Record
   Host: grpay
   Value: IP_DA_SUA_VPS (ex: 123.456.789.10)
   TTL: Automatic
   ```

4. **Salve as mudanças**

⏳ **Propagação DNS:** Pode levar 5 minutos a 1 hora.

---

## 🖥️ **PARTE 3: CONECTAR NA VPS**

### **3.1 - Conectar via SSH**

1. **Abra o PuTTY** (ou seu cliente SSH)
2. Digite o **IP da VPS**
3. **Porta:** 22
4. Clique **"Open"**
5. Digite usuário e senha

✅ Conectado!

---

## 📦 **PARTE 4: CRIAR CONTAINER LXD PARA O GRPAY**

### **4.1 - Criar novo container Ubuntu**

```bash
# Criar container chamado 'grpay'
lxc launch ubuntu:22.04 grpay

# Aguardar container iniciar (10 segundos)
sleep 10

# Verificar se está rodando
lxc list
```

Deve aparecer o container `grpay` com status **RUNNING**.

---

### **4.2 - Configurar container**

```bash
# Entrar no container
lxc exec grpay -- bash

# Agora você está DENTRO do container grpay
# O prompt vai mudar para: root@grpay:~#
```

---

### **4.3 - Atualizar sistema dentro do container**

```bash
# Atualizar pacotes
apt update && apt upgrade -y

# Instalar dependências básicas
apt install -y curl wget git unzip nano
```

⏳ Pode demorar 5 minutos.

---

### **4.4 - Instalar Docker dentro do container**

```bash
# Instalar Docker
curl -fsSL https://get.docker.com -o get-docker.sh
sh get-docker.sh

# Iniciar Docker
systemctl start docker
systemctl enable docker

# Verificar
docker --version
```

---

### **4.5 - Instalar Docker Compose**

```bash
# Baixar Docker Compose
curl -L "https://github.com/docker/compose/releases/latest/download/docker-compose-$(uname -s)-$(uname -m)" -o /usr/local/bin/docker-compose

# Dar permissão
chmod +x /usr/local/bin/docker-compose

# Verificar
docker-compose --version
```

---

### **4.6 - Instalar Nginx**

```bash
# Instalar Nginx
apt install -y nginx

# Iniciar
systemctl start nginx
systemctl enable nginx

# Verificar
systemctl status nginx
```

Pressione `q` para sair.

---

### **4.7 - Instalar Certbot (SSL/HTTPS)**

```bash
# Instalar Certbot
apt install -y certbot python3-certbot-nginx
```

---

## 📤 **PARTE 5: ENVIAR PROJETO PARA O CONTAINER**

### **5.1 - Sair do container temporariamente**

```bash
# Sair do container (voltar para a VPS host)
exit
```

Agora você está de volta na VPS principal.

---

### **5.2 - Enviar arquivo ZIP para a VPS**

**Opção A: WinSCP (Recomendado)**
1. Abra o WinSCP
2. Conecte na VPS (IP, porta 22, usuário, senha)
3. Envie `grpay.zip` para `/root/`

**Opção B: Terminal (se tiver)**
```bash
# No seu computador Windows (PowerShell)
scp C:\Users\grcon\Downloads\grpay.zip root@IP_DA_VPS:/root/
```

---

### **5.3 - Copiar arquivo para dentro do container**

Na VPS (host), execute:

```bash
# Copiar ZIP da VPS para dentro do container
lxc file push /root/grpay.zip grpay/root/

# Verificar se copiou
lxc exec grpay -- ls -lh /root/grpay.zip
```

Deve mostrar o arquivo `grpay.zip` dentro do container.

---

### **5.4 - Entrar no container novamente**

```bash
# Entrar no container
lxc exec grpay -- bash
```

---

### **5.5 - Descompactar projeto**

```bash
# Ir para /root
cd /root

# Descompactar
unzip grpay.zip

# Se precisar instalar unzip
apt install -y unzip
unzip grpay.zip

# Entrar na pasta
cd grpay

# Ver arquivos
ls -la
```

---

## 🐳 **PARTE 6: RODAR O PROJETO COM DOCKER**

### **6.1 - Verificar arquivo .env**

```bash
# Ver conteúdo do .env
cat .env
```

Se não existir, crie:

```bash
nano .env
```

Cole o conteúdo da Parte 1.1, depois:
- `CTRL + O` (salvar)
- `ENTER`
- `CTRL + X` (sair)

---

### **6.2 - Ajustar docker-compose.yml**

```bash
nano docker-compose.yml
```

**Deixe assim:**
```yaml
version: '3.8'

services:
  web:
    build: .
    ports:
      - "5000:5000"
    environment:
      - FLASK_ENV=production
      - SECRET_KEY=${SECRET_KEY}
      - DATABASE_URL=${DATABASE_URL}
      - SYNCPAY_CLIENT_ID=${SYNCPAY_CLIENT_ID}
      - SYNCPAY_CLIENT_SECRET=${SYNCPAY_CLIENT_SECRET}
      - PLATFORM_SPLIT_USER_ID=${PLATFORM_SPLIT_USER_ID}
      - WEBHOOK_URL=${WEBHOOK_URL}
    volumes:
      - ./instance:/app/instance
    restart: unless-stopped
    depends_on:
      - db

  db:
    image: postgres:15-alpine
    environment:
      - POSTGRES_DB=botmanager_db
      - POSTGRES_USER=botmanager
      - POSTGRES_PASSWORD=senha-forte-db-2024
    volumes:
      - postgres_data:/var/lib/postgresql/data
    restart: unless-stopped

volumes:
  postgres_data:
```

Salve: `CTRL + O`, `ENTER`, `CTRL + X`

---

### **6.3 - Iniciar containers Docker**

```bash
# Iniciar (primeira vez demora 5-10 min)
docker-compose up -d --build
```

⏳ **Aguarde...** Docker vai baixar imagens e construir o projeto.

---

### **6.4 - Verificar se está rodando**

```bash
# Ver containers
docker-compose ps

# Ver logs
docker-compose logs -f web
```

Pressione `CTRL + C` para sair dos logs.

✅ Deve aparecer:
```
Listening at: 0.0.0.0:5000
```

---

### **6.5 - Inicializar banco de dados**

```bash
# Entrar no container web
docker-compose exec web bash

# Rodar init_db.py
python init_db.py

# Sair
exit
```

---

## 🌐 **PARTE 7: CONFIGURAR NGINX (PROXY)**

### **7.1 - Criar configuração do Nginx**

```bash
# Criar arquivo
nano /etc/nginx/sites-available/grpay
```

Cole (SUBSTITUA `grpay.seudominio.com.br`):

```nginx
server {
    listen 80;
    server_name grpay.seudominio.com.br;
    
    # Logs
    access_log /var/log/nginx/grpay_access.log;
    error_log /var/log/nginx/grpay_error.log;
    
    # Limite de upload
    client_max_body_size 50M;
    
    location / {
        proxy_pass http://127.0.0.1:5000;
        proxy_http_version 1.1;
        
        # Headers
        proxy_set_header Upgrade $http_upgrade;
        proxy_set_header Connection 'upgrade';
        proxy_set_header Host $host;
        proxy_set_header X-Real-IP $remote_addr;
        proxy_set_header X-Forwarded-For $proxy_add_x_forwarded_for;
        proxy_set_header X-Forwarded-Proto $scheme;
        
        # Timeouts WebSocket
        proxy_read_timeout 300s;
        proxy_connect_timeout 75s;
        
        proxy_cache_bypass $http_upgrade;
    }
    
    # Socket.IO
    location /socket.io {
        proxy_pass http://127.0.0.1:5000/socket.io;
        proxy_http_version 1.1;
        proxy_set_header Upgrade $http_upgrade;
        proxy_set_header Connection "upgrade";
        proxy_set_header Host $host;
        proxy_set_header X-Real-IP $remote_addr;
        proxy_set_header X-Forwarded-For $proxy_add_x_forwarded_for;
    }
}
```

Salve: `CTRL + O`, `ENTER`, `CTRL + X`

---

### **7.2 - Ativar configuração**

```bash
# Criar link simbólico
ln -s /etc/nginx/sites-available/grpay /etc/nginx/sites-enabled/

# Testar
nginx -t

# Reiniciar
systemctl restart nginx
```

---

## 🔒 **PARTE 8: ATIVAR HTTPS (SSL GRÁTIS)**

### **8.1 - Testar se DNS propagou**

```bash
# Testar DNS
ping grpay.seudominio.com.br
```

Se aparecer o IP da VPS, está ok!

---

### **8.2 - Gerar certificado SSL**

```bash
# Gerar certificado (SUBSTITUA o domínio)
certbot --nginx -d grpay.seudominio.com.br
```

**Responda:**
1. **Email:** seu@email.com
2. **Aceitar termos:** Y
3. **Compartilhar email:** N
4. **Redirect HTTPS:** 2

✅ Certificado gerado!

---

## 🔥 **PARTE 9: EXPOR PORTA DO CONTAINER PARA A VPS**

### **9.1 - Sair do container**

```bash
# Sair do container (voltar para VPS host)
exit
```

---

### **9.2 - Configurar proxy device LXD**

Na VPS (host), execute:

```bash
# Expor porta 80 do container para porta 8080 da VPS
lxc config device add grpay http proxy listen=tcp:0.0.0.0:8080 connect=tcp:127.0.0.1:80

# Expor porta 443 do container para porta 8443 da VPS
lxc config device add grpay https proxy listen=tcp:0.0.0.0:8443 connect=tcp:127.0.0.1:443

# Verificar
lxc config show grpay
```

---

### **9.3 - Configurar Nginx na VPS (host) como proxy**

Na VPS (host), crie configuração:

```bash
# Criar arquivo no host
nano /etc/nginx/sites-available/grpay-proxy
```

Cole (SUBSTITUA o domínio):

```nginx
server {
    listen 80;
    server_name grpay.seudominio.com.br;
    
    location / {
        proxy_pass http://127.0.0.1:8080;
        proxy_set_header Host $host;
        proxy_set_header X-Real-IP $remote_addr;
        proxy_set_header X-Forwarded-For $proxy_add_x_forwarded_for;
        proxy_set_header X-Forwarded-Proto $scheme;
    }
}

server {
    listen 443 ssl;
    server_name grpay.seudominio.com.br;
    
    # Certificados (serão criados pelo Certbot)
    ssl_certificate /etc/letsencrypt/live/grpay.seudominio.com.br/fullchain.pem;
    ssl_certificate_key /etc/letsencrypt/live/grpay.seudominio.com.br/privkey.pem;
    
    location / {
        proxy_pass http://127.0.0.1:8080;
        proxy_set_header Host $host;
        proxy_set_header X-Real-IP $remote_addr;
        proxy_set_header X-Forwarded-For $proxy_add_x_forwarded_for;
        proxy_set_header X-Forwarded-Proto $scheme;
        proxy_set_header Upgrade $http_upgrade;
        proxy_set_header Connection "upgrade";
    }
}
```

Salve e ative:

```bash
# Ativar
ln -s /etc/nginx/sites-available/grpay-proxy /etc/nginx/sites-enabled/

# Testar
nginx -t

# Reiniciar
systemctl restart nginx

# Gerar SSL no HOST
certbot --nginx -d grpay.seudominio.com.br
```

---

## ✅ **PARTE 10: VERIFICAR SE ESTÁ FUNCIONANDO**

### **10.1 - Acessar o site**

Abra o navegador:
```
https://grpay.seudominio.com.br
```

✅ Deve aparecer a página de login!

---

## 🔧 **COMANDOS ÚTEIS**

### **Gerenciar o container:**

```bash
# Ver todos containers
lxc list

# Entrar no container grpay
lxc exec grpay -- bash

# Ver logs da aplicação (dentro do container)
cd /root/grpay
docker-compose logs -f web

# Reiniciar aplicação (dentro do container)
docker-compose restart

# Parar container
lxc stop grpay

# Iniciar container
lxc start grpay

# Reiniciar container
lxc restart grpay
```

---

### **Ver recursos:**

```bash
# Ver uso de memória de todos containers LXD
lxc list

# Ver recursos detalhados do grpay
lxc info grpay

# Ver processos dentro do container
lxc exec grpay -- ps aux
```

---

## 🆘 **SOLUÇÃO DE PROBLEMAS**

### **Erro: "502 Bad Gateway"**

```bash
# Entrar no container
lxc exec grpay -- bash

# Ver logs
cd /root/grpay
docker-compose logs web

# Reiniciar
docker-compose restart
```

---

### **Erro: Container não inicia**

```bash
# Ver status
lxc list

# Ver logs do container
lxc info grpay

# Reiniciar
lxc restart grpay
```

---

### **Erro: "Database connection failed"**

```bash
# Entrar no container
lxc exec grpay -- bash
cd /root/grpay

# Verificar se banco está rodando
docker-compose ps

# Recriar banco
docker-compose down
docker volume rm grpay_postgres_data
docker-compose up -d
docker-compose exec web python init_db.py
```

---

## 📊 **BACKUP DO CONTAINER**

### **Criar snapshot:**

```bash
# Criar snapshot do container inteiro
lxc snapshot grpay backup-$(date +%Y%m%d)

# Listar snapshots
lxc info grpay

# Restaurar snapshot (se necessário)
lxc restore grpay backup-20240101
```

---

### **Backup dos dados:**

```bash
# Entrar no container
lxc exec grpay -- bash

# Criar backup do banco
cd /root/grpay
docker-compose exec -T db pg_dump -U botmanager botmanager_db > backup_$(date +%Y%m%d).sql

# Copiar backup para a VPS host
exit
lxc file pull grpay/root/grpay/backup_*.sql /root/backups/
```

---

## 📝 **CHECKLIST FINAL**

- [ ] 1. Criar arquivo `.env` local
- [ ] 2. Compactar projeto (`grpay.zip`)
- [ ] 3. Configurar DNS no Namecheap (A Record)
- [ ] 4. Conectar na VPS via SSH
- [ ] 5. Criar container LXD (`lxc launch ubuntu:22.04 grpay`)
- [ ] 6. Instalar Docker no container
- [ ] 7. Instalar Nginx no container
- [ ] 8. Enviar `grpay.zip` para o container
- [ ] 9. Descompactar e rodar `docker-compose up -d --build`
- [ ] 10. Inicializar banco (`python init_db.py`)
- [ ] 11. Configurar Nginx no container
- [ ] 12. Configurar proxy LXD (portas 8080/8443)
- [ ] 13. Configurar Nginx na VPS host
- [ ] 14. Gerar SSL na VPS host
- [ ] 15. Testar site: `https://grpay.seudominio.com.br`
- [ ] 16. Criar primeiro usuário

---

## 🎉 **PRONTO!**

Seu sistema grpay está rodando em um **container LXD isolado** dentro da sua VPS!

**Vantagens dessa arquitetura:**
- ✅ Isolamento total dos outros containers
- ✅ Fácil gerenciamento via LXD
- ✅ Snapshots rápidos para backup
- ✅ Pode ter domínio próprio
- ✅ Não interfere nos outros projetos

**Links importantes:**
- **Site:** https://grpay.seudominio.com.br
- **Login:** https://grpay.seudominio.com.br/login
- **Registro:** https://grpay.seudominio.com.br/register

---

**✍️ Deploy otimizado para LXD - Criado especialmente para sua VPS**



