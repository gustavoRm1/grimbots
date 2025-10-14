# ✅ CHECKLIST DE PRODUÇÃO

## 📋 PRÉ-DEPLOY

### Código
- [ ] Código testado localmente
- [ ] Sem erros de lint
- [ ] Logs limpos (sem prints desnecessários)
- [ ] Variáveis sensíveis em `.env`
- [ ] `.gitignore` configurado

### Banco de Dados
- [ ] PostgreSQL configurado
- [ ] Backup automático configurado
- [ ] Migrations aplicadas
- [ ] Dados de teste removidos

### Segurança
- [ ] `SECRET_KEY` gerada (min 32 chars)
- [ ] Senhas complexas (DB, admin)
- [ ] Firewall configurado (UFW)
- [ ] Fail2Ban instalado
- [ ] SSL configurado (Let's Encrypt)

---

## 🚀 DEPLOY

### Servidor
- [ ] VPS Ubuntu 20.04+ com mín 2GB RAM
- [ ] Python 3.11 instalado
- [ ] Node.js 20 instalado
- [ ] Docker + Docker Compose instalado
- [ ] PM2 instalado globalmente

### Aplicação
- [ ] Projeto clonado em `/var/www/bot-manager`
- [ ] Venv criado e dependências instaladas
- [ ] `.env` configurado com credenciais reais
- [ ] Banco inicializado (`init_db.py`)
- [ ] PM2 iniciado (`pm2 start ecosystem.config.js`)
- [ ] PM2 configurado para startup

### Nginx Proxy Manager
- [ ] Container Docker rodando
- [ ] Proxy Host criado
- [ ] SSL Let's Encrypt ativo
- [ ] WebSockets habilitado
- [ ] Porta 81 bloqueada (firewall)

### Integrações
- [ ] SyncPay configurado (Client ID + Secret)
- [ ] Platform Split User ID configurado
- [ ] Webhook configurado na SyncPay
- [ ] Webhook testado

---

## ✅ PÓS-DEPLOY

### Testes Funcionais
- [ ] Login funciona
- [ ] Dashboard carrega
- [ ] Criar bot funciona
- [ ] Configurar bot funciona
- [ ] Iniciar/Parar bot funciona
- [ ] Pagamento de teste funciona
- [ ] Webhook recebe confirmação
- [ ] WebSocket atualiza em tempo real

### Funcionalidades Avançadas
- [ ] Order Bumps funcionando
- [ ] Downsells enviando
- [ ] Remarketing ativo
- [ ] Ranking atualizando
- [ ] Badges desbloqueando
- [ ] Load Balancer redirecionando
- [ ] Pools com health check ativo

### Monitoramento
- [ ] PM2 monit funcionando
- [ ] Logs sendo gerados
- [ ] Backup automático agendado
- [ ] Alertas configurados

---

## 🔧 MANUTENÇÃO

### Diária
- [ ] Verificar logs de erro
- [ ] Monitorar uso de recursos
- [ ] Verificar uptime dos bots

### Semanal
- [ ] Revisar métricas de vendas
- [ ] Verificar pools de redirecionamento
- [ ] Limpar logs antigos
- [ ] Testar backups

### Mensal
- [ ] Atualizar dependências
- [ ] Revisar segurança
- [ ] Backup completo offline
- [ ] Análise de performance

---

## 🆘 CONTATOS EMERGÊNCIA

- **Servidor:** [IP/Hostname do VPS]
- **SSH:** `ssh user@servidor`
- **PM2:** `pm2 logs bot-manager`
- **Logs:** `/var/www/bot-manager/logs/`
- **Backup:** `/root/backups/`

---

**✅ Projeto pronto para produção!** 🚀



