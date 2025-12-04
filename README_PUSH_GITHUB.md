# 📤 Como Fazer Force Push para GitHub

O GitHub não aceita mais senha. Você precisa usar um **Personal Access Token (PAT)**.

## 🔑 Criar Token no GitHub

1. Acesse: https://github.com/settings/tokens
2. Clique em **"Generate new token"** → **"Generate new token (classic)"**
3. Dê um nome: `grimbots-push`
4. Selecione permissões:
   - ✅ **repo** (acesso completo aos repositórios)
5. Clique em **"Generate token"**
6. **COPIE O TOKEN** (você só verá uma vez!)

## 🚀 Métodos para Fazer Push

### Método 1: Script Interativo (Recomendado)

```bash
bash push_to_github.sh
```

O script vai:
- Detectar se usa HTTPS ou SSH
- Oferecer opções de autenticação
- Fazer o push automaticamente

### Método 2: Usar Token Diretamente

```bash
# Substitua SEU_TOKEN pelo token que você copiou
GITHUB_TOKEN=SEU_TOKEN bash push_with_token.sh
```

### Método 3: Configurar Token Permanentemente

```bash
# Criar token (copiar do GitHub)
GITHUB_TOKEN=seu_token_aqui

# Configurar credential helper
git config --global credential.helper store
echo "https://$(git config user.name):${GITHUB_TOKEN}@github.com" > ~/.git-credentials
chmod 600 ~/.git-credentials

# Agora pode fazer push normal
git push origin main --force
```

### Método 4: Converter para SSH (Mais Seguro)

Se você tem chave SSH configurada no GitHub:

```bash
# Ver remote atual
git remote get-url origin

# Se for HTTPS, converter para SSH
git remote set-url origin git@github.com:gustavoRm1/grimbots.git

# Fazer push (não pede senha)
git push origin main --force
```

## ⚠️ Importante

- **Token é sensível**: Não compartilhe ou commite no Git
- **Permissões mínimas**: Use apenas `repo` se possível
- **Token pode expirar**: Se expirar, crie um novo
- **Force push é destrutivo**: Certifique-se antes de executar

## ✅ Verificação

Após o push, verifique no GitHub:

```bash
# Ver commits no GitHub
git ls-remote origin main
```

Ou acesse: https://github.com/gustavoRm1/grimbots

## 🆘 Problemas Comuns

### "Invalid username or token"
- Token expirado ou inválido
- Solução: Crie um novo token

### "Permission denied"
- Token sem permissão `repo`
- Solução: Crie token com permissão `repo`

### "Authentication failed"
- URL do remote incorreta
- Solução: Verifique com `git remote get-url origin`

