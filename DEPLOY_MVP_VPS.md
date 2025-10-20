# 🚀 **DEPLOY MVP NA VPS - GUIA COMPLETO**

## 📋 **PRÉ-REQUISITOS NA VPS**

### **O que precisa ter instalado:**
```bash
- Ubuntu 20.04+ (ou Debian)
- Docker
- Docker Compose
- Git
- Acesso SSH root ou sudo
```

---

## 🔧 **PASSO 1: CONECTAR NA VPS**

```bash
# Do seu computador local
ssh usuario@seu_servidor_ip

# Ou se usar chave
ssh -i sua_chave.pem usuario@seu_servidor_ip
```

---

## 📦 **PASSO 2: INSTALAR DEPENDÊNCIAS**

### **2.1. Instalar Docker (se não tiver):**

```bash
# Atualizar sistema
sudo apt update && sudo apt upgrade -y

# Instalar Docker
curl -fsSL https://get.docker.com -o get-docker.sh
sudo sh get-docker.sh

# Adicionar usuário ao grupo docker
sudo usermod -aG docker $USER

# Aplicar mudanças (relogar SSH)
newgrp docker

# Verificar
docker --version
```

### **2.2. Instalar Docker Compose:**

```bash
# Baixar Docker Compose
sudo curl -L "https://github.com/docker/compose/releases/latest/download/docker-compose-$(uname -s)-$(uname -m)" -o /usr/local/bin/docker-compose

# Dar permissão
sudo chmod +x /usr/local/bin/docker-compose

# Verificar
docker-compose --version
```

---

## 📂 **PASSO 3: PREPARAR PROJETO NA VPS**

```bash
# Ir para o diretório do projeto
cd /seu/caminho/grpay

# OU se estiver começando do zero
# git clone seu_repositorio
# cd grpay

# Puxar últimas mudanças
git pull origin main
```

---

## ⚙️ **PASSO 4: CONFIGURAR VARIÁVEIS DE AMBIENTE**

```bash
# Criar arquivo .env
nano .env.mvp
```

**Conteúdo do `.env.mvp`:**
```bash
# Database
DB_PASSWORD=sua_senha_segura_aqui_2024

# Encryption (usar a mesma que já tem)
ENCRYPTION_KEY=sua_chave_existente

# Celery
CELERY_BROKER_URL=redis://redis:6379/0
CELERY_RESULT_BACKEND=redis://redis:6379/1

# Database URL
DATABASE_URL=postgresql://grimbots:sua_senha_segura_aqui_2024@postgres:5432/grimbots

# Redis
REDIS_URL=redis://redis:6379/2

# Flask (se precisar)
FLASK_APP=app.py
FLASK_ENV=production
SECRET_KEY=sua_secret_key_existente
```

**Salvar:** `Ctrl+O`, `Enter`, `Ctrl+X`

---

## 🚀 **PASSO 5: INICIAR SISTEMA MVP**

### **5.1. Build e Start:**

```bash
# Build dos containers (primeira vez)
docker-compose -f docker-compose.mvp.yml build

# Iniciar serviços
docker-compose -f docker-compose.mvp.yml up -d

# Verificar status
docker-compose -f docker-compose.mvp.yml ps
```

**Esperado:**
```
NAME                       STATUS
grimbots_redis            Up
grimbots_postgres         Up
grimbots_celery_worker    Up
grimbots_celery_beat      Up
grimbots_flower           Up
```

### **5.2. Verificar Logs:**

```bash
# Logs de todos os serviços
docker-compose -f docker-compose.mvp.yml logs -f

# Logs apenas do worker
docker-compose -f docker-compose.mvp.yml logs -f celery_worker

# Logs do Redis
docker-compose -f docker-compose.mvp.yml logs -f redis

# Logs do Postgres
docker-compose -f docker-compose.mvp.yml logs -f postgres
```

### **5.3. Verificar Banco de Dados:**

```bash
# Entrar no container do Postgres
docker exec -it grimbots_postgres psql -U grimbots -d grimbots

# Verificar tabelas criadas
\dt

# Deve mostrar:
# event_queue
# event_log
# event_metrics

# Sair
\q
```

---

## 🔍 **PASSO 6: MONITORAMENTO**

### **6.1. Acessar Flower (Celery Monitor):**

```
http://seu_servidor_ip:5555
```

**Se não abrir:**
```bash
# Verificar se porta está aberta no firewall
sudo ufw allow 5555/tcp

# Ou usar SSH tunnel
ssh -L 5555:localhost:5555 usuario@seu_servidor_ip
# Depois acessar: http://localhost:5555
```

### **6.2. Verificar Redis:**

```bash
# Entrar no Redis
docker exec -it grimbots_redis redis-cli

# Ver chaves
KEYS *

# Ver info
INFO

# Sair
exit
```

---

## 🛠️ **COMANDOS ÚTEIS NA VPS**

### **Parar sistema:**
```bash
docker-compose -f docker-compose.mvp.yml stop
```

### **Reiniciar sistema:**
```bash
docker-compose -f docker-compose.mvp.yml restart
```

### **Parar e remover:**
```bash
docker-compose -f docker-compose.mvp.yml down
```

### **Parar e remover TUDO (incluindo volumes):**
```bash
docker-compose -f docker-compose.mvp.yml down -v
# ⚠️ CUIDADO: Apaga dados do banco!
```

### **Ver recursos usados:**
```bash
docker stats
```

### **Limpar containers antigos:**
```bash
docker system prune -a
```

---

## 🔄 **PASSO 7: INTEGRAR COM APLICAÇÃO EXISTENTE**

### **7.1. Atualizar Flask App:**

O Flask app vai continuar rodando como antes, MAS agora:
- Em vez de enviar eventos síncronos
- Vai enfileirar eventos no Redis
- Celery processa em background

### **7.2. Manter ambos rodando:**

```bash
# Sistema antigo (Flask)
pm2 list
# OU
sudo systemctl status grimbots

# Sistema novo (MVP Async)
docker-compose -f docker-compose.mvp.yml ps
```

### **7.3. Não precisa parar o atual:**

O MVP roda em **paralelo** ao sistema existente:
- Flask: Porta 5000 (ou sua porta)
- MVP: Containers isolados
- Redis: Porta 6379 (interna)
- Postgres MVP: Porta 5432 (interna, separado do SQLite)

---

## 📊 **PASSO 8: VALIDAR FUNCIONAMENTO**

### **8.1. Teste rápido:**

```bash
# Entrar no worker
docker exec -it grimbots_celery_worker bash

# Testar importação
python -c "from celery_app import celery_app; print('OK')"

# Sair
exit
```

### **8.2. Ver fila:**

```bash
# Redis CLI
docker exec -it grimbots_redis redis-cli

# Ver tamanho da fila
LLEN celery

# Ver tasks
KEYS celery*

# Sair
exit
```

---

## ⚠️ **TROUBLESHOOTING**

### **Problema: Container não inicia**

```bash
# Ver logs detalhados
docker-compose -f docker-compose.mvp.yml logs celery_worker

# Ver erro específico
docker logs grimbots_celery_worker
```

### **Problema: Erro de conexão com banco**

```bash
# Verificar se Postgres está rodando
docker-compose -f docker-compose.mvp.yml ps postgres

# Verificar logs do Postgres
docker-compose -f docker-compose.mvp.yml logs postgres

# Testar conexão
docker exec -it grimbots_postgres psql -U grimbots -d grimbots -c "SELECT 1;"
```

### **Problema: Redis não conecta**

```bash
# Verificar Redis
docker-compose -f docker-compose.mvp.yml ps redis

# Testar ping
docker exec -it grimbots_redis redis-cli ping
# Deve retornar: PONG
```

### **Problema: Porta já em uso**

```bash
# Ver o que está usando a porta
sudo lsof -i :6379  # Redis
sudo lsof -i :5432  # Postgres
sudo lsof -i :5555  # Flower

# Matar processo
sudo kill -9 PID
```

---

## 🔐 **SEGURANÇA NA VPS**

### **Firewall:**

```bash
# Permitir apenas portas necessárias
sudo ufw allow 22/tcp      # SSH
sudo ufw allow 80/tcp      # HTTP
sudo ufw allow 443/tcp     # HTTPS
sudo ufw allow 5000/tcp    # Flask (se exposto)

# Flower (opcional, apenas para admin)
sudo ufw allow from SEU_IP to any port 5555

# Ativar firewall
sudo ufw enable
```

### **Senhas:**

```bash
# SEMPRE usar senhas fortes no .env.mvp
# NUNCA commitar .env no git
# Adicionar ao .gitignore
echo ".env.mvp" >> .gitignore
```

---

## 📈 **MONITORAMENTO DE RECURSOS**

```bash
# CPU e Memória dos containers
docker stats

# Espaço em disco
df -h

# Ver logs de tamanho
du -sh /var/lib/docker/
```

---

## 🔄 **ATUALIZAR MVP (quando tiver novas versões)**

```bash
# 1. Ir para o projeto
cd /seu/caminho/grpay

# 2. Puxar mudanças
git pull origin main

# 3. Rebuild (se mudou Dockerfile)
docker-compose -f docker-compose.mvp.yml build

# 4. Restart
docker-compose -f docker-compose.mvp.yml restart

# 5. Ver logs
docker-compose -f docker-compose.mvp.yml logs -f
```

---

## ✅ **CHECKLIST FINAL**

- [ ] Docker instalado
- [ ] Docker Compose instalado
- [ ] Arquivo `.env.mvp` configurado
- [ ] Containers iniciados
- [ ] Tabelas criadas no banco
- [ ] Flower acessível
- [ ] Logs sem erros críticos
- [ ] Redis respondendo
- [ ] Postgres acessível
- [ ] Workers processando

---

## 🚀 **PRÓXIMOS PASSOS**

Depois que o MVP estiver rodando na VPS:

1. **DIA 2:** Criar tasks de envio
2. **DIA 3:** Integrar com Flask app
3. **DIA 4:** Testes E2E
4. **DIA 5:** Testes de carga
5. **DIA 6-7:** Documentação e entrega

---

## 💪 **SUPORTE**

Se der erro:

1. **Ver logs:** `docker-compose -f docker-compose.mvp.yml logs -f`
2. **Verificar .env.mvp:** Senhas corretas?
3. **Verificar portas:** Alguma já em uso?
4. **Verificar recursos:** `docker stats` - tem memória suficiente?

---

*Deploy para VPS - QI 540* 🚀
*Produção-Ready*
*Zero Downtime*

