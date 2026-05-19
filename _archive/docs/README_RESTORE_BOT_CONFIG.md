# 🔧 Restaurar bot_config.html Completo

## 🎯 Objetivo

Restaurar o arquivo `templates/bot_config.html` para o estado funcional completo que estava antes dos commits serem removidos.

## 📋 Opções de Restauração

### Opção 1: Restaurar do Backup do Git (Recomendado)

O backup foi criado automaticamente antes do reset. Execute no servidor:

```bash
cd /root/grimbots
bash fix_bot_config_complete.sh
```

Este script vai:
1. Buscar no backup do Git (`backup-before-reset-*`)
2. Buscar no commit `9b48179` (antes do reset)
3. Buscar no reflog do Git
4. Restaurar o arquivo completo se encontrar

### Opção 2: Baixar do Servidor Atual

Se o arquivo no servidor (https://app.grimbots.online) estiver funcionando, baixe para o local:

**No seu computador local:**

```bash
bash download_bot_config_from_server.sh
```

Isso vai:
1. Fazer backup do arquivo local
2. Baixar do servidor via `scp`
3. Verificar se está completo (>4000 linhas)

### Opção 3: Restaurar Manualmente do Git

**No servidor:**

```bash
cd /root/grimbots

# Listar backups
git branch | grep backup

# Restaurar do backup (substitua BACKUP_NAME)
git show BACKUP_NAME:templates/bot_config.html > templates/bot_config.html

# Verificar
wc -l templates/bot_config.html
```

## ✅ Verificação

Após restaurar, verifique:

1. **Linhas do arquivo:**
   ```bash
   wc -l templates/bot_config.html
   ```
   Deve ter **~5000+ linhas**

2. **Testar no navegador:**
   - Acesse: https://app.grimbots.online/bots/48/config
   - Verifique se todas as tabs funcionam
   - Verifique se o flow editor funciona
   - Verifique se não há erros no console

3. **Verificar estrutura:**
   ```bash
   head -100 templates/bot_config.html
   tail -100 templates/bot_config.html
   ```

## 📝 Commit e Push

Após restaurar e verificar:

```bash
cd /root/grimbots

git add templates/bot_config.html
git commit -m "fix(bot_config): restore complete functional bot_config.html"
git push origin main
```

## 🚨 Se Nada Funcionar

Se nenhuma das opções funcionar, o arquivo precisa ser recriado manualmente baseado no template completo. Neste caso, será necessário:

1. Verificar o que estava no diff anterior
2. Recriar todas as seções:
   - CSS completo (order bumps, subscriptions, previews, flow editor)
   - HTML completo (todas as tabs)
   - JavaScript completo (todas as funções Alpine.js)

## 📞 Scripts Disponíveis

- `fix_bot_config_complete.sh` - Restaura do backup do Git (servidor)
- `download_bot_config_from_server.sh` - Baixa do servidor (local)
- `restore_from_server_or_backup.sh` - Tenta múltiplas fontes (servidor)

