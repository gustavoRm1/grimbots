# 🚀 META PIXEL V2.0 - DEPLOY COMPLETO (QI 300)

## 📋 RESUMO DA REFATORAÇÃO

### **✅ ANTES (Pixel por Bot) - ERRADO**
```
Bot A (Pixel 123) ──┐
Bot B (Pixel 456) ──┼──> Pool "ads" ──> Link /go/ads
Bot C (Pixel 789) ──┘
```
**Problemas:**
- Dados fragmentados em 3 pixels diferentes
- Se bot cai, tracking para
- Configuração complexa (N bots)

### **✅ DEPOIS (Pixel por Pool) - CORRETO**
```
Bot A (sem pixel) ──┐
Bot B (sem pixel) ──┼──> Pool "ads" (Pixel 123) ──> Link /go/ads
Bot C (sem pixel) ──┘
```
**Vantagens:**
- Dados consolidados em 1 pixel
- Bot cai, pool continua tracking
- Configuração simples (1 vez)

---

## 🔧 ARQUIVOS MODIFICADOS

### **1. `models.py`**
- ✅ Adicionado campos Meta Pixel em `RedirectPool`
- ✅ Comentado campos Meta Pixel em `Bot` (deprecated)

### **2. `app.py`**
- ✅ `send_meta_pixel_pageview_event(pool, request)` - Recebe pool ao invés de bot
- ✅ `send_meta_pixel_purchase_event(payment)` - Busca pool do bot
- ✅ `public_redirect()` - Envia pool para PageView
- ✅ Novas rotas API:
  - `/api/redirect-pools/<pool_id>/meta-pixel` (GET/PUT)
  - `/api/redirect-pools/<pool_id>/meta-pixel/test` (POST)
- ✅ Rotas antigas de bot deprecadas (mantidas para retrocompatibilidade)

### **3. `bot_manager.py`**
- ✅ `send_meta_pixel_viewcontent_event(bot, bot_user, message)` - Busca pool do bot

### **4. `utils/meta_pixel.py`**
- ✅ Adicionado comentário explicando arquitetura V2.0
- ✅ Funções já eram genéricas (sem mudanças necessárias)

### **5. `migrate_meta_pixel_to_pools.py`** ⭐ NOVO
- ✅ Script de migração completo
- ✅ Adiciona campos Meta Pixel em `redirect_pools`
- ✅ Migra configurações existentes de bots para pools
- ✅ Cria índices para performance

---

## 📦 DEPLOY NA VPS - PASSO A PASSO

### **PASSO 1: BACKUP OBRIGATÓRIO**

```bash
# Conectar na VPS
ssh root@seu-ip

# Navegar para o projeto
cd /root/grimbots  # ou seu caminho

# Criar backup do banco
cp instance/saas_bot_manager.db instance/saas_bot_manager.db.backup_meta_pool_$(date +%Y%m%d_%H%M%S)

# Verificar backup
ls -lh instance/*.backup*
```

### **PASSO 2: ATUALIZAR CÓDIGO**

```bash
# Puxar código atualizado do Git
git pull origin main

# Verificar arquivos novos
ls -la migrate_meta_pixel_to_pools.py

# Ativar ambiente virtual
source venv/bin/activate
```

### **PASSO 3: PARAR APLICAÇÃO**

```bash
# Parar serviço (escolha o método usado)
sudo systemctl stop grimbots

# OU se usar PM2
# pm2 stop grimbots

# OU se usar Docker
# docker-compose stop
```

### **PASSO 4: EXECUTAR MIGRAÇÃO**

```bash
# Executar script de migração
python migrate_meta_pixel_to_pools.py

# Confirmar com 'sim' quando solicitado
```

**Saída esperada:**
```
==============================================================================
  🚀 INICIANDO MIGRAÇÃO: META PIXEL PARA POOLS
==============================================================================

[1] Criando backup de segurança...
✅ Backup criado: instance/saas_bot_manager.db.backup_meta_pool_20251020_150000

[2] Conectando ao banco: instance/saas_bot_manager.db
✅ Banco conectado: instance/saas_bot_manager.db

[3] Adicionando campos Meta Pixel em 'redirect_pools'...
  ✅ Adicionada coluna: meta_pixel_id
  ✅ Adicionada coluna: meta_access_token
  ✅ Adicionada coluna: meta_tracking_enabled
  ...
✅ Campos Meta Pixel adicionados em 'redirect_pools'

[4] Migrando configurações existentes de 'bots' para 'redirect_pools'...
  ⚠️  Encontrados X bots com Meta Pixel configurado
  ✅ Bot 1 → Pool 1 migrado
  ✅ Bot 2 → Pool 2 migrado
✅ Configurações migradas com sucesso

[5] Removendo campos Meta Pixel de 'bots'...
  ⚠️  SQLite não suporta DROP COLUMN diretamente
  ⚠️  As colunas antigas em 'bots' permanecerão (serão ignoradas)

[6] Criando índices para otimização...
  ✅ Índice criado: idx_pools_meta_tracking
  ✅ Índice criado: idx_pools_meta_pixel

[7] Validando migração...
✅ Validação concluída - todas as colunas foram criadas

==============================================================================
  ✅ MIGRAÇÃO CONCLUÍDA COM SUCESSO!
==============================================================================

📋 RESUMO DA MIGRAÇÃO:
  • Backup criado: instance/saas_bot_manager.db.backup_meta_pool_20251020_150000
  • Colunas adicionadas em redirect_pools: 10
  • Pools com Meta Pixel: X
  • Índices criados: 2
```

### **PASSO 5: REINICIAR APLICAÇÃO**

```bash
# Iniciar serviço
sudo systemctl start grimbots

# Verificar status
sudo systemctl status grimbots

# Monitorar logs
sudo journalctl -u grimbots -f
```

**Logs esperados (SEM ERROS):**
```
INFO - ✅ Gamificação V2.0 carregada
INFO - ✅ SECRET_KEY validada (forte e única)
INFO - ✅ CORS configurado
INFO - ✅ CSRF Protection ativada
INFO - ✅ Rate Limiting configurado
INFO - BotManager inicializado
INFO - Banco de dados inicializado
INFO - 🔄 INICIANDO REINICIALIZAÇÃO AUTOMÁTICA DOS BOTS...
INFO - ✅ Bots iniciados com sucesso
============================================================
BOT MANAGER SAAS - SERVIDOR INICIADO
============================================================
```

### **PASSO 6: VERIFICAR FUNCIONAMENTO**

```bash
# Testar se API está respondendo
curl http://localhost:5000/api/redirect-pools

# Verificar banco de dados
sqlite3 instance/saas_bot_manager.db
> PRAGMA table_info(redirect_pools);
> SELECT meta_pixel_id, meta_tracking_enabled FROM redirect_pools;
> .quit
```

---

## ⚙️ CONFIGURAÇÃO APÓS DEPLOY

### **1. Acessar Painel Web**

1. Navegue para: `https://seudominio.com/redirect-pools`
2. Clique em um pool existente
3. Procure a seção **"Meta Pixel Configuration"**

### **2. Configurar Meta Pixel no Pool**

**Campos disponíveis:**
```
✅ Pixel ID: 123456789012345
✅ Access Token: EAABwzLixnjYBO... (criptografado)
✅ Ativar Meta Pixel Tracking
✅ Eventos:
   ☑ PageView (acesso ao link)
   ☑ ViewContent (iniciar conversa)
   ☑ Purchase (compra confirmada)
✅ Cloaker + AntiClone:
   ☑ Ativar proteção
   Parâmetro: apx = ohx9lury
```

### **3. Testar Conexão**

1. Clique em **"Testar Conexão"**
2. Aguarde validação
3. Se sucesso, clique em **"Salvar Configuração"**

### **4. Criar Link de Campanha**

```
URL no Meta Ads:
https://seudominio.com/go/seu-pool

Parâmetros de URL (com Cloaker):
apx=ohx9lury&utm_source=facebook&utm_campaign=teste
```

---

## 🧪 TESTE COMPLETO

### **TESTE 1: PageView**
```bash
# Acessar link do pool
curl "https://seudominio.com/go/seu-pool?utm_source=facebook"

# Verificar logs
sudo journalctl -u grimbots | grep "Meta PageView"

# Saída esperada:
# INFO - 📊 Preparando envio Meta PageView: Pool 1 (Meta Ads Campaign)
# INFO - ✅ Meta PageView confirmado: Pool 1 (Meta Ads Campaign) | Event ID: pageview_click_xxx
```

### **TESTE 2: ViewContent**
```bash
# Enviar /start para bot do pool
# Verificar logs
sudo journalctl -u grimbots | grep "Meta ViewContent"

# Saída esperada:
# INFO - 📊 Preparando envio Meta ViewContent: Pool Meta Ads Campaign | User 123456789
# INFO - ✅ Meta ViewContent confirmado: Pool Meta Ads Campaign | User 123456789 | Event ID: viewcontent_1_123456789
```

### **TESTE 3: Purchase**
```bash
# Simular pagamento no painel
# Verificar logs
sudo journalctl -u grimbots | grep "Meta Purchase"

# Saída esperada:
# INFO - 📊 Preparando envio Meta Purchase: PAY_XXX | Pool: Meta Ads Campaign
# INFO - ✅ Meta Purchase confirmado: R$ 97.00 | Pool: Meta Ads Campaign | Event ID: purchase_PAY_XXX
```

### **TESTE 4: Meta Events Manager**
1. Acesse: Meta Business Manager → Gerenciador de Eventos
2. Selecione seu Pixel
3. Vá em "Testar Eventos"
4. Verifique:
   - ✅ PageView aparecendo
   - ✅ ViewContent aparecendo
   - ✅ Purchase aparecendo com valor correto

---

## 🚨 TROUBLESHOOTING

### **Problema: Migração falha com erro de permissão**
```bash
# Solução: Executar como root
sudo python migrate_meta_pixel_to_pools.py
```

### **Problema: Aplicação não inicia após migração**
```bash
# Verificar logs
sudo journalctl -u grimbots -n 100

# Se erro relacionado a models.py:
# Verificar se código foi atualizado corretamente
git status
git diff models.py

# Restaurar backup se necessário
sudo systemctl stop grimbots
cp instance/saas_bot_manager.db.backup_meta_pool_XXXXXX instance/saas_bot_manager.db
sudo systemctl start grimbots
```

### **Problema: Eventos não aparecem no Meta**
```bash
# 1. Verificar se pool tem pixel configurado
sqlite3 instance/saas_bot_manager.db
> SELECT id, name, meta_pixel_id, meta_tracking_enabled FROM redirect_pools;
> .quit

# 2. Verificar logs de erro
sudo journalctl -u grimbots | grep -E "(Meta|ERROR)"

# 3. Testar conexão manualmente
# Acessar painel → Pool → Meta Pixel → Testar Conexão
```

### **Problema: Bot não está em nenhum pool**
```bash
# Verificar associações
sqlite3 instance/saas_bot_manager.db
> SELECT bot_id, pool_id FROM pool_bots;
> .quit

# Se bot não está em pool:
# 1. Acessar painel web
# 2. Ir em Redirecionadores
# 3. Editar pool
# 4. Adicionar bot ao pool
```

---

## 📊 VERIFICAÇÃO DE SUCESSO

### **✅ CHECKLIST FINAL**

- [ ] Backup do banco criado
- [ ] Código atualizado da main
- [ ] Migração executada com sucesso
- [ ] Aplicação reiniciada sem erros
- [ ] Logs não mostram "no such column"
- [ ] Pool tem Meta Pixel configurado
- [ ] Teste de conexão passou
- [ ] PageView aparece no Meta Events Manager
- [ ] ViewContent aparece no Meta Events Manager
- [ ] Purchase aparece com valor correto

### **📈 MÉTRICAS DE VALIDAÇÃO**

```sql
-- Total de pools com pixel configurado
SELECT COUNT(*) FROM redirect_pools WHERE meta_tracking_enabled = 1;

-- Eventos PageView enviados (últimas 24h)
SELECT COUNT(*) FROM bot_users 
WHERE meta_pageview_sent = 1 
AND meta_pageview_sent_at > datetime('now', '-1 day');

-- Eventos ViewContent enviados (últimas 24h)
SELECT COUNT(*) FROM bot_users 
WHERE meta_viewcontent_sent = 1 
AND meta_viewcontent_sent_at > datetime('now', '-1 day');

-- Eventos Purchase enviados (últimas 24h)
SELECT COUNT(*), SUM(amount) FROM payments 
WHERE meta_purchase_sent = 1 
AND meta_purchase_sent_at > datetime('now', '-1 day');
```

---

## 🎯 PRÓXIMOS PASSOS

1. **Configurar pools com Meta Pixel**
   - Acesse cada pool de campanha
   - Configure Pixel ID e Access Token
   - Ative eventos necessários

2. **Atualizar campanhas no Meta Ads**
   - Use links dos pools ao invés de bots diretos
   - Configure parâmetros UTM
   - Se usar Cloaker, configure parâmetro `apx`

3. **Monitorar por 48h**
   - Verificar eventos no Meta Events Manager
   - Verificar logs da aplicação
   - Validar valores das Purchase events

4. **Otimizar campanhas**
   - Use dados consolidados para análise
   - Ajuste orçamentos baseado em ROAS
   - Crie lookalike audiences

---

## 📝 NOTAS IMPORTANTES

### **🔒 Segurança**
- Access Tokens são criptografados no banco
- Backup criado automaticamente antes da migração
- Rotas antigas de bot mantidas para retrocompatibilidade

### **⚡ Performance**
- Índices criados para queries otimizadas
- Eventos enviados de forma assíncrona
- Retry automático em falhas de rede

### **🎯 Arquitetura**
- 1 Campanha = 1 Pool = 1 Pixel
- Alta disponibilidade (bot cai, tracking continua)
- Dados consolidados para análise precisa

---

## 🆘 SUPORTE

Em caso de dúvidas ou problemas:

1. **Verificar logs**: `sudo journalctl -u grimbots -f`
2. **Verificar banco**: `sqlite3 instance/saas_bot_manager.db`
3. **Restaurar backup**: `cp instance/saas_bot_manager.db.backup_XXX instance/saas_bot_manager.db`
4. **Rollback Git**: `git reset --hard HEAD~1`

---

**🚀 IMPLEMENTAÇÃO COMPLETA - QI 300 + QI 240**

**Arquitetura profissional, escalável e de alta disponibilidade.**

---

*Última atualização: 2025-10-20*

