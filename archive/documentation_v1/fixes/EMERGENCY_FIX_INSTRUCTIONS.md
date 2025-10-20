# 🚨 FIX EMERGENCIAL - Bot Users Archived

## PROBLEMA
Todos os bots estão falhando no `/start` com erro:
```
sqlite3.OperationalError: no such column: bot_users.archived
```

**Impacto:** ZERO conversões = ZERO dinheiro

---

## SOLUÇÃO (5 minutos)

### 1. Conectar no servidor
```bash
ssh root@grimbots
```

### 2. Ir para o diretório do projeto
```bash
cd /root/grimbots
```

### 3. Ativar ambiente virtual
```bash
source venv/bin/activate
```

### 4. Fazer backup do banco (OBRIGATÓRIO)
```bash
cp instance/saas_bot_manager.db instance/saas_bot_manager.db.backup_$(date +%Y%m%d_%H%M%S)
```

### 5. Executar migração
```bash
python fix_production_emergency.py
```

**Output esperado:**
```
🚨 EMERGENCY FIX - BotUser Archived Fields
================================================================================
✅ Coluna 'archived' adicionada
✅ Coluna 'archived_reason' adicionada
✅ Coluna 'archived_at' adicionada
✅ Índice criado
================================================================================
✅ MIGRAÇÃO CONCLUÍDA COM SUCESSO!
```

### 6. Reiniciar todos os bots
```bash
pm2 restart all
```

### 7. Verificar logs em tempo real
```bash
pm2 logs
```

### 8. Testar comando /start
- Abra qualquer bot do Telegram
- Envie `/start`
- Deve funcionar normalmente

---

## VALIDAÇÃO

Execute para verificar se está OK:
```bash
sqlite3 instance/saas_bot_manager.db "PRAGMA table_info(bot_users);" | grep archived
```

**Output esperado:**
```
26|archived|BOOLEAN|0|0|0
27|archived_reason|VARCHAR(100)|0||0
28|archived_at|DATETIME|0||0
```

---

## SE ALGO DER ERRADO

### Restaurar backup:
```bash
cp instance/saas_bot_manager.db.backup_XXXXXX instance/saas_bot_manager.db
pm2 restart all
```

### Reverter código temporariamente:
```bash
git stash
pm2 restart all
```

---

## CAUSA RAIZ

Deploy foi feito com `models.py` atualizado (define colunas `archived`), mas **migração não foi executada**.

SQLAlchemy tentou fazer SELECT com colunas que não existem no banco → crash.

---

## PREVENÇÃO FUTURA

Sempre que alterar `models.py`:
1. Criar script de migração
2. Testar localmente
3. **EXECUTAR migração em produção ANTES do deploy**
4. Depois fazer deploy do código

**Ordem correta:**
```bash
# 1. Migração
python migrate_xxx.py

# 2. Depois o código
git pull
pm2 restart all
```

