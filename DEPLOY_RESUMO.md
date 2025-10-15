# 🚀 DEPLOY VPS - COMANDOS ESSENCIAIS

## 📋 **CHECKLIST PRÉ-DEPLOY**

- [ ] VPS Ubuntu 20.04+ contratada
- [ ] IP da VPS anotado
- [ ] Domínio registrado (opcional mas recomendado)
- [ ] Acesso SSH funcionando
- [ ] Projeto funcionando localmente

---

## ⚡ **OPÇÃO 1: DEPLOY AUTOMATIZADO (Mais Rápido)**

### Do seu PC (Windows):

```bash
# Tornar script executável (Git Bash)
chmod +x deploy_to_vps.sh

# Fazer deploy
./deploy_to_vps.sh grimbots@SEU_IP_VPS
```

### Na VPS (via SSH):

```bash
# Conectar
ssh grimbots@SEU_IP_VPS

# Gerar SECRET_KEY
python3 -c "import secrets; print(secrets.token_hex(32))"

# Configurar .env
cd ~/grimbots-app
nano .env
# Colar SECRET_KEY gerada acima

# Seguir guia completo
cat DEPLOY_VPS.md
```

---

## 🔧 **OPÇÃO 2: PASSO A PASSO MANUAL**

### 1. Preparar VPS

```bash
# Conectar
ssh root@SEU_IP_VPS

# Atualizar
apt update && apt upgrade -y

# Instalar dependências
apt install -y python3 python3-pip python3-venv nginx certbot python3-certbot-nginx git ufw

# Criar usuário
adduser grimbots
usermod -aG sudo grimbots
su - grimbots
```

### 2. Configurar Projeto

```bash
cd /home/grimbots

# Upload do projeto (use SCP/FTP ou Git)
# Exemplo: fazer upload para /home/grimbots/grimbots-app

# Criar ambiente virtual
cd grimbots-app
python3 -m venv venv
source venv/bin/activate

# Instalar
pip install --upgrade pip
pip install -r requirements.txt
pip install gunicorn

# Configurar .env
python3 -c "import secrets; print(secrets.token_hex(32))"  # Copiar resultado
nano .env
# Adicionar SECRET_KEY=resultado_acima

# Inicializar
python3 init_db.py
```

### 3. Configurar Nginx

```bash
sudo nano /etc/nginx/sites-available/grimbots
```

Colar configuração do arquivo `DEPLOY_VPS.md` (seção PASSO 4)

```bash
sudo ln -s /etc/nginx/sites-available/grimbots /etc/nginx/sites-enabled/
sudo rm /etc/nginx/sites-enabled/default
sudo nginx -t
sudo systemctl restart nginx
```

### 4. Configurar Systemd

```bash
sudo nano /etc/systemd/system/grimbots.service
```

Colar configuração do arquivo `DEPLOY_VPS.md` (seção PASSO 6)

```bash
sudo mkdir -p /var/log/grimbots
sudo chown grimbots:grimbots /var/log/grimbots
sudo systemctl daemon-reload
sudo systemctl enable grimbots
sudo systemctl start grimbots
sudo systemctl status grimbots
```

### 5. Configurar SSL (HTTPS)

```bash
# Certifique-se que o DNS está apontando para o IP da VPS!
sudo certbot --nginx -d seudominio.com -d www.seudominio.com
```

### 6. Configurar Firewall

```bash
sudo ufw enable
sudo ufw allow 22/tcp
sudo ufw allow 80/tcp
sudo ufw allow 443/tcp
sudo ufw status
```

---

## 🎯 **COMANDOS ÚTEIS PÓS-DEPLOY**

```bash
# Ver status
sudo systemctl status grimbots

# Ver logs em tempo real
sudo journalctl -u grimbots -f

# Reiniciar aplicação
sudo systemctl restart grimbots

# Fazer backup
cp instance/saas_bot_manager.db instance/backup_$(date +%Y%m%d).db

# Atualizar aplicação (após git pull ou upload)
cd /home/grimbots/grimbots-app
source venv/bin/activate
pip install -r requirements.txt --upgrade
sudo systemctl restart grimbots
```

---

## 🔐 **CONFIGURAR DNS**

No painel do seu domínio (Registro.br, Cloudflare, GoDaddy, etc.):

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

Aguarde propagação (15min a 24h) e teste:
```bash
ping seudominio.com
```

---

## 🆘 **TROUBLESHOOTING RÁPIDO**

### Aplicação não inicia:
```bash
sudo journalctl -u grimbots -n 50 --no-pager
```

### Nginx retorna 502:
```bash
sudo systemctl status grimbots
sudo systemctl restart grimbots nginx
```

### Banco de dados corrompido:
```bash
cd /home/grimbots/grimbots-app/instance
cp saas_bot_manager.db saas_bot_manager.db.corrupted
cp backup_YYYYMMDD.db saas_bot_manager.db
sudo systemctl restart grimbots
```

### Ver uso de recursos:
```bash
htop
df -h
free -h
```

---

## ✅ **VERIFICAÇÃO FINAL**

Acesse no navegador:
- `http://SEU_IP_VPS` → Deve carregar
- `https://seudominio.com` → Deve carregar com cadeado verde
- Fazer login
- Criar bot de teste
- Processar venda teste

---

## 📚 **DOCUMENTAÇÃO COMPLETA**

Para guia detalhado com explicações completas, veja:
```bash
cat DEPLOY_VPS.md
```

---

## ⏱️ **TEMPO ESTIMADO**

- **Deploy automatizado:** ~30 minutos
- **Deploy manual:** ~60 minutos
- **Configuração SSL:** ~5 minutos
- **DNS propagação:** 15min a 24h

---

**✨ Pronto! Sua aplicação está em produção!** 🚀

