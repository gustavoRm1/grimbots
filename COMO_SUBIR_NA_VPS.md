# 🚀 COMO SUBIR NA VPS - GUIA RÁPIDO

**Versão:** 2.1.0  
**Tempo Estimado:** 15-20 minutos

---

## ⚡ COMANDOS RÁPIDOS

### Na VPS (copie e cole)

```bash
# 1. Preparar sistema
sudo apt update && sudo apt upgrade -y
sudo apt install -y python3.11 python3-pip git nginx postgresql

# 2. Criar usuário
sudo adduser grimbots
sudo usermod -aG sudo grimbots
su - grimbots

# 3. Clonar projeto
cd ~
git clone <SEU-REPOSITORIO-GIT> grimbots
cd grimbots

# 4. Configurar ambiente
cp env.example .env
nano .env
# Editar: SECRET_KEY, ENCRYPTION_KEY, DATABASE_URL, ALLOWED_ORIGINS, WEBHOOK_URL

# 5. Deploy automatizado
bash deploy_quick.sh

# 6. Configurar PostgreSQL
sudo -u postgres psql
CREATE DATABASE grimbots_db;
CREATE USER grimbots WITH PASSWORD 'senha_forte';
GRANT ALL PRIVILEGES ON DATABASE grimbots_db TO grimbots;
\q

# 7. Atualizar DATABASE_URL no .env
nano .env
# DATABASE_URL=postgresql://grimbots:senha_forte@localhost/grimbots_db

# 8. Inicializar
python init_db.py
cat .admin_password  # Anotar senha

# 9. Configurar Systemd
sudo nano /etc/systemd/system/grimbots.service
# Colar conteúdo de DEPLOY_VPS_v2.1.0.md

sudo systemctl daemon-reload
sudo systemctl enable grimbots
sudo systemctl start grimbots
sudo systemctl status grimbots

# 10. Configurar Nginx
sudo nano /etc/nginx/sites-available/grimbots
# Colar conteúdo de DEPLOY_VPS_v2.1.0.md
# Substituir "seudominio.com" pelo domínio real

sudo ln -s /etc/nginx/sites-available/grimbots /etc/nginx/sites-enabled/
sudo nginx -t
sudo systemctl reload nginx

# 11. SSL (HTTPS)
sudo apt install certbot python3-certbot-nginx -y
sudo certbot --nginx -d seudominio.com -d www.seudominio.com

# PRONTO!
```

---

## 🔑 GERAR KEYS (Antes de Editar .env)

```bash
# SECRET_KEY
python3 -c "import secrets; print('SECRET_KEY=' + secrets.token_hex(32))"

# ENCRYPTION_KEY
python3 -c "from cryptography.fernet import Fernet; print('ENCRYPTION_KEY=' + Fernet.generate_key().decode())"
```

Copiar outputs para .env

---

## ✅ TESTAR APÓS DEPLOY

```bash
# 1. Verificar serviço
sudo systemctl status grimbots

# 2. Ver logs
tail -f logs/error.log

# 3. Testar site
curl https://seudominio.com

# 4. Acessar navegador
https://seudominio.com
Login: admin@grimbots.com
Senha: <ver .admin_password>
```

---

## 🐛 SE DER ERRO

```bash
# Ver logs
sudo journalctl -u grimbots -n 100

# Reiniciar
sudo systemctl restart grimbots

# Verificar portas
sudo lsof -ti:5000

# Matar processo (se necessário)
sudo lsof -ti:5000 | xargs sudo kill -9
sudo systemctl start grimbots
```

---

## 📋 ARQUIVOS QUE VOCÊ PRECISA

**Guias Completos:**
- `DEPLOY_VPS_v2.1.0.md` - Passo a passo detalhado
- `CHECKLIST_DEPLOY_VPS.md` - Checklist completo
- `CHANGELOG_v2.1.0.md` - O que mudou nesta versão

**Documentação:**
- `docs/DOCUMENTACAO_COMPLETA.md` - Guia técnico
- `docs/GATEWAYS_README.md` - 5 gateways
- `docs/wiinpay.md` - WiinPay específico

---

## 🎯 VERSÃO v2.1.0 INCLUI

- ✅ Sistema de Upsell (backend + frontend)
- ✅ Gateway WiinPay (5º gateway)
- ✅ Split ID configurado: `6877edeba3c39f8451ba5bdd`
- ✅ 10 race conditions corrigidos
- ✅ Segurança OWASP Top 10
- ✅ Thread-safety 100%
- ✅ 0 bugs conhecidos

---

**TUDO PRONTO PARA SUBIR! 🚀**

