# 🔄 Restaurar bot_config.html do Commit Específico

## Comandos para Executar no Servidor (SSH)

### Opção 1: Script Automático (Recomendado)

```bash
cd /root/grimbots
chmod +x restore_bot_config.sh
./restore_bot_config.sh
```

### Opção 2: Comandos Manuais

```bash
cd /root/grimbots

# 1. Encontrar o commit
git log --all --oneline --grep="add safe strip utility" | head -1

# 2. Se encontrar, copie o hash (primeiros 7 caracteres) e execute:
git checkout <HASH> -- templates/bot_config.html

# 3. Verificar se restaurou corretamente
ls -lh templates/bot_config.html
head -20 templates/bot_config.html

# 4. Se estiver correto, fazer commit (opcional)
git add templates/bot_config.html
git commit -m "Restore bot_config.html from commit <HASH>"
```

### Opção 3: Busca Alternativa

Se não encontrar pelo grep, tente:

```bash
cd /root/grimbots

# Listar últimos commits que modificaram bot_config.html
git log --all --oneline -- templates/bot_config.html | head -20

# Escolher o commit desejado e restaurar
git checkout <HASH_DO_COMMIT> -- templates/bot_config.html
```

### Opção 4: Busca por Data ou Autor

```bash
cd /root/grimbots

# Buscar commits recentes
git log --all --oneline --since="1 week ago" -- templates/bot_config.html

# Ou buscar por autor
git log --all --oneline --author="seu-email" -- templates/bot_config.html
```

## ⚠️ Importante

Após restaurar, verifique se o arquivo está correto:

```bash
# Verificar tamanho (deve ter mais de 5000 linhas)
wc -l templates/bot_config.html

# Verificar se tem a estrutura correta
grep -n "botConfigApp" templates/bot_config.html | head -5
grep -n "flow_editor" templates/bot_config.html | head -5
```

## 🔄 Reiniciar Aplicação

Após restaurar, reinicie o Flask:

```bash
# Se usar systemd
sudo systemctl restart grimbots

# Ou se usar supervisor
sudo supervisorctl restart grimbots

# Ou se rodar manualmente, reinicie o processo
```

