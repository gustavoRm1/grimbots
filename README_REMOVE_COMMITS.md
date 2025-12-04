# 🗑️ Remover Commits Específicos do Git

Este guia explica como remover os commits específicos do histórico Git.

## 📋 Commits a Remover

- `b61ca1861a4963b1db33dc989b381667e7c7c059`
- `2f0130c7c4209d993934bf65f40a1c7a67a11543`
- `395c98a8670e97605c48bb51cd4c405ecf718874`
- `16e89642d726f9feb766114f85c10bf7439fd088`
- `6114b7f8275da4b68334c10145e64794ca7f5b81`
- `95ef66edfbe391ac078775c65bb9e076306276a5`
- `87b4c375203fb32c2ef493ab3143ede8a59d4278`

## 🚀 Método 1: Executar Script no Servidor (Recomendado)

### Opção A: Via SSH direto

```bash
# Copiar script para servidor
scp remove_commits_simple.sh root@app.grimbots.online:/root/

# Executar no servidor
ssh root@app.grimbots.online "cd /root/grimbots && bash /root/remove_commits_simple.sh"
```

### Opção B: Executar diretamente via SSH

```bash
ssh root@app.grimbots.online 'cd /root/grimbots && bash -s' < remove_commits_server.sh
```

## 🚀 Método 2: Manual (Passo a Passo)

### 1. Conectar ao servidor

```bash
ssh root@app.grimbots.online
cd /root/grimbots
```

### 2. Criar backup

```bash
git branch backup-antes-remover-commits-$(date +%Y%m%d_%H%M%S)
```

### 3. Verificar commits

```bash
git log --oneline | grep -E "b61ca18|2f0130c|395c98a|16e8964|6114b7f|95ef66e|87b4c37"
```

### 4. Encontrar o commit base

Encontre o commit mais antigo da lista e pegue o commit anterior a ele:

```bash
# Exemplo: se o commit mais antigo for b61ca18
git rev-parse b61ca1861a4963b1db33dc989b381667e7c7c059^
```

### 5. Iniciar rebase interativo

```bash
git rebase -i <COMMIT_BASE>
```

**Exemplo:**
```bash
git rebase -i b61ca1861a4963b1db33dc989b381667e7c7c059^
```

### 6. No editor que abrir

Altere `pick` para `drop` nas linhas dos commits que você quer remover:

```
pick abc1234 Mensagem do commit 1
drop b61ca18 Commit a remover 1    ← Altere 'pick' para 'drop'
pick def5678 Mensagem do commit 2
drop 2f0130c Commit a remover 2    ← Altere 'pick' para 'drop'
drop 395c98a Commit a remover 3    ← Altere 'pick' para 'drop'
...
```

### 7. Salvar e fechar o editor

- **Vim/Nano**: Salve com `:wq` (Vim) ou `Ctrl+X` depois `Y` (Nano)

### 8. Se houver conflitos

```bash
# Resolver conflitos manualmente
git add .
git rebase --continue
```

### 9. Force push (CUIDADO!)

```bash
# Verificar o branch atual
git branch --show-current

# Force push
git push origin <NOME_DO_BRANCH> --force
```

**⚠️ ATENÇÃO:** Force push reescreve o histórico no remoto. Certifique-se de que:
- Ninguém mais está trabalhando neste branch
- Você tem backup
- Você tem certeza do que está fazendo

## 🔄 Método 3: Usar Git Filter-Branch (Alternativa)

Se o rebase interativo não funcionar, você pode usar `git filter-branch`:

```bash
# Criar backup
git branch backup-filter-$(date +%Y%m%d_%H%M%S)

# Remover commits específicos
git filter-branch --force --index-filter \
  "git rm --cached --ignore-unmatch -r ." \
  --prune-empty --tag-name-filter cat -- \
  --all \
  --not $(git rev-parse --verify HEAD)

# Ou usar git filter-repo (mais moderno)
# git filter-repo --invert-paths --path <arquivo>
```

## ✅ Verificação

Após remover os commits, verifique:

```bash
# Verificar que os commits foram removidos
git log --oneline | grep -E "b61ca18|2f0130c|395c98a|16e8964|6114b7f|95ef66e|87b4c37"

# Não deve retornar nada
```

## 🆘 Rollback (Se algo der errado)

Se precisar voltar atrás:

```bash
# Voltar para o backup
git checkout backup-antes-remover-commits-XXXXXX
git branch -D <branch-atual>
git checkout -b <branch-atual>
```

Ou:

```bash
# Resetar para o commit antes do rebase
git reflog
git reset --hard HEAD@{N}  # Onde N é o número antes do rebase
```

## 📝 Notas Importantes

1. **Backup sempre primeiro**: O script cria backup automaticamente
2. **Force push é destrutivo**: Só faça se tiver certeza
3. **Commits já enviados**: Se os commits já foram enviados ao remoto, você precisará de force push
4. **Colaboradores**: Avise a equipe antes de fazer force push
5. **Commits mesclados**: Se os commits foram mesclados em outros branches, você precisará removê-los lá também

## 🎯 Scripts Disponíveis

- `remove_commits_simple.sh` - Script interativo simples
- `remove_commits_server.sh` - Script para executar via SSH
- `remove_commits.sh` - Script completo com mais opções

