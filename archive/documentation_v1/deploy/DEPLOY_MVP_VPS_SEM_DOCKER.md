# 🚀 **MVP META PIXEL - DEPLOY NA VPS (SEM DOCKER)**

## ✅ **SETUP REAL DA SUA VPS**

```
Atual:
- Python3 + venv
- Gunicorn (eventlet)
- SQLite (instance/saas_bot_manager.db)
- systemd OU supervisord para gerenciar
- Nginx como proxy

MVP vai adicionar:
- Redis (instalado no sistema)
- Celery workers (rodando com systemd)
- Mesma estrutura de pastas
```

---

## 📋 **PASSO 1: INSTALAR REDIS**

```bash
# Conectar na VPS
ssh usuario@seu_servidor

# Instalar Redis
sudo apt update
sudo apt install redis-server -y

# Configurar Redis para iniciar com sistema
sudo systemctl enable redis-server
sudo systemctl start redis-server

# Testar
redis-cli ping
# Deve retornar: PONG
```

---

## 📦 **PASSO 2: ATUALIZAR REQUIREMENTS**

```bash
# No projeto local, adicionar ao requirements.txt
cd /caminho/local/grpay

# Editar requirements.txt
nano requirements.txt
```

**Adicionar estas linhas:**
```txt
# Celery e dependências
celery[redis]==5.3.4
redis==5.0.1
kombu==5.3.4
```

**Salvar e commitar:**
```bash
git add requirements.txt
git commit -m "feat: add celery dependencies for MVP async"
git push origin main
```

---

## 🚀 **PASSO 3: ATUALIZAR CÓDIGO NA VPS**

```bash
# Na VPS
cd ~/grimbots-app  # ou seu caminho

# Puxar mudanças
git pull origin main

# Ativar venv
source venv/bin/activate

# Instalar novas dependências
pip install -r requirements.txt
```

---

## 📂 **PASSO 4: CRIAR ESTRUTURA MVP**

```bash
# Ainda na VPS, no diretório do projeto
mkdir -p tasks
mkdir -p logs

# Criar arquivos vazios (vamos preencher depois)
touch celery_app.py
touch tasks/__init__.py
touch tasks/meta_sender.py
```

---

## ⚙️ **PASSO 5: CONFIGURAR CELERY COM SYSTEMD**

### **5.1. Criar serviço Celery Worker:**

```bash
sudo nano /etc/systemd/system/grimbots-celery.service
```

**Conteúdo:**
```ini
[Unit]
Description=GrimBots Celery Worker
After=network.target redis-server.service

[Service]
Type=forking
User=seu_usuario
Group=seu_usuario
WorkingDirectory=/home/seu_usuario/grimbots-app
Environment="PATH=/home/seu_usuario/grimbots-app/venv/bin"
Environment="CELERY_BROKER_URL=redis://localhost:6379/0"
Environment="DATABASE_URL=sqlite:////home/seu_usuario/grimbots-app/instance/saas_bot_manager.db"

ExecStart=/home/seu_usuario/grimbots-app/venv/bin/celery \
    -A celery_app worker \
    --loglevel=info \
    --concurrency=4 \
    --logfile=/home/seu_usuario/grimbots-app/logs/celery-worker.log \
    --pidfile=/var/run/celery/worker.pid \
    --detach

ExecStop=/home/seu_usuario/grimbots-app/venv/bin/celery \
    -A celery_app control shutdown

Restart=always
RestartSec=10s

[Install]
WantedBy=multi-user.target
```

### **5.2. Criar serviço Celery Beat:**

```bash
sudo nano /etc/systemd/system/grimbots-celery-beat.service
```

**Conteúdo:**
```ini
[Unit]
Description=GrimBots Celery Beat
After=network.target redis-server.service grimbots-celery.service

[Service]
Type=forking
User=seu_usuario
Group=seu_usuario
WorkingDirectory=/home/seu_usuario/grimbots-app
Environment="PATH=/home/seu_usuario/grimbots-app/venv/bin"
Environment="CELERY_BROKER_URL=redis://localhost:6379/0"

ExecStart=/home/seu_usuario/grimbots-app/venv/bin/celery \
    -A celery_app beat \
    --loglevel=info \
    --logfile=/home/seu_usuario/grimbots-app/logs/celery-beat.log \
    --pidfile=/var/run/celery/beat.pid \
    --detach

ExecStop=/home/seu_usuario/grimbots-app/venv/bin/celery \
    -A celery_app control shutdown

Restart=always
RestartSec=10s

[Install]
WantedBy=multi-user.target
```

### **5.3. Criar diretório PID:**

```bash
sudo mkdir -p /var/run/celery
sudo chown seu_usuario:seu_usuario /var/run/celery
```

### **5.4. Recarregar e iniciar:**

```bash
# Recarregar systemd
sudo systemctl daemon-reload

# Habilitar para iniciar com sistema
sudo systemctl enable grimbots-celery
sudo systemctl enable grimbots-celery-beat

# Iniciar serviços
sudo systemctl start grimbots-celery
sudo systemctl start grimbots-celery-beat

# Verificar status
sudo systemctl status grimbots-celery
sudo systemctl status grimbots-celery-beat
```

---

## 📊 **PASSO 6: VERIFICAR FUNCIONAMENTO**

### **6.1. Ver logs:**

```bash
# Logs do worker
tail -f ~/grimbots-app/logs/celery-worker.log

# Logs do beat
tail -f ~/grimbots-app/logs/celery-beat.log
```

### **6.2. Testar Redis:**

```bash
redis-cli

# Dentro do Redis
KEYS *
INFO
exit
```

### **6.3. Ver processos:**

```bash
ps aux | grep celery
```

---

## 🔄 **PASSO 7: REINICIAR SERVIÇOS**

```bash
# Reiniciar Celery
sudo systemctl restart grimbots-celery
sudo systemctl restart grimbots-celery-beat

# Reiniciar Flask app (se tiver)
sudo systemctl restart grimbots
# OU se não tiver systemd
cd ~/grimbots-app
source venv/bin/activate
pkill -f gunicorn
gunicorn --worker-class eventlet -w 1 --bind 127.0.0.1:5000 wsgi:app &
```

---

## 🛠️ **COMANDOS ÚTEIS**

### **Ver status:**
```bash
sudo systemctl status grimbots-celery
sudo systemctl status grimbots-celery-beat
sudo systemctl status redis-server
```

### **Ver logs:**
```bash
tail -f ~/grimbots-app/logs/celery-worker.log
tail -f ~/grimbots-app/logs/celery-beat.log
sudo journalctl -u grimbots-celery -f
```

### **Reiniciar:**
```bash
sudo systemctl restart grimbots-celery
sudo systemctl restart grimbots-celery-beat
```

### **Parar:**
```bash
sudo systemctl stop grimbots-celery
sudo systemctl stop grimbots-celery-beat
```

---

## ⚠️ **TROUBLESHOOTING**

### **Erro: Celery não inicia**

```bash
# Ver logs detalhados
sudo journalctl -u grimbots-celery -n 50

# Testar manualmente
cd ~/grimbots-app
source venv/bin/activate
celery -A celery_app worker --loglevel=debug
```

### **Erro: Redis connection refused**

```bash
# Verificar se Redis está rodando
sudo systemctl status redis-server

# Reiniciar Redis
sudo systemctl restart redis-server

# Testar conexão
redis-cli ping
```

### **Erro: Permission denied no PID**

```bash
# Criar e dar permissão
sudo mkdir -p /var/run/celery
sudo chown seu_usuario:seu_usuario /var/run/celery
```

---

## 📈 **MONITORAMENTO**

### **Ver filas:**
```bash
cd ~/grimbots-app
source venv/bin/activate

# Ver tasks ativas
celery -A celery_app inspect active

# Ver tasks agendadas
celery -A celery_app inspect scheduled

# Ver workers
celery -A celery_app inspect stats
```

### **Flower (UI de monitoramento - opcional):**
```bash
# Instalar
pip install flower

# Iniciar
celery -A celery_app flower --port=5555

# Acessar
http://seu_servidor_ip:5555
```

---

## 🔐 **SEGURANÇA**

### **Firewall:**
```bash
# Se usar Flower, liberar apenas para seu IP
sudo ufw allow from SEU_IP to any port 5555
```

### **Redis:**
```bash
# Editar config do Redis
sudo nano /etc/redis/redis.conf

# Procurar e ajustar:
bind 127.0.0.1  # Apenas local
protected-mode yes  # Proteção ativa

# Reiniciar
sudo systemctl restart redis-server
```

---

## 📦 **ESTRUTURA FINAL NA VPS**

```
~/grimbots-app/
├── venv/                  # Ambiente virtual
├── instance/              # Banco SQLite
├── logs/                  # Logs
│   ├── celery-worker.log
│   ├── celery-beat.log
│   └── access.log
├── tasks/                 # Tasks Celery
│   ├── __init__.py
│   ├── meta_sender.py
│   ├── metrics.py
│   └── health.py
├── celery_app.py          # Config Celery
├── app.py                 # Flask app
├── wsgi.py                # Entry point
└── requirements.txt       # Dependências
```

---

## ✅ **CHECKLIST**

- [ ] Redis instalado e rodando
- [ ] requirements.txt atualizado
- [ ] Código atualizado (git pull)
- [ ] Dependências instaladas (pip install)
- [ ] celery_app.py criado
- [ ] tasks/ criados
- [ ] Serviços systemd criados
- [ ] Serviços iniciados
- [ ] Logs sem erros
- [ ] Redis respondendo
- [ ] Workers processando

---

## 💪 **PRÓXIMOS PASSOS**

Depois que Celery estiver rodando:

1. **DIA 2:** Criar tasks de envio (`tasks/meta_sender.py`)
2. **DIA 3:** Integrar Flask app para enfileirar eventos
3. **DIA 4:** Testes E2E
4. **DIA 5:** Testes de carga
5. **DIA 6-7:** Documentação

---

*Deploy sem Docker - QI 540* 🚀
*Compatível com setup atual*
*Zero downtime*

