# 🎯 GUIA VISUAL SIMPLIFICADO - DEPLOY VPS

**Resumo rápido para consulta**

---

## 📊 **FLUXO COMPLETO**

```
┌─────────────────────────────────────────────────────────────┐
│                    SEU COMPUTADOR                           │
│                                                             │
│  1. Criar .env                                             │
│  2. Compactar projeto (grpay.zip)                         │
│  3. Configurar DNS Namecheap                               │
│     │                                                       │
│     └──> IP: 123.456.789.10                               │
│                                                             │
└─────────────────────────────────────────────────────────────┘
                          │
                          │ Upload via WinSCP
                          ▼
┌─────────────────────────────────────────────────────────────┐
│                     VPS (SERVIDOR)                          │
│                                                             │
│  ┌───────────────────────────────────────────────┐        │
│  │  DOCKER COMPOSE                                │        │
│  │                                                 │        │
│  │  ┌─────────────┐      ┌──────────────┐       │        │
│  │  │   WEB APP   │◄────►│  POSTGRESQL  │       │        │
│  │  │  (Flask)    │      │  (Database)  │       │        │
│  │  │  Porta 5000 │      │  Porta 5432  │       │        │
│  │  └─────────────┘      └──────────────┘       │        │
│  │         ▲                                      │        │
│  └─────────┼──────────────────────────────────────┘        │
│            │                                                │
│  ┌─────────┴────────────────────┐                         │
│  │       NGINX                   │                         │
│  │  (Proxy Reverso)             │                         │
│  │  Porta 80/443 (HTTP/HTTPS)   │                         │
│  └─────────┬────────────────────┘                         │
│            │                                                │
│  ┌─────────┴────────────────────┐                         │
│  │     CERTBOT (SSL)            │                         │
│  │  Certificado HTTPS grátis    │                         │
│  └──────────────────────────────┘                         │
│                                                             │
└─────────────────────────────────────────────────────────────┘
                          │
                          │ HTTPS
                          ▼
┌─────────────────────────────────────────────────────────────┐
│               INTERNET (PÚBLICO)                            │
│                                                             │
│  https://seudominio.com.br                                 │
│                                                             │
└─────────────────────────────────────────────────────────────┘
```

---

## ⚡ **COMANDOS ESSENCIAIS (COPIE E COLE)**

### **1️⃣ Preparar VPS**

```bash
# Atualizar sistema
sudo apt update && sudo apt upgrade -y

# Instalar Docker
curl -fsSL https://get.docker.com -o get-docker.sh
sudo sh get-docker.sh

# Instalar Docker Compose
sudo curl -L "https://github.com/docker/compose/releases/latest/download/docker-compose-$(uname -s)-$(uname -m)" -o /usr/local/bin/docker-compose
sudo chmod +x /usr/local/bin/docker-compose

# Instalar Nginx
sudo apt install -y nginx

# Instalar Certbot (SSL)
sudo apt install -y certbot python3-certbot-nginx
```

---

### **2️⃣ Descompactar e Rodar Projeto**

```bash
# Descompactar
cd /root
unzip grpay.zip
cd grpay

# Rodar Docker
sudo docker-compose up -d --build

# Esperar 5 minutos...

# Inicializar banco
sudo docker-compose exec web python init_db.py

# Ver logs
sudo docker-compose logs -f web
```

---

### **3️⃣ Configurar Nginx**

```bash
# Criar configuração
sudo nano /etc/nginx/sites-available/grpay
```

**Cole o conteúdo do arquivo de configuração Nginx (veja guia completo)**

```bash
# Ativar
sudo ln -s /etc/nginx/sites-available/grpay /etc/nginx/sites-enabled/
sudo rm /etc/nginx/sites-enabled/default
sudo nginx -t
sudo systemctl restart nginx
```

---

### **4️⃣ Gerar SSL (HTTPS)**

```bash
# Gerar certificado (SUBSTITUA o domínio)
sudo certbot --nginx -d seudominio.com.br -d www.seudominio.com.br
```

**Responda:**
- Email: `seu@email.com`
- Aceitar termos: `Y`
- Compartilhar email: `N`
- Redirect HTTPS: `2`

---

### **5️⃣ Firewall**

```bash
sudo ufw allow 22/tcp
sudo ufw allow 80/tcp
sudo ufw allow 443/tcp
sudo ufw enable
```

---

## 🔍 **VERIFICAÇÃO RÁPIDA**

### **✅ Containers rodando?**
```bash
sudo docker ps
```

Deve mostrar 2 containers: `grpay_web_1` e `grpay_db_1`

---

### **✅ App respondendo?**
```bash
curl http://localhost:5000
```

Deve retornar HTML

---

### **✅ Nginx funcionando?**
```bash
curl http://localhost
```

Deve retornar HTML

---

### **✅ DNS propagou?**
```bash
ping seudominio.com.br
```

Deve mostrar o IP da sua VPS

---

### **✅ SSL ativo?**
```bash
sudo certbot certificates
```

Deve mostrar seu certificado válido

---

## 📁 **ESTRUTURA DE ARQUIVOS NA VPS**

```
/root/grpay/
├── app.py                    # Aplicação principal
├── bot_manager.py           # Gerenciador de bots
├── models.py                # Modelos do banco
├── wsgi.py                  # Entry point Gunicorn
├── requirements.txt         # Dependências Python
├── Dockerfile               # Configuração Docker
├── docker-compose.yml       # Orquestração
├── .env                     # SUAS CONFIGURAÇÕES
├── templates/               # HTMLs
├── static/                  # CSS/JS
└── instance/               # Dados SQLite (se usar)
```

---

## 🚨 **RESOLUÇÃO RÁPIDA DE PROBLEMAS**

### **Problema: Site não abre (502 Bad Gateway)**

```bash
# 1. Ver se containers estão rodando
sudo docker ps

# 2. Ver logs
cd /root/grpay
sudo docker-compose logs -f web

# 3. Reiniciar
sudo docker-compose restart
```

---

### **Problema: Erro de banco de dados**

```bash
# 1. Entrar no container
sudo docker-compose exec web bash

# 2. Rodar init_db.py novamente
python init_db.py

# 3. Sair
exit
```

---

### **Problema: SSL não gerou**

```bash
# 1. Verificar DNS
ping seudominio.com.br

# 2. Tentar novamente
sudo certbot --nginx -d seudominio.com.br -d www.seudominio.com.br --force-renewal
```

---

### **Problema: Container não inicia**

```bash
# 1. Ver erro completo
sudo docker-compose logs web

# 2. Verificar .env
cat /root/grpay/.env

# 3. Reconstruir
sudo docker-compose down
sudo docker-compose up -d --build
```

---

## 🔄 **ATUALIZAR O PROJETO**

Quando fizer mudanças no código:

```bash
# 1. Ir para a pasta
cd /root/grpay

# 2. Parar containers
sudo docker-compose down

# 3. Enviar novos arquivos via WinSCP
#    (ou usar git pull se tiver configurado)

# 4. Reconstruir e iniciar
sudo docker-compose up -d --build

# 5. Ver logs
sudo docker-compose logs -f web
```

---

## 📊 **MONITORAMENTO EM TEMPO REAL**

### **Ver logs continuamente:**
```bash
cd /root/grpay
sudo docker-compose logs -f
```

### **Ver uso de recursos:**
```bash
sudo docker stats
```

### **Ver processos:**
```bash
sudo docker ps -a
```

### **Ver espaço em disco:**
```bash
df -h
```

### **Limpar containers antigos:**
```bash
sudo docker system prune -a
```

---

## 🎯 **TEMPLATE .ENV (COPIE E EDITE)**

```bash
# Flask Configuration
SECRET_KEY=gere-uma-chave-aleatoria-com-32-caracteres-minimo
FLASK_ENV=production

# Database
DATABASE_URL=postgresql://botmanager:SuaSenhaSuperForte123@localhost:5432/botmanager_db

# SyncPay API
SYNCPAY_CLIENT_ID=cole-seu-client-id-aqui
SYNCPAY_CLIENT_SECRET=cole-seu-client-secret-aqui

# Platform Split
PLATFORM_SPLIT_USER_ID=mesmo-client-id-da-syncpay

# Webhook URL
WEBHOOK_URL=https://seudominio.com.br

# Server Port
PORT=5000
```

**⚠️ EDITE ANTES DE USAR:**
- Troque `seudominio.com.br`
- Troque credenciais da SyncPay
- Gere uma SECRET_KEY forte

**Como gerar SECRET_KEY:**
```bash
python3 -c "import secrets; print(secrets.token_hex(32))"
```

---

## 📞 **INFORMAÇÕES PARA SUPORTE**

Se precisar de ajuda, reúna estas informações:

```bash
# 1. Logs da aplicação
sudo docker-compose logs web > logs_app.txt

# 2. Logs do Nginx
sudo cat /var/log/nginx/grpay_error.log > logs_nginx.txt

# 3. Status dos containers
sudo docker-compose ps > status_containers.txt

# 4. Configuração do Nginx
sudo cat /etc/nginx/sites-available/grpay > config_nginx.txt

# 5. Arquivo .env (SEM as senhas)
cat /root/grpay/.env | sed 's/=.*/=***/' > config_env.txt
```

---

## ✅ **CHECKLIST RÁPIDO**

```
□ DNS configurado no Namecheap (A Records)
□ VPS atualizada (apt update && upgrade)
□ Docker instalado (docker --version)
□ Docker Compose instalado (docker-compose --version)
□ Nginx instalado (nginx -v)
□ Certbot instalado (certbot --version)
□ Projeto enviado via WinSCP
□ .env criado e configurado
□ docker-compose up -d --build executado
□ init_db.py executado
□ Nginx configurado e reiniciado
□ SSL gerado com Certbot
□ Firewall configurado (UFW)
□ Site acessível via HTTPS
□ Primeiro usuário criado
```

---

**🚀 Com este guia, seu projeto estará no ar em menos de 2 horas!**

