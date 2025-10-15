# 🚀 GUIA COMPLETO: DEPLOY NA VPS COM LXD + DOMÍNIO NAMECHEAP

**Para iniciantes - Passo a passo detalhado**

---

## 📋 **O QUE VOCÊ VAI PRECISAR**

Antes de começar, tenha em mãos:

1. ✅ **IP da sua VPS** (ex: `123.456.789.10`)
2. ✅ **Usuário e senha da VPS** (geralmente `root` ou `ubuntu`)
3. ✅ **Seu domínio** (ex: `meusite.com.br`)
4. ✅ **Acesso ao painel do Namecheap**
5. ✅ **Token do bot do Telegram** (pegue com o @BotFather)
6. ✅ **Credenciais da SyncPay** (Client ID e Secret)

---

## 📁 **PARTE 1: PREPARAR O PROJETO LOCALMENTE**

### **1.1 - Criar arquivo `.env` com suas configurações**

Na pasta do projeto (`grpay`), crie um arquivo chamado `.env` (sem nome antes do ponto):

```bash
# Flask Configuration
SECRET_KEY=minha-chave-super-segura-aleatoria-min-32-caracteres-2024
FLASK_ENV=production

# Database (PostgreSQL)
DATABASE_URL=postgresql://botmanager:senha-forte-db-2024@localhost:5432/botmanager_db

# SyncPay API
SYNCPAY_CLIENT_ID=seu-client-id-aqui
SYNCPAY_CLIENT_SECRET=seu-client-secret-aqui

# Platform Split (seu ID para receber comissões)
PLATFORM_SPLIT_USER_ID=seu-client-id-syncpay

# Webhook URL (seu domínio)
WEBHOOK_URL=https://seudominio.com.br

# Server Port
PORT=5000
```

**⚠️ IMPORTANTE:**
- Troque `seudominio.com.br` pelo seu domínio real
- Troque as credenciais da SyncPay pelas suas
- Guarde essa senha do banco (`senha-forte-db-2024`) - você vai usar

---

### **1.2 - Compactar o projeto**

No Windows:
1. Vá até a pasta `C:\Users\grcon\Downloads\`
2. Clique com botão direito na pasta `grpay`
3. Escolha **"Enviar para" > "Pasta compactada (zipada)"**
4. Vai criar um arquivo `grpay.zip`

**Arquivos que DEVEM estar no ZIP:**
- `app.py`
- `bot_manager.py`
- `models.py`
- `wsgi.py`
- `requirements.txt`
- `Dockerfile`
- `docker-compose.yml`
- `.env` (o arquivo que você criou acima)
- Pasta `templates/`
- Pasta `static/`

**Arquivos que NÃO precisam:**
- `venv/` (pasta virtual env - NÃO envie)
- `instance/` (banco local - NÃO envie)
- `__pycache__/` (cache - NÃO envie)

---

## 🌐 **PARTE 2: CONFIGURAR O DOMÍNIO NO NAMECHEAP**

### **2.1 - Apontar domínio para a VPS**

1. **Entre no Namecheap:**
   - Vá em https://www.namecheap.com/
   - Faça login
   - Clique em **"Domain List"**
   - Clique em **"Manage"** no seu domínio

2. **Configurar DNS:**
   - Vá na aba **"Advanced DNS"**
   - Clique em **"ADD NEW RECORD"**
   
3. **Adicione 2 registros:**

   **Registro 1 (domínio principal):**
   ```
   Type: A Record
   Host: @
   Value: SEU_IP_DA_VPS (ex: 123.456.789.10)
   TTL: Automatic
   ```
   
   **Registro 2 (www):**
   ```
   Type: A Record
   Host: www
   Value: SEU_IP_DA_VPS (ex: 123.456.789.10)
   TTL: Automatic
   ```

4. **Salve as mudanças**

⏳ **ATENÇÃO:** Pode levar de 5 minutos a 24 horas para o DNS propagar. Geralmente leva 1 hora.

---

## 🖥️ **PARTE 3: CONECTAR NA VPS**

### **3.1 - Baixar programa SSH (Windows)**

Se você não tem, baixe o **PuTTY**:
- Site: https://www.putty.org/
- Baixe a versão **64-bit** para Windows
- Instale normalmente

### **3.2 - Conectar na VPS**

1. **Abra o PuTTY**
2. Em **"Host Name"**, digite o IP da sua VPS: `123.456.789.10`
3. Em **"Port"**, deixe `22`
4. Clique em **"Open"**
5. Se aparecer um alerta de segurança, clique **"Yes"**
6. Digite o usuário (geralmente `root`) e pressione ENTER
7. Digite a senha e pressione ENTER (a senha não aparece enquanto digita, é normal)

✅ Se conectou, você vai ver algo como:
```
root@vps-servidor:~#
```

---

## 📦 **PARTE 4: PREPARAR A VPS**

### **4.1 - Atualizar o sistema**

Cole cada comando abaixo e pressione ENTER (um por vez):

```bash
# Atualizar lista de pacotes
sudo apt update

# Atualizar pacotes instalados
sudo apt upgrade -y
```

⏳ Pode demorar 5-10 minutos.

---

### **4.2 - Instalar Docker**

Cole cada comando (um por vez):

```bash
# Instalar dependências
sudo apt install -y apt-transport-https ca-certificates curl software-properties-common

# Adicionar chave GPG do Docker
curl -fsSL https://download.docker.com/linux/ubuntu/gpg | sudo gpg --dearmor -o /usr/share/keyrings/docker-archive-keyring.gpg

# Adicionar repositório do Docker
echo "deb [arch=$(dpkg --print-architecture) signed-by=/usr/share/keyrings/docker-archive-keyring.gpg] https://download.docker.com/linux/ubuntu $(lsb_release -cs) stable" | sudo tee /etc/apt/sources.list.d/docker.list > /dev/null

# Atualizar lista de pacotes novamente
sudo apt update

# Instalar Docker
sudo apt install -y docker-ce docker-ce-cli containerd.io

# Verificar se instalou
docker --version
```

Deve aparecer algo como: `Docker version 24.0.7`

---

### **4.3 - Instalar Docker Compose**

```bash
# Baixar Docker Compose
sudo curl -L "https://github.com/docker/compose/releases/latest/download/docker-compose-$(uname -s)-$(uname -m)" -o /usr/local/bin/docker-compose

# Dar permissão de execução
sudo chmod +x /usr/local/bin/docker-compose

# Verificar
docker-compose --version
```

Deve aparecer algo como: `Docker Compose version v2.23.0`

---

### **4.4 - Instalar Nginx (servidor web)**

```bash
# Instalar Nginx
sudo apt install -y nginx

# Iniciar Nginx
sudo systemctl start nginx

# Ativar para iniciar automaticamente
sudo systemctl enable nginx

# Verificar status
sudo systemctl status nginx
```

Pressione `q` para sair do status.

---

### **4.5 - Instalar Certbot (para SSL/HTTPS grátis)**

```bash
# Instalar Certbot
sudo apt install -y certbot python3-certbot-nginx
```

---

## 📤 **PARTE 5: ENVIAR O PROJETO PARA A VPS**

### **5.1 - Usando SFTP (WinSCP - Recomendado)**

1. **Baixe o WinSCP:**
   - Site: https://winscp.net/eng/download.php
   - Baixe e instale

2. **Conecte no servidor:**
   - Abra o WinSCP
   - **File protocol:** SFTP
   - **Host name:** IP da sua VPS
   - **Port number:** 22
   - **User name:** root (ou seu usuário)
   - **Password:** sua senha
   - Clique em **"Login"**

3. **Enviar o projeto:**
   - Do lado esquerdo (seu computador), navegue até a pasta onde está o `grpay.zip`
   - Do lado direito (VPS), você vai estar em `/root/`
   - Arraste o arquivo `grpay.zip` do lado esquerdo para o lado direito
   - Aguarde o upload terminar

---

### **5.2 - Descompactar na VPS**

No PuTTY (terminal SSH), digite:

```bash
# Ver se o arquivo está lá
ls -lh grpay.zip

# Instalar unzip (se não tiver)
sudo apt install -y unzip

# Descompactar
unzip grpay.zip

# Entrar na pasta
cd grpay

# Ver os arquivos
ls -la
```

Você deve ver todos os arquivos do projeto listados.

---

## 🐳 **PARTE 6: RODAR O PROJETO COM DOCKER**

### **6.1 - Criar arquivo .env na VPS (se não veio no ZIP)**

Se o arquivo `.env` não veio no ZIP, crie agora:

```bash
nano .env
```

Cole o conteúdo que você criou na Parte 1.1 e depois:
- Pressione `CTRL + O` (para salvar)
- Pressione `ENTER`
- Pressione `CTRL + X` (para sair)

---

### **6.2 - Ajustar docker-compose.yml**

Vamos editar o arquivo para usar porta interna:

```bash
nano docker-compose.yml
```

Mude a linha de portas para:
```yaml
    ports:
      - "127.0.0.1:5000:5000"
```

Depois:
- Pressione `CTRL + O` (salvar)
- Pressione `ENTER`
- Pressione `CTRL + X` (sair)

---

### **6.3 - Iniciar o projeto**

```bash
# Dar permissão para executar
chmod +x docker-compose.yml

# Iniciar os containers (primeira vez demora 5-10 min)
sudo docker-compose up -d --build
```

**Explicação:**
- `-d` = rodar em background
- `--build` = construir as imagens

⏳ **Aguarde...** Docker vai baixar as imagens e construir o projeto.

---

### **6.4 - Verificar se está rodando**

```bash
# Ver containers ativos
sudo docker-compose ps

# Ver logs da aplicação
sudo docker-compose logs -f web
```

Pressione `CTRL + C` para sair dos logs.

✅ Se tudo deu certo, você verá:
```
web_1  | [INFO] Booting worker with pid: ...
web_1  | [INFO] Listening at: 0.0.0.0:5000
```

---

### **6.5 - Inicializar o banco de dados**

```bash
# Entrar no container
sudo docker-compose exec web bash

# Dentro do container, rodar o script de inicialização
python init_db.py

# Sair do container
exit
```

---

## 🌐 **PARTE 7: CONFIGURAR NGINX (PROXY REVERSO)**

### **7.1 - Criar configuração do Nginx**

```bash
# Criar arquivo de configuração
sudo nano /etc/nginx/sites-available/grpay
```

Cole este conteúdo (SUBSTITUA `seudominio.com.br` pelo seu domínio real):

```nginx
server {
    listen 80;
    server_name seudominio.com.br www.seudominio.com.br;
    
    # Logs
    access_log /var/log/nginx/grpay_access.log;
    error_log /var/log/nginx/grpay_error.log;
    
    # Limite de tamanho de upload
    client_max_body_size 50M;
    
    location / {
        proxy_pass http://127.0.0.1:5000;
        proxy_http_version 1.1;
        
        # Headers importantes
        proxy_set_header Upgrade $http_upgrade;
        proxy_set_header Connection 'upgrade';
        proxy_set_header Host $host;
        proxy_set_header X-Real-IP $remote_addr;
        proxy_set_header X-Forwarded-For $proxy_add_x_forwarded_for;
        proxy_set_header X-Forwarded-Proto $scheme;
        
        # Timeouts para WebSocket
        proxy_read_timeout 300s;
        proxy_connect_timeout 75s;
        
        # Sem cache
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

Depois:
- Pressione `CTRL + O` (salvar)
- Pressione `ENTER`
- Pressione `CTRL + X` (sair)

---

### **7.2 - Ativar a configuração**

```bash
# Criar link simbólico
sudo ln -s /etc/nginx/sites-available/grpay /etc/nginx/sites-enabled/

# Remover configuração padrão
sudo rm /etc/nginx/sites-enabled/default

# Testar configuração
sudo nginx -t

# Reiniciar Nginx
sudo systemctl restart nginx

# Verificar status
sudo systemctl status nginx
```

Pressione `q` para sair.

---

## 🔒 **PARTE 8: ATIVAR HTTPS (CERTIFICADO SSL GRÁTIS)**

### **8.1 - Gerar certificado SSL**

⚠️ **IMPORTANTE:** Só faça isso depois que o DNS propagar (geralmente 1 hora após configurar no Namecheap).

Para testar se o DNS propagou:
```bash
ping seudominio.com.br
```

Se aparecer o IP da sua VPS, está ok!

Agora gere o certificado (SUBSTITUA o domínio):

```bash
# Gerar certificado
sudo certbot --nginx -d seudominio.com.br -d www.seudominio.com.br
```

**Perguntas que vão aparecer:**

1. **Email:** Digite seu email (para avisos de renovação)
2. **Termos:** Digite `Y` (aceitar)
3. **Compartilhar email:** Digite `N` (não compartilhar)
4. **Redirect HTTPS:** Digite `2` (redirecionar tudo para HTTPS)

✅ Se tudo der certo, vai aparecer:
```
Congratulations! You have successfully enabled HTTPS...
```

---

### **8.2 - Renovação automática**

O Certbot já configura renovação automática, mas vamos testar:

```bash
# Testar renovação (sem renovar de verdade)
sudo certbot renew --dry-run
```

Se aparecer `Congratulations, all renewals succeeded`, está ok!

---

## ✅ **PARTE 9: VERIFICAR SE ESTÁ FUNCIONANDO**

### **9.1 - Acessar o site**

Abra o navegador e acesse:
```
https://seudominio.com.br
```

✅ Deve aparecer a página de login do seu sistema!

---

### **9.2 - Comandos úteis**

**Ver logs da aplicação:**
```bash
cd /root/grpay
sudo docker-compose logs -f web
```

**Reiniciar aplicação:**
```bash
cd /root/grpay
sudo docker-compose restart
```

**Parar aplicação:**
```bash
cd /root/grpay
sudo docker-compose stop
```

**Iniciar aplicação:**
```bash
cd /root/grpay
sudo docker-compose start
```

**Reconstruir aplicação (após mudanças):**
```bash
cd /root/grpay
sudo docker-compose down
sudo docker-compose up -d --build
```

**Ver containers rodando:**
```bash
sudo docker ps
```

**Ver uso de recursos:**
```bash
sudo docker stats
```

---

## 🔥 **PARTE 10: FIREWALL (SEGURANÇA)**

### **10.1 - Configurar UFW**

```bash
# Permitir SSH (MUITO IMPORTANTE - NÃO PULE!)
sudo ufw allow 22/tcp

# Permitir HTTP
sudo ufw allow 80/tcp

# Permitir HTTPS
sudo ufw allow 443/tcp

# Permitir PostgreSQL (só localmente)
sudo ufw allow from 127.0.0.1 to any port 5432

# Ativar firewall
sudo ufw enable

# Verificar status
sudo ufw status
```

---

## 🎯 **PARTE 11: CRIAR PRIMEIRO USUÁRIO**

1. Acesse: `https://seudominio.com.br/register`
2. Cadastre-se
3. Faça login
4. Pronto! Comece a usar

---

## 📊 **PARTE 12: MONITORAMENTO**

### **12.1 - Ver logs em tempo real**

```bash
# Logs da aplicação
cd /root/grpay && sudo docker-compose logs -f web

# Logs do Nginx
sudo tail -f /var/log/nginx/grpay_access.log
sudo tail -f /var/log/nginx/grpay_error.log
```

Pressione `CTRL + C` para sair.

---

### **12.2 - Criar script de backup automático**

```bash
# Criar script
sudo nano /root/backup.sh
```

Cole:
```bash
#!/bin/bash
DATE=$(date +%Y%m%d_%H%M%S)
BACKUP_DIR="/root/backups"

# Criar pasta de backups
mkdir -p $BACKUP_DIR

# Backup do banco de dados
cd /root/grpay
sudo docker-compose exec -T db pg_dump -U botmanager botmanager_db > $BACKUP_DIR/db_$DATE.sql

# Backup dos arquivos
tar -czf $BACKUP_DIR/files_$DATE.tar.gz /root/grpay --exclude=venv --exclude=__pycache__

# Manter apenas últimos 7 backups
find $BACKUP_DIR -name "db_*.sql" -mtime +7 -delete
find $BACKUP_DIR -name "files_*.tar.gz" -mtime +7 -delete

echo "Backup concluído: $DATE"
```

Depois:
```bash
# Dar permissão
sudo chmod +x /root/backup.sh

# Testar
sudo /root/backup.sh

# Agendar para rodar todo dia às 3h da manhã
(crontab -l 2>/dev/null; echo "0 3 * * * /root/backup.sh >> /var/log/backup.log 2>&1") | crontab -
```

---

## 🆘 **SOLUÇÃO DE PROBLEMAS**

### **Erro: "502 Bad Gateway"**

```bash
# Verificar se containers estão rodando
sudo docker-compose ps

# Ver logs
sudo docker-compose logs -f web

# Reiniciar
sudo docker-compose restart
```

---

### **Erro: "Database connection failed"**

```bash
# Entrar no container do banco
sudo docker-compose exec db psql -U botmanager -d botmanager_db

# Se conectar, o banco está ok. Digite \q para sair.

# Se não conectar, recriar banco:
sudo docker-compose down
sudo docker volume rm grpay_postgres_data
sudo docker-compose up -d
```

---

### **Site não abre (DNS não propagou)**

```bash
# Testar DNS
nslookup seudominio.com.br

# Testar localmente
curl http://localhost
```

Se localhost funcionar mas o domínio não, aguarde a propagação do DNS (até 24h).

---

### **SSL não gerou**

```bash
# Renovar certificado manualmente
sudo certbot --nginx -d seudominio.com.br -d www.seudominio.com.br --force-renewal
```

---

## 📝 **CHECKLIST FINAL**

Marque cada item conforme concluir:

- [ ] 1. Criar arquivo `.env` local
- [ ] 2. Compactar projeto (`grpay.zip`)
- [ ] 3. Configurar DNS no Namecheap (A Records)
- [ ] 4. Conectar na VPS via SSH (PuTTY)
- [ ] 5. Atualizar sistema (`apt update && upgrade`)
- [ ] 6. Instalar Docker
- [ ] 7. Instalar Docker Compose
- [ ] 8. Instalar Nginx
- [ ] 9. Instalar Certbot
- [ ] 10. Enviar `grpay.zip` via WinSCP
- [ ] 11. Descompactar projeto na VPS
- [ ] 12. Rodar `docker-compose up -d --build`
- [ ] 13. Inicializar banco (`python init_db.py`)
- [ ] 14. Configurar Nginx
- [ ] 15. Gerar SSL com Certbot
- [ ] 16. Configurar Firewall (UFW)
- [ ] 17. Testar site: `https://seudominio.com.br`
- [ ] 18. Criar primeiro usuário
- [ ] 19. Configurar backup automático

---

## 🎉 **PARABÉNS!**

Seu sistema está no ar! 🚀

**Links importantes:**
- **Site:** https://seudominio.com.br
- **Login:** https://seudominio.com.br/login
- **Registro:** https://seudominio.com.br/register
- **Redirecionador:** https://seudominio.com.br/redirect-pools

---

## 📞 **SUPORTE**

Se tiver problemas, envie:
1. Logs da aplicação: `sudo docker-compose logs web`
2. Logs do Nginx: `sudo cat /var/log/nginx/grpay_error.log`
3. Status dos containers: `sudo docker-compose ps`

---

**✍️ Criado especialmente para iniciantes - Passo a passo completo**
**📅 Data: 2024**



