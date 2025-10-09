# ⚡ COMANDOS RÁPIDOS - BOT MANAGER SAAS

## 🚀 DEPLOY (No Servidor)

```bash
# 1. Setup automático (instala tudo)
wget https://raw.githubusercontent.com/gustavoRm1/grimbots/main/setup-production.sh
chmod +x setup-production.sh
sudo bash setup-production.sh

# 2. Clonar projeto
cd /var/www
git clone https://github.com/gustavoRm1/grimbots.git bot-manager
cd bot-manager

# 3. Configurar ambiente
python3.11 -m venv venv
source venv/bin/activate
pip install -r requirements.txt

# 4. Configurar .env
cp env.example .env
nano .env  # Preencher variáveis

# 5. Inicializar banco
python init_db.py

# 6. Iniciar com PM2
bash start-pm2.sh
```

---

## 🔄 PM2 - Gerenciamento

```bash
# Ver processos
pm2 list

# Ver logs ao vivo
pm2 logs bot-manager

# Ver logs (últimas 100 linhas)
pm2 logs bot-manager --lines 100

# Monitoramento em tempo real
pm2 monit

# Reiniciar
pm2 restart bot-manager

# Reload (zero-downtime)
pm2 reload bot-manager

# Parar
pm2 stop bot-manager

# Deletar
pm2 delete bot-manager

# Ver detalhes
pm2 show bot-manager

# Limpar logs
pm2 flush

# Salvar configuração
pm2 save

# Resetar contador de restarts
pm2 reset bot-manager
```

---

## 🐘 POSTGRESQL - Gerenciamento

```bash
# Ver status
docker ps | grep postgres

# Logs
docker logs -f postgres-botmanager

# Conectar ao banco
docker exec -it postgres-botmanager psql -U botmanager -d botmanager_db

# Dentro do psql:
\dt                    # Listar tabelas
\d users               # Descrever tabela users
SELECT * FROM users;   # Query
\q                     # Sair

# Backup
docker exec postgres-botmanager pg_dump -U botmanager botmanager_db > backup.sql

# Restaurar
cat backup.sql | docker exec -i postgres-botmanager psql -U botmanager -d botmanager_db

# Reiniciar
docker restart postgres-botmanager
```

---

## 🌐 NGINX PROXY MANAGER

```bash
# Ver status
docker ps | grep nginx-proxy-manager

# Logs
docker logs -f nginx-proxy-manager

# Reiniciar
cd /opt/nginx-proxy-manager
docker-compose restart

# Parar
docker-compose down

# Iniciar
docker-compose up -d

# Acessar interface
# http://SEU_IP:81
```

---

## 🔥 FIREWALL (UFW)

```bash
# Ver status
ufw status verbose

# Permitir porta
ufw allow 8080/tcp

# Remover regra
ufw delete allow 8080/tcp

# Desabilitar
ufw disable

# Habilitar
ufw enable

# Resetar (CUIDADO!)
ufw reset
```

---

## 🔍 DEBUG E TROUBLESHOOTING

```bash
# Verificar se porta 5000 está escutando
netstat -tlnp | grep 5000
ss -tlnp | grep 5000

# Testar endpoint local
curl http://127.0.0.1:5000

# Testar endpoint externo
curl http://SEU_IP:5000

# Ver processos Python
ps aux | grep python

# Matar todos processos Python
pkill -9 python

# Ver uso de disco
df -h

# Ver uso de memória
free -h

# Ver uso de CPU
htop

# Verificar DNS
nslookup seu-dominio.com.br

# Testar SSL
curl -I https://seu-dominio.com.br

# Ver certificados SSL
ls -la /opt/nginx-proxy-manager/letsencrypt/live/

# Logs do sistema
journalctl -xe
```

---

## 📦 ATUALIZAR PROJETO

```bash
cd /var/www/bot-manager

# 1. Backup
docker exec postgres-botmanager pg_dump -U botmanager botmanager_db > backup_$(date +%Y%m%d_%H%M%S).sql

# 2. Puxar código novo
git pull origin main

# 3. Ativar venv
source venv/bin/activate

# 4. Atualizar dependências (se mudou)
pip install -r requirements.txt --upgrade

# 5. Aplicar migrações (se houver)
# python migrate.py

# 6. Reload PM2 (zero-downtime)
pm2 reload bot-manager

# 7. Verificar logs
pm2 logs bot-manager --lines 50
```

---

## 🔐 SEGURANÇA

```bash
# Gerar SECRET_KEY segura
python3 -c "import secrets; print(secrets.token_urlsafe(32))"

# Ver portas abertas
nmap localhost

# Ver conexões ativas
netstat -an | grep ESTABLISHED

# Bloquear IP específico
ufw deny from IP_ADDRESS

# Ver tentativas de login SSH falhadas
grep "Failed password" /var/log/auth.log

# Instalar Fail2Ban
apt install -y fail2ban
systemctl enable fail2ban
systemctl start fail2ban
```

---

## 💾 BACKUP E RESTORE

```bash
# Backup completo
bash /root/backup-bot-manager.sh

# Backup manual do banco
docker exec postgres-botmanager pg_dump -U botmanager botmanager_db | gzip > backup.sql.gz

# Backup de arquivos
tar -czf backup_files.tar.gz /var/www/bot-manager

# Restore do banco
gunzip < backup.sql.gz | docker exec -i postgres-botmanager psql -U botmanager -d botmanager_db

# Restore de arquivos
tar -xzf backup_files.tar.gz -C /
```

---

## 🧹 LIMPEZA E MANUTENÇÃO

```bash
# Limpar logs antigos do PM2
pm2 flush

# Limpar logs do sistema
journalctl --vacuum-time=7d

# Limpar Docker
docker system prune -a

# Limpar apt cache
apt clean
apt autoclean
apt autoremove

# Ver espaço em disco
du -sh /var/www/bot-manager/*
```

---

## 🆘 COMANDOS DE EMERGÊNCIA

```bash
# Sistema travado - forçar restart do PM2
pm2 kill
pm2 resurrect

# Banco travado - forçar restart
docker restart postgres-botmanager

# Nginx travado - forçar restart
cd /opt/nginx-proxy-manager
docker-compose restart

# Verificar saúde geral
pm2 list
docker ps
ufw status
df -h
free -h
```

---

## 📊 MONITORAMENTO AVANÇADO

```bash
# PM2 Plus (dashboard web)
pm2 link CHAVE_SECRETA CHAVE_PUBLICA

# Instalar ferramentas de monitoramento
apt install -y sysstat iotop nethogs

# Ver I/O de disco
iotop

# Ver uso de rede por processo
nethogs

# Ver estatísticas do sistema
sar -u 1 10  # CPU
sar -r 1 10  # Memória
```

---

**💡 Mantenha este arquivo salvo para consultas rápidas!**

